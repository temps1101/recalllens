#!/usr/bin/env python3
"""Batch evaluation for the Recalllens OpenCV 5 scene matcher."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import ExifTags, Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

MAXIMUM_DIMENSION = 960
MAXIMUM_FEATURES = 1600
DEFAULT_THRESHOLD = 0.62
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".heic", ".heif", ".png", ".tif", ".tiff"}


@dataclass
class Features:
    keypoints: list[cv2.KeyPoint]
    descriptors: np.ndarray | None
    shape: tuple[int, int]


def image_paths(directory: Path) -> list[Path]:
    return sorted(path for path in directory.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES)


def read_gray(path: Path) -> np.ndarray:
    with Image.open(path) as source:
        normalized = ImageOps.exif_transpose(source).convert("L")
        image = np.asarray(normalized)
    largest = max(image.shape)
    if largest > MAXIMUM_DIMENSION:
        scale = MAXIMUM_DIMENSION / largest
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return image


def extract_features(path: Path) -> Features:
    image = read_gray(path)
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
    keypoints, descriptors = orb.detectAndCompute(image, None)
    return Features(keypoints or [], descriptors, image.shape)


def coverage(points: np.ndarray, shape: tuple[int, int]) -> float:
    if len(points) < 3:
        return 0.0
    area = float(shape[0] * shape[1])
    return min(1.0, float(cv2.contourArea(cv2.convexHull(points.astype(np.float32)))) / area) if area else 0.0


def compare(query: Features, reference: Features) -> dict[str, float | int]:
    if query.descriptors is None or reference.descriptors is None:
        return {"similarity": 0.0, "good_matches": 0, "inliers": 0, "inlier_ratio": 0.0, "coverage": 0.0}
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(query.descriptors, reference.descriptors, k=2)
    good = [pair[0] for pair in pairs if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance]
    if len(good) < 8:
        return {
            "similarity": round(0.18 * min(1.0, len(good) / 24.0), 6),
            "good_matches": len(good),
            "inliers": 0,
            "inlier_ratio": 0.0,
            "coverage": 0.0,
        }
    query_xy = np.float32([query.keypoints[item.queryIdx].pt for item in good])
    reference_xy = np.float32([reference.keypoints[item.trainIdx].pt for item in good])
    _, mask = cv2.findHomography(query_xy, reference_xy, cv2.RANSAC, 4.0)
    inlier_mask = mask.ravel().astype(bool) if mask is not None else np.zeros(len(good), dtype=bool)
    inliers = int(inlier_mask.sum())
    inlier_ratio = inliers / len(good)
    support = min(1.0, inliers / 36.0)
    spatial_coverage = min(1.0, coverage(query_xy[inlier_mask], query.shape) / 0.22)
    similarity = min(1.0, max(0.0, 0.52 * inlier_ratio + 0.33 * support + 0.15 * spatial_coverage))
    return {
        "similarity": round(similarity, 6),
        "good_matches": len(good),
        "inliers": inliers,
        "inlier_ratio": round(inlier_ratio, 6),
        "coverage": round(spatial_coverage, 6),
    }


def rational(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def coordinate(values: Any, reference: str | None) -> float | None:
    if not values or len(values) != 3:
        return None
    degrees, minutes, seconds = (rational(item) for item in values)
    if None in (degrees, minutes, seconds):
        return None
    result = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
    return -result if reference in {"S", "W"} else result


def exif_metadata(path: Path, role: str, scene: str = "") -> dict[str, Any]:
    row: dict[str, Any] = {
        "path": str(path), "role": role, "scene": scene, "captured_at": "",
        "latitude": "", "longitude": "", "altitude_m": "", "camera_make": "",
        "camera_model": "", "focal_length_mm": "", "exposure_seconds": "", "iso": "",
        "width": "", "height": "", "metadata_error": "",
    }
    try:
        with Image.open(path) as image:
            row["width"], row["height"] = image.size
            exif = image.getexif()
            row["camera_make"] = str(exif.get(271, ""))
            row["camera_model"] = str(exif.get(272, ""))
            row["focal_length_mm"] = rational(exif.get(37386)) or ""
            row["exposure_seconds"] = rational(exif.get(33434)) or ""
            row["iso"] = exif.get(34855, "")
            row["captured_at"] = str(exif.get(36867) or exif.get(36868) or exif.get(306) or "")
            try:
                gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
            except (KeyError, TypeError, AttributeError):
                gps = {}
            row["latitude"] = coordinate(gps.get(2), gps.get(1)) or ""
            row["longitude"] = coordinate(gps.get(4), gps.get(3)) or ""
            altitude = rational(gps.get(6))
            if altitude is not None:
                row["altitude_m"] = -altitude if gps.get(5) == 1 else altitude
    except Exception as error:  # Preserve the rest of a batch when one file has bad metadata.
        row["metadata_error"] = str(error)
    return row


def parse_exif_datetime(value: str) -> datetime | None:
    for pattern in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, pattern)
        except (TypeError, ValueError):
            pass
    return None


def haversine_meters(first: dict[str, Any], second: dict[str, Any]) -> float | None:
    try:
        lat1, lon1 = math.radians(float(first["latitude"])), math.radians(float(first["longitude"]))
        lat2, lon2 = math.radians(float(second["latitude"])), math.radians(float(second["longitude"]))
    except (TypeError, ValueError):
        return None
    dlat, dlon = lat2 - lat1, lon2 - lon1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(value))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    return float(np.percentile(np.asarray(values), probability * 100))


def summarize_predictions(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    positives = [row for row in predictions if row["expected_match"]]
    negatives = [row for row in predictions if not row["expected_match"]]
    true_unlocks = sum(row["authorized"] and row["predicted_scene"] == row["expected_scene"] for row in positives)
    false_unlocks = sum(bool(row["authorized"]) for row in negatives)
    wrong_reference = sum(row["authorized"] and row["predicted_scene"] != row["expected_scene"] for row in positives)
    durations = [row["duration_ms"] for row in predictions]
    return {
        "queries": len(predictions), "positive_queries": len(positives), "negative_queries": len(negatives),
        "accuracy": sum(bool(row["correct"]) for row in predictions) / len(predictions) if predictions else None,
        "top1_positive_accuracy": sum(row["predicted_scene"] == row["expected_scene"] for row in positives) / len(positives) if positives else None,
        "true_unlocks": true_unlocks, "true_unlock_rate": true_unlocks / len(positives) if positives else None,
        "negative_false_unlocks": false_unlocks, "false_unlock_rate": false_unlocks / len(negatives) if negatives else None,
        "wrong_reference_unlocks": wrong_reference,
        "unsafe_unlocks": false_unlocks + wrong_reference,
        "unsafe_unlock_rate_all_queries": (false_unlocks + wrong_reference) / len(predictions) if predictions else None,
        "median_query_ms": statistics.median(durations) if durations else None,
        "p95_query_ms": percentile(durations, 0.95),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Recalllens images with the production OpenCV 5 matcher.")
    parser.add_argument("--data", type=Path, default=Path(__file__).parents[1] / "data")
    parser.add_argument("--output", type=Path, default=Path(__file__).parents[1] / "output")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args()
    references_dir, queries_dir = args.data / "references", args.data / "queries"
    labels_path = args.data / "labels.csv"
    if not labels_path.exists():
        raise SystemExit(f"Missing {labels_path}. Copy labels.example.csv to labels.csv and label every query.")
    with labels_path.open(newline="", encoding="utf-8-sig") as source:
        labels = list(csv.DictReader(source))
    if not labels:
        raise SystemExit("No labeled queries; empty datasets are not evaluation results.")
    if len({row["query_path"].strip() for row in labels}) != len(labels):
        raise SystemExit("Duplicate query paths: each query must belong to exactly one split.")
    reference_paths = image_paths(references_dir)
    if not reference_paths:
        raise SystemExit(f"No reference images found in {references_dir}")
    reference_by_scene = {path.stem: path for path in reference_paths}
    if len(reference_by_scene) != len(reference_paths):
        raise SystemExit("Reference scene IDs must be unique filename stems.")
    for label in labels:
        expected = label.get("expected_scene", "").strip()
        if not expected or (expected.upper() != "NONE" and expected not in reference_by_scene):
            raise SystemExit("Each query needs NONE or a valid reference scene ID.")
    query_by_relative = {str(path.relative_to(args.data)): path for path in image_paths(queries_dir)}
    args.output.mkdir(parents=True, exist_ok=True)

    metadata: list[dict[str, Any]] = []
    reference_metadata: dict[str, dict[str, Any]] = {}
    reference_features: dict[str, Features] = {}
    for scene, path in reference_by_scene.items():
        item = exif_metadata(path, "reference", scene)
        metadata.append(item)
        reference_metadata[scene] = item
        reference_features[scene] = extract_features(path)

    comparisons: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    durations: list[float] = []
    for label in labels:
        relative = label["query_path"].strip()
        query_path = query_by_relative.get(relative)
        if query_path is None:
            raise SystemExit(f"Labeled query not found: {relative}")
        query_meta = exif_metadata(query_path, "query", label.get("expected_scene", ""))
        metadata.append(query_meta)
        started = time.perf_counter()
        query_features = extract_features(query_path)
        query_rows: list[dict[str, Any]] = []
        for scene, reference in reference_features.items():
            result = compare(query_features, reference)
            reference_meta = reference_metadata[scene]
            distance = haversine_meters(query_meta, reference_meta)
            query_time = parse_exif_datetime(str(query_meta["captured_at"]))
            reference_time = parse_exif_datetime(str(reference_meta["captured_at"]))
            elapsed = abs((query_time - reference_time).total_seconds()) / 3600 if query_time and reference_time else None
            row = {
                "query_path": relative, "reference_scene": scene,
                "expected_scene": label.get("expected_scene", ""), "condition": label.get("condition", ""),
                "split": label.get("split", ""), **result,
                "gps_distance_m": "" if distance is None else round(distance, 2),
                "elapsed_hours": "" if elapsed is None else round(elapsed, 3),
            }
            comparisons.append(row)
            query_rows.append(row)
        duration_ms = (time.perf_counter() - started) * 1000
        durations.append(duration_ms)
        best = max(query_rows, key=lambda item: float(item["similarity"]))
        authorized = float(best["similarity"]) >= args.threshold
        expected = label.get("expected_scene", "").strip()
        expected_match = bool(expected and expected.upper() != "NONE")
        correct = (authorized and best["reference_scene"] == expected) if expected_match else not authorized
        predictions.append({
            "query_path": relative, "expected_scene": expected, "condition": label.get("condition", ""),
            "split": label.get("split", ""), "predicted_scene": best["reference_scene"],
            "top_score": best["similarity"], "threshold": args.threshold,
            "authorized": authorized, "expected_match": expected_match, "correct": correct,
            "duration_ms": round(duration_ms, 3), "gps_distance_m": best["gps_distance_m"],
            "elapsed_hours": best["elapsed_hours"],
        })

    summary = {
        "opencv_version": cv2.__version__, "threshold": args.threshold,
        "references": len(reference_paths), "queries": len(predictions), "comparisons": len(comparisons),
        "by_split": {split: summarize_predictions([r for r in predictions if (r["split"] or "unassigned") == split])
                     for split in sorted({r["split"] or "unassigned" for r in predictions})},
        "note": "Splits are reported separately. Photo/scene/session independence must also be checked in dataset construction.",
        "images_with_gps": sum(bool(row["latitude"] and row["longitude"]) for row in metadata),
        "images_with_capture_time": sum(bool(row["captured_at"]) for row in metadata),
    }
    write_csv(args.output / "image_metadata.csv", metadata)
    write_csv(args.output / "comparisons.csv", comparisons)
    write_csv(args.output / "predictions.csv", predictions)
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
