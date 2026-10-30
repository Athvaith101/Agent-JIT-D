# Hybrid assurance controller — release 2.4

The visual workspace now has **Hybrid assurance**. Both Canvas executions and
invoice Studio executions automatically record monitoring observations. Invoice
Runs also exposes **Inspect hybrid controller**. No model is used to monitor
ordinary runs. Every existing strict check remains mandatory.

## What executes

1. The deterministic workflow runs its current contracts and evidence gates.
2. A persistent controller records per-step latency (invoice Studio), payment
   record counts and raw-payment/invoice ratios where observed. Canvas currently
   records total runtime only; its domain gates are still distinct per template.
3. Each signal uses a clean reference of eight qualifying predicate-pass runs by
   default. After warmup the reference freezes; invalid/unknown cases never train
   it. The robust score is (x − median)/(max(1.4826 MAD, 5% |median|, .01)), clipped
   to ±20. The explicit floor and clipping are engineering stabilizers.
4. CUSUM updates g=max(0,g+|z|−k), with defaults k=1.5, h=8; alarm when g>h.
   These defaults are evaluated in the bundled authored simulation. They do not
   imply false-alarm control on customer traffic. Baselines are per approved
   runtime content, not pooled across different versions. A policy save resets
   state into a new regime while retaining old observation records.
5. Beta(1,1) updates from verified predicate violations/passes only. UNKNOWN
   observations do not update counts. Per-step counts are recorded when observed
   step predicates support a label. A passing schema or authority predicate is
   not evidence of general real-world correctness. Model advice never updates
   counts. Run IDs deduplicate updates transactionally across restarts.
6. Graph ranking prioritizes failed checks whose direct dependencies have no
   observed failing checks, then manifest order. These are heuristic rankings,
   not a calibrated Bayesian posterior. Existing invoice hypothesis diagnosis
   retains its unit/pagination signatures and supporting features.
7. An expected-risk recommendation chooses a supported next action. Configured
   model assistance is eligible only for ambiguous failures, with qualifying
   evidence availability, enough verified labels and remaining attempt budget.
   A known local unit/pagination repair is preferred without a model; the invoice
   Studio still validates, reviews and replays any actual repair.

Monitoring happens **after strict execution**, before recording its monitoring
receipt. An operational alarm cannot retroactively revoke a previously qualified
local output. It recommends review. This is not a pre-action probabilistic safety
shield. Missing required evidence continues to block at the strict executor.

## Risk rule and assumptions

p_proxy = alpha/(alpha+beta)
R_unchecked_accept_proxy = p_proxy × configured_loss
R_model_assumption = configured_model_and_validation_cost
                     + configured_residual_probability × configured_loss

For an ambiguous blocked run, model assistance is eligible when the first quantity
exceeds the second and the second is below configured human-review cost. Model
and human action costs are assumptions, not learned quality estimates. Include
latency, validation and follow-up effort in those estimates. Human review is
modeled with zero residual risk for routing purposes; that is an explicit
simplification. No unchecked acceptance action becomes eligible for blocked runs.

The Beta mean measures historical predicate violations. It is **not calibrated
P(output wrong | current evidence)**; stationarity, IID and representative audits
are not established. The cost comparison is an experimental proxy, not a proved
optimal policy or a certified silent-error bound. No 3/n claim is made. Unknowns,
self-reported model confidence and reviewer notes cannot override mandatory gates.
BOCPD and conformal/WATCH monitoring are research directions, not implemented
features. No online fine-tuning occurs.

## Enable intentionally

1. Launch normally. Open /builder → Hybrid assurance, inspect observations.
2. Model assistance is disabled by default. Configure an admin-only model
   connection in Models & keys. For hackathon evidence use Nemotron via Nebius.
3. Review your credits/billing. Stop the server, set JITD_MAX_MODEL_CALLS to a small
   absolute ceiling in the terminal, restart, and paste the memory-only key again.
4. Save a controller policy with assistance enabled and justified cost assumptions.
   Minimum verified labels defaults to eight. Saving begins a fresh regime.
5. Run clean examples to populate baselines. Inject an ambiguous fault.
6. Either select **Run policy-gated diagnosis**, or check **Enable policy-gated
   model diagnosis for this run** before a Canvas execution. Studio API also
   accepts auto_assist:true on execution. The normal Studio Run button stays
   deterministic; inspection/assistance is available from the visual workspace.
7. Stable verified runs, known local repair signatures and missing evidence do
   not dispatch a model. Neither do disabled policy, insufficient labels, missing
   connection, exhausted budget, or unfavorable cost assumptions.
8. Model responses must have an allowlisted suspect_step and short explanation.
   They are advice only, never executable patches or verified labels. A model
   can be wrong even if its response satisfies this schema.
9. A persistent claim allows at most one diagnosis attempt per run. Interrupted
   or failed attempts are not automatically retried. Re-run with fresh evidence
   for another attempt. Policy/source/runtime changes invalidate stale assistance.
   Successful replies and unknown usage are retained in Cost evidence receipts.

A model never repairs missing authority. Existing invoice repairs still require
strict fresh-evidence validation, captured-case replay and separate approval in
enterprise mode. Canvas families do not gain automatic domain repair adapters.
The model call cap is not a currency cap. This build made no paid API calls.

## Reproduce and inspect

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_hybrid.py -q
.\.venv\Scripts\python.exe -m jitd.hybrid_bench --output benchmark/hybrid/local.json
```

The bundled experiment freezes development seeds 11/29 and reports new seeds
101/207/809 at default thresholds separately. It measures clean operational alarm
rates, detection delay, policy-request counts and blocked-policy invariants. It
uses authored synthetic signal/label streams, not actual agents or model results.
The always-reason comparator is a request-count counterfactual. No measured cost,
repair-token savings, model quality advantage, production guarantee or formal
false-alarm bound follows from it. Existing matched workflow and authority studies
remain included with their negative findings.

SQLite hybrid.sqlite3 stores policy, regimes, state, immutable-by-API observations,
labels and dispatch claims. Offline backups include it. The invoice passport binds
the original monitoring report hash. Canvas execution records retain the report.
Disk-controlling administrators can rewrite local storage; external anchoring is
not implemented. Inspection lists the latest 100 observations.

## Research grounding

- Dekoninck, Baader, Vechev (ICML 2025), *A Unified Approach to Routing and Cascading
  for LLMs*: https://proceedings.mlr.press/v267/dekoninck25a.html — motivates explicit
  cost/quality routing; its optimality guarantees are not inherited by this proxy.
- Prinster et al. (ICML 2025), *WATCH*: https://proceedings.mlr.press/v267/prinster25a.html
  — relevant advanced sequential monitoring; not implemented here.
- Gibbs and Candès (JMLR 2024), *Conformal Inference for Online Prediction with
  Arbitrary Distribution Shifts*: https://jmlr.org/beta/papers/v25/22-1218.html —
  adaptive prediction-set methodology, not automatic workflow fault localization.

This implementation integrates standard contracts, robust statistics and Bayesian
counting. It does not claim these components or their general combination are new.

The concurrent Nebius setup guide and bounded nebius_smoke helper are preserved. Its attempts now use the durable workspace ledger as well, and the helper rejects destinations outside the approved Nebius HTTPS endpoints. No live smoke call was made for this release.
