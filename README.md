# Nordic 3D Forest

A playable Swedish forest for a mystical survival game set around a northern village. The first deliverable is a small, convincing forest that can be edited, regenerated and measured. Biome authoring and character production share versioned data and editable source assets.

Start with [the project brief](docs/PROJECT.md), [the milestone roadmap](docs/ROADMAP.md) and [the proposed engine experiment](docs/decisions/0001-engine.md). The working recommendation is Godot 4 and Blender; the engine decision awaits the actual M1 scene comparison.

Try the [character physics lab](https://donnybystrom.github.io/nordic-forest/): two zombies, shared animation controls and a draggable physics ball. The [web build instructions](docs/CHARACTER-REVIEW.md#github-pages) describe deployment and local testing. The prototype uses virtual pelvis support; autonomous balance and recovery stepping remain future work.

## What is here

- [Agent orchestration](docs/AGENT-WORKFLOW.md): project separation, role mandates, platform configuration and the local Python planning harness.
- [Biome and asset production](docs/PRODUCTION-PIPELINES.md): procedural rules, painted overrides, textures, models, concept identity and animation.
- [Beach zombie experiment](docs/experiments/ZOMBIE-BEACH.md): proposed image-to-rig pipeline, anatomical damage, prepared fractures and adaptive Godot movement.
- [Reference asset analysis](docs/REFERENCE-ASSET-PIPELINE.md): scanned resources, tree construction/LOD recipes, game/mod evidence and a Blender mesh inspector.
- [Sketchfab acquisition](docs/ASSET-ACQUISITION.md): token-backed downloads, source manifests and a bounded SDK download tool.
- [Planning board and agent tickets](docs/PLANNING-BOARD.md): live GitHub views, milestones and explicit Ready-ticket planning dispatch.
- [Indie work management](docs/INDIE-WORKFLOW.md): GitHub Projects, feature/story ownership, PR review and CI.
- [Repository assets](docs/REPOSITORY-ASSETS.md): large reference files, staging cleanup and when to use LFS.
- [Shared agent platform](docs/AGENT-PLATFORM.md): shared control architecture, agent change review and scoped memory.
- [Langflow integration](docs/LANGFLOW.md): the installed planning, role and PR flows and local job service.
- [Source register](docs/SOURCES.md): official technical documentation and starting points for ecology and regional folklore.

This is a planning and pipeline foundation. There is no main-game scene, biome generator, paint editor or accepted production art yet. The separate [beach zombie experiment](output/zombie-beach/rodin-tpose-v1/README.md) now uses the new Rodin T-pose source with a fitted 52-bone rig, 13 transferred clips and a working Godot animation reviewer. Blender/GLB roundtrip, Godot import and review controls have focused checks; contact cleanup, physics and procedural gameplay remain pending. The Langflow bridge and local job dashboard are installed; broader shared memory and agent publication remain future work. Local role prompts and platform configuration are separate artifacts; consult the agent workflow for the verification boundary.

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

## Langflow bridge

Open the **Nordic Forest** project in IBM Langflow Desktop. Start with **05 — Planning Board** for tickets and **04 — PR Control** for delivery. The original **01 — Plan Feature**, **02 — Collect and Audit Reference**, and **03 — Propose Agent Change** remain available. Those three connect Chat Input → Nordic Job Bridge → Chat Output. All imported templates start offline by default.

Start the service with `tools/start_bridge.command`, then open [the local dashboard](http://127.0.0.1:8765/). Use `/opt/miniconda3/bin/python3 tools/manage_bridge.py status`, `stop` or `restart` to manage it. No login item or public tunnel was installed. On this Mac, Blender jobs require launching the local service with access to native system/Metal detection; a tightly sandboxed service crashed before its audit script.

Alla 15 Nordic Forest-roller är nu installerade som sparade Langflow-komponenter och individuella flöden. Se [Langflow: individuella agenter](docs/LANGFLOW.md) för Task, Upstream context och Tool Mode. Alla 15 har genomfört riktiga integrationstest via Langflows verktygsgränssnitt; körvägen lämnar planeringsunderlag.

PR-publicering, lokala kodgranskningar och första delegerade merge-kategorin finns i [PR-rutinen](docs/PR-DELIVERY.md). Roller delar GitHub-konto; den lokala orkestratorn sparar roll- och revisionsidentitet.

GitHub planning is available in **05 — Planning Board** and **NF · Planning Board**. Open the [live board](https://github.com/users/donnybystrom/projects/2); see [commands and recovery](docs/PLANNING-BOARD.md).
