import copy
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from jitd import server
from jitd.lab import Lab, LabError
from jitd.platform import password_hash
from jitd.studio import CostInputs, DraftInput, Settings, Studio, fingerprint, project_cost

TASK = 'Reconcile invoices and payments against independent evidence.'


def published(studio):
    draft = studio.create(DraftInput(name='Test invoice agent', task=TASK), 'builder')
    report = studio.test(draft['id'], 1, 'builder')
    assert report['passed']
    version = studio.publish(draft['id'], 1, report['id'], 'reviewer', True)
    return draft, report, version


def test_complete_lifecycle_and_restart(tmp_path):
    s=Studio(tmp_path);d,r,v=published(s)
    clean=s.execute(v['id'],None,'operator');assert clean['run']['oracle_verdict']=='correct_post'
    s.configure_run(v['id'],'unit_cents','independent','operator')
    bad=s.execute(v['id'],None,'operator');assert bad['run']['outcome']=='halted'
    preview=s.propose(v['id'],bad['id'],False,'operator')
    assert preview['impact']['corrected_outputs']==1 and preview['impact']['harmful_changes']==0
    assert 'normalize_amount' in preview['recovery_plan']['invalidated_nodes']
    assert s.decide(preview['id'],True,'reviewer',True)['status']=='approved'
    retried=s.execute(v['id'],bad['run']['inputs']['invoice_id'],'operator')
    assert retried['run']['oracle_verdict']=='correct_post' and retried['run']['model_calls']==0
    assert retried['passport']['repair_approvals'][0]['reviewer']=='reviewer'
    restored=Studio(tmp_path)
    assert restored.version_detail(v['id'])['state']['workflow']['version']=='1.0.1'
    assert restored._get('versions',v['id'])['manifest_hash']==v['manifest_hash']
    assert restored.verify_passports()['valid'] and restored.verify_passports()['count']==3


def test_edit_invalidates_validation_but_not_published_version(tmp_path):
    s=Studio(tmp_path);d,r,v=published(s)
    edited=s.update(d['id'],1,'Changed invoice agent',TASK,Settings(max_pages=4),'builder')
    assert edited['content_hash']!=d['content_hash'] and edited['last_report'] is None
    with pytest.raises(LabError,match='passing report'):s.publish(d['id'],2,r['id'],'reviewer',True)
    with pytest.raises(LabError,match='Draft changed'):s.update(d['id'],1,'Old edit',TASK,Settings(),'builder')
    assert s.execute(v['id'],None,'operator')['run']['oracle_verdict']=='correct_post'
    new_report=s.test(d['id'],2,'builder');new_version=s.publish(d['id'],2,new_report['id'],'reviewer',True)
    assert new_version['number']==2 and new_version['manifest_hash']!=v['manifest_hash']


@pytest.mark.parametrize('task',['Find weather in Coimbatore.','Reconcile invoices and email payment receipts.','Reconcile invoice payments and transfer money.','Reconcile EUR invoice payments.','Reconcile invoice payments from https://untrusted.example'])
def test_unsupported_tasks_are_refused(tmp_path,task):
    with pytest.raises(LabError,match='supports|outside'):Studio(tmp_path).create(DraftInput(name='Unsupported agent',task=task),'builder')


@pytest.mark.parametrize('settings',[{'max_pages':True},{'max_pages':21},{'required_evidence':False},{'output':'real_erp'},{'currency':'EUR'},{'arbitrary_python':'print(1)'}])
def test_draft_settings_cannot_weaken_the_gate(settings):
    with pytest.raises(ValidationError):Settings.model_validate(settings)


def test_draft_is_not_executable_and_report_is_agent_bound(tmp_path):
    s=Studio(tmp_path);d=s.create(DraftInput(name='Draft only',task=TASK),'builder')
    with pytest.raises(LabError):s.execute(d['id'],None,'operator')
    other,r,_=published(s)
    with pytest.raises(LabError):s.publish(d['id'],1,r['id'],'reviewer')


