import copy
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

from forest_agents.bridge_runtime import JobRequest, Runtime
from forest_agents.job_store import JobStore
from forest_agents.pr_delivery import classify, merge_gate, review_digest, changed_lines, create
from forest_agents.pr_review import LocalPRReview, PROFILE
from forest_agents.workflow import load_config, instructions_for


def sample():
    files=[{'filename':'docs/example.md','status':'modified','additions':1,'deletions':1,'patch':'@@ -1 +1 @@\n-before\n+after'}]
    return {'repo':'donnybystrom/nordic-forest','number':42,'head_sha':'a'*40,'base_sha':'b'*40,'base_branch':'main',
            'head_repo':'donnybystrom/nordic-forest','author':'shared-account','state':'open','draft':False,
            'files':files,'classification':classify(files),'threads':[],'reviews':[]}


def approval(s,role):
    config=load_config()
    review={'scope':'code_review_only',**{k:s[k] for k in ['repo','number','head_sha','base_sha']},
            'diff_sha256':review_digest(s),'review_role':role,'verdict':'approve','summary':'Reviewed the complete small diff.','findings':[],'limitations':[]}
    session={'status':'completed','agent_id':config['roles'][role]['platform_agent_id'],
             'execution_profile_sha256':hashlib.sha256(PROFILE.format(role_name=config['roles'][role]['name']).encode()).hexdigest(),
             'instruction_sha256':hashlib.sha256(instructions_for(role,config).encode()).hexdigest(),'output_schema':'LocalPRReview',
             'observed_turn_status':'completed','handover':copy.deepcopy(review)}
    return {'status':'pr_review_complete','request':{'operation':'review_pr','target_role':role},
            'result':{'review':review,'sessions':{'pr_review_'+role:session}}}


CHECKS=[{'name':'contracts','bucket':'pass','workflow':'Agent harness checks'}]


