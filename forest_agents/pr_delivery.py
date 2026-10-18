"""Bounded GitHub PR operations; existing gh credential stays outside model input.

No checkout, shell tool, arbitrary repository, force push or administrative merge.
Policy comes from the local trusted checkout, never from the PR's branch.
"""
import argparse
import json
import re
import subprocess
from pathlib import PurePosixPath

from .workflow import ROOT, SECRET_PATTERN


def policy():
    return json.loads((ROOT / 'config/pr-policy.json').read_text())


def github(*args, payload=None, allowed_codes=(0,)):
    cmd = ['gh', *args]
    if payload is not None:
        cmd += ['--input', '-']
    p = subprocess.run(cmd, input=json.dumps(payload) if payload is not None else None,
                       cwd=ROOT, capture_output=True, text=True, timeout=45)
    if p.returncode not in allowed_codes:
        raise RuntimeError('GitHub request failed; inspect authentication, permissions and PR state')
    return json.loads(p.stdout) if p.stdout.strip() else None


def api(path, payload=None, method=None):
    return github('api', path, *(['--method', method] if method else []), payload=payload)


def paged(path):
    rows = []
    for page in range(1, 31):
        part = api(path + ('&' if '?' in path else '?') + f'per_page=100&page={page}')
        rows += part
        if len(part) < 100:
            return rows
    raise ValueError('Incomplete inventory; refusing a partial review/merge decision')


def classify(files, rules=None):
    rules = rules or policy()
    units, roles, human, unknown = set(), set(), False, []
    small = bool(files) and len(files) <= rules['automatic_merge']['maximum_files']
    lines = 0
    for f in files:
        name = f['filename']
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name:
            raise ValueError('Invalid repository path')
        # First matching owner wins; sensitive prefixes precede general ones.
        owner = next((o for o in rules['ownership'] if any(name.startswith(p) for p in o['prefixes'])), None)
        if owner:
            units.add(owner['unit']); roles.update(owner['review_roles']); human |= owner['human_decision']
        else:
            unknown.append(name); human = True
        auto = rules['automatic_merge']
        small &= (any(name.startswith(p) for p in auto['allowed_prefixes']) and path.suffix in auto['allowed_suffixes']
                  and f.get('status') in {'added', 'modified'} and not f.get('previous_filename'))
        lines += f['additions'] + f['deletions']
    small &= lines <= rules['automatic_merge']['maximum_changed_lines'] and not human
    return {'units': sorted(units), 'review_roles': sorted(roles), 'human_decision': human,
            'unclassified_files': unknown, 'files': len(files), 'changed_lines': lines,
            'merge_lane': 'small_documentation' if small else 'owned_review'}


def snapshot(number):
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise ValueError('Use a positive PR number')
    rules = policy(); repo = rules['repo']
    pr = api(f'repos/{repo}/pulls/{number}')
    files = paged(f'repos/{repo}/pulls/{number}/files')
    if len(files) != pr['changed_files']:
        raise ValueError('Incomplete changed-file inventory')
    reviews = paged(f'repos/{repo}/pulls/{number}/reviews')
    comments = paged(f'repos/{repo}/issues/{number}/comments')
    query = '''query($owner:String!,$repo:String!,$number:Int!,$cursor:String){repository(owner:$owner,name:$repo){pullRequest(number:$number){reviewThreads(first:100,after:$cursor){nodes{id isResolved isOutdated comments(first:1){nodes{url path line body}}}pageInfo{hasNextPage endCursor}}}}}'''
    threads, cursor = [], None
    for _ in range(30):
        owner, name = repo.split('/')
        d = github('api', 'graphql', payload={'query': query, 'variables': {'owner': owner, 'repo': name, 'number': number, 'cursor': cursor}})
        page = d['data']['repository']['pullRequest']['reviewThreads']
        threads += page['nodes']
        if not page['pageInfo']['hasNextPage']:
            break
        cursor = page['pageInfo']['endCursor']
    else:
        raise ValueError('Incomplete review thread inventory')
    latest = api(f'repos/{repo}/pulls/{number}')
    if (latest['head']['sha'], latest['base']['sha'], latest['changed_files']) != (pr['head']['sha'], pr['base']['sha'], len(files)):
        raise ValueError('PR changed during inspection; inspect again')
    return {'repo': repo, 'number': number, 'url': pr['html_url'], 'state': pr['state'], 'draft': pr['draft'],
            'head_sha': pr['head']['sha'], 'base_sha': pr['base']['sha'], 'base_branch': pr['base']['ref'],
            'author': pr['user']['login'], 'head_repo': (pr['head'].get('repo') or {}).get('full_name'),
            'classification': classify(files, rules), 'files': files, 'reviews': reviews,
            'comments': comments, 'threads': threads}


