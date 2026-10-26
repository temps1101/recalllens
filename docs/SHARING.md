# Account-free photo sharing

Implemented flow: capture → full-screen review → Share → save locally and explicitly upload JPEG → copy link → HTTPS landing page → installed app → receipt notice → local, scene-dependent received-photo display.

## Client behavior

Every capture opens Save / Share / Discard. Until Save or Share is chosen, the draft stays in memory without repository writes or cloud enrollment. Share saves first, then uploads and copies a link; a failed upload retains the saved photo and offers Retry. Japanese and English resources cover this flow, main camera guidance, receipt notices and camera permission text.

- Captured records remain compatible with the existing JSON index. Missing `sourceShareID` means an owner-created photo.
- A received record stores its share ID, server-assigned UUID, capture date, JPEG and locally generated ORB features. Received photos are excluded from cloud reference enrollment and remain locally matchable when AWS is unavailable.
- Link parsing accepts only the `recalllens://receive/` scheme/path or the configured HTTPS host and `/prod/s/` path, with exactly one 32-character URL-safe ID. Arbitrary remote URLs are never fetched.
- A serialized receive queue handles multiple links. Reopening an imported share shows an already-received notice and performs no duplicate write.
- The repository commits its index before replacing the in-memory record list. Failed index writes remove the new JPEG without exposing a phantom record.
- The receipt contains no photo thumbnail. A single representative thumbnail beside the shutter indicates currently matching photos. Each viewer page identifies whether the photo was received. Opening a viewer snapshots the matching records; they remain visible until manually closed, even if the camera turns away or the app is backgrounded. This does not create a permanent unlocked album.
- The sender caches a successful share link until its expiry, avoiding another upload on repeated copy actions.

## AWS behavior

The existing API/Lambda gains sharing routes and a private encrypted S3 bucket. Uploads require the bundled demo token; downloads require possession of the random share ID. No account, message, friend list or public discovery feed is added. The server strips metadata and enforces a 30-day retrieval deadline. Stored objects are cleaned up by lifecycle rules; downloaded copies are not remotely revoked.

The HTTPS page contains no picture and opens a custom URL scheme. Automatic launch depends on browser policy; a visible button is always provided. Universal Links require a separately configured associated domain/signing setup and are not claimed in this build. A recipient must already have an installed Recalllens build.

## Scope of verification

The latest interface adds one representative matching-photo thumbnail and retains an opened viewer until the user closes it. A separate local feature check runs about every 0.4 seconds, disables capture below eight keypoints, and displays inline guidance. Fewer than eight keypoints are also rejected when saving a capture. This checks whether geometry could be attempted, not overall match quality.

Owner registration now uses a 20-second request timeout and up to three attempts for throttling/service errors or transient timeouts. Enrollment is serialized; remote matching requests pause while registration is in flight. An unsuccessful enrollment remains pending for a bounded delayed retry and the next foreground sync. Existing photos are not lost on network failure.

Server tests cover upload authorization, public bearer-link receipt, repeated retrieval, expiry before physical deletion, preview privacy and invalid/oversized uploads. Swift checks cover strict URL parsing and compatibility of old and received records. Simulator and device builds are compiled separately. Live deployment and device checks are recorded in `docs/evidence/sharing-checks.json` when completed; camera-view matching remains distinct from HTTP/persistence validation.

## Reproduction

Generate the Xcode project using `Tools/generate_project.rb`, preserving the existing team/bundle identifier for device updates. Build/deploy the updated SAM template, Dockerfile, handler.py and sharing.py together. Existing cloud configuration points to the same verifier endpoint; sharing routes are derived from its base URL. Do not distribute the real token in source archives.
