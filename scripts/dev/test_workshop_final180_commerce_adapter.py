"""Constructed-byte tests for the restricted synthetic commerce contract."""
from dataclasses import replace
import hashlib
import json
import unittest
from unittest.mock import patch
from scripts.dev.workshop_final180_identity_adapter import AdapterError, SimulatedExit
try:
    from scripts.dev import workshop_final180_commerce_adapter as adapter
except ImportError:
    adapter = None

COMMERCE_NAMES = ('test_orders_create_and_owner_scope', 'test_same_key_replay_and_conflict', 'test_concurrent_keys_share_one_checkout', 'test_scope_races_single_active_grant', 'test_lost_create_response_and_retention_boundary', 'test_expiry_requires_remote_nonchargeable_proof', 'test_completion_races_expiry_without_recharge', 'test_webhook_before_create_response', 'test_settlement_binds_financial_owner_scope', 'test_duplicate_and_distinct_events_grant_once', 'test_refund_chargeback_ordering_and_monotonic_revocation', 'test_payment_survives_source_unavailable_and_restart', 'test_library_is_owner_only_and_paginated', 'test_grant_check_exact_scope_legacy_and_revoked')
SUPPORT_NAMES = ('test_migrations_are_numeric_and_ordered', 'test_customer_identity_migration_and_all_four_driver_boundaries', 'test_commerce_migration_has_structured_owner_and_financial_guards', 'test_dataset_request_ownership_is_backfilled_without_overwriting_existing_values', 'test_schema_migrations_cover_platform_spine_and_vector', 'test_foundation_fixture_is_separate_from_schema_migrations', 'test_chat_quote_revision_publication_state_and_immutability_are_database_enforced', 'test_price_snapshots_are_immutable_and_refresh_failures_are_separate', 'test_visual_artifacts_require_and_preserve_source_artifact_linkage', 'test_quote_arithmetic_and_overlap_bounds_are_database_enforced', 'test_quote_persists_required_and_recommended_operation_collections', 'test_quote_operation_categories_upgrade_existing_025_table', 'test_worker_events_persist_the_complete_event_envelope', 'test_reusable_derived_article_key_prevents_query_uniqueness_collisions', 'test_markup_is_structurally_prohibited', 'test_psql_command_includes_host_and_port_when_address_provided', 'test_resolve_database_address_respects_explicit_and_environment', 'test_emit_is_embedded_and_uses_one_session_lock', 'test_manifest_rejects_holes_unsafe_names_symlinks_and_wrong_stems', 'test_fixture_prefix_accepts_only_contiguous_canonical_prefix', 'test_default_refuses_truncated_manifest_before_sql_output', 'test_default_invocation_executes_identical_emit_output_and_cleans_tempfile', 'test_fixed_transaction_contract_is_audited', 'test_adapter_streams_one_driver_and_returns_only_actual_applications', 'test_adapter_propagates_generator_and_psql_failure', 'test_full_chain_restart_preserves_every_marker_and_schema', 'test_partial_catalog_row_survives_full_restart', 'test_empty_bootstrap_and_untracked_application_rejection[False]', 'test_empty_bootstrap_and_untracked_application_rejection[True]', 'test_invalid_ledger_fails_before_pending_application_ddl[unknown]', 'test_invalid_ledger_fails_before_pending_application_ddl[wrong_stem]', 'test_invalid_ledger_fails_before_pending_application_ddl[gap]', 'test_invalid_ledger_fails_before_pending_application_ddl[duplicate_shape]', 'test_invalid_ledger_fails_before_pending_application_ddl[wrong_timestamp]', 'test_original_038_adoption_and_markerless_033_effects_are_once_only', 'test_genuine_036_upgrade_preserves_jobs_and_matches_fresh_schema', 'test_migration_failure_rolls_back_only_active_file_then_retry[2]', 'test_migration_failure_rolls_back_only_active_file_then_retry[33]', 'test_migration_failure_rolls_back_only_active_file_then_retry[36]', 'test_migration_failure_rolls_back_only_active_file_then_retry[37]', 'test_migration_failure_rolls_back_only_active_file_then_retry[38]', 'test_migration_failure_rolls_back_only_active_file_then_retry[39]', 'test_migration_failure_rolls_back_only_active_file_then_retry[40]', 'test_recorded_001_and_partial_unmarked_next_file_remain_retryable', 'test_two_full_runners_serialize_and_apply_each_version_once[False]', 'test_two_full_runners_serialize_and_apply_each_version_once[True]', 'test_connection_death_releases_lock_and_rolls_back_active_file', 'test_restart_after_committed_037_only_applies_038_and_039', 'test_native_python_adapter_applies_then_skips_in_one_session', 'test_markerless_033_failure_rolls_back_reviewer_effects_and_marker', 'test_populated_publication_and_all_lifecycle_records_survive_restart', 'test_populated_038_upgrade_only_adds_identity_schema', 'test_populated_customer_identity_restart_preserves_rows_and_ledger')
COMMON_REFS = ('workshop-commerce-tests.xml', 'workshop-commerce-pytest.stdout.log', 'workshop-commerce-pytest.stderr.log')
GO_REFS = ('workshop-commerce-go-events.jsonl', 'workshop-commerce-go-stderr.log')
CLEAN = SimulatedExit(0, False, False, False, True)
PACKAGE = 'github.com/lucronn/autodata/apps/api-go'
ROOT = 'TestWorkshopCommercePythonIntegration'


