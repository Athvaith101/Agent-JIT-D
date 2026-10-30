"""Read models for the operations UI. Cost projections never masquerade as measured savings."""
import statistics


def overview(lab):
    with lab.lock:
        rows = [lab.run_view(r) for r in reversed(list(lab.runs.values()))]
        correct = sum(r['oracle_verdict'] in ('correct_post', 'correct_block') for r in rows)
        completed = sum(r['outcome'] == 'posted' and r['oracle_verdict'] == 'correct_post' for r in rows if r.get('verification_policy') != 'legacy_comparison')
        incidents = [r for r in rows if r['outcome'] in ('halted', 'held', 'error')]
        open_incidents = [r for r in incidents if not (r.get('repair') or {}).get('accepted')]
        return {
            'mode': 'synthetic_provider', 'scope': f'Last {lab.run_cap} retained runs; counters reset with sandbox',
            'completed_correctly': completed, 'cost_summary': lab.meter.cost_summary(completed),
            'total_runs': len(rows), 'correct_runs': correct,
            'correct_run_rate': correct / len(rows) if rows else None,
            'silent_errors': sum(r['oracle_verdict'] == 'silent_error' for r in rows),
            'blocked': sum(r['outcome'] in ('halted', 'held') for r in rows),
            'open_incidents': len(open_incidents), 'paused': lab.paused,
            'median_ms': statistics.median(r['duration_ms'] for r in rows) if rows else None,
            'versions': sorted((p.stem for p in (lab.dir / 'workflows' / lab.manifest.workflow_id).glob('*.json')),
                               key=lambda v: tuple(map(int, v.split('.')))),
            'runs': rows, 'incidents': incidents,
            'pending_proposals': [{'proposal_id': p['id'], 'run_id': p['run_id'], 'created': p['created'],
                'validated': True, 'repair': lab._repair_view(p['record'])} for p in lab.store.pending()
                if p['run_id'] in lab.runs and p['version'] == lab.manifest.version and p['scenario'] == lab.scenario_id],
            'usage': lab.meter.usage, 'meter': lab.meter.snapshot(),
            'cost_note': 'No measured agent baseline is available. Savings are scenario estimates, not customer ROI.'
        }
