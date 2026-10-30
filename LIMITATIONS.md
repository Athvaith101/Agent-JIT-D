> Release 2.3 adds a separate visual workspace with ten bounded JSON templates. The invoice Studio retains its deeper recovery integration. See docs/VISUAL_BUILDER.md (or VISUAL_BUILDER.md from this directory) for current scope. Earlier sections below describe the original Studio.

# Limitations (read before quoting any number)

**Evidence**
- Everything is a mock provider with synthetic data. The contracts, hypotheses and scenarios were written by the same author; the benchmark is not an external or real-traffic evaluation.
- Scenarios are tagged `dev` (used while building) or `heldout` (evaluated afterwards, thresholds untouched). One process caveat: the golden corpus used for mining was raised from 60 to 400 runs after false positives appeared on the dev `clean` scenario; heldout scenarios were visible in that same run. The ×3 range margin and 0.01 tolerance never changed.
- No real Nemotron run is included. The Nebius path is covered with fake clients (success, rate limit, timeout, malformed JSON, bad plan, bad repair). Compile and repair with a real model are untested here, and the model's plan/repair quality is unknown.
- Agent baselines are modelled, not run: assumed correct on every run, with assumed tokens, prices and latency. Cost is an estimate under those assumptions.
- Repair validation inside the benchmark runs in-process (same function as the isolated worker); the demo and API use the isolated process.

**What JIT-D does not catch or does badly**
- **Whale invoices:** legitimately huge invoices are held for review (16.3% false-block rate on that scenario) because a magnitude warning cannot separate them from a unit shift on one run.
- **Consistent drift:** if invoice and payments scale together, arithmetic checks pass; only magnitude ranges can notice, and small invoices stay in range (97/2282 silent errors).
- **Compound faults** are not repaired (correctly halted). Only two repair types exist: a unit divisor from a cutover time, and a page limit.
- **Mined contracts** assume the golden corpus represents normal data; tails produce rare false positives (2/2343 on clean).
- Localization is a hand-built hypothesis set over an 8-step graph. It will not generalize to arbitrary workflows, and the suspicion score is not calibrated.
- The oracle is fixture truth. In production there is no oracle; the contract checks (and a second source such as the invoice) must stand in, and they are weaker.
- A repair keyed to a cutover timestamp assumes you can date the change; a provider that rolls out gradually breaks that assumption.

**Not production software.** Basic Auth and an optional named-role profile are included. Tenant isolation and real financial integrations are not included. Local SQLite persistence is included; this remains a single-process prototype. Repairs are data parameters, not generated code, by design.

## Added 2026-10-22
- **No provider evidence file is bundled in this release.** `evidence/README.md` explains how to produce it with `python -m jitd.live`. Until then the model path is only tested with scripted fake clients.
- **The "external" scenarios are written by the JIT-D authors** and are labelled not independent. No independent scenario set exists.
- **Hard case:** when both sources scale together JIT-D has no repair and only a warning-level magnitude check (97/2282 silent errors in the benchmark). A human must decide.
- **Mined contracts can cost availability:** tax_in_cents shows a 74.6% false-block rate relative to the benchmark ledger oracle. Contrary to the earlier improvement note, invoice tax IS read by invoice_total and the declared arithmetic invariant. Removing that invariant would hide a business consistency problem. The rate is retained and disclosed.

## Added 2026-10-25
- The saved benchmark result `bench_20261022T010900Z_17ec0ad2.json` records an earlier `code_version` than the final code. Re-running `python -m jitd.bench --external benchmark/external` on the final code reproduced every one of the 72 scenario-by-strategy cells (counts and repair outcomes identical).
- The model-call cap, CI workflow, Render blueprint and Docker healthcheck were added after the benchmark; they do not touch the benchmarked code paths.
- Not carried over from the earlier checkpoint-N line: second workflow, adaptive audit controller, model shadow audit, GNN localization (see `docs/HISTORY_AND_RESEARCH_NOTES.md`). Nothing here should be read as evidence for those.
- The deployment files (`render.yaml`, Dockerfile healthcheck) have not been exercised on a real host.


## Final build, 2026-10-26

