"""Bake an existing humanoid motion set onto another named body rig.

Run in isolated Blender. Direction-aligned reference frames reconcile T/A binds;
target bone lengths are retained and only hips translation is height-scaled.
"""
import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix
from mathutils.kdtree import KDTree


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def glb_info(path):
    with Path(path).open('rb') as stream:
        assert stream.read(4) == b'glTF'
        stream.read(8)
        size, kind = struct.unpack('<II', stream.read(8))
        assert kind == 0x4E4F534A
        return json.loads(stream.read(size))


def mesh_coordinates(scene, mesh, frame):
    bpy.context.window.scene = scene
    scene.frame_set(int(frame), subframe=float(frame % 1))
    obj = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data = obj.to_mesh()
    xyz = np.empty(len(data.vertices)*3, np.float64)
    data.vertices.foreach_get('co',xyz)
    obj.to_mesh_clear()
    matrix = np.array(obj.matrix_world)
    return xyz.reshape(-1,3) @ matrix[:3,:3].T + matrix[:3,3]


def bind_action(rig, action, slot=None):
    rig.animation_data_create()
    rig.animation_data.action = action
    if action:
        rig.animation_data.action_slot = slot or action.slots[0]
    for track in rig.animation_data.nla_tracks:
        track.mute = True


def add_curve(bag, path, axis, frames, values):
    curve = bag.fcurves.new(data_path=path,index=axis)
    curve.keyframe_points.add(len(frames))
    curve.keyframe_points.foreach_set('co',np.stack([frames,values],axis=1).astype(np.float32).ravel())
    for key in curve.keyframe_points:
        key.interpolation = 'LINEAR'
    curve.update()


