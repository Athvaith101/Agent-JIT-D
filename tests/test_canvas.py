import sqlite3
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from jitd.canvas import CanvasStore, FAMILIES, Node, RunInput, canonical, default_graph, example, execute, validate
from jitd.lab import Lab, LabError
from jitd import server, canvas_api
from jitd.platform import allowed

@pytest.mark.parametrize('family',list(FAMILIES))
def test_family_lifecycle_and_fresh_gate(tmp_path,family):
    store=CanvasStore(tmp_path);g=default_graph(family)
    r=store.test(g,'builder');assert r['passed'] and len(r['cases'])==3
    with pytest.raises(LabError):store.publish(r['id'],'builder',True)
    v=store.publish(r['id'],'reviewer',True)
    for mode,expected in [('clean','accepted_local'),('drift','blocked'),('missing','blocked')]:
        run=store.run(v['id'],RunInput(**example(family,mode)),'operator')
        assert run['result']['outcome']==expected and run['result']['model_calls']==0
    assert CanvasStore(tmp_path).get(v['id'])==v
    with store.db() as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute('UPDATE objects SET kind=?',('forged',))

@pytest.mark.parametrize('fault',['gate_removed','reorder','cycle','duplicate','branch','unknown_family'])
def test_graph_cannot_bypass_evidence(fault):
    g=default_graph('inventory_reconciliation')
    if fault=='gate_removed':g.nodes.pop(2)
    elif fault=='reorder':g.nodes[1],g.nodes[2]=g.nodes[2],g.nodes[1]
    elif fault=='cycle':g.edges.append(('output','source'))
    elif fault=='duplicate':g.nodes[1].id='source'
    elif fault=='branch':g.edges=[('source','verify'),('source','normalize'),('verify','output')]
    else:g.family='arbitrary_python'
    assert validate(g) and execute(g,RunInput(**example('inventory_reconciliation')))['outcome']=='blocked'

def test_optional_report_is_executed():
    g=default_graph('inventory_reconciliation');g.nodes.insert(3,Node(id='summary',kind='report'));ids=[n.id for n in g.nodes];g.edges=list(zip(ids,ids[1:]))
    assert not validate(g)
    assert execute(g,RunInput(**example(g.family)))['output']['result']['closing']==110

def test_stale_snapshot_wrong_value_and_nonfinite_block():
    g=default_graph('invoice_reconciliation')
    for mutation in ('expired','snapshot','wrong','nan'):
        x=example(g.family)
        if mutation=='expired':x['authority']['observed_at']='2000-01-01T00:00:00+00:00'
        if mutation=='snapshot':x['authority']['snapshot']='wrong'
        if mutation=='wrong':x['authority']['expected']['amount']='999.00'
        if mutation=='nan':x['data']['invoice']='NaN'
        assert execute(g,RunInput(**x))['outcome']=='blocked'

def test_domain_rules():
    assert canonical('shipment_reconciliation',{'declared_kg':'0.45359237','measured':'1','unit':'lb'})=={'weight_kg':'0.454'}
    assert canonical('payout_reconciliation',{'expected':'5','actual_minor':5,'minor_digits':0,'currency':'JPY'})['actual']=='5'
    x=example('data_quality')['data'];x['rows'][1]['id']='a'
    with pytest.raises(ValueError):canonical('data_quality',x)

def test_policy_edit_requires_revalidation(tmp_path,monkeypatch):
    s=CanvasStore(tmp_path);r=s.test(default_graph('inventory_reconciliation'),'builder');v=s.publish(r['id'],'reviewer',True)
    monkeypatch.setattr('jitd.canvas.policy_hash',lambda:'changed')
    with pytest.raises(LabError):s.publish(r['id'],'reviewer',True)
    with pytest.raises(LabError):s.run(v['id'],RunInput(**example('inventory_reconciliation')),'operator')

