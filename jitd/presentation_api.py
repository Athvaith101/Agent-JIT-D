"""Read-only, bounded presentation of recorded evidence; never dispatches inference."""
import json
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse
from .live import summarize

router = APIRouter()
ROOT = Path(__file__).resolve().parent.parent


def evidence_summary(root=ROOT):
    records = []
    for path in sorted((root / 'evidence').glob('live_*.json'), reverse=True)[:20]:
        try:
            if path.stat().st_size > 5_000_000:
                continue
            value = json.loads(path.read_text())
            if value.get('kind') != 'jitd_live_evidence' or value.get('source_mode') != 'nebius_api':
                continue
            stats = summarize(value)
            # Strict projection: no raw prompts, credentials, errors or arbitrary response text.
            records.append({'file': path.name, 'model_id': str(value.get('model_id', ''))[:160],
                            'started_utc': str(value.get('started_utc', ''))[:40], 'summary': stats,
                            'compiles': [{'attempt': row.get('attempt'), 'used_model_plan': bool(row.get('used_model_plan')),
                                          'plan_source': str(row.get('plan_source', ''))[:80]} for row in value.get('compiles', [])[:10]],
                            'repairs': [{'scenario': str(row.get('scenario', ''))[:40],
                                         'nemotron_proposal_accepted': bool(row.get('nemotron_proposal_accepted')),
                                         'deterministic_fallback_accepted': bool(row.get('deterministic_fallback_accepted'))}
                                        for row in value.get('repairs', [])[:10]]})
        except (ValueError, OSError, TypeError, AttributeError, KeyError):
            continue
    return {'available': bool(records), 'records': records, 'replay_only': True,
            'note': 'Recorded provider receipts, not a new model call or an independent provider attestation. Synthetic financial inputs. No dollar savings inferred.'}


@router.get('/demo')
def demo_page():
    return FileResponse(ROOT / 'web' / 'demo.html')


@router.get('/api/presentation/evidence')
def evidence():
    return evidence_summary()


@router.get('/api/presentation/usage.csv')
def usage_csv():
    import csv
    import io
    from fastapi.responses import Response
    from .studio_api import get_studio
    from . import llm
    studio = get_studio()
    with studio.connect() as db:
        receipts = [json.loads(row[0]) for row in db.execute('SELECT payload FROM receipts ORDER BY rowid DESC LIMIT 1000')]
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(['receipt_id', 'role', 'model_id', 'source', 'accepted', 'input_tokens', 'output_tokens', 'status'])
    def cell(value):
        value = llm.sanitize(Exception(str(value))).removeprefix('Exception: ')
        return "'" + value if value.startswith(('=', '+', '-', '@', '\t', '\r')) else value
    for receipt in receipts:
        for usage in receipt.get('usage', []) or [{}]:
            writer.writerow([cell(receipt.get('id', '')), cell(receipt.get('role', '')), cell(receipt.get('model_id', '')),
                             cell(receipt.get('source_mode', '')), receipt.get('accepted', False), usage.get('input_tokens'),
                             usage.get('output_tokens'), cell(usage.get('status', receipt.get('status', '')))])
    return Response(out.getvalue(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="jitd-model-usage.csv"', 'Cache-Control': 'no-store'})
