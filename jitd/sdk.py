"""Small, read-only recording adapter for invoice connectors.

The caller supplies an authenticated provider implementing invoice_get and payment_list.
No credentials, headers, network client or write method are recorded. This is an
invoice adapter, not a general agent compiler. Expectations must be independently supplied.
"""
import copy
import json
from pathlib import Path
from .services import capture_case
from .schemas import InvoiceResp, PaymentsResp, validate
from .validation import run_validation


def record_invoice(provider, invoice_id, as_of, *, expected='unknown'):
    case = capture_case(provider, invoice_id, as_of, expected)
    check_recording(case)
    return copy.deepcopy(case)


def check_recording(case):
    if not isinstance(case, dict) or not isinstance(case.get('invoice_id'), str) or not isinstance(case.get('as_of'), str):
        raise ValueError('recording needs invoice_id and as_of strings')
    validate(InvoiceResp, case.get('invoice'), 'recorded invoice')
    if case['invoice']['invoice_id'] != case['invoice_id']:
        raise ValueError('invoice identity does not match recording')
    pages = case.get('pages')
    if not isinstance(pages, dict) or '' not in pages or not 1 <= len(pages) <= 50:
        raise ValueError('recording needs 1..50 cursor-indexed pages, beginning with the empty cursor')
    cursor, seen = '', set()
    while cursor is not None:
        if cursor in seen or cursor not in pages:
            raise ValueError('recording has a missing or cyclic cursor')
        seen.add(cursor)
        page = pages[cursor]
        validate(PaymentsResp, page, 'recorded payments')
        if page['invoice_id'] != case['invoice_id']:
            raise ValueError('payment page identity does not match recording')
        cursor = page.get('next_cursor')
    if seen != set(pages):
        raise ValueError("recording contains unreachable payment pages")
    return case


def save_recording(case, path):
    check_recording(case)
    Path(path).write_text(json.dumps(case, indent=2, default=str), encoding='utf-8')


def validate_recording(manifest, case):
    check_recording(case)
    report = run_validation({'manifest': manifest.model_dump(), 'groups': {'recorded': [case]}})
    report['correctness_basis'] = ('independent expectation supplied by caller' if case.get('expected', 'unknown') != 'unknown'
                                   else 'contracts only; correctness is not independently established')
    report['writes'] = 'in-memory RecordedServices only; never the source provider'
    return report
