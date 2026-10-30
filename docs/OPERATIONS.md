# Operation and recovery

This release supports one workspace, one process and a synthetic invoice ledger. The enterprise profile adds named-user
access, role enforcement and controlled repair promotion. It is a hardened pilot, not an enterprise certification.

## Named users on Windows

Use PowerShell in the extracted `jitd` directory. No activation script or BAT file is needed.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m jitd.admin user-add admin --role admin
.\.venv\Scripts\python.exe -m jitd.admin user-add operator --role operator
.\.venv\Scripts\python.exe -m jitd.admin user-add reviewer --role reviewer
.\.venv\Scripts\python.exe -m jitd.launch --profile enterprise
```

Each user command prompts for a unique password of at least fourteen characters, twice, with input hidden. Passwords are
stored as independently salted PBKDF2-SHA256 hashes with 600,000 iterations. No default users or passwords are bundled.
Open http://127.0.0.1:8000 for Studio (or /lab for the original lab) and enter a created username/password in the browser's authentication prompt.
Use separate browser profiles or different browsers for operator and reviewer. Two private windows may share credentials. Basic authentication is cached by browsers;
closing the applicable private context is the reliable way to end its session. This prototype does not implement SSO/MFA.

| Role | Permitted operations |
|---|---|
| Viewer | Read workflow/evidence/status; no execution or mutation; no detailed security export |
| Builder | Create/edit/test Studio drafts; cannot publish or execute |
| Operator | Execute/configure Studio runtimes and propose repairs; original lab execution controls; cannot approve/reset/rollback |
| Reviewer | Read, approve/reject proposals and review pilot evidence; cannot execute or change scenarios |
| Admin | Operator controls plus reset, rollback and detailed receipts; still cannot approve their own proposal |

Enterprise promotion requires a proposal from an authenticated actor. A different admin/reviewer approves it; approval
revalidates the exact accepted bounded parameter proposal on the failing input, fresh inputs and stored regressions.
There is no direct-repair or legacy unsafe-comparison route in this profile. Reviewer notes cannot bypass the evidence gate.

## Connect a model through the terminal

Stop the server with Ctrl+C first. Confirm promotional balance and top-up settings in your Nebius account before enabling
inference. The default ceiling is zero. Setting twelve below enables **at most twelve total reserved attempts in this data
directory**, not twelve per restart or per browser. Existing CLI/server attempts share this ledger through the supplied entry points.

```powershell
$env:NEBIUS_MODEL_ID = "COPY_THE_EXACT_NVIDIA_MODEL_ID_FROM_NEBIUS"
$env:JITD_MAX_MODEL_CALLS = "12"
$env:JITD_MODEL_MAX_OUTPUT_TOKENS = "4096"
.\.venv\Scripts\python.exe -m jitd.launch --profile enterprise --ask-api-key
```

The key is entered at a hidden terminal prompt, remains in that server process and is not written to configuration files,
HTML or audit receipts. Environment variables supplied by an operator take precedence over `.env` values. Model IDs are
not secrets. The inference endpoint is restricted to the approved HTTPS Nebius Token Factory hosts in this profile.
Select **Compile with Nemotron**, or diagnose a blocked run and select **Propose repair with Nemotron**. Inspect the recorded
proposal source: a deterministic fallback is not a successful model contribution. Configured does not mean connected or validated.

The optional output override gives reasoning models room to return the final JSON. It is an output-token ceiling per call,
not proof of response quality. Without the override, each workflow phase uses its smaller existing token limit.

The attempted-call cap reserves **before** dispatch and does not refund failures or interrupted calls. Unknown usage stays
unknown. It is not a dollar cap, a guarantee of free inference, or access to the account's billing balance. Disabling top-ups
and monitoring available credits are account-level actions. Increase the absolute limit deliberately only after checking usage.
Running multiple data directories creates separate caps and therefore does not protect an account-wide budget.

Offline live-run preflight and explicit evidence collection:

```powershell
.\.venv\Scripts\python.exe -m jitd.live --compiles 1 --plan
.\.venv\Scripts\python.exe -m jitd.live --compiles 1 --ask-api-key
```

Only the second command performs inference. Its receipts remain separate from synthetic benchmark results. Do not publish
the local data directory or customer recordings. The exact model's access and actual quality must be checked in your account.

## Inspect and correlate

`/operations` shows profile, current identity, budget, reported usage, audit-chain validity and workflow pause state.
Admins can view/export the last 500 security receipts. The normal workflow audit remains available separately.
Every response has an application-generated `X-Request-ID`; structured request logs and security receipts use that ID.
Security receipts omit bodies, credentials and query strings. They contain named actors and operation paths.

- `/api/health`: public process liveness. It does not assert successful model calls.
- `/api/platform/ready`: authenticated storage and audit check; 503 if unhealthy.
- `/api/platform/metrics`: admin-only Prometheus-style gauges of retained runs, reserved model attempts and unknown usage.
- `/api/platform/audit`: admin-only recent receipts with a full-chain verification result.

```powershell
.\.venv\Scripts\python.exe -m jitd.admin doctor
.\.venv\Scripts\python.exe -m jitd.admin audit-verify
```

The local SHA256 chain detects changes relative to the recorded chain. Preserve exported heads externally. Tail deletion
and a full database rewrite by someone controlling the disk are not independently detectable. It is not signed/WORM storage.

## Execution retries

Enterprise execution is `POST /api/executions` with JSON `{}` or `{"invoice_id":"..."}` and an `Idempotency-Key` header
(8–128 letters, digits, underscore, dot, colon or hyphen). The UI supplies a fresh key for each intended new execution.
The same actor/key/body returns the saved result; different input or an unfinished reservation returns 409.
After a crash or lost connection, inspect execution history before taking further action. An uncertain reservation is
never automatically repeated. This protects this API entry point; it is not a distributed exactly-once financial-write guarantee.
Other mutation endpoints rely on their existing version/revision/status checks and are not generically idempotent.

## Back up and restore

Stop the server and all other writers before these commands. A cross-platform exclusive lock rejects a running instance.
The backup uses SQLite's backup API, includes workflow/regression files, identities, request reservations and usage limits,
and embeds SHA256 checksums for every included file. It contains business data and password hashes; protect it accordingly.
No API key or `.env` file is included by the supplied layout. Keep custom secrets outside the data directory.

```powershell
.\.venv\Scripts\python.exe -m jitd.admin backup --output ..\jitd-backup-20261029.zip
.\.venv\Scripts\python.exe -m jitd.admin restore ..\jitd-backup-20261029.zip --target ..\jitd-restored
$env:JITD_DATA_DIR = (Resolve-Path ..\jitd-restored).Path
.\.venv\Scripts\python.exe -m jitd.admin doctor
.\.venv\Scripts\python.exe -m jitd.launch --profile enterprise
```

Restore never overwrites an existing directory. Inventory, size/path/checksum checks run before writing; SQLite integrity
and the audit chain are verified afterward. Checksums establish integrity, not authenticity: trust the archive's source.
Restoring an old backup also restores old spending counters; reconcile later usage before enabling inference again.
Recovery time and recovery-point objectives depend on your backup frequency and deployment; no SLA is claimed.

User administration is offline to avoid conflicting writes. Stop the server, then use:

```powershell
.\.venv\Scripts\python.exe -m jitd.admin user-password operator
.\.venv\Scripts\python.exe -m jitd.admin user-disable operator
```

On Windows, restrict the data directory's NTFS permissions to the service administrator/account. The application does not
replace OS access controls or encrypt SQLite files. Linux-created identity/backup files use restrictive file modes.

## Container deployment

Docker/Compose are optional; native Python is the simplest Windows path. The container runs as UID 10001, with read-only
application files, a writable named data volume and temporary validation storage. It requires named-user initialization:

```powershell
docker compose build
docker compose run --rm jitd python -m jitd.admin user-add admin --role admin
docker compose run --rm jitd python -m jitd.admin user-add builder --role builder
docker compose run --rm jitd python -m jitd.admin user-add operator --role operator
docker compose run --rm jitd python -m jitd.admin user-add reviewer --role reviewer
docker compose up -d
```

Compose binds only to 127.0.0.1. For remote access, terminate HTTPS with a reverse proxy, set `JITD_ALLOWED_HOSTS` to the
actual hostname and retain Basic authentication. A Caddy template is in `deploy/Caddyfile`. Do not trust forwarded headers
from arbitrary peers. A shared proxy IP intentionally shares ingress throttling in this release.
Use **one instance and one worker**. Horizontal scaling, Redis queues, PostgreSQL and multi-tenant separation are not implemented.
The old free-host configuration is archived as a disposable shared-password demo; it is not the enterprise deployment path.

## Release acceptance

Run `python -m pytest -q`, `python scripts/secret_scan.py`, then the clean → unit drift → proposal → different reviewer →
retry path. Test the downloaded ZIP on your actual Windows laptop and verify all public links before submission.
Linux tests do not establish Windows execution, Docker runtime success, paid model quality or customer production readiness.

Studio adds its own SQLite database and per-version runtime directories beneath the same data directory. Offline backup includes them. Doctor and readiness also inspect the Studio passport chain. See STUDIO.md for immutable base versus approved runtime revision semantics.

The System & access pause indicator and original workflow pause/rollback routes refer to `/lab`, not a global kill switch for every Studio runtime. Studio evidence mode is configured per published runtime. Legacy retained-run metrics describe the original Lab; Studio run history is available through its version API.
