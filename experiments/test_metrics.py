import sys
import unittest
from pathlib import Path
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "src"))
from recall_lens_eval import summarize_predictions
from recall_lens_eval import Features, compare
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "aws"))
import handler


class MetricsTests(unittest.TestCase):
    def test_wrong_photo_unlock_is_counted_even_for_a_positive_query(self):
        samples = [
            dict(expected_match=True, expected_scene="A", predicted_scene="B", authorized=True, correct=False, duration_ms=1),
            dict(expected_match=False, expected_scene="NONE", predicted_scene="B", authorized=True, correct=False, duration_ms=2),
            dict(expected_match=True, expected_scene="A", predicted_scene="A", authorized=False, correct=False, duration_ms=3),
            dict(expected_match=True, expected_scene="A", predicted_scene="A", authorized=True, correct=True, duration_ms=4),
        ]
        summary = summarize_predictions(samples)
        self.assertEqual(summary["unsafe_unlocks"], 2)
        self.assertEqual(summary["wrong_reference_unlocks"], 1)
        self.assertEqual(summary["negative_false_unlocks"], 1)
        self.assertEqual(summary["top1_positive_accuracy"], 2/3)
        self.assertEqual(summary["true_unlock_rate"], 1/3)
        self.assertEqual(summary["accuracy"], .25)

    def test_empty_has_no_accuracy(self):
        self.assertIsNone(summarize_predictions([])["accuracy"])

    def test_offline_scoring_agrees_with_lambda_on_identical_feature_inputs(self):
        rng = np.random.default_rng(30)
        image = rng.integers(0, 256, (480, 640), dtype=np.uint8)
        orb = cv2.ORB.create(nfeatures=1600, fastThreshold=12)
        rp, rd = orb.detectAndCompute(image, None)
        queries = [image, cv2.GaussianBlur(image, (9, 9), 2), np.zeros_like(image)]
        for query in queries:
            qp, qd = orb.detectAndCompute(query, None)
            cv2.setRNGSeed(42)
            offline = compare(Features(qp, qd, query.shape), Features(rp, rd, image.shape))
            cv2.setRNGSeed(42)
            cloud = handler._match_features(qp, qd, query.shape, rp, rd)
            self.assertEqual(offline["similarity"], cloud["similarity"])
            self.assertEqual(offline["inliers"], cloud["inliers"])


if __name__ == "__main__":
    unittest.main()
