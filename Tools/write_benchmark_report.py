#!/usr/bin/env python3
"""Write the retrospective evaluation report from frozen result files."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "experiments/output/benchmark-2026-10-26"


def main():
    summary = json.loads((DATA / "summary.json").read_text())
    with (DATA / "natural_pair_trials.csv").open() as source:
        pairs = list(csv.DictReader(source))
    n = summary["decoded_photos"]
    table = ["| Transformation | ORB + RANSAC accepted | Descriptor support accepted |", "|---|---:|---:|"]
    for condition, methods in summary["stress_by_condition"].items():
        a, b = methods["geometric"], methods["descriptor_support"]
        table.append(f"| {condition} | {a['true_accepts']}/{a['positives']} | {b['true_accepts']}/{b['positives']} |")
    natural_table = ["| Method / direction | Same-scene accepted | Different-scene accepted (errors) |", "|---|---:|---:|"]
    for method, column in [("ORB + RANSAC", "geometric_accept"), ("Descriptor support", "descriptor_accept")]:
        for direction in ["A_to_B", "B_to_A"]:
            pos = [r for r in pairs if r["direction"] == direction and r["expected_match"] == "True"]
            neg = [r for r in pairs if r["direction"] == direction and r["expected_match"] == "False"]
            natural_table.append(f"| {method} / {direction} | {sum(r[column]=='True' for r in pos)}/{len(pos)} | {sum(r[column]=='True' for r in neg)}/{len(neg)} |")
    misses = [r for r in pairs if r["expected_match"] == "True" and r["geometric_accept"] == "False"]
    failure_table = ["| Pair | Direction | Score | Threshold |", "|---|---|---:|---:|"]
    failure_table += [f"| {r['pair_id']} | {r['direction']} | {float(r['similarity']):.6f} | 0.62 |" for r in misses]
    document = f"""# Recalllens - Retrospective photographic evaluation

## Evidence and scope

This evaluation uses **{n} existing photographs**, not newly captured field trials. The sources are {summary['photos_by_source']['supplied']} supplied stills and {summary['photos_by_source']['library_hash_sample']} additional Apple Photos originals. The latter were selected by SHA256 ordering of asset identifiers from locally available files with valid coordinates in an existing metadata manifest. Selection did not use the matcher's similarity score. All selected files decoded; exact-file deduplication found no duplicate selected files. These are photographs, not necessarily distinct scenes or independent visits.

Each source received six fixed synthetic transformations and an identity control: {n*6:,} transformed positive comparisons plus {n:,} identity controls. The original image was the reference. Transformations were generated in memory; no images were uploaded. The threshold stayed at the pre-existing 0.62 throughout the experiment. There was no search for the best threshold on these results.

Separately, all {summary['natural_unique_pairs']} existing human-labeled photo pairs were evaluated in both directions: 7 same-scene pairs and 42 different-scene pairs, giving 14 positive and 84 negative directional comparisons. Their original selection used the current matcher, so this is an exploratory audit with selection bias. Reverse directions are correlated observations of the same pair, not new independent examples.

## Synthetic transformation results

{chr(10).join(table)}

![Controlled transformations of archived photos](figures/photo-stress-test.png)

Brightness was multiplied by 0.45; Gaussian blur used a 15-pixel kernel and sigma 3; rotation was 25 degrees; perspective corners shifted by the fixed fractions in the protocol; a central 65% crop was resized; occlusion replaced the left 40% with black. These planar digital transformations preserve correspondence by construction. They do not simulate all changes in real revisits, such as depth-dependent parallax, seasonal change, or moving objects. There are no negative examples in this stress test, so it cannot measure false-acceptance rate.

The diagnostic ablation uses min(ratio-test match count / 36, 1) at 0.62, removing geometric verification. It is not independently calibrated or claimed to be the strongest competing method. The comparison isolates a design tradeoff at fixed settings; it does not establish statistical superiority.

## Existing natural-photo pair audit

{chr(10).join(natural_table)}

![Human-labeled pairs evaluated in both directions](figures/natural-pair-audit.png)

