#!/usr/bin/env python3
"""Bounded offline Workshop envelope diagnostics. No verification profiles enabled.

Candidate evidence is data only. The only subprocess is a read-only Git object
reader in this tool's owned checkout, with an isolated Git configuration.
"""
import argparse
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import stat
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib

CONTRACT = 'workshop-product-evidence-v1'
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_RAW_JSON_BYTES = 4 * 1024 * 1024
MAX_JSONL_RECORDS = 65536
MAX_XML_NODES = 20000
MAX_XML_DEPTH = 64
# Transport ceilings only; these do not enable any raw acceptance profile.
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
MAX_EVIDENCE_BYTES = 64 * 1024 * 1024
REPO_ROOT = Path(__file__).resolve().parents[2]
TASK_REF = 'docs/agents/tasks/2026-11-03-production-release/r6-release.json'
GATES = ('deterministic_ci', 'contract_compatibility', 'schema_integrity',
         'source_provenance', 'data_quality', 'security', 'reliability', 'independent_review')
BINDINGS = ('source_manifest_artifact', 'migration_manifest_artifact',
            'production_images_artifact', 'sdk_provenance_artifact')
FIXTURE_SLOTS = ('fixture.identity', 'fixture.catalog', 'fixture.commerce', 'fixture.paid',
                 'fixture.browser_dto', 'fixture.browser_api', 'ci.required',
                 'security.application', 'images.production', 'review.independent')
STAGING_SLOTS = ('staging.population', 'staging.firebase_google', 'staging.stripe_test',
                 'staging.banks_model', 'staging.host_isolation', 'staging.restore_recovery',
                 'staging.alert_delivery', 'staging.independent_review')
SLOT_KINDS = dict(zip(FIXTURE_SLOTS + STAGING_SLOTS,
    ('identity', 'catalog', 'commerce', 'paid', 'browser_dto', 'browser_api', 'ci', 'security',
     'images', 'review', 'population', 'firebase_google', 'stripe_test', 'banks_model',
     'host_isolation', 'restore_recovery', 'alert_delivery', 'review')))
ARTIFACT_KINDS = ('manifest', 'host_receipt', 'collector_result', 'junit', 'measurement',
                  'http_observations', 'ci_response', 'ci_log', 'scan', 'review', 'provenance', 'raw')
COUNTS = ('identity', 'catalog', 'commerce', 'paid', 'browser_dto', 'browser_api', 'total')
FLAGS = ('fixture_verified', 'product_candidate_verified', 'staging_verified',
         'deployment_authorized', 'cutover_verified')

# Literal inventories copied from inspected producer inputs, never imported from
# candidate modules. These are internal parser contracts, not enabled profiles.
PAID_GO_ROOTS = (
    'TestPostgresPaidCatalogGrantBeforeWork',
    'TestPostgresPaidCatalogExactScopeAndOwnerIsolation',
    'TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse',
    'TestPostgresPaidCatalogContextualMediaAndRevocation',
    'TestPostgresPaidCatalogHistoricalSourceAndRights',
    'TestPostgresPaidCatalogCustomerLegacyRoutesDenied')
PAID_CASE_IDS = tuple(root+'-'+bank for root in PAID_GO_ROOTS for bank in ('bankone', 'banktwo'))
DTO_ENGINES = ('chromium', 'firefox', 'webkit')
DTO_SCENARIOS = (
    'bankone-cascade', 'banktwo-cascade', 'dual-bank-coverage', 'one-bank-unavailable',
    'pending-no-content', 'source-to-canonical', 'source-rewrite-failure', 'review-required',
    'warm-reload', 'selection-change-in-flight', 'source-review-change-in-flight',
    'cancel-and-retry', 'history-restore', 'document-only', 'missing-media', 'withdrawal',
    'keyboard-print-mobile', 'source-media-isolation', 'auth-cookie-reload',
    'google-popup-exchange', 'google-popup-blocked', 'google-popup-cancelled',
    'google-stale-reauthentication', 'firebase-memory-persistence', 'signin-unavailable-local',
    'signin-malformed-config', 'session-expired', 'session-blocked', 'auth-dependency-unavailable',
    'quote-exact-scope', 'terms-config-unavailable', 'checkout-double-click-retry',
    'checkout-processing-return', 'checkout-untrusted-return', 'checkout-expired',
    'already-owned-no-pay', 'library-pagination-and-states', 'paid-prepare-before-poll',
    'media-renew-coalesced', 'logout-and-bfcache-clear')
