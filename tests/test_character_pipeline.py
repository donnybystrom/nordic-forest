import hashlib
import json
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from forest_agents import character_pipeline as c
from forest_agents.bridge_runtime import JobRequest, Runtime
from forest_agents.job_store import Conflict, JobStore, canonical


class CharacterPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = JobStore(self.root / 'runs/control')
        self.image_path = 'assets/work/characters/test/front.png'
        target = self.root / self.image_path
        target.parent.mkdir(parents=True)
        Image.new('RGB', (32, 32), (90, 80, 70)).save(target)
        self.command = c.CharacterCommand(action='prepare', views=[c.CharacterView(view='front', path=self.image_path)])
        self.package = c.prepare(self.command, self.root)
        body = JobRequest(operation='character_pipeline', request='Prepare test character',
                          character_request=self.command).checked()
        self.jid, _ = self.store.submit(body, 'prepare-test-character')
        self.store.update(self.jid, status='awaiting_review', result=self.package)
        self.client = Mock()
        self.client.request.return_value = {'balance': 216.5}
        self.client.submit.return_value = {'uuid': str(uuid.uuid4()), 'jobs': {'subscription_key': 'private-subscription'}, 'consumed': 1.5}
        self.factory = Mock(return_value=self.client)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def approve(self):
        digest = hashlib.sha256(canonical(self.package).encode()).hexdigest()
        self.store.decision(self.jid, 'approve_generation', digest)

    def call(self, action, live=True):
        return c.execute(c.CharacterCommand(action=action, source_job_id=self.jid), self.store,
                         live=live, root=self.root, client_factory=self.factory)

    def state(self):
        return self.store.directory / 'artifacts' / self.jid / 'rodin-state.json'

    def test_offline_submission_cannot_read_credentials_or_call_provider(self):
        result = self.call('submit_rodin', live=False)
        self.assertEqual(result['provider_calls'], 0)
        self.factory.assert_not_called()

    def test_generation_requires_matching_review_type_and_hash(self):
        with self.assertRaises(Conflict):
            self.call('submit_rodin')
        with self.assertRaises(Conflict):
            self.store.decision(self.jid, 'approve_direction', hashlib.sha256(canonical(self.package).encode()).hexdigest())
        with self.assertRaises(Conflict):
            self.store.decision(self.jid, 'approve_generation', 'stale')
        self.factory.assert_not_called()

    def test_changed_input_invalidates_approval_before_provider_call(self):
        self.approve()
        Image.new('RGB', (32, 32), (0, 0, 0)).save(self.root / self.image_path)
        with self.assertRaises(Conflict):
            self.call('submit_rodin')
        self.factory.assert_not_called()

    def test_paid_create_is_reused_even_with_new_stage_job(self):
        self.approve()
        result = self.call('submit_rodin')
        self.assertEqual(result['rodin']['consumed_credits'], 1.5)
        self.assertNotIn('subscription_key', result['rodin'])
        self.assertTrue(self.call('submit_rodin')['reused'])
        self.client.submit.assert_called_once()

    def test_form_encoding_matches_provider_csv_addons_and_image_mime(self):
        client = object.__new__(c.RodinClient)
        client.request = Mock(return_value={})
        client.submit(self.package, self.root)
        body = client.request.call_args.args[1]
        self.assertIn(b'name="addons"\r\n\r\nHighPack\r\n', body)
        self.assertIn(b'Content-Type: image/png\r\n', body)
        self.assertNotIn(b'["HighPack"]', body)

    def test_rejection_receipt_is_retained_without_raw_provider_error(self):
        self.approve()
        self.client.submit.side_effect = c.RodinError(400, 'INVALID_REQUEST', rejected=True)
        result = self.call('submit_rodin')['rodin']
        self.assertEqual(result['status'], 'rejected')
        self.assertEqual(result['error_receipt'], {'http_status': 400, 'provider_code': 'INVALID_REQUEST'})
        self.assertTrue(self.call('submit_rodin')['reused'])
        self.client.submit.assert_called_once()

    def test_lost_create_reply_is_durable_and_never_retried_after_restart(self):
        self.approve()
        def fail_after_dispatch(*args):
            self.assertEqual(json.loads(self.state().read_text())['status'], 'dispatch_unknown')
            raise TimeoutError('lost reply')
        self.client.submit.side_effect = fail_after_dispatch
        with self.assertRaises(TimeoutError):
            self.call('submit_rodin')
        self.store.close()
        self.store = JobStore(self.root / 'runs/control')
        result = self.call('submit_rodin')
        self.assertTrue(result['reused'])
        self.assertEqual(result['rodin']['status'], 'dispatch_unknown')
        self.client.submit.assert_called_once()

    def test_poll_requires_nonempty_all_done_and_stops_on_failure(self):
        self.approve()
        self.call('submit_rodin')
        for statuses, expected in [([], None), (['Done', 'Generating'], 'generating'),
                                   (['Done', 'Failed'], 'failed'), (['Done', 'Done'], 'ready_to_download')]:
            state = json.loads(self.state().read_text())
            state.update(status='generating', next_poll_at=0)
            c.save_state(self.state(), state)
            self.client.request.return_value = {'jobs': [{'status': s} for s in statuses]}
            if expected is None:
                with self.assertRaises(ValueError):
                    self.call('poll_rodin')
            else:
                self.assertEqual(self.call('poll_rodin')['rodin']['status'], expected)
        state['status'] = 'failed'
        c.save_state(self.state(), state)
        self.client.request.reset_mock()
        self.call('poll_rodin')
        self.client.request.assert_not_called()

    def test_poll_backoff_is_durable_and_early_fetch_is_rejected(self):
        self.approve()
        self.call('submit_rodin')
        self.client.request.reset_mock()
        self.call('poll_rodin')
        self.client.request.assert_not_called()
        with self.assertRaises(Conflict):
            self.call('fetch_rodin')

    def test_sheet_split_preserves_pixels_and_does_not_call_provider(self):
        sheet = Image.new('RGB', (32, 32))
        for y in range(32):
            for x in range(32):
                sheet.putpixel((x, y), (x, y, x + y))
        sheet.save(self.root / self.image_path)
        cmd = c.CharacterCommand(action='split_sheet', sheet_path=self.image_path,
                                 panels=[c.SheetPanel(view='front', box=[3, 2, 27, 30])])
        result = c.execute(cmd, self.store, live=True, root=self.root, client_factory=self.factory)
        with Image.open(self.root / result['views'][0]['path']) as crop:
            self.assertEqual(crop.tobytes(), sheet.crop((3, 2, 27, 30)).tobytes())
        self.assertEqual(result, c.split_sheet(cmd, self.root))
        self.factory.assert_not_called()

    def test_reference_and_motion_sheets_cannot_be_sent_as_views(self):
        with self.assertRaises(ValueError):
            c.prepare(self.command.model_copy(update={'motion_references': [self.image_path]}), self.root)
        result = c.prepare(c.CharacterCommand(reference_sheets=[self.image_path]), self.root)
        self.assertFalse(result['ready_for_generation_review'])
        self.assertEqual(result['later_stages']['active_ragdoll'], 'not_implemented')

    def test_paths_and_symlinks_cannot_escape_character_inputs(self):
        for path in ['.RODIN_API_KEY', '../front.png', '/tmp/front.png']:
            with self.assertRaises(ValueError):
                c.file_record(path, self.root)
        outside = self.root / 'private.png'
        Image.new('RGB', (32, 32)).save(outside)
        (self.root / 'assets/work/characters/test/link.png').symlink_to(outside)
        with self.assertRaises(ValueError):
            c.file_record('assets/work/characters/test/link.png', self.root)

    def test_fetch_uses_top_level_uuid_and_records_actual_billing(self):
        self.approve()
        self.call('submit_rodin')
        state = json.loads(self.state().read_text())
        state['status'] = 'ready_to_download'
        c.save_state(self.state(), state)
        task = state['task_uuid']
        self.client.request.side_effect = [
            {'list': [{'name': 'model.glb', 'url': 'https://cdn.example/model'}]},
            {'balance': 215, 'usage': [{'task_uuid': task, 'item': 'rodin', 'amount': 1.5},
                                     {'task_uuid': 'other', 'amount': 4}]},
        ]
        def download(url, target, limit):
            target.write_bytes(b'glb-test')
            return {'path': str(target), 'sha256': hashlib.sha256(b'glb-test').hexdigest(), 'bytes': 8}
        with patch.object(c, 'fetch_file', side_effect=download):
            result = self.call('fetch_rodin')['rodin']
        self.assertEqual(self.client.request.call_args_list[-2].args, ('download', {'task_uuid': task}))
        self.assertEqual(result['balance_after_credits'], 215)
        self.assertEqual(len(result['usage_for_task']), 1)
        self.assertTrue(self.call('fetch_rodin')['reused'])

    def test_bridge_preview_preserves_existing_operations(self):
        body = JobRequest(operation='character_pipeline', request='Preview one submission',
                          character_request=c.CharacterCommand(action='submit_rodin', source_job_id=self.jid)).checked()
        jid, _ = self.store.submit(body, 'bridge-character-preview')
        Runtime(self.store).execute(jid)
        self.assertEqual(self.store.get(jid)['status'], 'prepared_offline')
        old = JobRequest(operation='plan_feature', request='Existing planning flow').checked()
        self.assertNotIn('character_request', old)

    def test_automatic_run_continues_stages_and_stops_on_unknown_dispatch(self):
        command = c.CharacterCommand(action='run_rodin', source_job_id=self.jid)
        checkpoint = Mock()
        states = [{'rodin': {'status': 'submitted', 'next_poll_at': 0}},
                  {'rodin': {'status': 'ready_to_download'}}, {'rodin': {'status': 'downloaded'}}]
        with patch.object(c, 'execute', side_effect=states) as stage:
            result = c.run_to_download(command, self.store, checkpoint=checkpoint)
        self.assertEqual(result['rodin']['status'], 'downloaded')
        self.assertEqual([call.args[0].action for call in stage.call_args_list], ['submit_rodin', 'poll_rodin', 'fetch_rodin'])
        self.assertEqual(checkpoint.call_count, 2)
        with patch.object(c, 'execute', return_value={'rodin': {'status': 'dispatch_unknown'}}) as stage:
            self.assertEqual(c.run_to_download(command, self.store)['rodin']['status'], 'dispatch_unknown')
            stage.assert_called_once()


if __name__ == '__main__':
    unittest.main()
