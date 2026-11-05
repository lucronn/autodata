"""Authenticated-v3 workshop adapter library; no executable activation entry point.

All authority is supplied independently. Imports perform no I/O beyond loading
fixed sibling contract code. No default credentials, token discovery or v2
simulation receipts participate in authenticated verification.
"""
import binascii
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import functools
import http.client
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import selectors
import signal
import socket
import ssl
import stat
import struct
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlsplit
import zlib

HERE = Path(__file__).resolve().parent
MiB = 1048576
WORKFLOW = 'lucronn/autodata/.github/workflows/release-workshop.yml@refs/heads/master'
CONTEXT_FIELDS = ('protocol_version environment repository repository_id repository_owner_id run_id run_attempt '
                  'workflow_ref workflow_sha source_sha service_config_sha256 protected_environment '
                  'activation_sha256 toolchain_sha256 trust_policy_sha256').split()
LIVE_FIELDS = CONTEXT_FIELDS + 'manifest_sha256 candidate_digest candidate_run_id candidate_run_attempt'.split()
OWNED = ('api', 'ingestion', 'migration')
UPSTREAM = ('caddy', 'postgres', 'nats', 'minio')


class AdapterError(ValueError):
    """Only fixed, redacted error codes cross this boundary."""


def require(condition, code='invalid_input'):
    if not condition: raise AdapterError(code)


def _sibling(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rt = _sibling('publisher_runtime_v1', 'runtime-check.py')
ops = _sibling('publisher_cloud_v1', 'cloud-ops.py')


def canonical(value):
    try: return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (ValueError, TypeError, UnicodeError, RecursionError): raise AdapterError('invalid_input') from None


def digest(data):
    require(type(data) is bytes)
    return hashlib.sha256(data).hexdigest()


def _bounds(value, depth=1):
    require(depth <= 32)
    if type(value) is dict:
        require(len(value) <= 1024)
        for key, item in value.items():
            require(type(key) is str and len(key.encode('utf-8')) <= 1024)
            _bounds(item, depth + 1)
    elif type(value) is list:
        require(len(value) <= 4096)
        for item in value: _bounds(item, depth + 1)
    elif type(value) is str: require(len(value.encode('utf-8')) <= 16384)
    else: require(value is None or type(value) in (bool, int))


def strict_json(data, maximum=MiB):
    require(type(data) is bytes and 0 < len(data) <= maximum)
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result)
            result[key] = value
        return result
    def invalid(_): raise AdapterError('invalid_input')
    try:
        value = json.loads(data.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)
        _bounds(value)
        canonical(value)
        return value
    except (ValueError, UnicodeError, RecursionError): raise AdapterError('invalid_input') from None


def object_fields(value, fields):
    require(type(value) is dict and set(value) == set(fields))
    strict_json(canonical(value))


def match(value, pattern): require(type(value) is str and re.fullmatch(pattern, value) is not None)
def sha(value): match(value, r'[0-9a-f]{64}')
def source(value): match(value, r'[0-9a-f]{40}')
def numeric(value): match(value, r'[1-9][0-9]{0,19}')
def integer(value, low, high): require(type(value) is int and low <= value <= high)


