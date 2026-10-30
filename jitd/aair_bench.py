"""Matched AAIR benchmark. Provider data is synthetic; agent token/cost assumptions are explicit.
Run: python -m jitd.aair_bench --seeds 5 --runs 40
No API calls are made here. Use jitd.live for actual Nemotron evidence.
"""
import argparse
import json
import time
from datetime import datetime, timezone
from dataclasses import replace
from pathlib import Path

from .bench import ASSUMPTIONS, code_version, golden_regression, agent_call_cost
from .compiler import compile_workflow
from .diagnosis import diagnose
from .executor import Executor
from .manifest import Manifest
from .oracle import entry_matches
from .recovery import recover
from .repair import attempt_repair
from .scenarios import build_stream
from .services import MockServices

STRATEGIES = ['repeated_reasoning_modelled', 'cached_execution', 'ordinary_validation', 'full_regeneration', 'data_dependency_replay', 'fixed_audit_10', 'aair']
SCENARIOS = ['clean', 'cosmetic', 'big_invoice', 'malformed', 'unit_cents', 'unit_mills', 'truncation', 'compound', 'underpayment', 'consistent_scale', 'missing_evidence', 'correlated_evidence']


def workload(base, seed, n_runs):
    full, original_onset = build_stream(base, seed, max(120, n_runs))
    if n_runs >= 120:
        return full, original_onset
    warmup = max(3, n_runs//4)
    selected = full[:warmup] + full[original_onset:original_onset+n_runs-warmup]
    return [replace(r, index=i) for i, r in enumerate(selected)], warmup


def benchmark(seeds=5, n_runs=40, cpu_usd_per_ms=.00000001):
    rows, traces = [], []
    # Every stream pays an attributable initial compilation. Each strategy receives the same workload.
    for scenario in SCENARIOS:
        base = 'clean' if scenario == 'missing_evidence' else 'consistent_scale' if scenario == 'correlated_evidence' else scenario
        for strategy in STRATEGIES:
            totals = dict(runs=0, correct_outputs=0, silent_errors=0, safe_halts=0, false_blocks=0,
                          compilation_ms=0., execution_ms=0., verification_ms=0., recovery_ms=0.,
                          modelled_calls=0, measured_model_calls=0, measured_tokens=0, reused_nodes=0,
                          executed_nodes=0, invalidated_nodes=0, repairs=0, detection_delay_runs=[])
            for seed in range(seeds):
                start = time.perf_counter()
                manifest, _ = compile_workflow()
                if strategy != 'repeated_reasoning_modelled':
                    totals['compilation_ms'] += (time.perf_counter()-start)*1000
                if strategy != 'repeated_reasoning_modelled':
                    totals['modelled_calls'] += 1  # assumed initial discovery, not an API measurement
                regression = golden_regression()
                runs, onset = workload(base, seed, n_runs)
                svc = MockServices([r.truth for r in runs])
                first_detected = False
                for run in runs:
                    totals['runs'] += 1
                    svc.set_behavior(run.behavior)
                    svc.evidence_mode = 'missing' if scenario == 'missing_evidence' and run.post else 'correlated' if scenario == 'correlated_evidence' and run.post else 'independent'
                    start = time.perf_counter()
                    if strategy == 'repeated_reasoning_modelled':
                        totals['modelled_calls'] += 1
                        # Deliberately optimistic upper baseline: an oracle-correct agent, explicitly modelled.
                        correct, silent, blocked, used = run.expected is not None, False, run.expected is None, None
                    else:
                        strict = strategy in ('aair', 'full_regeneration', 'data_dependency_replay') or strategy == 'fixed_audit_10' and run.index % 10 == 0
                        contracts = strategy != 'cached_execution' and (strategy != 'fixed_audit_10' or strict)
                        used = Executor(svc, strict=strict, contracts_enabled=contracts).run(manifest, {'invoice_id': run.truth.invoice_id, 'as_of': run.as_of})
                        detected = used.outcome in ('halted', 'held')
                        ms = (time.perf_counter()-start)*1000
                        totals['execution_ms'] += max(0, ms-used.verification_ms)
                        totals['verification_ms'] += used.verification_ms
                        if strategy in ('aair', 'full_regeneration', 'data_dependency_replay') and used.outcome in ('halted', 'held'):
                            timer = time.perf_counter()
                            d = diagnose(manifest, used)
                            rep = attempt_repair(manifest, d, svc, [(run.truth.invoice_id, run.as_of, run.expected)], regression, isolated=False)
                            if rep['accepted']:
                                old = manifest
                                candidate = Manifest.model_validate(rep['candidate'])
                                if strategy == 'full_regeneration':
                                    # Rebuild the entire typed plan and mined contracts, transplant the validated patch,
                                    # and rerun every node. A real model discovery call is modelled, not made here.
                                    rebuilt, _ = compile_workflow()
                                    for step in rebuilt.steps:
                                        step.params = candidate.step_for_op(step.operation).params
                                    rebuilt.version = candidate.version
                                    candidate = rebuilt
                                    totals['modelled_calls'] += 1
                                    used = Executor(svc, strict=True).run(candidate, used.inputs)
                                else:
                                    used = recover(old, candidate, used, svc, semantic=strategy != 'data_dependency_replay')
                                    if strategy == 'data_dependency_replay':
                                        used.recovery['method'] = 'ordinary data-dependency replay' 
                                manifest = candidate
                                totals['repairs'] += 1
                            totals['recovery_ms'] += (time.perf_counter()-timer)*1000
                        correct = used.outcome == 'posted' and entry_matches(used.posted_entry(), run.expected)
                        silent = used.outcome == 'posted' and not correct
                        blocked = used.outcome != 'posted'
                        totals['reused_nodes'] += sum(bool(s.get('reused')) for s in used.steps)
                        totals['executed_nodes'] += sum(s['status'] != 'skipped' and not s.get('reused') for s in used.steps)
                        totals['invalidated_nodes'] += len((used.recovery or {}).get('invalidated_nodes', []))
                        if run.post and not first_detected and detected:
                            totals['detection_delay_runs'].append(run.index-onset)
                            first_detected = True
                    totals['correct_outputs'] += int(correct)
                    totals['silent_errors'] += int(silent)
                    totals['safe_halts'] += int(blocked)
                    if blocked and run.expected is not None:
                        # Matched naive correctness, rather than labelling every interrupted drift a false alarm.
                        naive = Executor(MockServices([run.truth], run.behavior), contracts_enabled=False).run(manifest, {'invoice_id': run.truth.invoice_id, 'as_of': run.as_of})
                        totals['false_blocks'] += int(naive.outcome == 'posted' and entry_matches(naive.posted_entry(), run.expected))
                    traces.append({'scenario': scenario, 'strategy': strategy, 'seed': seed, 'idx': run.index,
                                   'post': run.post, 'correct': correct, 'silent': silent, 'safe_halt': blocked,
                                   'recovery': used.recovery if used else None})
            total_ms = sum(totals[k] for k in ('compilation_ms','execution_ms','verification_ms','recovery_ms'))
            modelled_model_cost = agent_call_cost(totals['modelled_calls'])
            estimated_runtime_cost = total_ms*cpu_usd_per_ms
            totals.update(estimated_planning_usd=modelled_model_cost, estimated_runtime_usd=estimated_runtime_cost,
                          estimated_total_usd=modelled_model_cost+estimated_runtime_cost,
                          cost_per_correct_workflow=(modelled_model_cost+estimated_runtime_cost)/totals['correct_outputs'] if totals['correct_outputs'] else None,
                          safe_halt_rate=totals['safe_halts']/totals['runs'], silent_error_rate=totals['silent_errors']/totals['runs'],
                          modelled_tokens=totals['modelled_calls']*(ASSUMPTIONS['agent_tokens_in']+ASSUMPTIONS['agent_tokens_out']))
            rows.append({'scenario': scenario, 'strategy': strategy, **totals})
        print('  evaluated', scenario, flush=True)
    return {'meta': {'kind': 'aair_benchmark/1', 'created_utc': datetime.now(timezone.utc).isoformat(), 'code_version': code_version(),
                     'seeds': seeds, 'runs': n_runs, 'strategies': STRATEGIES, 'cpu_usd_per_ms': cpu_usd_per_ms,
                     'assumptions': ASSUMPTIONS, 'metric': 'All attributable planning, compilation, execution, verification and recovery costs / oracle-correct completed outputs. Zero outputs => undefined, never zero.',
                     'caveats': ['All services and authority evidence are synthetic; authority and oracle share fixture truth, so this is a mechanism test, not independent field validation.',
                                 'Repeated reasoning is an assumed-correct modelled baseline. No real Nemotron token/cost claim is made.',
                                 'Full regeneration rebuilds the deterministic compiler and uses the same validated bounded patch; its discovery call cost is modelled.',
                                 'Runtime and verification latency are measured; USD uses assumed CPU and token rates, not provider billing.',
                                 'The data-dependency replay ablation uses identical independent verification and patching. Its slice can equal AAIR on this eight-step workflow; no semantic-slicing superiority is assumed.',
                                 'AAIR can lose on small workflows because verification, snapshot hashing and checkpoint bookkeeping have overhead.',
                                 'Fixed auditing deliberately allows unaudited outputs: safety is shown alongside cost.',
                                 'Missing evidence requires a safe halt even when the fixture oracle would have accepted the invoice.']},
            'cells': rows, 'trials': traces}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', type=int, default=5)
    ap.add_argument('--runs', type=int, default=40)
    ap.add_argument('--out', default='benchmark/aair')
    a = ap.parse_args()
    if a.seeds < 1 or a.runs < 12:
        ap.error('use seeds >= 1 and runs >= 12')
    result = benchmark(a.seeds, a.runs)
    path = Path(a.out)
    path.mkdir(parents=True, exist_ok=True)
    dest = path / ('aair_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json')
    dest.write_text(json.dumps(result, separators=(',', ':')), encoding='utf-8')
    print('wrote', dest)


if __name__ == '__main__':
    main()
