# Integration API

Use the running instance's authenticated `/docs` for the generated request schemas. Examples below target one
enterprise-profile workspace on loopback. Use HTTPS for remote access. Application passwords and the Nebius API key
are separate credentials; the model key belongs only in the server process.

## Execute from Windows terminal

`curl.exe --user operator` prompts for the application password; it does not put that password in command history.
Use a different idempotency key for each intentional new execution. Retain the key to retrieve the same response after a lost reply.

```powershell
curl.exe --user operator -X POST http://127.0.0.1:8000/api/executions -H "Content-Type: application/json" -H "Idempotency-Key: invoice-demo-0001" --data "{}"
```

The response includes run ID, input identity, outcome, evidence/contract results, events, workflow version and accounting.
The `X-Request-ID` response header correlates the request with application logs and security receipts.
This endpoint's writes remain in the synthetic ledger. It is not an ERP connector.

| Method and path | Purpose | Enterprise permission |
|---|---|---|
| GET `/api/state` | Current workflow, guards and state | Any authenticated role |
| POST `/api/executions` | Execute `{}` or retry `{"invoice_id":"..."}` | Operator/admin; idempotency key required |
| GET `/api/runs/{id}` | Inspect a retained run | Any authenticated role |
| POST `/api/runs/{id}/diagnose` | Localize a blocked run | Operator/admin |
| POST `/api/runs/{id}/propose` | Validate a deterministic bounded proposal | Operator/admin |
| POST `/api/runs/{id}/propose-model` | Request model proposal, with labelled deterministic fallback | Operator/admin; model configured/budget available |
| POST `/api/proposals/{id}/decision` | Approve/reject `{"approve":true}` | Reviewer/admin; approving actor must differ from proposer |
| POST `/api/workflow/pause` | `{"paused":true}` | Operator/admin |
| POST `/api/workflow/rollback` | Restore `{"version":"1.0.0"}` as a new version | Admin; workflow must be paused |
| GET `/api/runs/{id}/export` | Export retained run evidence | Any authenticated role |
| POST `/api/pilot/import` | Import supported recorded-case bundle | Operator/admin |
| POST `/api/pilot/{id}/review` | Re-evaluate evidence with optimistic revision | Reviewer/admin; actor comes from authentication |
| GET `/api/platform/ready` | Storage/audit readiness | Any authenticated role |
| GET `/api/platform/metrics` | Retained-state gauges | Admin |
| GET `/api/platform/audit` | Recent security receipts and chain verification | Admin |

All mutation bodies are capped at 2 MiB, including chunked requests, with a fifteen-second per-chunk read timeout.
The server limits active connections/work to 32 through the supplied launcher. Authenticated mutation throttling and
an enterprise ingress rate guard provide additional bounds; limits are process-local and proxy clients share a peer IP.

## Response handling

- 400: invalid execution idempotency key or request headers/host.
- 401: missing/incorrect application credentials.
- 403: role restriction, self-approval or cross-origin mutation.
- 409: stale version/revision, already-decided proposal, busy workflow or uncertain/conflicting execution reservation.
- 413: body exceeds the ingress limit.
- 422: request/case validation failed.
- 429: request throttled; observe `Retry-After`.
- 500: unexpected failure; investigate its request ID before repeating an operation.
- 503: configuration/storage/audit readiness failure or concurrency protection.

Error payloads retain compatibility with the existing API and may use `error.message` or FastAPI's `detail` field.
Do not automatically retry every mutation. Only POST execution has generic persistent key replay; other endpoints use
their specific state/revision safeguards. Unfinished reservations after an interruption remain blocked for inspection.
The legacy GET execution stream is disabled in the enterprise profile.

## Studio API

Studio is served at `/` and `/studio`. The original UI is at `/lab`. Builder permissions are distinct from execution permissions
in enterprise mode; local sandbox treats the local actor as admin and allows same-person publication/review.

| Method and path | Behavior | Enterprise permission |
|---|---|---|
| GET `/api/studio` | Draft/version list and passport-chain status | Any authenticated role |
| POST `/api/studio/drafts` | Name, supported task, bounded settings and optional use_model | Builder/admin |
| PUT `/api/studio/drafts/{id}` | Edit with required current revision | Builder/admin |
| POST `/api/studio/drafts/{id}/test` | Validate saved revision | Builder/admin |
| GET `/api/studio/reports/{id}` | Exact validation report | Any authenticated role |
| POST `/api/studio/drafts/{id}/publish` | Publish revision/report, optional declared review minutes | Reviewer/admin different from last editor |
| GET `/api/studio/versions/{id}` | Runtime state, saved runs, proposals and model receipts | Any authenticated role |
| POST `/api/studio/versions/{id}/configure` | Select supported synthetic scenario/evidence mode | Operator/admin |
| POST `/api/studio/versions/{id}/executions` | Execute/retry; Idempotency-Key required | Operator/admin |
| POST `/api/studio/versions/{id}/runs/{run}/propose` | Bounded repair with optional use_model | Operator/admin |
| POST `/api/studio/proposals/{id}/decision` | Exact-candidate approval/rejection | Reviewer/admin; separate approving actor |
| GET `/api/studio/runs/{id}/passport` | Stored receipt and current chain verification | Any authenticated role |
| GET `/api/studio/runs/{id}/comparison` | Captured-input schema-only comparison | Any authenticated role |
| GET `/api/studio/receipts/{id}` | Raw model receipt with source and validation | Any authenticated role |
| POST `/api/studio/cost/project` | Pure cost sensitivity from assumptions | Any authenticated role |

A draft request can be `{"name":"Invoice agent","task":"Reconcile invoices and payments against independent evidence.",
"settings":{"max_pages":1,"currency":"USD","required_evidence":true,"output":"synthetic_ledger"},"use_model":false}`.
Generated API schemas at `/docs` remain authoritative for complete fields and bounds. Imported arbitrary manifests, URLs,
code, disabled evidence or external sinks are not supported draft settings.
