# First downloaded reference audit

Checked 18 October 2026. These are file measurements from isolated Blender 5.2 imports; no production optimization or engine benchmark is claimed.

Sketchfab API access succeeded. The oak author-source archive (179,854,240 bytes) and converted GLB (63,405,656 bytes) were downloaded deterministically. A separate live SDK agent called the restricted download tool and fetched Wood Stick 02 GLB (4,913,220 bytes). Its returned usage was 1,084 input / 128 output tokens. Download manifests preserve hashes and metadata; credentials and signed download URLs are not included.

## Oak LOD structure

The FBX contains 75 mesh objects, including display/reference objects and repeated seasonal demonstration geometry. The converted GLB contains 131 material-split mesh objects and 409,422 total triangles. Object counts are not comparable without accounting for material splitting. Neither total is the cost of a single tree.

The 17 canonical named tree families contain the following evaluated triangle counts in the source FBX:

| Family | LOD0 | LOD1 | LOD2 | Billboard |
| --- | ---: | ---: | ---: | ---: |
| Big_oak_tree__001 | 11016 | 4859 | 3193 | 28 |
| Big_oak_tree__002 | 9150 | 4716 | 3108 | 28 |
| Big_oak_tree__003 | 11352 | 5147 | 3356 | 28 |
| Big_oak_tree__004 | 18440 | 9041 | 5917 | 28 |
| Large_oak_tree_001 | 24309 | 9853 | 6385 | 28 |
| Large_oak_tree_002 | 21945 | 9716 | 6352 | 28 |
| Large_oak_tree_003 | 37684 | 15139 | 9886 | 28 |
| Large_oak_tree_004 | 18790 | 7790 | 4965 | 28 |
| Medium_oak_tree__001 | 5122 | 1854 | 1071 | 28 |
| Medium_oak_tree__002 | 6786 | 2378 | 1394 | 28 |
| Medium_oak_tree__003 | 6513 | 2612 | 1494 | 28 |
| Sapling_oak_tree_001 | 170 | 116 | 40 | 28 |
| Sapling_oak_tree_002 | 189 | 135 | 40 | 28 |
| Sapling_oak_tree_003 | 159 | 109 | 37 | 28 |
| Small_oak_tree__001 | 1217 | 763 | 163 | 28 |
| Small_oak_tree__002 | 1333 | 826 | 205 | 28 |
| Small_oak_tree__003 | 1275 | 797 | 248 | 28 |

Every canonical Billboard object has 28 triangles. For the first big oak, connectivity finds seven disconnected planar components, each with six vertices and four triangles. This is more informative than assuming that every distant representation is a single two-triangle quad. The audit does not establish whether any component is rotated by a shader or how view selection works.

Sapling LOD2 has only 37–40 triangles, so switching to the 28-triangle billboard saves very little geometry in that class. Material cost, silhouette, screen size, alpha coverage and shadows must decide whether the transition is worthwhile. This is an inference to test, not a measured GPU result.

The source import retains named color attributes and reports custom normals. Their existence does not establish correct Godot use or verify the author-described channel semantics. Larger meshes have explicitly sampled connectivity analyses; do not fit a crown-wide placement distribution to the first 256 components.

## Textures and representation differences

The author archive contains 66 PNG files, including named spring, summer, early/late autumn and winter cluster families. Header dimensions and file hashes are in the summary. The FBX importer references 12 image paths that do not resolve in the extracted layout. Filenames/layout differ from those exported in the FBX; this is a relinking/material reconstruction task, not proof that the archive lacks every texture. The author’s supplemental folder has not been incorporated.

The converted GLB imports embedded images and usable material assignments, but it is a conversion, not a lossless substitute for source authoring/shaders. Do not infer source channel packing, alpha culling or final material intent solely from the imported defaults.

## Scan and next bounded work

Wood Stick 02 imports as one mesh with 29,988 triangles and three image datablocks, matching the public triangle count. Its source here is Sketchfab’s converted GLB; the original author archive was not downloaded. No decimation or bake has been performed.

The next R0-001 step is to relink one oak family on a working copy, validate its cards/material channels with neutral views, and create one measured stick derivative before building the Godot comparison. A generation recipe remains uncalibrated until those visual and semantic checks pass. Gold River binaries and the two user-selected Skyrim archives have not yet been analyzed.

Evidence: [oak summary](../data/references/analysis/oak-pack-summary.json), [stick summary](../data/references/analysis/wood-stick-02-summary.json), [catalog](../data/references/catalog.json). Raw per-object reports and the live SDK packet are retained under local ignored `runs/`; the summary records report hashes. Downloaded binaries live under ignored `data/references/downloads/`.
