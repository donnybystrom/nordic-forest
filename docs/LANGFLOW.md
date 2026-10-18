# Installed Langflow bridge

Installed and checked on 18 October 2026 in IBM Langflow Desktop **1.12.6**. Project **Nordic Forest** contains three imported flows connected as **Chat Input → Nordic Job Bridge → Chat Output**. The existing empty New Flow was retained.

| Flow | Desktop flow ID | Operation |
| --- | --- | --- |
| 01 — Plan Feature | `8b3e1739-1731-46f8-896c-301b53cd0647` | Offline stage preview or a bounded chain of saved OpenAI agent sessions |
| 02 — Collect and Audit Reference | `b60f81f9-6cb9-4782-9e9f-992a72f05ee4` | Preview, or reuse/fetch an approved reference and run an isolated Blender audit |
| 03 — Propose Agent Change | `07941af9-0792-419e-b1d3-4caa34fe1409` | Candidate diff; optional Technical Lead and QA review; no publication |

Portable import files are in `flows/langflow/`; Desktop assigns its own IDs when importing. The component source is `integrations/langflow/nordic_job_bridge.py`. It uses the local HTTP bridge and does not require installing the project's OpenAI packages inside Desktop.

## Start and use

Run `tools/start_bridge.command`, or:

```sh
/opt/miniconda3/bin/python3 tools/manage_bridge.py start
/opt/miniconda3/bin/python3 tools/manage_bridge.py status
```

The [local dashboard](http://127.0.0.1:8765/) lists jobs, stages, handovers, audit evidence and reviewable proposal diffs. It links to [the GitHub board](https://github.com/users/donnybystrom/projects/2). Jobs and events persist in `runs/control/jobs.sqlite3`; large reports and logs remain below `runs/control/artifacts/`. These local files and the generated client credential are ignored by Git.

In a flow, enter the task in Chat Input or Playground. **Live** defaults to off in the import files. Turn it on deliberately for actual OpenAI calls or file/tool work. Run the bridge node or send a Playground message. A response containing `running` means that work continues in the backend; it is not a completed feature.

Repeated identical submissions with the same **Submission key** reuse the same job, including when refreshing a completed result. Change that advanced key to deliberately repeat the same work. For a different existing job, advanced **Action** supports `status`, `cancel` and `resume` with its **Existing job ID**. The dashboard can also inspect these states. Refreshing status does not start another billed job.

For the reference flow, supply one registered Sketchfab model UID/URL, for example `0ab534c493e14f67bac01ee94f20e43f`. A previously downloaded, hash-matching catalog source is reused. Otherwise the backend downloads a GLB through the restricted collector. An isolated Blender process imports it with startup scripts disabled, writes a new audit and verifies source identity. The operation performs file measurements, not an optimization, visual approval or engine benchmark.

For an agent proposal, the backend produces a candidate addition to the current role instructions and its diff/hash. Live mode obtains two separate saved-agent reviews. Evaluation remains `not_run`; the local browser can approve the proposal's direction or reject it. Neither decision publishes a platform agent, runs an evaluation suite, merges code or substitutes for a GitHub approval.

## Actual OpenAI runtime

This bridge uses `client.beta.agents.sessions.create(agent_id=...)`. It retrieves the saved role, verifies its instruction hash against the prepared job, stores the remote session ID and checks saved turns/items for a completed, schema-valid Handover. Five mandatory stages are Product → Technical → independent QA → one Technical integration → Curator; at most two specialists can be added.

Saved instructions/model are reused, with explicit session-only overrides: medium reasoning, the Handover output schema, no tools and no automatic subagents. Effective session overrides and role identity are recorded in the job. Role prompts remain planning-only. This is separate from the earlier SDK planning CLI, which constructs local Agent/Runner objects.

One local worker executes up to seven stage sessions per planning job; input is bounded to 65,000 characters per stage, provider requests have a 25-second timeout and the stage polling deadline is 150 seconds. Deadline/cancellation checks occur between blocking requests. A cancellation request is recorded before attempting to stop remote work; receipt alone does not count as a confirmed remote stop. The asset audit has a separate 120-second process deadline.

The installed SDK advertises `spend_control`, but the live endpoint rejected that create parameter with HTTP 400. The bridge therefore does **not** claim a hard USD cap or output-token cap for Agents API sessions. There is no automatic retry of an uncertain create. The rejected initial pilot and its diagnostic are retained; the subsequent supported request completed normally. [OpenAI session lifecycle](https://developers.openai.com/api/docs/guides/agents-api/sessions), [configuration](https://developers.openai.com/api/docs/guides/agents-api/configuration).

## Persistence, access and interruption

The service binds only to `127.0.0.1:8765`. Requests require a generated local bearer credential or local browser session. Host/Origin checks reject cross-origin browser requests; provider keys stay in the backend. A one-use same-origin nonce bootstraps the dashboard's HttpOnly/SameSite cookie. This is a local single-user pilot, not multi-user identity isolation: the browser's review event does not cryptographically establish which human clicked it.

A caller-provided idempotency key is unique in SQLite; reusing it with a changed request is rejected. Jobs pin context and instruction hashes. On service restart, running work becomes `interrupted`; explicit resume reconciles an existing remote session and reuses completed stage results. If a create outcome is unknown and no session ID was saved, resume refuses to dispatch again. The UI can request cancellation; `remote_cancel_unconfirmed` remains distinct from `cancelled`.

Use `tools/manage_bridge.py stop` or `restart`; stop refuses while jobs are active. No login item, public tunnel, background schedule or extra MCP server was installed. On this Mac, the sandboxed detached service's Blender children crashed before the audit script during native startup. Restarting the bounded service with normal native system access allowed the real audit to finish. Do not label those failed jobs successful or hide their retained logs.

## MCP is optional

A saved-agent API call does not require MCP. Langflow's **Project → MCP Server** exposes enabled flows as tools to another client. **MCP sidebar / Settings → MCP Servers** consumes external tools. Neither direction automatically imports saved OpenAI agent definitions or shares Codex connectors. [Langflow server guide](https://docs.langflow.org/mcp-server), [client guide](https://docs.langflow.org/mcp-client).

The current planning sessions have no tool access. The bridge performs the separately approved acquisition/audit operation locally. A future project-tools MCP adapter can expose the same narrow operations to tool-using agents. A managed cloud session does not automatically see this Mac's localhost, files or Blender. [OpenAI MCP connections](https://developers.openai.com/api/docs/guides/agents-api/tools/mcp).

## Verification and remaining work

All three operations were exercised offline from imported Langflow flows; the proposal path was submitted from Playground. Plan Feature completed five actual saved-agent sessions. The reference path completed a real 29,988-triangle stick audit and repeated identical submission returned the same completed job. Unit tests cover authorization, idempotency, persistence, ambiguous dispatch, cached results, output validation and review hashes. Exact job IDs/results are recorded in `docs/bridge-verification.json`.

The GitHub board and issue hierarchy are provisioned separately through the explicit adapter. Continuous board/job synchronization, authenticated agent GitHub App identities, enforced human merge gates, shared semantic memory, autonomous implementation and evaluated agent publication remain separate work. See [the indie workflow](INDIE-WORKFLOW.md) and [the broader architecture](AGENT-PLATFORM.md).
