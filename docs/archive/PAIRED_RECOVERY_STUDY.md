# Paired recovery study — what the implementation actually adds

## Reproduce on Windows

From the extracted project directory, after installing requirements:

```powershell
.\.venv\Scripts\python.exe -m jitd.paired_study --seeds 5 --output benchmark/paired/latest.json
```

Unset JITD_AUTHORITY_CSV first: this controlled synthetic experiment must not accidentally consume a customer file.
No keys or paid calls are required. Raw per-trial records and cell summaries are saved in JSON.

## Experimental controls

Five cases, five deterministic seed configurations, three methods: 75 recovery trials. Within each episode every method
receives the same prior checkpoint, candidate manifest, inputs, immutable source version and frozen authority observation.
Hash receipts for evidence, prior and candidate make this inspectable. Method order rotates with seed. Each method has
its own cloned services, counters and empty ledger. The ordinary dependency ablation retains integrity checks, snapshot
checks, changed-policy fallback and the same final independent verification gate. It disables semantic invalidation roots
explicitly; it no longer deletes assumption records from the prior run to implement the comparison.

Full rerun executes the same candidate without checkpoints. It is not model regeneration. Unit repair is supplied identically
to all methods; patch discovery and approval cost are outside this recovery-only experiment. Compilation is measured once
as common setup. Recovery wall and verification time are measured; no dollar savings or paid-model result is inferred.

## Saved outcomes

Each row summarizes five episodes per method. All methods produced the same accepted ledger or blocked outcome in every
paired episode. There were zero silent errors in these 75 synthetic trials.

| Case | Correct outputs per method | Blocked per method | AAIR reused nodes | Dependency replay reused nodes | Full rerun reused nodes |
|---|---:|---:|---:|---:|---:|
| Unit conversion repair | 5/5 | 0 | 20 | 20 | 0 |
| Missing evidence becomes available | 5/5 | 0 | 10 | 35 | 0 |
| Fresh evidence contradicts unchanged data | 0/5 | 5 | 10 | 35 | 0 |
| Required unsupported policy introduced | 0/5 | 5 | 0 | 0 | 0 |
| Source version changes | 5/5 | 0 | 0 | 0 | 0 |

Reused-node counts are totals across five episodes, not percentages. A node can be reused without being independently
certified until the final gate. In the contradiction case dependency replay executes no data transforms and the shared
fresh evidence gate still blocks the sink. An executed-node count excludes a sink skipped because verification failed.

## Interpretation

The assumption-only cases deliberately hold data and code fixed while evidence availability or its conclusion changes.
They do not demonstrate superiority of semantic slicing. In this graph the shared fresh verification gate already protects
ordinary data-dependency replay. AAIR invalidates additional regions and can perform unnecessary work. Zero silent errors
here is a mechanism result, not a general accuracy estimate. Timing differences on an eight-step in-process graph do not
establish a customer speed or cost advantage.

The supported claim is bounded, snapshot-safe recovery with explicit independently gated acceptance. The stronger claim
that semantic slicing outperforms ordinary incremental recovery is not established by this release. Present the negative
result if asked. Do not create a weak comparison by withholding evidence or integrity checks from the baseline.

## Remaining acceptance gates

- Independently authored incidents and genuinely independent observations.
- A real workflow where semantic dependency metadata changes a recovery decision beyond equivalent verification.
- Connector call cost, verification coverage, false blocks and human incident-resolution time.
- Measured live Nemotron proposal quality and usage; same patch-validation standard for all methods.

All authorities and ground truth here remain synthetic and share fixture construction. Seeds vary generated input values,
not independently discovered fault classes. The existing UI benchmark still displays the earlier broad synthetic study;
this paired study is a separate CLI artifact with its own source fingerprint. Older benchmark files keep historical hashes.
