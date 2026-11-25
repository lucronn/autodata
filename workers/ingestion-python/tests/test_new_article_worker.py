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


@pytest.mark.parametrize("continuous", [False, True])
def test_only_continuous_start_can_capture_without_configured_model(monkeypatch, capsys, continuous):
    from autodata_ingestion import source_connector_client
    from autodata_ingestion import worker as worker_dependencies

    class State:
        def __init__(self, *, source_sha, continuous):
            assert source_sha == SHA
            self.schema = 2 if continuous else 1

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    repo, fixture_store = object(), object()

    def run(actual_repo, state, *, registry, object_store, model_client, stop):
        assert continuous and state.schema == 2
        assert actual_repo is repo and registry == {"bankone": "fixture"}
        assert object_store is fixture_store and model_client is None and not stop.is_set()
        return 0

    monkeypatch.setenv("AUTODATA_NEW_ARTICLE_SOURCE_SHA", SHA)
    monkeypatch.delenv("INCEPTION_API_KEY", raising=False)
    for name, value in {"AUTODATA_S3_ENDPOINT": "http://minio:9000", "AUTODATA_S3_ACCESS_KEY": "fixture",
                        "AUTODATA_S3_SECRET_KEY": "fixture", "AUTODATA_SOURCE_BUCKET": "fixture"}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(worker, "RolloutState", State)
    monkeypatch.setattr(worker_dependencies, "ArticleRepository", lambda: repo)
    monkeypatch.setattr(worker_dependencies, "ArticleObjectStore", lambda **kwargs: fixture_store)
    monkeypatch.setattr(source_connector_client, "source_connector_registry",
                        lambda *, include_defaults: {"bankone": "fixture"})
    monkeypatch.setattr(worker, "run_new_article_worker", run)

    assert worker.main(["--continuous"] if continuous else []) == (0 if continuous else 1)
    expected = "NEW_ARTICLE_MODEL_PAUSED" if continuous else "NEW_ARTICLE_WORKER_BLOCKED"
    assert capsys.readouterr().out.strip() == expected


def test_stop_during_database_clock_read_cannot_dispatch(state,monkeypatch):
    from threading import Event
    state.initialize(NOW);state.set_enabled(True)
    stop=Event()
    def clock(repo):
        stop.set()
        return NOW
    monkeypatch.setattr(worker,'database_now',clock)
    monkeypatch.setattr(worker,'dispatch_next',lambda *a,**k: pytest.fail('dispatch after stop'))
    assert worker.run_new_article_worker(None,state,registry={},object_store=None,model_client=object(),stop=stop)==0
    assert state.read()['reservations']==[]


def test_stop_while_state_lock_waited_prevents_reservation(state):
    from threading import Event
    state.initialize(NOW);state.set_enabled(True)
    stop=Event();stop.set()
    assert state.reserve(uuid4(),NOW,stop=stop) is False
    assert state.read()['reservations']==[]


@pytest.fixture
def continuous_state(tmp_path):
    directory=tmp_path/'continuous';directory.mkdir(mode=0o700)
    with worker.RolloutState(directory,source_sha=SHA,owner_uid=os.getuid(),continuous=True) as state:
        state.initialize(NOW);yield state


def test_continuous_initialization_and_mode_are_explicit(continuous_state,state):
    value=continuous_state.read()
    assert value['schema']==2 and value['enabled'] is False and 'expires_at' not in value
    assert value['cutoff']==NOW.isoformat() and value['reservations']==[]
    with pytest.raises(worker.WorkerBlocked):continuous_state.initialize(NOW)
    with worker.RolloutState(continuous_state.directory,source_sha=SHA,owner_uid=os.getuid()) as finite:
        with pytest.raises(worker.WorkerBlocked):finite.read()
    state.initialize(NOW)
    with worker.RolloutState(state.directory,source_sha=SHA,owner_uid=os.getuid(),continuous=True) as sustained:
        with pytest.raises(worker.WorkerBlocked):sustained.read()


