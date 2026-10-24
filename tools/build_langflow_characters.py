"""Build the character broker with the installed Langflow serializer."""
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from integrations.langflow.nordic_character_pipeline import NordicCharacterPipeline
from tools.build_langflow_agents import edge


def build():
    base = json.loads((ROOT / 'flows/langflow/01-plan-feature.json').read_text())
    code = (ROOT / 'integrations/langflow/nordic_character_pipeline.py').read_text()
    node = NordicCharacterPipeline(_code=code).to_frontend_node()
    node.update(id='NordicCharacterPipeline-call', type='genericNode', position={'x': 450, 'y': 80})
    node['data']['id'] = node['id']
    node['data']['node']['field_order'] = ['request_json', 'live', 'run_key']
    common = {'folder_id': base['folder_id'], 'mcp_enabled': False,
              'last_tested_version': '1.12.6', 'description': NordicCharacterPipeline.description}
    component = dict(common, name='NF · Character Pipeline', is_component=True,
                     data={'nodes': [node], 'edges': [], 'viewport': {'x': 20, 'y': 20, 'zoom': .8}})
    (ROOT / 'integrations/langflow/character-pipeline.json').write_text(json.dumps(component, ensure_ascii=False, indent=2) + '\n')
    inp, out = copy.deepcopy(base['data']['nodes'][0]), copy.deepcopy(base['data']['nodes'][-1])
    for item, kind, x in [(inp, 'ChatInput', 0), (out, 'ChatOutput', 1000)]:
        item.update(id=kind + '-Characters', position={'x': x, 'y': 80})
        item['data']['id'] = item['id']
    inp['data']['node']['template']['input_value']['value'] = '{"action":"prepare","character_id":"beach-tourist-zombie-v1","reference_sheets":["assets/work/characters/beach-tourist-zombie-v1/references/model-sheet.png"],"motion_references":["assets/work/characters/beach-tourist-zombie-v1/references/motion-sheet.png"]}'
    first = edge(inp, node, 'request_json')
    first['data']['targetHandle'].update(inputTypes=['Message'], type='str')
    first['targetHandle'] = json.dumps(first['data']['targetHandle']).replace('"', 'œ')
    flow = dict(common, name='06 — Character Pipeline · Rodin', is_component=False,
                data={'nodes': [inp, node, out], 'edges': [first, edge(node, out, 'input_value')],
                      'viewport': {'x': 20, 'y': 20, 'zoom': .8}})
    (ROOT / 'flows/langflow/06-character-pipeline.json').write_text(json.dumps(flow, ensure_ascii=False, indent=2) + '\n')
    print('Built character-pipeline component and flow')


if __name__ == '__main__':
    build()
