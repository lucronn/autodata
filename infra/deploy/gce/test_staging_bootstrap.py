"""Offline bare-resource bootstrap contract. Every transport is intercepted."""
import copy
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import socket
import unittest
from unittest.mock import patch
import uuid

import test_host_runtime as host_test

HERE = Path(__file__).resolve().parent
NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
ROOT = 'https://www.googleapis.com/compute/v1'


def load():
    path = HERE / 'staging_bootstrap.py'
    assert path.is_file(), 'staging bootstrap implementation missing'
    spec = importlib.util.spec_from_file_location('staging_bootstrap', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        fixture = host_test.ContractTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.rt, self.config = fixture.rt, fixture.config
        self.m = load()
        self.p = ROOT + '/projects/autodata-host'
        self.z = self.p + '/zones/us-central1-a'
        self.r = self.p + '/regions/us-central1'
        self.network = self.p + '/global/networks/staging'
        self.subnet = self.r + '/subnetworks/staging'
        self.image = ROOT + '/projects/image-owner/global/images/reviewed'
        self.approval = {
            'schema_version': 1, 'operation': 'create-staging-resources',
            'authorization_id': '12345678-1234-4234-8234-123456789abc',
            'resource_nonce': '22345678-1234-4234-8234-123456789abc',
            'expires_at': '2026-11-04T13:00:00Z', 'service_config_sha256': self.rt.sha256(self.config),
            'boot_image': {'self_link': self.image, 'id': '101', 'architecture': 'X86_64'},
            'network': {'network_self_link': self.network, 'subnetwork_self_link': self.subnet,
                        'reviewed_firewall_evidence_sha256': 'a' * 64, 'reviewed_routes_evidence_sha256': 'b' * 64},
            'attached_identity': {'email': 'autodata-api-firebase@autodata-host.iam.gserviceaccount.com',
                                  'reviewed_iam_evidence_sha256': 'c' * 64},
            'bootstrap_identity_evidence_sha256': 'd' * 64, 'owner_cost_and_region_evidence_sha256': 'e' * 64}

    def validate(self, value=None):
        return self.m.validate_approval(self.config, self.approval if value is None else value, self.rt, NOW)

    def test_apply_production_denied(self):
        self.config['environment'] = 'production'
        with self.assertRaises(self.m.Denied): self.validate()
        self.config['environment'] = 'staging'
        self.config['public_origin'] = 'https://cars.tk'
        with self.assertRaises(self.m.Denied): self.validate()

    def test_unknown_duplicate_or_expired_approval_denied(self):
        self.validate()
        for edit in (lambda x: x.update(extra=True), lambda x: x.update(schema_version=True),
                     lambda x: x.update(expires_at='2026-11-04T12:00:00Z'),
                     lambda x: x.update(expires_at='2026-11-06T12:00:00Z'),
                     lambda x: x['boot_image'].update(id='0'), lambda x: x.update(resource_nonce=str(uuid.uuid1())),
                     lambda x: x['network'].update(extra='bad'), lambda x: x.update(owner_cost_and_region_evidence_sha256=None)):
            candidate = copy.deepcopy(self.approval); edit(candidate)
            with self.subTest(candidate=candidate), self.assertRaises(self.m.Denied): self.validate(candidate)
        for data in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":null}', b'{}' * 40000):
            with self.assertRaises(self.m.Denied): self.m.strict_json(data, 65536)

    def routes(self, cidr='10.50.0.0/24'):
        return [{'network': self.network, 'destRange': cidr, 'nextHopNetwork': self.network},
                {'network': self.network, 'destRange': '0.0.0.0/0',
                 'nextHopGateway': self.p + '/global/gateways/default-internet-gateway'}]

    def test_approved_default_and_disjoint_subnet_pass(self):
        self.m.validate_routes(self.routes(), self.network, '10.50.0.0/24', self.p)

    def test_overlapping_selected_subnet_denied(self):
        for cidr in ('172.30.10.0/24', '172.30.0.0/16'):
            with self.assertRaises(self.m.Denied): self.m.validate_routes(self.routes(cidr), self.network, cidr, self.p)

    def test_default_route_custom_next_hop_denied(self):
        routes = self.routes(); routes[1].pop('nextHopGateway'); routes[1]['nextHopInstance'] = self.z + '/instances/other'
        with self.assertRaises(self.m.Denied): self.m.validate_routes(routes, self.network, '10.50.0.0/24', self.p)

    def test_additional_destination_denied_even_when_disjoint(self):
        routes = self.routes() + [{'network': self.network, 'destRange': '10.60.0.0/24', 'nextHopNetwork': self.network}]
        with self.assertRaises(self.m.Denied): self.m.validate_routes(routes, self.network, '10.50.0.0/24', self.p)

    def test_no_approval_no_token_no_requests(self):
        calls = []
        with patch.object(self.m, 'read_inputs', side_effect=self.m.Dependency), patch.object(self.m, 'read_token', side_effect=AssertionError('token read')):
            code, receipt = self.m.main(self.rt, transport=lambda *args: calls.append(args), now=lambda: NOW, persist=lambda x: None)
        self.assertEqual(code, 3); self.assertEqual(calls, []); self.assertFalse(receipt['deployment_authorized'])

    def engine(self, fake=None, **kwargs):
        kwargs.setdefault('sleep', lambda _: None)
        return self.m.Bootstrap(self.config, self.approval, self.rt, fake or self.fake(), now=lambda: NOW, **kwargs)

    def fake(self):
        return FakeCompute(self)

    def test_request_inventory_exact(self):
        fake = self.fake(); engine = self.engine(fake); result = engine.run()
        self.assertEqual(result['status'], 'passed')
        posts = [(path, body) for method, path, body in fake.calls if method == 'POST']
        self.assertEqual([p.split('?')[0] for p, b in posts], [self.r + '/addresses', self.z + '/disks', self.z + '/instances'])
        for kind, (path, body) in zip(('address', 'disk', 'instance'), posts):
            self.assertIn('requestId=' + str(uuid.uuid5(uuid.UUID(self.approval['resource_nonce']), self.approval['authorization_id'] + ':' + kind)), path)
        self.assertEqual(posts[0][1], {'name': 'workshop-ip', 'addressType': 'EXTERNAL', 'ipVersion': 'IPV4', 'networkTier': 'PREMIUM', 'labels': engine.labels})
        self.assertEqual(posts[1][1], {'name': 'workshop-data', 'sizeGb': '200', 'type': self.z + '/diskTypes/pd-balanced', 'labels': engine.labels})
        self.assertTrue(all(method in ('GET', 'POST') for method, _, _ in fake.calls))
        self.assertEqual(set(engine.resources), {'address', 'disk', 'instance', 'boot_disk'})

    def test_bare_vm_has_no_startup_script_or_format_action(self):
        fake = self.fake(); self.engine(fake).run()
        body = [b for m, p, b in fake.calls if m == 'POST'][-1]
        self.assertEqual(body['metadata']['items'], [{'key': 'enable-oslogin', 'value': 'TRUE'}, {'key': 'block-project-ssh-keys', 'value': 'TRUE'}, {'key': 'serial-port-enable', 'value': 'FALSE'}])
        self.assertTrue(body['deletionProtection']); self.assertFalse(body['canIpForward'])
        self.assertEqual(body['tags'], {'items': ['workshop-stage']})
        self.assertEqual(body['disks'][0]['initializeParams']['diskSizeGb'], '20')
        self.assertFalse(body['disks'][0]['autoDelete']); self.assertFalse(body['disks'][1]['autoDelete'])
        self.assertNotIn('startup', json.dumps(body)); self.assertNotIn('format', json.dumps(body))

    def test_passed_receipt_has_no_runtime_authority(self):
        receipt = self.engine().run()
        self.assertFalse(receipt['definition_only']); self.assertFalse(receipt['deployment_authorized'])
        self.assertEqual(receipt['cleanup'], 'resources-retained')
        for key in ('schema', 'services', 'runtime_evidence'): self.assertFalse(receipt['checks'][key])

    def test_idempotent_matching_rerun(self):
        fake = self.fake(); prior = self.engine(fake).run(); fake.calls.clear()
        self.assertEqual(self.engine(fake, prior=prior).run()['status'], 'passed')
        self.assertFalse(any(m == 'POST' for m, _, _ in fake.calls))

    def test_unowned_existing_resource_not_adopted(self):
        fake = self.fake(); fake.objects[self.r + '/addresses/workshop-ip'] = {'id': '1', 'labels': {}}
        with self.assertRaises(self.m.Denied): self.engine(fake).run()
        self.assertFalse(any(m == 'POST' for m, _, _ in fake.calls))

    def test_pin_route_policy_or_owner_drift_denied(self):
        for path, change in ((self.image, {'id': '102'}), (self.network, {'peerings': [{}]}),
                             (self.network + '/getEffectiveFirewalls', {'firewallPolicys': [{}]}),
                             (self.p, {'commonInstanceMetadata': {'items': [{'key': 'startup-script', 'value': 'bad'}]}})):
            fake = self.fake(); fake.objects[path].update(change)
            with self.subTest(path=path), self.assertRaises(self.m.Denied): self.engine(fake).run()
            self.assertFalse(any(m == 'POST' for m, _, _ in fake.calls))

    def test_post_transport_loss_same_request_id(self):
        fake = self.fake(); fake.lose_post = True
        self.assertEqual(self.engine(fake).run()['status'], 'passed')
        self.assertEqual(sum(m == 'POST' for m, _, _ in fake.calls), 3)

    def test_timeout_retains_resources(self):
        fake = self.fake(); fake.pending = True
        tick = iter(range(0, 100000, 31))
        engine = self.engine(fake, monotonic=lambda: next(tick), sleep=lambda x: None)
        with self.assertRaises(self.m.TimedOut): engine.run()
        self.assertTrue(fake.objects[self.r + '/addresses/workshop-ip'])
        self.assertFalse(any(m == 'DELETE' for m, _, _ in fake.calls))

    def test_output_bounds_and_token_redaction(self):
        for token in (b'', b'abc\n', b'abc\x00', b'x' * 16385):
            with self.assertRaises(self.m.Denied): self.m.validate_token(token)
        self.assertEqual(self.m.validate_token(b'private-token'), 'private-token')
        receipt = self.engine().run()
        self.assertLessEqual(len(json.dumps(receipt)), 65536)
        self.assertNotIn('private-token', json.dumps(receipt))

    def launcher(self):
        body = (HERE / 'cloud-bootstrap.sh').read_text().split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
        namespace = {'__name__': 'offline_definition'}
        exec(compile(body, 'cloud-bootstrap.sh', 'exec'), namespace)
        return namespace

    def test_launcher_delegates_only_apply_to_fixed_installed_helper(self):
        launcher = self.launcher()
        self.assertIn('load_staging', launcher)
        helper = type('Helper', (), {'main': staticmethod(lambda runtime: (0, {'sentinel': True}))})
        with patch.dict(launcher, load_staging=lambda: helper):
            self.assertEqual(launcher['main'](['apply'], runtime=self.rt), (0, {'sentinel': True}))
        self.assertEqual(launcher['STAGING_HELPER'], '/opt/autodata/bin/staging_bootstrap.py')

    def test_schema_is_strict_and_matches_approval_keys(self):
        schema = HERE / 'staging-bootstrap.schema.json'
        self.assertTrue(schema.is_file(), 'approval schema missing')
        value = json.loads(schema.read_text())
        self.assertEqual(set(value['required']), set(self.approval))
        self.assertFalse(value['additionalProperties'])
        for field in ('network', 'boot_image', 'attached_identity'):
            child = value['properties'][field]
            self.assertFalse(child['additionalProperties'])
            self.assertEqual(set(child['required']), set(self.approval[field]))

    def test_redirect_and_ambient_adc_denied(self):
        client = self.m.ComputeTransport('private-token', opener=lambda *a, **k: (_ for _ in ()).throw(AssertionError('network')))
        for url in ('http://compute.googleapis.com/compute/v1/projects/x', 'https://evil/compute/v1/projects/x', ROOT + '/projects/x'):
            with self.assertRaises(self.m.Denied): client('GET', url, None, 30)
        self.assertNotIn('gcloud', (HERE / 'staging_bootstrap.py').read_text())


class FakeCompute:
    def __init__(self, test):
        self.t = test; self.calls = []; self.lose_post = False; self.pending = False
        self.objects = {
            test.p: {'commonInstanceMetadata': {'items': []}},
            test.image: {'selfLink': test.image, 'id': '101', 'architecture': 'X86_64', 'status': 'READY'},
            test.z + '/machineTypes/e2-standard-4': {'selfLink': test.z + '/machineTypes/e2-standard-4', 'name': 'e2-standard-4', 'guestCpus': 4, 'memoryMb': 16384},
            test.network: {'selfLink': test.network, 'autoCreateSubnetworks': False, 'subnetworks': [test.subnet]},
            test.subnet: {'selfLink': test.subnet, 'network': test.network, 'region': test.r, 'stackType': 'IPV4_ONLY', 'ipCidrRange': '10.50.0.0/24'},
            test.p + '/global/routes': {'items': test.routes()},
            test.p + '/global/firewalls': {'items': self.rules()},
            test.network + '/getEffectiveFirewalls': {'firewallPolicys': [], 'firewalls': self.rules()},
            test.r + '/firewallPolicies/getEffectiveFirewalls?network=' + test.m.quote(test.network, safe=''): {'firewallPolicys': []},
            test.z + '/instances/workshop-stage/getEffectiveFirewalls?networkInterface=nic0': {'firewallPolicys': [], 'firewalls': self.rules()}}

    def rules(self):
        return [{'network': self.t.network, 'direction': 'INGRESS', 'disabled': False, 'targetTags': ['workshop-stage'],
                 'sourceRanges': [source], 'allowed': [{'IPProtocol': 'tcp', 'ports': ports}]} for source, ports in (('0.0.0.0/0', ['80', '443']), ('35.235.240.0/20', ['22']))]

    def __call__(self, method, path, body, timeout):
        assert timeout <= 30
        assert path.startswith(self.t.m.API + '/projects/')
        path = ROOT + path[len(self.t.m.API):]
        self.calls.append((method, path, copy.deepcopy(body)))
        if method == 'GET':
            if '/operations/' in path: return 200, {'status': 'RUNNING' if self.pending else 'DONE'}
            return (200, copy.deepcopy(self.objects[path])) if path in self.objects else (404, {})
        assert method == 'POST'
        target = path.split('?')[0] + '/' + body['name']
        observed = copy.deepcopy(body); observed.update(id=str(200 + len(self.objects)), selfLink=target)
        if '/addresses/' in target: observed.update(address='203.0.113.10', status='RESERVED', region=self.t.r, users=[])
        elif '/disks/' in target: observed.update(status='READY', users=[])
        else:
            boot = body['disks'][0]['initializeParams']; boot_path = self.t.z + '/disks/' + boot['diskName']
            self.objects[boot_path] = {'id': '900', 'selfLink': boot_path, 'name': boot['diskName'], 'labels': boot['labels'], 'sizeGb': '20', 'type': boot['diskType'], 'status': 'READY', 'sourceImage': boot['sourceImage'], 'sourceImageId': '101', 'users': [target]}
            observed['disks'][0].pop('initializeParams'); observed['disks'][0].update(source=boot_path, deviceName=boot['diskName'], mode='READ_WRITE')
            observed['disks'][1]['index'] = 1
            observed.update(status='RUNNING')
            self.objects[self.t.z + '/disks/workshop-data']['users'] = [target]
            self.objects[self.t.r + '/addresses/workshop-ip'].update(users=[target], status='IN_USE')
        self.objects[target] = observed
        if self.lose_post:
            self.lose_post = False
            raise self.t.m.TransportLoss()
        scope = self.t.r if '/addresses' in target else self.t.z
        return 200, {'selfLink': scope + '/operations/op-' + body['name'], 'name': 'op-' + body['name'], 'status': 'RUNNING'}


if __name__ == '__main__': unittest.main()
