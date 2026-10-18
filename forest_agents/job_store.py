"""Small durable job store. No automatic retry of uncertain remote dispatch."""
import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


class Conflict(ValueError):
    pass


class JobStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.directory / 'jobs.sqlite3', check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
          PRAGMA journal_mode=WAL;
          CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, idem TEXT UNIQUE NOT NULL, request_hash TEXT NOT NULL,
            created TEXT NOT NULL, updated TEXT NOT NULL, status TEXT NOT NULL,
            cancelled INTEGER NOT NULL DEFAULT 0, request TEXT NOT NULL, result TEXT NOT NULL,
            decision TEXT, decision_hash TEXT);
          CREATE TABLE IF NOT EXISTS events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
            at TEXT NOT NULL, actor TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL);
        ''')
        self.db.commit()

    def submit(self, request, key):
        if not isinstance(key, str) or not 8 <= len(key) <= 128:
            raise ValueError('Use an idempotency key of 8–128 characters')
        raw = canonical(request)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        with self.lock, self.db:
            existing = self.db.execute('SELECT * FROM jobs WHERE idem=?', (key,)).fetchone()
            if existing:
                if existing['request_hash'] != digest:
                    raise Conflict('Idempotency key already belongs to a different request')
                return existing['id'], False
            jid = str(uuid.uuid4())
            stamp = now()
            self.db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,0,?,?,NULL,NULL)',
                            (jid, key, digest, stamp, stamp, 'queued', raw, '{}'))
            self.event(jid, 'runtime', 'submitted', {'operation': request['operation'], 'live': request['live']})
            return jid, True

    def get(self, jid):
        with self.lock:
            r = self.db.execute('SELECT * FROM jobs WHERE id=?', (jid,)).fetchone()
            if r is None:
                raise KeyError(jid)
            d = dict(r)
            for field in ('request', 'result'):
                d[field] = json.loads(d[field])
            d.pop('idem')
            return d

    def list(self):
        with self.lock:
            rows = self.db.execute('SELECT id FROM jobs ORDER BY created DESC LIMIT 100').fetchall()
            return [self.get(r['id']) for r in rows]

    def update(self, jid, status=None, result=None):
        with self.lock, self.db:
            old = self.get(jid)
            self.db.execute('UPDATE jobs SET status=?,result=?,updated=? WHERE id=?',
                            (status or old['status'], canonical(result if result is not None else old['result']), now(), jid))

    def event(self, jid, actor, kind, detail):
        with self.lock, self.db:
            self.db.execute('INSERT INTO events(job_id,at,actor,kind,detail) VALUES (?,?,?,?,?)',
                            (jid, now(), actor, kind, canonical(detail)))

    def events(self, jid):
        self.get(jid)
        with self.lock:
            return [dict(r, detail=json.loads(r['detail'])) for r in self.db.execute(
                'SELECT * FROM events WHERE job_id=? ORDER BY seq', (jid,))]

    def cancel(self, jid):
        with self.lock, self.db:
            job = self.get(jid)
            if job['status'] not in {'queued', 'running', 'interrupted', 'cancel_requested', 'remote_cancel_unconfirmed'}:
                return job
            self.db.execute('UPDATE jobs SET cancelled=1,status=?,updated=? WHERE id=?', ('cancel_requested', now(), jid))
            self.event(jid, 'user', 'cancel_requested', {})
            return self.get(jid)

    def decision(self, jid, decision, expected_hash):
        if decision not in {'approve_direction', 'reject'}:
            raise ValueError('Unsupported decision')
        with self.lock, self.db:
            job = self.get(jid)
            if job['status'] != 'awaiting_review' or job['request']['operation'] != 'propose_agent_change':
                raise Conflict('This job is not an agent change awaiting review')
            digest = hashlib.sha256(canonical(job['result']).encode()).hexdigest()
            if digest != expected_hash:
                raise Conflict('Review content changed; refresh before deciding')
            self.db.execute('UPDATE jobs SET decision=?,decision_hash=?,updated=? WHERE id=?',
                            (decision, digest, now(), jid))
            self.event(jid, 'human_reviewer', decision, {'result_sha256': digest, 'publication': 'not_performed'})
            return self.get(jid)

    def mark_interrupted(self):
        with self.lock, self.db:
            self.db.execute("UPDATE jobs SET status='interrupted',updated=? WHERE status IN ('running','cancel_requested')", (now(),))

    def close(self):
        self.db.close()