def retarget(source_path,target_path,destination):
    assert not destination.exists(), 'Use a new versioned motion destination'
    destination.mkdir(parents=True)
    hashes = {'source':sha(source_path),'target':sha(target_path)}
    source_gltf = glb_info(source_path)
    clips = [{'name':a['name'],'duration_seconds':max(source_gltf['accessors'][s['input']]['max'][0] for s in a['samplers'])}
             for a in source_gltf.get('animations',[])]
    assert clips and len({c['name'] for c in clips}) == len(clips)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.name,scene.render.fps = 'Shared Motion Review',30
    bpy.ops.import_scene.gltf(filepath=str(target_path))
    target = next(o for o in scene.objects if o.type=='ARMATURE')
    mesh = next(o for o in scene.objects if o.type=='MESH')
    target_objects = set(scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(source_path))
    source_objects = set(scene.objects)-target_objects
    source = next(o for o in source_objects if o.type=='ARMATURE')
    assert np.max(np.abs(np.array(source.matrix_world)-np.eye(4))) < 1e-5
    assert np.max(np.abs(np.array(target.matrix_world)-np.eye(4))) < 1e-5
    source_actions = {track.name:(track.strips[0].action,track.strips[0].action_slot)
                      for track in source.animation_data.nla_tracks}
    assert set(source_actions) == {c['name'] for c in clips}
    bind_action(source,None)
    bind_action(target,None)
    for rig in (source,target):
        for bone in rig.pose.bones:
            bone.matrix_basis.identity()
    names = [bone.name for bone in target.data.bones]
    ignored_source_bones = [bone.name for bone in source.data.bones if bone.name not in names]
    assert all(name in source.data.bones for name in names)
    parents = {b.name:b.parent.name if b.parent else None for b in target.data.bones}
    rest = {b.name:b.matrix_local.to_quaternion() for b in target.data.bones}
    local_rest = {n:rest[parents[n]].inverted() @ rest[n] if parents[n] else rest[n] for n in names}
    source_ref = {n:source.data.bones[n].matrix_local.to_quaternion() for n in names}
    target_ref = {}
    for name in names:
        sb,tb = source.data.bones[name],target.data.bones[name]
        direction_from = (tb.tail_local-tb.head_local).normalized()
        direction_to = (sb.tail_local-sb.head_local).normalized()
        target_ref[name] = direction_from.rotation_difference(direction_to) @ rest[name]
    source_hips = source.data.bones['Hips'].head_local.copy()
    target_hips = target.data.bones['Hips'].head_local.copy()
    height_scale = target_hips.z/source_hips.z
    pose_checks, baked = [], {}
    for clip in clips:
        name = clip['name']
        action,slot = source_actions[name]
        bind_action(source,action,slot)
        last = round(clip['duration_seconds']*30)
        frames = np.arange(last+1,dtype=np.float64)
        quaternions = {n:np.empty((last+1,4)) for n in names}
        positions = np.empty((last+1,3))
        for index,frame in enumerate(frames):
            scene.frame_set(int(frame))
            current = source.evaluated_get(bpy.context.evaluated_depsgraph_get())
            desired = {n:current.pose.bones[n].matrix.to_quaternion() @ source_ref[n].inverted() @ target_ref[n] for n in names}
            for bone_name in names:
                parent = parents[bone_name]
                relative = desired[parent].inverted() @ desired[bone_name] if parent else desired[bone_name]
                q = local_rest[bone_name].inverted() @ relative
                q.normalize()
                if index and np.dot(quaternions[bone_name][index-1],np.array(q)) < 0:
                    q.negate()
                quaternions[bone_name][index] = q
            delta = (current.pose.bones['Hips'].head-source_hips)*height_scale
            positions[index] = rest['Hips'].inverted() @ delta
            if index in {0,last//4,last//2,3*last//4,last}:
                for bone_name in names:
                    target.pose.bones[bone_name].rotation_mode = 'QUATERNION'
                    target.pose.bones[bone_name].rotation_quaternion = quaternions[bone_name][index]
                target.pose.bones['Hips'].location = positions[index]
                bpy.context.view_layer.update()
                current_target = target.evaluated_get(bpy.context.evaluated_depsgraph_get())
                errors = [min(math.degrees(current_target.pose.bones[n].matrix.to_quaternion().rotation_difference(desired[n]).angle),
                              abs(360-math.degrees(current_target.pose.bones[n].matrix.to_quaternion().rotation_difference(desired[n]).angle))) for n in names]
                pose_checks.append({'clip':name,'frame':index,'max_rotation_error_degrees':max(errors),
                                    'hips_error':float((current_target.pose.bones['Hips'].head-(target_hips+delta)).length)})
        target_action = bpy.data.actions.new('Shared_'+name)
        target_slot = target_action.slots.new(id_type='OBJECT',name=target.name)
        layer = target_action.layers.new('Retargeted body motion')
        bag = layer.strips.new(type='KEYFRAME').channelbags.new(target_slot)
        for bone_name in names:
            for axis in range(4):
                add_curve(bag,'pose.bones['+json.dumps(bone_name)+'].rotation_quaternion',axis,frames,quaternions[bone_name][:,axis])
        for axis in range(3):
            add_curve(bag,'pose.bones["Hips"].location',axis,frames,positions[:,axis])
        track = target.animation_data.nla_tracks.new()
        track.name = name
        strip = track.strips.new(name,0,target_action)
        strip.action_slot = target_slot
        track.mute = True
        baked[name] = (target_action,target_slot)
        print('RETARGETED',name,'frames',last+1,flush=True)
    assert max(c['max_rotation_error_degrees'] for c in pose_checks) < .15
    assert max(c['hips_error'] for c in pose_checks) < .00001
    snapshots, strain = {}, []
    original = np.array([list(mesh.matrix_world @ v.co) for v in mesh.data.vertices])
    edges = np.array([list(e.vertices) for e in mesh.data.edges])
    edge_lengths = np.linalg.norm(original[edges[:,0]]-original[edges[:,1]],axis=1)
    valid_edges = edge_lengths > 1e-6
    for clip in clips:
        bind_action(target,*baked[clip['name']])
        for phase in (0,.25,.5,.75,1):
            frame = round(clip['duration_seconds']*30)*phase
            xyz = mesh_coordinates(scene,mesh,frame)
            assert np.isfinite(xyz).all()
            snapshots[(clip['name'],phase)] = xyz
            lengths = np.linalg.norm(xyz[edges[:,0]]-xyz[edges[:,1]],axis=1)
            strain.append({'clip':clip['name'],'phase':phase,
                           'p99_edge_stretch':float(np.quantile(lengths[valid_edges]/edge_lengths[valid_edges],.99)),
                           'max_edge_growth':float((lengths-edge_lengths).max())})
    bind_action(target,None)
    for bone in target.pose.bones:
        bone.matrix_basis.identity()
    for obj in source_objects:
        bpy.data.objects.remove(obj,do_unlink=True)
    scene.frame_start,scene.frame_end = 0,max(round(c['duration_seconds']*30) for c in clips)
    scene.frame_set(0)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in (target,mesh):
        obj.select_set(True)
    bpy.context.view_layer.objects.active = target
    exported = destination/'character-animated.glb'
    bpy.ops.export_scene.gltf(filepath=str(exported),export_format='GLB',use_selection=True,use_active_scene=True,
                              export_animations=True,export_animation_mode='NLA_TRACKS',export_force_sampling=True,
                              export_frame_range=False,export_skins=True,export_influence_nb=4,
                              export_all_influences=False,export_current_frame=False,export_rest_position_armature=True)
    gltf = glb_info(exported)
    durations = {a['name']:max(gltf['accessors'][s['input']]['max'][0] for s in a['samplers']) for a in gltf['animations']}
    assert set(durations) == {c['name'] for c in clips}
    assert max(abs(durations[c['name']]-c['duration_seconds']) for c in clips) < .00002
    roundtrip = bpy.data.scenes.new('Motion GLB Roundtrip')
    roundtrip.render.fps = 30
    bpy.context.window.scene = roundtrip
    bpy.ops.import_scene.gltf(filepath=str(exported))
    imported = next(o for o in roundtrip.objects if o.type=='ARMATURE')
    imported_mesh = next(o for o in roundtrip.objects if o.type=='MESH')
    imported_actions = {t.name:(t.strips[0].action,t.strips[0].action_slot) for t in imported.animation_data.nla_tracks}
    assert set(imported_actions) == set(baked)
    bind_action(imported,None)
    for bone in imported.pose.bones:
        bone.matrix_basis.identity()
    rest_positions = mesh_coordinates(roundtrip,imported_mesh,0)
    tree = KDTree(len(original))
    for index,point in enumerate(original):
        tree.insert(point,index)
    tree.balance()
    mapping,rest_errors = [],[]
    for point in rest_positions:
        _,index,error = tree.find(point)
        mapping.append(index)
        rest_errors.append(error)
    assert max(rest_errors) < 1e-5
    checks = []
    for clip in clips:
        bind_action(imported,*imported_actions[clip['name']])
        for phase in (0,.25,.5,.75,1):
            frame = round(clip['duration_seconds']*30)*phase
            xyz = mesh_coordinates(roundtrip,imported_mesh,frame)
            errors = np.linalg.norm(xyz-snapshots[(clip['name'],phase)][mapping],axis=1)
            checks.append({'clip':clip['name'],'phase':phase,'max_vertex_error':float(errors.max()),'mean_vertex_error':float(errors.mean())})
    assert max(c['max_vertex_error'] for c in checks) < .0002
    bpy.context.window.scene = scene
    bind_action(target,None)
    for bone in target.pose.bones:
        bone.matrix_basis.identity()
    scene.frame_set(0)
    bpy.ops.wm.save_as_mainfile(filepath=str(destination/'character-animated.blend'))
    assert sha(source_path) == hashes['source'] and sha(target_path) == hashes['target']
    report = {'status':'retargeted_candidate','source':str(source_path),'target':str(target_path),'source_hashes':hashes,
              'bones':len(names),'mapped_bones':names,'ignored_source_bones':ignored_source_bones,
              'reference':'Source rest directions; target rest frames minimally rotated to the same anatomical directions before transferring model-space rotation deltas.',
              'hips_translation_scale':height_scale,'clips':clips,'pose_checks':pose_checks,'deformation_samples':strain,
              'roundtrip_samples':checks,'roundtrip_max_vertex_error':max(c['max_vertex_error'] for c in checks),
              'max_rotation_error_degrees':max(c['max_rotation_error_degrees'] for c in pose_checks),
              'frames_baked':sum(round(c['duration_seconds']*30)+1 for c in clips),
              'files':[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in [exported,destination/'character-animated.blend']],
              'limitations':['Finger motion is omitted on the 22-bone target.','No planted-foot IK, self-collision, balance, damage or active-ragdoll acceptance.','Source motion and source contact errors are retained; proportions may introduce additional contact errors.']}
    (destination/'retarget-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('MOTION_RETARGET_COMPLETE',json.dumps({k:v for k,v in report.items() if k not in {'pose_checks','deformation_samples','roundtrip_samples','files'}}),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--target',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    retarget(args.source.resolve(),args.target.resolve(),args.output.resolve())
