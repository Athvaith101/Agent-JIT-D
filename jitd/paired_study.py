"""Same-evidence recovery study. Synthetic mechanism experiment, no model/ROI claims."""
import argparse
import copy
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from .compiler import compile_workflow
from .executor import Executor
from .fixtures import make_truth
from .oracle import entry_matches, expected_ledger
from .recovery import recover
from .services import MockServices

CASES = ['unit_repair', 'evidence_restored', 'evidence_contradiction', 'policy_unknown', 'snapshot_changed']
METHODS = ['aair', 'data_dependency_replay', 'full_rerun']


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class FrozenEvidenceServices(MockServices):
    def verification_evidence(self, invoice_id):
        return copy.deepcopy(self.proof)


def episode(manifest, case, seed):
    truth = make_truth('paired-'+str(seed), seed)
    svc = FrozenEvidenceServices([truth], 'unit_cents' if case == 'unit_repair' else 'clean')
    # Freeze the same original observation for all compared runs; never refresh timestamps per method.
    proof = MockServices.verification_evidence(svc, truth.invoice_id)
    svc.proof = proof if case == 'unit_repair' else {}
    inputs = {'invoice_id': truth.invoice_id, 'as_of': '2026-10-16T00:00:00Z'}
    prior = Executor(svc, strict=True).run(manifest, inputs)
    if prior.outcome not in ('halted', 'held'):
        raise RuntimeError('Study requires a blocked prior run')
    candidate = manifest.clone()
    if case == 'unit_repair':
        candidate.step_for_op('normalize_money').params['rules'].append({'divisor':100,'effective_from':'2026-10-16T00:00:00Z'})
        candidate.version='1.0.1'
    elif case == 'evidence_contradiction':
        proof['settlement_authority']['settled_total_usd']=str(truth.paid_total+10)
    elif case == 'policy_unknown':
        candidate.assumptions.append({'id':'unsupported-date-policy','node':'fetch_invoice','required':True,
                                     'status':'UNKNOWN','consumers':['fetch_invoice'],'semantic_contract':'date meaning verified'})
    elif case == 'snapshot_changed':
        svc.set_behavior('cosmetic')
    svc.proof=proof
    svc.ledger=[]
    svc.calls={k:0 for k in svc.calls}
    return candidate, prior, svc, expected_ledger(truth)


def study(seeds=3):
    if os.getenv('JITD_AUTHORITY_CSV'):
        raise ValueError('Unset JITD_AUTHORITY_CSV for the controlled synthetic comparison')
    if not 1 <= seeds <= 100:
        raise ValueError('seeds must be between 1 and 100')
    start=time.perf_counter();manifest,_=compile_workflow();compile_ms=(time.perf_counter()-start)*1000
    rows=[]
    for seed in range(seeds):
        for case in CASES:
            candidate,prior,svc,expected=episode(manifest,case,seed)
            # Rotate order to reduce systematic first-run timing bias.
            order=METHODS[seed%3:]+METHODS[:seed%3]
            for method in order:
                local=copy.deepcopy(svc)
                baseline=copy.deepcopy(prior)
                timer=time.perf_counter()
                if method=='full_rerun':
                    result=Executor(local,strict=True).run(candidate,baseline.inputs)
                else:
                    result=recover(manifest,candidate,baseline,local,semantic=method=='aair')
                elapsed=(time.perf_counter()-timer)*1000
                correct=result.outcome=='posted' and entry_matches(result.posted_entry(),expected)
                rows.append({'seed':seed,'case':case,'method':method,
                    'evidence_sha256':sha(local.proof),'candidate_sha256':sha(candidate.model_dump()),
                    'prior_sha256':sha(prior.to_dict(with_values=True)), 'snapshot':local.snapshot_token(prior.inputs['invoice_id']),
                    'outcome':result.outcome,'correct_output':correct,'silent_error':result.outcome=='posted' and not correct,
                    'halt':result.halt,'assumptions':result.assumptions,'ledger_entry':result.posted_entry(),
                    'reused_nodes':[s['id'] for s in result.steps if s.get('reused')],
                    'executed_nodes':[s['id'] for s in result.steps if s['status']!='skipped' and not s.get('reused')],
                    'source_calls':local.calls,'wall_ms':elapsed,'verification_ms':result.verification_ms})
    cells=[]
    for case in CASES:
        for method in METHODS:
            subset=[r for r in rows if r['case']==case and r['method']==method]
            cells.append({'case':case,'method':method,'trials':len(subset),
                          'correct_outputs':sum(r['correct_output'] for r in subset),
                          'silent_errors':sum(r['silent_error'] for r in subset),
                          'blocked':sum(r['outcome']!='posted' for r in subset),
                          'reused_nodes':sum(len(r['reused_nodes']) for r in subset),
                          'executed_nodes':sum(len(r['executed_nodes']) for r in subset),
                          'mean_wall_ms':sum(r['wall_ms'] for r in subset)/len(subset)})
    code=hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob('*.py')):
        code.update(path.name.encode());code.update(path.read_bytes())
    return {'meta':{'created_at':datetime.now(timezone.utc).isoformat(),'code_sha256':code.hexdigest(),
            'seeds':seeds,'shared_compilation_ms':compile_ms,'model_calls':0,'cost_usd':None,
            'scope':'Same frozen evidence, prior checkpoint, candidate patch, inputs, snapshot and final strict gate for each paired episode.',
            'limitations':['Synthetic authorities share fixture truth; no independent corpus.',
                          'Patch supplied identically; repair discovery/validation costs are outside this recovery-only study.',
                          'Full rerun means same candidate with no checkpoint reuse; it is not full model regeneration.',
                          'Evidence-only changes hold provider bytes and version fixed; refreshed verification is shared by every method.',
                          'Common compile setup measured once; wall timings exclude episode setup and are not customer savings.',
                          'Ordinary dependency replay retains the same checkpoint integrity and policy-change safeguards.',
                          'No claim of semantic-slicing superiority follows from fewer or more invalidated nodes.']},
            'cells':cells,'trials':rows}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds',type=int,default=3)
    parser.add_argument('--output',default='benchmark/paired/latest.json')
    args=parser.parse_args();result=study(args.seeds)
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
    print(json.dumps({'output':str(target),'trials':len(result['trials']),
                      'silent_errors':sum(r['silent_error'] for r in result['trials'])}))


if __name__=='__main__':
    main()