def overview(s):
    c = s['classification']
    lines = ['<!-- nordic-pr-overview -->', '## Delivery overview', '',
             f"Reviewed revision: `{s['head_sha']}` → `{s['base_branch']}`", '',
             f"Scope: {c['files']} files, {c['changed_lines']} added/deleted lines.",
             f"Owning units: {', '.join(c['units']) or 'unassigned'}.",
             f"Review roles: {', '.join(c['review_roles']) or 'technical_lead, qa'}.",
             f"Merge lane: **{c['merge_lane']}**. Human decision: **{'required for scope/permissions' if c['human_decision'] else 'not required by this scope classification'}**.", '',
             '| Reviewer focus | Expected evidence / developer response |', '| --- | --- |',
             '| Scope and architecture | Check the actual diff and stated feature/story; identify owned changes. |',
             '| QA | Inspect CI results and missing integration/visual checks; a green unit suite is not feature acceptance. |',
             '| Security / capabilities | Inspect credential paths, tool boundaries and workflow permissions where changed. |',
             '| Developer follow-up | Reply in each finding thread with fix commit and actual test evidence. Reviewer resolves after recheck. |', '',
             f"Unresolved inline threads: {sum(not t['isResolved'] for t in s['threads'])}. New commits invalidate approvals of older revisions.", '',
             'Use Files changed for inline findings, Conversation for decisions and Checks for CI. '
             'Role-labelled evidence uses one configured GitHub account. Local saved-agent review jobs, rather than separate GitHub identities, govern delegated merges. Planning critiques are not code approvals.']
    return '\n'.join(lines)


def publish_overview(number):
    s = snapshot(number); path = f"repos/{s['repo']}/issues/{number}/comments"; body = overview(s)
    actor = api('user')['login']
    matches = [c for c in s['comments'] if '<!-- nordic-pr-overview -->' in c['body'] and c['user']['login'] == actor]
    if len(matches) > 1:
        raise ValueError('Ambiguous overview comments')
    latest = api(f"repos/{s['repo']}/pulls/{number}")
    if latest['head']['sha'] != s['head_sha']:
        raise ValueError('Head changed before publication')
    if matches:
        result = api(f"repos/{s['repo']}/issues/comments/{matches[0]['id']}", {'body': body}, 'PATCH')
    else:
        result = api(path, {'body': body}, 'POST')
    return {'url': result['html_url'], 'head_sha': s['head_sha'], 'classification': s['classification']}


def create(branch, title, body):
    rules = policy(); repo = rules['repo']
    if not re.fullmatch(r'(codex|agent)/[A-Za-z0-9][A-Za-z0-9._/-]{0,150}', branch) or '..' in branch or '//' in branch or branch.endswith('/'):
        raise ValueError('Use an agent/ or codex/ feature branch')
    if not title.strip() or len(title) > 180 or not body.strip() or len(body) > 20000 or SECRET_PATTERN.search(title + body):
        raise ValueError('Invalid PR title/body')
    # Only an already-pushed branch in the configured repo; no local git/shell access.
    api(f'repos/{repo}/git/ref/heads/{branch}')
    existing = api(f"repos/{repo}/pulls?state=open&head={repo.split('/')[0]}:{branch}&base={rules['base_branch']}")
    if len(existing) > 1:
        raise ValueError('Ambiguous existing PR')
    result = existing[0] if existing else api(f'repos/{repo}/pulls', {'head': branch, 'base': rules['base_branch'], 'title': title, 'body': body, 'draft': True}, 'POST')
    return {'url': result['html_url'], 'number': result['number'], 'reused': bool(existing), 'draft': result['draft']}


def publish_planning_review(number, job_id):
    # Existing saved roles produce planning handovers, not code-approval certificates.
    from .job_store import JobStore
    import uuid
    jid = str(uuid.UUID(job_id)); store = JobStore(ROOT / 'runs/control')
    try: job = store.get(jid)
    finally: store.close()
    role = job['request'].get('target_role')
    if job['request']['operation'] != 'run_agent' or job['status'] != 'agent_complete' or role not in {'technical_lead', 'qa', 'security', 'devx', 'curator'}:
        raise ValueError('Use a completed reviewer-role consultation')
    s = snapshot(number)
    context = json.loads(job['request'].get('shared_context', ''))
    if any(context.get(k) != s[k] for k in ['repo', 'number', 'head_sha']):
        raise ValueError('Review context does not match this repository, PR and exact head')
    key = 'single_' + role; session = job['result']['sessions'][key]
    if session['status'] != 'completed' or session['agent_id'] != job['result']['agent']['agent_id']:
        raise ValueError('Missing completed saved-agent session')
    handover = job['result']['handover']
    body = '\n'.join([f'<!-- nordic-planning-review:{jid} -->', f'## {role} · planning critique', '',
        f"Commit: `{s['head_sha']}` · Job: `{jid}` · Agent: `{session['agent_id']}`", '',
        '**COMMENT only: the current role profile does not certify code approval.**', '',
        '```json', json.dumps(handover, ensure_ascii=False, indent=2), '```'])
    actor = api('user')['login']
    match = [r for r in s['reviews'] if f'<!-- nordic-planning-review:{jid} -->' in r['body'] and r['user']['login'] == actor and r['commit_id'] == s['head_sha']]
    if match: return {'url': match[0]['html_url'], 'reused': True}
    result = api(f"repos/{s['repo']}/pulls/{number}/reviews", {'event': 'COMMENT', 'commit_id': s['head_sha'], 'body': body}, 'POST')
    return {'url': result['html_url'], 'reused': False}


