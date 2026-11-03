"""Pure protocol regressions; these do not establish PostgreSQL execution safety."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('schema_probe', Path(__file__).with_name('schema_probe.py'))
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)

EXPECTED = ('001_initial', '002_accounts')


def catalog():
    return {
        'protocol_version': 3, 'phase': 'catalog_locked',
        'identity': {'session_user': 'autodata_schema_probe', 'current_user': 'autodata_schema_probe',
                     'database': 'autodata', 'server_version_num': 170000, 'transaction_read_only': True,
                     'default_transaction_read_only': True, 'isolation': 'repeatable read',
                     'client_addr': None, 'client_port': None},
        'rights': {'login': True, 'superuser': False, 'create_db': False, 'create_role': False,
                   'replication': False, 'bypass_rls': False, 'inherit': False, 'membership_count': 0,
                   'connect': True, 'schema_usage': True, 'ledger_select': True, 'ledger_maintain': True,
                   'other_maintain': False, 'database_create': False, 'database_temp': False,
                   'database_owner': False, 'schema_create': False, 'schema_owner': False,
                   'relation_owner': False, 'sequence_owner': False, 'relation_write': False,
                   'column_write': False, 'sequence_write': False},
        'relation': {'oid': 100, 'schema': 'public', 'name': 'schema_migrations', 'kind': 'r',
                     'persistence': 'p', 'heap_builtin': True, 'owner': 'autodata_schema_owner',
                     'owner_login': False, 'is_partition': False, 'has_inheritance': False,
                     'rls': False, 'force_rls': False, 'rule_count': 0, 'trigger_count': 0,
                     'dropped_user_column_count': 0, 'toast_builtin_safe': True},
        'columns': [{'attnum': 1, 'name': 'version', 'type': 'pg_catalog.text', 'not_null': True,
                     'generated': '', 'identity': '', 'collation_safe': True},
                    {'attnum': 2, 'name': 'applied_at', 'type': 'pg_catalog.timestamptz', 'not_null': True,
                     'generated': '', 'identity': '', 'collation_safe': True}],
        'indexes': {'count': 1, 'primary_version_only': True, 'valid': True, 'ready': True,
                    'live': True, 'unique': True, 'immediate': True, 'include_count': 0,
                    'has_expression': False, 'has_predicate': False, 'has_exclusion': False,
                    'btree_builtin': True, 'text_ops_builtin': True, 'collation_safe': True,
                    'support_inventory_count': 28, 'support_inventory_matches_baseline': True},
        'builtins': {'heap_identity_matches': True, 'btree_identity_matches': True,
                     'text_identity_matches': True, 'timestamptz_identity_matches': True,
                     'text_ops_family_matches': True, 'operators_and_support_match': True}}


def ledger(versions=EXPECTED):
    return {'protocol_version': 3, 'phase': 'ledger_locked', 'count': len(versions),
            'overflow': False, 'invalid': False, 'migrations': list(versions)}


def frame(value):
    return json.dumps(value, separators=(',', ':')).encode() + b'\n'


class Transcript:
    """Strict boundary double; only predefined transport operations are permitted."""
    def __init__(self, cat=None, rows=None):
        self.frames = [frame(catalog() if cat is None else cat), frame(ledger() if rows is None else rows)]
        self.events = []
        self.reads = 0
        self.closed = False
        self.aborted = False
        self.fail_close = False
        self.fail_send = False

    def send(self, data):
        if self.fail_send:
            raise OSError('sensitive server error')
        if not self.events:
            assert data == b'BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;\nLOCK TABLE ONLY public.schema_migrations IN SHARE ROW EXCLUSIVE MODE;\n'
        elif data == probe.LEDGER_SQL:
            assert self.reads == 1, 'ledger bytes arrived before catalog frame was consumed'
        else:
            assert data in (probe.CATALOG_SQL, probe.FINISH_SQL, probe.ROLLBACK_SQL), 'unknown SQL'
        self.events.append(('send', data))

    def read_frame(self, maximum, deadline):
        assert maximum == 524288
        assert deadline > 0
        self.events.append(('read', self.reads))
        data = self.frames[self.reads]
        self.reads += 1
        return data

    def close(self):
        self.events.append(('close', None))
        if self.fail_close:
            raise OSError('sensitive exit failure')
        self.closed = True

    def abort(self):
        self.events.append(('abort', None))
        self.aborted = True

    def ledger_sent(self):
        return ('send', probe.LEDGER_SQL) in self.events


class ProbeTests(unittest.TestCase):
    def assert_rejected(self, transport):
        with self.assertRaises(probe.ProbeUnavailable) as caught:
            probe.observe_catalog_ledger(transport, EXPECTED)
        self.assertNotIn('sensitive', str(caught.exception))
        self.assertTrue(transport.aborted)

    def test_no_ledger_bytes_before_catalog_acceptance(self):
        t = Transcript()
        result = probe.observe_catalog_ledger(t, EXPECTED)
        self.assertEqual(result, {'protocol_version': 3, 'scope': 'disposable_schema_ledger',
                                 'ledger_matches': True, 'schema_attested': False,
                                 'production_ready': False, 'deployment_authorized': False})
        self.assertEqual([kind for kind, _ in t.events], ['send', 'send', 'read', 'send', 'read', 'send', 'close'])
        self.assertTrue(t.closed)

    def test_lock_is_before_first_select(self):
        t = Transcript()
        probe.observe_catalog_ledger(t, EXPECTED)
        self.assertIn(b'SHARE ROW EXCLUSIVE', t.events[0][1])
        self.assertNotIn(b'SELECT', t.events[0][1])
        self.assertEqual(t.events[1], ('send', probe.CATALOG_SQL))

    def test_invalid_catalog_aborts_without_ledger(self):
        for path, value in [('kind', 'v'), ('kind', 'f'), ('kind', 'p'), ('rls', True),
                            ('force_rls', True), ('heap_builtin', False), ('has_inheritance', True)]:
            with self.subTest(path=path, value=value):
                cat = catalog(); cat['relation'][path] = value
                t = Transcript(cat); self.assert_rejected(t); self.assertFalse(t.ledger_sent())

    def test_each_field_mutation(self):
        def walk(obj, path=()):
            if isinstance(obj, dict):
                for key, val in obj.items():
                    yield path, key
                    yield from walk(val, path + (key,))
            elif isinstance(obj, list):
                for num, val in enumerate(obj):
                    yield from walk(val, path + (num,))
        for path, key in walk(catalog()):
            for mutation in ('missing', 'null', 'wrong_type', 'wrong_value'):
                with self.subTest(path=path + (key,), mutation=mutation):
                    cat = catalog(); obj = cat
                    for part in path: obj = obj[part]
                    old = obj[key]
                    if mutation == 'missing': del obj[key]
                    elif mutation == 'null':
                        if old is None: continue
                        obj[key] = None
                    elif mutation == 'wrong_type': obj[key] = []
                    elif type(old) is bool: obj[key] = not old
                    elif old is None: obj[key] = 'not-null'
                    elif type(old) is int: obj[key] = -1
                    elif type(old) is str: obj[key] = 'invalid'
                    else: obj[key] = {}
                    t = Transcript(cat); self.assert_rejected(t); self.assertFalse(t.ledger_sent())
        for path in [(), ('identity',), ('rights',), ('relation',), ('indexes',), ('builtins',), ('columns', 0)]:
            cat = catalog(); obj = cat
            for part in path: obj = obj[part]
            obj['unexpected'] = False
            t = Transcript(cat); self.assert_rejected(t); self.assertFalse(t.ledger_sent())

    def test_public_column_maintain_privileges(self):
        for key in ('other_maintain', 'relation_write', 'column_write', 'database_owner', 'schema_owner', 'relation_owner'):
            cat = catalog(); cat['rights'][key] = True
            t = Transcript(cat); self.assert_rejected(t); self.assertFalse(t.ledger_sent())

    def test_no_reconnect_or_commit(self):
        t = Transcript(); probe.observe_catalog_ledger(t, EXPECTED)
        self.assertEqual(sum(data.startswith(b'BEGIN') for kind, data in t.events if kind == 'send'), 1)
        self.assertFalse(any(b'COMMIT' in data for kind, data in t.events if kind == 'send'))

    def test_valid_ledger_requires_rollback_and_exit(self):
        t = Transcript(); t.fail_close = True
        self.assert_rejected(t)
        self.assertIn(('send', probe.FINISH_SQL), t.events)
        self.assertFalse(t.closed)

    def test_wrong_ledger_has_no_success(self):
        variants = [ledger(()), ledger(('003_extra',)), ledger(('001_initial', '001_initial')),
                    ledger(tuple(reversed(EXPECTED)))]
        for key, value in [('count', True), ('overflow', True), ('invalid', True),
                           ('migrations', None), ('count', 257), ('protocol_version', 2), ('extra', 0)]:
            obj = ledger(); obj[key] = value; variants.append(obj)
        for rows in variants:
            with self.subTest(rows=rows):
                t = Transcript(rows=rows); self.assert_rejected(t)
                self.assertIn(('send', probe.ROLLBACK_SQL), t.events)

    def test_inventory_rejected_before_any_sql(self):
        for expected in [(), ['001_initial'], ('001_initial',) * 2, ('001_UPPER',), ('001_a;SELECT',),
                         ('001_' + 'a' * 121,), tuple(f'{i:03}_x' for i in range(257))]:
            with self.subTest(expected=str(expected)[:40]):
                t = Transcript()
                with self.assertRaises(probe.ProbeUnavailable): probe.observe_catalog_ledger(t, expected)
                self.assertEqual(t.events, [])

    def test_every_stream_bound(self):
        good = frame(catalog())
        malformed = [b'', b'{}', good + b'{}\n', good[:-1], b'\xff\n', b'[' * 9 + b']' * 9 + b'\n',
                     good.replace(b'"protocol_version":3', b'"protocol_version":3,"protocol_version":3'),
                     good.replace(b'170000', b'1.7e5'), good.replace(b'170000', b'170000.0'),
                     good.replace(b'170000', b'99999999999'), good.replace(b'170000', b'NaN'),
                     good.replace(b'catalog_locked', b'c' * 129), b' ' * 524289 + good,
                     b'"' + b'\\' * 524288 + b'\n', b'{"x":' * 9 + b'0' + b'}' * 9 + b'\n']
        for data in malformed:
            with self.subTest(data=data[:40]):
                t = Transcript(); t.frames[0] = data
                self.assert_rejected(t); self.assertFalse(t.ledger_sent())
        t = Transcript(); t.frames[0] = b' ' * (524288 - len(good)) + good
        self.assertFalse(probe.observe_catalog_ledger(t, EXPECTED)['production_ready'])

    def test_deadline_aborts_without_ledger(self):
        t = Transcript()
        with patch.object(probe.time, 'monotonic', side_effect=[0, 0, 0, 13]):
            with self.assertRaises(probe.ProbeTimedOut): probe.observe_catalog_ledger(t, EXPECTED)
        self.assertFalse(t.ledger_sent()); self.assertTrue(t.aborted)

    def test_send_failure_redacts_and_aborts(self):
        t = Transcript(); t.fail_send = True
        self.assert_rejected(t)

    def test_catalog_oid_version_inventory_boundaries(self):
        for oid in (1, 4294967295):
            for version in (170000, 179999):
                cat = catalog(); cat['relation']['oid'] = oid; cat['identity']['server_version_num'] = version
                self.assertIsNone(probe.validate_catalog(cat))
        for section, key, values in [('relation', 'oid', (0, 4294967296, True, 1.0)),
                                     ('identity', 'server_version_num', (169999, 180000, True)),
                                     ('indexes', 'support_inventory_count', (1, 27, 29, 33, True))]:
            for value in values:
                cat = catalog(); cat[section][key] = value
                with self.assertRaises(probe.ProbeUnavailable): probe.validate_catalog(cat)

class AdditionalBoundsTests(unittest.TestCase):
    def test_maximum_inventory_and_no_manifest_sql_interpolation(self):
        versions = tuple(f'{i:03}_entry' for i in range(256))
        t = Transcript(rows=ledger(versions))
        result = probe.observe_catalog_ledger(t, versions)
        self.assertTrue(result['ledger_matches'])
        for kind, data in t.events:
            if kind == 'send':
                self.assertNotIn(b'255_entry', data)

    def test_stream_more_than_64_members_and_nested_strings(self):
        for data in [(json.dumps({f'x{i}': i for i in range(65)}) + '\n').encode(),
                     b'{"x":"' + b'\\u0061' * 129 + b'"}\n',
                     b'{"x":"\\ud800"}\n',
                     b'{"x":true,"x":false}\n',
                     b'{"x":0001}\n', b'{"x":Infinity}\n', b'{"x":-1}\n']:
            t = Transcript(); t.frames[0] = data
            with self.assertRaises(probe.ProbeUnavailable): probe.observe_catalog_ledger(t, EXPECTED)
            self.assertFalse(t.ledger_sent())

    def test_short_write_is_failure(self):
        t = Transcript()
        t.send = lambda data: 1
        with self.assertRaises(probe.ProbeUnavailable): probe.observe_catalog_ledger(t, EXPECTED)
        self.assertTrue(t.aborted)

    def test_timeout_from_transport_preserves_timeout_class(self):
        t = Transcript()
        def timeout(*args): raise TimeoutError('sensitive timeout')
        t.read_frame = timeout
        with self.assertRaises(probe.ProbeTimedOut): probe.observe_catalog_ledger(t, EXPECTED)
        self.assertFalse(t.ledger_sent()); self.assertTrue(t.aborted)


if __name__ == '__main__':
    unittest.main()
