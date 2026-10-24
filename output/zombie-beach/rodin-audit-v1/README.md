# Rodin working candidate v1

2026-10-22. Rodin is now the working mesh for the beach-zombie experiment. Original Rodin and Meshy exports remain unchanged. This candidate proves animation transfer and asset export; it is not an accepted production character.

## Deliverables

- [Rodin_Working_v1.glb](../../../assets/models/zombies/rodin-working-v1/Rodin_Working_v1.glb): one mesh, one 52-bone skin, 30,000 triangles, original PBR maps, eight skin influences where needed, 13 animation clips.
- [Rodin_Working_v1.blend](../../../assets/models/zombies/rodin-working-v1/Rodin_Working_v1.blend): isolated editable asset scene. Choose an Action or unmute one NLA track to preview a clip; tracks are initially muted to avoid layering all clips.
- [Rodin_Review_v1.blend](Rodin_Review_v1.blend): comparison sources, candidate, studio and working rig. Opens with the transferred Meshy Unsteady Walk action selected on the working rig.
- [Transferred Meshy walk render](rodin-meshy-unsteady-walk.png), a single pose at frame 34/30 fps.
- [Raised-arm comparison](arms90-comparison.png): original left, candidate right; persistent armpit webbing is clearly visible. Outer hands extend beyond this comparison's framing.

## What was found and changed

The walking and crawling Rodin exports share geometry, skin weights and rest skeleton. The 52-bone rig uses Mixamo-like names without the `mixamorig:` namespace. It has no dedicated soft-tissue, hair or twist helper bones and no morph targets. The original geometry has 27,138 exported vertices; a measurement-only 1 µm weld leaves 14,980 vertices and no boundary/non-manifold edges. This is a connectivity check, not an anatomical quality certificate.

The localized weight candidate changes 3,695 source vertices around the shoulders/underarms without changing geometry or UVs. Across all 205 native walking/crawling poses, the largest edge-length increase drops from 9.83 to 5.10 cm for walking, and from 28.29 to 9.09 cm for crawling. The maxima can occur at different frames/edges. These metrics do not prove good anatomy: raised arms still reveal generated skin webs, requiring local geometry/retopology and pose corrections. No limb has been cut away in this candidate.

PBR inputs already include a 4096² albedo and 2048² normal/packed metallic-roughness maps. The shaded alternative stores a baked emissive appearance. The working asset uses the PBR version and only lowers normal-map strength from 1.0 to 0.65. No texture repainting, recovered detail or AI upscaling was performed. Improving facial/skin detail will need better texture content and potentially revised UV allocation, rather than just larger image dimensions.

## Animation transfer

All 52 Rodin bones map to corresponding names in the 66-bone Meshy Mixamo source. Eleven clips were baked at 30 fps onto Rodin's own rest skeleton, retaining Rodin bone lengths. Model-space rotation deltas are corrected through the two rest poses. Hips displacement is scaled by the rest hip-height ratio (1.195956). The two native Rodin clips are retained: `Rodin_HumanWalking2` and `Rodin_HumanZombieCrawl`.

Meshy names include `Meshy_Unsteady_Walk`, `Meshy_Walking`, `Meshy_Running` and eight original UUID names. UUID clips have not been assigned guessed gameplay meanings. Mathematical checks at five frames per transferred clip agree with the requested target transforms, but do not establish correct foot planting, balance or self-collision. No foot IK cleanup was applied.

## Verification and limits

[Roundtrip validation](roundtrip-validation.json) passes: one scene, one mesh, one skin, 52 joints, all 13 names and durations preserved. Five phases per clip (65 pose samples) compare the exported/reimported skin to the Blender master; maximum vertex difference is 0.1385 mm. Imported vertices rise to 27,183 due to export/import splits; rest-position mapping remains within 0.001 mm.

The GLB preserves second joint/weight sets rather than pruning to four influences. Material export emits a shared-texture sampler warning; the three PBR texture inputs and normal strength were inspected in the GLB. Runtime appearance and import behavior in Godot remain unverified.

Jiggle, corrective morphs, ragdoll, anatomy masks, Voronoi damage and procedural locomotion have not been added. Next mesh work is local armpit/shoulder reconstruction and deformation review, followed by regional helper bones/weights for limited secondary motion. Those helper bones must be excluded from locomotion retarget mapping and receive their dynamics after the base animation. Godot's [SpringBoneSimulator3D](https://docs.godotengine.org/en/stable/classes/class_springbonesimulator3d.html) is a possible later secondary-motion component; it does not repair topology or provide a balance controller.

## Evidence and reproduction

- [Source inventory and hashes](source-inventory.json)
- [Candidate vertex IDs and parameters](candidate-changes.json), [native clip comparisons](candidate-comparison.json)
- [Retarget method, mapping and checks](retarget-report.json)
- [Deliverable hashes and manifest](deliverable-manifest.json)
- [Export roundtrip checks](roundtrip-validation.json)
- [Blender scripts](../../../tools/zombie_beach/rodin/)

Scripts act on named objects in the live Blender review session and create versioned objects/scenes. They are staged experiment steps, not an idempotent unattended Langflow pipeline. Preparation/import order and the Meshy source rig are prerequisites; do not rerun creation steps blindly in an already populated session. `source_inventory.py` runs with ordinary Python and reads originals only.
