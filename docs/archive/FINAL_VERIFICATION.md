> Historical AAIR release notes. For the integrated release see P0_P2_VERIFICATION.md and RELEASE_P0_P2.md.

# AAIR final release verification — 26 October 2026

## Tests and execution

- Runtime: Python 3.12.14, Linux.
- Final full suite: **123 passed in 32.30 seconds**.
- Original five reported repair/API failures remain passing.
- New coverage includes explicit registry/dependency links, unsupported/missing/same-source/stale evidence, correlated numeric shifts,
  wrong currency despite matching numeric values, snapshot changes and executor-entry race, corrupt checkpoint rejection,
  changed verification policy, selective replay/full-rerun equivalence, restart persistence, pricing absence/zero denominator,
  correctly resolving magnitude alerts without overriding business failures, and meaningful short benchmark drift exposure.
- `python scripts/run_aair_demo.py` passes the complete story: VALID clean run; unit drift block; wrong repair rejected;
  proposal/approval; 4 reused + 4 re-executed nodes; correct output independently re-verified; missing evidence safely halted.
- `python scripts/secret_scan.py`: clean.
- JavaScript syntax checks passed for app.js, operations.js and aair.js.

## Browser and visual QA

Headless Chromium at 1440×1000 completed Home → architecture → Execution → clean run → cents drift → diagnosis →
proposal → approval → selective retry → re-verified output → missing-evidence safe halt → Performance → Home.
No JavaScript page/console errors. The graph and evidence records are actual backend data.
The Obsidian/NVIDIA Green home and recovered execution screens were visually inspected.
Mobile Home at 390×844 was inspected with no page-wide horizontal overflow. Tables scroll inside their containers.
Screenshots are internal QA only and are not bundled as deliverables.

## AAIR matched comparison

- Source fingerprint: `281d8f156497a2e8`.
- Result: `benchmark/aair/aair_20261026T163152Z.json`.
- 3 seeds × 60 runs × 12 scenarios × 7 methods = **15,120 recorded trials**.
- The 12 scenarios include stable/cosmetic data, large valid invoices, malformed responses, cents/mills, pagination,
  compound faults, underpayment, correlated numeric drift, unavailable evidence and same-source evidence.
- Each 60-run stream deliberately includes 15 warmup and 45 post-onset inputs. Methods share the same workload.
- Initial planning/compilation, execution, verification and recovery are charged. Provider calls/tokens are zero in this offline study.
  Repeated reasoning/discovery tokens and USD rates are modelled; runtime and outcomes are measured.

| AAIR scenario | Correct completed outputs | Silent errors | Safe halts | Reused nodes across streams |
|---|---:|---:|---:|---:|
| unit_cents | 180/180 | 0 | 0 | 12 |
| unit_mills | 180/180 | 0 | 0 | 12 |
| truncation | 180/180 | 0 | 0 | 3 |
| consistent_scale | 45/180 | 0 | 135 | 0 |
| missing_evidence | 45/180 | 0 | 135 | 0 |
| correlated_evidence | 45/180 | 0 | 135 | 0 |
| big_invoice | 180/180 | 0 | 0 | 0 |

The ordinary data-dependency replay ablation also reuses 4 nodes per successful unit recovery in this graph, matching AAIR.
Therefore these experiments do **not** establish an advantage for semantic slicing over ordinary incremental replay.
They demonstrate bounded repair, safe checkpoint reuse and independently gated results. Missing evidence deliberately loses
completion/availability relative to unverified cached execution. Small-workflow bookkeeping can cost more than recomputation.
Use the saved per-cell metrics, including losses, rather than claiming a universal speed or cost improvement.

## Legacy validation-only comparison

- Result: `benchmark/results/runs/bench_20261026T163230Z_6d1e81b3.json`; same final code fingerprint.
- 30 seeds × 120 runs × 12 scenarios × 6 methods = **259,200 trials**.
- Compressed raw records for guarded legacy and naive replay: **86,400**.
- The legacy correlated-drift misses and large-invoice false blocks remain visible as the baseline.
  Strict AAIR adds a simulated independent authority, so improvements cannot be attributed solely to slicing.

## External evidence still needed

No live Nebius/Nemotron call, paired real-agent billing comparison, independent field corpus, customer pilot,
Windows runtime, Docker build, remote CI or public cloud deployment was executed here.
Provider keys were not supplied. The live harness records real usage and recovery traces when configured;
it does not fabricate a successful model proposal or price. The authority and evaluation oracle share synthetic fixture truth.
Prior-art review and broader experiments are required before a research novelty claim.