def test_rebind_preserves_enabled_state_and_spent_quota(continuous_state):
    continuous_state.set_enabled(True)
    jobs = [uuid4() for _ in range(10)]
    for job_id in jobs:
        assert continuous_state.reserve(job_id, NOW)
    original = continuous_state.read()
    next_sha = 'b' * 40
    with worker.RolloutState(continuous_state.directory, source_sha=next_sha,
                             owner_uid=os.getuid(), continuous=True) as upgraded:
        upgraded.rebind_source(SHA)
        assert upgraded.read() == {**original, 'source_sha': next_sha}
        upgraded.rebind_source(SHA)
        with pytest.raises(worker.WorkerBlocked, match='ROLLOUT_SCOPE_INVALID'):
            continuous_state.read()
        assert not upgraded.reserve(uuid4(), NOW + timedelta(hours=23))
        assert not upgraded.reserve(jobs[0], NOW + timedelta(days=2))
        assert upgraded.reserve(uuid4(), NOW + timedelta(days=2))


def test_rebind_requires_an_idle_worker_and_matching_previous_pin(continuous_state):
    original = continuous_state.read()
    with worker.RolloutState(continuous_state.directory, source_sha='b' * 40,
                             owner_uid=os.getuid(), continuous=True) as upgraded:
        with pytest.raises(worker.WorkerBlocked, match='ROLLOUT_SCOPE_INVALID'):
            upgraded.rebind_source('c' * 40)
        with continuous_state.worker_lock():
            with pytest.raises(worker.WorkerBlocked, match='WORKER_ALREADY_RUNNING'):
                upgraded.rebind_source(SHA)
    assert continuous_state.read() == original


def test_rebind_refuses_a_finite_rollout(state):
    state.initialize(NOW)
    original = state.read()
    with worker.RolloutState(state.directory, source_sha='b' * 40, owner_uid=os.getuid()) as upgraded:
        with pytest.raises(worker.WorkerBlocked, match='ROLLOUT_REBIND_INVALID'):
            upgraded.rebind_source(SHA)
    assert state.read() == original


def test_continuous_rolling_boundary_keeps_all_spent_ids(continuous_state):
    state=continuous_state;state.set_enabled(True);jobs=[uuid4() for _ in range(10)]
    for job in jobs:assert state.reserve(job,NOW)
    assert not state.reserve(uuid4(),NOW+timedelta(hours=24,microseconds=-1))
    assert state.reserve(uuid4(),NOW+timedelta(hours=24))
    state.set_enabled(False);assert not state.reserve(uuid4(),NOW+timedelta(days=3));state.set_enabled(True)
    with worker.RolloutState(state.directory,source_sha=SHA,owner_uid=os.getuid(),continuous=True) as reopened:
        assert len(reopened.read()['reservations'])==11
        assert not reopened.reserve(jobs[0],NOW+timedelta(days=3))
        assert reopened.reserve(uuid4(),NOW+timedelta(days=3))


def test_continuous_concurrent_reservations_cannot_overspend(continuous_state):
    from concurrent.futures import ThreadPoolExecutor
    continuous_state.set_enabled(True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:continuous_state.reserve(uuid4(),NOW),range(16)))
    assert sum(results)==10 and len(continuous_state.read()['reservations'])==10


@pytest.mark.parametrize('mutation',['historical_burst','hidden_future','clockback','duplicate','providers','extra'])
def test_continuous_rejects_bad_ledger(continuous_state,mutation):
    state=continuous_state;state.set_enabled(True);state.reserve(uuid4(),NOW);raw=state.read()
    if mutation=='historical_burst':raw['reservations']=[{'job_id':str(uuid4()),'reserved_at':NOW.isoformat()} for _ in range(11)]
    elif mutation=='hidden_future':raw['reservations']=[{'job_id':str(uuid4()),'reserved_at':(NOW+timedelta(hours=1)).isoformat()},raw['reservations'][0]]
    elif mutation=='clockback':pass
    elif mutation=='duplicate':raw['reservations']*=2
    elif mutation=='providers':raw['providers']=['bankone']
    else:raw['unexpected']=True
    (state.directory/'rollout.json').write_text(json.dumps(raw))
    with pytest.raises(worker.WorkerBlocked):state.reserve(uuid4(),NOW-timedelta(microseconds=1) if mutation=='clockback' else NOW+timedelta(days=3) if mutation=='historical_burst' else NOW+timedelta(seconds=1))


def test_continuous_unsorted_history_does_not_change_stored_order(continuous_state):
    state=continuous_state;state.set_enabled(True);raw=state.read()
    raw['reservations']=[{'job_id':str(uuid4()),'reserved_at':(NOW+timedelta(hours=h)).isoformat()} for h in [48,0,24]]
    (state.directory/'rollout.json').write_text(json.dumps(raw))
    assert state.reserve(uuid4(),NOW+timedelta(hours=49))
    assert state.read()['reservations'][:3]==raw['reservations']


