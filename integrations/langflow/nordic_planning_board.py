"""Explicit GitHub planning broker tool for a Langflow orchestration flow."""
import asyncio
import hashlib
import json
import time
import uuid
import urllib.request
from pathlib import Path
from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, MessageTextInput, Output, StrInput
from lfx.schema.message import Message


class NordicPlanningBoard(Component):
    display_name='NF · Planning Board'
    name='NordicPlanningBoard'
    icon='Kanban'
    description='Inspect and edit the GitHub Projects board; explicitly dispatch a Ready planning ticket to its saved local role. Preview by default.'
    inputs=[MessageTextInput(name='request_json',display_name='Board command JSON',tool_mode=True,required=True,
                value='{"action":"inspect"}',info='Actions: inspect, create_ticket (ticket contract), set_state (issue, expected_state, state), dispatch_plan (issue), sync_job (job_id), link_pr (issue, pr). Repository is fixed.'),
            BoolInput(name='live',display_name='Execute live',value=False,info='Allows GitHub reads/writes and, only for dispatch_plan, a billed saved-role planning session.'),
            StrInput(name='run_key',display_name='Submission key',value='board-1',advanced=True)]
    outputs=[Output(name='message',display_name='Board result',method='execute')]

    async def execute(self)->Message:
        try: return await asyncio.to_thread(self._execute)
        except (OSError,ValueError,KeyError,TypeError):
            return Message(text=json.dumps({'status':'bridge_error','message':'Inspect the local dashboard; raw errors and credentials are withheld.'}))

    def _execute(self)->Message:
        c=json.loads(Path('/Users/donnybystrom/code/Nordic-3D-forest/runs/control/client.json').read_text())
        if c['url']!='http://127.0.0.1:8765': raise ValueError('Unexpected bridge address')
        def call(path,body=None,key=None):
            headers={'Authorization':'Bearer '+c['token']}
            if body is not None: headers['Content-Type']='application/json'
            if key: headers['Idempotency-Key']=key
            req=urllib.request.Request(c['url']+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
            with urllib.request.urlopen(req,timeout=10) as r:return json.load(r)
        command=json.loads(str(self.request_json))
        body={'operation':'planning_board','request':'Execute the explicit GitHub planning command.','board_request':command,'live':bool(self.live)}
        key=hashlib.sha256(json.dumps({'body':body,'run_key':self.run_key},sort_keys=True).encode()).hexdigest()
        if command.get('action')=='inspect': key=str(uuid.uuid4())  # Always read current GitHub state.
        job=call('/jobs',body,key)['job'];deadline=time.monotonic()+180
        while job['status'] in {'queued','running'} and time.monotonic()<deadline:
            time.sleep(1);job=call('/jobs/'+job['id'])
        result=job['result'];output=result.get('output',result.get('review'))
        self.status=job['status']
        return Message(text=json.dumps({'status':job['status'],'job_id':job['id'],'result':output,
            'preview':result.get('preview'),'reason':result.get('reason'),
            'message':'Pending jobs require inspection/reconciliation before any downstream action.' if job['status'] in {'queued','running','interrupted'} else None,
            'dashboard':'http://127.0.0.1:8765/'},ensure_ascii=False))
