"""Inspect available evidence; never treat implementation as proof of field performance."""
import json
from pathlib import Path


def readiness(root,pilot=None):
    root=Path(root);live=[];baseline=[];connections=[];contributions=[]
    for p in (root/'evidence').rglob('*.json'):
        try:
            if p.stat().st_size>10*1024*1024:continue
            r=json.loads(p.read_text(encoding='utf-8'))
            if r.get('source_mode')!='nebius_api':continue
            if r.get('kind')=='jitd_live_evidence' and r.get('finished_utc') and r.get('smoke',{}).get('ok'):
                connections.append(p.name)
                summary=r.get('summary',{})
                validated=any(c.get('used_model_plan') for c in r.get('compiles',[])) or any(c.get('nemotron_proposal_accepted') for c in r.get('repairs',[]))
                if validated:
                    contributions.append(p.name)
                    if summary.get('usage_complete') is True and summary.get('recorded_requests',0)>0:live.append(p.name)
            if r.get('kind')=='jitd.measured_full_input_reasoning/1' and r.get('completed') is True and r.get('finished_utc') and len(r.get('cases',[]))==r.get('expected_cases') and any(c.get('reasoning',{}).get('provider_usage') for c in r.get('cases',[])):baseline.append(p.name)
        except (ValueError,OSError,AttributeError,TypeError):continue
    report=pilot.report() if pilot else {'cases':0,'declared_real_cases':0,'review_count':0}
    gates=[
      {'id':'live_nemotron','priority':'P0','status':'validated_contribution_with_usage' if live else 'validated_contribution_usage_incomplete' if contributions else 'connectivity_only' if connections else 'pending_external','evidence':{'complete':live,'contributions':contributions,'connectivity':connections},'why':'Inspect accepted/rejected proposals and complete usage; real calls alone do not establish quality.'},
      {'id':'provider_and_authority','priority':'P0','status':'declared_records_present' if report['declared_real_cases'] else 'pending_external','evidence':report['declared_real_cases'],'why':'Importer-declared real records require independent provenance review; origin separation is not proof.'},
      {'id':'unseen_incidents','priority':'P0','status':'pending_external','why':'Independent author must freeze incidents before running evaluation.'},
      {'id':'novelty','priority':'P0','status':'not_established','why':'Same-evidence study has not shown a semantic-slicing advantage.'},
      {'id':'model_baseline','priority':'P1','status':'evidence_present' if baseline else 'pending_external','evidence':baseline,'why':'Single-call full-input comparison; review coverage, failures and actual usage.'},
      {'id':'incident_resolution','priority':'P1','status':'exercised' if report['review_count'] else 'implemented_not_exercised','why':'Reviews reverify evidence; notes never override UNKNOWN.'},
      {'id':'shadow_pilot','priority':'P1','status':'records_present' if report['cases'] else 'pending_external','evidence':report,'why':'Acceptance is distinct from independently established correctness.'},
      {'id':'windows_validation','priority':'P1','status':'pending_external','why':'Run installation, tests, HTTP connector and live harness on the actual Windows laptop.'},
      {'id':'submission_demo','priority':'P1','status':'implemented_not_recorded','why':'Capture three-minute demonstration and reconcile claims with evidence.'},
      {'id':'hosted_demo','priority':'P2','status':'configured_not_deployed','why':'Protected single-instance deployment configuration requires an actual host test.'}]
    return {'gates':gates,'ready_to_claim_field_validation':False,'note':'These are evidence gates, not a prediction of competition results. Uploaded reports are not cryptographically authenticated.'}
