"""Read-only GLB inventory, embedded PNG sizes and exact geometry stream hashes."""
import hashlib, json, struct
from pathlib import Path

ROOT = Path('/Users/donnybystrom/code/Nordic-3D-forest')
OUT = ROOT/'output/zombie-beach/rodin-audit-v1'
records = []
for path in sorted((ROOT/'assets/models/zombies/zombie girl hyper3d').rglob('*.glb')):
    raw = path.read_bytes()
    size = struct.unpack_from('<I', raw, 12)[0]
    gltf = json.loads(raw[20:20+size])
    binary = raw[28+size:]
    def view(index):
        v = gltf['bufferViews'][index]
        start = v.get('byteOffset', 0)
        return binary[start:start+v['byteLength']]
    def digest(index):
        accessor = gltf['accessors'][index]
        return hashlib.sha256(view(accessor['bufferView'])).hexdigest()
    primitive = gltf['meshes'][0]['primitives'][0]
    images = []
    for img in gltf.get('images', []):
        data = view(img['bufferView'])
        png = data.startswith(b'\x89PNG\r\n\x1a\n')
        images.append({'name':img.get('name'), 'mime_type':img.get('mimeType'),
            'bytes':len(data), 'dimensions':list(struct.unpack_from('>II', data, 16)) if png else None,
            'sha256':hashlib.sha256(data).hexdigest()})
    records.append({'path':str(path.relative_to(ROOT)), 'bytes':len(raw),
        'sha256':hashlib.sha256(raw).hexdigest(), 'generator':gltf.get('asset',{}).get('generator'),
        'vertices':gltf['accessors'][primitive['attributes']['POSITION']]['count'],
        'triangles':gltf['accessors'][primitive['indices']]['count']//3,
        'skin_bones':[gltf['nodes'][i].get('name') for i in gltf['skins'][0]['joints']],
        'animations':[{'name':a['name'], 'duration_seconds':max(
            gltf['accessors'][s['input']]['max'][0] for s in a['samplers'])}
            for a in gltf.get('animations',[])],
        'attribute_buffer_hashes':{k:digest(v) for k,v in primitive['attributes'].items()},
        'index_buffer_hash':digest(primitive['indices']), 'images':images,
        'materials':gltf.get('materials',[])})
(OUT/'source-inventory.json').write_text(json.dumps(records, indent=2)+'\n')
print(json.dumps([{'path':r['path'], 'vertices':r['vertices'], 'triangles':r['triangles'],
    'bones':len(r['skin_bones']), 'images':[(i['name'],i['dimensions']) for i in r['images']]}
    for r in records], indent=2))
