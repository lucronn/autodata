"""Restricted synthetic paid slots: caller bytes and claims, zero execution authority."""
from dataclasses import dataclass
import hashlib
import json
import re

from scripts.dev.workshop_final180_identity_adapter import (
    parse_identity_events, GoEvent, AdapterError, SimulatedExit)

CANDIDATE = '4d82e413e04fb2401ac7bc28dc828375ac662180'
INVENTORY = 'c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39'
PACKAGE = 'github.com/lucronn/autodata/apps/api-go'
SLOTS = (
    ('bankone', 'TestPostgresPaidCatalogGrantBeforeWork',
     'TestPostgresPaidCatalogGrantBeforeWork-bankone',
     ('paid-access/bankone/TestPostgresPaidCatalogGrantBeforeWork/go-events.jsonl',
      'paid-access/bankone/TestPostgresPaidCatalogGrantBeforeWork/go-stderr.log')),
    ('banktwo', 'TestPostgresPaidCatalogGrantBeforeWork',
     'TestPostgresPaidCatalogGrantBeforeWork-banktwo',
     ('paid-access/banktwo/TestPostgresPaidCatalogGrantBeforeWork/go-events.jsonl',
      'paid-access/banktwo/TestPostgresPaidCatalogGrantBeforeWork/go-stderr.log')),
    ('bankone', 'TestPostgresPaidCatalogExactScopeAndOwnerIsolation',
     'TestPostgresPaidCatalogExactScopeAndOwnerIsolation-bankone',
     ('paid-access/bankone/TestPostgresPaidCatalogExactScopeAndOwnerIsolation/go-events.jsonl',
      'paid-access/bankone/TestPostgresPaidCatalogExactScopeAndOwnerIsolation/go-stderr.log')),
    ('banktwo', 'TestPostgresPaidCatalogExactScopeAndOwnerIsolation',
     'TestPostgresPaidCatalogExactScopeAndOwnerIsolation-banktwo',
     ('paid-access/banktwo/TestPostgresPaidCatalogExactScopeAndOwnerIsolation/go-events.jsonl',
      'paid-access/banktwo/TestPostgresPaidCatalogExactScopeAndOwnerIsolation/go-stderr.log')),
    ('bankone', 'TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse',
     'TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse-bankone',
     ('paid-access/bankone/TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse/go-events.jsonl',
      'paid-access/bankone/TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse/go-stderr.log')),
    ('banktwo', 'TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse',
     'TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse-banktwo',
     ('paid-access/banktwo/TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse/go-events.jsonl',
      'paid-access/banktwo/TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse/go-stderr.log')),
    ('bankone', 'TestPostgresPaidCatalogContextualMediaAndRevocation',
     'TestPostgresPaidCatalogContextualMediaAndRevocation-bankone',
     ('paid-access/bankone/TestPostgresPaidCatalogContextualMediaAndRevocation/go-events.jsonl',
      'paid-access/bankone/TestPostgresPaidCatalogContextualMediaAndRevocation/go-stderr.log')),
    ('banktwo', 'TestPostgresPaidCatalogContextualMediaAndRevocation',
     'TestPostgresPaidCatalogContextualMediaAndRevocation-banktwo',
     ('paid-access/banktwo/TestPostgresPaidCatalogContextualMediaAndRevocation/go-events.jsonl',
      'paid-access/banktwo/TestPostgresPaidCatalogContextualMediaAndRevocation/go-stderr.log')),
    ('bankone', 'TestPostgresPaidCatalogHistoricalSourceAndRights',
     'TestPostgresPaidCatalogHistoricalSourceAndRights-bankone',
     ('paid-access/bankone/TestPostgresPaidCatalogHistoricalSourceAndRights/go-events.jsonl',
      'paid-access/bankone/TestPostgresPaidCatalogHistoricalSourceAndRights/go-stderr.log')),
    ('banktwo', 'TestPostgresPaidCatalogHistoricalSourceAndRights',
     'TestPostgresPaidCatalogHistoricalSourceAndRights-banktwo',
     ('paid-access/banktwo/TestPostgresPaidCatalogHistoricalSourceAndRights/go-events.jsonl',
      'paid-access/banktwo/TestPostgresPaidCatalogHistoricalSourceAndRights/go-stderr.log')),
    ('bankone', 'TestPostgresPaidCatalogCustomerLegacyRoutesDenied',
     'TestPostgresPaidCatalogCustomerLegacyRoutesDenied-bankone',
     ('paid-access/bankone/TestPostgresPaidCatalogCustomerLegacyRoutesDenied/go-events.jsonl',
      'paid-access/bankone/TestPostgresPaidCatalogCustomerLegacyRoutesDenied/go-stderr.log')),
    ('banktwo', 'TestPostgresPaidCatalogCustomerLegacyRoutesDenied',
     'TestPostgresPaidCatalogCustomerLegacyRoutesDenied-banktwo',
     ('paid-access/banktwo/TestPostgresPaidCatalogCustomerLegacyRoutesDenied/go-events.jsonl',
      'paid-access/banktwo/TestPostgresPaidCatalogCustomerLegacyRoutesDenied/go-stderr.log')),
)

