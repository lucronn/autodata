import sys
import unittest
import json
import os
import hashlib
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.catalog_service import (
    _ArticleCatalogProgress,
    CatalogRequest,
    CatalogResult,
    CacheFirstCatalogService,
    _engine_number,
    _persist_hydration_scope,
    _source_failure_detail,
    _find_source_article,
    _load_autoapitwo_article_catalog,
    _load_autoapitwo_article_detail,
    _configured_catalog_providers,
    canonical_catalog_id,
    ensure_catalog_hydration,
)


class CatalogServiceTests(unittest.TestCase):
    def test_catalog_provider_configuration_ignores_legacy_base_urls(self):
        with patch("autodata_ingestion.source_connector_client.source_connector_registry", return_value={}), \
                patch.dict(os.environ, {
                    "AUTODATA_AUTOAPI_BASE_URL": "https://old-bankone.test",
                    "AUTODATA_AUTOAPITWO_BASE_URL": "https://old-banktwo.test",
                }, clear=True):
            self.assertEqual(_configured_catalog_providers(), ())

    def test_article_catalog_progress_throttles_durable_writes_by_count_and_time(self):
        request = {"vehicle_id": "vehicle-1", "year": 2012, "make": "Ram", "model": "Ram 1500 Ds"}
        payload = {
            "phase": "normalizing",
            "total_units": 1000,
            "current_article_id": "article",
            "current_title": "Article",
        }
        with patch("autodata_ingestion.catalog_service._update_article_catalog_progress") as update, \
                patch("autodata_ingestion.catalog_service.time.monotonic", side_effect=[0.0, 0.1, 0.1, 0.6]):
            progress = _ArticleCatalogProgress(request)
            progress.publish({**payload, "processed_units": 0}, force=True)
            progress.publish({**payload, "processed_units": 1})
            progress.publish({**payload, "processed_units": 100})
            progress.publish({**payload, "processed_units": 101})

        self.assertEqual(update.call_count, 3)
        self.assertEqual(
            [call.kwargs["processed_units"] for call in update.call_args_list],
            [0, 100, 101],
        )

    def test_source_failure_detail_names_source_and_outcome(self):
        self.assertEqual(
            _source_failure_detail('AutoAPI', RuntimeError('expired authentication token')),
            'AutoAPI failed — authentication expired or unauthorized.',
        )
        self.assertEqual(
            _source_failure_detail('AutoAPItwo', RuntimeError('server timed out')),
            'AutoAPItwo failed — server timed out.',
        )
        self.assertEqual(
            _source_failure_detail('AutoAPItwo', RuntimeError('AutoAPItwo did not resolve a matching vehicle')),
            'AutoAPItwo failed — returned no matching vehicle.',
        )
        self.assertIn("more than one", _source_failure_detail("AutoAPItwo", RuntimeError("source connector ambiguous")))

    def test_generic_banktwo_article_index_preserves_page_order_and_lineage(self):
        from autodata_ingestion.source_connector_client import SourceEnvelopeV1

        page_one = SourceEnvelopeV1(
            "request-1", "banktwo", "revision-7", "2026-10-08T12:00:00Z", "https://banktwo.test/catalog",
            {"complete": False, "next_cursor": "cursor-2", "articles": [
                {"opaque_ref": "article-2", "title": "Second", "resource_ref": "resource-2"},
            ]},
        )
        page_two = SourceEnvelopeV1(
            "request-2", "banktwo", "revision-7", "2026-10-08T12:00:01Z", "https://banktwo.test/catalog?page=2",
            {"complete": True, "articles": [
                {"opaque_ref": "article-1", "title": "First", "resource_ref": "resource-1"},
            ]},
        )

        class Connector:
            provider = "banktwo"
            base_url = "https://banktwo.test"

            def __init__(self):
                self.cursors = []

            def resolve_vehicle(self, selector):
                self.selector = selector
                return SourceEnvelopeV1(
                    "resolve-1", "banktwo", "revision-7", "2026-10-08T12:00:00Z", None,
                    {"candidates": [{"opaque_ref": "vehicle/ref-1", "label": "2.0L Sport", "confidence": 1.0}]},
                )

            def list_articles(self, source_vehicle_ref, cursor=None):
                self.cursors.append((source_vehicle_ref, cursor))
                return page_one if cursor is None else page_two

        connector = Connector()
        with patch("autodata_ingestion.source_connector_client.source_connector_registry", return_value={"banktwo": connector}), \
                patch.dict(os.environ, {"AUTODATA_SOURCE_PERSIST": "0"}):
            records, metadata = _load_autoapitwo_article_catalog(
                {"year": 2020},
                {"model_year": 2020, "year": 2020, "make": "Example", "model": "Sedan", "region": "US", "engine": "2.0L"},
            )

        self.assertEqual(connector.selector["configuration"], "2.0L")
        self.assertEqual(connector.cursors, [("vehicle/ref-1", None), ("vehicle/ref-1", "cursor-2")])
        self.assertEqual([row["article"]["article_id"] for row in records], [
            "autoapitwo:vehicle/ref-1:article-2", "autoapitwo:vehicle/ref-1:article-1",
        ])
        self.assertEqual(metadata["index_read_count"], 2)

    def test_generic_banktwo_selected_article_reads_original_resources_and_keeps_id(self):
        from autodata_ingestion.source_bundle import SourceBundle
        from autodata_ingestion.source_connector_client import SourceEnvelopeV1
        from autodata_ingestion.source_adapters import SourceResource

        raw_article = b'{"kind":"article","article_id":"new-id","title":"Oil pump"}'
        raw_labor = b'{"operations":[{"name":"Replace oil pump"}]}'

        def resource(ref, kind, body):
            raw = raw_article if ref == "article-resource" else raw_labor
            return SourceEnvelopeV1(
                f"request-{ref}", "banktwo", "revision-9", "2026-10-08T12:00:00Z",
                f"https://banktwo.test/source/{ref}",
                {"kind": kind, "media_type": "application/json", "sha256": hashlib.sha256(raw).hexdigest()},
                resource_uri=ref, raw_resource=raw,
            )

        class Connector:
            provider = "banktwo"
            base_url = "https://banktwo.test"

            def __init__(self):
                self.reads = []

            def resolve_vehicle(self, _selector):
                return SourceEnvelopeV1(
                    "resolve-1", "banktwo", "revision-9", "2026-10-08T12:00:00Z", None,
                    {"candidates": [{"opaque_ref": "vehicle/ref-1", "label": "Exact", "confidence": 1.0}]},
                )

            def list_articles(self, _source_vehicle_ref, cursor=None):
                return SourceEnvelopeV1(
                    "list-1", "banktwo", "revision-9", "2026-10-08T12:00:00Z", None,
                    {"complete": True, "articles": [{
                        "opaque_ref": "article-1", "title": "Oil pump", "resource_ref": "article-resource",
                        "labor_resource_ref": "labor-resource",
                    }]},
                )

            def read_resource(self, ref):
                self.reads.append(ref)
                return resource(ref, "article" if ref == "article-resource" else "labor", {})

        connector = Connector()
        observed = []
        bundle = SourceBundle(
            status="complete", vehicle={"vehicle_key": "vehicle:1"}, specifications=(), models=(),
            powertrains=(), parts=(), articles=({"article_id": "new-id", "title": "Oil pump", "evidence_id": "e1"},),
            documents=(), diagrams=(), evidence=({"evidence_id": "e1"},), quarantined=(), conflicts=(),
        )
        request = {
            "year": 2013, "make": "Honda", "model": "Accord", "region": "US",
            "source_article_id": "autoapitwo:old-vehicle-ref:article-1", "title": "Oil pump",
        }
        vehicle = {"model_year": 2013, "year": 2013, "make": "Honda", "model": "Accord", "region": "US"}
        with patch("autodata_ingestion.source_connector_client.source_connector_registry", return_value={"banktwo": connector}), \
                patch("autodata_ingestion.source_adapters.adapt_source_resource", side_effect=lambda item: observed.append(item) or item), \
                patch("autodata_ingestion.source_bundle.normalize_source_bundle", return_value=bundle), \
                patch("autodata_ingestion.procedure_normalize.normalize_procedure_article", side_effect=lambda item: dict(item)), \
                patch("autodata_ingestion.procedure_images.localize_procedure_images", side_effect=lambda item, vehicle: item), \
                patch.dict(os.environ, {"AUTODATA_SOURCE_PERSIST": "0"}):
            rows, metadata = _load_autoapitwo_article_detail(request, vehicle)

        self.assertEqual(connector.reads, ["article-resource", "labor-resource"])
        self.assertEqual([item.payload for item in observed], [raw_article, raw_labor])
        self.assertEqual([item.content_sha256 for item in observed], [hashlib.sha256(raw_article).hexdigest(), hashlib.sha256(raw_labor).hexdigest()])
        self.assertEqual([item.locator for item in observed], ["https://banktwo.test/source/article-resource", "https://banktwo.test/source/labor-resource"])
        self.assertEqual(rows[0]["article"]["article_id"], request["source_article_id"])
        self.assertEqual(metadata["content_source"], "autoapitwo")

    def test_legacy_banktwo_article_suffix_must_match_one_descriptor(self):
        from autodata_ingestion.source_connector_client import SourceConnectorError, SourceEnvelopeV1

        class Connector:
            def list_articles(self, _vehicle_ref, _cursor=None):
                return SourceEnvelopeV1(
                    "list-1", "banktwo", "revision-1", "2026-10-08T12:00:00Z", "https://banktwo.test/articles",
                    {"complete": True, "articles": [
                        {"opaque_ref": "article:1535667", "title": "Oil pump", "resource_ref": "r1"},
                        {"opaque_ref": "other:1535667", "title": "Oil pump alternate", "resource_ref": "r2"},
                    ]},
                )

        with self.assertRaises(SourceConnectorError) as caught:
            _find_source_article(
                Connector(), "vehicle/opaque",
                {"source_article_id": "autoapitwo:52597:1535667"},
            )
        self.assertEqual(caught.exception.code, "AMBIGUOUS")

    def test_generic_vehicle_resolution_rejects_ambiguous_source_candidates(self):
        from autodata_ingestion.source_connector_client import SourceConnectorError, SourceEnvelopeV1

        class Connector:
            def resolve_vehicle(self, _selector):
                return SourceEnvelopeV1(
                    "resolve-ambiguous", "banktwo", "revision-1", "2026-10-08T12:00:00Z", None,
                    {"candidates": [
                        {"opaque_ref": "candidate-1", "label": "Base", "confidence": 0.8},
                        {"opaque_ref": "candidate-2", "label": "Sport", "confidence": 0.8},
                    ]},
                )

        with self.assertRaises(SourceConnectorError) as caught:
            from autodata_ingestion.catalog_service import _resolve_source_vehicle_ref
            _resolve_source_vehicle_ref(Connector(), {}, {"year": 2020, "make": "Example", "model": "Sedan"})
        self.assertEqual(caught.exception.code, "AMBIGUOUS")

    def test_generic_article_search_rejects_duplicate_exact_titles(self):
        from autodata_ingestion.source_connector_client import SourceConnectorError, SourceEnvelopeV1
        from autodata_ingestion.catalog_service import _find_source_article

        class Connector:
            def search_articles(self, source_vehicle_ref, query, cursor=None):
                self.asserted = (source_vehicle_ref, query, cursor)
                return SourceEnvelopeV1(
                    "search-1", "banktwo", "revision-1", "2026-10-08T12:00:00Z", None,
                    {"complete": True, "articles": [
                        {"opaque_ref": "article-1", "title": "Oil pump"},
                        {"opaque_ref": "article-2", "title": "Oil pump"},
                    ]},
                )

        connector = Connector()
        with self.assertRaises(SourceConnectorError) as caught:
            _find_source_article(connector, "vehicle-ref", {"title": "Oil pump"})
        self.assertEqual(caught.exception.code, "AMBIGUOUS")
        self.assertEqual(connector.asserted, ("vehicle-ref", "Oil pump", None))

    def test_engine_number_prefers_displacement_in_provider_engine_label(self):
        self.assertEqual(_engine_number("L4-2.4L (K24W1)"), 2.4)
        self.assertEqual(_engine_number("V6-3.5L (J35Y2)"), 3.5)

    def test_complete_cache_is_returned_without_calling_provider(self):
        provider_calls = []
        service = CacheFirstCatalogService(
            cache_reader=lambda _request: {
                "complete": True,
                "rows": [{"year": 2024, "make": "Toyota", "model": "RAV4", "region": "US"}],
                "provenance": [{"provider": "autoapi", "uri": "db://cached"}],
            },
            providers=[lambda _request: provider_calls.append(True)],
        )

        result = service.resolve(CatalogRequest(2024, "Toyota", "RAV4"))

        self.assertTrue(result.cache_hit)
        self.assertTrue(result.complete)
        self.assertEqual(provider_calls, [])
        self.assertEqual(result.rows[0]["catalog_id"], canonical_catalog_id(result.rows[0]))

    def test_incomplete_cache_hydrates_and_merges_provider_rows_and_provenance(self):
        provider_calls = []

        def autoapi(_request):
            provider_calls.append("autoapi")
            return {
                "complete": False,
                "missing_scopes": ["engine"],
                "rows": [{"year": 2024, "make": "Toyota", "model": "RAV4", "region": "US"}],
                "provenance": [{"provider": "autoapi", "uri": "https://autoapi.test/a", "hash": "a"}],
            }

        def autoapitwo(_request):
            provider_calls.append("autoapitwo")
            return {
                "complete": True,
                "rows": [{
                    "year": 2024, "make": "Toyota", "model": "RAV4", "region": "US",
                    "engine": 2.5, "trim": "XLE",
                }],
                "provenance": [{"provider": "autoapitwo", "uri": "https://autoapitwo.test/b", "hash": "b"}],
            }

        written = []
        service = CacheFirstCatalogService(
            cache_reader=lambda _request: {"complete": False, "rows": [], "missing_scopes": ["model"]},
            providers=[autoapi, autoapitwo],
            cache_writer=written.append,
        )

        result = service.resolve(CatalogRequest(2024, "Toyota", "RAV4"))

        self.assertEqual(provider_calls, ["autoapi", "autoapitwo"])
        self.assertTrue(result.complete)
        self.assertEqual(len(result.rows), 2)
        self.assertEqual({item["provider"] for item in result.provenance}, {"autoapi", "autoapitwo"})
        self.assertEqual(written[0], result)
        self.assertTrue(all("provider" not in row.get("raw", {}) for row in result.rows))

    def test_configurations_require_all_providers_and_preserve_partial_rows(self):
        from autodata_ingestion.source_connector_client import SourceConnectorError

        row = {"year": 2020, "make": "Honda", "model": "Accord", "region": "US", "engine": "2.0L"}
        for failed in (False, True):
            with self.subTest(failed=failed):
                def unfinished(_request):
                    if failed:
                        raise SourceConnectorError("UPSTREAM_UNAVAILABLE", retryable=True, status=502)
                    return {"rows": [row], "complete": False, "missing_scopes": ["configurations"]}
                written = []
                result = CacheFirstCatalogService(
                    cache_reader=lambda _: {"rows": [row], "complete": False},
                    providers=[unfinished, lambda _: {"rows": [], "complete": True, "missing_scopes": []}],
                    cache_writer=written.append,
                ).resolve(CatalogRequest(2020, "Honda", "Accord", scope="configurations"))
                self.assertFalse(result.complete)
                self.assertEqual(len(result.rows), 1)
                self.assertEqual(result.rows[0]["model"], "Accord")
                self.assertIn("configurations", result.missing_scopes)
                if failed:
                    self.assertIn("provider", result.missing_scopes)
                self.assertEqual(written, [result])

    def test_http_hydration_replays_the_same_idempotent_result(self):
        request = json.dumps({
            "scope": "models",
            "idempotency_key": "catalog-http-replay-1",
            "year": 2024,
            "make": "Toyota",
            "model": "RAV4",
        })

        first = ensure_catalog_hydration(request)
        second = ensure_catalog_hydration(request)

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "accepted")
        self.assertEqual(first["missing_scopes"], ["models"])

    def test_selector_ensure_logs_redacted_failure_stage(self):
        from autodata_ingestion import catalog_service

        scenarios = (
            ("resolve", "resolve", RuntimeError("provider-secret-url"), "RuntimeError"),
            ("coverage_persistence", "_persist_hydration_scope", OSError("database-secret-dsn"), "OSError"),
        )
        for stage, failing_operation, failure, error_type in scenarios:
            with self.subTest(stage=stage):
                request = json.dumps({
                    "scope": "makes",
                    "year": 2024,
                    "region": "US",
                    "idempotency_key": f"caller-secret-{stage}",
                })
                with patch.object(catalog_service, "_configured_catalog_providers", return_value=(object(),)), \
                        patch.object(catalog_service.CacheFirstCatalogService, "resolve", return_value=CatalogResult(rows=(), complete=False, missing_scopes=("makes",))) as resolve, \
                        patch.object(catalog_service, "_persist_resolved_catalog_rows", return_value={"status": "no_persistable_rows", "row_count": 0}), \
                        patch.object(catalog_service, "_persist_hydration_scope", return_value={"status": "persisted"}) as persist:
                    operation = resolve if failing_operation == "resolve" else persist
                    operation.side_effect = failure
                    with self.assertLogs("autodata_ingestion.catalog_service", level="ERROR") as captured:
                        with self.assertRaises(type(failure)):
                            ensure_catalog_hydration(request)
                self.assertEqual(len(captured.output), 1)
                self.assertIn("scope=makes", captured.output[0])
                self.assertIn(f"stage={stage}", captured.output[0])
                self.assertIn(f"error_type={error_type}", captured.output[0])
                self.assertNotIn(str(failure), captured.output[0])
                self.assertNotIn("caller-secret-", captured.output[0])

    def test_selector_ensure_does_not_log_invalid_request_as_dependency_failure(self):
        from autodata_ingestion import catalog_service

        request = json.dumps({
            "scope": "makes",
            "year": 1750,
            "region": "US",
            "idempotency_key": "invalid-year-request",
        })
        with patch.object(catalog_service, "_configured_catalog_providers", return_value=(object(),)):
            with self.assertNoLogs("autodata_ingestion.catalog_service", level="ERROR"):
                with self.assertRaises(ValueError):
                    ensure_catalog_hydration(request)

    def test_http_hydration_complete_cache_is_provider_free(self):
        result = ensure_catalog_hydration(json.dumps({
            "scope": "configurations",
            "idempotency_key": "catalog-http-cache-1",
            "cache": {
                "complete": True,
                "rows": [{"year": 2024, "make": "Toyota", "model": "RAV4", "region": "US"}],
            },
        }))

        self.assertEqual(result["status"], "cache_hit")
        self.assertTrue(result["complete"])
        self.assertEqual(len(result["rows"]), 1)

    def test_article_scope_does_not_fall_back_to_full_provider_snapshot(self):
        class SnapshotOnlyProvider:
            def __init__(self):
                self.calls = []

            def fetch_catalog_snapshot(self):
                self.calls.append("snapshot")
                raise AssertionError("article scope must not call a full snapshot")

            def fetch_catalog(self):
                self.calls.append("catalog")
                raise AssertionError("article scope must not call full catalog")

        provider = SnapshotOnlyProvider()
        service = CacheFirstCatalogService(
            cache_reader=lambda _request: {"complete": False, "rows": []},
            providers=[provider],
        )

        result = service.resolve(
            CatalogRequest(1999, "Toyota Truck", "4 Runner 4wd", scope="articles")
        )

        self.assertFalse(result.complete)
        self.assertEqual(provider.calls, [])
        self.assertEqual(result.missing_scopes, ("provider",))


    def test_persist_hydration_scope_allows_empty_complete_provider_reads(self):
        import sys
        from types import ModuleType
        from unittest.mock import MagicMock

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            def execute(self, *_args, **_kwargs):
                return None

        class Connection:
            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            def cursor(self):
                return Cursor()

            def commit(self):
                return None

        connect = MagicMock(return_value=Connection())
        jsonb_mod = ModuleType("psycopg.types.json")
        jsonb_mod.Jsonb = lambda value: value
        types_mod = ModuleType("psycopg.types")
        types_mod.json = jsonb_mod
        psycopg_mod = ModuleType("psycopg")
        psycopg_mod.connect = connect
        psycopg_mod.types = types_mod

        request = {
            "scope": "configurations",
            "year": 2026,
            "make": "Dodge",
            "model": "Charger R T 4 Door",
            "region": "US",
        }
        result = CatalogResult(rows=(), complete=True, provenance=())
        with patch.dict(os.environ, {"AUTODATA_SOURCE_PERSIST": "1"}), patch(
            "autodata_ingestion.catalog_sync._conninfo", return_value={}
        ), patch.dict(
            sys.modules,
            {
                "psycopg": psycopg_mod,
                "psycopg.types": types_mod,
                "psycopg.types.json": jsonb_mod,
            },
        ):
            coverage = _persist_hydration_scope(request, result)

        self.assertEqual(coverage["status"], "persisted")
        self.assertIn("configurations|2026|dodge|charger r t 4 door|US", coverage["scope_key"])
        connect.assert_called_once()


