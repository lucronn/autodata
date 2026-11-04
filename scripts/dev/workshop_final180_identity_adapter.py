"""Bounded synthetic identity translation. No execution or artifact I/O authority."""
from dataclasses import dataclass
import hashlib
import json
import math
import re

CANDIDATE = '4d82e413e04fb2401ac7bc28dc828375ac662180'
INVENTORY = 'c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39'
PACKAGE = 'github.com/lucronn/autodata/apps/api-go'
ROOT = 'TestPostgresAuthSessionsIntegration'
IDENTITY_IDS = tuple(ROOT + '/' + name for name in (
    'ConcurrentCustomerProvisionAndRotation', 'SharedSessionRevocation',
    'ExpiryAndPersistedSecrecy', 'FirebaseExchangeAndUserRevocation',
    'FirebaseStartupRequiresMigratedPostgres'))
RAW_REFS = ('r5-access-go-events.jsonl', 'r5-access-go-stderr.log')
AUTHORITY = tuple((name, False) for name in (
    'fixture_verified', 'product_candidate_verified', 'staging_verified',
    'deployment_authorized', 'cutover_verified', 'implementation_authorized',
    'runtime_execution_authorized', 'profile_promotion_authorized', 'merge_authorized'))
EVENTS_LIMIT = 67108864
STDERR_LIMIT = 1048576
PARSER_CODES = (
    'input_type', 'events_size', 'events_count', 'line_size', 'line_delimiter',
    'json_invalid', 'json_duplicate_key', 'json_nonfinite', 'json_depth',
    'json_string', 'event_keys', 'event_type', 'unsupported_go_action')
SEMANTIC_CODES = (
    'package_mismatch', 'unknown_test', 'package_lifecycle', 'root_lifecycle',
    *(f'child_lifecycle:{i}' for i in range(5)), 'root_failed', 'root_skipped',
    'package_failed', 'package_skipped', *(f'child_failed:{i}' for i in range(5)),
    *(f'child_skipped:{i}' for i in range(5)), 'simulated_nonzero',
    'simulated_timeout', 'simulated_interrupted', 'ownership_lost', 'cleanup_incomplete')


class AdapterError(ValueError):
    """A stable code only; never embeds source strings or decoder exceptions."""


@dataclass(frozen=True)
class IdentityContext:
    candidate_sha: str
    inventory_sha256: str
    source_manifest_sha256: str


@dataclass(frozen=True)
class GoEvent:
    time: str
    action: str
    package: str
    test: str | None
    elapsed: int | float | None
    output: str | None
    failed_build: str | None


@dataclass(frozen=True)
class SimulatedExit:
    exit_code: int | None
    timed_out: bool
    interrupted: bool
    ownership_lost: bool
    cleanup_complete: bool


@dataclass(frozen=True)
class CaseOutcome:
    family: str
    logical_id: str
    status: str
    raw_refs: tuple[str, ...]


@dataclass(frozen=True)
class IdentityDiagnostic:
    contract: str
    observation_kind: str
    candidate_sha: str
    inventory_sha256: str
    source_manifest_sha256: str
    events_sha256: str
    stderr_sha256: str
    status: str
    observations: tuple[CaseOutcome, ...]
    failures: tuple[str, ...]
    accepted_case_credit: int
    profiles_enabled: bool
    enabled_tiers: tuple[str, ...]
    authority: tuple[tuple[str, bool], ...]


@dataclass(frozen=True)
class FakeFrame:
    at_ns: int
    kind: str
    data: bytes
    code: int | None


@dataclass(frozen=True)
class FakeReplay:
    result: SimulatedExit
    stdout: bytes
    stderr: bytes
    decisions: tuple[tuple[int, str], ...]


def _require(condition, code):
    if not condition:
        raise AdapterError(code)