def utc(value):
    match(value, r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z')
    try: return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except ValueError: raise AdapterError('invalid_input') from None


def validate_context(context, *, live=False):
    object_fields(context, LIVE_FIELDS if live else CONTEXT_FIELDS)
    require(type(context['protocol_version']) is int and context['protocol_version'] == 3)
    require(context['environment'] == 'staging' and context['repository'] == 'lucronn/autodata')
    require(context['workflow_ref'] == WORKFLOW and context['protected_environment'] == 'workshop-staging-publish')
    for name in ('repository_id', 'repository_owner_id', 'run_id'): numeric(context[name])
    integer(context['run_attempt'], 1, 1000)
    for name in ('source_sha', 'workflow_sha'): source(context[name])
    for name in ('service_config_sha256', 'activation_sha256', 'toolchain_sha256', 'trust_policy_sha256'): sha(context[name])
    if live:
        sha(context['manifest_sha256']); immutable(context['candidate_digest'])
        numeric(context['candidate_run_id']); integer(context['candidate_run_attempt'], 1, 1000)
    return context


def validate_run(run, context, *, completed):
    """Finite real REST projection; extra documented provider fields are allowed."""
    strict_json(canonical(run), 65536)
    try:
        require(type(run['id']) is int and str(run['id']) == context['run_id'])
        require(type(run['run_attempt']) is int and run['run_attempt'] == context['run_attempt'])
        require(run['head_sha'] == context['workflow_sha'] and run['head_branch'] == 'master')
        require(run['event'] == 'workflow_dispatch' and run['path'] == '.github/workflows/release-workshop.yml')
        require(type(run['repository']['id']) is int and str(run['repository']['id']) == context['repository_id'])
        require(type(run['repository']['owner']['id']) is int and str(run['repository']['owner']['id']) == context['repository_owner_id'])
        require(run['repository']['full_name'] == context['repository'])
        require(run['status'] == ('completed' if completed else 'in_progress'))
        require(run['conclusion'] == ('success' if completed else None))
        require(utc(run['run_started_at']) <= utc(run['updated_at']))
    except (KeyError, TypeError): raise AdapterError('identity_mismatch') from None
    return {key: run[key] for key in ('id', 'run_attempt', 'event', 'head_branch', 'head_sha', 'path', 'status', 'conclusion', 'repository', 'run_started_at', 'updated_at')}


def immutable(value):
    match(value, r'[a-z0-9][a-z0-9./:_-]{0,500}@sha256:[0-9a-f]{64}')


def validate_url(url, origins, *, signed=False):
    require(type(url) is str and 0 < len(url) <= 8192)
    require(not any(ord(c) < 33 or ord(c) == 127 for c in url) and '\\' not in url)
    try:
        parsed = urlsplit(url)
        require(parsed.scheme == 'https' and parsed.hostname in origins and parsed.port in (None, 443))
        require(not parsed.username and not parsed.password and not parsed.fragment and (signed or not parsed.query))
        require(parsed.netloc == parsed.hostname or parsed.netloc == parsed.hostname + ':443')
        try: ipaddress.ip_address(parsed.hostname)
        except ValueError: pass
        else: raise AdapterError('invalid_input')
        require(parsed.hostname not in ('metadata.google.internal', 'localhost'))
        return parsed
    except (ValueError, TypeError): raise AdapterError('invalid_input') from None


def _extra(data):
    seen = set(); offset = 0; values = {}
    while offset < len(data):
        require(offset + 4 <= len(data))
        kind, size = struct.unpack_from('<HH', data, offset); offset += 4
        require(kind in (0x5455, 0x000a) and kind not in seen and offset + size <= len(data))
        seen.add(kind); value = data[offset:offset + size]; offset += size
        if kind == 0x5455:
            require(size >= 1 and value[0] in (1, 3, 5, 7) and size == 1 + 4 * value[0].bit_count())
            values[kind] = value[1:5]
        else:
            require(size == 32 and value[:4] == b'\0' * 4 and value[4:8] == b'\x01\x00\x18\x00')
            values[kind] = value[8:]
    return values


def decode_actions_outer_zip(data: bytes, expected_inner_sha256: str, expected_inner_bytes: int) -> bytes:
    """Decode a strict one-member Actions ZIP32 without filesystem extraction."""
    sha(expected_inner_sha256); integer(expected_inner_bytes, 1, 8 * MiB)
    require(type(data) is bytes and 98 <= len(data) <= 16 * MiB)
    try:
        end = struct.unpack_from('<4s4H2IH', data, len(data) - 22)
        require(end[:5] == (b'PK\x05\x06', 0, 0, 1, 1) and end[7] == 0)
        cd_size, cd_offset = end[5:7]
        require(cd_offset + cd_size == len(data) - 22)
        central = struct.unpack_from('<4s6H3I5H2I', data, cd_offset)
        require(central[0] == b'PK\x01\x02')
        _, made, needed, flags, method, mtime, mdate, crc, packed, size, nlen, xlen, clen, disk, attrs, ext, offset = central
        require(needed <= 20 and flags & ~0x808 == 0 and method in (0, 8))
        require(nlen == 11 and clen == disk == offset == 0 and size == expected_inner_bytes)
        require(packed <= 16 * MiB and cd_size == 46 + nlen + xlen)
        require(data[cd_offset + 46:cd_offset + 57] == b'release.zip')
        central_extra = _extra(data[cd_offset + 57:cd_offset + cd_size])
        require(made >> 8 in (0, 3) and not ext & 0x18)
        if made >> 8 == 3: require(stat.S_IFMT(ext >> 16) in (0, stat.S_IFREG))
        local = struct.unpack_from('<4s5H3I2H', data, 0)
        require(local[:6] == (b'PK\x03\x04', needed, flags, method, mtime, mdate))
        require(local[9] == 11 and data[30:41] == b'release.zip')
        lcrc, lpacked, lsize, _, lxlen = local[6:]
        local_extra = _extra(data[41:41 + lxlen])
        require(all(local_extra[key] == value for key,value in central_extra.items() if key in local_extra))
        start = 41 + lxlen; finish = start + packed
        require(finish <= cd_offset)
        if flags & 8:
            require((lcrc, lpacked, lsize) in ((0, 0, 0), (crc, packed, size)))
            descriptor = data[finish:cd_offset]
            if len(descriptor) == 16:
                require(descriptor[:4] == b'PK\x07\x08'); descriptor = descriptor[4:]
            require(len(descriptor) == 12 and struct.unpack('<III', descriptor) == (crc, packed, size))
        else: require((lcrc, lpacked, lsize) == (crc, packed, size) and finish == cd_offset)
        payload = data[start:finish]
        if method == 8:
            decoder = zlib.decompressobj(-15)
            inner = decoder.decompress(payload, size + 1)
            require(len(inner) == size and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail)
        else: inner = payload
        require(len(inner) == size and binascii.crc32(inner) == crc and digest(inner) == expected_inner_sha256)
        return inner
    except (struct.error, zlib.error, IndexError): raise AdapterError('invalid_archive') from None


class Budget:
    """One monotonic total deadline, with cleanup reserve inside it."""
    def __init__(self, seconds=7200, *, clock=time.monotonic):
        require(0 < seconds <= 7200)
        self.clock = clock; self.end = clock() + seconds
    def deadline(self, seconds):
        remaining = self.end - self.clock() - 30
        require(remaining > 0, 'operation_timed_out')
        return min(self.end - 30, self.clock() + seconds)
    def check(self, deadline): require(self.clock() < deadline, 'operation_timed_out')


@contextmanager
def private_workspace():
    with tempfile.TemporaryDirectory(prefix='workshop-publisher-') as directory:
        os.chmod(directory, 0o700)
        yield Path(directory)


def _private_parent(parent):
    fd=os.open(parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        info=os.fstat(fd)
        require(stat.S_ISDIR(info.st_mode) and info.st_uid==os.getuid() and stat.S_IMODE(info.st_mode)==0o700)
        return fd
    except BaseException:
        os.close(fd); raise


def private_write(parent, name, data):
    require(type(data) is bytes and re.fullmatch(r'[a-zA-Z0-9._-]+', name) is not None)
    directory=_private_parent(parent)
    try:
        fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
        try:
            with os.fdopen(fd,'wb') as stream: stream.write(data)
        except BaseException:
            os.unlink(name,dir_fd=directory); raise
    finally: os.close(directory)
    return parent / name


def private_read(parent, name, maximum):
    require(re.fullmatch(r'[a-zA-Z0-9._-]+', name) is not None)
    directory=_private_parent(parent)
    try:
        fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
        try:
            st=os.fstat(fd)
            require(stat.S_ISREG(st.st_mode) and st.st_uid==os.getuid() and st.st_nlink==1)
            require(stat.S_IMODE(st.st_mode)==0o600 and 0<st.st_size<=maximum)
            with os.fdopen(fd,'rb',closefd=False) as stream: data=stream.read(maximum+1)
            after=os.fstat(fd)
            require((after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)==(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns))
            require(len(data)==st.st_size and len(data)<=maximum)
            return data
        finally: os.close(fd)
    finally: os.close(directory)


_process_owner = False


def bounded_process(argv, *, cwd, deadline, maximum=65536, input_bytes=None, env=None):
    """Own one isolated child group; cancellation records a flag until cleanup."""
    global _process_owner
    require(type(argv) is list and argv and Path(argv[0]).is_absolute())
    require(all(type(arg) is str and '\0' not in arg for arg in argv))
    safe_env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C', 'HOME': str(cwd),
                'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_TERMINAL_PROMPT': '0'}
    require(env is None or set(env) <= {'DOCKER_CONFIG', 'CLOUDSDK_CONFIG', 'GOOGLE_APPLICATION_CREDENTIALS'})
    safe_env.update(env or {})
    if input_bytes is not None:
        require(type(input_bytes) is bytes and len(input_bytes) <= 65536)
    require(threading.current_thread() is threading.main_thread() and
            hasattr(signal, 'pthread_sigmask') and not _process_owner, 'missing_dependency')
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
    if signal.SIGTERM in previous_mask:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        raise AdapterError('missing_dependency')
    previous_handler = signal.getsignal(signal.SIGTERM)
    process = None
    cancelled = False
    output = [bytearray(), bytearray()]
    _process_owner = True

    def cancel(signum, frame):
        nonlocal cancelled
        cancelled = True

    def check():
        require(not cancelled, 'operation_cancelled')
        require(time.monotonic() < deadline, 'operation_timed_out')

    try:
        signal.signal(signal.SIGTERM, cancel)
        # A pending signal now sets the flag. Never let this handler raise
        # across Popen's return/assignment, and never pass a blocked mask down.
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        check()
        process = subprocess.Popen(argv, cwd=cwd, env=safe_env, stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, umask=0o077)
        check()
        with selectors.DefaultSelector() as selector:
            for index, stream in enumerate((process.stdout, process.stderr)):
                os.set_blocking(stream.fileno(), False); selector.register(stream, selectors.EVENT_READ, index)
            pending = memoryview(input_bytes or b'')
            if process.stdin is not None:
                os.set_blocking(process.stdin.fileno(), False)
                if pending: selector.register(process.stdin, selectors.EVENT_WRITE, 2)
                else: process.stdin.close()
            while selector.get_map():
                check()
                for key, _ in selector.select(min(.1, max(0, deadline - time.monotonic()))):
                    if key.data == 2:
                        try: count = os.write(key.fd, pending)
                        except BlockingIOError: continue
                        pending = pending[count:]
                        if not pending: selector.unregister(key.fileobj); key.fileobj.close()
                    else:
                        try: chunk = os.read(key.fd, min(65536, maximum + 1))
                        except BlockingIOError: continue
                        if not chunk: selector.unregister(key.fileobj); continue
                        output[key.data].extend(chunk)
                        require(sum(map(len, output)) <= maximum, 'output_overflow')
            while True:
                check()
                try:
                    code = process.wait(timeout=min(.1, max(.001, deadline - time.monotonic())))
                    break
                except subprocess.TimeoutExpired: pass
        check()
        return code, bytes(output[0]), bytes(output[1])
    finally:
        # A second cancellation stays pending until all owned resources are
        # gone and the caller's signal policy has been restored.
        signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
        cleanup_failed = False
        try:
            if process is not None:
                try: os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError: pass
                except OSError: cleanup_failed = True
                try: process.wait(timeout=2)
                except subprocess.TimeoutExpired: pass
                except OSError: cleanup_failed = True
                # Always kill the group, even after its leader exits: another
                # group member may still own a pipe or ignore TERM.
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                except OSError: cleanup_failed = True
                try: process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired): cleanup_failed = True
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream is not None:
                        try: stream.close()
                        except OSError: cleanup_failed = True
        finally:
            try: signal.signal(signal.SIGTERM, previous_handler)
            finally:
                _process_owner = False
                # Last ownership action: pending SIGTERM follows caller policy
                # only after group cleanup, pipe closure and handler restore.
                signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        require(not cleanup_failed, 'cleanup_failed')


