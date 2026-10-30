import copy
import pytest
from jitd.paired_study import study, episode
from jitd.compiler import compile_workflow
from jitd.recovery import recover


@pytest.fixture(scope='module')
def report():return study(seeds=2)


def test_all_methods_get_identical_inputs_evidence_and_candidate(report):
    for seed in range(2):
        for case in {r['case'] for r in report['trials']}:
            rows=[r for r in report['trials'] if r['case']==case and r['seed']==seed]
            assert len(rows)==3
            for field in ('evidence_sha256','candidate_sha256','prior_sha256','snapshot'):
                assert len({r[field] for r in rows})==1
            assert len({(r['outcome'],str(r['ledger_entry'])) for r in rows})==1
    assert not any(r['silent_error'] for r in report['trials'])


def test_assumption_only_episode_is_not_advertised_as_a_safety_win(report):
    rows=[r for r in report['trials'] if r['case']=='evidence_contradiction']
    assert all(r['outcome']!='posted' for r in rows)
    for method in ('aair','data_dependency_replay','full_rerun'):
        assert any(r['method']==method for r in rows)
    restored=[r for r in report['trials'] if r['case']=='evidence_restored']
    assert all(r['correct_output'] for r in restored)
    assert report['meta']['cost_usd'] is None and report['meta']['model_calls']==0


def test_unit_repair_and_fallback_checks(report):
    unit=[r for r in report['trials'] if r['case']=='unit_repair']
    assert all(r['correct_output'] for r in unit)
    assert all(len(r['reused_nodes'])==4 for r in unit if r['method']!='full_rerun')
    for row in report['trials']:
        if row['case'] in ('policy_unknown','snapshot_changed'):assert not row['reused_nodes']


def test_dependency_ablation_does_not_mutate_original_assumptions():
    m,_=compile_workflow();candidate,prior,svc,_=episode(m,'evidence_restored',0)
    original=copy.deepcopy(prior.assumptions)
    recover(m,candidate,prior,svc,semantic=False)
    assert prior.assumptions==original and original
