import json
import tempfile
import unittest
from unittest.mock import patch
from forest_agents import planning_board as b
from forest_agents.bridge_runtime import JobRequest, Runtime
from forest_agents.job_store import JobStore


def spec(**kw):
    return b.TicketSpec(**dict(dict(id='NF-T099', title='Bounded planning test', owner_role='qa',
        objective='Plan one measured comparison.', acceptance=['Require actual evidence.'],
        allowed_paths=['docs/'], non_goals=['No implementation.']), **kw))


class PlanningTests(unittest.TestCase):
    def test_editable_contract_roundtrip_and_reject_unsafe_scope(self):
        self.assertEqual(b.parse_spec(b.render(spec())), spec())
        for path in ['../outside','/tmp/x','.git/config','OPENAI_API_SECRET_KEY.md']:
            with self.assertRaises(ValueError):spec(allowed_paths=[path])
        with self.assertRaises(ValueError):b.parse_spec(b.render(spec())+b.START)
        with self.assertRaises(ValueError):spec(owner_role='unknown')

    @patch.object(b,'issue',return_value={'state':'open'})
    def test_ready_requires_resolved_questions_and_closed_prerequisites(self,issue):
        for s in [spec(questions=['Missing images?']),spec(dependencies=[2]),spec(dependencies=[9])]:
            with self.assertRaises(ValueError):b.assert_ready({'number':9,'state':'open'},s)
        issue.return_value={'state':'closed'}
        b.assert_ready({'number':9,'state':'open'},spec(dependencies=[2]))

    @patch.object(b,'set_field')
    @patch.object(b,'issue',return_value={'state':'open'})
    @patch.object(b,'card',return_value={'id':'item','status':'Ready'})
    def test_stale_state_and_open_issue_done_are_rejected(self,card,issue,write):
        for command in [b.BoardCommand(action='set_state',issue=9,state='Blocked',expected_state='Todo',reason='Need images'),
                        b.BoardCommand(action='set_state',issue=9,state='Done',expected_state='Ready')]:
            with self.assertRaises(ValueError):b.set_state(command)
        write.assert_not_called()

    def test_offline_board_never_calls_github_and_old_requests_keep_shape(self):
        request=JobRequest(operation='plan_feature',request='Plan one tree').checked()
        self.assertNotIn('board_request',request);self.assertNotIn('ticket_issue',request)
        with tempfile.TemporaryDirectory() as td:
            store=JobStore(td)
            try:
                jid,_=store.submit(JobRequest(operation='planning_board',request='Inspect the board',board_request=b.BoardCommand(action='inspect')).checked(),'offline-board')
                with patch.object(b,'inspect',side_effect=AssertionError('Network offline')):Runtime(store).execute(jid)
                self.assertEqual(store.get(jid)['status'],'prepared_offline')
            finally:store.close()

    @patch.object(b,'connection',return_value={'repo':'owner/repo'})
    @patch.object(b,'set_field')
    @patch.object(b,'card',return_value={'id':'item','status':'Ready','ownerRole':'qa'})
    @patch.object(b,'issue')
    def test_dispatch_is_single_flight_and_retains_child_before_publication(self,issue,card,write,config):
        issue.return_value={'number':9,'state':'open','html_url':'https://github.com/owner/repo/issues/9','body':b.render(spec())}
        with tempfile.TemporaryDirectory() as td:
            store=JobStore(td);calls=[]
            def submit(body,key):calls.append(body);return store.submit(JobRequest.model_validate(body).checked(),key)
            try:
                command=b.BoardCommand(action='dispatch_plan',issue=9)
                first=b.dispatch_plan(command,store,submit)
                # A changed visible state must not launch another same-contract session.
                card.return_value['status']='In Progress'
                second=b.dispatch_plan(command,store,submit)
                self.assertEqual(first['job_id'],second['job_id']);self.assertTrue(second['reused']);self.assertEqual(len(calls),1)
                self.assertEqual(store.events(first['job_id'])[-1]['kind'],'board_dispatch_created')
                # A revised contract is still blocked while the first run is unresolved.
                issue.return_value['body']=b.render(spec(objective='Plan another measured comparison.'))
                with self.assertRaises(ValueError):b.dispatch_plan(command,store,submit)
            finally:store.close()

    @patch.object(b,'connection',return_value={'repo':'owner/repo'})
    @patch.object(b,'set_field')
    @patch.object(b,'card',return_value={'id':'item','status':'Ready','ownerRole':'rendering'})
    @patch.object(b,'issue')
    def test_dispatch_rejects_role_drift(self,issue,card,write,config):
        issue.return_value={'number':9,'state':'open','body':b.render(spec())}
        with tempfile.TemporaryDirectory() as td:
            store=JobStore(td)
            try:
                with self.assertRaises(ValueError):b.dispatch_plan(b.BoardCommand(action='dispatch_plan',issue=9),store,lambda *a:self.fail('Submitted'))
                write.assert_not_called()
            finally:store.close()

    @patch.object(b,'api')
    @patch.object(b,'gh',return_value=[])
    @patch.object(b,'connection',return_value={'repo':'owner/repo'})
    @patch.object(b,'set_field')
    @patch.object(b,'issue')
    @patch.object(b,'card',return_value={'id':'item','status':'In Progress','agentJob':'job-1'})
    def test_handover_moves_to_review_and_preserves_human_changes(self,card,issue,write,config,gh,api):
        issue.return_value={'body':b.render(spec())}
        job={'id':'job-1','status':'agent_complete','request':{'ticket_issue':9,'target_role':'qa','shared_context':json.dumps({'ticket_spec':spec().model_dump()})},
             'result':{'handover':{'status':'COMPLETE','recommendation':'Review the protocol.'}}}
        result=b.sync_job(job)
        self.assertEqual(result['state'],'In Review');self.assertEqual(result['feature_acceptance'],'not_performed')
        self.assertNotIn(unittest.mock.call('item','Status','Done'),write.call_args_list)
        api.assert_called_once()
        write.reset_mock();api.reset_mock()
        card.return_value['status']='Blocked'
        self.assertEqual(b.sync_job(job)['board_update'],'preserved_external_change')
        write.assert_not_called();api.assert_not_called()
        card.return_value['status']='In Progress';issue.return_value['body']=b.render(spec(objective='A newly revised work contract.'))
        self.assertEqual(b.sync_job(job)['board_update'],'preserved_changed_ticket_contract')
        write.assert_not_called()

    @patch.object(b,'connection',return_value={'repo':'owner/repo'})
    @patch.object(b,'card',return_value={'id':'item','status':'In Progress','agentJob':'job-1'})
    @patch.object(b,'issue')
    @patch.object(b,'set_field')
    @patch.object(b,'api')
    @patch.object(b,'gh',return_value=[{'body':'<!-- nordic-ticket-job:job-1 -->'}])
    def test_sync_deduplicates_a_comment_after_partial_publication(self,gh,api,write,issue,card,config):
        issue.return_value={'body':b.render(spec())}
        job={'id':'job-1','status':'agent_complete','request':{'ticket_issue':9,'target_role':'qa','shared_context':json.dumps({'ticket_spec':spec().model_dump()})},
             'result':{'handover':{'status':'COMPLETE','recommendation':'Review the protocol.'}}}
        self.assertEqual(b.sync_job(job)['state'],'In Review')
        api.assert_not_called()

    @patch.object(b,'connection',return_value={'repo':'owner/repo'})
    @patch.object(b,'issue',return_value={'body':b.render(spec(kind='Spike'))})
    @patch.object(b,'api',return_value={'state':'open','base':{'repo':{'full_name':'owner/repo'}}})
    def test_pr_closing_requires_concrete_task(self,api,issue,config):
        with self.assertRaises(ValueError):b.link_pr(b.BoardCommand(action='link_pr',issue=9,pr=11,close_on_merge=True))
        self.assertEqual(api.call_count,1)  # Read only; no PR write.

    @patch.object(b,'connection',return_value={'id':'board'})
    @patch.object(b,'gql')
    def test_incomplete_field_inventory_fails_closed(self,gql,config):
        gql.return_value={'node':{'fields':{'pageInfo':{'hasNextPage':True},'nodes':[]}}}
        with self.assertRaises(ValueError):b.list_fields()

    @patch.object(b,'connection',return_value={'id':'board'})
    @patch.object(b,'list_fields',return_value=[{'id':'status','name':'Status','options':[{'id':'ready','name':'Ready'}]}])
    @patch.object(b,'gql')
    def test_unknown_status_never_reaches_mutation(self,gql,fields,config):
        with self.assertRaises(ValueError):b.set_field('item','Status','Invented state')
        gql.assert_not_called()

    @patch.object(b,'connection',return_value={'id':'board'})
    @patch.object(b,'gql')
    def test_board_inventory_paginates_and_retains_editable_fields(self,gql,config):
        row={'id':'item','content':{'title':'A task','url':'https://github.com/owner/repo/issues/9'},
             'fieldValues':{'pageInfo':{'hasNextPage':False},'nodes':[{'name':'Ready','field':{'name':'Status'}},{'text':'qa','field':{'name':'Owner Role'}}]}}
        gql.side_effect=[{'node':{'items':{'pageInfo':{'hasNextPage':True,'endCursor':'next'},'nodes':[row]}}},
                         {'node':{'items':{'pageInfo':{'hasNextPage':False,'endCursor':None},'nodes':[]}}}]
        items=b.inventory()
        self.assertEqual(b.value(items[0],'Status'),'Ready');self.assertEqual(b.value(items[0],'Owner Role'),'qa')
        self.assertEqual(gql.call_args.args[1]['after'],'next')


if __name__=='__main__':unittest.main()
