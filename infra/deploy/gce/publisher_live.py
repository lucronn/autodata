"""Concrete bounded dependencies for the authenticated staging v3 validators.

The executable boundary accepts no URLs, paths or commands. Installed Node trust
verification is the only source of adapter policy. All mutable state is private
and ephemeral; publication output never contains tokens or owner acceptance.
"""
import base64
from datetime import datetime, timezone
import importlib.util
import inspect
import os
from pathlib import Path
import re
import resource
import stat
import time

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('publisher_live_adapters', HERE/'publisher_adapters.py')
a = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(a)
INPUT = Path('/run/autodata-publisher/input')
OUTPUT = Path('/run/autodata-publisher/output')
NODE = '/usr/local/bin/node'
NODE_SHA256 = '94efd062ed066c1a0b332e18249859c905e920eeada5df55d24c99b919629a90'
BRIDGE = HERE/'publisher_artifact.mjs'
CREDS = Path('/run/autodata-publisher/credentials')
CREDENTIAL_FIELDS = ('ACTIONS_ID_TOKEN_REQUEST_URL', 'ACTIONS_ID_TOKEN_REQUEST_TOKEN',
                     'ACTIONS_RUNTIME_TOKEN', 'ACTIONS_RESULTS_URL', 'GITHUB_TOKEN')
RUNTIME_FIELDS = ('project_id region zone maximum_monthly_budget_usd staging_origin wif_provider '
                  'publisher_service_account registry toolchain_image_digest').split()


def read_json(root, name, maximum=a.MiB):
    try: return a.strict_json(a.private_read(root, name, maximum), maximum)
    except OSError: raise a.AdapterError('invalid_input') from None


def read_tool_json(root, name, maximum=a.MiB):
    """Adopt original tool output without relaxing private input permissions.

    Buildx's atomic writer explicitly chmods metadata to0644 after creation,
    overriding its inherited umask. The containing workspace is already0700.
    Pin the original regular file through one descriptor before making it0600.
    """
    a.match(name, r'[A-Za-z0-9._-]+'); a.integer(maximum, 1, a.MiB)
    directory = None; fd = None
    try:
        directory = a._private_parent(root)
        fd = os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
        before = os.fstat(fd)
        a.require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1)
        a.require(stat.S_IMODE(before.st_mode) in (0o600,0o644) and 0 < before.st_size <= maximum)
        with os.fdopen(fd,'rb',closefd=False) as stream: data = stream.read(maximum+1)
        after = os.fstat(fd)
        stable = lambda value:(value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns)
        a.require(stable(before) == stable(after) and len(data) == before.st_size)
        os.fchmod(fd,0o600)
        adopted = os.fstat(fd)
        named = os.stat(name,dir_fd=directory,follow_symlinks=False)
        a.require(stable(before) == stable(adopted) == stable(named) and adopted.st_nlink == named.st_nlink == 1
                  and stat.S_ISREG(named.st_mode) and stat.S_IMODE(named.st_mode) == 0o600)
        return a.strict_json(data, maximum)
    except OSError: raise a.AdapterError('invalid_input') from None
    finally:
        if fd is not None: os.close(fd)
        if directory is not None: os.close(directory)


def runtime_config(runtime, config):
    """Resolve owner fields before any credential/environment read or mutation."""
    a.object_fields(runtime, RUNTIME_FIELDS)
    a._v1(a.rt.validate_config, config)
    a.require(config['environment'] == 'staging')
    a.require(config['public_origin'] not in ('https://cars.tk', 'https://www.cars.tk'))
    resources = config['resources']
    for field, expected in (('project_id', resources['host_project_id']), ('region', resources['region']),
                            ('zone', resources['zone']), ('registry', resources['artifact_repository']),
                            ('staging_origin', config['public_origin'])):
        a.require(type(runtime[field]) is str and runtime[field] == expected, 'missing_dependency')
    a.integer(runtime['maximum_monthly_budget_usd'], 1, 100000)
    a.match(runtime['wif_provider'], r'projects/[1-9][0-9]{0,19}/locations/global/workloadIdentityPools/[a-z0-9-]{1,32}/providers/[a-z0-9-]{1,32}')
    a.match(runtime['publisher_service_account'], r'[a-z][a-z0-9-]{4,28}[a-z0-9]@'+re.escape(runtime['project_id'])+r'\.iam\.gserviceaccount\.com')
    a.immutable(runtime['toolchain_image_digest'])


