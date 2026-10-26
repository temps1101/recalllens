<p align="center"><img src="docs/recalllens.svg" width="180" alt="recalllens — three lowercase l marks"></p>

# Recalllens

Recalllens is an iOS camera that uses the physical world as the key to a private photo archive. A past photograph becomes visible only when the current camera view returns to the same scene and composition.

## Quick start: local mode

The app works without an AWS account. Local mode keeps captures and matching on the iPhone and is the recommended way to try the project first.

Requirements: macOS, Xcode with an iOS 17 SDK, Ruby, and an iPhone running iOS 17 or later.

```sh
git clone https://github.com/temps1101/recalllens.git
cd recalllens
gem install xcodeproj --version 1.23.0
cp Config/Cloud.xcconfig.example Config/Cloud.xcconfig
./Tools/setup_opencv.sh
RECALL_LENS_BUNDLE_IDENTIFIER=com.yourname.recalllens ruby Tools/generate_project.rb
open RecallLens.xcodeproj
```

In Xcode, select the Recalllens target, choose your Apple signing team, connect an iPhone, and press Run. A free Apple ID is sufficient for installation on your own device; TestFlight distribution requires the paid Apple Developer Program.

The matching pipeline uses OpenCV 5.0.0 throughout:

1. ORB extracts up to 1,600 local features from the live frame and each capture.
2. A Hamming-distance KNN matcher applies a 0.75 ratio test.
3. RANSAC estimates a homography and rejects geometrically inconsistent matches.
4. Inlier ratio, spatial support, and image coverage produce the unlock score.
5. EMA smoothing, separate entry/exit thresholds, consecutive decisions, and a minimum hold time stabilize the interface.

Capture, storage, and scene matching are entirely on-device. Ordinary use makes no AWS request: each saved JPEG and its compact ORB signature stay in the application container, and live camera frames are matched only against that local archive.

## Share a photo without an account

Every capture opens a full-screen review with **Save / Share / Discard**. Save commits the photo locally; Discard drops the unsaved draft. Share saves it locally, then uploads a downscaled EXIF-free JPEG together with its OpenCV ORB signature. AWS Lambda independently checks that the supplied signature matches the supplied image before the pair is stored temporarily in private S3. The returned HTTPS link opens a small landing page that launches the installed app with `recalllens://receive/<id>`; browsers that block automatic app opening provide an explicit button. Universal Links and App Store distribution are not configured.

Anyone with the link can receive the validated image-signature pair without creating an account. The app saves it in the background and shows a receipt notice without a photo preview. After that download, matching is entirely local and works without AWS. A single representative thumbnail appears beside the shutter when one or more photos match; opening it shows all current matches. The viewer identifies received photos and remains open until manually closed. Opening a link twice does not duplicate the record. This is a visual discovery interaction, not secure geofencing or proof of location.

Shared JPEGs have EXIF removed and can be downloaded for 30 days; S3 lifecycle cleanup follows asynchronously. Already received copies remain on recipients' devices. Only tapping the share action uploads a photo. See `docs/SHARING.md` for implementation and deployment details.

## Repository layout

- `RecallLens/`: SwiftUI iOS application and Objective-C++ OpenCV bridge
- `aws/`: optional AWS SAM service for validating and temporarily delivering explicitly shared image-signature pairs
- `experiments/`: reproducible offline evaluation environment; private images are ignored by Git
- `docs/`: competition report, architecture, and evaluation protocol
- `Tools/setup_opencv.sh`: reproducible OpenCV 5.0.0 dependency setup
- `Tools/generate_project.rb`: deterministic Xcode project generation

## Build options

To regenerate the project with the repository's default identifier:

```sh
ruby Tools/generate_project.rb
```

Set `RECALL_LENS_BUNDLE_IDENTIFIER` when you need a unique identifier. Set `RECALL_LENS_DEVELOPMENT_TEAM` to generate a project with a signing-team ID. The simulator can compile the project but cannot exercise the camera flow. The official OpenCV iOS framework is downloaded from the OpenCV 5.0.0 GitHub release and is intentionally not committed.

Captured photos remain in the app's private `Application Support/recalllens/Captures` directory. Existing installations migrate the former `RecallLens` or `WeirdBoots` directory automatically. Photos are not written to Photos or Files and are removed when the app is deleted.

## Deploy the optional AWS sharing service

AWS is optional and is contacted only when a user shares or receives a photo. Follow [`aws/README.md`](aws/README.md), then put the endpoint and temporary demo token in the ignored `Config/Cloud.xcconfig`. Never commit that file. Without cloud values, local capture and matching still work; sharing is unavailable.

## Evaluation

For offline evaluation, follow [`experiments/README.md`](experiments/README.md). The batch evaluator reproduces the OpenCV 5 matcher and extracts EXIF capture time and GPS for stratified analysis. GPS and time are not used to decide an unlock. The production app intentionally contains no developer dashboard or destructive database controls.

## Submission evidence

See [`docs/PHOTO_BENCHMARK.md`](docs/PHOTO_BENCHMARK.md) for the retrospective photo evaluation and its limits. Synthetic transformations of archived photographs are reported separately from human-labeled natural photo pairs and the six-trial iPhone integration pilot. They are not new field captures.

The image benchmark, iPhone integration checks, and sharing-service checks are reported separately. AWS availability and latency do not affect normal capture or recall. Physical-camera transitions still need a recorded demonstration.

The shared demonstration token does not provide user ownership or tamper-resistant access control. The product is a visual memory-retrieval prototype, not proof that someone physically returned to a location.

## License

Recalllens source code is available under the MIT License. Private photographs, device backups, credentials and the deployed demonstration token are not included. OpenCV and other dependencies retain their own licenses.

Read [`SECURITY.md`](SECURITY.md) before exposing the AWS service publicly. The supplied cloud authentication is intentionally scoped to a controlled competition demonstration, not a production deployment.


The app supports Japanese and English, selected by the device’s preferred app language. Capture review, sharing notices, camera guidance and camera permission text are localized. Sharing landing pages use the browser’s preferred language.
