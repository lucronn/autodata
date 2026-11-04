"""Owner-approved, staging-only bare Compute resources. No host/runtime actions.

All network requests pass through a finite request inventory. Public methods accept
injected clocks/transport only for offline tests; the installed launcher has no
configuration, endpoint, credential or receipt-path arguments.
"""
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import fcntl
import ipaddress
import json
import math
import os
import re
import select
import signal
import stat
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler, Request

ROOT = 'https://www.googleapis.com/compute/v1'
API = 'https://compute.googleapis.com/compute/v1'
HOST_CONFIG = '/etc/autodata/host.json'
APPROVAL_CONFIG = '/etc/autodata/staging-bootstrap.json'
MAX_RESPONSE = 1048576
MAX_RECEIPT = 65536
SCOPES = ['https://www.googleapis.com/auth/' + x for x in ('cloud-platform', 'userinfo.email', 'identitytoolkit')]
DOCKER = [ipaddress.ip_network(x) for x in ('172.30.10.0/24', '172.30.20.0/24', '172.30.30.0/24')]
RFC1918 = [ipaddress.ip_network(x) for x in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
NAME = r'[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?'
PROJECT = r'[a-z][a-z0-9-]{4,28}[a-z0-9]'
HEX = r'[0-9a-f]{64}'


class Denied(ValueError):
    """Fixed error class: never carry provider/caller text into a receipt."""


class Dependency(Exception): pass
class TransportLoss(Exception): pass
class TimedOut(Exception): pass
class OperationFailed(Exception): pass


def require(value):
    if not value: raise Denied()


def match(value, pattern):
    require(type(value) is str and re.fullmatch(pattern, value) is not None)


def exact(value, keys):
    require(type(value) is dict and set(value) == set(keys))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def strict_json(data, maximum=MAX_RESPONSE):
    require(type(data) is bytes and 0 < len(data) <= maximum)
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out); out[key] = value
        return out
    def bad(_): raise Denied()
    try:
        value = json.loads(data.decode('utf-8'), object_pairs_hook=pairs, parse_constant=bad)
        def check(item):
            require(item is not None)
            if type(item) is dict:
                for child in item.values(): check(child)
            elif type(item) is list:
                for child in item: check(child)
            elif type(item) is float: require(math.isfinite(item))
        check(value)
        return value
    except (UnicodeError, ValueError, RecursionError): raise Denied() from None


def uuid4(value):
    match(value, r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}')
    require(str(uuid.UUID(value)) == value)


