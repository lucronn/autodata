#!/usr/bin/env python3
"""Private read-only transport plus network-isolated hash/schema validation.

No real access is made by default. --run requires coordinator-reviewed runtime
access. Transport stdout is a private memory-only protocol, never a log/receipt.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

BODY_MAX = 64 * 1024
DOCUMENT_MAX = 128 * 1024
INPUT_MAX = 512 * 1024
IMAGE = 'sha256:3132da4cdfa56a36240132e7c83e2bf260f679c0294c7dc06669cb607c6390f7'
CONTAINER = '343896791b0377600b9825b53c1ddb1b179d54c424d19ea935c0b9b8a681eb07'
DOCKER = ['/usr/bin/docker', '--host', 'unix:///var/run/docker.sock']
CHILD_ENV = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}

SOURCE_ROOT = '/home/corp/autodata-candidate/private-diagnostics-svg-083f1a5-20261115/source'
SOURCE_HASHES = {'workers/ingestion-python/src/autodata_ingestion/http_service.py': 'd665fe2f79e18f661dcd5bb06ae258f0fbd0e8427dd748669d820bc27d2b63b2', 'workers/ingestion-python/src/autodata_ingestion/article_lifecycle_store.py': '49a1af17c4a6815ff40ae54f47723a7b71f28e5df673dd822f5d90674078032d', 'workers/ingestion-python/src/autodata_ingestion/worker.py': '03c768e60be7a0564056a8da09a5c4619bcd6a26f1f076e0eeef38fdfe23e3db', 'workers/ingestion-python/src/autodata_ingestion/commerce_service.py': '156890573e52aa5f61db03b13229cf77740f56721379d39912c344a0e075eec7'}
EXPECTED_ENV = {'AUTODATA_DB_ADDRESS': '127.0.0.1:5432', 'AUTODATA_POSTGRES_DB': 'autodata', 'AUTODATA_POSTGRES_USER': 'autodata', 'AUTODATA_SOURCE_BUCKET': 'autodata-sources', 'AUTODATA_S3_ENDPOINT': '127.0.0.1:19000', 'AUTODATA_S3_ADDRESS': '127.0.0.1:19000'}
EXPECTED_RUNTIME = {'id': '343896791b0377600b9825b53c1ddb1b179d54c424d19ea935c0b9b8a681eb07', 'image': 'sha256:3132da4cdfa56a36240132e7c83e2bf260f679c0294c7dc06669cb607c6390f7', 'running': True, 'readonly': True, 'network': 'host', 'mounts': [{'source': '/home/corp/autodata-candidate/private-diagnostics-svg-083f1a5-20261115/source', 'destination': '/app', 'rw': False, 'type': 'bind'}], 'env': {'AUTODATA_DB_ADDRESS': '127.0.0.1:5432', 'AUTODATA_POSTGRES_DB': 'autodata', 'AUTODATA_POSTGRES_USER': 'autodata', 'AUTODATA_SOURCE_BUCKET': 'autodata-sources', 'AUTODATA_S3_ENDPOINT': '127.0.0.1:19000', 'AUTODATA_S3_ADDRESS': '127.0.0.1:19000'}}
TYPES = {'heading', 'paragraph', 'ordered_list', 'unordered_list', 'step', 'table',
         'callout', 'image', 'link', 'break', 'unknown'}
SQL = """SELECT jsonb_build_object(
 'article_id',a.canonical_article_id::text,'configuration_id',a.vehicle_configuration_id::text,
 'source_revision_id',s.source_revision_id::text,'snapshot_id',b.source_snapshot_id::text,
 'canonical_revision_id',r.canonical_article_revision_id::text,
 'current_article_id',c.canonical_article_id::text,'current_source_revision_id',c.source_revision_id::text,
 'current_canonical_revision_id',c.canonical_revision_id::text,
 'source_sha256',b.content_sha256::text,'object_key',b.object_key,
 'source_document',s.source_document,'current_document',c.document,
 'available',c.availability='available','canonical',c.content_origin='canonical',
 'published',r.status='published','readable',s.projection_status='readable',
 'unreviewed',c.review_status='UNREVIEWED','license_metadata_empty',b.license_metadata='{}'::jsonb)
 FROM canonical_articles a
 JOIN canonical_article_source_revisions s ON s.source_revision_id=a.current_source_revision_id AND s.canonical_article_id=a.canonical_article_id
 JOIN source_snapshots b ON b.source_snapshot_id=s.body_source_snapshot_id
 JOIN canonical_article_revisions r ON r.canonical_article_revision_id=a.current_canonical_revision_id AND r.canonical_article_id=a.canonical_article_id AND r.source_revision_id=s.source_revision_id
 JOIN catalog_article_current c ON c.canonical_article_id=a.canonical_article_id AND c.source_revision_id=s.source_revision_id AND c.canonical_revision_id=r.canonical_article_revision_id
 WHERE c.availability='available' AND c.content_origin='canonical' AND c.takedown_status='active'
 AND a.membership_status='active' AND b.takedown_status='active'
 AND s.projection_status='readable' AND r.status='published'
 AND octet_length(s.source_document::text)<=131072 AND octet_length(c.document::text)<=131072
 ORDER BY a.canonical_article_id LIMIT 1"""


class Refused(Exception):
    pass


def require(condition, code):
    if not condition:
        raise Refused(code)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def document_counts(document):
    require(isinstance(document, dict), 'DOCUMENT_SCHEMA')
    require(document.get('schema_version') == 1 and
            document.get('normalization_version') == 'ordered-article-v1', 'DOCUMENT_SCHEMA')
    blocks = document.get('blocks')
    require(isinstance(blocks, list) and 0 < len(blocks) <= 1024, 'DOCUMENT_SCHEMA')
    # Count the complete JSON tree with iterative depth/element bounds before
    # inspecting individual ordered blocks. This never interprets HTML/URLs.
    stack = [(document, 0)]
    nodes = 0
    while stack:
        value, depth = stack.pop()
        nodes += 1
        require(nodes <= 16000 and depth <= 24, 'DOCUMENT_LIMIT')
        if isinstance(value, dict):
            stack.extend((v, depth + 1) for v in value.values())
        elif isinstance(value, list):
            stack.extend((v, depth + 1) for v in value)
    for order, block in enumerate(blocks, 1):
        require(isinstance(block, dict) and block.get('source_order') == order and
                isinstance(block.get('block_id'), str) and bool(block['block_id']) and
                block.get('type') in TYPES, 'DOCUMENT_SCHEMA')
        kind = block['type']
        if kind in {'paragraph', 'heading', 'step', 'callout', 'link'}:
            require(isinstance(block.get('text'), str) and bool(block['text'].strip()), 'DOCUMENT_SCHEMA')
        if kind == 'table':
            require(isinstance(block.get('rows'), list), 'DOCUMENT_SCHEMA')
        if kind in {'ordered_list', 'unordered_list'}:
            require(isinstance(block.get('items'), list), 'DOCUMENT_SCHEMA')
        if kind == 'image':
            require(block.get('status') in {'available', 'unavailable'}, 'DOCUMENT_SCHEMA')
    return len(blocks), nodes


def validate(raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= INPUT_MAX, 'INPUT_LIMIT')
    value = json.loads(raw)
    keys = {'article_id', 'configuration_id', 'source_revision_id', 'snapshot_id',
            'canonical_revision_id', 'current_article_id', 'current_source_revision_id',
            'current_canonical_revision_id', 'source_sha256', 'object_key', 'source_document',
            'current_document', 'available', 'canonical', 'published', 'readable', 'unreviewed',
            'license_metadata_empty', 'body_base64'}
    require(isinstance(value, dict) and set(value) == keys, 'INPUT_SCHEMA')
    for name in keys:
        if name.endswith('_id'):
            require(isinstance(value[name], str) and str(uuid.UUID(value[name])) == value[name], 'IDENTITY')
    require(value['article_id'] == value['current_article_id'] and
            value['source_revision_id'] == value['current_source_revision_id'] and
            value['canonical_revision_id'] == value['current_canonical_revision_id'], 'IDENTITY')
    require(all(value[k] is True for k in ('available', 'canonical', 'published', 'readable')), 'PROJECTION_STATE')
    require(all(type(value[k]) is bool for k in ('unreviewed', 'license_metadata_empty')), 'INPUT_SCHEMA')
    expected = value['source_sha256']
    require(isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected), 'SOURCE_HASH')
    require(value['object_key'] == 'sources/' + expected[:16] + '/' + expected, 'OBJECT_KEY')
    body = base64.b64decode(value['body_base64'], validate=True)
    require(0 < len(body) <= BODY_MAX, 'BODY_LIMIT')
    require(digest(body) == expected, 'SOURCE_HASH')
    counts = {}
    for name in ('source_document', 'current_document'):
        require(len(encoded(value[name])) <= DOCUMENT_MAX, 'DOCUMENT_LIMIT')
        blocks, nodes = document_counts(value[name])
        counts[name] = {'blocks': blocks, 'nodes': nodes, 'sha256': digest(encoded(value[name]))}
    return {'version': 1, 'passed': True, 'source_hash_verified': True,
            'identity_verified': True, 'ordered_projection_schema_verified': True,
            'canonical_published': True, 'unreviewed': value['unreviewed'],
            'license_metadata_empty': value['license_metadata_empty'],
            'body_bytes': len(body), 'body_sha256': expected,
            'private_selection_sha256': digest(value['article_id'].encode()),
            'documents': counts, 'paid_reader_acceptance': False,
            'licensed_display': False, 'supplier_calls': 0, 'model_calls': 0}


def transport_audit(event, args):
    """Defense in depth for Python-level writes/egress, not a libpq sandbox."""
    if event == 'open':
        mode, flags = args[1], args[2]
        require(not (isinstance(mode, str) and any(c in mode for c in 'wax+')) and
                not (isinstance(flags, int) and flags &
                     (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)), 'WRITE_DENIED')
    if event in {'os.remove', 'os.rename', 'os.mkdir', 'os.rmdir', 'os.chmod',
                 'os.chown', 'os.link', 'os.symlink', 'os.truncate', 'subprocess.Popen', 'os.system'}:
        raise Refused('WRITE_OR_EXEC_DENIED')
    if event == 'socket.connect':
        address = args[1]
        require(isinstance(address, tuple) and address[:2] in
                {('127.0.0.1', 5432), ('127.0.0.1', 19000)}, 'EGRESS_DENIED')
    if event == 'socket.getaddrinfo':
        require(args[0] == '127.0.0.1', 'EGRESS_DENIED')


def transport():
    """Fixed local-only reads. Stdout MUST remain captured in private memory."""
    import resource
    import signal
    from urllib.parse import urlsplit
    signal.alarm(20)
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    require(os.environ.get('AUTODATA_DB_ADDRESS') == '127.0.0.1:5432', 'LOCAL_ENDPOINT')
    require(all(os.environ.get(k) == v for k, v in EXPECTED_ENV.items()), 'LOCAL_ENDPOINT')
    endpoint = os.environ.get('AUTODATA_S3_ENDPOINT', '')
    endpoint = urlsplit(endpoint if '://' in endpoint else 'http://' + endpoint)
    require(endpoint.scheme == 'http' and endpoint.netloc == '127.0.0.1:19000' and
            endpoint.path in ('', '/') and not endpoint.query and not endpoint.fragment, 'LOCAL_ENDPOINT')
    # No application/provider/model imports; no ambient DSN, DNS or retry.
    import psycopg
    from minio import Minio
    from urllib3 import PoolManager, Timeout, Retry
    sys.addaudithook(transport_audit)
    with psycopg.connect(host='127.0.0.1', port=5432,
            dbname=os.environ.get('AUTODATA_POSTGRES_DB', 'autodata'),
            user=os.environ.get('AUTODATA_POSTGRES_USER', 'autodata'),
            password=os.environ.get('AUTODATA_POSTGRES_PASSWORD', ''), connect_timeout=2,
            options='-c default_transaction_read_only=on -c statement_timeout=2000 -c lock_timeout=250 -c idle_in_transaction_session_timeout=5000') as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        require(conn.execute('SHOW transaction_read_only').fetchone()[0] == 'on', 'DB_NOT_READ_ONLY')
        row = conn.execute(SQL).fetchone()
        require(row is not None, 'NO_BOUNDED_CANDIDATE')
        value = row[0]
        require(len(encoded(value)) <= INPUT_MAX - 100000, 'INPUT_LIMIT')
    expected = value['source_sha256']
    require(isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected) and
            value['object_key'] == 'sources/' + expected[:16] + '/' + expected, 'OBJECT_KEY')
    client = Minio('127.0.0.1:19000', secure=False, region='us-east-1',
            access_key=os.environ['AUTODATA_S3_ACCESS_KEY'], secret_key=os.environ['AUTODATA_S3_SECRET_KEY'],
            http_client=PoolManager(timeout=Timeout(connect=2, read=3),
                retries=Retry(total=0, connect=0, read=0, redirect=0, status=0)))
    response = client.get_object(os.environ['AUTODATA_SOURCE_BUCKET'], value['object_key'])
    try:
        body = response.read(BODY_MAX + 1)
    finally:
        response.close()
        response.release_conn()
    require(0 < len(body) <= BODY_MAX, 'BODY_LIMIT')
    require(digest(body) == expected, 'SOURCE_HASH')
    value['body_base64'] = base64.b64encode(body).decode('ascii')
    raw = encoded(value)
    require(len(raw) <= INPUT_MAX, 'INPUT_LIMIT')
    sys.stdout.buffer.write(raw)


def validator_command(script, name):
    return [*DOCKER, 'run', '--pull', 'never', '--rm', '-i', '--name', name, '--log-driver', 'none',
        '--network', 'none', '--read-only', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges', '--pids-limit', '32',
        '--memory', '128m', '--memory-swap', '128m', '--cpus', '0.5',
        '--ulimit', 'cpu=5:5', '--ulimit', 'fsize=0:0', '--ulimit', 'core=0:0',
        '--env', 'PYTHONDONTWRITEBYTECODE=1',
        '--mount', 'type=bind,src=' + str(script) + ',dst=/audit.py,readonly',
        '--entrypoint', '/usr/local/bin/python3', IMAGE, '-I', '-S', '-B', '/audit.py', '--validate']


def bounded_run(argv, *, input=None, timeout, stdout_max, stderr_max=4096):
    """Drain both pipes concurrently with hard byte/deadline caps; never log."""
    import selectors
    import time
    process = subprocess.Popen(argv, stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=CHILD_ENV, close_fds=True)
    deadline = time.monotonic() + timeout
    streams = {'stdout': bytearray(), 'stderr': bytearray()}
    caps = {'stdout': stdout_max, 'stderr': stderr_max}
    pending = memoryview(input or b'')
    selector = selectors.DefaultSelector()
    try:
        for name, pipe in [('stdout', process.stdout), ('stderr', process.stderr)]:
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, name)
        if process.stdin:
            os.set_blocking(process.stdin.fileno(), False)
            if pending:
                selector.register(process.stdin, selectors.EVENT_WRITE, 'stdin')
            else:
                process.stdin.close()
        while selector.get_map():
            remaining = deadline - time.monotonic()
            require(remaining > 0, 'SUBPROCESS_TIMEOUT')
            for key, _ in selector.select(remaining):
                if key.data == 'stdin':
                    try:
                        count = os.write(key.fd, pending[:16384])
                        pending = pending[count:]
                    except BrokenPipeError:
                        pending = pending[len(pending):]
                    if not pending:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    continue
                data = os.read(key.fd, 16384)
                if not data:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                else:
                    buffer = streams[key.data]
                    require(len(buffer) + len(data) <= caps[key.data], 'SUBPROCESS_OUTPUT_LIMIT')
                    buffer.extend(data)
        remaining = deadline - time.monotonic()
        require(remaining > 0, 'SUBPROCESS_TIMEOUT')
        try:
            code = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            raise Refused('SUBPROCESS_TIMEOUT') from None
        return subprocess.CompletedProcess(argv, code, stdout=bytes(streams['stdout']), stderr=bytes(streams['stderr']))
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is not None and not pipe.closed:
                pipe.close()


def script_guard(script, expected):
    """Require reviewed physical root-owned package; return exact sealed bytes."""
    import stat
    require(isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected), 'SCRIPT_SEAL')
    require(script.is_absolute() and script == script.resolve() and not script.is_symlink(), 'SCRIPT_SEAL')
    parent = script.parent
    info = parent.stat()
    require(info.st_uid == 0 and info.st_gid == 0 and stat.S_IMODE(info.st_mode) == 0o700 and
            info.st_dev == Path('/home').stat().st_dev, 'SCRIPT_SEAL')
    descriptor = os.open(script, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_gid == 0 and
                stat.S_IMODE(info.st_mode) == 0o400 and info.st_nlink == 1 and info.st_size <= 65536, 'SCRIPT_SEAL')
        raw = os.read(descriptor, 65537)
        require(digest(raw) == expected and len(raw) == info.st_size, 'SCRIPT_SEAL')
        return raw, (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    finally:
        os.close(descriptor)


def runtime_snapshot(value):
    """Parse Docker response privately, returning only exact nonsecret contract."""
    require(isinstance(value, list) and len(value) == 1, 'RUNTIME_DRIFT')
    item = value[0]
    env = {}
    for entry in item['Config']['Env']:
        name, separator, content = entry.partition('=')
        if name in EXPECTED_ENV:
            require(separator and name not in env, 'RUNTIME_DRIFT')
            env[name] = content
    require(type(item['State']['Running']) is bool and type(item['HostConfig']['ReadonlyRootfs']) is bool and all(type(m['RW']) is bool for m in item['Mounts']), 'RUNTIME_DRIFT')
    contract = {'id': item['Id'], 'image': item['Image'], 'running': item['State']['Running'],
        'readonly': item['HostConfig']['ReadonlyRootfs'], 'network': item['HostConfig']['NetworkMode'],
        'mounts': [{'type': m['Type'], 'source': m['Source'], 'destination': m['Destination'], 'rw': m['RW']} for m in item['Mounts']],
        'env': env}
    require(contract == EXPECTED_RUNTIME, 'RUNTIME_DRIFT')
    for name, expected in SOURCE_HASHES.items():
        path = Path(SOURCE_ROOT) / name
        require(path.resolve() == path and not path.is_symlink() and path.is_file() and
                path.stat().st_size <= 2 * 1024 * 1024, 'SOURCE_DRIFT')
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            require(digest(os.read(descriptor, 2 * 1024 * 1024 + 1)) == expected, 'SOURCE_DRIFT')
        finally:
            os.close(descriptor)
    return contract


def runtime_guard():
    child = bounded_run([*DOCKER, 'inspect', CONTAINER], timeout=5, stdout_max=131072)
    require(child.returncode == 0, 'RUNTIME_DRIFT')
    return runtime_snapshot(json.loads(child.stdout))


def receipt_guard(value):
    """An untrusted/swapped child cannot add any free text to parent output."""
    bools = {'passed': True, 'source_hash_verified': True, 'identity_verified': True,
        'ordered_projection_schema_verified': True, 'canonical_published': True,
        'paid_reader_acceptance': False, 'licensed_display': False}
    keys = set(bools) | {'version', 'unreviewed', 'license_metadata_empty', 'body_bytes',
        'body_sha256', 'private_selection_sha256', 'documents', 'supplier_calls', 'model_calls'}
    require(isinstance(value, dict) and set(value) == keys, 'RECEIPT_SCHEMA')
    require(type(value['version']) is int and value['version'] == 1, 'RECEIPT_SCHEMA')
    for name, expected in bools.items():
        require(type(value[name]) is bool and value[name] is expected, 'RECEIPT_SCHEMA')
    for name in ['unreviewed', 'license_metadata_empty']:
        require(type(value[name]) is bool, 'RECEIPT_SCHEMA')
    for name in ['supplier_calls', 'model_calls']:
        require(type(value[name]) is int and value[name] == 0, 'RECEIPT_SCHEMA')
    require(type(value['body_bytes']) is int and 0 < value['body_bytes'] <= BODY_MAX, 'RECEIPT_SCHEMA')
    for name in ['body_sha256', 'private_selection_sha256']:
        require(isinstance(value[name], str) and re.fullmatch('[0-9a-f]{64}', value[name]), 'RECEIPT_SCHEMA')
    documents = value['documents']
    require(isinstance(documents, dict) and set(documents) == {'source_document', 'current_document'}, 'RECEIPT_SCHEMA')
    for document in documents.values():
        require(isinstance(document, dict) and set(document) == {'blocks', 'nodes', 'sha256'}, 'RECEIPT_SCHEMA')
        require(type(document['blocks']) is int and 0 < document['blocks'] <= 1024 and
                type(document['nodes']) is int and 0 < document['nodes'] <= 16000 and
                isinstance(document['sha256'], str) and re.fullmatch('[0-9a-f]{64}', document['sha256']), 'RECEIPT_SCHEMA')
    return value


def run(expected_hash):
    script = Path(__file__).absolute()
    source, seal = script_guard(script, expected_hash)
    before = runtime_guard()
    child = bounded_run([*DOCKER, 'exec', '-e', 'PYTHONDONTWRITEBYTECODE=1', '-i',
        CONTAINER, '/usr/local/bin/python3', '-B', '-c', source.decode('utf-8'), '--transport'],
        timeout=25, stdout_max=INPUT_MAX)
    after = runtime_guard()
    require(before == after, 'RUNTIME_DRIFT')
    require(script_guard(script, expected_hash) == (source, seal), 'SCRIPT_SEAL')
    require(child.returncode == 0 and 0 < len(child.stdout) <= INPUT_MAX, 'TRANSPORT_FAILED')
    name = 'autodata-retained-integrity-' + uuid.uuid4().hex
    try:
        result = bounded_run(validator_command(script, name), input=child.stdout,
            timeout=10, stdout_max=4096)
        require(result.returncode == 0, 'VALIDATOR_FAILED')
        require(script_guard(script, expected_hash) == (source, seal), 'SCRIPT_SEAL')
        receipt = receipt_guard(json.loads(result.stdout))
        return receipt
    finally:
        bounded_run([*DOCKER, 'rm', '-f', name], timeout=5, stdout_max=1024)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--validate', action='store_true')
    mode.add_argument('--transport', action='store_true', help=argparse.SUPPRESS)
    mode.add_argument('--run', action='store_true', help='Requires prior exact-package coordinator review')
    parser.add_argument('--expected-script-sha256', help='Required reviewed sealed-script hash for --run')
    args = parser.parse_args()
    try:
        if args.transport:
            transport()
            return 0
        receipt = validate(sys.stdin.buffer.read(INPUT_MAX + 1)) if args.validate else run(args.expected_script_sha256)
        receipt_guard(receipt)
        print(json.dumps(receipt, sort_keys=True))
        return 0
    except BaseException as error:
        # Never log exception text/traceback/raw child output or a selected ID.
        code = str(error) if isinstance(error, Refused) else 'INTEGRITY_FAILED'
        print(json.dumps({'version': 1, 'passed': False, 'code': code}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
