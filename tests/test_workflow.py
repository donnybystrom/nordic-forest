import copy
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from pydantic import ValidationError

from forest_agents.contracts import Claim, Handover, Milestone
from forest_agents.platform_migration import definition, digest, exact_clone, remove_verified_sources
from forest_agents.workflow import ROOT, load_config, make_agent, prepare, read_project_text, run_live, stages_for


class PlanningTests(unittest.TestCase):
    def test_asset_branch_receives_catalog_with_explicit_evidence_states(self):
        p = prepare(ROOT / "examples/reference-analysis-request.txt", ["asset_analysis"], load_config())
        self.assertIn("docs/REFERENCE-ASSET-PIPELINE.md", p["context"])
        catalog = json.loads(p["context"]["data/references/catalog.json"])
        for asset in catalog["assets"]:
            if asset["source_file"] is None:
                self.assertEqual(asset["geometry_measurement_state"], "source_file_required")
            else:
                self.assertRegex(asset["source_file_sha256"], r"^[0-9a-f]{64}$")
                self.assertIn("audit_evidence", asset)
                self.assertEqual(asset["geometry_measurement_state"], "blender_import_measured_not_runtime")
        self.assertEqual(p["remote_calls"], 0)

    def test_wall_clock_timeout_saves_failure_without_retry(self):
        c = load_config()
        c["limits"]["call_timeout_seconds"] = 0.01
        packet = prepare(ROOT / "examples/first-request.txt", [], c)
        client = SimpleNamespace(close=AsyncMock())

        async def slow_response(*args, **kwargs):
            await asyncio.sleep(0.2)

        with tempfile.TemporaryDirectory(dir=ROOT / "runs") as directory, \
             patch("forest_agents.workflow.load_key", return_value="unused-test-credential"), \
             patch("forest_agents.workflow.AsyncOpenAI", return_value=client), \
             patch("forest_agents.workflow.Runner.run", side_effect=slow_response) as run:
            with self.assertRaises(TimeoutError):
                asyncio.run(run_live(packet, c, Path(directory)))
            self.assertEqual(packet["status"], "failed")
            self.assertEqual(packet["remote_calls"], 1)
            self.assertEqual(run.call_count, 1)
            self.assertTrue((Path(directory) / "packet.json").is_file())
            client.close.assert_awaited_once()

    def test_reasoning_override_is_explicit_and_does_not_change_role_defaults(self):
        c = load_config()
        original = copy.deepcopy(c)
        p = prepare(ROOT / "examples/first-request.txt", [], c, True, "medium")
        self.assertEqual(c, original)
        self.assertEqual(p["reasoning_override"], "medium")
        self.assertTrue(all(s["reasoning"] == "medium" for s in p["stages"]))
        with self.assertRaises(ValueError):
            prepare(ROOT / "examples/first-request.txt", [], c, True, "unsupported")

    def test_offline_preparation_never_loads_key_or_calls_api(self):
        with patch("forest_agents.workflow.load_key", side_effect=AssertionError), \
             patch("forest_agents.workflow.AsyncOpenAI", side_effect=AssertionError):
            packet = prepare(ROOT / "examples/first-request.txt", ["ecology", "rendering"], load_config(), True)
        self.assertEqual(packet["remote_calls"], 0)
        self.assertEqual(len(packet["stages"]), 7)
        self.assertEqual(packet["feature_verification"], "not_performed")

    def test_specialist_budget_and_identity(self):
        c = load_config()
        for selection in [["ecology"] * 2, ["unknown"], c["specialist_roles"]]:
            with self.assertRaises(ValueError):
                stages_for(selection, c)

    def test_key_and_external_paths_are_not_request_inputs(self):
        for path in [ROOT / "OPENAI_API_SECRET_KEY.md", Path("/private/tmp/request.txt")]:
            with self.assertRaises(ValueError):
                read_project_text(path)

    def test_remote_settings_cannot_inherit_tools_or_project_instructions(self):
        c = load_config()
        role = "art_director"
        remote = SimpleNamespace(id=c["roles"][role]["platform_agent_id"], model="gpt-6.1-sol",
                                 reasoning=SimpleNamespace(effort="medium"),
                                 instructions="Unrelated project instructions", tools=["web_search"],
                                 multi_agent={"enabled": True})
        agent = make_agent(role, c, platform_spec=remote)
        self.assertIn("Nordic 3D Forest", agent.instructions)
        self.assertNotIn(remote.instructions, agent.instructions)
        self.assertEqual((agent.tools, agent.handoffs, agent.mcp_servers), ([], [], []))

    def test_platform_identity_is_checked(self):
        with self.assertRaises(ValueError):
            make_agent("art_director", load_config(), platform_spec=SimpleNamespace(id="wrong"))

    def test_observation_requires_reference(self):
        with self.assertRaises(ValidationError):
            Claim(kind="observed", statement="60 FPS", evidence=[])

    def test_milestone_cannot_be_marked_verified(self):
        with self.assertRaises(ValidationError):
            Milestone(id="M0", outcome="Forest", owner="QA", depends_on=[],
                      acceptance_evidence=["runtime"], state="verified")

    def test_dependency_cycle_is_rejected(self):
        with self.assertRaises(ValidationError):
            Handover(scope="planning_only", status="COMPLETE", recommendation="Plan",
                     claims=[], open_questions=[], critique=[], next_owner="Technical Lead",
                     milestones=[Milestone(id="A", outcome="A", owner="T", depends_on=["B"],
                                           acceptance_evidence=["runtime"], state="proposed"),
                                 Milestone(id="B", outcome="B", owner="T", depends_on=["A"],
                                           acceptance_evidence=["runtime"], state="proposed")])


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.original = {"name": "Original", "model": "model", "instructions": "Original instructions",
                         "reasoning": {"effort": "high", "summary": "auto"},
                         "text": {"format": {"type": "text"}, "verbosity": "medium"},
                         "service_tier": "auto", "tools": [], "metadata": {},
                         "multi_agent": {"enabled": False, "max_concurrent_subagents": None}}

    def test_clone_normalizes_request_but_verifies_original_definition(self):
        a, b = Mock(), Mock()
        a.beta.agents.retrieve.return_value = self.original
        b.beta.agents.create.return_value = SimpleNamespace(id="new")
        b.beta.agents.retrieve.return_value = copy.deepcopy(self.original)
        m = {"target_project": "target", "copies": {}}
        for _ in range(2):
            exact_clone(a, b, "old", m, lambda: None)
        self.assertEqual(b.beta.agents.create.call_count, 1)
        payload = b.beta.agents.create.call_args.kwargs
        self.assertNotIn("max_concurrent_subagents", payload["multi_agent"])
        self.assertEqual(m["copies"]["old"]["target_verified_sha256"], digest(self.original))

    def test_mismatch_stops_before_any_source_removal(self):
        a, b = Mock(), Mock()
        changed = {**self.original, "instructions": "Different"}
        b.beta.agents.retrieve.side_effect = [self.original, changed]
        m = {"expected_count": 2, "copies": {
            "old1": {"target_id": "new1", "source_sha256": digest(self.original)},
            "old2": {"target_id": "new2", "source_sha256": digest(self.original)}}}
        a.beta.agents.retrieve.return_value = self.original
        with self.assertRaises(ValueError):
            remove_verified_sources(a, b, m, lambda: None)
        a.beta.agents.delete.assert_not_called()

    def test_incomplete_copy_set_cannot_remove_sources(self):
        a, b = Mock(), Mock()
        with self.assertRaises(ValueError):
            remove_verified_sources(a, b, {"expected_count": 16, "copies": {}}, lambda: None)
        a.beta.agents.delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