def clean_xml():
    commerce = ''.join('<testcase classname="tests.test_commerce_postgres" name="' + n + '"/>' for n in COMMERCE_NAMES)
    support = ''.join('<testcase classname="synthetic.unobserved" name="' + n + '"/>' for n in SUPPORT_NAMES)
    return ('<testsuite>' + commerce + support + '</testsuite>').encode()


def go_bytes(rows=None):
    if rows is None:
        rows = [('start', None), ('run', ROOT), ('pass', ROOT), ('pass', None)]
    events = []
    for action, name in rows:
        event = dict(Time='synthetic', Action=action, Package=PACKAGE)
        if name is not None:
            event['Test'] = name
        if action == 'output':
            event['Output'] = 'opaque'
        events.append(event)
    return b'\n'.join(json.dumps(e, separators=(',', ':')).encode() for e in events) + b'\n'


def context():
    return adapter.CommerceContext('4d82e413e04fb2401ac7bc28dc828375ac662180',
        'c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39', '0' * 64)


def value(xml=None, receipt=CLEAN, go=None, go_receipt=CLEAN, absent=False):
    support = None if absent else adapter.CommerceGoSupport(go_bytes() if go is None else go, b'', go_receipt)
    return adapter.CommerceInput(clean_xml() if xml is None else xml, b'', b'', receipt, support)


def translate(**kwargs):
    return adapter.translate_commerce(value(**kwargs), context())