if __name__ == "__main__":
    unittest.main()


def test_lifecycle_ensure_ignores_fabricated_process_cache_and_never_calls_banks(fresh_database,monkeypatch):
    from lifecycle_support import seed_vehicle,insert_descriptor
    from autodata_ingestion.article_lifecycle_types import ArticleKey
    import autodata_ingestion.catalog_service as service
    repo=fresh_database();vehicle=seed_vehicle(repo)
    article=insert_descriptor(repo,ArticleKey("bankone",vehicle,None,"opaque:v","opaque:a"))
    monkeypatch.setattr("autodata_ingestion.worker.ArticleRepository",lambda:repo)
    def never(*args,**kwargs):pytest.fail("ensure called provider")
    monkeypatch.setattr(service,"_hydrate_article_catalog",never)
    request={"scope":"article","vehicle_id":str(vehicle),"canonical_article_id":str(article),"idempotency_key":"same"}
    service._HYDRATION_RESULTS["same"]=(0,{"complete":True,"rows":[{"forged":True}]})
    first=service.ensure_catalog_hydration(json.dumps(request))
    second=service.ensure_catalog_hydration(json.dumps(request))
    assert first==second
    assert set(first)=={"job_id","state","canonical_article_id","source_revision_id","retry_after_seconds"}
    assert first["state"]=="queued" and first.http_status==202
    with repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM source_fetch_jobs").fetchone()["n"]==1


