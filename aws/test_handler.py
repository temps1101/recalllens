import base64
import json
import os
import struct
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

import handler

REFERENCE_ID = "96c95be0-8796-4d7b-b44c-bdf0be13ed46"


def encoded_test_image(shift_x: int = 0) -> str:
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    generator = np.random.default_rng(7)
    for index in range(120):
        x = int(generator.integers(25, 615))
        y = int(generator.integers(25, 455))
        radius = int(generator.integers(3, 15))
        shade = int(generator.integers(100, 256))
        cv2.circle(image, (x, y), radius, (shade, shade, shade), 2)
        if index % 12 == 0:
            cv2.putText(image, str(index), (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    if shift_x:
        image = cv2.warpAffine(image, np.float32([[1, 0, shift_x], [0, 1, 0]]), (640, 480))
    ok, jpeg = cv2.imencode(".jpg", image)
    assert ok
    return base64.b64encode(jpeg).decode("ascii")


def encoded_features(image_base64: str) -> str:
    raw = base64.b64decode(image_base64)
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    orb = cv2.ORB.create(
        nfeatures=1600,
        scaleFactor=1.2,
        nlevels=8,
        edgeThreshold=31,
        firstLevel=0,
        WTA_K=2,
        scoreType=cv2.ORB_HARRIS_SCORE,
        patchSize=31,
        fastThreshold=12,
    )
    points, descriptors = orb.detectAndCompute(image, None)
    header = struct.pack(
        "<IIiiiii",
        handler.FEATURE_MAGIC,
        handler.FEATURE_VERSION,
        image.shape[1],
        image.shape[0],
        len(points),
        descriptors.shape[1],
        0,
    )
    xy = np.asarray([point.pt for point in points], dtype="<f4").tobytes()
    return base64.b64encode(header + xy + descriptors.tobytes()).decode("ascii")


class HandlerTests(unittest.TestCase):
    def setUp(self):
        os.environ["API_TOKEN"] = "test-token-with-at-least-24-chars"
        self.references = {}
        self.store_patch = patch.object(
            handler,
            "_store_reference",
            side_effect=lambda reference_id, blob: self.references.__setitem__(reference_id, blob),
        )
        self.load_patch = patch.object(
            handler,
            "_load_reference",
            side_effect=lambda reference_id: self.references.get(reference_id),
        )
        self.store_patch.start()
        self.load_patch.start()

    def tearDown(self):
        self.store_patch.stop()
        self.load_patch.stop()

    def invoke(self, path: str, payload: dict, token: str | None = None):
        return handler.lambda_handler(
            {
                "rawPath": path,
                "requestContext": {"http": {"method": "POST"}},
                "headers": {"x-api-key": token or os.environ["API_TOKEN"]},
                "body": json.dumps(payload),
            },
            None,
        )

    def enroll(self, image: str):
        return self.invoke(
            "/prod/references",
            {"referenceId": REFERENCE_ID, "featureData": encoded_features(image)},
        )

    def request(self, query: str, token: str | None = None):
        return self.invoke(
            "/prod/verify",
            {"queryImage": query, "referenceId": REFERENCE_ID},
            token,
        )

    def test_same_scene_scores_as_match(self):
        enrolled = self.enroll(encoded_test_image(8))
        self.assertEqual(enrolled["statusCode"], 201)
        response = self.request(encoded_test_image())
        body = json.loads(response["body"])
        self.assertEqual(response["statusCode"], 200)
        self.assertTrue(body["authorized"])
        self.assertGreater(body["similarity"], 0.62)
        self.assertGreater(body["inliers"], 20)
        self.assertFalse(body["imagesRetained"])
        self.assertTrue(body["referenceSignatureStored"])
        self.assertEqual(body["registry"], "DynamoDB")
        self.assertTrue(body["engine"].startswith("OpenCV 5."))

    def test_unrelated_scene_does_not_match(self):
        self.enroll(encoded_test_image())
        noise = np.random.default_rng(42).integers(0, 255, (480, 640, 3), dtype=np.uint8)
        ok, jpeg = cv2.imencode(".jpg", noise)
        self.assertTrue(ok)
        unrelated = base64.b64encode(jpeg).decode("ascii")
        response = self.request(unrelated)
        body = json.loads(response["body"])
        self.assertFalse(body["authorized"])
        self.assertLess(body["similarity"], 0.62)

    def test_rejects_wrong_token(self):
        response = self.request(encoded_test_image(), token="wrong")
        self.assertEqual(response["statusCode"], 401)

    def test_missing_reference_fails_closed(self):
        response = self.request(encoded_test_image())
        self.assertEqual(response["statusCode"], 404)


class ReferenceExpiryTests(unittest.TestCase):
    def test_expiry_boundary_is_enforced_before_ttl_deletion(self):
        table = MagicMock()
        with patch.object(handler, "_table", return_value=table), patch.object(handler.time, "time", return_value=1000):
            for expiry, expected in [(1001, b"signature"), (1000, None), (999, None), (None, None)]:
                with self.subTest(expiry=expiry):
                    item = {"featureData": b"signature"}
                    if expiry is not None:
                        item["expiresAt"] = expiry
                    table.get_item.return_value = {"Item": item}
                    self.assertEqual(handler._load_reference(REFERENCE_ID), expected)


if __name__ == "__main__":
    unittest.main()
