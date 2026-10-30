# External evidence integration — first milestone

The read-only invoice recording path now accepts an independently supplied authority CSV.
It does not derive reference amounts from fixture truth. Existing interactive invoice providers remain simulated.
No real customer corpus, bank integration or live model evaluation has been performed.

## Windows terminal

From the project directory after installing requirements:

```powershell
.\.venv\Scripts\python.exe -m jitd.integrate --recording recording.json --snapshot-only
.\.venv\Scripts\python.exe -m jitd.integrate --recording recording.json --authority authority.csv --source finance-control
```

The first command returns the immutable recording content hash. An authorized evidence preparer must bind independently
obtained reference values to that recording by putting the hash into provider_snapshot. This binds the reviewed artifact;
it does not establish atomic consistency between two live remote systems.

CSV header (exact columns, any order):

```csv
invoice_id,invoice_total_usd,settled_total_usd,currency,observed_at,source_id,provider_snapshot
```

Supply exactly one row per invoice. source_id must match --source. Use USD, nonnegative finite amounts,
a timezone-aware ISO observation timestamp within five minutes, and the recording hash. A duplicate row, mismatched
snapshot/source/currency, malformed value, stale record or missing file cannot establish VALID. Timestamp means the time
the control observation was actually obtained; never refresh it merely to pass validation. Old exports need a separately
specified historical verification policy; they cannot pass the current live-freshness gate.

Recording shape follows jitd.sdk.record_invoice: invoice_id, as_of, invoice response, cursor-keyed pages, optional expected.
The CLI ignores expected for authority verification. Provider response schemas remain the existing invoice schemas.
The ledger is in memory. Exit 0 means the guarded recording completed; exit 2 means held/halted. A malformed input may
produce an input error. No external writes are performed.

## Existing runtime integration

Optional .env settings JITD_AUTHORITY_CSV and JITD_AUTHORITY_SOURCE select the file evidence adapter for execution.
Once selected it never falls back to simulated evidence on error. An external adapter must provide snapshot_token;
without immutable snapshot semantics the required authority check remains UNKNOWN. In the local interactive lab the
source provider and its snapshot remain synthetic; selecting an external file does not turn it into a real API connector.
Evidence records retain the authority file SHA-256 and invoice identity for audit linkage.

## Trust and scope

The configured source is an operator trust decision. A CSV source name is not authenticated bank provenance and a content
hash is not a signature. A malicious preparer can fabricate values and timestamps. Use separately controlled evidence
collection and obtain authorized, sanitized recordings for a pilot. One combined authority export currently supplies both
monetary references; their independence from the provider must be established operationally. A settlement-only export
cannot prove invoice truth. The current gate still requires both references.

This milestone makes external testing possible; it does not establish field accuracy or novel slicing. Packaged benchmark
results and their fingerprints describe the preceding synthetic release and have not been regenerated for this integration.

## Next acceptance gates

1. Obtain independently collected invoice and settlement observations with an accountable source owner.
2. Measure coverage and freshness failures in read-only shadow mode.
3. Run same-evidence AAIR versus dependency replay and full recomputation on unseen incidents.
4. Run actual Nemotron proposals and retain usage, rejected patches and outcomes.
5. Demonstrate an assumption-only invalidation case and operator resolution before proposing real writes.