def _policy(policy, context):
    # The owner document's finite adapter projection is independent of the
    # observed images, artifacts or statements it will later verify.
    required=set(('activation_sha256 repository_id repository_owner_id workflow_sha toolchain_sha256 trust_policy_sha256 '
                  'tools storage_origins upstream_policy_sha256 approval_keys approvers registry evidence_layout').split())
    optional={'toolkit_lock_sha256','runtime_service_origin','host','publisher_principal'}
    require(type(policy) is dict and required<=set(policy), 'missing_dependency')
    require(set(policy)<=required|optional)
    strict_json(canonical(policy))
    require(policy['activation_sha256']==context['activation_sha256'], 'missing_dependency')
    for name in ('repository_id','repository_owner_id','workflow_sha','toolchain_sha256','trust_policy_sha256'):
        require(policy[name]==context[name], 'missing_dependency')
    sha(policy['upstream_policy_sha256'])
    require(type(policy['tools']) is dict and policy['tools'], 'missing_dependency')
    for pin in policy['tools'].values():
        object_fields(pin,('path','sha256','version'))
        require(Path(pin['path']).is_absolute()); sha(pin['sha256'])
        require(type(pin['version']) is str and 0<len(pin['version'])<=100)
    require(type(policy['storage_origins']) is list and 0<len(policy['storage_origins'])<=16, 'missing_dependency')
    for origin in policy['storage_origins']:
        match(origin,r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?')
        validate_url('https://'+origin+'/',{origin})
    require(type(policy['approval_keys']) is dict and 0<len(policy['approval_keys'])<=16, 'missing_dependency')
    for fingerprint,key in policy['approval_keys'].items():
        sha(fingerprint)
        require(type(key) is str and 0<len(key.encode())<=16384 and digest(key.encode())==fingerprint, 'missing_dependency')
    require(type(policy['approvers']) is list and 0<len(policy['approvers'])<=16, 'missing_dependency')
    for approver in policy['approvers']: require(type(approver) is str and 0<len(approver.encode())<=200)
    match(policy['registry'],r'[a-z0-9][a-z0-9./_-]{0,400}')
    _v1(rt._https,policy['evidence_layout'])


def _runtime_origin(value):
    require(type(value) is str)
    try: parsed=urlsplit(value)
    except ValueError: raise AdapterError('invalid_input') from None
    require(type(parsed.hostname) is str)
    match(parsed.hostname,r'(?!-)[a-z0-9-]{1,63}(?<!-)(?:\.(?!-)[a-z0-9-]{1,63}(?<!-))*')
    validate_url(value,{parsed.hostname})
    require(len(parsed.hostname)<=253 and value=='https://'+parsed.hostname)
    return value


def _upload_policy(policy):
    require(type(policy) is dict and {'toolkit_lock_sha256','runtime_service_origin'}<=set(policy), 'missing_dependency')
    sha(policy['toolkit_lock_sha256'])
    _runtime_origin(policy['runtime_service_origin'])


def build_authenticated_candidate(build_input, config, build_context, policy, *, rollback_manifest=None, dependencies=None):
    validate_context(build_context); _policy(policy, build_context)
    input_hash = validate_build_input(build_input, config, build_context, rollback_manifest=rollback_manifest)
    require(build_input['upstream_policy_sha256'] == policy['upstream_policy_sha256'])
    require(policy['registry'] == config['resources']['artifact_repository'])
    require(dependencies is not None, 'missing_dependency')
    methods = ('prepare', 'now', 'run', 'checkout', 'build', 'verify_image', 'create_image_evidence', 'sign_candidate', 'cleanup')
    require(all(callable(getattr(dependencies, name, None)) for name in methods), 'missing_dependency')
    try:
        dependencies.prepare(policy, build_context)
        validate_run(dependencies.run(build_context, completed=False), build_context, completed=False)
        dependencies.checkout(build_input['source_sha'], build_input['source_epoch'])
        owned = {}
        for role in OWNED:
            image = dependencies.build(role, build_input, build_context)
            object_fields(image, ('reference', 'image_id', 'platform'))
            immutable(image['reference']); match(image['image_id'], r'sha256:[0-9a-f]{64}')
            require(image['platform'] == 'linux/amd64' and image['reference'].startswith(policy['registry'] + '/' + role + '@sha256:'))
            dependencies.verify_image(image)
            evidence = dependencies.create_image_evidence(role, image, build_input, build_context)
            object_fields(evidence, ('provenance_uri', 'sbom_uri'))
            schema = rt.strict_json((HERE / 'release.schema.json').read_bytes())['properties']['images']['properties'][role]
            projected = {key:value for key,value in image.items() if key != 'platform'} | evidence
            _v1(rt._schema_validate, projected, schema)
            owned[role] = projected | {'platform': 'linux/amd64'}
        record = {'protocol_version':3, 'build_input_sha256':input_hash, 'context':build_context,
                  'owned_images':owned, 'created_at':dependencies.now().strftime('%Y-%m-%dT%H:%M:%SZ')}
        for key in ('dependency_images','migrations','toolchain','secret_versions','rollback_source_sha','rollback_manifest_sha256'):
            record[key] = build_input[key]
        strict_json(canonical(record))
        reference = dependencies.sign_candidate(record, build_context)
        immutable(reference)
        require(reference.startswith(policy['registry'] + '/candidate@sha256:'))
        return {'protocol_version':3, 'status':'candidate_built_unaccepted', 'candidate_digest':reference,
                'candidate':record, 'deployment_authorized':False}
    finally:
        dependencies.cleanup()


def build_argv(role, docker, source_dir, registry, context, epoch, postgres, builder):
    require(role in OWNED and docker == '/usr/bin/docker')
    validate_context(context); integer(epoch, 1, 9999999999); immutable(postgres)
    match(registry, r'[a-z0-9][a-z0-9./_-]{0,400}')
    match(builder, r'workshop-[1-9][0-9]{0,19}-[1-9][0-9]{0,3}')
    files = {'api': 'apps/api-go/Dockerfile', 'ingestion': 'workers/ingestion-python/Dockerfile', 'migration': 'infra/deploy/gce/migration.Dockerfile'}
    tag = registry + '/' + role + ':source-' + context['source_sha'] + '-run-' + context['run_id'] + '-attempt-' + str(context['run_attempt'])
    argv = [docker, 'buildx', 'build', '--builder', builder, '--platform=linux/amd64', '--push', '--provenance=mode=max',
            '--sbom=true', '--tag', tag, '--metadata-file', str(Path(source_dir).parent / (role + '-metadata.json')),
            '--build-arg', 'SOURCE_DATE_EPOCH=' + str(epoch)]
    if role == 'migration': argv += ['--build-arg', 'POSTGRES_IMAGE=' + postgres]
    return argv + ['--file', str(Path(source_dir) / files[role]), str(source_dir)]


def verify_registry_image(reference, fetch, *, deadline=None):
    """Fetch original OCI bytes; config digest is image ID, never index digest."""
    immutable(reference)
    deadline = time.monotonic() + 300 if deadline is None else deadline
    require(type(deadline) in (int, float) and 0 < deadline - time.monotonic() <= 7200, 'operation_timed_out')
    def read(kind, expected, length=None):
        match(expected, r'sha256:[0-9a-f]{64}')
        data = fetch(reference, kind, expected)
        require(type(data) is bytes and 0 < len(data) <= 4 * MiB and digest(data) == expected[7:], 'registry_mismatch')
        if length is not None: require(type(length) is int and len(data) == length, 'registry_mismatch')
        return strict_json(data, 4 * MiB)
    root_digest = 'sha256:' + reference.rsplit('@sha256:', 1)[1]
    root = read('manifests', root_digest)
    require(type(root.get('schemaVersion')) is int and root['schemaVersion'] == 2)
    manifest = root
    if root.get('mediaType') in ('application/vnd.oci.image.index.v1+json', 'application/vnd.docker.distribution.manifest.list.v2+json'):
        require(type(root.get('manifests')) is list and 1 <= len(root['manifests']) <= 16)
        runnable = []
        for descriptor in root['manifests']:
            platform = descriptor.get('platform')
            if platform == {'architecture': 'amd64', 'os': 'linux'}: runnable.append(descriptor)
            else:
                require(platform == {'architecture': 'unknown', 'os': 'unknown'})
                require(descriptor.get('annotations', {}).get('vnd.docker.reference.type') == 'attestation-manifest')
                # Hash every declared attestation manifest as well; evidence verifier
                # separately verifies its subject and DSSE signature.
                read('manifests', descriptor['digest'], descriptor['size'])
        require(len(runnable) == 1, 'registry_mismatch')
        manifest = read('manifests', runnable[0]['digest'], runnable[0]['size'])
    require(manifest.get('mediaType') in ('application/vnd.oci.image.manifest.v1+json', 'application/vnd.docker.distribution.manifest.v2+json'))
    require(type(manifest.get('layers')) is list and len(manifest['layers']) <= 256)
    descriptor = manifest['config']
    config = read('blobs', descriptor['digest'], descriptor['size'])
    require(config.get('os') == 'linux' and config.get('architecture') == 'amd64', 'registry_mismatch')
    # Descriptors alone never authenticate layers. Hash original bytes with a
    # bounded chunk size and total budget; the concrete transport owns socket
    # timeouts and closes when this generator is closed on every outcome.
    total = 0
    for layer in manifest['layers']:
        match(layer.get('digest'), r'sha256:[0-9a-f]{64}')
        integer(layer.get('size'), 1, 1024 * MiB)
        total += layer['size']
        require(total <= 4 * 1024 * MiB, 'output_overflow')
    for layer in manifest['layers']:
        require(time.monotonic() < deadline, 'operation_timed_out')
        raw = fetch(reference, 'blobs', layer['digest'])
        if type(raw) is bytes:
            require(len(raw) <= 4 * MiB and len(raw) == layer['size'] and digest(raw) == layer['digest'][7:], 'registry_mismatch')
            require(time.monotonic() < deadline, 'operation_timed_out')
            continue
        require(callable(getattr(raw, '__next__', None)) and callable(getattr(raw, 'close', None)), 'registry_mismatch')
        observed = 0; hasher = hashlib.sha256()
        try:
            for chunk in raw:
                require(time.monotonic() < deadline, 'operation_timed_out')
                require(type(chunk) is bytes and 0 < len(chunk) <= MiB, 'registry_mismatch')
                observed += len(chunk)
                require(observed <= layer['size'], 'registry_mismatch')
                hasher.update(chunk)
            require(observed == layer['size'] and hasher.hexdigest() == layer['digest'][7:], 'registry_mismatch')
            require(time.monotonic() < deadline, 'operation_timed_out')
        finally:
            try: raw.close()
            except Exception: raise AdapterError('cleanup_failed') from None
    return {'reference': reference, 'image_id': descriptor['digest'], 'platform': 'linux/amd64'}


class PinnedHTTPS:
    """TLS transport with pinned public DNS peers and zero redirect credentials.

    Resolver is an explicit bounded owner-reviewed operation taking (host,
    deadline); it must return IP strings. This class never uses system proxy or
    .netrc settings and never asks the TLS library to resolve a second hostname.
    """
    def __init__(self, ca_file, resolver, *, connect_factory=None):
        require(Path(ca_file).is_absolute() and callable(resolver), 'missing_dependency')
        self.tls = ssl.create_default_context(cafile=ca_file)
        self.resolver = resolver
        self.connect_factory = connect_factory or socket.create_connection

    def get(self, url, *, origins, deadline, maximum, token=None, signed=False):
        parsed = validate_url(url, origins, signed=signed)
        require(token is None or (parsed.hostname == 'api.github.com' and not signed), 'credential_scope')
        addresses = self.resolver(parsed.hostname, deadline)
        require(type(addresses) in (list, tuple) and 0 < len(addresses) <= 32)
        for address in addresses:
            try: require(ipaddress.ip_address(address).is_global, 'unsafe_address')
            except ValueError: raise AdapterError('unsafe_address') from None
        remaining = deadline - time.monotonic(); require(remaining > 0, 'operation_timed_out')
        raw = self.connect_factory((addresses[0], 443), timeout=remaining)
        connection = None
        try:
            require(raw.getpeername()[0] in addresses and ipaddress.ip_address(raw.getpeername()[0]).is_global, 'unsafe_address')
            raw.settimeout(max(.001, deadline - time.monotonic()))
            secured = self.tls.wrap_socket(raw, server_hostname=parsed.hostname)
            connection = http.client.HTTPSConnection(parsed.hostname, timeout=max(.001, deadline - time.monotonic()), context=self.tls)
            connection.sock = secured
            headers = {'Accept': 'application/vnd.github+json' if parsed.hostname == 'api.github.com' else 'application/octet-stream',
                       'User-Agent': 'autodata-workshop-publisher-v3', 'Accept-Encoding': 'identity'}
            if token is not None:
                require(type(token) is str and token and not any(ord(c) < 33 or ord(c) > 126 for c in token))
                headers.update(Authorization='Bearer ' + token, **{'X-GitHub-Api-Version': '2022-11-28'})
            connection.request('GET', parsed.path + ('?' + parsed.query if parsed.query else ''), headers=headers)
            response = connection.getresponse()
            require(response.status in (200, 302), 'http_failed')
            if response.status == 302:
                location = response.getheader('Location'); require(type(location) is str)
                return 302, location
            lengths = response.headers.get_all('Content-Length', [])
            require(len(lengths) <= 1 and response.getheader('Content-Encoding') in (None, 'identity'), 'http_failed')
            length = None
            if lengths:
                match(lengths[0], r'[0-9]{1,10}'); length = int(lengths[0]); require(0 < length <= maximum, 'output_overflow')
            output = bytearray()
            while True:
                require(time.monotonic() < deadline, 'operation_timed_out')
                secured.settimeout(max(.001, deadline - time.monotonic()))
                chunk = response.read1(min(65536, maximum + 1 - len(output)))
                if not chunk: break
                output.extend(chunk); require(len(output) <= maximum, 'output_overflow')
                # HTTPResponse closes an HTTP/1.0 socket after the declared
                # final byte. Do not touch that closed socket for an EOF read.
                if length is not None and len(output) == length: break
            require(length is None or len(output) == length, 'http_failed')
            return 200, bytes(output)
        except (OSError, http.client.HTTPException, ssl.SSLError): raise AdapterError('http_failed') from None
        finally:
            if connection is not None: connection.close()
            raw.close()


def download_actions_outer(http, artifact_id, token, origins, *, deadline):
    numeric(artifact_id); require(type(origins) is list and origins, 'missing_dependency')
    url = 'https://api.github.com/repos/lucronn/autodata/actions/artifacts/' + artifact_id + '/zip'
    status, value = http.get(url, origins={'api.github.com'}, deadline=deadline, maximum=16 * MiB, token=token)
    require(status == 302, 'http_failed')
    validate_url(value, set(origins), signed=True)
    status, data = http.get(value, origins=set(origins), deadline=deadline, maximum=16 * MiB, signed=True)
    require(status == 200 and type(data) is bytes, 'http_failed')
    return data

BUILD_FIELDS = ('protocol_version source_sha platform service_config_sha256 source_epoch dependency_images migrations toolchain '
                'secret_versions rollback_source_sha rollback_manifest_sha256 toolchain_policy_sha256 upstream_policy_sha256').split()
APPROVAL_FIELDS = ('protocol_version repository_id repository_owner_id environment source_sha service_config_sha256 manifest_sha256 '
                   'rollback_manifest_sha256 candidate_digest candidate_run_id candidate_run_attempt build_input_sha256 workflow_sha '
                   'trust_policy_sha256 approved_by issued_at expires_at').split()


def _v1(function, *args):
    try: return function(*args)
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError): raise AdapterError('invalid_input') from None


