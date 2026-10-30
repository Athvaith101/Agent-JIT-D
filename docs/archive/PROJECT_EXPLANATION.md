> **AAIR release note:** This document preserves the earlier validation-only prototype explanation. The current strict assumption registry, snapshot-safe incremental replay, evidence gate and cost comparison are documented in [AAIR_IMPLEMENTATION.md](AAIR_IMPLEMENTATION.md) and [ARCHITECTURE.md](ARCHITECTURE.md). Claims about correlated misses below refer to the explicitly retained legacy baseline.

# JIT-D: project explanation

*Compile a successful AI workflow once. Replay it with no model calls. When the world silently changes meaning, stop before a wrong result propagates, find the assumption that broke, repair it within bounds, and prove the repair, or stay halted.*

## 1. The problem

Replaying a workflow a model once got right is cheap. But a provider can change what a field *means* without changing its schema: dollars become cents, a list becomes paginated, a unit shifts. Schema validation still passes and the business result is wrong (a **silent error**). Rebuilding the whole workflow after every anomaly wastes the savings that replay was meant to give.

JIT-D targets that trade-off for one concrete workflow (invoice reconciliation): avoid repeated reasoning without treating a cached plan as permanently correct.

## 2. How it works

| Stage | What happens | Where |
|---|---|---|
| Compile | A plan (from Nemotron via Nebius when configured, otherwise a labelled deterministic plan) is parsed into a typed manifest, restricted to allowlisted operations, checked against boundary schemas, and must reproduce an independent oracle on 400 golden invoices. Contracts are declared (invoice arithmetic, payment == invoice when paid) and mined from golden runs (ranges, completeness, enums, key sets). | `compiler.py`, `contracts.py`, `llm.py` |
| Replay | Deterministic executor with no model handle (tested); the meter reports `replay_model_calls: 0`. Contracts run on every replay. | `executor.py` |
| Detect | A critical contract failure halts before the ledger step; a warning holds the entry for review. | `executor.py`, `contracts.py` |
| Localize | Each step has a named drift hypothesis scored by fixed-weight evidence. The check that fired is often not the step whose assumption broke. Outcomes include *ambiguous*, *unexplained* and *business exception*. Scores are heuristic, not probabilities. | `diagnosis.py` |
| Repair | A typed, allowlisted parameter change (unit divisor from a cutover time, or a page limit), proposed deterministically or by Nemotron, validated in a separate process with a scrubbed environment against recorded drift cases, the regression suite and the oracle. Wrong repairs are rejected; unrepairable cases stay halted. | `repair.py`, `validation.py`, `validate_worker.py` |
| Remember | An accepted repair persists a regression guard and adds the confirmed cases to the regression suite. | `lab.py` |

**Trust boundary.** The model proposes; it is never the authority for correctness, contract outcomes, patch safety or benchmark success. Repairs are data parameters, never generated code. A process-wide cap (`JITD_MAX_MODEL_CALLS`) bounds paid model calls.

## 3. What the evidence shows (mock provider only)

30 seeded streams × 120 runs per cell. Full table, intervals and caveats: README, `docs/BENCHMARK_METHODOLOGY.md`, `LIMITATIONS.md`.

- Dollars→cents: 0/2257 silent errors for JIT-D vs 2257/2257 for naive and schema-only replay; unseen dollars→mills variant 0/2319.
- A genuine under-payment is diagnosed as a business exception and correctly *not* repaired; compound faults stay halted.
- **Where it fails:** both services scaling together gives 97/2282 silent errors (4.3%); legitimately huge invoices are held in 347/2131 runs (16.3%); a mined contract on an unused field blocks 74.6% of runs in the external `tax_in_cents` scenario.
- Agent baselines are modelled (assumed correct, assumed tokens and prices), not run. **No real Nemotron result exists yet.**

## 4. Role of NVIDIA Nemotron and Nebius

Nemotron, served by Nebius Token Factory through an OpenAI-compatible client, can propose the compiled plan and repairs. Both go through the same independent validators as the deterministic path, and the plan or proposal source is labelled in the console and the evidence files. `python -m jitd.live` exercises the real path and records everything, failures included.

## 5. One-minute explanation

"Workflows get replayed to save cost, but a provider can change what a field means without changing its schema, and then the replay is quietly wrong. JIT-D compiles a workflow once, replays it with no model calls, and checks contracts on every run. When something breaks it halts before the ledger, names the assumption that broke, proposes a bounded repair, and accepts it only after an isolated validation against recorded drift cases and regression tests, otherwise it stays halted. We measured it on a simulated provider, report where it fails, and have not claimed any real-model result yet."

## 6. Remaining work

Record real Nemotron compile and repair evidence; deploy a public demo with `JITD_MAX_MODEL_CALLS` set low; record the demo video; check the official rules and submit before the deadline.
