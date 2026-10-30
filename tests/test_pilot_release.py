import copy
import json
from datetime import datetime,timezone,timedelta
import pytest
from fastapi.testclient import TestClient
from jitd import server
from jitd.lab import Lab
from jitd.pilot import PilotStore,evaluate,bundle_evidence
from jitd.model_baseline import compare,gate_entry
from jitd.compiler import compile_workflow
from jitd.meter import ModelMeter
from scripts.create_pilot_demo import demo_bundle


def test_durable_missing_evidence_resolution_and_stale_review_conflict(tmp_path):
    b=demo_bundle();authority=b['authority'];b['authority']=None
    store=PilotStore(tmp_path);case=store.create(b)
    assert case['result']['outcome']!='posted'
    unchanged=store.resolve(case['id'],1,'operator','Review alone supplies no proof',2,None)
    assert unchanged['result']['outcome']!='posted'
    resolved=store.resolve(case['id'],2,'operator','Fetched independent observation',3,authority)
    assert resolved['result']['outcome']=='posted' and resolved['result']['external_writes']==0
    assert len(resolved['observations'])==3 and resolved['observations'][0]['authority'] is None
    assert PilotStore(tmp_path).get(case['id'])['revision']==3
    assert store.report()['reported_human_minutes']==5 and len(store.events())==3
    with pytest.raises(RuntimeError):store.resolve(case['id'],2,'op','stale',0,authority)


@pytest.mark.parametrize('fault',['wrong','stale','identity','nonindependent','snapshot'])
def test_review_never_overrides_bad_evidence(tmp_path,fault):
    b=demo_bundle()
    if fault=='wrong':b['authority']['settled_total_usd']='999999.00'
    if fault=='stale':b['authority']['observed_at']=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
    if fault=='identity':b['authority']['invoice_id']='other'
    if fault=='nonindependent':b['provenance']['independent_authority']=False
    if fault=='snapshot':b['authority']['provider_snapshot']='bad'
    store=PilotStore(tmp_path);case=store.create(b)
    r=store.resolve(case['id'],1,'reviewer','Approve anyway',0,None)
    assert r['result']['outcome']!='posted'


def test_model_baseline_measured_and_same_gate_rejects_wrong_model():
    b=demo_bundle();manifest,_=compile_workflow();entry=evaluate(b)['entry'];entry.pop('disposition')
    class Fake:
        def __init__(self,m):self.m=m
        def complete(self,*a,**kw):
            self.m.record('replay',12,input_tokens=10,output_tokens=2,model='fake',latency_ms=1)
            return json.dumps(entry)
    report=compare([b],lambda m:Fake(m))
    row=report['cases'][0]
    assert row['compiled']['shared_gate_passed'] and row['reasoning']['shared_gate_passed']
    assert row['reasoning']['meter']['total_model_calls']==1 and report['source_mode']=='injected_client'
    wrong=dict(entry,amount_usd='0.00')
    assert not gate_entry(b,bundle_evidence(b),wrong,manifest)
    b['authority']=None
    assert not compare([b],lambda m:Fake(m))['cases'][0]['reasoning']['shared_gate_passed']


def test_pilot_api_import_review_export_and_readiness(tmp_path,monkeypatch):
    monkeypatch.setattr(server,'LAB',Lab(tmp_path));server._hits.clear();c=TestClient(server.app)
    b=demo_bundle();authority=b['authority'];b['authority']=None
    response=c.post('/api/pilot/import',json=b);assert response.status_code==200,response.text
    row=response.json();payload={'revision':1,'reviewer':'reviewer','note':'Fresh observation supplied','human_minutes':1,'authority':authority}
    assert c.post('/api/pilot/'+row['id']+'/review',json=payload).json()['result']['outcome']=='posted'
    assert c.post('/api/pilot/'+row['id']+'/review',json=payload).status_code==409
    assert c.get('/api/pilot/export').json()['events']
    gates=c.get('/api/readiness').json();assert not gates['ready_to_claim_field_validation']
    assert next(g for g in gates['gates'] if g['id']=='novelty')['status']=='not_established'
    assert c.get('/api/pilot').json()['report']['declared_real_cases']==0


