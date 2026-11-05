"""Synthetic purchase delivery definitions; no daemon, cloud or acceptance credit."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_host_runtime as host_contract

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'workers/ingestion-python/src'))
from autodata_ingestion.purchase_config import parse_purchase_config

ENV_NAME = 'AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON'
DISABLED = {'enabled': False, 'terms_version': 'workshop-v1', 'terms_url': None,
            'privacy_url': None, 'refund_url': None, 'contact_url': None, 'tax_notice': None}
URL_KEYS = ('terms_url', 'privacy_url', 'refund_url', 'contact_url')


def enabled_public():
    return dict(DISABLED, enabled=True, terms_url='https://legal.example.test/terms',
                privacy_url='https://legal.example.test/privacy', refund_url='https://legal.example.test/refund',
                contact_url='https://legal.example.test/contact', tax_notice='Synthetic USD20 notice')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def fixture():
    case = host_contract.ContractTests()
    try:
        case.setUp()
        return case.rt, case.config, case.manifest
    finally:
        case.doCleanups()


def boundary_public(target):
    # Each dollar adds five bytes after transport escaping. Trim at most four
    # ASCII notice bytes to reach each residue, retaining valid nonempty text.
    value = dict(enabled_public(), **{key: 'https://legal.example.test/' + 'x' * (2048 - 27) for key in URL_KEYS},
                 tax_notice='x' * 1024)
    while (target - len(canonical(value))) % 5:
        value['tax_notice'] = value['tax_notice'][:-1]
    count = (target - len(canonical(value))) // 5
    value['terms_url'] = 'https://legal.example.test/' + '$' * count + 'x' * (2048 - 27 - count)
    return value


class PurchaseDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.rt, self.config, self.manifest = fixture()
        for guard in (patch.object(subprocess, 'Popen', side_effect=AssertionError('subprocess forbidden')),
                      patch.object(socket, 'socket', side_effect=AssertionError('network forbidden'))):
            guard.start(); self.addCleanup(guard.stop)

    def configure(self, value):
        self.config['workshop_purchase_config'] = copy.deepcopy(value)
        self.manifest['service_config_sha256'] = hashlib.sha256(canonical(self.config)).hexdigest()

    def assert_parity(self, value, valid):
        parsed, malformed = parse_purchase_config(json.dumps(value, ensure_ascii=True))
        self.assertEqual(not malformed, valid)
        self.config['workshop_purchase_config'] = copy.deepcopy(value)
        if valid:
            self.rt.validate_config(self.config)
            wire = self.rt._purchase_config_environment_json(value)
            delivered, malformed = parse_purchase_config(wire)
            self.assertFalse(malformed)
            self.assertEqual(delivered.public(), parsed.public())
        else:
            with self.assertRaises(self.rt.ContractError):
                self.rt.validate_config(self.config)

    def test_independent_task59_url_vectors_and_all_forbidden_codepoints(self):
        # Reuse only the frozen public vectors, never a production validator.
        spec = importlib.util.spec_from_file_location('task59_purchase_vectors', ROOT / 'workers/ingestion-python/tests/test_purchase_config.py')
        vectors = importlib.util.module_from_spec(spec); spec.loader.exec_module(vectors)
        for vector in vectors.URL_VECTORS:
            with self.subTest(vector=vector['id']):
                self.assert_parity(dict(enabled_public(), terms_url=vector['url']), vector['valid'])
        for code in vectors.FORBIDDEN:
            for url in (chr(code) + 'https://example.com/a', 'https://example.com/a' + chr(code) + 'b',
                        'https://example.com/a' + chr(code)):
                with self.subTest(code=code, url=repr(url)):
                    self.assert_parity(dict(enabled_public(), terms_url=url), False)

    def test_scalar_closed_shape_and_disabled_parity(self):
        self.assert_parity(DISABLED, True)
        self.assert_parity(enabled_public(), True)
        for value in (None, '', 'disabled', [], True, {}, {'enabled': False}, dict(DISABLED, extra=1),
                      dict(DISABLED, terms_url='https://example.com'), dict(DISABLED, tax_notice=''),
                      dict(DISABLED, enabled=0), dict(DISABLED, terms_version=None)):
            with self.subTest(value=value): self.assert_parity(value, False)
        for key in DISABLED:
            value = enabled_public(); value.pop(key)
            with self.subTest(missing=key): self.assert_parity(value, False)
        for key, value in (('enabled', 1), ('enabled', 'true'), ('terms_version', 'v2'), ('terms_url', None),
                           ('tax_notice', None), ('tax_notice', 20), ('tax_notice', ''), ('tax_notice', ' '),
                           ('tax_notice', '\ufeff'), ('tax_notice', '\u00a0\u1680\u2000\u202f\u205f\u3000'),
                           ('tax_notice', 'a\nb'), ('tax_notice', 'a\u2028b'), ('tax_notice', 'a\u2029b'),
                           ('tax_notice', 'a\x7fb'), ('tax_notice', 'a\x9fb'), ('tax_notice', 'a\ud800b'),
                           ('terms_url', 'https://example.com/\udfff')):
            with self.subTest(key=key, value=repr(value)):
                self.assert_parity(dict(enabled_public(), **{key: value}), False)
        for code in list(range(32)) + list(range(127, 160)):
            self.assert_parity(dict(enabled_public(), tax_notice='a' + chr(code)), False)
        self.assert_parity(dict(enabled_public(), tax_notice='\u00a0a\ufeff'), True)

    def test_utf8_url_notice_and_dns_boundaries_match_task59(self):
        prefix = 'https://legal.example.test/'
        for length, valid in ((2048, True), (2049, False)):
            self.assert_parity(dict(enabled_public(), terms_url=prefix + 'x' * (length - len(prefix))), valid)
        for notice, valid in (('x' * 1024, True), ('x' * 1025, False), ('é' * 512, True), ('é' * 512 + 'x', False)):
            self.assert_parity(dict(enabled_public(), tax_notice=notice), valid)
        for host, valid in (('a.co', True), ('a.c', False), ('a.' + 'x' * 63, True), ('a.' + 'x' * 64, False),
                            ('x' * 63 + '.test', True), ('x' * 64 + '.test', False),
                            ('.'.join(['x' * 63] * 3 + ['x' * 61]), True),
                            ('.'.join(['x' * 63] * 3 + ['x' * 62]), False)):
            self.assert_parity(dict(enabled_public(), terms_url='https://' + host + '/'), valid)

    def test_escaped_wire_16384_succeeds_16385_rejects_before_render(self):
        for target in (16384, 16385):
            value = boundary_public(target)
            raw = canonical(value).decode()
            wire = raw.replace('$', r'\u0024')
            self.assertEqual(len(wire.encode()), target)
            self.assertFalse(parse_purchase_config(raw)[1])
            self.configure(value)
            if target == 16384:
                self.rt.validate_config(self.config)
                self.assertEqual(self.rt._purchase_config_environment_json(value), wire)
                self.assertEqual(parse_purchase_config(wire)[0].public(), value)
            else:
                for operation in (lambda: self.rt.validate_config(self.config),
                                  lambda: self.rt.render_bundle(self.manifest, self.config)):
                    with self.assertRaisesRegex(self.rt.ContractError, '^purchase_config_transport_limit$'):
                        operation()

    def test_pathological_task59_valid_dollars_fail_transport_ceiling(self):
        value = dict(enabled_public(), **{key: 'https://legal.example.test/' + '$' * (2048 - 27) for key in URL_KEYS},
                     tax_notice='$' * 1024)
        raw = canonical(value).decode()
        self.assertEqual(len(raw.encode()), 9343)
        self.assertEqual(len(raw.replace('$', r'\u0024').encode()), 54883)
        self.assertFalse(parse_purchase_config(raw)[1])
        self.configure(value)
        with self.assertRaisesRegex(self.rt.ContractError, '^purchase_config_transport_limit$'):
            self.rt.validate_config(self.config)

    def test_renderer_delivers_exact_literals_only_to_ingestion_without_aliasing(self):
        value = dict(enabled_public(), tax_notice='$20 ${UNTRUSTED_ENV} $(id) `id` $$ \\" café 🚗',
                     terms_url='https://legal.example.test/$20/${UNTRUSTED_ENV}/$(id)/`id`/$$/\\/%20')
        self.configure(value)
        before = copy.deepcopy(self.config)
        bundle = self.rt.render_bundle(self.manifest, self.config)
        self.assertEqual(bundle, self.rt.render_bundle(self.manifest, self.config))
        compose = json.loads(bundle['compose.production.yaml'])
        self.assertEqual(set(compose['services']), set(self.rt.NORMAL_SERVICES) | {'migration', 'bootstrap', 'metrics-probe'})
        for name, service in compose['services'].items():
            env = service.get('environment', {})
            self.assertEqual(ENV_NAME in env, name == 'ingestion-http')
            self.assertTrue(all('$' not in item for item in env.values()))
            for secret in self.rt.SECRET_NAMES.get(name, ()):
                self.assertNotIn(secret, env)
        wire = compose['services']['ingestion-http']['environment'][ENV_NAME]
        self.assertEqual(wire, canonical(value).decode().replace('$', r'\u0024'))
        parsed, malformed = parse_purchase_config(wire)
        self.assertFalse(malformed); self.assertEqual(parsed.public(), value)
        self.assertEqual(self.config, before)
        compose['services']['ingestion-http']['environment'][ENV_NAME] = 'changed'
        self.assertEqual(bundle, self.rt.render_bundle(self.manifest, self.config))
        self.config['workshop_purchase_config']['tax_notice'] = 'later'
        self.assertEqual(parse_purchase_config(wire)[0].public(), value)

    def test_hash_changes_for_every_field_and_pause_blocks_automatic_rollback(self):
        self.configure(enabled_public())
        original_hash = self.rt.validate_config(self.config)
        reversed_config = copy.deepcopy(self.config)
        reversed_config['workshop_purchase_config'] = dict(reversed(list(enabled_public().items())))
        self.assertEqual(self.rt.validate_config(reversed_config), original_hash)
        for key in (*URL_KEYS, 'tax_notice'):
            changed = copy.deepcopy(self.config); changed['workshop_purchase_config'][key] += 'x'
            self.assertNotEqual(self.rt.validate_config(changed), original_hash)
            with self.assertRaises(self.rt.ContractError): self.rt.render_bundle(self.manifest, changed)
        for old, new in ((enabled_public(), DISABLED), (DISABLED, enabled_public())):
            self.configure(old)
            previous = copy.deepcopy(self.manifest); previous['source_sha'] = 'd' * 40
            current = copy.deepcopy(self.manifest); current['rollback_source_sha'] = 'd' * 40
            self.rt.validate_manifest(current, self.config, previous)
            self.configure(new)
            current['service_config_sha256'] = self.manifest['service_config_sha256']
            with self.assertRaises(self.rt.ContractError): self.rt.validate_manifest(current, self.config, previous)
            previous['service_config_sha256'] = current['service_config_sha256']
            self.rt.validate_manifest(current, self.config, previous)

    def test_rollback_also_rejects_inconsistent_internal_token_version(self):
        previous = copy.deepcopy(self.manifest); previous['source_sha'] = 'd' * 40
        current = copy.deepcopy(self.manifest); current['rollback_source_sha'] = 'd' * 40
        previous['secret_versions']['ingestion-http']['AUTODATA_INGESTION_INTERNAL_TOKEN'] = 'projects/autodata-host/secrets/different/versions/1'
        with self.assertRaises(self.rt.ContractError): self.rt.validate_manifest(current, self.config, previous)


# Fixed harmless child. No HTTP listener, DB/provider call or session creation.
TRANSPORT_CHILD = r"""
import hashlib, json, os, pathlib, sys
from autodata_ingestion.purchase_config import parse_purchase_config
from autodata_ingestion.commerce_service import CommerceService, CommerceConfig, CommerceError

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()

