"""Single-instance durable session and ordered audit trail. No customer secrets stored."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class Store:
    def __init__(self, directory):
        self.path = Path(directory) / 'operations.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS session (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT NOT NULL,
                    action TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS proposals (id TEXT PRIMARY KEY, status TEXT NOT NULL, payload TEXT NOT NULL);
            ''')

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def load(self):
        with self.connect() as db:
            row = db.execute('SELECT payload FROM session WHERE id=1').fetchone()
        return json.loads(row[0]) if row else None

    def save(self, payload, action, detail=None):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO session VALUES(1,?)', (json.dumps(payload, default=str),))
            db.execute('INSERT INTO audit(created,action,payload) VALUES(?,?,?)',
                       (datetime.now(timezone.utc).isoformat(), action, json.dumps(detail or {}, default=str)))

    def audit(self):
        with self.connect() as db:
            return [{'seq': a, 'created': b, 'action': c, 'detail': json.loads(d)}
                    for a, b, c, d in db.execute('SELECT seq,created,action,payload FROM audit ORDER BY seq')]

    def proposal(self, pid, payload=None, status='pending'):
        with self.connect() as db:
            if payload is not None:
                db.execute('INSERT OR REPLACE INTO proposals VALUES(?,?,?)', (pid, status, json.dumps(payload)))
            row = db.execute('SELECT status,payload FROM proposals WHERE id=?', (pid,)).fetchone()
        return dict(json.loads(row[1]), status=row[0]) if row else None

    def pending(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT payload FROM proposals WHERE status='pending' ORDER BY rowid DESC")]