class DeliveryTests(unittest.TestCase):
    def test_two_local_roles_can_approve_with_one_github_account(self):
        s=sample();jobs=[approval(s,r) for r in ['curator','qa']]
        self.assertTrue(merge_gate(s,CHECKS,jobs)['allowed'])
        self.assertFalse(merge_gate(s,CHECKS,[jobs[0],jobs[0]])['allowed'])
    def test_stale_or_mismatched_head_base_patch_and_profile_cannot_merge(self):
        for field in ['head_sha','base_sha','diff_sha256','repo','number','review_role']:
            s=sample();jobs=[approval(s,r) for r in ['curator','qa']]
            jobs[0]['result']['review'][field]='wrong' if field!='number' else 99
            self.assertFalse(merge_gate(s,CHECKS,jobs)['allowed'],field)
        s=sample();jobs=[approval(s,r) for r in ['curator','qa']]
        jobs[0]['result']['sessions']['pr_review_curator']['execution_profile_sha256']='stale'
        self.assertFalse(merge_gate(s,CHECKS,jobs)['allowed'])
    def test_native_account_approval_or_planning_completion_does_not_substitute_for_role_review(self):
        s=sample();s['reviews']=[{'user':{'login':'shared-account'},'state':'APPROVED','commit_id':s['head_sha']}]
        self.assertFalse(merge_gate(s,CHECKS,[])['allowed'])
        jobs=[approval(s,r) for r in ['curator','qa']];jobs[0]['request']['operation']='run_agent'
        self.assertFalse(merge_gate(s,CHECKS,jobs)['allowed'])
    def test_blocking_findings_pending_checks_and_unresolved_threads_block(self):
        for mutate in ['finding','check','thread','changes','draft']:
            s=sample();jobs=[approval(s,r) for r in ['curator','qa']];checks=copy.deepcopy(CHECKS)
            if mutate=='finding':jobs[0]['result']['review']['findings']=[{'severity':'P1','path':'docs/example.md','line':1,'problem':'Wrong','requested_change':'Fix','validation':'Inspect'}]
            if mutate=='check':checks[0]['bucket']='pending'
            if mutate=='thread':s['threads']=[{'isResolved':False,'isOutdated':True}]
            if mutate=='changes':s['reviews']=[{'user':{'login':'someone'},'state':'CHANGES_REQUESTED'}]
            if mutate=='draft':s['draft']=True
            self.assertFalse(merge_gate(s,checks,jobs)['allowed'],mutate)
    def test_sensitive_or_large_or_deleted_docs_are_not_delegated(self):
        for name in ['config/agents.json','.github/workflows/ci.yml','prompts/shared.txt','docs/PROJECT.md','docs/decisions/0001-engine.md','forest_agents/new.py','unknown.txt']:
            f={'filename':name,'status':'modified','additions':1,'deletions':0}
            self.assertEqual(classify([f])['merge_lane'],'owned_review',name)
        for extra in [{'additions':201},{'status':'removed'},{'previous_filename':'config/agents.json'},{'status':'renamed'}]:
            f=dict(sample()['files'][0],**extra);self.assertEqual(classify([f])['merge_lane'],'owned_review')
    def test_check_with_same_name_in_different_workflow_is_not_trusted(self):
        s=sample();jobs=[approval(s,r) for r in ['curator','qa']]
        self.assertFalse(merge_gate(s,[dict(CHECKS[0],workflow='untrusted')],jobs)['allowed'])
    def test_create_reuses_existing_pr_without_duplication(self):
        with patch('forest_agents.pr_delivery.api',side_effect=[{},[{'html_url':'https://github.com/donnybystrom/nordic-forest/pull/6','number':6,'draft':True}]]) as api:
            result=create('codex/langflow-bridge','Existing feature','Actual evidence')
        self.assertTrue(result['reused']);self.assertEqual(api.call_count,2)
        with self.assertRaises(ValueError):create('main','Bad','No')
    def test_merge_refuses_head_change_after_review(self):
        from forest_agents.pr_delivery import merge_small
        s=sample();changed=copy.deepcopy(s);changed['head_sha']='c'*40
        jobs=[approval(s,r) for r in ['curator','qa']]
        with patch('forest_agents.job_store.JobStore') as store, patch('forest_agents.pr_delivery.snapshot',side_effect=[s,changed]), patch('forest_agents.pr_delivery.github',return_value=CHECKS), patch('forest_agents.pr_delivery.api') as api:
            store.return_value.get.side_effect=jobs
            with self.assertRaises(ValueError):merge_small(42,['00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000002'],apply=True)
            api.assert_not_called()
    def test_delegated_merge_uses_exact_head_and_returns_revert_identity(self):
        from forest_agents.pr_delivery import merge_small
        s=sample();jobs=[approval(s,r) for r in ['curator','qa']]
        with patch('forest_agents.job_store.JobStore') as store, patch('forest_agents.pr_delivery.snapshot',return_value=s), patch('forest_agents.pr_delivery.github',return_value=CHECKS), patch('forest_agents.pr_delivery.api',return_value={'merged':True,'sha':'d'*40}) as api:
            store.return_value.get.side_effect=jobs
            result=merge_small(42,['00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000002'],apply=True)
            self.assertTrue(result['merged']);self.assertEqual(result['sha'],'d'*40)
            self.assertEqual(api.call_args.args[1],{'sha':s['head_sha'],'merge_method':'squash'})
            self.assertIn('Revert',result['rollback'])
    def test_inline_comments_only_use_actual_added_lines(self):
        self.assertEqual(changed_lines('@@ -2,3 +2,3 @@\n context\n-old\n+new\n rest'),{3})
    def test_offline_broker_and_review_make_no_github_or_model_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            store=JobStore(directory)
            try:
                for body in [JobRequest(operation='github_pr',request='Inspect',github_request={'action':'inspect'}).checked(),
                             JobRequest(operation='review_pr',request='Review',target_role='qa').checked()]:
                    jid,_=store.submit(body,'offline-'+body['operation'])
                    with patch('forest_agents.pr_delivery.snapshot',side_effect=AssertionError('Network called')):
                        Runtime(store,client_factory=lambda: self.fail('Provider called')).execute(jid)
                    self.assertEqual(store.get(jid)['status'],'prepared_offline')
            finally:store.close()
    def test_existing_request_serialization_does_not_change_idempotency_keys(self):
        old=JobRequest(operation='run_agent',request='Existing',target_role='qa').checked()
        self.assertNotIn('github_request',old);self.assertNotIn('pr_number',old)
    def test_profile_has_no_tools_and_is_ephemeral_with_bound_assignment(self):
        s=sample();job=approval(s,'qa');output=LocalPRReview.model_validate(job['result']['review'])
        self.assertEqual(output.scope,'code_review_only')
        with self.assertRaises(ValueError):LocalPRReview.model_validate(dict(output.model_dump(),scope='planning_only'))


if __name__=='__main__':unittest.main()