def validate_approval(config, approval, runtime, now):
    try: digest = runtime.validate_config(config)
    except Exception: raise Denied() from None
    require(config['environment'] == 'staging')
    require(config['public_origin'].split('/')[2].split(':')[0].lower().rstrip('.') not in ('cars.tk', 'www.cars.tk'))
    resources = config['resources']
    for key in ('host_project_id',): match(resources[key], PROJECT)
    for key in ('region', 'zone', 'instance_name', 'data_disk_name', 'static_ip_name'): match(resources[key], NAME)
    require(resources['zone'].startswith(resources['region'] + '-') and len(resources['instance_name']) <= 58)
    require(resources['data_disk_name'] != resources['instance_name'] + '-boot')
    exact(approval, ('schema_version', 'operation', 'authorization_id', 'expires_at', 'service_config_sha256',
                     'resource_nonce', 'boot_image', 'network', 'attached_identity',
                     'bootstrap_identity_evidence_sha256', 'owner_cost_and_region_evidence_sha256'))
    require(type(approval['schema_version']) is int and approval['schema_version'] == 1)
    require(approval['operation'] == 'create-staging-resources')
    for key in ('authorization_id', 'resource_nonce'): uuid4(approval[key])
    for key in ('service_config_sha256', 'bootstrap_identity_evidence_sha256', 'owner_cost_and_region_evidence_sha256'): match(approval[key], HEX)
    require(approval['service_config_sha256'] == digest)
    match(approval['expires_at'], r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z')
    try: expires = datetime.strptime(approval['expires_at'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except ValueError: raise Denied() from None
    require(0 < (expires - now).total_seconds() <= 86400)
    image = approval['boot_image']; exact(image, ('self_link', 'id', 'architecture'))
    match(image['self_link'], re.escape(ROOT) + '/projects/' + PROJECT + '/global/images/' + NAME)
    match(image['id'], r'[1-9][0-9]{0,19}'); require(image['architecture'] == 'X86_64')
    network = approval['network']; exact(network, ('network_self_link', 'subnetwork_self_link', 'reviewed_firewall_evidence_sha256', 'reviewed_routes_evidence_sha256'))
    prefix = ROOT + '/projects/' + resources['host_project_id']
    match(network['network_self_link'], re.escape(prefix + '/global/networks/') + NAME)
    match(network['subnetwork_self_link'], re.escape(prefix + '/regions/' + resources['region'] + '/subnetworks/') + NAME)
    for key in ('reviewed_firewall_evidence_sha256', 'reviewed_routes_evidence_sha256'): match(network[key], HEX)
    attached = approval['attached_identity']; exact(attached, ('email', 'reviewed_iam_evidence_sha256'))
    require(attached['email'] == 'autodata-api-firebase@' + resources['host_project_id'] + '.iam.gserviceaccount.com')
    match(attached['reviewed_iam_evidence_sha256'], HEX)
    return digest


def subnet_range(value):
    try: network = ipaddress.ip_network(value, strict=True)
    except (ValueError, TypeError): raise Denied() from None
    require(network.version == 4 and any(network.subnet_of(parent) for parent in RFC1918))
    require(all(not network.overlaps(other) for other in DOCKER))
    return network


def validate_routes(routes, network, cidr, project):
    subnet_range(cidr)
    require(type(routes) is list and len(routes) <= 1000)
    found = []
    for route in routes:
        require(type(route) is dict)
        require(type(route.get('network')) is str)
        if route['network'] != network: continue
        destination = route.get('destRange')
        hops = {key: value for key, value in route.items() if key.startswith('nextHop')}
        require(not route.get('tags') and not route.get('routeType') in ('DYNAMIC', 'PEERING_DYNAMIC', 'PEERING_STATIC'))
        if destination == '0.0.0.0/0':
            require(hops == {'nextHopGateway': project + '/global/gateways/default-internet-gateway'})
            found.append('default')
        else:
            subnet_range(destination)
            require(destination == cidr and hops == {'nextHopNetwork': network})
            found.append('subnet')
    require(sorted(found) == ['default', 'subnet'])


def normalized_firewalls(rules, network, tag):
    require(type(rules) is list and len(rules) == 2)
    found = []
    recognized = {'kind', 'id', 'creationTimestamp', 'name', 'description', 'selfLink', 'network', 'priority',
                  'direction', 'disabled', 'targetTags', 'sourceRanges', 'allowed', 'logConfig'}
    for rule in rules:
        require(type(rule) is dict and set(rule) <= recognized)
        require(rule.get('network') == network and rule.get('direction', 'INGRESS') == 'INGRESS')
        require(rule.get('disabled', False) is False and rule.get('targetTags') == [tag])
        priority = rule.get('priority', 1000); require(type(priority) is int and 0 <= priority <= 65535)
        allowed = rule.get('allowed'); require(type(allowed) is list and len(allowed) == 1)
        exact(allowed[0], ('IPProtocol', 'ports')); require(allowed[0]['IPProtocol'] == 'tcp')
        ports = allowed[0]['ports']; sources = rule.get('sourceRanges')
        require(type(ports) is list and all(type(x) is str for x in ports) and type(sources) is list)
        normalized = (tuple(sources), tuple(sorted(ports)), priority)
        require(normalized[:2] in ((('0.0.0.0/0',), ('443', '80')), (('35.235.240.0/20',), ('22',))))
        found.append(normalized)
    require(len({item[:2] for item in found}) == 2)
    return sorted(found)


def validate_token(data):
    require(type(data) is bytes and 0 < len(data) <= 16384)
    # OAuth bearer grammar, one frame terminated by EOF, never a line protocol.
    require(re.fullmatch(rb'[A-Za-z0-9._~+/-]+=*', data) is not None)
    return data.decode('ascii')


def read_token():
    try:
        metadata = os.fstat(3)
        require(stat.S_ISFIFO(metadata.st_mode) and fcntl.fcntl(3, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY)
        deadline = time.monotonic() + 30
        data = bytearray()
        while len(data) <= 16384:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([3], [], [], remaining)[0]: raise TimedOut()
            chunk = os.read(3, 16385 - len(data))
            if not chunk: return validate_token(bytes(data))
            data.extend(chunk)
        raise Denied()
    except OSError: raise Dependency() from None
    finally:
        try: os.close(3)
        except OSError: pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): raise Denied()


@contextmanager
def request_deadline(seconds):
    # urllib socket timeouts alone allow a slow response to extend indefinitely.
    # This fixed single-threaded operator process also bounds total wall time.
    require(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0))
    previous = signal.getsignal(signal.SIGALRM)
    def expired(signum, frame): raise TimedOut()
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try: yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


class ComputeTransport:
    def __init__(self, token, opener=None):
        self._token = validate_token(token.encode('ascii'))
        self._opener = opener or build_opener(ProxyHandler({}), NoRedirect()).open

    def __call__(self, method, url, body, timeout):
        require(method in ('GET', 'POST') and url.startswith(API + '/projects/'))
        require('#' not in url and '@' not in url and '..' not in url and 0 < timeout <= 30)
        headers = {'Authorization': 'Bearer ' + self._token, 'Accept': 'application/json'}
        data = None if body is None else canonical(body)
        if data is not None: headers['Content-Type'] = 'application/json'
        request = Request(url, data=data, headers=headers, method=method)
        with request_deadline(timeout):
            try:
                try: response = self._opener(request, timeout=timeout)
                except HTTPError as error:
                    if error.code == 404:
                        error.close(); return 404, {}
                    error.close(); raise OperationFailed() from None
                with response:
                    require(response.status == 200)
                    raw = response.read(MAX_RESPONSE + 1)
                    return 200, strict_json(raw)
            except (TimeoutError, URLError, ConnectionError, OSError): raise TransportLoss() from None


def read_inputs(runtime):
    try:
        with ExitStack() as stack:
            parent = None
            for component in ('/', 'etc', 'autodata'):
                fd = runtime._owned_directory(component, parent=parent)
                stack.callback(os.close, fd); parent = fd
            # Reuse the descriptor-based bounded no-follow helper, pinned to parent.
            config = runtime.strict_json(runtime._owned_bytes(parent, 'host.json', 0, 0, 0o600, MAX_RECEIPT))
            approval = strict_json(runtime._owned_bytes(parent, 'staging-bootstrap.json', 0, 0, 0o600, MAX_RECEIPT), MAX_RECEIPT)
            return config, approval
    except (OSError, runtime.ContractError): raise Dependency() from None


def receipt_base(now):
    stamp = now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    return {'schema_version': 1, 'operation': 'cloud-bootstrap.sh apply', 'run_id': None, 'source_sha': None,
            'status': 'failed', 'started_at': stamp, 'finished_at': stamp, 'failure_code': 'operation_failed',
            'checks': {'config': False, 'prerequisites': False, 'address': False, 'disk': False, 'instance': False,
                       'schema': False, 'services': False, 'runtime_evidence': False},
            'definition_only': False, 'deployment_authorized': False, 'cleanup': 'resources-retained',
            'resources': {}, 'operations': [], 'request_ids': {}}


class ReceiptStore:
    """Fixed operator-local receipt directory; descriptor-relative atomic writes."""
    def __init__(self, runtime): self.runtime = runtime

    def __enter__(self):
        self.stack = ExitStack()
        try:
            parent = None
            for component in ('/', 'var', 'lib', 'autodata-bootstrap', 'receipts'):
                if component in ('autodata-bootstrap', 'receipts'):
                    try: os.mkdir(component, mode=0o700, dir_fd=parent); os.fsync(parent)
                    except FileExistsError: pass
                fd = self.runtime._owned_directory(component, parent=parent, mode=0o700 if component in ('autodata-bootstrap', 'receipts') else None)
                self.stack.callback(os.close, fd); parent = fd
            self.fd = parent
            # One operator process at a time, including different authorizations.
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return self
        except Exception:
            self.stack.close(); raise Dependency() from None

    def __exit__(self, *args): self.stack.close()

    def read(self, authorization):
        uuid4(authorization)
        try:
            raw = self.runtime._owned_bytes(self.fd, authorization + '.json', 0, 0, 0o600, MAX_RECEIPT)
        except FileNotFoundError: return None
        # Receipt has intentional null common fields; runtime strict parser allows those.
        return self.runtime.strict_json(raw)

    def write(self, value):
        authorization = value['authorization_id']; uuid4(authorization)
        raw = canonical(value); require(len(raw) <= MAX_RECEIPT)
        target = authorization + '.json'
        temporary = '.' + authorization + '.' + str(uuid.uuid4())
        fd = None
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.fd)
            with os.fdopen(fd, 'wb') as output:
                fd = None; output.write(raw); output.flush(); os.fsync(output.fileno())
            # Never replace an unverified file, symlink, directory or other owner.
            try:
                info = os.stat(target, dir_fd=self.fd, follow_symlinks=False)
                require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_gid == 0 and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1)
            except FileNotFoundError: pass
            os.replace(temporary, target, src_dir_fd=self.fd, dst_dir_fd=self.fd); os.fsync(self.fd)
        finally:
            if fd is not None: os.close(fd)
            try: os.unlink(temporary, dir_fd=self.fd)
            except FileNotFoundError: pass