def _digest(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _context(value):
    _require(type(value) is IdentityContext, 'context_invalid')
    _require(type(value.candidate_sha) is str and value.candidate_sha == CANDIDATE
             and type(value.inventory_sha256) is str and value.inventory_sha256 == INVENTORY
             and _digest(value.source_manifest_sha256), 'context_invalid')


def _receipt(value):
    _require(type(value) is SimulatedExit, 'receipt_invalid')
    _require(all(type(v) is bool for v in (value.timed_out, value.interrupted,
                 value.ownership_lost, value.cleanup_complete)), 'receipt_invalid')
    _require(value.exit_code is None or (type(value.exit_code) is int
                 and -255 <= value.exit_code <= 255), 'receipt_invalid')
    _require(value.exit_code is not None or value.timed_out or value.interrupted
             or value.ownership_lost or not value.cleanup_complete, 'receipt_invalid')


def _outer(raw):
    _require(type(raw) is bytes, 'input_type')
    _require(len(raw) <= EVENTS_LIMIT, 'events_size')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, 'json_duplicate_key')
        result[key] = value
    return result


def _nonfinite(_):
    raise AdapterError('json_nonfinite')


def _depth(text):
    # Bound the decoder before invoking it, respecting quoted/escaped delimiters.
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '[{':
            depth += 1
            _require(depth <= 32, 'json_depth')
        elif char in ']}':
            depth -= 1


def _strings(value):
    if type(value) is str:
        try:
            size = len(value.encode('utf-8'))
        except UnicodeError:
            raise AdapterError('json_string') from None
        _require(size <= 65536, 'json_string')
    elif type(value) is dict:
        for key, item in value.items():
            _strings(key)
            _strings(item)
    elif type(value) is list:
        for item in value:
            _strings(item)


def _text(value, limit, empty=False):
    return type(value) is str and (empty or bool(value)) and len(value.encode('utf-8')) <= limit


def parse_identity_events(raw: bytes) -> tuple[GoEvent, ...]:
    _outer(raw)
    _require(bool(raw), 'events_count')
    body = raw[:-1] if raw.endswith(b'\n') else raw
    lines = body.split(b'\n')
    _require(len(lines) <= 65536, 'events_count')
    events = []
    for line in lines:
        _require(bool(line) and b'\r' not in line, 'line_delimiter')
        _require(len(line) <= 1048576, 'line_size')
        try:
            text = line.decode('utf-8')
            _depth(text)
            row = json.loads(text, object_pairs_hook=_pairs, parse_constant=_nonfinite)
        except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
            if type(exc) is AdapterError:
                raise
            raise AdapterError('json_invalid') from None
        _strings(row)
        _require(type(row) is dict, 'event_type')
        _require({'Time', 'Action', 'Package'} <= row.keys()
                 and row.keys() <= {'Time', 'Action', 'Package', 'Test', 'Elapsed', 'Output', 'FailedBuild'},
                 'event_keys')
        _require(all(v is not None for v in row.values()), 'event_type')
        _require(_text(row['Time'], 128) and _text(row['Package'], 256)
                 and type(row['Action']) is str, 'event_type')
        action = row['Action']
        _require(action in ('start', 'run', 'output', 'pass', 'fail', 'skip'), 'unsupported_go_action')
        test = row.get('Test')
        elapsed = row.get('Elapsed')
        output = row.get('Output')
        failed = row.get('FailedBuild')
        _require('Test' not in row or _text(test, 256), 'event_type')
        _require('Elapsed' not in row or (type(elapsed) in (int, float)
                 and 0 <= elapsed <= 86400 and math.isfinite(elapsed)), 'event_type')
        _require(('Output' not in row or (action == 'output' and type(output) is str))
                 and (action != 'output' or 'Output' in row), 'event_type')
        _require('FailedBuild' not in row or (action == 'fail' and test is None
                 and _text(failed, 1024)), 'event_type')
        _require((action != 'start' or test is None) and (action != 'run' or test is not None), 'event_type')
        events.append(GoEvent(row['Time'], action, row['Package'], test, elapsed, output, failed))
    return tuple(events)


def _receipt_failures(receipt):
    return tuple(code for flag, code in (
        (receipt.exit_code is not None and receipt.exit_code != 0, 'simulated_nonzero'),
        (receipt.timed_out, 'simulated_timeout'), (receipt.interrupted, 'simulated_interrupted'),
        (receipt.ownership_lost, 'ownership_lost'), (not receipt.cleanup_complete, 'cleanup_incomplete')) if flag)


