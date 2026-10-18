# Foundation verification

Checked on 18 October 2026. This verifies project configuration and the planning harness, not game visuals or runtime performance.

## Initial platform split

- Nordic Forest project `proj_prCcGUHbiAHQGz8UmHcwjUKG`: final list contained exactly the 14 newly provisioned forest agent IDs.
- Beasts & Bumpkins project `proj_sBhh0dtFlUyaAAAKqMBy0jII`: final list contained exactly the 16 copied original agent IDs.
- All copied configuration fields matched canonical SHA-256 hashes: name, model, instructions, reasoning, text, service tier, tools, multi-agent settings and metadata. Both Art Directors were retained.
- Every original source-removal flag is recorded in `config/project-migration.json`; its phase is `complete`. Full before/after definitions are retained under `runs/platform-inventory/`.
- All 14 forest instruction hashes matched the composed local prompts. Tools were empty and automatic subagents were disabled on every forest definition.
- Organization project administration and renaming the current project returned HTTP 403 with the service-account key. The user subsequently confirmed changing its display name to **Nordic Forest**, without a hyphen.

## Local checks

Initial run: `python3 -m unittest discover -s tests -v`: 13 tests passed. The checks cover offline isolation from credential/API use, input path restrictions, specialist/call limits, wall-clock timeout persistence without retry, platform identity, explicit reasoning overrides, exclusion of hosted tools/instructions, evidence requirements, proposed-only milestone state, dependency cycles and migration safeguards.

`python3 -m compileall -q forest_agents tests` passed. Configuration and biome draft JSON parsed. Local documentation links resolved. A credential-pattern scan of non-secret, non-run project artifacts found no credential values.

`runs/forest-plan-offline/packet.json` was prepared with ecology and rendering specialists and platform bindings: seven proposed stages, zero remote calls and no feature verification. It is an execution plan, not model-generated output.

## Live planning pilot

The initial run at `runs/forest-plan-live-pilot/packet.json` completed Product Lead with 3,501 input tokens and 3,260 output tokens. The following Technical Lead request reached the 90-second API timeout. The partial packet is retained; the failed request may have incurred usage that was not returned. No automatic retry occurred.

The medium-reasoning follow-up completed all five stages: Product Lead, Technical Lead, independent plan review, one Technical Lead integration and Curator handover. `runs/forest-plan-live-medium/packet.json` has `status=planning_complete`, five attempted/successful model calls and all five resolved effort settings equal to medium. Returned usage totaled 37,592 input tokens and 12,288 output tokens. This did not alter the saved platform effort settings.

Every returned handover passed the Pydantic contract with `scope=planning_only` and proposed-only milestone states. QA identified gaps in the comparison matrix, dense-cover timing and timing-source validation. The single integration addressed them in its proposed protocol, and the engine decision now explicitly separates common-feature and enhanced-atmosphere comparisons and measures the stress view. No renderer or feature acceptance is implied by that planning result. Optional specialist branches were prepared offline and tested structurally; they were not included in the completed five-stage live pilot.

## Tool installation

Python inspection found openai-agents 0.24.0, openai 3.35.1 and pydantic 2.14.1. Godot reported 4.7.1 and Blender reported 5.2.0 LTS. The initial IBM Langflow Desktop and local OpenAPI observation reported 1.12.0; `/health` returned HTTP 200 on port 7860.

The installed SDK's HTTP client hit a response-decompression compatibility error during the first agent inventory attempt. Explicit `Accept-Encoding: identity` avoided that error for the subsequent configuration operations and initial successful inference. This is a transport workaround, not a tested repair of the installed compression dependencies.

## Remaining acceptance work

The initial foundation had no native Langflow workflow or managed Agents API session. The installed bridge follow-up below supersedes that limitation. The planning agents have no repository/shell, Blender/Godot or generation tools attached. The separately tested SDK acquisition agent has a restricted Sketchfab download tool. No biome generator/editor, game scene, concept/video asset, mesh, rig or animation was produced. Actual visual, ecological, authoring and M1 performance acceptance belongs to the roadmap experiments.

## Reference collection and current Langflow inspection

The forest catalog now contains 15 saved roles after the Reference and Asset Analysis Engineer addition. Five affected role definitions were synchronized and all 15 composed instruction hashes matched the remote definitions. Tools remain empty and automatic delegation disabled in these saved roles; this is separate from the tool-enabled local acquisition runner.

