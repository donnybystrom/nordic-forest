"""Create missing visual views and native story-parent links on the selected board."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from forest_agents.github_board import gh


def gql(query, variables):
    return gh('api', 'graphql', '--input', '-', stdin=json.dumps({'query':query,'variables':variables}))['data']


def configure():
    p=ROOT/'config/github-project.json';config=json.loads(p.read_text());pid=config['id'];owner=config['owner'];number=str(config['number'])
    fields=gh('project','field-list',number,'--owner',owner,'--format','json','--limit','100')['fields']
    visible=[f['id'] for f in fields if f['name'] in {'Title','Status','Kind','Priority','Sprint','Feature','Evidence'}]
    query='query($id:ID!){node(id:$id){...on ProjectV2{views(first:30){nodes{id name layout}}}}}'
    views=gql(query,{'id':pid})['node']['views']['nodes']
    for name,layout in [('Board','BOARD_LAYOUT'),('Sprint Plan','TABLE_LAYOUT'),('Feature Map','TABLE_LAYOUT')]:
        if any(v['name']==name for v in views):continue
        gql('mutation($input:CreateProjectV2ViewInput!){createProjectV2View(input:$input){__typename}}',
            {'input':{'projectId':pid,'name':name,'layout':layout,'configuration':{'visibleFieldIds':visible}}})
    config['views']=gql(query,{'id':pid})['node']['views']['nodes']
    plan=json.loads((ROOT/'data/github-project-plan.json').read_text());links=[]
    for item in plan['items']:
        if not item['parent']:continue
        child_ref=config['issues'][item['id']];parent_ref=config['issues'][item['parent']]
        child=gh('api',f"repos/{config['repo']}/issues/{child_ref['number']}")
        parent=gh('api',f"repos/{config['repo']}/issues/{parent_ref['number']}")
        actual=gql('query($id:ID!){node(id:$id){...on Issue{parent{id}}}}',{'id':child['node_id']})['node']['parent']
        if actual and actual['id']!=parent['node_id']:raise ValueError('Existing parent differs; refusing to reparent')
        if not actual:
            gql('mutation($input:AddSubIssueInput!){addSubIssue(input:$input){__typename}}',
                {'input':{'issueId':parent['node_id'],'subIssueId':child['node_id'],'replaceParent':False}})
        links.append({'story':child_ref['url'],'feature':parent_ref['url']})
    config['parent_links']=links
    p.write_text(json.dumps(config,indent=2)+'\n')
    print(json.dumps({'url':config['url'],'views':config['views'],'parent_links':links},indent=2))


if __name__=='__main__':configure()
