import copy
import json
import subprocess
import unittest
from unittest.mock import patch
from forest_agents.github_board import ROOT, apply, gh, preview


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.plan=json.loads((ROOT/'data/github-project-plan.json').read_text())
    def test_portable_parent_graph_and_acceptance_are_retained(self):
        packet=preview(self.plan)
        self.assertEqual(packet['remote_writes'],0)
        self.assertTrue(all('Acceptance:' in i['body'] for i in packet['items']))
        story=next(i for i in packet['items'] if i['kind']=='Story')
        self.assertIn(story['parent'],story['body'])
    def test_dangling_parent_fails_before_remote_write(self):
        plan=copy.deepcopy(self.plan);plan['items'][0]['parent']='missing'
        with patch('forest_agents.github_board.gh') as api:
            with self.assertRaises(ValueError):apply(plan,'donnybystrom')
            api.assert_not_called()
    def test_repo_owner_must_be_explicit_and_match(self):
        with patch('forest_agents.github_board.gh') as api:
            with self.assertRaises(ValueError):apply(self.plan,'owner','different/repo')
            api.assert_not_called()
    def test_cli_error_never_echoes_credentials_or_provider_body(self):
        result=subprocess.CompletedProcess([],1,'','sensitive provider text')
        with patch('forest_agents.github_board.subprocess.run',return_value=result):
            with self.assertRaises(RuntimeError) as e:gh('api','user')
        self.assertNotIn('sensitive',str(e.exception))


if __name__=='__main__':unittest.main()
