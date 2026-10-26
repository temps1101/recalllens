# OpenCV AI Competition 2026 submission checklist

Official Devpost deadline: October 26, 2026 at 11:45 p.m. PDT, equivalent to October 27 at 3:45 p.m. JST. Internal target: complete the submission by the evening of October 26 JST.

## Required deliverables

- [ ] Join the competition with the submitting Devpost account.
- [x] Create a personal AWS account on the Free plan and leave it on that plan.
- [x] Deploy the AWS Lambda verifier in `ap-northeast-1` and record its configuration.
- [x] Confirm the `WeirdBoots-Monthly-Cost` email budget exists.
- [x] Configure and launch the signed Recalllens build on the development iPhone.
- [x] Evaluate existing natural photographs and report the scope separately from device/network checks.
- [x] Compare four method families across 34 settings on a separate 144-photo pool; freeze tuning before held-out evaluation and disclose AI label provenance/exclusions.
- [x] Add method, threshold and runtime plots plus two additional real-photo illustrations; preserve all measured failures.
- [x] Include real-photo success and failure case figures; confirm publication selection before submitting.
- [x] Deploy the expiry fix and verify registration, matching, invalid-token and expired-reference responses.
- [x] Install and launch the updated development iPhone build while preserving its seven photos and six log entries.
- [x] Publish the judge-accessible source, report, instructions, tests and evidence at `https://github.com/temps1101/recalllens`.
- [x] Pin OpenCV 5 and Python dependencies.
- [x] Provide iOS build and AWS deployment instructions.
- [x] Provide the OpenCV 5 and AWS architecture diagram.
- [x] Document the free-signing limitation: no TestFlight build; judges receive the continuous real-device video, report and reproducible source package.
- [ ] State in the Devpost entry that a live screen-share demonstration is available to judges through Devpost contact; keep the AWS deployment active through judging.
- [ ] Publish a public or unlisted judge-accessible video of no more than five minutes.
- [ ] Submit the technical report covering problem, users, architecture, OpenCV 5, AWS, evaluation, limitations, and responsible use.
- [ ] After judging, run `sam delete --stack-name weird-boots-verifier`.

## Five-minute video structure

1. **0:00–0:25 — Problem:** digital photos lose their physical context; Recalllens uses a real view as the key.
2. **0:25–1:35 — Working application:** capture a photo, choose Save, show that an unrelated view does not unlock it, return to the scene, and open the unlocked photo.
3. **1:35–2:10 — Account-free sharing:** choose Share, open the HTTPS link, show the receipt without a preview, then reveal the received photo only from the matching scene.
4. **2:10–2:55 — OpenCV 5 and AWS:** show the architecture diagram while explaining ORB, Hamming KNN, RANSAC, local candidate selection, Lambda verification, DynamoDB expiry and private S3 delivery.
5. **2:55–3:50 — Results:** show the natural-pair result, broader held-out comparison and one visible failure case. Identify exploratory and synthetic evidence explicitly.
6. **3:50–4:25 — Reliability and privacy:** show the published deployed-check evidence for valid match, bad-token rejection and expired-reference rejection; state that unshared JPEGs remain local.
7. **4:25–4:50 — Reproducibility:** show the public repository, pinned dependencies, tests and technical report.
8. **4:50–5:00 — Closing:** restate the physical-world-as-key concept and offer a live screen-share to judges.

## Distribution without a paid Apple membership

The submitting Apple account is a free Personal Team. The app therefore cannot be distributed through TestFlight, Ad Hoc distribution or the App Store. Judges evaluate the continuous physical-device recording and the source package. A technically equipped judge may build the app on a physical iPhone with their own signing team; no private token is included. Friends can test the actual sharing flow by connecting their iPhones to the developer Mac and installing a free-signed build. This limitation must be stated plainly in the submission rather than presenting the development build as publicly installable.

## Submission positioning

**One-line description:** A private iOS camera that uses OpenCV 5 to turn a real-world view into the key that unlocks photographs captured from that scene.

**Core claim:** Visual correspondence changes the application state: the local index proposes a scene, while the AWS registry independently authorizes access using its stored OpenCV signature.

**Primary judging strengths:** original interaction, substantive OpenCV 5 geometry, clear physical-world action, privacy-bounded architecture, and a concise live demonstration.

Do not claim Agentic Vision or Best Use of COOL unless the implementation changes to meet those special-prize requirements.
