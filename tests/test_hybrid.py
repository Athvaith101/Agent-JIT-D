import math
import pytest
from jitd.hybrid import Monitor,Policy,rank_causes,robust_score,route
from jitd.canvas import CanvasStore,RunInput,default_graph,example
from jitd.platform import allowed


def obs(m,i,**kwargs):
    body=dict(signals={'latency':10.0},label=False,label_basis='test predicate truth',verified=True,unknown=False,known_local=False,ambiguous=False,causes=[],predicates={'compute':False})
    body.update(kwargs)
    return m.observe(str(i),'workflow:version1',**body)


def test_frozen_baseline_cusum_and_restart(tmp_path):
    m=Monitor(tmp_path)
    for i in range(8):obs(m,i,signals={'latency':10+(i%2)*.1})
    a=obs(m,8,signals={'latency':20},label=True,verified=False,ambiguous=True)
    assert a['alarm'] and a['signals'][0]['baseline_count']==8
    assert Monitor(tmp_path).get('8')==a
    b=obs(m,9,signals={'latency':10.05})
    assert b['signals'][0]['baseline_count']==8
    assert b['reliability']=={'alpha':2,'beta':10,'verified':10,'mean':2/12,'prior':'Beta(1,1)','warning':'No IID, stationarity or calibrated silent-error bound is claimed.'}


def test_unknowns_do_not_train_and_no_duplicate_labels(tmp_path):
    m=Monitor(tmp_path)
    r=obs(m,'unknown',label=None,verified=False,unknown=True,predicates={})
    assert r['reliability']['verified']==0 and r['route']['action']=='block_missing_evidence'
    for i in range(3):obs(m,'same')
    assert m.overview()['states'][0]['verified']==1
    assert m.overview()['states'][0]['steps']['compute']['verified']==1
    obs(m,'nan',signals={'bad':math.nan,'infinite':math.inf,'bool':True})
    assert m.get('nan')['signals']==[]
    with pytest.raises(ValueError):obs(m,'bad',label=1)


def test_unknown_missing_and_known_local_never_call():
    p=Policy(enabled=True,minimum_verified=0,residual_probability=0)
    args=dict(beta={'alpha':10,'beta':1,'verified':10},verified=False,unknown=False,known_local=False,ambiguous=True,alarm=True,model_ready=True,budget_remaining=10)
    assert route(p,**args)['action']=='model_diagnosis'
    assert route(p,**{**args,'unknown':True})['action']=='block_missing_evidence'
    assert route(p,**{**args,'known_local':True})['action']=='propose_local_repair'
    assert route(p,**{**args,'verified':True,'ambiguous':False,'alarm':False})['action']=='accept_verified_fast_path'
    for change in ({'model_ready':False},{'budget_remaining':0},{'ambiguous':False}):assert not route(p,**{**args,**change})['model_eligible']
    assert not route(Policy(enabled=False),**args)['model_eligible']
    assert not route(Policy(enabled=True,model_cost_usd=1000),**args)['model_eligible']


def test_graph_ranks_upstream_before_symptom():
    rows=rank_causes(['fetch','normalize','output'],{'normalize':['fetch'],'output':['normalize']},['normalize','output'])
    assert [r['step'] for r in rows]==['normalize','output']
    assert rows[0]['upstream_inputs_failed']==[]


def test_regime_reset_and_dispatch_claim(tmp_path):
    m=Monitor(tmp_path);a=obs(m,1);p=m.policy()
    assert m.claim('1',p,a['regime_id'])
    assert not m.claim('1',p,a['regime_id'])
    m.complete('1',{'receipt_id':'test'})
    assert Monitor(tmp_path).dispatch('1')['result']['receipt_id']=='test'
    m.configure(p,'admin')
    assert m.generation()!=a['regime_id'] and m.overview()['states']==[]
    assert not m.claim('2',p,a['regime_id'])
    assert m.get('1')==a


def test_canvas_hooks(tmp_path):
    s=CanvasStore(tmp_path);r=s.test(default_graph('inventory_reconciliation'),'builder');v=s.publish(r['id'],'reviewer',True)
    good=s.run(v['id'],RunInput(**example('inventory_reconciliation')),'operator')
    assert good['hybrid']['run_id']==good['id']
    assert good['hybrid']['route']['action']=='accept_verified_fast_path'
    bad=s.run(v['id'],RunInput(**example('inventory_reconciliation','drift')),'operator')
    assert bad['hybrid']['label']['predicate_violation'] is True
    unknown=s.run(v['id'],RunInput(**example('inventory_reconciliation','missing')),'operator')
    assert unknown['hybrid']['label']['predicate_violation'] is None
    assert unknown['hybrid']['route']['action']=='block_missing_evidence'


