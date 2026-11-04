"""Constructed synthetic bytes only: catalog slot and lifecycle contracts."""
import ast
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.dev.workshop_final180_identity_adapter import (
    AdapterError, SimulatedExit, parse_identity_events)
try:
    from scripts.dev import workshop_final180_catalog_adapter as adapter
except ImportError:
    adapter = None

ROOTS = (
    'TestPostgresCatalogLifecycleColdHTTPRaceOneJob',
    'TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP',
    'TestPostgresCatalogLifecycleAtomicPublication',
    'TestPostgresCatalogLifecycleWarmReadsNoExternalCalls',
)
IDS = (
    'TestPostgresCatalogLifecycleColdHTTPRaceOneJob-bankone',
    'TestPostgresCatalogLifecycleColdHTTPRaceOneJob-banktwo',
    'TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP-bankone',
    'TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP-banktwo',
    'TestPostgresCatalogLifecycleAtomicPublication-bankone',
    'TestPostgresCatalogLifecycleAtomicPublication-banktwo',
    'TestPostgresCatalogLifecycleWarmReadsNoExternalCalls-bankone',
    'TestPostgresCatalogLifecycleWarmReadsNoExternalCalls-banktwo',
)
PACKAGE = 'github.com/lucronn/autodata/apps/api-go'
NORMAL = SimulatedExit(0, False, False, False, True)


def event(action, test=None, **extra):
    row = dict(Time='synthetic', Action=action, Package=PACKAGE)
    if test is not None:
        row['Test'] = test
    row.update(extra)
    return json.dumps(row, separators=(',', ':'), ensure_ascii=True).encode() + b'\n'


def fake_stream(root, terminal='pass'):
    return b''.join((event('start'), event('run', root),
                     event(terminal, root), event(terminal)))


class TranslationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(adapter, 'catalog adapter implementation is absent')
        self.context = adapter.CatalogContext(
            '4d82e413e04fb2401ac7bc28dc828375ac662180',
            'c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39',
            'a' * 64)
        self.cases = tuple(adapter.CatalogCase(bank, root, fake_stream(root), b'', NORMAL)
                           for root in ROOTS for bank in ('bankone', 'banktwo'))

    def translate(self, **first):
        cases = (replace(self.cases[0], **first),) + self.cases[1:]
        return adapter.translate_catalog(cases, self.context)

    def row(self, **first):
        return self.translate(**first).observations[0]

    def rejects(self, code, cases=None, context=None):
        with self.assertRaisesRegex(AdapterError, '^' + code + '$'):
            adapter.translate_catalog(self.cases if cases is None else cases,
                                      self.context if context is None else context)

    def test_exact_eight_literal_slots_and_identical_bank_bytes(self):
        result = adapter.translate_catalog(tuple(reversed(self.cases)), self.context)
        self.assertEqual(tuple(row.logical_id for row in result.observations), IDS)
        self.assertEqual(tuple(row.status for row in result.observations), ('passed',) * 8)
        self.assertEqual(result.status, 'consistent')
        self.assertEqual(result.accepted_case_credit, 0)
        self.assertIs(type(result.accepted_case_credit), int)
        self.assertIs(result.profiles_enabled, False)
        self.assertEqual(result.enabled_tiers, ())
        self.assertTrue(all(flag is False for _, flag in result.authority))
        for index, row in enumerate(result.observations):
            root, bank = ROOTS[index // 2], ('bankone', 'banktwo')[index % 2]
            self.assertEqual(row.family, 'catalog')
            self.assertEqual(row.raw_refs, (f'r3/{bank}/{root}/go-events.jsonl',
                                            f'r3/{bank}/{root}/go-stderr.log'))
        self.assertEqual(result.observations[0].events_sha256, result.observations[1].events_sha256)

    def test_context_schema(self):
        for context in (None, {}, replace(self.context, candidate_sha='0' * 40),
                        replace(self.context, inventory_sha256='0' * 64),
                        replace(self.context, source_manifest_sha256='A' * 64),
                        replace(self.context, source_manifest_sha256=True)):
            with self.subTest(context=context):
                self.rejects('context_invalid', context=context if context is not None else {})

    def test_case_collection_schema(self):
        for cases in ([], list(self.cases), self.cases[:-1], self.cases + self.cases[:1],
                      (None,) + self.cases[1:]):
            self.rejects('cases_invalid', cases=cases)
        self.rejects('case_set', cases=(self.cases[1],) + self.cases[1:])
        for changes in ({'provider':'BANKONE'}, {'provider':True},
                        {'go_test_name':ROOTS[0] + '-bankone'}, {'go_test_name':ROOTS[0] + '/child'}):
            self.rejects('case_identity', cases=(replace(self.cases[0], **changes),) + self.cases[1:])

    def test_all_outer_validation_precedes_parse_and_hash(self):
        # A later bad schema must reject instead of parsing the earlier malformed slot.
        cases = (replace(self.cases[0], events_raw=b'bad'),) + self.cases[1:-1] + (replace(self.cases[-1], stderr_raw='bad'),)
        with patch.object(adapter, 'parse_catalog_events', side_effect=AssertionError('parsed early')), \
             patch.object(adapter.hashlib, 'sha256', side_effect=AssertionError('hashed early')):
            self.rejects('stderr_type', cases=cases)
        self.rejects('input_type', cases=(replace(self.cases[0], events_raw=bytearray()),) + self.cases[1:])

    def test_receipt_schema_and_none_exit(self):
        for receipt in (None, (0,False,False,False,True), replace(NORMAL, exit_code=True),
                        replace(NORMAL, exit_code=256), replace(NORMAL, exit_code=-256),
                        replace(NORMAL, timed_out=0), replace(NORMAL, exit_code=None)):
            self.rejects('receipt_invalid', cases=(replace(self.cases[0], receipt=receipt),) + self.cases[1:])
        for field in ('timed_out', 'interrupted', 'ownership_lost', 'cleanup_complete'):
            receipt = replace(NORMAL, exit_code=None, **{field: field != 'cleanup_complete'})
            self.assertNotEqual(self.row(receipt=receipt).status, 'passed')

    def test_receipt_poison_and_order(self):
        for field, value, code, status in (
            ('exit_code', -255, 'simulated_nonzero', 'failed'),
            ('exit_code', 255, 'simulated_nonzero', 'failed'),
            ('timed_out', True, 'simulated_timeout', 'failed'),
            ('interrupted', True, 'simulated_interrupted', 'unavailable'),
            ('ownership_lost', True, 'ownership_lost', 'failed'),
            ('cleanup_complete', False, 'cleanup_incomplete', 'failed')):
            row = self.row(receipt=replace(NORMAL, **{field:value}))
            self.assertEqual((row.status, row.failures), (status, (code,)))
        receipt = SimulatedExit(1, True, True, True, False)
        result = self.translate(receipt=receipt)
        self.assertEqual(result.status, 'interrupted')
        self.assertEqual(result.observations[0].failures, ('simulated_nonzero', 'simulated_timeout',
                         'simulated_interrupted', 'ownership_lost', 'cleanup_incomplete'))

    def test_parser_failure_retains_receipts_and_seven_independent_rows(self):
        result = self.translate(events_raw=b'bad\n', receipt=replace(NORMAL, interrupted=True))
        self.assertEqual(result.status, 'interrupted')
        self.assertEqual(result.observations[0].status, 'unavailable')
        self.assertEqual(result.observations[0].failures, ('json_invalid', 'simulated_interrupted'))
        self.assertEqual(tuple(row.status for row in result.observations[1:]), ('passed',) * 7)
        self.assertEqual(self.translate(events_raw=b'').status, 'unavailable')

    def test_exact_hashes_and_opaque_stderr(self):
        original = self.row()
        changed = self.row(events_raw=self.cases[0].events_raw[:-1], stderr_raw=b'\xfffail timeout pass\x00')
        self.assertEqual(changed.status, 'passed')
        self.assertEqual(changed.events_sha256, hashlib.sha256(self.cases[0].events_raw[:-1]).hexdigest())
        self.assertEqual(changed.stderr_sha256, hashlib.sha256(b'\xfffail timeout pass\x00').hexdigest())
        self.assertNotEqual(original.events_sha256, changed.events_sha256)
        self.assertEqual(original.stderr_sha256, hashlib.sha256(b'').hexdigest())

    def test_lifecycle_structural_adversaries(self):
        start, run, end, finish = self.cases[0].events_raw.splitlines(keepends=True)
        for raw, code in (
            (run+end+finish, 'package_lifecycle'), (start+start+run+end+finish, 'package_lifecycle'),
            (start+run+end, 'package_lifecycle'), (start+run+end+finish+finish, 'package_lifecycle'),
            (start+end+finish, 'root_lifecycle'), (start+run+run+end+finish, 'root_lifecycle'),
            (start+run+finish, 'root_lifecycle'), (start+run+end+end+finish, 'root_lifecycle'),
            (start+end+run+finish, 'root_lifecycle'), (start+finish+run+end, 'package_lifecycle'),
            (start+event('output',ROOTS[0],Output='x')+run+end+finish, 'root_lifecycle'),
            (start+run+end+event('output',ROOTS[0],Output='x')+finish, 'root_lifecycle'),
            (start+run+end+finish+event('output',Output='x'), 'package_lifecycle'),
            (event('output',Output='x')+start+run+end+finish, 'package_lifecycle'),
            (fake_stream(ROOTS[1]), 'unknown_test'), (fake_stream(ROOTS[0]+'/child'), 'unknown_test'),
            (self.cases[0].events_raw.replace(PACKAGE.encode(), b'foreign'), 'package_mismatch')):
            with self.subTest(raw=raw):
                row = self.row(events_raw=raw)
                self.assertEqual(row.status, 'failed')
                self.assertIn(code, row.failures)

    def test_output_is_opaque_and_repeated_outputs_are_allowed(self):
        root = ROOTS[0]
        raw = event('start') + event('output',Output='fail skip banktwo') + event('run',root)
        raw += event('output',root,Output='fail timeout') * 2 + event('pass',root) + event('pass')
        self.assertEqual(self.row(events_raw=raw).status, 'passed')

    def test_failure_and_skip_precedence(self):
        root = ROOTS[0]
        for terminal, package, receipt, state in (
            ('fail','pass',NORMAL,'failed'), ('skip','skip',NORMAL,'skipped'),
            ('pass','skip',NORMAL,'skipped'), ('skip','pass',NORMAL,'skipped'),
            ('fail','skip',NORMAL,'failed'), ('skip','skip',replace(NORMAL,exit_code=1),'failed'),
            ('pass','pass',replace(NORMAL,timed_out=True),'failed')):
            raw = event('start')+event('run',root)+event(terminal,root)+event(package)
            self.assertEqual(self.row(events_raw=raw,receipt=receipt).status,state)
        self.assertEqual(self.row(events_raw=event('start')+event('skip')).status,'failed')
        self.assertEqual(self.row(events_raw=event('start')+event('skip',root)+event('skip')).status,'failed')
        self.assertEqual(self.translate(events_raw=fake_stream(root,'skip')).status,'inconsistent')

    def test_parser_wrapper_matches_public_b1_grammar(self):
        samples = [b'', b'\n', b'{}\n\n', b'{}\r\n', b'\xef\xbb\xbf{}', b'\xff', b'null', b'[]',
                   b'{"Time":"x","Time":"y"}', b'{"x":{"a":1,"a":2}}', b'{"x":NaN}',
                   b'{"x":Infinity}', b'{"x":"\\ud800"}', b'{"x":'+b'['*33+b'0'+b']'*33+b'}',
                   event('pause'), event('cont'), event('bench'), event('start',ROOTS[0]),
                   event('run'), event('pass',Output='x'), event('output'), event('pass',FailedBuild='x'),
                   event('fail',FailedBuild=''), event('pass',Elapsed=True), event('pass',Elapsed=None),
                   event('pass',Unexpected=1), event('pass',Time=''), event('pass',Package=''),
                   event('pass',Time='x'*129), event('pass',Output=None), event('pass',Elapsed=86401),
                   event('output',Output='x'*65537), self.cases[0].events_raw+b'bad\n',
                   self.cases[0].events_raw, event('fail',FailedBuild='build'), event('pass',Elapsed=86400)]
        for raw in samples:
            with self.subTest(raw=raw[:100]):
                try:
                    expected = parse_identity_events(raw)
                except AdapterError as exc:
                    with self.assertRaisesRegex(AdapterError, '^'+str(exc)+'$'):
                        adapter.parse_catalog_events(raw)
                else:
                    self.assertEqual(adapter.parse_catalog_events(raw), expected)
        self.assertEqual(self.row(events_raw=self.cases[0].events_raw+b'bad\n').failures, ('json_invalid',))

    def test_resource_ceilings_and_validation_order(self):
        self.rejects('events_size', cases=(replace(self.cases[0],events_raw=b'x'*67108865),)+self.cases[1:])
        self.rejects('stderr_size', cases=(replace(self.cases[0],stderr_raw=b'x'*1048577),)+self.cases[1:])
        self.assertEqual(self.row(stderr_raw=b'x'*1048576).status,'passed')
        # Exact event ceiling admitted by outer validation; grammar then rejects its line size.
        self.assertEqual(self.row(events_raw=b'x'*67108864).failures, ('line_size',))
        total_other = sum(len(case.events_raw) for case in self.cases[1:])
        remaining = 68157440 - 67108864 - total_other
        cases = (replace(self.cases[0],events_raw=b'x'*67108864,stderr_raw=b'x'*remaining),)+self.cases[1:]
        self.assertEqual(adapter.translate_catalog(cases,self.context).observations[0].failures,('line_size',))
        self.rejects('aggregate_size',cases=(replace(cases[0],stderr_raw=cases[0].stderr_raw+b'x'),)+cases[1:])
        for raw, expected in ((b'x'*1048576,'json_invalid'),(b'x'*1048577,'line_size'),
                              (event('pass')*65537,'events_count')):
            with self.assertRaisesRegex(AdapterError,'^'+expected+'$'):
                adapter.parse_catalog_events(raw)
        self.assertEqual(len(adapter.parse_catalog_events(event('pass')*65536)),65536)
        self.assertEqual(adapter.parse_catalog_events(event('output',Output='x'*65536))[0].output,'x'*65536)


if __name__ == '__main__':
    unittest.main()
