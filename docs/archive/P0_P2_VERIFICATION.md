# Integrated release verification — 27 October 2026

- Full suite: **177 passed in 48.65 seconds**, Linux Python 3.12.
- New coverage: durable pilot import, missing-evidence resolution, non-bypassable verification, stale review conflicts,
  original observation history, independent/provenance declarations, wrong/stale/identity/version evidence,
  measured full-input baseline accounting, failed model requests, import validation errors, fake evidence rejection,
  hosted auth fail-closed behavior, cross-origin mutation refusal, and HTTP capture-to-pilot content/version binding.
- JavaScript syntax checks pass for all four frontend modules.
- Browser: existing clean → drift → diagnose → propose → approve → recover → missing-proof halt flow passes.
- Browser: Pilot navigation → import missing-proof case → fresh evidence review → accepted shadow output → navigation
  away/back → reload persistence passes. Desktop and 390-pixel mobile inspected; no JavaScript errors or page overflow.
- Secret scan: clean. Synthetic demo data and internal screenshots are not bundled as customer evidence.
- Same-evidence recovery comparison rerun: five seeds x five cases x three methods = 75 trials, zero silent errors within
  this synthetic experiment. It still establishes no superiority of semantic slicing over equally guarded replay.
- Paired results and no-call preflight source fingerprints match packaged Python modules.
- No credentials configured; zero paid provider requests were sent. Readiness artifact retains pending external gates.

## Material limits

No real financial integration, independently authored incident corpus, live Nemotron quality/billing, customer ROI,
Windows runtime, Docker build, remote CI or public deployment has been evaluated in this session. Docker is unavailable
in the build environment. Deployment files and OS CI matrix are configuration, not executed results.

The new model comparison is a single-call full-input baseline, not a general iterative tool-using agent benchmark. Its
shared final monetary/business verification gate checks configured authority agreement; it does not establish field
correctness. Compiled execution retains additional mined checks. Pilot metrics report authority verification coverage
and reviewer-entered effort, with no fabricated correctness/false-alarm/cost denominator.

Hosted access is optional single-workspace Basic authentication over HTTPS, not enterprise identity or tenant isolation.
Reviewer names are entered text, SQLite is not encrypted, and audit records are durable rather than tamper-proof.
A provider version header and a source name remain trusted adapter assertions, not cryptographic independence proofs.

See RELEASE_P0_P2.md for commands, contracts, synthetic resolution demonstration and pending acceptance gates.
