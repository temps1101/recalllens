# Recalllens — Devpost submission copy

## One-line description

A private iOS camera that uses OpenCV 5 to turn a real-world view into a key for photographs, with AWS for optional account-free sharing.

## Inspiration

Photo libraries make images easy to retrieve but detach them from the viewpoints that gave them meaning. Recalllens explores a different interaction: a memory becomes available when the user physically returns the camera to the corresponding visible scene.

## What it does

The user captures a photograph inside Recalllens. Later, the application compares the live camera view with locally stored scene signatures. Matching photos appear as one compact preview and a swipeable set; a deliberately opened photo remains until manually closed.

Each capture opens a full-screen review with Save, Share and Discard. Share saves the photo and copies a sharing link. Anyone with an installed app can receive the photo without an account; the receipt reveals no preview. A representative thumbnail appears when the scene matches locally; the viewer identifies received photos. AWS stores and delivers the explicitly shared photos across devices.

## How we built it

The iOS application is written in SwiftUI with an Objective-C++ OpenCV bridge. OpenCV 5.0.0 extracts up to 1,600 ORB features, performs Hamming KNN matching with a 0.75 ratio test, and estimates a homography with RANSAC. Similarity combines inlier ratio, inlier support, and spatial coverage. Temporal smoothing and hysteresis stabilize the camera interface.

Ordinary capture, storage and matching remain on-device. Sharing explicitly uploads a downscaled JPEG together with its ORB signature. An arm64 Lambda running OpenCV 5 independently extracts features and rejects mismatched pairs; validated pairs are stored in private S3 for 30-day bearer-link delivery. Recipients download the pair once and then match locally. No live camera frame is sent to AWS. Deliberately opened viewers remain until manually closed.

## Challenges

The main technical challenge was making robust local geometric retrieval feel stable while keeping cloud behavior explicit. Additional challenges included multi-photo matching, temporal stabilization, strict image-signature pair validation, expiration before asynchronous object cleanup, and account-free delivery without exposing a photo preview on the landing page.

## Accomplishments

- The same OpenCV 5 feature and geometry pipeline runs on iOS and AWS.
- Visual evidence changes application state entirely on-device.
- Ordinary captures and live camera frames remain local; only explicit Share uploads a downscaled image-signature pair.
- Lambda uses OpenCV 5 to validate the pair before private, expiring delivery.
- The deployment includes throttling, short log retention, invalid-token rejection, and budget monitoring.
- The project includes deterministic build/deployment instructions, unit tests, an offline evaluator, and an architecture diagram. The production app contains no developer dashboard or destructive database controls.

## What we learned

The controlled transformation tests showed high acceptance when geometry remained related. The natural-pair audit exposed a tradeoff: geometric verification rejected three negative comparisons accepted by the descriptor-support ablation, but also missed one additional positive. Temporal stabilization must reduce flicker without keeping stale matches visible indefinitely. The shared-token prototype validates uploaded pairs and distributes them; it does not prevent a modified client from accessing locally stored photos.

## Evaluation

Our primary image-recognition study evaluated 49 existing human-labeled natural-photo pairs in both directions. Geometric verification accepted 9/14 positive and 0/84 negative directional comparisons; a descriptor-support ablation accepted 10/14 and 3/84. The original pair selection used the matcher, reverse directions share photos, and the ablation was not separately calibrated. These are exploratory findings, not unbiased population accuracy estimates.

The positive pairs use eight photographs in one GPS candidate group, so scene coverage is limited. The report shows actual-photo successes, a missed close-up match, and rejection of different subjects at the same place.

An additional study used 144 new-to-evaluation archived photographs from 24 GPS blocks. Four method families and 34 settings were scored, with tuning and test blocks fixed separately. Two AI visual passes retained 74/96 pairs by agreement; 22 uncertain/disputed pairs were excluded. These labels have no human validation. On 39 retained test pairs, the deployed ORB accepted 12/28 positive and 0/50 negative directions; tuned SIFT accepted 19/28 and 3/50. Tuning exposed a failure of unconstrained threshold selection: the selected ORB threshold could accept too few matches to estimate geometry. We report this outcome and preserve the deployed setting. These exploratory results reveal significant viewpoint limitations, not general accuracy or a validated improvement.

As a supplementary robustness test, we evaluated 641 archived photographs under six fixed synthetic transformations, producing 3,846 transformed positive comparisons plus identity controls. These are generated queries of existing images, not new field captures. Depending on the transformation, the geometric matcher accepted 631 to 641 of 641 queries at the unchanged threshold of 0.62.

A separate six-trial iPhone pilot produced 2/2 expected unlocks and 0/4 false unlocks, with median on-device matching of 54.1 ms and AWS round trip of 330.0 ms. It supports integration, not broad accuracy or camera-to-unlock latency claims.

The updated sharing deployment passed live checks for authenticated pair upload, account-free pair receipt, repeat identity, private landing-page behavior and logical expiry before S3 cleanup.

Use `docs/figures/photo-stress-test.png`, `docs/figures/natural-pair-audit.png` and `docs/architecture.png`. The small pilot is supplementary evidence.

## Limitations and responsible use

ORB depends on textured, stable scenes. Blur, occlusion, low texture, repeated patterns, strong lighting changes, and major viewpoint changes can reduce accuracy. Recalllens recognizes visual correspondence, not identity or geographic proof. It is not suitable for access control, surveillance, or safety-critical authentication.

## What's next

The next steps are human validation of the broader labels, calibration with hard geometry constraints on new held-out data, registration quality and viewpoint guidance, indexed retrieval, and user-scoped cloud authentication.

## Technologies

SwiftUI, Objective-C++, OpenCV 5.0.0, ORB, Hamming KNN, RANSAC homography, AWS Lambda arm64, API Gateway, S3, CloudWatch, AWS SAM, Python, and Jupyter.

## Rubric alignment

| Criterion | Primary evidence |
|---|---|
| Technical execution — 30% | Local OpenCV 5 geometric retrieval, temporal stabilization, Lambda pair validation, tests, evaluation tooling |
| Innovation — 20% | Physical scene as a visual key for deliberate memory retrieval |
| Real-world impact — 20% | Private place-bound archives and extensions to field notes or site histories |
| User experience — 10% | Camera-first capture, stable unlock state, hidden archive until authorization |
| Documentation — 10% | Technical report, architecture diagram, pinned dependencies, build/deploy/test instructions, five-minute demo plan |
| Cloud/reproducibility/responsibility — 10% | arm64 Lambda OpenCV pair validation, private S3 delivery with expiry, throttling, short logs, budget |
