# Evaluation protocol

The final submission must report measurements from a real iPhone.

## Dataset

Capture at least 20 reference scenes across indoor and outdoor conditions. For every scene, record one near-duplicate view, one moderate viewpoint or framing change, one lighting change where practical, three unrelated negative views, and one deliberately difficult case such as blur, occlusion, repeated patterns, or low texture.

This produces at least 60 positive and 60 negative comparisons. Keep the images private unless every identifiable person has consented to publication.

## Metrics

At the fixed production threshold, report true unlock rate, false unlock rate, median and p95 on-device processing time, median and p95 AWS verification time, and failures grouped by lighting, viewpoint, blur, occlusion, and texture.

Use the first half of the comparisons for threshold tuning and the second half for final reporting.

## Procedure

1. Enable `-matchingDebug` and reset the internal database.
2. Capture the reference set and wait for indexing to finish.
3. Present each evaluation view for five seconds.
4. Open **Matching Lab**, enter the scene label and condition, then tap **Expected MATCH** or **Expected NO MATCH** once. The app records the decision, score, local latency, AWS round-trip latency, AWS compute latency, and cloud status.
5. Repeat on a different network, including an offline run to demonstrate fail-closed cloud authority.
6. Use **Export evaluation CSV** and summarize it with `python3 Tools/summarize_evaluation.py recall-lens-evaluation.csv`.
7. Preserve representative successes and failures for the submission video and report.

When the iPhone remains connected, the CSV can also be copied directly from its app container:

```sh
xcrun devicectl device copy from \
  --device <device-id> \
  --domain-type appDataContainer \
  --domain-identifier com.example.WeirdBoots \
  --source "Library/Application Support/RecallLens/Evaluation/recall-lens-evaluation.csv" \
  --destination recall-lens-evaluation.csv
```

The Lambda unit tests verify authorization and basic related/unrelated behavior. They do not replace real-world evaluation.

For a larger offline dataset, place reference and query photographs under `experiments/data/` and follow `experiments/README.md`. The evaluator extracts EXIF GPS and capture time when present, but visual accuracy is calculated independently of that metadata.
