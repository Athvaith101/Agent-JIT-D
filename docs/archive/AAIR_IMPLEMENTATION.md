# AAIR implementation and acceptance status

The project preserves the existing FastAPI backend and functional vanilla JavaScript frontend. The brief referred to React,
but the supplied working code is not React; replacing it solely to match that description would add no core value.

## Assumption dependency graph

`Manifest.assumptions` stores IDs, semantic contracts, producer nodes, affected consumer closures, evidence sources and UNKNOWN initial state.
`assumptions.verify` evaluates each against the observed step outputs and adapter-supplied evidence. Each observation records status,
reason, source, expected/observed values and a verification timestamp.
The current registry covers invoice units, normalized payment units, declared pagination completeness and business reconciliation.
A new required assumption without an implemented verifier remains UNKNOWN, rather than disappearing from the gate.

Schemas and same-source arithmetic establish structure/consistency, not independent units.
The demo exposes separate simulated billing and settlement authorities. Each supplies an explicit provenance claim,
USD reference amount, timezone-aware observation time and snapshot binding. Missing, malformed, stale (over 5 minutes),
future-dated (over 5 seconds) or same-provider evidence cannot establish VALID. This is a trusted adapter interface,
not a cryptographic proof of independence; a real adapter and independent field evaluation are still needed.

The strict executor blocks the sink unless every required assumption is VALID. A distribution-range warning can be
resolved for the current monetary output only when independent authority and all business checks agree. The warning
and resolution remain in the trace. Other business/schema/enum failures are not suppressed.

## Invalidation and incremental execution

1. Compare old and candidate steps to find changed operations/parameters.
2. Collect INVALID/UNKNOWN required assumptions and trace their consumer dependencies.
3. Invalidate the transitive downstream closure. Raw payment acquisition can remain an immutable observation when only its conversion rule changes.
4. Reuse only completed, unchanged nodes whose content hash matches, whose dependencies are reusable, and whose source snapshot still matches.
5. If contracts/assumption policy changed, discard every checkpoint. If the source cannot guarantee an immutable snapshot, perform a full reread.
6. Check the snapshot again on entry to the executor to close the planning/entry race.
7. Re-execute the affected region. Never reuse the sink, even when it is idempotent.
8. Independently verify the new result before posting.

The immutable-snapshot implementation is currently provided by the synthetic adapter. Arbitrary real API responses do not qualify merely because
a local timestamp is recent. Checkpoint reuse uses the original invoice ID and as-of inputs; it does not silently substitute a new request.

Typical unit change: reuse fetch_invoice, fetch_payments, expected_total and classify_status. Execute normalize_amount,
sum_payments, reconcile and post_ledger. Snapshot changes, corrupt checkpoint values or changed verification policies safely expand replay.
`RunResult.recovery` persists the actual changed/invalidated/reused/executed nodes, fallback reasons and final verification outcome.

## Repair and escalation

Repairs remain data-only parameters: append one effective unit-divisor rule or change a bounded page limit. Isolated validation
checks recorded drift inputs plus regression cases against fixture expectations. Main UI actions use propose/review/approve,
and approval validates again. The same old run must still match the current version and provider scenario.

The escalation controller recommends eligible low-call-cost bounded recovery or safe halt. A reproducible semantic contradiction is
not treated as a transient retry. Missing independent evidence cannot be repaired by model reasoning. Full regeneration is implemented
in the benchmark as full deterministic plan/contract reconstruction plus the same validated patch, and is labelled accordingly;
there is no automatic unconstrained model rewrite on the critical path. This is a conservative supported-tier policy, not a calibrated optimal-cost controller.

## Cost and comparison

The primary denominator is **oracle-correct posted outputs**, not total attempts, safe halts or model-call reduction.
Compilation, execution, verification and recovery runtime are recorded. Real provider input/output tokens and latency are captured when supplied.
Workspace USD remains unpriced until all applicable rates are configured. Zero correct outputs gives undefined cost, not a zero-cost victory.
The retained-run denominator is limited to the latest 200 runs while session costs are cumulative: the workspace estimate is conservative
once old outputs age out; use full benchmark/audit accounting for study claims.

The matched synthetic benchmark includes seven methods:

- Repeated reasoning, explicitly modelled as oracle-correct with assumed tokens/prices.
- Cached execution without semantic guards.
- Ordinary schema/contract validation without recovery.
- Full deterministic regeneration plus full rerun, with model discovery cost assumed.
- Ordinary data-dependency incremental replay, sharing the same independent proof gate and patch mechanism.
- Fixed-rate audit every 10 runs.
- AAIR.

Short workloads deliberately include both pre-drift warmup and post-drift inputs; a no-drift prefix cannot masquerade as successful recovery.
All methods receive the same stream and ground truth. Raw trial records, costs, silent errors, safe halts, false blocks, detection delay,
recovery wall time and checkpoint counts are saved. CPU/token rates are assumptions; runtime is measured. There is no provider-billing claim.
The ordinary incremental ablation can match AAIR on the current graph. Small workflows can make verification and checkpoint bookkeeping costlier than recomputing.

## Acceptance checklist

| Brief item | Status |
|---|---|
| Audit working ZIP and preserve regression coverage | Implemented; see FINAL_VERIFICATION.md |
| Explicit assumption/consumer links | Implemented |
| Required UNKNOWN cannot pass | Implemented and tested |
| Correlated / missing / stale evidence checks | Implemented against simulated independent authority |
| Snapshot-safe selective repair/replay | Implemented and tested |
| Independent output re-verification | Implemented with explicit synthetic authority boundary |
| Usage and primary cost metric | Implemented; USD needs configured estimates |
| Strong matched baselines | Implemented offline; real-model comparison not yet executed |
| Complete Obsidian/NVIDIA Green design tokens | Implemented, responsive, reduced-motion and focus styles |
| Graph/console/metrics from backend events | Implemented |
| Reproducible demo and deployment commands | Included |
| Real Nemotron run and field evidence | Requires user credentials and real integration; not fabricated |
| Date inclusivity, timestamp-order and arbitrary enum semantics | Outside the invoice operation set; unsupported required contracts remain UNKNOWN |
| Proven research novelty | Not claimed; close prior-art review and broader independent experiments still required |