@pytest.mark.parametrize('continuous,limit',[(False,16384),(True,2*1024*1024)])
def test_schema_specific_state_byte_ceiling(tmp_path,continuous,limit):
    directory=tmp_path/'bytes';directory.mkdir(mode=0o700)
    with worker.RolloutState(directory,source_sha=SHA,owner_uid=os.getuid(),continuous=continuous) as state:
        state.initialize(NOW);path=directory/'rollout.json';raw=path.read_bytes()
        path.write_bytes(raw+b' '*(limit-len(raw)+1))
        with pytest.raises(worker.WorkerBlocked):state.read()


def test_continuous_permanent_ledger_ceiling(continuous_state):
    state=continuous_state;state.set_enabled(True);raw=state.read()
    raw['reservations']=[{'job_id':str(uuid4()),'reserved_at':(NOW+timedelta(hours=3*i)).isoformat()} for i in range(10000)]
    (state.directory/'rollout.json').write_text(json.dumps(raw))
    assert len(state.read()['reservations'])==10000
    with pytest.raises(worker.WorkerBlocked):state.reserve(uuid4(),NOW+timedelta(hours=30001))
    raw['reservations'].append({'job_id':str(uuid4()),'reserved_at':(NOW+timedelta(hours=30002)).isoformat()})
    (state.directory/'rollout.json').write_text(json.dumps(raw))
    with pytest.raises(worker.WorkerBlocked):state.read()


def test_continuous_quota_waits_and_resumes(continuous_state,monkeypatch):
    state=continuous_state;state.set_enabled(True)
    for _ in range(10):assert state.reserve(uuid4(),NOW)
    from threading import Event
    stop=Event();clock=[NOW];observed=[]
    subscriptions = []
    class Stop:
        def is_set(self):return stop.is_set()
        def wait(self,seconds):
            assert seconds==2
            if clock[0]==NOW:clock[0]=NOW+timedelta(hours=24)
            else:stop.set()
    monkeypatch.setattr(worker,'database_now',lambda repo:clock[0])
    monkeypatch.setattr(worker,'_subscribe_to_article_jobs',lambda repo: subscriptions.append(clock[0]))
    monkeypatch.setattr(worker,'_reserve_next_article',lambda *a,**k:observed.append(state.reserve(uuid4(),clock[0])))
    worker.run_new_article_worker(None,state,registry={},object_store=None,model_client=None,stop=Stop())
    assert observed==[True] and len(state.read()['reservations'])==11
    assert subscriptions == [NOW + timedelta(hours=24)]


@pytest.mark.parametrize("listener_fails", [False, True])
def test_continuous_waits_for_notifications_and_falls_back_if_listener_fails(
    continuous_state, monkeypatch, listener_fails,
):
    state = continuous_state
    state.set_enabled(True)
    calls = []

    class Stop:
        stopped = False

        def is_set(self):
            return self.stopped

        def wait(self, seconds):
            if not self.stopped:
                calls.append(("poll", seconds))

    class Listener:
        autocommit = False

        def execute(self, statement):
            assert self.autocommit
            assert statement.as_string() == 'LISTEN "autodata_article_job"'
            calls.append("subscribe")

        def notifies(self, *, timeout, stop_after):
            calls.append(("notify", timeout, stop_after))
            if listener_fails:
                raise OSError("fixture listener disconnected")
            yield object()

        def close(self):
            calls.append("close")

    class Repo:
        def connect(self):
            return Listener()

    stop = Stop()
    dispatches = 0

    def dispatch(*args, **kwargs):
        nonlocal dispatches
        calls.append("queue")
        dispatches += 1
        stop.stopped = dispatches == 2
        return None

    monkeypatch.setattr(worker, "database_now", lambda repo: NOW)
    monkeypatch.setattr(worker, "_reserve_next_article", dispatch)
    assert worker.run_new_article_worker(
        Repo(), state, registry={}, object_store=None, model_client=None, stop=stop,
    ) == 0
    assert calls == [
        "subscribe", "queue", ("notify", 2, 1),
        *(["close", ("poll", 2), "subscribe"] if listener_fails else []),
        "queue", "close",
    ]


