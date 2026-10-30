"""Assumption-aware recovery with content-checked snapshot reuse and independent output verification."""
import copy
from .assumptions import closure
from .executor import Executor, digest
from .manifest import validate_manifest


def plan(old, candidate, prior, services, *, semantic=True):
    if validate_manifest(candidate):
        raise ValueError('candidate manifest is invalid')
    if prior.outcome not in ('halted', 'held'):
        raise ValueError('only blocked runs can supply recovery checkpoints')
    old_steps = {s.id: s for s in old.steps}
    changed = [s.id for s in candidate.steps if s.id not in old_steps or s.model_dump() != old_steps[s.id].model_dump()]
    invalid = {a['id'] for a in prior.assumptions if a['status'] != 'VALID' and a.get('required')} if semantic else set()
    roots = set(changed)
    for a in candidate.assumptions:
        if a['id'] in invalid:
            # Raw acquisitions remain immutable evidence. A changed conversion invalidates its consumers,
            # not the already captured provider bytes. Other semantic faults invalidate their own region.
            if a['id'] != 'payment-unit' or not changed:
                roots.add(a['node'])
    affected = set(closure(candidate, roots))
    # A sink is never checkpointed, including idempotent sinks.
    affected.update(s.id for s in candidate.steps if s.kind == 'sink')
    snapshot = getattr(services, 'snapshot_token', None)
    try:
        same_snapshot = bool(prior.snapshot_token and snapshot and snapshot(prior.inputs['invoice_id']) == prior.snapshot_token)
    except Exception:
        same_snapshot = False
    old_results = {s['id']: s for s in prior.steps}
    reusable = {}
    reasons = []
    if same_snapshot:
        for s in candidate.steps:
            prev = old_results.get(s.id)
            if s.id in affected or not prev or prev['status'] != 'passed' or s.id not in prior.values:
                continue
            if any(not c['ok'] for c in prior.contract_results if c['step'] == s.id):
                continue
            if digest(prior.values[s.id]) != prev['output_hash']:
                reasons.append(s.id + ': checkpoint content hash mismatch')
                continue
            if old_steps.get(s.id) is None or old_steps[s.id].model_dump() != s.model_dump():
                continue
            # A value can be reused only if all of its data dependencies are reusable too.
            if any(dep not in reusable for dep in candidate.deps()[s.id]):
                continue
            reusable[s.id] = copy.deepcopy(prior.values[s.id])
    else:
        reasons.append('immutable provider snapshot unavailable or changed: full reread required')
    # Changed contracts/assumptions can invalidate a retained value even if data wiring did not change.
    if old.contracts != candidate.contracts or old.assumptions != candidate.assumptions:
        reusable = {}
        reasons.append('verification policy changed: discard every checkpoint')
    report = {'method': 'AAIR' if semantic else 'data_dependency_replay', 'source_run': prior.run_id, 'from_version': old.version,
              'to_version': candidate.version, 'changed_nodes': changed, 'invalid_assumptions': sorted(invalid),
              'invalidated_nodes': [s.id for s in candidate.steps if s.id in affected],
              'reused_nodes': list(reusable), 'executed_nodes': [s.id for s in candidate.steps if s.id not in reusable],
              'expected_snapshot_token': prior.snapshot_token, 'snapshot_matched': same_snapshot, 'fallback_reasons': reasons,
              'checkpoint_rule': 'same inputs and immutable source snapshot; unchanged code, params and verification policy; content hash matches; never reuse a sink'}
    return report, reusable


def recover(old, candidate, prior, services, meter=None, emit=None, *, semantic=True):
    report, reuse = plan(old, candidate, prior, services, semantic=semantic)
    if emit:
        emit({'type': 'recovery_planned', 'recovery': report})
    result = Executor(services, meter, emit, strict=True).run(candidate, prior.inputs, reuse=reuse, recovery=report)
    report['executed_nodes'] = [s['id'] for s in result.steps if s['status'] != 'skipped' and not s.get('reused')]
    report['reverified'] = bool(result.assumptions) and all(a['status'] == 'VALID' for a in result.assumptions if a.get('required'))
    report['accepted_output'] = result.outcome == 'posted' and report['reverified']
    return result
