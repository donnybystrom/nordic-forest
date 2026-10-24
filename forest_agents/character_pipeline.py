"""First character-pipeline adapter: reviewed references -> Rodin -> local files.

Rigging, motion generation and active-ragdoll acceptance are separate stages.
Provider state lives beside the immutable review result, never inside a flow.
"""
import hashlib
import ipaddress
import json
import mimetypes
import os
import re
import socket
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from .job_store import Conflict, canonical
from .workflow import ROOT

API = 'https://api.hyper3d.com/api/v2'
DOCS = 'https://docs.hyper3d.ai/en/api-specification/rodin-gen2-5'


class RodinSettings(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    tier: Literal['Gen-2.5-Medium', 'Gen-2.5-High'] = 'Gen-2.5-High'
    mesh_mode: Literal['Quad'] = 'Quad'
    quality_override: int = Field(default=30000, ge=500, le=200000)
    geometry_file_format: Literal['glb'] = 'glb'
    material: Literal['PBR'] = 'PBR'
    texture_mode: Literal['high'] = 'high'
    addons: list[Literal['HighPack']] = Field(default_factory=lambda: ['HighPack'], max_length=1)
    TAPose: Literal[True] = True
    seed: int = Field(default=42, ge=0, le=65535)


class CharacterView(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    view: Literal['front', 'back', 'left', 'right', 'three_quarter']
    path: str = Field(min_length=1, max_length=500)


class SheetPanel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    view: Literal['front', 'back', 'left', 'right', 'three_quarter']
    box: list[int] = Field(min_length=4, max_length=4, description='Pixel coordinates: left, top, right, bottom')


class CharacterCommand(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    action: Literal['split_sheet', 'prepare', 'inspect', 'balance', 'run_rodin', 'submit_rodin', 'poll_rodin', 'fetch_rodin', 'rig_character'] = 'prepare'
    character_id: str = Field(default='beach-tourist-zombie-v1', pattern=r'^[a-z0-9][a-z0-9-]{0,79}$')
    brief: str = Field(default='', max_length=4000)
    reference_sheets: list[str] = Field(default_factory=list, max_length=5)
    motion_references: list[str] = Field(default_factory=list, max_length=5)
    views: list[CharacterView] = Field(default_factory=list, max_length=5)
    settings: RodinSettings = Field(default_factory=RodinSettings)
    source_job_id: str = Field(default='', max_length=40)
    sheet_path: str = Field(default='', max_length=500)
    panels: list[SheetPanel] = Field(default_factory=list, max_length=5)
    rig_profile: str = Field(default='', max_length=500)
    rig_recipe_sha256: str = Field(default='', pattern=r'^(?:|[a-f0-9]{64})$')


def file_record(name, root=ROOT):
    """Only authored/generated character inputs inside this workspace are readable."""
    root = Path(root).resolve()
    path = (root / name).resolve()
    allowed = [root / 'assets/work/characters', root / 'assets/generated/characters']
    if not any(path.is_relative_to(p) for p in allowed):
        raise ValueError('Use a character input inside assets/work/characters or assets/generated/characters')
    if path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'} or not path.is_file():
        raise ValueError('A reference must be an existing PNG, JPEG or WebP')
    size = path.stat().st_size
    if not 0 < size <= 25 * 1024 * 1024:
        raise ValueError('Reference image exceeds the 25 MiB input limit')
    return {'path': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': size}


def prepare(command, root=ROOT):
    views = [dict(file_record(v.path, root), view=v.view) for v in command.views]
    if len({v['view'] for v in views}) != len(views) or len({v['sha256'] for v in views}) != len(views):
        raise ValueError('Repeated view or image')
    if views and views[0]['view'] != 'front':
        raise ValueError('Put the front view first')
    references = [file_record(p, root) for p in command.reference_sheets]
    motion = [file_record(p, root) for p in command.motion_references]
    if {v['sha256'] for v in views} & {v['sha256'] for v in references + motion}:
        raise ValueError('Sheets and motion references must not be reconstruction views')
    return {
        'scope': 'character_pipeline', 'character_id': command.character_id,
        'adapter_version': 'rodin-v2-csv-addons-1',
        'brief': command.brief, 'views': views, 'reference_sheets': references,
        'motion_references': motion, 'settings': command.settings.model_dump(),
        'ready_for_generation_review': bool(views),
        'next_action': 'Review these single-character neutral views and Rodin settings.' if views else
                       'Prepare separate neutral single-character views; front first. The supplied sheets are references.',
        'provider_calls': 0, 'pricing_reference': DOCS + '#pricing',
        'review_scope': 'Approval permits one Rodin mesh/texture submission with this exact snapshot.',
        'later_stages': {
            'concept_chat_and_view_generation': 'manual_image_generation_handoff',
            'mesh_material_review': 'required_after_download',
            'rigging': 'local_blender_profile_stage_available; explicit source-bound landmarks',
            'animation_generation': 'provider_api_not_verified; manual_delivery_handoff',
            'motion_retargeting': 'not_run',
            'godot_import': 'not_run', 'active_ragdoll': 'not_implemented',
        },
    }


def split_sheet(command, root=ROOT):
    """Lossless crops of an explicitly supplied layout; no inferred new views."""
    from PIL import Image
    source = file_record(command.sheet_path, root)
    if not command.panels or len({p.view for p in command.panels}) != len(command.panels):
        raise ValueError('Specify one unique named panel per view')
    layout = [p.model_dump() for p in command.panels]
    key = hashlib.sha256(canonical({'source': source, 'layout': layout}).encode()).hexdigest()[:16]
    destination = Path(root) / 'assets/work/characters' / command.character_id / ('views-' + key)
    destination.mkdir(parents=True, exist_ok=True)
    records = []
    with Image.open(Path(root) / source['path']) as image:
        for panel in command.panels:
            x0, y0, x1, y1 = panel.box
            if not (0 <= x0 < x1 <= image.width and 0 <= y0 < y1 <= image.height):
                raise ValueError('Panel lies outside the source image')
            crop = image.crop(tuple(panel.box))
            target = destination / (panel.view + '.png')
            if target.exists():
                with Image.open(target) as previous:
                    if previous.mode != crop.mode or previous.size != crop.size or previous.tobytes() != crop.tobytes():
                        raise Conflict('Existing cropped view changed')
            else:
                crop.save(target)
            records.append(dict(file_record(str(target.relative_to(root)), root), view=panel.view))
    return {'scope': 'character_pipeline', 'action': 'split_sheet', 'source': source,
            'layout': layout, 'views': records, 'method': 'lossless_pixel_crop', 'provider_calls': 0,
            'next_action': 'Inspect these crops, then prepare a generation package with their paths.'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class RodinError(RuntimeError):
    def __init__(self, status=None, code=None, rejected=False):
        self.status = status
        self.code = code if isinstance(code, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}', code) else 'UNSPECIFIED'
        self.rejected = rejected
        super().__init__('Rodin request failed')

    def receipt(self):
        return {'http_status': self.status, 'provider_code': self.code}


class RodinClient:
    def __init__(self, key_file=None):
        key = os.environ.get('RODIN_API_KEY') or Path(key_file or ROOT / '.RODIN_API_KEY').read_text().strip()
        if not key or any(ch.isspace() for ch in key):
            raise ValueError('Rodin credential must contain one token')
        self._key = key

    def request(self, endpoint, body=None, content_type='application/json'):
        if endpoint not in {'rodin', 'status', 'download', 'check_balance', 'check_balance?usage_page=1'}:
            raise ValueError('Unknown Rodin operation')
        raw = body if isinstance(body, bytes) else canonical(body).encode() if body is not None else None
        req = urllib.request.Request(API + '/' + endpoint, data=raw, headers={
            'Authorization': 'Bearer ' + self._key, 'Content-Type': content_type})
        try:
            with urllib.request.build_opener(NoRedirect).open(req, timeout=45) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            # Do not propagate bodies, signed URLs or request headers into job history.
            try:
                error = json.load(exc)
            except (ValueError, OSError):
                error = {}
            raise RodinError(exc.code, error.get('error') if isinstance(error, dict) else None,
                             rejected=exc.code in {400, 401, 403, 422}) from None
        except (OSError, ValueError):
            raise RuntimeError('Rodin response unavailable; inspect retained dispatch state') from None
        if not isinstance(result, dict):
            raise RuntimeError('Invalid Rodin response')
        if result.get('error'):
            raise RodinError(code=result['error'], rejected=not bool(result.get('uuid')))
        return result

    def submit(self, package, root=ROOT):
        boundary = 'nf-' + uuid.uuid4().hex
        data = bytearray()
        for name, value in package['settings'].items():
            if isinstance(value, list) and not value:
                continue
            # The provider's official client uses comma-separated add-ons in form data.
            text = ','.join(value) if isinstance(value, list) else canonical(value) if isinstance(value, bool) else str(value)
            data.extend((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{text}\r\n').encode())
        for index, view in enumerate(package['views']):
            path = Path(root) / view['path']
            payload = path.read_bytes()
            # Hash the bytes actually uploaded, closing the review-to-read race.
            if hashlib.sha256(payload).hexdigest() != view['sha256']:
                raise Conflict('View changed since review; prepare a new snapshot')
            mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
            data.extend((f'--{boundary}\r\nContent-Disposition: form-data; name="images"; filename="view-{index}{path.suffix}"\r\n'
                         f'Content-Type: {mime}\r\n\r\n').encode())
            data.extend(payload)
            data.extend(b'\r\n')
        data.extend(f'--{boundary}--\r\n'.encode())
        return self.request('rodin', bytes(data), 'multipart/form-data; boundary=' + boundary)


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_suffix('.tmp')
    with temp.open('w') as stream:
        os.chmod(temp, 0o600)
        stream.write(canonical(state) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def public_state(state):
    return {k: v for k, v in state.items() if k != 'subscription_key'}


def fetch_file(url, target, max_bytes=400 * 1024 * 1024):
    """Fetch provider artifact without forwarding the provider credential."""
    parts = urlsplit(url)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.port not in {None, 443}:
        raise ValueError('Artifact URL must be public HTTPS')
    addresses = socket.getaddrinfo(parts.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Artifact address is not public')
    partial = target.with_suffix(target.suffix + '.part')
    digest, size = hashlib.sha256(), 0
    try:
        with urllib.request.build_opener(NoRedirect).open(url, timeout=45) as response, partial.open('wb') as stream:
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError('Artifact exceeds download budget')
                digest.update(chunk)
                stream.write(chunk)
        if not size:
            raise ValueError('Empty artifact')
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    return {'path': str(target), 'sha256': digest.hexdigest(), 'bytes': size}


def execute(command, store, live=False, client_factory=RodinClient, root=ROOT):
    """Each call performs one explicit stage; no automatic generation retry."""
    if command.action == 'prepare':
        return prepare(command, root)
    if command.action == 'rig_character':
        from .character_rigging import prepare_rig, run_rig
        packet = prepare_rig(command, store, root)
        if not live:
            return dict(packet, provider_calls=0, preview=True)
        return run_rig(packet)
    if not live and command.action != 'inspect':
        return {'scope': 'character_pipeline', 'preview': command.model_dump(), 'provider_calls': 0}
    if command.action == 'run_rodin':
        return run_to_download(command, store, client_factory=client_factory, root=root)
    if command.action == 'split_sheet':
        return split_sheet(command, root)
    if command.action == 'balance':
        balance = client_factory().request('check_balance')
        return {'scope': 'character_pipeline', 'balance_credits': balance['balance']}
    source = store.get(command.source_job_id)
    if source['request']['operation'] != 'character_pipeline' or source['request']['character_request']['action'] != 'prepare':
        raise Conflict('Reference a character prepare job')
    package = source['result']
    path = store.directory / 'artifacts' / source['id'] / 'rodin-state.json'
    state = json.loads(path.read_text()) if path.exists() else {}
    if command.action == 'inspect':
        return {'scope': 'character_pipeline', 'package': package, 'decision': source['decision'], 'rodin': public_state(state)}
    if command.action == 'submit_rodin':
        digest = hashlib.sha256(canonical(package).encode()).hexdigest()
        if not package.get('ready_for_generation_review') or source['decision'] != 'approve_generation' or source['decision_hash'] != digest:
            raise Conflict('Approve the exact prepared references/settings in the local review UI first')
        if state:
            # Even a new Langflow submission key cannot duplicate this package's paid create.
            return {'scope': 'character_pipeline', 'rodin': public_state(state), 'reused': True}
        for view in package['views']:
            if file_record(view['path'], root)['sha256'] != view['sha256']:
                raise Conflict('Reference changed since review; prepare and review again')
        client = client_factory()  # Validate local credential before marking dispatch.
        balance_before = client.request('check_balance')['balance']
        state = {'status': 'dispatch_unknown', 'review_sha256': digest, 'balance_before_credits': balance_before,
                 'recovery': 'No automatic retry. Reconcile task UUID in the provider dashboard if the create reply is lost.'}
        save_state(path, state)  # Must reach disk BEFORE the billable request.
        try:
            response = client.submit(package, root)
        except RodinError as exc:
            state.update(status='rejected' if exc.rejected else 'dispatch_unknown', error_receipt=exc.receipt())
            save_state(path, state)
            return {'scope': 'character_pipeline', 'rodin': public_state(state)}
        task_id = str(uuid.UUID(response['uuid']))
        subscription = response['jobs']['subscription_key']
        if not isinstance(subscription, str) or not subscription:
            raise RuntimeError('Missing Rodin subscription identifier')
        state.update(status='submitted', task_uuid=task_id, subscription_key=subscription,
                     consumed_credits=response.get('consumed'), next_poll_at=time.time() + 5, poll_delay=5)
        save_state(path, state)
    elif command.action == 'poll_rodin':
        if state.get('status') not in {'submitted', 'generating'}:
            return {'scope': 'character_pipeline', 'rodin': public_state(state), 'provider_calls': 0}
        if time.time() < state['next_poll_at']:
            return {'scope': 'character_pipeline', 'rodin': public_state(state), 'provider_calls': 0}
        # Reserve the next poll before requesting; a rate-limit/error cannot cause a tight retry loop.
        state['poll_delay'] = min(30, state['poll_delay'] * 2)
        state['next_poll_at'] = time.time() + state['poll_delay']
        save_state(path, state)
        response = client_factory().request('status', {'subscription_key': state['subscription_key']})
        statuses = [j['status'] for j in response.get('jobs', [])]
        if not statuses or any(s not in {'Waiting', 'Generating', 'Done', 'Failed'} for s in statuses):
            raise ValueError('Rodin returned missing or unknown job states')
        state.update(jobs=statuses, status='failed' if 'Failed' in statuses else
                     'ready_to_download' if all(s == 'Done' for s in statuses) else 'generating')
        save_state(path, state)
    elif command.action == 'fetch_rodin':
        if state.get('status') == 'downloaded':
            for record in state['files']:
                if hashlib.sha256(Path(record['path']).read_bytes()).hexdigest() != record['sha256']:
                    raise Conflict('Downloaded artifact changed; inspect before reuse')
            return {'scope': 'character_pipeline', 'rodin': public_state(state), 'reused': True}
        if state.get('status') != 'ready_to_download':
            raise Conflict('All provider jobs must be Done before download')
        response = client_factory().request('download', {'task_uuid': state['task_uuid']})
        items = response.get('list', [])
        if not items or len(items) > 30:
            raise ValueError('Invalid Rodin file list')
        names = [i['name'] for i in items]
        if len(set(names)) != len(names) or any(not isinstance(n, str) or n in {'.', '..'} or
                '/' in n or '\\' in n or not n or len(n) > 200 for n in names):
            raise ValueError('Unsafe or duplicate provider artifact names')
        dest = Path(root) / 'assets/generated/characters' / package['character_id'] / source['id']
        dest.mkdir(parents=True, exist_ok=True)
        files, budget = [], 750 * 1024 * 1024
        for item in items:
            record = fetch_file(item['url'], dest / item['name'], min(budget, 400 * 1024 * 1024))
            files.append(record)
            budget -= record['bytes']
        state.update(status='downloaded', files=files, next_action='Review mesh and materials before rigging.')
        try:
            billing = client_factory().request('check_balance?usage_page=1')
            state['balance_after_credits'] = billing['balance']
            state['usage_for_task'] = [{k: row[k] for k in ('item', 'amount', 'task_uuid', 'time') if k in row}
                                      for row in billing.get('usage', []) if row.get('task_uuid') == state['task_uuid']]
        except (RuntimeError, KeyError):
            state['billing_reconciliation'] = 'Balance unavailable; consumed_credits is the submission receipt.'
        save_state(path, state)
    return {'scope': 'character_pipeline', 'rodin': public_state(state)}


def run_to_download(command, store, client_factory=RodinClient, root=ROOT, checkpoint=None, deadline_seconds=1200):
    """Continue one approved package through submission, polling and download.

    Each stage still persists its own provider state. Stopping this local runner
    does not cancel a provider task; a later explicit run reconciles the same task.
    """
    def step(action):
        return execute(command.model_copy(update={'action': action}), store, live=True,
                       client_factory=client_factory, root=root)
    output = step('submit_rodin')
    deadline = time.monotonic() + deadline_seconds
    while True:
        output['remote_cancellation'] = 'not_requested; local stop does not stop the Rodin task'
        if checkpoint:
            checkpoint(output)
        state = output['rodin']
        if state.get('status') in {'ready_to_download', 'downloaded'}:
            return step('fetch_rodin')
        if state.get('status') not in {'submitted', 'generating'}:
            return output
        if time.monotonic() >= deadline:
            output['next_action'] = 'Local deadline reached. Inspect or explicitly run the same package again; no new generation is required.'
            return output
        if time.time() < state.get('next_poll_at', 0):
            time.sleep(.5)
            continue
        output = step('poll_rodin')
