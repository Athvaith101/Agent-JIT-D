"""Conservative recovery tiers. Cost weights are assumptions, not measured model billing."""

def choose(run, diagnosis, model_available=False):
    unknown = any(a['status'] == 'UNKNOWN' and a.get('required') for a in run.assumptions)
    local = diagnosis.get('status') == 'localized' and (diagnosis.get('top') or {}).get('name') in ('unit_scale', 'truncated_pagination')
    tiers = [
        {'id': 'T0', 'action': 'deterministic_retry', 'eligible': False, 'estimated_model_calls': 0,
         'reason': 'A repeat cannot resolve a reproducible semantic contradiction; retry only after fresh source evidence.'},
        {'id': 'T1', 'action': 'localized_repair', 'eligible': bool(local and not unknown), 'estimated_model_calls': 0,
         'reason': 'Allowlisted deterministic patch, isolated regression validation and snapshot-safe downstream replay.'},
        {'id': 'T2', 'action': 'model_localized_repair', 'eligible': bool(local and not unknown and model_available), 'estimated_model_calls': 1,
         'reason': 'Nemotron may propose the same bounded parameter change; validation still decides.'},
        {'id': 'T3', 'action': 'full_regeneration', 'eligible': False, 'estimated_model_calls': 1,
         'reason': 'Missing independent evidence cannot be repaired by more reasoning. Full regeneration is benchmarked; manual reset/recompile is separate.'},
        {'id': 'T4', 'action': 'safe_halt_human_review', 'eligible': True, 'estimated_model_calls': 0,
         'reason': 'Required evidence is UNKNOWN or no safe supported patch is available.'}
    ]
    recommended = 'T1' if local and not unknown else 'T4'
    return {'recommended': recommended, 'tiers': tiers,
            'objective': 'Minimize supported safe recovery cost; never pay for reasoning as a substitute for independent evidence.',
            'cost_basis': 'model-call estimates; actual validation/runtime latency is recorded per run; human cost is unpriced'}
