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

When the AWS key registry is configured, an ordinary capture registers its compact ORB signature in DynamoDB; the JPEG remains on the iPhone unless its owner chooses to share it. For the owner's photos, the phone selects a candidate, then sends its ID and a 960-pixel live frame to Lambda for independent geometric verification. A configured cloud failure keeps those photos closed.

## Share a photo without an account

Every capture opens a full-screen review with **Save / Share / Discard**. Save commits the photo locally; Discard drops the unsaved draft. Share saves it locally and creates a sharing link. For Share, the app uploads a downscaled JPEG to private AWS S3 storage and copies an HTTPS link. The link opens a small landing page that launches the installed app with `recalllens://receive/<id>`; browsers that block automatic app opening provide an explicit button. Universal Links and App Store distribution are not configured.

Anyone with the link can receive the photo without creating an account. The app saves it in the background, builds its OpenCV signature locally, and shows a receipt notice without a photo preview. A single representative thumbnail appears beside the shutter when photos match. The viewer identifies received photos. Once deliberately opened, the viewer remains until manually closed; the camera thumbnail still disappears when the scene changes. Received photos use on-device matching and do not require cloud verification after receipt. Opening a link twice does not duplicate the record. This is a visual discovery interaction, not secure geofencing or proof of location.

Shared JPEGs have EXIF removed and can be downloaded for 30 days; S3 lifecycle cleanup follows asynchronously. Already received copies remain on recipients' devices. Only tapping the share action uploads a photo. See `docs/SHARING.md` for implementation and deployment details.

## Repository layout

- `RecallLens/`: SwiftUI iOS application and Objective-C++ OpenCV bridge
- `aws/`: AWS SAM application for the OpenCV 5 key registry and authorization endpoint
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

## Deploy the AWS verifier

AWS is optional and exists to demonstrate server-side verification and account-free sharing. Follow [`aws/README.md`](aws/README.md), then put your endpoint and temporary demo token in the ignored `Config/Cloud.xcconfig`. Never commit that file. Without cloud values, the application uses the on-device OpenCV pipeline.

## Evaluation

For offline evaluation, follow [`experiments/README.md`](experiments/README.md). The batch evaluator reproduces the OpenCV 5 matcher and extracts EXIF capture time and GPS for stratified analysis. GPS and time are not used to decide an unlock. The production app intentionally contains no developer dashboard or destructive database controls.

## Submission evidence

See [`docs/PHOTO_BENCHMARK.md`](docs/PHOTO_BENCHMARK.md) for the retrospective photo evaluation and its limits. Synthetic transformations of archived photographs are reported separately from human-labeled natural photo pairs and the six-trial iPhone integration pilot. They are not new field captures.

The cloud client immediately removes revoked IDs from its match state, bypassing display smoothing. The server checks signature expiry on every lookup; DynamoDB's later TTL deletion is a separate cleanup operation. The updated service was deployed and the updated app installed on the development iPhone on 26 October. Physical-camera transitions still need a recorded demonstration.

The shared demonstration token does not provide user ownership or tamper-resistant access control. The product is a visual memory-retrieval prototype, not proof that someone physically returned to a location.

## License

Recalllens source code is available under the MIT License. Private photographs, device backups, credentials and the deployed demonstration token are not included. OpenCV and other dependencies retain their own licenses.

Read [`SECURITY.md`](SECURITY.md) before exposing the AWS service publicly. The supplied cloud authentication is intentionally scoped to a controlled competition demonstration, not a production deployment.


The app supports Japanese and English, selected by the device’s preferred app language. Capture review, sharing notices, camera guidance and camera permission text are localized. Sharing landing pages use the browser’s preferred language.
