"""Narrow local PR broker tool for a Langflow orchestration flow."""
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


class NordicPRControl(Component):
    display_name='NF · PR Control'
    name='NordicPRControl'
    icon='GitPullRequest'
    description='Local PR creation, inspection, role reviews and gated small-documentation merge through one shared GitHub account. Preview by default.'
    inputs=[MessageTextInput(name='request_json',display_name='PR command JSON',tool_mode=True,required=True,
                value='{"action":"inspect","number":6}',info='Actions: inspect, create, overview, review_pr (number, role), publish_review (number, review_job), merge_small (number, review_jobs). Repository is fixed by local policy.'),
            BoolInput(name='live',display_name='Execute live',value=False,info='Allows GitHub reads/writes or a billed code-review session. Merge still requires the local policy and exact-revision evidence.'),
            StrInput(name='run_key',display_name='Submission key',value='pr-1',advanced=True)]
    outputs=[Output(name='message',display_name='PR result',method='execute')]

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
        if command.get('action')=='review_pr':
            if set(command)!={'action','number','role'}:raise ValueError('Use only action, number and role for review_pr')
            body={'operation':'review_pr','request':'Review the complete PR diff with the local code-review execution profile.',
                  'target_role':command['role'],'pr_number':command['number'],'live':bool(self.live)}
        else: body={'operation':'github_pr','request':'Execute the bounded local GitHub PR command.','github_request':command,'live':bool(self.live)}
        key=hashlib.sha256(json.dumps({'body':body,'run_key':self.run_key},sort_keys=True).encode()).hexdigest()
        if command.get('action')=='inspect': key=str(uuid.uuid4())  # Always read current GitHub state.
        job=call('/jobs',body,key)['job'];deadline=time.monotonic()+180
        while job['status'] in {'queued','running'} and time.monotonic()<deadline:
            time.sleep(1);job=call('/jobs/'+job['id'])
        result=job['result'];output=result.get('output',result.get('review'))
        if command.get('action')=='inspect' and isinstance(output,dict) and 'files' in output:
            output={k:output[k] for k in ['repo','number','url','state','draft','head_sha','base_sha','classification']}
            output['message']='Full files, comments and review threads are retained in the local job and visible in GitHub.'
        self.status=job['status']
        return Message(text=json.dumps({'status':job['status'],'job_id':job['id'],'result':output,
            'preview':result.get('planned_command'),'reason':result.get('reason'),
            'message':'Pending jobs require inspection/reconciliation before any downstream action.' if job['status'] in {'queued','running','interrupted'} else None,
            'dashboard':'http://127.0.0.1:8765/'},ensure_ascii=False))