DTO_CASE_IDS = tuple((engine, scenario) for engine in DTO_ENGINES for scenario in DTO_SCENARIOS)
DTO_ARCHIVE_LIMITS = {'browser/evidence.json': MAX_RAW_JSON_BYTES,
                      'go-fixture.log': MAX_ARTIFACT_BYTES, 'ready.json': MAX_RAW_JSON_BYTES}



class ContractError(ValueError):
    """A static diagnostic code, never candidate-controlled text."""


def require(condition, code='invalid_contract'):
    if not condition:
        raise ContractError(code)


def exact(value, keys):
    require(type(value) is dict and set(value) == set(keys), 'invalid_object_keys')


def string(value):
    require(type(value) is str and bool(value) and value == value.strip(), 'invalid_string')
    require(not any(ord(char) < 32 or 0xD800 <= ord(char) <= 0xDFFF for char in value), 'invalid_string')


def identifier(value):
    require(type(value) is str and re.fullmatch(r'[a-z][a-z0-9_.-]{0,95}', value) is not None, 'invalid_identifier')


def digest(value, length=64):
    require(type(value) is str and re.fullmatch('[0-9a-f]{'+str(length)+'}', value) is not None, 'invalid_digest')


def safe_ref(value):
    string(value)
    require('\\' not in value and ':' not in value and not value.startswith('/') and
            all(part not in ('', '.', '..') for part in value.split('/')), 'unsafe_reference')


def enum(value, choices):
    require(type(value) is str and value in choices, 'invalid_enum')


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum, 'invalid_integer')


def array(value):
    require(type(value) is list, 'invalid_array')


def unique(values):
    require(len(values) == len(set(values)), 'duplicate_identity')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def _strict_json(raw, limit, size_code):
    require(type(raw) is bytes and len(raw) <= limit, size_code)

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate_json_key')
            result[key] = value
        return result

    def nonfinite(_):
        raise ContractError('nonfinite_number')

    def walk(value):
        if type(value) is float:
            require(math.isfinite(value), 'nonfinite_number')
        elif type(value) is str:
            require(not any(0xD800 <= ord(char) <= 0xDFFF for char in value), 'invalid_utf8')
        elif type(value) is dict:
            for key, item in value.items():
                walk(key); walk(item)
        elif type(value) is list:
            for item in value:
                walk(item)
    try:
        result = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=nonfinite)
        walk(result)
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError, ValueError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError('invalid_json') from None
    require(type(result) is dict, 'invalid_json_object')
    return result


def strict_json(raw):
    """The envelope and trusted task retain their separate 2 MiB ceiling."""
    return _strict_json(raw, MAX_MANIFEST_BYTES, 'manifest_size')


def strict_raw_json(raw):
    """Explicit internal raw JSON parser; it cannot enable a profile."""
    return _strict_json(raw, MAX_RAW_JSON_BYTES, 'raw_json_size')


def strict_jsonl(raw):
    """Bounded complete UTF-8 object records, without interpreting Go outcomes."""
    require(type(raw) is bytes and 0 < len(raw) <= MAX_RAW_JSON_BYTES, 'jsonl_size')
    require(raw.endswith(b'\n'), 'incomplete_jsonl')
    require(raw.count(b'\n') <= MAX_JSONL_RECORDS, 'jsonl_record_limit')
    lines = raw.split(b'\n')[:-1]
    require(len(lines) <= MAX_JSONL_RECORDS, 'jsonl_record_limit')
    return [strict_raw_json(line) for line in lines]


