"""Close only the boundaries introduced by the contact-bridge repair."""
import bpy,bmesh,json
import numpy as np
from pathlib import Path
from collections import Counter,defaultdict
OUT=Path('/Users/donnybystrom/code/Nordic-3D-forest/output/zombie-beach/mesh-repair-v1')
ob=bpy.data.objects['ZB_Repaired_Mesh'];bm=bmesh.new();bm.from_mesh(ob.data)
region=bm.verts.layers.int['anatomical_region'];fid=bm.faces.layers.int['source_face_id']
split_count=0
for v in list(bm.verts):
    boundary=[e for e in v.link_edges if e.is_boundary]
    if len(boundary)>2:split_count+=len(bmesh.utils.vert_separate(v,boundary))-1
unseen=set(bm.faces);slivers=[];sliver_source_ids=[]
while unseen:
    first=unseen.pop();component={first};todo=[first]
    while todo:
        f=todo.pop()
        for edge in f.edges:
            for neighbor in edge.link_faces:
                if neighbor in unseen:
                    unseen.remove(neighbor);component.add(neighbor);todo.append(neighbor)
    if len(component)<=8 and any(e.is_boundary for f in component for e in f.edges):
        slivers.extend(component);sliver_source_ids.extend(f[fid] for f in component)
if slivers:bmesh.ops.delete(bm,geom=slivers,context='FACES')
boundary={e for e in bm.edges if e.is_boundary}
assert all(sum(e.is_boundary for e in v.link_edges)==2 for e in boundary for v in e.verts)
loops=[]
while boundary:
    e=next(iter(boundary));old_loop=next(l for l in e.link_faces[0].loops if l.edge==e)
    start=old_loop.link_loop_next.vert;cur=old_loop.vert
    ordered=[start,cur];boundary.remove(e)
    while cur != start:
        candidates=[ed for ed in cur.link_edges if ed in boundary]
        assert len(candidates)==1, 'Ambiguous closure boundary'
        edge=candidates[0];boundary.remove(edge);cur=edge.other_vert(cur)
        if cur != start:ordered.append(cur)
    loops.append(ordered)
uv_layer=bm.loops.layers.uv.active
source_mat=ob.data.materials[0]
bsdf=next(n for n in source_mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
link=bsdf.inputs['Base Color'].links[0]
tex=link.from_node
assert tex.type=='TEX_IMAGE'
im=tex.image;w,h=im.size
pixels=np.empty(w*h*4,np.float32);im.pixels.foreach_get(pixels);pixels=pixels.reshape(h,w,4)
region_colors=defaultdict(list);loop_uvs=[]
for loop in loops:
    regs={v[region] for v in loop};assert len(regs)==1, regs
    reg=next(iter(regs));uvs=[]
    for v in loop:
        candidates=[l[uv_layer].uv.copy() for f in v.link_faces for l in f.loops if l.vert==v]
        uv=candidates[0];uvs.append(uv)
        x=int((uv.x%1)*(w-1));y=int((uv.y%1)*(h-1));region_colors[reg].append(pixels[y,x,:3])
    loop_uvs.append(uvs)
materials={};patchcolors={}
for reg,samples in region_colors.items():
    color=np.median(np.array(samples),axis=0)
    # Image pixel values are sampled in the image's storage color space.
    linear=np.where(color<=0.04045,color/12.92,((color+0.055)/1.055)**2.4)
    mat=bpy.data.materials.new('ZB_RepairSkin_region_'+str(reg));mat.use_nodes=True
    shader=mat.node_tree.nodes.get('Principled BSDF');shader.inputs['Base Color'].default_value=(*linear,1);shader.inputs['Roughness'].default_value=0.82
    ob.data.materials.append(mat);materials[reg]=len(ob.data.materials)-1;patchcolors[str(reg)]={'sampled_srgb':color.tolist(),'material_linear':linear.tolist()}
newfaces=[];info=[]
for verts,uvs in zip(loops,loop_uvs):
    # A contact contour may touch itself geometrically after splitting a
    # pinched vertex. Ear-clipping such an ngon can create duplicate faces.
    # An inset fan provides a unique center and explicit manifold topology.
    center=bm.verts.new(sum((v.co for v in verts),verts[0].co*0)/len(verts))
    normal=sum((f.normal for v in verts for f in v.link_faces),verts[0].co*0)
    if normal.length>1e-8:center.co-=normal.normalized()*0.001
    center[region]=verts[0][region];center[bm.verts.layers.int['source_vertex_id']]=-1
    deform=bm.verts.layers.deform.active
    for vertex in verts:
        for group,weight in vertex[deform].items():center[deform][group]=center[deform].get(group,0)+weight/len(verts)
    uvcenter=sum(uvs,uvs[0]*0)/len(uvs)
    for i,vertex in enumerate(verts):
        f=bm.faces.new((vertex,verts[(i+1)%len(verts)],center));f[fid]=-1;f.material_index=materials[vertex[region]];f.smooth=True
        for l,uv in zip(f.loops,(uvs[i],uvs[(i+1)%len(verts)],uvcenter)):l[uv_layer].uv=uv
        newfaces.append(f)
    info.append({'region':verts[0][region],'boundary_vertices':len(verts),'bounds_min':np.min([v.co for v in verts],axis=0).tolist(),'bounds_max':np.max([v.co for v in verts],axis=0).tolist()})
triangulated=newfaces
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
assert not any(e.is_boundary for e in bm.edges), 'Repair left open boundaries'
assert all(e.is_manifold for e in bm.edges), 'Repair created nonmanifold edges'
bm.to_mesh(ob.data);bm.free();ob.data.update()
assert not ob.data.validate(verbose=True,clean_customdata=False), 'Mesh validation changed the closed candidate'
report=json.loads((OUT/'repair-changes.json').read_text())
report.update({'status':'closed_candidate','split_pinched_boundary_vertices':split_count,'removed_contact_sliver_source_face_ids':sliver_source_ids,'surface_patches':info,'new_patch_triangles':len(triangulated),'patch_materials':patchcolors,'output_vertices':len(ob.data.vertices),'output_triangles':len(ob.data.polygons),'patch_texture_note':'Original surfaces retain their UVs/material. Rebuilt hidden contact surfaces use region-specific skin colors sampled from neighboring texture; missing anatomical detail is not reconstructed.'})
(OUT/'repair-changes.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('status','split_pinched_boundary_vertices','new_patch_triangles','output_vertices','output_triangles')},indent=2));print('patches',info)