def _rollback(current, config, rollback_manifest):
    if current['rollback_source_sha'] is None:
        require(rollback_manifest is None and current['rollback_manifest_sha256'] is None)
        return
    source(current['rollback_source_sha']); sha(current['rollback_manifest_sha256'])
    require(type(rollback_manifest) is dict and 0 < len(canonical(rollback_manifest)) <= MiB)
    strict_json(canonical(rollback_manifest))
    require(digest(canonical(rollback_manifest)) == current['rollback_manifest_sha256'])
    schema = rt.strict_json((HERE / 'release.schema.json').read_bytes())
    _v1(rt._schema_validate, rollback_manifest, schema)
    _v1(rt._validate_immutable_images, rollback_manifest, config)
    require(rollback_manifest['source_sha'] == current['rollback_source_sha'] != current['source_sha'])
    for key in ('platform', 'service_config_sha256', 'migrations'): require(rollback_manifest[key] == current[key])


def validate_build_input(build_input, config, context, *, rollback_manifest=None):
    object_fields(build_input, BUILD_FIELDS)
    require(type(build_input['protocol_version']) is int and build_input['protocol_version'] == 3)
    validate_context(context)
    require(build_input['source_sha'] == context['source_sha'])
    require(build_input['service_config_sha256'] == context['service_config_sha256'] == _v1(rt.validate_config, config))
    require(build_input['platform'] == 'linux/amd64')
    integer(build_input['source_epoch'], 1, 9999999999)
    sha(build_input['toolchain_policy_sha256']); sha(build_input['upstream_policy_sha256'])
    require(build_input['toolchain_policy_sha256'] == context['toolchain_sha256'])
    schema = rt.strict_json((HERE / 'release.schema.json').read_bytes())['properties']
    for key in ('source_sha', 'platform', 'migrations', 'toolchain', 'secret_versions', 'rollback_source_sha'):
        _v1(rt._schema_validate, build_input[key], schema[key])
    object_fields(build_input['dependency_images'], UPSTREAM)
    for role, image in build_input['dependency_images'].items():
        _v1(rt._schema_validate, image, schema['images']['properties'][role])
        for name in ('provenance_uri', 'sbom_uri'): _v1(rt._https, image[name])
    minio = build_input['dependency_images']['minio']
    require(minio['reference'] == 'ghcr.io/chrislusf/seaweedfs@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d')
    require(minio['image_id'] == 'sha256:7b5ca1f11aa4c91593612d2d4a9e253ec9152a4bd13a19e551290a042a4c52f5')
    files = build_input['migrations']['files']
    require(len(files) <= 999 and [f['name'] for f in files] == sorted(f['name'] for f in files))
    require([int(f['name'][:3]) for f in files] == list(range(1, len(files) + 1)))
    require(build_input['migrations']['inventory_sha256'] == digest(canonical(files)))
    _rollback(build_input, config, rollback_manifest)
    return digest(canonical(build_input))


