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

    def test_support_duplicates_and_child_after_root(self):
        for index in (0,1,12,13):
            rows = clean(); rows.insert(index,dict(rows[index]))
            d = self.translate(rows)
            self.assertEqual(tuple(r.status for r in d.observations),('failed',)*5)
        rows = clean(); child = rows[2:4]; del rows[2:4]; rows[-1:-1] = child
        d = self.translate(rows)
        self.assertEqual(d.observations[0].status,'failed')
        self.assertIn('child_lifecycle:0',d.failures)
        for index, code in ((12,'root_lifecycle'),(13,'package_lifecycle')):
            rows = clean(); rows.insert(index+1,event('output',ROOT if index==12 else None,Output='late'))
            self.assertIn(code,self.translate(rows).failures)


class ReplayTests(unittest.TestCase):
    error = AdapterTests.error
    context = AdapterTests.context
    receipt = AdapterTests.receipt
    translate = AdapterTests.translate

    def frame(self, t, kind, data=b'', code=None):
        return a.FakeFrame(t, kind, data, code)

    def replay(self, *frames):
        return a.replay_identity_fake(tuple(frames))

    def test_normal_exit_and_deadline_equality(self):
        for code in (-255, 0, 255):
            r = self.replay(self.frame(179999999999, 'exit', code=code))
            self.assertEqual(r.result, a.SimulatedExit(code, False, False, False, True))
            self.assertEqual(r.decisions, ())
        r = self.replay(self.frame(180000000000, 'exit', code=0))
        self.assertEqual(r.result, a.SimulatedExit(0, True, False, False, True))
        self.assertEqual(r.decisions, ((180000000000, 'timeout'), (180000000000, 'term'),
                                       (180000000000, 'cleanup_complete')))
        r = self.replay()
        self.assertEqual(r.result, a.SimulatedExit(None, True, False, False, False))
        self.assertEqual(r.decisions, ((180000000000, 'timeout'), (180000000000, 'term'),
                                       (185000000000, 'kill'), (190000000000, 'leftover')))

    def test_cleanup_boundaries_and_acknowledgements(self):
        cancel = self.frame(10000000000, 'cancel')
        for kind, time, last in (('exit', 10000000000, 'term'),
                                 ('term_exit', 10000000000, 'term'),
                                 ('term_exit', 14999999999, 'term'),
                                 ('kill_exit', 15000000000, 'kill'),
                                 ('kill_exit', 19999999999, 'kill')):
            with self.subTest(kind=kind, time=time):
                r = self.replay(cancel, self.frame(time, kind, code=-2))
                self.assertEqual(r.result, a.SimulatedExit(-2, False, True, False, True))
                self.assertEqual(r.decisions[-2][1], last)
                self.assertEqual(r.decisions[-1], (time, 'cleanup_complete'))
        for kind, time in (('term_exit', 9999999999), ('term_exit', 15000000000),
                           ('kill_exit', 14999999999), ('kill_exit', 20000000000),
                           ('exit', 10000000001)):
            frames = tuple(sorted((cancel, self.frame(time, kind, code=0)), key=lambda f:f.at_ns))
            self.error('fake_cleanup_sequence', a.replay_identity_fake, frames)
        r = self.replay(cancel, self.frame(15000000000, 'cancel'),
                        self.frame(15000000000, 'kill_exit', code=0))
        self.assertEqual(tuple(k for _,k in r.decisions), ('cancel','term','kill','cleanup_complete'))
        r = self.replay(cancel, self.frame(19999999999, 'cancel'))
        self.assertEqual(r.decisions[-1], (20000000000, 'leftover'))
        self.assertEqual(len(r.decisions), 4)

    def test_ownership_loss_disarms_actions(self):
        r = self.replay(self.frame(0, 'identity_lost'))
        self.assertEqual(r.result, a.SimulatedExit(None, False, False, True, False))
        self.assertEqual(r.decisions, ((0,'ownership_lost'),))
        for time in (10000000000, 15000000000, 20000000000):
            r = self.replay(self.frame(10000000000, 'cancel'), self.frame(time, 'identity_lost')) if time > 10000000000 else self.replay(self.frame(time, 'identity_lost'))
            self.assertEqual(r.decisions[-1], (time,'ownership_lost'))
            self.assertFalse(r.result.cleanup_complete)
            self.assertNotIn((time,'kill'), r.decisions)
        for time in (180000000000,185000000000,190000000000):
            r = self.replay(self.frame(time,'identity_lost'))
            self.assertEqual(r.decisions[-1], (time,'ownership_lost'))
            self.assertNotIn((time,'term'), r.decisions)
            self.assertNotIn((time,'kill'), r.decisions)
        for pair in ((self.frame(11000000000,'identity_lost'),self.frame(11000000000,'term_exit',code=0)),
                     (self.frame(11000000000,'term_exit',code=0),self.frame(11000000000,'identity_lost'))):
            self.error('fake_cleanup_sequence', a.replay_identity_fake,
                       (self.frame(10000000000,'cancel'),)+pair)

    def test_every_frame_pair_tie_is_independent_of_tuple_order(self):
        import itertools
        kinds = ('identity_lost','cancel','exit','term_exit','kill_exit','stdout','stderr')
        def make(kind, t):
            return self.frame(t, kind, b'x' if kind in ('stdout','stderr') else b'',
                              0 if kind in ('exit','term_exit','kill_exit') else None)
        def outcome(frames):
            try:
                return self.replay(*frames)
            except a.AdapterError as exc:
                return str(exc)
        for time, prefix in ((10000000000,()),
                             (10000000000,(self.frame(9000000000,'cancel'),)),
                             (14000000000,(self.frame(9000000000,'cancel'),)),
                             (19000000000,(self.frame(9000000000,'cancel'),)),
                             (180000000000,()), (185000000000,()), (190000000000,())):
            for one,two in itertools.combinations(kinds,2):
                with self.subTest(time=time, prefix=prefix, one=one, two=two):
                    self.assertEqual(outcome(prefix+(make(one,time),make(two,time))),
                                     outcome(prefix+(make(two,time),make(one,time))))
        for pair in ((make('cancel',10000000000),make('term_exit',10000000000)),
                     (make('term_exit',10000000000),make('cancel',10000000000))):
            r = self.replay(*pair)
            self.assertTrue(r.result.interrupted)
            self.assertTrue(r.result.cleanup_complete)
        r = self.replay(make('cancel',180000000000),make('exit',180000000000))
        self.assertFalse(r.result.timed_out)
        self.assertTrue(r.result.interrupted)

    def test_post_terminal_frames_rejected(self):
        for kind in ('stdout','stderr','exit','cancel','identity_lost','term_exit','kill_exit'):
            extra = self.frame(1,kind,code=0 if kind in ('exit','term_exit','kill_exit') else None)
            self.error('fake_after_exit', a.replay_identity_fake,
                       (self.frame(0,'exit',code=0),extra))
            self.error('fake_cleanup_sequence', a.replay_identity_fake,
                       (self.frame(0,'identity_lost'),extra))
            self.error('fake_cleanup_sequence', a.replay_identity_fake,
                       (self.frame(0,'cancel'),self.frame(0,'term_exit',code=0),extra))
        for kind in ('stdout','stderr'):
            self.error('fake_cleanup_sequence', a.replay_identity_fake,
                       (self.frame(0,'cancel'),self.frame(1,kind)))
            self.error('fake_after_exit', a.replay_identity_fake,
                       (self.frame(0,kind),self.frame(0,'exit',code=0)))
        self.error('fake_cleanup_sequence', a.replay_identity_fake,
                   (self.frame(190000000000,'stdout'),))

    def test_complete_shape_validation_precedes_replay(self):
        self.error('fake_frames', a.replay_identity_fake, [])
        self.error('fake_frames', a.replay_identity_fake, (self.frame(0,'stdout'),)*65537)
        self.error('fake_frame_type', a.replay_identity_fake, (None,))
        for kind in ('exit','term_exit','kill_exit'):
            for code in (None,True,False,-256,256,0.0):
                self.error('fake_code', a.replay_identity_fake, (self.frame(0,kind,code=code),))
        for kind in ('stdout','stderr','cancel','identity_lost'):
            for code in (0,True,False):
                self.error('fake_code', a.replay_identity_fake, (self.frame(0,kind,code=code),))
        for kind in ('stdout','exit'):
            self.error('fake_frame_type', a.replay_identity_fake,
                       (self.frame(0,kind,data=bytearray(),code=0 if kind=='exit' else None),))
        self.error('fake_frame_type', a.replay_identity_fake, (self.frame(0,'cancel',b'x'),))
        for time in (-1,190000000001,True,0.0):
            self.error('fake_time', a.replay_identity_fake, (self.frame(time,'cancel'),))
        self.error('fake_time', a.replay_identity_fake, (self.frame(1,'cancel'),self.frame(0,'cancel')))
        self.error('fake_kind', a.replay_identity_fake, (self.frame(0,'process'),))
        self.error('fake_kind', a.replay_identity_fake, (self.frame(0,[]),))
        self.error('fake_code', a.replay_identity_fake,
                   (self.frame(0,'exit',code=0),self.frame(1,'term_exit')))
        r = self.replay(*((self.frame(0,'stdout'),)*65535+(self.frame(1,'exit',code=0),)))
        self.assertEqual(r.result.exit_code, 0)

    def test_chunk_and_aggregate_byte_boundaries(self):
        chunk = b'x'*1048576
        r = self.replay(*((self.frame(0,'stdout',chunk),)*64 +
                          (self.frame(0,'stderr',chunk),self.frame(1,'exit',code=0))))
        self.assertEqual(len(r.stdout),67108864)
        self.assertEqual(len(r.stderr),1048576)
        self.error('fake_chunk_size', a.replay_identity_fake, (self.frame(0,'stdout',chunk+b'x'),))
        self.error('fake_stdout_size', a.replay_identity_fake,
                   (self.frame(0,'stdout',chunk),)*64+(self.frame(0,'stdout',b'x'),))
        self.error('fake_stderr_size', a.replay_identity_fake,
                   (self.frame(0,'stderr',chunk),self.frame(0,'stderr',b'x')))

    def test_fake_translation_never_erases_adverse_receipts(self):
        for terminal in ((self.frame(1,'exit',code=0),),
                         (self.frame(180000000000,'exit',code=0),),
                         (self.frame(1,'cancel'),self.frame(1,'term_exit',code=0)),
                         (self.frame(1,'identity_lost'),)):
            r = self.replay(self.frame(0,'stdout',raw(clean())),self.frame(0,'stderr',b'opaque'),*terminal)
            d = a.translate_identity(r.stdout,r.stderr,r.result,self.context())
            self.assertEqual(d.status, 'consistent' if terminal[0].kind=='exit' and terminal[0].at_ns==1
                             else 'interrupted' if terminal[0].kind=='cancel' else 'inconsistent')

    def test_serializer_canonical_and_rejects_authority_and_row_changes(self):
        d = self.translate()
        result = a.serialize_identity_diagnostic(d)
        obj = json.loads(result)
        self.assertEqual(result,(json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode())
        self.assertLessEqual(len(result),65536)
        self.assertEqual(set(obj), {'contract','observation_kind','candidate_sha','inventory_sha256',
                                  'source_manifest_sha256','events_sha256','stderr_sha256','status',
                                  'observations','failures','accepted_case_credit','profiles_enabled',
                                  'enabled_tiers','authority'})
        self.assertEqual(obj['profiles_enabled'],False)
        self.assertEqual(obj['enabled_tiers'],[])
        self.assertEqual(obj['accepted_case_credit'],0)
        self.assertEqual(tuple(r['logical_id'] for r in obj['observations']),IDS)
        self.assertEqual(obj['authority'],dict(d.authority))
        bad_rows = (d.observations[:4],d.observations+(d.observations[0],),
                    (d.observations[0],)*5,tuple(reversed(d.observations)),
                    (dataclasses.replace(d.observations[0],family='other'),)+d.observations[1:],
                    (dataclasses.replace(d.observations[0],raw_refs=('private/path',)),)+d.observations[1:])
        changes = [dict(observations=rows) for rows in bad_rows]
        changes += [dict(profiles_enabled=True),dict(profiles_enabled=0),dict(enabled_tiers=('x',)),
                    dict(enabled_tiers=[]),dict(accepted_case_credit=True),dict(accepted_case_credit=1),
                    dict(authority=d.authority+(('unknown',False),)),
                    dict(authority=(('fixture_verified',True),)+d.authority[1:]),
                    dict(authority=(('fixture_verified',0),)+d.authority[1:]),
                    dict(authority=tuple(reversed(d.authority))),dict(contract='other'),
                    dict(source_manifest_sha256='A'*64),dict(status='interrupted'),
                    dict(failures=('private/path',)),dict(failures=('root_failed','root_failed')),
                    dict(failures=('simulated_timeout',)),dict(observations=list(d.observations))]
        for change in changes:
            with self.subTest(change=change):
                self.error('diagnostic_invalid', a.serialize_identity_diagnostic,dataclasses.replace(d,**change))
        for bad in (None,{},result):
            self.error('diagnostic_invalid',a.serialize_identity_diagnostic,bad)

    def test_serializer_all_translation_statuses(self):
        for receipt in (self.receipt(),self.receipt(interrupted=True),self.receipt(timed_out=True),
                        self.receipt(ownership_lost=True,cleanup_complete=False,exit_code=None)):
            for rows in (clean(),[event('pause')],[event('start'),event('run',ROOT),event('skip',ROOT),event('pass')]):
                d = self.translate(rows,receipt=receipt)
                self.assertEqual(json.loads(a.serialize_identity_diagnostic(d))['status'],d.status)
        d = self.translate()
        self.error('diagnostic_invalid',a.serialize_identity_diagnostic,
                   dataclasses.replace(d,failures=('simulated_timeout','root_failed')))

    def test_maximal_fixed_failure_diagnostic_is_bounded(self):
        # All semantic codes together dominate any subset's encoded failure bytes.
        codes = ('package_mismatch','unknown_test','package_lifecycle','root_lifecycle',
                 *(f'child_lifecycle:{i}' for i in range(5)), 'root_failed','root_skipped',
                 'package_failed','package_skipped',*(f'child_failed:{i}' for i in range(5)),
                 *(f'child_skipped:{i}' for i in range(5)), 'simulated_nonzero',
                 'simulated_timeout','simulated_interrupted','ownership_lost','cleanup_incomplete')
        d = self.translate(receipt=self.receipt(interrupted=True))
        encoded = a.serialize_identity_diagnostic(dataclasses.replace(d,failures=codes))
        self.assertLess(len(encoded),65536)
        self.assertEqual(json.loads(encoded)['failures'],list(codes))
        self.error('diagnostic_invalid',a.serialize_identity_diagnostic,
                   dataclasses.replace(d,failures=('root_failed',)*65))

    def test_library_has_no_runtime_or_filesystem_adapter(self):
        import ast
        import pathlib
        tree = ast.parse(pathlib.Path(a.__file__).read_text())
        allowed = {'dataclasses','hashlib','json','math','re'}
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                self.assertTrue(all(n.name in allowed for n in node.names))
            elif isinstance(node,ast.ImportFrom):
                self.assertIn(node.module,allowed)
            elif isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
                self.assertNotIn(node.func.id,{'open','exec','eval','compile','__import__'})
        self.assertFalse(any(isinstance(node,ast.If) and isinstance(node.test,ast.Compare)
                             and isinstance(node.test.left,ast.Name) and node.test.left.id=='__name__'
                             for node in tree.body))


if __name__ == '__main__':
    unittest.main()
