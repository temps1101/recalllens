#!/usr/bin/env python3
"""Prefilter GPS-nearby pairs with the production-equivalent OpenCV matcher."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "experiments/src"))

from recall_lens_eval import compare, extract_features  # noqa: E402

ORIGINALS = Path.home() / "Pictures/Photos Library.photoslibrary/originals"
MAX_IMAGES = 8


def image_path(asset: dict[str, str]) -> Path:
    return ORIGINALS / asset["directory"] / asset["filename"]


def representatives(assets: list[dict[str, str]]) -> list[dict[str, str]]:
    local = sorted((asset for asset in assets if image_path(asset).exists()), key=lambda row: row["captured_at"])
    if len(local) <= MAX_IMAGES:
        return local
    indices = sorted({round(index * (len(local) - 1) / (MAX_IMAGES - 1)) for index in range(MAX_IMAGES)})
    return [local[index] for index in indices]


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove visually unrelated GPS-nearby pairs before human labeling.")
    parser.add_argument("--minimum-similarity", type=float, default=0.12)
    parser.add_argument("--max-clusters", type=int, default=30, help="Analyze the highest-priority GPS clusters only.")
    parser.add_argument("--include-cluster", action="append", default=[], help="Also analyze a specific cluster ID.")
    parser.add_argument("--input", type=Path, default=ROOT / "experiments/output/photo_library_places_assets.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "experiments/output/photo_library_label_candidates.csv")
    args = parser.parse_args()
    with args.input.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    by_cluster: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_cluster[row["cluster_id"]].append(row)

    output: list[dict[str, object]] = []
    analyzed = 0
    ordered_clusters = sorted(by_cluster)
    selected_clusters = ordered_clusters[: args.max_clusters]
    selected_clusters.extend(cluster for cluster in args.include_cluster if cluster in by_cluster and cluster not in selected_clusters)
    for cluster_index, cluster_id in enumerate(selected_clusters, start=1):
        assets = by_cluster[cluster_id]
        images = representatives(assets)
        features = {}
        for asset in images:
            try:
                features[asset["uuid"]] = extract_features(image_path(asset))
            except Exception:
                pass
        candidates: list[dict[str, object]] = []
        for first_index, first in enumerate(images):
            if first["uuid"] not in features:
                continue
            for second in images[first_index + 1:]:
                if second["uuid"] not in features:
                    continue
                result = compare(features[first["uuid"]], features[second["uuid"]])
                analyzed += 1
                if float(result["similarity"]) < args.minimum_similarity:
                    continue
                candidates.append({
                    "cluster_id": cluster_id, "asset_a_uuid": first["uuid"], "asset_b_uuid": second["uuid"],
                    "similarity": result["similarity"], "good_matches": result["good_matches"],
                    "inliers": result["inliers"], "inlier_ratio": result["inlier_ratio"],
                })
        candidates.sort(key=lambda row: float(row["similarity"]), reverse=True)
        output.extend(candidates)
        if cluster_index % 50 == 0:
            print(f"clusters {cluster_index}/{len(selected_clusters)}; retained pairs {len(output)}", flush=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["cluster_id", "asset_a_uuid", "asset_b_uuid", "similarity", "good_matches", "inliers", "inlier_ratio"]
    with args.output.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)
    print(f"analyzed_pairs={analyzed} retained_pairs={len(output)} output={args.output}")


if __name__ == "__main__":
    main()
