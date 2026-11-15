"""Background selector budgets must not consume foreground connector capacity."""

from threading import Barrier, Event, Thread
from types import SimpleNamespace

import pytest

from autodata_ingestion import catalog_service as catalog
from autodata_ingestion.source_connector_client import SourceConnectorError, SourceEnvelopeV1


REQUEST = catalog.CatalogRequest(2020, "Ford", "Focus", scope="models")


class Clock:
    def __init__(self):
        self.now = 0.0
        self.waits = []
        self.on_wait = None

    def wait(self, delay):
        self.waits.append(delay)
        if self.on_wait:
            self.on_wait()
        self.now += delay
        return False


@pytest.fixture
def clock(monkeypatch):
    value = Clock()
    monkeypatch.setattr(catalog.time, "monotonic", lambda: value.now)
    return value


def control(clock):
    value = catalog._SelectorDeepeningControl()
    value.cancelled = SimpleNamespace(is_set=lambda: False, wait=clock.wait)
    return value


def page(scope="models", *, complete=True, cursor=None):
    item = {"year": 2020, "make": "Ford", "model": "Focus", "region": "US",
            "opaque_ref": "vehicle", "label": "Focus"}
    return SourceEnvelopeV1("request", "bankone", "v1", "2026-11-05T00:00:00Z", None,
                            {"items": [item], "complete": complete, "next_cursor": cursor})


class Client:
    base_url = "https://connector.test"

    def __init__(self, clock, fetch=None):
        self.clock = clock
        self.calls = []
        self.fetch = fetch

    def catalog(self, scope, selector, cursor, **kwargs):
        self.calls.append((self.clock.now, kwargs))
        return self.fetch(scope, len(self.calls)) if self.fetch else page(scope)


@pytest.fixture(autouse=True)
def idle_slot(monkeypatch):
    monkeypatch.setattr(catalog, "_DEEPEN_NEXT_DISPATCH", 0.0, raising=False)
    yield
    cancel = getattr(catalog, "cancel_selector_deepening", None)
    if cancel:
        cancel()
    with catalog._DEEPEN_LOCK:
        catalog._DEEPEN_IN_FLIGHT.clear()
        catalog._DEEPEN_CONTROL = None


def test_distinct_simultaneous_keys_start_only_one_daemon(monkeypatch):
    started = []
    monkeypatch.setattr(catalog, "Thread", lambda **kwargs: SimpleNamespace(start=lambda: started.append(kwargs)))
    barrier = Barrier(3)
    results = []

    def schedule(make):
        barrier.wait()
        results.append(catalog._schedule_selector_deepening({"year": 2020, "make": make}, "models", []))

    threads = [Thread(target=schedule, args=(make,)) for make in ("Ford", "Toyota")]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(2)
    assert sorted(result["status"] for result in results) == ["busy", "scheduled"]
    assert len(started) == 1
    winner = next(result for result in results if result["status"] == "scheduled")
    make = winner["key"].split("|")[2]
    assert catalog._schedule_selector_deepening({"year": 2020, "make": make}, "models", [])["status"] == "already_running"


def test_thread_start_failure_releases_slot(monkeypatch):
    def fail():
        raise RuntimeError("cannot start")
    monkeypatch.setattr(catalog, "Thread", lambda **kwargs: SimpleNamespace(start=fail))
    with pytest.raises(RuntimeError, match="cannot start"):
        catalog._schedule_selector_deepening({"year": 2020}, "makes", [])
    assert not catalog._DEEPEN_IN_FLIGHT
    assert catalog._DEEPEN_CONTROL is None


def test_each_pagination_page_is_spaced_and_thirteenth_attempt_is_blocked(clock):
    client = Client(clock, lambda scope, n: page(scope, complete=False, cursor=str(n)))
    provider = catalog._SourceCatalogProvider(client, deepening_control=control(clock))
    with pytest.raises(catalog._SelectorDeepeningStopped):
        provider.resolve_catalog(REQUEST)
    assert [at for at, _ in client.calls] == list(range(0, 72, 6))
    assert len(clock.waits) == 11


def test_failed_attempts_share_budget_across_providers(clock):
    budget = control(clock)
    def fail(scope, n):
        raise SourceConnectorError("UPSTREAM_UNAVAILABLE")
    clients = [Client(clock, fail), Client(clock, fail)]
    service = catalog.CacheFirstCatalogService(cache_reader=lambda _: None,
        providers=[catalog._SourceCatalogProvider(client, deepening_control=budget) for client in clients])
    for _ in range(6):
        service.resolve(REQUEST)
    with pytest.raises(catalog._SelectorDeepeningStopped):
        service.resolve(REQUEST)
    assert sum(len(client.calls) for client in clients) == 12
    assert clock.now == 66


def test_deadline_and_remaining_transport_timeout(clock):
    budget = control(clock)
    clock.now = 118
    client = Client(clock, lambda scope, n: page(scope, complete=False, cursor=str(n)))
    with pytest.raises(catalog._SelectorDeepeningStopped):
        catalog._SourceCatalogProvider(client, deepening_control=budget).resolve_catalog(REQUEST)
    assert [(started, kwargs["timeout"]) for started, kwargs in client.calls] == [(118, 2)]
    assert client.calls[0][1]["before_additional_request"] == budget.before_request
    assert clock.now == 120


def test_cancellation_during_wait_stops_future_pages(clock):
    budget = catalog._SelectorDeepeningControl()
    cancelled = Event()
    clock.on_wait = cancelled.set
    budget.cancelled = SimpleNamespace(is_set=cancelled.is_set, wait=clock.wait)
    client = Client(clock, lambda scope, n: page(scope, complete=False, cursor=str(n)))
    with pytest.raises(catalog._SelectorDeepeningStopped):
        catalog._SourceCatalogProvider(client, deepening_control=budget).resolve_catalog(REQUEST)
    assert len(client.calls) == 1


