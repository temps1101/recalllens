#!/usr/bin/env python3
"""Generate non-private procedural images for evaluator smoke tests, not accuracy claims."""
import argparse
import csv
from pathlib import Path
import cv2
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "references").mkdir()
    (args.output / "queries").mkdir()
    rows = []
    for scene in range(3):
        rng = np.random.default_rng(100 + scene)
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        for i in range(100):
            x, y = int(rng.integers(30, 610)), int(rng.integers(30, 450))
            color = tuple(int(x) for x in rng.integers(60, 256, 3))
            cv2.circle(image, (x, y), int(rng.integers(3, 16)), color, 2)
        name = f"scene_{scene}"
        cv2.imwrite(str(args.output / "references" / f"{name}.png"), image)
        shifted = cv2.warpAffine(image, np.float32([[1, 0, 12], [0, 1, 8]]), (640, 480))
        cv2.imwrite(str(args.output / "queries" / f"{name}.png"), shifted)
        rows.append(dict(query_path=f"queries/{name}.png", expected_scene=name, condition="procedural_shift", split="smoke"))
    cv2.imwrite(str(args.output / "queries/blank.png"), np.zeros((480, 640, 3), dtype=np.uint8))
    rows.append(dict(query_path="queries/blank.png", expected_scene="NONE", condition="procedural_blank", split="smoke"))
    with (args.output / "labels.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(args.output)


if __name__ == "__main__":
    main()
