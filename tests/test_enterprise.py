"""Regression tests for deployment boundaries, exact approval, durable budgets and recovery."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from jitd import llm, server
from jitd.admin import add_user, backup, exclusive, restore
from jitd.lab import Lab
from jitd.platform import PlatformStore, allowed, authenticate, password_hash, validate_runtime

PASSWORD = 'example-test-password-only'


@pytest.fixture(scope='module')
def users():
    record = password_hash(PASSWORD)
    return {name: {'role': role, 'disabled': False, 'password': record} for name, role in
            [('alice', 'admin'), ('bob', 'operator'), ('claire', 'reviewer'), ('dave', 'viewer')]}


@pytest.fixture
def pilot(tmp_path, monkeypatch, users):
    (tmp_path / 'users.json').write_text(json.dumps(users))
    monkeypatch.setenv('JITD_PROFILE', 'enterprise')
    monkeypatch.setenv('JITD_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('JITD_ALLOWED_HOSTS', 'testserver')
    monkeypatch.setenv('JITD_USERS_FILE', str(tmp_path / 'users.json'))
    monkeypatch.setenv('JITD_BUDGET_DB', str(tmp_path / 'platform.sqlite3'))
    monkeypatch.setenv('JITD_MAX_MODEL_CALLS', '0')
    monkeypatch.delenv('JITD_ACCESS_TOKEN', raising=False)
    monkeypatch.setattr(server, 'LAB', Lab(tmp_path))
    server._hits.clear()
    return TestClient(server.app), tmp_path


def auth(name):
    return name, PASSWORD


def test_auth_fail_closed_and_public_liveness(pilot):
    c, _ = pilot
    assert c.get('/api/health').status_code == 200
    assert c.get('/api/state').status_code == 401
    assert c.get('/api/state', auth=('alice', 'incorrect')).status_code == 401
    assert c.get('/api/platform/me', auth=auth('dave')).json()['role'] == 'viewer'
    assert c.get('/api/platform/status', auth=auth('dave')).status_code == 200
    assert c.get('/api/platform/audit', auth=auth('dave')).status_code == 403
    assert c.get('/api/platform/audit', auth=auth('alice')).status_code == 200


def test_revocation_invalidates_cached_credentials(pilot):
    c, path = pilot
    assert c.get('/api/state', auth=auth('dave')).status_code == 200
    p = path / 'users.json'; users = json.loads(p.read_text()); users['dave']['disabled'] = True; p.write_text(json.dumps(users))
    assert c.get('/api/state', auth=auth('dave')).status_code == 401


@pytest.mark.parametrize('name,path,expected', [('dave','/api/executions',403),('claire','/api/executions',403),
    ('bob','/api/lab/reset',403),('alice','/api/lab/hard-case',403),('bob','/api/runs/unknown/repair',403)])
def test_role_enforcement(pilot, name, path, expected):
    c, _ = pilot
    assert c.post(path, json={}, auth=auth(name)).status_code == expected


def test_execution_idempotency_and_get_cannot_execute(pilot):
    c, _ = pilot
    assert c.get('/api/run/stream', auth=auth('bob')).status_code == 403
    assert c.post('/api/executions', json={}, auth=auth('bob')).status_code == 400
    headers = {'Idempotency-Key': 'example-once-0001'}
    a = c.post('/api/executions', json={}, auth=auth('bob'), headers=headers)
    assert a.status_code == 200
    b = c.post('/api/executions', json={}, auth=auth('bob'), headers=headers)
    assert a.json()['run_id'] == b.json()['run_id'] and b.headers['Idempotency-Replayed'] == 'true'
    assert server.LAB.n == 1
    assert c.post('/api/executions', json={'invoice_id': 'different'}, auth=auth('bob'), headers=headers).status_code == 409
    # Keys are scoped to authenticated actors.
    assert c.post('/api/executions', json={}, auth=auth('alice'), headers=headers).json()['run_id'] != a.json()['run_id']


def test_two_person_promotion(pilot):
    c, path = pilot
    assert c.post('/api/lab/inject', json={'scenario':'unit_cents'}, auth=auth('alice')).status_code == 200
    run = c.post('/api/executions', json={}, headers={'Idempotency-Key':'example-broken-01'}, auth=auth('alice')).json()
    assert run['outcome'] == 'halted'
    p = c.post(f'/api/runs/{run["run_id"]}/propose', auth=auth('alice')).json()
    assert p['validated']
    endpoint = '/api/proposals/' + p['proposal_id'] + '/decision'
    assert c.post(endpoint, json={'approve':True}, auth=auth('alice')).status_code == 403
    assert c.post(endpoint, json={'approve':True}, auth=auth('bob')).status_code == 403
    assert c.post(endpoint, json={'approve':True}, auth=auth('claire')).json()['accepted']
    assert c.post(endpoint, json={'approve':True}, auth=auth('claire')).status_code == 409
    assert Lab(path).manifest.version == '1.0.1'


def test_unknown_proposer_cannot_bypass_review(pilot):
    c, _ = pilot
    server.LAB.inject('unit_cents'); run = server.LAB.run()
    p = server.LAB.repair(run['run_id'], preview=True)
    r = c.post('/api/proposals/'+p['proposal_id']+'/decision', json={'approve':True}, auth=auth('claire'))
    assert r.status_code == 409


def test_exact_approved_proposal_revalidated_not_resynthesized(tmp_path, monkeypatch):
    lab = Lab(tmp_path); lab.inject('unit_cents'); run = lab.run()
    p = lab.repair(run['run_id'], preview=True)
    pending = lab.store.proposal(p['proposal_id'])
    entry = next(x for x in pending['record']['proposals'] if x.get('status') == 'accepted')
    entry['source'] = 'nemotron'  # a stored, validated model proposal; no real model call claimed
    lab.store.proposal(p['proposal_id'], pending)
    monkeypatch.setattr('jitd.repair.synthesize', lambda *args: pytest.fail('approval must not synthesize a replacement'))
    result = lab.decide(p['proposal_id'], True)
    assert result['accepted'] and result['accepted_proposal'] == 'nemotron'
    assert lab.run(invoice_id=run['inputs']['invoice_id'])['oracle_verdict'] == 'correct_post'


def test_bounded_ingress_origin_host_and_request_receipts(pilot):
    c, path = pilot
    assert c.post('/api/recordings/validate', content=b'x'*(2*1024*1024+1), auth=auth('alice')).status_code == 413
    assert c.post('/api/workflow/pause', json={'paused':True}, auth=auth('alice'), headers={'Origin':'https://evil.example'}).status_code == 403
    assert c.get('/api/state', auth=auth('alice'), headers={'Host':'evil.example'}).status_code == 400
    response = c.post('/api/workflow/pause', json={'paused':True}, auth=auth('bob'), headers={'Origin':'https://testserver'})
    assert response.status_code == 200 and response.headers['X-Request-ID']
    rows = PlatformStore(path).events()
    assert any(e.get('request_id') == response.headers['X-Request-ID'] and e['actor'] == 'bob' and e.get('status') == 200 for e in rows)
    assert PASSWORD not in json.dumps(rows)
    assert PlatformStore(path).verify()['valid']


def test_audit_detects_modified_record(tmp_path):
    store = PlatformStore(tmp_path); store.event(action='first'); store.event(action='second')
    assert store.verify()['valid']
    with store.connect() as db:
        db.execute("UPDATE security_events SET record='{}' WHERE seq=1")
    assert not store.verify()['valid']


def test_persistent_budget_atomic_across_store_instances(tmp_path, monkeypatch):
    monkeypatch.setenv('JITD_BUDGET_DB', str(tmp_path / 'platform.sqlite3'))
    monkeypatch.setenv('JITD_MAX_MODEL_CALLS', '3')
    PlatformStore(tmp_path)
    def reserve(_):
        try:
            PlatformStore(tmp_path).reserve_call(3, 'example-model', 'repair'); return True
        except llm.BudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(20))) == 3
    llm.reset_budget()  # reset of legacy process counter must not reset durable spending
    assert llm.budget() == {'limit':3, 'used':3, 'remaining':0}
    assert PlatformStore(tmp_path).usage()['usage_unknown_calls'] == 3


def test_failed_model_call_reservation_survives_restart(tmp_path, monkeypatch):
    monkeypatch.setenv('JITD_BUDGET_DB', str(tmp_path / 'platform.sqlite3')); monkeypatch.setenv('JITD_MAX_MODEL_CALLS', '1')
    class Broken:
        def __init__(self): self.chat=self; self.completions=self
        def create(self, **kw): raise RuntimeError('example-provider-timeout')
    with pytest.raises(RuntimeError): llm.NebiusClient(model='example', client=Broken()).complete('repair','s','u')
    assert PlatformStore(tmp_path).usage()['used'] == 1
    with pytest.raises(llm.BudgetExceeded): llm.NebiusClient(model='example', client=Broken()).complete('repair','s','u')


def test_backup_restore_state_budget_audit_and_integrity(tmp_path):
    original = tmp_path / 'original'; lab = Lab(original); lab.run(); lab.pause(True)
    store = PlatformStore(original); store.reserve_call(2,'example','compile'); store.event(action='saved')
    add_user(original, 'example-admin', 'admin', PASSWORD)
    archive = tmp_path / 'backup.zip'; report = backup(original, archive)
    assert report['files'] >= 4
    target = tmp_path / 'restored'; restore(archive, target)
    assert Lab(target).paused and Lab(target).n == 1
    assert PlatformStore(target).usage()['used'] == 1 and PlatformStore(target).verify()['valid']
    assert (target/'users.json').read_bytes() == (original/'users.json').read_bytes()
    with pytest.raises(ValueError): restore(archive, target)
    with pytest.raises(ValueError): backup(original, archive)


def test_lock_refuses_second_instance(tmp_path):
    with exclusive(tmp_path):
        with pytest.raises(RuntimeError):
            with exclusive(tmp_path): pass


def test_restore_rejects_path_traversal_before_writing(tmp_path):
    import hashlib, zipfile
    p = tmp_path / 'bad.zip'
    with zipfile.ZipFile(p,'w') as z:
        z.writestr('manifest.json',json.dumps({'schema':'jitd.backup/1','files':{'../escape':hashlib.sha256(b'x').hexdigest()}}))
        z.writestr('data/../escape',b'x')
    with pytest.raises(ValueError, match='Unsafe'): restore(p,tmp_path/'new')
    assert not (tmp_path/'new').exists() and not (tmp_path/'escape').exists()


def test_enterprise_startup_requires_valid_users(tmp_path, monkeypatch):
    monkeypatch.setenv('JITD_PROFILE','enterprise'); monkeypatch.setenv('JITD_USERS_FILE',str(tmp_path/'missing'))
    with pytest.raises(RuntimeError,match='valid users'): validate_runtime()


def test_placeholder_credentials_are_offline(monkeypatch):
    monkeypatch.setenv('NEBIUS_API_KEY','replace_me'); monkeypatch.setenv('NEBIUS_MODEL_ID','replace_with_a_model')
    assert not llm.available()


def test_no_details_in_unexpected_error(pilot, monkeypatch):
    c, _ = pilot
    def broken(*args, **kw): raise RuntimeError('example-private-business-value')
    monkeypatch.setattr(server.LAB,'run',broken)
    r = c.post('/api/executions',json={},auth=auth('bob'),headers={'Idempotency-Key':'example-crash-01'})
    assert r.status_code == 500 and 'example-private-business-value' not in r.text
    assert r.json()['request_id']


def test_corrupt_audit_blocks_mutations(pilot):
    c, path = pilot
    store = PlatformStore(path); store.event(action='original')
    with store.connect() as db: db.execute("UPDATE security_events SET record='{}' WHERE seq=1")
    assert c.post('/api/workflow/pause',json={'paused':True},auth=auth('alice')).status_code == 503
    assert not server.LAB.paused


def test_invalid_output_limit_never_dispatches_or_spends(monkeypatch):
    monkeypatch.setenv('JITD_MODEL_MAX_OUTPUT_TOKENS','999999')
    from tests.test_budget import _Fake
    fake=_Fake(); before=llm.budget()
    with pytest.raises(ValueError,match='no request was sent'):
        llm.NebiusClient(model='example',client=fake).complete('repair','s','u')
    assert fake.calls == 0 and llm.budget() == before


def test_viewer_can_check_readiness(pilot):
    c, _ = pilot
    assert c.get('/api/platform/ready',auth=auth('dave')).status_code == 200