def validate_upload_statement(statement, core, identity, context):
    """Called only after cryptographic verification, never on unsigned evidence."""
    object_fields(statement, ('_type', 'subject', 'predicateType', 'predicate'))
    require(statement['_type'] == 'https://in-toto.io/Statement/v1')
    require(statement['predicateType'] == 'https://autodata.invalid/attestations/workshop-upload/v3')
    require(statement['subject'] == [{'name': 'github-actions-artifact:' + core['artifact_id'], 'digest': {'sha256': core['artifact_digest'][7:]}}])
    object_fields(statement['predicate'], ('binding_core', 'upload_evidence'))
    require(statement['predicate']['binding_core'] == core)
    evidence = statement['predicate']['upload_evidence']
    for key in ('run_id', 'run_attempt'): require(evidence.get(key) == context[key] == core[key])
    require(evidence.get('control_workflow_sha') == context['workflow_sha'] == core['workflow_sha'])
    require(evidence.get('returned_artifact_id') == core['artifact_id'] and evidence.get('returned_digest') == core['artifact_digest'])
    expected = 'https://github.com/lucronn/autodata/actions/runs/' + context['run_id'] + '/attempts/' + str(context['run_attempt'])
    require(identity.get('run_invocation_uri') == expected, 'identity_mismatch')
    require(identity.get('workflow_sha') == context['workflow_sha'] and identity.get('workflow_ref') == context['workflow_ref'], 'identity_mismatch')


def validate_approval(approval, manifest, candidate, context, policy, now):
    object_fields(approval, APPROVAL_FIELDS)
    for key in ('repository_id', 'repository_owner_id', 'environment', 'source_sha', 'service_config_sha256', 'workflow_sha', 'trust_policy_sha256'):
        require(approval[key] == context[key], 'approval_mismatch')
    require(type(approval['protocol_version']) is int and approval['protocol_version'] == 3)
    require(approval['manifest_sha256'] == digest(canonical(manifest)) == context['manifest_sha256'], 'approval_mismatch')
    require(approval['candidate_digest'] == context['candidate_digest'])
    require(approval['candidate_run_id'] == context['candidate_run_id'] == candidate['context']['run_id'])
    require(type(approval['candidate_run_attempt']) is int and approval['candidate_run_attempt'] == context['candidate_run_attempt'] == candidate['context']['run_attempt'])
    require(approval['build_input_sha256'] == candidate['build_input_sha256'])
    require(approval['rollback_manifest_sha256'] == candidate['rollback_manifest_sha256'])
    require(type(approval['approved_by']) is str and len(approval['approved_by'].encode()) <= 200 and approval['approved_by'] in policy['approvers'])
    issued, expiry = utc(approval['issued_at']), utc(approval['expires_at'])
    require(issued <= now < expiry and 0 < (expiry-issued).total_seconds() <= 86400, 'approval_expired')


def validate_candidate_record(candidate, context):
    object_fields(candidate, ('protocol_version build_input_sha256 context owned_images dependency_images migrations toolchain secret_versions '
                              'rollback_source_sha rollback_manifest_sha256 created_at').split())
    require(type(candidate['protocol_version']) is int and candidate['protocol_version']==3)
    sha(candidate['build_input_sha256']); utc(candidate['created_at'])
    validate_context(candidate['context'])
    for key in ('repository_id','repository_owner_id','source_sha','service_config_sha256','workflow_sha','workflow_ref','trust_policy_sha256','toolchain_sha256'):
        require(candidate['context'][key]==context[key], 'candidate_mismatch')
    require(candidate['context']['run_id']==context['candidate_run_id'])
    require(candidate['context']['run_attempt']==context['candidate_run_attempt'])
    object_fields(candidate['owned_images'],OWNED); object_fields(candidate['dependency_images'],UPSTREAM)
    schema=rt.strict_json((HERE/'release.schema.json').read_bytes())['properties']
    for role,image in candidate['owned_images'].items():
        object_fields(image,('reference','image_id','provenance_uri','sbom_uri','platform'))
        require(image['platform']=='linux/amd64')
        _v1(rt._schema_validate,{key:value for key,value in image.items() if key!='platform'},schema['images']['properties'][role])
    for role,image in candidate['dependency_images'].items(): _v1(rt._schema_validate,image,schema['images']['properties'][role])
    for key in ('migrations','toolchain','secret_versions','rollback_source_sha'): _v1(rt._schema_validate,candidate[key],schema[key])
    if candidate['rollback_source_sha'] is None: require(candidate['rollback_manifest_sha256'] is None)
    else: sha(candidate['rollback_manifest_sha256'])


