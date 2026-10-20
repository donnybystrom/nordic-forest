"""Loopback-only Langflow bridge with durable jobs and a local review dashboard."""
import argparse
import hashlib
import hmac
import json
import os
import queue
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .bridge_runtime import JobRequest, Runtime
from .job_store import Conflict, JobStore, canonical
from .workflow import ROOT, SECRET_PATTERN


class Bridge:
    def __init__(self, directory, key_file=None, port=8765, runtime_factory=Runtime):
        self.store = JobStore(directory)
        self.store.mark_interrupted()
        self.runtime = runtime_factory(self.store, key_file)
        self.token = secrets.token_urlsafe(32)
        self.origin = f'http://127.0.0.1:{port}'
        self.queue = queue.Queue(maxsize=20)
        self.active = set()
        self.lock = threading.RLock()
        self.closed = threading.Event()
        self.worker = threading.Thread(target=self.work, daemon=True)
        self.runtime.submit_child = self.submit
        self.worker.start()
        self.nonces = set()
        self.cookies = set()
        path = Path(directory) / 'client.json'
        path.write_text(canonical({'url': self.origin, 'token': self.token, 'pid': os.getpid()}))
        path.chmod(0o600)
        # Queued jobs were never dispatched; interrupted jobs require explicit reconciliation.
        for job in reversed(self.store.list()):
            if job['status'] == 'queued':
                self.enqueue(job['id'])

    def enqueue(self, jid):
        with self.lock:
            if jid in self.active:
                return
            self.queue.put_nowait(jid)
            self.active.add(jid)

    def work(self):
        while not self.closed.is_set():
            try:
                jid = self.queue.get(timeout=.2)
            except queue.Empty:
                continue
            try:
                self.runtime.execute(jid)
            finally:
                with self.lock:
                    self.active.discard(jid)
                self.queue.task_done()

    def submit(self, body, key):
        request = JobRequest.model_validate(body).checked()
        with self.lock:
            if self.queue.full():
                raise Conflict('Queue full; wait for an existing job')
            jid, fresh = self.store.submit(request, key)
            if fresh:
                self.enqueue(jid)
        return jid, fresh

    def resume(self, jid):
        job = self.store.get(jid)
        if job['status'] != 'interrupted' or job['cancelled']:
            raise Conflict('Only an interrupted, non-cancelled job can reconcile')
        states = job['result'].get('sessions', {}).values()
        if any(s.get('status') == 'dispatching' and not s.get('session_id') for s in states):
            raise Conflict('Unknown remote create outcome; inspect OpenAI sessions before any new dispatch')
        if job['request']['operation'] == 'collect_audit_reference' or (job['request']['operation']=='planning_board' and job['request']['board_request']['action']!='inspect') or (job['request']['operation'] == 'github_pr' and job['request']['github_request']['action'] != 'inspect'):
            raise Conflict('Interrupted file or GitHub write requires inspecting retained evidence and remote state')
        self.store.update(jid, status='queued')
        self.enqueue(jid)
        return self.store.get(jid)

    def close(self):
        self.closed.set()
        self.worker.join(timeout=2)
        if not self.worker.is_alive():
            self.store.close()


