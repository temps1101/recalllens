#!/usr/bin/env python3
"""Offline photographic stress test and selected human-labeled pair audit.

No images are uploaded. Synthetic queries are NOT new captures or field trials.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments/src"))
from recall_lens_eval import Features, compare, image_paths, read_gray, write_csv

CONDITIONS = ["identity_control", "dim_45pct", "blur_sigma3", "rotation25", "perspective15pct", "crop65pct", "occlusion40pct"]
THRESHOLD = 0.62
PROTOCOL = {
    "version": 1, "threshold": THRESHOLD, "seed": 20261026,
    "conditions": CONDITIONS,
    "methods": {"geometric": "Unchanged ORB + RANSAC score, threshold 0.62",
                "descriptor_support": "Ablation: min(ratio-test matches / 36, 1), threshold 0.62; not independently calibrated"},
    "sampling": "All supplied reference stills plus up to 512 locally available valid-GPS library originals, ordered by SHA256(UUID), exact-file deduplicated before scoring",
    "limitations": ["Synthetic transformations are not new captures or revisit trials",
                    "Human pair labels were selected through the production matcher and are exploratory",
                    "Bidirectional results share the same pair; they are not independent observations",
                    "Desktop pair verification excludes camera, temporal stabilization, network and retrieval ranking",
                    "Different photographs are not automatically labeled as different scenes"],
}


def rows(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def extract(image):
    orb = cv2.ORB.create(nfeatures=1600, scaleFactor=1.2, nlevels=8, edgeThreshold=31,
                        firstLevel=0, WTA_K=2, scoreType=cv2.ORB_HARRIS_SCORE,
                        patchSize=31, fastThreshold=12)
    keypoints, descriptors = orb.detectAndCompute(image, None)
    return Features(keypoints or [], descriptors, image.shape)


def transform(image, name):
    h, w = image.shape
    if name == "identity_control":
        return image.copy()
    if name == "dim_45pct":
        return np.round(image.astype(float) * .45).astype(np.uint8)
    if name == "blur_sigma3":
        return cv2.GaussianBlur(image, (15, 15), 3)
    if name == "rotation25":
        matrix = cv2.getRotationMatrix2D((w/2, h/2), 25, 1)
        return cv2.warpAffine(image, matrix, (w, h), borderMode=cv2.BORDER_CONSTANT)
    if name == "perspective15pct":
        src = np.float32([[0, 0], [w-1, 0], [w-1, h-1], [0, h-1]])
        dst = np.float32([[.15*w, .08*h], [.85*w, 0], [w-1, .92*h], [0, h-1]])
        return cv2.warpPerspective(image, cv2.getPerspectiveTransform(src, dst), (w, h))
    if name == "crop65pct":
        return cv2.resize(image[int(.175*h):int(.825*h), int(.175*w):int(.825*w)], (w, h))
    if name == "occlusion40pct":
        result = image.copy()
        result[:, :int(.4*w)] = 0
        return result
    raise ValueError(name)


def measure(query, reference):
    cv2.setRNGSeed(PROTOCOL["seed"])
    start = time.perf_counter()
    result = compare(query, reference)
    elapsed = (time.perf_counter() - start) * 1000
    return {**result, "geometric_accept": float(result["similarity"]) >= THRESHOLD,
            "descriptor_score": min(1, int(result["good_matches"]) / 36),
            "descriptor_accept": min(1, int(result["good_matches"]) / 36) >= THRESHOLD,
            "pair_compare_ms": round(elapsed, 4)}


def aggregate(results, acceptance):
    positives = [r for r in results if r["expected_match"]]
    negatives = [r for r in results if not r["expected_match"]]
    tp = sum(r[acceptance] for r in positives)
    fp = sum(r[acceptance] for r in negatives)
    return {"trials": len(results), "positives": len(positives), "negatives": len(negatives),
            "true_accepts": tp, "false_accepts": fp,
            "true_accept_rate": tp / len(positives) if positives else None,
            "false_accept_rate": fp / len(negatives) if negatives else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--library-count", type=int, default=512)
    parser.add_argument("--output", type=Path, default=ROOT / "experiments/output/benchmark-2026-10-26")
    parser.add_argument("--library-originals", type=Path, default=Path.home() / "Pictures/Photos Library.photoslibrary/originals")
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    if (out / "summary.json").exists():
        raise SystemExit("Completed results already exist; choose a new --output to preserve evidence")
    protocol = {**PROTOCOL, "library_count_requested": args.library_count,
                "started_utc": datetime.now(timezone.utc).isoformat()}
    (out / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    library_rows = rows(ROOT / "experiments/output/photo_library_places_assets.csv")
    assets = {r["uuid"]: r for r in library_rows}
    def asset_path(r):
        return args.library_originals / r["directory"] / r["filename"]
    available = []
    for r in assets.values():
        try:
            valid = -90 <= float(r["latitude"]) <= 90 and -180 <= float(r["longitude"]) <= 180
        except (ValueError, TypeError):
            valid = False
        if valid and asset_path(r).is_file():
            available.append(r)
    available.sort(key=lambda r: hashlib.sha256(r["uuid"].encode()).hexdigest())
    selected = [(p, "supplied") for p in image_paths(ROOT / "experiments/data/references")]
    selected += [(asset_path(r), "library_hash_sample") for r in available[:args.library_count]]
    manifest, exclusions, unique, seen = [], [], [], set()
    for path, source in selected:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen:
            exclusions.append({"path": str(path), "reason": "exact_file_duplicate"})
            continue
        seen.add(digest)
        photo_id = f"photo_{len(unique)+1:04d}"
        unique.append((photo_id, path, source))
        manifest.append({"photo_id": photo_id, "path": str(path), "sha256": digest, "source": source})
    write_csv(out / "private_manifest.csv", manifest)
    print(f"Frozen selection: {len(unique)} unique photos; {len(available)} eligible local library assets", flush=True)
    cv2.setNumThreads(1)
    stress = []
    for index, (photo_id, path, source) in enumerate(unique):
        try:
            image = read_gray(path)
            reference = extract(image)
        except Exception as error:
            exclusions.append({"path": str(path), "reason": f"decode_or_extract_error:{type(error).__name__}"})
            continue
        for condition in CONDITIONS:
            start = time.perf_counter()
            query = extract(transform(image, condition))
            extract_ms = (time.perf_counter()-start)*1000
            stress.append({"photo_id": photo_id, "source": source, "condition": condition,
                           "expected_match": True, "query_features": len(query.keypoints),
                           "transform_extract_ms": round(extract_ms, 4), **measure(query, reference)})
        if (index+1) % 25 == 0:
            print(f"Stress photos {index+1}/{len(unique)}", flush=True)
    write_csv(out / "stress_trials.csv", stress)
    natural, feature_cache, included_pairs = [], {}, []
    labels = rows(ROOT / "experiments/data/photo_library_pair_labels.csv")
    for i, label in enumerate(labels):
        if label["label"] not in {"same_scene", "different_scene"}:
            continue
        a, b = label["asset_a_uuid"], label["asset_b_uuid"]
        try:
            for uid in (a, b):
                if uid not in feature_cache:
                    feature_cache[uid] = extract(read_gray(asset_path(assets[uid])))
        except Exception as error:
            exclusions.append({"path": f"pair_{i+1:03d}", "reason": f"pair_unavailable:{type(error).__name__}"})
            continue
        pair_id = f"pair_{i+1:03d}"
        meta_a, meta_b = assets[a], assets[b]
        same_date = meta_a["captured_at"][:10] == meta_b["captured_at"][:10]
        included_pairs.append({"pair_id": pair_id, "label": label["label"], "same_capture_date": same_date})
        for direction, q, r in [("A_to_B", a, b), ("B_to_A", b, a)]:
            natural.append({"pair_id": pair_id, "direction": direction,
                            "expected_match": label["label"] == "same_scene",
                            "same_capture_date": same_date, **measure(feature_cache[q], feature_cache[r])})
    write_csv(out / "natural_pair_trials.csv", natural)
    write_csv(out / "natural_pairs.csv", included_pairs)
    write_csv(out / "private_exclusions.csv", exclusions)
    summary = {
        "protocol": protocol, "completed_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "opencv": cv2.__version__, "opencv_threads": cv2.getNumThreads(),
                        "packages": {n: importlib.metadata.version(n) for n in ["numpy", "Pillow", "pillow-heif"]}},
        "source_hashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in [Path(__file__), ROOT / "experiments/src/recall_lens_eval.py"]},
        "selected_photos": len(unique), "decoded_photos": len({r["photo_id"] for r in stress}),
        "photos_by_source": dict(Counter(r["source"] for r in stress if r["condition"] == "identity_control")),
        "exclusion_counts": dict(Counter(r["reason"] for r in exclusions)),
        "stress_by_condition": {c: {m: aggregate([r for r in stress if r["condition"] == c], a)
                                     for m, a in [("geometric", "geometric_accept"), ("descriptor_support", "descriptor_accept")]}
                                for c in CONDITIONS},
        "natural_unique_pairs": len(included_pairs),
        "natural_pair_labels": dict(Counter(r["label"] for r in included_pairs)),
        "natural_same_date_pairs": sum(r["same_capture_date"] for r in included_pairs),
        "natural_directional": {m: aggregate(natural, a) for m, a in [("geometric", "geometric_accept"), ("descriptor_support", "descriptor_accept")]},
        "desktop_pair_compare_ms": {"median": float(np.median([r["pair_compare_ms"] for r in stress])),
                                    "p95": float(np.percentile([r["pair_compare_ms"] for r in stress], 95))},
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in ["decoded_photos", "photos_by_source", "exclusion_counts", "natural_unique_pairs", "natural_directional"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