def test_continuous_preview_unit_is_inert_and_throttled():
    unit=(Path(__file__).parents[3]/'infra/deploy/preview/autodata-new-article-worker.service').read_text()
    for text in ['--continuous','Restart=on-failure','RestartSec=5','StartLimitIntervalSec=60','StartLimitBurst=3','WantedBy=multi-user.target','TimeoutStopSec=80','--read-only','--cap-drop ALL','--security-opt no-new-privileges','StateDirectoryMode=0700']:
        assert text in unit
    assert 'ExecStartPre=' not in unit and '--initialize' not in unit and '--enable' not in unit


def test_continuous_overlaps_providers_and_refills_a_finished_slot(continuous_state, monkeypatch):
    from threading import Event

    continuous_state.set_enabled(True)
    stop = Event()
    banktwo_started = Event()
    next_bankone_started = Event()
    waiting_for_completion = Event()
    first, next_one, first_two, next_two = [uuid4() for _ in range(4)]
    queued = [(first, "bankone"), (next_one, "bankone"), (first_two, "banktwo"), (next_two, "banktwo")]
    reserved = []

    def reserve(repo, state, *, providers, stop):
        for index, (job, provider) in enumerate(queued):
            if provider in providers:
                assert state.reserve(job, NOW)
                reserved.append(job)
                return queued.pop(index)
        return None

    def dispatch(repo, state, job, *, model_client, **kwargs):
        assert model_client is None
        if job == first:
            assert banktwo_started.wait(3)
            assert waiting_for_completion.wait(3)
            assert not next_bankone_started.is_set()
        elif job == first_two:
            banktwo_started.set()
            assert next_bankone_started.wait(3)
        else:
            assert job == next_one
            stop.set()
            next_bankone_started.set()

    def no_poll(seconds):
        pytest.fail(f"Worker polled for {seconds}s while jobs were active")

    select = worker.select

    def wait_for_completion(*args):
        waiting_for_completion.set()
        ready = select(*args)
        assert ready[0], "A finished job must wake the coordinator before its polling timeout"
        return ready

    monkeypatch.setattr(stop, "wait", no_poll)
    monkeypatch.setattr(worker, "select", wait_for_completion)
    monkeypatch.setattr(worker, "database_now", lambda repo: NOW)
    monkeypatch.setattr(worker, "_subscribe_to_article_jobs", lambda repo: None)
    monkeypatch.setattr(worker, "_reserve_next_article", reserve)
    monkeypatch.setattr(worker, "_dispatch_reserved_job", dispatch)

    worker.run_new_article_worker(
        None, continuous_state, registry={}, object_store=None, model_client=None, stop=stop,
    )

    assert reserved == [first, first_two, next_one]
    assert [item["job_id"] for item in continuous_state.read()["reservations"]] == list(map(str, reserved))
    assert queued == [(next_two, "banktwo")]


def test_continuous_clock_before_activation_fails_closed(continuous_state):
    continuous_state.set_enabled(True)
    with pytest.raises(worker.WorkerBlocked):continuous_state.reserve(uuid4(),NOW-timedelta(microseconds=1))
    assert continuous_state.read()['reservations']==[]


def test_continuous_fsync_uncertainty_keeps_permanent_reservation(continuous_state,monkeypatch):
    state=continuous_state;state.set_enabled(True);job=uuid4();original=os.fsync;count=0
    def fail_directory(fd):
        nonlocal count
        count+=1
        if count==2:raise OSError('fixture directory fsync')
        return original(fd)
    with monkeypatch.context() as patch:
        patch.setattr(os,'fsync',fail_directory)
        with pytest.raises(OSError):state.reserve(job,NOW)
    assert not state.reserve(job,NOW+timedelta(days=2))
    assert state.read()['reservations'][0]['job_id']==str(job)


def test_continuous_disabled_at_quota_stops_without_dispatch(continuous_state,monkeypatch):
    state=continuous_state;state.set_enabled(True)
    for _ in range(10):assert state.reserve(uuid4(),NOW)
    state.set_enabled(False)
    monkeypatch.setattr(worker,'database_now',lambda repo:NOW)
    monkeypatch.setattr(worker,'_reserve_next_article',lambda *a,**k:pytest.fail('disabled reserved'))
    assert worker.run_new_article_worker(None,state,registry={},object_store=None,model_client=object())==0