def _lifecycle(events, name):
    runs = [i for i, e in enumerate(events) if e.test == name and e.action == 'run']
    ends = [(i, e.action) for i, e in enumerate(events)
            if e.test == name and e.action in ('pass', 'fail', 'skip')]
    valid = len(runs) == len(ends) == 1 and runs[0] < ends[0][0]
    if valid:
        valid = all(runs[0] < i < ends[0][0] for i, e in enumerate(events)
                    if e.test == name and e.action == 'output')
    return valid, runs, ends


def translate_identity(events_raw: bytes, stderr_raw: bytes,
                       receipt: SimulatedExit, context: IdentityContext) -> IdentityDiagnostic:
    _outer(events_raw)
    _require(type(stderr_raw) is bytes, 'stderr_type')
    _require(len(stderr_raw) <= STDERR_LIMIT, 'stderr_size')
    _context(context)
    _receipt(receipt)
    receipt_codes = _receipt_failures(receipt)
    try:
        events = parse_identity_events(events_raw)
    except AdapterError as exc:
        return _diagnostic(context, events_raw, stderr_raw, 'unavailable',
                           ('unavailable',) * 5, (str(exc),) + receipt_codes)
    failures = set(receipt_codes)
    if any(e.package != PACKAGE for e in events):
        failures.add('package_mismatch')
    if any(e.test is not None and e.test not in (ROOT, *IDENTITY_IDS) for e in events):
        failures.add('unknown_test')
    starts = [i for i, e in enumerate(events) if e.action == 'start']
    package_ends = [(i, e.action) for i, e in enumerate(events)
                    if e.test is None and e.action in ('pass', 'fail', 'skip')]
    package_ok = starts == [0] and len(package_ends) == 1 and package_ends[0][0] == len(events) - 1
    if not package_ok:
        failures.add('package_lifecycle')
    root_ok, root_runs, root_ends = _lifecycle(events, ROOT)
    if not root_ok:
        failures.add('root_lifecycle')
    for name, prefix in ((ROOT, 'root'), (None, 'package')):
        for e in events:
            if e.test == name and e.action in ('fail', 'skip'):
                failures.add(prefix + ('_failed' if e.action == 'fail' else '_skipped'))
    statuses = []
    for index, name in enumerate(IDENTITY_IDS):
        valid, runs, ends = _lifecycle(events, name)
        if valid and root_ok:
            valid = root_runs[0] < runs[0] < ends[0][0] < root_ends[0][0]
        if not valid:
            failures.add(f'child_lifecycle:{index}')
        for e in events:
            if e.test == name and e.action in ('fail', 'skip'):
                failures.add(('child_failed:' if e.action == 'fail' else 'child_skipped:') + str(index))
        statuses.append('failed' if not valid or f'child_failed:{index}' in failures
                        else 'skipped' if ends[0][1] == 'skip' else 'passed')
    poison = {'package_mismatch', 'unknown_test', 'package_lifecycle', 'root_lifecycle',
              'root_failed', 'package_failed', 'simulated_nonzero', 'simulated_timeout',
              'ownership_lost', 'cleanup_incomplete'}
    if receipt.interrupted:
        status, statuses = 'interrupted', ('unavailable',) * 5
    elif failures & poison:
        status, statuses = 'inconsistent', ('failed',) * 5
    elif failures & {'root_skipped', 'package_skipped'}:
        status, statuses = 'inconsistent', ('skipped',) * 5
    else:
        status = 'consistent' if all(s == 'passed' for s in statuses) else 'inconsistent'
    return _diagnostic(context, events_raw, stderr_raw, status, statuses,
                       tuple(code for code in SEMANTIC_CODES if code in failures))


def _diagnostic(context, events_raw, stderr_raw, status, statuses, failures):
    return IdentityDiagnostic(
        'workshop-final180-identity-synthetic-v1', 'simulated-source-profile-validation',
        context.candidate_sha, context.inventory_sha256, context.source_manifest_sha256,
        hashlib.sha256(events_raw).hexdigest(), hashlib.sha256(stderr_raw).hexdigest(),
        status, tuple(CaseOutcome('identity', name, state, RAW_REFS)
                      for name, state in zip(IDENTITY_IDS, statuses)),
        tuple(failures), 0, False, (), AUTHORITY)
