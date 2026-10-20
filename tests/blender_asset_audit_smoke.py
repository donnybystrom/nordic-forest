"""Run inside isolated Blender; tests a synthetic fixture, not a downloaded asset."""
import argparse
import hashlib
import json
import runpy
from datetime import datetime, timezone
from pathlib import Path

import bpy

root = Path(__file__).resolve().parents[1]
output = root / "runs" / ("asset-audit-smoke-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
output.mkdir(parents=True, exist_ok=False)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.5))
bpy.context.object.name = "Trunk_LOD0"
mesh = bpy.data.meshes.new("TwoDisconnectedCards")
mesh.from_pydata([(-1, 0, 1), (1, 0, 1), (1, 0, 3), (-1, 0, 3),
                  (0, -1, 1), (0, 1, 1), (0, 1, 3), (0, -1, 3)], [],
                 [(0, 1, 2, 3), (4, 5, 6, 7)])
mesh.uv_layers.new(name="BranchAtlas")
mesh.color_attributes.new(name="TreeMask", type="BYTE_COLOR", domain="POINT")
material = bpy.data.materials.new("FoliageAlphaHint")
material.use_nodes = True
material.node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value = 0.5
mesh.materials.append(material)
mesh.normals_split_custom_set_from_vertices([(0, 0, 1)] * 8)
for name, x in [("Foliage_LOD0", 0), ("Foliage_LOD0_Instance", 4)]:
    obj = bpy.data.objects.new(name, mesh)
    obj.location.x = x
    bpy.context.collection.objects.link(obj)
source = output / "synthetic-tree.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(source))
source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
module = runpy.run_path(str(root / "tools/blender_asset_audit.py"), run_name="audit_module")
report = output / "audit.json"
module["audit"](argparse.Namespace(input=str(source), output=str(report), object_regex=None,
                                  max_component_vertices=100000, max_components=256))
d = json.loads(report.read_text())
assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
assert len(d["objects"]) == 3
trunk = next(o for o in d["objects"] if o["object"] == "Trunk_LOD0")
assert trunk["evaluated_triangles"] == 12
foliage = next(o for o in d["objects"] if o["object"] == "Foliage_LOD0")
assert foliage["evaluated_triangles"] == 4
assert foliage["lod_name_hint"] == 0
assert foliage["has_custom_normals"]
assert foliage["components"]["component_count"] == 2
assert all(c["nearly_planar_hint"] for c in foliage["components"]["samples"])
assert len(d["shared_source_meshes"]["TwoDisconnectedCards"]) == 2
assert d["materials"][0]["alpha_input_hint"]
assert module["rgba8_mips"](4, 4) == 84
assert module["rgba8_mips"](0, 0) == 0
try:
    module["audit"](argparse.Namespace(input=str(source), output=str(report), object_regex=None,
                                      max_component_vertices=100000, max_components=256))
    raise AssertionError("Existing output was overwritten")
except ValueError:
    pass
glb = output / "synthetic-tree.glb"
bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB")
glb_report = output / "glb-audit.json"
module["audit"](argparse.Namespace(input=str(glb), output=str(glb_report), object_regex=None,
                                  max_component_vertices=100000, max_components=256))
g = json.loads(glb_report.read_text())
assert sum(o["evaluated_triangles"] for o in g["objects"]) == 20
assert len(g["objects"]) == 3
assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
print("ASSET_AUDIT_SMOKE_PASS: source identity, BLEND/GLB geometry, cards, sharing, materials, budget and overwrite boundary")
