# AAIR matched study and legacy benchmark

The current matched AAIR study is implemented in `jitd/aair_bench.py`, with results in `benchmark/aair/`.
See AAIR_IMPLEMENTATION.md for its seven methods, attributed cost accounting and synthetic evidence boundary.
Ordinary data-dependency replay uses the same independent gate and patch to avoid attributing evidence differences to semantic slicing.
Short streams include an explicit pre/post drift split. Actual timings and counts are measured; agent reasoning and prices are modelled.

The older study below is a **validation-only legacy baseline**, still reproduced and displayed separately. Its missed correlated drifts
must not be quoted as strict AAIR results, nor used to claim improvement without disclosing the added independent evidence.

# Benchmark methodology

`python -m jitd.bench [--seeds 30] [--runs 120]` → `benchmark/results/runs/bench_<stamp>_<id>.json` (+ CSV). Fixed seeds; identical streams for every strategy.

**Stream.** Per scenario and seed: 120 invoices; the provider behaviour switches at a seeded onset in [30, 60]. Truth (line items, payments) comes from `fixtures.py`; the oracle derives the correct ledger entry from truth only.

**Strategies.** `agent_every_run` (modelled: assumed correct, 1 model call/run), `naive_replay` (no checks), `schema_only` (boundary schemas, no contracts), `fixed_audit_10/25` (naive replay plus a modelled agent audit every N runs; on mismatch halt and fall back to the agent), `jitd_guarded` (real executor, real contracts, diagnosis, repair).

**Metrics** (definitions are also stored in the result file):
- *silent error*: a wrong ledger entry was **posted** (or one posted that should need a human). Halted, held and crashed runs are not silent.
- *needs protection*: naive replay did not produce the oracle-correct posted entry. *Detection*: of those, the share that were recovered (correct entry posted) or blocked.
- *false block*: naive replay was correct, but the strategy halted or held the run (held-for-review counts).
- *localization*: on the first halted/flagged run, the top hypothesis names the true fault location (or correctly "business exception"). Episodes on benign scenarios count against it.
- Rates are reported as k/n with 95% Wilson intervals. Latency is measured wall time of the deterministic path only; agent latency is modelled.

**Assumptions (editable in `jitd/bench.py`):** 4000 input + 600 output tokens per agent call, $0.20/$0.60 per million tokens, 3 s per call. Not Nebius pricing.

**Dev vs heldout.** `clean, cosmetic, unit_cents, truncation` were used while developing contracts and hypotheses. `big_invoice, unit_mills, malformed, underpayment, compound, consistent_scale` were run afterwards. See LIMITATIONS.md for the one process caveat (golden corpus size).

**What this does not show.** Real-provider behaviour, real-model plan/repair quality, production reliability, or performance on workflows other than this one.

## Evaluation run 2 (2026-10-22): additions

Run 1 (`bench_20261021T183627Z_c1c735b1.*`) is preserved unchanged. Run 2 (`bench_20261022T010900Z_17ec0ad2.*`) uses the same
code and scenarios, plus two **external-format** scenarios, and saves raw per-trial output.

- **Splits.** dev: clean, cosmetic, unit_cents, truncation. heldout: big_invoice, unit_mills, malformed, underpayment, compound,
  consistent_scale. external: tax_in_cents, three_per_page (`benchmark/external/*.json`).
- **External scenarios are NOT independent.** Their author is the JIT-D team (the file says so, the UI shows "NOT independent").
  They only prove that scenarios can be defined declaratively without touching the code. To get an independent set, someone else must
  write JSON files in `benchmark/external/` without reading `contracts.py` or `diagnosis.py`, set `"independent": true`, and rerun
  `python -m jitd.bench --external benchmark/external`. Scenarios must not be tuned after seeing results.
- **Raw per-trial output.** `*.trials.jsonl.gz`: one row per run for jitd_guarded and naive_replay (scenario, strategy, seed, idx, post,
  behavior, outcome glyph, oracle-expected ledger). 86,400 rows. Glyphs: C correct post, S silent error, F false block, B blocked drift,
  K correct block, R recovered.
- **Findings reported prominently (also in the UI, before the chart):**
  - big_invoice: 347/2131 false blocks (16.3%). A legitimately huge invoice is indistinguishable from a unit shift on one run.
  - consistent_scale: 97/2282 silent errors (4.3%, CI 3.5-5.2%). Reconciliation cannot see it; the magnitude range only warns, and
    small invoices stay inside it.
  - tax_in_cents (external, new): 1672/2241 false blocks (74.6%). The workflow never uses `tax`, so naive replay is *correct* here, yet JIT-D
    halts on the mined key/range contracts. A mined contract on an unused field is a cost, not a protection.
  - compound: 0/60 repairs accepted (by design: two faults, one bounded repair).
  - Localization on big_invoice is wrong in 60/60 episodes (misdiagnosed as provider_wide).
- Agent baselines are still modelled, not run. Nothing here measures Nemotron.