class ToolRunner:
    def __init__(self, pins, root, budget):
        self.pins, self.root, self.budget = pins, root, budget

    def run(self, tool, arguments, *, cwd=None, seconds=300, maximum=65536, input_bytes=None, credentials=False, cleanup=False):
        a.require(tool in self.pins, 'missing_dependency')
        pin = self.pins[tool]
        a.verify_tool(pin)
        environment = None
        if credentials:
            environment = {'DOCKER_CONFIG': str(CREDS/'docker'), 'CLOUDSDK_CONFIG': str(CREDS/'gcloud'),
                           'GOOGLE_APPLICATION_CREDENTIALS': str(CREDS/'gcp.json')}
        deadline = min(self.budget.end,time.monotonic()+seconds) if cleanup else self.budget.deadline(seconds)
        code, out, _ = a.bounded_process([pin['path'], *arguments], cwd=cwd or self.root,
                                       deadline=deadline, maximum=maximum,
                                       input_bytes=input_bytes, env=environment)
        a.require(code == 0, 'operation_failed')
        return out


def bridge(mode, value, root, budget):
    a.require(mode in ('--installed-policy', '--authenticate-context', '--upload-release'))
    a.verify_tool({'path': NODE, 'sha256': NODE_SHA256, 'version': 'v22.23.4'})
    data = a.canonical(value)
    a.require(len(data) <= 65536)
    code, out, _ = a.bounded_process([NODE, str(BRIDGE), mode], cwd=root,
                                    deadline=budget.deadline(300), maximum=2*a.MiB,
                                    input_bytes=data)
    a.require(code == 0, 'missing_dependency')
    return a.strict_json(out, 2*a.MiB)


def credentials():
    value = {name: os.environ.get(name) for name in CREDENTIAL_FIELDS}
    for item in value.values():
        a.require(type(item) is str and 0 < len(item.encode()) <= 16384 and '\0' not in item,
                  'missing_dependency')
    a.require(len(a.canonical(value)) <= 60000)
    return value


def _der(data):
    """Finite DER TLV decoder used only after Cosign verifies the original cert."""
    a.require(type(data) is bytes and 0 < len(data) <= 65536)
    result = []; offset = 0
    while offset < len(data):
        a.require(offset+2 <= len(data))
        tag, length = data[offset:offset+2]; offset += 2
        if length & 128:
            count = length & 127
            a.require(1 <= count <= 3 and offset+count <= len(data) and data[offset] != 0)
            length = int.from_bytes(data[offset:offset+count], 'big'); offset += count
            a.require(length >= 128)
        a.require(offset+length <= len(data) and len(result) < 256)
        result.append((tag, data[offset:offset+length])); offset += length
    return result


def certificate_identity(bundle, context):
    """Bind verified Fulcio certificate extensions to this exact run and control."""
    material = bundle['verificationMaterial']
    cert = material.get('certificate')
    if cert is None:
        certs = material['x509CertificateChain']['certificates']
        a.require(type(certs) is list and 1 <= len(certs) <= 8)
        cert = certs[0]
    raw = base64.b64decode(cert['rawBytes'], validate=True)
    outer = _der(raw); a.require(len(outer) == 1 and outer[0][0] == 0x30)
    certificate = _der(outer[0][1]); a.require(len(certificate) == 3 and certificate[0][0] == 0x30)
    tbs = _der(certificate[0][1])
    extensions = [value for tag, value in tbs if tag == 0xa3]
    a.require(len(extensions) == 1)
    sequence = _der(extensions[0]); a.require(len(sequence) == 1 and sequence[0][0] == 0x30)
    values = {}
    for tag, extension in _der(sequence[0][1]):
        a.require(tag == 0x30)
        fields = _der(extension)
        a.require(len(fields) in (2, 3) and fields[0][0] == 6 and fields[-1][0] == 4)
        oid = fields[0][1]; a.require(oid not in values)
        values[oid] = fields[-1][1]
    prefix = bytes.fromhex('2b0601040183bf3001')
    def extension(number):
        encoded = values.get(prefix+bytes([number]))
        a.require(encoded is not None, 'identity_mismatch')
        fields = _der(encoded)
        a.require(len(fields) == 1 and fields[0][0] in (12, 22), 'identity_mismatch')
        return fields[0][1].decode('utf-8')
    workflow = 'https://github.com/'+context['workflow_ref']
    invocation = 'https://github.com/lucronn/autodata/actions/runs/'+context['run_id']+'/attempts/'+str(context['run_attempt'])
    a.require(extension(8) == 'https://token.actions.githubusercontent.com', 'identity_mismatch')
    a.require(extension(18) == workflow and extension(19) == context['workflow_sha'], 'identity_mismatch')
    a.require(extension(21) == invocation, 'identity_mismatch')
    return {'run_invocation_uri': invocation, 'workflow_sha': context['workflow_sha'],
            'workflow_ref': context['workflow_ref']}