def strict_junit_xml(raw):
    """Bounded non-namespaced JUnit syntax, never DTD/entity resolution."""
    require(type(raw) is bytes and 0 < len(raw) <= MAX_RAW_JSON_BYTES, 'xml_size')
    try:
        text = raw.decode('utf-8')
        require(re.search(r'<!\s*(?:DOCTYPE|ENTITY)|<!--', text, re.I) is None,
                'unsafe_xml_declaration')
        # XML declarations may only advertise the decoding used above.
        declaration = re.match(r'^\ufeff?(<\?xml\s+[^?]*\?>)', text)
        body = text
        if declaration:
            encoding = re.search(r'encoding\s*=\s*[\'"]([^\'"]+)[\'"]', declaration[1])
            require(encoding is None or encoding[1].lower() == 'utf-8', 'xml_encoding')
            body = text[declaration.end():]
        require('<?' not in body, 'unsafe_xml_declaration')
        parser = ET.XMLPullParser(events=('start', 'end'))
        depth = nodes = 0
        root = None
        for offset in range(0, len(text), 4096):
            parser.feed(text[offset:offset+4096])
            for event, element in parser.read_events():
                if event == 'start':
                    depth += 1; nodes += 1
                    require(depth <= MAX_XML_DEPTH and nodes <= MAX_XML_NODES, 'xml_complexity')
                    require(type(element.tag) is str and '{' not in element.tag, 'xml_namespace')
                    if root is None:
                        root = element
                else:
                    depth -= 1
        parser.close()
        require(root is not None and root.tag in ('testsuite', 'testsuites') and depth == 0,
                'invalid_junit_root')
        return root
    except (UnicodeError, ET.ParseError, RecursionError, ValueError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError('invalid_xml') from None


def strict_dto_archive(raw):
    """Read the fixed three-member DTO ZIP in memory; never extract paths.

    Only observed ZIP32 stored/deflated regular files without descriptors,
    comments or extra fields are understood. Complete bounded deflate streams,
    local/central metadata and CRC must agree; hidden expansion is rejected.
    """
    require(type(raw) is bytes and 22 <= len(raw) <= MAX_ARTIFACT_BYTES, 'zip_size')
    require(raw[-22:-18] == b'PK\x05\x06', 'invalid_zip')
    end = struct.unpack_from('<4s4H2IH', raw, len(raw)-22)
    require(end[1:5] == (0, 0, 3, 3) and end[7] == 0, 'invalid_zip_directory')
    require(end[5]+end[6] == len(raw)-22, 'invalid_zip_directory')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            records = archive.infolist()
            require(len(records) == 3 and archive.start_dir == end[6] and not archive.comment,
                    'invalid_zip_directory')
            names = [record.filename for record in records]
            unique(names)
            require(set(names) == set(DTO_ARCHIVE_LIMITS), 'dto_archive_inventory')
            offsets = sorted(record.header_offset for record in records)
            unique(offsets)
            require(offsets[0] == 0, 'invalid_zip_layout')
            result = {}
            for record in records:
                name = record.filename
                safe_ref(name)
                require(record.orig_filename == name and not record.is_dir() and
                        not record.extra and not record.comment and
                        stat.S_IFMT(record.external_attr >> 16) in (0, stat.S_IFREG) and
                        not (record.external_attr & 0x10), 'unsafe_zip_member')
                require(record.flag_bits in (0, 0x800) and record.extract_version <= 20 and
                        record.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                        'unsupported_zip_format')
                limit = DTO_ARCHIVE_LIMITS[name]
                require(0 <= record.file_size <= limit and 0 <= record.compress_size <= MAX_ARTIFACT_BYTES,
                        'zip_expansion_limit')
                offset = record.header_offset
                require(0 <= offset <= archive.start_dir-30, 'invalid_zip_layout')
                header = struct.unpack_from('<4s5H3I2H', raw, offset)
                require(header[0] == b'PK\x03\x04' and header[1] == record.extract_version and
                        header[2] == record.flag_bits and
                        header[3] == record.compress_type and header[6] == record.CRC and
                        header[7] == record.compress_size and header[8] == record.file_size and
                        header[10] == 0, 'zip_header_mismatch')
                start = offset+30+header[9]
                finish = start+record.compress_size
                next_offset = min((item for item in offsets if item > offset), default=archive.start_dir)
                require(finish == next_offset and raw[offset+30:start] == name.encode('ascii'),
                        'invalid_zip_layout')
                compressed = raw[start:finish]
                if record.compress_type == zipfile.ZIP_STORED:
                    data = compressed
                else:
                    decoder = zlib.decompressobj(-15)
                    data = decoder.decompress(compressed, limit+1)
                    require(len(data) <= limit and decoder.eof and not decoder.unconsumed_tail and
                            not decoder.unused_data, 'zip_expansion_limit')
                require(len(data) == record.file_size and zlib.crc32(data) == record.CRC,
                        'zip_content_mismatch')
                result[name] = data
            require(sum(map(len, result.values())) <= MAX_EVIDENCE_BYTES, 'zip_expansion_limit')
            return result
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, UnicodeError,
            OSError, ValueError, struct.error, zlib.error) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError('invalid_zip') from None


def paid_case_identities(case_ids):
    """Identity inventory only; does not corroborate producer assertions."""
    array(case_ids)
    for case_id in case_ids:
        string(case_id)
    unique(case_ids)
    require(set(case_ids) == set(PAID_CASE_IDS), 'paid_case_inventory')
    return PAID_CASE_IDS