class CommerceTranslationTests(unittest.TestCase):
    def test_clean_synthetic_rows(self):
        self.assertIsNotNone(adapter, 'commerce adapter implementation missing')
        result = translate()
        self.assertEqual((result.status, result.reasons), ('consistent', ()))
        self.assertEqual(tuple(r.logical_id for r in result.observations), COMMERCE_NAMES)
        self.assertEqual(tuple(r.status for r in result.observations), ('passed',) * 14)
        self.assertEqual(tuple(r.raw_refs for r in result.observations), (COMMON_REFS + GO_REFS,) + (COMMON_REFS,) * 13)
        self.assertIs(type(result.accepted_case_credit), int)
        self.assertEqual(result.accepted_case_credit, 0)
        self.assertTrue(all(v is False for _, v in result.authority))

    def test_twelve_cell_product_retains_every_stream_fact(self):
        receipts = (CLEAN, SimulatedExit(1, False, False, False, True), SimulatedExit(0, False, True, False, True))
        wants = (
            (('consistent', 'passed', 'passed'), ('unavailable', 'unavailable', 'passed'), ('inconsistent', 'failed', 'passed'), ('interrupted', 'unavailable', 'passed')),
            (('inconsistent', 'failed', 'failed'), ('unavailable', 'unavailable', 'failed'), ('inconsistent', 'failed', 'failed'), ('interrupted', 'unavailable', 'failed')),
            (('interrupted', 'unavailable', 'unavailable'), ('unavailable', 'unavailable', 'unavailable'), ('interrupted', 'unavailable', 'unavailable'), ('interrupted', 'unavailable', 'unavailable')))
        go_cases = ((go_bytes(), CLEAN, ()), (b'{\n', CLEAN, ('go:json_invalid',)),
                    (go_bytes([('start', None), ('run', ROOT), ('fail', ROOT), ('pass', None)]), CLEAN, ('go:root_failed',)),
                    (go_bytes(), receipts[2], ('go:simulated_interrupted',)))
        for i, receipt in enumerate(receipts):
            for j, (raw, gr, reasons) in enumerate(go_cases):
                with self.subTest(pytest=i, go=j):
                    result = translate(receipt=receipt, go=raw, go_receipt=gr)
                    top, first, rest = wants[i][j]
                    self.assertEqual(result.status, top)
                    self.assertEqual(tuple(r.status for r in result.observations), (first,) + (rest,) * 13)
                    py = () if i == 0 else ('pytest:simulated_nonzero',) if i == 1 else ('pytest:simulated_interrupted',)
                    expected = tuple(r for r in ('go:json_invalid', 'go:root_failed') if r in reasons) + py + tuple(r for r in reasons if r == 'go:simulated_interrupted')
                    self.assertEqual(result.reasons, expected)

    def test_absence_and_dual_parser_failures(self):
        for receipt, rest, reasons in ((CLEAN, 'passed', ()), (SimulatedExit(1, False, False, False, True), 'failed', ('pytest:simulated_nonzero',)), (SimulatedExit(None, False, True, False, False), 'unavailable', ('pytest:simulated_interrupted', 'pytest:cleanup_incomplete'))):
            result = translate(receipt=receipt, absent=True)
            self.assertEqual(result.status, 'unavailable')
            self.assertEqual(result.reasons, ('go:support_absent',) + reasons)
            self.assertEqual(tuple(r.status for r in result.observations), ('unavailable',) + (rest,) * 13)
            self.assertEqual(result.observations[0].raw_refs, COMMON_REFS)
        result = translate(xml=b'<', go=b'{\n', receipt=SimulatedExit(1, True, True, True, False))
        self.assertEqual(result.reasons, ('xml:xml_invalid', 'go:json_invalid', 'pytest:simulated_nonzero', 'pytest:simulated_timeout', 'pytest:simulated_interrupted', 'pytest:ownership_lost', 'pytest:cleanup_incomplete'))
        self.assertEqual(tuple(r.status for r in result.observations), ('unavailable',) * 14)

    def test_identity_missing_duplicate_and_reserved_class_for_every_name(self):
        for name in COMMERCE_NAMES + SUPPORT_NAMES:
            with self.subTest(name=name):
                raw = clean_xml().replace(('name="' + name + '"').encode(), b'name="unknown"')
                self.assertEqual(translate(xml=raw).reasons, ('xml:unknown_case', 'xml:missing_case'))
                cls = 'tests.test_commerce_postgres' if name in COMMERCE_NAMES else 'opaque'
                duplicate = ('<testcase classname="' + cls + '" name="' + name + '"/>').encode()
                self.assertEqual(translate(xml=clean_xml().replace(b'</testsuite>', duplicate + b'</testsuite>')).reasons, ('xml:case_count', 'xml:duplicate_case'))
                old = ('classname="tests.test_commerce_postgres" name="' + name + '"') if name in COMMERCE_NAMES else ('classname="synthetic.unobserved" name="' + name + '"')
                new = ('classname="wrong" name="' + name + '"') if name in COMMERCE_NAMES else ('classname="tests.test_commerce_postgres" name="' + name + '"')
                self.assertEqual(translate(xml=clean_xml().replace(old.encode(), new.encode())).reasons, ('xml:identity_mismatch',))

    def test_global_terminals_and_opaque_support_and_hashes(self):
        for terminal in ('failure', 'error', 'skipped'):
            raw = clean_xml().replace(b'/>', ('><' + terminal + '>opaque</' + terminal + '></testcase>').encode(), 1)
            self.assertEqual(translate(xml=raw).reasons, ('xml:testcase_' + terminal,))
        raw = clean_xml().replace(b'synthetic.unobserved', b'new:opaque')
        self.assertEqual(translate(xml=raw).status, 'consistent')
        self.assertEqual(translate(xml=raw).junit_sha256, hashlib.sha256(raw).hexdigest())