def changed_lines(patch):
    line=None; result=set()
    for text in (patch or '').splitlines():
        if text.startswith('@@'):
            match=re.match(r'@@ -\d+(?:,\d+)? \+(\d+)',text)
            line=int(match.group(1)) if match else None
        elif line is not None:
            if text.startswith('+'): result.add(line);line+=1
            elif text.startswith(' '): line+=1
    return result


def publish_local_review(number, job_id):
    from .job_store import JobStore
    from .pr_review import LocalPRReview
    import uuid
    jid=str(uuid.UUID(job_id));store=JobStore(ROOT/'runs/control')
    try: job=store.get(jid)
    finally: store.close()
    if job['request']['operation']=='run_agent': return publish_planning_review(number,jid)
    if job['request']['operation']!='review_pr' or job['status']!='pr_review_complete': raise ValueError('Use a completed local PR review job')
    s=snapshot(number); review=LocalPRReview.model_validate(job['result']['review'])
    role=job['request']['target_role'];session=job['result']['sessions']['pr_review_'+role]
    if session['status']!='completed' or review.review_role!=role: raise ValueError('Missing completed role session')
    if any(getattr(review,k)!=s[k] for k in ['repo','number','head_sha','base_sha']) or review.diff_sha256!=review_digest(s): raise ValueError('Stale review; review the new revision')
    marker=f'<!-- nordic-code-review:{jid} -->';actor=api('user')['login']
    matches=[r for r in s['reviews'] if marker in r['body'] and r['user']['login']==actor and r['commit_id']==s['head_sha']]
    if matches: return {'url':matches[0]['html_url'],'reused':True}
    body='\n'.join([marker,f'## Local {role} review · {review.verdict}',f"Commit: `{s['head_sha']}` · Job: `{jid}` · Session: `{session['session_id']}`",'',
         review.summary,'','Local role decision, published through the shared GitHub account as COMMENT. No separate GitHub identity or native approval is implied.','',
         '```json',json.dumps(review.model_dump(),ensure_ascii=False,indent=2),'```'])
    patches={f['filename']:f.get('patch','') for f in s['files']};comments=[]
    for finding in review.findings:
        if finding.line and finding.line in changed_lines(patches.get(finding.path,'')):
            comments.append({'path':finding.path,'line':finding.line,'side':'RIGHT','body':f'[{finding.severity}] {finding.problem}\n\nRequested change: {finding.requested_change}\n\nValidation: {finding.validation}\n\nLocal reviewer role: {role}; job {jid}.'})
    result=api(f"repos/{s['repo']}/pulls/{number}/reviews",{'event':'COMMENT','commit_id':s['head_sha'],'body':body,'comments':comments},'POST')
    return {'url':result['html_url'],'reused':False,'inline_findings':len(comments),'local_verdict':review.verdict}


