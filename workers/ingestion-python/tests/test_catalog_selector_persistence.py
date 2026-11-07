"""Sparse selectors are durable without materializing synthetic vehicles."""
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

import pytest

from autodata_ingestion.catalog_service import (
    CacheFirstCatalogService, CatalogRequest, CatalogResult, _persist_hydration_scope,
)
from lifecycle_support import fresh_database, apply_migration


@pytest.mark.parametrize("scope", ["makes", "models"])
@pytest.mark.parametrize("failed_first", [False, True])
@pytest.mark.parametrize("failure", ["exception", "incomplete"])
def test_selector_completeness_requires_every_provider(scope, failed_first, failure):
    def failed(_):
        if failure == "exception":
            raise TimeoutError("source unavailable")
        return {"complete": False, "missing_scopes": [scope], "rows": []}

    def complete(_):
        return {"complete": True, "rows": [{"year": 2020, "make": "Ford", "model": "Focus"}]}

    providers = [failed, complete] if failed_first else [complete, failed]
    result = CacheFirstCatalogService(
        cache_reader=lambda _: {"complete": False, "missing_scopes": [scope]},
        providers=providers,
    ).resolve(CatalogRequest(2020, "Ford", "unknown", scope=scope))
    assert not result.complete
    assert result.missing_scopes
    assert len(result.rows) == 1


def test_selector_complete_empty_sources_clear_stale_cache_missing():
    result = CacheFirstCatalogService(
        cache_reader=lambda _: {"complete": False, "missing_scopes": ["makes"]},
        providers=[lambda _: {"complete": True, "rows": []}] * 2,
    ).resolve(CatalogRequest(2014, "unknown", "unknown", scope="makes"))
    assert result.complete and not result.rows and not result.missing_scopes


def test_sparse_scope_rows_and_version_upgrade(fresh_database, monkeypatch):
    repo = fresh_database(through=41)
    with repo.connect() as conn:
        conn.execute("""INSERT INTO vehicle_catalog_hydration_scopes
            (scope_key,scope,model_year,region) VALUES ('makes|2014|||US','makes',2014,'US')""")
    apply_migration(repo, 42)
    with repo.connect() as conn:
        row = conn.execute("SELECT selector_rows,completion_version FROM vehicle_catalog_hydration_scopes").fetchone()
        assert row == {"selector_rows": [], "completion_version": 0}
    monkeypatch.setattr("autodata_ingestion.catalog_sync._conninfo", lambda: {
        "host": "postgres", "dbname": repo.database_name, "user": "lifecycle_test", "password": "lifecycle_test_only",
    })
    monkeypatch.setenv("AUTODATA_SOURCE_PERSIST", "1")
    request = {"scope": "makes", "year": 2014, "region": "US"}
    result = CatalogResult(rows=({"year": 2014, "make": "Ford"}, {"year": 2014, "make": "Saab"}), complete=True)
    _persist_hydration_scope(request, result)
    with repo.connect() as conn:
        row = conn.execute("SELECT selector_rows,completion_version FROM vehicle_catalog_hydration_scopes").fetchone()
        assert row["completion_version"] == 1
        assert {r["make"] for r in row["selector_rows"]} == {"Ford", "Saab"}
        assert conn.execute("SELECT count(*) AS n FROM vehicle_identity_bases").fetchone()["n"] == 0
    partial = CatalogResult(rows=({"year": 2014, "make": "Volvo"},), complete=False, missing_scopes=("provider",))
    _persist_hydration_scope(request, partial)
    _persist_hydration_scope(request, partial)
    with repo.connect() as conn:
        row = conn.execute("SELECT selector_rows,completion_version FROM vehicle_catalog_hydration_scopes").fetchone()
        assert row["completion_version"] == 0
        assert len(row["selector_rows"]) == 3
    model_request = {"scope": "models", "year": 2020, "make": "Ford", "region": "US"}
    model_result = CatalogResult(rows=({"year": 2020, "make": "Ford", "model": "Bronco"},),
        complete=True, provenance=({"provider": "bankone", "source_uri": "fixture://models"},))
    _persist_hydration_scope(model_request, model_result)
    with repo.connect() as conn:
        row = conn.execute("SELECT selector_rows,completion_version,provenance FROM vehicle_catalog_hydration_scopes WHERE scope='models'").fetchone()
        assert row["selector_rows"] == [{"year": 2020, "make": "Ford", "model": "Bronco", "region": "US"}]
        assert row["completion_version"] == 1
        assert row["provenance"] == list(model_result.provenance)
    # Off-scope source rows must never be certified as a completed requested scope.
    with pytest.raises(ValueError):
        _persist_hydration_scope(request, CatalogResult(rows=({"year": 2027, "make": "Ford"},), complete=True))
    with pytest.raises(ValueError):
        _persist_hydration_scope({"scope": "models", "year": 2020, "make": "Ford", "region": "US"},
            CatalogResult(rows=({"year": 2020, "make": "Saab", "model": "900"},), complete=True))


def test_go_sparse_selector_store(fresh_database):
    repo = fresh_database()
    root = Path(__file__).resolve().parents[3]
    result = subprocess.run(["go", "test", "-run", "^TestPostgresSparseSelector", "-count=1", "./..."],
        cwd=root / "apps/api-go", env={**os.environ,
        "AUTODATA_SELECTOR_TEST_DSN": f"postgres://lifecycle_test:lifecycle_test_only@postgres:5432/{repo.database_name}?sslmode=disable"},
        capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr


def test_partial_selector_retry_is_bounded_then_replays_complete(monkeypatch):
    import autodata_ingestion.catalog_service as service

    clock = [0.0]
    healthy = [False]
    calls = []

    def first(_):
        calls.append("first")
        return {"complete": True, "rows": [{"year": 2020, "make": "Ford", "model": "Focus"}]}

    def second(_):
        calls.append("second")
        if not healthy[0]:
            raise TimeoutError("temporary source outage")
        return {"complete": True, "rows": [{"year": 2020, "make": "Ford", "model": "Bronco"}]}

    monkeypatch.setattr(service.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(service, "_configured_catalog_providers", lambda: (first, second))
    monkeypatch.setattr(service, "_persist_resolved_catalog_rows", lambda *a, **k: {})
    persisted = []
    monkeypatch.setattr(service, "_persist_hydration_scope", lambda request, result: persisted.append(result) or {})
    monkeypatch.setattr(service, "_schedule_selector_deepening", lambda *a: {})
    request = '{"scope":"models","year":2020,"make":"Ford","idempotency_key":"selector-retry-test"}'
    service._HYDRATION_RESULTS.pop("selector-retry-test", None)
    try:
        partial = service.ensure_catalog_hydration(request)
        assert not partial["complete"] and len(partial["rows"]) == 1
        clock[0] = 10.0
        assert service.ensure_catalog_hydration(request) == partial
        assert len(calls) == 2
        clock[0] = 21.0
        healthy[0] = True
        complete = service.ensure_catalog_hydration(request)
        assert complete["complete"] and len(complete["rows"]) == 2
        clock[0] = 1000.0
        assert service.ensure_catalog_hydration(request) == complete
        assert len(calls) == 4
        assert [result.complete for result in persisted] == [False, True]
    finally:
        service._HYDRATION_RESULTS.pop("selector-retry-test", None)
