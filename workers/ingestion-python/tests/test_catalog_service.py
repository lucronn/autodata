import sys
import unittest
import json
from hashlib import sha256
import os
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.catalog_service import (
    _ArticleCatalogProgress,
    CatalogRequest,
    CacheFirstCatalogService,
    _autoapitwo_car_ids,
    _autoapitwo_search_queries,
    _descriptor_href,
    _engine_number,
    _same_autoapitwo_vehicle,
    _source_failure_detail,
    _repair_stored_autoapitwo_article,
    canonical_catalog_id,
    ensure_catalog_hydration,
)


class CatalogServiceTests(unittest.TestCase):
    def test_source_repair_uses_snapshot_order_and_matches_idless_images_by_url_hash(self):
        first_url = "https://source.example/figure-1.png"
        second_url = "https://source.example/figure-2.png"
        source_article = {
            "id": "210265",
            "title": "Axle Shaft Bearing - Removal",
            "blocks": [
                {"type": "heading", "text": "Removal"},
                {"type": "text", "text": "Disconnect the connector."},
                {"type": "image", "url": first_url, "alt": "Connector location"},
                {"type": "text", "text": "Remove the bearing."},
                {"type": "image", "url": second_url, "alt": "Bearing location"},
            ],
            "images": [{"url": first_url}, {"url": second_url}],
        }
        source_bytes = json.dumps({
            "year": 2012, "make": "Ram", "model": "Ram 1500 DS", "region": "US",
            "articleDetails": [source_article],
        }, sort_keys=True, separators=(",", ":")).encode()
        legacy_article = {
            "article_id": "autoapitwo:50582:210265",
            "title": source_article["title"],
            "body": "Disconnect the connector. Remove the bearing.",
            "content_status": "content_complete",
            "source_original": {"keep": "byte-identical"},
            "steps": [{"number": 1, "heading": "Disconnect connector and remove bearing."}],
            "images": [],
            "normalized_document": {"schema_version": 1, "normalization_version": "ordered-article-v1", "blocks": []},
        }
        stored = {
            "catalog_article_id": "00000000-0000-0000-0000-000000000001",
            "vehicle_id": "00000000-0000-0000-0000-000000000002",
            "article": legacy_article,
            "object_key": "sources/test/snapshot",
            "snapshot_sha256": sha256(source_bytes).hexdigest(),
            "source_uri": "https://source.example/article/210265",
            "source_version": "autoapitwo-content-detail-v1",
        }
        vehicle = {"model_year": 2012, "year": 2012, "make": "Ram", "model": "Ram 1500 DS", "region": "US"}
        persisted = []
        with patch("autodata_ingestion.catalog_service._load_stored_article_for_repair", return_value=stored), patch(
            "autodata_ingestion.catalog_service._read_stored_article_snapshot", return_value=source_bytes
        ), patch(
            "autodata_ingestion.procedure_images.localize_procedure_images", side_effect=lambda article, **_kwargs: article
        ), patch(
            "autodata_ingestion.catalog_service._persist_stored_article_repair",
            side_effect=lambda article_id, article, **kwargs: persisted.append(article),
        ):
            repaired = _repair_stored_autoapitwo_article(
                {"vehicle_id": "configuration-1", "source_article_id": "autoapitwo:50582:210265"}, vehicle
            )

        self.assertIsNotNone(repaired)
        article = repaired[0][0]["article"]
        blocks = article["normalized_document"]["blocks"]
        self.assertEqual([block["type"] for block in blocks], ["heading", "paragraph", "image", "paragraph", "image"])
        self.assertEqual([block["source_order"] for block in blocks], [1, 2, 3, 4, 5])
        expected_ids = [sha256(url.encode()).hexdigest() for url in (first_url, second_url)]
        self.assertEqual([block["image_id"] for block in blocks if block["type"] == "image"], expected_ids)
        self.assertEqual(article["source_original"], legacy_article["source_original"])
        self.assertTrue(article["steps"])
        self.assertEqual(len(persisted), 1)

    def test_stored_source_repair_preserves_steps_images_and_is_idempotent(self):
        source_bytes = json.dumps({
            "year": 2012,
            "make": "Ram",
            "model": "Ram 1500 DS",
            "region": "US",
            "articleDetails": [{
                "id": "210189", "title": "Axle Shaft Bearing - Removal",
                "blocks": [
                    {"type": "text", "text": "Disconnect the connector."},
                    {"type": "image", "image_id": "figure-1", "url": "https://source.example/figure.png", "alt": "Bearing location"},
                    {"type": "text", "text": "Remove the bearing."},
                ],
                "images": [{"image_id": "figure-1", "url": "https://source.example/figure.png", "alt": "Bearing location"}],
            }],
        }, sort_keys=True, separators=(",", ":")).encode()
        legacy_article = {
            "article_id": "autoapitwo:50582:210189",
            "title": "Axle Shaft Bearing - Removal",
            "body": "Disconnect the connector. Remove the bearing.",
            "content_status": "content_complete",
            "source_original": {"keep": "byte-identical"},
            "steps": [
                {"number": 1, "heading": "Disconnect the connector.", "instructions": ["Unplug the harness."], "images": []},
                {"number": 2, "heading": "Remove the bearing.", "instructions": ["Remove the two fasteners."], "images": [{"image_id": "figure-1", "url": "https://source.example/figure.png", "alt": "Bearing location"}]},
            ],
            "images": [],
            "normalized_document": {"schema_version": 1, "normalization_version": "ordered-article-v1", "blocks": []},
        }
        stored = {
            "catalog_article_id": "00000000-0000-0000-0000-000000000001",
            "vehicle_id": "00000000-0000-0000-0000-000000000002",
            "article": legacy_article,
            "object_key": "sources/test/snapshot",
            "snapshot_sha256": sha256(source_bytes).hexdigest(),
            "source_uri": "https://source.example/article/210189",
            "source_version": "autoapitwo-content-detail-v1",
        }
        vehicle = {"model_year": 2012, "year": 2012, "make": "Ram", "model": "Ram 1500 DS", "region": "US"}
        persisted = []

        with patch("autodata_ingestion.catalog_service._load_stored_article_for_repair", return_value=stored), patch(
            "autodata_ingestion.catalog_service._read_stored_article_snapshot", return_value=source_bytes
        ) as read_snapshot, patch(
            "autodata_ingestion.procedure_images.localize_procedure_images", side_effect=lambda article, **_kwargs: article
        ) as localize, patch(
            "autodata_ingestion.catalog_service._persist_stored_article_repair",
            side_effect=lambda article_id, article, **kwargs: persisted.append((article_id, article, kwargs)),
        ):
            repaired = _repair_stored_autoapitwo_article(
                {"vehicle_id": "configuration-1", "source_article_id": "autoapitwo:50582:210189"}, vehicle
            )
            self.assertIsNotNone(repaired)
            article = repaired[0][0]["article"]
            blocks = article["normalized_document"]["blocks"]
            self.assertEqual([block["source_order"] for block in blocks], list(range(1, len(blocks) + 1)))
            self.assertEqual(blocks[1]["image_id"], "figure-1")
            self.assertTrue(article["steps"])
            self.assertEqual(article["steps"][0]["images"][0]["image_id"], "figure-1")
            self.assertEqual(article["source_original"], legacy_article["source_original"])
            self.assertEqual(repaired[1]["llm_requests"], 0)
            self.assertEqual(repaired[1]["source_article_requests"], 0)
            self.assertEqual(localize.call_count, 1)
            self.assertEqual(read_snapshot.call_count, 1)
            self.assertEqual(len(persisted), 1)

            repaired_row = {
                **stored,
                "article": {
                    **legacy_article,
                    "normalized_document": article["normalized_document"],
                },
            }
            with patch(
                "autodata_ingestion.catalog_service._load_stored_article_for_repair",
                return_value=repaired_row,
            ), patch(
                "autodata_ingestion.catalog_service._read_stored_article_snapshot",
                side_effect=AssertionError("valid documents need no source reread"),
            ), patch(
                "autodata_ingestion.catalog_service._persist_stored_article_repair",
                side_effect=AssertionError("valid documents need no rewrite"),
            ):
                self.assertIsNone(
                    _repair_stored_autoapitwo_article(
                        {"vehicle_id": "configuration-1", "source_article_id": "autoapitwo:50582:210189"},
                        vehicle,
                    )
                )

    def test_corrupt_stored_snapshot_marks_existing_article_partial(self):
        stored = {
            "catalog_article_id": "00000000-0000-0000-0000-000000000001",
            "snapshot_sha256": "0" * 64,
            "article": {"normalized_document": {"blocks": []}},
        }
        with patch(
            "autodata_ingestion.catalog_service._load_stored_article_for_repair",
            return_value=stored,
        ), patch(
            "autodata_ingestion.catalog_service._read_stored_article_snapshot",
            return_value=b'{"articleDetails":[]}',
        ), patch(
            "autodata_ingestion.catalog_service._mark_stored_article_partial"
        ) as mark_partial:
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                _repair_stored_autoapitwo_article(
                    {"vehicle_id": "configuration-1", "source_article_id": "autoapitwo:50582:210189"},
                    {"model_year": 2012, "make": "Ram", "model": "Ram 1500 DS", "region": "US"},
                )
        mark_partial.assert_called_once_with("00000000-0000-0000-0000-000000000001")

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

    def test_autoapitwo_vehicle_match_accepts_make_alias_and_inserted_model_variant(self):
        self.assertTrue(
            _same_autoapitwo_vehicle(
                {"year": "2012", "make": "Chevy Truck", "model": "Express 1500 AWD"},
                {"year": 2012, "make": "Chevrolet", "model": "Express Awd"},
            )
        )
        self.assertFalse(
            _same_autoapitwo_vehicle(
                {"year": "2012", "make": "Chevy Truck", "model": "Express 1500 RWD"},
                {"year": 2012, "make": "Chevrolet", "model": "Express Awd"},
            )
        )

    def test_autoapitwo_search_falls_back_from_provider_model_code(self):
        queries = []

        class Connector:
            def search_vehicles(self, query):
                queries.append(query)
                if query == "2018 Dodge Charger":
                    return [{"year": "2018", "make": "Dodge", "model": "Charger AWD", "id": "58065"}]
                return []

        vehicle = {"model_year": 2018, "make": "Dodge", "model": "Charger Ld"}
        self.assertEqual(_autoapitwo_search_queries(vehicle), ("2018 Dodge Charger Ld", "2018 Dodge Charger"))
        self.assertEqual(_autoapitwo_car_ids({"vehicle_id": ""}, vehicle, Connector()), ("58065",))
        self.assertEqual(queries, ["2018 Dodge Charger Ld", "2018 Dodge Charger"])

    def test_autoapitwo_matches_ram_ds_to_dodge_or_ram_provider_family(self):
        queries = []

        class Connector:
            def search_vehicles(self, query):
                queries.append(query)
                if query == "2012 Ram 1500":
                    return [
                        {
                            "year": "2012",
                            "make": "Dodge or Ram Truck",
                            "model": "RAM 1500 Truck 2WD",
                            "engine": "V6-3.7L",
                            "id": "50578",
                        },
                    ]
                return []

        vehicle = {"model_year": 2012, "make": "Ram", "model": "Ram 1500 Ds"}
        self.assertEqual(
            _autoapitwo_search_queries(vehicle),
            (
                "2012 Ram Ram 1500 Ds",
                "2012 Ram Ram 1500",
                "2012 Ram 1500 Ds",
                "2012 Ram 1500",
            ),
        )
        self.assertEqual(
            _autoapitwo_car_ids({"vehicle_id": ""}, vehicle, Connector()),
            ("50578",),
        )
        self.assertEqual(
            queries,
            [
                "2012 Ram Ram 1500 Ds",
                "2012 Ram Ram 1500",
                "2012 Ram 1500 Ds",
                "2012 Ram 1500",
            ],
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

    def test_descriptor_href_accepts_persisted_article_shapes(self):
        self.assertEqual(
            _descriptor_href({"href": "https://source.test/direct"}),
            "https://source.test/direct",
        )
        self.assertEqual(
            _descriptor_href({"source_uri": "https://source.test/source"}),
            "https://source.test/source",
        )
        self.assertEqual(
            _descriptor_href({"_links": {"self": {"href": "https://source.test/link"}}}),
            "https://source.test/link",
        )
        self.assertEqual(
            _descriptor_href({"evidence": [{"source_uri": "https://source.test/evidence"}]}),
            "https://source.test/evidence",
        )

    def test_engine_number_prefers_displacement_in_provider_engine_label(self):
        self.assertEqual(_engine_number("L4-2.4L (K24W1)"), 2.4)
        self.assertEqual(_engine_number("V6-3.5L (J35Y2)"), 3.5)

    def test_autoapitwo_id_only_mapping_is_enriched_before_engine_filtering(self):
        class Connector:
            def search_vehicles(self, query):
                return [
                    {"id": "52597", "year": "2013", "make": "Honda", "model": "Accord Coupe", "engine": "L4-2.4L (K24W1)"},
                    {"id": "52599", "year": "2013", "make": "Honda", "model": "Accord Coupe", "engine": "V6-3.5L (J35Y2)"},
                ]

        vehicle = {"model_year": 2013, "make": "Honda", "model": "Accord Coupe", "engine": "2.4"}
        self.assertEqual(
            _autoapitwo_car_ids(
                {"vehicle_id": "vehicle-1"},
                vehicle,
                Connector(),
            ),
            ("52597",),
        )

    def test_autoapitwo_accepts_provider_model_variants_for_normalized_model(self):
        class Connector:
            def search_vehicles(self, query):
                return [
                    {"id": "52992", "year": "2013", "make": "Honda", "model": "Crosstour 2WD", "engine": "L4-2.4L (K24Y2)"},
                    {"id": "52998", "year": "2013", "make": "Honda", "model": "Crosstour 2WD", "engine": "V6-3.5L (J35Y1)"},
                    {"id": "52999", "year": "2013", "make": "Honda", "model": "Crosstour 4WD", "engine": "V6-3.5L (J35Y1)"},
                ]

        vehicle = {"model_year": 2013, "make": "Honda", "model": "Crosstour"}
        self.assertEqual(
            _autoapitwo_car_ids({"vehicle_id": "vehicle-crosstour"}, vehicle, Connector()),
            ("52992", "52998", "52999"),
        )

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

    def test_article_scope_uses_targeted_index_loader_with_empty_query(self):
        calls = []

        def load_catalog(vehicle, target, *, query):
            calls.append((vehicle, target, query))
            return (
                [{"article": {"article_id": "a1", "title": "Oil pump replacement"}}],
                {"traversal": "vehicle_bundle", "targeted_article_fetch_count": 0},
            )

        request = json.dumps({
            "scope": "articles",
            "idempotency_key": "catalog-http-articles-index-1",
            "year": 1999,
            "make": "Toyota Truck",
            "model": "4 Runner 4wd",
            "region": "US",
            "trim": "SR5",
            "engine": "2.7",
        })
        with patch.dict(os.environ, {"AUTODATA_AUTOAPI_BASE_URL": "https://autoapi.test"}), \
                patch("autodata_ingestion.worker._load_autoapi_job_catalog", load_catalog):
            result = ensure_catalog_hydration(request)

        self.assertEqual(result["status"], "hydrated")
        self.assertTrue(result["complete"])
        self.assertEqual(result["metadata"]["targeted_article_fetch_count"], 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][2], "")

    def test_article_scope_falls_back_to_autoapitwo_when_autoapi_fails(self):
        primary_calls = []
        fallback_calls = []

        def load_catalog(vehicle, target, *, query):
            primary_calls.append(query)
            raise RuntimeError("AutoAPI vehicle lookup failed")

        def load_autoapitwo(request, vehicle):
            fallback_calls.append((request["make"], vehicle["model"]))
            return (
                [{"article": {"article_id": "autoapitwo:52597:1535667", "title": "Oil Pump"}}],
                {"mode": "autoapitwo_article_index", "targeted_article_fetch_count": 0},
            )

        request = json.dumps({
            "scope": "articles",
            "idempotency_key": "catalog-http-articles-autoapitwo-fallback-1",
            "vehicle_id": "vehicle-1",
            "year": 2013,
            "make": "Honda",
            "model": "Accord Coupe",
            "region": "US",
            "engine": "2.4",
        })
        with patch.dict(os.environ, {"AUTODATA_AUTOAPI_BASE_URL": "https://autoapi.test"}), \
                patch("autodata_ingestion.catalog_service._load_stored_article_for_repair", return_value=None), \
                patch("autodata_ingestion.worker._load_autoapi_job_catalog", load_catalog), \
                patch("autodata_ingestion.catalog_service._load_autoapitwo_article_catalog", load_autoapitwo):
            result = ensure_catalog_hydration(request)

        self.assertEqual(result["status"], "hydrated")
        self.assertTrue(result["complete"])
        self.assertEqual(result["metadata"]["mode"], "autoapitwo_article_index")
        self.assertEqual(primary_calls, [""])
        self.assertEqual(fallback_calls, [("Honda", "Accord Coupe")])

    def test_selected_article_scope_falls_back_to_autoapitwo(self):
        request = json.dumps({
            "scope": "article",
            "idempotency_key": "catalog-http-article-autoapitwo-fallback-1",
            "vehicle_id": "vehicle-1",
            "year": 2013,
            "make": "Honda",
            "model": "Accord Coupe",
            "region": "US",
            "engine": "2.4",
            "source_article_id": "autoapitwo:52597:1535667",
            "title": "Oil Pump",
        })

        def load_catalog(vehicle, target, *, query):
            raise RuntimeError("AutoAPI vehicle lookup failed")

        def load_detail(request, vehicle):
            return ([{"article": {"article_id": "autoapitwo:52597:1535667", "title": "Oil Pump"}}], {"mode": "autoapitwo_article_detail"})

        with patch.dict(os.environ, {"AUTODATA_AUTOAPI_BASE_URL": "https://autoapi.test"}), \
                patch("autodata_ingestion.catalog_service._load_stored_article_for_repair", return_value=None), \
                patch("autodata_ingestion.worker._load_autoapi_job_catalog", load_catalog), \
                patch("autodata_ingestion.catalog_service._load_autoapitwo_article_detail", load_detail):
            result = ensure_catalog_hydration(request)

        self.assertEqual(result["status"], "hydrated")
        self.assertEqual(result["metadata"]["mode"], "autoapitwo_article_detail")
        self.assertEqual(result["rows"][0]["article"]["article_id"], "autoapitwo:52597:1535667")

    def test_selected_article_repairs_from_stored_snapshot_before_source_connectors(self):
        request = json.dumps({
            "scope": "article",
            "idempotency_key": "catalog-http-article-stored-repair-1",
            "vehicle_id": "configuration-1",
            "year": 2012,
            "make": "Ram",
            "model": "Ram 1500 DS",
            "region": "US",
            "source_article_id": "autoapitwo:50582:210189",
            "title": "Axle Shaft Bearing - Removal",
            "cache": {
                "complete": True,
                "rows": [{
                    "article": {
                        "content_status": "content_complete",
                        "normalized_document": {
                            "schema_version": 1,
                            "normalization_version": "ordered-article-v1",
                            "blocks": [],
                        },
                    },
                }],
            },
        })
        stored_row = {
            "kind": "article",
            "article": {
                "article_id": "autoapitwo:50582:210189",
                "content_status": "content_complete",
                "normalized_document": {"blocks": [{"source_order": 1, "type": "step"}]},
            },
        }
        stored_metadata = {
            "mode": "stored_source_repair",
            "source_article_requests": 0,
            "source_catalog_requests": 0,
            "llm_requests": 0,
        }

        with patch(
            "autodata_ingestion.catalog_service._repair_stored_autoapitwo_article",
            return_value=([stored_row], stored_metadata),
            create=True,
        ) as repair, patch(
            "autodata_ingestion.worker._load_autoapi_job_catalog",
            side_effect=AssertionError("stored article repair must not call AutoAPI"),
        ), patch(
            "autodata_ingestion.catalog_service._load_autoapitwo_article_detail",
            side_effect=AssertionError("stored article repair must not call AutoAPItwo"),
        ):
            result = ensure_catalog_hydration(request)

        self.assertTrue(repair.called)
        self.assertEqual(result["status"], "hydrated")
        self.assertTrue(result["complete"])
        self.assertEqual(result["metadata"]["mode"], "stored_source_repair")
        self.assertEqual(result["metadata"]["source_article_requests"], 0)
        self.assertEqual(result["rows"][0]["article"]["article_id"], "autoapitwo:50582:210189")

    def test_invalid_stored_article_source_returns_failure_without_provider_retry(self):
        request = json.dumps({
            "scope": "article",
            "idempotency_key": "catalog-http-article-stored-repair-invalid-1",
            "vehicle_id": "configuration-1",
            "year": 2012,
            "make": "Ram",
            "model": "Ram 1500 DS",
            "region": "US",
            "source_article_id": "autoapitwo:50582:210189",
            "title": "Axle Shaft Bearing - Removal",
        })

        with patch(
            "autodata_ingestion.catalog_service._repair_stored_autoapitwo_article",
            side_effect=ValueError("stored article snapshot hash mismatch"),
        ), patch(
            "autodata_ingestion.worker._load_autoapi_job_catalog",
            side_effect=AssertionError("invalid stored source must not retry AutoAPI"),
        ), patch(
            "autodata_ingestion.catalog_service._load_autoapitwo_article_detail",
            side_effect=AssertionError("invalid stored source must not retry AutoAPItwo"),
        ):
            result = ensure_catalog_hydration(request)

        self.assertEqual(result["status"], "repair_failed")
        self.assertFalse(result["complete"])
        self.assertIn("hash check", result["metadata"]["detail"])
        self.assertEqual(result["metadata"]["source_article_requests"], 0)
        self.assertEqual(result["metadata"]["source_catalog_requests"], 0)

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


if __name__ == "__main__":
    unittest.main()
