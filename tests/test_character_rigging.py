import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from forest_agents.character_pipeline import CharacterCommand, execute
from forest_agents.character_rigging import RigProfile, prepare_rig, run_rig
from forest_agents.job_store import JobStore, Conflict
from forest_agents.workflow import ROOT


class RigStageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = JobStore(self.root / 'runs/control')
        self.source = self.root / 'assets/generated/characters/test/source.glb'
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(b'glb-source-for-adapter-tests')
        self.digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.profile = json.loads((ROOT / 'config/rig-profiles/beach-tourist-body-v1.json').read_text())
        self.profile['source_sha256'] = self.digest
        self.profile_path = self.root / 'config/rig-profiles/test.json'
        self.profile_path.parent.mkdir(parents=True)
        self.profile_path.write_text(json.dumps(self.profile))
        script = self.root / 'tools/rig_character_blender.py'
        script.parent.mkdir()
        script.write_text('# test recipe')
        self.jid, _ = self.store.submit({'operation':'character_pipeline','character_request':{'action':'prepare'},'live':False}, 'rig-source-job')
        self.store.update(self.jid, status='awaiting_review', result={'character_id':'test'})
        state = self.store.directory / 'artifacts' / self.jid / 'rodin-state.json'
        state.parent.mkdir(parents=True)
        state.write_text(json.dumps({'status':'downloaded','files':[{'path':str(self.source),'sha256':self.digest}]}))
        self.command = CharacterCommand(action='rig_character',source_job_id=self.jid,rig_profile='config/rig-profiles/test.json')

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_offline_prepares_source_bound_recipe_without_blender(self):
        with patch('forest_agents.character_rigging.run_rig', side_effect=AssertionError('Blender ran offline')):
            result = execute(self.command, self.store, root=self.root)
        self.assertTrue(result['preview'])
        self.assertEqual(result['rodin_credits'], 0)
        self.assertEqual(result['profile']['source_sha256'], self.digest)
        self.assertFalse(Path(result['output_directory']).exists())

    def test_changed_glb_or_unrelated_profile_cannot_be_rigged(self):
        self.source.write_bytes(b'changed source')
        with self.assertRaises(Conflict):
            prepare_rig(self.command,self.store,self.root)
        self.source.write_bytes(b'glb-source-for-adapter-tests')
        self.profile['source_sha256'] = 'f'*64
        self.profile_path.write_text(json.dumps(self.profile))
        with self.assertRaises(Conflict):
            prepare_rig(self.command,self.store,self.root)

    def test_profile_paths_and_symlinks_cannot_escape_config(self):
        for value in ['.RODIN_API_KEY','../outside.json','/tmp/profile.json']:
            with self.assertRaises(ValueError):
                prepare_rig(self.command.model_copy(update={'rig_profile':value}),self.store,self.root)
        outside = self.root / 'outside.json'
        outside.write_text(json.dumps(self.profile))
        self.profile_path.unlink()
        self.profile_path.symlink_to(outside)
        with self.assertRaises(ValueError):
            prepare_rig(self.command,self.store,self.root)

    def test_invalid_hierarchy_and_nonfinite_landmarks_are_rejected(self):
        self.profile['bones'][0]['parent']='Head'
        with self.assertRaises(ValueError):
            RigProfile.model_validate(self.profile)
        self.profile['bones'][0]['parent']=None
        self.profile['bones'][0]['head'][0]=float('nan')
        with self.assertRaises(ValueError):
            RigProfile.model_validate(self.profile)

    def test_queued_recipe_rejects_profile_change_before_execution(self):
        packet=prepare_rig(self.command,self.store,self.root)
        pinned=self.command.model_copy(update={'rig_recipe_sha256':packet['fingerprint']})
        self.profile['bones'][0]['head'][0]=.01
        self.profile_path.write_text(json.dumps(self.profile))
        with self.assertRaises(Conflict):
            prepare_rig(pinned,self.store,self.root)

    def test_completed_recipe_is_verified_and_reused_without_process(self):
        packet=prepare_rig(self.command,self.store,self.root)
        dest=Path(packet['output_directory']);dest.mkdir()
        artifact=dest/'rig.glb';artifact.write_bytes(b'rigged')
        manifest={'fingerprint':packet['fingerprint'],'files':[{'path':str(artifact),'sha256':hashlib.sha256(b'rigged').hexdigest()}]}
        (dest/'rig-manifest.json').write_text(json.dumps(manifest))
        with patch('forest_agents.character_rigging.subprocess.Popen') as process:
            self.assertTrue(run_rig(packet)['reused'])
            process.assert_not_called()
            artifact.write_bytes(b'changed')
            with self.assertRaises(Conflict):
                run_rig(packet)

    def test_incomplete_output_is_retained_and_not_overwritten(self):
        packet=prepare_rig(self.command,self.store,self.root)
        dest=Path(packet['output_directory']);dest.mkdir()
        (dest/'blender.log').write_text('failure evidence')
        with self.assertRaises(Conflict):
            run_rig(packet)
        self.assertEqual((dest/'blender.log').read_text(),'failure evidence')

    def test_local_cancellation_terminates_child_process(self):
        packet=prepare_rig(self.command,self.store,self.root)
        process=Mock()
        process.poll.return_value=None
        def stop(_):
            raise InterruptedError('local cancellation')
        with patch('forest_agents.character_rigging.subprocess.Popen',return_value=process):
            with self.assertRaises(InterruptedError):
                run_rig(packet,checkpoint=stop)
        process.terminate.assert_called_once()
        process.wait.assert_called_once()


if __name__ == '__main__':
    unittest.main()
