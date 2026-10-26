#!/usr/bin/env python3
"""Regenerate report figures from recorded rows, never hand-entered metrics."""
import argparse
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

def read_csv(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))

def save(fig, path):
    for ext in ["png", "pdf"]:
        fig.savefig(path.with_suffix("." + ext), dpi=180, bbox_inches="tight")
    plt.close(fig)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", type=Path, default=ROOT / "experiments/output/audit-2026-10-25/device-pilot-2026-10-20.csv")
    parser.add_argument("--benchmark", type=Path, default=ROOT / "experiments/output/benchmark-2026-10-26")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/figures")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False})
    pilot = read_csv(args.pilot)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
    for index, expected in enumerate(["true", "false"]):
        subset = [r for r in pilot if r["expected_match"] == expected]
        correct = sum(r["actual_match"] == expected for r in subset)
        axes[0].bar(index, correct, color="#16756a")
        axes[0].bar(index, len(subset)-correct, bottom=correct, color="#ce5148")
        axes[0].text(index, len(subset)+.1, f"{correct}/{len(subset)} correct", ha="center")
    axes[0].set(xticks=[0, 1], xticklabels=["Expected match", "Expected no match"],
                ylabel="Recorded trials", ylim=(0, max(len(pilot), 1)), title=f"iPhone integration pilot: n={len(pilot)}")
    for i, key in enumerate(["local_ms", "aws_compute_ms", "aws_round_trip_ms"]):
        vals = np.array([float(r[key]) for r in pilot if key == "local_ms" or float(r[key]) > 0])
        axes[1].scatter(i + np.linspace(-.08, .08, len(vals)), vals, color="#357abb", s=30)
        if len(vals):
            med = np.median(vals)
            axes[1].plot([i-.18, i+.18], [med, med], color="#162b40", linewidth=2)
            axes[1].text(i, max(vals)+20, f"n={len(vals)}\nmedian {med:.1f}", ha="center", fontsize=9)
    axes[1].set(xticks=[0, 1, 2], xticklabels=["On device", "AWS compute", "AWS round trip"],
                ylabel="Milliseconds", title="Individual timing observations")
    axes[1].margins(y=.22)
    fig.supxlabel("One short session; matching/verification time excludes time to stable UI unlock.", fontsize=9)
    save(fig, args.output / "preliminary-evaluation")

    summary = json.loads((args.benchmark / "summary.json").read_text())
    stress = read_csv(args.benchmark / "stress_trials.csv")
    natural = read_csv(args.benchmark / "natural_pair_trials.csv")
    conditions = [c for c in summary["protocol"]["conditions"] if c != "identity_control"]
    names = ["Dim (45%)", "Blur (sigma 3)", "Rotation (25 deg)", "Perspective (15%)", "Central crop (65%)", "Occlusion (40%)"]
    fig, ax = plt.subplots(figsize=(11, 5.5), layout="constrained")
    x = np.arange(len(conditions))
    for offset, field, name, color in [(-.19, "descriptor_accept", "Descriptor-support ablation", "#95abc0"),
                                      (.19, "geometric_accept", "ORB + RANSAC (current)", "#16756a")]:
        counts = [(sum(r[field] == "True" for r in stress if r["condition"] == c),
                   sum(r["condition"] == c for r in stress)) for c in conditions]
        vals = [100*a/n for a, n in counts]
        ax.bar(x+offset, vals, .36, label=name, color=color)
        for pos, value, (a, n) in zip(x+offset, vals, counts):
            ax.text(pos, value+1, f"{a}/{n}", ha="center", fontsize=8, rotation=90)
    ax.set(xticks=x, xticklabels=names, ylabel="Known transformed-image pairs accepted (%)", ylim=(0, 125),
           title=f"Offline transformation stress test | {summary['decoded_photos']} source photographs")
    ax.legend(loc="upper center", ncol=2, frameon=False)
    fig.supxlabel("Synthetic queries, not new captures. Photos reused across conditions. Fixed thresholds; ablation not separately calibrated.", fontsize=8)
    save(fig, args.output / "photo-stress-test")

    fig, axes = plt.subplots(1, 2, figsize=(11, 5), layout="constrained")
    for i, (field, color) in enumerate([("descriptor_accept", "#95abc0"), ("geometric_accept", "#16756a")]):
        pos = [r for r in natural if r["expected_match"] == "True"]
        neg = [r for r in natural if r["expected_match"] == "False"]
        for ax, subset in zip(axes, [pos, neg]):
            count = sum(r[field] == "True" for r in subset)
            ax.bar(i, count, color=color, width=.55)
            ax.text(i, count+.3, f"{count}/{len(subset)}", ha="center")
            ax.set(xticks=[0, 1], xticklabels=["Descriptor\nsupport", "ORB +\nRANSAC"],
                   ylim=(0, max(len(subset)*1.15, 2)), ylabel="Accepted directional comparisons")
    axes[0].set_title("Same-scene labels: accepted (higher is better)")
    axes[1].set_title("Different-scene labels: accepted (lower is better)")
    fig.suptitle(f"Exploratory audit | {summary['natural_unique_pairs']} human-labeled photo pairs")
    fig.supxlabel("Each pair tested in both directions. Selection used the current matcher; these are not held-out accuracy estimates.", fontsize=8)
    save(fig, args.output / "natural-pair-audit")
    print(args.output)

if __name__ == "__main__":
    main()