def _manifest_candidate(manifest, candidate, context, config, rollback_manifest):
    """A complete approval is compared; observations never rewrite its fields."""
    validate_candidate_record(candidate, context)
    _v1(rt.validate_manifest, manifest, config, rollback_manifest)
    expected = {key:candidate[key] for key in ('migrations','toolchain','secret_versions','rollback_source_sha')}
    expected.update(schema_version=1, source_sha=context['source_sha'], platform='linux/amd64',
                    service_config_sha256=context['service_config_sha256'],
                    images={role:{key:value for key,value in candidate['owned_images'][role].items() if key != 'platform'} for role in OWNED} | candidate['dependency_images'])
    require(manifest == expected, 'candidate_mismatch')
    rollback_projection = {key:manifest[key] for key in ('rollback_source_sha','source_sha','platform','service_config_sha256','migrations')}
    rollback_projection['rollback_manifest_sha256'] = candidate['rollback_manifest_sha256']
    _rollback(rollback_projection, config, rollback_manifest)


def approval_envelope(value):
    require(type(value) is dict and set(value) == {'approval_bytes','signature_bytes','key_sha256'})
    require(type(value['approval_bytes']) is bytes and 0 < len(value['approval_bytes']) <= MiB)
    require(type(value['signature_bytes']) is bytes and 0 < len(value['signature_bytes']) <= 65536)
    sha(value['key_sha256'])


def finalize_authenticated_publication(manifest, config, candidate_reference, approval_record, context, policy, *, rollback_manifest=None, dependencies=None):
    validate_context(context, live=True); _policy(policy, context)
    _upload_policy(policy)
    # The approval envelope contains original independently signed bytes and a
    # detached signature, never a dictionary plus a caller assertion boolean.
    approval_envelope(approval_record)
    require(type(approval_record['approval_bytes']) is bytes and type(approval_record['signature_bytes']) is bytes)
    require(0 < len(approval_record['approval_bytes']) <= MiB and 0 < len(approval_record['signature_bytes']) <= 65536)
    require(approval_record['key_sha256'] in policy['approval_keys'], 'approval_mismatch')
    approval = strict_json(approval_record['approval_bytes'])
    object_fields(approval, APPROVAL_FIELDS)
    require(candidate_reference == context['candidate_digest'])
    _v1(rt.validate_manifest, manifest, config, rollback_manifest)
    require(dependencies is not None, 'missing_dependency')
    methods = ('prepare','now','run','load_candidate','verify_approval','verify_image','verify_image_evidence',
               'sign_source','upload','artifact_metadata','download','sign_upload','cleanup')
    require(all(callable(getattr(dependencies, name, None)) for name in methods), 'missing_dependency')
    try:
        dependencies.prepare(policy, context)
        dependencies.verify_approval(approval_record, policy)
        candidate = dependencies.load_candidate(candidate_reference, context)
        _manifest_candidate(manifest, candidate, context, config, rollback_manifest)
        require(0 <= (dependencies.now()-utc(candidate['created_at'])).total_seconds() <= 86400, 'candidate_expired')
        validate_approval(approval, manifest, candidate, context, policy, dependencies.now())
        candidate_context = candidate['context']
        validate_context(candidate_context)
        validate_run(dependencies.run(candidate_context, completed=True), candidate_context, completed=True)
        validate_run(dependencies.run(context, completed=False), context, completed=False)
        for role in OWNED:
            dependencies.verify_image(candidate['owned_images'][role])
            dependencies.verify_image_evidence(role, manifest['images'][role], candidate)
        # No build, image copy, retag or evidence regeneration operation exists in
        # this function's dependency contract.
        archive, envelope = ops.produce_release_archive(manifest, config, ops._image_observations(manifest), rollback_manifest=rollback_manifest)
        expected_source = source_statement(manifest, envelope, candidate, context)
        source_evidence = dependencies.sign_source(expected_source, context)
        object_fields(source_evidence, ('source_statement_uri','source_statement_sha256','source_statement_bundle_sha256'))
        require(source_evidence['source_statement_sha256'] == digest(canonical(expected_source)))
        upload = dependencies.upload(archive, context)
        validate_upload_observation(upload, archive, context, policy)
        metadata = dependencies.artifact_metadata(upload['artifact_id'])
        outer = dependencies.download(upload['artifact_id'])
        core = {key:context[key] for key in ('repository_id','repository_owner_id','run_id','run_attempt','workflow_sha','workflow_ref',
                                            'source_sha','service_config_sha256','manifest_sha256','candidate_digest','candidate_run_id','candidate_run_attempt')}
        core.update(protocol_version=3, artifact_id=upload['artifact_id'], artifact_name=artifact_name(context),
                    artifact_digest=upload['digest'], artifact_bytes=len(outer), archive_sha256=envelope['archive_sha256'],
                    archive_bytes=len(archive), member_sha256=envelope['member_sha256'], member_bytes=envelope['member_bytes'],
                    created_at=metadata['created_at'], expires_at=metadata['expires_at'], rollback_manifest_sha256=candidate['rollback_manifest_sha256'], **source_evidence)
        metadata_projection = validate_artifact_metadata(metadata, core, context, dependencies.now())
        require(digest(outer) == core['artifact_digest'][7:] and len(outer) == core['artifact_bytes'])
        require(decode_actions_outer_zip(outer, core['archive_sha256'], core['archive_bytes']) == archive)
        upload_evidence = {key:upload[key] for key in ('toolkit_lock_sha256','control_workflow_sha','run_id','run_attempt','upload_request_sha256','runtime_service_origin','upload_started_at','upload_finished_at')}
        upload_evidence.update(returned_artifact_id=upload['artifact_id'], returned_digest=upload['digest'], artifact_metadata_sha256=digest(canonical(metadata_projection)))
        statement = upload_statement(core, upload_evidence)
        signed = dependencies.sign_upload(statement, context)
        object_fields(signed, ('upload_statement_uri','upload_statement_sha256','upload_statement_bundle_sha256'))
        require(signed['upload_statement_sha256'] == digest(canonical(statement)))
        binding = core | signed
        require(len(canonical(binding)) <= 65536)
        return {'protocol_version':3, 'status':'uploaded_unaccepted', 'binding':binding, 'simulation':False,
                'provenance_authenticated':False, 'deployment_authorized':False}
    finally: dependencies.cleanup()


def artifact_name(context):
    return 'workshop-release-' + context['source_sha'] + '-run-' + context['run_id'] + '-attempt-' + str(context['run_attempt'])


def upload_request(archive, context):
    return {'filename':'release.zip','archive_sha256':digest(archive),'archive_bytes':len(archive),
            'artifact_name':artifact_name(context),'overwrite':False,'retention_days':7,'compression_level':0,
            'include_hidden_files':False,'run_id':context['run_id'],'run_attempt':context['run_attempt']}


def validate_upload_observation(upload, archive, context, policy):
    _upload_policy(policy)
    object_fields(upload, ('protocol_version artifact_id digest digestMismatch runtime_service_origin upload_request_sha256 '
                          'upload_started_at upload_finished_at toolkit_lock_sha256 control_workflow_sha run_id run_attempt').split())
    require(type(upload['protocol_version']) is int and upload['protocol_version'] == 3)
    numeric(upload['artifact_id']); match(upload['digest'], r'sha256:[0-9a-f]{64}')
    require(type(upload['digestMismatch']) is bool and upload['digestMismatch'] is False, 'digest_mismatch')
    for key in ('run_id','run_attempt'): require(type(upload[key]) is type(context[key]) and upload[key] == context[key])
    require(upload['control_workflow_sha'] == context['workflow_sha'])
    sha(upload['toolkit_lock_sha256'])
    _runtime_origin(upload['runtime_service_origin'])
    require(upload['toolkit_lock_sha256'] == policy['toolkit_lock_sha256'], 'missing_dependency')
    require(upload['runtime_service_origin'] == policy['runtime_service_origin'], 'credential_scope')
    require(upload['upload_request_sha256'] == digest(canonical(upload_request(archive, context))))
    require(utc(upload['upload_started_at']) <= utc(upload['upload_finished_at']))


