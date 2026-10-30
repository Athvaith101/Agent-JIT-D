# Judge testing instructions — fill these after deployment

- Live URL: OWNER MUST INSERT THE TESTED URL.
- Source repository: OWNER MUST INSERT THE PUBLIC REPO URL.
- Video: OWNER MUST INSERT THE PUBLIC VIDEO URL (under three minutes).
- Authentication: username `jitd`; password supplied privately by owner from JITD_ACCESS_TOKEN. Never provide a model API key.
- Start at `/demo`. Leave optional model use unchecked for the deterministic synthetic flow; check it only when server model access and quota have been verified.
- Click: Build/test/publish → clean run → unit drift/block → propose and inspect → approve reviewed candidate → retry → remove evidence/block.
- The repair screen is a review boundary. Inspect its impact and strict validation before approving. Named-role enterprise deployments require a different reviewer and are not the one-user shared demo profile.
- Open recorded Nemotron evidence to inspect imported live reports. If unavailable, the interface says so; template execution is not live inference.
- Inspect Studio receipts and CSV export. Cost projections are assumptions; historical UI observations are not an N-case benchmark.
- Data: synthetic invoices and synthetic ledger only. No bank or ERP writes occur.

## Three-minute recording

0:00–0:20: problem — valid JSON can change meaning, e.g. dollars to cents.
0:20–0:50: build with Nemotron on Nebius Token Factory, inspect actual provenance and provider tokens.
0:50–1:10: clean run, accepted, no model calls during execution.
1:10–1:40: unit drift blocked; show invalid evidence and acceptance=false.
1:40–2:20: bounded proposal, input impact, strict checks, reviewer approval, retry.
2:20–2:40: remove authority evidence, show UNKNOWN blocks without inference.
2:40–3:00: show measured paired usage only if collected; name omissions and synthetic scope.

Keep the model badge and actual receipts visible. Keep failures and deterministic fallbacks visible. The historical synthetic-demo.mp4 is not a live Studio demonstration.