class Bootstrap:
    def __init__(self, config, approval, runtime, transport, now=None, monotonic=time.monotonic, sleep=time.sleep, prior=None, persist=None):
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.monotonic, self.sleep = monotonic, sleep
        self.deadline = monotonic() + 1800
        self.config, self.approval, self.runtime, self.transport = config, approval, runtime, transport
        self.digest = validate_approval(config, approval, runtime, self.now())
        r = config['resources']; self.p = ROOT + '/projects/' + r['host_project_id']
        self.z, self.r = self.p + '/zones/' + r['zone'], self.p + '/regions/' + r['region']
        self.network = approval['network']['network_self_link']; self.subnet = approval['network']['subnetwork_self_link']
        self.image = approval['boot_image']['self_link']; self.vm = self.z + '/instances/' + r['instance_name']
        self.paths = {'address': self.r + '/addresses/' + r['static_ip_name'], 'disk': self.z + '/disks/' + r['data_disk_name'],
                      'instance': self.vm, 'boot_disk': self.z + '/disks/' + r['instance_name'] + '-boot'}
        self.labels = {'autodata-stage': approval['resource_nonce'], 'autodata-config': self.digest[:32]}
        self.resources = {}; self.prior = prior or {}; self.persist = persist or (lambda value: None)
        self.receipt = receipt_base(self.now())
        self.receipt.update(authorization_id=approval['authorization_id'], service_config_sha256=self.digest, resource_nonce=approval['resource_nonce'])
        self.receipt['request_ids'] = {kind: str(uuid.uuid5(uuid.UUID(approval['resource_nonce']), approval['authorization_id'] + ':' + kind)) for kind in ('address', 'disk', 'instance')}
        self.receipt['checks']['config'] = True
        self.gets = {self.p, self.image, self.z + '/machineTypes/e2-standard-4', self.network, self.subnet,
                     self.p + '/global/routes', self.p + '/global/firewalls', self.network + '/getEffectiveFirewalls',
                     self.r + '/firewallPolicies/getEffectiveFirewalls?network=' + quote(self.network, safe=''),
                     self.vm + '/getEffectiveFirewalls?networkInterface=nic0', *self.paths.values()}
        self.operations = set()

    def remaining(self):
        remaining = self.deadline - self.monotonic()
        if remaining <= 0: raise TimedOut()
        return min(30, remaining)

    def request(self, method, path, body=None):
        base = path.split('?', 1)[0]
        if method == 'GET':
            require(path in self.gets or path in self.operations or
                    (base in (self.p + '/global/routes', self.p + '/global/firewalls') and re.fullmatch(r'.*\?pageToken=[A-Za-z0-9%._~-]+&maxResults=100', path)))
        else:
            require(method == 'POST' and any(path == self.paths[k].rsplit('/', 1)[0] + '?requestId=' + self.receipt['request_ids'][k] for k in ('address', 'disk', 'instance')))
            validate_approval(self.config, self.approval, self.runtime, self.now())
        timeout = self.remaining()
        # SelfLinks are always canonical www.googleapis.com; the sole wire origin is Compute.
        wire = API + path[len(ROOT):]
        status, value = self.transport(method, wire, body, timeout)
        require(type(status) is int and status in (200, 404) and type(value) is dict and len(canonical(value)) <= MAX_RESPONSE)
        if method == 'POST': require(status == 200)
        return status, value

    def get(self, path, missing=False):
        status, value = self.request('GET', path)
        if status == 404:
            if missing: return None
            raise OperationFailed()
        return value

    def listing(self, path):
        items, tokens = [], set()
        for page in range(10):
            value = self.get(path if page == 0 else path + '?pageToken=' + quote(token, safe='') + '&maxResults=100')
            batch = value.get('items', []); require(type(batch) is list)
            items.extend(batch); require(len(items) <= 1000)
            token = value.get('nextPageToken')
            if token is None: return items
            match(token, r'[A-Za-z0-9._~+/=-]{1,2048}'); require(token not in tokens); tokens.add(token)
        raise Denied()

    def prerequisites(self):
        project = self.get(self.p)
        metadata = project.get('commonInstanceMetadata', {})
        require(type(metadata) is dict)
        require(metadata.get('items', []) in ([], [{'key': 'enable-oslogin', 'value': 'TRUE'}]))
        image = self.get(self.image)
        require(image.get('selfLink') == self.image and image.get('id') == self.approval['boot_image']['id'] and image.get('architecture') == 'X86_64' and image.get('status') == 'READY')
        require(not any(image.get(key) for key in ('deprecated',)))
        machine = self.get(self.z + '/machineTypes/e2-standard-4')
        require(machine.get('selfLink') == self.z + '/machineTypes/e2-standard-4' and machine.get('name') == 'e2-standard-4' and machine.get('guestCpus') == 4 and machine.get('memoryMb') == 16384)
        network = self.get(self.network)
        require(network.get('selfLink') == self.network and network.get('autoCreateSubnetworks') is False and network.get('subnetworks') == [self.subnet])
        require(not any(network.get(k) for k in ('peerings', 'firewallPolicy', 'enableUlaInternalIpv6', 'internalIpv6Range')))
        subnet = self.get(self.subnet)
        require(subnet.get('selfLink') == self.subnet and subnet.get('network') == self.network and subnet.get('region') == self.r and subnet.get('stackType', 'IPV4_ONLY') == 'IPV4_ONLY')
        require(not any(subnet.get(k) for k in ('secondaryIpRanges', 'allowSubnetCidrRoutesOverlap', 'ipv6AccessType', 'externalIpv6Prefix', 'internalIpv6Prefix')))
        subnet_range(subnet.get('ipCidrRange'))
        validate_routes(self.listing(self.p + '/global/routes'), self.network, subnet['ipCidrRange'], self.p)
        rules = self.listing(self.p + '/global/firewalls')
        # Cap the whole list before filtering by exact network.
        require(all(type(rule) is dict and type(rule.get('network')) is str for rule in rules))
        rules = [rule for rule in rules if rule['network'] == self.network]
        normalized = normalized_firewalls(rules, self.network, self.config['resources']['instance_name'])
        effective = self.get(self.network + '/getEffectiveFirewalls')
        require(effective.get('firewallPolicys') == [])
        require(normalized_firewalls(effective.get('firewalls'), self.network, self.config['resources']['instance_name']) == normalized)
        regional = self.get(self.r + '/firewallPolicies/getEffectiveFirewalls?network=' + quote(self.network, safe=''))
        require(regional.get('firewallPolicys') == [])
        fingerprint = canonical({'network': network, 'subnet': subnet, 'routes': self.listing(self.p + '/global/routes'), 'rules': normalized})
        if hasattr(self, 'prerequisite_fingerprint'): require(fingerprint == self.prerequisite_fingerprint)
        self.prerequisite_fingerprint = fingerprint; self.rules = normalized
        self.receipt['checks']['prerequisites'] = True

    def identity(self, kind, value, created=False):
        require(value.get('selfLink') == self.paths[kind] and value.get('labels') == self.labels)
        match(value.get('id'), r'[1-9][0-9]{0,19}')
        expected = self.resources.get(kind)
        if expected: require(expected['id'] == value['id'])
        elif not created:
            require(self.prior.get('authorization_id') == self.approval['authorization_id'] and self.prior.get('service_config_sha256') == self.digest and self.prior.get('resource_nonce') == self.approval['resource_nonce'])
            old = self.prior.get('resources', {}).get(kind, {})
            require(old == {'id': value['id'], 'self_link': self.paths[kind]})
        self.resources[kind] = {'id': value['id'], 'self_link': self.paths[kind]}
        self.receipt['resources'] = dict(self.resources)

    def disk(self, value, boot=False, attached=False, created=False):
        kind = 'boot_disk' if boot else 'disk'; self.identity(kind, value, created)
        require(value.get('name') == self.paths[kind].rsplit('/', 1)[1] and value.get('status') == 'READY')
        require(str(value.get('sizeGb')) == ('20' if boot else '200') and value.get('type') == self.z + '/diskTypes/pd-balanced')
        require(value.get('users', []) == ([self.vm] if attached else []))
        require(not any(value.get(k) for k in ('sourceSnapshot', 'sourceSnapshotId', 'sourceDisk', 'sourceDiskId', 'diskEncryptionKey', 'sourceStorageObject', 'resourcePolicies', 'enableConfidentialCompute')))
        if boot: require(value.get('sourceImage') == self.image and value.get('sourceImageId') == self.approval['boot_image']['id'])
        else: require(not any(value.get(k) for k in ('sourceImage', 'sourceImageId', 'sourceInstantSnapshot', 'sourceInstantSnapshotId')))

    def address(self, value, attached=False, created=False):
        self.identity('address', value, created)
        require(value.get('name') == self.config['resources']['static_ip_name'] and value.get('addressType') == 'EXTERNAL' and value.get('ipVersion') == 'IPV4' and value.get('networkTier') == 'PREMIUM' and value.get('region') == self.r)
        require(value.get('status') == ('IN_USE' if attached else 'RESERVED') and value.get('users', []) == ([self.vm] if attached else []))
        try: require(ipaddress.ip_address(value['address']).version == 4)
        except (KeyError, ValueError): raise Denied() from None
        require(not any(value.get(k) for k in ('subnetwork', 'purpose', 'prefixLength', 'ipv6EndpointType', 'addressLength')))
        if hasattr(self, 'ip'): require(value['address'] == self.ip)
        self.ip = value['address']

    def instance_body(self):
        return {'name': self.config['resources']['instance_name'], 'labels': self.labels,
                'machineType': self.z + '/machineTypes/e2-standard-4',
                'disks': [{'boot': True, 'type': 'PERSISTENT', 'autoDelete': False, 'initializeParams': {
                    'diskName': self.config['resources']['instance_name'] + '-boot', 'sourceImage': self.image,
                    'diskSizeGb': '20', 'diskType': self.z + '/diskTypes/pd-balanced', 'labels': self.labels}},
                    {'boot': False, 'type': 'PERSISTENT', 'source': self.paths['disk'], 'mode': 'READ_WRITE', 'autoDelete': False, 'deviceName': 'autodata-data'}],
                'networkInterfaces': [{'network': self.network, 'subnetwork': self.subnet,
                    'accessConfigs': [{'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT', 'natIP': self.ip, 'networkTier': 'PREMIUM'}]}],
                'serviceAccounts': [{'email': self.approval['attached_identity']['email'], 'scopes': SCOPES}],
                'metadata': {'items': [{'key': 'enable-oslogin', 'value': 'TRUE'}, {'key': 'block-project-ssh-keys', 'value': 'TRUE'}, {'key': 'serial-port-enable', 'value': 'FALSE'}]},
                'canIpForward': False, 'tags': {'items': [self.config['resources']['instance_name']]}, 'deletionProtection': True}

    def instance(self, value, created=False):
        self.identity('instance', value, created)
        body = self.instance_body()
        for key in ('name', 'machineType', 'canIpForward', 'deletionProtection'): require(value.get(key) == body[key] and type(value.get(key)) is type(body[key]))
        require(value.get('status') in ('RUNNING', 'STOPPED', 'TERMINATED'))
        require(value.get('metadata', {}).get('items') == body['metadata']['items'] and value.get('tags', {}).get('items') == body['tags']['items'])
        accounts = value.get('serviceAccounts'); require(type(accounts) is list and len(accounts) == 1)
        exact(accounts[0], ('email', 'scopes')); require(accounts[0]['email'] == body['serviceAccounts'][0]['email'] and sorted(accounts[0]['scopes']) == sorted(SCOPES))
        nics = value.get('networkInterfaces'); require(type(nics) is list and len(nics) == 1)
        nic = nics[0]; require(nic.get('network') == self.network and nic.get('subnetwork') == self.subnet and nic.get('stackType', 'IPV4_ONLY') == 'IPV4_ONLY')
        require(not any(nic.get(k) for k in ('ipv6Address', 'externalIpv6', 'ipv6AccessConfigs', 'aliasIpRanges')))
        access = nic.get('accessConfigs'); require(type(access) is list and len(access) == 1)
        for key, expected in body['networkInterfaces'][0]['accessConfigs'][0].items(): require(access[0].get(key) == expected)
        require(not access[0].get('externalIpv6'))
        disks = value.get('disks'); require(type(disks) is list and len(disks) == 2)
        for observed, expected, path in zip(disks, body['disks'], (self.paths['boot_disk'], self.paths['disk'])):
            require(observed.get('source') == path and observed.get('mode') == 'READ_WRITE' and observed.get('type') == 'PERSISTENT')
            require(observed.get('boot') is expected['boot'] and observed.get('autoDelete') is False and not observed.get('initializeParams'))
            require(observed.get('deviceName') == (path.rsplit('/', 1)[1] if expected['boot'] else 'autodata-data'))
        require(not any(value.get(k) for k in ('sourceInstanceTemplate', 'resourcePolicies', 'reservationAffinity', 'confidentialInstanceConfig')))

    def poll(self, operation, kind):
        path = operation.get('selfLink'); scope = self.r if kind == 'address' else self.z
        match(path, re.escape(scope + '/operations/') + NAME)
        name = path.rsplit('/', 1)[1]; require(operation.get('name') == name)
        self.operations.add(path)
        self.receipt['operations'].append(path)
        self.save()
        delay = 1
        while True:
            self.remaining()
            if operation.get('error') or operation.get('httpErrorStatusCode') or operation.get('status') in ('CANCELLED', 'ABORTED'): raise OperationFailed()
            if operation.get('status') == 'DONE': return
            require(operation.get('status') in ('PENDING', 'RUNNING'))
            self.sleep(min(delay, self.remaining())); delay = min(10, delay * 2)
            operation = self.get(path)

    def save(self):
        self.receipt['finished_at'] = self.now().isoformat(timespec='seconds').replace('+00:00', 'Z')
        require(len(canonical(self.receipt)) <= MAX_RECEIPT)
        self.persist(self.receipt)

    def create(self, kind, body):
        path = self.paths[kind].rsplit('/', 1)[0] + '?requestId=' + self.receipt['request_ids'][kind]
        # Persist deterministic request identity before dispatch. Never blind-retry POST.
        self.save()
        try:
            _, operation = self.request('POST', path, body)
            self.poll(operation, kind)
        except TransportLoss:
            # The only safe recovery is exact-target readback; missing target stops.
            pass
        value = self.get(self.paths[kind])
        self.identity(kind, value, created=True)
        return value

    def run(self):
        self.prerequisites()
        existing_vm = self.get(self.paths['instance'], missing=True)
        attached = existing_vm is not None
        address = self.get(self.paths['address'], missing=True)
        if address is None:
            require(not attached)
            address = self.create('address', {'name': self.config['resources']['static_ip_name'], 'addressType': 'EXTERNAL', 'ipVersion': 'IPV4', 'networkTier': 'PREMIUM', 'labels': self.labels})
        self.address(address, attached=attached); self.receipt['checks']['address'] = True; self.save()
        disk = self.get(self.paths['disk'], missing=True)
        if disk is None:
            require(not attached)
            disk = self.create('disk', {'name': self.config['resources']['data_disk_name'], 'sizeGb': '200', 'type': self.z + '/diskTypes/pd-balanced', 'labels': self.labels})
        self.disk(disk, attached=attached); self.receipt['checks']['disk'] = True; self.save()
        boot = self.get(self.paths['boot_disk'], missing=True)
        if existing_vm is None:
            require(boot is None)
            self.prerequisites()
            # Revalidate resource identities and unattached state immediately before VM POST.
            self.address(self.get(self.paths['address'])); self.disk(self.get(self.paths['disk']))
            require(self.get(self.paths['instance'], missing=True) is None and self.get(self.paths['boot_disk'], missing=True) is None)
            existing_vm = self.create('instance', self.instance_body())
            boot = self.get(self.paths['boot_disk']); self.identity('boot_disk', boot, created=True)
        self.instance(existing_vm)
        self.disk(boot, boot=True, attached=True)
        self.disk(self.get(self.paths['disk']), attached=True)
        self.address(self.get(self.paths['address']), attached=True)
        self.prerequisites()
        effective = self.get(self.vm + '/getEffectiveFirewalls?networkInterface=nic0')
        require(effective.get('firewallPolicys') == [] and normalized_firewalls(effective.get('firewalls'), self.network, self.config['resources']['instance_name']) == self.rules)
        self.receipt['checks']['instance'] = True
        self.receipt.update(status='passed', failure_code=None); self.save()
        return self.receipt


