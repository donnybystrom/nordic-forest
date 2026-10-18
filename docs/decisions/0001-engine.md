# Engine selection experiment

Status: proposed. Recommendation: use Godot 4 with Blender for the first forest slice. Do not develop a custom renderer or engine at this stage. The installed tools were identified as Godot 4.7.1 and Blender 5.2.0 LTS; the project has not yet been rendered or benchmarked.

## Candidates

| Choice | Fit for this project | Main uncertainty | Rank |
| --- | --- | --- | --- |
| Godot 4 and Blender | Small editable pipeline, data-driven placement, custom authoring UI, direct control of rendering budgets | Whether the target density and atmosphere meet visual and frame-time criteria on the actual M1 | 1 |
| Unreal Engine | Strong candidate if the desired visual target benefits enough from its environment tools to justify a heavier workflow | M1 rendering feature limits, editor overhead and production complexity | 2 |
| Unity | Worth evaluating if a particular vegetation/terrain tool materially shortens authoring | Package quality, dependencies, maintenance and licensing need a separate current review | 3 |

These ranks are project judgments, not comparative benchmark results. Investigate Unity only if a concrete requirement justifies another toolchain.

## Rendering profiles

Godot's Mobile and Forward+ renderers both support Metal through RenderingDevice. Mobile supports depth/height fog but not volumetric fog, SSAO or screen-space reflections. Forward+ provides those features. Treat them as separate launch profiles, because a renderer change is not an ordinary live quality slider. See [Godot's renderer feature table](https://docs.godotengine.org/en/stable/tutorials/rendering/renderers.html).

- **M1 baseline:** Mobile, ordinary distance/height fog, controlled shadow distance, limited transparent layering, chunked instances, baked/probe lighting where useful. Test 1280×720 first.
- **Atmosphere:** Forward+, optional volumetric fog and additional lighting features, with measured caps. Establish whether this can run acceptably on M1 before promising it there.
- **High quality capture:** higher internal resolution and visual settings on hardware that passes the same route. This is not the baseline gameplay requirement.

For Unreal on macOS, Epic lists software Lumen for M1+, while Nanite and Virtual Shadow Maps require M2+ with beta support in the checked documentation. An M1 build therefore cannot assume the complete feature combination commonly seen in high-end Unreal demonstrations. See [Epic's macOS requirements](https://dev.epicgames.com/documentation/unreal-engine/macos-development-requirements-for-unreal-engine).

## Decision experiment

Use the same source meshes, materials, placement manifest, route and camera captures in Mobile and Forward+. Do not change vegetation density to hide a renderer cost without recording that difference. First implement only the Godot comparison; build an Unreal comparison only if a named visual criterion remains unmet.

Run two explicitly different comparisons. The **common-feature comparison** uses the same ordinary fog, lighting and supported effects in both renderers to expose their baseline cost. The **enhanced-atmosphere comparison** enables selected Forward+ effects and records each change; evaluate the extra visual value and cost separately. Do not attribute the cost of extra effects to the renderer alone.

Record chip, RAM, macOS, engine build, renderer/driver, power mode, display/internal resolution, VSync, antialiasing and all quality settings. Use a 30-second warmup and three 90-second route passes after import/shader warmup. Capture four fixed views in daylight and blue hour, plus a dense ground-cover stress view. Report cold-start/import and warm traversal separately.

Also measure three 30-second passes at the dense ground-cover stress view after warmup. Apply the chosen baseline frame-time gate to both the route and stress trials; still images alone do not verify the dense case. Record raw monotonic per-frame wall-clock intervals, frame IDs and engine monitor samples in the same trial. Cross-check total frame count/elapsed time against the engine profiler or an independent capture. Declare CPU/GPU timing sources separately; if GPU timers are unavailable, report that explicitly and do not relabel CPU submission time as GPU time.

Proposed baseline gate: p95 frame time at most 33.3 ms at 1280×720 on the actual base M1, with p99 and every hitch above 100 ms reported, memory recorded, and no repeated traversal hitch above 100 ms after warmup. A 60 FPS profile is an optimization target, not a promise. Thresholds require the human's agreement when M0 begins. Headless parsing cannot satisfy this gate.

A debug panel should expose vegetation density/view distance, LOD bias, shadow distance, wind, ordinary fog, exposure and supported lighting controls. Show unsupported features disabled with a short explanation. Persist settings per renderer profile; log changes into benchmark metadata.

Accept Godot when the visual criteria, authoring path and target Mac gate pass. Reconsider it when an important unmet criterion survives a bounded optimization experiment. Separate the engine decision from approval of the art direction.
