"""Import a generated character into isolated Blender and render review views.

Run in Blender with --background --factory-startup --disable-autoexec.
The source model is read only; the .blend, measurements and renders are new files.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def review(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    if (destination / 'character-review.blend').exists():
        raise ValueError('Use a fresh review destination')
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(source))
    scene = bpy.context.scene
    meshes = [obj for obj in scene.objects if obj.type == 'MESH']
    if not meshes:
        raise ValueError('No imported mesh')
    points = [obj.matrix_world @ Vector(point) for obj in meshes for point in obj.bound_box]
    low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    center, size = (low + high) / 2, high - low
    images = [{'name': image.name, 'width': image.size[0], 'height': image.size[1],
               'channels': image.channels} for image in bpy.data.images if image.size[0] and image.source != 'VIEWER']
    skeletons = [{'name': obj.name, 'bone_count': len(obj.data.bones)}
                 for obj in scene.objects if obj.type == 'ARMATURE']
    inventory = {'source': str(source), 'source_sha256': source_hash,
                 'blender_version': bpy.app.version_string,
                 'meshes': [{'name': obj.name, 'vertices': len(obj.data.vertices),
                             'faces': len(obj.data.polygons),
                             'triangles': sum(len(p.vertices) - 2 for p in obj.data.polygons),
                             'uv_layers': len(obj.data.uv_layers)} for obj in meshes],
                 'bounds_world_units': list(size), 'skeletons': skeletons,
                 'actions': [{'name': action.name, 'frames': list(action.frame_range)} for action in bpy.data.actions],
                 'textures': images, 'scale_note': 'Source bounds measured; real character height is not assigned.',
                 'rig_acceptance': 'not_performed', 'active_ragdoll': 'not_implemented'}
    (destination / 'inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = 'AgX'
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (.12, .14, .16, 1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .5
    height = max(size.z, .1)
    for name, offset, energy, width in [
        ('Key', (-2, -3, 2.5), 450, 3), ('Fill', (2, -1, 1), 250, 2.5), ('Rim', (0, 2, 2), 350, 2),
    ]:
        lamp = bpy.data.lights.new('Review ' + name, 'AREA')
        lamp.energy = energy * height * height
        lamp.shape = 'DISK'
        lamp.size = width * height
        obj = bpy.data.objects.new(lamp.name, lamp)
        scene.collection.objects.link(obj)
        obj.location = center + Vector(offset) * height
        obj.rotation_euler = (center - obj.location).to_track_quat('-Z', 'Y').to_euler()
    data = bpy.data.cameras.new('Review Camera')
    camera = bpy.data.objects.new(data.name, data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    data.type = 'ORTHO'
    data.ortho_scale = max(size.z, size.x) * 1.2
    for name, offset in [('front', (0, -3, 0)), ('back', (0, 3, 0)), ('three-quarter', (2, -3, .25))]:
        camera.location = center + Vector(offset) * height
        camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = str(destination / (name + '.png'))
        bpy.ops.render.render(write_still=True)
    for image in bpy.data.images:
        if image.source == 'FILE' and not image.packed_file:
            image.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(destination / 'character-review.blend'))
    if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
        raise ValueError('Source changed during review')
    print('CHARACTER_REVIEW_COMPLETE', json.dumps(inventory))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    review(args.input.resolve(), args.output.resolve())