def validate_artifact_metadata(metadata, binding, context, now):
    strict_json(canonical(metadata), 65536)
    try:
        require(type(metadata['id']) is int and str(metadata['id']) == binding['artifact_id'])
        require(metadata['name'] == artifact_name(context) == binding['artifact_name'])
        require(type(metadata['expired']) is bool and metadata['expired'] is False)
        require(metadata['digest'] == binding['artifact_digest'])
        require(type(metadata['size_in_bytes']) is int and metadata['size_in_bytes'] == binding['artifact_bytes'])
        integer(binding['artifact_bytes'], 1, 16 * MiB)
        require(metadata['workflow_run']['id'] == int(context['run_id']) and type(metadata['workflow_run']['id']) is int)
        require(metadata['workflow_run']['repository_id'] == int(context['repository_id']) and type(metadata['workflow_run']['repository_id']) is int)
        require(metadata['created_at'] == binding['created_at'] and metadata['expires_at'] == binding['expires_at'])
        created, expiry = utc(metadata['created_at']), utc(metadata['expires_at'])
        require(0 <= (now-created).total_seconds() <= 86400 and (expiry-now).total_seconds() >= 3600, 'artifact_expired')
        return {key:metadata[key] for key in ('id','name','expired','digest','size_in_bytes','created_at','expires_at','workflow_run')}
    except (KeyError, TypeError): raise AdapterError('artifact_mismatch') from None


def upload_statement(core, upload_evidence):
    return {'_type':'https://in-toto.io/Statement/v1',
            'subject':[{'name':'github-actions-artifact:'+core['artifact_id'],'digest':{'sha256':core['artifact_digest'][7:]}}],
            'predicateType':'https://autodata.invalid/attestations/workshop-upload/v3',
            'predicate':{'binding_core':core,'upload_evidence':upload_evidence}}

BINDING_FIELDS = ('protocol_version repository_id repository_owner_id run_id run_attempt workflow_sha workflow_ref source_sha '
                  'service_config_sha256 manifest_sha256 artifact_id artifact_name artifact_digest artifact_bytes archive_sha256 archive_bytes '
                  'member_sha256 member_bytes created_at expires_at candidate_digest candidate_run_id candidate_run_attempt rollback_manifest_sha256 '
                  'source_statement_uri source_statement_sha256 source_statement_bundle_sha256 upload_statement_uri upload_statement_sha256 upload_statement_bundle_sha256').split()
UPLOAD_LOCATORS = ('upload_statement_uri','upload_statement_sha256','upload_statement_bundle_sha256')


def source_statement(manifest, envelope, candidate, context):
    return {'_type':'https://in-toto.io/Statement/v1',
            'subject':[{'name':'release.json','digest':{'sha256':context['manifest_sha256']}},
                       {'name':'release.zip','digest':{'sha256':envelope['archive_sha256']}}],
            'predicateType':'https://autodata.invalid/attestations/workshop-source/v3',
            'predicate':{key:context[key] for key in ('source_sha','service_config_sha256','manifest_sha256','workflow_sha','workflow_ref',
                                                     'run_id','run_attempt','candidate_digest','candidate_run_id','candidate_run_attempt')} |
                        {'images':{role:manifest['images'][role] for role in OWNED},
                         'rollback_manifest_sha256':candidate['rollback_manifest_sha256']}}


def _binding(binding, manifest, context, rollback_manifest):
    object_fields(binding, BINDING_FIELDS)
    require(type(binding['protocol_version']) is int and binding['protocol_version'] == 3)
    for key in ('repository_id','repository_owner_id','run_id','run_attempt','workflow_sha','workflow_ref','source_sha',
                'service_config_sha256','manifest_sha256','candidate_digest','candidate_run_id','candidate_run_attempt'):
        require(type(binding[key]) is type(context[key]) and binding[key] == context[key], 'binding_mismatch')
    require(binding['manifest_sha256'] == digest(canonical(manifest)))
    require(binding['rollback_manifest_sha256'] == (None if rollback_manifest is None else digest(canonical(rollback_manifest))))
    numeric(binding['artifact_id']); require(binding['artifact_name'] == artifact_name(context))
    match(binding['artifact_digest'], r'sha256:[0-9a-f]{64}')
    integer(binding['artifact_bytes'], 1, 16 * MiB); integer(binding['archive_bytes'], 1, 8 * MiB)
    sha(binding['archive_sha256'])
    for field in ('member_bytes','member_sha256'): object_fields(binding[field], ('release.json','images.json'))
    for size in binding['member_bytes'].values(): integer(size, 1, MiB)
    for value in binding['member_sha256'].values(): sha(value)
    for prefix in ('source_statement','upload_statement'):
        _v1(rt._https, binding[prefix + '_uri']); sha(binding[prefix + '_sha256']); sha(binding[prefix + '_bundle_sha256'])


def verify_authenticated_publication(manifest, config, binding, context, policy, *, rollback_manifest=None, dependencies=None):
    validate_context(context, live=True); _policy(policy, context)
    _upload_policy(policy)
    _v1(rt.validate_manifest, manifest, config, rollback_manifest)
    _binding(binding, manifest, context, rollback_manifest)
    require(dependencies is not None, 'missing_dependency')
    methods = ('prepare','now','run','load_candidate','load_approval','verify_approval','verify_image',
               'verify_image_evidence','artifact_metadata','download','verify_signed','cleanup')
    require(all(callable(getattr(dependencies, name, None)) for name in methods), 'missing_dependency')
    try:
        dependencies.prepare(policy, context)
        candidate = dependencies.load_candidate(context['candidate_digest'], context)
        _manifest_candidate(manifest, candidate, context, config, rollback_manifest)
        approval_record = dependencies.load_approval(context['manifest_sha256'])
        approval_envelope(approval_record)
        require(approval_record['key_sha256'] in policy['approval_keys'])
        dependencies.verify_approval(approval_record, policy)
        require(0 <= (dependencies.now()-utc(candidate['created_at'])).total_seconds() <= 86400, 'candidate_expired')
        validate_approval(strict_json(approval_record['approval_bytes']), manifest, candidate, context, policy, dependencies.now())
        validate_run(dependencies.run(candidate['context'], completed=True), candidate['context'], completed=True)
        validate_run(dependencies.run(context, completed=True), context, completed=True)
        metadata = dependencies.artifact_metadata(binding['artifact_id'])
        projection = validate_artifact_metadata(metadata, binding, context, dependencies.now())
        outer = dependencies.download(binding['artifact_id'])
        require(type(outer) is bytes and len(outer) == binding['artifact_bytes'] and digest(outer) == binding['artifact_digest'][7:])
        inner = decode_actions_outer_zip(outer, binding['archive_sha256'], binding['archive_bytes'])
        verified = ops.verify_release_archive(inner, manifest, expected_archive_sha256=binding['archive_sha256'], expected_member_sha256=binding['member_sha256'])
        require(verified['member_bytes'] == binding['member_bytes'])
        for role in OWNED:
            dependencies.verify_image(candidate['owned_images'][role])
            dependencies.verify_image_evidence(role, manifest['images'][role], candidate)
        source_bytes, source_identity = dependencies.verify_signed(binding['source_statement_uri'], binding['source_statement_sha256'], binding['source_statement_bundle_sha256'], context)
        require(digest(source_bytes) == binding['source_statement_sha256'])
        require(strict_json(source_bytes) == source_statement(manifest, binding, candidate, context))
        _signed_identity(source_identity, context)
        upload_bytes, upload_identity = dependencies.verify_signed(binding['upload_statement_uri'], binding['upload_statement_sha256'], binding['upload_statement_bundle_sha256'], context)
        require(digest(upload_bytes) == binding['upload_statement_sha256'])
        statement = strict_json(upload_bytes)
        core = {key:value for key,value in binding.items() if key not in UPLOAD_LOCATORS}
        validate_upload_statement(statement, core, upload_identity, context)
        evidence = statement['predicate']['upload_evidence']
        object_fields(evidence, ('toolkit_lock_sha256 control_workflow_sha run_id run_attempt upload_request_sha256 returned_artifact_id '
                                 'returned_digest runtime_service_origin artifact_metadata_sha256 upload_started_at upload_finished_at').split())
        require(evidence['artifact_metadata_sha256'] == digest(canonical(projection)))
        observation = {key:evidence[key] for key in ('toolkit_lock_sha256','control_workflow_sha','run_id','run_attempt','upload_request_sha256',
                                                     'runtime_service_origin','upload_started_at','upload_finished_at')}
        observation.update(protocol_version=3,artifact_id=evidence['returned_artifact_id'],digest=evidence['returned_digest'],digestMismatch=False)
        validate_upload_observation(observation, inner, context, policy)
        run = dependencies.run(context, completed=True)
        require(utc(run['run_started_at']).timestamp()-60 <= utc(evidence['upload_started_at']).timestamp())
        require(utc(evidence['upload_finished_at']).timestamp() <= utc(run['updated_at']).timestamp()+60)
        return {'protocol_version':3,'status':'publication_verified','simulation':False,'provenance_authenticated':True,
                'deployment_authorized':False,'binding_sha256':digest(canonical(binding)),
                'checks':{'schema':False,'services':False,'runtime_evidence':False}}
    finally: dependencies.cleanup()


