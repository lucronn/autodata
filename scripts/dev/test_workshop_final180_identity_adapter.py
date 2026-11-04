"""Synthetic bytes only: restricted identity profile, never fixture evidence."""
import dataclasses
import json
import unittest

from scripts.dev import workshop_final180_identity_adapter as a

CANDIDATE = '4d82e413e04fb2401ac7bc28dc828375ac662180'
INVENTORY = 'c4e9293875d22e04469c6a3fb4cdab27889328d6519243cee3862f9ecf490b39'
PACKAGE = 'github.com/lucronn/autodata/apps/api-go'
ROOT = 'TestPostgresAuthSessionsIntegration'
IDS = tuple(ROOT + '/' + s for s in (
    'ConcurrentCustomerProvisionAndRotation', 'SharedSessionRevocation',
    'ExpiryAndPersistedSecrecy', 'FirebaseExchangeAndUserRevocation',
    'FirebaseStartupRequiresMigratedPostgres'))
REFS = ('r5-access-go-events.jsonl', 'r5-access-go-stderr.log')


def event(action, test=None, **fields):
    row = dict(Time='2026-11-04T00:00:00Z', Action=action, Package=PACKAGE)
    if test is not None:
        row['Test'] = test
    return dict(row, **fields)


def clean():
    return [event('start'), event('run', ROOT)] + [
        row for name in IDS for row in (event('run', name), event('pass', name))
    ] + [event('pass', ROOT), event('pass')]


def raw(rows):
    return b'\n'.join(json.dumps(row, separators=(',', ':')).encode() for row in rows) + b'\n'


