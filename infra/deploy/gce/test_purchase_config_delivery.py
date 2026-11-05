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


if __name__ == '__main__':
    unittest.main()