def main(runtime, transport=None, now=None, persist=None):
    now = now or (lambda: datetime.now(timezone.utc))
    result = receipt_base(now()); engine = None
    try:
        config, approval = read_inputs(runtime)
        # Preserve the existing unavailable production-apply exit contract.
        if config.get('environment') != 'staging' or config.get('public_origin', '').split('/')[2].split(':')[0].lower().rstrip('.') in ('cars.tk', 'www.cars.tk'):
            raise Dependency()
        validate_approval(config, approval, runtime, now())
        if persist is None:
            with ReceiptStore(runtime) as store:
                return _apply(config, approval, runtime, transport, now, store.write, store.read(approval['authorization_id']))
        return _apply(config, approval, runtime, transport, now, persist, None)
    except Denied: code, failure = 2, 'invalid_input'
    except Dependency: code, failure = 3, 'missing_dependency'
    except TimedOut: code, failure = 5, 'operation_timed_out'
    except (Exception, KeyboardInterrupt): code, failure = 4, 'operation_failed'
    result.update(status='timed_out' if code == 5 else 'failed', failure_code=failure)
    return code, result


def _apply(config, approval, runtime, transport, now, persist, prior):
    engine = None
    try:
        # Approval and fixed private input validation always precede token access.
        token = read_token()
        engine = Bootstrap(config, approval, runtime, transport or ComputeTransport(token), now=now, persist=persist, prior=prior)
        engine.run()
        return 0, engine.receipt
    except Denied: code, failure = 2, 'invalid_input'
    except Dependency: code, failure = 3, 'missing_dependency'
    except TimedOut: code, failure = 5, 'operation_timed_out'
    except (Exception, KeyboardInterrupt): code, failure = 4, 'operation_failed'
    result = engine.receipt if engine else receipt_base(now())
    result.update(status='timed_out' if code == 5 else 'failed', failure_code=failure)
    if engine:
        try: engine.save()
        except Exception:
            result.update(status='incomplete', failure_code='recovery_incomplete'); code = 6
    return code, result
