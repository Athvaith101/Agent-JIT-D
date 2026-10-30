"""Explicit semantic assumptions and evidence. A schema pass is never a unit proof.

The demo's independent authority is simulated. It is a different service boundary,
not an independently authored evaluation corpus. Production requires a real trusted authority.
"""
import os
from datetime import datetime, timezone
from decimal import Decimal
from .money import D


def closure(manifest, roots):
    affected = set(roots)
    for step, deps in manifest.deps().items():
        if set(deps) & affected:
            affected.add(step)
    return [s.id for s in manifest.steps if s.id in affected]


def registry(manifest):
    def sid(op):
        step = manifest.step_for_op(op)
        return step.id if step else None
    out = []
    for aid, text, op, source, contract in [
        ('invoice-unit', 'Invoice total is expressed in USD dollars', 'invoice.get', 'billing_authority', 'invoice_total_usd'),
        ('payment-unit', 'Normalized payments equal the independent settled USD amount', 'normalize_money', 'settlement_authority', 'settled_total_usd'),
        ('pagination', 'Every declared payment page has been consumed', 'payment.list', 'provider', 'next_cursor'),
        ('business-reconciliation', 'Invoice arithmetic and paid totals agree', 'reconcile_amounts', 'cross_service', 'residuals'),
    ]:
        node = sid(op)
        if node:
            out.append({'id': aid, 'semantic_contract': text, 'operation': op, 'node': node,
                        'evidence_source': source, 'evidence_field': contract,
                        'consumers': closure(manifest, [node]), 'status': 'UNKNOWN', 'verified_at': None,
                        'required': True})
    return out


def verify(manifest, values, evidence=None):
    records = []
    evidence = evidence or {}
    for assumption in manifest.assumptions or registry(manifest):
        a = dict(assumption, status='UNKNOWN', verified_at=None, reason='Required evidence has not been observed.', evidence=None)
        node = a['node']
        output = values.get(node)
        now = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
        if node not in values:
            records.append(a)
            continue
        try:
            if a['id'] in ('invoice-unit', 'payment-unit'):
                proof = evidence.get(a['evidence_source'])
                # Explicit trust is configured at the service adapter boundary. Same-source aliases do not qualify.
                if not isinstance(proof, dict) or proof.get('independent_of') != 'provider' or not proof.get('source_id') or str(proof['source_id']).startswith('provider') or proof.get('currency') != 'USD':
                    a['reason'] = 'Independent USD authority unavailable or provenance does not establish separation from the provider.'
                elif not proof.get('observed_at') or not evidence.get('snapshot_bound'):
                    a['reason'] = 'Authority evidence is not bound to this read snapshot.'
                else:
                    observed_at = datetime.fromisoformat(proof['observed_at'].replace('Z', '+00:00'))
                    if observed_at.tzinfo is None or not -5 <= (datetime.now(timezone.utc)-observed_at).total_seconds() <= 300:
                        raise ValueError('independent observation is stale or not timezone-aware')
                    expected = D(proof[a['evidence_field']])
                    observed = D(output['total']) if a['id'] == 'invoice-unit' else sum((D(v) for v in output), Decimal('0'))
                    agrees = abs(observed-expected) <= Decimal('.01') and (a['id'] != 'invoice-unit' or output.get('currency') == 'USD')
                    a.update(status='VALID' if agrees else 'INVALID',
                             verified_at=now, evidence={'source_id': proof['source_id'], 'independent_of': 'provider',
                             'observed_at': proof['observed_at'], 'expected_usd': str(expected), 'observed_usd': str(observed),
                             'invoice_id': proof.get('invoice_id'), 'record_sha256': proof.get('record_sha256'),
                             'basis': 'simulated independent authority' if proof.get('simulated') else 'adapter-supplied trusted authority'},
                             reason='Independent USD authority agrees.' if agrees else 'Independent USD authority contradicts the provider-derived amount or currency.')
            elif a['id'] == 'pagination':
                complete = isinstance(output, dict) and 'next_cursor' in output and output['next_cursor'] is None
                a.update(status='VALID' if complete else 'INVALID', verified_at=now,
                         reason='Declared cursor chain is complete; hidden provider omissions require settlement evidence.' if complete else 'More payment pages remain.',
                         evidence={'source_id': 'provider', 'scope': 'cursor completeness only; not independent unit evidence'})
            elif a['id'] == 'business-reconciliation':
                valid = D(output['invoice_residual']) <= Decimal('.01') and (output['provider_status'] != 'paid' or D(output['payment_residual']) <= Decimal('.01'))
                a.update(status='VALID' if valid else 'INVALID', verified_at=now,
                         reason='Business residuals agree; this does not establish source independence.',
                         evidence={'source_id': 'provider', 'scope': 'internal/cross-service consistency; may fail together'})
            else:
                a['reason'] = 'No verifier is implemented for this assumption.'
        except (KeyError, ValueError, TypeError, ArithmeticError):
            a.update(status='UNKNOWN', reason='Evidence is malformed or incomplete; no proof established.')
        records.append(a)
    return records


def evidence_from(services, invoice_id):
    getter = getattr(services, 'verification_evidence', None)
    try:
        if os.getenv('JITD_AUTHORITY_CSV'):
            from .evidence_csv import load_evidence
            snapshot = getattr(services, 'snapshot_token', lambda _: None)(invoice_id)
            return load_evidence(os.environ['JITD_AUTHORITY_CSV'], invoice_id, snapshot,
                                 os.getenv('JITD_AUTHORITY_SOURCE', ''))
        return getter(invoice_id) if getter else {}
    except Exception:
        return {}  # unavailable is UNKNOWN; never substitute provider data or model agreement
