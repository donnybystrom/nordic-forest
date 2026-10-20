"""Build 15 fixed-role components and 15 runnable flows with Langflow's own serializer.

Run with the Langflow Python environment, not the harness environment.
"""
import copy
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = '7ce97d6f-f7c3-4c19-988c-fa353879b9cc'


def role_code(role, spec):
    source = (ROOT / 'integrations/langflow/nordic_agent.py').read_text()
    cls = 'Nordic' + ''.join(word.title() for word in role.split('_'))
    return (source.replace('NordicSavedAgent', cls)
            .replace("display_name = 'NF · Product Lead'", 'display_name = ' + repr('NF · ' + spec['name']))
            .replace('saved Nordic Forest Product Lead.', 'saved Nordic Forest ' + spec['name'] + '.')
            .replace("role = 'product_lead'", 'role = ' + repr(role))), cls


def edge(source, target, field):
    sh = {'dataType': source['data']['type'], 'id': source['id'], 'name': 'message', 'output_types': ['Message']}
    th = {'fieldName': field, 'id': target['id'], 'inputTypes': ['Message'] if field == 'request_text' else ['Data','JSON','DataFrame','Table','Message'],
          'type': 'str' if field == 'request_text' else 'other'}
    handle = lambda v: json.dumps(v).replace('"', 'œ')
    return {'id': 'edge-' + source['id'] + '-' + target['id'], 'source': source['id'], 'target': target['id'],
            'sourceHandle': handle(sh), 'targetHandle': handle(th), 'data': {'sourceHandle': sh, 'targetHandle': th}}


def build():
    config = json.loads((ROOT / 'config/agents.json').read_text())
    base = json.loads((ROOT / 'flows/langflow/01-plan-feature.json').read_text())
    out = ROOT / 'flows/langflow/agents'; out.mkdir(exist_ok=True)
    components = ROOT / 'integrations/langflow/agents'; components.mkdir(exist_ok=True)
    flows, catalog, bindings = [], [], []
    def wrap(title, key, nodes, edges, component=False):
        return {'name': title, 'id': str(uuid.uuid5(uuid.NAMESPACE_URL, 'nordic-forest:role:' + key)),
                'description': 'Saved OpenAI role through the local durable bridge. Offline by default. Task + upstream context → planning Handover.',
                'is_component': component, 'folder_id': FOLDER, 'mcp_enabled': False,
                'endpoint_name': 'nf-' + key.replace('_','-'), 'last_tested_version': '1.12.6',
                'data': {'nodes': nodes, 'edges': edges, 'viewport': {'x': 20, 'y': 20, 'zoom': .7}}}
    for ix, (role, spec) in enumerate(config['roles'].items()):
        code, cls = role_code(role, spec)
        namespace = {'__name__': '__main__'}
        exec(compile(code, '<' + cls + '>', 'exec'), namespace)
        instance = namespace[cls](_code=code)
        n = instance.to_frontend_node()
        n.update(id=cls + '-call', type='genericNode', position={'x': 450, 'y': 80})
        n['data'].update(id=n['id'])
        n['data']['node']['field_order'] = ['request_text', 'shared_context', 'live', 'run_key']
        n['data']['node']['template']['request_text']['value'] = 'Beskriv ditt ansvarsområde och föreslå ett avgränsat nästa steg. Håll svaret under 200 ord.'
        n['data']['node']['template']['run_key']['value'] = 'role-' + role + '-1'
        comp = wrap('NF · ' + spec['name'], 'component_' + role, [copy.deepcopy(n)], [], True)
        (components / (role + '.json')).write_text(json.dumps(comp, ensure_ascii=False, indent=2) + '\n')
        inp, output = copy.deepcopy(base['data']['nodes'][0]), copy.deepcopy(base['data']['nodes'][-1])
        for node, typ, x in [(inp, 'ChatInput', 0), (output, 'ChatOutput', 1000)]:
            node.update(id=typ + '-' + role, position={'x': x, 'y': 80})
            node['data']['id'] = node['id']
        inp['data']['node']['template']['input_value']['value'] = n['data']['node']['template']['request_text']['value']
        flow = wrap('Agent · ' + spec['name'], role, [inp, copy.deepcopy(n), output], [edge(inp,n,'request_text'), edge(n,output,'input_value')])
        (out / (role + '.json')).write_text(json.dumps(flow, ensure_ascii=False, indent=2) + '\n')
        flows += [comp, flow]
        tile = copy.deepcopy(n); tile['position'] = {'x': (ix % 5) * 440, 'y': (ix // 5) * 650};catalog.append(tile)
        bindings.append({'role': role, 'name': spec['name'], 'agent_id': spec['platform_agent_id'],
                         'component_import_id': comp['id'], 'flow_import_id': flow['id'], 'component_class': cls})
    library = wrap('00 — Agent Library · 15 roles', 'library', catalog, [])
    flows.append(library)
    (ROOT / 'flows/langflow/00-agent-library.json').write_text(json.dumps(library, ensure_ascii=False, indent=2) + '\n')
    bundle = ROOT / 'flows/langflow/nordic-agent-library.json'
    bundle.write_text(json.dumps({'folder_name': 'Nordic Forest Agent Library', 'folder_description': '15 saved-role components and runnable flows; offline by default.', 'flows': flows}, ensure_ascii=False, indent=2) + '\n')
    (ROOT / 'config/langflow-agents.json').write_text(json.dumps({'schema_version': 1, 'project_id': config['project_id'],
        'langflow_folder_id': FOLDER, 'generated_for_version': '1.12.6', 'id_note': 'Desktop upload assigns new IDs; these are stable source-template IDs, not installed Desktop IDs.', 'roles': bindings}, ensure_ascii=False, indent=2) + '\n')
    print(f'Built {len(bindings)} components, {len(bindings)} runnable flows and one visual library: {bundle}')


if __name__ == '__main__':
    build()