def test_self_approval_and_duplicate_publication_refused(tmp_path):
    s=Studio(tmp_path);d=s.create(DraftInput(name='Separation test',task=TASK),'builder');r=s.test(d['id'],1,'builder')
    with pytest.raises(LabError,match='different reviewer'):s.publish(d['id'],1,r['id'],'builder',True)
    s.publish(d['id'],1,r['id'],'reviewer',True)
    with pytest.raises(LabError,match='already published'):s.publish(d['id'],1,r['id'],'reviewer',True)


def test_policy_change_requires_new_publication(tmp_path,monkeypatch):
    s=Studio(tmp_path);d,_,v=published(s)
    monkeypatch.setattr('jitd.studio.policy_hash',lambda:'changed-policy')
    with pytest.raises(LabError,match='runtime policy changed'):s.execute(v['id'],None,'operator')
    report=s.test(d['id'],1,'builder');updated=s.publish(d['id'],1,report['id'],'reviewer',True)
    assert updated['number']==2 and s.execute(updated['id'],None,'operator')['run']['oracle_verdict']=='correct_post'


def test_published_version_sql_immutability(tmp_path):
    s=Studio(tmp_path);_,_,v=published(s)
    with s.connect() as db:
        with pytest.raises(sqlite3.IntegrityError,match='immutable'):db.execute('UPDATE versions SET payload=? WHERE id=?',('{}',v['id']))


def test_unknown_stays_blocked_after_repair(tmp_path):
    s=Studio(tmp_path);_,_,v=published(s);s.configure_run(v['id'],'unit_cents','independent','operator')
    run=s.execute(v['id'],None,'operator');p=s.propose(v['id'],run['id'],False,'operator')
    with pytest.raises(LabError,match='different reviewer'):s.decide(p['id'],True,'operator',True)
    s.decide(p['id'],True,'reviewer',True)
    s.configure_run(v['id'],'unit_cents','missing','operator')
    run=s.execute(v['id'],None,'operator')
    assert run['run']['outcome']!='posted' and any(a['status']=='UNKNOWN' for a in run['run']['assumptions'])
    assert run['passport']['outcome']!='posted'


def test_runtime_mutation_cannot_bypass_approval(tmp_path):
    s=Studio(tmp_path);_,_,v=published(s);_,lab=s.runtime(v['id'])
    lab.manifest.step_for_op('payment.list').params['max_pages']=10
    with pytest.raises(LabError,match='not bound'):s.execute(v['id'],None,'operator')


def test_passport_covers_run_output_and_manifest(tmp_path):
    s=Studio(tmp_path);_,_,v=published(s);run=s.execute(v['id'],None,'operator')
    value=s._get('executions',run['id']);value['run']['ledger_entry']['amount_usd']='0.00'
    with s.connect() as db:db.execute('UPDATE executions SET payload=? WHERE id=?',(json.dumps(value),run['id']))
    with pytest.raises(LabError,match='integrity failed'):s._get('executions',run['id'])


def test_passport_chain_tampering_blocks_new_execution(tmp_path):
    s=Studio(tmp_path);_,_,v=published(s);s.execute(v['id'],None,'operator')
    with s.connect() as db:db.execute("UPDATE passports SET body='{}' WHERE seq=1")
    assert not s.verify_passports()['valid']
    with pytest.raises(LabError,match='chain is invalid'):s.execute(v['id'],None,'operator')


class Model:
    model='example-injected-model'
    def __init__(self,meter,reply):self.meter,self.reply=meter,reply
    def complete(self,phase,*args,**kwargs):
        self.meter.record(phase,10,input_tokens=8,output_tokens=2,model=self.model)
        return self.reply