AUTHORITY = (
    ('fixture_verified', False),
    ('product_candidate_verified', False),
    ('staging_verified', False),
    ('deployment_authorized', False),
    ('cutover_verified', False),
    ('implementation_authorized', False),
    ('runtime_execution_authorized', False),
    ('profile_promotion_authorized', False),
    ('merge_authorized', False),
)

PARSER_CODES = (
    'input_type', 'events_size', 'events_count', 'line_size', 'line_delimiter',
    'json_invalid', 'json_duplicate_key', 'json_nonfinite', 'json_depth',
    'json_string', 'event_keys', 'event_type', 'unsupported_go_action',
)

SEMANTIC_CODES = (
    'package_mismatch', 'unknown_test', 'package_lifecycle', 'root_lifecycle',
    'root_failed', 'root_skipped', 'package_failed', 'package_skipped',
    'simulated_nonzero', 'simulated_timeout', 'simulated_interrupted',
    'ownership_lost', 'cleanup_incomplete',
)
RECEIPT_CODES = SEMANTIC_CODES[-5:]
POISON_CODES = (
    'package_mismatch', 'unknown_test', 'package_lifecycle', 'root_lifecycle',
    'root_failed', 'package_failed', 'simulated_nonzero', 'simulated_timeout',
    'ownership_lost', 'cleanup_incomplete',
)

@dataclass(frozen=True)
class PaidContext:
    candidate_sha: str
    inventory_sha256: str
    source_manifest_sha256: str

@dataclass(frozen=True)
class PaidCase:
    provider: str
    go_test_name: str
    events_raw: bytes
    stderr_raw: bytes
    receipt: SimulatedExit

@dataclass(frozen=True)
class PaidOutcome:
    family: str
    logical_id: str
    status: str
    raw_refs: tuple[str, ...]
    events_sha256: str
    stderr_sha256: str
    failures: tuple[str, ...]

@dataclass(frozen=True)
class PaidDiagnostic:
    contract: str
    observation_kind: str
    candidate_sha: str
    inventory_sha256: str
    source_manifest_sha256: str
    status: str
    observations: tuple[PaidOutcome, ...]
    accepted_case_credit: int
    profiles_enabled: bool
    enabled_tiers: tuple[str, ...]
    authority: tuple[tuple[str, bool], ...]

def _require(condition, code):
    if not condition:
        raise AdapterError(code)


def _require_fields(value, names, code):
    # Exact frozen dataclasses can still be allocated without initialization.
    _require(all(name in value.__dict__ for name in names), code)


