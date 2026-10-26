# Security and privacy

Recalllens is a competition prototype. Local mode is the safest default: captures remain in the app's private storage and visual matching runs on the iPhone.

## Public repository

This repository must not contain:

- `Config/Cloud.xcconfig` or any deployed API token;
- private photographs, EXIF location data, or Photos-library exports;
- AWS credentials, device backups, or signing material.

The ignored paths and submission packager enforce these exclusions, but contributors should still review staged files before every push.

## AWS demonstration boundary

The AWS stack is optional. Its shared API token is embedded in a configured app build, so it is not production authentication. Anyone who extracts that token can use the protected demonstration endpoints until it is rotated. Deploy the stack only for controlled testing, retain throttling and budget alerts, and rotate or delete it after judging.

Shared-photo links are bearer links. Anyone who obtains a valid link can download its image until expiry. The server removes EXIF metadata, uses private encrypted S3 storage, and exposes no listing endpoint, but the link is not proof of identity or physical presence. A recipient receives image bytes before the app visually unlocks them.

Before a public multi-user release, add user-scoped authentication, per-user authorization, abuse controls, revocation, a privacy policy, and a security review.

## Reporting

Do not open a public issue containing credentials, private images, or precise location data. Revoke exposed credentials first, then contact the repository owner privately through their GitHub profile.
