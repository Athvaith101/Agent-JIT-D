"""Read-only authority integration; independence is configured by the operator."""
import csv
import hashlib
import io
from decimal import Decimal
from pathlib import Path
FIELDS = {'invoice_id', 'invoice_total_usd', 'settled_total_usd', 'currency', 'observed_at', 'source_id', 'provider_snapshot'}


def load_evidence(path, invoice_id, snapshot, trusted_source):
    if not trusted_source or trusted_source.startswith('provider') or not snapshot:
        raise ValueError('Explicit independent source and immutable snapshot required')
    raw = Path(path).read_bytes()
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError('Authority file exceeds 2 MiB')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    if set(reader.fieldnames or []) != FIELDS:
        raise ValueError('Authority CSV columns do not match schema')
    matches = [r for r in reader if r['invoice_id'] == invoice_id]
    if len(matches) != 1:
        raise ValueError('Exactly one authority record required per invoice')
    return evidence_record(matches[0], invoice_id, snapshot, trusted_source, hashlib.sha256(raw).hexdigest())


def evidence_record(row, invoice_id, snapshot, trusted_source, record_hash):
    if not trusted_source or trusted_source.startswith('provider') or not snapshot:
        raise ValueError('Explicit independent source and immutable snapshot required')
    if row.get('invoice_id') != invoice_id:
        raise ValueError('Authority invoice identity mismatch')
    if row['source_id'] != trusted_source or row['provider_snapshot'] != snapshot or row['currency'] != 'USD':
        raise ValueError('Authority source, snapshot or currency mismatch')
    for field in ('invoice_total_usd', 'settled_total_usd'):
        amount = Decimal(row[field])
        if not amount.is_finite() or amount < 0:
            raise ValueError('Authority amount must be finite and nonnegative')
    common = {'source_id': trusted_source, 'independent_of': 'provider', 'currency': 'USD',
              'observed_at': row['observed_at'], 'simulated': False,
              'record_sha256': record_hash, 'invoice_id': invoice_id}
    return {'snapshot_bound': True,
            'billing_authority': {**common, 'invoice_total_usd': row['invoice_total_usd']},
            'settlement_authority': {**common, 'settled_total_usd': row['settled_total_usd']}}
