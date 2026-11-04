"""Synthetic caller-selected catalog Go slots; no execution or artifact I/O."""
from dataclasses import dataclass
import hashlib
import json
import re

from scripts.dev.workshop_final180_identity_adapter import (
    parse_identity_events, GoEvent, AdapterError, SimulatedExit)

CANDIDATE = '4d82e413e04fb2401ac7bc28dc828375ac662180'
INVENTORY = 'c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39'
PACKAGE = 'github.com/lucronn/autodata/apps/api-go'
# Each provider, root, ID and retained-memory reference is literal and independent
# of caller text. Provider attribution is synthetic context, never authenticated.
SLOTS = (
    ('bankone', 'TestPostgresCatalogLifecycleColdHTTPRaceOneJob',
     'TestPostgresCatalogLifecycleColdHTTPRaceOneJob-bankone',
     ('r3/bankone/TestPostgresCatalogLifecycleColdHTTPRaceOneJob/go-events.jsonl',
      'r3/bankone/TestPostgresCatalogLifecycleColdHTTPRaceOneJob/go-stderr.log')),
    ('banktwo', 'TestPostgresCatalogLifecycleColdHTTPRaceOneJob',
     'TestPostgresCatalogLifecycleColdHTTPRaceOneJob-banktwo',
     ('r3/banktwo/TestPostgresCatalogLifecycleColdHTTPRaceOneJob/go-events.jsonl',
      'r3/banktwo/TestPostgresCatalogLifecycleColdHTTPRaceOneJob/go-stderr.log')),
    ('bankone', 'TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP',
     'TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP-bankone',
     ('r3/bankone/TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP/go-events.jsonl',
      'r3/bankone/TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP/go-stderr.log')),
    ('banktwo', 'TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP',
     'TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP-banktwo',
     ('r3/banktwo/TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP/go-events.jsonl',
      'r3/banktwo/TestPostgresCatalogLifecycleSourceReadableDuringActualModelHTTP/go-stderr.log')),
    ('bankone', 'TestPostgresCatalogLifecycleAtomicPublication',
     'TestPostgresCatalogLifecycleAtomicPublication-bankone',
     ('r3/bankone/TestPostgresCatalogLifecycleAtomicPublication/go-events.jsonl',
      'r3/bankone/TestPostgresCatalogLifecycleAtomicPublication/go-stderr.log')),
    ('banktwo', 'TestPostgresCatalogLifecycleAtomicPublication',
     'TestPostgresCatalogLifecycleAtomicPublication-banktwo',
     ('r3/banktwo/TestPostgresCatalogLifecycleAtomicPublication/go-events.jsonl',
      'r3/banktwo/TestPostgresCatalogLifecycleAtomicPublication/go-stderr.log')),
    ('bankone', 'TestPostgresCatalogLifecycleWarmReadsNoExternalCalls',
     'TestPostgresCatalogLifecycleWarmReadsNoExternalCalls-bankone',
     ('r3/bankone/TestPostgresCatalogLifecycleWarmReadsNoExternalCalls/go-events.jsonl',
      'r3/bankone/TestPostgresCatalogLifecycleWarmReadsNoExternalCalls/go-stderr.log')),
    ('banktwo', 'TestPostgresCatalogLifecycleWarmReadsNoExternalCalls',
     'TestPostgresCatalogLifecycleWarmReadsNoExternalCalls-banktwo',
     ('r3/banktwo/TestPostgresCatalogLifecycleWarmReadsNoExternalCalls/go-events.jsonl',
      'r3/banktwo/TestPostgresCatalogLifecycleWarmReadsNoExternalCalls/go-stderr.log')),
)
AUTHORITY = tuple((name, False) for name in (
    'fixture_verified', 'product_candidate_verified', 'staging_verified',
    'deployment_authorized', 'cutover_verified', 'implementation_authorized',
    'runtime_execution_authorized', 'profile_promotion_authorized', 'merge_authorized'))
