"""Portable board preview and idempotent GitHub Projects bootstrap via the official gh CLI.

No repo creation, CI policy changes, merge or publication. Remote apply is explicit.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path
from .workflow import ROOT


def gh(*args, stdin=None):
    p = subprocess.run(['gh', *args], cwd=ROOT, capture_output=True, text=True, timeout=45, input=stdin)
    if p.returncode:
        raise RuntimeError('GitHub CLI request failed; check gh authentication and project scope')
    return json.loads(p.stdout) if p.stdout.strip() else None


def render(item):
    return '\n'.join([f"<!-- nordic-work-item:{item['id']} -->", '', item['goal'], '',
                      f"Kind: {item['kind']} · Sprint: {item['sprint']} · Priority: {item['priority']}",
                      f"Parent: {item['parent'] or 'none'}", '', 'Acceptance:',
                      *['- [ ] ' + a for a in item['acceptance']], '',
                      'Planning proposal. Completion requires actual acceptance evidence.'])


def preview(plan):
    ids = {i['id'] for i in plan['items']}
    if len(ids) != len(plan['items']) or any(i['parent'] and i['parent'] not in ids for i in plan['items']):
        raise ValueError('Invalid item identity or parent')
    return {'schema_version': plan['schema_version'], 'provider': 'github_projects', 'title': plan['title'],
            'items': [dict(i, body=render(i)) for i in plan['items']], 'fields': plan['fields'],
            'remote_writes': 0, 'views_to_configure': ['Board by Status', 'Sprint table grouped by Sprint', 'Roadmap after assigning dates'],
            'iteration_note': 'Bootstrap uses a portable Sprint text field. Configure a native GitHub Iteration field in the UI for dated sprint scheduling.'}


def apply(plan, owner, repo=None):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', owner):
        raise ValueError('Use an explicit GitHub owner login')
    if repo is not None and (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo) or repo.split('/')[0] != owner):
        raise ValueError('Use an explicit owner/repo matching the board owner')
    # Preview/validate everything before remote writes; do not accept credentials as arguments.
    packet = preview(plan)
    gh('api', 'user')
    projects = gh('project', 'list', '--owner', owner, '--format', 'json', '--limit', '100')['projects']
    matches = [p for p in projects if p['title'] == plan['title']]
    if len(matches) > 1:
        raise ValueError('Ambiguous project title; reconcile existing boards')
    project = matches[0] if matches else gh('project', 'create', '--owner', owner, '--title', plan['title'], '--format', 'json')
    number = str(project['number'])
    fields = gh('project', 'field-list', number, '--owner', owner, '--format', 'json', '--limit', '100')['fields']
    for name, spec in packet['fields'].items():
        if any(f['name'] == name for f in fields):
            continue
        args = ['project', 'field-create', number, '--owner', owner, '--name', name, '--data-type', 'SINGLE_SELECT' if isinstance(spec, list) else spec, '--format', 'json']
        if isinstance(spec, list):
            args += ['--single-select-options', ','.join(spec)]
        gh(*args)
    fields = gh('project', 'field-list', number, '--owner', owner, '--format', 'json', '--limit', '100')['fields']
    by_name = {f['name']: f for f in fields}
    listing = gh('project', 'item-list', number, '--owner', owner, '--format', 'json', '--limit', '1000')
    items = listing['items']
    if listing.get('totalCount', len(items)) > len(items):
        raise ValueError('Incomplete item inventory; refusing duplicate-prone bootstrap')
    issue_refs = {}
    if repo:
        existing_issues = gh('issue', 'list', '--repo', repo, '--state', 'all', '--limit', '1000', '--json', 'number,title,body,url')
        if len(existing_issues) >= 1000:
            raise ValueError('Issue inventory limit reached; reconcile before bootstrap')
        for item in packet['items']:
            marker = f"<!-- nordic-work-item:{item['id']} -->"
            matches = [i for i in existing_issues if marker in (i.get('body') or '')]
            if len(matches) > 1:
                raise ValueError('Duplicate issue marker')
            if matches:
                issue_refs[item['id']] = matches[0]
            else:
                issue = gh('api', f'repos/{repo}/issues', '--method', 'POST', '-f', 'title=' + item['id'] + ': ' + item['title'], '-f', 'body=' + item['body'])
                issue_refs[item['id']] = {'number': issue['number'], 'url': issue['html_url']}
    mapping = {}
    for item in packet['items']:
        marker = f"<!-- nordic-work-item:{item['id']} -->"
        found = [i for i in items if marker in i.get('content', {}).get('body', '')]
        if len(found) > 1:
            raise ValueError('Duplicate remote work-item marker; reconcile before retry')
        if found:
            remote = found[0]
        elif repo:
            remote = gh('project', 'item-add', number, '--owner', owner, '--url', issue_refs[item['id']]['url'], '--format', 'json')
        else:
            remote = gh('project', 'item-create', number, '--owner', owner, '--title', item['id'] + ': ' + item['title'], '--body', item['body'], '--format', 'json')
        rid = remote['id']; mapping[item['id']] = rid
        if found:
            continue  # The board owns edited priority/sprint/state; bootstrap never overwrites them.
        for name, value in [('Kind', item['kind']), ('Priority', item['priority']), ('Sprint', item['sprint']), ('Feature', item['parent'] or item['id'])]:
            f = by_name[name]
            args = ['project', 'item-edit', '--id', rid, '--project-id', project['id'], '--field-id', f['id']]
            if 'options' in f:
                options = [o for o in f['options'] if o['name'] == value]
                if len(options) != 1:
                    raise ValueError('Existing field options differ; do not guess an option')
                args += ['--single-select-option-id', options[0]['id']]
            else:
                args += ['--text', value]
            gh(*args)
    output = ROOT / 'config/github-project.json'
    saved = json.loads(output.read_text()) if output.exists() else {}
    if saved.get('id') != project['id']:
        saved = {}
    saved.update({'provider':'github_projects','owner':owner,'number':project['number'], 'id':project['id'],
                  'url':project.get('url'),'item_ids':mapping,'repo':repo,'issues':issue_refs})
    output.write_text(json.dumps(saved,indent=2)+'\n')
    return {'project': project, 'mapping_file': str(output), 'repository_issues_created': bool(repo),
            'native_iteration_field_configured': False, 'branch_policies_changed': False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');p.add_argument('--owner');p.add_argument('--repo');args=p.parse_args()
    plan=json.loads((ROOT/'data/github-project-plan.json').read_text())
    if args.apply and not args.owner:p.error('--apply requires --owner')
    try:print(json.dumps(apply(plan,args.owner,args.repo) if args.apply else preview(plan),indent=2,ensure_ascii=False))
    except (ValueError,RuntimeError,subprocess.TimeoutExpired) as e:p.exit(1,str(e)+'\n')


if __name__=='__main__':main()