from lifecycle_support import fresh_database
import pytest


@pytest.mark.parametrize("states,retryable,http_status,state",[
    (("completed","completed"),False,200,"completed"),
    (("needs_review","needs_review"),False,409,"needs_review"),
    (("completed","needs_review"),False,409,"needs_review"),
    (("completed","dead_letter"),False,409,"failed"),
    (("completed","failed"),False,409,"failed"),
    (("completed","failed"),True,202,"queued"),
    (("completed","processing"),False,202,"queued"),
    (("pending","needs_review"),False,202,"queued"),
])
def test_catalog_acknowledgment_reports_all_provider_outcomes(fresh_database,states,retryable,http_status,state):
    from uuid import uuid4
    from lifecycle_support import seed_vehicle
    from autodata_ingestion.catalog_coverage import ensure_article_catalog_jobs
    from autodata_ingestion.catalog_service import _ensure_lifecycle_catalog
    repo=fresh_database();vehicle=seed_vehicle(repo)
    results=ensure_article_catalog_jobs(repo,vehicle_id=vehicle,vehicle_configuration_id=None)
    with repo.connect() as conn:
        for result,status in zip(results,states):
            conn.execute("""UPDATE source_fetch_jobs SET status=%s,phase=CASE WHEN %s='completed' THEN 'completed' ELSE 'fetching_source' END,
                retryable=%s,next_attempt_at=CASE WHEN %s THEN clock_timestamp()+interval '1 minute' ELSE NULL END,
                lease_owner=%s,lease_token=%s,lease_expires_at=CASE WHEN %s THEN clock_timestamp()+interval '90 seconds' ELSE NULL END,
                heartbeat_at=CASE WHEN %s THEN clock_timestamp() ELSE NULL END WHERE source_fetch_job_id=%s""",
                (status,status,retryable and status=='failed',retryable and status=='failed',uuid4() if status=='processing' else None,1 if status=='processing' else 0,status=='processing',status=='processing',result.job_id))
    ack=_ensure_lifecycle_catalog({"scope":"articles","vehicle_id":str(vehicle)},repo=repo)
    assert ack.http_status==http_status and ack["state"]==state
    assert [row["job_id"] for row in ack["jobs"]]==[str(result.job_id) for result in results]
    assert [row["state"] for row in ack["jobs"]]==[{"pending":"queued","dead_letter":"failed"}.get(status,status) for status in states]
    if retryable:assert 0<ack["jobs"][1]["retry_after_seconds"]<=60


