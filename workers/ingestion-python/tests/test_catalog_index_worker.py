"""Catalog admission must never turn into a generic article queue drain."""
from contextlib import contextmanager
from threading import Event
from unittest.mock import Mock
from uuid import uuid4

import pytest

from autodata_ingestion import catalog_index_worker as worker


class Repository:
    def __init__(self, job_id):
        self.job_id = job_id
        self.open = False

    @contextmanager
    def connect(self):
        self.open = True
        try:
            yield self
        finally:
            self.open = False

    def execute(self, query, params):
        self.query, self.params = query, params
        return self

    def fetchone(self):
        return None if self.job_id is None else {'source_fetch_job_id': self.job_id}


@pytest.mark.parametrize('job_id', [None, uuid4()])
def test_exact_dispatch_after_selection_connection_closes(monkeypatch, job_id):
    repo = Repository(job_id)
    def dispatch(actual, **kwargs):
        assert actual is repo and not repo.open
        assert kwargs['job_id'] == job_id
        assert kwargs['model_client'] is None
        return True
    run = Mock(side_effect=dispatch)
    monkeypatch.setattr(worker, 'run_article_worker_once', run)
    assert worker.dispatch_next(repo, worker_id=uuid4(), registry={}, object_store=None) is (job_id is not None)
    assert run.call_count == (job_id is not None)
    assert repo.params == ('catalog_index', ['bankone', 'banktwo'])


def test_stop_after_select_prevents_dispatch(monkeypatch):
    stop = Event()
    def select(_):
        stop.set()
        return uuid4()
    monkeypatch.setattr(worker, 'select_next_catalog_job', select)
    run = Mock()
    monkeypatch.setattr(worker, 'run_article_worker_once', run)
    assert not worker.dispatch_next(None, worker_id=uuid4(), registry={}, object_store=None, stop=stop)
    run.assert_not_called()


@pytest.mark.parametrize('claimed', [False, True])
def test_once_dispatches_at_most_one_without_wait(monkeypatch, claimed):
    dispatch = Mock(return_value=claimed)
    monkeypatch.setattr(worker, 'dispatch_next', dispatch)
    stop = Mock()
    stop.is_set.return_value = False
    assert worker.run_catalog_worker(None, registry={}, object_store=None, once=True, stop=stop) == 0
    dispatch.assert_called_once()
    stop.wait.assert_not_called()


def test_idle_or_lost_claim_waits_two_seconds_and_stops(monkeypatch):
    stop = Event()
    waits = []
    def wait(seconds):
        waits.append(seconds)
        stop.set()
    monkeypatch.setattr(stop, 'wait', wait)
    dispatch = Mock(return_value=False)
    monkeypatch.setattr(worker, 'dispatch_next', dispatch)
    worker.run_catalog_worker(None, registry={}, object_store=None, stop=stop)
    assert waits == [2]
    dispatch.assert_called_once()


def test_already_stopped_never_selects(monkeypatch):
    stop = Event()
    stop.set()
    select = Mock()
    monkeypatch.setattr(worker, 'select_next_catalog_job', select)
    worker.run_catalog_worker(None, registry={}, object_store=None, stop=stop)
    select.assert_not_called()


@pytest.mark.parametrize('endpoint', ['', 'localhost:9000', 'ftp://host', 'http://host/path',
                                       'http://user:password@host', 'http://host?secret', 'http://host#fragment'])
def test_bad_configuration_fails_closed_without_contents(monkeypatch, capsys, endpoint):
    configured_environment(monkeypatch)
    monkeypatch.setenv('AUTODATA_S3_ENDPOINT', endpoint)
    assert worker.main(['--once']) == 1
    assert capsys.readouterr().out == 'CATALOG_INDEX_WORKER_BLOCKED\n'


