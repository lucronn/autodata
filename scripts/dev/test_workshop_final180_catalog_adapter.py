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
        # JSON whitespace reaches the inclusive line/byte ceilings without
        # violating decoded-string limits or substituting a fake parser.
        line = event('pass').rstrip(b'\n')
        self.assertEqual(len(adapter.parse_catalog_events(line+b' '*(1048576-len(line)))),1)
        rows = [event('start'),event('run',ROOTS[0])]
        rows += [event('output',ROOTS[0],Output='synthetic')] * 60
        rows += [event('pass',ROOTS[0]),event('pass')]
        at_limit = b''.join(row[:-1]+b' '*(1048575-len(row[:-1]))+b'\n' for row in rows)
        self.assertEqual(len(at_limit),67108864)
        self.assertEqual(self.row(events_raw=at_limit).status,'passed')


    def test_explicit_grammar_rejection_codes_and_scalar_boundaries(self):
        valid = event('pass')
        bad = (
            (valid+b'\n', 'line_delimiter'), (valid+b'\n'+valid, 'line_delimiter'),
            (valid.replace(b'synthetic', b'syn\rthetic'), 'line_delimiter'),
            (b'\xef\xbb\xbf'+valid, 'json_invalid'), (b'\xff', 'json_invalid'),
            (b'{"Time":"x","Action":"pass","Package":"p","Time":"y"}', 'json_duplicate_key'),
            (b'{"x":{"a":1,"a":2}}', 'json_duplicate_key'),
            (b'{"x":NaN}', 'json_nonfinite'), (b'{"x":-Infinity}', 'json_nonfinite'),
            (event('pass',Elapsed=float('inf')), 'json_nonfinite'),
            (event('pass',Elapsed=1e309), 'json_nonfinite'),
            (b'{"x":"\\ud800"}', 'json_string'),
            (event('output',Output='x'*65537), 'json_string'),
            (event('pass',Time=None), 'event_type'), (b'null', 'event_type'),
            (event('run',''), 'event_type'), (event('run','x'*257), 'event_type'),
            (event('pass',Package='x'*257), 'event_type'),
            (event('fail',ROOTS[0],FailedBuild='build'), 'event_type'),
            (event('fail',FailedBuild='x'*1025), 'event_type'),
            (event('pass',Elapsed=-1), 'event_type'),
            (b'{"x":'+b'['*32+b'0'+b']'*32+b'}', 'json_depth'))
        for raw, code in bad:
            with self.subTest(code=code,raw=raw[:100]):
                with self.assertRaisesRegex(AdapterError,'^'+code+'$'):
                    adapter.parse_catalog_events(raw)
        for raw in (event('pass',Time='x'*128,Package='x'*256), event('run','x'*256),
                    event('fail',FailedBuild='x'*1024),event('output',Output=''),
                    event('pass',Elapsed=0),event('pass',Elapsed=86400.0)):
            self.assertEqual(len(adapter.parse_catalog_events(raw)),1)
        # Depth32 is admitted structurally, then rejected for its unsupported field.
        with self.assertRaisesRegex(AdapterError,'^event_keys$'):
            adapter.parse_catalog_events(b'{"x":'+b'['*31+b'0'+b']'*31+b'}')

    def test_semantic_and_receipt_failures_have_fixed_order(self):
        root = ROOTS[0]
        raw = event('start',Package='foreign')+event('run',root+'/child')
        raw += event('skip',root)+event('fail',root)+event('skip')+event('fail')
        row = self.row(events_raw=raw,receipt=SimulatedExit(1,True,False,True,False))
        self.assertEqual(row.status,'failed')
        self.assertEqual(row.failures,('package_mismatch','unknown_test','package_lifecycle',
            'root_lifecycle','root_failed','root_skipped','package_failed','package_skipped',
            'simulated_nonzero','simulated_timeout','ownership_lost','cleanup_incomplete'))

    def test_receipt_schema_checks_all_flags_and_exact_classes(self):
        for field in ('timed_out','interrupted','ownership_lost','cleanup_complete'):
            self.rejects('receipt_invalid',cases=(replace(self.cases[0],receipt=replace(NORMAL,**{field:1})),)+self.cases[1:])
        class ForeignCase(adapter.CatalogCase):
            pass
        class ForeignContext(adapter.CatalogContext):
            pass
        class ForeignExit(SimulatedExit):
            pass
        self.rejects('cases_invalid',cases=(ForeignCase(**self.cases[0].__dict__),)+self.cases[1:])
        self.rejects('context_invalid',context=ForeignContext(**self.context.__dict__))
        self.rejects('receipt_invalid',cases=(replace(self.cases[0],receipt=ForeignExit(**NORMAL.__dict__)),)+self.cases[1:])


