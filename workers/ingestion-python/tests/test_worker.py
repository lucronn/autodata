import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from autodata_ingestion.worker import run_once  # noqa: E402
from autodata_ingestion.source_adapters import SourceResource  # noqa: E402


class IngestionWorkerTests(unittest.TestCase):
    def test_default_worker_does_not_activate_chat_environment_requests(self):
        from autodata_ingestion.worker import run_once

        with patch.dict(
            "os.environ",
            {
                "AUTODATA_CHAT_QUERY_JSON": '{"message":"legacy chat request"}',
                "AUTODATA_CHAT_SELECTION_JSON": '{"query_id":"legacy"}',
                "AUTODATA_CHAT_WORKER_ENABLED": "1",
                "AUTODATA_SOURCE_DIRECTORY": "",
                "AUTODATA_SOURCE_URI": "",
                "AUTODATA_FAST_EVENT_JSON": "",
                "AUTODATA_ARTICLE_URI": "",
                "AUTODATA_KNOWLEDGE_REQUEST_JSON": "",
                "AUTODATA_JOB_PLAN_REQUEST_JSON": "",
                "AUTODATA_VEHICLE_LIST_JSON": "",
            },
            clear=True,
        ):
            result = run_once()

        self.assertEqual(result["status"], "idle")

    def test_labor_article_match_uses_component_when_titles_use_different_operations(self):
        from autodata_ingestion.worker import _match_labor_article_id

        procedure = {
            "article_id": "P:564294320",
            "title": "Brake Line Inspect",
            "bucket": "Maintenance Procedures",
        }
        labor_articles = [{
            "article_id": "L:23903519",
            "title": "Brake Line R&R",
            "bucket": "Labor",
        }]

        self.assertEqual(
            _match_labor_article_id(procedure, labor_articles),
            "L:23903519",
        )

    def test_title_only_catalog_requires_procedure_content_hydration(self):
        from autodata_ingestion.worker import _catalog_needs_procedure_content_hydration

        title_only = [{
            "kind": "article",
            "article": {
                "article_id": "P:brake-line",
                "title": "Brake Line Inspect",
                "component": "brake_line",
                "operations": [{
                    "operation_id": "replace-brake-line",
                    "action": "Replace brake line",
                    "duration_hours": 1.2,
                }],
                "evidence": [{"evidence_id": "index-evidence"}],
            },
        }]

        complete = [{
            "kind": "article",
            "article": {
                **title_only[0]["article"],
                "body": "Remove the line and bleed the system.",
                "steps": ["Remove the line", "Bleed the system"],
            },
        }]

        self.assertTrue(
            _catalog_needs_procedure_content_hydration(
                "brake line replacement procedure", title_only
            )
        )
        self.assertFalse(
            _catalog_needs_procedure_content_hydration(
                "brake line replacement procedure", complete
            )
        )

    def test_stale_content_complete_metadata_only_cache_requires_hydration(self):
        from autodata_ingestion.worker import _catalog_needs_procedure_content_hydration

        stale = [{
            "kind": "article",
            "article": {
                "article_id": "autoapitwo:50589:210926",
                "title": "Generator - Removal (6.7L DSL)",
                "component": "alternator",
                "content_status": "content_complete",
                "body": "7L DIESEL",
                "steps": [{"action": "7L DIESEL", "instructions": []}],
                "source_original": {"immutable": True},
            },
        }]

        self.assertTrue(
            _catalog_needs_procedure_content_hydration(
                "alternator replacement", stale
            )
        )

    def test_job_plan_repairs_weak_cached_article_from_original_without_detail_refetch(self):
        from autodata_ingestion.worker import _load_autodb_two_job_catalog

        vehicle = {
            "vehicle_id": "canonical-vehicle-1",
            "year": 2012,
            "make": "Dodge Or Ram Truck",
            "model": "Ram 3500 Truck 2wd",
            "region": "US",
            "engine_displacement_l": 6.7,
            "autoapitwo_vehicle_ids": ["50590"],
        }
        stale_alternator = {
            "kind": "article",
            "article": {
                "article_id": "autoapitwo:50589:210926",
                "title": "Generator - Removal (6.7L DSL)",
                "component": "alternator",
                "content_status": "content_complete",
                "body": "7L DIESEL",
                "steps": [{"action": "7L DIESEL", "instructions": []}],
            },
        }
        usable_oil_pump = {
            "kind": "article",
            "article": {
                "article_id": "autoapitwo:50589:212033",
                "title": "Engine Oil Pump - Removal",
                "component": "oil_pump",
                "content_status": "content_complete",
                "body": "Remove the oil pan bolts. Remove the oil pump assembly.",
                "steps": [{"action": "Remove the oil pan bolts."}],
            },
        }
        repaired = {
            "kind": "article",
            "vehicle_identity": vehicle,
            "article": {
                **stale_alternator["article"],
                "body": "Disconnect the battery. Remove the generator fasteners. Lift out the generator.",
                "steps": [
                    {"action": "Disconnect the battery."},
                    {"action": "Remove the generator fasteners."},
                    {"action": "Lift out the generator."},
                ],
            },
        }

        with patch(
            "autodata_ingestion.catalog_service._repair_stored_autoapitwo_article",
            return_value=([repaired], {"mode": "stored_source_repair", "targeted_article_fetch_count": 0}),
        ) as repair, patch(
            "autodata_ingestion.catalog_service._load_autoapitwo_article_detail",
            side_effect=AssertionError("usable immutable source must prevent a new provider detail call"),
        ) as detail:
            records, source = _load_autodb_two_job_catalog(
                vehicle,
                query="alternator and oil pump replacement",
                existing_catalog=[stale_alternator, usable_oil_pump],
            )

        repair.assert_called_once()
        self.assertEqual(
            repair.call_args.args[0]["source_article_id"],
            "autoapitwo:50589:210926",
        )
        detail.assert_not_called()
        by_id = {
            str((record.get("article") or record).get("article_id")): record
            for record in records
        }
        self.assertEqual(
            by_id["autoapitwo:50589:210926"]["article"]["steps"][0]["action"],
            "Disconnect the battery.",
        )
        self.assertEqual(source["mode"], "stored_source_repair")
        self.assertEqual(source["targeted_article_fetch_count"], 0)
    def test_autoapi_content_source_defaults_from_vehicle_make(self):
        from autodata_ingestion.worker import _autoapi_content_source

        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(
                _autoapi_content_source({"make": "Toyota"}),
                "Motor",
            )
            self.assertEqual(
                _autoapi_content_source({"make": "Chevrolet"}),
                "Motor",
            )

    def test_explicit_autoapi_content_source_wins_over_make_default(self):
        from autodata_ingestion.worker import _autoapi_content_source

        with patch.dict(
            "os.environ",
            {"AUTODATA_AUTOAPI_CONTENT_SOURCE": "Motor"},
            clear=True,
        ):
            self.assertEqual(
                _autoapi_content_source({"make": "Toyota"}),
                "Motor",
            )

    def test_job_plan_falls_back_when_catalog_has_rows_but_not_requested_article_content(self):
        from autodata_ingestion.worker import run_job_plan

        vehicle = {"year": 1999, "make": "Chevrolet", "model": "Silverado 1500", "region": "US"}
        cached_catalog = [{
            "kind": "article",
            "article": {"article_id": "brake-1", "title": "Brake replacement"},
        }]
        hydrated_catalog = [{
            "kind": "article",
            "article": {
                "article_id": "oil-1",
                "title": "Oil pump replacement",
                "body": "Remove the pan. Replace the oil pump. Install the pan.",
                "steps": [
                    "Remove the pan.",
                    "Replace the oil pump.",
                    "Install the pan.",
                ],
                "operations": [{"operation_id": "oil", "action": "Replace oil pump", "duration_hours": 2.0}],
                "evidence": [{"evidence_id": "oil-evidence"}],
            },
        }]
        with patch(
            "autodata_ingestion.knowledge_catalog.load_vehicle_knowledge_catalog",
            return_value=cached_catalog,
        ) as load_local_index, patch(
            "autodata_ingestion.worker._load_autoapi_job_catalog",
            return_value=(hydrated_catalog, {"mode": "autoapi_fallback", "targeted_article_fetch_count": 1}),
        ) as fallback:
            with patch.dict(
                "os.environ",
                {"AUTODATA_MERCURY2_JOB_PLANS_ENABLED": "0", "AUTODATA_SOURCE_PERSIST": "0"},
                clear=False,
            ):
                result = run_job_plan(json.dumps({"vehicle": vehicle, "query": "oil pump replacement"}))

        fallback.assert_called_once()
        load_local_index.assert_called_once()
        self.assertEqual(
            load_local_index.call_args.kwargs["query"], "oil pump replacement"
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["selected_articles"], ["oil-1"])
        self.assertNotIn("labor", result)
        self.assertEqual(
            [step["instructions"][0] for step in result["procedure"]["steps"]],
            ["Remove the pan.", "Replace the oil pump.", "Install the pan."],
        )

    def test_job_plan_passes_catalog_evidence_into_mercury_composition(self):
        from autodata_ingestion.worker import run_job_plan

        captured = {}
        catalog = [{
            "kind": "article",
            "article": {
                "article_id": "alternator-article",
                "title": "Alternator Removal/Installation",
                "component": "alternator",
                "body": "Disconnect the battery, remove the alternator, and install it.",
                "steps": ["Disconnect the battery", "Remove the alternator", "Install the alternator"],
            },
            "evidence": [{"evidence_id": "alternator-evidence", "locator": "body.steps"}],
        }]

        def capture_composition(_client, _query, _vehicle, selected_articles, _labor, fallback):
            captured["articles"] = selected_articles
            return fallback

        with patch(
            "autodata_ingestion.knowledge_catalog.load_vehicle_knowledge_catalog",
            return_value=catalog,
        ), patch(
            "autodata_ingestion.job_plan.compose_procedure_with_llm",
            side_effect=capture_composition,
        ), patch(
            "autodata_ingestion.mercury2.Mercury2Client.from_environment",
            return_value=object(),
        ), patch.dict(
            "os.environ",
            {
                "AUTODATA_MERCURY2_JOB_PLANS_ENABLED": "1",
                "AUTODATA_AUTOAPI_BASE_URL": "",
            },
            clear=False,
        ):
            result = run_job_plan(json.dumps({
                "vehicle": {"year": 2013, "make": "Honda", "model": "Crosstour 2wd", "region": "US"},
                "query": "replace the alternator",
            }))

        self.assertEqual(result["llm_status"], "generated")
        self.assertEqual(
            captured["articles"][0]["evidence"],
            [{"evidence_id": "alternator-evidence", "locator": "body.steps"}],
        )

    def test_autodbone_never_receives_an_autodbtwo_vehicle_id(self):
        from autodata_ingestion.autoapi_connector import AutoAPIVehicleBundle
        from autodata_ingestion.worker import _load_autoapi_job_catalog

        vehicle = {
            "year": 2013,
            "make": "Honda",
            "model": "Crosstour 2wd",
            "region": "US",
            "provider": "autodbtwo",
            "provider_vehicle_id": "52992",
        }
        bundle = AutoAPIVehicleBundle(
            vehicle_id="autodbone-resolved-id",
            content_source="Motor",
            vehicle=vehicle,
            configurations=(),
            resources=(),
            article_ids=(),
        )
        with patch("autodata_ingestion.autoapi_connector.AutoAPIConnector") as connector_class:
            connector = connector_class.return_value
            connector.find_vehicle_targets.return_value = [
                {"vehicle_id": "autodbone-resolved-id"}
            ]
            connector.fetch_vehicle_bundle.return_value = bundle
            with patch.dict(
                "os.environ",
                {"AUTODATA_AUTOAPI_BASE_URL": "https://autodbone.example"},
                clear=False,
            ):
                _load_autoapi_job_catalog(vehicle, object(), query="alternator")

        connector.find_vehicle_targets.assert_called_once_with(
            2013, "Honda", "Crosstour 2wd"
        )
        connector.fetch_vehicle_bundle.assert_called_once_with(
            {"vehicle_id": "autodbone-resolved-id"}
        )

    def test_autodb_two_hydration_preserves_articles_already_loaded_from_autodbone(self):
        from autodata_ingestion.worker import run_job_plan

        vehicle = {
            "vehicle_id": "configuration-1",
            "year": 2013,
            "make": "Honda",
            "model": "Crosstour 2wd",
            "region": "US",
        }
        alternator = {
            "article": {
                "article_id": "autodbone:alternator-1",
                "title": "Alternator Replacement",
                "component": "alternator",
                "steps": ["Disconnect battery.", "Remove alternator."],
                "body": "Disconnect battery. Remove alternator.",
            }
        }
        pump_index = {
            "article": {
                "article_id": "autodbone:water-pump-index",
                "title": "Water Pump Replacement",
                "component": "water_pump",
            }
        }
        water_pump = {
            "article": {
                "article_id": "autoapitwo:52992:water-pump-1",
                "title": "Water Pump Replacement",
                "component": "water_pump",
                "steps": ["Remove pump.", "Install pump."],
                "body": "Remove pump. Install pump.",
            }
        }
        local = [alternator, pump_index]
        with patch(
            "autodata_ingestion.knowledge_catalog.load_vehicle_knowledge_catalog",
            return_value=local,
        ), patch(
            "autodata_ingestion.worker._load_autoapi_job_catalog",
            return_value=(local, {"mode": "autoapi_fallback"}),
        ), patch(
            "autodata_ingestion.worker._load_autodb_two_job_catalog",
            return_value=([water_pump], {"mode": "autodb_two_fallback"}),
        ) as two_provider:
            with patch.dict(
                "os.environ",
                {"AUTODATA_MERCURY2_JOB_PLANS_ENABLED": "0"},
                clear=False,
            ):
                result = run_job_plan(json.dumps({
                    "vehicle": vehicle,
                    "query": "alternator and water pump replacement",
                }))

        self.assertEqual(two_provider.call_args.kwargs["existing_catalog"], local)
        self.assertIn("autodbone:alternator-1", result["selected_articles"])
        self.assertIn("autoapitwo:52992:water-pump-1", result["selected_articles"])

    def test_autodbone_article_id_is_never_sent_to_autodbtwo(self):
        from autodata_ingestion.worker import _load_autodb_two_job_catalog

        vehicle = {
            "vehicle_id": "canonical-vehicle-1",
            "year": 2013,
            "make": "Honda",
            "model": "Crosstour 2wd",
            "engine_displacement_l": 2.4,
            "autoapitwo_vehicle_ids": ["52992"],
            "provider": "autodbone",
            "provider_vehicle_id": "autodbone-private-vehicle-id",
        }
        autodbone_article = {
            "article": {
                "article_id": "autodbone:procedure:ALT-1",
                "title": "Alternator Replacement",
                "component": "alternator",
                "steps": ["Remove alternator."],
                "body": "Remove alternator.",
            }
        }
        autodbtwo_index = {
            "article": {
                "article_id": "autoapitwo:52992:WP-1",
                "title": "Water Pump Replacement",
                "component": "water_pump",
            }
        }
        hydrated = {
            "article": {
                **autodbtwo_index["article"],
                "steps": ["Remove water pump.", "Install water pump."],
                "body": "Remove water pump. Install water pump.",
            }
        }
        with patch(
            "autodata_ingestion.catalog_service._load_autoapitwo_article_detail",
            return_value=([hydrated], {"targeted_article_fetch_count": 1}),
        ) as detail:
            records, _source_info = _load_autodb_two_job_catalog(
                vehicle,
                query="alternator and water pump replacement",
                existing_catalog=[autodbone_article, autodbtwo_index],
            )

        detail_request = detail.call_args.args[0]
        self.assertEqual(detail_request["source_article_id"], "autoapitwo:52992:WP-1")
        self.assertNotIn("provider_vehicle_id", detail_request)
        self.assertNotIn("autodbone-private-vehicle-id", repr(detail_request))
        self.assertIn("autodbone:procedure:ALT-1", [
            str((record.get("article") or record).get("article_id"))
            for record in records
        ])

    def test_job_plan_catalog_excludes_other_engine_and_drivetrain_variants(self):
        from autodata_ingestion.worker import _filter_job_plan_catalog_for_vehicle

        vehicle = {
            "engine_displacement_l": "2.4L",
            "drivetrain": "2WD",
        }
        catalog = [
            {
                "vehicle_identity": {
                    "engine_displacement_l": 2.4,
                    "drivetrain": "2WD",
                },
                "article": {"article_id": "autoapitwo:52992:1", "title": "Alternator Removal"},
            },
            {
                "vehicle_identity": {
                    "engine_displacement_l": 3.5,
                    "drivetrain": "2WD",
                },
                "article": {"article_id": "autoapitwo:52998:1", "title": "Alternator Removal"},
            },
            {
                "vehicle_identity": {
                    "engine_displacement_l": 2.4,
                    "drivetrain": "4WD",
                },
                "article": {"article_id": "autoapitwo:52992:2", "title": "Water Pump Replacement"},
            },
        ]

        result = _filter_job_plan_catalog_for_vehicle(vehicle, catalog)

        self.assertEqual(
            [record["article"]["article_id"] for record in result],
            ["autoapitwo:52992:1"],
        )

    def test_job_plan_falls_back_to_selected_autodbtwo_articles_after_autodbone_failure(self):
        from autodata_ingestion.worker import run_job_plan

        vehicle = {
            "vehicle_id": "configuration-1",
            "year": 2013,
            "make": "Honda",
            "model": "Crosstour 2wd",
            "region": "US",
        }
        cached_catalog = [
            {
                "kind": "article",
                "article": {
                    "article_id": "autoapitwo:52992:alternator-1",
                    "title": "Alternator Replacement",
                    "component": "alternator",
                },
            },
            {
                "kind": "article",
                "article": {
                    "article_id": "autoapitwo:52992:water-pump-1",
                    "title": "Water Pump Replacement",
                    "component": "water_pump",
                },
            },
        ]
        hydrated = [
            {
                **record,
                "article": {
                    **record["article"],
                    "steps": ["Remove the component.", "Install the replacement."],
                    "body": "Remove the component. Install the replacement.",
                },
            }
            for record in cached_catalog
        ]
        with patch(
            "autodata_ingestion.knowledge_catalog.load_vehicle_knowledge_catalog",
            return_value=cached_catalog,
        ), patch(
            "autodata_ingestion.worker._load_autoapi_job_catalog",
            side_effect=RuntimeError("AutoDBone source unavailable"),
        ), patch(
            "autodata_ingestion.catalog_service._load_autoapitwo_article_detail",
            side_effect=[
                ([hydrated[0]], {"mode": "autoapitwo_article_detail"}),
                ([hydrated[1]], {"mode": "autoapitwo_article_detail"}),
            ],
        ) as autodbtwo_detail:
            with patch.dict(
                "os.environ",
                {
                    "AUTODATA_MERCURY2_JOB_PLANS_ENABLED": "0",
                    "AUTODATA_SOURCE_PERSIST": "1",
                },
                clear=False,
            ):
                result = run_job_plan(
                    json.dumps(
                        {
                            "vehicle": vehicle,
                            "query": "alternator and water pump replacement",
                        }
                    )
                )

        self.assertEqual(result["status"], "ready")
        self.assertNotIn("labor", result)
        self.assertCountEqual(
            result["selected_articles"],
            [
                "autoapitwo:52992:alternator-1",
                "autoapitwo:52992:water-pump-1",
            ],
        )
        self.assertEqual(autodbtwo_detail.call_count, 2)
        self.assertTrue(all(step.get("instructions") for step in result["procedure"]["steps"]))

    def test_autoapi_query_hydrates_and_persists_only_selected_articles_without_labor(self):
        from autodata_ingestion.autoapi_connector import AutoAPIVehicleBundle
        from autodata_ingestion.worker import _load_autoapi_job_catalog

        def resource(uri, payload):
            return SourceResource.from_bytes(uri, "autoapi-test-v1", json.dumps(payload).encode(), "application/json")

        vehicle = {
            "vehicle_id": "v1",
            "autoapi_vehicle_id": "v1",
            "vehicle_key": "chevrolet-silverado-1500-1999-us",
            "year": 1999,
            "make": "Chevrolet",
            "model": "Silverado 1500",
            "region": "US",
        }
        bundle = AutoAPIVehicleBundle(
            vehicle_id="v1",
            content_source="GeneralMotors",
            vehicle=vehicle,
            configurations=(),
            resources=(
                resource("http://source/name", {"body": "1999 Chevrolet Silverado 1500"}),
                resource("http://source/motorvehicles", {"body": [{"id": "m1", "model": "Silverado 1500", "engines": []}]}),
                resource(
                    "http://source/articles/v2",
                    {"body": {"articleDetails": [
                        {"id": "alt-1", "title": "Alternator replacement"},
                        {"id": "starter-1", "title": "Starter replacement"},
                        {"id": "brake-1", "title": "Brake replacement"},
                    ]}},
                ),
            ),
            article_ids=("alt-1", "starter-1", "brake-1"),
        )
        details = {
            "alt-1": (
                resource("http://source/article/alt-1", {"body": {"documentId": "alt-1", "html": "Replace the alternator."}}),
                resource("http://source/labor/alt-1", {"body": {"operations": [{"operationId": "shared-belt", "name": "Remove belt", "hours": 0.25}, {"operationId": "alternator", "name": "Replace alternator", "hours": 1.5}]}}),
            ),
            "starter-1": (
                resource("http://source/article/starter-1", {"body": {"documentId": "starter-1", "html": "Replace the starter."}}),
                resource("http://source/labor/starter-1", {"body": {"operations": [{"operationId": "shared-belt", "name": "Remove belt", "hours": 0.25}, {"operationId": "starter", "name": "Replace starter", "hours": 2.0}]}}),
            ),
        }
        with patch("autodata_ingestion.autoapi_connector.AutoAPIConnector") as connector_class:
            connector = connector_class.return_value
            connector.fetch_vehicle_bundle.return_value = bundle
            connector.fetch_article_resources.side_effect = (
                lambda _vehicle_id, article_id, **_kwargs: details[article_id][:1]
            )
            with patch(
                "autodata_ingestion.procedure_images.localize_procedure_images",
                side_effect=lambda article, **_kwargs: dict(article),
            ):
                with patch("autodata_ingestion.bundle_persistence.persist_source_bundle") as persist_bundle:
                    with patch.dict(
                        "os.environ",
                        {
                            "AUTODATA_AUTOAPI_BASE_URL": "http://127.0.0.1:3000",
                            "AUTODATA_SOURCE_PERSIST": "1",
                        },
                        clear=False,
                    ):
                        records, source_info = _load_autoapi_job_catalog(
                            vehicle, object(), query="replace alternator and starter"
                        )

        self.assertEqual(source_info["targeted_article_fetch_count"], 2)
        self.assertEqual(source_info["targeted_labor_fetch_count"], 0)
        self.assertEqual(connector.fetch_article_resources.call_count, 2)
        by_id = {record["article"]["article_id"]: record["article"] for record in records}
        self.assertTrue(by_id["alt-1"]["steps"])
        self.assertTrue(by_id["starter-1"]["steps"])
        self.assertTrue(
            all(
                call.kwargs.get("include_labor") is False
                for call in connector.fetch_article_resources.call_args_list
            )
        )
        self.assertNotIn("brake-1", [call.args[1] for call in connector.fetch_article_resources.call_args_list])
        persisted_bundle = persist_bundle.call_args.args[0]
        self.assertEqual(
            {article["article_id"] for article in persisted_bundle.articles},
            {"alt-1", "starter-1"},
        )

    def test_autoapi_article_catalog_fallback_reads_index_without_detail_fetches(self):
        from types import SimpleNamespace

        from autodata_ingestion.autoapi_connector import AutoAPIVehicleBundle
        from autodata_ingestion.worker import _load_autoapi_job_catalog

        vehicle = {
            "vehicle_id": "v1",
            "autoapi_vehicle_id": "v1",
            "year": 1999,
            "make": "Toyota",
            "model": "RAV4",
            "region": "US",
        }
        bundle = AutoAPIVehicleBundle(
            vehicle_id="v1",
            content_source="Motor",
            vehicle=vehicle,
            configurations=(),
            resources=(),
            article_ids=("oil-1",),
        )
        article = {"article_id": "oil-1", "title": "Oil pump replacement", "content_status": "list_only"}
        normalized = SimpleNamespace(articles=(article,), evidence=())
        with patch("autodata_ingestion.autoapi_connector.AutoAPIConnector") as connector_class:
            connector = connector_class.return_value
            connector.fetch_vehicle_bundle.return_value = bundle
            with patch(
                "autodata_ingestion.source_bundle.normalize_source_bundle",
                return_value=normalized,
            ) as normalize_source_bundle:
                with patch.dict(
                    "os.environ",
                    {
                        "AUTODATA_AUTOAPI_BASE_URL": "http://127.0.0.1:3000",
                        "AUTODATA_SOURCE_PERSIST": "0",
                    },
                    clear=False,
                ):
                    records, source_info = _load_autoapi_job_catalog(
                        vehicle, object(), query=""
                    )

        self.assertEqual([record["article"]["article_id"] for record in records], ["oil-1"])
        self.assertEqual(source_info["targeted_article_fetch_count"], 0)
        connector.fetch_article_resources.assert_not_called()

        self.assertEqual(
            normalize_source_bundle.call_args.kwargs["expected_vehicle"],
            vehicle,
        )

    def test_autoapi_article_catalog_fallback_filters_provider_variants_by_engine(self):
        from types import SimpleNamespace

        from autodata_ingestion.worker import _filter_vehicle_bundles

        bundles = tuple(
            SimpleNamespace(
                vehicle={"year": 1999, "make": "Toyota", "model": "4Runner"},
                configurations=({"engine_displacement_l": engine, "trim": trim},),
            )
            for engine, trim in ((2.7, "4RUNNERBASE"), (3.4, "4RUNNERSR5"))
        )

        result = _filter_vehicle_bundles(
            bundles,
            {"year": 1999, "make": "Toyota Truck", "model": "4 Runner 4wd", "engine": "2.7"},
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].configurations[0]["engine_displacement_l"], 2.7)

    def test_autoapi_query_fallback_does_not_fetch_separate_labor_row(self):
        from autodata_ingestion.autoapi_connector import AutoAPIVehicleBundle
        from autodata_ingestion.worker import _load_autoapi_job_catalog

        def resource(uri, payload):
            return SourceResource.from_bytes(uri, "autoapi-test-v1", json.dumps(payload).encode(), "application/json")

        vehicle = {
            "vehicle_id": "v1",
            "autoapi_vehicle_id": "v1",
            "vehicle_key": "toyota-rav4-1997-us",
            "year": 1997,
            "make": "Toyota",
            "model": "RAV4",
            "region": "US",
        }
        bundle = AutoAPIVehicleBundle(
            vehicle_id="v1",
            content_source="Motor",
            vehicle=vehicle,
            configurations=(),
            resources=(
                resource("http://source/name", {"body": "1997 Toyota RAV4"}),
                resource("http://source/articles/v2", {"body": {"articleDetails": [
                    {"id": "P:1", "title": "Water Pump R&R", "bucket": "Component Replacement"},
                    {"id": "L:2", "title": "Water Pump R&R", "bucket": "Labor"},
                ]}}),
            ),
            article_ids=("P:1", "L:2"),
        )
        labor = resource("http://source/labor/L:2", {"body": {"operations": [
            {"operationId": "pump", "name": "Replace water pump", "hours": 2.0},
        ]}})
        labor.metadata["target_article_id"] = "P:1"
        details = {
            "P:1": (
                resource("http://source/article/P:1", {"body": {"documentId": "P:1", "html": "Replace the water pump."}}),
                labor,
            ),
        }
        with patch("autodata_ingestion.autoapi_connector.AutoAPIConnector") as connector_class:
            connector = connector_class.return_value
            connector.fetch_vehicle_bundle.return_value = bundle
            connector.fetch_article_resources.side_effect = (
                lambda _vehicle_id, article_id, **_kwargs: details[article_id][:1]
            )
            with patch.dict(
                "os.environ",
                {"AUTODATA_AUTOAPI_BASE_URL": "http://127.0.0.1:3000", "AUTODATA_SOURCE_PERSIST": "0"},
                clear=False,
            ):
                records, _source_info = _load_autoapi_job_catalog(
                    vehicle, object(), query="water pump replacement"
                )

        connector.fetch_article_resources.assert_called_once_with(
            "v1", "P:1", include_labor=False
        )
        article = next(record["article"] for record in records if record["article"]["article_id"] == "P:1")
        self.assertNotIn("operations", article)

    def test_job_plan_ignores_persisted_composition_and_never_persists_new_composition(self):
        from autodata_ingestion.worker import run_job_plan

        vehicle = {"year": 1997, "make": "Toyota", "model": "RAV4", "region": "US"}
        derived = {
            "vehicle_key": "toyota-rav4-1997-us",
            "kind": "article",
            "article": {
                "article_id": "combined:1997-toyota-rav4:water_pump:v1",
                "title": "water pump service",
                "status": "ready",
                "contract_version": 5,
                "derived_components": ["water_pump"],
                "source_article_ids": ["P:1"],
                "evidence_ids": ["evidence-1"],
                "derived_revision_id": "revision-1",
                "source_version": "source-v1",
                "labor": {"total_labor_hours": 3.9},
                "procedure": {
                    "title": "water pump service",
                    "steps": [
                        {
                            "action": "Replace water pump",
                            "components": ["water_pump"],
                            "instructions": [
                                "Remove the timing cover and replace the water pump gasket."
                            ],
                        }
                    ],
                },
            },
            "evidence": [],
        }
        source_catalog = [{
            "kind": "article",
            "article": {
                "article_id": "water-pump-source-1",
                "title": "Water pump replacement",
                "component": "water_pump",
                "body": "Remove the water pump and install a replacement using the source procedure.",
                "operations": [{"operation_id": "water-pump", "action": "Replace water pump"}],
                "procedure": {"steps": [{
                    "action": "Replace water pump",
                    "components": ["water_pump"],
                    "instructions": ["Remove the water pump and install a replacement using the source procedure."],
                }]},
            },
        }]
        with patch("autodata_ingestion.knowledge_catalog.load_vehicle_knowledge_catalog", return_value=[derived]), patch(
            "autodata_ingestion.worker._load_autoapi_job_catalog",
            return_value=(source_catalog, {"mode": "autoapi_fallback", "targeted_article_fetch_count": 1}),
        ) as source_fetch, patch(
            "autodata_ingestion.derived_article_persistence.persist_derived_article",
            side_effect=AssertionError("the composed response must never be persisted"),
        ) as persist_composition:
            with patch.dict("os.environ", {"AUTODATA_DERIVED_ARTICLE_CACHE_ENABLED": "1", "AUTODATA_SOURCE_PERSIST": "1"}, clear=False):
                result = run_job_plan(json.dumps({"vehicle": vehicle, "query": "water pump replacement"}))

        source_fetch.assert_called_once()
        persist_composition.assert_not_called()
        self.assertEqual(result["selected_articles"], ["water-pump-source-1"])
        self.assertNotIn("derived_article_persistence", result)
        self.assertFalse(result.get("cache_hit", False))

    def test_autoapi_job_fallback_uses_targeted_ymme_resolution(self):
        from types import SimpleNamespace

        from autodata_ingestion.worker import _load_autoapi_job_catalog

        vehicle = {
            "year": 1997,
            "make": "Toyota",
            "model": "RAV4",
            "drivetrain": "4WD",
            "region": "US",
        }
        bundle = SimpleNamespace(
            vehicle={**vehicle, "model": "RAV4 Base", "vehicle_id": "rav4-4wd"},
            vehicle_id="rav4-4wd",
            resources=(),
        )
        with patch("autodata_ingestion.autoapi_connector.AutoAPIConnector") as connector_class:
            connector = connector_class.return_value
            connector.find_vehicle_targets.return_value = (
                {"vehicle_id": "rav4-4wd", "year": 1997, "make": "Toyota", "model": "RAV4"},
            )
            connector.fetch_vehicle_bundle.return_value = bundle
            with patch("autodata_ingestion.source_bundle.normalize_source_bundle") as normalize:
                normalize.return_value.articles = []
                normalize.return_value.evidence = []
                with patch.dict(
                    "os.environ",
                    {
                        "AUTODATA_AUTOAPI_BASE_URL": "http://127.0.0.1:3000",
                        "AUTODATA_AUTOAPI_CONTENT_SOURCE": "",
                        "AUTODATA_SOURCE_PERSIST": "0",
                    },
                    clear=False,
                ):
                    records, source_info = _load_autoapi_job_catalog(
                        vehicle, object(), query="oil pump replacement"
                    )

        connector.find_vehicle_targets.assert_called_once_with(1997, "Toyota", "RAV4")
        connector.fetch_vehicle_bundle.assert_called_once()
        self.assertEqual(records, [])
        self.assertEqual(source_info["traversal"], "targeted_vehicle_family")

    def test_unknown_structured_source_can_use_opt_in_mercury_extractor(self):
        from autodata_ingestion.source_adapters import NormalizationCandidate
        from autodata_ingestion.worker import _collect_connector

        resource = SourceResource.from_bytes(
            "provider://vehicle/unknown.json",
            "source-v1",
            b'{"providerPayload":{"headline":"Brake connector bulletin"}}',
            "application/json",
        )

        class FakeConnector:
            def fetch(self, request):
                self.request = request
                return [resource]

        candidate = NormalizationCandidate(
            "article",
            "mercury2:article:stable",
            {
                "id": "TSB-42",
                "title": "Brake connector bulletin",
                "body": "Inspect the brake connector.",
            },
            "providerPayload.article",
        )
        identity = NormalizationCandidate(
            "vehicle_identity",
            "mercury2:vehicle_identity:stable",
            {"year": 2019, "make": "Cadillac", "model": "Escalade ESV"},
            "providerPayload.vehicle",
        )
        with patch.dict(
            "os.environ",
            {"AUTODATA_MERCURY2_EXTRACTION_ENABLED": "1"},
            clear=False,
        ):
            with patch(
                "autodata_ingestion.mercury2.Mercury2Client.from_environment",
                return_value=object(),
            ) as client_factory:
                with patch(
                    "autodata_ingestion.mercury2.Mercury2SourceExtractor.extract",
                    return_value=(identity, candidate),
                ) as extract:
                    artifacts, bundle, quality = _collect_connector(FakeConnector())

        self.assertEqual(artifacts[0].metadata["extraction_mode"], "mercury-2")
        self.assertEqual(artifacts[0].metadata["candidate_count"], 2)
        self.assertEqual(bundle.articles[0]["article_id"], "TSB-42")
        self.assertEqual(quality.status, "needs_review")
        client_factory.assert_called_once_with()
        extract.assert_called_once()

    def test_idle_run_reports_fast_lane_identity(self):
        result = run_once()

        self.assertEqual(result, {"worker": "ingestion", "lane": "fast", "status": "idle"})

    def test_configured_vehicle_list_returns_deterministic_structured_selection(self):
        with patch.dict(
            "os.environ",
            {
                "AUTODATA_SOURCE_DIRECTORY": "",
                "AUTODATA_SOURCE_URI": "",
                "AUTODATA_FAST_EVENT_JSON": "",
                "AUTODATA_VEHICLE_LIST_JSON": json.dumps([
                    {"model_year": "99", "make": "Chevy", "model": "Silverado 1500", "region": "US", "drivetrain": "2wd"},
                    {"year": 1999, "make": "Chevrolet", "model": "Silverado 1500", "region": "US", "drivetrain": "2WD", "engine_displacement_l": 5.3},
                ]),
            },
            clear=False,
        ):
            result = run_once()

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["vehicle_count"], 1)
        self.assertEqual(result["vehicles"][0]["vehicle_id_key"], "chevrolet-silverado-1500-1999-us")
        self.assertEqual(len(result["vehicles"][0]["configurations"]), 2)

    def test_configured_vehicle_list_surfaces_conflicting_dimensions_as_review(self):
        from autodata_ingestion.worker import run_vehicle_selection

        result = run_vehicle_selection(
            json.dumps(
                [
                    {
                        "year": 1999,
                        "make": "Chevrolet",
                        "model": "Silverado 1500",
                        "region": "US",
                        "drivetrain": "2WD",
                    },
                    {
                        "year": 1999,
                        "make": "Chevrolet",
                        "model": "Silverado 1500",
                        "region": "US",
                        "drivetrain": "4WD",
                    },
                ]
            )
        )

        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(
            result["vehicles"][0]["configurations"][-1]["status"],
            "needs_review",
        )

    def test_configured_vehicle_list_can_persist_identity_observations(self):
        from autodata_ingestion import vehicle_selection_persistence

        values = [
            {"year": 1999, "make": "Chevy", "model": "Silverado 1500", "region": "US", "drivetrain": "2wd"},
            {"year": 1999, "make": "Chevrolet", "model": "Silverado 1500", "region": "US", "drivetrain": "2WD", "engine_displacement_l": 5.3},
        ]
        with patch(
            "autodata_ingestion.vehicle_selection_persistence.persist_vehicle_selection_list",
            return_value={
                "status": "persisted",
                "observation_count": 2,
                "observations": [
                    {
                        "vehicle_id": "vehicle-1",
                        "vehicle_key": "chevrolet-silverado-1500-1999-us",
                        "vehicle_configuration_id": "configuration-1",
                        "configuration_key": "chevrolet-silverado-1500-1999-us",
                        "observation_id": "observation-1",
                        "resolution_status": "matched",
                    },
                    {
                        "vehicle_id": "vehicle-1",
                        "vehicle_key": "chevrolet-silverado-1500-1999-us",
                        "vehicle_configuration_id": "configuration-2",
                        "configuration_key": "chevrolet-silverado-1500-1999-us-engine-5-3l",
                        "observation_id": "observation-2",
                        "resolution_status": "matched",
                    },
                ],
            },
        ) as persist:
            with patch.dict(
                "os.environ",
                {
                    "AUTODATA_SOURCE_DIRECTORY": "",
                    "AUTODATA_SOURCE_URI": "",
                    "AUTODATA_FAST_EVENT_JSON": "",
                    "AUTODATA_VEHICLE_LIST_JSON": json.dumps(values),
                    "AUTODATA_SOURCE_PERSIST": "1",
                    "AUTODATA_SOURCE_REGION": "US",
                },
                clear=False,
            ):
                result = run_once()

        self.assertEqual(result["persistence"]["status"], "persisted")
        self.assertEqual(result["vehicles"][0]["vehicle_id"], "vehicle-1")
        self.assertEqual(
            result["vehicles"][0]["configurations"][1]["vehicle_configuration_id"],
            "configuration-2",
        )
        persist.assert_called_once()
        self.assertEqual(persist.call_args.args[0], values)

    def test_cached_derived_article_rejects_label_only_procedure(self):
        from autodata_ingestion.worker import _cached_derived_job_plan

        vehicle = {"year": 1997, "make": "Toyota", "model": "RAV4", "region": "US"}
        article = {
            "derived_components": ["oil_pump", "water_pump"],
            "source_article_ids": ["oil-1", "water-1"],
            "labor": {
                "operations": [
                    {"operation_id": "oil", "action": "Replace oil pump", "components": ["oil_pump"]},
                    {"operation_id": "water", "action": "Replace water pump", "components": ["water_pump"]},
                ]
            },
            "procedure": {
                "steps": [
                    {"action": "Replace oil pump", "components": ["oil_pump"]},
                    {"action": "Replace water pump", "components": ["water_pump"]},
                ]
            },
        }

        self.assertIsNone(
            _cached_derived_job_plan(
                "oil pump and water pump replacement",
                vehicle,
                [{"article": article}],
            )
        )

    def test_cached_derived_article_accepts_source_instruction_text(self):
        from autodata_ingestion.worker import _cached_derived_job_plan

        vehicle = {"year": 1997, "make": "Toyota", "model": "RAV4", "region": "US"}
        article = {
            "article_id": "combined:rav4:oil-water:v1",
            "derived_components": ["oil_pump", "water_pump"],
            "source_article_ids": ["oil-1", "water-1"],
            "status": "ready",
            "contract_version": 5,
            "model": "mercury-2",
            "labor": {"operations": [
                {"operation_id": "oil", "action": "Replace oil pump", "components": ["oil_pump"]},
                {"operation_id": "water", "action": "Replace water pump", "components": ["water_pump"]},
            ]},
            "procedure": {"steps": [
                {"action": "Replace oil pump", "components": ["oil_pump"], "instructions": ["Remove the oil pan and clean the strainer before releasing the pump body."]},
                {"action": "Replace water pump", "components": ["water_pump"], "instructions": ["Drain coolant, remove the bypass connection, and replace the pump seals."]},
            ]},
        }

        result = _cached_derived_job_plan(
            "oil pump and water pump replacement",
            vehicle,
            [{"article": article}],
        )
        self.assertIsNotNone(result)
        self.assertTrue(result["cache_hit"])

    def test_cached_derived_article_accepts_persisted_markdown_body(self):
        from autodata_ingestion.worker import _cached_derived_job_plan

        vehicle = {"year": 1997, "make": "Toyota", "model": "RAV4", "region": "US"}
        article = {
            "article_id": "combined:rav4:oil-water:v2",
            "title": "Oil and water pump service",
            "body": "# Oil and water pump service\n\nDisconnect the battery. Remove the timing cover. Replace the pumps. Reassemble and verify leaks.",
            "derived_components": ["oil_pump", "water_pump"],
            "source_article_ids": ["oil-1", "water-1"],
            "status": "needs_review",
            "contract_version": 5,
            "model": "mercury-2",
            "labor": {"operations": [
                {"operation_id": "oil", "action": "Replace oil pump", "components": ["oil_pump"]},
                {"operation_id": "water", "action": "Replace water pump", "components": ["water_pump"]},
            ]},
            "procedure": {"steps": [
                {"action": "Replace oil pump", "components": ["oil_pump"]},
                {"action": "Replace water pump", "components": ["water_pump"]},
            ]},
        }

        result = _cached_derived_job_plan(
            "oil pump and water pump replacement",
            vehicle,
            [{"article": article}],
        )

        self.assertIsNotNone(result)
        self.assertTrue(result["cache_hit"])

    def test_cached_derived_article_infers_components_from_persisted_steps(self):
        from autodata_ingestion.worker import _cached_derived_job_plan

        vehicle = {"year": 1997, "make": "Toyota", "model": "RAV4", "region": "US"}
        article = {
            "article_id": "combined:rav4:oil-water:v2",
            "title": "Oil and water pump service",
            "body": "# Oil and water pump service\n\nRemove shared covers, replace both pumps, and verify leaks.",
            "derived_components": [],
            "source_article_ids": ["oil-1", "water-1"],
            "status": "needs_review",
            "contract_version": 5,
            "model": "mercury-2",
            "procedure": {"steps": [
                {"action": "Replace oil pump", "components": ["oil_pump"]},
                {"action": "Replace water pump", "components": ["water_pump"]},
            ]},
        }

        result = _cached_derived_job_plan(
            "oil pump and water pump replacement",
            vehicle,
            [{"article": article}],
        )

        self.assertIsNotNone(result)
        self.assertTrue(result["cache_hit"])

    def test_derived_r_and_r_labels_require_source_hydration(self):
        from autodata_ingestion.worker import _catalog_needs_procedure_content_hydration

        catalog = [{
            "kind": "article",
            "article": {
                "derived_components": ["oil_pump", "water_pump"],
                "procedure": {"steps": [
                    {"action": "Engine Oil Pump R&R", "components": ["oil_pump"]},
                    {"action": "Water Pump R&R", "components": ["water_pump"]},
                ]},
            },
        }]

        self.assertTrue(
            _catalog_needs_procedure_content_hydration(
                "oil pump and water pump replacement procedure", catalog
            )
        )

    def test_oil_water_catalog_requires_timing_belt_individual(self):
        from autodata_ingestion.worker import _catalog_needs_procedure_content_hydration

        body = "1. Remove the cover.\n2. Remove the pump.\n" * 5
        catalog = [
            {
                "kind": "article",
                "article": {
                    "article_id": "oil-1",
                    "component": "oil_pump",
                    "title": "Oil Pump Removal",
                    "body": body,
                    "steps": ["Remove oil pump"],
                },
            },
            {
                "kind": "article",
                "article": {
                    "article_id": "water-1",
                    "component": "water_pump",
                    "title": "Water Pump Removal",
                    "body": body,
                    "steps": ["Remove water pump"],
                },
            },
        ]
        self.assertTrue(
            _catalog_needs_procedure_content_hydration(
                "oil pump and water pump replacement procedure", catalog
            )
        )
        catalog.append(
            {
                "kind": "article",
                "article": {
                    "article_id": "timing-1",
                    "component": "timing_belt",
                    "title": "Timing Belt Removal",
                    "body": body,
                    "steps": ["Remove timing belt"],
                },
            }
        )
        self.assertFalse(
            _catalog_needs_procedure_content_hydration(
                "oil pump and water pump replacement procedure", catalog
            )
        )

    def test_configured_article_url_returns_normalized_article_and_evidence_json(self):
        from autodata_ingestion.worker import run_article_url

        resource = SourceResource.from_bytes(
            "https://source.example/tsb-42",
            "v1",
            b'<html><head><meta name="vehicle" content="2019 Cadillac Escalade ESV"><meta name="article:id" content="TSB-42"><meta property="og:title" content="Brake connector bulletin"></head><body><article><p>Inspect connector.</p></article></body></html>',
            "text/html",
        )
        with patch("autodata_ingestion.http_connector.HttpSourceConnector") as connector_class:
            connector_class.return_value.fetch.return_value = [resource]
            with patch.dict("os.environ", {"AUTODATA_SOURCE_VERSION": "v1", "AUTODATA_SOURCE_REQUEST_HEADERS_JSON": "", "AUTODATA_SOURCE_PERSIST": "0"}, clear=False):
                result = run_article_url(
                    resource.source_uri,
                    json.dumps({"year": 2019, "make": "Cadillac", "model": "Escalade ESV", "region": "US"}),
                )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["vehicle"]["vehicle_key"], "cadillac-escalade-esv-2019-us")
        self.assertEqual(result["articles"][0]["article_id"], "TSB-42")
        self.assertTrue(result["evidence"])

    def test_configured_article_url_persists_ready_intake_when_enabled(self):
        from autodata_ingestion.worker import run_article_url

        resource = SourceResource.from_bytes(
            "https://source.example/tsb-42",
            "v1",
            b'<html><head><meta name="vehicle" content="2019 Cadillac Escalade ESV"><meta name="article:id" content="TSB-42"><meta property="og:title" content="Brake connector bulletin"></head><body><article><p>Inspect connector.</p></article></body></html>',
            "text/html",
        )
        with patch("autodata_ingestion.http_connector.HttpSourceConnector") as connector_class:
            connector_class.return_value.name = "http"
            connector_class.return_value.fetch.return_value = [resource]
            with patch(
                "autodata_ingestion.bundle_persistence.persist_source_bundle",
                return_value={"status": "ready", "vehicle_id": "vehicle-1"},
            ) as persist:
                with patch.dict(
                    "os.environ",
                    {"AUTODATA_SOURCE_PERSIST": "1", "AUTODATA_SOURCE_REQUEST_HEADERS_JSON": ""},
                    clear=False,
                ):
                    result = run_article_url(
                        resource.source_uri,
                        json.dumps({"year": 2019, "make": "Cadillac", "model": "Escalade ESV", "region": "US"}),
                    )

        self.assertEqual(result["persistence"]["vehicle_id"], "vehicle-1")
        persist.assert_called_once()
        self.assertEqual(persist.call_args.kwargs["adapter_name"], "http")

    def test_configured_knowledge_request_returns_catalog_hit_without_http_fetch(self):
        from autodata_ingestion.worker import run_vehicle_knowledge

        request = {
            "vehicle": {"year": 1999, "make": "Chevy", "model": "Silverado 1500", "region": "US"},
            "query": "brake connector",
            "catalog": [
                {
                    "vehicle_key": "chevrolet-silverado-1500-1999-us",
                    "kind": "article",
                    "article": {"article_id": "TSB-42", "title": "Brake connector bulletin"},
                    "evidence": [],
                }
            ],
        }

        with patch.dict(
            "os.environ",
            {
                "AUTODATA_SOURCE_DIRECTORY": "",
                "AUTODATA_SOURCE_URI": "",
                "AUTODATA_FAST_EVENT_JSON": "",
                "AUTODATA_ARTICLE_URI": "",
                "AUTODATA_KNOWLEDGE_REQUEST_JSON": json.dumps(request),
            },
            clear=False,
        ):
            result = run_once()

        self.assertEqual(result["status"], "cache_hit")
        self.assertEqual(result["vehicle"]["make"], "Chevrolet")
        self.assertEqual(result["results"][0]["article"]["article_id"], "TSB-42")

    def test_configured_knowledge_request_fetches_on_catalog_miss(self):
        from autodata_ingestion.worker import run_vehicle_knowledge

        source_uri = "https://source.example/{vehicle_key}/{drivetrain}/{engine_displacement_l}?q={query}"
        resource = SourceResource.from_bytes(
            "https://source.example/chevrolet-silverado-1500-1999-us/2WD/5.3?q=brake%20connector",
            "source-v1",
            b'<html><head><meta name="vehicle" content="1999 Chevrolet Silverado 1500"><meta name="article:id" content="TSB-42"><meta property="og:title" content="Brake connector bulletin"></head><body><article><p>Inspect the brake connector.</p></article></body></html>',
            "text/html",
        )
        with patch("autodata_ingestion.http_connector.HttpSourceConnector") as connector_class:
            connector_class.return_value.fetch.return_value = [resource]
            with patch(
                "autodata_ingestion.bundle_persistence.persist_source_bundle",
                return_value={"status": "ready", "vehicle_id": "vehicle-1"},
            ) as persist:
                with patch.dict(
                    "os.environ",
                    {"AUTODATA_SOURCE_PERSIST": "1", "AUTODATA_SOURCE_REQUEST_HEADERS_JSON": ""},
                    clear=False,
                ):
                    result = run_vehicle_knowledge(
                        json.dumps(
                            {
                                "vehicle": {
                                    "year": 1999,
                                    "make": "Chevy",
                                    "model": "Silverado 1500",
                                    "region": "US",
                                    "drivetrain": "2wd",
                                    "engine_displacement_l": 5.3,
                                },
                                "query": "brake connector",
                                "source_uri_template": source_uri,
                            }
                        )
                    )

        self.assertEqual(result["status"], "fetched")
        self.assertEqual(result["results"][0]["article"]["article_id"], "TSB-42")
        connector_class.assert_called_once()
        self.assertEqual(
            connector_class.call_args.args[0],
            "https://source.example/chevrolet-silverado-1500-1999-us/2WD/5.3?q=brake%20connector",
        )
        persist.assert_called_once()
        self.assertEqual(persist.call_args.kwargs["adapter_name"], "knowledge-fallback")

    def test_configured_knowledge_request_reads_database_catalog_when_not_supplied(self):
        from autodata_ingestion.worker import run_vehicle_knowledge

        with patch(
            "autodata_ingestion.knowledge_catalog.load_vehicle_knowledge_catalog",
            return_value=[
                {
                    "vehicle_key": "chevrolet-silverado-1500-1999-us",
                    "kind": "article",
                    "article": {
                        "article_id": "TSB-42",
                        "title": "Brake connector bulletin",
                    },
                    "evidence": [],
                }
            ],
        ) as load_catalog:
            result = run_vehicle_knowledge(
                json.dumps(
                    {
                        "vehicle": {
                            "year": 1999,
                            "make": "Chevy",
                            "model": "Silverado 1500",
                            "region": "US",
                        },
                        "query": "brake connector",
                    }
                )
            )

        self.assertEqual(result["status"], "cache_hit")
        self.assertEqual(result["results"][0]["article"]["article_id"], "TSB-42")
        load_catalog.assert_called_once()

    def test_configured_source_directory_runs_the_normalization_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "name.json").write_bytes(b'{"body":"2019 Cadillac Escalade ESV - 2WD"}')
            (root / "procedure").write_bytes(b"<html><body>Connector procedure</body></html>")

            with patch.dict(
                "os.environ",
                {
                    "AUTODATA_SOURCE_DIRECTORY": directory,
                    "AUTODATA_SOURCE_VERSION": "drop-v1",
                    "AUTODATA_SOURCE_REGION": "US",
                    "AUTODATA_SOURCE_PERSIST": "0",
                },
                clear=False,
            ):
                result = run_once()

        self.assertEqual(result["worker"], "ingestion")
        self.assertEqual(result["lane"], "fast")
        self.assertEqual(result["bundle_status"], "ready")
        self.assertEqual(result["quality_status"], "needs_review")
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["vehicle_key"], "cadillac-escalade-esv-2019-us")
        self.assertEqual(result["source_artifacts"], 2)
        self.assertEqual(result["quarantined"], 0)

    def test_configured_http_source_runs_through_the_same_pipeline(self):
        resource = SourceResource.from_bytes(
            "https://source.example/vehicle",
            "http-drop-v1",
            b'{"body":"2019 Cadillac Escalade ESV"}',
            "application/json",
        )
        with patch("autodata_ingestion.http_connector.HttpSourceConnector") as connector_class:
            connector_class.return_value.fetch.return_value = [resource]
            with patch.dict(
                "os.environ",
                {
                    "AUTODATA_SOURCE_DIRECTORY": "",
                    "AUTODATA_SOURCE_URI": "https://source.example/vehicle",
                    "AUTODATA_SOURCE_VERSION": "http-drop-v1",
                    "AUTODATA_SOURCE_REGION": "US",
                    "AUTODATA_SOURCE_REQUEST_HEADERS_JSON": '{"X-Source-Token":"local-test"}',
                    "AUTODATA_SOURCE_PERSIST": "0",
                },
                clear=False,
            ):
                result = run_once()

        connector_class.assert_called_once()
        self.assertEqual(connector_class.call_args.args[:2], ("https://source.example/vehicle", "http-drop-v1"))
        self.assertEqual(connector_class.call_args.kwargs["request_headers"], {"X-Source-Token": "local-test"})
        self.assertEqual(result["bundle_status"], "ready")
        self.assertEqual(result["quality_status"], "needs_review")
        self.assertEqual(result["vehicle_key"], "cadillac-escalade-esv-2019-us")
        self.assertEqual(result["source_artifacts"], 1)

    def test_module_entrypoint_does_not_preload_itself(self):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
        environment["AUTODATA_WORKER_ONCE"] = "1"
        for variable in ("AUTODATA_SOURCE_DIRECTORY", "AUTODATA_SOURCE_URI"):
            environment.pop(variable, None)

        completed = subprocess.run(
            [sys.executable, "-m", "autodata_ingestion.worker"],
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertNotIn("RuntimeWarning", completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {"worker": "ingestion", "lane": "fast", "status": "idle"})

    def test_fast_event_json_dispatches_a_source_descriptor_through_the_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "vehicle.json").write_bytes(b'{"body":"2019 Cadillac Escalade ESV"}')
            fast_event = {
                "event_id": "event-1",
                "event_type": "dataset.fast.requested",
                "event_version": 1,
                "occurred_at": "2026-09-03T12:00:00+00:00",
                "producer": "payment-reconciler",
                "request_id": "request-1",
                "projection_id": "projection-1",
                "revision_id": None,
                "correlation_id": "correlation-1",
                "idempotency_key": "fast-request-1",
                "payload": {
                    "vehicle_key": "cadillac-escalade-esv-2019-us",
                    "region": "US",
                    "source": {"kind": "directory", "location": directory, "version": "drop-v1"},
                },
            }
            with patch.dict(
                "os.environ",
                {
                    "AUTODATA_SOURCE_DIRECTORY": "",
                    "AUTODATA_SOURCE_URI": "",
                    "AUTODATA_FAST_EVENT_JSON": json.dumps(fast_event),
                    "AUTODATA_SOURCE_PERSIST": "0",
                },
                clear=False,
            ):
                result = run_once()

        self.assertEqual(result["request_id"], "request-1")
        self.assertEqual(result["projection_id"], "projection-1")
        self.assertEqual(result["idempotency_key"], "fast-request-1")
        self.assertEqual(result["bundle_status"], "ready")
        self.assertEqual(result["vehicle_key"], "cadillac-escalade-esv-2019-us")

    def test_persistent_fast_event_passes_projection_identity_to_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "vehicle.json").write_bytes(b'{"body":"2019 Cadillac Escalade ESV"}')
            fast_event = {
                "event_id": "event-2",
                "event_type": "dataset.fast.requested",
                "event_version": 1,
                "occurred_at": "2026-09-03T12:00:00+00:00",
                "producer": "payment-reconciler",
                "request_id": "request-2",
                "projection_id": "projection-2",
                "correlation_id": "correlation-2",
                "idempotency_key": "fast-request-2",
                "payload": {
                    "vehicle_key": "cadillac-escalade-esv-2019-us",
                    "region": "US",
                    "source": {"kind": "directory", "location": directory, "version": "drop-v2"},
                },
            }
            with patch(
                "autodata_ingestion.bundle_persistence.persist_source_bundle",
                return_value={"status": "viewable", "publication": {"published": True}},
            ) as persist:
                with patch.dict(
                    "os.environ",
                    {
                        "AUTODATA_SOURCE_DIRECTORY": "",
                        "AUTODATA_SOURCE_URI": "",
                        "AUTODATA_FAST_EVENT_JSON": json.dumps(fast_event),
                        "AUTODATA_SOURCE_PERSIST": "1",
                    },
                    clear=False,
                ):
                    result = run_once()

        self.assertEqual(result["persistence_status"], "viewable")
        publication = persist.call_args.kwargs["publication"]
        self.assertEqual(publication.request_id, "request-2")
        self.assertEqual(publication.projection_id, "projection-2")
        self.assertEqual(publication.idempotency_key, "fast-request-2")

    def test_nats_once_delegates_to_the_durable_consumer(self):
        with patch("autodata_ingestion.consumer.consume_once", new_callable=AsyncMock) as consume:
            consume.return_value = {"status": "idle", "received": 0}

            from autodata_ingestion.worker import run_nats_once

            result = run_nats_once()

        self.assertEqual(result, {"status": "idle", "received": 0})
        consume.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
