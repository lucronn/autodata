"""Restricted synthetic commerce translation; no execution or artifact I/O authority."""
from dataclasses import dataclass
import hashlib
import json
import re
from xml.parsers import expat
from scripts.dev.workshop_final180_identity_adapter import (
    parse_identity_events, GoEvent, AdapterError, SimulatedExit)

CANDIDATE = '4d82e413e04fb2401ac7bc28dc828375ac662180'
INVENTORY = 'c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39'
CLASSNAME = 'tests.test_commerce_postgres'
PACKAGE = 'github.com/lucronn/autodata/apps/api-go'
ROOT = 'TestWorkshopCommercePythonIntegration'
COMMERCE_IDS = ('test_orders_create_and_owner_scope', 'test_same_key_replay_and_conflict', 'test_concurrent_keys_share_one_checkout', 'test_scope_races_single_active_grant', 'test_lost_create_response_and_retention_boundary', 'test_expiry_requires_remote_nonchargeable_proof', 'test_completion_races_expiry_without_recharge', 'test_webhook_before_create_response', 'test_settlement_binds_financial_owner_scope', 'test_duplicate_and_distinct_events_grant_once', 'test_refund_chargeback_ordering_and_monotonic_revocation', 'test_payment_survives_source_unavailable_and_restart', 'test_library_is_owner_only_and_paginated', 'test_grant_check_exact_scope_legacy_and_revoked')
SUPPORT_NAMES = ('test_migrations_are_numeric_and_ordered', 'test_customer_identity_migration_and_all_four_driver_boundaries', 'test_commerce_migration_has_structured_owner_and_financial_guards', 'test_dataset_request_ownership_is_backfilled_without_overwriting_existing_values', 'test_schema_migrations_cover_platform_spine_and_vector', 'test_foundation_fixture_is_separate_from_schema_migrations', 'test_chat_quote_revision_publication_state_and_immutability_are_database_enforced', 'test_price_snapshots_are_immutable_and_refresh_failures_are_separate', 'test_visual_artifacts_require_and_preserve_source_artifact_linkage', 'test_quote_arithmetic_and_overlap_bounds_are_database_enforced', 'test_quote_persists_required_and_recommended_operation_collections', 'test_quote_operation_categories_upgrade_existing_025_table', 'test_worker_events_persist_the_complete_event_envelope', 'test_reusable_derived_article_key_prevents_query_uniqueness_collisions', 'test_markup_is_structurally_prohibited', 'test_psql_command_includes_host_and_port_when_address_provided', 'test_resolve_database_address_respects_explicit_and_environment', 'test_emit_is_embedded_and_uses_one_session_lock', 'test_manifest_rejects_holes_unsafe_names_symlinks_and_wrong_stems', 'test_fixture_prefix_accepts_only_contiguous_canonical_prefix', 'test_default_refuses_truncated_manifest_before_sql_output', 'test_default_invocation_executes_identical_emit_output_and_cleans_tempfile', 'test_fixed_transaction_contract_is_audited', 'test_adapter_streams_one_driver_and_returns_only_actual_applications', 'test_adapter_propagates_generator_and_psql_failure', 'test_full_chain_restart_preserves_every_marker_and_schema', 'test_partial_catalog_row_survives_full_restart', 'test_empty_bootstrap_and_untracked_application_rejection[False]', 'test_empty_bootstrap_and_untracked_application_rejection[True]', 'test_invalid_ledger_fails_before_pending_application_ddl[unknown]', 'test_invalid_ledger_fails_before_pending_application_ddl[wrong_stem]', 'test_invalid_ledger_fails_before_pending_application_ddl[gap]', 'test_invalid_ledger_fails_before_pending_application_ddl[duplicate_shape]', 'test_invalid_ledger_fails_before_pending_application_ddl[wrong_timestamp]', 'test_original_038_adoption_and_markerless_033_effects_are_once_only', 'test_genuine_036_upgrade_preserves_jobs_and_matches_fresh_schema', 'test_migration_failure_rolls_back_only_active_file_then_retry[2]', 'test_migration_failure_rolls_back_only_active_file_then_retry[33]', 'test_migration_failure_rolls_back_only_active_file_then_retry[36]', 'test_migration_failure_rolls_back_only_active_file_then_retry[37]', 'test_migration_failure_rolls_back_only_active_file_then_retry[38]', 'test_migration_failure_rolls_back_only_active_file_then_retry[39]', 'test_migration_failure_rolls_back_only_active_file_then_retry[40]', 'test_recorded_001_and_partial_unmarked_next_file_remain_retryable', 'test_two_full_runners_serialize_and_apply_each_version_once[False]', 'test_two_full_runners_serialize_and_apply_each_version_once[True]', 'test_connection_death_releases_lock_and_rolls_back_active_file', 'test_restart_after_committed_037_only_applies_038_and_039', 'test_native_python_adapter_applies_then_skips_in_one_session', 'test_markerless_033_failure_rolls_back_reviewer_effects_and_marker', 'test_populated_publication_and_all_lifecycle_records_survive_restart', 'test_populated_038_upgrade_only_adds_identity_schema', 'test_populated_customer_identity_restart_preserves_rows_and_ledger')
COMMON_REFS = ('workshop-commerce-tests.xml', 'workshop-commerce-pytest.stdout.log', 'workshop-commerce-pytest.stderr.log')
GO_REFS = ('workshop-commerce-go-events.jsonl', 'workshop-commerce-go-stderr.log')
AUTHORITY = tuple((name, False) for name in (
    'fixture_verified', 'product_candidate_verified', 'staging_verified',
    'deployment_authorized', 'cutover_verified', 'implementation_authorized',
    'runtime_execution_authorized', 'profile_promotion_authorized', 'merge_authorized'))
