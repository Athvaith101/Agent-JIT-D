"""Integration checks for durable operations and human-approved repair."""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from jitd.lab import Lab, LabError
from jitd import server
from jitd.repair import validate_isolated
from jitd.validation import run_validation


def broken(lab):
    lab.inject('unit_cents')
    r = lab.run()
    assert r['outcome'] == 'halted'
    lab.diagnose(r['run_id'])
    return r


def test_approve_revalidates_and_survives_restart(tmp_path):
    lab = Lab(tmp_path)
    r = broken(lab)
    proposal = lab.repair(r['run_id'], preview=True)
    assert proposal['validated'] and lab.manifest.version == '1.0.0'
    restored = Lab(tmp_path)
    assert restored.run_view(restored.get_run(r['run_id']))['diagnosis']['status'] == 'localized'
    assert restored.decide(proposal['proposal_id'], True)['accepted']
    again = Lab(tmp_path)
    assert again.manifest.version == '1.0.1' and len(again.regression) == 25
    assert again.run(invoice_id=r['inputs']['invoice_id'])['oracle_verdict'] == 'correct_post'
    with pytest.raises(LabError, match='already has a decision'):
        again.decide(proposal['proposal_id'], True)
    actions = [a['action'] for a in again.store.audit()]
    assert 'repair_proposed' in actions and 'repair_accepted' in actions


def test_reject_keeps_original_and_stale_proposal_cannot_promote(tmp_path):
    lab = Lab(tmp_path)
    r = broken(lab)
    p = lab.repair(r['run_id'], preview=True)
    assert lab.decide(p['proposal_id'], False)['status'] == 'rejected'
    assert lab.manifest.version == '1.0.0'
    p = lab.repair(r['run_id'], preview=True)
    lab.inject('truncation')
    with pytest.raises(LabError) as e:
        lab.decide(p['proposal_id'], True)
    assert e.value.code == 'stale_proposal'


def test_pause_rollback_and_restart(tmp_path):
    lab = Lab(tmp_path)
    r = broken(lab)
    assert lab.repair(r['run_id'])['accepted']
    with pytest.raises(LabError) as e:
        lab.rollback('1.0.0')
    assert e.value.code == 'pause_required'
    lab.pause(True)
    with pytest.raises(LabError) as e:
        Lab(tmp_path).run()
    assert e.value.code == 'paused'
    assert lab.rollback('1.0.0')['version'] == '1.0.2'
    assert Lab(tmp_path).manifest.meta['restored_from'] == '1.0.0'
    lab.pause(False)
    assert lab.run()['outcome'] == 'halted'  # removed divisor must trigger the contract again


def test_mutations_refused_during_validation(tmp_path):
    lab = Lab(tmp_path)
    lab.repairing = True
    for fn in (lab.reset, lab.compile, lambda: lab.inject('clean'), lambda: lab.pause(True)):
        with pytest.raises(LabError) as e:
            fn()
        assert e.value.code == 'busy'


def test_worker_environment_preserves_windows_loader_but_no_keys(monkeypatch):
    from jitd import repair
    observed = {}
    monkeypatch.setenv('SystemRoot', 'C:\\Windows')
    monkeypatch.setenv('NEBIUS_API_KEY', 'secret-sentinel')
    monkeypatch.setenv('PYTHONPATH', '/untrusted')
    monkeypatch.setattr(repair.site, 'getusersitepackages', lambda: '/trusted-user-packages')
    def launch(args, **kw):
        observed.update(args=args, **kw)
        return SimpleNamespace(returncode=0, stdout='{"ok":true,"groups":{}}')
    monkeypatch.setattr(repair.subprocess, 'run', launch)
    assert validate_isolated({})['isolated']
    assert observed['env']['SystemRoot'] == 'C:\\Windows'
    assert set(observed['env']) <= {'PATH', 'SystemRoot', 'WINDIR', 'PYTHONDONTWRITEBYTECODE'}
    assert '-I' in observed['args'] and '/trusted-user-packages' in observed['args'][-1]
    assert '/untrusted' not in observed['args'][-1]


def test_malformed_or_unlaunchable_worker_fails_closed(monkeypatch):
    from jitd import repair
    for out in ('garbage', '[]', '{"ok":"yes","groups":{}}'):
        monkeypatch.setattr(repair.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=0, stdout=out))
        assert validate_isolated({})['ok'] is False
    def fail(*a, **k):
        raise OSError('cannot launch')
    monkeypatch.setattr(repair.subprocess, 'run', fail)
    assert validate_isolated({})['ok'] is False


def test_no_validation_groups_is_not_proof(tmp_path):
    lab = Lab(tmp_path)
    assert not run_validation({'manifest': lab.manifest.model_dump(), 'groups': {}})['ok']


def test_operations_http_and_export(tmp_path, monkeypatch):
    lab = Lab(tmp_path)
    monkeypatch.setattr(server, 'LAB', lab)
    server._hits.clear()
    c = TestClient(server.app)
    assert c.get('/api/operations').json()['total_runs'] == 0
    r = broken(lab)
    p = c.post(f"/api/runs/{r['run_id']}/propose").json()
    assert p['validated']
    assert c.post(f"/api/proposals/{p['proposal_id']}/decision", json={'approve': True}).json()['accepted']
    assert c.get('/api/operations').json()['open_incidents'] == 0
    assert c.get('/api/audit/export').json()['events'][-1]['action'] == 'proposal_decided'
    assert c.post('/api/workflow/pause', json={'paused': True}).json()['paused']
    assert c.post('/api/workflow/rollback', json={'version': '../../bad'}).status_code == 422


def test_recording_adapter_and_unused_golden_metadata(tmp_path):
    from jitd.sdk import record_invoice, validate_recording
    from jitd.fixtures import make_truth
    from jitd.services import MockServices
    from jitd.compiler import compile_workflow
    from jitd.executor import Executor
    lab = Lab(tmp_path)
    t = make_truth('record', 3)
    svc = MockServices([t])
    case = record_invoice(svc, t.invoice_id, '2026-09-30T00:00:00Z')
    assert svc.calls['ledger.post'] == 0
    report = validate_recording(lab.manifest, case)
    assert report['ok'] and report['groups']['recorded']['oracle_checked'] == 0
    assert 'not independently' in report['correctness_basis']
    case['pages']['']['next_cursor'] = 'missing'
    with pytest.raises(ValueError, match='missing or cyclic'):
        validate_recording(lab.manifest, case)
    class Provider(MockServices):
        def invoice_get(self, invoice_id):
            d = super().invoice_get(invoice_id)
            d.pop('issued_at')
            return d
    assert Executor(Provider([t])).run(lab.manifest, {'invoice_id': t.invoice_id, 'as_of': '2026-09-30T00:00:00Z'}).outcome == 'posted'


def test_retries_do_not_duplicate_postings_and_conflicts_fail_closed(tmp_path):
    from jitd.services import ServiceError
    lab = Lab(tmp_path)
    first = lab.run()
    assert first['outcome'] == 'posted'
    invoice = first['inputs']['invoice_id']
    assert lab.run(invoice_id=invoice)['outcome'] == 'posted'
    assert len(lab.services.ledger) == 1
    lab = Lab(tmp_path)
    assert lab.run(invoice_id=invoice)['outcome'] == 'posted'
    assert len(lab.services.ledger) == 1
    entry = dict(lab.services.ledger[0], amount_usd='999999.00')
    with pytest.raises(ServiceError, match='idempotency conflict'):
        lab.services.ledger_post(entry)
    assert len(lab.services.ledger) == 1
