# Recall Lens - Judge guide

Start with `Recall-Lens-Technical-Report.pdf` and `docs/PHOTO_BENCHMARK.md`. This source package contains the iOS app, AWS service, tests, anonymized measurement rows, chart tools and a procedural smoke-test generator. The report includes six selected real-photo comparison pairs. The full personal photo dataset, source-file metadata, location coordinates and live demonstration token are excluded.

## Recreate the figures

From the package root, create the experiment environment using `experiments/requirements.txt`, then run:

```sh
experiments/.venv/bin/python Tools/generate_report_figures.py --pilot docs/evidence/pilot.csv --benchmark docs/evidence/benchmark
```

The large dataset consists of archived photographs and synthetic transformations, not new field captures. Its natural-photo pairs were previously selected by the matcher. These limitations are recorded in the report. Private image inputs are not distributed, so the package reproduces published aggregates and figures but not independent feature extraction on those originals.

## Exercise the evaluator without private data

Choose new directories that do not already exist:

```sh
experiments/.venv/bin/python Tools/make_public_fixture.py /tmp/recall-lens-smoke-data
experiments/.venv/bin/python experiments/src/recall_lens_eval.py --data /tmp/recall-lens-smoke-data --output /tmp/recall-lens-smoke-results
experiments/.venv/bin/python -m unittest discover -s experiments -p 'test_*.py' -v
```

These four procedural queries check the pipeline. They are not included in the photographic benchmark's accuracy counts.

## Run the application

Follow `README.md` to fetch the pinned OpenCV iOS framework, generate the Xcode project and select your own signing team. The supplied configuration starts in local mode. The camera flow requires a physical iPhone; simulator builds validate compilation only.

No TestFlight binary is provided because the project uses an Apple Personal Team rather than a paid distribution membership. The primary judge-facing demonstration is the continuous real-device video. The source remains buildable with a judge's own signing team.

For independent AWS deployment, follow `aws/README.md` using your own account. A controlled demonstration of the existing deployment requires separately arranged access; no credentials are embedded in this package. Owner verification sends a downscaled live frame to AWS. Explicit sharing uploads a downscaled JPEG for account-free delivery. Received photos match locally after download; see docs/SHARING.md. A shared demo token is not production user authentication.

## Demonstration to record

The final video should be at most five minutes. Show a continuous real-device sequence: capture a permitted scene, show an unrelated view, return to the saved view, open the matching photo, then show rejection or network failure. Include the team, architecture diagram, the retrospective results and their limits. Describe controlled synthetic trials as synthetic. Do not splice an offline result into the video as if it were a live recognition result.

Publication of the source archive and video, and the Devpost submission status, must be verified separately. This guide does not claim those external steps are complete.