def test_hybrid_roles():
    assert not allowed('viewer','POST','/api/hybrid/policy')
    assert not allowed('reviewer','POST','/api/hybrid/runs/a/assist')
    assert allowed('operator','POST','/api/hybrid/runs/a/assist')


def test_actual_gated_dispatch_once_and_no_learning_from_model(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from jitd import server,canvas_api,hybrid_api
    from jitd.lab import Lab
    monkeypatch.setattr(server,'LAB',Lab(tmp_path));monkeypatch.setenv('JITD_DATA_DIR',str(tmp_path));monkeypatch.setenv('JITD_BUDGET_DB',str(tmp_path/'platform.sqlite3'));monkeypatch.setenv('JITD_MAX_MODEL_CALLS','10')
    canvas_api._credentials['primary']={'model':'fake','key':'fake-secret','provider':'nebius','input_rate':'1','output_rate':'1'}
    calls=[]
    def fake(*args):
        calls.append(args)
        return {'raw_output':'{"suspect_step":"normalize","explanation":"Inspect the failed count invariant."}','usage':[],'calculated_usd':None,'source':'injected_test_client'}
    monkeypatch.setattr(hybrid_api,'measured',fake)
    with TestClient(server.app) as client:
        p=Policy(enabled=True,minimum_verified=0,residual_probability=0)
        assert client.post('/api/hybrid/policy',json=p.model_dump()).status_code==200
        s=CanvasStore(tmp_path);r=s.test(default_graph('inventory_reconciliation'),'builder');v=s.publish(r['id'],'reviewer',True)
        good=s.run(v['id'],RunInput(**example('inventory_reconciliation')),'operator')
        assert not client.post('/api/hybrid/runs/'+good['id']+'/assist').json()['dispatched']
        bad=s.run(v['id'],RunInput(**example('inventory_reconciliation','drift')),'operator')
        before=Monitor(tmp_path).get(bad['id'])['reliability']
        response=client.post('/api/hybrid/runs/'+bad['id']+'/assist').json()
        assert response['dispatched'] and response['model_result_accepted_as_advice'] and not response['acceptance_authorized']
        assert not client.post('/api/hybrid/runs/'+bad['id']+'/assist').json()['dispatched']
        assert len(calls)==1 and Monitor(tmp_path).get(bad['id'])['reliability']==before
        auto=client.post('/api/canvas/versions/'+v['id']+'/executions?auto_assist=true',json=example('inventory_reconciliation','drift')).json()
        assert auto['result']['outcome']=='blocked' and auto['hybrid_assistance']['dispatched']
        stable=client.post('/api/canvas/versions/'+v['id']+'/executions?auto_assist=true',json=example('inventory_reconciliation')).json()
        assert not stable['hybrid_assistance']['dispatched'] and len(calls)==2
        stale=s.run(v['id'],RunInput(**example('inventory_reconciliation','drift')),'operator')
        client.post('/api/hybrid/policy',json=p.model_dump())
        assert client.get('/api/hybrid/runs/'+stale['id']).json()['dispatch_decision']['action']=='new_run_required'
        assert not client.post('/api/hybrid/runs/'+stale['id']+'/assist').json()['dispatched']
    canvas_api._credentials.clear()


def test_studio_hard_failure_localizes_and_missing_stays_unknown(tmp_path):
    from jitd.studio import Studio,DraftInput
    s=Studio(tmp_path);d=s.create(DraftInput(name='Hybrid invoice',task='Reconcile invoices and payments.'),'builder');r=s.test(d['id'],1,'builder');v=s.publish(d['id'],1,r['id'],'reviewer',True)
    clean=s.execute(v['id'],None,'operator');assert clean['hybrid']['route']['action']=='accept_verified_fast_path'
    s.configure_run(v['id'],'unit_cents','independent','operator');bad=s.execute(v['id'],None,'operator')
    assert bad['hybrid']['route']['action']=='propose_local_repair'
    assert bad['passport']['hybrid_report_hash']
    s.configure_run(v['id'],'clean','missing','operator');unknown=s.execute(v['id'],None,'operator')
    assert unknown['hybrid']['route']['action']=='block_missing_evidence'
