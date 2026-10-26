# AWS sharing service

This optional AWS SAM application is used only for explicit sharing. Recalllens capture, storage and live scene matching remain on the iPhone and make no AWS request.

When Share is selected, the client uploads a downscaled, EXIF-free JPEG with its OpenCV 5 ORB signature. Lambda re-extracts ORB features from the uploaded image and rejects a mismatched pair. A validated pair is stored temporarily in private encrypted S3 and delivered through a random bearer link. After a recipient downloads the pair, all matching is local and can run offline.

## Local tests

```sh
python3 -m venv .venv-aws
.venv-aws/bin/pip install --requirement aws/requirements.txt
cd aws
../.venv-aws/bin/python -m unittest -v test_handler.py test_sharing.py
```

## Cost policy

Create a new **personal AWS account on the Free plan**. Do not upgrade it to the Paid plan for the competition demo. The stack has no continuously running server. Shared objects expire after 30 days. It also applies these safeguards:

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

SAM prints `VerificationEndpoint` after deployment (the historical output name is retained for stack compatibility; its URL now points to `/shares`). Put that URL and the same temporary token in `Config/Cloud.xcconfig`. In an `.xcconfig` file, write the URL as `https:/$()/host/path`; `$()` prevents `//` from being parsed as a comment.

The token is bundled into a configured demonstration build, so it is not suitable as long-term user authentication. Use a short-lived token, keep API throttling enabled, and rotate the token after judging. A production release should use user-scoped authentication such as Amazon Cognito and signed requests.

## Remove every deployed resource

After judging, run:

```sh
sam delete --stack-name weird-boots-verifier
```

Confirm removal in the prompt. This removes the Lambda function, HTTP API, short-lived log group, cost budget, and SAM-managed deployment artifacts. The shared-photo bucket is retained to avoid deleting shared photos accidentally; its objects expire through the 30-day lifecycle rule. After the desired retention period, empty and delete that bucket explicitly to remove the remaining resource.

## Photo-sharing API

- `POST /shares`, with the demo token: accepts `photo`, `featureData`, `featureAlgorithm`, and `capturedAt`. Lambda validates the image-signature pair with OpenCV 5 and returns a random bearer share ID, HTTPS link and expiry.
- `GET /s/{shareId}`: public HTML landing page; no photo preview, analytics, or account login. Opens `recalllens://receive/{shareId}` with a manual fallback button.
- `GET /shares/{shareId}`: anyone holding the bearer ID can fetch the image-signature pair before expiry. No listing endpoint is exposed. Repeated fetches return the same record UUID for deduplication.

The app downscales uploads to 1600 pixels. The server re-encodes them to remove metadata. S3 blocks public access and encrypts stored objects; Lambda has get/put access only under `shares/`. Expiry is checked on each download, independently of delayed S3 lifecycle deletion. The API throttle and budget also apply. The shared upload token remains a demonstration mechanism, not production abuse prevention. Recipients intentionally receive image bytes before visual unlock; the display rule is not cryptographic secrecy.

Run `.venv-aws/bin/python -m unittest -v test_handler.py test_sharing.py` from this directory. There are no reference-registration, live-frame verification, or listing endpoints.
