# Nordic 3D Forest

A playable Swedish forest for a mystical survival game set around a northern village. The first deliverable is a small, convincing forest that can be edited, regenerated and measured. Biome authoring and character production share versioned data and editable source assets.

Start with [the project brief](docs/PROJECT.md), [the milestone roadmap](docs/ROADMAP.md) and [the proposed engine experiment](docs/decisions/0001-engine.md). The working recommendation is Godot 4 and Blender; the engine decision awaits the actual M1 scene comparison.

## What is here

- [Agent orchestration](docs/AGENT-WORKFLOW.md): project separation, role mandates, platform configuration and the local Python planning harness.
- [Biome and asset production](docs/PRODUCTION-PIPELINES.md): procedural rules, painted overrides, textures, models, concept identity and animation.
- [Reference asset analysis](docs/REFERENCE-ASSET-PIPELINE.md): scanned resources, tree construction/LOD recipes, game/mod evidence and a Blender mesh inspector.
- [Sketchfab acquisition](docs/ASSET-ACQUISITION.md): token-backed downloads, source manifests and a bounded SDK download tool.
- [Shared agent platform](docs/AGENT-PLATFORM.md): proposed multi-project control service, agent change review, scoped memory and Linear.
- [Langflow integration](docs/LANGFLOW.md): a proposed visual interface around the same workflow, without duplicating orchestration.
- [Source register](docs/SOURCES.md): official technical documentation and starting points for ecology and regional folklore.

This is a planning and pipeline foundation. There is no game scene, biome generator, paint editor, finished art, rig, animation importer or live Langflow integration yet. Local role prompts and platform configuration are separate artifacts; consult the agent workflow for the verification boundary.

The OpenAI projects are separated: Nordic Forest contains the forest role catalog, and `proj_sBhh0dtFlUyaAAAKqMBy0jII` contains verified copies of all 16 original definitions. [The migration map](config/project-migration.json) preserves every old/new agent ID and configuration hash. The user confirmed the project display name is now **Nordic Forest**, without a hyphen.

## Run locally

Use Python 3.11 or later. The verified interpreter is `/opt/miniconda3/bin/python3`; the shell's `python3` may instead resolve to Xcode Python 3.9. The inspected Python already has the pinned dependencies. If needed, install into a project virtual environment with `python3 -m pip install -e .`. Dependency versions are pinned directly in `pyproject.toml`; a full transitive lock remains future work.

```sh
python3 -m forest_agents doctor
python3 -m forest_agents plan --specialist ecology --specialist rendering
python3 -m unittest discover -s tests -v
```

`plan` prepares a run packet offline, without reading credentials or calling an API. Inspect `runs/<timestamp>/packet.json`. To run billed model calls explicitly:

```sh
python3 -m forest_agents plan --use-platform-settings --reasoning medium --live --key-file OPENAI_API_SECRET_KEY.md
```

The platform option retrieves saved agents' model/reasoning settings. The SDK runs local forest instructions and structured outputs, with no tool execution or automatic subagents. It does not launch a hosted Agents API session. The CLI uses the configured organization and project explicitly. Request files must be inside `docs/`, `examples/`, `data/` or `prompts/`; results go into a fresh `runs/` directory.

`--reasoning medium` overrides saved reasoning for this run only and is the starting pilot profile. Omit it to use each role's saved setting. Add specialist flags when a task needs those perspectives.

Both service-account key files, `.env` files and `runs/` are ignored. Do not paste keys into prompts or commit them. Agent IDs, project IDs and instruction hashes are safe configuration references and do not provide authentication.
# nordic-forest
