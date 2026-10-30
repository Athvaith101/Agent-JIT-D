"""AAIR safety and incremental-execution tests; synthetic authority is explicit."""
import copy
from pathlib import Path
import pytest

from jitd.assumptions import closure, verify
from jitd.compiler import compile_workflow
from jitd.executor import Executor
from jitd.fixtures import make_truth
from jitd.lab import Lab
from jitd.recovery import recover
from jitd.services import MockServices


@pytest.fixture(scope='module')
def manifest():
    return compile_workflow()[0]


def test_registry_is_explicit_and_starts_unknown(manifest):
    assert {a['id'] for a in manifest.assumptions} == {'invoice-unit', 'payment-unit', 'pagination', 'business-reconciliation'}
    assert all(a['status'] == 'UNKNOWN' and a['verified_at'] is None for a in manifest.assumptions)
    a = next(a for a in manifest.assumptions if a['id'] == 'payment-unit')
    assert a['consumers'] == ['normalize_amount', 'sum_payments', 'reconcile', 'post_ledger']


@pytest.mark.parametrize('mode',['missing','correlated'])
def test_missing_or_same_source_evidence_never_posts(manifest, mode):
    t = make_truth('strict',0)
    svc = MockServices([t]);svc.evidence_mode=mode
    r = Executor(svc,strict=True).run(manifest,{'invoice_id':t.invoice_id,'as_of':'2026-09-30T00:00:00Z'})
    assert r.outcome == 'halted' and svc.calls['ledger.post'] == 0
    assert r.halt['reason'] == 'assumption_unknown'
    assert any(a['status'] == 'UNKNOWN' for a in r.assumptions)


def test_correlated_numeric_drift_requires_independent_authority(manifest):
    t = make_truth('correlated',3)
    svc = MockServices([t],'consistent_scale')
    r = Executor(svc,strict=True).run(manifest,{'invoice_id':t.invoice_id,'as_of':'2026-10-16T00:00:00Z'})
    assert r.outcome != 'posted' and not svc.ledger
    assert next(a for a in r.assumptions if a['id']=='invoice-unit')['status']=='INVALID'
    assert next(a for a in r.assumptions if a['id']=='business-reconciliation')['status']=='VALID'


def repair_episode(tmp_path):
    lab = Lab(tmp_path);lab.inject('unit_cents')
    r = lab.run();assert r['outcome']=='halted'
    old = lab.manifest.clone();prior=lab.get_run(r['run_id'])['result']
    lab.diagnose(r['run_id']);assert lab.repair(r['run_id'])['accepted']
    return lab,old,prior


def test_local_recovery_reuses_only_safe_snapshot_and_verifies_output(tmp_path):
    lab,old,prior = repair_episode(tmp_path)
    r = recover(old,lab.manifest,prior,lab.services)
    assert r.outcome=='posted' and r.recovery['accepted_output']
    assert r.recovery['reused_nodes']==['fetch_invoice','fetch_payments','expected_total','classify_status']
    assert r.recovery['executed_nodes']==['normalize_amount','sum_payments','reconcile','post_ledger']
    assert all(a['status']=='VALID' and a['verified_at'] for a in r.assumptions)
    full=Executor(lab.services,strict=True).run(lab.manifest,prior.inputs)
    assert full.posted_entry()==r.posted_entry()


def test_snapshot_change_discards_all_checkpoints(tmp_path):
    lab,old,prior=repair_episode(tmp_path)
    lab.services.evidence_mode='missing'
    r=recover(old,lab.manifest,prior,lab.services)
    assert r.recovery['reused_nodes']==[] and not r.recovery['snapshot_matched']
    assert r.outcome=='halted' and not r.recovery['accepted_output']


def test_tampered_checkpoint_is_not_reused(tmp_path):
    lab,old,prior=repair_episode(tmp_path)
    prior.values['fetch_invoice']['total']=1
    r=recover(old,lab.manifest,prior,lab.services)
    assert 'fetch_invoice' not in r.recovery['reused_nodes']
    assert any('hash mismatch' in reason for reason in r.recovery['fallback_reasons'])
    assert r.outcome=='posted' and r.recovery['accepted_output']


def test_changed_contracts_prevent_checkpoint_reuse(tmp_path):
    lab,old,prior=repair_episode(tmp_path)
    lab.manifest.contracts[0]['tol']='0.001'
    r=recover(old,lab.manifest,prior,lab.services)
    assert not r.recovery['reused_nodes']
    assert any('verification policy changed' in reason for reason in r.recovery['fallback_reasons'])


def test_unsupported_assumption_remains_unknown(manifest):
    m=manifest.clone()
    m.assumptions.append({'id':'date-filter-inclusive','node':'fetch_invoice','required':True,'status':'UNKNOWN',
                          'semantic_contract':'date filter is inclusive','evidence_source':'not_implemented','consumers':['fetch_invoice']})
    t=make_truth('dates',0);svc=MockServices([t])
    r=Executor(svc,strict=True).run(m,{'invoice_id':t.invoice_id,'as_of':'2026-09-30T00:00:00Z'})
    assert r.outcome=='halted' and not svc.ledger
    assert next(a for a in r.assumptions if a['id']=='date-filter-inclusive')['status']=='UNKNOWN'


