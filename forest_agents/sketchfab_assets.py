"""Bounded Sketchfab acquisition. Credentials and expiring URLs never enter tool outputs."""
import hashlib
import json
import os
import re
import shutil
import stat
import threading
import urllib.error
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
UID = re.compile(r"^[0-9a-f]{32}$")


class AssetError(Exception):
    """Only short, non-sensitive error categories are allowed here."""


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_token(path=None):
    if path is None and os.getenv("SKETCHFAB_API_TOKEN"):
        value = os.environ["SKETCHFAB_API_TOKEN"].strip()
        if not re.fullmatch(r"[0-9a-fA-F]{32}", value):
            raise AssetError("invalid_token_format")
        return value
    values = set(re.findall(r"\b[0-9a-fA-F]{32}\b", Path(path or ROOT / "SKETCHFAB_API_TOKEN.md").read_text()))
    if len(values) != 1:
        raise AssetError("ambiguous_token_file")
    return values.pop()


def validate_download_url(url):
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in {None, 443}:
        raise AssetError("invalid_download_url")
    if not (host.endswith(".amazonaws.com") or host.endswith(".sketchfab.com") or host.endswith(".sketchfabcdn.com")):
        raise AssetError("unsupported_download_host")
    return url


class NoAPIRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise AssetError("api_redirect_refused")


class DownloadRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_download_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def extract_zip(archive, target, byte_limit=2 * 1024**3, file_limit=12000):
    target = Path(target)
    if target.exists():
        raise AssetError("extraction_target_exists")
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        if len(entries) > file_limit or sum(e.file_size for e in entries) > byte_limit:
            raise AssetError("archive_extraction_budget_exceeded")
        seen = set()
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in entry.filename or ":" in entry.filename:
                raise AssetError("unsafe_archive_path")
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise AssetError("archive_symlink_refused")
            name = str(path)
            if name in seen:
                raise AssetError("duplicate_archive_path")
            seen.add(name)
        target.mkdir(parents=True)
        for entry in entries:
            destination = target.joinpath(*PurePosixPath(entry.filename).parts)
            if entry.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with z.open(entry) as source, destination.open("xb") as out:
                    shutil.copyfileobj(source, out, 1024 * 1024)
    return sum(e.file_size for e in entries)


