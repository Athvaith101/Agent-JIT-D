"""Reproducible offline AAIR mechanism demonstration, without a UI or provider key."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jitd.lab import Lab

with tempfile.TemporaryDirectory() as td:
    lab = Lab(Path(td))
    clean = lab.run()
    print('Clean:', clean['outcome'], [a['status'] for a in clean['assumptions']])
    lab.inject('unit_cents')
    blocked = lab.run()
    print('Unit drift:', blocked['outcome'])
    print('Diagnosis:', lab.diagnose(blocked['run_id'])['top']['name'])
    print('Wrong repair accepted:', lab.repair(blocked['run_id'], 'wrong')['accepted'])
    proposal = lab.repair(blocked['run_id'], preview=True)
    print('Proposed, version still:', lab.manifest.version)
    result = lab.decide(proposal['proposal_id'], True)
    print('Approved:', result['accepted'], 'new version:', lab.manifest.version)
    recovered = lab.run(invoice_id=blocked['inputs']['invoice_id'])
    print('Retry:', recovered['outcome'], recovered['oracle_verdict'])
    print('Reused:', recovered['recovery']['reused_nodes'])
    print('Executed:', recovered['recovery']['executed_nodes'])
    print('Independent re-verification:', recovered['recovery']['reverified'])
    lab.services.evidence_mode = 'missing'
    unknown = lab.run()
    print('Missing evidence:', unknown['outcome'], unknown['halt']['reason'])
    assert unknown['outcome'] != 'posted'
    assert recovered['recovery']['accepted_output']
