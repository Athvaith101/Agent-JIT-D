# Architecture and assurance boundary

Invoice/payment provider → immutable read set → typed invoice recipe → structural/business contracts → required assumption verification → in-memory ledger sink. A blocked run can produce a bounded model/deterministic proposal; validation and operator approval precede version promotion and snapshot-safe recovery.

The sink executes only if every required assumption is VALID against the configured freshness, identity, source and snapshot checks. These checks rely on trusted adapters: source names, independence declarations and version headers do not authenticate real-world truth. When authority and provider drift together, wrong outputs can pass. See EVALUATION.md.

| Module | Role |
|---|---|
| ops.py | Allowlisted invoice operations |
| operations.py | Workspace UI read model |
| compiler.py | Typed plan, golden fixture validation, declared/mined contracts |
| assumptions.py | Required VALID/INVALID/UNKNOWN observations |
| executor.py / recovery.py | Strict execution and checkpoint-integrity checks |
| diagnosis.py / repair.py | Heuristic localization, bounded proposals, isolated validation |
| sdk.py / integrate.py | Complete recording schema/cursor validation and file evidence |
| http_connector.py / shadow.py | GET-only remote capture; immutable version binding |
| pilot.py | Durable review/reverification and observed-evidence history |
| live.py / model_baseline.py | Optional measured model proposals, actual usage, partial checkpoints |
| stream_stats.py / authority_study.py | Stream-level uncertainty and synthetic trust-boundary failures |
| server.py | Local FastAPI UI; optional authenticated hosted workspace |

Only one invoice workflow and two repair families are supported. General compilation, independent field accuracy and optimal recovery policy remain unproven. POSIX/Windows worker isolation is a scrubbed subprocess with timeout, not an OS security sandbox. Hosting uses a shared workspace credential, not per-user identity or tenant isolation.

Origin checks compare normalized host/port across TLS termination without trusting arbitrary forwarded hosts. Configure HTTPS at the host. CSP forbids external scripts/frames; inline styles remain explicitly allowed for the existing graph/UI. /api/health is public; container routes fail closed without the configured access token.

## Enterprise pilot boundary

The existing typed executor remains the workflow engine. `boundary.py` adds bounded HTTP ingress, authenticated role checks,
request IDs and execution idempotency. `platform.py` owns named identities, SHA256-chained security receipts and atomic
model-call reservations. `admin.py` provides an exclusive process lock and offline user/backup/restore operations.
The separate `/operations` page reads these controls without making inference requests. See OPERATIONS.md and API.md.

Approval now uses the exact saved accepted parameter proposal. It revalidates that proposal against the failing invoice,
fresh inputs and regression recordings before promotion. Enterprise self-approval and direct repair routes are refused.
Security receipts and business checkpoints are separate transactions: an interrupted operation may leave a started receipt
without a finished receipt. Such uncertainty must be investigated; it is not evidence of success or exactly-once posting.

## Studio lifecycle layer

`studio.py` stores typed bounded drafts, validation reports, immutable published bases, per-version runtime bindings, model
receipts and evidence passports. `studio_api.py` exposes the lifecycle outside the ASGI event loop. It calls the existing
compiler/executor/Lab; it does not introduce generated Python or a second execution language. `web/studio.html` is the new
home page. `/lab` preserves the original workflow UI. See STUDIO.md for exact boundaries and PLAN_REVIEW.md for claim corrections.
