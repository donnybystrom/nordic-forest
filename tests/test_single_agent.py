import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

from forest_agents.bridge_runtime import JobRequest, Runtime
from forest_agents.job_store import JobStore
from forest_agents.workflow import ROOT, load_config

HANDOVER = {'scope': 'planning_only', 'status': 'COMPLETE', 'recommendation': 'Inspect evidence.',
            'claims': [], 'milestones': [], 'open_questions': [], 'critique': [], 'next_owner': 'qa'}


class SingleAgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = JobStore(self.tmp.name)
    def tearDown(self):
        self.store.close(); self.tmp.cleanup()
    def test_all_roles_prepare_without_provider_and_pin_correct_identity(self):
        config = load_config()
        runtime = Runtime(self.store, client_factory=lambda: self.fail('Provider called offline'))
        for role, spec in config['roles'].items():
            with self.subTest(role=role):
                body = JobRequest(operation='run_agent', request='Inspect the plan', target_role=role,
                                  shared_context='A provisional upstream finding').checked()
                jid, _ = self.store.submit(body, 'offline-' + role)
                runtime.execute(jid); job = self.store.get(jid)
                self.assertEqual(job['status'], 'prepared_offline')
                self.assertEqual(job['result']['agent']['agent_id'], spec['platform_agent_id'])
                self.assertEqual(job['result']['remote_calls'], 0)
                payload = json.loads(job['result']['payload'])
                self.assertEqual(payload['upstream_context'], body['shared_context'])
                self.assertEqual(payload['assigned_role'], role)
    def test_one_consultation_has_one_stage_and_propagates_handover(self):
        body = JobRequest(operation='run_agent', request='Review one proposal', target_role='qa', live=True).checked()
        jid, _ = self.store.submit(body, 'one-consultation')
        with patch.object(Runtime, 'stage', return_value=HANDOVER) as stage:
            Runtime(self.store).execute(jid)
        self.assertEqual(stage.call_count, 1)
        self.assertEqual(stage.call_args.args[2], 'qa')
        job = self.store.get(jid)
        self.assertEqual(job['status'], 'agent_complete')
        self.assertEqual(job['result']['handover'], HANDOVER)
        self.assertEqual(job['result']['feature_acceptance'], 'not_performed')
    def test_unknown_roles_and_secrets_in_upstream_context_rejected(self):
        for extra in [{'target_role': 'agent_external'}, {'shared_context': 'sk-' + 'x'*40}, {'shared_context': 'x'*20001}]:
            with self.assertRaises(ValueError):
                JobRequest(operation='run_agent', request='Inspect', **extra).checked()
    def test_context_participates_in_idempotency_and_snapshots(self):
        a = JobRequest(operation='run_agent', request='Inspect', shared_context='first').checked()
        b = JobRequest(operation='run_agent', request='Inspect', shared_context='second').checked()
        self.assertNotEqual(hashlib.sha256(json.dumps(a).encode()).hexdigest(), hashlib.sha256(json.dumps(b).encode()).hexdigest())
        jid, _ = self.store.submit(a, 'frozen-context')
        Runtime(self.store).execute(jid)
        result = self.store.get(jid)['result']
        self.assertEqual(json.loads(result['payload'])['upstream_context'], 'first')
        self.assertIn('asset_analysis', result['role_hashes'])

    def test_installed_component_templates_bind_every_role_and_expose_only_task_context(self):
        import ast
        for role in load_config()['roles']:
            with self.subTest(role=role):
                source = json.loads((ROOT / 'integrations/langflow/agents' / (role + '.json')).read_text())
                node = source['data']['nodes'][0]['data']['node']
                fields = node['template']
                self.assertTrue(source['is_component'])
                self.assertFalse(fields['live']['value'])
                self.assertEqual({k for k, v in fields.items() if isinstance(v, dict) and v.get('tool_mode')}, {'request_text', 'shared_context'})
                tree = ast.parse(fields['code']['value'])
                cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
                fixed_role = next(n.value.value for n in cls.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'role' for t in n.targets))
                self.assertEqual(fixed_role, role)
    def test_every_role_flow_connects_input_to_agent_and_agent_to_output(self):
        for role in load_config()['roles']:
            with self.subTest(role=role):
                flow = json.loads((ROOT / 'flows/langflow/agents' / (role + '.json')).read_text())
                inp, agent, out = flow['data']['nodes']
                self.assertEqual(inp['data']['type'], 'ChatInput')
                self.assertEqual(out['data']['type'], 'ChatOutput')
                self.assertFalse(flow['mcp_enabled'])
                edges = flow['data']['edges']
                self.assertEqual([(e['source'], e['target']) for e in edges], [(inp['id'], agent['id']), (agent['id'], out['id'])])


if __name__ == '__main__': unittest.main()