def _digest(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _admit(cases, context):
    _require(type(context) is PaidContext, 'context_invalid')
    _require_fields(context, ('candidate_sha', 'inventory_sha256', 'source_manifest_sha256'),
                    'context_invalid')
    _require(type(context.candidate_sha) is str and context.candidate_sha == CANDIDATE
             and type(context.inventory_sha256) is str and context.inventory_sha256 == INVENTORY
             and _digest(context.source_manifest_sha256), 'context_invalid')
    _require(type(cases) is tuple and len(cases) == 12, 'cases_invalid')
    pairs = []
    for case in cases:
        _require(type(case) is PaidCase, 'cases_invalid')
        _require_fields(case, ('provider', 'go_test_name'), 'case_identity')
        _require(type(case.provider) is str and type(case.go_test_name) is str
                 and (case.provider, case.go_test_name) in tuple(slot[:2] for slot in SLOTS),
                 'case_identity')
        pairs.append((case.provider, case.go_test_name))
    _require(len(set(pairs)) == 12, 'case_set')
    for case in cases:
        _require_fields(case, ('events_raw',), 'input_type')
        _require(type(case.events_raw) is bytes, 'input_type')
        _require(len(case.events_raw) <= 67108864, 'events_size')
        _require_fields(case, ('stderr_raw',), 'stderr_type')
        _require(type(case.stderr_raw) is bytes, 'stderr_type')
        _require(len(case.stderr_raw) <= 1048576, 'stderr_size')
    for case in cases:
        _require_fields(case, ('receipt',), 'receipt_invalid')
        receipt = case.receipt
        _require(type(receipt) is SimulatedExit, 'receipt_invalid')
        _require_fields(receipt, ('exit_code', 'timed_out', 'interrupted', 'ownership_lost',
                                 'cleanup_complete'), 'receipt_invalid')
        _require(all(type(flag) is bool for flag in (receipt.timed_out, receipt.interrupted,
                 receipt.ownership_lost, receipt.cleanup_complete)), 'receipt_invalid')
        _require(receipt.exit_code is None or (type(receipt.exit_code) is int
                 and -255 <= receipt.exit_code <= 255), 'receipt_invalid')
        _require(receipt.exit_code is not None or receipt.timed_out or receipt.interrupted
                 or receipt.ownership_lost or not receipt.cleanup_complete, 'receipt_invalid')
    _require(sum(len(case.events_raw) + len(case.stderr_raw) for case in cases) <= 68157440,
             'aggregate_size')


def parse_paid_events(raw: bytes) -> tuple[GoEvent, ...]:
    """Preserve the pinned parser's first-raised error without preprocessing."""
    return parse_identity_events(raw)


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


def translate_paid(cases: tuple[PaidCase, ...], context: PaidContext) -> PaidDiagnostic:
    """Admit all twelve supplied slots before interpreting any byte stream."""
    _admit(cases, context)
    indexed = {(case.provider, case.go_test_name): case for case in cases}
    rows = []
    for provider, root, logical_id, refs in SLOTS:
        case = indexed[(provider, root)]
        receipt = case.receipt
        receipt_codes = tuple(code for flag, code in (
            (receipt.exit_code is not None and receipt.exit_code != 0, 'simulated_nonzero'),
            (receipt.timed_out, 'simulated_timeout'),
            (receipt.interrupted, 'simulated_interrupted'),
            (receipt.ownership_lost, 'ownership_lost'),
            (not receipt.cleanup_complete, 'cleanup_incomplete')) if flag)
        try:
            events = parse_paid_events(case.events_raw)
        except AdapterError as exc:
            failures = (str(exc),) + receipt_codes
        else:
            failures = _semantic_failures(events, root, receipt_codes)
        rows.append(PaidOutcome('paid', logical_id, _row_status(failures), refs,
                    hashlib.sha256(case.events_raw).hexdigest(),
                    hashlib.sha256(case.stderr_raw).hexdigest(), failures))
    return PaidDiagnostic('workshop-final180-paid-go-synthetic-v1',
        'simulated-source-profile-validation', context.candidate_sha, context.inventory_sha256,
        context.source_manifest_sha256, _top_status(rows), tuple(rows), 0, False, (), AUTHORITY)


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


def serialize_paid_diagnostic(value: PaidDiagnostic) -> bytes:
    """Revalidate synthetic claims and emit bounded canonical JSON, never raw text."""
    _require(type(value) is PaidDiagnostic, 'diagnostic_invalid')
    _require_fields(value, ('contract', 'observation_kind', 'candidate_sha', 'inventory_sha256',
                           'source_manifest_sha256', 'status', 'observations',
                           'accepted_case_credit', 'profiles_enabled', 'enabled_tiers',
                           'authority'), 'diagnostic_invalid')
    _require(type(value.contract) is str and value.contract == 'workshop-final180-paid-go-synthetic-v1'
             and type(value.observation_kind) is str
             and value.observation_kind == 'simulated-source-profile-validation', 'diagnostic_invalid')
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
    _require(type(value.observations) is tuple and len(value.observations) == 12,
             'diagnostic_invalid')
    observations = []
    for row, slot in zip(value.observations, SLOTS):
        _require(type(row) is PaidOutcome, 'diagnostic_invalid')
        _require_fields(row, ('family', 'logical_id', 'status', 'raw_refs', 'events_sha256',
                              'stderr_sha256', 'failures'), 'diagnostic_invalid')
        _require(type(row.family) is str and row.family == 'paid'
                 and type(row.logical_id) is str and row.logical_id == slot[2]
                 and type(row.raw_refs) is tuple and len(row.raw_refs) == 2
                 and all(type(ref) is str and ref == expected
                         for ref, expected in zip(row.raw_refs, slot[3]))
                 and _digest(row.events_sha256) and _digest(row.stderr_sha256), 'diagnostic_invalid')
        _validate_failures(row.failures)
        _require(type(row.status) is str and row.status == _row_status(row.failures),
                 'diagnostic_invalid')
        observations.append(dict(family=row.family, logical_id=row.logical_id, status=row.status,
            raw_refs=row.raw_refs, events_sha256=row.events_sha256, stderr_sha256=row.stderr_sha256,
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