def test_aair_recovery_persists_across_restart(tmp_path):
    lab,old,prior=repair_episode(tmp_path)
    reloaded=Lab(tmp_path)
    r=reloaded.run(invoice_id=prior.inputs['invoice_id'])
    assert r['recovery']['accepted_output'] and len(r['recovery']['reused_nodes'])==4
    r2=Lab(tmp_path).get_run(r['run_id'])
    assert r2['result'].recovery['accepted_output']


def test_cost_without_complete_prices_is_not_zero(monkeypatch):
    from jitd.meter import ModelMeter
    m=ModelMeter();m.record_runtime('execution',100)
    for k in ('JITD_RUNTIME_USD_PER_MS','JITD_PRICE_INPUT_USD_PER_M','JITD_PRICE_OUTPUT_USD_PER_M'):
        monkeypatch.delenv(k,raising=False)
    assert m.cost_summary(1)['cost_per_correct_usd'] is None
    monkeypatch.setenv('JITD_RUNTIME_USD_PER_MS','0.01')
    assert m.cost_summary(1)['cost_per_correct_usd']==1
    assert m.cost_summary(0)['cost_per_correct_usd'] is None
    m.record('compile',30,input_tokens=20,output_tokens=10)
    assert m.cost_summary(1)['cost_per_correct_usd'] is None


def test_short_benchmark_contains_post_drift_runs_and_no_false_victory():
    from jitd.aair_bench import workload
    runs,onset=workload('unit_cents',0,12)
    assert len(runs)==12 and sum(r.post for r in runs)==9 and onset==3
    assert runs[-1].behavior=='unit_cents'


def test_snapshot_race_at_executor_entry_prevents_reuse(tmp_path):
    lab,old,prior=repair_episode(tmp_path)
    original=lab.services.snapshot_token
    calls=[]
    def changing(invoice_id):
        calls.append(invoice_id)
        return original(invoice_id) if len(calls)==1 else 'different-snapshot'
    lab.services.snapshot_token=changing
    r=recover(old,lab.manifest,prior,lab.services)
    assert not r.recovery['reused_nodes']
    assert any('executor entry' in why for why in r.recovery['fallback_reasons'])


def test_aair_benchmark_really_recovers_and_counts_all_cost_stages(monkeypatch):
    import jitd.aair_bench as b
    monkeypatch.setattr(b,'SCENARIOS',['unit_cents','missing_evidence'])
    monkeypatch.setattr(b,'STRATEGIES',['cached_execution','full_regeneration','data_dependency_replay','aair'])
    d=b.benchmark(seeds=1,n_runs=12)
    cells={(c['scenario'],c['strategy']):c for c in d['cells']}
    fast=cells[('unit_cents','aair')]
    assert fast['correct_outputs']==12 and fast['silent_errors']==0 and fast['reused_nodes']==4
    assert cells[('unit_cents','cached_execution')]['silent_errors']==9
    assert cells[('unit_cents','full_regeneration')]['correct_outputs']==12
    assert cells[('unit_cents','data_dependency_replay')]['reused_nodes']==4
    assert fast['compilation_ms']>0 and fast['recovery_ms']>0 and fast['verification_ms']>0
    assert cells[('missing_evidence','aair')]['safe_halts']==9
    assert d['meta']['caveats']


def test_independent_evidence_can_resolve_magnitude_alert_but_not_business_failure(manifest):
    t=make_truth('whale',0,big=True)
    legacy=Executor(MockServices([t])).run(manifest,{'invoice_id':t.invoice_id,'as_of':'2026-09-30T00:00:00Z'})
    strict=Executor(MockServices([t]),strict=True).run(manifest,legacy.inputs)
    assert legacy.outcome=='held' and strict.outcome=='posted'
    assert all(a['status']=='VALID' for a in strict.assumptions)
    assert any(c.get('resolution') for c in strict.contract_results)
    bad=make_truth('short-whale',0,big=True,short=True)
    blocked=Executor(MockServices([bad]),strict=True).run(manifest,{'invoice_id':bad.invoice_id,'as_of':'2026-09-30T00:00:00Z'})
    assert blocked.outcome=='halted'


def test_stale_authority_evidence_is_unknown(manifest):
    class Stale(MockServices):
        def verification_evidence(self, invoice):
            proof=super().verification_evidence(invoice)
            for key in ('billing_authority','settlement_authority'):
                proof[key]['observed_at']='2020-01-01T00:00:00Z'
            return proof
    t=make_truth('staleproof',0);svc=Stale([t])
    r=Executor(svc,strict=True).run(manifest,{'invoice_id':t.invoice_id,'as_of':'2026-09-30T00:00:00Z'})
    assert r.outcome=='halted' and not svc.ledger
    assert r.halt['reason']=='assumption_unknown'


def test_same_numeric_invoice_with_wrong_currency_is_not_valid(manifest):
    class CurrencyDrift(MockServices):
        def invoice_get(self, invoice):
            raw=super().invoice_get(invoice);raw['currency']='EUR';return raw
    t=make_truth('wrongcurrency',0);svc=CurrencyDrift([t])
    r=Executor(svc,strict=True).run(manifest,{'invoice_id':t.invoice_id,'as_of':'2026-09-30T00:00:00Z'})
    assert r.outcome=='halted' and not svc.ledger
    assert next(a for a in r.assumptions if a['id']=='invoice-unit')['status']=='INVALID'