def _signed_identity(identity, context):
    expected='https://github.com/lucronn/autodata/actions/runs/'+context['run_id']+'/attempts/'+str(context['run_attempt'])
    require(identity.get('run_invocation_uri') == expected and identity.get('workflow_sha') == context['workflow_sha']
            and identity.get('workflow_ref') == context['workflow_ref'], 'identity_mismatch')


def run_fixed_iap_check(manifest, config, accepted_binding, context, policy, *, rollback_manifest=None, dependencies=None):
    validate_context(context, live=True); _policy(policy, context)
    _upload_policy(policy)
    _v1(rt.validate_manifest, manifest, config, rollback_manifest)
    _binding(accepted_binding, manifest, context, rollback_manifest)
    host = policy.get('host')
    object_fields(host, ('instance_id','ssh_fingerprint','known_hosts','server_deadline_sha256','cleanup_proof_sha256','helper_sha256','principal'))
    numeric(host['instance_id'])
    for key in ('server_deadline_sha256','cleanup_proof_sha256','helper_sha256'): sha(host[key])
    require(host['principal'] != policy.get('publisher_principal'), 'credential_scope')
    match(host['ssh_fingerprint'], r'SHA256:[A-Za-z0-9+/]{43}')
    require(dependencies is not None and callable(getattr(dependencies,'host_check',None)), 'missing_dependency')
    # A host operation re-verifies the accepted publication; a caller-provided
    # status or receipt can never grant it permission.
    verify_authenticated_publication(manifest, config, accepted_binding, context, policy, rollback_manifest=rollback_manifest, dependencies=dependencies)
    resources=config['resources']
    with private_workspace() as directory:
        known_hosts=private_write(directory,'known_hosts',host['known_hosts'].encode('utf-8'))
        argv=['/usr/bin/gcloud','compute','ssh',resources['instance_name'],'--project',resources['host_project_id'],
              '--zone',resources['zone'],'--tunnel-through-iap','--quiet','--command',
              'sudo -n /opt/autodata/bin/deploy.sh check '+manifest['source_sha'],
              '--ssh-flag=-oBatchMode=yes','--ssh-flag=-oStrictHostKeyChecking=yes',
              '--ssh-flag=-oUserKnownHostsFile='+str(known_hosts),'--ssh-flag=-oForwardAgent=no',
              '--ssh-flag=-oClearAllForwardings=yes','--ssh-flag=-oConnectTimeout=10']
        response=dependencies.host_check(argv,host,resources,directory)
    object_fields(response,('exit_code','receipt'))
    require(type(response['exit_code']) is int and response['exit_code'] in (3,5))
    receipt=response['receipt']; object_fields(receipt,ops.COMMON_RECEIPT)
    require(receipt['schema_version'] == 1 and type(receipt['schema_version']) is int)
    require(receipt['source_sha'] == manifest['source_sha'] and receipt['run_id'] is None and receipt['status'] == 'failed')
    require(receipt['operation'] == 'deploy.sh check' and utc(receipt['started_at']) <= utc(receipt['finished_at']))
    object_fields(receipt['checks'],ops._HOST_CHECKS)
    require(all(type(value) is bool for value in receipt['checks'].values()))
    require(all(receipt['checks'][key] is False for key in ('schema','services','runtime_evidence')))
    code='missing_dependency' if response['exit_code']==3 else 'operation_timed_out'
    require(receipt['failure_code'] == code)
    return {'protocol_version':3,'status':'unavailable' if response['exit_code']==3 else 'timed_out',
            'failure_code':code,'deployment_authorized':False,'checks':{'schema':False,'services':False,'runtime_evidence':False}}


def _redacted_boundary(function):
    @functools.wraps(function)
    def call(*args, **kwargs):
        try: return function(*args, **kwargs)
        except AdapterError: raise
        except Exception: raise AdapterError('operation_failed') from None
    return call


build_authenticated_candidate = _redacted_boundary(build_authenticated_candidate)
finalize_authenticated_publication = _redacted_boundary(finalize_authenticated_publication)
verify_authenticated_publication = _redacted_boundary(verify_authenticated_publication)
run_fixed_iap_check = _redacted_boundary(run_fixed_iap_check)


def verify_tool(pin):
    object_fields(pin, ('path','sha256','version'))
    require(type(pin['path']) is str and Path(pin['path']).is_absolute(), 'missing_dependency')
    sha(pin['sha256']); require(type(pin['version']) is str and 0 < len(pin['version']) <= 100)
    try:
        fd=os.open(pin['path'],os.O_RDONLY|os.O_NOFOLLOW)
        try:
            info=os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_uid in (0,os.getuid()) and not info.st_mode & 0o022, 'tool_mismatch')
            require(0 < info.st_size <= 256*MiB, 'tool_mismatch')
            hasher=hashlib.sha256()
            with os.fdopen(fd,'rb',closefd=False) as stream:
                while True:
                    chunk=stream.read(65536)
                    if not chunk: break
                    hasher.update(chunk)
            require(hasher.hexdigest()==pin['sha256'], 'tool_mismatch')
        finally: os.close(fd)
    except OSError: raise AdapterError('missing_dependency') from None


class PinnedCosignApproval:
    """Detached independent-owner verification with pinned key bytes.

    This performs no key provisioning, signing, token acquisition or network
    operation. It is separate from keyless publisher/signature verification.
    The real Cosign binary and key fingerprints still require owner review.
    """
    def __init__(self, tool_pin, approved_keys, *, process=bounded_process):
        self.pin=tool_pin; self.keys=approved_keys; self.process=process

    @_redacted_boundary
    def verify(self, envelope):
        approval_envelope(envelope)
        require(envelope['key_sha256'] in self.keys, 'approval_mismatch')
        key=self.keys[envelope['key_sha256']]
        if type(key) is str: key=key.encode('utf-8')
        require(type(key) is bytes and 0 < len(key) <= 16384 and digest(key)==envelope['key_sha256'], 'approval_mismatch')
        verify_tool(self.pin)
        with private_workspace() as directory:
            deadline=time.monotonic()+300
            code,out,_=self.process([self.pin['path'],'version','--json'],cwd=directory,deadline=deadline,maximum=65536)
            require(type(code) is int and code==0, 'tool_mismatch')
            version=strict_json(out,65536)
            require(version.get('gitVersion')==self.pin['version'], 'tool_mismatch')
            key_path=private_write(directory,'owner.pem',key)
            statement=private_write(directory,'approval.json',envelope['approval_bytes'])
            signature=private_write(directory,'approval.sig',envelope['signature_bytes'])
            code,_,_=self.process([self.pin['path'],'verify-blob','--key',str(key_path),'--signature',str(signature),
                                   '--offline',str(statement)],cwd=directory,deadline=deadline,maximum=65536)
            require(type(code) is int and code==0, 'approval_signature_invalid')