class CommerceParserTests(unittest.TestCase):
    def assertCode(self, code, raw):
        for _ in range(2):
            with self.assertRaisesRegex(AdapterError, '^' + code + '$'):
                adapter.parse_commerce_junit(raw)
        self.assertIn('xml:' + code, translate(xml=raw).reasons)

    def test_character_precedence_exact_fixtures(self):
        for count, tail, code in ((1048574, b'X' + b' ' * 100, 'xml_structure'), (1048575, b'X', 'xml_structure'), (1048576, b'X', 'xml_text')):
            self.assertCode(code, b'<testsuite>' + b' ' * count + tail + b'</testsuite>')
        for _ in range(2):
            self.assertEqual(adapter.parse_commerce_junit(b'<testsuite>' + b' ' * 1048576 + b'</testsuite>'), ())
        raw = b'<testsuite><testcase classname="c" name="n"><failure>'
        self.assertEqual(adapter.parse_commerce_junit(raw + b' ' * 4096 + b'</failure></testcase></testsuite>')[0].terminal, 'failure')
        self.assertCode('xml_text', raw + b' ' * 4097 + b'</failure></testcase></testsuite>')

    def test_checker_segmentation_stops_at_same_codepoint(self):
        text = ' ' * 1048574 + 'X' + ' ' * 100
        segmentations = ((text,), iter(text), (text[:1048574], text[1048574:1048575], text[1048575:1048576], text[1048576:]))
        for chunks in segmentations:
            state = adapter._CharacterData()
            with self.assertRaisesRegex(AdapterError, '^xml_structure$'):
                for chunk in chunks:
                    state.check(chunk)
            self.assertEqual(state.total, 1048575)

    def test_grammar_and_encoding_rejections(self):
        fixtures = (
            ('xml_encoding', b'\xff'), ('xml_forbidden', b'\xef\xbb\xbf<testsuite/>'),
            ('xml_forbidden', b'<?xml version="1.0"?><testsuite/>'), ('xml_forbidden', b'<testsuite><!--x--></testsuite>'),
            ('xml_forbidden', b'<!DOCTYPE x SYSTEM "file:///no-read"><testsuite/>'), ('xml_forbidden', b'<testsuite><![CDATA[x]]></testsuite>'),
            ('xml_invalid', b''), ('xml_invalid', b'<testsuite/><testsuite/>'), ('xml_invalid', b'<testsuite>&missing;</testsuite>'),
            ('xml_invalid', b'<testsuite>\x00</testsuite>'), ('xml_invalid', b'<testsuite>'),
            ('xml_structure', b'<testsuites/>'), ('xml_structure', b'<testsuite tests="0"/>'),
            ('xml_structure', b'<testsuite><testcase classname="c" name="n"><failure/><error/></testcase></testsuite>'),
            ('xml_structure', b'<testsuite><testcase classname="c" name="n"><failure x="a"/></testcase></testsuite>'),
            ('xml_structure', b'<testsuite xmlns="x"/>'), ('xml_structure', b'<testsuite>x</testsuite>'),
            ('xml_structure', b'<testsuite><system-out/></testsuite>'),
            ('xml_depth', b'<testsuite><testcase classname="c" name="n"><failure><a/></failure></testcase></testsuite>'),
            ('xml_string', b'<testsuite><testcase classname="" name="n"/></testsuite>'),
            ('xml_string', b'<testsuite><testcase classname="' + b'a' * 1025 + b'" name="n"/></testsuite>'),
            ('xml_nodes', b'<testsuite>' + b'<testcase classname="c" name="n"/>' * 256 + b'</testsuite>'))
        for code, raw in fixtures:
            with self.subTest(code=code, raw=raw[:80]):
                self.assertCode(code, raw)

    def test_normalization_entities_and_bounds(self):
        raw = b'<testsuite><testcase name="a&amp;&lt;&gt;&quot;&apos;&#233;" classname="c\tX\r\nY"><failure>' + '&#233;'.encode() * 2048 + b'</failure></testcase></testsuite>'
        case, = adapter.parse_commerce_junit(raw)
        self.assertEqual((case.classname, case.name), ('c X Y', 'a&<>"\'é'))
        self.assertCode('xml_text', raw.replace(b'</failure>', b' </failure>'))
        self.assertEqual(len(adapter.parse_commerce_junit(b'<testsuite>' + b'<testcase classname="c" name="n"/>' * 255 + b'</testsuite>')), 255)
        self.assertEqual(adapter.parse_commerce_junit(b'<testsuite><testcase classname="' + b'a' * 1024 + b'" name="n"/></testsuite>')[0].name, 'n')


