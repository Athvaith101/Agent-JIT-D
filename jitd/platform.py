"""Single-workspace pilot controls. No secrets or request bodies enter audit records."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROLES = {'admin', 'builder', 'operator', 'reviewer', 'viewer'}
ITERATIONS = 600_000


def enterprise():
    return os.getenv('JITD_PROFILE', 'local') == 'enterprise'


def data_dir():
    return Path(os.getenv('JITD_DATA_DIR', Path(__file__).resolve().parent.parent / 'data'))


def password_hash(password, salt=None):
    if len(password) < 14:
        raise ValueError('Use a password of at least fourteen characters')
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return {'algorithm': 'pbkdf2_sha256', 'iterations': ITERATIONS, 'salt': salt, 'digest': digest}


def verify_password(password, record):
    try:
        if record['algorithm'] != 'pbkdf2_sha256' or record['iterations'] != ITERATIONS:
            return False
        digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(record['salt']), ITERATIONS).hex()
        return hmac.compare_digest(digest, record['digest'])
    except (ValueError, KeyError, TypeError):
        return False


_auth_cache = {}
_auth_lock = threading.Lock()


def authenticate(header):
    """Read each time so revoked/rotated user files invalidate cached credentials immediately."""
    path = Path(os.getenv('JITD_USERS_FILE', data_dir() / 'users.json'))
    try:
        raw = path.read_bytes()
        users = json.loads(raw)
        scheme, encoded = header.split(' ', 1)
        user, password = base64.b64decode(encoded, validate=True).decode().split(':', 1)
        if scheme.lower() != 'basic' or len(header) > 4096:
            return None
        record = users.get(user)
        if not record or record.get('disabled') or record.get('role') not in ROLES:
            return None
        cache_key = hashlib.sha256(raw + header.encode()).digest()
        with _auth_lock:
            expiry = _auth_cache.get(cache_key, 0)
        if expiry < time.monotonic():
            if not verify_password(password, record['password']):
                return None
            with _auth_lock:
                if len(_auth_cache) > 256:
                    _auth_cache.clear()
                _auth_cache[cache_key] = time.monotonic() + 60
        return {'name': user, 'role': record['role']}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None


def allowed(role, method, path):
    if path.startswith('/api/hybrid'):
        if method in ('GET','HEAD','OPTIONS'):return True
        if path == '/api/hybrid/policy':return role == 'admin'
        return role in ('operator','admin')
    if path.startswith('/api/canvas/'):
        if path.startswith('/api/canvas/connections'):return role == 'admin'
        if method in ('GET','HEAD','OPTIONS'):return True
        if path == '/api/canvas/cost':return True
        if path == '/api/canvas/publish':return role in ('reviewer','admin')
        if path in ('/api/canvas/test','/api/canvas/architect'):return role in ('builder','admin')
        return role in ('operator','admin')
    if path.startswith('/api/studio/') and method not in ('GET', 'HEAD', 'OPTIONS'):
        if path == '/api/studio/cost/project':
            return True
        if path.endswith('/publish') or path.startswith('/api/studio/proposals/') and path.endswith('/decision'):
            return role in ('reviewer', 'admin')
        if path.startswith('/api/studio/drafts'):
            return role in ('builder', 'admin')
        return role in ('operator', 'admin')
    if path == '/api/run/stream':
        return False  # enterprise execution uses POST; GET is reserved for observation
    if method in ('GET', 'HEAD', 'OPTIONS'):
        if path.startswith('/api/platform/') and path not in ('/api/platform/status', '/api/platform/me', '/api/platform/ready'):
            return role == 'admin'
        return True
    if path.endswith('/repair') or path == '/api/lab/hard-case':
        return False  # promotion must go through a validated proposal and review
    if path.startswith('/api/platform/'):
        return role == 'admin'
    if path.startswith('/api/proposals/') and path.endswith('/decision'):
        return role in ('reviewer', 'admin')
    if path.endswith('/review'):
        return role in ('reviewer', 'admin')
    if path == '/api/workflow/rollback' or path == '/api/lab/reset':
        return role == 'admin'
    return role in ('operator', 'admin')


class PlatformStore:
    def __init__(self, directory):
        self.path = Path(directory) / 'platform.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS security_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,
                  record TEXT NOT NULL, previous TEXT NOT NULL, digest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS model_calls(id TEXT PRIMARY KEY, created TEXT NOT NULL,
                  model TEXT NOT NULL, phase TEXT NOT NULL, status TEXT NOT NULL,
                  input_tokens INTEGER, output_tokens INTEGER, latency_ms REAL);
                CREATE TABLE IF NOT EXISTS proposal_actors(id TEXT PRIMARY KEY, actor TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS requests(actor TEXT, key TEXT, fingerprint TEXT,
                  status INTEGER, body TEXT, PRIMARY KEY(actor,key));
            ''')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.execute('PRAGMA busy_timeout=15000')
        return db

    def event(self, **fields):
        record = json.dumps(dict(created=datetime.now(timezone.utc).isoformat(), **fields), sort_keys=True, separators=(',', ':'))
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT digest FROM security_events ORDER BY seq DESC LIMIT 1').fetchone()
            previous = row[0] if row else '0' * 64
            digest = hashlib.sha256((previous + record).encode()).hexdigest()
            db.execute('INSERT INTO security_events(record,previous,digest) VALUES(?,?,?)', (record, previous, digest))
        return digest

    def events(self, limit=100):
        with self.connect() as db:
            rows = db.execute('SELECT seq,record,digest FROM security_events ORDER BY seq DESC LIMIT ?', (limit,)).fetchall()
        return [dict(json.loads(r), seq=s, digest=d) for s, r, d in rows]

    def verify(self):
        previous, count = '0' * 64, 0
        with self.connect() as db:
            for seq, record, prev, digest in db.execute('SELECT seq,record,previous,digest FROM security_events ORDER BY seq'):
                expected = hashlib.sha256((previous + record).encode()).hexdigest()
                if prev != previous or not hmac.compare_digest(expected, digest):
                    return {'valid': False, 'first_invalid_sequence': seq, 'verified_events': count}
                previous, count = digest, count + 1
        return {'valid': True, 'verified_events': count, 'head': previous,
                'scope': 'Local hash chain; retain exported heads externally. Tail deletion or a full rewrite is not independently detectable.'}

    def reserve_call(self, limit, model, phase):
        import uuid
        call_id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            used = db.execute('SELECT COUNT(*) FROM model_calls').fetchone()[0]
            if used >= limit:
                from .llm import BudgetExceeded
                raise BudgetExceeded('Persistent model-call budget exhausted; no provider request was sent')
            db.execute('INSERT INTO model_calls VALUES(?,?,?,?,?,?,?,?)',
                       (call_id, datetime.now(timezone.utc).isoformat(), model, phase, 'reserved_usage_unknown', None, None, None))
        return call_id

    def finish_call(self, call_id, status, input_tokens=None, output_tokens=None, latency_ms=None):
        with self.connect() as db:
            db.execute('UPDATE model_calls SET status=?,input_tokens=?,output_tokens=?,latency_ms=? WHERE id=?',
                       (status, input_tokens, output_tokens, latency_ms, call_id))

    def usage(self):
        with self.connect() as db:
            count, unknown, inputs, outputs = db.execute('SELECT COUNT(*),COALESCE(SUM(input_tokens IS NULL OR output_tokens IS NULL),0),SUM(input_tokens),SUM(output_tokens) FROM model_calls').fetchone()
        return {'used': count, 'usage_unknown_calls': unknown, 'reported_input_tokens': inputs, 'reported_output_tokens': outputs,
                'note': 'Attempt cap, not a currency cap. Failed/interrupted calls retain their reservation.'}

    def proposer(self, pid, actor=None):
        with self.connect() as db:
            if actor is not None:
                db.execute('INSERT INTO proposal_actors VALUES(?,?)', (pid, actor))
            row = db.execute('SELECT actor FROM proposal_actors WHERE id=?', (pid,)).fetchone()
        return row[0] if row else None

    def claim(self, actor, key, fingerprint):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT fingerprint,status,body FROM requests WHERE actor=? AND key=?', (actor, key)).fetchone()
            if row:
                if row[0] != fingerprint:
                    return 'conflict', None
                if row[1] is None:
                    return 'in_progress', None
                return 'replay', {'status': row[1], 'body': json.loads(row[2])}
            db.execute('INSERT INTO requests VALUES(?,?,?,NULL,NULL)', (actor, key, fingerprint))
        return 'new', None

    def complete_request(self, actor, key, status, body):
        with self.connect() as db:
            db.execute('UPDATE requests SET status=?,body=? WHERE actor=? AND key=?', (status, json.dumps(body), actor, key))


def validate_runtime():
    if not enterprise():
        return
    users_path = Path(os.getenv('JITD_USERS_FILE', data_dir() / 'users.json'))
    try:
        users = json.loads(users_path.read_text())
        if not isinstance(users, dict) or not any(v.get('role') == 'admin' and not v.get('disabled') for v in users.values()):
            raise ValueError()
        for name, value in users.items():
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', name) or value.get('role') not in ROLES:
                raise ValueError()
            pw = value['password']
            if pw['algorithm'] != 'pbkdf2_sha256' or pw['iterations'] != ITERATIONS or len(bytes.fromhex(pw['salt'])) != 16 or len(bytes.fromhex(pw['digest'])) != 32:
                raise ValueError()
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise RuntimeError('Enterprise profile requires a valid users file with an enabled admin; run python -m jitd.admin user-add') from None
    from urllib.parse import urlsplit
    target = urlsplit(os.getenv('NEBIUS_BASE_URL', 'https://api.tokenfactory.nebius.com/v1/'))
    if target.scheme != 'https' or target.hostname not in {'api.tokenfactory.nebius.com', 'api.tokenfactory.us-central1.nebius.com'} or target.username or target.password or target.port not in (None,443) or target.path.rstrip('/') != '/v1' or target.query or target.fragment:
        raise RuntimeError('Enterprise inference must use an approved HTTPS Nebius Token Factory endpoint')
    os.environ.setdefault('JITD_MAX_MODEL_CALLS', '0')
    try:
        if not 0 <= int(os.environ['JITD_MAX_MODEL_CALLS']) <= 10000:
            raise ValueError()
    except ValueError:
        raise RuntimeError('JITD_MAX_MODEL_CALLS must be an integer from 0 to 10000') from None
    os.environ['JITD_BUDGET_DB'] = str(data_dir() / 'platform.sqlite3')
