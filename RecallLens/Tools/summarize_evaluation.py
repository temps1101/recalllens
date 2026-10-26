#!/usr/bin/env python3

import argparse
import csv
import math
import statistics
from collections import Counter


def percentile(values, probability):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize_latency(label, values):
    if not values:
        return f"- {label}: no samples"
    return (
        f"- {label}: median {statistics.median(values):.1f} ms, "
        f"p95 {percentile(values, 0.95):.1f} ms (n={len(values)})"
    )


def main():
    parser = argparse.ArgumentParser(description="Summarize Recall Lens evaluation CSV")
    parser.add_argument("csv_path")
    args = parser.parse_args()

    with open(args.csv_path, newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))

    positives = [row for row in rows if row["expected_match"] == "true"]
    negatives = [row for row in rows if row["expected_match"] == "false"]
    true_unlocks = sum(row["actual_match"] == "true" for row in positives)
    false_unlocks = sum(row["actual_match"] == "true" for row in negatives)
    failures = Counter(
        row["condition"]
        for row in rows
        if row["expected_match"] != row["actual_match"]
    )

    local = [float(row["local_ms"]) for row in rows]
    cloud_round_trip = [
        float(row["aws_round_trip_ms"])
        for row in rows
        if float(row["aws_round_trip_ms"]) > 0
    ]
    cloud_compute = [
        float(row["aws_compute_ms"])
        for row in rows
        if float(row["aws_compute_ms"]) > 0
    ]

    print("# Recall Lens evaluation summary")
    print()
    print(f"- Samples: {len(rows)} ({len(positives)} positive, {len(negatives)} negative)")
    if positives:
        print(f"- True unlock rate: {true_unlocks / len(positives):.1%} ({true_unlocks}/{len(positives)})")
    if negatives:
        print(f"- False unlock rate: {false_unlocks / len(negatives):.1%} ({false_unlocks}/{len(negatives)})")
    print(summarize_latency("On-device matching", local))
    print(summarize_latency("AWS round trip", cloud_round_trip))
    print(summarize_latency("AWS compute", cloud_compute))
    print(f"- AWS verified: {sum(row['aws_status'] == 'verified' for row in rows)}/{len(rows)}")
    if rows and "aws_authorized" in rows[0]:
        print(f"- AWS authorized: {sum(row['aws_authorized'] == 'true' for row in rows)}/{len(rows)}")
        print(f"- References registered: {sum(row['aws_reference_registered'] == 'true' for row in rows)}/{len(rows)}")
    print("- Failures by condition: " + (", ".join(f"{key}={value}" for key, value in sorted(failures.items())) or "none"))


if __name__ == "__main__":
    main()
