# Sources and verification register

Official documentation was checked on 18 October 2026. Recommendations, density values, performance gates and team design are project proposals, not claims established by those sources.

| Source | What it supports |
| --- | --- |
| [OpenAI Agents API configuration](https://developers.openai.com/api/docs/guides/agents-api/configuration) | Saved reusable agents, `agent_id` sessions and session overrides |
| [OpenAI Agents API reference](https://developers.openai.com/api/reference/python/resources/beta/subresources/agents) | Project-scoped agent list/retrieve/create/update/delete interfaces |
| [OpenAI agent creation schema](https://developers.openai.com/api/reference/resources/beta/subresources/agents/methods/create) | Explicit tools, model, reasoning and delegation configuration |
| [OpenAI Agents SDK](https://developers.openai.com/api/docs/guides/agents/sdk) | Local SDK runtime versus managed Agents API runtime |
| [OpenAI orchestration](https://developers.openai.com/api/docs/guides/agents/orchestration) | Agent-as-tool versus ownership handoff patterns |
| [OpenAI model configuration](https://developers.openai.com/api/docs/guides/agents/models) | Explicit model/settings and stored prompt surfaces |
| [GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol) | Model ID, reasoning levels and Responses tool-calling requirement |
| [OpenAI project creation](https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/projects/methods/create) | Organization administration endpoint; separate from project agent management |
| [Godot renderers](https://docs.godotengine.org/en/stable/tutorials/rendering/renderers.html) | Metal driver and Mobile/Forward+ feature differences |
| [Epic macOS requirements](https://dev.epicgames.com/documentation/unreal-engine/macos-development-requirements-for-unreal-engine) | Apple Silicon rendering feature requirements |
| [Godot skeleton retargeting](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html) | Rest-transform and bone mapping issues in skeletal transfer |
| [Langflow agents](https://docs.langflow.org/agents) | Langflow's own agent/component execution surface |
| [Langflow API Request](https://docs.langflow.org/api-request) | A possible HTTP adapter component; no automatic SDK import |
| [Skogskunskap site descriptions](https://www.skogskunskap.se/skota-skog/foryngra/planera-och-forbered-foryngringen/standortsanpassad-foryngring/) | Site moisture, fertility and vegetation categories; not complete natural-forest generation rules |
| [Skogskunskap mixed woodland](https://www.skogskunskap.se/skota-skog/roja/roja-for-blandskog/) | Mixed-species context and damp-site birch examples; locality still matters |
| [User's Wikipedia creature index](https://sv.wikipedia.org/wiki/Lista_%C3%B6ver_varelser_i_nordisk_folktro) | Starting vocabulary and research links, not a regional design specification |
| [Isof skogsrå](https://www.isof.se/folkminnen/amnesomraden/folktro-och-forestallningsvarldar/lar-dig-mer-om-vasen-i-folktron/vasengalleriet/skogsra) | Folklore variation, including northern overlap with vittra |

The two user-provided agent discussions are indexed with hashes in `input-sources.json`. Their OpenBumpkins context is not adopted as this project's scope. Local prompts combine one shared forest contract with one role-specific text file; the composed instruction hash is stored with each provisioned forest agent.

Local inspection found Python packages openai-agents 0.24.0, openai 3.35.1 and pydantic 2.14.1, plus Godot 4.7.1 and Blender 5.2.0 LTS. Langflow runs separately: IBM Langflow Desktop 1.12.0 is installed at `/Applications/Langflow .app`, and its local health/OpenAPI endpoints responded on port 7860 with API title Langflow and version 1.12.0.

`docs/VERIFICATION.md` records the final checks for this foundation. Runtime forest quality and base-M1 performance require the future M0 scene experiment.

## Agent platform and Langflow follow-up — checked 18 October 2026

- [OpenAI saved agent configuration](https://developers.openai.com/api/docs/guides/agents-api/configuration), [session lifecycle](https://developers.openai.com/api/docs/guides/agents-api/sessions), [architecture](https://developers.openai.com/api/docs/guides/agents-api/architecture), [managed delegation](https://developers.openai.com/api/docs/guides/agents-api/multi-agent), [MCP connections](https://developers.openai.com/api/docs/guides/agents-api/tools/mcp), [SDK orchestration](https://developers.openai.com/api/docs/guides/agents/orchestration) and [session memory example](https://developers.openai.com/cookbook/examples/agents_sdk/session_memory). Distinguish platform definitions, managed sessions and local SDK runs.
- [Langflow Agent component](https://docs.langflow.org/components-agents), [OpenAI model bundle](https://docs.langflow.org/bundles-openai), [custom Python components](https://docs.langflow.org/components-custom-components), [HTTP requests](https://docs.langflow.org/api-request), [MCP client](https://docs.langflow.org/mcp-client) and [MCP server](https://docs.langflow.org/mcp-server). Local Desktop and OpenAPI now report 1.12.6; documentation capabilities still need end-to-end integration tests in that runtime.
- [Linear milestones](https://linear.app/docs/project-milestones), [official MCP server](https://linear.app/docs/mcp), [agent integration](https://linear.app/developers/agents) and [webhooks](https://linear.app/developers/webhooks). The proposed recommendation is a product choice; no account connection or board has been created.
- [GitHub Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects), the alternative with board, table and roadmap views alongside issues and pull requests.

Downloaded reference metadata, source hashes and measured summaries are indexed in [the reference catalog](../data/references/catalog.json) and [the first audit](REFERENCE-FIRST-AUDIT.md). Public model descriptions remain author claims wherever a measurement has not established the property.
