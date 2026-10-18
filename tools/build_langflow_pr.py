"""Serialize the PR broker with the installed Langflow Python environment."""
import copy
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from integrations.langflow.nordic_pr_control import NordicPRControl
from tools.build_langflow_agents import edge

base=json.loads((ROOT/'flows/langflow/01-plan-feature.json').read_text())
code=(ROOT/'integrations/langflow/nordic_pr_control.py').read_text();node=NordicPRControl(_code=code).to_frontend_node()
node.update(id='NordicPRControl-call',type='genericNode',position={'x':450,'y':80});node['data']['id']=node['id'];node['data']['node']['field_order']=['request_json','live','run_key']
common={'folder_id':'7ce97d6f-f7c3-4c19-988c-fa353879b9cc','mcp_enabled':False,'last_tested_version':'1.12.6','description':NordicPRControl.description}
comp=dict(common,name='NF · PR Control',is_component=True,data={'nodes':[node],'edges':[],'viewport':{'x':20,'y':20,'zoom':.8}})
(ROOT/'integrations/langflow/pr-control.json').write_text(json.dumps(comp,ensure_ascii=False,indent=2)+'\n')
inp,out=copy.deepcopy(base['data']['nodes'][0]),copy.deepcopy(base['data']['nodes'][-1])
for n,kind,x in [(inp,'ChatInput',0),(out,'ChatOutput',1000)]:
 n.update(id=kind+'-PRControl',position={'x':x,'y':80});n['data']['id']=n['id']
inp['data']['node']['template']['input_value']['value']='{"action":"inspect","number":6}'
e1=edge(inp,node,'request_json');e1['data']['targetHandle']['inputTypes']=['Message'];e1['data']['targetHandle']['type']='str';e1['targetHandle']=json.dumps(e1['data']['targetHandle']).replace('"','œ')
flow=dict(common,name='04 — PR Control',is_component=False,data={'nodes':[inp,node,out],'edges':[e1,edge(node,out,'input_value')],'viewport':{'x':20,'y':20,'zoom':.8}})
(ROOT/'flows/langflow/04-pr-control.json').write_text(json.dumps(flow,ensure_ascii=False,indent=2)+'\n')
print('Built PR Control component and flow')