class CommerceAdmissionTests(unittest.TestCase):
    def assertOuter(self, code, inp=None, ctx=None):
        with patch.object(adapter, 'parse_commerce_junit', side_effect=AssertionError('parsed before admission')):
            with patch.object(adapter.hashlib, 'sha256', side_effect=AssertionError('hashed before admission')):
                with self.assertRaisesRegex(AdapterError, '^' + code + '$'):
                    adapter.translate_commerce(value() if inp is None else inp, context() if ctx is None else ctx)

    def test_outer_types_context_and_order(self):
        class ContextSubclass(adapter.CommerceContext):
            pass
        for ctx in (object(), replace(context(), candidate_sha='a' * 40), replace(context(), source_manifest_sha256='A' * 64), ContextSubclass(*context().__dict__.values())):
            self.assertOuter('context_invalid', object(), ctx)
        self.assertOuter('input_invalid', object())
        for field in ('junit_raw', 'pytest_stdout_raw', 'pytest_stderr_raw'):
            self.assertOuter('input_type', replace(value(), **{field: bytearray()}))
        self.assertOuter('go_support_invalid', replace(value(), go_support=()))
        self.assertOuter('input_type', replace(value(), go_support=adapter.CommerceGoSupport('', b'', CLEAN)))
        self.assertOuter('input_type', replace(value(), go_support=adapter.CommerceGoSupport(b'', '', CLEAN)))
        # All byte types precede every size check.
        self.assertOuter('input_type', replace(value(), junit_raw=b'x' * 4194305, pytest_stderr_raw=''))

    def test_each_stream_boundary_and_sum_invariant(self):
        for field, size, code in (('junit_raw', 4194304, 'junit_size'), ('pytest_stdout_raw', 1048576, 'pytest_stdout_size'), ('pytest_stderr_raw', 1048576, 'pytest_stderr_size')):
            inp = replace(value(), **{field: b' ' * size})
            result = adapter.translate_commerce(inp, context())
            self.assertIsInstance(result, adapter.CommerceDiagnostic)
            self.assertOuter(code, replace(inp, **{field: b' ' * (size + 1)}))
        for field, size, code in (('events_raw', 67108864, 'events_size'), ('stderr_raw', 1048576, 'stderr_size')):
            inp = replace(value(), go_support=replace(value().go_support, **{field: b' ' * size}))
            self.assertIsInstance(adapter.translate_commerce(inp, context()), adapter.CommerceDiagnostic)
            self.assertOuter(code, replace(inp, go_support=replace(inp.go_support, **{field: b' ' * (size + 1)})))
        self.assertEqual(4194304 + 1048576 + 1048576 + 67108864 + 1048576, 74448896)

    def test_receipt_validation_and_all_flags(self):
        invalid = (None, (), SimulatedExit(True, False, False, False, True), SimulatedExit(256, False, False, False, True), SimulatedExit(-256, False, False, False, True), SimulatedExit(None, False, False, False, True), SimulatedExit(0, 0, False, False, True))
        for receipt in invalid:
            self.assertOuter('receipt_invalid', replace(value(), pytest_receipt=receipt))
            self.assertOuter('receipt_invalid', replace(value(), go_support=replace(value().go_support, receipt=receipt)))
        for field, reason in (('timed_out', 'simulated_timeout'), ('interrupted', 'simulated_interrupted'), ('ownership_lost', 'ownership_lost'), ('cleanup_complete', 'cleanup_incomplete')):
            receipt = replace(CLEAN, exit_code=None, **{field: field != 'cleanup_complete'})
            result = translate(receipt=receipt, go_receipt=receipt)
            self.assertEqual(result.reasons, ('pytest:' + reason, 'go:' + reason))
            self.assertEqual((result.status, tuple(r.status for r in result.observations)), ('interrupted', ('unavailable',) * 14))
        for code in (-255, 255):
            self.assertEqual(translate(receipt=replace(CLEAN, exit_code=code)).status, 'inconsistent')

    def test_both_public_parsers_still_attempted_after_other_failure(self):
        xml_parser = adapter.parse_commerce_junit
        go_parser = adapter.parse_commerce_go_events
        with patch.object(adapter, 'parse_commerce_junit', wraps=xml_parser) as xp, patch.object(adapter, 'parse_commerce_go_events', wraps=go_parser) as gp:
            result = translate(xml=b'<', go=b'{\n')
            self.assertEqual(result.reasons, ('xml:xml_invalid', 'go:json_invalid'))
            xp.assert_called_once_with(b'<')
            gp.assert_called_once_with(b'{\n')


