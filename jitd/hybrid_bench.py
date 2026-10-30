"""Authored monitoring/routing simulation. No model calls or inference savings claims."""
import argparse
import json
import random
import tempfile
from pathlib import Path
from .hybrid import Monitor,Policy


def evaluate(seed,k,h):
    rng=random.Random(seed)
    with tempfile.TemporaryDirectory() as directory:
        m=Monitor(directory);m.configure(Policy(enabled=True,minimum_verified=8,cusum_k=k,cusum_h=h,residual_probability=.001),'benchmark')
        rows=[]
        for phase,count in [('clean',80),('cosmetic',20),('known_unit_fault',20),('ambiguous_fault',20),('missing_evidence',20)]:
            for index in range(count):
                verified=phase in ('clean','cosmetic');unknown=phase=='missing_evidence';known=phase=='known_unit_fault'
                value=10+rng.gauss(0,.15)+(4 if phase=='ambiguous_fault' else 0)
                r=m.observe(str(len(rows)),'frozen-routing-simulation',signals={'latency':value},label=None if unknown else not verified,
                    label_basis='authored simulator labels',verified=verified,unknown=unknown,known_local=known,ambiguous=phase=='ambiguous_fault',
                    causes=[],model_ready=True,budget_remaining=1000)
                rows.append({'phase':phase,'index':index,'alarm':r['alarm'],'route':r['route']['action'],'verified':verified})
        clean=[r for r in rows if r['phase']=='clean' and r['index']>=8]
        alarms=[r['index'] for r in rows if r['phase']=='ambiguous_fault' and r['alarm']]
        return {'seed':seed,'k':k,'h':h,'runs':len(rows),'clean_alarm_rate':sum(r['alarm'] for r in clean)/len(clean),
                'first_ambiguous_shift_alarm_delay_runs':alarms[0] if alarms else None,
                'policy_model_diagnosis_requests':sum(r['route']=='model_diagnosis' for r in rows),
                'always_reason_requests_comparator':len(rows),
                'accept_recommendations_without_verified_predicates':sum(r['route']=='accept_verified_fast_path' and not r['verified'] for r in rows),
                'missing_evidence_model_requests':sum(r['phase']=='missing_evidence' and r['route']=='model_diagnosis' for r in rows)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);args=parser.parse_args()
    result={'scope':'Authored statistical/routing simulation, not end-to-end agent accuracy or live LLM evaluation.',
            'actual_model_calls':0,'measured_token_or_cost_savings':None,
            'development_threshold_sweep':[evaluate(seed,k,h) for seed in (11,29) for k,h in ((1,6),(1.5,8),(2,12))],
            'held_out_default_thresholds':[evaluate(seed,1.5,8) for seed in (101,207,809)],
            'limitations':'Synthetic labels and cost assumptions; no calibrated error probabilities, formal false-alarm guarantee or deployment generalization.'}
    text=json.dumps(result,indent=2)
    if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(text+'\n')
    print(text)


if __name__=='__main__':main()