def test_model_draft_and_raw_receipt_are_attributed(tmp_path):
    raw=json.dumps({'template_id':'invoice_reconciliation','max_pages':4,'rationale':'Read all supported pages.'})
    s=Studio(tmp_path,lambda m,r:Model(m,raw));d=s.create(DraftInput(name='Model draft',task=TASK,use_model=True),'builder')
    assert d['settings']['max_pages']==4 and d['provenance']['source']=='model'
    receipt=s.receipt(d['provenance']['receipt_ids'][0])
    assert receipt['raw_output']==raw and receipt['accepted'] and receipt['source_mode']=='injected_client'
    assert receipt['usage'][0]['input_tokens']==8


@pytest.mark.parametrize('reply',['not json','{"template_id":"invoice_reconciliation","max_pages":999,"rationale":"bad"}','{"template_id":"invoice_reconciliation","max_pages":4,"rationale":"bad","disable_evidence":true}'])
def test_model_rejections_are_labelled_fallback(tmp_path,reply):
    s=Studio(tmp_path,lambda m,r:Model(m,reply));d=s.create(DraftInput(name='Fallback draft',task=TASK,use_model=True),'builder')
    assert d['settings']['max_pages']==1 and d['provenance']['source']=='deterministic_fallback'
    assert not s.receipt(d['provenance']['receipt_ids'][0])['accepted']


def test_no_model_configuration_does_not_fake_a_call(tmp_path):
    with pytest.raises(LabError,match='No model'):Studio(tmp_path).create(DraftInput(name='No key draft',task=TASK,use_model=True),'builder')


def test_same_input_schema_only_comparison_is_synthetic_and_read_only(tmp_path):
    s=Studio(tmp_path);_,_,v=published(s);s.configure_run(v['id'],'unit_cents','independent','operator');run=s.execute(v['id'],None,'operator')
    comparison=s.comparison(run['id'])
    assert comparison['strict_outcome']=='halted' and comparison['schema_only_outcome']=='posted' and not comparison['schema_only_correct']
    assert comparison['always_llm']=='Not measured' and comparison['external_writes']==0
    assert len(s.runtime(v['id'])[1].services.ledger)==0


def test_projection_counts_human_time_and_reports_negative_savings():
    result=project_cost(CostInputs(baseline_usd_per_run=.001,setup_usd=.01,replay_usd_per_run=.0001,audit_and_repair_usd=0,human_minutes=5,hourly_rate_usd=30,runs=1000))
    assert result['fixed_usd']==2.51 and result['net_savings_usd']==-1.61 and result['break_even_runs']==2789
    assert 'not measured' in result['basis']
    result=project_cost(CostInputs(baseline_usd_per_run=0,setup_usd=0,replay_usd_per_run=.001,audit_and_repair_usd=0,human_minutes=0,hourly_rate_usd=0,runs=10))
    assert result['break_even_runs'] is None


@pytest.fixture(scope='module')
def users():
    password=password_hash('example-studio-password-only')
    return {name:{'role':name,'password':password,'disabled':False} for name in ('admin','builder','operator','reviewer','viewer')}


@pytest.fixture
def client(tmp_path,monkeypatch,users):
    monkeypatch.setenv('JITD_PROFILE','enterprise');monkeypatch.setenv('JITD_DATA_DIR',str(tmp_path));monkeypatch.setenv('JITD_ALLOWED_HOSTS','testserver')
    monkeypatch.setenv('JITD_USERS_FILE',str(tmp_path/'users.json'));monkeypatch.setenv('JITD_BUDGET_DB',str(tmp_path/'platform.sqlite3'));monkeypatch.setenv('JITD_MAX_MODEL_CALLS','0')
    (tmp_path/'users.json').write_text(json.dumps(users));monkeypatch.setattr(server,'LAB',Lab(tmp_path));server._hits.clear()
    return TestClient(server.app)


def auth(role):return role,'example-studio-password-only'


