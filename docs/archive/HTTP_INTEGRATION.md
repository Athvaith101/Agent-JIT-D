# HTTP shadow integration

This release adds actual GET requests over HTTP(S), full declared payment pagination, immutable snapshot checks,
and separately configured authority retrieval. It performs no external writes. It is a generic adapter contract,
not a prebuilt Stripe, bank or ERP integration. Existing interactive UI providers remain simulated.

## Run on Windows PowerShell

After installing the existing requirements, from the project directory:

```powershell
$env:JITD_PROVIDER_TOKEN="your-read-only-provider-token"
$env:JITD_AUTHORITY_TOKEN="your-read-only-authority-token"
.\.venv\Scripts\python.exe -m jitd.shadow --provider-url https://provider.example/api --authority-url https://control.example/api --invoice-id INV-001 --as-of 2026-10-26T00:00:00Z --source finance-control
```

Replace the example URLs with services implementing the contract below. Tokens are optional for local test services;
they are sent only to their corresponding origin. Unset JITD_AUTHORITY_CSV when using this HTTP authority path.
Tokens are not CLI arguments and are not included in reports. TLS certificate checks remain enabled. Redirects are rejected;
no retries hide rate limits or source failures. Loopback HTTP requires --allow-local-http for local testing.

## Provider contract

- GET /invoice?invoice_id=...&as_of=... returns the existing InvoiceResp JSON schema.
- GET /payments?invoice_id=...&as_of=...&snapshot=... returns PaymentsResp JSON.
- Subsequent payment requests add cursor=... . Cursor values remain opaque query parameters, never URLs.
- Every response must return the same nonempty X-JITD-Snapshot header (maximum 256 characters).
- Every payment page must explicitly include next_cursor; null terminates pagination.
- At most 20 pages are captured. Cycles, repeated payment IDs, wrong invoice identities and changed snapshots reject capture.
- All endpoints return application/json, HTTP 200, and at most 2 MiB per response.

The upstream adapter must guarantee that the token describes immutable, versioned data covering the invoice and payment
pages. An arbitrary repeated header does not create that guarantee. Unsupported APIs need a connector providing equivalent
version semantics before checkpoint reuse can be trusted. Different source origins are an additional guard, not proof
of independent ownership or failure modes.

## Authority contract

GET /evidence?invoice_id=...&snapshot=... returns a single JSON object:

```json
{
  "invoice_id": "INV-001",
  "invoice_total_usd": "125.00",
  "settled_total_usd": "125.00",
  "currency": "USD",
  "observed_at": "2026-10-26T00:00:00Z",
  "source_id": "finance-control",
  "provider_snapshot": "immutable-version-from-provider"
}
```

Use actual observation time; this sample will not remain fresh. Evidence must be independently obtained and explicitly
bound to the source version, not computed by blindly echoing the query. Monetary references are finite and nonnegative.
Freshness remains the existing five-minute policy. Wrong invoice, source, version, currency, stale/malformed/unavailable
proof cannot establish VALID. A canonical evidence hash appears in the verification trace.

The authority supplies both invoice and settlement truth. It must have a justified basis for both. Same-origin sources
are refused before requests; distinct origins alone cannot prove independence. Authentication and semantic correctness
of the evidence producer remain deployment responsibilities.

## Execution and reports

The connector first captures an immutable read set, validates its identities and pagination, then executes the guarded
workflow against that captured data. It uses the captured page count as the workflow read limit; this is not a discovered
repair. No automatic patch approval or replay advantage is claimed by this connector. The simulated in-memory ledger is
the only sink. `posted` means the shadow calculation was accepted, not that a bank/ERP was updated.

Reports include required assumptions, evidence hashes, snapshot, page count, GET counts, measured network time and total
time. Missing authority fails closed with UNKNOWN. Capture/configuration failures return a sanitized error. Exit 0 means
accepted shadow calculation; exit 2 means rejected/held/input failure. HTTPX timeout is an inactivity timeout per operation,
not a total transaction deadline. Maximum response/page limits bound retained data, not remote server processing time.

## Evidence and remaining gates

Local socket tests exercise real HTTP requests against two independently addressed test servers. Their financial data
is synthetic. No external provider account, real financial corpus, pilot ROI or live Nemotron run has been evaluated.
Bundled synthetic benchmark files retain their original source fingerprints and describe the older release.

Next: implement these endpoints for a chosen real provider and independently controlled authority; run read-only shadow
cases; measure evidence coverage and false blocks; compare recovery approaches on identical evidence; then measure live
Nemotron proposals. The core UI and normal local demo remain available through python -m jitd.launch.