def test_unconfigured_catalog_workers_return_terminal_review_ack(fresh_database):
    from uuid import uuid4
    from lifecycle_support import seed_vehicle
    from autodata_ingestion.catalog_coverage import ensure_article_catalog_jobs
    from autodata_ingestion.article_lifecycle import run_article_worker_once
    from autodata_ingestion.catalog_service import _ensure_lifecycle_catalog
    repo=fresh_database();vehicle=seed_vehicle(repo)
    ensure_article_catalog_jobs(repo,vehicle_id=vehicle,vehicle_configuration_id=None)
    for _ in range(2):assert run_article_worker_once(repo,worker_id=uuid4(),registry={},object_store=None,model_client=None)
    ack=_ensure_lifecycle_catalog({"scope":"articles","vehicle_id":str(vehicle)},repo=repo)
    assert ack.http_status==409 and ack["state"]=="needs_review"
    assert [row["state"] for row in ack["jobs"]]==["needs_review","needs_review"]


def test_total_catalog_deadline_rolls_back_first_bank_when_second_waits(runtime,monkeypatch):
    import threading,time
    from autodata_ingestion.worker import ArticleRepository
    from autodata_ingestion.catalog_service import _ensure_lifecycle_catalog,LifecycleSchedulingUnavailable
    for name,value in runtime.env.items():monkeypatch.setenv(name,value)
    repo=ArticleRepository()
    with repo.connect() as conn:
        conn.execute("UPDATE catalog_article_provider_scopes SET current_job_id=NULL,generation=generation+1,status='pending' WHERE vehicle_id=%s AND provider_slug='bankone'",(runtime.vehicle,))
        before=conn.execute("SELECT count(*) AS n FROM source_fetch_jobs").fetchone()["n"]
    with repo.connect() as first,repo.connect() as second:
        first.execute("SELECT * FROM catalog_article_provider_scopes WHERE vehicle_id=%s AND provider_slug='bankone' FOR UPDATE",(runtime.vehicle,)).fetchall()
        second.execute("SELECT * FROM catalog_article_provider_scopes WHERE vehicle_id=%s AND provider_slug='banktwo' FOR UPDATE",(runtime.vehicle,)).fetchall()
        outcome={}
        def call():
            started=time.monotonic()
            try:outcome["ack"]=_ensure_lifecycle_catalog({"scope":"articles","vehicle_id":str(runtime.vehicle)},repo=repo)
            except Exception as error:outcome["error"]=error
            outcome["seconds"]=time.monotonic()-started
        thread=threading.Thread(target=call);thread.start()
        try:
            time.sleep(1.1);first.commit()
            time.sleep(1.1);second.commit()
        finally:
            first.rollback();second.rollback();thread.join(4)
    assert not thread.is_alive()
    assert outcome["seconds"]<=2,outcome
    assert isinstance(outcome.get("error"),LifecycleSchedulingUnavailable),outcome
    with repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM source_fetch_jobs").fetchone()["n"]==before
        assert conn.execute("SELECT current_job_id FROM catalog_article_provider_scopes WHERE vehicle_id=%s AND provider_slug='bankone'",(runtime.vehicle,)).fetchone()["current_job_id"] is None


