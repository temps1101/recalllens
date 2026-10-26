# AWS OpenCV 5 scene-key registry

This AWS SAM application verifies the owner's photos and delivers optionally shared photos. Ordinary capture registers only an ORB signature in DynamoDB. The explicit share action uploads a downscaled, EXIF-free JPEG to private S3 storage for account-free link delivery. Recipients prefetch the photo and match it locally. Owner verification still uses a live frame and registered signature; live verification frames are not retained.

## Local tests

```sh
python3 -m venv .venv-aws
.venv-aws/bin/pip install --requirement aws/requirements.txt
cd aws
../.venv-aws/bin/python -m unittest -v test_handler.py
```

## Cost policy

Create a new **personal AWS account on the Free plan**. Do not upgrade it to the Paid plan for the competition demo. The stack has no continuously running server. DynamoDB uses on-demand billing and automatically expires demo signatures after 30 days. It also applies these safeguards:

- one API request per second with a burst of two;
- the new-account Lambda concurrency quota as an account-level ceiling;
- a 10-second execution timeout;
- CloudWatch logs deleted after three days;
- email alerts at USD 0.10 actual gross usage and USD 1 forecast monthly usage.

The budget is an alert, not an immediate kill switch. AWS cost data can be delayed. The Free plan is the hard billing guard: AWS says it does not charge unless the account is upgraded to the Paid plan. Leave it on the Free plan.

## Deployment

Requirements: an AWS account, Docker, AWS CLI, and AWS SAM CLI.

```sh
cd aws
sam build
sam deploy --guided \
  --parameter-overrides \
  ApiToken="replace-with-a-random-token-of-at-least-24-characters" \
  BillingEmail="your-email@example.com"
```

SAM prints `VerificationEndpoint` after deployment. Put that URL and the same temporary token in `Config/Cloud.xcconfig`. In an `.xcconfig` file, write the URL as `https:/$()/host/path`; `$()` prevents `//` from being parsed as a comment.

The token is bundled into a configured demonstration build, so it is not suitable as long-term user authentication. Use a short-lived token, keep API throttling enabled, and rotate the token after judging. A production release should use user-scoped authentication such as Amazon Cognito and signed requests.

## Remove every deployed resource

After judging, run:

```sh
sam delete --stack-name weird-boots-verifier
```

Confirm removal in the prompt. This removes the Lambda function, HTTP API, DynamoDB signature table, short-lived log group, cost budget, and SAM-managed deployment artifacts. The shared-photo bucket is retained to avoid deleting shared photos accidentally; its objects expire through the 30-day lifecycle rule. After the desired retention period, empty and delete that bucket explicitly to remove the remaining resource.

## Photo-sharing API

- `POST /shares`, with the demo token: accepts `photo` (base64 JPEG, at most 2 MB encoded and 2000 px per edge) and `capturedAt` (Unix seconds). Returns a random 192-bit bearer share ID, HTTPS link and expiry.
- `GET /s/{shareId}`: public HTML landing page; no photo preview, analytics, or account login. Opens `recalllens://receive/{shareId}` with a manual fallback button.
- `GET /shares/{shareId}`: anyone holding the bearer ID can fetch the photo envelope before expiry. No listing endpoint is exposed. Repeated fetches return the same record UUID for deduplication.

The app downscales uploads to 1600 pixels. The server re-encodes them to remove metadata. S3 blocks public access and encrypts stored objects; Lambda has get/put access only under `shares/`. Expiry is checked on each download, independently of delayed S3 lifecycle deletion. The existing API throttle and budget also apply. The shared upload token remains a demonstration mechanism, not production abuse prevention. Recipients intentionally receive image bytes before visual unlock; the display rule is not cryptographic secrecy.

Run `.venv-aws/bin/python -m unittest -v test_handler.py test_sharing.py` from this directory. The two systems' image-retention semantics differ: the verifier's `imagesRetained: false` refers only to live verification requests, not explicitly shared uploads.

## API

Register a reference with `POST /references`:

```json
{"referenceId":"UUID","featureData":"base64 WBO5 ORB signature"}
```

Only the OpenCV keypoints and binary descriptors are retained. The handler rejects signatures at their 30-day expiry. DynamoDB TTL removes expired records asynchronously; deletion is not guaranteed at the expiry instant. Deploy the updated handler to enable this read-time check.

Send `POST /verify` with an `x-api-key` header and this JSON body:

```json
{"queryImage":"base64 JPEG","referenceId":"UUID"}
```

The response includes the server-owned `authorized` decision, `similarity`, geometric diagnostics, `registry`, `engine`, `durationMs`, and `imagesRetained`. The live image is limited to 2 MB.