class CommerceGoTests(unittest.TestCase):
    def test_lifecycle_full_summary_and_package_independence(self):
        fixtures = (
            ([('run', ROOT), ('pass', ROOT), ('pass', None)], ('go:package_lifecycle',)),
            ([('start', None), ('run', ROOT), ('pass', ROOT)], ('go:package_lifecycle',)),
            ([('start', None), ('run', ROOT), ('run', ROOT), ('pass', ROOT), ('pass', None)], ('go:root_lifecycle',)),
            ([('start', None), ('pass', ROOT), ('run', ROOT), ('pass', None)], ('go:root_lifecycle',)),
            ([('start', None), ('output', ROOT), ('run', ROOT), ('pass', ROOT), ('pass', None)], ('go:root_lifecycle',)),
            ([('start', None), ('run', ROOT), ('pass', ROOT), ('output', ROOT), ('pass', None)], ('go:root_lifecycle',)),
            ([('start', None), ('run', ROOT), ('skip', ROOT), ('fail', None)], ('go:root_skipped', 'go:package_failed')),
            ([('start', None), ('run', ROOT), ('fail', ROOT), ('skip', None)], ('go:root_failed', 'go:package_skipped')),
            ([('start', None), ('start', None), ('run', ROOT), ('pass', ROOT), ('pass', None)], ('go:package_lifecycle',)),
            ([('start', None), ('run', ROOT + '/child'), ('pass', ROOT + '/child'), ('pass', None)], ('go:unknown_test', 'go:root_lifecycle')),
            ([('start', None), ('run', ROOT), ('pass', ROOT), ('pass', None), ('output', None)], ('go:package_lifecycle',)))
        for rows, reasons in fixtures:
            with self.subTest(rows=rows):
                self.assertEqual(translate(go=go_bytes(rows)).reasons, reasons)
        self.assertEqual(translate(go=go_bytes().replace(PACKAGE.encode(), b'foreign')).reasons, ('go:package_mismatch',))
        self.assertEqual(translate(go=go_bytes([('start', None), ('output', None), ('run', ROOT), ('output', ROOT), ('pass', ROOT), ('pass', None)])).status, 'consistent')

    def test_inherited_go_parser_codes(self):
        fixtures = (
            (b'', 'events_count'), (b'\n', 'line_delimiter'), (b'{}\r\n', 'line_delimiter'),
            (b' ' * 1048577, 'line_size'), (b'{\n', 'json_invalid'),
            (b'{"a":1,"a":2}', 'json_duplicate_key'), (b'{"a":NaN}', 'json_nonfinite'),
            (b'[' * 33 + b']' * 33, 'json_depth'),
            (json.dumps({'a': 'x' * 65537}).encode(), 'json_string'),
            (b'{}', 'event_keys'), (b'[]', 'event_type'),
            (b'{"Time":"t","Action":"pause","Package":"p"}', 'unsupported_go_action'),
            (b'{}\n' * 65537, 'events_count'),
            (b'{"Time":"t","Action":"start","Package":"p","Test":"x"}', 'event_type'))
        for raw, code in fixtures:
            with self.subTest(code=code):
                with self.assertRaisesRegex(AdapterError, '^' + code + '$'):
                    adapter.parse_commerce_go_events(raw)
                self.assertEqual(translate(go=raw).reasons, ('go:' + code,))
        with self.assertRaisesRegex(AdapterError, '^input_type$'):
            adapter.parse_commerce_go_events(bytearray())


class CommerceParserConfigurationTests(unittest.TestCase):
    def test_expat_utf8_single_final_feed_and_rejecting_handlers(self):
        real = adapter.expat.ParserCreate
        created = []
        class Spy:
            def __init__(self, parser):
                object.__setattr__(self, 'parser', parser)
                object.__setattr__(self, 'calls', [])
            def __setattr__(self, key, val):
                setattr(self.parser, key, val)
            def Parse(self, raw, final):
                self.calls.append((raw, final, self.parser.buffer_text))
                return self.parser.Parse(raw, final)
        def create(**kwargs):
            self.assertEqual(kwargs, dict(encoding='UTF-8', namespace_separator=None))
            spy = Spy(real(**kwargs))
            created.append(spy)
            return spy
        raw = b'<testsuite/>'
        with patch.object(adapter.expat, 'ParserCreate', side_effect=create):
            self.assertEqual(adapter.parse_commerce_junit(raw), ())
        self.assertEqual(created[0].calls, [(raw, True, False)])
        for handler in ('StartDoctypeDeclHandler', 'EntityDeclHandler', 'ExternalEntityRefHandler', 'CommentHandler', 'ProcessingInstructionHandler', 'StartCdataSectionHandler', 'XmlDeclHandler'):
            with self.assertRaisesRegex(AdapterError, '^xml_forbidden$'):
                getattr(created[0].parser, handler)()