PARSER_CODES = (
    'input_type', 'events_size', 'events_count', 'line_size', 'line_delimiter',
    'json_invalid', 'json_duplicate_key', 'json_nonfinite', 'json_depth',
    'json_string', 'event_keys', 'event_type', 'unsupported_go_action')
SEMANTIC_CODES = (
    'package_mismatch', 'unknown_test', 'package_lifecycle', 'root_lifecycle',
    'root_failed', 'root_skipped', 'package_failed', 'package_skipped',
    'simulated_nonzero', 'simulated_timeout', 'simulated_interrupted',
    'ownership_lost', 'cleanup_incomplete')
RECEIPT_CODES = SEMANTIC_CODES[-5:]
POISON_CODES = (
    'package_mismatch', 'unknown_test', 'package_lifecycle', 'root_lifecycle',
    'root_failed', 'package_failed', 'simulated_nonzero', 'simulated_timeout',
    'ownership_lost', 'cleanup_incomplete')


@dataclass(frozen=True)
class CatalogContext:
    candidate_sha: str
    inventory_sha256: str
    source_manifest_sha256: str


@dataclass(frozen=True)
class CatalogCase:
    provider: str
    go_test_name: str
    events_raw: bytes
    stderr_raw: bytes
    receipt: SimulatedExit


@dataclass(frozen=True)
class CatalogOutcome:
    family: str
    logical_id: str
    status: str
    raw_refs: tuple[str, ...]
    events_sha256: str
    stderr_sha256: str
    failures: tuple[str, ...]


@dataclass(frozen=True)
class CatalogDiagnostic:
    contract: str
    observation_kind: str
    candidate_sha: str
    inventory_sha256: str
    source_manifest_sha256: str
    status: str
    observations: tuple[CatalogOutcome, ...]
    accepted_case_credit: int
    profiles_enabled: bool
    enabled_tiers: tuple[str, ...]
    authority: tuple[tuple[str, bool], ...]


def _require(condition, code):
    if not condition:
        raise AdapterError(code)


