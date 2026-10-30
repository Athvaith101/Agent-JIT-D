# Visual Agent Builder — 2.3

Open http://127.0.0.1:8000/builder or follow **Visual agent builder** in Studio.
This workspace adds ten executable, bounded JSON templates. The original invoice
Studio remains the deeper integration for drift diagnosis, reviewed repair,
counterfactual replay, checkpoint reuse and Evidence Passports. New canvas
families do not inherit those specialized repair features automatically.

## Build and operate

1. Select a family and load its template. Rename the agent.
2. Drag blocks from the palette onto the canvas, or click them. Drag existing
   blocks to reorder, or use their arrow buttons. Remove blocks with ×.
3. Connections follow the displayed order with typed ports. This is a linear
   pipeline editor, not a branching or arbitrary-code editor. Invalid connections,
   duplicate core blocks, cycles and removal of verification fail validation.
4. Optional summary: add it and move it between Verify and Output.
5. Test & save draft creates an immutable report with the exact graph hash and
   runtime policy hash. Three authored cases test clean, drift and missing evidence.
6. Open Test & operate. Select the report and publish it. In enterprise mode a
   reviewer/admin distinct from the testing builder must publish.
7. Load a clean example and run. Load drift and missing evidence examples to see
   blocks. Examples include five-minute snapshot-bound control records; reload
   after expiry. Paste your own JSON using the same shape for local processing.
8. Runs and versions persist in canvas.sqlite3. The latest 100 appear in lists.
   Draft graph layout is restored from browser local storage. Keys are never there.

Graph edits need a new report; publication always uses the graph recorded in the
selected report. Publishing an older saved report publishes that exact older
content. Published versions and result records are immutable through API/SQL
triggers. Local disk administrators can defeat these controls. No distributed
consensus or externally anchored signatures are claimed.

## Available families

| Family | Calculation / decision | Gate |
|---|---|---|
| Invoice reconciliation | USD paid amount versus invoice | Arithmetic plus control result |
| Invoice discrepancy | USD remaining difference report | Control difference |
| Refund/payout | Integer minor units to major units | Currency minor-unit policy, expected payout and control |
| Shipment | kg or lb to kg | Positive weight, declared match and control |
| Inventory | Opening + received − shipped | Physical count and control |
| Data quality | Unique IDs, count, USD sum | Complete flag, unit and control |
| Recurring report | USD sums grouped by category | Complete flag and control groups/total |
| Ticket triage | Fixed v1 urgent/normal review routing | Known labels, unique IDs and control routes |
| Document change | Compare supplied SHA256 revisions | Claim invalidations and control |
| Deployment readiness | Compare tested/current commit and config | Passed tests, exact revisions and control |

These are actual distinct local computations, not remote business integrations.
Template coverage is narrow: ticket triage has a fixed policy, document monitoring
compares supplied hashes, deployment readiness does not build or deploy software.
Sources are supplied JSON. Synthetic control records are authored with the
implementation. User control records use source IDs prefixed user_control:.
Neither is independently authenticated. Hashes bind bytes, not real-world truth.
There are no real financial writes, email sends, live subscriptions or CI commands.

## API keys and model assistance

Models & keys is admin-only. Paste the key into the password field, copy the exact
model ID from your account, and enter USD input/output rates per million tokens.
Two connection slots support Nebius Token Factory and NVIDIA API Catalog through
fixed HTTPS destinations. No custom URLs are accepted. No network call occurs on
configuration. Credentials stay in server memory, clear on restart, and can be
forgotten. A secure remote deployment needs TLS. Use your provider console to
verify credits; the application cannot guarantee a free call.

The Canvas **Draft with model** action calls the selected connection to select a
supported family. It validates a strict bounded proposal and records its receipt.
It never generates code. The original invoice Studio continues to use its terminal
Nebius configuration; memory connections are scoped to this visual workspace.

The launcher defaults to JITD_MAX_MODEL_CALLS=0. To intentionally allow up to 12
attempts in this workspace, stop the server, then run in PowerShell:

```powershell
$env:JITD_MAX_MODEL_CALLS = "12"
.\.venv\Scripts\python.exe -m jitd.launch
```

Paste the key in Models & keys after restarting. Existing attempted reservations
count against this ceiling. A call cap is not a monetary cap. Failed or interrupted
calls retain reservations. Configuration does not raise the ceiling. Model request
bodies are never included in security audit records. Usage receipts retain model
output and usage; avoid putting personal data or credentials in tasks.

## Tokens, cost and evidence

A live baseline call uses the same input JSON as deterministic execution and the
same strict evidence gate before dispatch. The model is asked to compute the
normalized output without seeing the control's expected answer. Its result is
compared exactly with the qualifying deterministic candidate. This evaluates one
bounded task, not a general autonomous-agent baseline.

Each receipt retains exact model/provider, prompt and completion usage, latency,
rates at dispatch, calculated cost, raw output and correctness/acceptance. Missing
usage is unpriced. Input/output counts are used once; reasoning tokens included
in completion counts must not be added again. Calculated USD uses supplied rates,
not invoices, discounts, caching-specific rates, taxes or account credits.

C_call = (T_input × P_input + T_output × P_output) / 1,000,000
C_baseline(N) = N × C_call
C_JITD(N) = C_setup + C_audit_repair + review_minutes × hourly_rate / 60
            + N × C_verification_runtime
Savings(N) = C_baseline(N) − C_JITD(N)

For positive per-run gap, the first strictly positive break-even is
floor(fixed_cost / per_run_gap) + 1. No positive gap means no positive break-even.
Zero model price does not imply zero verification or human cost. Zero-cost
baselines have undefined percent savings. The calculator labels every curve as
an assumption projection. It does not manufacture proof of cost reduction.

To establish evidence: retain real successful baseline receipts on frozen inputs,
measure stable compiled executions, include setup/repair/audit calls and overhead,
record human effort, and compare accepted correct outputs. Report failed baselines,
unknown usage and negative savings. This release was tested with injected model
clients and no paid calls; those test results are not live NVIDIA/Nebius evidence.

Provider references:
- https://docs.tokenfactory.nebius.com/other-capabilities/billing
- https://dev.nebius.com/cookbook/opencode-nebius-token-factory
- https://docs.api.nvidia.com/nim/reference/llm-apis