def handler_for(bridge):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'NordicBridge/0.1'

        def log_message(self, *_):
            pass  # No tokens, provider errors or request bodies in access logs.

        def send(self, value, status=200, content_type='application/json', extra=None):
            data = value.encode() if isinstance(value, str) else canonical(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type + '; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def trusted_host(self):
            return self.headers.get('Host') == urlsplit(bridge.origin).netloc

        def authenticated(self):
            bearer = self.headers.get('Authorization', '').removeprefix('Bearer ')
            cookie = self.headers.get('Cookie', '')
            session = next((p.strip().split('=', 1)[1] for p in cookie.split(';') if p.strip().startswith('nordic_session=')), '')
            return hmac.compare_digest(bearer, bridge.token) or session in bridge.cookies

        def route(self, post=False):
            if not self.trusted_host():
                return self.send({'error': 'host_rejected'}, 403)
            path = urlsplit(self.path).path
            if self.headers.get('Origin') not in {None, bridge.origin}:
                return self.send({'error': 'origin_rejected'}, 403)
            if not post and path == '/health':
                return self.send({'status': 'ok', 'service': 'nordic-forest-bridge', 'version': '0.1'})
            if not post and path == '/':
                # Same-origin one-use nonce bootstraps an HttpOnly local UI session. No API key in HTML/URLs.
                nonce = secrets.token_urlsafe(24)
                bridge.nonces.add(nonce)
                if len(bridge.nonces) > 100:
                    bridge.nonces = {nonce}
                html = (ROOT / 'integrations/langflow/dashboard.html').read_text().replace('__BOOTSTRAP__', nonce)
                return self.send(html, content_type='text/html', extra={'Content-Security-Policy': "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"})
            body = {}
            if post:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 20000:
                    return self.send({'error': 'body_size_rejected'}, 413)
                body = json.loads(self.rfile.read(length))
                if path == '/ui-session':
                    nonce = self.headers.get('X-Local-Bootstrap', '')
                    if nonce not in bridge.nonces:
                        return self.send({'error': 'bootstrap_rejected'}, 403)
                    bridge.nonces.remove(nonce)
                    cookie = secrets.token_urlsafe(32)
                    bridge.cookies.add(cookie)
                    return self.send({'status': 'local_session'}, extra={'Set-Cookie': f'nordic_session={cookie}; HttpOnly; SameSite=Strict; Path=/'})
            if not self.authenticated():
                return self.send({'error': 'authentication_required'}, 401)
            if post and path == '/control/stop':
                if any(j['status'] in {'running', 'queued', 'cancel_requested'} for j in bridge.store.list()):
                    raise Conflict('Active jobs must finish or acknowledge cancellation first')
                self.send({'status': 'stopping'})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            bits = path.strip('/').split('/')
            if bits == ['jobs']:
                if not post:
                    return self.send({'jobs': bridge.store.list()})
                jid, fresh = bridge.submit(body, self.headers.get('Idempotency-Key'))
                return self.send({'job': bridge.store.get(jid), 'created': fresh}, 202 if fresh else 200)
            if len(bits) >= 2 and bits[0] == 'jobs':
                jid = bits[1]
                if not post and len(bits) == 2:
                    job = bridge.store.get(jid)
                    job['result_sha256'] = hashlib.sha256(canonical(job['result']).encode()).hexdigest()
                    return self.send(job)
                if not post and bits[2:] == ['events']:
                    return self.send({'events': bridge.store.events(jid)})
                if post and bits[2:] == ['cancel']:
                    return self.send(bridge.store.cancel(jid), 202)
                if post and bits[2:] == ['resume']:
                    return self.send(bridge.resume(jid), 202)
                if post and bits[2:] == ['decision']:
                    # Model clients cannot vote as the human. Only local browser session.
                    if self.headers.get('Authorization'):
                        return self.send({'error': 'human_ui_session_required'}, 403)
                    return self.send(bridge.store.decision(jid, body.get('decision'), body.get('result_sha256')))
            return self.send({'error': 'not_found'}, 404)

        def dispatch(self, post):
            try:
                self.route(post)
            except Conflict as exc:
                self.send({'error': 'conflict', 'message': str(exc)}, 409)
            except KeyError:
                self.send({'error': 'not_found'}, 404)
            except (ValueError, TypeError):
                self.send({'error': 'invalid_request'}, 400)
            except Exception:
                self.send({'error': 'internal_error'}, 500)

        def do_GET(self):
            self.dispatch(False)

        def do_POST(self):
            self.dispatch(True)

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--key-file', default=str(ROOT / 'OPENAI_API_SECRET_KEY.md'))
    args = parser.parse_args()
    # Bind first: never replace a running service's client token when the port is busy.
    server = ThreadingHTTPServer(('127.0.0.1', args.port), BaseHTTPRequestHandler)
    bridge = Bridge(ROOT / 'runs/control', args.key_file, args.port)
    server.RequestHandlerClass = handler_for(bridge)
    print(f'Nordic bridge listening on {bridge.origin}', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        bridge.close()


if __name__ == '__main__':
    main()