class SerializationTests(unittest.TestCase):
    setUp = TranslationTests.setUp

    def diagnostic(self):
        return adapter.translate_catalog(self.cases, self.context)

    def assert_invalid(self, value):
        with self.assertRaisesRegex(AdapterError, '^diagnostic_invalid$'):
            adapter.serialize_catalog_diagnostic(value)

    def test_serializer_exists(self):
        self.assertTrue(callable(getattr(adapter, 'serialize_catalog_diagnostic', None)),
                        'strict catalog serializer implementation is absent')

    def test_canonical_roundtrip_order_ascii_lf_and_size(self):
        value = self.diagnostic()
        raw = adapter.serialize_catalog_diagnostic(value)
        self.assertEqual(raw, adapter.serialize_catalog_diagnostic(
            adapter.translate_catalog(tuple(reversed(self.cases)), self.context)))
        obj = json.loads(raw)
        self.assertEqual(raw, (json.dumps(obj, sort_keys=True, separators=(',', ':'),
                                         ensure_ascii=True, allow_nan=False)+'\n').encode('utf-8'))
        self.assertLessEqual(len(raw), 65536)
        self.assertEqual(raw.count(b'\n'), 1)
        self.assertTrue(raw.isascii())
        self.assertEqual(obj['accepted_case_credit'], 0)
        self.assertEqual(obj['enabled_tiers'], [])
        self.assertEqual(len(obj['authority']), 9)
        self.assertEqual(set(obj), set(adapter.CatalogDiagnostic.__dataclass_fields__))
        self.assertEqual(set(obj['observations'][0]), set(adapter.CatalogOutcome.__dataclass_fields__))

    def test_every_authority_pair_and_top_claim_is_revalidated(self):
        value = self.diagnostic()
        for i in range(9):
            pairs = list(value.authority)
            pairs[i] = (pairs[i][0], True)
            self.assert_invalid(replace(value, authority=tuple(pairs)))
        for changes in (
            {'accepted_case_credit': 1}, {'accepted_case_credit': True},
            {'profiles_enabled': True}, {'profiles_enabled': 0}, {'enabled_tiers': ('x',)},
            {'enabled_tiers': []}, {'authority': dict(value.authority)},
            {'authority': tuple(reversed(value.authority))}, {'authority': value.authority[:-1]},
            {'authority': (('extra', False),)+value.authority[1:]},
            {'authority': ((value.authority[0][0], 0),)+value.authority[1:]},
            {'contract': 'other'}, {'observation_kind': 'genuine-run'},
            {'candidate_sha': '0'*40}, {'inventory_sha256': '0'*64},
            {'source_manifest_sha256': 'A'*64}, {'status': 'interrupted'},
            {'observations': tuple(reversed(value.observations))},
            {'observations': value.observations[:-1]}, {'observations': list(value.observations)},
            {'observations': value.observations+value.observations[:1]}):
            with self.subTest(changes=changes):
                self.assert_invalid(replace(value, **changes))
        self.assert_invalid(None)
        self.assert_invalid({})

    def test_row_schema_refs_digests_and_failure_lists_are_revalidated(self):
        value = self.diagnostic()
        row = value.observations[0]
        for changes in (
            {'family':'identity'}, {'logical_id': IDS[1]}, {'logical_id': IDS[0]+'/child'},
            {'raw_refs':tuple(reversed(row.raw_refs))}, {'raw_refs':list(row.raw_refs)},
            {'raw_refs':('elsewhere',row.raw_refs[1])}, {'raw_refs':row.raw_refs+('extra',)},
            {'events_sha256':'A'*64}, {'stderr_sha256':'0'*63}, {'events_sha256':True},
            {'status':'skipped'}, {'status':False}, {'failures':[]},
            {'failures':('unknown',)}, {'failures':('root_failed','root_failed')},
            {'failures':('simulated_timeout','root_failed')},
            {'failures':('events_count','json_invalid')},
            {'failures':('events_count','root_failed')}, {'failures':(True,)},
            {'failures':(['unhashable'],)}):
            with self.subTest(changes=changes):
                bad_row = replace(row, **changes)
                self.assert_invalid(replace(value,observations=(bad_row,)+value.observations[1:]))
        self.assert_invalid(replace(value,observations=(None,)+value.observations[1:]))

    def test_serializer_derives_row_and_top_status_from_failures(self):
        value = self.diagnostic()
        for failures, row_status, top in (
            ((), 'passed', 'consistent'),
            (('events_count',), 'unavailable','unavailable'),
            (('events_count','simulated_interrupted'), 'unavailable','interrupted'),
            (('root_failed','simulated_interrupted'), 'unavailable','interrupted'),
            (('root_skipped',),'skipped','inconsistent'),
            (('root_skipped','simulated_nonzero'),'failed','inconsistent'),
            (('package_failed',),'failed','inconsistent')):
            row = replace(value.observations[0],failures=failures,status=row_status)
            diagnostic = replace(value,observations=(row,)+value.observations[1:],status=top)
            self.assertEqual(json.loads(adapter.serialize_catalog_diagnostic(diagnostic))['status'],top)
            self.assert_invalid(replace(diagnostic,status='fabricated'))
            bad = replace(row,status='failed' if row_status != 'failed' else 'passed')
            self.assert_invalid(replace(diagnostic,observations=(bad,)+value.observations[1:]))
        # An interrupted slot dominates another unavailable malformed slot.
        cases = (replace(self.cases[0],events_raw=b''),
                 replace(self.cases[1],receipt=replace(NORMAL,interrupted=True)))+self.cases[2:]
        diagnostic = adapter.translate_catalog(cases,self.context)
        self.assertEqual(json.loads(adapter.serialize_catalog_diagnostic(diagnostic))['status'],'interrupted')

    def test_frozen_types_and_concrete_type_admission(self):
        from dataclasses import FrozenInstanceError
        for value, field in ((self.context,'candidate_sha'), (self.cases[0],'provider'),
                             (self.diagnostic(),'status'), (self.diagnostic().observations[0],'status')):
            with self.assertRaises(FrozenInstanceError):
                setattr(value,field,'changed')
        class ForeignDiagnostic(adapter.CatalogDiagnostic):
            pass
        value = self.diagnostic()
        self.assert_invalid(ForeignDiagnostic(**value.__dict__))

    def test_static_import_and_call_boundary(self):
        source = Path(adapter.__file__).read_text()
        tree = ast.parse(source)
        expected_imports = {'hashlib','json','re'}
        expected_from = {
            'dataclasses': {'dataclass'},
            'scripts.dev.workshop_final180_identity_adapter': {
                'parse_identity_events','GoEvent','AdapterError','SimulatedExit'}}
        seen_imports = set()
        seen_from = {}
        functions = {node.name for node in ast.walk(tree) if isinstance(node,(ast.FunctionDef,ast.ClassDef))}
        allowed_names = functions | {'dataclass','type','all','any','len','tuple','set','sum','str',
                                    'enumerate','zip','dict','sorted','parse_identity_events','AdapterError'}
        allowed_attrs = {'fullmatch','sha256','hexdigest','append','add','dumps','encode','index'}
        forbidden_names = {'open','eval','exec','getattr','__import__','compile','input','breakpoint'}
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                for alias in node.names:
                    self.assertIsNone(alias.asname)
                    seen_imports.add(alias.name)
            elif isinstance(node,ast.ImportFrom):
                seen_from[node.module] = {alias.name for alias in node.names}
                self.assertTrue(all(alias.asname is None for alias in node.names))
            elif isinstance(node,ast.Call):
                if isinstance(node.func,ast.Name):
                    self.assertNotIn(node.func.id,forbidden_names)
                    self.assertIn(node.func.id,allowed_names)
                elif isinstance(node.func,ast.Attribute):
                    self.assertIn(node.func.attr,allowed_attrs)
                else:
                    self.fail('dynamic or callback call')
            elif isinstance(node,ast.Name):
                self.assertNotEqual(node.id,'__name__')
        self.assertEqual(seen_imports,expected_imports)
        self.assertEqual(seen_from,expected_from)


if __name__ == '__main__':
    unittest.main()
