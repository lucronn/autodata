"""Authored-only integrity/containment tests; never touch Docker/DB/S3."""
import base64
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import patch
import uuid

spec = importlib.util.spec_from_file_location('integrity', Path(__file__).with_name('retained_article_integrity.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture():
    article, config, source, snapshot, canonical = [str(uuid.uuid4()) for _ in range(5)]
    body = b'FICTIONAL_PRIVATE_MARKER_7e9b: inspect a made-up mechanism.'
    sha = m.digest(body)
    doc = {'schema_version': 1, 'normalization_version': 'ordered-article-v1',
           'blocks': [{'source_order': 1, 'block_id': article + ':block:0001',
                       'type': 'paragraph', 'text': 'FICTIONAL_PRIVATE_MARKER_7e9b'}]}
    return {'article_id': article, 'configuration_id': config, 'source_revision_id': source,
            'snapshot_id': snapshot, 'canonical_revision_id': canonical, 'current_article_id': article,
            'current_source_revision_id': source, 'current_canonical_revision_id': canonical,
            'source_sha256': sha, 'object_key': 'sources/' + sha[:16] + '/' + sha,
            'source_document': doc, 'current_document': copy.deepcopy(doc), 'available': True,
            'canonical': True, 'published': True, 'readable': True, 'unreviewed': True,
            'license_metadata_empty': True, 'body_base64': base64.b64encode(body).decode()}


class IntegrityTests(unittest.TestCase):
    def test_authored_success_is_redacted(self):
        value = fixture()
        result = m.validate(m.encoded(value))
        output = json.dumps(result)
        self.assertTrue(result['passed'])
        self.assertTrue(result['source_hash_verified'])
        self.assertFalse(result['paid_reader_acceptance'])
        self.assertEqual(result['documents']['source_document']['blocks'], 1)
        for private in [value['article_id'], value['configuration_id'], value['object_key'],
                        'FICTIONAL_PRIVATE_MARKER_7e9b', value['body_base64']]:
            self.assertNotIn(private, output)

    def test_hash_identity_key_state_schema_fail_closed(self):
        changes = [({'body_base64': base64.b64encode(b'wrong').decode()}, 'SOURCE_HASH'),
                   ({'source_sha256': '0' * 64}, 'OBJECT_KEY'),
                   ({'object_key': 'other'}, 'OBJECT_KEY'),
                   ({'current_article_id': str(uuid.uuid4())}, 'IDENTITY'),
                   ({'current_source_revision_id': str(uuid.uuid4())}, 'IDENTITY'),
                   ({'current_canonical_revision_id': str(uuid.uuid4())}, 'IDENTITY'),
                   ({'published': False}, 'PROJECTION_STATE'),
                   ({'license_metadata_empty': 'true'}, 'INPUT_SCHEMA'),
                   ({'source_document': {}}, 'DOCUMENT_SCHEMA')]
        for change, code in changes:
            with self.subTest(code=code, keys=list(change)):
                value = fixture(); value.update(change)
                with self.assertRaisesRegex(m.Refused, '^' + code + '$'):
                    m.validate(m.encoded(value))

    def test_document_depth_order_types_and_limits(self):
        changes = [lambda d: d.update(schema_version=2),
                   lambda d: d.update(blocks=[]),
                   lambda d: d['blocks'][0].update(source_order=2),
                   lambda d: d['blocks'][0].update(type='script'),
                   lambda d: d['blocks'][0].update(text=' ')]
        for change in changes:
            value = fixture(); change(value['source_document'])
            with self.assertRaises(m.Refused): m.validate(m.encoded(value))
        value = fixture(); nested = value['source_document']
        for _ in range(26): nested['nested'] = {}; nested = nested['nested']
        with self.assertRaisesRegex(m.Refused, 'DOCUMENT_LIMIT'): m.validate(m.encoded(value))
        with self.assertRaisesRegex(m.Refused, 'INPUT_LIMIT'): m.validate(b'x' * (m.INPUT_MAX + 1))
        value = fixture(); value['body_base64'] = base64.b64encode(b'x' * (m.BODY_MAX + 1)).decode()
        with self.assertRaisesRegex(m.Refused, 'BODY_LIMIT'): m.validate(m.encoded(value))
        value = fixture(); value['source_document']['blocks'][0]['text'] = 'x' * (m.DOCUMENT_MAX + 1)
        with self.assertRaisesRegex(m.Refused, 'DOCUMENT_LIMIT'): m.validate(m.encoded(value))

    def test_unknown_fields_and_malformed_ids(self):
        value = fixture(); value['secret_extra'] = 'private'
        with self.assertRaisesRegex(m.Refused, 'INPUT_SCHEMA'): m.validate(m.encoded(value))
        value = fixture(); value['article_id'] = 'private-invalid-id'
        with self.assertRaises(ValueError): m.validate(m.encoded(value))

    def test_no_raw_error_or_transport_forwarding(self):
        output = io.StringIO()
        with patch.object(sys, 'argv', ['audit', '--run']), patch.object(m, 'run', side_effect=ValueError('PRIVATE_SOURCE')), contextlib.redirect_stdout(output):
            self.assertEqual(m.main(), 1)
        self.assertNotIn('PRIVATE_SOURCE', output.getvalue())
        self.assertEqual(json.loads(output.getvalue())['code'], 'INTEGRITY_FAILED')
        with patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, stdout=b'PRIVATE_SOURCE', stderr=b'PRIVATE_SOURCE')):
            with self.assertRaisesRegex(m.Refused, '^TRANSPORT_FAILED$'): m.run()

    def test_validator_is_network_none_read_only_no_secrets(self):
        argv = m.validator_command(Path('/fixture/audit.py'), 'fixture')
        for flag, value in [('--network', 'none'), ('--cap-drop', 'ALL'), ('--log-driver', 'none'),
                            ('--memory', '128m'), ('--memory-swap', '128m'), ('--pids-limit', '32')]:
            self.assertEqual(argv[argv.index(flag) + 1], value)
        self.assertIn('--read-only', argv)
        self.assertIn('no-new-privileges', argv)
        self.assertIn(m.IMAGE, argv)
        self.assertNotIn('AUTODATA_S3_SECRET_KEY', ' '.join(argv))
        self.assertIn('readonly', argv[argv.index('--mount') + 1])
        self.assertEqual(argv[-5:], ['-I', '-S', '-B', '/audit.py', '--validate'])

    def test_timeout_is_redacted_and_own_child_cleanup_only(self):
        calls = []
        def run(argv, **kwargs):
            calls.append(argv)
            if 'exec' in argv: return subprocess.CompletedProcess(argv, 0, stdout=b'{}', stderr=b'')
            if 'run' in argv: raise subprocess.TimeoutExpired(argv, 10)
            return subprocess.CompletedProcess(argv, 0, stdout=b'', stderr=b'')
        with patch.object(m.subprocess, 'run', side_effect=run):
            with self.assertRaises(subprocess.TimeoutExpired): m.run()
        self.assertEqual(calls[-1][:len(m.DOCKER) + 2], m.DOCKER + ['rm', '-f'])
        self.assertTrue(calls[-1][-1].startswith('autodata-retained-integrity-'))
        self.assertNotIn(m.CONTAINER, calls[-1])

    def test_write_and_python_egress_guards(self):
        for event, args in [('open', ('/file', 'w', 0)),
                            ('open', ('/file', None, m.os.O_RDWR)),
                            ('open', ('/file', None, m.os.O_TRUNC)),
                            ('os.remove', ('/file',)), ('os.rename', ('a', 'b')),
                            ('os.mkdir', ('dir',)), ('subprocess.Popen', ('command',)),
                            ('socket.connect', (None, ('198.51.100.9', 443))),
                            ('socket.getaddrinfo', ('provider.invalid', 443))]:
            with self.subTest(event=event):
                with self.assertRaises(m.Refused): m.transport_audit(event, args)
        m.transport_audit('open', ('/source', 'r', m.os.O_RDONLY))
        m.transport_audit('socket.connect', (None, ('127.0.0.1', 19000)))

    def test_transport_local_endpoint_guard_precedes_any_client_import(self):
        # No psycopg/minio on this host is needed: the endpoint guard runs first.
        with patch.dict(m.os.environ, {'AUTODATA_DB_ADDRESS': 'remote.invalid:5432'}, clear=True), \
             patch('resource.setrlimit'), patch('signal.alarm'):
            with self.assertRaisesRegex(m.Refused, 'LOCAL_ENDPOINT'): m.transport()
        self.assertTrue(m.SQL.lstrip().startswith('SELECT '))
        self.assertNotIn('FOR UPDATE', m.SQL)
        for keyword in ['INSERT ', 'UPDATE ', 'DELETE ', 'CREATE ', 'DROP ', 'ALTER ']:
            self.assertNotIn(keyword, m.SQL.upper())


if __name__ == '__main__':
    unittest.main()
