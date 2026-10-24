"""Fit an explicit humanoid profile, bind on a welded proxy and verify GLB skinning.

The delivered mesh keeps its original vertices, UV loops and materials. Only the
weighting proxy is welded. QA_RigRange is a diagnostic clip, not gameplay motion.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector
from mathutils.kdtree import KDTree


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evaluated(scene, mesh, frame):
    bpy.context.window.scene = scene
    scene.frame_set(frame)
    obj = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data = obj.to_mesh()
    result = np.array([list(obj.matrix_world @ v.co) for v in data.vertices])
    obj.to_mesh_clear()
    return result


def set_world_rotation(rig, name, axis, degrees):
    rest = rig.data.bones[name].matrix_local.to_quaternion()
    rig.pose.bones[name].rotation_quaternion = rest.inverted() @ Quaternion(axis, math.radians(degrees)) @ rest


def studio(scene, height, directory, mesh, rig):
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 20
    scene.cycles.use_denoising = True
    scene.render.resolution_x = scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = 'AgX'
    scene.world = bpy.data.worlds.new('Rig Review World')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (.12, .14, .16, 1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .5
    center = Vector((0, 0, height / 2))
    for name, offset, energy, width in [('Key', (-2,-3,2.5),450,3),('Fill',(2,-1,1),250,2.5),('Rim',(0,2,2),350,2)]:
        light = bpy.data.lights.new(name, 'AREA')
        light.energy, light.shape, light.size = energy * height**2, 'DISK', width * height
        obj = bpy.data.objects.new(name, light)
        scene.collection.objects.link(obj)
        obj.location = center + Vector(offset) * height
        obj.rotation_euler = (center - obj.location).to_track_quat('-Z', 'Y').to_euler()
    data = bpy.data.cameras.new('Review Camera')
    camera = bpy.data.objects.new(data.name, data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    data.type, data.ortho_scale = 'ORTHO', height * 1.25
    for name, frame, offset in [('rest',1,(0,-3,0)),('joint-test',91,(1.8,-3,.2)),('crouch-test',121,(1.8,-3,.2))]:
        scene.frame_set(frame)
        camera.location = center + Vector(offset) * height
        camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = str(directory / (name + '.png'))
        bpy.ops.render.render(write_still=True)
    scene.frame_set(1)


def run(packet):
    source = Path(packet['source'])
    destination = Path(packet['output_directory'])
    profile = packet['profile']
    assert sha(source) == profile['source_sha256'], 'Source hash mismatch'
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(source))
    scene = bpy.context.scene
    scene.name, scene.render.fps = 'Character Rig Review', 30
    meshes = [o for o in scene.objects if o.type == 'MESH']
    assert len(meshes) == 1 and not any(o.type == 'ARMATURE' for o in scene.objects)
    mesh = meshes[0]
    mesh.name = 'CharacterMesh'
    mesh.data.transform(mesh.matrix_world)
    mesh.matrix_world.identity()
    co = np.array([list(v.co) for v in mesh.data.vertices])
    offset = Vector(((co[:,0].min()+co[:,0].max())/2, 0, co[:,2].min()))
    mesh.data.transform(Matrix.Translation(-offset))
    mesh.data.update()
    original = np.array([list(v.co) for v in mesh.data.vertices])
    original_count, original_faces = len(mesh.data.vertices), len(mesh.data.polygons)
    height = float(np.ptp(original[:,2]))
    armature = bpy.data.armatures.new('HumanoidBody')
    rig = bpy.data.objects.new('HumanoidRig', armature)
    scene.collection.objects.link(rig)
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for spec in profile['bones']:
        bone = armature.edit_bones.new(spec['name'])
        bone.head, bone.tail = spec['head'], spec['tail']
        bone.use_deform = True
        if spec['parent']:
            bone.parent = armature.edit_bones[spec['parent']]
        bone.use_connect = False
    bpy.ops.object.mode_set(mode='OBJECT')
    rig.show_in_front = True
    for bone in rig.pose.bones:
        bone.rotation_mode = 'QUATERNION'
    # A welded weighting proxy closes exporter-created UV/normal seams without
    # changing authored topology, UVs or normals in the deliverable mesh.
    proxy = mesh.copy()
    proxy.data = mesh.data.copy()
    proxy.name = 'WeightingProxy'
    scene.collection.objects.link(proxy)
    bm = bmesh.new()
    bm.from_mesh(proxy.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-7)
    bm.to_mesh(proxy.data)
    bm.free()
    proxy.data.update()
    bpy.ops.object.select_all(action='DESELECT')
    proxy.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    names = [b.name for b in rig.data.bones]
    weights = np.zeros((len(proxy.data.vertices), len(names)))
    for vertex in proxy.data.vertices:
        for group in vertex.groups:
            label = proxy.vertex_groups[group.group].name
            if label in names:
                weights[vertex.index, names.index(label)] = group.weight
    assert np.all(weights.sum(1) > 1e-8), 'Bone heat left unweighted vertices'
    pruned = []
    for row in weights:
        order = np.argsort(row)[::-1]
        pruned.append(float(row[order[profile['max_influences']:]].sum()))
        row[order[profile['max_influences']:]] = 0
        row /= row.sum()
    tree = KDTree(len(proxy.data.vertices))
    for vertex in proxy.data.vertices:
        tree.insert(vertex.co, vertex.index)
    tree.balance()
    groups = [mesh.vertex_groups.new(name=name) for name in names]
    bound = np.zeros((len(mesh.data.vertices), len(names)))
    mapping_error = 0
    for vertex in mesh.data.vertices:
        _, index, error = tree.find(vertex.co)
        mapping_error = max(mapping_error, error)
        assert error < 1e-6, 'Proxy changed the surface'
        row = weights[index]
        bound[vertex.index] = row
        for j in np.flatnonzero(row > 0):
            groups[int(j)].add([vertex.index], float(row[j]), 'REPLACE')
    proxy_count = len(proxy.data.vertices)
    bpy.data.objects.remove(proxy, do_unlink=True)
    mesh.parent = rig
    modifier = mesh.modifiers.new('Humanoid Skin', 'ARMATURE')
    modifier.object = rig
    modifier.use_deform_preserve_volume = False
    np.savez_compressed(destination / 'skin-weights.npz', weights=bound, names=np.array(names), positions=original)
    assert np.isfinite(bound).all() and np.max(abs(bound.sum(1)-1)) < 1e-6
    assert np.max((bound > 0).sum(1)) <= profile['max_influences']
    rest_error = float(np.max(np.linalg.norm(evaluated(scene, mesh, 1)-original, axis=1)))
    assert rest_error < 1e-6, 'Binding changed the rest surface'
    poses = {
        1: ('Rest', {}),
        31: ('Elbows', {'LeftForeArm':((1,0,0),-90),'RightForeArm':((1,0,0),-90)}),
        61: ('Knees', {'LeftLeg':((1,0,0),85),'RightLeg':((1,0,0),85)}),
        91: ('Reach', {'LeftArm':((0,1,0),-45),'RightArm':((0,1,0),45),
                       'LeftForeArm':((1,0,0),-45),'RightForeArm':((1,0,0),-45)}),
        121: ('Crouch', {'LeftUpLeg':((1,0,0),-35),'RightUpLeg':((1,0,0),-35),
                         'LeftLeg':((1,0,0),70),'RightLeg':((1,0,0),70)}),
        151: ('Head turn', {'Head':((0,0,1),20)}),
        181: ('Rest', {}),
    }
    for frame, (label, rotations) in poses.items():
        for bone in rig.pose.bones:
            bone.matrix_basis.identity()
        for name, (axis, angle) in rotations.items():
            set_world_rotation(rig, name, axis, angle)
        if frame == 121:
            rig.pose.bones['Hips'].location.z = -.12
        for bone in rig.pose.bones:
            bone.keyframe_insert('rotation_quaternion', frame=frame)
            bone.keyframe_insert('location', frame=frame)
        scene.timeline_markers.new(label, frame=frame)
    action = rig.animation_data.action
    action.name = 'QA_RigRange'
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:
                        key.interpolation = 'LINEAR'
    scene.frame_start, scene.frame_end = 1, 181
    edges = np.array([list(e.vertices) for e in mesh.data.edges])
    baseline = np.linalg.norm(original[edges[:,0]]-original[edges[:,1]], axis=1)
    valid_edges = baseline > 1e-6
    sampled_frames = sorted(set(poses) | {16,46,76,106,136,166})
    samples, snapshots = [], {}
    for frame in sampled_frames:
        xyz = evaluated(scene, mesh, frame)
        assert np.isfinite(xyz).all(), 'Invalid posed vertex'
        snapshots[frame] = xyz
        ratio = np.linalg.norm(xyz[edges[:,0]]-xyz[edges[:,1]], axis=1)[valid_edges] / baseline[valid_edges]
        samples.append({'frame': frame, 'p99_edge_stretch': float(np.quantile(ratio,.99)),
                        'max_edge_stretch': float(ratio.max()),
                        'max_displacement': float(np.linalg.norm(xyz-original,axis=1).max())})
    report = {'status':'structural_candidate', 'bones':len(names), 'bone_names':names,
              'weight_method':'Blender bone heat on welded proxy, nearest identical position transfer',
              'source_vertices':original_count, 'proxy_vertices':proxy_count, 'source_triangles':original_faces,
              'max_influences':int((bound>0).sum(1).max()), 'unweighted_vertices':int((bound.sum(1)==0).sum()),
              'weight_sum_max_error':float(np.max(abs(bound.sum(1)-1))),
              'max_pruned_weight_mass':max(pruned), 'proxy_mapping_max_error':mapping_error,
              'rest_surface_max_error':rest_error, 'origin_offset_removed':list(offset),
              'height_source_units':height, 'pose_samples':samples, 'profile':profile,
              'limitations':['Body rig only; palms and fingers currently move as one hand.',
                             'Diagnostic pose clip; no locomotion, foot IK, balance or active ragdoll.',
                             'Landmarks are an explicit initial fit; anatomical quality requires visual review.']}
    (destination / 'rig-report.json').write_text(json.dumps(report,indent=2)+'\n')
    scene.frame_set(1)
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = rig
    common = dict(export_format='GLB', use_selection=True, export_skins=True,
                  export_influence_nb=4, export_all_influences=False)
    clean = destination / 'character-rigged.glb'
    diagnostic = destination / 'character-rig-test.glb'
    bpy.ops.export_scene.gltf(filepath=str(clean), export_animations=False, **common)
    bpy.ops.export_scene.gltf(filepath=str(diagnostic), export_animations=True,
                              export_animation_mode='ACTIONS', export_force_sampling=True, **common)
    check_scene = bpy.data.scenes.new('GLB Roundtrip Check')
    bpy.context.window.scene = check_scene
    check_scene.render.fps = 30
    bpy.ops.import_scene.gltf(filepath=str(diagnostic))
    imported_mesh = next(o for o in check_scene.objects if o.type=='MESH')
    imported_rig = next(o for o in check_scene.objects if o.type=='ARMATURE')
    assert len(imported_rig.data.bones) == len(names)
    assert imported_rig.animation_data and imported_rig.animation_data.action, 'Missing diagnostic action'
    # Blender's exporter retains source times: frame 1 is 1/30 s, not zero.
    imported_rest = evaluated(check_scene, imported_mesh, 1)
    tree = KDTree(len(original))
    for index, point in enumerate(original):
        tree.insert(point,index)
    tree.balance()
    indices, errors = [], []
    for point in imported_rest:
        _, index, error = tree.find(point)
        indices.append(index)
        errors.append(error)
    assert max(errors) < 1e-5, 'Roundtrip rest mismatch'
    comparisons = []
    for frame in sampled_frames:
        xyz = evaluated(check_scene, imported_mesh, frame)
        errors = np.linalg.norm(xyz-snapshots[frame][indices],axis=1)
        comparisons.append({'source_frame':frame,'max_vertex_error':float(errors.max()),'mean_vertex_error':float(errors.mean())})
    maximum = max(row['max_vertex_error'] for row in comparisons)
    (destination / 'roundtrip-check.json').write_text(json.dumps({'max_vertex_error':maximum,'samples':comparisons},indent=2)+'\n')
    assert maximum < .0002, 'Roundtrip skinning mismatch'
    report.update(roundtrip_max_vertex_error=maximum, roundtrip_samples=comparisons,
                  glb_skinning_validation='passed', source_geometry_unchanged=sha(source)==profile['source_sha256'])
    assert report['source_geometry_unchanged']
    (destination / 'rig-report.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.context.window.scene = scene
    studio(scene,height,destination,mesh,rig)
    for image in bpy.data.images:
        if image.source == 'FILE' and not image.packed_file:
            image.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(destination/'character-rig-review.blend'))
    files = []
    for name in ['character-rigged.glb','character-rig-test.glb','character-rig-review.blend',
                 'rig-report.json','skin-weights.npz','rest.png','joint-test.png','crouch-test.png']:
        path = destination/name
        files.append({'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size})
    manifest = {'scope':'character_rigging','status':'rig_candidate_ready','fingerprint':packet['fingerprint'],
                'source_job_id':packet['source_job_id'],'source_sha256':profile['source_sha256'],
                'bones':len(names),'max_influences':report['max_influences'], 'unweighted_vertices':report['unweighted_vertices'],
                'roundtrip_max_vertex_error':maximum,'rodin_credits':0,'files':files,
                'next_action':'Review rest pose and joint-test renders before accepting the rig for motion retargeting.',
                'limitations':report['limitations']}
    (destination/'rig-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('CHARACTER_RIG_VALIDATED',json.dumps({k:v for k,v in manifest.items() if k!='files'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--request',type=Path,required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    run(json.loads(args.request.read_text()))
