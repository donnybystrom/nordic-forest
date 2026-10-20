# Reference assets and reusable generation recipes

Use scanned assets for convincing local detail, and use tree packs and game references to recover useful construction rules. Deliver an editable source asset, a measured runtime derivative and a reproducible generation recipe. Preserve the distinction between reusing an asset, borrowing a visual idea and identifying a technique.

## Current reference evidence

The user supplied three screenshots and an oak pack link. Screenshots are retained byte-for-byte under `assets/references/screenshots/`, with hashes in `data/references/screenshot-evidence.json`. The [catalog](../data/references/catalog.json) separates screenshots, author metadata and local file measurements. The [first measured report](REFERENCE-FIRST-AUDIT.md) records the downloaded oak FBX/GLB and stick GLB.

| Reference | Evidence available now | Appropriate first experiment |
| --- | --- | --- |
| Oak trees pack by LOLIPOP | Sketchfab metadata, source FBX, converted GLB and per-LOD file audit; reported CC BY 4.0 | Compare one sapling, medium and large tree across every included LOD; separate bark, branch cards and whole-tree impostors |
| Mushrooms on tree stump by pancakesbassoondonut | Screenshot and matching public metadata: 631,404 reported triangles, 317,338 vertices | Separate the useful stump/fungi silhouette from the scan's ground collar; compare clean decimation and retopology/bake alternatives |
| Wood Stick 02 by 3dhdscan | Screenshot, metadata and converted GLB: 29,988 triangles measured after import | Small first import/audit/LOD/bake round-trip with a manageable source |
| Old Tree Stump by Ninma | Screenshot reports approximately 500k triangles; exact source and license not resolved | Identify the actual source before selecting it as a production input |

The stump counts remain page/API claims. Oak and stick file measurements are now recorded separately; they do not establish runtime costs. No downloaded model has been optimized yet. The linked oak pack is a construction reference; its leaf shapes and crown architecture do not define the species mix for the northern Swedish setting.

## Oak pack findings from the author

The pack's [public metadata](https://api.sketchfab.com/v3/models/a5e4e64f9f1d4089bdcc6170a9333393) describes shared bark and branch texture families, five seasonal branch sets, and separate smaller billboard textures. Bark maps are described as 1024×2048. The actual files must establish dimensions, channel packing and completeness.

The author associates vertex red with AO, green with a base-to-tip gradient and blue with bark blending, and mentions custom normals for a fuller crown. These are material/authoring inputs to preserve and inspect, not evidence that the Godot importer already reproduces the intended shading. The green gradient's exact use in wind or another shader remains a question until the material is inspected.

The author lists approximate LOD0 classes from about 170 triangles for saplings to roughly 19–24k for large trees, with larger double forms. These are not the aggregate pack count or measured runtime cost. A size-aware recipe should reproduce distinct architectures rather than scaling one adult mesh down to make every age.

The author warns that unused seasonal and billboard-related textures were removed from the Sketchfab upload and supplies a separate texture folder. Acquire the complete source package and that supplement, then hash and inventory them together. Do not conclude that all seasons exist from the viewer download alone. The author calls for single-sided billboard materials; the exported geometry and intended facing behavior still need inspection.

## Scanned object conversion