class LiveDependencies:
    """Real Git/Buildx/ORAS/Cosign/GitHub operations; no injectable success facade."""
    def __init__(self, root, policy, context, runtime, *, readonly=False, budget=None):
        self.root, self.policy, self.context, self.runtime = root, policy, context, runtime
        self.readonly = readonly
        self.budget = budget or a.Budget()
        self.tools = ToolRunner(policy['tools'], root, self.budget)
        self.base = {key: context[key] for key in a.CONTEXT_FIELDS}
        self.http = None
        self.token = None
        self.builder = None
        self.archive = None
        self.image_evidence = {}
        self.layer_sizes = {}

    def prepare(self, policy, context):
        a.require(policy == self.policy and context == self.context)
        a._policy(policy, context)
        a.require('deadline' in inspect.signature(a.verify_registry_image).parameters, 'missing_dependency')
        for name in ('git', 'docker', 'oras', 'cosign', 'getent', 'sigstore-root', 'sigstore-signing-config', 'buildkit-image'):
            a.require(name in policy['tools'], 'missing_dependency')
            a.verify_tool(policy['tools'][name])
        a.require(policy['tools']['docker']['path'] == '/usr/bin/docker')
        a.require(policy['tools']['cosign']['version'] == 'v3.0.2', 'tool_mismatch')
        # An independently accepted immutable BuildKit image is encoded in this
        # signed pin's version; its file pin must be the accepted Docker binary.
        buildkit = policy['tools']['buildkit-image']
        a.require(buildkit['path'] == policy['tools']['docker']['path'] and
                  buildkit['sha256'] == policy['tools']['docker']['sha256'])
        a.immutable(buildkit['version'])
        for tool, args in (('git', ['--version']), ('docker', ['--version']),
                           ('oras', ['version']), ('cosign', ['version'])):
            observed = self.tools.run(tool, args)
            a.require(policy['tools'][tool]['version'].encode() in observed, 'tool_mismatch')
        # Trust root/config are data pins, supplied read-only beside owner trust.
        for name, filename in (('sigstore-root','sigstore-trusted-root.json'),
                               ('sigstore-signing-config','sigstore-signing-config.json')):
            a.require(policy['tools'][name]['path'] == '/etc/autodata/publisher/'+filename)
        a.require(policy['evidence_layout'] == 'https://'+policy['registry']+'/evidence')
        self.http = a.PinnedHTTPS('/etc/ssl/certs/ca-certificates.crt', self.resolve)
        if not self.readonly:
            self.authenticate()
        registry_credentials(policy['registry'])
        # REST read authority is distinct from opaque runtime upload authority.
        self.token = os.environ.get('GITHUB_TOKEN')
        a.require(type(self.token) is str and 0 < len(self.token) <= 16384, 'missing_dependency')

    def authenticate(self):
        token = self.root/'identity-token'
        if token.exists():
            a.private_read(self.root, 'identity-token', 16384)
            token.unlink()
        response = bridge('--authenticate-context', {'context': self.base, 'credentials': credentials()}, self.root, self.budget)
        a.object_fields(response, ('protocol_version','context_sha256','status'))
        a.require(response == {'protocol_version':3, 'context_sha256':a.digest(a.canonical(self.base)),
                               'status':'runtime_authenticated'}, 'identity_mismatch')
        a.private_read(self.root, 'identity-token', 16384)

    def now(self): return datetime.now(timezone.utc)

    def resolve(self, host, deadline):
        a.match(host, r'[a-z0-9.-]{1,253}')
        # getent is separately hash-pinned; DNS is a bounded owned child, then
        # PinnedHTTPS validates every peer as public and pins the TLS hostname.
        remaining = max(.001, deadline-time.monotonic())
        out = self.tools.run('getent', ['ahostsv4', host], seconds=remaining, maximum=16384)
        peers = []
        for line in out.decode('ascii').splitlines():
            address = line.split()[0]
            if address not in peers: peers.append(address)
        a.require(0 < len(peers) <= 32)
        return peers

    def api(self, path):
        a.require(path.startswith('/repos/lucronn/autodata/actions/'))
        status, data = self.http.get('https://api.github.com'+path, origins={'api.github.com'},
                                     deadline=self.budget.deadline(60), maximum=a.MiB, token=self.token)
        a.require(status == 200)
        return a.strict_json(data)

    def run(self, context, *, completed):
        a.validate_context({key:context[key] for key in a.CONTEXT_FIELDS})
        run = self.api('/repos/lucronn/autodata/actions/runs/'+context['run_id']+'/attempts/'+str(context['run_attempt']))
        return a.validate_run(run, context, completed=completed)

    def checkout(self, source, epoch):
        a.source(source); a.integer(epoch, 1, 9999999999)
        a.require(source == self.context['source_sha'])
        self.source = self.root/'source'
        self.source.mkdir(mode=0o700)
        self.tools.run('git', ['init', '--quiet', str(self.source)])
        self.tools.run('git', ['remote','add','origin','https://github.com/lucronn/autodata.git'], cwd=self.source)
        self.tools.run('git', ['-c', 'protocol.allow=never', '-c', 'protocol.https.allow=always',
                               'fetch', '--no-tags', '--depth=1', 'origin', source],
                       cwd=self.source)
        self.tools.run('git', ['-c','core.hooksPath=/dev/null','checkout','--detach','--force',source], cwd=self.source)
        a.require(self.tools.run('git', ['rev-parse','HEAD'], cwd=self.source).strip().decode() == source)
        a.require(self.tools.run('git', ['show','-s','--format=%ct','HEAD'], cwd=self.source).strip() == str(epoch).encode())
        a.require(self.tools.run('git', ['status','--porcelain','--untracked-files=all'], cwd=self.source) == b'')

    def build(self, role, build_input, context):
        a.require(not self.readonly and role in a.OWNED)
        a._v1(a.rt.validate_migration_tree, build_input, self.source/'db/migrations',
              self.source/'scripts/dev/migrate_sql.sh', len(build_input['migrations']['files']))
        if self.builder is None:
            builder = 'workshop-'+context['run_id']+'-'+str(context['run_attempt'])
            self.tools.run('docker', ['buildx','create','--name',builder,'--driver','docker-container',
                                     '--driver-opt','image='+self.policy['tools']['buildkit-image']['version']], credentials=True)
            self.builder = builder
        argv = a.build_argv(role, '/usr/bin/docker', self.source, self.policy['registry'], context,
                            build_input['source_epoch'], build_input['dependency_images']['postgres']['reference'], self.builder)
        self.tools.run('docker', argv[1:], seconds=3600, maximum=4*a.MiB, credentials=True)
        metadata = read_tool_json(self.root, role+'-metadata.json')
        image_digest = metadata.get('containerimage.digest')
        a.match(image_digest, r'sha256:[0-9a-f]{64}')
        reference = self.policy['registry']+'/'+role+'@'+image_digest
        return a.verify_registry_image(reference, self.registry_fetch, deadline=self.budget.deadline(1800))

    def registry_fetch(self, reference, kind, expected):
        a.immutable(reference); a.match(expected, r'sha256:[0-9a-f]{64}')
        a.require(kind in ('manifests','blobs'))
        size = self.layer_sizes.get((reference, expected)) if kind == 'blobs' else None
        if size is not None and size > 4*a.MiB:
            a.integer(size, 1, 1024*a.MiB)
            return self._layer_stream(reference, expected, size)
        data = self._registry_bytes(reference, kind, expected, 4*a.MiB)
        if kind == 'manifests':
            value = a.strict_json(data, 4*a.MiB)
            layers = value.get('layers', [])
            a.require(type(layers) is list and len(layers) <= 256)
            for layer in layers:
                a.match(layer['digest'], r'sha256:[0-9a-f]{64}')
                a.integer(layer['size'], 1, 1024*a.MiB)
                self.layer_sizes[(reference,layer['digest'])] = layer['size']
        return data

    def _registry_file(self, reference, kind, expected, directory, maximum):
        output = directory/'object'
        repository = reference.split('@')[0]
        command = ['manifest' if kind == 'manifests' else 'blob', 'fetch',
                   '--registry-config', str(CREDS/'docker/config.json'), '--output', str(output), repository+'@'+expected]
        # The accepted ORAS process inherits a finite file-size limit. Bounding
        # its stdout alone would leave downloaded files unbounded on disk.
        previous = resource.getrlimit(resource.RLIMIT_FSIZE)
        soft = maximum if previous[0] == resource.RLIM_INFINITY else min(maximum, previous[0])
        try:
            resource.setrlimit(resource.RLIMIT_FSIZE, (soft, previous[1]))
            self.tools.run('oras', command, seconds=300, credentials=True)
        finally: resource.setrlimit(resource.RLIMIT_FSIZE, previous)
        return output

    def _registry_bytes(self, reference, kind, expected, maximum):
        with a.private_workspace() as directory:
            self._registry_file(reference, kind, expected, directory, maximum)
            data = a.private_read(directory, 'object', maximum)
            a.require('sha256:'+a.digest(data) == expected, 'registry_mismatch')
            return data

    def _layer_stream(self, reference, expected, size):
        with a.private_workspace() as directory:
            output = self._registry_file(reference, 'blobs', expected, directory, size)
            fd = os.open(output, os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            try:
                info = os.fstat(fd)
                a.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid()
                          and stat.S_IMODE(info.st_mode) == 0o600 and info.st_size == size)
                with os.fdopen(fd, 'rb', closefd=False) as stream:
                    while True:
                        chunk = stream.read(a.MiB)
                        if not chunk: break
                        yield chunk
                after = os.fstat(fd)
                a.require((info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns) ==
                          (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns))
            finally: os.close(fd)

    def verify_image(self, image):
        actual = a.verify_registry_image(image['reference'], self.registry_fetch, deadline=self.budget.deadline(1800))
        a.require(actual['image_id'] == image['image_id'] and actual['platform'] == 'linux/amd64', 'registry_mismatch')

    def _cosign(self, operation, statement, bundle, context):
        a.require(operation in ('sign','verify'))
        roots = self.policy['tools']['sigstore-root']
        a.verify_tool(roots)
        if operation == 'sign':
            a.require(not self.readonly)
            # A fresh authenticated probe also refreshes the short-lived JWT.
            self.authenticate()
            signing = self.policy['tools']['sigstore-signing-config']; a.verify_tool(signing)
            args = ['sign-blob','--yes','--identity-token',str(self.root/'identity-token'),
                    '--signing-config',signing['path'],'--trusted-root',roots['path'],
                    '--bundle',str(bundle),str(statement)]
        else:
            args = ['verify-blob','--bundle',str(bundle),'--trusted-root',roots['path'],
                    '--certificate-identity','https://github.com/'+context['workflow_ref'],
                    '--certificate-oidc-issuer','https://token.actions.githubusercontent.com',str(statement)]
        self.tools.run('cosign', args, seconds=300, maximum=a.MiB)
        parsed = a.strict_json(a.private_read(bundle.parent, bundle.name, a.MiB))
        return certificate_identity(parsed, context)

    def _put_signed(self, value, context, repository):
        data = a.canonical(value)
        a.strict_json(data)
        with a.private_workspace() as directory:
            statement = a.private_write(directory, 'statement.json', data)
            bundle = directory/'bundle.json'
            self._cosign('sign', statement, bundle, context)
            # Verify our own original output before storing immutable material.
            self._cosign('verify', statement, bundle, context)
            bundle_bytes = a.private_read(directory, 'bundle.json', a.MiB)
            a.private_write(directory,'config.json',b'{}')
            media = {'statement.json':'application/vnd.autodata.statement.v3+json',
                     'bundle.json':'application/vnd.dev.sigstore.bundle.v0.3+json',
                     'config.json':'application/vnd.oci.empty.v1+json'}
            descriptors = {}
            target = self.policy['registry']+'/'+repository
            for name, raw in (('statement.json',data),('bundle.json',bundle_bytes),('config.json',b'{}')):
                descriptor = {'mediaType':media[name],'digest':'sha256:'+a.digest(raw),'size':len(raw)}
                # Blobs and the exact manifest are uploaded by digest. No tag,
                # latest fallback or mutable reference is created or rewritten.
                self.tools.run('oras',['blob','push','--registry-config',str(CREDS/'docker/config.json'),
                                      target+'@'+descriptor['digest'],name],cwd=directory,credentials=True)
                descriptors[name] = descriptor
            manifest = {'schemaVersion':2,'mediaType':'application/vnd.oci.image.manifest.v1+json',
                        'artifactType':'application/vnd.autodata.publisher.v3','config':descriptors['config.json'],
                        'layers':[descriptors[name] | {'annotations':{'org.opencontainers.image.title':name}}
                                  for name in ('statement.json','bundle.json')]}
            encoded = a.canonical(manifest)
            a.private_write(directory,'manifest.json',encoded)
            reference = target+'@sha256:'+a.digest(encoded)
            self.tools.run('oras',['manifest','push','--registry-config',str(CREDS/'docker/config.json'),
                                  '--media-type','application/vnd.oci.image.manifest.v1+json',reference,'manifest.json'],
                           cwd=directory,credentials=True)
            return reference, a.digest(data), a.digest(bundle_bytes)

    def _get_signed(self, reference, context, expected_statement=None, expected_bundle=None):
        a.immutable(reference)
        a.require(reference.startswith(self.policy['registry']+'/candidate@sha256:') or
                  reference.startswith(self.policy['registry']+'/evidence@sha256:'))
        raw = self.registry_fetch(reference, 'manifests', 'sha256:'+reference.rsplit(':',1)[1])
        a.require(a.digest(raw) == reference.rsplit(':',1)[1])
        manifest = a.strict_json(raw)
        a.object_fields(manifest, ('schemaVersion','mediaType','artifactType','config','layers'))
        a.require(manifest.get('schemaVersion') == 2 and type(manifest.get('schemaVersion')) is int)
        a.require(manifest['mediaType'] == 'application/vnd.oci.image.manifest.v1+json')
        a.require(manifest.get('artifactType') == 'application/vnd.autodata.publisher.v3')
        a.require(manifest['config'] == {'mediaType':'application/vnd.oci.empty.v1+json',
                                        'digest':'sha256:'+a.digest(b'{}'),'size':2})
        a.require(self.registry_fetch(reference,'blobs',manifest['config']['digest']) == b'{}')
        layers = manifest.get('layers')
        a.require(type(layers) is list and len(layers) == 2)
        values = {}
        for layer in layers:
            a.object_fields(layer, ('mediaType','digest','size','annotations'))
            a.object_fields(layer['annotations'], ('org.opencontainers.image.title',))
            name = layer.get('annotations', {}).get('org.opencontainers.image.title')
            a.require(name in ('statement.json','bundle.json') and name not in values)
            a.require(layer['mediaType'] == ('application/vnd.autodata.statement.v3+json' if name == 'statement.json'
                                            else 'application/vnd.dev.sigstore.bundle.v0.3+json'))
            a.integer(layer['size'], 1, a.MiB)
            data = self.registry_fetch(reference, 'blobs', layer['digest'])
            a.require(len(data) == layer['size'] and 'sha256:'+a.digest(data) == layer['digest'])
            values[name] = data
        statement, bundle = values['statement.json'], values['bundle.json']
        a.require(expected_statement is None or a.digest(statement) == expected_statement)
        a.require(expected_bundle is None or a.digest(bundle) == expected_bundle)
        with a.private_workspace() as directory:
            statement_path = a.private_write(directory, 'statement.json', statement)
            bundle_path = a.private_write(directory, 'bundle.json', bundle)
            identity = self._cosign('verify', statement_path, bundle_path, context)
        return statement, identity

    def sign_candidate(self, record, context): return self._put_signed(record, context, 'candidate')[0]

    def load_candidate(self, reference, context):
        a.require(reference == context['candidate_digest'])
        candidate_context = {key:context[key] for key in a.CONTEXT_FIELDS}
        candidate_context.update(run_id=context['candidate_run_id'], run_attempt=context['candidate_run_attempt'])
        raw, _ = self._get_signed(reference, candidate_context)
        value = a.strict_json(raw)
        a.validate_candidate_record(value, context)
        return value

    def _statement(self, statement, context, prefix):
        reference, digest, bundle = self._put_signed(statement, context, 'evidence')
        return {prefix+'_uri':'https://'+reference, prefix+'_sha256':digest, prefix+'_bundle_sha256':bundle}

    def sign_source(self, statement, context): return self._statement(statement, context, 'source_statement')
    def sign_upload(self, statement, context): return self._statement(statement, context, 'upload_statement')

    def verify_signed(self, uri, digest, bundle_digest, context):
        a.sha(digest); a.sha(bundle_digest)
        a.require(uri.startswith(self.policy['evidence_layout']+'@sha256:'))
        return self._get_signed(uri[len('https://'):], context, digest, bundle_digest)

    def create_image_evidence(self, role, image, build_input, context):
        evidence = {}
        for kind, template in (('provenance','{{json .Provenance.SLSA}}'), ('sbom','{{json .SBOM.SPDX}}')):
            observed = a.strict_json(self.tools.run('docker', ['buildx','imagetools','inspect', image['reference'],
                                                              '--format',template], maximum=4*a.MiB,
                                                       credentials=True), 4*a.MiB)
            a.require(type(observed) is dict and observed, 'missing_dependency')
            image_predicate(kind, observed, role, context['source_sha'])
            # These are actual BuildKit attestation bytes fetched by immutable
            # image reference, then retained with independent keyless signatures.
            statement = {'_type':'https://in-toto.io/Statement/v1',
                         'subject':[{'name':image['reference'].split('@')[0],
                                     'digest':{'sha256':image['reference'].rsplit(':',1)[1]}}],
                         'predicateType': 'https://slsa.dev/provenance/v0.2' if kind == 'provenance' else 'https://spdx.dev/Document',
                         'predicate': observed,
                         'autodata': {'role':role,'context':context,'build_input_sha256':a.digest(a.canonical(build_input))}}
            reference, _, _ = self._put_signed(statement, context, 'evidence')
            evidence[kind+'_uri'] = 'https://'+reference
        return evidence

    def verify_image_evidence(self, role, image, candidate):
        context = candidate['context']
        for kind in ('provenance','sbom'):
            uri = image[kind+'_uri']
            a.require(uri.startswith(self.policy['evidence_layout']+'@sha256:'))
            raw, _ = self._get_signed(uri[len('https://'):], context)
            statement = a.strict_json(raw)
            a.require(statement.get('_type') == 'https://in-toto.io/Statement/v1')
            a.require(statement.get('subject') == [{'name':image['reference'].split('@')[0],
                          'digest':{'sha256':image['reference'].rsplit(':',1)[1]}}])
            a.require(statement.get('autodata') == {'role':role,'context':context,'build_input_sha256':candidate['build_input_sha256']})
            a.require(type(statement.get('predicate')) is dict and statement['predicate'])
            a.require(statement.get('predicateType') == ('https://slsa.dev/provenance/v0.2' if kind == 'provenance' else 'https://spdx.dev/Document'))
            image_predicate(kind, statement['predicate'], role, context['source_sha'])

    def verify_approval(self, envelope, policy):
        a.PinnedCosignApproval(policy['tools']['cosign'], policy['approval_keys']).verify(envelope)

    def load_approval(self, manifest_digest):
        a.sha(manifest_digest)
        approval = read_approval(INPUT)
        a.require(a.strict_json(approval['approval_bytes'])['manifest_sha256'] == manifest_digest)
        return approval

    def upload(self, archive, context):
        a.require(not self.readonly)
        request = {'protocol_version':3, 'operation':'upload', 'context':self.base,
                   'archive_sha256':a.digest(archive), 'archive_bytes':len(archive),
                   'artifact_name':a.artifact_name(context)}
        with a.private_workspace() as directory:
            a.private_write(directory, 'release.zip', archive)
            return bridge('--upload-release', {'request':request, 'credentials':credentials()}, directory, self.budget)

    def artifact_metadata(self, artifact_id):
        a.numeric(artifact_id)
        return self.api('/repos/lucronn/autodata/actions/artifacts/'+artifact_id)

    def download(self, artifact_id):
        outer = a.download_actions_outer(self.http, artifact_id, self.token, self.policy['storage_origins'],
                                         deadline=self.budget.deadline(300))
        self.archive = outer
        return outer

    def cleanup(self):
        try:
            if self.builder is not None:
                self.tools.run('docker', ['buildx','rm','--force',self.builder], seconds=20, credentials=True, cleanup=True)
                self.builder = None
        finally:
            self.token = None
            token = self.root/'identity-token'
            if token.exists(): token.unlink()