def review_digest(s):
    import hashlib
    material = {'repo':s['repo'],'number':s['number'],'head_sha':s['head_sha'],'base_sha':s['base_sha'],
                'files': [{k:f.get(k) for k in ['filename','previous_filename','status','additions','deletions','patch']} for f in s['files']]}
    return hashlib.sha256(json.dumps(material,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def merge_gate(s, checks, local_jobs, rules=None):
    rules = rules or policy(); reasons = []
    if s['classification']['merge_lane'] != 'small_documentation': reasons.append('Outside the delegated small-documentation lane')
    if s['state'] != 'open' or s['draft']: reasons.append('PR must be open and ready')
    if s['repo'] != rules['repo'] or s['head_repo'] != rules['repo'] or s['base_branch'] != rules['base_branch']: reasons.append('Unexpected repository/base')
    if any(not t['isResolved'] for t in s['threads']): reasons.append('Unresolved review threads')
    latest = {}
    for r in s['reviews']:
        if r['state'] in {'CHANGES_REQUESTED','DISMISSED'} or (r['state']=='APPROVED' and r.get('commit_id')==s['head_sha']): latest[r['user']['login']] = r
    if any(r['state'] == 'CHANGES_REQUESTED' for r in latest.values()): reasons.append('Outstanding changes requested')
    approved = set()
    from .workflow import load_config
    from .pr_review import LocalPRReview, PROFILE
    from .workflow import instructions_for
    import hashlib
    config=load_config()
    for job in local_jobs:
        try:
            role=job['request']['target_role']; result=job['result']; session=result['sessions']['pr_review_'+role]
            review=LocalPRReview.model_validate(result['review'])
            if job['status'] != 'pr_review_complete' or job['request']['operation'] != 'review_pr': continue
            if session['status'] != 'completed' or session['agent_id'] != config['roles'][role]['platform_agent_id']: continue
            if session.get('observed_turn_status') != 'completed' or session.get('handover') != review.model_dump(): continue
            if session.get('execution_profile_sha256') != hashlib.sha256(PROFILE.format(role_name=config['roles'][role]['name']).encode()).hexdigest() or session.get('output_schema') != 'LocalPRReview': continue
            if session.get('instruction_sha256') != hashlib.sha256(instructions_for(role,config).encode()).hexdigest(): continue
            if any(getattr(review,k) != s[k] for k in ['repo','number','head_sha','base_sha']): continue
            if review.diff_sha256 != review_digest(s) or review.review_role != role: continue
            if review.verdict != 'approve': reasons.append('Local reviewer requested changes or human input'); continue
            approved.add(role)
        except (KeyError,ValueError,TypeError):
            continue
    if not set(rules['required_review_roles']).issubset(approved): reasons.append('Missing local role approval for the exact head, base and diff')
    if not checks or any(c['bucket'] != 'pass' for c in checks): reasons.append('All reported checks must pass')
    if not any(c['name'] == rules['required_check'] and c['bucket'] == 'pass' and c.get('workflow') == rules['required_check_workflow_name'] for c in checks): reasons.append('Required trusted workflow check missing')
    return {'allowed': not reasons, 'reasons': reasons, 'head_sha': s['head_sha'], 'base_sha': s['base_sha'], 'approving_roles': sorted(approved)}


def merge_small(number, job_ids, apply=False):
    from .job_store import JobStore
    import uuid
    store=JobStore(ROOT/'runs/control')
    try: jobs=[store.get(str(uuid.UUID(jid))) for jid in job_ids]
    finally: store.close()
    s = snapshot(number); rules = policy()
    checks = github('pr', 'checks', str(number), '--repo', rules['repo'], '--json', 'name,bucket,workflow', allowed_codes=(0,1,8))
    gate = merge_gate(s, checks, jobs)
    if not apply or not gate['allowed']: return gate
    latest = snapshot(number)
    if (latest['head_sha'],latest['base_sha']) != (s['head_sha'],s['base_sha']): raise ValueError('PR changed before merge')
    checks = github('pr', 'checks', str(number), '--repo', rules['repo'], '--json', 'name,bucket,workflow', allowed_codes=(0,1,8))
    if not merge_gate(latest, checks, jobs)['allowed']: raise ValueError('Review/check state changed before merge')
    # Normal server-side rules apply; exact-head check, no admin bypass or branch deletion.
    result = api(f"repos/{rules['repo']}/pulls/{number}/merge", {'sha': s['head_sha'], 'merge_method': 'squash'}, 'PUT')
    return {'merged': result['merged'], 'sha': result.get('sha'), 'gate': gate,
            'rollback': 'Revert this squash commit on a new branch and submit a PR; external API effects require explicit compensation.'}


def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='action',required=True)
    for action in ['inspect','overview','review','merge-small']:
        q=sub.add_parser(action);q.add_argument('number',type=int)
        if action in {'overview','review','merge-small'}: q.add_argument('--apply',action='store_true')
        if action=='review': q.add_argument('--job-id',required=True)
        if action=='merge-small': q.add_argument('--review-job',action='append',default=[])
    q=sub.add_parser('create');q.add_argument('--branch',required=True);q.add_argument('--title',required=True);q.add_argument('--body-file',required=True);q.add_argument('--apply',action='store_true')
    args=p.parse_args()
    try:
        if args.action=='inspect': result=snapshot(args.number)
        elif args.action=='overview': result=publish_overview(args.number) if args.apply else {'body':overview(snapshot(args.number)),'remote_writes':0}
        elif args.action=='review': result=publish_local_review(args.number,args.job_id) if args.apply else {'operation':'publish_planning_review','pr':args.number,'job_id':args.job_id,'remote_writes':0}
        elif args.action=='merge-small': result=merge_small(args.number,args.review_job,args.apply)
        else:
            body=(ROOT/args.body_file).read_text()
            result=create(args.branch,args.title,body) if args.apply else {'branch':args.branch,'title':args.title,'body':body,'remote_writes':0}
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,KeyError,RuntimeError,subprocess.TimeoutExpired) as exc:
        p.exit(1,str(exc)+'\n')


if __name__=='__main__': main()
