"""Bounded sequential planning using Agents SDK and optional saved-agent settings.

The platform bridge retrieves configuration; it does not run a hosted Agents API
session or copy its tools, environment, instructions or delegation settings.
"""
import asyncio
import hashlib
import json
import os
import re
from pathlib import Path

from agents import Agent, ModelSettings, OpenAIResponsesModel, RunConfig, Runner
from openai import AsyncOpenAI
from openai.types.shared import Reasoning

from .contracts import Handover

ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{20,}")


def load_config():
    return json.loads((ROOT / "config/agents.json").read_text())


def read_project_text(path: Path) -> str:
    path = path.resolve()
    allowed = [ROOT / name for name in ("docs", "examples", "data", "prompts")]
    if not any(path.is_relative_to(base) for base in allowed):
        raise ValueError("Input must be inside docs, examples, data or prompts")
    if path.suffix not in {".md", ".txt", ".json"} or path.stat().st_size > 100000:
        raise ValueError("Unsupported input file or size")
    text = path.read_text()
    if SECRET_PATTERN.search(text):
        raise ValueError("Credential-like content rejected")
    return text


def instructions_for(role, config):
    return read_project_text(ROOT / "prompts/shared.txt") + "\n\n" + read_project_text(
        ROOT / config["roles"][role]["prompt"]
    )


def stages_for(specialists, config):
    if len(specialists) != len(set(specialists)):
        raise ValueError("Duplicate specialist")
    if len(specialists) > config["limits"]["max_specialists"]:
        raise ValueError("Too many specialists")
    if any(role not in config["specialist_roles"] for role in specialists):
        raise ValueError("Unknown specialist")
    stages = [("product_brief", "product_lead"), ("technical_plan", "technical_lead")]
    stages += [("specialist_" + role, role) for role in specialists]
    stages += [("independent_plan_review", "qa"), ("integrate_critique", "technical_lead"),
               ("planning_handover", "curator")]
    if len(stages) > config["limits"]["max_calls"]:
        raise ValueError("Model call limit exceeded")
    return stages


def load_key(key_file=None):
    if key_file:
        keys = set(SECRET_PATTERN.findall(Path(key_file).read_text()))
        if len(keys) != 1:
            raise ValueError("Key file must contain one unambiguous OpenAI key")
        return keys.pop()
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("Set OPENAI_API_KEY or use --key-file")
    return key


def make_agent(role, config, client=None, platform_spec=None):
    spec = config["roles"][role]
    model = spec.get("model", config["model"])
    effort = spec["reasoning"]
    if platform_spec is not None:
        if platform_spec.id != spec.get("platform_agent_id"):
            raise ValueError("Platform agent ID does not match role binding")
        model = platform_spec.model
        effort = platform_spec.reasoning.effort or effort
    return Agent(
        name=spec["name"], instructions=instructions_for(role, config),
        model=OpenAIResponsesModel(model, client) if client else model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort=effort),
            max_tokens=config["limits"]["max_output_tokens_per_call"], store=False,
        ),
        output_type=Handover, tools=[], handoffs=[], mcp_servers=[],
    )


def prepare(request_file, specialists, config, use_platform_settings=False, reasoning_override=None):
    if reasoning_override not in {None, "low", "medium", "high", "xhigh", "max"}:
        raise ValueError("Unsupported reasoning override")
    request = read_project_text(Path(request_file))
    # Explicit small inputs. No repository crawl; no key file or remote instruction upload.
    context_paths = ["docs/PROJECT.md", "docs/ROADMAP.md", "docs/decisions/0001-engine.md"]
    for role in specialists:
        if role in config["roles"]:
            for path in config["roles"][role].get("context_files", []):
                if path not in context_paths:
                    context_paths.append(path)
    context = {path: read_project_text(ROOT / path) for path in context_paths}
    stages = stages_for(specialists, config)
    agent_info = []
    for stage, role in stages:
        agent = make_agent(role, config)
        agent_info.append({"stage": stage, "role": role, "model": config["roles"][role].get("model", config["model"]),
                           "reasoning": reasoning_override or config["roles"][role]["reasoning"],
                           "instruction_sha256": hashlib.sha256(agent.instructions.encode()).hexdigest(),
                           "platform_agent_id": config["roles"][role].get("platform_agent_id"),
                           "settings_source": "platform_on_live_run" if use_platform_settings and
                           config["roles"][role].get("platform_agent_id") else "local"})
    return {"scope": "planning_only", "status": "prepared_offline", "remote_calls": 0,
            "request": request, "context": context, "stages": agent_info,
            "use_platform_settings": use_platform_settings, "reasoning_override": reasoning_override,
            "limits": config["limits"],
            "results": [], "feature_verification": "not_performed"}