Across both directions, ORB + RANSAC accepted 9/14 positive comparisons and 0/84 negative comparisons. Descriptor support accepted 10/14 and 3/84 respectively. At these settings, geometric verification rejected the three negative comparisons accepted by the ablation but also missed one additional positive comparison. Zero observed false accepts does not imply zero risk outside this selected sample.

{summary['natural_same_date_pairs']} of the 49 pairs share the same capture date in the metadata manifest; 37 have different dates. Date similarity and GPS proximity are contextual metadata, not the visual ground truth. No success rate for a new visit is inferred from those counts.

## Recorded failures

All five missed positive directions are listed here, without exposing private photographs:

{chr(10).join(failure_table)}

One direction of pair_047 scored 0.617837, just below the fixed 0.62 threshold. The threshold was not lowered after observing this failure. The other two missed pairs fail in both directions. A visual explanation for each failure still requires inspection; low texture, viewpoint and blur are hypotheses, not established causes for these specific cases.

## Runtime and reproducibility

Runtime: Python {summary['environment']['python']}, OpenCV {summary['environment']['opencv']}, {summary['environment']['platform']}. The recorded OpenCV thread setting was {summary['environment']['opencv_threads']}. Desktop cached-feature pair comparison had median {summary['desktop_pair_compare_ms']['median']:.2f} ms and p95 {summary['desktop_pair_compare_ms']['p95']:.2f} ms across stress comparisons. This is descriptive timing on a development computer with other work running; it excludes image loading, feature extraction, searching the full archive, network requests, and the phone's temporal stabilization.

The run saves protocol, per-comparison rows, environment, source hashes, a private source-file manifest, and exclusions. Scores are reproduced by `Tools/run_photo_benchmark.py` with access to the original photos. `Tools/generate_report_figures.py` regenerates the figures from saved rows. The submission evidence exposes only anonymized result rows and aggregate metadata. Private originals and source paths are not distributed; judges can reproduce the tables and charts, but cannot independently re-extract these private image features from the public package.

## What this evidence supports

The large positive stress test supports robustness to the specified digital transformations. The small natural-pair audit exposes a measured sensitivity/specificity tradeoff. The six-trial iPhone pilot remains separate evidence of client/cloud integration. None of these establishes population-level scene-recognition accuracy, user benefit, location proof, end-to-end camera parity, or protection against a modified client.
"""
    # Lead with separately captured natural photos; controlled transformations are supporting evidence.
    prefix, rest = document.split('## Synthetic transformation results', 1)
    synthetic, rest = rest.split('## Existing natural-photo pair audit', 1)
    natural, rest = rest.split('## Recorded failures', 1)
    cases = '''
## Illustrated real-photo cases

The seven positive pairs involve eight photographs within one GPS candidate group. This narrow scene coverage limits generalization. The figures below show separately captured originals, oriented and scaled for presentation with EXIF omitted; scores were computed before rendering.

![Successful matches on actual counter and song-list photographs](figures/natural-cases-1.png)

Pair_043 preserves counter structure despite changed contents. Pair_046 preserves song-list correspondence under a different angle and illumination. Both pass in both directions.

![A missed close-up correspondence and a same-location different-subject rejection](figures/natural-cases-2.png)

Pair_045 is a user-labeled same-scene pair comparing a close-up with the full jukebox; it fails in both directions. Scale and visible area differ substantially, though this case alone does not isolate a causal explanation. Pair_044 shows different subjects in the same location group and is correctly rejected. Case selection illustrates outcomes and is not an additional accuracy sample.

'''
    document = prefix + '## Existing natural-photo pair audit' + natural + cases + '## Supplement: synthetic transformation results' + synthetic + '## Recorded failures' + rest
    document = document.replace('A visual explanation for each failure still requires inspection; low texture, viewpoint and blur are hypotheses, not established causes for these specific cases.', 'The illustrated whole-object/close-up pair shows a large change in scale and visible area. This is an observation, not a controlled causal finding; causes of the remaining failures are not established.')
    (ROOT / "docs/PHOTO_BENCHMARK.md").write_text(document)
    print(ROOT / "docs/PHOTO_BENCHMARK.md")


if __name__ == "__main__":
    main()
