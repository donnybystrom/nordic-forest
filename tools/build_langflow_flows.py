"""Create three versioned, secret-free flows from an official I/O template."""
import copy
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(template):
    code = (ROOT / 'integrations/langflow/nordic_job_bridge.py').read_text()
    input_node = next(n for n in template['data']['nodes'] if n['data']['type'] == 'ChatInput')
    output_node = next(n for n in template['data']['nodes'] if n['data']['type'] == 'ChatOutput')
    basecode = input_node['data']['node']['template']['code']
    specs = [
        ('01 — Plan Feature', 'plan_feature', 'Planera en avgränsad ekträds-LOD-jämförelse med leverans och acceptanskriterier.'),
        ('02 — Collect and Audit Reference', 'collect_audit_reference', '0ab534c493e14f67bac01ee94f20e43f'),
        ('03 — Propose Agent Change', 'propose_agent_change', 'Require every LOD recommendation to cite the source mesh hash and distinguish visual acceptance from triangle counts.'),
    ]
    paths = []
    for ix, (title, operation, task) in enumerate(specs, 1):
        nodes = [copy.deepcopy(input_node), copy.deepcopy(output_node)]
        for n, kind, pos in zip(nodes, ['ChatInput', 'ChatOutput'], [{'x': 0, 'y': 80}, {'x': 900, 'y': 80}]):
            nid = kind + '-Nordic' + str(ix)
            n.update(id=nid, position=pos, selected=False, dragging=False)
            n['data']['id'] = nid
            n['data']['node']['minimized'] = False
            n.pop('measured', None)
        nodes[0]['data']['node']['template']['input_value']['value'] = task
        node_id = 'NordicJobBridge-Nordic' + str(ix)
        def field(name, value, typ='str', input_type='StrInput', **extra):
            return {'name': name, 'display_name': name.replace('_', ' ').title(), 'value': value, 'type': typ,
                    '_input_type': input_type, 'required': False, 'show': True, 'advanced': name in {'action','job_id','run_key','target_role','specialists'},
                    'list': False, 'input_types': ['Message'] if name == 'request_text' else [], **extra}
        fields = {
            '_type': 'Component', 'code': dict(basecode, value=code),
            'request_text': field('request_text', task, input_type='MessageTextInput'),
            'operation': field('operation', operation, input_type='DropdownInput', options=[s[1] for s in specs]),
            'live': field('live', False, typ='bool', input_type='BoolInput'),
            'action': field('action', 'submit', input_type='DropdownInput', options=['submit','status','cancel','resume']),
            'job_id': field('job_id', ''), 'run_key': field('run_key', 'pilot-1'),
            'target_role': field('target_role', 'asset_analysis'), 'specialists': field('specialists', ''),
        }
        node = {'id': node_id, 'type': 'genericNode', 'position': {'x': 430, 'y': 80}, 'selected': False,
                'data': {'id': node_id, 'type': 'NordicJobBridge', 'node': {
                    'display_name': 'Nordic Job Bridge', 'description': 'Durable local job bridge · offline by default',
                    'base_classes': ['Message'], 'template': fields, 'field_order': [k for k in fields if k not in {'_type','code'}],
                    'outputs': [{'name':'message','display_name':'Job Status','method':'job_status','types':['Message'],'selected':'Message','value':'__UNDEFINED__','group_outputs':False,'cache':True}],
                    'icon':'Workflow','custom_fields':{},'edited':True,'frozen':False,'minimized':False,'legacy':False,'beta':False}}}
        nodes.insert(1, node)
        edges = []
        for source, target, target_field, target_types, target_type in [(nodes[0],node,'request_text',['Message'],'str'),(node,nodes[2],'input_value',['Data','JSON','DataFrame','Table','Message'],'other')]:
            sh = {'dataType': source['data']['type'], 'id': source['id'], 'name': 'message', 'output_types': ['Message']}
            th = {'fieldName':target_field,'id':target['id'],'inputTypes':target_types,'type':target_type}
            handle = lambda v: json.dumps(v).replace('"', 'œ')
            edges.append({'id': 'edge-' + source['id'] + '-' + target['id'], 'source':source['id'],'target':target['id'],
                          'sourceHandle':handle(sh),'targetHandle':handle(th),'data':{'sourceHandle':sh,'targetHandle':th},'animated':False,'selected':False})
        flow = {'name':title,'id':str(uuid.uuid5(uuid.NAMESPACE_URL,'nordic-forest:'+operation)),
                'description':'Local bridge pilot. Offline by default. Change Execute Live for actual work. Dashboard: http://127.0.0.1:8765/',
                'data':{'nodes':nodes,'edges':edges,'viewport':{'x':10,'y':20,'zoom':.8}},
                'is_component':False,'last_tested_version':'1.12.6','endpoint_name':'nordic-'+operation.replace('_','-'),
                'folder_id':'7ce97d6f-f7c3-4c19-988c-fa353879b9cc','tags':[]}
        path = ROOT / 'flows/langflow' / (str(ix).zfill(2)+'-'+operation.replace('_','-')+'.json')
        path.write_text(json.dumps(flow,ensure_ascii=False,indent=2)+'\n');paths.append(str(path))
    return paths


if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--template',required=True);args=p.parse_args()
    print('\n'.join(build(json.loads(Path(args.template).read_text()))))