def dto_case_identities(case_ids):
    """Explicit scenario/engine pairs only; cannot substitute DTO for API21."""
    array(case_ids)
    pairs = []
    for item in case_ids:
        exact(item, ('browser', 'scenario'))
        enum(item['browser'], DTO_ENGINES); enum(item['scenario'], DTO_SCENARIOS)
        pairs.append((item['browser'], item['scenario']))
    unique(pairs)
    require(set(pairs) == set(DTO_CASE_IDS), 'dto_case_inventory')
    return DTO_CASE_IDS


def references(value, artifacts):
    array(value)
    for ref in value:
        identifier(ref)
        require(ref in artifacts, 'undeclared_artifact')
    unique(value)


def timestamp(value):
    require(type(value) is str, 'invalid_timestamp')
    match = re.fullmatch(r'([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(?:\.([0-9]+))?(?:Z|\+00:00)', value)
    require(match is not None, 'invalid_timestamp')
    try:
        # Preserve arbitrary RFC3339 fractional precision for exact ordering.
        return (datetime.fromisoformat(match[1]+'+00:00'), Decimal('0.'+(match[2] or '0')))
    except ValueError:
        raise ContractError('invalid_timestamp') from None


def parse_envelope(raw):
    """Validate structure and internal references; never read or trust raw evidence."""
    item = strict_json(raw)
    exact(item, ('contract', 'schema_version', 'candidate_sha', 'trusted_base_sha',
                 'requested_tier', 'task_ref', 'policy_sha256', 'bindings', 'artifacts', 'slots', 'eight_reports'))
    require(item['contract'] == CONTRACT, 'invalid_contract_version')
    require(type(item['schema_version']) is int and item['schema_version'] == 1, 'invalid_schema_version')
    digest(item['candidate_sha'], 40); digest(item['trusted_base_sha'], 40)
    digest(item['policy_sha256']); safe_ref(item['task_ref'])
    enum(item['requested_tier'], ('fixture', 'staging'))
    artifacts = {}
    refs = []
    array(item['artifacts'])
    for artifact in item['artifacts']:
        exact(artifact, ('artifact_id', 'kind', 'ref', 'sha256', 'bytes', 'visibility'))
        identifier(artifact['artifact_id']); enum(artifact['kind'], ARTIFACT_KINDS)
        safe_ref(artifact['ref']); digest(artifact['sha256']); integer(artifact['bytes'])
        enum(artifact['visibility'], ('private', 'public'))
        require(artifact['artifact_id'] not in artifacts, 'duplicate_artifact_id')
        artifacts[artifact['artifact_id']] = artifact
        refs.append(artifact['ref'])
    unique(refs)
    exact(item['bindings'], BINDINGS)
    # Multiple binding roles may index one manifest, but each must be declared.
    for ref in item['bindings'].values():
        identifier(ref); require(ref in artifacts, 'undeclared_artifact')
        require(artifacts[ref]['kind'] in ('manifest', 'provenance'), 'binding_artifact_kind')
    array(item['slots'])
    slots = []
    for slot in item['slots']:
        exact(slot, ('slot_id', 'kind', 'scope', 'candidate_sha', 'profile_sha256',
                     'result_artifact', 'host_receipt_artifact', 'raw_artifact_ids', 'command',
                     'started_at', 'finished_at', 'deadline_seconds', 'exit_code', 'timed_out'))
        enum(slot['slot_id'], SLOT_KINDS)
        require(slot['kind'] == SLOT_KINDS[slot['slot_id']], 'slot_kind_mismatch')
        enum(slot['scope'], ('fixture', 'staging'))
        require(item['requested_tier'] == 'staging' or slot['scope'] == 'fixture', 'tier_scope_mismatch')
        require(slot['scope'] == ('staging' if slot['slot_id'] in STAGING_SLOTS else 'fixture'), 'slot_scope_mismatch')
        digest(slot['candidate_sha'], 40)
        require(slot['candidate_sha'] == item['candidate_sha'], 'candidate_mismatch')
        digest(slot['profile_sha256'])
        for field, kind in (('result_artifact', 'collector_result'), ('host_receipt_artifact', 'host_receipt')):
            ref = slot[field]; identifier(ref)
            require(ref in artifacts and artifacts[ref]['kind'] == kind, 'slot_artifact_kind')
        references(slot['raw_artifact_ids'], artifacts)
        exact(slot['command'], ('argv', 'sha256'))
        argv = slot['command']['argv']; array(argv); require(bool(argv), 'empty_command')
        for arg in argv:
            # Empty argv operands are valid data, but not control characters.
            require(type(arg) is str and not any(ord(char) < 32 for char in arg), 'invalid_argv')
        require(bool(argv[0]), 'empty_command')
        digest(slot['command']['sha256'])
        require(sha256(canonical(argv)) == slot['command']['sha256'], 'command_hash_mismatch')
        start = timestamp(slot['started_at']); finish = timestamp(slot['finished_at'])
        require(finish >= start, 'negative_elapsed')
        integer(slot['deadline_seconds'], 1); integer(slot['exit_code'])
        require(type(slot['timed_out']) is bool, 'invalid_timeout')
        slots.append(slot['slot_id'])
    unique(slots)
    array(item['eight_reports'])
    gates = []
    finding_ids = []
    for report in item['eight_reports']:
        exact(report, ('gate_id', 'candidate_sha', 'scope', 'verdict', 'author_id',
                       'reviewer_id', 'artifact_ids', 'findings', 'reason_code'))
        enum(report['gate_id'], GATES); digest(report['candidate_sha'], 40)
        require(report['candidate_sha'] == item['candidate_sha'], 'candidate_mismatch')
        enum(report['scope'], ('fixture', 'staging'))
        require(item['requested_tier'] == 'staging' or report['scope'] == 'fixture', 'tier_scope_mismatch')
        enum(report['verdict'], ('pass', 'fail', 'pending', 'unavailable'))
        for role in ('author_id', 'reviewer_id'):
            if report[role] is None:
                require(report['verdict'] == 'pending', 'missing_report_identity')
            else:
                identifier(report[role])
        references(report['artifact_ids'], artifacts)
        if report['verdict'] == 'pass':
            require(report['reason_code'] is None, 'pass_reason')
        else:
            enum(report['reason_code'], ('missing', 'unavailable', 'invalid', 'failed',
                 'disagreement', 'not_required_at_fixture_tier'))
        array(report['findings'])
        for finding in report['findings']:
            exact(finding, ('finding_id', 'severity', 'blocking', 'status', 'artifact_ids'))
            identifier(finding['finding_id'])
            enum(finding['severity'], ('critical', 'high', 'medium', 'low', 'informational'))
            enum(finding['status'], ('open', 'resolved'))
            require(type(finding['blocking']) is bool, 'invalid_blocking')
            references(finding['artifact_ids'], artifacts)
            finding_ids.append(finding['finding_id'])
        gates.append(report['gate_id'])
    unique(gates); unique(finding_ids)
    require(set(gates) == set(GATES), 'missing_gate_report')
    return item


