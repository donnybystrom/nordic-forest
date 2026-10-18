# Agent workflow and project separation

Current execution adapters: [Langflow and saved roles](LANGFLOW.md), [local PR delivery and review profiles](PR-DELIVERY.md). The earlier SDK-only stages below are historical checkpoints; they do not describe the full current bridge. Separate GitHub identities are not required for the local role model.

The organization is `org-mOUZocPcLddOyV1Bgcfj0inC` (the user identified its display name as Personal). Use IDs rather than casing to distinguish it from the other personal organization.

| Project | Purpose | Credential file |
| --- | --- | --- |
| `proj_prCcGUHbiAHQGz8UmHcwjUKG` | Nordic Forest agents and runs | `OPENAI_API_SECRET_KEY.md` |
| `proj_sBhh0dtFlUyaAAAKqMBy0jII` | Preserved Beasts & Bumpkins role definitions | `BEASTS_BUMPKINS_OPENAI_API_SECRET_KEY.md` |

The user supplied a scoped service-account key for each project. Organization project administration returned HTTP 403 with the first key; creating the second project required the human's platform access. Agent configuration is accessible through the project keys.

## Platform agents and SDK agents

The supplied `agent_…` identifier belongs to the current Agents API. The official [configuration guide](https://developers.openai.com/api/docs/guides/agents-api/configuration) shows saving an agent and starting a hosted session with `agent_id`. [List/retrieve operations](https://developers.openai.com/api/reference/python/resources/beta/subresources/agents) are available through `client.beta.agents`. These objects differ from stored prompts, legacy Assistants and Agent Builder workflows.

The [Agents SDK](https://developers.openai.com/api/docs/guides/agents/sdk) runs in our Python application. Our adapter retrieves a saved agent's model and reasoning configuration and constructs an SDK `Agent` using the reviewed local forest instructions and `Handover` output schema. It does not transfer the hosted harness, tools, environment, history or delegation behavior. This keeps the first pipeline bounded and reproducible. A future hosted-session adapter is a separate implementation choice.

All new forest definitions use explicit Nordic Forest context, no tools and disabled automatic subagents. Do not infer Blender, repository, video-generation or shell access from their titles. Add capabilities only at a separately provisioned execution boundary. Existing Beasts & Bumpkins copies retain their original settings, including their original web-search and multi-agent configuration.

## Migration evidence

The original inventory contained 16 definitions: 15 explicitly named OpenBumpkins in their instructions and one older generic Art Director. There were two Art Director definitions. Preserve both; identify them by ID rather than name. No source project sessions were present in the initial list check.

The split operation creates new definitions in the destination, reads back every configuration field and compares a canonical SHA-256 before removing source definitions. The API does not expose a project reassignment field in agent update. New agent IDs are expected; this is a verified copy/remove migration of definitions, not a transfer of sessions, traces, environments or resource IDs.

`config/project-migration.json` records original IDs, destination IDs, definition hashes and removal status. The full initial export is in `runs/platform-inventory/agents.json`. `config/platform-agents.json` is the historical initial inventory; it is not the current Nordic agent list. `config/nordic-platform-agents.json` and `config/agents.json` hold the forest bindings. Read the migration's actual phase/removal flags before treating the split as complete.

The final readback verified 16 original definitions in Beasts & Bumpkins and 14 forest definitions in Nordic Forest, with exact ID sets and configuration hashes. All 16 source-removal flags are recorded. Agent lists briefly lagged the deletions; a later complete list established the final state.

## Team and decision ownership

| Role | Mandate and output | Default model / reasoning |
| --- | --- | --- |
| Human product owner | Product scope, locality/era, visual approval | Human |
| Product Lead | Small outcome, priorities, non-goals and acceptance proposal | gpt-6.1-sol / medium |
| Technical Lead | System boundaries, ranked technical decisions and owned work packages | gpt-6.1-sol / high |
| Reference and Ecology Analyst | Species/layer rules and ecological evidence/uncertainty | gpt-6.1-sol / high |
| Reference and Asset Analysis Engineer | Source/dependency inventory, tree/LOD construction, supplied game/mod evidence and reusable recipe proposals | gpt-6.1-sol / high |
| Folklore and Narrative Researcher | Local accounts, variants and bounded encounter references | gpt-6.1-sol / medium |
| Art Director | Visual identity, reference sheets and review criteria | gpt-6.1-sol / medium |
| Technical Artist | Asset/material/LOD/rig/export contracts | gpt-6.1-sol / high |
| Rendering and Performance Engineer | Repeatable route measurements and quality tradeoffs | gpt-6.1-sol / high |
| Implementation Engineer | An assigned change with actual tool access, otherwise an implementation ticket | gpt-6.1-sol / medium |
| QA and Verification Engineer | Independent acceptance review and falsifiable experiments | gpt-6.1-sol / high |
| Knowledge Curator | Canonical evidence, decisions and next-owner handover | gpt-6.1-sol / medium |
| Developer Experience and Tooling Engineer | Reproducible setup, import and authoring workflows | gpt-6.1-sol / medium |
| UI and UX Designer | Player/author interaction and usability checks | gpt-6.1-sol / medium |
| Delivery Coordinator | Already approved scope into dependency-ordered tickets | gpt-6-luna / low |
| Security Reviewer | Concrete import, tool, credential or network boundaries | gpt-6.1-sol / high |

The 15 roles are a catalog, not 15 concurrent runs. Asset Analysis was added for the requested photogrammetry, tree-pack and game/mod pipeline, using forest context and the preserved Beasts & Bumpkins analysis role as provenance. Networking and modding roles stay with that project until needed. Model/effort defaults remain unmeasured choices for these roles. [Sol's documented reasoning levels](https://developers.openai.com/api/docs/models/gpt-6.1-sol) include medium and high; the project model list also exposed Sol and Luna. Model listing does not prove inference quality or the best cost/quality tradeoff.

Select the new branch with `--specialist asset_analysis --request-file examples/reference-analysis-request.txt`. Its explicit context includes the reference pipeline and catalog. This remains text-based planning: screenshots/model files are not automatically loaded or inspected by the API agent. The standalone Blender audit provides measurements for a later supplied evidence packet.

## Implemented planning flow

`Product brief → Technical plan → zero to three selected specialists → independent plan review → one Technical Lead integration → Curator handover`.

The CLI deliberately uses deterministic routing in Python, rather than a model to forward messages. Specialists execute sequentially and each receives the same brief/plan, not the other specialists' advice. QA sees their outputs; Technical Lead integrates once. The final curator preserves unresolved questions. The SDK also supports [agents as tools and handoffs](https://developers.openai.com/api/docs/guides/agents/orchestration); adopt them when dynamic selection or conversation ownership actually needs them.

Enforced in code: at most three selected specialists and eight model calls, one SDK turn per stage, 4,000 output tokens per call, a 70,000-character serialized input/schema/instruction check, 90 seconds per API call, 480 seconds per workflow, SDK retries disabled, no model-call tools or handoffs, explicit organization/project, and new output directories only. An output-token cap includes reasoning consumption and may result in an incomplete output; that run fails rather than silently accepting partial JSON.

There is no hard USD spend cap or exact input-token cap. Character limits are a payload bound, not a token count. Usage is saved after successful calls; a failed request may still have incurred cost without returning usage. Default tracing is disabled for this prototype; local packets contain the request, selected source documents, stage outputs and usage. Review these files before sharing.

The packet is saved after each stage, including failures. This is durable diagnostic state, not automatic resume: a new CLI invocation starts a new run and may repeat billed work. There is no automatic retry/review loop. A future job service needs explicit idempotency and safe resume semantics.

Use `--reasoning medium` for the first bounded planning pilot. This is an explicit runtime override of saved effort, recorded in the packet, and does not modify the platform definitions. The initial saved-effort pilot completed its product brief but timed out on the Technical Lead stage. Retain its partial packet as evidence; do not label it a completed workflow.

## Acceptance boundary

`COMPLETE` means the assigned planning deliverable is complete. Every output has `scope=planning_only`; every proposed milestone has `state=proposed`. The schema rejects cyclic/missing dependencies and unsupported milestone states, and requires evidence references for observations. A reference field cannot prove the referenced fact; independent verification remains necessary.

Actual implementation, engine execution, source control integration, role-specific write access, approval of product changes and feature acceptance remain separate steps in the roadmap. Do not attach a general shell and rely on a read-only sentence in a prompt as a sandbox.
