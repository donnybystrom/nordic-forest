"""Idempotent Nordic Forest planning setup; preserve existing work and manual edits."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from forest_agents.planning_board import connection,gql,api,inventory,value,set_field,BoardCommand,TicketSpec,create_ticket,set_state,list_fields
from forest_agents.github_board import gh


def configure():
    c=connection();pid=c['id'];repo=c['repo'];number=str(c['number'])
    fields=list_fields()
    status=next(f for f in fields if f['name']=='Status')
    full=gql('query($id:ID!){node(id:$id){...on ProjectV2SingleSelectField{options{id name color description}}}}',{'id':status['id']})['node']['options']
    desired=[('Todo','GRAY'),('Ready','BLUE'),('In Progress','YELLOW'),('In Review','PURPLE'),('Blocked','RED'),('Done','GREEN')]
    byname={o['name']:o for o in full}
    if not all(name in byname for name,_ in desired):
        options=[byname.get(name,{'name':name,'color':color,'description':''}) for name,color in desired]
        options += [o for o in full if o['name'] not in {name for name,_ in desired}]
        gql('mutation($input:UpdateProjectV2FieldInput!){updateProjectV2Field(input:$input){__typename}}',{'input':{'fieldId':status['id'],'singleSelectOptions':options}})
    for name in ['Owner Role','Blocker','Agent Job']:
        if not any(f['name']==name for f in fields):gh('project','field-create',number,'--owner',c['owner'],'--name',name,'--data-type','TEXT','--format','json')
    fields=list_fields()
    visible=[next(f['id'] for f in fields if f['name']==name) for name in ['Title','Status','Kind','Owner Role','Priority','Milestone','Parent issue','Sub-issues progress','Linked pull requests','Blocker','Agent Job','Evidence']]
    query='query($id:ID!){node(id:$id){...on ProjectV2{views(first:30){nodes{id name layout filter}}}}}'
    views=gql(query,{'id':pid})['node']['views']['nodes']
    for name,layout,filter_text in [('Ready for agents','TABLE_LAYOUT','status:Ready'),('Needs input','TABLE_LAYOUT','status:Blocked')]:
        if not any(v['name']==name for v in views):
            created_view=gql('mutation($input:CreateProjectV2ViewInput!){createProjectV2View(input:$input){projectV2View{id}}}',{'input':{'projectId':pid,'name':name,'layout':layout,'configuration':{'visibleFieldIds':visible}}})['createProjectV2View']['projectV2View']
            gql('mutation($input:UpdateProjectV2ViewInput!){updateProjectV2View(input:$input){__typename}}',{'input':{'viewId':created_view['id'],'filter':filter_text}})
    for v in views:
        if v['name'] in {'Board','Feature Map','Sprint Plan'}:
            gql('mutation($input:UpdateProjectV2ViewInput!){updateProjectV2View(input:$input){__typename}}',{'input':{'viewId':v['id'],'configuration':{'visibleFieldIds':visible}}})
    milestones=api(f'repos/{repo}/milestones?state=all&per_page=100');milestone_map={m['title']:m for m in milestones}
    for title,description in [('A0 — Agent workflow foundation','Reviewable agent planning, Langflow, local delivery and board integration. No game feature acceptance implied.'),('R0 — Reference asset slice','One tree family and one scan, with source identity, measured conversion and comparison evidence.'),('M0 — Renderer and authoring decision','Representative decision scene, hardware-specific measurements and visual review. Dates remain uncommitted.')]:
        if title not in milestone_map:milestone_map[title]=api(f'repos/{repo}/milestones',{'title':title,'description':description},'POST')
    existing=inventory();roles={1:'technical_lead',2:'product_lead',3:'qa',4:'asset_analysis',5:'rendering'}
    for n,role in roles.items():
        data=api(f'repos/{repo}/issues/{n}');item=next(i for i in existing if i.get('content',{}).get('url')==data['html_url'])
        if not value(item,'Owner Role'):set_field(item['id'],'Owner Role',role)
        title='A0 — Agent workflow foundation' if n<4 else 'R0 — Reference asset slice' if n==4 else 'M0 — Renderer and authoring decision'
        if not data['milestone']:api(f'repos/{repo}/issues/{n}',{'milestone':milestone_map[title]['number']},'PATCH')
        if n<4 and value(item,'Status')=='In Progress' and api(f'repos/{repo}/pulls/6')['merged']:
            set_field(item['id'],'Status','In Review')
    specs=[
      (4,'R0 — Reference asset slice',TicketSpec(id='NF-T001',title='Plan the first oak-family evidence and conversion checklist',kind='Spike',owner_role='asset_analysis',
       objective='Using the supplied reference catalog and pipeline notes, propose a bounded evidence checklist for one oak family. Clearly distinguish supplied measurements from missing file/Blender/render checks.',
       acceptance=['Identify one candidate source family and cite only supplied source/hash references, marking unavailable identities unknown.','Separate structural LOD checks, matched visual comparison and runtime measurements.','Give Technical Artist a short dependency-ordered next experiment; do not claim conversion or visual acceptance.'],
       allowed_paths=['docs/REFERENCE-ASSET-PIPELINE.md','data/references/analysis/'],non_goals=['No model editing, downloading, engine execution or visual approval.'])),
      (5,'M0 — Renderer and authoring decision',TicketSpec(id='NF-T002',title='Plan a reproducible M1 renderer benchmark protocol',kind='Spike',owner_role='rendering',
       objective='Propose the measurement protocol for the first representative renderer decision scene, distinguishing base M1 from M1 Pro and measured results from future experiments.',
       acceptance=['Specify scene/camera/settings identity and a repeatable traversal.','Define warmup, sample duration, p50/p95/p99 frame time, memory and hitch reporting.','State what remains unknown until an actual hardware run and matched images exist.'],
       allowed_paths=['docs/decisions/','data/benchmarks/'],non_goals=['No measured performance claims or engine decision.'])),
      (4,'R0 — Reference asset slice',TicketSpec(id='NF-T003',title='Review the acceptance contract for a tree/scan recipe',kind='Spike',owner_role='qa',
       objective='Propose an independent acceptance checklist for a source-to-runtime tree/photogrammetry recipe, using the supplied reference pipeline context.',
       acceptance=['Define source/derived hash and lineage requirements.','Separate mesh counts, rendered appearance and runtime frame cost.','Include a missing-evidence failure case and the exact next owner; no game feature approval.'],
       allowed_paths=['docs/REFERENCE-ASSET-PIPELINE.md','docs/VERIFICATION.md'],non_goals=['No file mutation, rendered evaluation or runtime certification.'])),
      (5,'M0 — Renderer and authoring decision',TicketSpec(id='NF-T004',title='Prepare the human visual-target review when comparison images exist',kind='Task',owner_role='art_director',
       objective='Prepare a visual review brief for the first renderer comparison once actual matched reference images and scene settings are available.',
       acceptance=['Identify the actual image set, scene revision and settings.','List the visual decisions for the human without treating an AI preference as visual acceptance.'],
       allowed_paths=['docs/art/'],non_goals=['No invented images or automatic human visual approval.'],questions=['Which actual matched comparison images and scene revision will be reviewed? They are not available yet.']))]
    created=[]
    for parent,milestone,spec in specs:
        ref=create_ticket(BoardCommand(action='create_ticket',ticket=spec,parent_issue=parent,milestone=milestone_map[milestone]['number']))
        items=inventory();item=next(i for i in items if i.get('content',{}).get('url')==ref['url'])
        if value(item,'Status')=='Todo':
            set_state(BoardCommand(action='set_state',issue=ref['issue'],expected_state='Todo',state='Blocked' if spec.questions else 'Ready',reason='Await actual matched renderer comparison images; Art Director prepares the brief and the human owns visual acceptance.' if spec.questions else ''))
        created.append(dict(ref,id=spec.id,owner_role=spec.owner_role))
    readme='''# Nordic Forest — planning and agent work

Board: all work by status. Ready for agents: bounded planning tickets with a complete editable contract. Needs input: explicit blockers and unblocking owners. Feature Map: parent/child hierarchy and progress. Sprint Plan uses planning tags; no dates are committed.

Milestones are delivery checkpoints; Feature → Story → Task is represented with parent/sub-issues. Owner Role identifies the local agent role while GitHub uses the shared account. Agent Job and Evidence link actual runs and PRs.

Todo → Ready → In Progress → In Review → Done; Blocked carries an exact unblocking action. A finished planning job moves to In Review and posts its handover. It does not close a feature or certify game behavior. Done mirrors an already closed GitHub issue.

Langflow: 05 — Planning Board / NF · Planning Board. Inspect before writes. dispatch_plan starts only an explicit Ready ticket, one saved-role planning job, with duplicate-dispatch protection in the local single-worker bridge. There is no unattended backlog polling or implementation loop.
'''
    gh('project','edit',number,'--owner',c['owner'],'--readme',readme)
    c['planning']={'configured_on':'2026-10-20','statuses':[x[0] for x in desired],'milestones':{name:m['number'] for name,m in milestone_map.items()},'tickets':created,'scope':'explicit_ready_ticket_planning_dispatch_only'}
    c['views']=gql(query,{'id':pid})['node']['views']['nodes'];(ROOT/'config/github-project.json').write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'url':c['url'],'tickets':created,'views':c['views']},ensure_ascii=False,indent=2))


if __name__=='__main__':configure()
