# Evaluation: observations, uncertainty and limits

## Protocol and units

After installing requirements-research.lock, the active reproduction command is `python scripts/reproduce.py`. It runs 30 seed streams per cell, each containing 12
inputs including warmup and post-onset inputs, on twelve synthetic scenarios and seven methods. Shortening each stream
does not create more independent fault classes. Seeds vary generated data; scenario authorship remains shared.
The paired recovery study and authority sensitivity sweep are saved separately in benchmark/final/.

Rates are calculated per seed stream. Cluster bootstrap resamples entire streams, not individual runs. We retain per-stream
rates, min/max, the bootstrap interval and a Wilson interval on the proportion of streams exhibiting an error. An all-zero
bootstrap interval is degenerate and cannot establish zero population risk. Run-level counts are descriptive only. Legacy
saved pooled intervals remain historical artifacts and are not displayed as inferential claims in the UI.

## Mechanism expectations, not preregistered research hypotheses

These expectations derive from known implementation and prior experiments; do not describe them as independent preregistration.

- Required unavailable/stale proof must prevent posting. Generated safety tests exercise fifty randomized invalid-evidence cases.
- Correlated wrong authority can certify a correlated wrong provider. Authority reliability is a necessary external condition;
  more model reasoning or internal arithmetic cannot prove independence.
- Ordinary dependency replay can match or outperform semantic invalidation in this graph. Keep the negative result.

## Authority reliability experiment

`python -m jitd.authority_study` runs thirty streams of ten invoices for each combination of four fault modes and seven
injection probabilities: 8,400 recorded trials. Faults are wrong references, stale observations, missing evidence and
provider/authority drifting together. The latter deliberately invalidates the trusted-authority premise. The simulated
probabilities are experimental settings, not measured reliability of any real authority.

See figures/authority-sensitivity.svg and benchmark/final/authority.json. Silent error and false-block rates are reported
separately. In stale/missing cases, UNKNOWN prevents acceptance. A corrupted authority with clean provider data primarily
costs availability. When provider and authority share the same scale error, accepted outputs can be wrong. No universal
"safe above reliability X" threshold follows without measuring dependence and the deployment's loss model.

## Baselines and ablations

The full matched comparison includes modelled repeated reasoning (correctness assumed), naive cached execution,
ordinary contract validation, full deterministic reconstruction/rerun, dependency replay, fixed audit and strict AAIR.
The paired study shares evidence, candidate patches and checkpoint integrity checks across methods. These are mechanism
comparisons, not measurements against Stagehand or Skyvern. Calling a synthetic baseline one of those products would be
misleading. Model-as-judge, a genuinely iterative real-agent baseline and a full factorial ablation matrix remain open.

The optional model_baseline CLI makes real single-call full-input proposals when credentials are supplied. It is not an
iterative tool-using agent. No actual model result is bundled. Its final monetary gate is shared, while compiled execution
also retains mined contracts. Missing provider usage is not zero billing.

## Economics including human work

Illustrative break-even per run: replay/verification cost + hold rate × review minutes × hourly review cost / 60.
This compares costs only when output correctness and all other operational burdens are comparable. At assumed $30/hour,
five review minutes and a 1% hold rate, review alone costs $0.025/run; with assumed $0.0001 replay cost, break-even is
$0.0251/agent run. This can exceed the model-call saving. See benchmark/final/break_even_assumptions.json. These are
assumptions, not provider prices, measured ROI or customer savings. Real-agent cost and adjudicated correctness remain needed.

## Evidence that remains absent

No independent field corpus, outside-authored heldout scenarios, live model calls, customer pilot, Windows execution,
Docker build or remote CI has been performed in this environment. A source name and a boolean independence declaration
remain trusted adapter assertions. A dependency audit and undefined-name lint step are configured in CI but were not
executed locally because those optional tools were unavailable. Do not turn these configurations into green results.

## Review disposition

Fixed: video recording lifecycle; TLS-proxy mutation check; framing/CSP headers; apostrophe escaping; container auth default;
credential-keyed workspace throttling; README/story; contradictory improvement note removal; documentation consolidation;
stream-level uncertainty; authority-error experiment; generated gate checks and gate-weakening counterexample.

Retained limits: one workflow/two repair families; shared fixture truth; non-OS-sandbox worker; threshold sensitivity not
measured; no independent real-drift corpus; no actual platform/pilot/publication evidence. See archive/REVIEW_2026_10_27.md
for the supplied review verbatim. New subframeworks, GNNs, SSO and cosmetic score inflation were not added.

## Saved release outcomes

Matched evaluation: **84 cells, 30 streams per cell, 30,240 recorded runs** (12 runs/stream). These are 2,520 seed/strategy/scenario streams, not independent real incidents.

| Authority condition | Injected fault probability | Mean silent-error rate | Mean false-block rate |
|---|---:|---:|---:|
| correlated_drift | 0 | 0.000 | 0.000 |
| correlated_drift | 1 | 1.000 | 0.000 |
| wrong_reference | 0 | 0.000 | 0.000 |
| wrong_reference | 1 | 0.000 | 1.000 |
| stale | 0 | 0.000 | 0.000 |
| stale | 1 | 0.000 | 1.000 |
| missing | 0 | 0.000 | 0.000 |
| missing | 1 | 0.000 | 1.000 |

Full per-stream distributions and intervals are in benchmark/final/authority.json and aair.json. Endpoint rows above are descriptive summaries, not population guarantees.