XML_PARSER = ('xml_encoding', 'xml_forbidden', 'xml_invalid', 'xml_nodes',
              'xml_depth', 'xml_structure', 'xml_string', 'xml_text')
XML_SEMANTIC = ('case_count', 'unknown_case', 'identity_mismatch', 'duplicate_case',
                'missing_case', 'testcase_failure', 'testcase_error', 'testcase_skipped')
GO_PARSER = ('events_count', 'line_size', 'line_delimiter', 'json_invalid',
             'json_duplicate_key', 'json_nonfinite', 'json_depth', 'json_string',
             'event_keys', 'event_type', 'unsupported_go_action')
GO_SEMANTIC = ('package_mismatch', 'unknown_test', 'package_lifecycle', 'root_lifecycle',
               'root_failed', 'root_skipped', 'package_failed', 'package_skipped')
RECEIPT_CODES = ('simulated_nonzero', 'simulated_timeout', 'simulated_interrupted',
                 'ownership_lost', 'cleanup_incomplete')
REASONS = (tuple('xml:' + c for c in XML_PARSER + XML_SEMANTIC)
           + ('go:support_absent',) + tuple('go:' + c for c in GO_PARSER + GO_SEMANTIC)
           + tuple('pytest:' + c for c in RECEIPT_CODES)
           + tuple('go:' + c for c in RECEIPT_CODES))


@dataclass(frozen=True)
class CommerceContext:
    candidate_sha: str
    inventory_sha256: str
    source_manifest_sha256: str


@dataclass(frozen=True)
class CommerceGoSupport:
    events_raw: bytes
    stderr_raw: bytes
    receipt: SimulatedExit


@dataclass(frozen=True)
class CommerceInput:
    junit_raw: bytes
    pytest_stdout_raw: bytes
    pytest_stderr_raw: bytes
    pytest_receipt: SimulatedExit
    go_support: CommerceGoSupport | None


@dataclass(frozen=True)
class JUnitCase:
    classname: str
    name: str
    terminal: str | None


