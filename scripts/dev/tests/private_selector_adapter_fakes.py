"""Authored in-memory backend; no subprocess, network, filesystem or SQL calls."""
import copy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import private_selector_adapter_contract as c
import private_selector_image_fixture as f
import private_selector_runtime_adapter as r


def manifest(phase):
    value = {'phase': phase, 'pins': copy.deepcopy(c.PINS), 'run_id': '2' * 32,
             'artifacts': {name: '3' * 64 for name in c.ARTIFACTS[phase]},
             'home_cap': 128 * c.MIB, 'docker_cap': 64 * c.MIB, 'offloaded_cap': 64 * c.MIB,
             'execution_approved': True}
    if phase == 'runtime':
        value['candidate'] = {'id': 'a' * 64, 'image': c.IMAGE, 'source': c.SOURCE,
                              'config': 'd' * 64, 'mounts': 'e' * 64,
                              'hostconfig_by_status': {'created': 'f' * 64,
                                                       'running': '1' * 64, 'exited': '1' * 64}}
    return value


def state(expected, status):
    return {**{k: expected[k] for k in ('id', 'image', 'source', 'config', 'mounts')},
            'hostconfig': expected['hostconfig_by_status'][status], 'status': status,
            'running': status == 'running', 'restarting': False,
            'pid': 123 if status == 'running' else 0, 'restart_count': 0,
            'started_at': c.OLD_STARTED if expected['id'] == c.OLD else 'synthetic-stable-start'}


class Backend:
    def __init__(self, value):
        self.manifest = value; self.events = []; self.markers = {}; self.states = {}
        self.states[c.OLD] = state(c.OLD_IDENTITY, 'running')
        self.states[c.SECONDARY] = state(c.SECONDARY_IDENTITY, 'exited')
        if value['phase'] == 'runtime':
            self.states[value['candidate']['id']] = state(value['candidate'], 'created')
        self.stop_errors = set(); self.start_errors = set(); self.inspect_errors = set()
        self.stop_still_running = set(); self.proof_patch = {}; self.fixture_values = {}
        self.fixture_stop_errors = set(); self.fixture_bad_role = None
        self.fixture_checks = {name: True for name in f.CHECKS}; self.data_clean = True
        self.postcheck_bad_ids = set(); self.drift_old_after_start = False

    def boundary_proof(self, phase, digest):
        self.events.append(('admit', phase))
        return {'approved_manifest': digest, 'physical_device': 66315,
                'docker_root': '/mnt/openfoam/docker', 'socket_identity': [25, 66375],
                'empty_fixed_docker_config': True,
                'artifact_hashes': copy.deepcopy(self.manifest['artifacts']),
                'home_allocated': 0, 'docker_allocated': 0,
                'offloaded_allocated': 0, 'offloaded_free': 500000000,
                'home_free': 6000000000, 'docker_free': 1000000000, **self.proof_patch}

    def public_identity(self): return copy.deepcopy(c.PUBLIC)
    def record_once(self, name, value):
        if name in self.markers: raise c.Refused('one_attempt')
        self.markers[name] = copy.deepcopy(value); self.events.append(('marker', name))
    def pause(self, value): self.events.append(('pause', value))
    def inspect(self, identifier):
        self.events.append(('inspect', identifier))
        if identifier in self.inspect_errors: raise RuntimeError('SENTINEL_SECRET')
        return copy.deepcopy(self.states[identifier])
    def stop(self, identifier):
        self.events.append(('stop', identifier))
        if identifier in self.stop_errors: raise TimeoutError('SENTINEL_SECRET')
        if identifier not in self.stop_still_running:
            expected = c.OLD_IDENTITY if identifier == c.OLD else self.manifest['candidate']
            self.states[identifier] = state(expected, 'exited')
    def start(self, identifier):
        self.events.append(('start', identifier))
        if identifier in self.start_errors: raise RuntimeError('SENTINEL_SECRET')
        expected = c.OLD_IDENTITY if identifier == c.OLD else self.manifest['candidate']
        self.states[identifier] = state(expected, 'running')
        if identifier == c.OLD and self.drift_old_after_start: self.states[identifier]['config'] = '0' * 64
    def postcheck(self, identifier):
        self.events.append(('postcheck', identifier))
        return {} if identifier in self.postcheck_bad_ids else copy.deepcopy(r.POSTCHECK)
    def serving_snapshot(self): return copy.deepcopy(self.states[c.OLD])
    def create_fixture(self, role, manifest):
        self.events.append(('fixture_create', role))
        if self.fixture_bad_role == role: return c.OLD
        identifier = ('b' if role == 'bootstrap' else 'c') * 64
        self.fixture_values[identifier] = {'id': identifier, 'run_id': manifest['run_id'],
                                         'role': role, 'image': c.TEST_IMAGE if role == 'bootstrap' else c.IMAGE,
                                         'source': c.SOURCE, 'owned_synthetic': True,
                                         'policy': copy.deepcopy(f.OWNED_POLICY)}
        return identifier
    def fixture_identity(self, identifier): return copy.deepcopy(self.fixture_values[identifier])
    def fixture_cleanup_owned(self, identifier, role=None):
        return identifier in self.fixture_values and (role is None or self.fixture_values[identifier]['role'] == role)
    def wait_fixture_ready(self, identifier):
        self.events.append(('fixture_ready', identifier))

    def start_fixture(self, identifier): self.events.append(('fixture_start', identifier))
    def exercise_fixture(self, identifier, manifest): return copy.deepcopy(self.fixture_checks)
    def stop_fixture(self, identifier):
        self.events.append(('fixture_stop', identifier))
        if identifier in self.fixture_stop_errors: raise TimeoutError('SENTINEL_SECRET')
    def fixture_stopped(self, identifier): return True
    def remove_fixture(self, identifier):
        self.events.append(('fixture_remove', identifier)); del self.fixture_values[identifier]
    def fixture_absent(self, identifier): return identifier not in self.fixture_values
    def owned_database_bucket_removed(self, run_id): return self.data_clean