class SketchfabCollector:
    def __init__(self, allowed_uids, token_file=None, root=None, max_archives=4,
                 max_archive_bytes=512 * 1024**2, max_total_bytes=1024**3,
                 allowed_formats=("source", "glb", "gltf")):
        if not allowed_uids or any(not UID.fullmatch(uid) for uid in allowed_uids):
            raise AssetError("invalid_model_uid")
        self.allowed = frozenset(allowed_uids)
        self.allowed_formats = frozenset(allowed_formats)
        self._token_file = token_file
        self.root = Path(root or ROOT / "data/references/downloads").resolve()
        self.max_archives, self.max_archive_bytes, self.max_total_bytes = max_archives, max_archive_bytes, max_total_bytes
        self.attempts, self.downloaded_bytes = 0, 0
        self.manifests = []
        self.tool_events = []
        self._lock = threading.Lock()

    def _check_uid(self, uid):
        if not UID.fullmatch(uid) or uid not in self.allowed:
            raise AssetError("model_outside_assigned_allowlist")

    def _api(self, path):
        request = urllib.request.Request("https://api.sketchfab.com/v3/" + path,
                                         headers={"Authorization": "Token " + load_token(self._token_file),
                                                  "User-Agent": "NordicForestAssetCollector/0.1"})
        try:
            with urllib.request.build_opener(NoAPIRedirect()).open(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise AssetError("sketchfab_http_" + str(exc.code)) from None
        except AssetError:
            raise
        except Exception:
            raise AssetError("sketchfab_request_failed") from None

    def metadata(self, uid):
        self._check_uid(uid)
        d = self._api("models/" + uid)
        return {"uid": d["uid"], "title": d["name"], "source_url": d["viewerUrl"],
                "creator": d.get("user", {}).get("displayName"), "creator_url": d.get("user", {}).get("profileUrl"),
                "description": d.get("description"), "license": d.get("license"),
                "downloadable": d.get("isDownloadable"), "updated_at": d.get("updatedAt"),
                "reported_triangles": d.get("faceCount"), "reported_vertices": d.get("vertexCount")}

    def fetch(self, uid, archive_format="source"):
        self._check_uid(uid)
        if archive_format not in {"source", "glb", "gltf"} or archive_format not in self.allowed_formats:
            raise AssetError("unsupported_archive_format")
        # Serialize acquisition and counters even if a model tries parallel tool calls.
        with self._lock:
            if self.attempts >= self.max_archives:
                raise AssetError("archive_call_budget_exceeded")
            self.attempts += 1
            metadata = self.metadata(uid)
            if not metadata["downloadable"]:
                raise AssetError("model_not_downloadable")
            formats = self._api("models/" + uid + "/download")
            package = formats.get(archive_format)
            if not isinstance(package, dict) or not package.get("url"):
                raise AssetError("requested_format_unavailable")
            declared_size = package.get("size")
            if not isinstance(declared_size, int) or declared_size <= 0:
                raise AssetError("archive_size_unavailable")
            if declared_size > min(self.max_archive_bytes, self.max_total_bytes - self.downloaded_bytes):
                raise AssetError("archive_download_budget_exceeded")
            self.root.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(self.root).free < 2 * 1024**3 + declared_size:
                raise AssetError("insufficient_cache_space")
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            directory = self.root / uid / (archive_format + "-" + stamp + "-" + uuid.uuid4().hex[:6])
            directory.mkdir(parents=True)
            partial = directory / "download.part"
            url = validate_download_url(package["url"])
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "NordicForestAssetCollector/0.1"})
                with urllib.request.build_opener(DownloadRedirect()).open(request, timeout=30) as response, partial.open("xb") as out:
                    size = 0
                    while block := response.read(1024 * 1024):
                        size += len(block)
                        self.downloaded_bytes += len(block)
                        if size > self.max_archive_bytes or self.downloaded_bytes > self.max_total_bytes:
                            raise AssetError("stream_download_budget_exceeded")
                        out.write(block)
                if size != declared_size:
                    raise AssetError("declared_archive_size_mismatch")
                with partial.open("rb") as stream:
                    magic = stream.read(4)
                suffix = ".zip" if zipfile.is_zipfile(partial) else ".glb" if magic == b"glTF" else ".bin"
                archive = directory / ("asset" + suffix)
                partial.rename(archive)
                unpacked_bytes = extract_zip(archive, directory / "extracted") if suffix == ".zip" else 0
                files = [{"path": str(path.relative_to(directory)), "bytes": path.stat().st_size,
                          "sha256": file_hash(path)} for path in sorted(directory.rglob("*")) if path.is_file()]
                manifest = {"schema_version": "0.1", "status": "downloaded", "captured_at": stamp,
                            "provider": "Sketchfab", "archive_format": archive_format, "metadata": metadata,
                            "archive_sha256": file_hash(archive), "downloaded_bytes": size,
                            "unpacked_bytes": unpacked_bytes, "files": files,
                            "reuse_status": "source_license_recorded_production_acceptance_pending",
                            "conversion_note": "source is the author upload; glb/gltf are provider conversions",
                            "supplemental_texture_completeness": "not_verified"}
                manifest_path = directory / "manifest.json"
                manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
                self.manifests.append(str(manifest_path))
                result = {"status": "downloaded", "uid": uid, "format": archive_format,
                          "manifest": str(manifest_path), "archive_sha256": manifest["archive_sha256"],
                          "downloaded_bytes": size, "file_count": len(files),
                          "model_files": [str(directory / f["path"]) for f in files
                                          if Path(f["path"]).suffix.lower() in {".blend", ".glb", ".gltf", ".obj", ".fbx"}][:30]}
                self.tool_events.append(result)
                return result
            except AssetError:
                raise
            except Exception:
                raise AssetError("archive_download_or_extraction_failed") from None

    def agent_tools(self):
        """The credential is captured by the backend, never a model-visible argument."""
        import asyncio
        from typing import Literal
        from agents import function_tool

        @function_tool
        async def fetch_sketchfab_reference(model_uid: str, archive_format: Literal["source", "glb", "gltf"] = "source") -> str:
            """Download an assigned Sketchfab model and return local evidence paths. No model inspection is performed."""
            try:
                result = await asyncio.to_thread(self.fetch, model_uid, archive_format)
                return json.dumps(result)
            except AssetError as exc:
                return json.dumps({"status": "error", "category": str(exc)})

        return [fetch_sketchfab_reference]
