# Agent Studio behavior and boundaries

Studio is a bounded builder for the existing USD invoice/payment workflow. It can save multiple named agents and published
versions in one workspace. It does not synthesize arbitrary tool graphs or coordinate a swarm of autonomous agents.

## Build

A supported task description maps to the invoice template. Task recognition is a conservative English keyword/scope filter,
not a general semantic understanding guarantee. Unrelated actions, arbitrary URLs and unsupported currencies are refused.
The fixed graph uses invoice.get, payment.list, normalize_money, sum_money, invoice_total, provider_status,
reconcile_amounts and post_ledger. Tool bindings and required evidence cannot be edited through the builder.
The supported executable parameter is max_pages, an integer from 1 to 20. USD, required evidence and synthetic output are locked.

Optional Architect inference proposes a template ID and bounded page parameter. The reply passes a strict schema; unknown
fields and out-of-range values are rejected. Raw response, exact model ID, usage and validation are recorded. A rejected or
unavailable reply produces a labelled deterministic fallback. A user override records human field provenance.
This is task-to-template configuration, not learning arbitrary executable code from a successful agent trace.

## Test and publication

Validation executes 28 fixed synthetic cases: 12 clean, 4 cosmetic, 4 unit drift, 2 missing evidence, 2 same-source evidence,
and 4 pagination cases. Clean/cosmetic cases must post the correct synthetic result; unsupported evidence must block;
pagination must either produce the correct complete output or block. The suite is authored with the implementation and
is not an independently authored corpus or proof of generalization.

Reports bind the draft hash, revision, case-set hash and Python runtime-policy hash. Editing a saved draft clears its current
report. A stale or foreign report cannot publish it. Publication requires a passing current report; in enterprise mode a
reviewer/admin different from the last editor must publish. An identical draft under the same policy cannot be published twice.
A source-policy upgrade requires retesting and a new publication, even if draft content stays the same.

Published base records have no update/delete API and SQLite triggers refuse ordinary updates/deletes. Someone controlling
the files can still alter database controls; this is not signed or independently immutable storage.

## Runtime and recovery

Each published version gets a separate Lab runtime beneath the data directory. The runtime starts from the exact approved
manifest hash. Draft edits do not change an existing runtime. An approved bounded repair advances the runtime manifest revision;
the original published base remains unchanged. Every run identifies both hashes.

Only the defined synthetic scenarios are available in Drift Lab. Evidence can be simulated independent, unavailable, or
same-source. Strict execution refuses acceptance without qualifying required evidence. Its configured authority observations
must be USD, snapshot-bound and sufficiently fresh. This release inherits the existing five-minute freshness limit; users
cannot relax it through Studio settings. Authority declarations still depend on the adapter's trustworthiness.

Repair uses the existing deterministic diagnosis and allowlisted parameter proposal. Optional Repairer inference is recorded
separately. Initial regression/static validation is followed by a fresh strict check on up to five current synthetic inputs.
Before approval, captured-input impact is recomputed, harmful changes to previously correct sampled outputs block promotion,
and fresh strict evidence is checked again. The exact stored accepted proposal is then revalidated through the existing repair
engine. A different reviewer is required in named-user mode. Changing authority to missing between proposal and approval blocks
promotion. A later runtime change without an approved binding fails closed for investigation.

## Counterfactual impact

The preview replays the last twenty captured synthetic inputs in memory and reports sampled inputs, changed outputs,
corrected outputs and previously correct outputs worsened. It also shows the actual changed/invalidation/reuse plan.
The captured-input replay disables the strict authority gate only for output-impact inspection; it cannot write to an
external system and cannot grant acceptance. Fresh strict checking is a distinct promotion requirement.

Its correctness reference is synthetic fixture truth. It is not independently adjudicated customer truth, live shadow traffic,
a complete blast-radius bound or a guarantee about unseen inputs. Inspect the case list and sample size rather than treating
zero harmful sampled changes as zero population risk.

## Evidence Passport

Accepted and blocked runs get chained receipts binding the full run record, output, runtime manifest, published base,
input identity, recorded source snapshot, required evidence observations, model-call count and review provenance.
Receipt downloads include the stored passport and a current chain verification. Altered run/output/manifest content is refused
when inspected. New execution is refused if the passport chain is invalid. Readiness/doctor include the Studio chain check;
offline restore verifies it too.

Retain exported chain heads externally. Full rewrite or tail deletion by someone controlling the disk is not independently
detectable. A receipt records why a policy accepted a result; it does not prove that an authority was factually correct.

## Comparison and economics

The selected-run comparison shows a saved strict run against schema-only in-memory replay of its captured synthetic input.
It is a mechanism counterexample, not an always-LLM or LLM-self-check experiment. The comparison records no external writes.
The UI leaves those model baselines “not measured”. No forecast or money-at-risk prediction is manufactured.

Cost & model usage displays real receipt fields when actual calls are made, labelled injected clients in tests, user-declared
review minutes and reviews without timing. Missing timing is not measured zero. Its cumulative cost curve and first strictly
positive break-even run count use explicitly entered assumptions, including review time. Defaults are illustrative and can
show a loss. They are not provider prices, measured savings or a benchmark. Different models may need different actual rates;
role routing alone does not establish a cost advantage.

## Storage and deployment

Use one workspace/process/worker. Studio serializes lifecycle operations and stores drafts, reports, versions, runs, proposals,
model receipts and passports in studio.sqlite3. Per-version Lab state is in studio_runtime. The UI shows the latest 100 run
records per version; the impact preview samples at most 20. These limits are not a lifetime retention policy.
Offline backup includes these records and runtime files. An interrupted promotion can leave a runtime/binding mismatch;
inspect its audit/checkpoints before recovery rather than rerunning uncertain operations.
POST Studio execution uses the same persistent actor-scoped idempotency mechanism as the existing execution API. Other
mutations use revision/status checks and are not generically idempotent. No distributed exactly-once guarantee is made.

## Status against the expanded platform plan

| Plan area | Current release |
|---|---|
| Build/Test/Versions/Runs | Implemented for one fixed invoice family |
| Architect and Repairer | Implemented optional model calls; real provider validation still requires credentials/results |
| Diagnosis, verification, execution | Deterministic; no additional model role claimed |
| Evidence Passport and recorded-input impact | Implemented with the scope above |
| Cost curve and break-even | Assumption-based sensitivity; measured baseline remains open |
| Tiered model IDs | Configurable Architect/Repairer IDs; no measured routing benefit |
| Prompt caching, forecast, schedules | Proposed |
| Trace-to-general-procedure compiler | Proposed |
| Live shadow/canary and additional families | Proposed |
| Independent field evaluation and real-agent baselines | External evidence still required |
| SSO/MFA, tenant isolation, HA and production financial writes | Not implemented |
