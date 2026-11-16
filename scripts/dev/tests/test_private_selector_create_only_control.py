"""Owned lifecycle controls only: no Docker/socket/SQL/provider calls."""
import copy
import json
import unittest
import private_selector_create_only_control as m


IDENTIFIER = '0123456789abcdef' * 4


def command(role):
    return {'role': role, 'owned_name': 'autodata-selector-fixture-' + 'a' * 32 + '-' + role + '-lifecycle',
            'payload': {'Image': 'authored-image', 'Cmd': ['authored'], 'Entrypoint': ['python'],
                        'User': '', 'WorkingDir': '/app', 'Env': ['PATH=/usr/bin'],
                        'HostConfig': {'ReadonlyRootfs': True, 'RestartPolicy': {'Name': 'no'},
                                       'Mounts': [{'Source': '/authored/source', 'Target': '/app', 'ReadOnly': True}]}}}


class Backend:
    def __init__(self):
        self.events = []; self.response = {'Id': IDENTIFIER}; self.change = None
        self.proof_changed = False; self.inspections = 0; self.cleanup = True
    def boundary(self, command): self.command = command; self.events.append('boundary')
    def absent_name(self, name): return True
    def create(self, command): self.events.append('create'); return json.dumps(self.response).encode()
    def record(self, name, value): self.events.append(name)
    def inspect(self, identifier):
        self.inspections += 1; self.events.append('inspect')
        p = self.command['payload']
        raw = {'Id': identifier, 'Name': '/' + self.command['owned_name'], 'Image': p['Image'],
               'Config': {k: p[k] for k in ('Cmd', 'Entrypoint', 'User', 'WorkingDir', 'Env')},
               'HostConfig': {**p['HostConfig'], 'RestartPolicy': {'Name': 'no', 'MaximumRetryCount': 0}},
               'Mounts': [{'Source': '/authored/source', 'Destination': '/app', 'RW': False}],
               'State': {'Status': 'created', 'Running': False, 'Restarting': False, 'Pid': 0,
                         'StartedAt': '0001-01-01T00:00:00Z'}, 'RestartCount': 0}
        raw = copy.deepcopy(raw)
        if self.change: self.change(raw)
        if self.proof_changed and self.inspections == 2: raw['RestartCount'] = 1
        return raw
    def remove(self, identifier): self.events.append('remove:' + identifier)
    def absent(self, identifier): return self.cleanup


class Tests(unittest.TestCase):
    def test_all_sixteen_hex_digits_are_valid_and_response_is_durable_before_validation(self):
        b = Backend(); result = m.run({'commands': [command('bootstrap'), command('worker')]}, b)
        self.assertEqual(result['status'], 'CREATE_ONLY_PASS_REMOVED_ABSENT')
        self.assertLess(b.events.index('create-response-bootstrap'), b.events.index('create-returned-id-bootstrap'))
        self.assertLess(b.events.index('create-returned-id-bootstrap'), b.events.index('inspect'))
        self.assertEqual(b.events.count('remove:' + IDENTIFIER), 2)

    def test_invalid_or_missing_id_preserves_response_without_inspect_or_cleanup(self):
        for response in ({}, {'Id': 'not-hex'}, {'Id': 'G' * 64}):
            b = Backend(); b.response = response
            with self.assertRaises(m.c.Refused):m.run({'commands': [command('bootstrap'), command('worker')]}, b)
            self.assertIn('create-response-bootstrap', b.events)
            self.assertNotIn('inspect', b.events)
            self.assertFalse(any(x.startswith('remove:') for x in b.events))

    def test_unexpected_environment_never_removes_unknown_identity(self):
        b = Backend(); b.change = lambda raw: raw['Config']['Env'].append('AWS_SECRET_ACCESS_KEY=sentinel')
        with self.assertRaises(m.c.Refused):m.run({'commands': [command('bootstrap'), command('worker')]}, b)
        self.assertIn('create-full-identity-bootstrap', b.events)
        self.assertFalse(any(x.startswith('remove:') for x in b.events))

    def test_running_or_previously_started_container_is_never_removed(self):
        for key, value in [('Running', True), ('Pid', 7), ('StartedAt', 'authored-started')]:
            b = Backend(); b.change = lambda raw: raw['State'].update({key: value})
            with self.assertRaises(m.c.Refused):m.run({'commands': [command('bootstrap'), command('worker')]}, b)
            self.assertFalse(any(x.startswith('remove:') for x in b.events))

    def test_second_inspection_change_blocks_removal(self):
        b = Backend(); b.proof_changed = True
        with self.assertRaises(m.c.Refused):m.run({'commands': [command('bootstrap'), command('worker')]}, b)
        self.assertFalse(any(x.startswith('remove:') for x in b.events))

    def test_unknown_absence_never_claims_success_or_creates_worker(self):
        b = Backend(); b.cleanup = False
        with self.assertRaises(m.c.Refused):m.run({'commands': [command('bootstrap'), command('worker')]}, b)
        self.assertEqual(b.events.count('create'), 1)
        self.assertNotIn('create-only-result', b.events)


if __name__ == '__main__': unittest.main()
