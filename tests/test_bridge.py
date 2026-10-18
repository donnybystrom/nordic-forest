import hashlib
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from forest_agents.bridge_runtime import JobRequest, Runtime, UncertainDispatch
from forest_agents.bridge_server import Bridge, handler_for
from forest_agents.job_store import Conflict, JobStore, canonical
from forest_agents.workflow import instructions_for, load_config

HANDOVER = {'scope':'planning_only','status':'COMPLETE','recommendation':'Measure one tree.', 'claims':[], 'milestones':[], 'open_questions':[], 'critique':[], 'next_owner':'qa'}


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = JobStore(self.tmp.name)
        self.body = JobRequest(operation='plan_feature', request='Inspect one tree').checked()
    def tearDown(self):
        self.store.close();self.tmp.cleanup()
    def test_idempotency_and_changed_payload_conflict(self):
        jid,fresh=self.store.submit(self.body,'same-action');self.assertTrue(fresh)
        self.assertEqual(self.store.submit(self.body,'same-action'),(jid,False))
        with self.assertRaises(Conflict):self.store.submit(dict(self.body,request='different'),'same-action')
        self.assertEqual(len(self.store.list()),1)
    def test_restart_preserves_evidence_and_marks_inflight(self):
        jid,_=self.store.submit(self.body,'restart-test')
        self.store.update(jid,status='running',result={'session_id':'sess_saved'})
        self.store.close();self.store=JobStore(self.tmp.name);self.store.mark_interrupted()
        self.assertEqual(self.store.get(jid)['status'],'interrupted')
        self.assertEqual(self.store.get(jid)['result']['session_id'],'sess_saved')
    def test_cancel_is_persisted_but_does_not_claim_remote_stop(self):
        jid,_=self.store.submit(self.body,'cancel-test');self.store.cancel(jid)
        self.assertEqual(self.store.get(jid)['status'],'cancel_requested')
        self.assertTrue(self.store.get(jid)['cancelled'])
    def test_review_binds_hash_and_cannot_publish(self):
        jid,_=self.store.submit(dict(self.body,operation='propose_agent_change'),'review-test')
        result={'proposal':'candidate','publication':'not_performed'}
        self.store.update(jid,status='awaiting_review',result=result)
        with self.assertRaises(Conflict):self.store.decision(jid,'approve_direction','stale')
        digest=hashlib.sha256(canonical(result).encode()).hexdigest()
        r=self.store.decision(jid,'approve_direction',digest)
        self.assertEqual(r['result']['publication'],'not_performed')
        with self.assertRaises(ValueError):self.store.decision(jid,'publish',digest)
    def test_request_disallows_paths_tools_other_projects_and_credentials(self):
        for extra in [{'project':'beasts'},{'tools':['shell']},{'key_file':'secret'},{'live':'true'},{'request':'sk-'+'x'*30}]:
            with self.assertRaises(ValueError):JobRequest.model_validate(dict(self.body,**extra)).checked()
    def test_offline_execution_does_not_read_key_or_call_provider(self):
        jid,_=self.store.submit(self.body,'offline-test')
        runtime=Runtime(self.store,client_factory=lambda: self.fail('Provider called offline'))
        runtime.execute(jid)
        job=self.store.get(jid)
        self.assertEqual(job['status'],'prepared_offline')
        self.assertEqual(job['result']['packet']['remote_calls'],0)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=JobStore(self.tmp.name)
        self.body=JobRequest(operation='plan_feature',request='Inspect one tree',live=True).checked()
        self.jid,_=self.store.submit(self.body,'runtime-test')
    def tearDown(self):self.store.close();self.tmp.cleanup()
    def test_uncertain_create_is_never_repeated(self):
        self.store.update(self.jid,result={'sessions':{'product_brief':{'status':'dispatching'}}})
        runtime=Runtime(self.store,client_factory=lambda:self.fail('Provider retried'))
        with self.assertRaises(UncertainDispatch):runtime.stage(self.jid,load_config(),'product_lead','task','product_brief')
    def test_completed_saved_items_are_validated_and_reused(self):
        config=load_config();calls=[]
        saved=SimpleNamespace(id=config['roles']['product_lead']['platform_agent_id'],instructions=instructions_for('product_lead',config),model='existing-model')
        def create(**kwargs):calls.append(kwargs);return SimpleNamespace(id='sess_test')
        sessions=SimpleNamespace(create=create,retrieve=lambda sid:SimpleNamespace(required_actions=[]),
          turns=SimpleNamespace(list=lambda *a,**k:SimpleNamespace(data=[SimpleNamespace(id='turn_test',status='completed',usage=None)])),
          items=SimpleNamespace(list=lambda *a,**k:SimpleNamespace(data=[{'type':'message','role':'assistant','content':[{'type':'output_text','text':json.dumps(HANDOVER)}]}])))
        client=SimpleNamespace(beta=SimpleNamespace(agents=SimpleNamespace(retrieve=lambda aid:saved,sessions=sessions)),close=lambda:None)
        runtime=Runtime(self.store,client_factory=lambda:client)
        first=runtime.stage(self.jid,config,'product_lead','task','product_brief')
        self.assertEqual(first,HANDOVER)
        self.assertEqual(runtime.stage(self.jid,config,'product_lead','task','product_brief'),HANDOVER)
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0]['agent_id'],saved.id)
        self.assertEqual(calls[0]['agent']['tools'],[])
        self.assertFalse(calls[0]['agent']['multi_agent']['enabled'])
    def test_idle_session_does_not_certify_success(self):
        # A completed output is required; an invalid saved handover cannot pass.
        config=load_config();saved=SimpleNamespace(id=config['roles']['product_lead']['platform_agent_id'],instructions=instructions_for('product_lead',config),model='existing-model')
        sessions=SimpleNamespace(create=lambda **kw:SimpleNamespace(id='sess_test'),retrieve=lambda sid:SimpleNamespace(required_actions=[]),
          turns=SimpleNamespace(list=lambda *a,**k:SimpleNamespace(data=[SimpleNamespace(id='turn_test',status='completed',usage=None)])),
          items=SimpleNamespace(list=lambda *a,**k:SimpleNamespace(data=[])))
        client=SimpleNamespace(beta=SimpleNamespace(agents=SimpleNamespace(retrieve=lambda aid:saved,sessions=sessions)),close=lambda:None)
        with self.assertRaises(ValueError):Runtime(self.store,client_factory=lambda:client).stage(self.jid,config,'product_lead','task','product_brief')
    def test_completed_stage_needs_no_client_or_new_call(self):
        self.store.update(self.jid,result={'sessions':{'product_brief':{'status':'completed','handover':HANDOVER}}})
        runtime=Runtime(self.store,client_factory=lambda:self.fail('Repeated billing'))
        self.assertEqual(runtime.stage(self.jid,load_config(),'product_lead','task','product_brief'),HANDOVER)


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),lambda *a:None)
        self.port=self.server.server_port
        self.bridge=Bridge(self.tmp.name,port=self.port)
        self.server.RequestHandlerClass=handler_for(self.bridge)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=self.bridge.origin
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.bridge.close();self.tmp.cleanup()
    def request(self,path,body=None,auth=False,**headers):
        if auth:headers['Authorization']='Bearer '+self.bridge.token
        if body is not None:headers['Content-Type']='application/json'
        req=urllib.request.Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        with urllib.request.urlopen(req,timeout=3) as r:return r.status,json.load(r)
    def test_auth_origin_and_host_enforcement(self):
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/jobs')
        self.assertEqual(e.exception.code,401)
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/jobs',auth=True,Origin='https://other.example')
        self.assertEqual(e.exception.code,403)
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/health',Host='attacker.example')
        self.assertEqual(e.exception.code,403)
    def test_duplicate_http_submission_keeps_one_job(self):
        body={'operation':'plan_feature','request':'one small feature'}
        a=self.request('/jobs',body,True,**{'Idempotency-Key':'http-same-action'})
        b=self.request('/jobs',body,True,**{'Idempotency-Key':'http-same-action'})
        self.assertEqual(a[1]['job']['id'],b[1]['job']['id']);self.assertFalse(b[1]['created'])
    def test_bearer_model_client_cannot_cast_browser_review(self):
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/jobs/unknown/decision',{},True)
        self.assertEqual(e.exception.code,403)
    def test_unknown_remote_dispatch_cannot_resume(self):
        jid,_=self.bridge.store.submit(JobRequest(operation='plan_feature',request='one feature').checked(),'uncertain-http')
        self.bridge.store.update(jid,status='interrupted',result={'sessions':{'one':{'status':'dispatching'}}})
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/jobs/'+jid+'/resume',{},True)
        self.assertEqual(e.exception.code,409)


if __name__=='__main__':unittest.main()