- Worker isolation is process/environment isolation for a fixed allowlisted validator, **not** an operating-system sandbox. It does not execute generated code or contact a provider. Installed package paths are explicitly inherited so user-site installs work with isolated Python.
- SQLite persists the single workspace; it does not add tenants, authorization, encrypted storage, a queue or distributed execution. Audit rows are durable but not tamper-proof. No SSO, production alerts, or Postgres adapter is claimed.
- The default local launcher binds to loopback. Hosted demos still need an access gateway; deployment files have not been executed on a public host here.
- The savings calculator uses user-entered assumptions, including overhead. There is no paired real-agent baseline, measured customer ROI, or pilot evidence.
- Recording imports validate the invoice workflow only and never contact the source provider. Contract-only passes without an independent expected result are explicitly labelled. Captured data is handled locally; do not package customer recordings with a public submission.
- Range thresholds are unchanged. Unused invoice metadata such as issued_at is no longer included in mined key contracts. Known large-invoice and correlated-drift failures remain visible.
- The sandbox retains immediate repair endpoints for deterministic/model experiments; the main Propose action and Incidents screen use explicit review. Approvals govern synthetic postings only.
- Runtime state keeps at most 200 run records. Audit events persist separately until the data directory is removed. Reset clears the active session but preserves audit history and prior manifest files.

## AAIR redesign — supersedes validation-only execution claims above

Strict AAIR now uses a separate **simulated** billing/settlement authority to gate invoice/payment unit assumptions.
With that evidence available, correlated numeric shifts are blocked, and independently confirmed large invoices can resolve
magnitude-only warnings. Missing, same-source, malformed or stale evidence blocks posting as UNKNOWN.
The old 97/2282 correlated misses and 347/2131 large-invoice blocks remain results of the legacy validation-only method;
they are not advertised as the strict AAIR performance. The UI keeps a clearly labelled legacy comparison.

This improves the demonstrated mechanism by adding a trusted evidence boundary. It does not prove that a real independent
source exists for every customer. Authority and oracle share fixture truth in this prototype; independent real-world evidence,
source independence validation, adapter authentication and a field drift corpus remain necessary.

The ordinary data-dependency replay ablation can yield the same slice as AAIR for this eight-step workflow. An improvement
over full regeneration does not establish superiority over all existing incremental runtimes, nor research novelty.
Real repeated Nemotron reasoning and paired provider billing have not been executed without user credentials. The matched
offline baseline explicitly assumes a correct agent and modelled token/cost rates.

Date-filter inclusivity, timestamp meaning/order and arbitrary enum-remapping verification are not implemented by this invoice
operation set. A required unsupported assumption remains UNKNOWN; the prototype does not silently certify those cases.
Checkpoint reuse is supported only with an adapter-provided immutable snapshot. An ordinary recent timestamp is insufficient.
The escalation controller is a conservative eligible-tier policy, not a learned/calibrated expected-cost optimizer.

## Enterprise pilot profile

Named roles, separate review, persistent attempted-call budgets and backup/restore are implemented. These controls do not
establish enterprise certification, tenant isolation, SSO/MFA, encrypted data at rest, high availability or a service SLA.
Basic authentication requires HTTPS outside loopback. Identity/backup files and customer recordings require OS access controls.
The security hash chain requires an externally retained head to strengthen detection; it is not independently tamper-proof.
Inference caps count attempts in one data directory, not dollars or account-wide credit balances. Restoring older data can
restore older counters. Request replay protection applies to POST execution, not every mutation or an external ledger.
The validator subprocess is still not a general OS security sandbox. Do not import or execute untrusted code.

## Agent Studio

The builder configures a fixed USD invoice template with bounded parameters; it is not arbitrary graph or trace synthesis.
Its task filter is conservative English keyword routing. Its 28 validation cases share authorship with the implementation.
Counterfactual impact uses at most twenty captured synthetic cases and fixture truth, not a complete or independent blast-radius
bound. Its offline output-impact replay is not an acceptance authority. Fresh strict checks still rely on a trustworthy configured
authority. Evidence passports record a policy decision; they do not certify factual correctness. Cost curves use assumptions;
no measured always-LLM baseline, net customer savings or routing advantage is bundled. Draft/version/receipt persistence does
not add SSO/MFA, tenant isolation, encrypted storage or HA. Read PLAN_REVIEW.md before reusing the expanded plan's marketing claims.
