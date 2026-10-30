# Integrated P0–P2 release

## What can be completed in this package

| Gate | Implemented workflow | Evidence still required |
|---|---|---|
| P0 live Nemotron | Bounded measured live harness, failure accounting, checkpoints | Actual account/model run |
| P0 real provider | GET-only versioned HTTP adapter and recording capture | Authorized real provider and version guarantees |
| P0 independent authority | Source/identity/version/freshness checks; evidence import and refresh | Operationally independent source owner and data |
| P0 unseen incidents | Provenance-bearing case bundle import; preserve author/collection declaration | Someone outside implementation must author and freeze cases |
| P0 novelty | Same-evidence paired comparison and UI results | No semantic-slicing advantage currently established |
| P1 actual model baseline | Single-call full-input reasoning with real usage and shared output gate | Real paid run; not an iterative tool-agent baseline |
| P1 practical overhead | Runtime, request usage, verification coverage and review-time reports | Customer workload and independently adjudicated correctness labels |
| P1 resolution flow | Missing proof → review → fresh evidence → strict re-verification → shadow acceptance | Operational exercise on real cases |
| P1 pilot | Durable cases, revision conflicts, observation history and export | Read-only customer pilot |
| P1 Windows | Terminal commands, OS CI matrix, smoke checklist | Execute on the actual Windows laptop |
| P1 demo/submission | Updated script, readiness panel and claim boundaries | Record video and review submission |
| P2 hosted demo | Optional Basic access gate, same-origin mutations, protected Render defaults | Deploy/test on chosen HTTPS host |

A runnable implementation is not a completed external experiment. The readiness page explicitly retains pending gates.
No token, customer data, external account, Windows desktop or deployment host was supplied in this session.

## Run locally, without .bat or activation