wire = os.environ['AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON']
initial, malformed = parse_purchase_config(wire)
assert not malformed
private = pathlib.Path(sys.argv[1]) / 'ingestion-http' / 'AUTODATA_INGESTION_INTERNAL_TOKEN'
token_matches = private.read_text() == os.environ['AUTODATA_INGESTION_INTERNAL_TOKEN']
calls = {'database': 0, 'provider': 0}
def forbidden_database():
    calls['database'] += 1
    raise AssertionError('database forbidden')
class ForbiddenProvider:
    def __getattr__(self, name):
        calls['provider'] += 1
        raise AssertionError('provider forbidden')
financial = CommerceConfig(os.environ['AUTODATA_COMMERCE_MODE'], os.environ['AUTODATA_STRIPE_ACCOUNT_ID'], os.environ['AUTODATA_STRIPE_PRICE_ID'])
old = CommerceService(forbidden_database, financial, ForbiddenProvider(), purchase_config=initial)
initial_projection = old.purchase_configuration()
os.environ['AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON'] = sys.argv[2]
paused, malformed = parse_purchase_config(os.environ['AUTODATA_WORKSHOP_PURCHASE_CONFIG_JSON'])
assert not malformed and not paused.enabled
replacement = CommerceService(forbidden_database, financial, ForbiddenProvider(), purchase_config=paused)
denials = []
for key in ('11111111-1111-4111-8111-111111111111', '11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222'):
    try:
        replacement.checkout('synthetic-account', 'synthetic-org', key, dict(configuration_id='33333333-3333-4333-8333-333333333333', region='US', terms_version='workshop-v1'))
    except CommerceError as error:
        denials.append(error.code == 'COMMERCE_UNAVAILABLE' and error.http_status == 503)
    else:
        denials.append(False)
