"""Character production stages through the project's durable local bridge."""
import asyncio
import hashlib
import json
import time
import urllib.request
import uuid
from pathlib import Path

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, MessageTextInput, Output, StrInput
from lfx.schema.message import Message


class NordicCharacterPipeline(Component):
    display_name = 'NF · Character Pipeline'
    name = 'NordicCharacterPipeline'
    icon = 'PersonStanding'
    description = 'Prepare character views, generate through Rodin, then build and validate a local Blender body rig. Motion retargeting and physics follow separately.'
    inputs = [
        MessageTextInput(name='request_json', display_name='Character command JSON', required=True, tool_mode=True,
                         value='{"action":"prepare","character_id":"beach-tourist-zombie-v1"}',
                         info='Actions: split_sheet, prepare, run_rodin, rig_character (source_job_id + rig_profile), inspect, balance, submit_rodin, poll_rodin, fetch_rodin. Later stages reference source_job_id from prepare.'),
        BoolInput(name='live', display_name='Execute stage', value=False,
                  info='Allows local crop writes and provider calls. A billable Rodin submission also requires approval of its exact prepared package.'),
        StrInput(name='run_key', display_name='Submission key', value='character-1', advanced=True),
    ]
    outputs = [Output(name='message', display_name='Character stage result', method='execute')]

    async def execute(self) -> Message:
        try:
            return await asyncio.to_thread(self._execute)
        except (OSError, ValueError, KeyError, TypeError):
            return Message(text=json.dumps({'status': 'bridge_error', 'message': 'Inspect the local dashboard; credentials and raw provider errors are withheld.'}))

    def _execute(self) -> Message:
        config = json.loads(Path('/Users/donnybystrom/code/Nordic-3D-forest/runs/control/client.json').read_text())
        if config['url'] != 'http://127.0.0.1:8765':
            raise ValueError('Unexpected bridge address')
        def call(path, body=None, key=None):
            headers = {'Authorization': 'Bearer ' + config['token']}
            if body is not None:
                headers['Content-Type'] = 'application/json'
            if key:
                headers['Idempotency-Key'] = key
            req = urllib.request.Request(config['url'] + path,
                                         data=json.dumps(body).encode() if body is not None else None, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.load(response)
        command = json.loads(str(self.request_json))
        body = {'operation': 'character_pipeline', 'request': 'Execute one explicit character-production stage.',
                'character_request': command, 'live': bool(self.live)}
        key = hashlib.sha256(json.dumps({'body': body, 'run_key': self.run_key}, sort_keys=True).encode()).hexdigest()
        if command.get('action') in {'inspect', 'balance', 'poll_rodin'}:
            key = str(uuid.uuid4())
        job = call('/jobs', body, key)['job']
        deadline = time.monotonic() + 40
        while job['status'] in {'queued', 'running'} and time.monotonic() < deadline:
            time.sleep(1)
            job = call('/jobs/' + job['id'])
        self.status = job['status']
        return Message(text=json.dumps({'status': job['status'], 'job_id': job['id'], 'result': job['result'],
                                        'dashboard': 'http://127.0.0.1:8765/'}, ensure_ascii=False))