def test_http_roles_publication_and_idempotent_execution(client):
    c=client
    body={'name':'HTTP invoice agent','task':TASK}
    assert c.post('/api/studio/drafts',json=body,auth=auth('operator')).status_code==403
    draft=c.post('/api/studio/drafts',json=body,auth=auth('builder')).json();aid=draft['id']
    report=c.post(f'/api/studio/drafts/{aid}/test',json={'revision':1},auth=auth('builder')).json()
    pub={'revision':1,'report_id':report['id']}
    assert c.post(f'/api/studio/drafts/{aid}/publish',json=pub,auth=auth('builder')).status_code==403
    version=c.post(f'/api/studio/drafts/{aid}/publish',json=pub,auth=auth('reviewer')).json();vid=version['id']
    path=f'/api/studio/versions/{vid}/executions'
    assert c.post(path,json={},auth=auth('viewer')).status_code==403
    assert c.post(path,json={},auth=auth('operator')).status_code==400
    head={'Idempotency-Key':'example-studio-unique-01'}
    first=c.post(path,json={},auth=auth('operator'),headers=head);second=c.post(path,json={},auth=auth('operator'),headers=head)
    assert first.status_code==200 and first.json()['id']==second.json()['id'] and second.headers['Idempotency-Replayed']=='true'
    assert c.get('/api/studio/runs/'+first.json()['id']+'/passport',auth=auth('viewer')).json()['chain_verification']['valid']
    assert c.get('/studio',auth=auth('viewer')).status_code==200
    assert 'Build your agent' in c.get('/',auth=auth('viewer')).text
    assert 'id="agentSelect"' in c.get('/studio',auth=auth('viewer')).text


def test_missing_evidence_prevents_candidate_promotion(tmp_path):
    s=Studio(tmp_path);_,_,v=published(s);s.configure_run(v['id'],'unit_cents','independent','operator')
    run=s.execute(v['id'],None,'operator');p=s.propose(v['id'],run['id'],False,'operator')
    assert p['strict_validation']['passed']
    s.configure_run(v['id'],'unit_cents','missing','operator')
    with pytest.raises(LabError,match='Fresh strict evidence'):s.decide(p['id'],True,'reviewer',True)
    assert s.runtime(v['id'])[1].manifest.version=='1.0.0'


def test_offline_backup_restores_agent_versions_and_passports(tmp_path):
    from jitd.admin import backup, restore
    source=tmp_path/'source';s=Studio(source);d,_,v=published(s);saved=s.execute(v['id'],None,'operator')
    target=tmp_path/'restored';archive=tmp_path/'studio-backup.zip';backup(source,archive);restore(archive,target)
    recovered=Studio(target)
    assert recovered.overview()['drafts'][0]['id']==d['id']
    assert recovered._get('executions',saved['id'])['passport']['digest']==saved['passport']['digest']
    assert recovered.execute(v['id'],None,'operator')['run']['oracle_verdict']=='correct_post'


def test_known_key_is_redacted_from_model_rationale_and_receipt(tmp_path,monkeypatch):
    key='example-private-value-for-redaction'
    monkeypatch.setenv('NEBIUS_API_KEY',key)
    raw=json.dumps({'template_id':'invoice_reconciliation','max_pages':1,'rationale':key})
    s=Studio(tmp_path,lambda m,r:Model(m,raw));d=s.create(DraftInput(name='Redaction test',task=TASK,use_model=True),'builder')
    assert key not in json.dumps(d)
    assert key not in json.dumps(s.receipt(d['provenance']['receipt_ids'][0]))


def test_model_receipt_rejected_when_fresh_strict_validation_fails(tmp_path):
    raw=json.dumps({'op':'normalize_money','param':'rules','value':[{'divisor':1,'effective_from':None},{'divisor':100,'effective_from':'2026-10-16T00:00:00Z'}],'rationale':'Restore supported units.'})
    s=Studio(tmp_path,lambda m,r:Model(m,raw));_,_,v=published(s);s.configure_run(v['id'],'unit_cents','independent','operator')
    run=s.execute(v['id'],None,'operator');s.configure_run(v['id'],'unit_cents','missing','operator')
    result=s.propose(v['id'],run['id'],True,'operator')
    assert not result['validated'] and not s.receipt(result['receipt_ids'][0])['accepted']
