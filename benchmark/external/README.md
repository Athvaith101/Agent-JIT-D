# Externally authored scenarios

Drop a JSON file here and run `python -m jitd.bench --external benchmark/external`. No code changes are needed.

```json
{"id": "my_drift", "title": "...", "kind": "drift|benign|business_exception|hard",
 "fault_op": null | "invoice.get" | "payment.list" | "normalize_money" | "invoice.get+payment.list",
 "repairable": false, "author": "your name (required)", "independent": true,
 "desc": "...", "truth_mod": null | "short" | "big", "truth_p": 0.25, "installments": 4,
 "mutations": [{"endpoint": "payment.list", "op": "scale", "fields": ["payments[*].amount"], "factor": 100}]}
```
Mutation ops: `scale` (fields, factor in 10/100/1000/10000), `null`, `stringify`, `upper` (fields), `add_field` (name, value), `page_size` (value 1..50).
Fields are simple paths such as `total`, `tax`, `line_items[*].unit_price`, `payments[*].amount`, `payments[*].status`.

Set `"independent": true` **only if someone other than the JIT-D authors wrote the scenario without reading the contracts**. The two files here are examples written by the authors and are marked as such; results on them are reported as external-format but NOT independent.
Mutations are applied only after the seeded onset. Scenarios are evaluated with the thresholds and contracts as they are; do not tune them afterwards.
