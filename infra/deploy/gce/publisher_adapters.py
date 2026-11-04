"""Authenticated-v3 workshop adapter library; no executable activation entry point.

All authority is supplied independently. Imports perform no I/O beyond loading
fixed sibling contract code. No default credentials, token discovery or v2
simulation receipts participate in authenticated verification.
"""
import binascii
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
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
    seen = set(); offset = 0
    while offset < len(data):
        require(offset + 4 <= len(data))
        kind, size = struct.unpack_from('<HH', data, offset); offset += 4
        require(kind in (0x5455, 0x000a) and kind not in seen and offset + size <= len(data))
        seen.add(kind); value = data[offset:offset + size]; offset += size
        if kind == 0x5455:
            require(size >= 1 and value[0] in (1, 3, 5, 7) and size == 1 + 4 * value[0].bit_count())
        else:
            require(size == 32 and value[:4] == b'\0' * 4 and value[4:8] == b'\x01\x00\x18\x00')


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
        _extra(data[cd_offset + 57:cd_offset + cd_size])
        require(made >> 8 in (0, 3) and not ext & 0x18)
        if made >> 8 == 3: require(stat.S_IFMT(ext >> 16) in (0, stat.S_IFREG))
        local = struct.unpack_from('<4s5H3I2H', data, 0)
        require(local[:6] == (b'PK\x03\x04', needed, flags, method, mtime, mdate))
        require(local[9] == 11 and data[30:41] == b'release.zip')
        lcrc, lpacked, lsize, _, lxlen = local[6:]
        _extra(data[41:41 + lxlen])
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


def private_write(parent, name, data):
    require(type(data) is bytes and re.fullmatch(r'[a-zA-Z0-9._-]+', name) is not None)
    fd = os.open(parent / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream: stream.write(data)
    except BaseException:
        (parent / name).unlink(missing_ok=True); raise
    return parent / name


def private_read(parent, name, maximum):
    require(re.fullmatch(r'[a-zA-Z0-9._-]+', name) is not None)
    fd = os.open(parent / name, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        require(stat.S_ISREG(st.st_mode) and st.st_uid == os.getuid() and st.st_nlink == 1)
        require(stat.S_IMODE(st.st_mode) == 0o600 and 0 < st.st_size <= maximum)
        with os.fdopen(fd, 'rb', closefd=False) as stream: data = stream.read(maximum + 1)
        require(len(data) == st.st_size and len(data) <= maximum)
        return data
    finally: os.close(fd)


def bounded_process(argv, *, cwd, deadline, maximum=65536, input_bytes=None, env=None):
    """No shell, inherited credentials, proxies, config or agent sockets."""
    require(type(argv) is list and argv and Path(argv[0]).is_absolute())
    require(all(type(arg) is str and '\0' not in arg for arg in argv))
    safe_env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C', 'HOME': str(cwd),
                'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_TERMINAL_PROMPT': '0'}
    require(env is None or set(env) <= {'DOCKER_CONFIG', 'CLOUDSDK_CONFIG', 'GOOGLE_APPLICATION_CREDENTIALS'})
    safe_env.update(env or {})
    process = subprocess.Popen(argv, cwd=cwd, env=safe_env, stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    output = [bytearray(), bytearray()]
    try:
        if input_bytes is not None:
            # IPC is deliberately <=64KiB; nonblocking writes share the deadline.
            require(type(input_bytes) is bytes and len(input_bytes) <= 65536)
        with selectors.DefaultSelector() as selector:
            for index, stream in enumerate((process.stdout, process.stderr)):
                os.set_blocking(stream.fileno(), False); selector.register(stream, selectors.EVENT_READ, index)
            pending = memoryview(input_bytes or b'')
            if process.stdin is not None:
                os.set_blocking(process.stdin.fileno(), False)
                if pending: selector.register(process.stdin, selectors.EVENT_WRITE, 2)
                else: process.stdin.close()
            while selector.get_map():
                require(time.monotonic() < deadline, 'operation_timed_out')
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
            code = process.wait(timeout=max(.001, deadline - time.monotonic()))
        return code, bytes(output[0]), bytes(output[1])
    except BaseException:
        try: os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError: pass
        try: process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            process.wait(timeout=2)
        raise
    finally:
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None: stream.close()


def _policy(policy, context):
    # No external callback is reached until the independent owner tuple exists.
    require(type(policy) is dict and policy.get('activation_sha256') == context['activation_sha256'], 'missing_dependency')
    for name in ('repository_id', 'repository_owner_id', 'workflow_sha', 'toolchain_sha256', 'trust_policy_sha256'):
        require(policy.get(name) == context[name], 'missing_dependency')
    for name in ('tools', 'storage_origins', 'upstream_policy_sha256', 'approval_keys', 'approvers', 'registry', 'evidence_layout'):
        require(policy.get(name), 'missing_dependency')


def build_authenticated_candidate(build_input, config, build_context, policy, *, rollback_manifest=None, dependencies=None):
    validate_context(build_context); _policy(policy, build_context)
    raise AdapterError('missing_dependency')


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


def verify_registry_image(reference, fetch):
    """Fetch original OCI bytes; config digest is image ID, never index digest."""
    immutable(reference)
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
    # All layer descriptor digests/sizes are validated; the registry download path
    # streams and verifies the full bytes when the consumer selects the image.
    for layer in manifest['layers']:
        match(layer.get('digest'), r'sha256:[0-9a-f]{64}'); integer(layer.get('size'), 1, 4 * MiB)
        raw = fetch(reference, 'blobs', layer['digest'])
        require(type(raw) is bytes and len(raw) == layer['size'] and digest(raw) == layer['digest'][7:], 'registry_mismatch')
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