Open PowerShell in the extracted jitd folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m jitd.launch
```

Open http://127.0.0.1:8000 and select **Pilot & readiness**. Keep external CSV environment settings unset when using
pilot case bundles or the controlled model comparison; each bundle supplies its own frozen evidence.

## Demonstrate the complete resolution workflow

In another terminal from the same folder:

```powershell
.\.venv\Scripts\python.exe scripts/create_pilot_demo.py
```

1. Import data/pilot-demo/missing.json in Pilot & readiness. It must remain blocked with UNKNOWN evidence.
2. Open Review evidence & re-verify. Enter reviewer and evidence note.
3. Paste the JSON from data/pilot-demo/authority.json into the authority field and enter actual human minutes.
4. Submit within five minutes of observation. Fresh proof permits a verified **shadow** output; no bank/ERP write occurs.
5. Review again with a wrong amount. Verification must block; a note cannot override it.
6. Export pilot evidence. Cases, all observations, review notes, revisions and ordered audit events survive restarts.

The generator is explicitly fixture-derived; it is not independent financial evidence. Generate again rather than altering
a stale timestamp. Never relabel this data real. Original observations remain in history when evidence is refreshed.

## Case bundle contract

```json
{
  "recording": {"invoice_id":"INV-001","as_of":"2026-10-27T00:00:00Z","invoice":{},"pages":{},"expected":"unknown"},
  "source":"finance-control",
  "authority":null,
  "provenance":{
    "author":"person or source owner",
    "collection_method":"authorized read-only export; describe collection",
    "real_data":false,
    "independent_authority":true
  }
}
```

invoice/pages must use the complete schemas documented in EXTERNAL_INTEGRATION.md; empty objects above illustrate only
the envelope, not a valid recording. At most twenty pages and 2 MiB per imported bundle are supported. No repeated payment
IDs or credential fields are permitted. Authority uses the documented monetary fields, invoice_id, actual observed_at,
source_id and provider_snapshot. For bundle imports provider_snapshot is the recording content hash from
`python -m jitd.integrate --recording recording.json --snapshot-only`. It binds the reviewed artifact, not a live cross-service
transaction. A live provider version token from the HTTP connector is a different contract; an export preparer must bind
independent observations to the captured recording without inventing atomicity.

The author and independence fields are declarations, not authenticated provenance. Someone outside the implementation
must supply unseen cases. Do not submit customer personal data without authorization. Local SQLite is not encrypted.
Review identity in this single-workspace prototype is entered text, not SSO. Audit events are durable, not tamper-proof.

## Measured reasoning baseline

Configure your actual Nebius key/model as described in LIVE_EVALUATION.md, then run:

```powershell
$env:JITD_MAX_MODEL_CALLS="5"
.\.venv\Scripts\python.exe -m jitd.model_baseline data/pilot-demo/ready.json --output evidence/baseline_run.json
```

This sends one model request per bundle (up to twenty cases), with complete captured inputs and the same frozen authority
observations available to the compiled calculation. Replies are proposals. Both outputs must pass the same final
monetary/business gate; compiled execution also retains existing mined contracts. A model can correctly use the supplied
reference amounts; this tests reasoning/proposal behavior, not discovery of hidden truth. The compiled source is the
predefined invoice recipe. No model-compilation bill is claimed for it.

Request counts, usage, wall time and shared compile setup are recorded. Incomplete usage is not zero billing. Real API
failure and malformed reply outcomes are retained. Each completed case is atomically checkpointed. An interrupted batch has completed=false and is not final evidence. There is no independent correctness denominator, so cost_per_correct_usd
remains undefined. This is a measured single-call full-input baseline, not a universal repeated tool-using agent comparison.

## Reports and claims

Pilot metrics count verified shadow outputs, blocked cases, declared-real cases, evidence coverage (required observations
not UNKNOWN), and reviewer-entered time. Contradictory INVALID evidence counts as observed coverage but never acceptance.
There is no automatic inference of false-positive rate, customer ROI or field correctness. To measure those, an independent
reviewer must label true business outcomes, and cost accounting must include acquisition, verification, failures and human
work. Repeated imports are separate cases; do not treat them as independent customers or incidents.

The readiness screen inspects local live/model reports and pilot records. Evidence presence is not authenticity. Pending
unseen incidents, Windows validation, novelty and hosted testing never silently turn into completed research claims.

## Hosted demonstration

Default local launch remains loopback. For an HTTPS host:

- Set JITD_REQUIRE_AUTH=1 and a long random JITD_ACCESS_TOKEN. The supplied Render blueprint generates one and sets a
  low paid-call cap of twelve. Browser login uses username **jitd** and that token as password.
- Missing token with required auth returns 503; incorrect credentials return 401. /api/health remains public for healthchecks.
- All application/static/API routes are protected except health. Origin-bearing cross-site mutations are rejected.
- Use one instance/worker. SQLite needs durable storage for retained pilot data; the free blueprint is explicitly ephemeral.
- Configure Nebius keys as runtime secrets, not in an uploaded archive. Access protection is a single-workspace gate,
  not tenant isolation, SSO or a transactional financial posting guarantee. Use HTTPS; Basic credentials are not encryption.

Docker and Render configuration are supplied; this session has not built an image or deployed a public host.

## Submission demo (three minutes)

0:00–0:30 Explain a schema-valid semantic change and the consequential incorrect write it could cause.
0:30–1:20 Run the existing unit-drift demo, propose a bounded repair, validate, approve and show safe recovery.
1:20–2:10 Import a missing-proof case, demonstrate that a note cannot approve it, add fresh authority proof and re-verify.
2:10–2:40 Show measured live usage if actually collected and the same-evidence comparison including its negative result.
2:40–3:00 Show readiness gates and describe the remaining independent pilot evidence. Do not claim semantic-slicing
superiority, production financial safety, research novelty or numerical ROI without results establishing those claims.

## Windows acceptance checklist

Run `python -m pytest -q`, launch the browser, run the resolution demo, run HTTP local connector tests, and collect one actual
live model report. Save terminal output, Python version and exact ZIP version. Remote CI and a Linux test pass are not a
substitute for executing on your laptop. A separate recording of the final demonstration remains required.

## HTTP capture directly into the pilot

The existing shadow command can export an importable case without retyping evidence:

```powershell
.\.venv\Scripts\python.exe -m jitd.shadow --provider-url https://provider.example/api --authority-url https://control.example/api --invoice-id INV-001 --as-of 2026-10-27T00:00:00Z --source finance-control --case-out data/captured-case.json --author "Authorized operator" --real-data
```

Use actual endpoints, invoice and observation time. Omit --real-data for synthetic/local services. Import the exported
JSON in Pilot & readiness. This preserves the authority's original provider-version token and records a separate content
hash of the captured recording. Pilot verification requires both the unchanged local recording hash and the matching
provider/authority version. The exporter does not rewrite authority timestamps or amounts. Provenance and independence
remain operator declarations, with no cryptographic authentication. Changing captured invoice/payment bytes invalidates
the local binding and leaves proof UNKNOWN. Fresh authority still must satisfy the five-minute observation policy.