def _digest(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _context(value):
    _require(type(value) is CatalogContext, 'context_invalid')
    _require(type(value.candidate_sha) is str and value.candidate_sha == CANDIDATE
             and type(value.inventory_sha256) is str and value.inventory_sha256 == INVENTORY
             and _digest(value.source_manifest_sha256), 'context_invalid')


def _receipt(value):
    _require(type(value) is SimulatedExit, 'receipt_invalid')
    _require(all(type(flag) is bool for flag in (value.timed_out, value.interrupted,
                 value.ownership_lost, value.cleanup_complete)), 'receipt_invalid')
    _require(value.exit_code is None or (type(value.exit_code) is int
                 and -255 <= value.exit_code <= 255), 'receipt_invalid')
    _require(value.exit_code is not None or value.timed_out or value.interrupted
             or value.ownership_lost or not value.cleanup_complete, 'receipt_invalid')


def _validate_inputs(cases, context):
    _context(context)
    _require(type(cases) is tuple and len(cases) == 8, 'cases_invalid')
    identities = []
    for case in cases:
        _require(type(case) is CatalogCase, 'cases_invalid')
        _require(type(case.provider) is str and type(case.go_test_name) is str
                 and (case.provider, case.go_test_name) in tuple(slot[:2] for slot in SLOTS),
                 'case_identity')
        identities.append((case.provider, case.go_test_name))
    _require(len(set(identities)) == 8, 'case_set')
    for case in cases:
        _require(type(case.events_raw) is bytes, 'input_type')
        _require(len(case.events_raw) <= 67108864, 'events_size')
        _require(type(case.stderr_raw) is bytes, 'stderr_type')
        _require(len(case.stderr_raw) <= 1048576, 'stderr_size')
    for case in cases:
        _receipt(case.receipt)
    _require(sum(len(case.events_raw) + len(case.stderr_raw) for case in cases) <= 68157440,
             'aggregate_size')


def parse_catalog_events(raw: bytes) -> tuple[GoEvent, ...]:
    """Delegate grammar only to the pinned public B1 parser, unchanged."""
    return parse_identity_events(raw)


def _receipt_failures(receipt):
    return tuple(code for flag, code in (
        (receipt.exit_code is not None and receipt.exit_code != 0, 'simulated_nonzero'),
        (receipt.timed_out, 'simulated_timeout'), (receipt.interrupted, 'simulated_interrupted'),
        (receipt.ownership_lost, 'ownership_lost'),
        (not receipt.cleanup_complete, 'cleanup_incomplete')) if flag)


def _row_status(failures):
    if any(code in PARSER_CODES for code in failures) or 'simulated_interrupted' in failures:
        return 'unavailable'
    if any(code in POISON_CODES for code in failures):
        return 'failed'
    if 'root_skipped' in failures or 'package_skipped' in failures:
        return 'skipped'
    return 'passed'


def _top_status(rows):
    if any('simulated_interrupted' in row.failures for row in rows):
        return 'interrupted'
    if any(row.status == 'unavailable' for row in rows):
        return 'unavailable'
    if any(row.status != 'passed' for row in rows):
        return 'inconsistent'
    return 'consistent'


def _semantic_failures(events, root, receipt_codes):
    failures = set(receipt_codes)
    if any(event.package != PACKAGE for event in events):
        failures.add('package_mismatch')
    if any(event.test is not None and event.test != root for event in events):
        failures.add('unknown_test')
    starts = [i for i, event in enumerate(events) if event.action == 'start']
    package_ends = [i for i, event in enumerate(events)
                    if event.test is None and event.action in ('pass', 'fail', 'skip')]
    package_ok = starts == [0] and package_ends == [len(events) - 1]
    if package_ok:
        package_ok = all(0 < i < package_ends[0] for i, event in enumerate(events)
                         if event.test is None and event.action == 'output')
    if not package_ok:
        failures.add('package_lifecycle')
    runs = [i for i, event in enumerate(events) if event.test == root and event.action == 'run']
    ends = [i for i, event in enumerate(events)
            if event.test == root and event.action in ('pass', 'fail', 'skip')]
    root_ok = len(runs) == len(ends) == 1 and runs[0] < ends[0]
    if root_ok:
        root_ok = (len(starts) == len(package_ends) == 1
                   and starts[0] < runs[0] < ends[0] < package_ends[0]
                   and all(runs[0] < i < ends[0] for i, event in enumerate(events)
                           if event.test == root and event.action == 'output'))
    if not root_ok:
        failures.add('root_lifecycle')
    for event in events:
        if event.test in (None, root) and event.action in ('fail', 'skip'):
            failures.add(('package' if event.test is None else 'root')
                         + ('_failed' if event.action == 'fail' else '_skipped'))
    return tuple(code for code in SEMANTIC_CODES if code in failures)


def translate_catalog(cases: tuple[CatalogCase, ...], context: CatalogContext) -> CatalogDiagnostic:
    """Translate eight caller-selected slots independently after full outer admission."""
    _validate_inputs(cases, context)
    by_identity = {(case.provider, case.go_test_name): case for case in cases}
    rows = []
    for provider, root, logical_id, refs in SLOTS:
        case = by_identity[(provider, root)]
        receipt_codes = _receipt_failures(case.receipt)
        try:
            events = parse_catalog_events(case.events_raw)
        except AdapterError as exc:
            failures = (str(exc),) + receipt_codes
        else:
            failures = _semantic_failures(events, root, receipt_codes)
        rows.append(CatalogOutcome('catalog', logical_id, _row_status(failures), refs,
                    hashlib.sha256(case.events_raw).hexdigest(),
                    hashlib.sha256(case.stderr_raw).hexdigest(), failures))
    return CatalogDiagnostic(
        'workshop-final180-catalog-go-synthetic-v1', 'simulated-source-profile-validation',
        context.candidate_sha, context.inventory_sha256, context.source_manifest_sha256,
        _top_status(rows), tuple(rows), 0, False, (), AUTHORITY)


def _validate_failures(failures):
    order = PARSER_CODES + SEMANTIC_CODES
    _require(type(failures) is tuple and len(failures) <= len(order)
             and all(type(code) is str and code in order for code in failures),
             'diagnostic_invalid')
    _require(len(set(failures)) == len(failures)
             and failures == tuple(sorted(failures, key=order.index)), 'diagnostic_invalid')
    parser_codes = tuple(code for code in failures if code in PARSER_CODES)
    _require(len(parser_codes) <= 1, 'diagnostic_invalid')
    if parser_codes:
        _require(all(code in RECEIPT_CODES for code in failures[1:]), 'diagnostic_invalid')


def serialize_catalog_diagnostic(value: CatalogDiagnostic) -> bytes:
    """Revalidate every claim before producing bounded canonical diagnostic bytes."""
    _require(type(value) is CatalogDiagnostic, 'diagnostic_invalid')
    _require(type(value.contract) is str
             and value.contract == 'workshop-final180-catalog-go-synthetic-v1'
             and type(value.observation_kind) is str
             and value.observation_kind == 'simulated-source-profile-validation',
             'diagnostic_invalid')
    _require(type(value.candidate_sha) is str and value.candidate_sha == CANDIDATE
             and type(value.inventory_sha256) is str and value.inventory_sha256 == INVENTORY
             and _digest(value.source_manifest_sha256), 'diagnostic_invalid')
    _require(type(value.accepted_case_credit) is int and value.accepted_case_credit == 0
             and value.profiles_enabled is False and type(value.enabled_tiers) is tuple
             and value.enabled_tiers == (), 'diagnostic_invalid')
    _require(type(value.authority) is tuple and len(value.authority) == 9, 'diagnostic_invalid')
    for pair, expected in zip(value.authority, AUTHORITY):
        _require(type(pair) is tuple and len(pair) == 2 and type(pair[0]) is str
                 and pair[0] == expected[0] and pair[1] is False, 'diagnostic_invalid')
    _require(type(value.observations) is tuple and len(value.observations) == 8,
             'diagnostic_invalid')
    observations = []
    for row, slot in zip(value.observations, SLOTS):
        _require(type(row) is CatalogOutcome, 'diagnostic_invalid')
        _require(type(row.family) is str and row.family == 'catalog'
                 and type(row.logical_id) is str and row.logical_id == slot[2]
                 and type(row.raw_refs) is tuple and len(row.raw_refs) == 2
                 and all(type(ref) is str and ref == expected
                         for ref, expected in zip(row.raw_refs, slot[3]))
                 and _digest(row.events_sha256) and _digest(row.stderr_sha256),
                 'diagnostic_invalid')
        _validate_failures(row.failures)
        _require(type(row.status) is str and row.status == _row_status(row.failures),
                 'diagnostic_invalid')
        observations.append(dict(family=row.family, logical_id=row.logical_id,
                                 status=row.status, raw_refs=row.raw_refs,
                                 events_sha256=row.events_sha256, stderr_sha256=row.stderr_sha256,
                                 failures=row.failures))
    _require(type(value.status) is str and value.status == _top_status(value.observations),
             'diagnostic_invalid')
    obj = dict(contract=value.contract, observation_kind=value.observation_kind,
               candidate_sha=value.candidate_sha, inventory_sha256=value.inventory_sha256,
               source_manifest_sha256=value.source_manifest_sha256, status=value.status,
               observations=observations, accepted_case_credit=0, profiles_enabled=False,
               enabled_tiers=(), authority=dict(value.authority))
    encoded = (json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                          allow_nan=False) + '\n').encode('utf-8')
    _require(len(encoded) <= 65536, 'diagnostic_invalid')
    return encoded
