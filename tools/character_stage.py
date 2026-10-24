"""Submit a character command to the same local bridge used by Langflow."""
import argparse
import hashlib
import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from forest_agents.bridge_runtime import JobRequest
from forest_agents.job_store import canonical


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', type=Path, help='JSON file containing one CharacterCommand')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--run-key', default='character-1')
    args = parser.parse_args()
    command = json.loads(args.command.read_text())
    body = JobRequest(operation='character_pipeline', request='Execute one explicit character-production stage.',
                      character_request=command, live=args.execute).checked()
    config = json.loads((ROOT / 'runs/control/client.json').read_text())
    if config['url'] != 'http://127.0.0.1:8765':
        raise ValueError('Unexpected bridge address')
    def call(path, payload=None, key=None):
        headers = {'Authorization': 'Bearer ' + config['token'], 'Content-Type': 'application/json'}
        if key:
            headers['Idempotency-Key'] = key
        req = urllib.request.Request(config['url'] + path,
                                     data=canonical(payload).encode() if payload is not None else None, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.load(response)
    key = hashlib.sha256(canonical({'body': body, 'run_key': args.run_key}).encode()).hexdigest()
    if command['action'] in {'balance', 'inspect', 'poll_rodin'}:
        key = str(uuid.uuid4())
    job = call('/jobs', body, key)['job']
    deadline = time.monotonic() + 50
    while job['status'] in {'queued', 'running'} and time.monotonic() < deadline:
        time.sleep(.5)
        job = call('/jobs/' + job['id'])
    print(json.dumps({'job_id': job['id'], 'status': job['status'], 'result': job['result']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
