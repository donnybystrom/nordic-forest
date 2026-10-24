import unittest
from unittest.mock import patch

from tools import check_repository_inputs as guard


class SizedBinary:
    """Model Git's reported binary content size without allocating 100 MiB."""
    def __init__(self, size):
        self.size = size

    def __len__(self):
        return self.size


class RepositoryInputTests(unittest.TestCase):
    def inspect_blob(self, blob, path="assets/character.glb"):
        index = f"100644 abc123 0\t{path}\0".encode()
        with patch.object(guard.subprocess, "check_output", side_effect=[index, blob]):
            return guard.inspect_index()

    def test_regular_git_allows_assets_above_old_limit_through_100_mib(self):
        for size in [10 * 1024 * 1024 + 1, 50 * 1024 * 1024, 100 * 1024 * 1024]:
            with self.subTest(size=size):
                self.assertEqual(self.inspect_blob(SizedBinary(size))["rejected"], [])

    def test_git_rejects_one_byte_above_100_mib(self):
        result = self.inspect_blob(SizedBinary(100 * 1024 * 1024 + 1))
        self.assertEqual(result["rejected"], [("assets/character.glb", "regular Git blob exceeds project 100 MiB limit")])

    def test_credential_and_local_path_rules_remain_active(self):
        self.assertEqual(self.inspect_blob(b"sk-" + b"a" * 32)["rejected"][0][1], "credential-like value")
        self.assertEqual(self.inspect_blob(b"local", "runs/local.json")["rejected"][0][1], "local/secret path")


if __name__ == "__main__":
    unittest.main()
