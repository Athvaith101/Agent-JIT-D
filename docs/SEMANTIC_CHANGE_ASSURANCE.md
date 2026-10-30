# Semantic Change Assurance — 2.2

In Studio → Runs, select a saved run, enter a verification budget, declare an
optional changed evidence source, then click **Plan revalidation**. The read-only
report displays recorded obligations, affected consumers, selected checks and
uncovered obligations. An empty impact highlight never removes mandatory checks.

The new planner runs in shadow mode. Existing strict execution still obtains fresh
mandatory evidence before acceptance. Recorded VALID states are never reused by
this report: they do not establish present validity. A complete plan identifies
checks to perform; it does not establish that they passed. Human review and a
larger budget cannot override missing or invalid required evidence.

## Algorithm and boundaries

The required universe consists of individual obligations, not decisions. A check
may cover several obligations. For at most 16 registered self-contained check
actions, exact subset enumeration chooses the cheapest complete cover within
budget, when available. Otherwise it maximizes covered obligation count, then
minimizes cost. Every action's prerequisites must be included in its cost. Dependent
action scheduling is unsupported. Complexity is exponential, capped at 65,536
subsets. This is not a general optimal workflow scheduler.

The invoice adapter assigns one planning unit per mandatory check. Units are not
measured tokens, latency or money. The planner dispatches no tools or model calls.
Existing recovery independently retains its snapshot, policy and content checks.
GET /api/studio/runs/{run_id}/assurance?budget=4&changed_source=provider uses the
same authenticated read access as other Studio inspection. Reports refer to
recorded runs and cannot certify current external state. No continuous watcher,
formal proof checker or new signed authority integration is included.

## Experiment and defensible claims

Run `python -m jitd.assurance_bench` for a reproducible synthetic check-selection
experiment. It measures planning coverage under nine budgets, not end-to-end
inference savings. The shared-check example demonstrates why obligation coverage
can matter; the present invoice adapter has individual checks only.

Tighter budgets increase incomplete coverage and blocking requirements. Never
intentionally introduce silent errors on the live path. Runtime benefit must be
evaluated against full revalidation, current JIT-D and dependency replay with the
same acceptance gates. Include completion rate, false blocks, silent errors per
attempt and per accepted output, overhead, and uncertainty. Preserve negative
findings, including dependency replay matching semantic recovery.

Use "verification obligations" rather than formal proofs. This release integrates
known techniques into bounded agent workflows; it does not claim to invent them.
Prior art includes Doyle, Truth Maintenance Systems for Problem Solving (IJCAI
1977); Acar et al., self-adjusting computation; and STALE/CUPMem (Chao et al.,
arXiv:2605.06527, 2026).

## Final submission boundary

Shipped: invoice builder, hash-bound testing/publication, separate review, guarded
execution and repair, passports, human-inclusive cost projections, shadow planning.
Proposed: live selective verification skipping, continuous monitoring, multiple
independent domains, arbitrary task synthesis and automatic canary promotion.
Real Nemotron-on-Nebius results, measured inference savings, Windows validation,
public repository/demo access and a current demonstration recording require
operator execution. No paid call was made while creating this release.