def file_identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


class ArtifactStore:
    """Confined immutable transport, independent of any raw producer schema.

    Every read reopens files and rechecks the complete inventory. No bytes are
    cached across calls. A matching digest proves integrity, never authorship.
    """
    def __init__(self, root, artifacts, *, max_file_bytes=MAX_ARTIFACT_BYTES,
                 max_total_bytes=MAX_EVIDENCE_BYTES):
        integer(max_file_bytes, 1); integer(max_total_bytes, 1)
        require(max_file_bytes <= MAX_ARTIFACT_BYTES and max_total_bytes <= MAX_EVIDENCE_BYTES,
                'unsupported_transport_limit')
        root_path = os.fspath(root)
        string(root_path)
        require('..' not in root_path.split('/'), 'unsafe_evidence_root')
        self.root = os.path.abspath(root_path)
        self.closed = False
        self.artifacts = {}
        self.by_ref = {}
        self.directories = {''}
        array(artifacts)
        total = 0
        for record in artifacts:
            exact(record, ('artifact_id', 'kind', 'ref', 'sha256', 'bytes', 'visibility'))
            identifier(record['artifact_id']); safe_ref(record['ref']); digest(record['sha256'])
            enum(record['kind'], ARTIFACT_KINDS); enum(record['visibility'], ('private', 'public'))
            integer(record['bytes'])
            require(record['artifact_id'] not in self.artifacts and record['ref'] not in self.by_ref,
                    'duplicate_artifact_identity')
            require(record['bytes'] <= max_file_bytes, 'artifact_size_limit')
            total += record['bytes']
            require(total <= max_total_bytes, 'evidence_size_limit')
            # Snapshot declarations too: callers cannot mutate records after binding.
            record = dict(record)
            self.artifacts[record['artifact_id']] = record
            self.by_ref[record['ref']] = record
            parts = record['ref'].split('/')
            self.directories.update('/'.join(parts[:index]) for index in range(1, len(parts)))
        self.snapshot = self._inventory()

    def __enter__(self):
        require(not self.closed, 'artifact_store_closed')
        return self

    def __exit__(self, *_):
        self.closed = True

    def _open_root(self):
        # Open every absolute component with NOFOLLOW, including root ancestors.
        current = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            for part in self.root.split('/')[1:]:
                if not part:
                    continue
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                  dir_fd=current)
                os.close(current)
                current = next_fd
            return current
        except BaseException:
            os.close(current)
            raise

    def _inventory(self):
        require(not self.closed, 'artifact_store_closed')
        pending = []
        result = {}
        found = set()
        inodes = set()
        try:
            pending.append(('', self._open_root()))
            while pending:
                prefix, fd = pending.pop()
                try:
                    before = file_identity(os.fstat(fd))
                    result[prefix+'/'] = before
                    for name in os.listdir(fd):
                        ref = prefix+'/'+name if prefix else name
                        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                        if stat.S_ISDIR(info.st_mode):
                            require(ref in self.directories, 'undeclared_inventory_entry')
                            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                            dir_fd=fd)
                            if file_identity(os.fstat(child)) != file_identity(info):
                                os.close(child)
                                raise ContractError('artifact_identity_drift')
                            pending.append((ref, child))
                        else:
                            require(stat.S_ISREG(info.st_mode), 'unsafe_evidence_file')
                            require(ref in self.by_ref, 'undeclared_inventory_entry')
                            require(info.st_nlink == 1 and (info.st_dev, info.st_ino) not in inodes,
                                    'aliased_evidence_inode')
                            require(info.st_size == self.by_ref[ref]['bytes'], 'artifact_size_mismatch')
                            found.add(ref); inodes.add((info.st_dev, info.st_ino))
                            result[ref] = file_identity(info)
                    require(file_identity(os.fstat(fd)) == before, 'artifact_identity_drift')
                finally:
                    os.close(fd)
            require(found == set(self.by_ref), 'missing_evidence_file')
            return result
        except OSError:
            raise ContractError('evidence_unavailable') from None
        finally:
            for _, fd in pending:
                os.close(fd)

    def recheck(self):
        require(self._inventory() == self.snapshot, 'artifact_identity_drift')

    def _open_file(self, ref):
        current = self._open_root()
        try:
            parts = ref.split('/')
            for part in parts[:-1]:
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                  dir_fd=current)
                os.close(current); current = next_fd
            return os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                           dir_fd=current)
        finally:
            os.close(current)

    def read(self, artifact_id):
        identifier(artifact_id)
        require(artifact_id in self.artifacts, 'undeclared_artifact')
        self.recheck()
        record = self.artifacts[artifact_id]
        expected = self.snapshot[record['ref']]
        try:
            fd = self._open_file(record['ref'])
            try:
                require(file_identity(os.fstat(fd)) == expected, 'artifact_identity_drift')
                chunks = []
                remaining = record['bytes']+1
                while remaining:
                    chunk = os.read(fd, min(65536, remaining))
                    if not chunk:
                        break
                    chunks.append(chunk); remaining -= len(chunk)
                raw = b''.join(chunks)
                require(file_identity(os.fstat(fd)) == expected, 'artifact_identity_drift')
            finally:
                os.close(fd)
        except OSError:
            raise ContractError('evidence_unavailable') from None
        require(len(raw) == record['bytes'], 'artifact_size_mismatch')
        require(sha256(raw) == record['sha256'], 'artifact_hash_mismatch')
        self.recheck()
        return raw

    def read_identity_json(self, artifact_id, *, candidate_sha, trusted_base_sha, profile_sha256=None):
        """Explicit JSON reader; missing identity is never filled in or proof.

        This checks declared reserved identities only. Required fields and raw
        producer schemas remain unavailable until their own profile is frozen.
        """
        return self._read_bound_json(artifact_id, strict_json, candidate_sha,
                                     trusted_base_sha, profile_sha256)

    def read_raw_json(self, artifact_id, *, candidate_sha, trusted_base_sha, profile_sha256):
        """Explicit 4 MiB data reader reserved for internal typed validators.

        No CLI kind/filename selects this method. Profile authorization and
        completeness are separate from reserved-identity equality.
        """
        digest(profile_sha256)
        return self._read_bound_json(artifact_id, strict_raw_json, candidate_sha,
                                     trusted_base_sha, profile_sha256)

    def _read_bound_json(self, artifact_id, parser, candidate_sha, trusted_base_sha, profile_sha256):
        digest(candidate_sha, 40); digest(trusted_base_sha, 40)
        if profile_sha256 is not None:
            digest(profile_sha256)
        value = parser(self.read(artifact_id))
        expected = dict(candidate_sha=candidate_sha, trusted_base_sha=trusted_base_sha,
                        profile_sha256=profile_sha256)
        pending = [value]
        while pending:
            item = pending.pop()
            if type(item) is dict:
                for key, nested in item.items():
                    if key in expected:
                        require(type(nested) is str and expected[key] is not None and nested == expected[key],
                                'raw_identity_mismatch')
                    pending.append(nested)
            elif type(item) is list:
                pending.extend(item)
        self.recheck()
        return value