def read_approval(root):
    key = read_json(root, 'approval-key.json', 1024)
    a.object_fields(key, ('key_sha256',)); a.sha(key['key_sha256'])
    return {'key_sha256':key['key_sha256'], 'approval_bytes':a.private_read(root, 'approval.json', a.MiB),
            'signature_bytes':a.private_read(root, 'approval.sig', 65536)}


def registry_credentials(registry):
    """Allow only an externally supplied scoped auth entry, never helper commands."""
    data = read_json(CREDS/'docker', 'config.json', 65536)
    a.object_fields(data, ('auths',))
    a.object_fields(data['auths'], (registry.split('/')[0],))
    entry = data['auths'][registry.split('/')[0]]
    a.object_fields(entry, ('auth',))
    a.require(type(entry['auth']) is str and 0 < len(entry['auth']) <= 32768)
    decoded = base64.b64decode(entry['auth'], validate=True)
    a.require(decoded.startswith(b'oauth2accesstoken:') and len(decoded) > len(b'oauth2accesstoken:'), 'credential_scope')


def image_predicate(kind, value, role, source):
    a.require(role in a.OWNED)
    if kind == 'provenance':
        a.require(value.get('buildType') == 'https://mobyproject.org/buildkit@v1', 'identity_mismatch')
        config = value.get('invocation', {}).get('configSource', {})
        vcs = value.get('metadata', {}).get('https://mobyproject.org/buildkit@v1#metadata', {}).get('vcs', {})
        remote = 'https://github.com/lucronn/autodata.git'
        # BuildKit places remote Git contexts in configSource, and local Git
        # contexts in its documented VCS extension. Both come from the actual
        # image attestation fetched above; dirty revisions never match.
        a.require((config.get('digest', {}).get('sha1') == source and config.get('uri') == remote) or
                  (vcs.get('revision') == source and vcs.get('source') == remote), 'identity_mismatch')
        expected = {'api':'apps/api-go/Dockerfile','ingestion':'workers/ingestion-python/Dockerfile',
                    'migration':'infra/deploy/gce/migration.Dockerfile'}
        a.require(config.get('entryPoint') in (expected[role],Path(expected[role]).name), 'identity_mismatch')
    else:
        a.require(kind == 'sbom' and value.get('spdxVersion') in ('SPDX-2.2','SPDX-2.3'))
        a.require(type(value.get('packages')) is list and 0 < len(value['packages']) <= 4096)
        a.require(type(value.get('documentNamespace')) is str and value['documentNamespace'])