class AdapterTests(unittest.TestCase):
    def context(self):
        return a.IdentityContext(CANDIDATE, INVENTORY, 'a' * 64)

    def receipt(self, **changes):
        return dataclasses.replace(a.SimulatedExit(0, False, False, False, True), **changes)

    def translate(self, rows=None, **kw):
        return a.translate_identity(raw(clean() if rows is None else rows), b'opaque\xff',
                                    kw.get('receipt', self.receipt()), self.context())

    def error(self, code, fn, *args):
        with self.assertRaises(a.AdapterError) as caught:
            fn(*args)
        self.assertEqual(str(caught.exception), code)

    def test_clean_order_and_no_authority(self):
        d = self.translate()
        self.assertEqual(d.status, 'consistent')
        self.assertEqual(d.failures, ())
        self.assertEqual(tuple(r.logical_id for r in d.observations), IDS)
        self.assertEqual(tuple(r.status for r in d.observations), ('passed',) * 5)
        self.assertTrue(all(r.family == 'identity' and r.raw_refs == REFS for r in d.observations))
        self.assertEqual(d.accepted_case_credit, 0)
        self.assertIs(d.profiles_enabled, False)
        self.assertEqual(d.enabled_tiers, ())
        self.assertEqual(len(d.authority), 9)
        self.assertTrue(all(v is False for _, v in d.authority))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            d.status = 'passed'

    def test_child_missing_duplicate_failed_skipped_individually(self):
        for i, name in enumerate(IDS):
            for change, expected, code in (
                ('missing', 'failed', 'child_lifecycle:'),
                ('duplicate_pass', 'failed', 'child_lifecycle:'),
                ('duplicate_run', 'failed', 'child_lifecycle:'),
                ('fail', 'failed', 'child_failed:'), ('skip', 'skipped', 'child_skipped:')):
                with self.subTest(i=i, change=change):
                    rows = clean()
                    at = 3 + 2 * i
                    if change == 'missing':
                        del rows[at]
                    elif change.startswith('duplicate'):
                        rows.insert(at, event('pass' if change.endswith('pass') else 'run', name))
                    else:
                        rows[at] = event(change, name)
                    d = self.translate(rows)
                    self.assertEqual(d.status, 'inconsistent')
                    self.assertEqual(d.observations[i].status, expected)
                    self.assertIn(code + str(i), d.failures)
                    self.assertTrue(all(r.status == 'passed' for j, r in enumerate(d.observations) if j != i))

    def test_support_failures_poison_all_rows(self):
        variants = []
        for index in (0, 1, 12, 13):
            rows = clean(); del rows[index]; variants.append(rows)
        for index in (12, 13):
            rows = clean(); rows[index]['Action'] = 'fail'; variants.append(rows)
        rows = clean(); rows[4]['Package'] = 'foreign'; variants.append(rows)
        rows = clean(); rows.insert(4, event('run', ROOT + '/foreign/nested')); variants.append(rows)
        for rows in variants:
            with self.subTest(rows=rows):
                d = self.translate(rows)
                self.assertEqual(d.status, 'inconsistent')
                self.assertEqual(tuple(r.status for r in d.observations), ('failed',) * 5)

    def test_child_order_and_output_intervals(self):
        rows = clean(); rows[2], rows[3] = rows[3], rows[2]
        self.assertIn('child_lifecycle:0', self.translate(rows).failures)
        rows = clean(); rows.insert(2, event('output', IDS[0], Output='passed=true secret'))
        self.assertIn('child_lifecycle:0', self.translate(rows).failures)
        rows = clean(); rows.insert(4, event('output', IDS[0], Output='too late'))
        self.assertIn('child_lifecycle:0', self.translate(rows).failures)
        rows = clean(); rows[3:3] = [event('output', IDS[0], Output='passed=true')] * 2
        self.assertEqual(self.translate(rows).status, 'consistent')
        rows = clean(); rows[2:12] = list(reversed([rows[i:i+2] for i in range(2,12,2)]))
        rows = rows[:2] + [r for pair in rows[2:7] for r in pair] + rows[7:]
        self.assertEqual(tuple(r.logical_id for r in self.translate(rows).observations), IDS)

    def test_skip_precedence_and_lifecycle(self):
        rows = [event('start'), event('run', ROOT), event('skip', ROOT), event('pass')]
        d = self.translate(rows)
        self.assertEqual(tuple(r.status for r in d.observations), ('skipped',) * 5)
        self.assertIn('child_lifecycle:0', d.failures)
        rows[-1]['Action'] = 'fail'
        self.assertEqual(tuple(r.status for r in self.translate(rows).observations), ('failed',) * 5)
        rows = clean(); rows[3]['Action'] = 'skip'; rows.insert(3, event('skip', IDS[0]))
        self.assertEqual(self.translate(rows).observations[0].status, 'failed')

    def test_receipt_precedence(self):
        for fields, code in ((dict(exit_code=2), 'simulated_nonzero'),
                             (dict(timed_out=True), 'simulated_timeout'),
                             (dict(ownership_lost=True), 'ownership_lost'),
                             (dict(cleanup_complete=False), 'cleanup_incomplete')):
            d = self.translate(receipt=self.receipt(**fields))
            self.assertEqual(tuple(r.status for r in d.observations), ('failed',) * 5)
            self.assertIn(code, d.failures)
        d = self.translate(receipt=self.receipt(interrupted=True, timed_out=True))
        self.assertEqual(d.status, 'interrupted')
        self.assertEqual(tuple(r.status for r in d.observations), ('unavailable',) * 5)
        self.assertEqual(d.failures, ('simulated_timeout', 'simulated_interrupted'))

    def test_context_receipt_and_outer_types(self):
        for context in (None, dataclasses.replace(self.context(), candidate_sha='b'*40),
                        dataclasses.replace(self.context(), inventory_sha256='b'*64),
                        dataclasses.replace(self.context(), source_manifest_sha256='A'*64)):
            self.error('context_invalid', a.translate_identity, b'', b'', self.receipt(), context)
        for fields in (dict(exit_code=True), dict(exit_code=256), dict(exit_code=None),
                       dict(timed_out=1), dict(cleanup_complete=0)):
            self.error('receipt_invalid', a.translate_identity, b'', b'', self.receipt(**fields), self.context())
        self.error('input_type', a.parse_identity_events, bytearray())
        self.error('stderr_type', a.translate_identity, b'', '', self.receipt(), self.context())
        self.error('stderr_size', a.translate_identity, b'', b'x'*(1048576+1), self.receipt(), self.context())
        self.error('events_size', a.parse_identity_events, b'x'*(67108864+1))

    def test_parser_rejections_and_no_prefix(self):
        cases = [(b'', 'events_count'), (b'\n', 'line_delimiter'),
                 (raw(clean())+b'\n', 'line_delimiter'), (raw(clean()).replace(b'\n', b'\r\n'), 'line_delimiter'),
                 (b'\xef\xbb\xbf{}', 'json_invalid'), (b'\xff', 'json_invalid'),
                 (b'[]', 'event_type'), (b'{', 'json_invalid'),
                 (b'{"Time":"x","Time":"x"}', 'json_duplicate_key'),
                 (b'{"Elapsed":NaN}', 'json_nonfinite'),
                 (b'['*33+b'0'+b']'*33, 'json_depth'),
                 (b'{"Time":"\\ud800"}', 'json_string'),
                 (b'"'+b'x'*65537+b'"', 'json_string'),
                 (b'x'*1048577, 'line_size')]
        for fields, code in ((dict(Action='pause'), 'unsupported_go_action'),
                             (dict(Action='bench'), 'unsupported_go_action'),
                             (dict(Action='cont'), 'unsupported_go_action'),
                             (dict(Elapsed=True), 'event_type'), (dict(Elapsed=-1), 'event_type'),
                             (dict(Elapsed=86401), 'event_type'), (dict(Output='x'), 'event_type'),
                             (dict(Test=None), 'event_type'), (dict(Time=''), 'event_type'),
                             (dict(Time='x'*129), 'event_type'), (dict(Package='x'*257), 'event_type'),
                             (dict(passed=True), 'event_keys'), (dict(FailedBuild='x'), 'event_type')):
            cases.append((raw([dict(event('start'), **fields)]), code))
        for data, code in cases:
            with self.subTest(code=code, data=data[:100]):
                self.error(code, a.parse_identity_events, data)
                d = a.translate_identity(data, b'', self.receipt(interrupted=True), self.context())
                self.assertEqual(d.status, 'unavailable')
                self.assertEqual(tuple(r.status for r in d.observations), ('unavailable',)*5)
                self.assertEqual(d.failures, (code, 'simulated_interrupted'))
        d = a.translate_identity(raw(clean()) + raw([event('pause')]), b'', self.receipt(), self.context())
        self.assertEqual(d.status, 'unavailable')

    def test_valid_optional_fields_and_limits(self):
        rows = clean(); rows.insert(3, event('output', IDS[0], Output='x'*65536, Elapsed=86400))
        rows[0]['Time'] = 'x'*128
        parsed = a.parse_identity_events(raw(rows).rstrip(b'\n'))
        self.assertEqual(len(parsed), 15)
        self.assertEqual(parsed[3].output, 'x'*65536)
        self.assertEqual(self.translate(rows).status, 'consistent')
        data = raw([event('output', Output='')])*65536
        self.assertEqual(len(a.parse_identity_events(data)), 65536)
        self.error('events_count', a.parse_identity_events, data+raw([event('start')]))
        # JSON whitespace can fill a line without creating oversized decoded strings.
        line = raw([event('start')]).rstrip(b'\n')
        self.assertEqual(len(a.parse_identity_events(line+b' '*(1048576-len(line)))), 1)
        self.error('line_size', a.parse_identity_events, line+b' '*(1048577-len(line)))
        self.assertEqual(self.translate().stderr_sha256, __import__('hashlib').sha256(b'opaque\xff').hexdigest())

    def test_extreme_elapsed_is_stable_error(self):
        self.error('event_type', a.parse_identity_events, raw([event('start', Elapsed=10**400)]))

    def test_exact_outer_and_decoded_boundaries(self):
        line = raw([event('start')]).rstrip(b'\n')
        at_limit = (line + b' ' * (1048575-len(line)) + b'\n') * 64
        self.assertEqual(len(at_limit), 67108864)
        self.assertEqual(len(a.parse_identity_events(at_limit)), 64)
        d = a.translate_identity(raw(clean()), b'x'*1048576, self.receipt(), self.context())
        self.assertEqual(d.status, 'consistent')
        for field, n in (('Test', 256), ('Package', 256), ('Time', 128)):
            self.assertEqual(len(a.parse_identity_events(raw([event('output', Output='', **{field:'x'*n})]))), 1)
            self.error('event_type', a.parse_identity_events, raw([event('output', Output='', **{field:'x'*(n+1)})]))
        self.assertEqual(len(a.parse_identity_events(raw([event('fail', FailedBuild='x'*1024)]))), 1)
        self.error('event_type', a.parse_identity_events, raw([event('fail', FailedBuild='x'*1025)]))
        self.assertEqual(len(a.parse_identity_events(raw([event('output', Output='é'*32768)]))), 1)
        self.error('json_string', a.parse_identity_events, raw([event('output', Output='é'*32769)]))
        for n, code in ((31, 'event_keys'), (32, 'json_depth')):
            data = b'{"Time":"x","Action":"start","Package":"x","unknown":' + b'['*n+b'0'+b']'*n+b'}'
            self.error(code, a.parse_identity_events, data)

    def test_parent_only_interleaving_and_static_failure_codes(self):
        d = self.translate([event('start'), event('run', ROOT), event('pass', ROOT), event('pass')])
        self.assertEqual(tuple(r.status for r in d.observations), ('failed',)*5)
        rows = [event('start'), event('run', ROOT)]
        rows += [event('run', name) for name in IDS]
        rows += [event('output', name, Output='secret/path passed=true') for name in IDS]
        rows += [event('pass', name) for name in reversed(IDS)]
        rows += [event('pass', ROOT), event('pass')]
        self.assertEqual(self.translate(rows).status, 'consistent')
        rows.insert(2, event('run', ROOT+'/secret/path'))
        d = self.translate(rows)
        self.assertEqual(d.failures, ('unknown_test',))
        self.assertNotIn('secret', str(d))


if __name__ == '__main__':
    unittest.main()