def test_connection_completing_after_total_deadline_cannot_schedule(fresh_database):
    import threading,time
    from lifecycle_support import seed_vehicle
    from autodata_ingestion.catalog_service import _ensure_lifecycle_catalog,LifecycleSchedulingUnavailable
    repo=fresh_database();vehicle=seed_vehicle(repo)
    release=threading.Event();connected=threading.Event()
    class DelayedRepository:
        def connect(self):
            release.wait(3)
            conn=repo.connect();connected.set()
            return conn
    started=time.monotonic()
    try:
        with pytest.raises(LifecycleSchedulingUnavailable):
            _ensure_lifecycle_catalog({"scope":"articles","vehicle_id":str(vehicle)},repo=DelayedRepository())
        assert time.monotonic()-started<=2
    finally:release.set()
    assert connected.wait(3)
    time.sleep(.05)
    with repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM catalog_article_provider_scopes").fetchone()["n"]==0
        assert conn.execute("SELECT count(*) AS n FROM source_fetch_jobs").fetchone()["n"]==0


from lifecycle_support import runtime


def test_timeout_revokes_commit_authority_after_precommit_check(fresh_database):
    import threading,time
    from lifecycle_support import seed_vehicle
    from autodata_ingestion.catalog_service import _ensure_lifecycle_catalog,LifecycleSchedulingUnavailable
    repo=fresh_database();vehicle=seed_vehicle(repo)
    arrived=threading.Event();release=threading.Event();finished=threading.Event()
    class DelayedCommit:
        def __init__(self,conn):self.conn=conn
        def __getattr__(self,key):return getattr(self.conn,key)
        def __enter__(self):self.conn.__enter__();return self
        def __exit__(self,*args):
            # Bounded barrier simulates descheduling/network pause immediately before
            # COMMIT, after the scheduling wrapper's last deadline check.
            arrived.set();release.wait(4)
            try:return self.conn.__exit__(*args)
            finally:finished.set()
    class PausedRepository:
        calls=0
        def connect(self):
            self.calls+=1
            conn=repo.connect()
            return DelayedCommit(conn) if self.calls==2 else conn
    try:
        with pytest.raises(LifecycleSchedulingUnavailable):
            _ensure_lifecycle_catalog({'scope':'articles','vehicle_id':str(vehicle)},repo=PausedRepository())
        assert arrived.is_set()
        # Allow cancellation to finish while the connection is idle in transaction.
        time.sleep(.2)
    finally:release.set()
    assert finished.wait(3)
    with repo.connect() as conn:
        assert conn.execute('SELECT count(*) AS n FROM source_fetch_jobs').fetchone()['n']==0
        assert conn.execute('SELECT count(*) AS n FROM catalog_article_provider_scopes').fetchone()['n']==0
