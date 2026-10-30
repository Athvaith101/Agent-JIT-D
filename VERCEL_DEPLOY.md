# Deploy the JIT-D demo on Vercel

This package includes a Vercel FastAPI entry point. It is suitable for a protected **hackathon demo/test deployment**, not a durable multi-user production service. Vercel runs FastAPI as a Function; its project filesystem is read-only and only `/tmp` is writable scratch space. This demo stores its SQLite data under `/tmp/jitd-data`, which can disappear or differ between function instances. The UI's Models & keys credentials are also process-memory only. Do not store financial or personal data here.

## Deploy from a public Git repository

1. Extract this ZIP and push the contents of the `jitd` directory to a new public GitHub, GitLab or Bitbucket repository. Keep the included `LICENSE`. Never commit `.env`, provider keys, or real customer records.
2. In Vercel, import that repository. Set the **Root Directory** to the directory containing `index.py`, `requirements.txt`, and `vercel.json` (the repository root if you pushed the contents of `jitd`). Let Vercel detect FastAPI and install `requirements.txt`; do not set a custom build command.
3. Add these environment variables in Vercel Project Settings for **Production** and **Preview**:

   - `JITD_ACCESS_TOKEN`: a long random password. This protects every route except health. Share it only with authorized testers through a private channel. The Basic Auth username is `jitd`.
   - `JITD_REQUIRE_AUTH`: `1` (also set by the entry point if omitted).
   - `JITD_MAX_MODEL_CALLS`: `0` by default. This prevents accidental hosted model calls.
   - Keep `JITD_MAX_MODEL_CALLS=0`. This entry point intentionally refuses nonzero values. Do not add a model key to this preview; use Render for live inference and persistent state.


4. Redeploy after setting variables. Open the deployment URL and sign in with Basic Auth (`jitd` plus your `JITD_ACCESS_TOKEN`). `/api/health` can be opened without auth; the app itself should require auth.
5. Test `/`, `/builder`, `/studio`, `/operations`, and one safe synthetic clean/drift/missing-evidence flow. Model-backed drafting and repair belong on the later Render deployment.

## Important Vercel boundaries

- `/tmp` is temporary. A redeploy, cold start, scale-out or different Function instance can lose or fail to share SQLite runs, audit history, and persistent call reservations. The app may restart with empty state. Do not claim durable history or a persistent global call ceiling on this deployment.
- The Visual Builder's **Models & keys** entries live only in one Python process. They can vanish or be unavailable on another Function instance. For a limited demo, prefer one deployment instance and test the exact URL repeatedly; Vercel does not guarantee a single persistent instance.
- Use only the bundled synthetic examples. Do not enter real invoices, credentials, or sensitive data. No real external financial writes are performed.
- This deployment config has not been run on the user's Vercel account. Complete a Vercel preview deployment and smoke-test it before submitting its URL. ZIP packaging and local import checks do not certify a cloud deployment.
- For durable judge testing or enterprise use, replace local SQLite and process memory with managed persistent database/secret storage, and redesign limits/idempotency for multiple concurrent Function instances.

## Local parity check

From PowerShell in this directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:JITD_ACCESS_TOKEN = "choose-a-long-private-demo-password"
$env:JITD_REQUIRE_AUTH = "1"
$env:JITD_MAX_MODEL_CALLS = "0"
.\.venv\Scripts\python.exe -m jitd.launch
```

Local launch uses `http://127.0.0.1:8000`; the Vercel adapter provides the same FastAPI application under Vercel Functions.