def configured_environment(monkeypatch):
    for name in ('AUTODATA_DB_ADDRESS', 'AUTODATA_POSTGRES_DB', 'AUTODATA_POSTGRES_USER',
                 'AUTODATA_POSTGRES_PASSWORD', 'AUTODATA_S3_ACCESS_KEY', 'AUTODATA_S3_SECRET_KEY',
                 'AUTODATA_SOURCE_BUCKET', 'AUTODATA_BANKONE_API_KEY', 'AUTODATA_BANKTWO_API_KEY'):
        monkeypatch.setenv(name, 'fixture')
    monkeypatch.setenv('AUTODATA_S3_ENDPOINT', 'https://fixture:9000/')
    monkeypatch.setenv('BANKONE_BASE_URL', 'https://bankone.example')
    monkeypatch.setenv('BANKTWO_BASE_URL', 'https://banktwo.example')


def test_main_builds_only_catalog_clients_and_installs_stop_handlers(monkeypatch):
    from autodata_ingestion import worker as runtime, source_connector_client, mercury2
    configured_environment(monkeypatch)
    monkeypatch.delenv('INCEPTION_API_KEY', raising=False)
    model = Mock(side_effect=AssertionError('model must not be constructed'))
    monkeypatch.setattr(mercury2.Mercury2Client, 'from_environment', model)
    objects = Mock()
    monkeypatch.setattr(runtime, 'ArticleObjectStore', objects)
    monkeypatch.setattr(runtime, 'ArticleRepository', Mock())
    registry = Mock(return_value={})
    monkeypatch.setattr(source_connector_client, 'source_connector_registry', registry)
    handlers = {}
    monkeypatch.setattr(worker.signal, 'signal', lambda sig, handler: handlers.update({sig: handler}))
    def run(*args, **kwargs):
        assert kwargs['once'] is True
        assert not kwargs['stop'].is_set()
        handlers[worker.signal.SIGTERM](None, None)
        assert kwargs['stop'].is_set()
        return 0
    monkeypatch.setattr(worker, 'run_catalog_worker', run)
    assert worker.main(['--once']) == 0
    assert set(handlers) == {worker.signal.SIGTERM, worker.signal.SIGINT}
    registry.assert_called_once_with(include_defaults=False)
    assert objects.call_args.kwargs['endpoint'] == 'fixture:9000'
    assert objects.call_args.kwargs['secure'] is True
    model.assert_not_called()


def test_successful_jobs_are_serial_and_stop_before_next_selection(monkeypatch):
    stop = Event()
    active = 0
    calls = 0
    def dispatch(*args, **kwargs):
        nonlocal active, calls
        active += 1
        assert active == 1
        calls += 1
        if calls == 2:
            stop.set()
        active -= 1
        return True
    monkeypatch.setattr(worker, 'dispatch_next', dispatch)
    worker.run_catalog_worker(None, registry={}, object_store=None, stop=stop)
    assert calls == 2


def test_dedicated_runtime_requires_canonical_provider_keys(monkeypatch, capsys):
    configured_environment(monkeypatch)
    monkeypatch.delenv('AUTODATA_BANKONE_API_KEY')
    monkeypatch.setenv('BANKONE_API_TOKEN', 'legacy-fixture')
    assert worker.main(['--once']) == 1
    assert capsys.readouterr().out == 'CATALOG_INDEX_WORKER_BLOCKED\n'


def test_preview_service_has_no_automatic_start_or_article_state():
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    unit = (root / 'infra/deploy/preview/autodata-catalog-index-worker.service').read_text()
    assert '[Install]' not in unit and 'Restart=no' in unit
    assert '--read-only --cap-drop ALL --security-opt no-new-privileges' in unit
    assert '--stop-timeout 70' in unit and 'TimeoutStopSec=80' in unit
    assert 'new-article' not in unit and 'INCEPTION' not in unit
    assert 'python -m autodata_ingestion.catalog_index_worker' in unit
    assert '--env-file /etc/autodata/catalog-index-runtime.env' in unit
    assert 'sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4' in unit
