import copy
import json
import pytest
from scripts.create_pilot_demo import demo_bundle
from jitd.sdk import check_recording
from jitd.model_baseline import compare
from jitd.readiness import readiness


def test_unreachable_page_is_rejected_before_any_model_call():
    b=demo_bundle();b['recording']['pages']['orphan']=copy.deepcopy(b['recording']['pages'][''])
    with pytest.raises(ValueError,match='unreachable'):check_recording(b['recording'])
    with pytest.raises(ValueError,match='unreachable'):compare([b],lambda m:pytest.fail('must not dispatch'))


def test_completed_cases_survive_batch_interruption():
    seen=[];calls=[]
    class Fake:
        def complete(self,*args,**kwargs):
            calls.append(1)
            if len(calls)==2:raise KeyboardInterrupt()
            return '{"hold":true}'
    with pytest.raises(KeyboardInterrupt):compare([demo_bundle(),demo_bundle()],lambda m:Fake(),checkpoint=seen.append)
    assert len(seen)==1 and len(seen[0]['cases'])==1 and seen[0]['completed'] is False


@pytest.mark.parametrize('validated,complete,status',[(False,False,'connectivity_only'),(True,False,'validated_contribution_usage_incomplete'),(True,True,'validated_contribution_with_usage')])
def test_smoke_is_not_a_validated_model_contribution(tmp_path,validated,complete,status):
    p=tmp_path/'evidence';p.mkdir()
    r={'kind':'jitd_live_evidence','source_mode':'nebius_api','finished_utc':'now','smoke':{'ok':True},
       'compiles':[{'used_model_plan':validated}],'summary':{'usage_complete':complete,'recorded_requests':1}}
    (p/'live.json').write_text(json.dumps(r))
    gate=next(g for g in readiness(tmp_path)['gates'] if g['id']=='live_nemotron')
    assert gate['status']==status
