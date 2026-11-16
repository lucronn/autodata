"""Pure admission contracts for injected adapters. No live transport is supplied."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat

MIB = 1024 ** 2
IMAGE = 'sha256:3132da4cdfa56a36240132e7c83e2bf260f679c0294c7dc06669cb607c6390f7'
TEST_IMAGE = 'sha256:35fd9a5c9f8249b424a4a97f0a3d691ef3705f718d49bdc9a775f349a3f88be7'
SOURCE = 'a82b31dc8850aa3956972928b8c720969765a972'
TREE = '11503a735d7d983ca3ebf090b471c89682e77278'
HELPER = '4246264a881382676927e22adad0a1d240f03268'
OLD = '17295fae5fe60b5b9c78b81206a3a0c8f3e202b811093f91ebb821babe648f3e'
SECONDARY = '343896791b0377600b9825b53c1ddb1b179d54c424d19ea935c0b9b8a681eb07'
OLD_STARTED = '2026-11-15T04:15:19.01131429Z'
PUBLIC = {'pid': 1293423, 'start_ticks': '19892443',
          'binary_sha256': 'bb11d963666e4fc44f6b0879ebb55a14cf7b2ca221bad6ffa8d3282d5360203e'}
PINS = {'image': IMAGE, 'test_image': TEST_IMAGE, 'source': SOURCE, 'tree': TREE,
        'helper': HELPER, 'old': OLD, 'secondary': SECONDARY, 'public': PUBLIC}
OLD_IDENTITY = {
    'id': OLD, 'image': IMAGE, 'source': '272aeeaad8399c305468e5d486cc391d7340f6a4',
    'config': 'c3f41d4fd990904af072ad63ff588fb6b9527c6d9c31161fa2dbc24822026a4a',
    'mounts': '057d43e246c0e85a9f8c972cde61120e5e6aecdfd8384d403f60ac0540cb539c',
    'hostconfig_by_status': {s: 'edba32fda365ec5666197ec2b1817d39484c635fce1e13ce1cd0e66007c08c25'
                             for s in ('running', 'exited')},
}
SECONDARY_IDENTITY = {
    'id': SECONDARY, 'image': IMAGE, 'source': '083f1a502a0f18d371793df59d3310408059d44e',
    'config': 'c3f41d4fd990904af072ad63ff588fb6b9527c6d9c31161fa2dbc24822026a4a',
    'mounts': '498a53a416147a3242b10287111b04a5c86398a908f431ad921a26e4e7b45383',
    'hostconfig_by_status': {'exited': '34418021636c59610bdc662197ff49bc65ad4970cbf29def9665aa290b4a155c'},
}
ARTIFACTS = {'fixture': {'archive', 'source_inventory', 'fixture_adapter', 'fixture_bootstrap',
                         'fixture_client', 'contract', 'transport', 'fixture_plan',
                         'fixture_payload_bootstrap', 'fixture_payload_worker'},
             'runtime': {'archive', 'source_inventory', 'dump', 'toc', 'baseline39',
                         'fixture_receipt', 'runtime_adapter', 'contract', 'launcher', 'payload', 'transport'}}


class Refused(RuntimeError):
    pass


def require(condition, reason):
    if not condition:
        raise Refused(reason)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def full_id(value):
    return isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value) is not None


def typed_equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(right, dict):
        return set(left) == set(right) and all(typed_equal(left[k], right[k]) for k in right)
    if isinstance(right, list):
        return len(left) == len(right) and all(typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def validate(manifest, phase):
    require(phase in ARTIFACTS and manifest.get('phase') == phase, 'phase')
    require(manifest.get('pins') == PINS, 'pins')
    require(re.fullmatch('[a-f0-9]{32}', manifest.get('run_id', '')) is not None, 'run_id')
    hashes = manifest.get('artifacts')
    require(isinstance(hashes, dict) and set(hashes) == ARTIFACTS[phase], 'artifact_names')
    require(all(full_id(v) for v in hashes.values()), 'artifact_hashes')
    require(manifest.get('home_cap') == 128 * MIB and manifest.get('docker_cap') == 64 * MIB,
            'caps')
    require(manifest.get('offloaded_cap') == 64 * MIB, 'offloaded_cap')
    if phase == 'runtime':
        candidate = manifest.get('candidate', {})
        require(full_id(candidate.get('id')) and candidate['id'] not in (OLD, SECONDARY), 'candidate_id')
        require(candidate.get('image') == IMAGE and candidate.get('source') == SOURCE, 'candidate_source')
        require(full_id(candidate.get('config')) and full_id(candidate.get('mounts')), 'candidate_config')
        states = candidate.get('hostconfig_by_status', {})
        require(set(states) == {'created', 'running', 'exited'} and all(full_id(v) for v in states.values()),
                'candidate_state_hashes')
        require(states['running'] == states['exited'], 'candidate_lifecycle')
    return {'manifest_sha256': digest(manifest), 'phase': phase, 'execution_authorized': False,
            'live_backend_supplied': False, 'status': 'VALID_DRY_ONLY_EXECUTION_HELD'}


def boundary(backend, manifest, phase):
    """Must be called before every backend mutation, including cleanup/recovery.

    A future reviewed transport must implement these methods with the pinned
    executable/empty physical Docker config/local socket, file+parent fsync,
    bounded calls and coherent SQL. A backend is a capability, not user input.
    This module deliberately implements no such transport or production CLI.
    """
    validate(manifest, phase)
    require(manifest.get('execution_approved') is True, 'phase_not_approved')
    proof = backend.boundary_proof(phase, digest(manifest))
    require(proof.get('approved_manifest') == digest(manifest), 'approved_manifest')
    require(proof.get('physical_device') == 66315 and proof.get('docker_root') == '/mnt/openfoam/docker',
            'physical_boundary')
    require(proof.get('socket_identity') == [25, 66375] and proof.get('empty_fixed_docker_config') is True,
            'daemon_boundary')
    require(proof.get('artifact_hashes') == manifest['artifacts'], 'artifact_drift')
    home_used, docker_used = proof.get('home_allocated'), proof.get('docker_allocated')
    require(type(home_used) is int and 0 <= home_used <= 128 * MIB, 'home_cap')
    require(type(docker_used) is int and 0 <= docker_used <= 64 * MIB, 'docker_cap')
    require(type(proof.get('home_free')) is int
            and proof['home_free'] >= 5502926848 + 128 * MIB - home_used, 'home_floor')
    require(type(proof.get('docker_free')) is int
            and proof['docker_free'] >= 880803840 + 64 * MIB - docker_used, 'docker_floor')
    offloaded_used = proof.get('offloaded_allocated')
    require(type(offloaded_used) is int and 0 <= offloaded_used <= 64 * MIB, 'offloaded_cap')
    require(type(proof.get('offloaded_free')) is int
            and proof['offloaded_free'] >= 64 * MIB - offloaded_used, 'offloaded_floor')
    require(typed_equal(backend.public_identity(), PUBLIC), 'public_identity')
    secondary = identity(backend.inspect(SECONDARY), SECONDARY_IDENTITY)
    require(secondary.get('running') is False and secondary.get('pid') == 0
            and secondary.get('restart_count') == 0, 'secondary_changed')


def identity(snapshot, expected):
    require(isinstance(snapshot, dict), 'identity_unknown')
    for key in ('id', 'image', 'source', 'config', 'mounts'):
        require(snapshot.get(key) == expected.get(key), 'identity_drift')
    status = snapshot.get('status')
    require(status in expected['hostconfig_by_status']
            and snapshot.get('hostconfig') == expected['hostconfig_by_status'][status], 'hostconfig_drift')
    require(snapshot.get('restarting') is False, 'restarting')
    return snapshot


def stopped(backend, identifier, expected):
    """Only an intentional stop followed by stable exact-ID proof fences restart."""
    samples = []
    for index in range(3):
        if index:
            backend.pause(0.2)
        item = identity(backend.inspect(identifier), expected)
        require(item.get('running') is False and item.get('pid') == 0
                and item['status'] in ('created', 'exited'), 'termination_unknown')
        samples.append(item)
    require(samples[0] == samples[1] == samples[2], 'termination_unstable')
    return samples[-1]


def incumbent(snapshot):
    identity(snapshot, OLD_IDENTITY)
    require(snapshot.get('running') is True and snapshot.get('pid', 0) > 0
            and snapshot.get('restart_count') == 0 and snapshot.get('started_at') == OLD_STARTED,
            'incumbent_lifecycle_drift')
    return snapshot


def read_manifest(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        state = os.fstat(stream.fileno())
        require(stat.S_ISREG(state.st_mode) and state.st_uid == os.getuid()
                and stat.S_IMODE(state.st_mode) == 0o600 and state.st_nlink == 1
                and state.st_size <= 65536, 'manifest_file')
        return json.loads(stream.read(65537))


def cli(phase, argv=None):
    parser = argparse.ArgumentParser(description='Dry-only adapter; no live transport exists.')
    parser.add_argument('--validate-only', action='store_true', required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = validate(read_manifest(args.manifest), phase)
    except (Refused, OSError, ValueError, TypeError):
        print(json.dumps({'status': 'REFUSED', 'execution_authorized': False}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0
