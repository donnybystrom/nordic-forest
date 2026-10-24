"""Matched-camera renders of source and repaired mesh, then a comparison grid."""
import bpy,numpy as np,json
from pathlib import Path
from mathutils import Vector
OUT=Path('/Users/donnybystrom/code/Nordic-3D-forest/output/zombie-beach/mesh-repair-v1')
s=bpy.data.scenes['ZombieRepair_v1'];rig=bpy.data.objects['ZB_Source_Rig'];src=bpy.data.objects['ZB_Source_Mesh'];dst=bpy.data.objects['ZB_Repaired_Mesh']
s.render.resolution_x=600;s.render.resolution_y=800
cases=[('running','Running.001',7.6,(0,-4,0.85),(0,0,0.85),1.9),('crawl','_01a16043_e8e4_7705_974e_7295ad5d516a.001',14.95,(0.9,-3,1.4),(0,0,0.38),1.7),('walk','Unsteady_Walk.001',35.6,(1,-4,1.15),(0,0,0.85),1.9)]
records=[]
available=[strip.action for track in rig.animation_data.nla_tracks for strip in track.strips]
for label,action,frame,camloc,target,scale in cases:
    base=action.removesuffix('.001');matched=next(a for a in available if a.name==base or a.name.startswith(base+'.'))
    rig.animation_data.action=matched;rig.animation_data.action_slot=rig.animation_data.action.slots[0]
    s.frame_set(int(frame),subframe=frame%1);s.camera.location=camloc;s.camera.rotation_euler=(Vector(target)-s.camera.location).to_track_quat('-Z','Y').to_euler();s.camera.data.ortho_scale=scale
    pair=[]
    for name,visible,hidden in [('before',src,dst),('after',dst,src)]:
        visible.hide_render=False;visible.hide_set(False);hidden.hide_render=True;hidden.hide_set(True)
        s.render.filepath=str(OUT/(label+'-'+name+'.png'));bpy.ops.render.render(write_still=True)
        im=bpy.data.images.load(s.render.filepath,check_existing=False);pix=np.empty(600*800*4,np.float32);im.pixels.foreach_get(pix);pair.append(pix.reshape(800,600,4));bpy.data.images.remove(im)
    records.append(pair)
canvas=np.concatenate([np.concatenate(row,axis=1) for row in records[::-1]],axis=0)
image=bpy.data.images.new('ZB_Comparison_Grid',width=1200,height=2400,alpha=True)
image.pixels.foreach_set(canvas.ravel());image.filepath_raw=str(OUT/'before-after-comparison.png');image.file_format='PNG';image.save()
src.hide_render=True;src.hide_set(True);dst.hide_render=False;dst.hide_set(False)
(OUT/'comparison-poses.json').write_text(json.dumps({'columns':['source','repaired'],'rows_top_to_bottom':[{'name':c[0],'action':c[1],'frame':c[2]} for c in cases]},indent=2)+'\n')
print('Saved comparison',image.filepath_raw)
