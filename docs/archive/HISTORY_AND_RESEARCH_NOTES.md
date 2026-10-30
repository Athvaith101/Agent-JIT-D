# History and research notes

An earlier line of this project (`Agent_JIT_D_v3_checkpoint_N`, 20 Oct 2026; overview kept at `docs/history/CHECKPOINT_N_overview.docx`) had a wider scope. This repository is the narrower, more heavily evaluated successor. The items below were **not carried into this repository**; they are recorded here so the findings are not lost.

| Checkpoint N feature | Status here |
|---|---|
| Finance and inventory-fulfilment workflows | Only invoice reconciliation is implemented |
| React + Vite dashboard (React Flow DAG) | Replaced by the static console in `web/` |
| Budget-aware / adaptive audit controller | Not included |
| Shadow audit with the model | Not included (fixed-interval agent audits are only a modelled baseline) |
| Graph neural network for fault localization / audit priority | Not included; see results below |
| Opt-in live smoke test with provider token counts | Replaced by `python -m jitd.live` |

## Findings worth keeping

**GNN fault localization (checkpoint N, offline mock services).**

| Experiment | GNN top-1 | Heuristic top-1 | Reading |
|---|---|---|---|
| Section J, runtime evaluation | 0% | 77.8% | Training on synthetic features did not transfer to real executions |
| Section L, held-out drift | 66.7% | 100% | Better with runtime telemetry, still behind the heuristic |
| Section M, grouped held-out | 100% | 100% | Benchmark saturated (36 correlated executions); no advantage shown |

Conclusion carried forward: localization here stays a transparent, hand-built hypothesis scorer. A learned model should only be promoted if it beats the heuristic on held-out drift.

**Adaptive auditing was never shown to beat fixed auditing.** In checkpoint N's inventory benchmark a nominal-40% fixed audit averaged 2.8 silent errors per seed against 5.2 for the adaptive policy, and the nominal percentages did not produce matched audit spending, so no superiority claim was supportable. The open question is a paired comparison at matched *observed* audit cost.

**Evaluation lessons applied here.** Scenarios are tagged dev or heldout; counts are reported as k/n with Wilson intervals; weak spots are listed before strengths; baselines and prices are labelled as modelled; the oracle is kept independent of the code under test.
