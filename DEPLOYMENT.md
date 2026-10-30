# Deploy Agent JIT-D

## Recommended: one persistent Render service

This ZIP is prepared for a single-process demonstration with persistent SQLite state. It has not been deployed to your account. Render persistent disks require a paid service; confirm the current plan and disk charges in your dashboard.

1. Extract the ZIP. Push the **contents of the `jitd` folder** to the root of your GitHub repository. `render.yaml`, `Dockerfile` and `requirements.txt` must be at that root.
2. In Render, create a Blueprint and select the repository. Review the service and disk settings before creating it. `render.yaml` configures one Docker web service, one persistent disk at `/app/data`, and health checks at `/api/health`.
3. Keep one instance and one worker. The launcher enforces a process lock and starts one Uvicorn worker. Do not use autoscaling or an alternate multi-worker command.
4. Read the generated `JITD_ACCESS_TOKEN` in Render's environment settings. Browser Basic Auth uses username **jitd** and this token as password. Provide it privately in judge testing instructions.
5. Model calls default to zero. For optional live calls, add `NEBIUS_API_KEY` privately in Render, confirm your account's exact `NEBIUS_MODEL_ID`, and set a deliberate attempted-call ceiling in `JITD_MAX_MODEL_CALLS` (for example 20 for a short rehearsal). This is not a dollar limit. Check provider billing controls too. The persistent budget records previous attempts and failures.
6. Open the actual service URL, sign in, and open `/demo`. Complete all seven steps. Repeat five times and after a restart; verify versions, passports and call counts persist. Also check `/api/health`, `/studio`, `/builder`, and the Lab SSE flow if you plan to show the Lab.
7. Put the tested URL, private judge credentials, source URL and public demo video URL into the submission. Never put the Nebius key into the repository or testing instructions.

The shared demo profile allows one user to build and review synthetic examples. It is not the separate-reviewer enterprise profile. UI-entered model connections remain in memory and must be reconnected after restart. Server-configured keys are the reliable route for the Studio demo. Durable disk preserves records and the budget; it does not make UI keys durable.

## Vercel preview

`index.py` and `vercel.json` remain available for an **ephemeral, zero-model-call preview**. Web assets, fonts, benchmark files and evidence are explicitly included. Calls above zero fail startup on this target to prevent a per-instance ceiling from being mistaken for a global cap. `/tmp` records and UI-entered connections may reset or differ across instances; this target is not the recommended host for the full lifecycle demo. Do not promise persistent state on it.

In Vercel, set root directory to the repository directory containing `index.py`, set `JITD_ACCESS_TOKEN` privately, leave `JITD_MAX_MODEL_CALLS=0`, and verify the exact deployed URL. Asset bundling and cold starts remain account-level checks.

## Local Windows

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m jitd.launch
```

Open http://127.0.0.1:8000/demo. For optional server model access, set model ID, base URL, call budget and output limit before starting with `--ask-api-key`. Use the hidden prompt for the key. No external account is required for the deterministic synthetic demo.

## Collect real evidence before submitting

In PowerShell inside the project folder:

```powershell
$env:NEBIUS_MODEL_ID = "nvidia/nemotron-3-super-120b-a12b"
$env:NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
$env:JITD_MAX_MODEL_CALLS = "20"
$env:JITD_MODEL_MAX_OUTPUT_TOKENS = "4096"
.\.venv\Scripts\python.exe -m jitd.live --compiles 3 --plan
.\.venv\Scripts\python.exe -m jitd.live --compiles 3 --ask-api-key
```

The second command can make paid requests. It records successes, failures and fallback separately. Keep the generated `evidence/live_*.json/.md` unedited. Inspect before publishing. The recorded-evidence view shows a strict projection of provider reports; it does not imply a new request or independent provider attestation.

For paired usage, run `python -m jitd.model_baseline <case1.json> <case2.json> ... --ask-api-key --output evidence/model_baseline.json` on independently authored validated capture bundles. It supports at most 20 per invocation; use separate files for additional batches. Report both gates' acceptance, failures, incomplete usage, and all setup/audit/repair/review costs separately. This baseline is a full-input single-call comparison, not an iterative tool-using agent.

No hosted smoke test, paid-model collection, Windows run or Docker image build is claimed unless recorded in docs/FINAL_VERIFICATION.md.

## Configuration references

Render Blueprint syntax and current compute plan IDs: https://render.com/docs/blueprint-spec

Vercel Python bundling: https://vercel.com/docs/functions/runtimes/python

Vercel function include/exclude fields: https://vercel.com/docs/project-configuration/vercel-json
