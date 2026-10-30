"""Synthetic authority error sensitivity; explicitly tests the trust boundary failing."""
import argparse
import copy
import json
import random
from datetime import datetime,timezone,timedelta
from pathlib import Path
from .compiler import compile_workflow
from .executor import Executor
from .fixtures import make_truth
from .services import MockServices
from .oracle import entry_matches,expected_ledger
from .stream_stats import summarize_streams


def study(streams=30,runs=10):
    m,_=compile_workflow();cells=[];trials=[]
    for mode in ('correlated_drift','wrong_reference','stale','missing'):
        for epsilon in (0,.01,.05,.1,.25,.5,1):
            rates={'silent':[],'blocked':[],'false_block':[]}
            for seed in range(streams):
                rng=random.Random(seed);counts={k:0 for k in rates}
                for i in range(runs):
                    t=make_truth('authority-'+str(seed),i)
                    svc=MockServices([t],'consistent_scale' if mode=='correlated_drift' else 'clean')
                    evidence=svc.verification_evidence(t.invoice_id);bad=rng.random()<epsilon
                    if bad:
                        if mode in ('correlated_drift','wrong_reference'):
                            for key,field in [('billing_authority','invoice_total_usd'),('settlement_authority','settled_total_usd')]:
                                evidence[key][field]=str(float(evidence[key][field])*100)
                        elif mode=='missing':evidence={}
                        else:
                            for key in ('billing_authority','settlement_authority'):evidence[key]['observed_at']=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
                    svc.verification_evidence=lambda invoice_id,proof=copy.deepcopy(evidence):copy.deepcopy(proof)
                    r=Executor(svc,strict=True).run(m,{'invoice_id':t.invoice_id,'as_of':'2026-10-16T00:00:00Z'})
                    silent=r.outcome=='posted' and not entry_matches(r.posted_entry(),expected_ledger(t))
                    blocked=r.outcome!='posted';false_block=blocked and mode!='correlated_drift'
                    values=dict(silent=silent,blocked=blocked,false_block=false_block)
                    for k,v in values.items():counts[k]+=int(v)
                    trials.append(dict(mode=mode,epsilon=epsilon,seed=seed,index=i,authority_fault=bad,**values))
                for k in rates:rates[k].append(counts[k]/runs)
            cells.append({'mode':mode,'epsilon':epsilon,**{k:summarize_streams(v) for k,v in rates.items()}})
    return {'scope':'Synthetic trust-boundary experiment, not empirical authority reliability. Correlated drift tests authority and provider failing together. No universal safe reliability threshold is inferred.', 'cells':cells,'trials':trials}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='benchmark/authority/latest.json');a=ap.parse_args()
    d=study();p=Path(a.out);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=1))
    print('Authority study trials:',len(d['trials']))


if __name__=='__main__':main()