1. **Register:** retain the source archive, file hashes, creator, source URL and exact license. Track source, working copy and engine derivative separately. The three matched public Sketchfab records report CC Attribution; retain attribution and a description of changes with derivatives. The [CC BY 4.0 deed](https://creativecommons.org/licenses/by/4.0/) explains attribution, license-link and modification notices. Do not infer another listing's terms from the marketplace name or from a download button.
2. **Inspect:** measure units, bounds, topology, material slots, texture dimensions, UVs, normals and texture/shader dependencies before choosing an optimization target. Check for a captured ground patch, loose leaves, holes, floating fragments and directional lighting baked into color.
3. **Clean on a copy:** remove irrelevant background/collar geometry and repair only what the intended views require. Preserve mushroom and moss silhouettes where they matter. Keep a hero source and independent masks or parts where practical; a scan with fused surfaces cannot always be separated cleanly.
4. **Choose reduction:** compare a Decimate working copy with a deliberately retopologized mesh. [Blender Decimate](https://docs.blender.org/manual/en/5.2/modeling/modifiers/generate/decimate.html) reduces geometry; it does not automatically reduce texture memory, material count, alpha overdraw or baked lighting. Its Planar delimiter options are not a general UV-preservation guarantee for Collapse mode.
5. **Bake:** transfer source detail to the selected runtime mesh using controlled source/target transforms, a checked cage/ray distance, compatible tangent normals and UV padding. Test missed projections around fungi, deep bark cavities and the underside. Preserve the high-resolution source; do not bake directional highlights into the new albedo intentionally.
6. **Validate:** compare source and derivative in neutral light and the target forest, at the largest intended screen size, around multiple viewing directions and across LOD transitions. Measure silhouette loss, material/shading changes, texture cost and frame time. A reduction ratio is a trial parameter, not an acceptance result.

Choose final triangle and texture budgets from projected size and measured density in the scene. A close-up stump and a stick glimpsed among hundreds of instances have different needs. Record geometry bytes, source texture bytes, decoded/mip estimates and measured runtime memory separately.

Variations can use controlled bending, scale within plausible limits, root/cut-end variants, material masks and independent fungus/moss modules. Avoid obvious repeated silhouettes and stretched bark. For newly generated assets, use a style brief describing observed properties; do not label a look-alike as the original scan or assume the original's material values are physically calibrated.

## Tree construction analysis

Measure selected size classes under fixed scale, neutral light and matched cameras. Keep these representations distinct:

- Woody geometry: trunk, major branches and secondary twigs.
- Foliage meshes/cards: textured surfaces distributed through the crown; they may be fixed, crossed, bent or shader-oriented.
- Whole-tree impostors: a distant representation of the entire tree. Single-view, crossed-plane and multiview/octahedral approaches are alternatives to test, not established properties of this pack.

Inventory each LOD's geometry, material slots, UV islands, textures, custom normals, vertex colors, alpha/culling modes, bounds and source sharing. Compare the same tree across levels: what disappears, which cards merge, whether the trunk changes, and whether normals/materials change. Similar names are mapping hints, not proof of a valid LOD chain.

For potential foliage cards, separate components by connectivity/material/UV structure, fit planes or local axes, and record center, dimensions, local orientation, atlas region and attachment to a branch. PCA can expose flat components but cannot determine the intended front side, camera-facing behavior or semantic branch. Joined/bent cards require another decomposition. Validate the classification visually before deriving distributions.

Normalize tree architecture by height, crown width and branch order. Fit distributions for trunk taper/lean, crown onset and shape, branch emergence/length, terminal clusters, gaps, card tilt/azimuth, cluster size and atlas choices. Keep species, age, damage and growth conditions as inputs. A final exported mesh does not uniquely identify the generator that produced it.

Fill [the tree recipe template](../data/references/tree-recipe.template.json) with measured values, evidence and uncertainties. It is deliberately uncalibrated and is not valid runtime input yet. The [biome transfer template](../data/biomes/reference-transfer.template.json) similarly separates a reference game's look/placement sample from Swedish ecology and engine quality settings.

### Proposed generator recipe

1. Generate an editable trunk/branch centerline graph from a seed and species/age profile. Use radius/taper curves and controlled asymmetry; mesh the woody graph with detail concentrated on the silhouette. Curves, growth simulation or a space-colonization approach are candidate implementations, not inferred source algorithms.
2. Texture bark along branch length with documented texel scale and seam placement; use distinct cut-end treatment and masks for roots, damaged wood and moss. Inspect whether the reference uses tiling UVs, atlas regions, vertex blends or combinations.
3. Place terminal clusters relative to branch order and distance along the parent. Use stable per-branch seeds so editing one limb does not reshuffle the whole tree.
4. Orient fixed cards in a branch-local orthonormal frame: branch tangent, outward crown direction and a stable fallback axis when those vectors are parallel. Apply an authored inclination/roll distribution, scale by the terminal cluster and select weighted atlas variants. Do not make every card face the camera by default.
5. Match crown silhouette and gap/opacity coverage first, then adjust card count and material complexity. Broad opaque texture margins and stacked transparent planes can cost more than their triangle count suggests. Preserve or deliberately reconstruct shading normals instead of indiscriminately clearing them.
6. Derive LODs by simplifying woody geometry, reducing/merging leaf clusters, changing material complexity and finally testing an impostor representation. Match color, alpha coverage through mipmaps, normals, wind phase and shadows across transitions.

[SpeedTree's generation properties](https://docs9.speedtree.com/modeler/doku.php?id=generation_properties) provide a useful reference for parent-relative placement/orientation; its [card generator](https://docs9.speedtree.com/modeler/doku.php?id=card_generator) separately documents camera-facing leaves and modified shading normals. This does not establish that the oak author used SpeedTree.

### Size-aware LOD

For an approximately upright tree near the view center, projected height is roughly `height_px = tree_height * viewport_height / (2 * view_depth * tan(vertical_fov / 2))`. Use consistent units and view-axis depth; compute projected bounds for oblique/complex cases. A large tree reaches the same screen-size threshold farther away than a sapling. Fixed distances copied between species and sizes are therefore a poor default.

Choose thresholds by screen-space error and measured frame cost at recorded FOV/resolution, with transition hysteresis. [Godot visibility ranges](https://docs.godotengine.org/en/stable/tutorials/3d/visibility_ranges.html) can implement manual replacement, including impostors; geometry reduction alone leaves material shading costs. Compare alpha scissor/hash, supported alpha-to-coverage and transitions in the active renderer rather than assuming the cheapest geometry is the cheapest result.

## Game and mod reference analysis

Keep visual observations, extracted asset data, code/shader interpretation, runtime evidence and reuse permission as separate records. Screenshots can suggest crown shape, contrast, apparent density, composition and atmospheric layering. They cannot uniquely reveal world-space density, hidden geometry, exact roughness, placement rules or whether photogrammetry was used.

The developer describes [The Gold River Project](https://fairviewgames.com/index.html) as set in the Pacific Northwest. Use it for composition, materials and rendering questions, while choosing Swedish species/site rules independently. Photogrammetry use remains the user's visual hypothesis until source or runtime evidence establishes it.

For a supplied game build: hash executable/archive inputs, identify engine/build/container format, inventory assets and material/LOD dependencies, then inspect one vegetation family. Correlate decoded resources and relevant functions/shaders with a bounded runtime capture. An embedded filename/string alone does not prove an active rendering or placement path. Record format/tool versions, unresolved fields and decoded versus opaque resources. No game binaries have been supplied or analyzed yet.

For a selected Skyrim mod: record the exact mod/archive version, game edition, relevant dependencies and effective file overwrite/load order. Separate source meshes/materials from generated LOD output and from plugins or placement records. [DynDOLOD's billboard documentation](https://dyndolod.info/Help/Tree-Grass-LOD-Billboards) describes dimension metadata and diffuse/normal variants; [its tree LOD guide](https://dyndolod.info/Help/Tree-LOD) distinguishes Skyrim's dedicated tree LOD system from ordinary mesh LOD. Those techniques are references, not an engine-independent import format.

Build our biome rules from evidence with provenance: species/family weights, clusters, spacing, age mix, terrain/site suitability, understory layers, exclusions, deadwood associations and variation seeds. World coordinates from a mod can support a measured placement sample; a texture pack alone cannot establish a biome distribution. Keep a reference-style preset separate from the ecological Swedish preset and from the engine quality profile.

## First analysis package

**R0-001 — one tree family and one scanned object.** Inputs: the oak source package plus supplemental textures, and Wood Stick 02 or the mushroom stump. Technical Artist owns conversion/recipe; Reference and Asset Analysis owns inventory/evidence; Rendering owns the engine comparison; Ecology reviews the Swedish translation; QA reviews the independent comparisons.

Deliver a source/dependency register, per-LOD audit, annotated neutral-light views, a parameterized draft tree recipe, one scan derivative and a Godot comparison scene with measured costs. Acceptance requires actual source-file hashes, a matched source/derivative comparison, unchanged originals and one seed-driven variation that preserves the intended visual properties. This package supplies M0/M1's small kit; it does not require importing an entire game world.

## Audit command

Run the supplied inspector in an isolated Blender process:

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python tools/blender_asset_audit.py -- --input /absolute/path/tree.glb --output runs/oak-audit.json
```

It supports `.blend`, `.glb`, `.gltf`, `.obj` and `.fbx`, never saves the source, refuses an existing output and checks that the input hash is unchanged. `--object-regex` narrows the selected mesh objects. Component analysis has explicit vertex/sample budgets and labels incomplete results. Material node-group internals and generated instances are not expanded; use an explicit realized export for that case.

The inspector has passed a Blender 5.2 synthetic-fixture check for triangle counts, shared meshes, UV/color/normal metadata, component geometry, material alpha hints, source identity and overwrite rejection. It has also measured the downloaded oak source FBX/converted GLB and stick GLB. Shader behavior, overdraw, neutral-light appearance and GPU performance remain unverified.
