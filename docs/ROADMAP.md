# Nordic Forest milestone roadmap

All game milestones below are proposals. The planning foundation and project configuration are supporting deliverables; they do not establish a playable forest or completed M0. Work is ordered by evidence and dependencies, without invented dates or velocity.

| Milestone | Outcome and owner | Dependencies | Acceptance evidence |
| --- | --- | --- | --- |
| M0 | Decide engine/profile and visual target. Technical Lead, Art Director, Rendering Engineer | None | One representative Godot scene compared in Mobile and Forward+ on the target Mac; recorded settings and frame times; fixed-camera images reviewed by the human; decision and remaining limits documented |
| M1 | Walk through a convincing small forest. Implementation, Technical Artist | M0 | A reproducible seeded map, grounded collidable terrain, usable inspection controller, readable route, source asset register, three site types and visible transitions; actual traversal video and images; baseline measurement repeated |
| M2 | Edit the biome without destructive regeneration. Technical Artist, Ecology Analyst, Tools owner | M1 | Paint, erase, exclusion and pinned landmarks exercised in the real UI; save/reopen preserves masks, seed, pins and placements; changes affect the intended area; identical inputs reproduce instance IDs and transforms; exported engine view matches authoring manifest |
| M3 | Tune atmosphere within measured budgets. Rendering Engineer, Art Director | M1; M2 before tuning the final authored slice | Daylight/blue-hour presets and supported live sliders; restore/save/reload works; fixed route shows visual differences and p50/p95/p99, memory and hitches for each profile; settings do not alter biome source |
| M4 | Produce one consistent, animated creature in-engine. Art Director, Folklore Researcher, Technical Artist | M0; regional and creature choice from human | Approved identity sheet; source/license manifest; editable mesh/UV/materials/rig; one idle and walk clip; GLB round-trip; scale/rest pose/root/feet checked in engine; optional video capture route compared against hand animation |
| M5 | Play one folklore encounter near the village. Product Lead, Implementation, QA | M2, M3, M4 | Short complete route, one encounter with an observable state change and recovery path, sound cues and minimal village context; save/load for the implemented encounter state; playtest evidence and performance within the chosen budget |
| M6 | Expand a demonstrated pipeline. Technical Lead, Curator | M5 | Second biome/creature added using existing contracts; production time and exceptions recorded; only then decide more regions, seasons, survival systems or streaming |

M4 concept research and motion experiments can proceed alongside M1/M2 after M0; they need not block the initial forest. A first humanoid rig can validate the transfer route, but nonhumanoid beings need their own experiment.

## Reference asset workstream

**R0-001** supplies M0/M1's small asset kit through [source asset analysis](REFERENCE-ASSET-PIPELINE.md): one oak size/LOD family and one photogrammetry object. Start with the source/dependency inventory, then measure actual geometry/materials, derive a seeded construction recipe and compare the derivative in Godot. The oak is a technical case; Swedish species and site rules remain separate. Game binary/mod analysis begins with one named version and one vegetation family when files are supplied.

The metadata catalog, screenshot evidence and synthetic Blender audit check are available. Real reference mesh measurements, conversion, shader analysis and runtime acceptance remain pending. The Godot comparison is shared with M0 rather than an additional prerequisite that creates a dependency cycle.

## First ready work package

**M0-001 — renderer and authoring decision scene.** Technical Lead scopes one 128×128 m test site with a pine rise, a mesic patch and a damp hollow. Technical Artist supplies a tiny consistent tree/ground kit. Rendering Engineer compares the profiles in the engine decision. Art Director defines four review cameras and the properties that carry Swedish forest identity. QA checks the experiment against the human's M1 constraint.

Deliver a launchable scene, source/placement manifests, benchmark CSV/JSON, four matched images per profile and a one-page decision. Do not implement a full biome editor, village, survival system or creature production in this package.

## Feature delivery contract

Every ticket records ID, outcome, owner, source revision, allowed write paths, dependencies, non-goals, acceptance criteria, exact verification steps, evidence locations and unresolved risks. Begin with one document owner per artifact. Use states `proposed → ready → in_progress → in_review → verified`; `blocked` includes an owner and exact unblocking action.

The delivery sequence is request, product brief, technical plan, selected specialist advice, implementation, independent verification and curated evidence. A planning review may make a ticket ready; only actual acceptance evidence can make the feature verified. Reopen a ticket when the accepted artifact or relevant environment changes.
