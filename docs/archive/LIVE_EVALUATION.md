# Measured Nemotron evaluation gate

This release strengthens the existing live harness. It does not include a real provider result: no credentials were supplied.
The harness still evaluates synthetic invoice workflows, even when the model calls are real.

## Windows PowerShell commands

From the extracted project directory with the virtual environment installed:

```powershell
.\.venv\Scripts\python.exe -m jitd.live --plan --compiles 1
```

This preflight sends no requests. It prints configuration presence, remaining request budget, a conservative request bound,
and the source fingerprint. It never prints the API key. Choose the model ID from your Nebius account; this package does
not assume that a particular model remains available.

To run the paid evaluation with your own account:

```powershell
$env:NEBIUS_API_KEY="your-key"
$env:NEBIUS_MODEL_ID="your-nemotron-model-id"
$env:JITD_MAX_MODEL_CALLS="12"
.\.venv\Scripts\python.exe -m jitd.live --compiles 1 --out evidence/my_run
```

Alternatively configure the root .env file. Exported variables take precedence. The current NEBIUS_BASE_URL is resolved
when constructing the client, so .env overrides work. `compiles` accepts 1 through 10. Unset external CSV evidence while
running this synthetic study. The request cap is process-wide, counts failed dispatched requests, and blocks further calls
before dispatch. SDK automatic retries are disabled to avoid uncounted repeat requests. A request count limit is not a dollar
spending limit. Provider charges and quotas may apply to unsuccessful requests; choose account billing limits separately.

## What is recorded

- Real versus injected-client provenance; injected test clients are never labelled real provider evidence.
- Smoke result without saving arbitrary model reply text.
- Validated model plans versus explicitly labelled deterministic compilation fallbacks.
- Model repair proposals accepted by isolated validation versus deterministic fallback repair acceptance.
- Strict recovery traces and fixture-oracle outcomes after accepted repair.
- Per-request phase, model, reported input/output/total tokens, latency and failure status.
- Failed requests with unknown tokens; they are never silently reported as zero billing.
- A summary with completeness flag, reported-token lower bounds, accepted model repairs and correct recoveries.

USD remains undefined in this evidence summary. Token totals are not a bill and missing provider usage cannot support
an exact cost claim. Compilation successes and repair acceptance rates must use their respective attempted-stage denominators.
A correct fallback recovery is not a successful model repair.

JSON is atomically checkpointed after each completed smoke/compile/repair stage and finalized at the end. If interrupted
mid-stage, completed stages remain available; calls within the unfinished stage may not yet be persisted. No finished_utc
means the run is incomplete. A Markdown report is written only after collection returns. Failed or rejected results are kept.

## Interpreting the result

This evaluates model-assisted planning/repair against controlled invoice fixtures. It is not a measured repeated-reasoning
baseline, production API benchmark, independently authored drift corpus or evidence of customer savings. A future paired
real-agent comparison must use identical cases, evidence, verification standard and attributable costs. Do not count the
existing modelled baseline as a real provider run.

No live JSON result is bundled as if a paid run happened. Scripted-client tests validate accounting, budget exhaustion,
failure retention, provenance, .env base URL behavior and progress callbacks. Before submission, run this command with
credentials and retain failed proposals alongside successes; inspect the summary's source_mode and usage_complete flags.
