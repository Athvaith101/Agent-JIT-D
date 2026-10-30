"""Generated safety cases and an explicit strict-gate weakening counterexample."""
from datetime import datetime,timezone,timedelta
import copy,random
from jitd.compiler import compile_workflow
from jitd.contracts import declared_contracts
from jitd.executor import Executor
from jitd.fixtures import make_truth
from jitd.services import MockServices
from jitd.oracle import entry_matches,expected_ledger


def test_generated_missing_stale_and_wrong_evidence_never_post():
    m,_=compile_workflow();rng=random.Random(27)
    for i in range(50):
        t=make_truth('generated',i);svc=MockServices([t]);proof=svc.verification_evidence(t.invoice_id)
        mode=rng.choice(['missing','stale','wrong','correlated'])
        if mode=='missing':proof={}
        else:
            for key in ['billing_authority','settlement_authority']:
                if mode=='stale':proof[key]['observed_at']=(datetime.now(timezone.utc)-timedelta(seconds=rng.randint(301,99999))).isoformat()
                if mode=='correlated':proof[key]['independent_of']=None
                if mode=='wrong':proof[key]['currency']='EUR'
        svc.verification_evidence=lambda _,p=copy.deepcopy(proof):p
        r=Executor(svc,strict=True).run(m,{'invoice_id':t.invoice_id,'as_of':'2026-10-16T00:00:00Z'})
        assert r.outcome!='posted' and not svc.ledger


def test_weakening_strict_gate_exposes_correlated_silent_error():
    m,_=compile_workflow();m.contracts=declared_contracts();t=make_truth('mutation',0)
    svc=MockServices([t],'consistent_scale');inputs={'invoice_id':t.invoice_id,'as_of':'2026-10-16T00:00:00Z'}
    guarded=Executor(svc,strict=True).run(m,inputs)
    weakened=Executor(MockServices([t],'consistent_scale'),strict=False).run(m,inputs)
    assert guarded.outcome!='posted'
    assert weakened.outcome=='posted' and not entry_matches(weakened.posted_entry(),expected_ledger(t))
