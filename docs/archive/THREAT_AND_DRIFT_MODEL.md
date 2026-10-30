# Drift model and threat model

## Drift classes implemented (mock provider)

| Scenario | Schema changes? | What changes | Independent check that notices | Expected handling |
|---|---|---|---|---|
| cosmetic | no | key order, extra fields, upper-case status, string amounts | none should fire | pass |
| unit_cents / unit_mills | no | `amount` is 100x / 1000x larger, still a number | payment == invoice (critical) | halt, localize to the unit assumption, repair |
| truncation | no | payments paginated (2 per page) | completeness (critical) | halt at fetch, repair with bounded pagination |
| malformed | yes (null amount) | boundary schema fails | schema | halt, no repair |
| underpayment | no | customer really paid 3.7% less | payment == invoice | halt, classify as business exception, **no repair** |
| consistent_scale | no | invoice and payments both in cents | magnitude ranges only (warning) | hold; partial miss expected |
| big_invoice (benign) | no | legitimate very large invoices | magnitude ranges (warning) | should pass; is held (false positive) |
| compound | no | cents + truncation together | completeness | halt; no single bounded repair fixes both |

Not implemented: timezone semantics, enum remapping, field-meaning shifts. They are plausible extensions, not claims.

## Threats and non-goals
- **Model errors:** a wrong plan or repair is rejected by independent validation (tested with fake clients that lie).
- **Generated code:** never executed. The only model output used is a JSON proposal checked against an allowlist.
- **Secrets:** the API key lives in the server process; the validation worker runs with a scrubbed environment (tested); events and exports contain only synthetic data.
- **Not covered:** adversarial providers, malicious fixtures, authentication, multi-tenant isolation, production deployment safety. Hackathon safeguards are not a security certification.