def test_rate_limit_stops_run_instead_of_trying_next_provider(clock):
    def limited(scope, n):
        raise SourceConnectorError("RATE_LIMITED", status=429, retryable=True)
    clients = [Client(clock, limited), Client(clock)]
    budget = control(clock)
    service = catalog.CacheFirstCatalogService(cache_reader=lambda _: None,
        providers=[catalog._SourceCatalogProvider(client, deepening_control=budget) for client in clients])
    with pytest.raises(catalog._SelectorDeepeningStopped):
        service.resolve(REQUEST)
    assert [len(client.calls) for client in clients] == [1, 0]


@pytest.mark.parametrize("failure", ["cancel_during_io", "provider", "persistence", "budget_after_write"])
def test_stopped_run_releases_slot_preserves_rows_and_never_marks_complete(monkeypatch, clock, failure):
    stored = [{"model": "prior canonical row"}]
    markers = []
    budget = control(clock)
    if failure == "budget_after_write":
        budget.remaining_attempts = 2

    def fetch(scope, n):
        if failure == "provider":
            raise RuntimeError("provider failure")
        if failure == "cancel_during_io" and scope == "configurations":
            budget.cancelled = Event()
            budget.cancelled.set()
        result = page(scope)
        if scope == "models" and failure == "budget_after_write":
            result.body["items"].append({**result.body["items"][0], "model": "Other", "opaque_ref": "other"})
        return result

    client = Client(clock, fetch)
    monkeypatch.setattr(catalog, "_configured_catalog_providers", lambda **kwargs: (
        catalog._SourceCatalogProvider(client, **kwargs),))
    def persist(rows, **kwargs):
        if failure == "persistence":
            raise RuntimeError("storage failure")
        stored.extend(rows)
    monkeypatch.setattr(catalog, "_persist_resolved_catalog_rows", persist)
    monkeypatch.setattr(catalog, "_persist_hydration_scope", lambda *args: markers.append(args))
    catalog._DEEPEN_IN_FLIGHT.add("run")
    catalog._DEEPEN_CONTROL = budget
    catalog._deepen_selector_scope({"year": 2020, "make": "Ford"}, "models", [], "run", budget)
    assert not catalog._DEEPEN_IN_FLIGHT
    assert catalog._DEEPEN_CONTROL is None
    assert stored[0] == {"model": "prior canonical row"}
    assert len(stored) == (2 if failure == "budget_after_write" else 1)
    assert not markers


def test_foreground_catalog_and_article_calls_continue_while_background_waits(monkeypatch):
    waiting, resume = Event(), Event()
    budget = catalog._SelectorDeepeningControl()
    original_wait = budget.cancelled.wait
    def wait(delay):
        waiting.set()
        assert resume.wait(2)
        return original_wait(0)
    monkeypatch.setattr(budget.cancelled, "wait", wait)
    clock = Clock()
    background = Client(clock, lambda scope, n: page(scope, complete=n > 1, cursor="next"))
    done = Event()
    def run():
        try:
            catalog._SourceCatalogProvider(background, deepening_control=budget).resolve_catalog(REQUEST)
        except catalog._SelectorDeepeningStopped:
            pass
        finally:
            done.set()
    thread = Thread(target=run)
    thread.start()
    try:
        assert waiting.wait(2)
        foreground = Client(clock)
        assert catalog._SourceCatalogProvider(foreground).resolve_catalog(REQUEST)["complete"]
        assert foreground.calls[0][1] == {}
        monkeypatch.setattr(catalog, "_ensure_lifecycle_catalog", lambda request: {"state": "queued"})
        assert catalog.ensure_catalog_hydration('{"scope":"article","idempotency_key":"foreground"}') == {"state": "queued"}
    finally:
        budget.cancelled.set()
        resume.set()
        thread.join(2)
    assert done.is_set()


def test_cancel_is_safe_while_idle():
    catalog.cancel_selector_deepening()


def test_cancel_active_run_before_thread_dispatch_releases_slot(monkeypatch):
    started = []
    monkeypatch.setattr(catalog, "Thread", lambda **kwargs: SimpleNamespace(start=lambda: started.append(kwargs)))
    result = catalog._schedule_selector_deepening({"year": 2020}, "makes", [])
    assert result["status"] == "scheduled"
    catalog.cancel_selector_deepening()
    def unexpected_provider_call(**kwargs):
        pytest.fail("canceled run must not resolve providers")
    monkeypatch.setattr(catalog, "_configured_catalog_providers", unexpected_provider_call)
    started[0]["target"](*started[0]["args"])
    assert not catalog._DEEPEN_IN_FLIGHT
    assert catalog._DEEPEN_CONTROL is None


@pytest.mark.parametrize("rate_limited", [False, True])
def test_adjacent_runs_preserve_six_second_dispatch_spacing(clock, rate_limited):
    def fetch(scope, n):
        if rate_limited:
            raise SourceConnectorError("RATE_LIMITED", status=429)
        return page(scope)

    first = Client(clock, fetch)
    provider = catalog._SourceCatalogProvider(first, deepening_control=control(clock))
    if rate_limited:
        with pytest.raises(catalog._SelectorDeepeningStopped):
            provider.resolve_catalog(REQUEST)
    else:
        provider.resolve_catalog(REQUEST)
    second = Client(clock)
    catalog._SourceCatalogProvider(second, deepening_control=control(clock)).resolve_catalog(REQUEST)
    assert first.calls[0][0] == 0
    assert second.calls[0][0] == 6