def test_hosted_auth_fails_closed_and_mutations_require_same_origin(monkeypatch):
    c=TestClient(server.app)
    monkeypatch.setenv('JITD_REQUIRE_AUTH','1');monkeypatch.delenv('JITD_ACCESS_TOKEN',raising=False)
    assert c.get('/api/health').status_code==200 and c.get('/api/state').status_code==503
    monkeypatch.setenv('JITD_ACCESS_TOKEN','local-demo-token')
    assert c.get('/').status_code==401
    assert c.get('/api/state',auth=('jitd','wrong')).status_code==401
    response=c.get('/api/state',auth=('jitd','local-demo-token'))
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    assert c.post('/api/workflow/pause',json={'paused':True},auth=('jitd','local-demo-token'),headers={'Origin':'https://evil.example'}).status_code==403


def test_import_rejects_credentials_and_invalid_page_count():
    b=demo_bundle();b['recording']['invoice']['api_key']='fake-secret'
    with pytest.raises(ValueError):evaluate(b)


def test_invalid_recording_returns_422_and_revision_is_unchanged(tmp_path,monkeypatch):
    monkeypatch.setattr(server,'LAB',Lab(tmp_path));server._hits.clear();c=TestClient(server.app)
    b=demo_bundle();b['recording']['invoice'].pop('total')
    assert c.post('/api/pilot/import',json=b).status_code==422
    assert c.get('/api/pilot').json()['report']['cases']==0


def test_baseline_failure_usage_is_retained_and_cannot_pass():
    class Broken:
        def __init__(self,m):self.m=m
        def complete(self,*args,**kwargs):
            self.m.record('replay',0,status='failed_usage_unknown')
            raise RuntimeError('network unavailable')
    report=compare([demo_bundle()],lambda m:Broken(m))
    assert report['cases'][0]['reasoning']['error']
    assert not report['cases'][0]['reasoning']['shared_gate_passed']
    assert report['cases'][0]['reasoning']['provider_usage'][0]['status']=='failed_usage_unknown'


def test_pending_gates_never_promote_fake_model_evidence(tmp_path):
    from jitd.readiness import readiness
    p=tmp_path/'evidence';p.mkdir()
    (p/'fake.json').write_text(json.dumps({'source_mode':'injected_client','kind':'jitd_live_evidence','finished_utc':'now','smoke':{'ok':True}}))
    r=readiness(tmp_path)
    assert next(g for g in r['gates'] if g['id']=='live_nemotron')['status']=='pending_external'
    assert not r['ready_to_claim_field_validation']


def test_http_capture_bundle_is_importable_and_bound_to_original_bytes(tmp_path):
    import httpx
    from jitd.http_connector import HTTPProvider,HTTPAuthority
    from jitd.shadow import shadow_run
    from jitd.fixtures import make_truth
    from jitd.services import MockServices
    t=make_truth('export',0);svc=MockServices([t])
    def handle(request):
        if request.url.host=='provider.test':
            value=svc.invoice_get(t.invoice_id) if request.url.path=='/invoice' else svc.payment_list(t.invoice_id)
            return httpx.Response(200,json=value,headers={'X-JITD-Snapshot':'v1'})
        row={'invoice_id':t.invoice_id,'source_id':'control','provider_snapshot':'v1','currency':'USD',
             'invoice_total_usd':str(t.total),'settled_total_usd':str(t.paid_total),'observed_at':datetime.now(timezone.utc).isoformat()}
        return httpx.Response(200,json=row)
    p=HTTPProvider('https://provider.test',transport=httpx.MockTransport(handle));a=HTTPAuthority('https://control.test',transport=httpx.MockTransport(handle))
    try:
        target=tmp_path/'case.json'
        result=shadow_run(p,a,t.invoice_id,'2026-09-30T00:00:00Z','control',export_case=target,author='test operator')
        assert result['outcome']=='posted'
        bundle=json.loads(target.read_text())
        assert evaluate(bundle)['outcome']=='posted' and bundle['authority']['provider_snapshot']=='v1'
        bundle['recording']['invoice']['total']='1.00'
        assert not bundle_evidence(bundle)
    finally:p.close();a.close()
