"""Inspect a supplied asset in a separate Blender --background --factory-startup process.

Run with --disable-autoexec. This script never saves or exports the source scene.
Card candidates are geometric hints, not a recovered tree generator or shader.
"""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import bpy
import numpy as np


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rgba8_mips(width, height):
    total = 0
    while width and height:
        total += width * height * 4
        if width == height == 1:
            break
        width, height = max(1, width // 2), max(1, height // 2)
    return total


def alpha_hint(material):
    if not material or not material.use_nodes:
        return False
    for node in material.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            socket = node.inputs.get("Alpha")
            if socket and (socket.is_linked or socket.default_value < 1.0):
                return True
    return False


def component_report(mesh, positions, limit_vertices, limit_components):
    if len(positions) > limit_vertices:
        return {"status": "skipped_vertex_budget", "vertex_limit": limit_vertices}
    parent = list(range(len(positions)))

    def root(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for edge in mesh.edges:
        a, b = (root(v) for v in edge.vertices)
        if a != b:
            parent[b] = a
    groups = {}
    for i in range(len(positions)):
        groups.setdefault(root(i), []).append(i)
    material_sets = {}
    for polygon in mesh.polygons:
        if polygon.vertices:
            material_sets.setdefault(root(polygon.vertices[0]), set()).add(polygon.material_index)
    samples = []
    ordered = sorted(groups.items(), key=lambda item: item[1][0])
    for key, indices in ordered[:limit_components]:
        p = positions[indices]
        center = p.mean(axis=0)
        entry = {"first_vertex": indices[0], "vertices": len(indices),
                 "vertex_centroid_world": center.tolist(),
                 "material_slots": sorted(material_sets.get(key, set()))}
        if len(indices) >= 3:
            covariance = (p - center).T @ (p - center) / len(p)
            values, vectors = np.linalg.eigh(covariance)
            local = (p - center) @ vectors
            extents = np.ptp(local, axis=0)
            denominator = max(float(extents[-1]), 1e-12)
            residual = float(np.sqrt(max(0.0, values[0])) / denominator)
            normal = vectors[:, 0]
            if normal[np.argmax(np.abs(normal))] < 0:
                normal = -normal
            entry.update({"pca_plane_normal_world": normal.tolist(),
                          "pca_plane_normal_sign": "largest absolute axis is positive; front/back not inferred",
                          "pca_extents_world_units": extents.tolist(),
                          "plane_residual_over_longest_span": residual,
                          "nearly_planar_hint": residual < 0.005,
                          "planarity_threshold": 0.005})
        samples.append(entry)
    return {"status": "sampled" if len(ordered) > limit_components else "complete",
            "component_count": len(ordered), "sample_count": len(samples),
            "sampling": "first components by vertex index; not a representative crown sample",
            "interpretation": "Planarity does not establish foliage, camera-facing behavior, or intended orientation.",
            "samples": samples}


def image_report(image):
    width, height = (int(v) for v in image.size)
    record = {"name": image.name, "width": width, "height": height,
              "channels": image.channels, "colorspace": image.colorspace_settings.name,
              "source": image.source,
              "rgba8_full_mip_estimate_bytes": rgba8_mips(width, height),
              "packed_bytes": image.packed_file.size if image.packed_file else 0}
    if image.filepath:
        path = Path(bpy.path.abspath(image.filepath)).resolve()
        record["path"] = str(path)
        record["exists"] = path.is_file()
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".tga", ".exr", ".hdr", ".dds", ".ktx2", ".tif", ".tiff", ".bmp"}:
            record["file_bytes"] = path.stat().st_size
            record["file_sha256"] = sha256(path)
    return record


def audit(args):
    source = Path(args.input).resolve()
    output = Path(args.output).resolve()
    if output.exists() or source == output:
        raise ValueError("Output must be a new report file")
    source_hash = sha256(source)
    if source.suffix.lower() == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    else:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        if source.suffix.lower() in {".glb", ".gltf"}:
            bpy.ops.import_scene.gltf(filepath=str(source))
        elif source.suffix.lower() == ".obj":
            bpy.ops.wm.obj_import(filepath=str(source))
        elif source.suffix.lower() == ".fbx":
            bpy.ops.import_scene.fbx(filepath=str(source))
        else:
            raise ValueError("Supported inputs: .blend, .glb, .gltf, .obj, .fbx")
    graph = bpy.context.evaluated_depsgraph_get()
    objects, materials, images, shared = [], {}, {}, {}
    for obj in sorted(bpy.context.scene.objects, key=lambda item: item.name):
        if obj.type != "MESH" or (args.object_regex and not re.search(args.object_regex, obj.name)):
            continue
        shared.setdefault(obj.data.name, []).append(obj.name)
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=graph)
        try:
            co = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
            mesh.vertices.foreach_get("co", co)
            local = co.reshape((-1, 3))
            matrix = np.asarray(evaluated.matrix_world, dtype=np.float64)
            world = local @ matrix[:3, :3].T + matrix[:3, 3]
            triangle_count = sum(max(0, len(poly.vertices) - 2) for poly in mesh.polygons)
            lod = re.search(r"(?:^|[_. -])LOD[_. -]?(\d+)(?:$|[_. -])", obj.name, re.IGNORECASE)
            record = {"object": obj.name, "source_mesh_datablock": obj.data.name,
                      "evaluated_vertices": len(mesh.vertices), "evaluated_triangles": triangle_count,
                      "source_vertices": len(obj.data.vertices),
                      "modifier_types": [modifier.type for modifier in obj.modifiers],
                      "lod_name_hint": int(lod[1]) if lod else None,
                      "uv_layers": [uv.name for uv in mesh.uv_layers],
                      "has_custom_normals": mesh.has_custom_normals,
                      "material_face_counts": dict(Counter(poly.material_index for poly in mesh.polygons)),
                      "color_attributes": [{"name": attr.name, "domain": attr.domain, "type": attr.data_type}
                                           for attr in mesh.color_attributes]}
            if len(world):
                record["bounds_world"] = {"min": world.min(axis=0).tolist(), "max": world.max(axis=0).tolist(),
                                          "dimensions": np.ptp(world, axis=0).tolist()}
            record["components"] = component_report(mesh, world, args.max_component_vertices, args.max_components)
            for mat in mesh.materials:
                if mat is None:
                    continue
                materials[mat.name] = {"name": mat.name, "alpha_input_hint": alpha_hint(mat),
                                       "backface_culling": mat.use_backface_culling,
                                       "surface_render_method": getattr(mat, "surface_render_method", None)}
                if mat.use_nodes:
                    for node in mat.node_tree.nodes:
                        if node.type == "TEX_IMAGE" and node.image:
                            images[node.image.name] = image_report(node.image)
            objects.append(record)
        finally:
            evaluated.to_mesh_clear()
    if sha256(source) != source_hash:
        raise ValueError("Source hash changed during inspection")
    result = {"schema_version": "0.1", "captured_at": datetime.now(timezone.utc).isoformat(),
              "source": {"path": str(source), "sha256": source_hash, "bytes": source.stat().st_size},
              "blender_version": bpy.app.version_string,
              "scope": "current scene, evaluated mesh objects, selected object names if provided",
              "unit_note": "Bounds use Blender world units; verify original real-world scale independently.",
              "scene_units": {"system": bpy.context.scene.unit_settings.system,
                              "scale_length": bpy.context.scene.unit_settings.scale_length},
              "objects": objects, "shared_source_meshes": shared,
              "materials": list(materials.values()), "referenced_images": list(images.values()),
              "texture_estimate_note": "RGBA8 full mip estimates only; not GPU residency or compressed texture memory.",
              "limitations": ["No visual, overdraw, shader, engine or FPS verification",
                              "Objects and LOD variants are inventoried together, not simultaneously rendered cost",
                              "Nested material node-group textures are not traversed",
                              "Generated collection/Geometry Nodes instances are not expanded",
                              "Component PCA cannot recover the original generator, card front, or runtime billboarding"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print("ASSET_AUDIT_SAVED", output, "mesh_objects", len(objects))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--object-regex")
    parser.add_argument("--max-component-vertices", type=int, default=100000)
    parser.add_argument("--max-components", type=int, default=256)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if args.max_components < 1 or args.max_component_vertices < 1:
        parser.error("Budgets must be positive")
    audit(args)
