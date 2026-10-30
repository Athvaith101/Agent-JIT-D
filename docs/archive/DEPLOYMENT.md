# Run and deploy

## Local Windows

Extract the entire ZIP, open `jitd`, and double-click `start_windows.bat`.
Python 3.12 is verified in this package. Python 3.11 is accepted by the launcher and included in CI configuration; Windows CI was not executed in this session.

Manual Command Prompt commands, from the extracted `jitd` folder:

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.lock
python -m jitd.launch
```

Visit http://127.0.0.1:8000. Stop with Ctrl+C. Linux/macOS: `./start.sh`.
The launcher loads optional `.env` values without overriding exported variables.
No Node build, frontend dependencies, CDN fonts or model credentials are needed for the simulator.

## Preserve state

`data/operations.sqlite3` stores the session, recent run records, model usage, pending proposals and ordered audit events.
Manifests, accepted guards and regression examples also have JSON copies in `data/`.
The API reloads the session when it starts. `JITD_DATA_DIR` changes the storage directory.
Back up the whole directory while the app is stopped. Run one process/worker per workspace.
Reset starts a fresh sandbox session while retaining historical audit events and manifest files.

## Optional Nebius/Nemotron

Copy `.env.example` to `.env`, fill in your key and model ID, and launch with `python -m jitd.launch`.
For `python -m jitd.live --compiles 3`, export those variables in the shell first.
The live harness records actual responses and failures; no live evidence is fabricated in this package.
`JITD_MAX_MODEL_CALLS` caps paid calls per process; restarting resets that cap. Provider input/output usage is captured when reported.

## Docker

```sh
docker build -t jitd .
docker volume create jitd-data
docker run --rm -p 127.0.0.1:8000:8000 -v jitd-data:/app/data jitd
```

The image uses Python 3.12 and pinned dependencies, runs as an unprivileged user, and includes a healthcheck.
Use runtime environment variables for provider secrets. Do not put keys in the image.
Docker and public hosting were not exercised in this session.
The included Render blueprint uses ephemeral `/tmp` storage for a disposable demo; use a persistent volume for durable state.

## Hosted access

This is a single-workspace prototype with no application authentication or multi-tenancy.
Use a trusted network or an access gateway for shared deployments. The default launcher binds to 127.0.0.1.
The API has per-IP limits, but those are not a substitute for access control.

## Verify

```sh
python -m pytest -q
python scripts/secret_scan.py
python scripts/run_demo.py
python -m jitd.bench --external benchmark/external
```

See FINAL_VERIFICATION.md for the actual checks performed on this build.

## AAIR modes and accounting

Home → Run demo opens strict AAIR execution. The evidence selector changes simulated authority availability.
An unavailable or same-source authority gives UNKNOWN and blocks posting. The legacy hard-case comparison is explicitly isolated.

Optional pricing environment variables are `JITD_PRICE_INPUT_USD_PER_M`, `JITD_PRICE_OUTPUT_USD_PER_M`, and
`JITD_RUNTIME_USD_PER_MS`. Use rates applicable to your model/host. If required values are unset or there are no correct
completed outputs, the metric is unpriced/undefined. Even with rates supplied, USD is an estimate rather than provider billing.

Reproduce the matched offline experiment:

```powershell
.\.venv\Scripts\python.exe -m jitd.aair_bench --seeds 3 --runs 60
```

Results are saved in `benchmark/aair/` and displayed on Performance. Real Nemotron evidence uses the existing live harness,
which now records provider token/latency observations and the subsequent AAIR retry's assumption/reuse trace.
