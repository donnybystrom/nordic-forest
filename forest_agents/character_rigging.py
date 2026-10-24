"""Bounded local Blender rig stage for a downloaded character package."""
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .job_store import Conflict, canonical
from .workflow import ROOT

BLENDER = '/Applications/Blender.app/Contents/MacOS/Blender'


class RigBone(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    name: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_]{0,63}$')
    parent: str | None = None
    head: list[float] = Field(min_length=3, max_length=3)
    tail: list[float] = Field(min_length=3, max_length=3)


class RigProfile(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    schema_version: int = 1
    name: str = Field(min_length=1, max_length=120)
    source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    coordinate_space: str = 'center_x_feet_z_blender_zup'
    hand_mode: str = 'rigid_palm; finger articulation is a later profile revision'
    max_influences: int = Field(default=4, ge=1, le=4)
    bones: list[RigBone] = Field(min_length=15, max_length=100)

    @model_validator(mode='after')
    def hierarchy(self):
        if self.coordinate_space != 'center_x_feet_z_blender_zup':
            raise ValueError('Unsupported rig coordinate frame')
        seen = set()
        roots = []
        for bone in self.bones:
            if bone.name in seen or (bone.parent is not None and bone.parent not in seen):
                raise ValueError('Use unique bones in parent-first order')
            if not all(math.isfinite(v) for v in bone.head + bone.tail) or math.dist(bone.head, bone.tail) < .00001:
                raise ValueError('Invalid bone coordinates')
            if bone.parent is None:
                roots.append(bone.name)
            seen.add(bone.name)
        required = {'Hips', 'Spine', 'Spine1', 'Spine2', 'Neck', 'Head'}
        for side in ('Left', 'Right'):
            required |= {side + name for name in ('Shoulder', 'Arm', 'ForeArm', 'Hand', 'UpLeg', 'Leg', 'Foot', 'ToeBase')}
        if roots != ['Hips'] or not required <= seen:
            raise ValueError('Require a complete humanoid body rooted at Hips')
        return self


def prepare_rig(command, store, root=ROOT):
    root = Path(root).resolve()
    source_job = store.get(command.source_job_id)
    if source_job['request']['operation'] != 'character_pipeline' or source_job['request']['character_request']['action'] != 'prepare':
        raise Conflict('Use the original character prepare job')
    state_path = store.directory / 'artifacts' / source_job['id'] / 'rodin-state.json'
    state = json.loads(state_path.read_text())
    if state.get('status') != 'downloaded':
        raise Conflict('Download the source character before rigging')
    sources = [f for f in state['files'] if f['path'].lower().endswith('.glb')]
    if len(sources) != 1:
        raise Conflict('The package must contain exactly one source GLB')
    source = Path(sources[0]['path']).resolve()
    if not source.is_relative_to(root / 'assets/generated/characters'):
        raise Conflict('Rigging source is outside generated character assets')
    if hashlib.sha256(source.read_bytes()).hexdigest() != sources[0]['sha256']:
        raise Conflict('Source GLB changed after download')
    profile_path = (root / command.rig_profile).resolve()
    if not profile_path.is_relative_to(root / 'config/rig-profiles') or profile_path.suffix != '.json':
        raise ValueError('Use a JSON profile under config/rig-profiles')
    profile = RigProfile.model_validate_json(profile_path.read_text())
    if profile.source_sha256 != sources[0]['sha256']:
        raise Conflict('Fit a profile for this exact source GLB')
    script = root / 'tools/rig_character_blender.py'
    recipe = {'source_sha256': sources[0]['sha256'], 'profile': profile.model_dump(),
              'script_sha256': hashlib.sha256(script.read_bytes()).hexdigest()}
    fingerprint = hashlib.sha256(canonical(recipe).encode()).hexdigest()
    if command.rig_recipe_sha256 and command.rig_recipe_sha256 != fingerprint:
        raise Conflict('Rig source, profile or implementation changed after submission; prepare a new stage request')
    dest = root / 'assets/generated/characters' / source_job['result']['character_id'] / ('rig-' + fingerprint[:16])
    return {'scope': 'character_rigging', 'source_job_id': source_job['id'], 'source': str(source),
            'profile': profile.model_dump(), 'fingerprint': fingerprint, 'output_directory': str(dest),
            'script': str(script), 'rodin_credits': 0, 'recipe': recipe}


def run_rig(packet, checkpoint=None, timeout_seconds=600):
    destination = Path(packet['output_directory'])
    manifest = destination / 'rig-manifest.json'
    if manifest.exists():
        previous = json.loads(manifest.read_text())
        if previous['fingerprint'] != packet['fingerprint']:
            raise Conflict('Rig output belongs to a different recipe')
        for item in previous['files']:
            if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest() != item['sha256']:
                raise Conflict('An existing rig artifact changed')
        return dict(previous, reused=True)
    if destination.exists():
        raise Conflict('Incomplete rig output requires inspection; use a revised recipe for a corrected attempt')
    destination.mkdir(parents=True)
    request = destination / 'rig-request.json'
    request.write_text(canonical(packet) + '\n')
    with (destination / 'blender.log').open('wb') as log:
        process = subprocess.Popen([BLENDER, '--background', '--factory-startup', '--disable-autoexec',
                                    '--python-exit-code', '1', '--python', packet['script'], '--',
                                    '--request', str(request)], stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + timeout_seconds
        try:
            while process.poll() is None:
                if checkpoint:
                    checkpoint({'scope': 'character_rigging', 'status': 'building_and_validating',
                                'output_directory': str(destination), 'rodin_credits': 0})
                if time.monotonic() > deadline:
                    raise TimeoutError('Local rig stage exceeded its deadline')
                time.sleep(.5)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    if process.returncode != 0 or not manifest.is_file():
        raise RuntimeError('Rig stage failed; inspect its retained Blender log and intermediate reports')
    return dict(json.loads(manifest.read_text()), reused=False)