@dataclass(frozen=True)
class TrustedInvocation:
    base_sha: str
    task_ref: str
    tier: str
    policy_sha256: str
    profile: dict


def git_read(base, ref):
    """Literal read-only object lookup, never candidate cwd/config or shell."""
    digest(base, 40); safe_ref(ref)
    env = {'PATH': '/usr/bin:/bin', 'GIT_CONFIG_NOSYSTEM': '1',
           'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_NO_REPLACE_OBJECTS': '1',
           'GIT_TERMINAL_PROMPT': '0', 'GIT_NO_LAZY_FETCH': '1', 'LC_ALL': 'C'}
    try:
        result = subprocess.run(['/usr/bin/git', '--no-pager', '-c', 'core.hooksPath='+os.devnull,
            '-c', 'core.fsmonitor=false', 'cat-file', 'blob', base+':'+ref],
            cwd=REPO_ROOT, env=env, capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        raise ContractError('trusted_object_unavailable') from None
    require(result.returncode == 0, 'trusted_object_unavailable')
    require(len(result.stdout) <= MAX_MANIFEST_BYTES, 'trusted_object_size')
    return result.stdout


def load_trusted(base_sha, task_ref, requested_tier):
    """Consume only the pinned direct task; promotion is unavailable in milestone 1."""
    digest(base_sha, 40); safe_ref(task_ref); enum(requested_tier, ('fixture', 'staging'))
    require(task_ref == TASK_REF, 'unrecognized_trusted_task')
    task = strict_json(git_read(base_sha, task_ref))
    require(task.get('dispatch_mode') == 'coordinator-direct' and
            task.get('repository') == 'lucronn/autodata' and
            task.get('task_id') == 'production-release-r6-release', 'invalid_trusted_task')
    profile = task.get('product_evidence')
    exact(profile, ('contract', 'schema_version', 'policy_sha256', 'assembler_ref', 'assembler_sha256',
                    'evaluator_ref', 'evaluator_sha256', 'supervisor_profiles', 'bindings_profile',
                    'slot_profiles', 'ci_profile', 'report_profile', 'enabled_tiers'))
    require(profile['contract'] == CONTRACT and type(profile['schema_version']) is int and
            profile['schema_version'] == 1, 'invalid_profile_version')
    digest(profile['policy_sha256']); digest(profile['evaluator_sha256'])
    require(profile['assembler_ref'] == 'scripts/dev/release_acceptance.py' and
            profile['evaluator_ref'] == 'scripts/autonomy/validate_run.py', 'invalid_tool_reference')
    if profile['assembler_sha256'] is not None:
        digest(profile['assembler_sha256'])
    require(sha256(git_read(base_sha, '.autodata-autonomy-policy.json')) == profile['policy_sha256'], 'policy_hash_mismatch')
    require(sha256(git_read(base_sha, profile['evaluator_ref'])) == profile['evaluator_sha256'], 'evaluator_hash_mismatch')
    # Only the committed disabled planning profile is understood here. A future
    # promoted raw contract requires a separate gate and explicit implementation.
    require(profile['enabled_tiers'] == [] and type(profile['enabled_tiers']) is list,
            'unsupported_promoted_profile')
    require(profile['supervisor_profiles'] == [] and type(profile['supervisor_profiles']) is list,
            'unsupported_supervisor_profile')
    exact(profile['bindings_profile'], ('enabled',))
    require(profile['bindings_profile']['enabled'] is False, 'unsupported_bindings_profile')
    array(profile['slot_profiles'])
    ids = []
    for slot in profile['slot_profiles']:
        exact(slot, ('slot_id', 'enabled', 'expected_cases'))
        enum(slot['slot_id'], FIXTURE_SLOTS[:6]); require(slot['enabled'] is False, 'unsupported_slot_profile')
        integer(slot['expected_cases'], 1); ids.append(slot['slot_id'])
    unique(ids); require(set(ids) == set(FIXTURE_SLOTS[:6]), 'missing_slot_profile')
    exact(profile['ci_profile'], ('enabled', 'workflow_sha256', 'dto_upload_required'))
    require(profile['ci_profile']['enabled'] is False and profile['ci_profile']['dto_upload_required'] is True,
            'unsupported_ci_profile')
    digest(profile['ci_profile']['workflow_sha256'])
    require(sha256(git_read(base_sha, '.github/workflows/autonomous-verification.yml')) ==
            profile['ci_profile']['workflow_sha256'], 'workflow_hash_mismatch')
    exact(profile['report_profile'], ('enabled', 'gate_ids'))
    require(profile['report_profile']['enabled'] is False and profile['report_profile']['gate_ids'] == list(GATES),
            'unsupported_report_profile')
    return TrustedInvocation(base_sha, task_ref, requested_tier, profile['policy_sha256'], profile)


def diagnostic(mode, candidate=None, base=None, tier=None, manifest_hash=None):
    return dict(contract=CONTRACT, schema_version=1, candidate_sha=candidate, trusted_base_sha=base,
        requested_tier=tier, status='planned' if mode == 'plan' else 'unavailable',
        **{flag: False for flag in FLAGS}, derived_counts={key: 0 for key in COUNTS},
        gate_statuses={gate: {'status': 'unavailable', 'reason_code': 'unavailable'} for gate in GATES},
        missing_slots=list(FIXTURE_SLOTS + (STAGING_SLOTS if tier == 'staging' else ())),
        failures=[], input_manifest_sha256=manifest_hash, tool_sha256=sha256(Path(__file__).read_bytes()))


def assemble(envelope, trusted, mode, manifest_sha256=None):
    require(mode in ('plan', 'validate'), 'invalid_mode')
    require(envelope['trusted_base_sha'] == trusted.base_sha and envelope['task_ref'] == trusted.task_ref and
            envelope['requested_tier'] == trusted.tier and envelope['policy_sha256'] == trusted.policy_sha256,
            'trusted_invocation_mismatch')
    profiles = {profile['slot_id']: profile for profile in trusted.profile['slot_profiles']}
    for slot in envelope['slots']:
        if slot['slot_id'] in profiles:
            require(slot['profile_sha256'] == sha256(canonical(profiles[slot['slot_id']])),
                    'slot_profile_hash_mismatch')
        # Missing/disabled profiles remain unavailable, never inferred from raw.
    result = diagnostic(mode, envelope['candidate_sha'], trusted.base_sha, trusted.tier, manifest_sha256)
    # No supplied report, counter, file hash or execution flag can enable trust.
    result['failures'] = ['profiles_unavailable', 'raw_validation_unimplemented']
    if trusted.profile['assembler_sha256'] is None:
        result['failures'].append('assembler_unpromoted')
    return result, 0 if mode == 'plan' else 3


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('plan', 'validate'))
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--evidence-root', required=True,
                        help='Dedicated declared raw input directory; plan does not read it')
    parser.add_argument('--trusted-base-sha', required=True)
    parser.add_argument('--task-ref', required=True)
    parser.add_argument('--requested-tier', required=True, choices=('fixture', 'staging'))
    args = parser.parse_args(argv)
    manifest_hash = None
    try:
        trusted = load_trusted(args.trusted_base_sha, args.task_ref, args.requested_tier)
        with Path(args.manifest).open('rb') as handle:
            raw = handle.read(MAX_MANIFEST_BYTES + 1)
        require(len(raw) <= MAX_MANIFEST_BYTES, 'manifest_size')
        manifest_hash = sha256(raw)
        envelope = parse_envelope(raw)
        result, code = assemble(envelope, trusted, args.mode, manifest_hash)
        if args.mode == 'validate':
            with ArtifactStore(args.evidence_root, envelope['artifacts']) as store:
                for artifact in envelope['artifacts']:
                    store.read(artifact['artifact_id'])
                store.recheck()
    except (ContractError, OSError) as exc:
        result = diagnostic(args.mode, manifest_hash=manifest_hash)
        result['status'] = 'failed'
        result['failures'] = [str(exc) if isinstance(exc, ContractError) else 'input_unavailable']
        code = 2
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
