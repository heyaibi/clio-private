# Push-protection recovery

- The private push was rejected because a synthetic Slack-shaped test literal in the F-05 redaction evidence was detected by GitHub Push Protection.
- The literal was replaced with `REDACTED_SYNTHETIC_SLACK_TOKEN` in both findings artifacts and in ignored console captures. No credential value is recorded here.
- Original `findings.original.json` SHA-256: `846f629a98a163d3b071566fdee18c346d524ef67f4426b64c6248e887db26d8`.
- Redacted `findings.original.json` SHA-256: `36725d09ba1e17cc7caf39f54bf1505dc8ab2152b076df59f4bab2d252443f57`.
- The two local-only private commits are being rebuilt on `origin/master`; no force-push or push-protection bypass is used.
- The phase approval checkbox is returned to unchecked until finalize completes, and the ledger's public-HEAD attestations are re-attested for the already-pushed public commit.
