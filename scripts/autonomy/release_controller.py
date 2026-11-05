#!/usr/bin/env python3
"""Read-only release planning and explicitly guarded exact-candidate GitHub transitions."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Callable

try:
    from . import orchestrator, runner
except ImportError:
    import orchestrator
    import runner

SHA_RE = re.compile(r'^[0-9a-f]{40}$')
REPOSITORY_RE = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
ID_RE = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_-]*$')
PR_FIELDS = 'number,headRefOid,headRefName,baseRefName,state,isDraft,mergeStateStatus,statusCheckRollup,mergedAt,mergeCommit'
MAX_PAGES = 100
Command = Callable[[list[str]], subprocess.CompletedProcess]


def _string(value: Any, name: str) -> str:
    if (not isinstance(value, str) or not value.strip() or value != value.strip()
            or value.startswith('-') or any(unicodedata.category(c).startswith('C') for c in value)):
        raise ValueError(f'{name} must be nonempty, without controls or option prefixes')
    return value


def _branch(value: Any, name: str) -> str:
    _string(value, name)
    # Mirror git check-ref-format --branch without a process in the pure planner.
    if (value in {'@', 'HEAD'} or value.startswith('/') or value.endswith(('/', '.'))
            or any(x in value for x in ('..', '@{', '//'))
            or any(c in value for c in ' ~^:?*[\\')
            or any(part.startswith('.') or part.endswith('.lock') for part in value.split('/'))):
        raise ValueError(f'{name} is not a valid branch ref')
    return value


@dataclass(frozen=True)
class ReleaseContext:
    repository: str
    base_branch: str
    head_branch: str
    pr_number: int
    issue_number: int
    project_owner: str
    project_number: int
    project_id: str
    project_item_id: str
    status_field_id: str
    review_option_id: str
    done_option_id: str
    dependency_field_id: str

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name in {'pr_number', 'issue_number', 'project_number'}:
                if type(value) is not int or value <= 0:
                    raise ValueError(f'{field.name} must be a positive integer')
            else:
                _string(value, field.name)
        if not REPOSITORY_RE.fullmatch(self.repository):
            raise ValueError('repository must be OWNER/REPO')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*', self.project_owner):
            raise ValueError('project_owner must be a GitHub login')
        for name in ('project_id', 'project_item_id', 'status_field_id',
                     'review_option_id', 'done_option_id', 'dependency_field_id'):
            if not ID_RE.fullmatch(getattr(self, name)):
                raise ValueError(f'{name} must be a GraphQL/option identifier')
        if self.status_field_id == self.dependency_field_id or self.review_option_id == self.done_option_id:
            raise ValueError('tracking fields and status options must be distinct')
        _branch(self.base_branch, 'base_branch')
        _branch(self.head_branch, 'head_branch')
        if self.head_branch == self.base_branch:
            raise ValueError('head and base branches must differ')

    @classmethod
    def from_dict(cls, value: Any) -> ReleaseContext:
        if not isinstance(value, dict) or set(value) != {f.name for f in fields(cls)}:
            raise ValueError('context must be an object with exactly the required fields')
        return cls(**value)


def validate_release_inputs(manifest, policy, registry, current_head_sha):
    failures = []
    sha = manifest.get('implementation_sha')
    if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
        failures.append('implementation_sha must be a 40-character lowercase SHA')
    elif sha != current_head_sha:
        failures.append('implementation SHA does not match checked-out HEAD')
    if manifest.get('decision') != 'pass':
        failures.append('run decision is not pass')
    repository = manifest.get('repository')
    if not isinstance(repository, str) or not REPOSITORY_RE.fullmatch(repository):
        failures.append('repository must be OWNER/REPO')
    autonomy = policy.get('autonomy', {})
    target = manifest.get('deployment_target', 'none')
    if target == 'production':
        failures.append('production deployment is disabled by policy')
    if target not in ['none', *autonomy.get('allowed_deployment_targets', [])]:
        failures.append('deployment target is not allowed by policy')
    authorities = [a for a in registry.get('agents', []) if isinstance(a, dict) and a.get('can_merge') is True]
    if len(authorities) != 1 or authorities[0].get('name') != 'autodata-release-agent':
        failures.append('registry must designate exactly autodata-release-agent as merge authority')
    return failures


def _digest(manifest):
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode('utf-8')).hexdigest()


def _edit(context, field_id, flag, value):
    return ['gh', 'project', 'item-edit', '--id', context.project_item_id,
            '--project-id', context.project_id, '--field-id', field_id, flag, value]


def build_release_plan(manifest: dict, context: ReleaseContext, *, repair_tracking=False) -> dict:
    """Pure command proposal. The executor independently rebuilds it before use."""
    if not isinstance(context, ReleaseContext):
        raise ValueError('a complete ReleaseContext is required')
    if manifest.get('repository') != context.repository:
        raise ValueError('context repository differs from manifest')
    sha = manifest.get('implementation_sha')
    if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
        raise ValueError('invalid implementation SHA')
    for key in ('run_id', 'task_id'):
        _string(manifest.get(key), key)
    digest = _digest(manifest)
    text = (f'Repository: {context.repository}; Issue: {context.issue_number}; '
            f'Task: {manifest["task_id"]}; Run: {manifest["run_id"]}; '
            f'Candidate: {sha}; Evidence: sha256:{digest}')
    evidence_update = _edit(context, context.dependency_field_id, '--text', text)
    done_update = _edit(context, context.status_field_id, '--single-select-option-id', context.done_option_id)
    return dict(repository=context.repository, implementation_sha=sha, repair_tracking=repair_tracking,
        context=asdict(context), manifest=copy.deepcopy(manifest), evidence_sha256=digest,
        evidence_text=text,
        before_merge=[] if repair_tracking else [
            _edit(context, context.status_field_id, '--single-select-option-id', context.review_option_id), evidence_update],
        request_merge=[] if repair_tracking else [['gh', 'pr', 'merge', str(context.pr_number), '--repo', context.repository,
                        '--squash', '--match-head-commit', sha]],
        after_merge=[evidence_update, done_update] if repair_tracking else [done_update])


def build_pr_proposal(manifest, head_branch, body_file, base_branch='master'):
    _branch(head_branch, 'head_branch')
    _branch(base_branch, 'base_branch')
    _string(body_file, 'body_file')
    if not REPOSITORY_RE.fullmatch(manifest.get('repository', '')):
        raise ValueError('repository must be OWNER/REPO')
    _string(manifest.get('task_id'), 'task_id')
    return ['gh', 'pr', 'create', '--repo', manifest['repository'], '--base', base_branch,
            '--head', head_branch, '--title', f'AutoData: {manifest["task_id"]}', '--body-file', body_file]


def _run(argv):
    return subprocess.run(argv, text=True, capture_output=True, check=False, timeout=60)


class ReleaseBlocked(ValueError):
    pass


def _read(argv, run_command, *, array=False):
    try:
        result = run_command(argv)
    except (OSError, subprocess.SubprocessError):
        raise ReleaseBlocked(f'{" ".join(argv[:3])} discovery unavailable') from None
    if result.returncode != 0:
        # Never include raw stderr/stdout: even errors can contain tokens or source data.
        raise ReleaseBlocked(f'{" ".join(argv[:3])} discovery failed (exit {result.returncode})')
    try:
        value = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise ReleaseBlocked(f'{" ".join(argv[:3])} discovery returned invalid JSON') from None
    if not isinstance(value, list if array else dict) or (not array and value.get('errors')):
        raise ReleaseBlocked(f'{" ".join(argv[:3])} discovery returned invalid data/errors')
    return value


def _pr_argv(context):
    return ['gh', 'pr', 'view', str(context.pr_number), '--repo', context.repository, '--json', PR_FIELDS]


def _pr_identity_errors(pr, context, sha):
    if (type(pr.get('number')) is not int or pr.get('number') != context.pr_number
            or pr.get('headRefOid') != sha or pr.get('headRefName') != context.head_branch
            or pr.get('baseRefName') != context.base_branch):
        return ['PR candidate, identity or branches differ']
    return []


def _pr_errors(pr, context, sha, repair=False):
    failures = _pr_identity_errors(pr, context, sha)
    if repair:
        commit = pr.get('mergeCommit')
        if (pr.get('state') != 'MERGED' or not isinstance(pr.get('mergedAt'), str)
                or not pr['mergedAt'] or not isinstance(commit, dict)
                or not isinstance(commit.get('oid'), str) or not SHA_RE.fullmatch(commit['oid'])):
            failures.append('repair requires confirmed MERGED metadata')
    else:
        if pr.get('state') != 'OPEN' or pr.get('isDraft') is not False:
            failures.append('normal merge requires an OPEN non-draft PR')
        if pr.get('mergeStateStatus') not in {'CLEAN', 'HAS_HOOKS'}:
            failures.append('PR merge/check state is not ready')
        checks = pr.get('statusCheckRollup')
        if not isinstance(checks, list) or not checks:
            failures.append('PR successful checks are unavailable')
        else:
            for check in checks:
                if not isinstance(check, dict) or not (
                    (check.get('__typename') == 'CheckRun' and check.get('status') == 'COMPLETED'
                     and check.get('conclusion') == 'SUCCESS')
                    or (check.get('__typename') == 'StatusContext' and check.get('state') == 'SUCCESS')
                ):
                    failures.append('PR has unsuccessful, pending or unknown checks')
                    break
    return failures


ITEMS_QUERY = '''query($project:ID!,$cursor:String){node(id:$project){... on ProjectV2{
 id fields(first:100){totalCount nodes{... on ProjectV2Field{id dataType}
 ... on ProjectV2SingleSelectField{id dataType} ... on ProjectV2IterationField{id dataType}}
 pageInfo{hasNextPage}}
 items(first:100,after:$cursor){nodes{id content{__typename ... on Issue{number url repository{nameWithOwner}}}
 fieldValues(first:100){totalCount nodes{__typename ... on ProjectV2ItemFieldTextValue{text field{... on ProjectV2Field{id}}}
 ... on ProjectV2ItemFieldSingleSelectValue{optionId field{... on ProjectV2SingleSelectField{id}}}}
 pageInfo{hasNextPage endCursor}}} pageInfo{hasNextPage endCursor}}}}}'''


def _project_item(context, run_command):
    cursor = None
    seen_cursors = set()
    matches = []
    seen_items = set()
    for _ in range(MAX_PAGES):
        argv = ['gh', 'api', 'graphql', '-f', 'query=' + ITEMS_QUERY, '-f', 'project=' + context.project_id]
        if cursor is not None:
            argv += ['-f', 'cursor=' + cursor]
        result = _read(argv, run_command)
        node = result['data']['node']
        if node['id'] != context.project_id:
            raise ReleaseBlocked('Project item enumeration belongs to another project')
        inventory = node['fields']
        if (inventory['pageInfo']['hasNextPage'] is not False
                or type(inventory['totalCount']) is not int
                or inventory['totalCount'] != len(inventory['nodes'])
                or len(inventory['nodes']) > 100):
            raise ReleaseBlocked('Project field type enumeration is incomplete')
        types = {field['id']: field['dataType'] for field in inventory['nodes']}
        if (len(types) != len(inventory['nodes'])
                or types.get(context.status_field_id) != 'SINGLE_SELECT'
                or types.get(context.dependency_field_id) != 'TEXT'):
            raise ReleaseBlocked('Project field data types differ')
        page = node['items']
        if not isinstance(page['nodes'], list) or len(page['nodes']) > 100:
            raise ReleaseBlocked('invalid Project item page')
        for item in page['nodes']:
            if item['id'] in seen_items:
                raise ReleaseBlocked('duplicate Project item during pagination')
            seen_items.add(item['id'])
            if item['id'] == context.project_item_id:
                matches.append(item)
        info = page['pageInfo']
        if info['hasNextPage'] is False:
            break
        cursor = info['endCursor']
        if info['hasNextPage'] is not True or not isinstance(cursor, str) or not cursor or cursor in seen_cursors:
            raise ReleaseBlocked('Project item pagination cannot prove completion')
        seen_cursors.add(cursor)
    else:
        raise ReleaseBlocked('Project item pagination exceeded safe bound')
    if len(matches) != 1:
        raise ReleaseBlocked('Project item not found in complete enumeration')
    item = matches[0]
    content = item['content']
    expected = f'https://github.com/{context.repository}/issues/{context.issue_number}'
    if (content['__typename'] != 'Issue' or content['number'] != context.issue_number
            or content['url'] != expected or content['repository']['nameWithOwner'] != context.repository):
        raise ReleaseBlocked('Project item does not reference expected repository Issue')
    values = item['fieldValues']
    if (values['pageInfo']['hasNextPage'] is not False or type(values['totalCount']) is not int
            or values['totalCount'] != len(values['nodes'])):
        raise ReleaseBlocked('Project item field enumeration is incomplete')
    result = {}
    required_types = {
        context.status_field_id: 'ProjectV2ItemFieldSingleSelectValue',
        context.dependency_field_id: 'ProjectV2ItemFieldTextValue',
    }
    for value in values['nodes']:
        field_id = value.get('field', {}).get('id')
        # Repository, Labels and other union variants expose only __typename in
        # this query. They are still counted for enumeration completeness, but
        # are unrelated to the two fields this controller may edit.
        if field_id not in required_types:
            continue
        if value.get('__typename') != required_types[field_id]:
            raise ReleaseBlocked('required Project item field has wrong value type')
        if field_id in result:
            raise ReleaseBlocked('duplicate Project item field')
        result[field_id] = value
    return result


def validate_live_context(context, implementation_sha, run_command, *,
                          planning_record, evidence_sha256, evidence_text, repair_tracking=False):
    """Read-only discovery. Missing/unknown/unavailable data always blocks."""
    confirmed_pr = None
    try:
        pr = _read(_pr_argv(context), run_command)
        errors = _pr_errors(pr, context, implementation_sha, repair_tracking)
        if errors:
            return errors, {}
        if repair_tracking:
            confirmed_pr = pr
        if not repair_tracking:
            required = _read(['gh', 'pr', 'checks', str(context.pr_number), '--repo', context.repository,
                              '--required', '--json', 'name,state,bucket'], run_command, array=True)
            if (not required or any(not isinstance(check, dict) or not check.get('name')
                                    or check.get('bucket') != 'pass' for check in required)):
                raise ReleaseBlocked('required PR checks are absent, pending or unsuccessful')
        project = _read(['gh', 'project', 'view', str(context.project_number), '--owner',
                         context.project_owner, '--format', 'json'], run_command)
        if (project.get('id') != context.project_id or project.get('number') != context.project_number
                or project.get('closed') is not False):
            raise ReleaseBlocked('Project identity/state differs')
        fields_result = _read(['gh', 'project', 'field-list', str(context.project_number), '--owner',
                               context.project_owner, '--limit', '100', '--format', 'json'], run_command)
        inventory = fields_result['fields']
        if (not isinstance(inventory, list) or type(fields_result.get('totalCount')) is not int
                or fields_result['totalCount'] != len(inventory) or len(inventory) > 100):
            raise ReleaseBlocked('Project field enumeration is incomplete')
        by_id = {f['id']: f for f in inventory}
        if len(by_id) != len(inventory):
            raise ReleaseBlocked('duplicate Project field identity')
        status = by_id[context.status_field_id]
        dependency = by_id[context.dependency_field_id]
        options = {o['id']: o['name'] for o in status['options']}
        if (status['name'] != 'Status' or status['type'] != 'ProjectV2SingleSelectField'
                or len(options) != len(status['options'])
                or options.get(context.review_option_id) != 'Review'
                or options.get(context.done_option_id) != 'Done'
                or dependency['type'] != 'ProjectV2Field'):
            raise ReleaseBlocked('Project field types or named status options differ')
        item = _project_item(context, run_command)
        current_status = item.get(context.status_field_id, {}).get('optionId')
        current_text = item.get(context.dependency_field_id, {}).get('text')
        if current_status not in options:
            raise ReleaseBlocked('Project item status is missing/unknown')
        if not repair_tracking and current_text != evidence_text:
            raise ReleaseBlocked('Project item candidate/evidence differs')
        if not repair_tracking and current_status == context.done_option_id:
            raise ReleaseBlocked('OPEN candidate Project item is already Done')
        issue = _read(['gh', 'issue', 'view', str(context.issue_number), '--repo', context.repository,
                       '--json', 'number,url,state,body,labels'], run_command)
        if (issue.get('number') != context.issue_number or issue.get('url') != planning_record['issue_ref']
                or (not repair_tracking and issue.get('state') != 'OPEN')
                or issue.get('state') not in {'OPEN', 'CLOSED'}):
            raise ReleaseBlocked('Issue identity/state differs from planning record')
        if any(label['name'].casefold() in {'blocked', 'blocker'} for label in issue['labels']):
            raise ReleaseBlocked('Issue has unresolved blocker label')
        matches = re.findall(r'<!-- autodata-release\s+(.*?)\s*-->', issue['body'], re.DOTALL)
        if len(matches) != 1:
            raise ReleaseBlocked('Issue must retain exactly one autodata-release tracking record')
        tracking = json.loads(matches[0])
        expected = {**planning_record, 'candidate_sha': implementation_sha,
                    'evidence_sha256': evidence_sha256, 'unresolved_blockers': []}
        if tracking != expected:
            raise ReleaseBlocked('Issue goal, plan, documents, todo, candidate/evidence or blockers differ')
        project_ref = planning_record['project_ref']
        if (project_ref not in {f'https://github.com/{kind}/{context.project_owner}/projects/{context.project_number}'
                                for kind in ('users', 'orgs')}
                or planning_record['issue_ref'] != f'https://github.com/{context.repository}/issues/{context.issue_number}'
                or planning_record['status'] != 'synchronized'):
            raise ReleaseBlocked('local planning record differs from release context')
        return [], dict(pr=pr, status=current_status, evidence_text=current_text)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        error = sys.exc_info()[1]
        return [str(error) if isinstance(error, ReleaseBlocked) else 'remote discovery returned malformed data'], (
            {'pr': confirmed_pr} if confirmed_pr is not None else {})


def _receipt(plan, pr):
    return dict(repository=plan['repository'], pr_number=plan['context']['pr_number'],
                context=plan['context'], candidate_sha=plan['implementation_sha'],
                evidence_sha256=plan['evidence_sha256'], base_branch=plan['context']['base_branch'],
                merge_commit=pr['mergeCommit']['oid'], merged_at=pr['mergedAt'])


def _save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def execute_release_plan(plan, run_command, *, trusted, evidence_root, state_root,
                         repair_tracking=False, execute=True):
    """Replay immutable evidence, discover live state, then run a guarded transition.

    trusted is resolved by runner.load_trusted_inputs from an independently pinned
    base/task, never from a candidate-supplied policy file or previous pass receipt.
    """
    outcome = _execute_release_plan(plan, run_command, trusted=trusted,
        evidence_root=evidence_root, state_root=state_root,
        repair_tracking=repair_tracking, execute=execute)
    if execute and os.environ.get('AUTODATA_RELEASE_AUTOMATION') == 'enabled':
        try:
            _save(Path(state_root) / 'release-outcome.json', outcome)
        except OSError:
            outcome['failures'].append('could not persist release outcome')
            outcome['decision'] = 'merged_tracking_failed' if outcome.get('receipt') else 'blocked'
            if outcome.get('receipt'):
                outcome['retry'] = '--repair-tracking'
    return outcome


def _execute_release_plan(plan, run_command, *, trusted, evidence_root, state_root,
                          repair_tracking, execute):
    result = dict(decision='blocked', failures=[], results=[])
    receipt = None
    phase = 'preflight'
    state_root = Path(state_root)
    receipt_path = state_root / 'release-receipt.json'
    operation_path = state_root / 'release-operation.json'
    command = run_command

    def recorded_command(argv):
        try:
            completed = command(argv)
        except (OSError, subprocess.SubprocessError):
            if execute:
                _event(state_root, phase, argv, None)
            raise
        if execute:
            _event(state_root, phase, argv, completed.returncode)
        return completed

    run_command = recorded_command
    try:
        plan = copy.deepcopy(plan)
        trusted = copy.deepcopy(trusted)
        context = ReleaseContext.from_dict(plan['context'])
        manifest = plan['manifest']
        if plan != build_release_plan(manifest, context, repair_tracking=repair_tracking):
            raise ReleaseBlocked('release plan differs from rebuilt structured commands')
        if execute and os.environ.get('AUTODATA_RELEASE_AUTOMATION') != 'enabled':
            raise ReleaseBlocked('set AUTODATA_RELEASE_AUTOMATION=enabled in the isolated release job')
        validation = orchestrator.validate_evidence_bundle(manifest, trusted, Path(evidence_root))
        errors = validation['failures'][:]
        errors += validate_release_inputs(manifest, trusted['policy'], trusted['registry'], manifest['implementation_sha'])
        if manifest['repository'] != trusted['task']['repository']:
            errors.append('repository differs from frozen task')
        authority = trusted['policy']['autonomy']
        if authority.get('allow_pull_request_merge') is not True and not repair_tracking:
            errors.append('policy denies pull request merge')
        if authority.get('allow_github_project_updates') is not True:
            errors.append('policy denies Project updates')
        if errors or validation.get('passed') is not True:
            result['failures'] = errors or ['bundle replay did not pass']
            return result
        retained = _load_json(receipt_path) if receipt_path.exists() else None
        if not repair_tracking:
            if retained is not None:
                raise ReleaseBlocked('retained merge receipt requires --repair-tracking')
            if operation_path.exists():
                previous = _load_json(operation_path)
                if (previous.get('context') != asdict(context)
                        or previous.get('candidate_sha') != plan['implementation_sha']
                        or previous.get('evidence_sha256') != plan['evidence_sha256']):
                    raise ReleaseBlocked('retained operation belongs to another context/candidate/evidence bundle')
                if previous.get('decision') in {'merge_requested', 'merge_pending'}:
                    # An existing request is observed, never resubmitted. Queue
                    # checks may now be pending or blocked without invalidating
                    # the request that already passed the initial preflight.
                    phase = 'pending_merge'
                    pr = _read(_pr_argv(context), run_command)
                    errors = _pr_identity_errors(pr, context, plan['implementation_sha'])
                    if errors:
                        raise ReleaseBlocked('; '.join(errors))
                    if pr.get('state') != 'OPEN':
                        raise ReleaseBlocked('retained merge request is no longer OPEN; inspect remote state or use --repair-tracking after MERGED')
                    return {**result, 'decision': 'merge_pending', 'failures': []}
        errors, remote = validate_live_context(context, plan['implementation_sha'], run_command,
            planning_record=trusted['task']['pre_implementation'], evidence_sha256=plan['evidence_sha256'],
            evidence_text=plan['evidence_text'], repair_tracking=repair_tracking)
        if errors:
            result['failures'] = errors
            # Exact MERGED metadata is already confirmed even when a later
            # tracking read fails. Reconstruct a missing receipt rather than
            # reporting the merged code as unconfirmed. Read-only callers get
            # the same honest state without creating any local files.
            if repair_tracking and remote.get('pr'):
                confirmed = _receipt(plan, remote['pr'])
                retained = _load_json(receipt_path) if receipt_path.exists() else None
                if retained is not None and retained != confirmed:
                    raise ReleaseBlocked('retained merge receipt differs from remote identity/target/merge')
                receipt = confirmed
                if execute:
                    _save(receipt_path, receipt)
                result.update(decision='merged_tracking_failed', receipt=receipt,
                              retry='--repair-tracking')
            return result
        if repair_tracking:
            receipt = _receipt(plan, remote['pr'])
            if retained is not None and retained != receipt:
                receipt = None
                raise ReleaseBlocked('retained merge receipt differs from remote identity/target/merge')
        if not execute:
            return {**result, 'decision': 'validated', 'plan': plan, 'measurements': validation['measurements']}
        if repair_tracking:
            _save(receipt_path, receipt)  # Survives another tracking failure or process death.
            phase = 'repair_tracking'
            mutations = []
            if remote['evidence_text'] != plan['evidence_text']:
                mutations.append(plan['after_merge'][0])
            if remote['status'] != context.done_option_id:
                mutations.append(plan['after_merge'][1])
        else:
            phase = 'before_merge'
            for argv in plan['before_merge']:
                _mutation(argv, phase, run_command, state_root, result)
            phase = 'head_recheck'
            pr = _read(_pr_argv(context), run_command)
            errors = _pr_errors(pr, context, plan['implementation_sha'])
            if errors:
                raise ReleaseBlocked('; '.join(errors))
            # Persist before requesting merge: interruption cannot silently reissue it.
            _save(operation_path, dict(context=asdict(context), candidate_sha=plan['implementation_sha'], evidence_sha256=plan['evidence_sha256'], decision='merge_requested'))
            phase = 'request_merge'
            merge_failed = False
            try:
                _mutation(plan['request_merge'][0], phase, run_command, state_root, result)
            except ReleaseBlocked:
                merge_failed = True
            phase = 'confirm_merge'
            pr = _read(_pr_argv(context), run_command)
            if pr.get('state') != 'MERGED':
                identity = (pr.get('headRefOid') == plan['implementation_sha']
                            and pr.get('baseRefName') == context.base_branch
                            and pr.get('headRefName') == context.head_branch and pr.get('number') == context.pr_number)
                if not identity or pr.get('state') != 'OPEN':
                    raise ReleaseBlocked('merge confirmation candidate/state differs')
                decision = 'blocked' if merge_failed else 'merge_pending'
                _save(operation_path, dict(context=asdict(context), candidate_sha=plan['implementation_sha'], evidence_sha256=plan['evidence_sha256'], decision=decision))
                return {**result, 'decision': decision, 'failures': ['merge request failed'] if merge_failed else []}
            errors = _pr_errors(pr, context, plan['implementation_sha'], repair=True)
            if errors:
                raise ReleaseBlocked('; '.join(errors))
            receipt = _receipt(plan, pr)
            phase = 'after_merge'
            _save(receipt_path, receipt)
            mutations = plan['after_merge']
        for argv in mutations:
            _mutation(argv, phase, run_command, state_root, result)
        decision = 'tracking_repaired' if repair_tracking else 'merged'
        _save(operation_path, dict(context=asdict(context), candidate_sha=plan['implementation_sha'], evidence_sha256=plan['evidence_sha256'], decision=decision))
        return {**result, 'decision': decision, 'receipt': receipt}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError):
        error = sys.exc_info()[1]
        result['failures'].append(str(error) if isinstance(error, ReleaseBlocked) else f'{phase} failed; inspect command exit evidence')
        if receipt is not None:
            result.update(decision='merged_tracking_failed', receipt=receipt, retry='--repair-tracking')
        return result


def _mutation(argv, phase, run_command, state_root, outcome):
    try:
        completed = run_command(argv)
        code = completed.returncode
    except (OSError, subprocess.SubprocessError):
        code = None
    event = dict(phase=phase, argv=argv, exit_code=code,
                 failure=None if code == 0 else 'command failed; raw output withheld')
    outcome['results'].append(event)
    if code != 0:
        raise ReleaseBlocked(f'{phase} command failed (exit {code})')


def _event(state_root, phase, argv, code):
    state_root.mkdir(parents=True, exist_ok=True)
    event = dict(phase=phase, argv=argv, exit_code=code,
                 failure=None if code == 0 else 'command failed; raw output withheld')
    with (state_root / 'release-events.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(event, sort_keys=True) + '\n')


def _load_json(path):
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('JSON input must be an object')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path.cwd())
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--evidence-root', type=Path, required=True)
    parser.add_argument('--context', type=Path)
    parser.add_argument('--trusted-base-sha')
    parser.add_argument('--task-ref')
    parser.add_argument('--head-branch')
    parser.add_argument('--base-branch', default='master')
    parser.add_argument('--body-file', type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--execute', action='store_true')
    mode.add_argument('--repair-tracking', action='store_true')
    mode.add_argument('--propose-pr', action='store_true')
    args = parser.parse_args(argv)
    try:
        manifest = _load_json(args.manifest)
        if args.propose_pr:
            if not args.head_branch or not args.body_file:
                raise ReleaseBlocked('PR proposal requires --head-branch and --body-file')
            outcome = dict(decision='proposal', argv=build_pr_proposal(manifest, args.head_branch,
                str(args.body_file), args.base_branch))
        else:
            if not args.context or not args.trusted_base_sha or not args.task_ref:
                raise ReleaseBlocked('--context, --trusted-base-sha and --task-ref are required')
            root = args.repo_root.resolve()
            if args.evidence_root.resolve().is_relative_to(root):
                raise ReleaseBlocked('release evidence/state directory must be outside the repository')
            trusted = runner.load_trusted_inputs(root, args.trusted_base_sha, args.task_ref)
            head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, text=True,
                                  capture_output=True, check=False)
            if head.returncode or head.stdout.strip() != manifest.get('implementation_sha'):
                raise ReleaseBlocked('implementation SHA does not match checked-out HEAD')
            context = ReleaseContext.from_dict(_load_json(args.context))
            for branch in (context.head_branch, context.base_branch):
                check = subprocess.run(['git', 'check-ref-format', '--branch', branch], cwd=root,
                                       text=True, capture_output=True, check=False)
                if check.returncode:
                    raise ReleaseBlocked('branch rejected by git check-ref-format --branch')
            outcome = execute_release_plan(build_release_plan(manifest, context, repair_tracking=args.repair_tracking), _run,
                trusted=trusted, evidence_root=args.evidence_root, state_root=args.evidence_root / 'release',
                repair_tracking=args.repair_tracking, execute=args.execute or args.repair_tracking)
        print(json.dumps(outcome, sort_keys=True))
        return 0 if outcome['decision'] in {'proposal', 'validated', 'merged', 'tracking_repaired', 'merge_pending'} else 20
    except (OSError, ValueError, KeyError, TypeError, runner.RunnerError):
        error = sys.exc_info()[1]
        print(json.dumps(dict(decision='blocked', failures=[str(error) if isinstance(error, ReleaseBlocked)
                                                            else 'invalid local release inputs'])))
        return 30


if __name__ == '__main__':
    sys.exit(main())