The current interpreter is `/opt/miniconda3/bin/python3` (Python 3.12.3); `python3` can resolve to Xcode Python 3.9 without the required dependencies. With the verified interpreter, all 20 unit tests passed, covering the original workflow plus reference context, download allowlists, tool schema and safe archive handling. Compile checks, local documentation links, reference source hashes and an exact-value credential scan of non-secret text artifacts passed.

A synthetic Blender source/GLB smoke test passed for measured geometry, shared meshes, source preservation and overwrite rejection. Real isolated imports completed for the oak source FBX (75 mesh objects), converted oak GLB (131 material-split mesh objects, 409,422 triangles) and converted stick GLB (one mesh, 29,988 triangles). Source hashes were preserved; see `data/references/analysis/` and `REFERENCE-FIRST-AUDIT.md`. One earlier background Blender launch crashed during Metal startup before Python; retry succeeded. These checks establish file import/audit behavior, not visual or engine acceptance.

The actual SDK acquisition pilot at `runs/sketchfab-live-collection/packet.json` completed one restricted tool call and downloaded the requested stick GLB. Returned model usage: 1,084 input tokens / 128 output tokens. The validated handover names the actual generated manifest. No original stick author archive was claimed.

Desktop's Info.plist and the current local OpenAPI service now report Langflow **1.12.6** (Desktop build `20261014.3171`), superseding the initial 1.12.0 observation. Native UI inspection confirmed the Nordic Forest project and its empty New Flow. A standard Agent node was temporarily added, inspected and removed; the empty canvas was verified again. No key was entered and no Langflow inference ran. Unauthenticated management API reads returned HTTP errors; authentication was not disabled.

The earlier design-only checkpoint has been superseded for the bridge, job service and three imported flows. Shared semantic memory, agent publication and full multi-project authorization remain unimplemented; GitHub Projects was selected instead of Linear.

## Installed bridge and GitHub Projects follow-up

All 38 offline unit tests passed with the verified Python 3.12 interpreter. The three secret-free flow files were imported into Nordic Forest and exercised offline; the agent proposal was submitted through Playground. Plan Feature completed five actual saved-agent sessions with schema-validated handovers. The real reference flow audited Wood Stick 02 as one mesh / 29,988 triangles, retained the source hash and reused the same completed job on a repeated submission. See `bridge-verification.json` for IDs and limits.

The first session-create request was rejected with HTTP 400 because this endpoint did not support the installed SDK's `spend_control` parameter. No session was listed for that rejected pilot. The supported request omits that field and does not claim a hard dollar cap. Two audit attempts crashed during Blender startup in the tightly sandboxed detached service; launching the local service with normal native system access allowed the isolated audit to finish. Failures and logs remain retained separately from success.

The private GitHub Project at https://github.com/users/donnybystrom/projects/2 contains five repository issues, three explicitly named visual views and two native story-to-feature parent links. Bootstrap preserves edited fields on existing items. Sprint is initially a portable text field; dated Iteration scheduling is not claimed. Continuous board synchronization and enforced human merge gates are not implemented.

Git staging cleanup removed 2,235 raw Skyrim reference files (5,794,975,426 bytes on disk) from the index without deleting any working file. No such input was in the initial committed tree. The checkpoint left 76 indexed files, about 2.7 MB of blobs, with a largest blob of 899,736 bytes. The source-input guard and Git ignores prevent ordinary additions of the reference payloads; no history rewrite or LFS migration was performed.

## Individuella Langflow-agenter · 2026-10-18

15 sparade komponenter under Saved, 15 Agent-flöden och en canvasöversikt installerades i Nordic Forest. Alla 15 sparade OpenAI-konfigurationer verifierades mot lokala instruktionhashar. Alla 15 klarade offline-bindning och verktygsschema; samtliga 15 genomförde därefter separata verkliga anrop via Langflows to_toolkit/ainvoke, med överlämningskontext mellan rollerna. Detta verifierar integrationen, inte featureacceptans eller generell agentkvalitet. 44 lokala enhetstester och Python-kompilering passerade. Se [individuellt verifieringsunderlag](individual-agent-verification.json).
