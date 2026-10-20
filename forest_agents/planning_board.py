"""Project-scoped planning commands and explicit planning-job dispatch.

GitHub holds editable work; the local single-worker bridge owns job dispatch.
"""
import hashlib
import json
import re
from pathlib import PurePosixPath
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .github_board import gh
from .workflow import ROOT, SECRET_PATTERN, load_config

STATES=['Todo','Ready','In Progress','In Review','Blocked','Done']
START='<!-- nf-ticket-spec:start -->';END='<!-- nf-ticket-spec:end -->'


class TicketSpec(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    id: str = Field(pattern=r'^NF-T\d{3,6}$')
    title: str = Field(min_length=4,max_length=160)
    kind: Literal['Task','Spike'] = 'Task'
    owner_role: str
    objective: str = Field(min_length=10,max_length=2000)
    acceptance: list[str] = Field(min_length=1,max_length=8)
    allowed_paths: list[str] = Field(min_length=1,max_length=10)
    non_goals: list[str] = Field(min_length=1,max_length=8)
    dependencies: list[int] = Field(default_factory=list,max_length=10)
    questions: list[str] = Field(default_factory=list,max_length=8)
    @model_validator(mode='after')
    def safe(self):
        if self.owner_role not in load_config()['roles']:raise ValueError('Unknown owner role')
        text=self.model_dump_json()
        if SECRET_PATTERN.search(text) or 'nf-ticket-spec:' in text:raise ValueError('Invalid ticket content')
        if any(len(x)>2000 for xs in [self.acceptance,self.non_goals,self.questions,self.allowed_paths] for x in xs):raise ValueError('Ticket text budget exceeded')
        if len(set(self.dependencies))!=len(self.dependencies) or any(n<1 for n in self.dependencies):raise ValueError('Invalid dependencies')
        for name in self.allowed_paths:
            p=PurePosixPath(name)
            if not p.parts or p.is_absolute() or '..' in p.parts or '\\' in name or p.parts[0] in {'.git','.codex','.aws'} or 'SECRET_KEY' in name or 'API_TOKEN' in name:raise ValueError('Invalid work scope')
        return self


class BoardCommand(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    action: Literal['inspect','create_ticket','set_state','dispatch_plan','sync_job','link_pr']
    issue: int = Field(default=0,ge=0)
    ticket: TicketSpec | None = None
    parent_issue: int = Field(default=0,ge=0)
    milestone: int = Field(default=0,ge=0)
    state: Literal['Todo','Ready','In Progress','In Review','Blocked','Done'] = 'Todo'
    expected_state: str = ''
    reason: str = Field(default='',max_length=2000)
    evidence: str = Field(default='',max_length=4000)
    job_id: str = Field(default='',max_length=36)
    pr: int = Field(default=0,ge=0)
    close_on_merge: bool = False


def connection():
    return json.loads((ROOT/'config/github-project.json').read_text())


def gql(query, variables):
    return gh('api','graphql','--input','-',stdin=json.dumps({'query':query,'variables':variables}))['data']


def api(path, body=None, method=None):
    args=['api',path]
    if method:args+=['--method',method]
    if body is not None:args+=['--input','-']
    return gh(*args,stdin=json.dumps(body) if body is not None else None)


def inventory():
    c=connection();items=[];after=None
    query='query($id:ID!,$after:String){node(id:$id){...on ProjectV2{items(first:50,after:$after){pageInfo{hasNextPage endCursor} nodes{id content{...on Issue{title url} ...on PullRequest{title url} ...on DraftIssue{title}} fieldValues(first:30){pageInfo{hasNextPage} nodes{...on ProjectV2ItemFieldTextValue{text field{...on ProjectV2Field{name}}} ...on ProjectV2ItemFieldSingleSelectValue{name field{...on ProjectV2SingleSelectField{name}}}}}}}}}}'
    while True:
        page=gql(query,{'id':c['id'],'after':after})['node']['items']
        for row in page['nodes']:
            if row['fieldValues']['pageInfo']['hasNextPage']:raise ValueError('Incomplete item field values')
            item={'id':row['id'],'content':row['content'] or {},'title':(row['content'] or {}).get('title','Archived content')}
            for entry in row['fieldValues']['nodes']:
                if entry.get('field'):item[entry['field']['name']]=entry.get('text',entry.get('name'))
            items.append(item)
        if len(items)>1000:raise ValueError('Board inventory limit reached')
        if not page['pageInfo']['hasNextPage']:return items
        if not page['pageInfo']['endCursor'] or page['pageInfo']['endCursor']==after:raise ValueError('Invalid board pagination')
        after=page['pageInfo']['endCursor']


def value(item,name):
    norm=lambda x:''.join(ch for ch in x.lower() if ch.isalnum())
    return next((v for k,v in item.items() if norm(k)==norm(name)),None)


def card(number,items=None):
    c=connection();url=f"https://github.com/{c['repo']}/issues/{number}"
    matches=[i for i in (inventory() if items is None else items) if i.get('content',{}).get('url')==url]
    if len(matches)!=1:raise ValueError('Issue must appear exactly once on this board')
    return matches[0]



def list_fields():
    c=connection()
    data=gql('query($id:ID!){node(id:$id){...on ProjectV2{fields(first:100){pageInfo{hasNextPage} nodes{...on ProjectV2Field{id name} ...on ProjectV2SingleSelectField{id name options{id name}} ...on ProjectV2IterationField{id name}}}}}}',{'id':c['id']})['node']['fields']
    if data['pageInfo']['hasNextPage']:raise ValueError('Incomplete board field inventory')
    return data['nodes']


def set_field(item_id,name,text):
    if name not in {'Status','Owner Role','Blocker','Agent Job','Evidence','Feature','Kind','Priority','Sprint'}:raise ValueError('Field outside planning scope')
    c=connection();fields=list_fields()
    field=next(f for f in fields if f['name']==name)
    ids={'projectId':c['id'],'itemId':item_id,'fieldId':field['id']}
    if 'options' in field:
        choices=[o for o in field['options'] if o['name']==text]
        if len(choices)!=1:raise ValueError('Unknown board field option')
        payload={'singleSelectOptionId':choices[0]['id']}
    elif text:payload={'text':text}
    else:
        gql('mutation($input:ClearProjectV2ItemFieldValueInput!){clearProjectV2ItemFieldValue(input:$input){__typename}}',{'input':ids})
        return
    gql('mutation($input:UpdateProjectV2ItemFieldValueInput!){updateProjectV2ItemFieldValue(input:$input){__typename}}',{'input':dict(ids,value=payload)})



def issue(number):
    c=connection();return api(f"repos/{c['repo']}/issues/{number}")


def parse_spec(body):
    if body.count(START)!=1 or body.count(END)!=1:raise ValueError('Ticket needs one complete structured work contract')
    raw=body.split(START,1)[1].split(END,1)[0].strip()
    if not raw.startswith('```json\n') or not raw.endswith('\n```'):raise ValueError('Invalid ticket contract block')
    return TicketSpec.model_validate_json(raw[8:-4])


def render(spec):
    return '\n'.join([f"<!-- nordic-work-item:{spec.id} -->",f"## {spec.objective}",'',
        f'Owner role: **{spec.owner_role}** · execution: **planning only**','',
        'This ticket requests a reviewable planning artifact. It does not authorize implementing a game feature, arbitrary shell commands or closing its parent feature.','',
        '### Editable work contract',START,'```json',json.dumps(spec.model_dump(),ensure_ascii=False,indent=2),'```',END,'',
        'The local broker validates this visible contract before dispatch. GitHub Assignee may remain the shared human account; Owner Role identifies the local worker role.'])


def assert_ready(data,spec):
    if data['state']!='open':raise ValueError('Closed issue cannot start work')
    if spec.questions:raise ValueError('Resolve or explicitly re-scope open questions first')
    if data['number'] in spec.dependencies:raise ValueError('Ticket cannot depend on itself')
    for dependency in spec.dependencies:
        if issue(dependency)['state']!='closed':raise ValueError('An explicit prerequisite is still open')


def inspect(number=0):
    c=connection();items=inventory()
    if number:items=[card(number,items)]
    return {'url':c['url'],'repo':c['repo'],'cards':[{'url':i.get('content',{}).get('url'),'title':i['title'],
        **{n:value(i,n) for n in ['Status','Kind','Owner Role','Blocker','Agent Job','Evidence','Feature','Sprint']}} for i in items]}


def create_ticket(command):
    spec=command.ticket
    if spec is None:raise ValueError('Ticket contract required')
    c=connection();marker=f'<!-- nordic-work-item:{spec.id} -->'
    existing=[]
    for page_number in range(1,11):
        page=api(f"repos/{c['repo']}/issues?state=all&per_page=100&page={page_number}")
        existing += [i for i in page if 'pull_request' not in i]
        if len(page)<100:break
    else:raise ValueError('Issue inventory limit reached')
    matches=[i for i in existing if marker in (i['body'] or '')]
    if len(matches)>1:raise ValueError('Duplicate ticket identity')
    if command.parent_issue:parent=issue(command.parent_issue)
    if matches:
        current=issue(matches[0]['number'])
        if parse_spec(current['body']).model_dump()!=spec.model_dump():raise ValueError('Existing ticket differs; edit it explicitly in GitHub')
        data=current
    else:
        payload={'title':spec.id+': '+spec.title,'body':render(spec)}
        if command.milestone:payload['milestone']=command.milestone
        data=api(f"repos/{c['repo']}/issues",payload,'POST')
    items=inventory();matches=[i for i in items if i.get('content',{}).get('url')==data['html_url']]
    item=matches[0] if matches else gql('mutation($input:AddProjectV2ItemByIdInput!){addProjectV2ItemById(input:$input){item{id}}}',{'input':{'projectId':c['id'],'contentId':data['node_id']}})['addProjectV2ItemById']['item']
    if not value(item,'Kind'):set_field(item['id'],'Kind',spec.kind)
    if not value(item,'Owner Role'):set_field(item['id'],'Owner Role',spec.owner_role)
    if not value(item,'Status'):set_field(item['id'],'Status','Todo')
    if command.parent_issue:
        actual=gql('query($id:ID!){node(id:$id){...on Issue{parent{id}}}}',{'id':data['node_id']})['node']['parent']
        if actual and actual['id']!=parent['node_id']:raise ValueError('Ticket already belongs to a different parent')
        if not actual:gql('mutation($input:AddSubIssueInput!){addSubIssue(input:$input){__typename}}',{'input':{'issueId':parent['node_id'],'subIssueId':data['node_id'],'replaceParent':False}})
        if not value(item,'Feature'):
            identity=re.search(r'<!-- nordic-work-item:(NF-[FS]\d+) -->',parent['body'] or '')
            set_field(item['id'],'Feature',identity.group(1) if identity else '#'+str(command.parent_issue))
    return {'url':data['html_url'],'issue':data['number'],'created_or_reused':True}


def set_state(command):
    item=card(command.issue);old=value(item,'Status')
    if not command.expected_state or old!=command.expected_state:raise ValueError('Board state changed; inspect before updating')
    if command.state=='Ready':assert_ready(issue(command.issue),parse_spec(issue(command.issue)['body']))
    if command.state=='Blocked' and not command.reason:raise ValueError('Blocked requires an exact reason/unblocking action')
    if command.state=='Done' and issue(command.issue)['state']!='closed':raise ValueError('Done mirrors an already closed GitHub issue; a planning handover cannot close it')
    if command.state=='In Progress':raise ValueError('Use dispatch_plan to start a traceable job')
    if command.state=='Blocked':set_field(item['id'],'Blocker',command.reason)
    if command.evidence:set_field(item['id'],'Evidence',command.evidence)
    set_field(item['id'],'Status',command.state)
    if command.state=='Ready':set_field(item['id'],'Blocker','')
    return {'issue':command.issue,'previous_state':old,'state':command.state}


def dispatch_plan(command,store,submit_child):
    c=connection();data=issue(command.issue);item=card(command.issue);spec=parse_spec(data['body'])
    fingerprint=hashlib.sha256(json.dumps(spec.model_dump(),sort_keys=True).encode()).hexdigest()
    key=f"board:{command.issue}:{fingerprint}"
    with store.lock:
        row=store.db.execute('SELECT id FROM jobs WHERE idem=?',(key,)).fetchone()
    if row:return {'issue':command.issue,'job_id':row['id'],'reused':True,'status':store.get(row['id'])['status']}
    with store.lock:
        active=store.db.execute("SELECT id FROM jobs WHERE json_extract(request,'$.ticket_issue')=? AND status IN ('queued','running','interrupted','cancel_requested','remote_cancel_unconfirmed')",(command.issue,)).fetchone()
    if active:raise ValueError('This ticket already has an active or unreconciled job')
    if value(item,'Status')!='Ready':raise ValueError('Only Ready tickets may start')
    assert_ready(data,spec)
    if value(item,'Owner Role')!=spec.owner_role:raise ValueError('Visible owner role differs from ticket contract')
    body={'operation':'run_agent','request':spec.objective+'\nReturn one concise planning Handover addressing every acceptance item; do not implement or claim feature acceptance.',
          'target_role':spec.owner_role,'shared_context':json.dumps({'ticket_url':data['html_url'],'ticket_spec':spec.model_dump()},ensure_ascii=False),
          'live':True,'ticket_issue':command.issue}
    jid,fresh=submit_child(body,key)
    store.event(jid,'delivery','board_dispatch_created',{'issue':command.issue,'next_action':'If metadata publication fails, reconcile Agent Job and Status in GitHub before sync_job; never create a replacement run.'})
    set_field(item['id'],'Agent Job',jid);set_field(item['id'],'Status','In Progress')
    return {'issue':command.issue,'job_id':jid,'reused':not fresh,'scope':'planning_only'}


def sync_job(job):
    number=job['request'].get('ticket_issue')
    if not number:raise ValueError('Job does not belong to a board ticket')
    c=connection();item=card(number)
    if value(item,'Agent Job')!=job['id'] or value(item,'Status')!='In Progress':
        return {'issue':number,'board_update':'preserved_external_change'}
    if parse_spec(issue(number)['body']).model_dump()!=json.loads(job['request']['shared_context'])['ticket_spec']:
        return {'issue':number,'board_update':'preserved_changed_ticket_contract'}
    status=job['status']
    if status in {'queued','running'}:return {'issue':number,'board_update':'still_running'}
    if status=='agent_complete':
        handover=job['result']['handover'];marker=f"<!-- nordic-ticket-job:{job['id']} -->"
        comments=gh('api',f"repos/{c['repo']}/issues/{number}/comments?per_page=100")
        if len(comments)>=100:raise ValueError('Comment inventory needs pagination before publication')
        if not any(marker in x['body'] for x in comments):
            body='\n'.join([marker,'## Planning handover · '+job['request']['target_role'],f"Job: `{job['id']}`",'',
                '**Planning deliverable only. Parent feature acceptance is not performed.**','','```json',json.dumps(handover,ensure_ascii=False,indent=2),'```'])
            api(f"repos/{c['repo']}/issues/{number}/comments",{'body':body},'POST')
        state='Blocked' if handover['status']=='BLOCKED' else 'In Review'
        if state=='Blocked':set_field(item['id'],'Blocker',handover['recommendation'][:1800])
        set_field(item['id'],'Evidence','planning job '+job['id'])
    else:
        state='Blocked';set_field(item['id'],'Blocker','Local job '+job['id']+' stopped as '+status+'. Inspect/reconcile the retained job before retrying.')
    set_field(item['id'],'Status',state)
    return {'issue':number,'state':state,'job_id':job['id'],'feature_acceptance':'not_performed'}


def link_pr(command):
    c=connection();data=issue(command.issue);spec=parse_spec(data['body'])
    pr=api(f"repos/{c['repo']}/pulls/{command.pr}")
    if pr['state']!='open' or pr['base']['repo']['full_name']!=c['repo']:raise ValueError('Use an open PR in this repository')
    if command.close_on_merge and spec.kind!='Task':raise ValueError('Automatic closing only applies to a concrete task, not features/stories')
    marker=f'<!-- nordic-ticket-link:{command.issue} -->'
    if marker not in (pr['body'] or ''):
        body=(pr['body'] or '')+'\n\n'+marker+'\n'+('Closes' if command.close_on_merge else 'Refs')+' #'+str(command.issue)
        api(f"repos/{c['repo']}/pulls/{command.pr}",{'body':body},'PATCH')
    set_field(card(command.issue)['id'],'Evidence',pr['html_url'])
    return {'issue':command.issue,'pr_url':pr['html_url'],'close_on_merge':command.close_on_merge}
