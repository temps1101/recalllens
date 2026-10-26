# Recalllens experiment environment

This directory reproduces the production OpenCV 5 ORB + RANSAC matcher and analyzes image metadata without uploading private photographs.

## 1. Set up

```sh
cd experiments
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 2. Add photographs

- Put one reference per scene in `data/references/`. The filename stem is the scene ID, for example `scene_001.jpg`.
- Put test photographs in `data/queries/`.
- Copy `data/labels.example.csv` to `data/labels.csv` and label every query.
- Use `NONE` when a query should not match any reference.

JPEG, HEIC/HEIF, PNG, and TIFF are supported. EXIF capture time, GPS, camera model, focal length, exposure, and ISO are extracted when present. Missing metadata remains blank. Keep private photographs out of Git; `.gitignore` excludes the data directories.

## 3. Run the reproducible analysis

```sh
.venv/bin/python src/recall_lens_eval.py
.venv/bin/jupyter lab notebooks/analysis.ipynb
```

Outputs are written to `output/`:

- `image_metadata.csv`: EXIF/GPS inventory
- `comparisons.csv`: every query-reference comparison
- `predictions.csv`: top-1 decision per query
- `summary.json`: accuracy, true unlock rate, false unlock rate, and latency

The production unlock threshold defaults to `0.62`. Use `--threshold` only for threshold exploration; choose it on the tuning split, freeze it, and report the test split separately.

The summary reports each split under `by_split`; it does not pool tuning and test accuracy. `unsafe_unlocks` includes both a negative query unlocking and a positive query unlocking the wrong reference. `top1_positive_accuracy` measures retrieval separately from threshold acceptance. Empty datasets fail explicitly.

## Retrospective photo benchmark

The submission benchmark uses existing photographs without requesting additional manual classification:

```sh
cd /path/to/RecallLens
experiments/.venv/bin/python Tools/run_photo_benchmark.py
experiments/.venv/bin/python Tools/generate_report_figures.py
```

The first command requires the owner's local photo files and metadata manifest, and refuses to overwrite a completed run. Use `--output` for another run. Selection is frozen before matching: supplied reference stills plus a hash-ordered sample of locally available, valid-coordinate originals from the existing metadata manifest. Exact file duplicates are removed. Every decoded source receives the same six synthetic transformations and an identity control. No transformed query is described as a newly captured photograph.

The existing human pair labels are evaluated in both directions. They were selected through the matcher, so they remain an exploratory audit rather than an unbiased test set. Unlabeled cross-photo pairs are not assumed to be negatives. Scores, selections, errors, protocol, source hashes and versions are saved locally. Private paths and photos are excluded from the submission; anonymized scores allow the published charts to be regenerated, but full re-extraction on the private originals requires access to those images.

The descriptor-support comparison removes geometric verification and uses a fixed support score at the existing threshold. It is a diagnostic ablation, not a separately optimized competitor. Read `docs/PHOTO_BENCHMARK.md` before interpreting its results.

GPS and time are evaluation covariates, not unlock inputs. This prevents location metadata from leaking into the visual-matching result while allowing analysis of distance, elapsed time, lighting changes, and repeated visits.

## Label repeated places from Apple Photos

The following commands read the Photos database without modifying it, group photographs taken within 35 meters, and open a local labeling interface:

```sh
cd /path/to/RecallLens
experiments/.venv/bin/python Tools/cluster_photos_library.py
experiments/.venv/bin/python Tools/build_label_candidates.py
experiments/.venv/bin/python Tools/label_photo_library.py
```

The candidate builder uses a conservative OpenCV similarity floor of `0.12` to remove pairs with almost no visual correspondence. Open `http://127.0.0.1:8765`. All retained pairs appear in one continuous queue; there is no per-place open/close step. Each comparison treats the two photographs symmetrically; label the pair as `same_scene`, `different_scene`, or `skip`. Use `S`, `D`, and `X` on the keyboard and the arrow keys to move. Labels are saved locally to `experiments/data/photo_library_pair_labels.csv`. Same-day photographs are included. GPS only proposes nearby candidates; reference/query roles are assigned later when the labeled scene groups are split for evaluation.
