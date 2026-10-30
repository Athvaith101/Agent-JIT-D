# Record an invoice without posting

The first integration adapter accepts a provider you already control. It needs two read methods:
`invoice_get(invoice_id)` and `payment_list(invoice_id, cursor=None)`. They return dictionaries matching
`jitd/schemas.py`. The adapter performs read calls only; it never receives or invokes a ledger writer.
Authentication stays in your provider adapter. Recorded payloads contain business data, not auth headers.
Review payloads for sensitive fields before sharing them.

```python
from jitd.sdk import record_invoice, save_recording, validate_recording
from jitd.compiler import compile_workflow

# provider is your own sandbox adapter implementing the two methods above.
case = record_invoice(provider, 'INV-123', '2026-10-26T12:00:00Z')
save_recording(case, 'invoice-recording.json')
manifest, _ = compile_workflow()
report = validate_recording(manifest, case)
print(report)
```

Upload `invoice-recording.json` in Overview → Bring a recorded invoice. Validation uses only an
in-memory replay service; it does not contact the source API or change its ledger.
Without `expected=...`, a successful result means the current contracts pass, not that correctness
has been independently established. Supply an independently calculated ledger expectation to check that too:

```python
case = record_invoice(provider, 'INV-123', '2026-10-26T12:00:00Z', expected={
    'invoice_id': 'INV-123', 'amount_usd': '125.00',
    'invoice_total_usd': '125.00', 'status': 'paid', 'disposition': 'posted',
})
```

Do not use an expected value computed by the same workflow as independent evidence.
Imported JSON is limited to 2 MiB and 50 pages. Cyclic or missing cursors and invoice identity mismatches
are rejected. A live recording can legitimately fail the synthetic workflow's learned ranges; review and
author domain contracts before using this on real data.