def execute(phase, source):
    a.source(source)
    a.require(phase in ('staging-build-candidate','staging-finalize','verify-publication'))
    context = read_json(INPUT, 'context.json')
    a.validate_context(context, live=phase != 'staging-build-candidate')
    a.require(context['source_sha'] == source)
    config = read_json(INPUT, 'config.json')
    runtime = read_json(INPUT, 'runtime.json')
    runtime_config(runtime, config)
    a.require(a._v1(a.rt.validate_config, config) == context['service_config_sha256'])
    rollback = read_json(INPUT, 'rollback.json') if (INPUT/'rollback.json').exists() else None
    if phase == 'staging-build-candidate':
        build_input = read_json(INPUT, 'build-input.json')
        a.validate_build_input(build_input, config, context, rollback_manifest=rollback)
    else:
        manifest = read_json(INPUT, 'release.json')
        a._v1(a.rt.validate_manifest, manifest, config, rollback)
        approval = read_approval(INPUT)
        a.object_fields(a.strict_json(approval['approval_bytes']), a.APPROVAL_FIELDS)
        a.require(a.digest(a.canonical(manifest)) == context['manifest_sha256'])
        if phase == 'verify-publication':
            binding = read_json(INPUT, 'binding.json', 65536)
            a._binding(binding, manifest, context, rollback)
    # Pre-existing output is never overwritten or accepted as successful work.
    a.require(not os.path.lexists(OUTPUT), 'output_collision')
    budget = a.Budget()
    with a.private_workspace() as directory:
        base = {key:context[key] for key in a.CONTEXT_FIELDS}
        installed = bridge('--installed-policy', base, directory, budget)
        a.object_fields(installed, ('protocol_version','live_policy','adapter_policy'))
        a.require(type(installed['protocol_version']) is int and installed['protocol_version'] == 3)
        policy = installed['adapter_policy']
        a._policy(policy, context)
        a.require(installed['live_policy']['toolchain_image_digest'] == runtime['toolchain_image_digest'])
        for target in ('wif_provider','publisher_service_account'):
            a.require(installed['live_policy'][target] == runtime[target], 'credential_scope')
        deps = LiveDependencies(directory, policy, context, runtime,
                                readonly=phase == 'verify-publication', budget=budget)
        if phase == 'staging-build-candidate':
            result = a.build_authenticated_candidate(build_input, config, context, policy,
                         rollback_manifest=rollback, dependencies=deps)
            outputs = {'candidate.json':a.canonical(result)}
        elif phase == 'staging-finalize':
            result = a.finalize_authenticated_publication(manifest, config, context['candidate_digest'], approval,
                         context, policy, rollback_manifest=rollback, dependencies=deps)
            outputs = {'binding.json':a.canonical(result['binding']), 'receipt.json':a.canonical(result)}
        else:
            result = a.verify_authenticated_publication(manifest, config, binding, context, policy,
                         rollback_manifest=rollback, dependencies=deps)
            a.require(deps.archive is not None)
            archive = a.decode_actions_outer_zip(deps.archive, binding['archive_sha256'], binding['archive_bytes'])
            outputs = {'binding.json':a.canonical(binding),'release.json':a.canonical(manifest),
                       'release.zip':archive,'verification.json':a.canonical(result)}
        OUTPUT.mkdir(mode=0o700)
        for name, data in outputs.items(): a.private_write(OUTPUT, name, data)
        return result
