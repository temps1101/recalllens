"""AWS Lambda handler for privacy-bounded OpenCV 5 scene verification."""

from __future__ import annotations

import base64
import binascii
import hmac
import json
import os
import struct
import time
import uuid
from typing import Any

os.environ.setdefault("OPENCV_IO_MAX_IMAGE_PIXELS", "4000000")
import cv2
import numpy as np

MAX_ENCODED_IMAGE_BYTES = 2_000_000
MAXIMUM_DIMENSION = 960
MAXIMUM_FEATURES = 1600
MAX_FEATURE_BYTES = 256_000
FEATURE_MAGIC = 0x57424F35
FEATURE_VERSION = 1
FEATURE_HEADER = struct.Struct("<IIiiiii")
UNLOCK_THRESHOLD = float(os.environ.get("UNLOCK_THRESHOLD", "0.62"))


def _response(status: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json",
            "cache-control": "no-store",
        },
        "body": json.dumps(payload, separators=(",", ":")),
    }


def _decode_image(encoded: Any) -> np.ndarray:
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("queryImage is required.")
    if len(encoded) > MAX_ENCODED_IMAGE_BYTES:
        raise ValueError("Image payload exceeds the 2 MB encoded limit.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("Image payload is not valid base64.") from error
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None or image.size == 0:
        raise ValueError("Image payload is not a supported image.")
    largest = max(image.shape)
    if largest > MAXIMUM_DIMENSION:
        scale = MAXIMUM_DIMENSION / largest
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return image


def _coverage(points: np.ndarray, shape: tuple[int, ...]) -> float:
    if len(points) < 3:
        return 0.0
    hull = cv2.convexHull(points.astype(np.float32))
    image_area = float(shape[0] * shape[1])
    return min(1.0, float(cv2.contourArea(hull)) / image_area) if image_area else 0.0


def _reference_id(value: Any) -> str:
    try:
        return str(uuid.UUID(str(value))).lower()
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError("referenceId must be a UUID.") from error


def _decode_feature_blob(encoded: Any) -> bytes:
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("featureData is required.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("featureData is not valid base64.") from error
    if len(raw) > MAX_FEATURE_BYTES:
        raise ValueError("featureData exceeds the 256 KB limit.")
    _unpack_features(raw)
    return raw


def _unpack_features(raw: bytes) -> tuple[list[cv2.KeyPoint], np.ndarray, tuple[int, int]]:
    if len(raw) < FEATURE_HEADER.size:
        raise ValueError("OpenCV feature signature is truncated.")
    magic, version, width, height, rows, columns, data_type = FEATURE_HEADER.unpack_from(raw)
    if (
        magic != FEATURE_MAGIC
        or version != FEATURE_VERSION
        or width <= 0
        or height <= 0
        or rows <= 0
        or rows > MAXIMUM_FEATURES
        or columns != 32
        or data_type != 0
    ):
        raise ValueError("OpenCV feature signature is invalid.")
    point_bytes = rows * 8
    descriptor_bytes = rows * columns
    expected = FEATURE_HEADER.size + point_bytes + descriptor_bytes
    if len(raw) != expected:
        raise ValueError("OpenCV feature signature has an invalid length.")
    xy = np.frombuffer(raw, dtype="<f4", count=rows * 2, offset=FEATURE_HEADER.size).reshape(rows, 2)
    descriptors = np.frombuffer(
        raw,
        dtype=np.uint8,
        count=descriptor_bytes,
        offset=FEATURE_HEADER.size + point_bytes,
    ).reshape(rows, columns).copy()
    keypoints = [cv2.KeyPoint(float(x), float(y), 31.0) for x, y in xy]
    return keypoints, descriptors, (height, width)


def _table():
    import boto3

    table_name = os.environ.get("REFERENCE_TABLE", "")
    if not table_name:
        raise RuntimeError("REFERENCE_TABLE is not configured.")
    return boto3.resource("dynamodb").Table(table_name)


def _store_reference(reference_id: str, feature_blob: bytes) -> None:
    now = int(time.time())
    _table().put_item(
        Item={
            "referenceId": reference_id,
            "featureData": feature_blob,
            "algorithm": "opencv-5-orb-v1",
            "createdAt": now,
            "expiresAt": now + 30 * 24 * 60 * 60,
        }
    )


def _load_reference(reference_id: str) -> bytes | None:
    item = _table().get_item(Key={"referenceId": reference_id}, ConsistentRead=True).get("Item")
    # DynamoDB TTL deletion is asynchronous; enforce expiry at verification time.
    if not item or "featureData" not in item:
        return None
    expires_at = item.get("expiresAt")
    if expires_at is None or float(expires_at) <= time.time():
        return None
    return bytes(item["featureData"])


def _match_features(
    query_points: list[cv2.KeyPoint],
    query_descriptors: np.ndarray | None,
    query_shape: tuple[int, ...],
    reference_points: list[cv2.KeyPoint],
    reference_descriptors: np.ndarray | None,
) -> dict[str, Any]:
    if query_descriptors is None or reference_descriptors is None:
        return {"similarity": 0.0, "goodMatches": 0, "inliers": 0, "inlierRatio": 0.0}

    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(
        query_descriptors, reference_descriptors, k=2
    )
    good = [pair[0] for pair in pairs if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance]
    if len(good) < 8:
        return {
            "similarity": round(0.18 * min(1.0, len(good) / 24.0), 6),
            "goodMatches": len(good),
            "inliers": 0,
            "inlierRatio": 0.0,
        }

    query_xy = np.float32([query_points[item.queryIdx].pt for item in good])
    reference_xy = np.float32([reference_points[item.trainIdx].pt for item in good])
    _, mask = cv2.findHomography(query_xy, reference_xy, cv2.RANSAC, 4.0)
    inlier_mask = mask.ravel().astype(bool) if mask is not None else np.zeros(len(good), dtype=bool)
    inliers = int(inlier_mask.sum())
    inlier_ratio = inliers / len(good)
    support = min(1.0, inliers / 36.0)
    coverage = min(1.0, _coverage(query_xy[inlier_mask], query_shape) / 0.22)
    similarity = min(1.0, max(0.0, 0.52 * inlier_ratio + 0.33 * support + 0.15 * coverage))
    return {
        "similarity": round(similarity, 6),
        "goodMatches": len(good),
        "inliers": inliers,
        "inlierRatio": round(inlier_ratio, 6),
        "coverage": round(coverage, 6),
    }


def verify(query: np.ndarray, reference: np.ndarray) -> dict[str, Any]:
    orb = cv2.ORB.create(
        nfeatures=MAXIMUM_FEATURES,
        scaleFactor=1.2,
        nlevels=8,
        edgeThreshold=31,
        firstLevel=0,
        WTA_K=2,
        scoreType=cv2.ORB_HARRIS_SCORE,
        patchSize=31,
        fastThreshold=12,
    )
    query_points, query_descriptors = orb.detectAndCompute(query, None)
    reference_points, reference_descriptors = orb.detectAndCompute(reference, None)
    return _match_features(
        query_points,
        query_descriptors,
        query.shape,
        reference_points,
        reference_descriptors,
    )


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    expected_token = os.environ.get("API_TOKEN", "")
    headers = {str(key).lower(): str(value) for key, value in (event.get("headers") or {}).items()}
    supplied_token = headers.get("x-api-key", "")
    path = event.get("rawPath") or event.get("path") or "/verify"
    method = (event.get("requestContext", {}).get("http", {}).get("method") or "POST").upper()
    if path.endswith('/shares') or '/shares/' in path or '/s/' in path:
        import sharing
        return sharing.handle(event, path, method, bool(expected_token) and hmac.compare_digest(supplied_token, expected_token))
    if not expected_token or not hmac.compare_digest(supplied_token, expected_token):
        return _response(401, {"error": "Unauthorized"})

    started = time.perf_counter()
    try:
        body = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode("utf-8")
        payload = json.loads(body)
        path = event.get("rawPath") or event.get("path") or "/verify"
        method = (event.get("requestContext", {}).get("http", {}).get("method") or "POST").upper()
        if path.endswith("/references") and method == "POST":
            reference_id = _reference_id(payload.get("referenceId"))
            feature_blob = _decode_feature_blob(payload.get("featureData"))
            _store_reference(reference_id, feature_blob)
            return _response(
                201,
                {
                    "referenceId": reference_id,
                    "registered": True,
                    "algorithm": "opencv-5-orb-v1",
                    "imageStored": False,
                    "expiresInDays": 30,
                },
            )

        reference_id = _reference_id(payload.get("referenceId"))
        feature_blob = _load_reference(reference_id)
        if feature_blob is None:
            return _response(404, {"error": "Reference signature not found."})
        query = _decode_image(payload.get("queryImage"))
        orb = cv2.ORB.create(
            nfeatures=MAXIMUM_FEATURES,
            scaleFactor=1.2,
            nlevels=8,
            edgeThreshold=31,
            firstLevel=0,
            WTA_K=2,
            scoreType=cv2.ORB_HARRIS_SCORE,
            patchSize=31,
            fastThreshold=12,
        )
        query_points, query_descriptors = orb.detectAndCompute(query, None)
        reference_points, reference_descriptors, _ = _unpack_features(feature_blob)
        result = _match_features(
            query_points,
            query_descriptors,
            query.shape,
            reference_points,
            reference_descriptors,
        )
        result.update(
            {
                "authorized": result["similarity"] >= UNLOCK_THRESHOLD,
                "referenceId": reference_id,
                "unlockThreshold": UNLOCK_THRESHOLD,
                "registry": "DynamoDB",
            }
        )
    except (ValueError, json.JSONDecodeError) as error:
        return _response(400, {"error": str(error)})
    except cv2.error:
        return _response(422, {"error": "OpenCV could not analyze the supplied images."})

    result.update(
        {
            "engine": f"OpenCV {cv2.__version__} ORB + RANSAC",
            "durationMs": round((time.perf_counter() - started) * 1000, 2),
            "imagesRetained": False,
            "referenceSignatureStored": True,
        }
    )
    return _response(200, result)