@dataclass(frozen=True)
class CommerceOutcome:
    family: str
    logical_id: str
    status: str
    raw_refs: tuple[str, ...]


@dataclass(frozen=True)
class CommerceDiagnostic:
    contract: str
    observation_kind: str
    candidate_sha: str
    inventory_sha256: str
    source_manifest_sha256: str
    junit_sha256: str
    pytest_stdout_sha256: str
    pytest_stderr_sha256: str
    go_support_present: bool
    go_events_sha256: str | None
    go_stderr_sha256: str | None
    pytest_receipt: SimulatedExit
    go_receipt: SimulatedExit | None
    status: str
    observations: tuple[CommerceOutcome, ...]
    reasons: tuple[str, ...]
    accepted_case_credit: int
    profiles_enabled: bool
    enabled_tiers: tuple[str, ...]
    authority: tuple[tuple[str, bool], ...]
    runtime_lock: None
    run_record: None


def _require(condition, code):
    if not condition:
        raise AdapterError(code)


def _digest(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _context(value):
    _require(type(value) is CommerceContext, 'context_invalid')
    _require(type(value.candidate_sha) is str and value.candidate_sha == CANDIDATE
             and type(value.inventory_sha256) is str and value.inventory_sha256 == INVENTORY
             and _digest(value.source_manifest_sha256), 'context_invalid')


def _receipt(value):
    _require(type(value) is SimulatedExit, 'receipt_invalid')
    _require(value.exit_code is None or (type(value.exit_code) is int
             and -255 <= value.exit_code <= 255), 'receipt_invalid')
    _require(all(type(v) is bool for v in (value.timed_out, value.interrupted,
             value.ownership_lost, value.cleanup_complete)), 'receipt_invalid')
    _require(value.exit_code is not None or value.timed_out or value.interrupted
             or value.ownership_lost or not value.cleanup_complete, 'receipt_invalid')


def _outer(value, context):
    _context(context)
    _require(type(value) is CommerceInput, 'input_invalid')
    streams = (value.junit_raw, value.pytest_stdout_raw, value.pytest_stderr_raw)
    for raw in streams:
        _require(type(raw) is bytes, 'input_type')
    support = value.go_support
    _require(support is None or type(support) is CommerceGoSupport, 'go_support_invalid')
    if support is not None:
        for raw in (support.events_raw, support.stderr_raw):
            _require(type(raw) is bytes, 'input_type')
        streams += (support.events_raw, support.stderr_raw)
    for raw, limit, code in zip(streams, (4194304, 1048576, 1048576, 67108864, 1048576),
                                ('junit_size', 'pytest_stdout_size', 'pytest_stderr_size', 'events_size', 'stderr_size')):
        _require(len(raw) <= limit, code)
    _receipt(value.pytest_receipt)
    if support is not None:
        _receipt(support.receipt)
    _require(sum(len(raw) for raw in streams) <= 74448896, 'aggregate_size')


class _CharacterData:
    """Production checker retains counters across Expat callback segments."""
    def __init__(self):
        self.total = 0
        self.terminal = None

    def check(self, text):
        for char in text:
            width = len(char.encode('utf-8'))
            self.total += width
            _require(self.total <= 1048576, 'xml_text')
            if self.terminal is not None:
                self.terminal += width
                _require(self.terminal <= 4096, 'xml_text')
            else:
                _require(char in ' \t\n\r', 'xml_structure')


def _forbidden(*_):
    raise AdapterError('xml_forbidden')


def parse_commerce_junit(raw: bytes) -> tuple[JUnitCase, ...]:
    _require(type(raw) is bytes, 'input_type')
    _require(len(raw) <= 4194304, 'junit_size')
    try:
        raw.decode('utf-8')
    except UnicodeError:
        raise AdapterError('xml_encoding') from None
    _require(not raw.startswith(b'\xef\xbb\xbf') and b'<?' not in raw and b'<!' not in raw, 'xml_forbidden')
    parser = expat.ParserCreate(encoding='UTF-8', namespace_separator=None)
    parser.buffer_text = False
    characters = _CharacterData()
    stack = []
    cases = []
    nodes = 0
    current = None

    def start(tag, attrs):
        nonlocal nodes, current
        nodes += 1
        depth = len(stack) + 1
        _require(nodes <= 256, 'xml_nodes')
        _require(depth <= 3, 'xml_depth')
        if depth == 1:
            _require(tag == 'testsuite' and not attrs, 'xml_structure')
        elif depth == 2:
            _require(tag == 'testcase' and set(attrs) == {'classname', 'name'}, 'xml_structure')
            for key in ('classname', 'name'):
                item = attrs[key]
                _require(type(item) is str and bool(item) and len(item.encode('utf-8')) <= 1024, 'xml_string')
            current = JUnitCase(attrs['classname'], attrs['name'], None)
        else:
            _require(tag in ('failure', 'error', 'skipped') and not attrs
                     and current.terminal is None, 'xml_structure')
            current = JUnitCase(current.classname, current.name, tag)
            characters.terminal = 0
        stack.append(tag)

    def end(tag):
        nonlocal current
        if len(stack) == 3:
            characters.terminal = None
        elif len(stack) == 2:
            cases.append(current)
            current = None
        stack.pop()

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = characters.check
    parser.StartDoctypeDeclHandler = _forbidden
    parser.EntityDeclHandler = _forbidden
    parser.ExternalEntityRefHandler = _forbidden
    parser.CommentHandler = _forbidden
    parser.ProcessingInstructionHandler = _forbidden
    parser.StartCdataSectionHandler = _forbidden
    parser.XmlDeclHandler = _forbidden
    try:
        parser.Parse(raw, True)
    except expat.ExpatError:
        raise AdapterError('xml_invalid') from None
    return tuple(cases)


def parse_commerce_go_events(raw: bytes) -> tuple[GoEvent, ...]:
    return parse_identity_events(raw)


def _xml_facts(cases):
    facts = set()
    expected = COMMERCE_IDS + SUPPORT_NAMES
    counts = dict.fromkeys(expected, 0)
    if len(cases) != 67:
        facts.add('xml:case_count')
    for case in cases:
        if case.name not in counts:
            facts.add('xml:unknown_case')
        else:
            counts[case.name] += 1
            if ((case.name in COMMERCE_IDS and case.classname != CLASSNAME)
                    or (case.name in SUPPORT_NAMES and case.classname == CLASSNAME)):
                facts.add('xml:identity_mismatch')
        if case.terminal is not None:
            facts.add('xml:testcase_' + case.terminal)
    if any(n > 1 for n in counts.values()):
        facts.add('xml:duplicate_case')
    if any(n == 0 for n in counts.values()):
        facts.add('xml:missing_case')
    return facts


def _go_facts(events):
    facts = set()
    if any(e.package != PACKAGE for e in events):
        facts.add('go:package_mismatch')
    if any(e.test is not None and e.test != ROOT for e in events):
        facts.add('go:unknown_test')
    starts = [i for i, e in enumerate(events) if e.action == 'start']
    ends = [i for i, e in enumerate(events) if e.test is None and e.action in ('pass', 'fail', 'skip')]
    package_valid = starts == [0] and ends == [len(events) - 1]
    if package_valid:
        package_valid = all(0 < i < ends[0] for i, e in enumerate(events) if e.test is None and e.action == 'output')
    if not package_valid:
        facts.add('go:package_lifecycle')
    runs = [i for i, e in enumerate(events) if e.test == ROOT and e.action == 'run']
    terminals = [i for i, e in enumerate(events) if e.test == ROOT and e.action in ('pass', 'fail', 'skip')]
    root_valid = len(runs) == len(terminals) == 1 and runs[0] < terminals[0]
    if root_valid:
        root_valid = all(runs[0] < i < terminals[0] for i, e in enumerate(events) if e.test == ROOT and e.action == 'output')
    if root_valid and package_valid:
        root_valid = 0 < runs[0] < terminals[0] < ends[0]
    if not root_valid:
        facts.add('go:root_lifecycle')
    for name, suffix in ((ROOT, 'root'), (None, 'package')):
        for action, code in (('fail', 'failed'), ('skip', 'skipped')):
            if any(e.test == name and e.action == action for e in events):
                facts.add('go:' + suffix + '_' + code)
    return facts


def _receipt_facts(receipt, prefix):
    flags = (receipt.exit_code is not None and receipt.exit_code != 0, receipt.timed_out,
             receipt.interrupted, receipt.ownership_lost, not receipt.cleanup_complete)
    return {prefix + ':' + code for flag, code in zip(flags, RECEIPT_CODES) if flag}


def _interrupted(reasons, prefix):
    return any(prefix + ':' + c in reasons for c in RECEIPT_CODES[1:])


def _statuses(reasons):
    xml_parser = any('xml:' + c in reasons for c in XML_PARSER)
    go_parser = any('go:' + c in reasons for c in GO_PARSER)
    absent = 'go:support_absent' in reasons
    py_interrupt = _interrupted(reasons, 'pytest')
    go_interrupt = _interrupted(reasons, 'go')
    baseline = ('unavailable' if xml_parser or py_interrupt else
                'failed' if any(r.startswith(('xml:', 'pytest:')) for r in reasons) else 'passed')
    local = ('unavailable' if absent or go_parser or go_interrupt else
             'failed' if any(r.startswith('go:') for r in reasons) else 'passed')
    severity = ('passed', 'failed', 'unavailable')
    first = severity[max(severity.index(baseline), severity.index(local))]
    rows = (first,) + (baseline,) * 13
    top = ('unavailable' if xml_parser or go_parser or absent else
           'interrupted' if py_interrupt or go_interrupt else
           'inconsistent' if any(s != 'passed' for s in rows) else 'consistent')
    return rows, top


def translate_commerce(value: CommerceInput, context: CommerceContext) -> CommerceDiagnostic:
    _outer(value, context)
    support = value.go_support
    facts = _receipt_facts(value.pytest_receipt, 'pytest')
    try:
        facts.update(_xml_facts(parse_commerce_junit(value.junit_raw)))
    except AdapterError as exc:
        facts.add('xml:' + str(exc))
    if support is None:
        facts.add('go:support_absent')
    else:
        facts.update(_receipt_facts(support.receipt, 'go'))
        try:
            facts.update(_go_facts(parse_commerce_go_events(support.events_raw)))
        except AdapterError as exc:
            facts.add('go:' + str(exc))
    reasons = tuple(r for r in REASONS if r in facts)
    statuses, top = _statuses(reasons)
    rows = tuple(CommerceOutcome('commerce', name, status,
                 COMMON_REFS + GO_REFS if i == 0 and support is not None else COMMON_REFS)
                 for i, (name, status) in enumerate(zip(COMMERCE_IDS, statuses)))
    return CommerceDiagnostic(
        'workshop-final180-commerce-synthetic-v1', 'simulated-source-profile-validation',
        context.candidate_sha, context.inventory_sha256, context.source_manifest_sha256,
        hashlib.sha256(value.junit_raw).hexdigest(), hashlib.sha256(value.pytest_stdout_raw).hexdigest(),
        hashlib.sha256(value.pytest_stderr_raw).hexdigest(), support is not None,
        None if support is None else hashlib.sha256(support.events_raw).hexdigest(),
        None if support is None else hashlib.sha256(support.stderr_raw).hexdigest(),
        value.pytest_receipt, None if support is None else support.receipt,
        top, rows, reasons, 0, False, (), AUTHORITY, None, None)
