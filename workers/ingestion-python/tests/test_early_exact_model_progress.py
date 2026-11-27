"""Exercise the early model read with the ordinary connector and shared budget."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
from time import monotonic, sleep
from urllib.parse import parse_qs, urlsplit

import pytest

from autodata_ingestion import catalog_service as catalog
from autodata_ingestion import selector_job
from autodata_ingestion.selector_job import SelectorJobControl, SelectorJobStopped
from autodata_ingestion.source_connector_client import SourceConnectorClient
from lifecycle_support import fresh_database
from test_initial_selector_safety import Clock
from test_source_connector_client import _Response, _envelope


def _selector(monkeypatch, *, banktwo_first="success", label="Fixture-Truck"):
    clock = Clock()
    control = SelectorJobControl(20, clock=clock, sleep=clock.sleep)
    calls = []
    progress = []
    proofs = []

    def open_page(provider):
        def opener(request, *, timeout):
            url = urlsplit(request.full_url)
            selector = parse_qs(url.query)
            path = url.path.rsplit("/", 1)[-1]
            make = selector.get("make", [None])[0]
            cursor = selector.get("cursor", [None])[0]
            calls.append((clock(), provider, path, make, cursor))
            shared = "Fixture Sedan" if provider == "bankone" else "FIXTURE SEDAN"
            if provider == "banktwo" and len(calls) == 1:
                assert 0 < timeout <= 2
                if banktwo_first == "429":
                    return _Response({}, url=request.full_url, status=429)
                if banktwo_first == "timeout":
                    clock.sleep(2)
                    raise TimeoutError
                if banktwo_first == "404":
                    return _Response({}, url=request.full_url, status=404)
            clock.sleep(0.125)
            complete = True
            if path == "makes":
                items = [{"year": 2021, "make": "Fixture Truck", "label": "Fixture Truck", "opaque_ref": "make-fixture"}]
            else:
                names = [shared, provider + " only"]
                if provider == "banktwo" and banktwo_first == "paginated":
                    names, complete = ([shared], False) if cursor is None else (["banktwo only"], True)
                items = [{"year": 2021, "make": "Fixture Truck", "model": model, "label": model,
                          "opaque_ref": f"{provider}-{index}-{cursor or 'first'}", **({"region": "US"} if provider == "bankone" else {})}
                         for index, model in enumerate(names)]
            return _Response(_envelope(provider, scope=path, items=items, complete=complete,
                                       next_cursor=None if complete else "page-2"), url=request.full_url)
        return opener

    providers = tuple(
        catalog._SourceCatalogProvider(
            SourceConnectorClient(f"http://127.0.0.1:{port}", provider=provider, opener=open_page(provider)),
            deepening_control=control,
        )
        for provider, port in (("bankone", 9010), ("banktwo", 9020))
    )
    monkeypatch.setattr(catalog, "_configured_catalog_providers", lambda **_kwargs: providers)

    def lookup(request, origin):
        proofs.append((request, origin))
        return label

    monkeypatch.setattr(catalog, "_stored_banktwo_make_label", lookup)
    request = catalog.CatalogRequest(2021, "fixture-truck", "unknown", scope="models")

    def resolve(*, early=True):
        return catalog._resolve_initial_catalog(
            request, control, on_progress=(lambda result: progress.append((clock(), result))) if early else None,
        )

    return resolve, calls, progress, control, proofs


def test_both_healthy_suppliers_merge_identically_and_make_early_choices(monkeypatch):
    baseline, old_calls, _, old_control, _ = _selector(monkeypatch)
    expected = baseline(early=False)
    candidate, calls, progress, control, proofs = _selector(monkeypatch)
    result = candidate()
    assert result == expected
    assert result.complete and len(result.rows) == 3
    assert [row["provider"] for row in result.provenance] == ["autoapi", "autoapitwo"]
    assert [row["provider"] for row in result.rows[0]["provider_mappings"]] == ["autoapi", "autoapitwo"]
    assert result.rows[0]["model"] == "FIXTURE SEDAN" and result.rows[0]["source_region"] == "US"
    assert calls == [(0, "banktwo", "models", "Fixture-Truck", None), (6, "bankone", "models", "fixture-truck", None)]
    assert [(event[0], event[1]) for event in old_calls] == [(0, "bankone"), (6, "banktwo")]
    assert control.requests == old_control.requests == 2 and control.rows == old_control.rows == 4
    assert len(proofs) == 1
    emitted_at, partial = progress[0]
    assert emitted_at == .125 and not partial.complete
    assert {row["model"] for row in partial.rows} == {"FIXTURE SEDAN", "banktwo only"}
    assert [(row["provider"], row["source_version"]) for row in partial.provenance] == [("autoapitwo", "revision-1")]


@pytest.mark.parametrize(("first_read", "expected"), (
    ("404", [(0, "banktwo", "models", "Fixture-Truck", None), (6, "bankone", "models", "fixture-truck", None),
             (12, "banktwo", "makes", None, None), (18, "banktwo", "models", "Fixture Truck", None)]),
    ("paginated", [(0, "banktwo", "models", "Fixture-Truck", None), (6, "bankone", "models", "fixture-truck", None),
                   (12, "banktwo", "models", "Fixture-Truck", "page-2")]),
    ("timeout", [(0, "banktwo", "models", "Fixture-Truck", None), (6, "bankone", "models", "fixture-truck", None),
                 (12, "banktwo", "models", "Fixture-Truck", None)]),
))
def test_preferred_read_falls_back_without_repeating_definite_results(monkeypatch, first_read, expected):
    resolve, calls, progress, control, proofs = _selector(monkeypatch, banktwo_first=first_read)
    result = resolve()
    assert calls == expected and control.requests == len(expected)
    assert len(proofs) == 1 and result.complete and len(result.rows) == 3
    assert progress[0][0] == 6.125
    assert progress[0][1].provenance[0]["provider"] == "autoapi"


def test_no_current_label_proves_the_banktwo_make_after_bankone(monkeypatch):
    resolve, calls, progress, control, proofs = _selector(monkeypatch, label=None)
    assert resolve().complete
    assert calls == [(0, "bankone", "models", "fixture-truck", None), (6, "banktwo", "makes", None, None),
                     (12, "banktwo", "models", "Fixture Truck", None)]
    assert progress[0][0] == .125 and control.requests == 3 and len(proofs) == 1


def test_rate_limit_on_the_preferred_read_stops_the_shared_job(monkeypatch):
    resolve, calls, progress, control, _ = _selector(monkeypatch, banktwo_first="429")
    with pytest.raises(SelectorJobStopped, match="^rate_limited$"):
        resolve()
    assert calls == [(0, "banktwo", "models", "Fixture-Truck", None)] and control.requests == 1
    assert not progress


def test_owned_job_persists_early_choices_then_complete_suppliers(fresh_database, monkeypatch):
    repo = fresh_database(through=42)
    with repo.connect() as db:
        address = f"{db.info.hostaddr or db.info.host}:{db.info.port}"
    for name, value in {
        "AUTODATA_DB_ADDRESS": address, "AUTODATA_POSTGRES_DB": repo.database_name,
        "AUTODATA_POSTGRES_USER": "lifecycle_test", "AUTODATA_POSTGRES_PASSWORD": "lifecycle_test_only",
        "AUTODATA_SOURCE_PERSIST": "1",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(selector_job, "ADMISSION", selector_job.SelectorAdmission())
    monkeypatch.setattr(catalog, "_HYDRATION_RESULTS", {})
    seen = []

    class Connector(BaseHTTPRequestHandler):
        def do_GET(self):
            bank = self.server.bank
            url = urlsplit(self.path)
            seen.append((bank, url.path, parse_qs(url.query)["make"][0], monotonic()))
            model = {"bankone": "Bankone Fixture", "banktwo": "Banktwo Fixture"}[bank]
            item = {"year": 2021, "make": "Fixture-Truck", "model": model, "label": model,
                    "opaque_ref": bank + "-model"}
            body = json.dumps(_envelope(bank, scope="models", items=[item], complete=True, next_cursor=None)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    with ExitStack() as stack:
        for bank in ("bankone", "banktwo"):
            source = stack.enter_context(ThreadingHTTPServer(("127.0.0.1", 0), Connector))
            source.bank = bank
            Thread(target=source.serve_forever, daemon=True).start()
            stack.callback(source.shutdown)
            origin = f"http://127.0.0.1:{source.server_port}"
            monkeypatch.setenv(bank.upper() + "_BASE_URL", origin)
        proof = {"provider": "autoapitwo", "metadata": {
            "coverage_basis": catalog._BANKTWO_MAKE_COVERAGE, "connector_origin": origin,
            "verified_at": "2026-11-27T00:00:00Z", "exact_make_labels": {"fixture-truck": "Fixture-Truck"},
        }}
        catalog._persist_hydration_scope({"scope": "makes", "year": 2021, "region": "US"},
                                         catalog.CatalogResult((), True, provenance=(proof,)))
        request = {"scope": "models", "year": 2021, "make": "fixture-truck", "region": "US",
                   "idempotency_key": "fixture-models"}
        with ThreadPoolExecutor() as work, repo.connect() as db:
            started = monotonic()
            pending = work.submit(catalog.ensure_catalog_hydration, json.dumps(request))
            query = "SELECT selector_rows, completion_version FROM vehicle_catalog_hydration_scopes WHERE scope='models'"
            while (partial := db.execute(query).fetchone()) is None and monotonic() - started < 5:
                sleep(.035)
            assert partial is not None and monotonic() - started < 5
            assert [item["model"] for item in partial["selector_rows"]] == ["Banktwo Fixture"]
            assert partial["completion_version"] == 0 and not pending.done()
            assert [(bank, path, make) for bank, path, make, _ in seen] == [
                ("banktwo", "/v1/catalog/models", "Fixture-Truck"),
            ]
            resolved = pending.result(timeout=15)
            assert resolved["complete"] and resolved["status"] == "hydrated"
            final = db.execute(query).fetchone()
            assert final["completion_version"] == 1
            assert [item["model"] for item in final["selector_rows"]] == ["Bankone Fixture", "Banktwo Fixture"]
        assert [(bank, path, make) for bank, path, make, _ in seen] == [
            ("banktwo", "/v1/catalog/models", "Fixture-Truck"),
            ("bankone", "/v1/catalog/models", "fixture-truck"),
        ]
        assert seen[1][3] - seen[0][3] >= 5.9
