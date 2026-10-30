import json
import pytest
from jitd import llm, live
from jitd.meter import ModelMeter
from tests.test_live import Fake


def test_failed_request_counted_and_billing_unknown(monkeypatch):
    monkeypatch.setenv('JITD_MAX_MODEL_CALLS','1');llm.reset_budget()
    class Broken:
        def __init__(self): self.chat=self;self.completions=self;self.calls=0
        def create(self,**kwargs):self.calls+=1;raise RuntimeError('provider failure')
    raw=Broken();meter=ModelMeter();client=llm.NebiusClient(meter,'test',client=raw)
    with pytest.raises(RuntimeError):client.complete('repair','s','u')
    with pytest.raises(llm.BudgetExceeded):client.complete('repair','s','u')
    assert raw.calls==1 and meter.snapshot()['repair_model_calls']==1
    assert meter.usage[0]['status']=='failed_usage_unknown'
    assert meter.usage[0]['input_tokens'] is None
    assert meter.cost_summary(1)['estimated_total_usd'] is None


def test_smoke_failure_retains_usage_and_is_not_zero_billing(monkeypatch):
    monkeypatch.setenv('JITD_MAX_MODEL_CALLS','1');llm.reset_budget()
    class Broken:
        def __init__(self):self.chat=self;self.completions=self
        def create(self,**kwargs):raise RuntimeError('down')
    ev=live.collect(lambda m:llm.NebiusClient(m,'test',client=Broken()),'test',1)
    assert not ev['smoke']['ok']
    assert ev['summary']['failed_requests']==1 and ev['summary']['recorded_requests']==1
    assert not ev['summary']['usage_complete'] and ev['summary']['estimated_usd'] is None
    assert ev['source_mode']=='injected_client'


def test_fake_evidence_never_labelled_real_and_fallbacks_separated():
    ev=live.collect(lambda m:Fake(m),'fake',1)
    assert ev['source_mode']=='injected_client'
    assert ev['summary']['model_plans_validated']==1
    assert ev['summary']['model_repairs_validated']==0
    assert ev['summary']['recorded_requests']>=2
    assert 'Accounting' in live.to_markdown(ev)


def test_preflight_no_calls_and_no_credentials(monkeypatch):
    monkeypatch.setenv('NEBIUS_API_KEY','secret-private-token')
    before=llm.budget()
    report=live.preflight(1)
    assert llm.budget()==before and report['sdk_automatic_retries']==0
    assert 'secret-private-token' not in json.dumps(report)
    for invalid in (0,-1,11):
        with pytest.raises(ValueError):live.preflight(invalid)
        with pytest.raises(ValueError):live.collect(None,'test',invalid)


def test_sdk_disables_hidden_retries_and_reads_current_base_url(monkeypatch):
    import openai
    seen={}
    def client(**kwargs):seen.update(kwargs);return object()
    monkeypatch.setenv('NEBIUS_API_KEY','not-a-real-key')
    monkeypatch.setenv('NEBIUS_BASE_URL','https://configured.example/v1/')
    monkeypatch.setattr(openai,'OpenAI',client)
    llm.NebiusClient(model='test')
    assert seen['max_retries']==0 and seen['base_url']=='https://configured.example/v1/'


def test_progress_checkpoint_keeps_completed_stages():
    snapshots=[]
    live.collect(lambda m:Fake(m),'fake',1,checkpoint=lambda ev:snapshots.append(json.loads(json.dumps(ev))))
    assert snapshots[0]['smoke']['ok'] and snapshots[0]['compiles']==[]
    assert any(len(ev['compiles'])==1 and not ev['repairs'] for ev in snapshots)
    assert len(snapshots[-1]['repairs'])==3 and snapshots[-1].get('finished_utc')