print(json.dumps({'projection_sha256': digest(initial_projection), 'wire_sha256': hashlib.sha256(wire.encode()).hexdigest(),
    'token_matches_private_file': token_matches, 'old_object_still_enabled': old.purchase_configuration()['enabled'],
    'replacement_disabled': replacement.purchase_configuration()['enabled'] is False,
    'disabled_projection_sha256': digest(replacement.purchase_configuration()), 'checkout_denials': denials,
    'database_calls': calls['database'], 'provider_calls': calls['provider']}))
"""


class PurchaseTransportTests(unittest.TestCase):
    def setUp(self):
        self.rt, self.config, self.manifest = fixture()
        guard = patch.object(socket, 'socket', side_effect=AssertionError('network forbidden'))
        guard.start(); self.addCleanup(guard.stop)
        self.assertEqual((os.getuid(), os.getgid()), (1000, 1000), 'required wrapper fixture ownership missing')
        self.temp = tempfile.TemporaryDirectory(prefix='purchase-delivery-')
        self.addCleanup(self.cleanup_tree)
        self.base = Path(self.temp.name)
        self.secret_root = self.base / 'secrets'; self.secret_root.mkdir(mode=0o700)
        directory = self.secret_root / 'ingestion-http'; directory.mkdir(mode=0o700)
        for name in self.rt.SECRET_NAMES['ingestion-http']:
            path = directory / name
            path.write_text('synthetic-opaque-$()`;"\\-value')
            path.chmod(0o400)
        directory.chmod(0o500)
        source = (HERE / 'runtime-entrypoint.sh').read_text()
        self.assertEqual(source.count('secret_root=/run/autodata'), 1)
        self.wrapper = self.base / 'entrypoint.sh'
        self.wrapper.write_text(source.replace('secret_root=/run/autodata', 'secret_root=' + str(self.secret_root)))
        self.value = dict(enabled_public(), tax_notice='$20 ${UNTRUSTED_ENV} $(id) `id` $$ \\" café 🚗',
                          terms_url='https://legal.example.test/$20/${UNTRUSTED_ENV}/$(id)/`id`/$$/\\/%20')

    def cleanup_tree(self):
        for base, _, _ in os.walk(self.temp.name):
            Path(base).chmod(0o700)
        self.temp.cleanup()

    def render(self, value):
        self.config['workshop_purchase_config'] = copy.deepcopy(value)
        self.manifest['service_config_sha256'] = hashlib.sha256(canonical(self.config)).hexdigest()
        self.rendered_compose = self.rt.render_bundle(self.manifest, self.config)['compose.production.yaml']
        return json.loads(self.rendered_compose)

    def through_wrapper(self, environment):
        disabled_env = self.render(DISABLED)['services']['ingestion-http']['environment']
        for key in ('AUTODATA_COMMERCE_MODE', 'AUTODATA_STRIPE_ACCOUNT_ID', 'AUTODATA_STRIPE_PRICE_ID'):
            self.assertEqual(environment[key], disabled_env[key])
        child_env = dict(environment, PATH='/usr/bin:/bin', PYTHONPATH=str(ROOT / 'workers/ingestion-python/src'),
                         PYTHONDONTWRITEBYTECODE='1')
        result = subprocess.run(['/bin/sh', str(self.wrapper), sys.executable, '-B', '-c', TRANSPORT_CHILD,
                                 str(self.secret_root), disabled_env[ENV_NAME]], env=child_env,
                                cwd=self.base, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, 'required wrapper/parser child failed: ' + result.stderr)
        self.assertEqual(result.stderr, '')
        observation = json.loads(result.stdout)
        self.assertEqual(observation, {
            'projection_sha256': hashlib.sha256(canonical(self.value)).hexdigest(),
            'wire_sha256': hashlib.sha256(environment[ENV_NAME].encode()).hexdigest(),
            'token_matches_private_file': True, 'old_object_still_enabled': True, 'replacement_disabled': True,
            'disabled_projection_sha256': hashlib.sha256(canonical(DISABLED)).hexdigest(),
            'checkout_denials': [True, True, True], 'database_calls': 0, 'provider_calls': 0})
        return observation

    def test_actual_renderer_wrapper_parser_and_frozen_service_replacement(self):
        for value in (self.value, boundary_public(16384)):
            with self.subTest(wire_bytes=len(canonical(value).decode().replace('$', r'\u0024').encode())):
                self.value = value
                environment = self.render(value)['services']['ingestion-http']['environment']
                self.through_wrapper(environment)

    def test_local_compose_preserves_wire_before_wrapper_required_mode(self):
        required = os.environ.get('AUTODATA_REQUIRE_PURCHASE_CONFIG_DELIVERY_COMPOSE') == '1'
        if not required:
            self.skipTest('local Compose phase requires AUTODATA_REQUIRE_PURCHASE_CONFIG_DELIVERY_COMPOSE=1')
        for value in (self.value, boundary_public(16384)):
            with self.subTest(wire_bytes=len(canonical(value).decode().replace('$', r'\u0024').encode())):
                self.value = value
                compose = self.render(value)
                path = self.base / 'compose.json'; path.write_text(self.rendered_compose)
                cli_env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C',
                           'UNTRUSTED_ENV': 'hostile-interpolation-would-corrupt-projection'}
                result = subprocess.run(['/usr/bin/docker', 'compose', '--project-directory', str(self.base),
                                         '-f', str(path), 'config', '--format', 'json'],
                                        env=cli_env, cwd=self.base, stdin=subprocess.DEVNULL,
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, 'required local Compose config failed: ' + result.stderr)
                configured = json.loads(result.stdout)
                actual = configured['services']['ingestion-http']['environment']
                expected = compose['services']['ingestion-http']['environment']
                self.assertEqual(actual, expected)
                self.through_wrapper(actual)


if __name__ == '__main__':
    unittest.main()
