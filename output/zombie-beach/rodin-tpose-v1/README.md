# Rodin T-pose: first rig and Godot review

2026-10-22. The user-selected T-pose generation is now the geometry source. Original inputs and previous working versions remain intact. This is a fitted, automatically weighted rig candidate, not final anatomical or gameplay acceptance.

The same Godot project now also includes the male beach tourist, with all 13 motions transferred to his 22-bone body rig. Model switching preserves clip, normalized time, speed and pause state. See [the expanded character reviewer](../../../docs/CHARACTER-REVIEW.md) for the catalog, controls and current two-character checks. The source/rig evidence below describes the original female deliverable.

On 2026-10-23, an active-ragdoll sandbox was added to this runtime. The launcher starts active physics, with an orange draggable ball, a test-push button, muscle strength, explicit virtual pelvis support and a passive-ragdoll mode. Both models use real articulated bodies and floor/body/ball contacts. [Physics controls and verification](../../../docs/CHARACTER-REVIEW.md#fysiklabb-med-dragbar-boll) describe the prototype; autonomous balance and foot placement remain future work.

## Open the result

- [Launch character and animation review in Godot](../../../tools/open_character_review.command) — double-click the executable `.command`, or run it from Terminal. The previous launcher still opens this scene. Requires Python 3 and the installed Godot CLI or `/Applications/Godot.app`.
- [Godot project](godot-review/project.godot): model and clip menus with previous/next buttons, rest pose, pause/resume, speed and time sliders, drag to orbit and wheel to zoom. Q/E switches models; arrows switch clips; space pauses. Clips loop only in the review. The camera follows the hips horizontally; no root motion is removed from the asset.
- [Rigged GLB](../../../assets/models/zombies/rodin-tpose-working-v1/Rodin_TPose_Working_v1.glb)
- [Editable isolated Blender asset](../../../assets/models/zombies/rodin-tpose-working-v1/Rodin_TPose_Working_v1.blend): choose an Action or unmute one NLA track. All tracks initially muted to preserve the bind pose.
- [Blender comparison/studio scene](Rodin_TPose_Review_v1.blend): leaves Meshy Unsteady Walk active on the working rig.
- [T-pose render](rodint-rest.png), [transferred walk](rodint-meshy-walk.png), [transferred crawl](rodint-rodin-crawl.png), [actual Godot render](godot-preview.png).

## Source and rig

Input: `assets/models/zombies/zombiegirl-rodin2-tshape-source/993bae00-0c2b-4136-888a-dec58539083d/lod_basic_pbr.fbx`.

The FBX provides five **unrigged** LODs: 30,000 / 15,000 / 7,500 / 3,750 / 1,874 triangles. LOD0 has 14,986 mesh vertices before UV/normal export splits, is 1.78386 m tall and has no boundary/non-manifold edges or loose vertices. This only verifies connectivity. Arms are visibly clear of the torso in the source pose; extreme pose quality still requires review. Only LOD0 is rigged and exported in this version.

The 52-bone, Mixamo-named rig uses the previous Rodin skeleton hierarchy with newly fitted bone positions. Trunk, shoulder and leg landmarks are specified explicitly in [build_rig.py](../../../tools/zombie_beach/rodin_tpose/build_rig.py); five finger endpoints per hand were identified from surface geodesic distance extrema, with initial finger joints fitted toward those endpoints. This is a prototype fitting method, not a claim of exact joint recovery. Fresh Blender bone-heat weights cover every vertex and are normalized and limited to eight influences. No weight mass was pruned in this build. No old surface weights were transferred from the previous mesh.

The working mesh is translated horizontally by +0.082101 m to center its source bounds. Surface geometry, topology and UVs are otherwise retained. Its original 2K albedo, normal, roughness and metallic maps are packed into the Blender deliverable and exported to GLB, with normal strength 0.65. Texture detail has not been regenerated or upscaled.

## Motion transfer

All 13 clips from the previous Rodin working asset are rebaked at 30 fps: 11 original Meshy clips plus `Rodin_HumanWalking2` and `Rodin_HumanZombieCrawl`. UUID clips retain their identifiers rather than guessed gameplay labels.

The transfer reference uses the old rig **posed with horizontal arms** against the new fitted T-pose rest skeleton. Using the old lowered-arm bind as reference would leave the new arms incorrectly raised during walking. Model-space rotation changes are converted back to the target bone spaces. Target bone lengths are retained; hips motion is scaled by the new/old hip-height ratio, 0.927185. Finger reference poses differ, so fine finger poses/grip are not accepted yet. These clips are transferred references for future control, not procedural locomotion.

## Checks performed

| Check | Observed result | What it establishes |
| --- | --- | --- |
| Blender deformation sweep | 1,607 frames across 13 clips; largest edge growth 6.12 cm, in the crotch region; native crawl 4.57 cm | Locates residual strain; does not certify anatomy or self-collision |
| Retarget transform checks | 65 samples; rotation error below 0.00002°, hips error below 0.0004 mm | Agreement with the chosen transfer transforms |
| GLB Blender roundtrip | 52 joints, 13 names/durations, eight influence sets retained; 65 poses, max vertex difference 0.0233 mm | Export/import skinning equivalence |
| Godot 4.7.1 import/runtime smoke | 52 bones and skin binds, 689 resolved track paths, 65 finite moving pose samples, durations within 0.00000045 s; eight influences preserved | Engine can import and evaluate all clips |
| Godot review controls | All 13 selections, pause/resume, time scrubbing and T-pose reset pass signal-path checks | These controls act on the loaded character |
| Godot rendering | Actual 1100×850 viewport capture on Apple M1 Pro, OpenGL Compatibility | One rendered pose; no performance benchmark or physics acceptance |

The imported Blender GLB contains 25,367 vertices after UV/normal splits; this is not additional anatomical detail. Godot's importer extracts three embedded texture files into the review project. These and its `.import` settings are local derivatives; `.godot/` is disposable cache.

Foot contact/height, hands, knee/elbow volume and self-intersections need further motion review. The observed raised feet in some transferred poses are not fixed by retarget math checks. Mouse orbit/zoom gestures were implemented but not automated in the UI smoke. The initial asset review did not include physics. The later runtime sandbox adds active and passive ragdoll, while planted-foot IK, corrective morphs, secondary/jiggle physics, damage masks, Voronoi fractures and an autonomous balance controller remain future work.

## Remaining asset and control work

Use this mesh and keep the 13 clips as movement targets. Correct contact/height and any local weight problems in a few accepted walk/crawl poses. Refine the sandbox's approximate collision shapes and broad joint limits, then replace virtual pelvis support with foot support and recovery stepping before gameplay control. Texture refinement can proceed after geometry and UVs stabilize.

## Evidence and reproduction

- [Source hashes](source-inventory.json), [source topology](source-geometry.json), [FBX import](import-inspection.json)
- [Rig landmarks and reference rotations](rig-report.json), [weights](bind-weights.npz)
- [Retarget method and samples](retarget-report.json), [deformation sweep](deformation-report.json)
- [Deliverable manifest and hashes](deliverable-manifest.json), [Blender roundtrip](roundtrip-validation.json)
- [Godot runtime report](godot-validation.json), [control report](godot-ui-validation.json)
- [Blender scripts](../../../tools/zombie_beach/rodin_tpose/): staged order `prepare.py`, `build_rig.py`, `retarget.py`, `review.py`, `export.py`, `validate.py`. Initial live import/studio setup was performed interactively through the Blender bridge; `prepare.py` records that setup for a fresh review scene and has not itself been replayed end-to-end. The previous Rodin working `.blend` supplies the motion rig if it is not already loaded. Creation steps assert against existing scenes/objects rather than silently overwrite.

Godot smoke can be repeated after import:

```sh
python3 tools/build_character_review.py
godot --headless --path output/zombie-beach/rodin-tpose-v1/godot-review --editor --import --log-file /tmp/character-import.log
godot --headless --path output/zombie-beach/rodin-tpose-v1/godot-review --script res://smoke.gd --log-file /tmp/character-assets.log
godot --headless --path output/zombie-beach/rodin-tpose-v1/godot-review --script res://ui_smoke.gd --log-file /tmp/character-ui.log
```

Inspect the generated JSON reports and errors as well as process status: a GDScript assertion alone may leave the process alive until `--quit-after`. The character GLB copy in the review project must match the deliverable hash before testing a new asset revision.

Current two-character reports are `godot-character-validation.json` and `godot-character-ui-validation.json`; the older reports above retain the initial female-only evidence.
