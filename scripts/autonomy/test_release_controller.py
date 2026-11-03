"""Deterministic controller tests. Fake GitHub commands never contact GitHub."""
import copy
import json
import os
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import release_controller as rc
import orchestrator
import test_orchestrator


CONTEXT = dict(repository='lucronn/autodata', base_branch='master',
               head_branch='codex/candidate', pr_number=12, issue_number=86,
               project_owner='portfolio-owner', project_number=8, project_id='PVT_project',
               project_item_id='PVTI_item', status_field_id='PVTSSF_status',
               review_option_id='review', done_option_id='done', dependency_field_id='PVTF_evidence')


class FakeGitHub:
    """Command boundary with actual gh JSON shapes and strict command dispatch."""
    def __init__(self, plan, record):
        self.plan = plan
        self.record = record
        self.calls = []
        self.pr = dict(number=12, headRefOid=plan['implementation_sha'],
                       headRefName='codex/candidate', baseRefName='master', state='OPEN',
                       isDraft=False, mergeStateStatus='CLEAN',
                       statusCheckRollup=[dict(__typename='CheckRun', status='COMPLETED', conclusion='SUCCESS')],
                       mergedAt=None, mergeCommit=None)
        self.tracking = dict(status='Review', evidence=plan['evidence_text'])
        self.issue = dict(number=86, url='https://github.com/lucronn/autodata/issues/86',
                          state='OPEN', labels=[], body='Résumé — проверено\n' +
                          '<!-- autodata-release\n' + json.dumps(record, ensure_ascii=False) + '\n-->')
        self.required_checks = [dict(name='required-ci', state='SUCCESS', bucket='pass')]
        self.field_type = 'TEXT'
        self.fields = dict(fields=[
            dict(id='PVTSSF_status', name='Status', type='ProjectV2SingleSelectField',
                 options=[dict(id='review', name='Review'), dict(id='done', name='Done')]),
            dict(id='PVTF_evidence', name='Dependencies', type='ProjectV2Field')], totalCount=2)
        self.fail = None
        self.queue = False
        self.stale = False
        self.pages = 1
        self.incomplete = False
        self.item_issue = None
        self.mutations = []

    def __call__(self, argv):
        self.calls.append(argv)
        if argv[:3] == ['gh', 'pr', 'view']:
            value = copy.deepcopy(self.pr)
            if self.stale and len([a for a in self.calls if a[:3] == ['gh', 'pr', 'view']]) == 2:
                value['headRefOid'] = 'f' * 40
        elif argv[:3] == ['gh', 'pr', 'checks']:
            value = self.required_checks
        elif argv[:3] == ['gh', 'issue', 'view']:
            value = self.issue
        elif argv[:3] == ['gh', 'project', 'view']:
            value = dict(id='PVT_project', number=8, closed=False)
        elif argv[:3] == ['gh', 'project', 'field-list']:
            value = self.fields
        elif argv[:3] == ['gh', 'api', 'graphql']:
            page = len([a for a in self.calls if a[:3] == ['gh', 'api', 'graphql']])
            item = dict(id='PVTI_item', content=dict(__typename='Issue', number=self.item_issue or self.issue['number'],
                        url=self.issue['url'], repository=dict(nameWithOwner='lucronn/autodata')),
                        fieldValues=dict(totalCount=2, nodes=[
                            dict(__typename='ProjectV2ItemFieldSingleSelectValue', optionId=self.tracking['status'].lower(), field=dict(id='PVTSSF_status')),
                            dict(__typename='ProjectV2ItemFieldTextValue', text=self.tracking['evidence'], field=dict(id='PVTF_evidence'))],
                            pageInfo=dict(hasNextPage=False, endCursor=None)))
            value = dict(data=dict(node=dict(id='PVT_project', fields=dict(totalCount=2,
                nodes=[dict(id='PVTSSF_status', dataType='SINGLE_SELECT'),
                       dict(id='PVTF_evidence', dataType=self.field_type)],
                pageInfo=dict(hasNextPage=False)), items=dict(
                nodes=[item] if page >= self.pages else [],
                pageInfo=dict(hasNextPage=self.incomplete or page < self.pages, endCursor='cursor' + str(page))))))
        elif argv[:3] == ['gh', 'project', 'item-edit']:
            self.mutations.append(argv)
            if self.fail == 'tracking' or (self.fail == 'evidence' and '--text' in argv) or (self.fail == 'done' and '--single-select-option-id' in argv and argv[-1] == 'done'):
                return subprocess.CompletedProcess(argv, 1, '', 'private token ghp_do_not_log')
            if '--single-select-option-id' in argv:
                self.tracking['status'] = argv[-1].title()
            else:
                self.tracking['evidence'] = argv[-1]
            value = {}
        elif argv[:3] == ['gh', 'pr', 'merge']:
            self.mutations.append(argv)
            if self.fail == 'merge':
                return subprocess.CompletedProcess(argv, 1, '', 'merge denied')
            if not self.queue:
                self.pr.update(state='MERGED', mergedAt='2026-11-03T12:00:00Z', mergeCommit=dict(oid='e' * 40))
            value = {}
        else:
            raise AssertionError('unexpected command: ' + repr(argv))
        if self.fail == 'discovery' and argv[:3] == ['gh', 'project', 'view']:
            return subprocess.CompletedProcess(argv, 1, '', 'scope denied secret')
        return subprocess.CompletedProcess(argv, 0, json.dumps(value, ensure_ascii=False), '')


class ReleaseControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory()
        code, path, cls.trusted, _ = test_orchestrator.FullChainV2Tests().run_fixture(Path(cls.fixture.name))
        if code:
            raise AssertionError(path.read_text())
        cls.manifest = json.loads(path.read_text())
        cls.bundle = path.parent
        # The fixture repository identity is part of the frozen task.
        cls.context_data = {**CONTEXT, 'repository': cls.manifest['repository']}

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        record = self.trusted['task']['pre_implementation']
        self.context = rc.ReleaseContext.from_dict({**self.context_data,
            'issue_number': int(record['issue_ref'].rsplit('/', 1)[1]),
            'project_owner': record['project_ref'].split('/')[4]})
        self.plan = rc.build_release_plan(self.manifest, self.context)
        record = self.trusted['task']['pre_implementation']
        self.remote_record = {**copy.deepcopy(record),
            'candidate_sha': self.manifest['implementation_sha'],
            'evidence_sha256': self.plan['evidence_sha256'], 'unresolved_blockers': []}
        self.fake = FakeGitHub(self.plan, self.remote_record)
        self.fake.issue['url'] = record['issue_ref']
        self.context = replace(self.context, issue_number=int(record['issue_ref'].rsplit('/', 1)[1]))
        self.plan = rc.build_release_plan(self.manifest, self.context)
        self.fake.plan = self.plan
        self.fake.issue['number'] = self.context.issue_number
        self.output = tempfile.TemporaryDirectory()
        self.addCleanup(self.output.cleanup)
        self.receipt_root = Path(self.output.name)

    def execute(self, repair=False, manifest=None):
        plan = rc.build_release_plan(manifest or self.manifest, self.context, repair_tracking=repair)
        with patch.dict(os.environ, {'AUTODATA_RELEASE_AUTOMATION': 'enabled'}):
            return rc.execute_release_plan(plan, self.fake, trusted=self.trusted,
                evidence_root=self.bundle, state_root=self.receipt_root, repair_tracking=repair)

    def test_plan_uses_project_identity_exact_head_and_separate_phases(self):
        review = self.plan['before_merge'][0]
        self.assertEqual(review, ['gh', 'project', 'item-edit', '--id', 'PVTI_item',
            '--project-id', 'PVT_project', '--field-id', 'PVTSSF_status', '--single-select-option-id', 'review'])
        self.assertEqual(self.plan['request_merge'], [['gh', 'pr', 'merge', '12', '--repo',
            self.manifest['repository'], '--squash', '--match-head-commit', self.manifest['implementation_sha']]])
        self.assertFalse(any('item-add' in a or '--admin' in a or '--project-number' in a
            for phase in ('before_merge', 'request_merge', 'after_merge') for a in self.plan[phase]))
        self.assertEqual(self.fake.calls, [])

    def test_context_rejects_incomplete_malformed_and_option_data(self):
        bad_values = [('pr_number', True), ('project_number', 0), ('issue_number', -1),
            ('project_id', ''), ('project_item_id', '--admin'), ('project_owner', 'x\ny'),
            ('head_branch', 'bad..branch'), ('base_branch', '-master'), ('status_field_id', 'a\x7fb')]
        for key, value in bad_values:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                rc.ReleaseContext.from_dict({**self.context_data, key: value})
        for value in ([], {}, {**self.context_data, 'extra': 'bad'}):
            with self.assertRaises(ValueError):
                rc.ReleaseContext.from_dict(value)
        with self.assertRaises(ValueError):
            rc.build_release_plan(self.manifest, replace(self.context, repository='wrong/repo'))

    def test_proposal_defaults_to_master_and_cannot_contain_merge(self):
        proposal = rc.build_pr_proposal(self.manifest, 'codex/candidate', '/tmp/body.md')
        self.assertEqual(proposal[proposal.index('--base') + 1], 'master')
        self.assertEqual(proposal[:3], ['gh', 'pr', 'create'])
        self.assertNotIn('merge', proposal)

    def test_bundle_replay_blocks_fabricated_metrics_before_discovery(self):
        bad = copy.deepcopy(self.manifest)
        bad['measurements']['provenance']['covered_count'] = 0
        outcome = self.execute(manifest=bad)
        self.assertEqual(outcome['decision'], 'blocked')
        self.assertEqual(self.fake.calls, [])

    def test_all_eight_gates_and_artifacts_are_reopened(self):
        for gate in range(len(self.manifest['gate_reports'])):
            bad = copy.deepcopy(self.manifest)
            del bad['gate_reports'][gate]
            with self.subTest(gate=gate):
                self.assertEqual(self.execute(manifest=bad)['decision'], 'blocked')
        artifact = self.bundle / self.manifest['artifacts'][0]['ref']
        original = artifact.read_bytes()
        try:
            artifact.write_bytes(b'tampered')
            self.assertEqual(self.execute()['decision'], 'blocked')
        finally:
            artifact.write_bytes(original)
        self.assertEqual(self.fake.calls, [])

    def test_remote_negatives_never_mutate(self):
        cases = [lambda: self.fake.pr.update(headRefOid='a'*40),
            lambda: self.fake.pr.update(state='CLOSED'), lambda: self.fake.pr.update(isDraft=True),
            lambda: self.fake.pr.update(baseRefName='main'), lambda: self.fake.pr.update(statusCheckRollup=[]),
            lambda: self.fake.pr['statusCheckRollup'][0].update(status='IN_PROGRESS'),
            lambda: self.fake.pr.update(mergeStateStatus='UNKNOWN'),
            lambda: self.fake.fields.update(totalCount=1000),
            lambda: self.fake.fields['fields'][0]['options'][0].update(name='Wrong'),
            lambda: setattr(self.fake, 'field_type', 'NUMBER'),
            lambda: setattr(self.fake, 'required_checks', []),
            lambda: self.fake.required_checks[0].update(bucket='pending'),
            lambda: self.fake.issue.update(state='CLOSED'),
            lambda: setattr(self.fake, 'item_issue', 999),
            lambda: self.fake.issue.update(body='stale'),
            lambda: self.fake.issue.update(labels=[dict(name='blocked')]),
            lambda: self.fake.tracking.update(evidence='stale'),
            lambda: setattr(self.fake, 'fail', 'discovery')]
        for mutate in cases:
            self.setUp()
            mutate()
            with self.subTest(mutate=mutate):
                self.assertEqual(self.execute()['decision'], 'blocked')
                self.assertEqual(self.fake.mutations, [])

    def test_non_ascii_issue_and_paginated_item_lookup_merge(self):
        self.fake.pages = 2
        result = self.execute()
        self.assertEqual(result['decision'], 'merged')
        graphql = [a for a in self.fake.calls if a[:3] == ['gh', 'api', 'graphql']]
        self.assertEqual(len(graphql), 2)
        self.assertIn('cursor=cursor1', graphql[1])

    def test_incomplete_item_pagination_blocks(self):
        self.fake.incomplete = True
        self.assertEqual(self.execute()['decision'], 'blocked')
        self.assertEqual(self.fake.mutations, [])

    def test_ordered_tracking_recheck_merge_confirmation_done(self):
        result = self.execute()
        self.assertEqual(result['decision'], 'merged')
        suffix = self.fake.calls[-6:]
        self.assertEqual([a[:3] for a in suffix], [
            ['gh','project','item-edit'], ['gh','project','item-edit'], ['gh','pr','view'],
            ['gh','pr','merge'], ['gh','pr','view'], ['gh','project','item-edit']])
        self.assertEqual(suffix[0][-1], 'review')
        self.assertEqual(suffix[-1][-1], 'done')
        receipt = json.loads((self.receipt_root / 'release-receipt.json').read_text())
        self.assertEqual(receipt['merge_commit'], 'e'*40)
        self.assertEqual(receipt['candidate_sha'], self.manifest['implementation_sha'])
        events = [json.loads(line) for line in (self.receipt_root / 'release-events.jsonl').read_text().splitlines()]
        self.assertEqual([event['argv'] for event in events], self.fake.calls)
        self.assertEqual(events[-2]['phase'], 'confirm_merge')
        self.assertEqual(events[-1]['phase'], 'after_merge')
        self.assertEqual(json.loads((self.receipt_root / 'release-outcome.json').read_text())['decision'], 'merged')

    def test_tracking_failure_or_changed_head_stops_before_merge(self):
        for failure in ('tracking', 'evidence', 'stale'):
            self.setUp()
            if failure in ('tracking', 'evidence'):
                self.fake.fail = failure
            else:
                self.fake.stale = True
            result = self.execute()
            self.assertEqual(result['decision'], 'blocked')
            self.assertFalse(any(a[:3] == ['gh','pr','merge'] for a in self.fake.calls))
            self.assertNotIn('ghp_do_not_log', json.dumps(result))
            self.assertNotIn('ghp_do_not_log', (self.receipt_root / 'release-events.jsonl').read_text())

    def test_failed_merge_and_queued_merge_are_not_confirmed(self):
        self.fake.fail = 'merge'
        self.assertEqual(self.execute()['decision'], 'blocked')
        self.fake.fail = None
        self.fake.queue = True
        self.assertEqual(self.execute()['decision'], 'merge_pending')
        count = len(self.fake.mutations)
        self.assertEqual(self.execute()['decision'], 'merge_pending')
        self.assertEqual(len(self.fake.mutations), count)
        self.assertEqual(self.fake.tracking['status'], 'Review')

    def test_merged_tracking_failure_repairs_only_outstanding_fields_then_noop(self):
        self.fake.fail = 'done'
        result = self.execute()
        self.assertEqual(result['decision'], 'merged_tracking_failed')
        self.assertEqual(result['receipt']['merge_commit'], 'e'*40)
        self.fake.fail = None
        self.fake.calls.clear(); self.fake.mutations.clear()
        self.assertEqual(self.execute(repair=True)['decision'], 'tracking_repaired')
        self.assertEqual(self.fake.mutations, [self.plan['after_merge'][0]])
        self.fake.calls.clear(); self.fake.mutations.clear()
        self.assertEqual(self.execute(repair=True)['decision'], 'tracking_repaired')
        self.assertEqual(self.fake.mutations, [])
        self.assertFalse(any(a[:3] in (['gh','pr','merge'], ['gh','pr','create']) for a in self.fake.calls))

    def test_reconstruct_receipt_after_crash_and_reject_wrong_merged_identity(self):
        self.fake.pr.update(state='MERGED', isDraft=True, statusCheckRollup=[], mergeStateStatus='UNKNOWN',
                            mergedAt='2026-11-03T12:00:00Z', mergeCommit=dict(oid='e'*40))
        self.assertEqual(self.execute(repair=True)['decision'], 'tracking_repaired')
        for change in (dict(state='CLOSED'), dict(headRefOid='f'*40), dict(baseRefName='main'), dict(mergeCommit=dict(oid='f'*40))):
            original = copy.deepcopy(self.fake.pr)
            self.fake.pr.update(change); self.fake.mutations.clear()
            self.assertEqual(self.execute(repair=True)['decision'], 'blocked')
            self.assertEqual(self.fake.mutations, [])
            self.fake.pr = original

    def test_repair_plan_contains_only_tracking_without_review_regression(self):
        plan = rc.build_release_plan(self.manifest, self.context, repair_tracking=True)
        self.assertEqual(plan['before_merge'], [])
        self.assertEqual(plan['request_merge'], [])
        self.assertEqual([a[:3] for a in plan['after_merge']],
                         [['gh', 'project', 'item-edit'], ['gh', 'project', 'item-edit']])
        self.assertEqual(plan['after_merge'][-1][-1], 'done')

    def test_repair_failure_keeps_merge_and_evidence_repair_is_idempotent(self):
        self.fake.pr.update(state='MERGED', mergedAt='2026-11-03T12:00:00Z',
                            mergeCommit=dict(oid='e'*40))
        self.fake.tracking['evidence'] = 'outdated'
        self.fake.fail = 'tracking'
        failed = self.execute(repair=True)
        self.assertEqual(failed['decision'], 'merged_tracking_failed')
        self.assertEqual(failed['receipt']['merge_commit'], 'e'*40)
        self.fake.fail = None
        self.assertEqual(self.execute(repair=True)['decision'], 'tracking_repaired')
        self.fake.mutations.clear()
        self.assertEqual(self.execute(repair=True)['decision'], 'tracking_repaired')
        self.assertEqual(self.fake.mutations, [])

    def test_readonly_preflight_does_not_write_state_or_mutate(self):
        with patch.dict(os.environ, {}, clear=True):
            result = rc.execute_release_plan(self.plan, self.fake, trusted=self.trusted,
                evidence_root=self.bundle, state_root=self.receipt_root, execute=False)
        self.assertEqual(result['decision'], 'validated')
        self.assertEqual(self.fake.mutations, [])
        self.assertEqual(list(self.receipt_root.iterdir()), [])

    def test_tampered_plan_cannot_bypass_rebuilt_commands(self):
        self.plan['request_merge'][0].append('--admin')
        with patch.dict(os.environ, {'AUTODATA_RELEASE_AUTOMATION': 'enabled'}):
            result = rc.execute_release_plan(self.plan, self.fake, trusted=self.trusted,
                evidence_root=self.bundle, state_root=self.receipt_root)
        self.assertEqual(result['decision'], 'blocked')
        self.assertEqual(self.fake.calls, [])

    def test_issue_record_mismatches_block_all_mutations(self):
        for key, value in [('goal', 'different goal'), ('plan_ref', 'docs/wrong.md'),
                           ('candidate_sha', 'f'*40), ('evidence_sha256', 'f'*64),
                           ('unresolved_blockers', ['waiting for review']), ('status', 'blocked')]:
            self.setUp()
            bad = {**self.remote_record, key: value}
            self.fake.issue['body'] = '<!-- autodata-release\n' + json.dumps(bad) + '\n-->'
            with self.subTest(key=key):
                self.assertEqual(self.execute()['decision'], 'blocked')
                self.assertEqual(self.fake.mutations, [])

    def test_repair_rejects_wrong_project_item_without_mutations(self):
        self.fake.pr.update(state='MERGED', mergedAt='2026-11-03T12:00:00Z',
                            mergeCommit=dict(oid='e'*40))
        self.fake.item_issue = 999
        self.assertEqual(self.execute(repair=True)['decision'], 'blocked')
        self.assertEqual(self.fake.mutations, [])

    def test_repair_discovery_failure_retains_confirmed_merge_receipt(self):
        self.fake.fail = 'done'
        original = self.execute()
        self.assertEqual(original['decision'], 'merged_tracking_failed')
        self.fake.fail = 'discovery'
        self.fake.mutations.clear()
        failed = self.execute(repair=True)
        self.assertEqual(failed['decision'], 'merged_tracking_failed')
        self.assertEqual(failed['receipt'], original['receipt'])
        self.assertEqual(self.fake.mutations, [])

    def test_pagination_bound_blocks_without_partial_authorization(self):
        self.fake.pages = 101
        self.assertEqual(self.execute()['decision'], 'blocked')
        pages = [a for a in self.fake.calls if a[:3] == ['gh', 'api', 'graphql']]
        self.assertEqual(len(pages), 100)
        self.assertEqual(self.fake.mutations, [])

    def test_guard_and_denied_policy_block_before_discovery(self):
        with patch.dict(os.environ, {}, clear=True):
            result = rc.execute_release_plan(self.plan, self.fake, trusted=self.trusted,
                evidence_root=self.bundle, state_root=self.receipt_root)
        self.assertEqual(result['decision'], 'blocked')
        self.assertEqual(self.fake.calls, [])
        trusted = copy.deepcopy(self.trusted)
        trusted['policy']['autonomy']['allow_pull_request_merge'] = False
        with patch.dict(os.environ, {'AUTODATA_RELEASE_AUTOMATION': 'enabled'}):
            result = rc.execute_release_plan(self.plan, self.fake, trusted=trusted,
                evidence_root=self.bundle, state_root=self.receipt_root)
        self.assertEqual(result['decision'], 'blocked')
        self.assertEqual(self.fake.calls, [])


if __name__ == '__main__':
    unittest.main()
