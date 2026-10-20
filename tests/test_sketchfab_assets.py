import json
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from forest_agents.sketchfab_assets import AssetError, SketchfabCollector, extract_zip, validate_download_url

OAK = "a5e4e64f9f1d4089bdcc6170a9333393"
STICK = "0ab534c493e14f67bac01ee94f20e43f"


class SketchfabTests(unittest.TestCase):
    def test_safe_archive_extracts_under_target(self):
        with tempfile.TemporaryDirectory() as d:
            archive = Path(d) / "asset.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("textures/bark.txt", b"fixture")
            target = Path(d) / "out"
            self.assertEqual(extract_zip(archive, target), 7)
            self.assertEqual((target / "textures/bark.txt").read_bytes(), b"fixture")

    def test_traversal_and_symlink_rejected_before_writing(self):
        for kind in ["traversal", "symlink"]:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as d:
                archive = Path(d) / "asset.zip"
                with zipfile.ZipFile(archive, "w") as z:
                    if kind == "traversal":
                        z.writestr("../outside.txt", "bad")
                    else:
                        entry = zipfile.ZipInfo("link")
                        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                        z.writestr(entry, "/outside")
                with self.assertRaises(AssetError):
                    extract_zip(archive, Path(d) / "out")
                self.assertFalse((Path(d) / "out").exists())

    def test_unpacked_budget_enforced(self):
        with tempfile.TemporaryDirectory() as d:
            archive = Path(d) / "asset.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("file", b"12345")
            with self.assertRaises(AssetError):
                extract_zip(archive, Path(d) / "out", byte_limit=4)

    def test_uid_and_format_allowlists_apply_before_credentials(self):
        collector = SketchfabCollector([OAK], allowed_formats=["source"])
        with patch("forest_agents.sketchfab_assets.load_token", side_effect=AssertionError):
            for uid, fmt in [(STICK, "source"), (OAK, "glb"), ("../../secret", "source")]:
                with self.assertRaises(AssetError):
                    collector.fetch(uid, fmt)

    def test_signed_download_cannot_target_local_or_other_service(self):
        for url in ["http://localhost/a", "https://127.0.0.1/a", "https://example.com/a", "https://sketchfab.com.evil.test/a"]:
            with self.assertRaises(AssetError):
                validate_download_url(url)
        validate_download_url("https://sketchfab-prod-media.s3.amazonaws.com/a?signature=not-real")

    def test_agent_tool_schema_never_accepts_credentials_or_output_paths(self):
        tool = SketchfabCollector([OAK]).agent_tools()[0]
        self.assertEqual(set(tool.params_json_schema["properties"]), {"model_uid", "archive_format"})


if __name__ == "__main__":
    unittest.main()
