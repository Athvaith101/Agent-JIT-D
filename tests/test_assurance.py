import pytest
from jitd.assurance import Check, plan_checks, report


def test_all_obligations_required():
    checks=[Check('currency',frozenset(['currency']),1),Check('freshness',frozenset(['freshness']),2)]
    p=plan_checks(['currency','freshness'],checks,1)
    assert not p['coverage_complete'] and p['uncovered_obligations']==['freshness']
    assert not p['acceptance_authorized']


def test_exact_shared_cover_and_budget():
    checks=[Check('a',frozenset(['a']),2),Check('b',frozenset(['b']),2),Check('both',frozenset(['a','b']),3)]
    assert plan_checks(['a','b'],checks,3)['selected_checks']==['both']
    assert not plan_checks(['a','b'],checks,2)['coverage_complete']
    assert plan_checks(['a','b'],checks,2)['estimated_cost_units']<=2


@pytest.mark.parametrize('budget',[-1,True,1.5,1000001])
def test_invalid_budget(budget):
    with pytest.raises(ValueError):plan_checks([],[],budget)


def test_missing_verifier_and_free_check():
    assert not plan_checks(['unknown'],[],10)['coverage_complete']
    assert plan_checks(['a'],[Check('free',frozenset(['a']),0)],0)['coverage_complete']


def test_no_stale_evidence_reuse():
    run={'assumptions':[{'id':'amount','required':True,'status':'VALID','evidence_source':'authority','consumers':['normalize','post']}]}
    r=report(run,0,['authority'])
    assert r['affected_nodes']==['normalize','post'] and r['reused_evidence']==[]
    assert not r['plan']['coverage_complete'] and not r['plan']['acceptance_authorized']
    assert report(run,1)['plan']['coverage_complete']


def test_registry_bounds():
    with pytest.raises(ValueError):plan_checks([], [Check('a',frozenset(),1)]*2,1)
    with pytest.raises(ValueError):plan_checks([], [Check(str(n),frozenset(),1) for n in range(17)],1)
    with pytest.raises(ValueError):plan_checks([], [Check('a',frozenset(),-1)],1)


def test_studio_http_assurance(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from jitd import server
    from jitd.lab import Lab
    from jitd.studio_api import get_studio
    from jitd.studio import DraftInput
    monkeypatch.setattr(server,'LAB',Lab(tmp_path))
    s=get_studio(); d=s.create(DraftInput(name='Assurance agent',task='Reconcile invoices and payments against independent evidence.'),'builder')
    r=s.test(d['id'],1,'builder');v=s.publish(d['id'],1,r['id'],'reviewer',True)
    run=s.execute(v['id'],None,'operator')
    with TestClient(server.app) as client:
        response=client.get('/api/studio/runs/'+run['id']+'/assurance?budget=0&changed_source=provider')
        assert response.status_code==200
        value=response.json()
        assert value['mode']=='shadow_only' and value['plan']['uncovered_obligations']
        assert not value['plan']['acceptance_authorized']
        assert client.get('/api/studio/runs/'+run['id']+'/assurance?budget=-1').status_code==422
