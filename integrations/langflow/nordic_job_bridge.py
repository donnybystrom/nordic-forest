"""Importable Langflow component; no OpenAI/Sketchfab keys in flow JSON."""
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, MessageTextInput, Output, StrInput
from lfx.schema.message import Message


class NordicJobBridge(Component):
    display_name = 'Nordic Job Bridge'
    description = 'Submit or inspect a durable local job. Offline by default; repeated identical run keys reuse a job.'
    icon = 'Workflow'
    name = 'NordicJobBridge'
    inputs = [
        MessageTextInput(name='request_text', display_name='Task', value='Planera en liten ekträds-LOD-jämförelse.'),
        DropdownInput(name='operation', display_name='Workflow', options=['plan_feature', 'collect_audit_reference', 'propose_agent_change'], value='plan_feature'),
        BoolInput(name='live', display_name='Execute live', value=False, info='Allows billed saved-agent sessions or actual asset/Blender work.'),
        DropdownInput(name='action', display_name='Action', options=['submit', 'status', 'cancel', 'resume'], value='submit', advanced=True),
        StrInput(name='job_id', display_name='Existing job ID', value='', advanced=True),
        StrInput(name='run_key', display_name='Submission key', value='pilot-1', info='Change deliberately to start a new run of the same task.', advanced=True),
        StrInput(name='target_role', display_name='Proposed role', value='asset_analysis', advanced=True),
        StrInput(name='specialists', display_name='Specialists (comma-separated)', value='', advanced=True),
    ]
    outputs = [Output(name='message', display_name='Job Status', method='job_status')]

    def job_status(self) -> Message:
        config_path = Path('/Users/donnybystrom/code/Nordic-3D-forest/runs/control/client.json')
        try:
            config = json.loads(config_path.read_text())
            if config['url'] != 'http://127.0.0.1:8765':
                raise ValueError('Unexpected bridge address')
            def call(path, body=None, key=None):
                headers = {'Authorization': 'Bearer ' + config['token']}
                if body is not None:
                    headers['Content-Type'] = 'application/json'
                if key:
                    headers['Idempotency-Key'] = key
                request = urllib.request.Request(config['url'] + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
                try:
                    with urllib.request.urlopen(request, timeout=10) as response:
                        return json.load(response)
                except urllib.error.HTTPError as exc:
                    safe = json.load(exc)
                    raise ValueError(safe.get('message', safe.get('error', 'Bridge rejected request'))) from None
            if self.action == 'submit':
                body = {'project': 'nordic-forest', 'operation': self.operation, 'request': str(self.request_text),
                        'live': bool(self.live), 'target_role': self.target_role,
                        'specialists': [s.strip() for s in self.specialists.split(',') if s.strip()]}
                key = hashlib.sha256(json.dumps({'body': body, 'run_key': self.run_key}, sort_keys=True).encode()).hexdigest()
                result = call('/jobs', body, key)
                job = result['job']
                for _ in range(10):
                    if job['status'] not in {'queued', 'running'}:
                        break
                    time.sleep(.3)
                    job = call('/jobs/' + job['id'])
            else:
                import uuid
                jid = str(uuid.UUID(self.job_id.strip()))
                job = call('/jobs/' + jid + ('/' + self.action if self.action != 'status' else ''), {} if self.action != 'status' else None)
            self.status = job['status']
            result = job['result']
            lines = [f"{job['request']['operation']} · {job['status']}", f"Job ID: {job['id']}",
                     'Dashboard: http://127.0.0.1:8765/', 'Feature acceptance: not performed']
            if result.get('packet'):
                lines += ['\nStages:'] + [s['stage'] + ' → ' + s['role'] for s in result['packet']['stages']]
                lines += ['\n' + r['role'] + ': ' + r['handover']['recommendation'] for r in result['packet']['results']]
            elif result.get('proposal'):
                lines += ['\n' + result['proposal']['diff'], '\nPublication: not performed', 'Evaluation: ' + result['evaluation']]
            else:
                lines += [json.dumps(result, ensure_ascii=False, indent=2)]
            return Message(text='\n'.join(lines)[:24000])
        except FileNotFoundError:
            return Message(text='Bridge is not running. Start tools/start_bridge.command in the Nordic Forest workspace.')
        except (OSError, ValueError, KeyError):
            return Message(text='Bridge request stopped. Inspect the local dashboard/job events; credentials and raw provider errors are withheld.')
