"""Local admission state never rearms or replays a consumed identity."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import pytest
from uuid import uuid4

from autodata_ingestion import new_article_worker as worker

SHA = 'a' * 40
NOW = datetime(2026, 11, 6, tzinfo=timezone.utc)


@pytest.fixture
def state(tmp_path):
    directory = tmp_path / 'state'
    directory.mkdir(mode=0o700)
    with worker.RolloutState(directory, source_sha=SHA, owner_uid=os.getuid()) as state:
        yield state


def test_initialize_disabled_is_once_only_and_enable_preserves_cutoff(state):
    state.initialize(NOW)
    original = state.read()
    assert original['enabled'] is False and original['max_jobs'] == 10
    assert original['expires_at'] == (NOW + timedelta(hours=24)).isoformat()
    with pytest.raises(worker.WorkerBlocked):
        state.initialize(NOW + timedelta(hours=1))
    state.set_enabled(True)
    assert state.read() == {**original, 'enabled': True}
    state.set_enabled(False)
    assert state.read() == original


def test_quota_expiry_disable_and_restart_never_replay(state):
    state.initialize(NOW)
    first = uuid4()
    assert state.reserve(first, NOW) is False
    state.set_enabled(True)
    assert state.reserve(first, NOW)
    assert state.reserve(first, NOW) is False
    state.set_enabled(False)
    assert state.reserve(uuid4(), NOW) is False
    state.set_enabled(True)
    assert state.reserve(uuid4(), NOW + timedelta(hours=24)) is False
    for _ in range(9):
        assert state.reserve(uuid4(), NOW)
    assert state.reserve(uuid4(), NOW) is False
    with worker.RolloutState(state.directory, source_sha=SHA, owner_uid=os.getuid()) as reopened:
        assert reopened.read() == state.read()
        assert reopened.reserve(first, NOW) is False


def test_second_worker_is_rejected_but_control_remains_available(state):
    state.initialize(NOW)
    with state.worker_lock():
        with worker.RolloutState(state.directory, source_sha=SHA, owner_uid=os.getuid()) as other:
            with pytest.raises(worker.WorkerBlocked):
                with other.worker_lock():
                    pytest.fail('second worker obtained lifetime lock')
            other.set_enabled(True)
            other.set_enabled(False)
    assert not state.read()['enabled']


@pytest.mark.parametrize('mutation', ['symlink', 'hardlink', 'mode', 'source', 'duplicate', 'unknown', 'oversize'])
def test_corrupt_or_replaced_state_fails_closed(state, mutation):
    state.initialize(NOW)
    path = state.directory / 'rollout.json'
    if mutation == 'symlink':
        moved = path.with_suffix('.old'); path.rename(moved); path.symlink_to(moved)
    elif mutation == 'hardlink':
        os.link(path, path.with_suffix('.linked'))
    elif mutation == 'mode':
        path.chmod(0o644)
    elif mutation == 'oversize':
        path.write_text(' ' * 20000)
    else:
        raw = json.loads(path.read_text())
        if mutation == 'source': raw['source_sha'] = 'b' * 40
        if mutation == 'unknown': raw['surprise'] = True
        path.write_text(json.dumps(raw) if mutation != 'duplicate' else '{"schema":1,"schema":1}')
    with pytest.raises((worker.WorkerBlocked, OSError)):
        state.read()


def test_replaced_directory_is_rejected(state):
    state.initialize(NOW)
    state.directory.rename(state.directory.with_name('old-state'))
    state.directory.mkdir(mode=0o700)
    with pytest.raises(worker.WorkerBlocked):
        state.set_enabled(True)


def test_fsync_failure_after_reservation_cannot_dispatch_and_consumes_quota(state, monkeypatch):
    state.initialize(NOW); state.set_enabled(True)
    original = os.fsync
    count = 0
    def fail_directory(fd):
        nonlocal count
        count += 1
        if count == 2: raise OSError('directory fsync failed')
        return original(fd)
    job = uuid4()
    with monkeypatch.context() as patch:
        patch.setattr(os, 'fsync', fail_directory)
        with pytest.raises(OSError): state.reserve(job, NOW)
    assert state.read()['reservations'][0]['job_id'] == str(job)
    assert not state.reserve(job, NOW)


@pytest.mark.parametrize('env', [{}, {'INCEPTION_API_KEY': 'fixture', 'INCEPTION_MODEL': 'mercury-2'},
    {'INCEPTION_API_KEY': 'fixture', 'INCEPTION_MODEL': 'mercury-3', 'INCEPTION_MAX_TOKENS': '8192'}])
def test_model_configuration_must_match_reviewed_limits_before_admission(monkeypatch, env):
    monkeypatch.setattr(os, 'environ', env)
    with pytest.raises(worker.WorkerBlocked): worker.configured_model()


def test_missing_model_cannot_reserve_or_touch_database(state):
    state.initialize(NOW);state.set_enabled(True)
    class ForbiddenDatabase:
        def connect(self): pytest.fail('unconfigured model reached database')
    with pytest.raises(worker.WorkerBlocked):
        worker.dispatch_next(ForbiddenDatabase(),state,worker_id=uuid4(),registry={},object_store=None,model_client=None)
    assert state.read()['reservations']==[]