def test_roles_are_explicit():
    for role,path in [('viewer','test'),('operator','connections'),('builder','publish')]:assert not allowed(role,'POST','/api/canvas/'+path)
    assert allowed('builder','POST','/api/canvas/architect')
    assert allowed('reviewer','POST','/api/canvas/publish')
    assert not allowed('viewer','GET','/api/canvas/connections')

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(server,'LAB',Lab(tmp_path));monkeypatch.setenv('JITD_DATA_DIR',str(tmp_path));monkeypatch.setenv('JITD_BUDGET_DB',str(tmp_path/'platform.sqlite3'));monkeypatch.setenv('JITD_MAX_MODEL_CALLS','0')
    canvas_api._credentials.clear()
    with TestClient(server.app) as c:yield c
    canvas_api._credentials.clear()

def test_api_lifecycle_cost_and_secret_storage(client,tmp_path):
    key='secret-test-key-never-persist-this';data={'slot':'primary','provider':'nebius','model':'test-model','key':key,'input_rate':'1','output_rate':'2'}
    assert client.post('/api/canvas/connections',json=data).status_code==200
    assert key not in client.get('/api/canvas/connections').text
    bad=client.post('/api/canvas/connections',json={**data,'provider':'http://localhost:1'})
    assert bad.status_code==422 and key not in bad.text
    assert client.post('/api/canvas/architect',json={'slot':'primary','task':'Reconcile invoices.'}).status_code==409
    for f in tmp_path.rglob('*'):
        if f.is_file():assert key.encode() not in f.read_bytes()
    g=default_graph('inventory_reconciliation').model_dump();r=client.post('/api/canvas/test',json=g).json();assert r['passed']
    v=client.post('/api/canvas/publish',json={'report_id':r['id']}).json()
    assert client.post('/api/canvas/versions/'+v['id']+'/executions',json=example(g['family'])).json()['result']['outcome']=='accepted_local'
    p={'baseline_input':1000,'baseline_output':500,'input_rate':'1','output_rate':'2','runs':1000,'setup_usd':'1','audit_repair_usd':'0','verification_per_run':'0','human_minutes':'0','hourly_rate':'0'}
    cost=client.post('/api/canvas/cost',json=p).json()
    assert Decimal(cost['baseline_per_run_usd'])==Decimal('.002') and Decimal(cost['net_savings_usd'])==1 and cost['first_positive_break_even_runs']==501
    assert client.delete('/api/canvas/connections/primary').json()['cleared']

def test_actual_token_receipts_and_baseline_quality(client,monkeypatch):
    from types import SimpleNamespace as NS
    import openai
    response={'text':'{"closing":110}','usage':NS(prompt_tokens=100,completion_tokens=20,total_tokens=120)}
    class Fake:
        def __init__(self,**kwargs):self.chat=NS(completions=NS(create=self.create))
        def create(self,**kwargs):return NS(usage=response['usage'],choices=[NS(message=NS(content=response['text']))])
        def close(self):pass
    monkeypatch.setattr(openai,'OpenAI',Fake);monkeypatch.setenv('JITD_MAX_MODEL_CALLS','5')
    client.post('/api/canvas/connections',json={'slot':'primary','provider':'nebius','model':'test','key':'fake-secret-key','input_rate':'1','output_rate':'2'})
    r=client.post('/api/canvas/test',json=default_graph('inventory_reconciliation').model_dump()).json();v=client.post('/api/canvas/publish',json={'report_id':r['id']}).json()
    body={'version_id':v['id'],'input':example('inventory_reconciliation')}
    first=client.post('/api/canvas/baseline',json=body).json()
    assert first['correct'] and Decimal(first['calculated_usd'])==Decimal('.00014')
    response['text']='{"closing":999}';response['usage']=None
    second=client.post('/api/canvas/baseline',json=body).json();assert not second['correct'] and second['calculated_usd'] is None
    response['text']='{"family":"inventory_reconciliation"}'
    proposal=client.post('/api/canvas/architect',json={'task':'Reconcile warehouse inventory.'}).json()
    assert proposal['graph']['family']=='inventory_reconciliation' and proposal['receipt']['accepted']