def reserve_run_dir(path):
    path = Path(path).resolve()
    runs = ROOT / "runs"
    if not path.is_relative_to(runs) or path == runs:
        raise ValueError("Output must be a new subdirectory of runs/")
    path.mkdir(parents=True, exist_ok=False)
    return path


def save_packet(packet, directory):
    # Never write credential-looking model outputs into a persistent run artifact.
    text = json.dumps(packet, indent=2, ensure_ascii=False) + "\n"
    if SECRET_PATTERN.search(text):
        raise ValueError("Credential-like output rejected")
    tmp = directory / "packet.tmp"
    tmp.write_text(text)
    tmp.replace(directory / "packet.json")


def stage_payload(packet, stage):
    # Each specialist sees the same initial brief and plan, not other specialists' opinions.
    previous = packet["results"]
    if stage.startswith("specialist_"):
        previous = [r for r in previous if r["stage"] in {"product_brief", "technical_plan"}]
    return json.dumps({"task": stage, "request": packet["request"],
                       "project_documents": packet["context"], "previous_outputs": previous,
                       "instruction": "Propose and critique only. Do not claim implementation or feature acceptance. "
                       "Keep this handover small: at most 3 milestones, 5 claims and 3 open questions. "
                       "Include every referenced milestone in your dependency graph."},
                      ensure_ascii=False)


async def run_live(packet, config, directory, key_file=None):
    key = load_key(key_file)
    client = AsyncOpenAI(api_key=key, organization=config["organization_id"],
                         project=config["project_id"], base_url="https://api.openai.com/v1",
                         default_headers={"Accept-Encoding": "identity"},
                         max_retries=0, timeout=config["limits"]["call_timeout_seconds"])
    packet["status"] = "running"
    save_packet(packet, directory)
    try:
        async with asyncio.timeout(config["limits"]["workflow_timeout_seconds"]):
            cache = {}
            for stage in packet["stages"]:
                role = stage["role"]
                remote = None
                if packet["use_platform_settings"] and stage["platform_agent_id"]:
                    aid = stage["platform_agent_id"]
                    if aid not in cache:
                        cache[aid] = await client.beta.agents.retrieve(aid)
                    remote = cache[aid]
                agent = make_agent(role, config, client, remote)
                if packet.get("reasoning_override"):
                    agent.model_settings.reasoning = Reasoning(effort=packet["reasoning_override"])
                payload = stage_payload(packet, stage["stage"])
                characters = len(payload) + len(agent.instructions) + len(json.dumps(Handover.model_json_schema()))
                if characters > config["limits"]["max_input_characters_per_call"]:
                    raise ValueError("Input character budget exceeded; split the task")
                model_name = remote.model if remote else config["roles"][role].get("model", config["model"])
                stage["resolved_model"] = model_name
                stage["resolved_reasoning"] = agent.model_settings.reasoning.effort
                stage["settings_source"] = "platform_settings_with_local_forest_instructions" if remote else "local"
                print(f"Running {stage['stage']} ({model_name})", flush=True)
                packet["remote_calls"] += 1
                save_packet(packet, directory)
                result = await asyncio.wait_for(
                    Runner.run(agent, payload, max_turns=1,
                               run_config=RunConfig(tracing_disabled=True,
                                                    trace_include_sensitive_data=False)),
                    timeout=config["limits"]["call_timeout_seconds"],
                )
                handover = Handover.model_validate(result.final_output)
                packet["results"].append({"stage": stage["stage"], "role": role,
                                           "handover": handover.model_dump(mode="json"),
                                           "usage": {"input_tokens": result.context_wrapper.usage.input_tokens,
                                                     "output_tokens": result.context_wrapper.usage.output_tokens}})
                save_packet(packet, directory)
        packet["status"] = "planning_complete"
    except BaseException as exc:
        # Error bodies may echo inputs or credentials. Persist only the exception class.
        packet["status"] = "failed"
        packet["error_type"] = type(exc).__name__
        save_packet(packet, directory)
        raise
    finally:
        await client.close()
    save_packet(packet, directory)
    return packet
