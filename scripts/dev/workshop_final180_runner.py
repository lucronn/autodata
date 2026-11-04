"""Stage A: offline source admission and normalized, unverified claim diagnostics.

No fixture execution, raw producer parsing, network, or acceptance authority.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import secrets
import stat
import subprocess
import tempfile
import time
from typing import Protocol

CHECKPOINT_SHA = 'b8ffaa39e6b9104df67f69541ce4da8a936adc0f'
CANDIDATE_SHA = '4d82e413e04fb2401ac7bc28dc828375ac662180'
PLAN_PATH = 'docs/superpowers/plans/2026-11-04-workshop-final180-runner.md'
RECORD_PATH = 'docs/agents/records/2026-11-04-workshop-final180-runner.json'
TASK_PATH = 'docs/agents/tasks/2026-11-03-production-release/workshop-final180-runner.json'
INVENTORY_PATH = 'docs/agents/specs/2026-11-04-workshop-final180-inventory.json'
FAMILIES = ('identity', 'catalog', 'commerce', 'paid', 'browser_dto', 'browser_api')
COUNTS = (5, 8, 14, 12, 120, 21)
AUTHORITY = ('fixture_verified', 'product_candidate_verified', 'staging_verified',
             'deployment_authorized', 'cutover_verified', 'implementation_authorized',
             'runtime_execution_authorized', 'profile_promotion_authorized', 'merge_authorized')
MAX_DIAGNOSTIC = 4 * 1024 * 1024
MAX_MANIFEST = 64 * 1024 * 1024
MAX_SOURCE_DIRECTORIES = 100000
FIXED_PATH = '/usr/local/bin:/usr/bin:/bin'
SHA40 = re.compile(r'[0-9a-f]{40}\Z')
SHA64 = re.compile(r'[0-9a-f]{64}\Z')
HOOK_NAMES = frozenset(('applypatch-msg pre-applypatch post-applypatch pre-commit pre-merge-commit '
    'prepare-commit-msg commit-msg post-commit pre-rebase post-checkout post-merge pre-push '
    'pre-receive update proc-receive post-receive post-update reference-transaction '
    'push-to-checkout pre-auto-gc post-rewrite sendemail-validate fsmonitor-watchman '
    'p4-changelist p4-prepare-changelist p4-post-changelist p4-pre-submit post-index-change').split())


class ContractError(ValueError):
    """A stable, bounded diagnostic code; never include input paths or raw errors."""


@dataclass(frozen=True)
class SourcePin:
    path: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class Contract:
    checkpoint_sha: str
    candidate_sha: str
    inventory_sha256: str
    expected_ids: tuple[tuple[str, tuple[str, ...]], ...]
    source_pins: tuple[SourcePin, ...]


@dataclass(frozen=True)
class SourceMember:
    path: str
    mode: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class SourceInspection:
    candidate_sha: str
    source_manifest_sha256: str
    source_manifest: tuple[SourceMember, ...]


@dataclass(frozen=True)
class Observation:
    family: str
    logical_id: str
    status: str
    raw_refs: tuple[str, ...]


@dataclass(frozen=True)
class HookEntry:
    path: str
    mode: str
    sha256: str
    active: bool


@dataclass(frozen=True)
class GitToolIdentity:
    path: str
    sha256: str
    version: str


class GitReader(Protocol):
    def read_blob(self, sha: str, path: str) -> bytes: ...
    def tracked_entries(self, sha: str) -> tuple[tuple[str, str, str], ...]: ...
    def observe_checkout(self, root: Path) -> dict: ...
    def tool_identity(self) -> GitToolIdentity: ...


def _require(condition, code):
    if not condition:
        raise ContractError(code)


def _string(value, limit, *, empty=False):
    if type(value) is not str or (not empty and not value):
        return False
    try:
        return len(value.encode('utf-8')) <= limit
    except UnicodeError:
        return False


def _safe_path(value, limit=4096):
    return (_string(value, limit) and not value.startswith('/') and '\\' not in value
            and '\x00' not in value and all(p not in ('', '.', '..') for p in value.split('/')))


def _keys(value, expected, code):
    _require(type(value) is dict and set(value) == set(expected), code)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                       allow_nan=False) + '\n').encode('utf-8')


def load_json_strict(raw: bytes, *, max_bytes: int) -> dict:
    _require(type(raw) is bytes and len(raw) <= max_bytes and not raw.startswith(b'\xef\xbb\xbf'), 'json_invalid')

    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, 'json_duplicate_key')
            result[key] = value
        return result

    def invalid_constant(_):
        raise ContractError('json_nonfinite')

    try:
        result = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid_constant)
        _require(type(result) is dict, 'json_object_required')
        pending = [(result, 0)]
        while pending:
            item, depth = pending.pop()
            _require(depth <= 32, 'json_depth')
            if type(item) is str:
                _require(_string(item, 65536, empty=True), 'json_string')
            elif type(item) in (dict, list):
                _require(len(item) <= 65536, 'json_collection')
                children = list(item.keys()) + list(item.values()) if type(item) is dict else item
                pending.extend((v, depth + 1) for v in children)
            elif type(item) is float:
                _require(item == item and abs(item) != float('inf'), 'json_nonfinite')
        return result
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError, ValueError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError('json_invalid') from None


def load_contract(checkpoint_sha: str, git: GitReader) -> Contract:
    _require(type(checkpoint_sha) is str and SHA40.fullmatch(checkpoint_sha) and checkpoint_sha == CHECKPOINT_SHA, 'checkpoint_sha')
    try:
        record = load_json_strict(git.read_blob(checkpoint_sha, RECORD_PATH), max_bytes=2*1024*1024)
        task = load_json_strict(git.read_blob(checkpoint_sha, TASK_PATH), max_bytes=2*1024*1024)
        plan = git.read_blob(checkpoint_sha, PLAN_PATH).decode('utf-8')
        _require(task.get('pre_implementation') == record and record.get('status') == 'synchronized'
                 and record.get('plan_ref') == PLAN_PATH and record.get('selected_candidate_sha') == CANDIDATE_SHA
                 and task.get('selected_candidate_sha') == CANDIDATE_SHA
                 and task.get('goal') == record.get('goal')
                 and task.get('allowed_paths') == ['scripts/dev/workshop_final180_runner.py',
                     'scripts/dev/test_workshop_final180_runner.py', 'docs/verification/workshop-final180-runbook.md']
                 and type(task.get('authority')) is dict and set(AUTHORITY) == set(task['authority'])
                 and all(v is False for v in task['authority'].values())
                 and task.get('product_evidence') == {'profiles_enabled': False, 'enabled_tiers': []}, 'checkpoint_contract')
        for key in ('goal', 'issue_ref', 'project_ref'):
            _require(_string(record.get(key), 8192) and record[key] in plan, 'checkpoint_contract')
        _require(record['issue_ref'] == 'https://github.com/lucronn/autodata/issues/186'
                 and record['project_ref'] == 'https://github.com/users/lucronn/projects/8'
                 and type(record.get('todo')) is list and bool(record['todo']), 'checkpoint_contract')
        for todo in record['todo']:
            _require(_string(todo, 8192) and todo in plan, 'checkpoint_contract')
        refs = record.get('repository_doc_refs')
        _require(type(refs) is list and bool(refs), 'checkpoint_contract')
        for ref in refs:
            _require(_safe_path(ref), 'checkpoint_contract')
            _require(bool(git.read_blob(checkpoint_sha, ref)), 'checkpoint_contract')
        raw = git.read_blob(checkpoint_sha, INVENTORY_PATH)
        inv = load_json_strict(raw, max_bytes=2*1024*1024)
        _require(inv.get('contract') == 'workshop-final180-inventory-draft-v1'
                 and inv.get('selected_candidate_sha') == CANDIDATE_SHA
                 and inv.get('source_hashes_sha') == CANDIDATE_SHA
                 and inv.get('selected_source_tuple', {}).get('candidate_sha') == CANDIDATE_SHA
                 and inv.get('selected_source_tuple', {}).get('source_pins_git_sha') == CANDIDATE_SHA
                 and inv.get('profiles_enabled') is False and inv.get('enabled_tiers') == [], 'inventory_contract')
        authority = inv.get('authority')
        _require(type(authority) is dict and set(AUTHORITY) <= set(authority)
                 and all(v is False for v in authority.values()), 'inventory_authority')
        ids = inv.get('expected_case_ids')
        _keys(ids, FAMILIES, 'inventory_ids')
        _require(inv.get('expected_counts') == dict(zip(FAMILIES + ('total',), COUNTS + (180,)))
                 and all(type(v) is int for v in inv['expected_counts'].values()), 'inventory_counts')
        expected = []
        for family, count in zip(FAMILIES, COUNTS):
            values = ids[family]
            _require(type(values) is list and len(values) == count
                     and all(_string(v, 256) for v in values) and len(set(values)) == count, 'inventory_ids')
            expected.append((family, tuple(values)))
        pins = inv.get('source_hashes')
        _require(type(pins) is list and len(pins) == 82, 'inventory_pins')
        parsed = []
        for pin in pins:
            _keys(pin, ('path', 'bytes', 'sha256'), 'inventory_pins')
            _require(_safe_path(pin['path']) and type(pin['bytes']) is int and pin['bytes'] > 0
                     and type(pin['sha256']) is str and SHA64.fullmatch(pin['sha256']), 'inventory_pins')
            parsed.append(SourcePin(**pin))
        _require(len({p.path for p in parsed}) == 82, 'inventory_pins')
        return Contract(checkpoint_sha, CANDIDATE_SHA, hashlib.sha256(raw).hexdigest(), tuple(expected), tuple(parsed))
    except (KeyError, TypeError, AttributeError, UnicodeError):
        raise ContractError('checkpoint_contract') from None


def _identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_mode, st.st_nlink, st.st_uid)


def _open_dir(path: Path, *, owned=False, protected=False):
    """Walk absolute components with openat/O_NOFOLLOW, retaining the final fd."""
    _require(path.is_absolute() and _string(str(path), 4096), 'unsafe_input')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in path.parts[1:]:
            _require(component not in ('', '.', '..'), 'unsafe_input')
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        st = os.fstat(fd)
        if owned:
            _require(st.st_uid == os.getuid(), 'unsafe_input')
        if protected:
            _require(not st.st_mode & 0o022, 'unsafe_output')
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read_regular(root: Path, relative: str, *, limit=MAX_MANIFEST):
    try:
        return _read_regular_impl(root, relative, limit=limit)
    except OSError:
        raise ContractError('unsafe_input') from None


def _read_regular_impl(root: Path, relative: str, *, limit):
    """Return bytes and inode snapshot, never following links or opening special files."""
    _require(_safe_path(relative), 'unsafe_input')
    directory = _open_dir(root, owned=True)
    try:
        components = relative.split('/')
        for component in components[:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(components[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        try:
            before = os.fstat(fd)
            _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.getuid(), 'unsafe_input')
            _require(before.st_size <= limit, 'input_size')
            chunks = []
            length = 0
            while True:
                chunk = os.read(fd, 1024*1024)
                if not chunk:
                    break
                length += len(chunk)
                _require(length <= limit, 'input_size')
                chunks.append(chunk)
            after = os.fstat(fd)
            current = os.stat(components[-1], dir_fd=directory, follow_symlinks=False)
            _require(_identity(before) == _identity(after) == _identity(current) and length == before.st_size, 'input_drift')
            return b''.join(chunks), _identity(after)
        finally:
            os.close(fd)
    finally:
        os.close(directory)


def _snapshot(root, path):
    fd = _open_dir(root, owned=True)
    try:
        pieces = path.split('/')
        for part in pieces[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return _identity(os.stat(pieces[-1], dir_fd=fd, follow_symlinks=False))
    finally:
        os.close(fd)


def _hash_regular(root, relative, limit, *, deadline):
    """Stream source bytes; the manifest never needs an in-memory source copy."""
    _require(_safe_path(relative), 'unsafe_input')
    directory = _open_dir(root, owned=True)
    try:
        pieces = relative.split('/')
        for piece in pieces[:-1]:
            child = os.open(piece, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(pieces[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        try:
            before = os.fstat(fd)
            _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                     and before.st_uid == os.getuid(), 'unsafe_input')
            _require(before.st_size <= limit, 'source_limit')
            digest, length = hashlib.sha256(), 0
            while chunk := os.read(fd, 1024*1024):
                _require(time.monotonic() < deadline, 'inspection_timeout')
                length += len(chunk)
                _require(length <= limit, 'source_limit')
                digest.update(chunk)
            snapshot = _identity(os.fstat(fd))
            _require(snapshot == _identity(before) == _identity(os.stat(pieces[-1], dir_fd=directory,
                     follow_symlinks=False)) and length == before.st_size, 'input_drift')
            return length, digest.hexdigest(), snapshot
        finally:
            os.close(fd)
    finally:
        os.close(directory)


def _walk_entries(root, *, deadline, include_git):
    """Stream a bounded no-follow tree with only the current directory open."""
    pending = ['']
    directories = 1
    while pending:
        _require(time.monotonic() < deadline, 'inspection_timeout')
        prefix = pending.pop()
        fd = _open_dir(root / prefix, owned=True)
        try:
            yield True, prefix, os.fstat(fd)
            # scandir streams names; only the current directory holds descriptors.
            with os.scandir(fd) as entries:
                for entry in entries:
                    _require(time.monotonic() < deadline, 'inspection_timeout')
                    name = entry.name
                    if not include_git and not prefix and name == '.git':
                        continue
                    path = prefix + name
                    _require(_safe_path(path), 'source_path')
                    st = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    if stat.S_ISDIR(st.st_mode):
                        directories += 1
                        _require(directories <= MAX_SOURCE_DIRECTORIES, 'source_directory_limit')
                        pending.append(path + '/')
                    else:
                        yield False, path, st
        finally:
            os.close(fd)


def _source_paths(root, *, deadline):
    """Independently enumerate source files, excluding root Git metadata."""
    paths = set()
    for directory, path, st in _walk_entries(root, deadline=deadline, include_git=False):
        if not directory:
            _require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1
                     and st.st_uid == os.getuid(), 'unsafe_input')
            paths.add(path)
            _require(len(paths) <= 100000, 'source_limit')
    return paths


def _ancestor_identities(parent, *, deadline):
    """Pin the output parent and collect its real inode ancestry, including mounts."""
    fd = _open_dir(parent, owned=True, protected=True)
    initial = os.fstat(fd)
    initial_identity = (initial.st_dev, initial.st_ino)
    ancestors = set()
    try:
        for _ in range(4096):
            _require(time.monotonic() < deadline, 'inspection_timeout')
            st = os.fstat(fd)
            identity = (st.st_dev, st.st_ino)
            if identity in ancestors:
                return ancestors, initial_identity
            ancestors.add(identity)
            child = os.open('..', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        raise ContractError('unsafe_output')
    finally:
        os.close(fd)


def _validate_output_location(candidate, output, *, deadline):
    """Reject any source/Git directory inode in the output parent's ancestry.

    This also catches a preexisting bind alias of a candidate descendant, where
    lexical paths and the candidate root inode alone cannot establish exclusion.
    No source files are opened and no directory is created by this pre-write scan.
    """
    _require(output.is_absolute() and output.name not in ('', '.', '..'), 'unsafe_output')
    ancestors, parent_identity = _ancestor_identities(output.parent, deadline=deadline)
    entries = _walk_entries(candidate, deadline=deadline, include_git=True)
    try:
        for directory, _, st in entries:
            if directory:
                _require((st.st_dev, st.st_ino) not in ancestors, 'unsafe_output')
    finally:
        entries.close()
    return parent_identity


def manifest_document(inspection):
    return dict(contract='workshop-final180-source-v1', candidate_sha=inspection.candidate_sha,
                members=[asdict(m) for m in inspection.source_manifest])


def _checkout_valid(observation, contract):
    _keys(observation, ('head', 'dirty', 'untracked', 'ignored', 'remotes', 'hooks', 'alternates', 'submodules'), 'checkout_schema')
    _require(observation['head'] == contract.candidate_sha, 'candidate_sha')
    for key in ('dirty', 'untracked', 'ignored', 'remotes', 'alternates', 'submodules'):
        _require(type(observation[key]) is tuple and not observation[key], 'checkout_' + key)
    hooks = observation['hooks']
    _require(type(hooks) is tuple and all(type(h) is HookEntry for h in hooks), 'checkout_hooks')
    _require(tuple(sorted(hooks, key=lambda h: h.path)) == hooks and len({h.path for h in hooks}) == len(hooks), 'checkout_hooks')
    for hook in hooks:
        _require(_safe_path(hook.path) and hook.path.startswith('.git/hooks/')
                 and len(hook.path.split('/')) == 3 and type(hook.mode) is str
                 and re.fullmatch(r'[0-7]{4}', hook.mode) and type(hook.sha256) is str
                 and SHA64.fullmatch(hook.sha256) and type(hook.active) is bool, 'checkout_hooks')
        _require(hook.path.rsplit('/', 1)[-1].endswith('.sample') and not hook.active, 'custom_hook')


def inspect_candidate(contract: Contract, candidate_root: Path, git: GitReader) -> SourceInspection:
    deadline = time.monotonic() + 300
    try:
        rootfd = _open_dir(candidate_root, owned=True)
        root_snapshot = _identity(os.fstat(rootfd))
        os.close(rootfd)
        initial_tool = git.tool_identity()
        _validate_tool(initial_tool)
        before = git.observe_checkout(candidate_root)
        _checkout_valid(before, contract)
        entries = git.tracked_entries(contract.candidate_sha)
        _require(type(entries) is tuple and len(entries) <= 100000, 'source_limit')
        members, snapshots, seen = [], {}, set()
        total = 0
        for path, mode, oid in entries:
            _require(time.monotonic() < deadline, 'inspection_timeout')
            _require(_safe_path(path) and path.split('/')[0] != '.git' and path not in seen, 'source_path')
            seen.add(path)
            _require(mode in ('100644', '100755') and type(oid) is str and SHA40.fullmatch(oid), 'source_mode')
            immutable = git.read_blob(contract.candidate_sha, path)
            total += len(immutable)
            _require(total <= 4*1024**3, 'source_limit')
            # Git object identity is checked as well as the complete SHA256 manifest.
            _require(hashlib.sha1(b'blob ' + str(len(immutable)).encode() + b'\0' + immutable).hexdigest() == oid, 'git_object_mismatch')
            length, digest, snapshot = _hash_regular(candidate_root, path, 4*1024**3-total+len(immutable), deadline=deadline)
            _require(bool(snapshot[5] & 0o111) == (mode == '100755'), 'source_mode')
            _require(length == len(immutable) and digest == hashlib.sha256(immutable).hexdigest(), 'source_mismatch')
            snapshots[path] = snapshot
            members.append(SourceMember(path, mode, length, digest))
        _require(_source_paths(candidate_root, deadline=deadline) == seen, 'source_members')
        manifest = tuple(sorted(members, key=lambda m: m.path))
        lookup = {m.path: m for m in manifest}
        for pin in contract.source_pins:
            member = lookup.get(pin.path)
            _require(member is not None and member.bytes == pin.bytes and member.sha256 == pin.sha256, 'source_pin_mismatch')
        for path, snapshot in snapshots.items():
            _require(_snapshot(candidate_root, path) == snapshot, 'source_drift')
        _require(_identity(candidate_root.stat(follow_symlinks=False)) == root_snapshot, 'source_drift')
        after = git.observe_checkout(candidate_root)
        _checkout_valid(after, contract)
        _require(after == before and git.tool_identity() == initial_tool, 'source_drift')
        for path, snapshot in snapshots.items():
            _require(_snapshot(candidate_root, path) == snapshot, 'source_drift')
        _require(time.monotonic() < deadline, 'inspection_timeout')
        result = SourceInspection(contract.candidate_sha, '', manifest)
        raw = canonical(manifest_document(result))
        _require(len(raw) <= MAX_MANIFEST, 'source_manifest_size')
        _require(time.monotonic() < deadline, 'inspection_timeout')
        return SourceInspection(contract.candidate_sha, hashlib.sha256(raw).hexdigest(), manifest)
    except OSError:
        raise ContractError('unsafe_input') from None


def load_observations(raw: bytes, contract: Contract) -> tuple[Observation, ...]:
    document = load_json_strict(raw, max_bytes=4*1024*1024)
    _keys(document, ('contract', 'candidate_sha', 'observations'), 'observation_schema')
    _require(document['contract'] == 'workshop-final180-observations-v1', 'observation_contract')
    _require(document['candidate_sha'] == contract.candidate_sha, 'observation_candidate')
    rows = document['observations']
    _require(type(rows) is list, 'observation_schema')
    _require(len(rows) <= 512, 'observation_count_exceeded')
    result = []
    for row in rows:
        _keys(row, ('family', 'logical_id', 'status', 'raw_refs'), 'observation_schema')
        _require(type(row['family']) is str and row['family'] in FAMILIES
                 and _string(row['logical_id'], 256) and type(row['status']) is str
                 and row['status'] in ('passed', 'failed', 'skipped', 'unavailable'), 'observation_schema')
        refs = row['raw_refs']
        _require(type(refs) is list and len(refs) <= 256
                 and all(_safe_path(ref, 1024) for ref in refs) and len(set(refs)) == len(refs), 'observation_refs')
        result.append(Observation(row['family'], row['logical_id'], row['status'], tuple(refs)))
    return tuple(result)


def reconcile(observed: tuple[Observation, ...], contract: Contract) -> tuple[str, ...]:
    failures = []
    for family, expected in contract.expected_ids:
        rows = [row for row in observed if row.family == family]
        counts = Counter(row.logical_id for row in rows)
        for logical_id in expected:
            if not counts[logical_id]:
                failures.append(f'missing:{family}:{logical_id}')
        duplicated = set()
        for row in rows:
            if row.logical_id not in expected:
                failures.append(f'extra:{family}:{row.logical_id}')
            if counts[row.logical_id] > 1 and row.logical_id not in duplicated:
                failures.append(f'duplicate:{family}:{row.logical_id}')
                duplicated.add(row.logical_id)
            if row.status != 'passed':
                failures.append(f'nonpass:{family}:{row.logical_id}:{row.status}')
    return tuple(failures)


def _validate_tool(identity):
    _require(type(identity) is GitToolIdentity and _string(identity.path, 4096)
             and Path(identity.path).is_absolute() and type(identity.sha256) is str and SHA64.fullmatch(identity.sha256)
             and _string(identity.version, 256) and '\n' not in identity.version
             and '\r' not in identity.version, 'git_tool_identity')


class ProductionGitReader:
    """Only fixed, isolated, bounded read-only Git commands are available."""
    def __init__(self, tooling_root: Path):
        self.tooling_root = tooling_root
        self.deadline = time.monotonic() + 300
        self.home = tempfile.TemporaryDirectory(prefix='final180-git-home-')
        self.env = dict(PATH=FIXED_PATH, HOME=self.home.name, GIT_CONFIG_NOSYSTEM='1',
                        GIT_CONFIG_GLOBAL='/dev/null', GIT_TERMINAL_PROMPT='0', GIT_NO_REPLACE_OBJECTS='1',
                        GIT_NO_LAZY_FETCH='1')
        self.identity = None
        try:
            path = shutil.which('git', path=FIXED_PATH)
            _require(path is not None, 'git_tool_discovery')
            self.executable = Path(path).resolve(strict=True)
            _require(_string(str(self.executable), 4096) and self.executable.is_file()
                     and os.access(self.executable, os.X_OK), 'git_tool_discovery')
            self.tool_hash = self._hash_executable()
            version = self._capture((str(self.executable), '--version'))
            if version.endswith(b'\n'):
                version = version[:-1]
            _require(len(version) <= 256 and b'\n' not in version and b'\r' not in version and bool(version), 'git_tool_discovery')
            self.identity = GitToolIdentity(str(self.executable), self.tool_hash, version.decode('utf-8'))
            self.tool_identity()
            self._validate_tooling_metadata()
        except BaseException as exc:
            self.home.cleanup()
            if isinstance(exc, (OSError, UnicodeError)):
                exc = ContractError('git_tool_discovery')
            if self.identity is not None:
                exc.git_tool = self.identity
            raise exc

    def close(self):
        self.home.cleanup()

    def _hash_executable(self):
        try:
            fd = os.open(self.executable, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                before = _identity(os.fstat(fd))
                _require(stat.S_ISREG(before[5]) and bool(before[5] & 0o111), 'git_tool_drift')
                _require(before == getattr(self, '_executable_snapshot', before), 'git_tool_drift')
                self._executable_snapshot = before
                h = hashlib.sha256()
                while chunk := os.read(fd, 1024*1024):
                    h.update(chunk)
                _require(before == _identity(os.fstat(fd))
                         == _identity(self.executable.stat(follow_symlinks=False)), 'git_tool_drift')
                return h.hexdigest()
            finally:
                os.close(fd)
        except OSError:
            raise ContractError('git_tool_drift') from None

    @staticmethod
    def _validate_config(config):
        try:
            text = config.decode('utf-8')
        except UnicodeError:
            raise ContractError('git_config') from None
        # Accept only the passive grammar emitted by ordinary clones/worktrees.
        # Git also supports same-line assignments, implicit booleans, legacy
        # dotted sections and continuations; reject those forms rather than
        # accidentally overlooking a helper or lazy-fetch configuration.
        allowed = {
            'core': {'repositoryformatversion', 'filemode', 'bare', 'logallrefupdates',
                     'ignorecase', 'precomposeunicode', 'symlinks', 'quotepath',
                     'protecthfs', 'protectntfs', 'warnambiguousrefs', 'abbrev',
                     'sparsecheckout', 'sparsecheckoutcone'},
            'extensions': {'worktreeconfig', 'objectformat', 'refstorage', 'relativeworktrees'},
            'remote': {'url', 'fetch'},
            'branch': {'remote', 'merge', 'description'},
            'user': {'name', 'email'},
            'codex': {'bookkeeping', 'localenvironmentconfigpath'},
        }
        text = text.replace('\r\n', '\n')
        _require('\\' not in text and all(ord(c) >= 32 or c in '\n\t' for c in text), 'git_config')
        section = None
        for line in text.split('\n'):
            line = line.strip(' \t')
            if not line or line.startswith(('#', ';')):
                continue
            if line.startswith('['):
                header = re.fullmatch(r'\[([A-Za-z][A-Za-z0-9-]*)(?:[ \t]+"[^"\\]*")?\][ \t]*(?:[#;].*)?', line)
                _require(header is not None, 'git_config')
                section = header.group(1).lower()
                _require(section in allowed, 'git_config')
            else:
                assignment = re.fullmatch(r'([A-Za-z][A-Za-z0-9-]*)[ \t]*=[ \t]*(.*)', line)
                _require(section is not None and assignment is not None, 'git_config')
                _require(assignment.group(1).lower() in allowed[section], 'git_config')

    @classmethod
    def _validate_worktree_config(cls, gitdir):
        path = gitdir / 'config.worktree'
        if path.exists() or path.is_symlink():
            config, _ = _read_regular(gitdir, 'config.worktree', limit=1024*1024)
            cls._validate_config(config)

    @classmethod
    def _validate_metadata(cls, gitdir):
        fd = _open_dir(gitdir, owned=True)
        os.close(fd)
        config, _ = _read_regular(gitdir, 'config', limit=1024*1024)
        cls._validate_config(config)
        cls._validate_worktree_config(gitdir)
        info = gitdir / 'info'
        if info.exists() or info.is_symlink():
            fd = _open_dir(info, owned=True)
            try:
                try:
                    os.stat('attributes', dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise ContractError('git_attributes')
            finally:
                os.close(fd)
        objects = _open_dir(gitdir / 'objects', owned=True)
        try:
            try:
                info = os.open('info', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=objects)
            except FileNotFoundError:
                return
            os.close(info)
        finally:
            os.close(objects)
        for name in ('alternates', 'http-alternates'):
            path = gitdir / 'objects/info' / name
            _require(not path.exists() and not path.is_symlink(), 'checkout_alternates')

    def _validate_tooling_metadata(self):
        dotgit = self.tooling_root / '.git'
        if stat.S_ISREG(dotgit.stat(follow_symlinks=False).st_mode):
            raw, _ = _read_regular(self.tooling_root, '.git', limit=4096)
            _require(raw.startswith(b'gitdir: ') and raw.endswith(b'\n') and raw.count(b'\n') == 1, 'git_metadata')
            try:
                value = raw[8:-1].decode('utf-8')
            except UnicodeError:
                raise ContractError('git_metadata') from None
            gitdir = Path(os.path.abspath(self.tooling_root / value))
            common, _ = _read_regular(gitdir, 'commondir', limit=4096)
            try:
                value = common.decode('utf-8').removesuffix('\n')
            except UnicodeError:
                raise ContractError('git_metadata') from None
            _require(_string(value, 4096) and '\x00' not in value and '\n' not in value, 'git_metadata')
            self._validate_metadata(Path(os.path.abspath(gitdir / value)))
            self._validate_worktree_config(gitdir)
        else:
            self._validate_metadata(dotgit)

    def tool_identity(self):
        _require(self._hash_executable() == self.tool_hash, 'git_tool_drift')
        _validate_tool(self.identity)
        return self.identity

    def _capture(self, argv, *, allow_one=False):
        _require(time.monotonic() < self.deadline, 'inspection_timeout')
        deadline = min(self.deadline, time.monotonic() + 30)
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=self.env, shell=False)
        selector = selectors.DefaultSelector()
        out, err = bytearray(), bytearray()
        try:
            stdout_limit = 257 if argv == (str(self.executable), '--version') else MAX_MANIFEST
            selector.register(proc.stdout, selectors.EVENT_READ, (out, stdout_limit))
            selector.register(proc.stderr, selectors.EVENT_READ, (err, 1024*1024))
            while selector.get_map():
                _require(time.monotonic() < deadline, 'git_timeout')
                for key, _ in selector.select(min(0.1, max(0, deadline-time.monotonic()))):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    else:
                        target, ceiling = key.data
                        _require(len(target) + len(chunk) <= ceiling, 'git_output_size')
                        target.extend(chunk)
            code = proc.wait(timeout=max(0.001, deadline-time.monotonic()))
            _require(code == 0 or (allow_one and code == 1), 'git_read_failed')
            return bytes(out)
        except subprocess.TimeoutExpired:
            raise ContractError('git_timeout') from None
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            selector.close()
            proc.stdout.close()
            proc.stderr.close()

    def _git(self, root, command, *, allow_one=False):
        self.tool_identity()
        argv = (str(self.executable), '--no-optional-locks', '-c', 'core.hooksPath=/dev/null',
                '-c', 'core.fsmonitor=false', '-c', 'protocol.file.allow=never', '-C', str(root)) + command
        result = self._capture(argv, allow_one=allow_one)
        self.tool_identity()
        return result

    def read_blob(self, sha, path):
        _require(type(sha) is str and SHA40.fullmatch(sha) and _safe_path(path), 'git_ref')
        return self._git(self.tooling_root, ('cat-file', 'blob', sha + ':' + path))

    def tracked_entries(self, sha):
        _require(type(sha) is str and SHA40.fullmatch(sha), 'git_ref')
        raw = self._git(self.tooling_root, ('ls-tree', '-r', '-z', sha))
        entries = []
        try:
            _require(not raw or raw.endswith(b'\0'), 'git_tree')
            for row in raw.split(b'\0')[:-1]:
                meta, path = row.split(b'\t', 1)
                mode, kind, oid = meta.decode('ascii').split(' ')
                _require(kind == 'blob' and mode in ('100644', '100755'), 'source_mode')
                entries.append((path.decode('utf-8'), mode, oid))
            _require(len(entries) <= 100000, 'source_limit')
            return tuple(entries)
        except (ValueError, UnicodeError):
            raise ContractError('git_tree') from None

    def runner_sha(self):
        value = self._git(self.tooling_root, ('rev-parse', '--verify', 'HEAD')).decode('ascii').removesuffix('\n')
        _require(SHA40.fullmatch(value), 'runner_sha')
        return value

    def observe_checkout(self, root):
        try:
            # A candidate must be a plain clone. Tooling may be an owned worktree.
            fd = _open_dir(root / '.git', owned=True)
            os.close(fd)
            self._validate_metadata(root / '.git')
            hooks = []
            hook_dir = root / '.git/hooks'
            if hook_dir.exists() or hook_dir.is_symlink():
                hfd = _open_dir(hook_dir, owned=True)
                try:
                    for name in sorted(os.listdir(hfd)):
                        _require('/' not in name and _safe_path(name), 'custom_hook')
                        data, snapshot = _read_regular(root, '.git/hooks/' + name, limit=MAX_MANIFEST)
                        mode = stat.S_IMODE(snapshot[5])
                        sample = name.endswith('.sample')
                        hooks.append(HookEntry('.git/hooks/' + name, f'{mode:04o}', hashlib.sha256(data).hexdigest(),
                                               not sample and name in HOOK_NAMES and bool(mode & 0o111)))
                        _require(sample, 'custom_hook')
                finally:
                    os.close(hfd)
            alternates = root / '.git/objects/info/alternates'
            _require(not alternates.exists() and not alternates.is_symlink(), 'checkout_alternates')
            head = self._git(root, ('rev-parse', '--verify', 'HEAD')).decode('ascii').removesuffix('\n')
            _require(SHA40.fullmatch(head), 'candidate_sha')
            branch = self._git(root, ('symbolic-ref', '-q', 'HEAD'), allow_one=True)
            _require(not branch, 'candidate_not_detached')
            status = self._git(root, ('status', '--porcelain=v1', '-z', '--untracked-files=all', '--ignored'))
            dirty, untracked, ignored = [], [], []
            # We reject every nonempty status, so rename continuation need not be interpreted.
            for row in status.split(b'\0'):
                if row:
                    _require(len(row) <= 4099, 'checkout_schema')
                    value = row[3:].decode('utf-8')
                    (untracked if row[:2] == b'??' else ignored if row[:2] == b'!!' else dirty).append(value)
            remote = self._git(root, ('remote',)).decode('utf-8').splitlines()
            _require(all(_string(v, 4096) for v in remote), 'checkout_schema')
            # Submodule mode is also rejected by immutable tree admission.
            submodules = ('.gitmodules',) if (root / '.gitmodules').exists() else ()
            return dict(head=head, dirty=tuple(dirty), untracked=tuple(untracked), ignored=tuple(ignored),
                        remotes=tuple(remote), hooks=tuple(hooks), alternates=(), submodules=submodules)
        except (OSError, UnicodeError):
            raise ContractError('unsafe_input') from None


class _PrivateOutput:
    def __init__(self, root, *, expected_parent):
        self.root = root
        _require(root.is_absolute() and root.name not in ('', '.', '..'), 'unsafe_output')
        self.parent = _open_dir(root.parent, owned=True, protected=True)
        self.fd = None
        try:
            st = os.fstat(self.parent)
            _require((st.st_dev, st.st_ino) == expected_parent, 'output_drift')
            os.mkdir(root.name, mode=0o700, dir_fd=self.parent)
            self.fd = os.open(root.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.parent)
            self.snapshot = _identity(os.fstat(self.fd))
            _require(stat.S_IMODE(self.snapshot[5]) == 0o700, 'unsafe_output')
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        if self.parent is not None:
            os.close(self.parent)
            self.parent = None

    def write(self, name, raw, limit):
        _require(name in ('diagnostic.json', 'source-manifest.json') and len(raw) <= limit, 'output_size')
        _require(_identity(os.stat(self.root.name, dir_fd=self.parent, follow_symlinks=False))[:2] == self.snapshot[:2], 'output_drift')
        temporary = '.' + name + '.' + secrets.token_hex(8) + '.tmp'
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=self.fd)
        try:
            position = 0
            while position < len(raw):
                position += os.write(fd, raw[position:position+1024*1024])
            os.fsync(fd)
            _require(stat.S_IMODE(os.fstat(fd).st_mode) == 0o600, 'unsafe_output')
        finally:
            os.close(fd)
        _require(_identity(os.stat(self.root.name, dir_fd=self.parent, follow_symlinks=False))[:2] == self.snapshot[:2], 'output_drift')
        # The root was exclusively created. Replacement permits a bounded interrupted
        # diagnostic to supersede our own completed write after an interrupted fsync.
        os.replace(temporary, name, src_dir_fd=self.fd, dst_dir_fd=self.fd)
        os.fsync(self.fd)


def _interrupted(_signum, _frame):
    raise KeyboardInterrupt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Offline source/claim diagnostics only; no measured execution or acceptance.', allow_abbrev=False)
    commands = parser.add_subparsers(dest='mode', required=True)
    for mode in ('inspect', 'reconcile'):
        sub = commands.add_parser(mode, allow_abbrev=False)
        sub.add_argument('--checkpoint-sha', required=True)
        sub.add_argument('--candidate-root', required=True, type=Path)
        sub.add_argument('--output-root', required=True, type=Path)
        if mode == 'reconcile':
            sub.add_argument('--observations', required=True, type=Path)
    args = parser.parse_args(argv)
    output = git = contract = inspection = None
    tool = None
    observations_hash = None
    observation_snapshot = None
    runner_sha = None
    rows = ()
    failures = ()
    status, code = 'unavailable', 2
    handlers = {}
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            handlers[sig] = signal.signal(sig, _interrupted)
        try:
            _require(args.candidate_root.is_absolute(), 'unsafe_input')
            candidate_fd = _open_dir(args.candidate_root, owned=True)
            os.close(candidate_fd)
            _require(not args.output_root.is_relative_to(args.candidate_root), 'unsafe_output')
            parent_identity = _validate_output_location(args.candidate_root, args.output_root,
                                                        deadline=time.monotonic() + 300)
            output = _PrivateOutput(args.output_root, expected_parent=parent_identity)
            git = ProductionGitReader(Path(__file__).resolve().parents[2])
            tool = asdict(git.tool_identity())
            runner_sha = git.runner_sha()
            contract = load_contract(args.checkpoint_sha, git)
            inspection = inspect_candidate(contract, args.candidate_root, git)
            if args.mode == 'reconcile':
                _require(args.observations.is_absolute(), 'unsafe_input')
                raw, observation_snapshot = _read_regular(args.observations.parent, args.observations.name, limit=4*1024*1024)
                observations_hash = hashlib.sha256(raw).hexdigest()
                rows = load_observations(raw, contract)
                failures = reconcile(rows, contract)
                _require(_snapshot(args.observations.parent, args.observations.name) == observation_snapshot, 'input_drift')
            status, code = ('inconsistent', 1) if failures else ('consistent', 0)
        except KeyboardInterrupt as exc:
            status, code, failures = 'interrupted', 1, ('interrupted',)
            identity = getattr(exc, 'git_tool', None) or getattr(git, 'identity', None)
            if identity is not None:
                tool = asdict(identity)
        except ContractError as exc:
            failures = (str(exc),)
            if getattr(exc, 'git_tool', None) is not None:
                tool = asdict(exc.git_tool)
            elif getattr(git, 'identity', None) is not None:
                tool = asdict(git.identity)
        except (OSError, ValueError, TypeError):
            failures = ('unsafe_input',)
        if output is None:
            return code
        diagnostic = dict(contract='workshop-final180-offline-diagnostic-v1', mode=args.mode,
            checkpoint_sha=args.checkpoint_sha if SHA40.fullmatch(args.checkpoint_sha) else None,
            runner_sha=runner_sha, candidate_sha=contract.candidate_sha if contract else CANDIDATE_SHA,
            inventory_sha256=contract.inventory_sha256 if contract else None,
            source_manifest_sha256=inspection.source_manifest_sha256 if inspection else None,
            observations_sha256=observations_hash, git_tool=tool, status=status,
            observed_counts={family: sum(row.family == family for row in rows) for family in FAMILIES},
            failures=list(failures), authority=dict.fromkeys(AUTHORITY, False))
        raw = canonical(diagnostic)
        if len(raw) > MAX_DIAGNOSTIC:
            diagnostic.update(status='unavailable', failures=['diagnostic_size_invariant'])
            raw, code = canonical(diagnostic), 2
        try:
            if inspection is not None:
                output.write('source-manifest.json', canonical(manifest_document(inspection)), MAX_MANIFEST)
            output.write('diagnostic.json', raw, 4*1024*1024)
        except KeyboardInterrupt:
            diagnostic.update(status='interrupted', failures=['interrupted'])
            # A second signal cannot turn an interrupted diagnostic into success or
            # prevent this final small atomic retention write.
            for sig in handlers:
                signal.signal(sig, signal.SIG_IGN)
            output.write('diagnostic.json', canonical(diagnostic), 4*1024*1024)
            code = 1
        except (OSError, ContractError):
            diagnostic.update(status='unavailable', failures=['output_failed'])
            try:
                output.write('diagnostic.json', canonical(diagnostic), 4*1024*1024)
            except (OSError, ContractError):
                return 2
            code = 2
        print(str(args.output_root / 'diagnostic.json') + ' ' + diagnostic['status'])
        return code
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        if output is not None:
            output.close()
        if git is not None:
            git.close()


if __name__ == '__main__':
    raise SystemExit(main())
