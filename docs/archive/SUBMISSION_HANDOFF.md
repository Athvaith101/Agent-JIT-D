# Final submission handoff

Positioning: **JIT-D verifies and recovers recurring invoice workflows using explicit evidence gates and bounded model proposals.**
Semantic slicing is experimental; the current matched study does not establish superiority over ordinary dependency replay.

## Status that must remain visible

This build has no configured Nebius credentials, GitHub publishing credentials, Windows host or authenticated video-upload
connection. It cannot produce real provider results, publish your repository, upload a public video, or certify Windows
execution. The included recording demonstrates synthetic services on Linux. It does not depict a live Nemotron call.
Independent cases must be supplied by a person outside implementation; the project author cannot manufacture independence.

## Collect actual model results

Use PowerShell from the extracted project folder:

```powershell
$env:NEBIUS_API_KEY="your-key"
$env:NEBIUS_MODEL_ID="exact-Nemotron-model-ID-from-your-account"
$env:JITD_MAX_MODEL_CALLS="12"
.\.venv\Scripts\python.exe -m jitd.live --plan --compiles 1
.\.venv\Scripts\python.exe -m jitd.live --compiles 1 --out evidence/submission
```

Do not paste keys into issue reports or commit .env. Retain rejected proposals and fallbacks. The readiness page now
separates connectivity-only results, validated model contributions with incomplete usage, and contributions with complete
usage. Baseline files checkpoint each completed case; completed=false means interrupted/incomplete, never final evidence.

## Public repository and judge access

With Git and GitHub CLI installed and signed in on your computer, from the project root:

```powershell
python scripts/secret_scan.py
git init
git add .
git commit -m "Agent JIT-D verified recovery submission"
gh auth login
gh repo create agent-jitd --public --source . --remote origin --push
```

Check staged contents before pushing; exclude recordings containing private business data. LICENSE and README are included.
Add the repository URL to Devpost. Use the Docker/Render configuration for an HTTPS demo, or provide an accessible test-build
URL with installation instructions. Configure hosted access and give judges the demo credentials through the submission's
appropriate access instructions. Never provide a provider API key as a demo password.

## Windows acceptance

Extract the exact delivered ZIP into a clean directory. Then:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m jitd.launch
```

Exercise clean execution, unit drift, repair approval/retry and pilot evidence refresh. Save your actual terminal output and
Python version. A Linux test pass or CI configuration is not a Windows execution result.

## Independent example and video

Ask an external reviewer to author and freeze a small case set before evaluation. Preserve author, collection method,
permission, source of reference values, input hashes and expected business outcomes. Import using Pilot & readiness.
An authorized real invoice/settlement example can establish integration feasibility; it does not establish population accuracy.

The included demo recording covers the synthetic mechanism. Record your actual Nemotron run and explain the model-generated
plan/repair, validation outcome, usage and fallback behavior before publishing the final public video. Follow the three-minute
script in RELEASE_P0_P2.md. Upload to your public YouTube account and add its URL to Devpost. Do not describe this Linux
synthetic recording as real-provider, independently authored, or Windows evidence.
