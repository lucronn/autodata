import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autodata_ingestion.job_plan import compose_procedure_with_llm, plan_job, translate_job_query_with_llm  # noqa: E402
from autodata_ingestion.worker import _cached_derived_job_plan  # noqa: E402


VEHICLE = {
    "vehicle_id": "vehicle-1999-silverado",
    "year": 1999,
    "make": "Chevrolet",
    "model": "Silverado 1500",
    "region": "US",
    "drivetrain": "2WD",
    "engine_displacement_l": 5.3,
}


def article(article_id, component, operations, *, images=None):
    return {
        "article_id": article_id,
        "title": f"{component.title()} replacement",
        "component": component,
        "operations": operations,
        "evidence": [{"evidence_id": f"evidence-{article_id}", "locator": f"{article_id}:body"}],
        "images": images or [],
    }


def test_combines_component_labor_once_for_shared_operation_and_keeps_images():
    articles = [
        article(
            "alternator-article",
            "alternator",
            [
                {"operation_id": "battery-isolation", "action": "Disconnect battery", "duration_hours": 0.25, "evidence_ids": ["evidence-alternator-article"]},
                {"operation_id": "remove-alternator", "action": "Remove alternator", "duration_hours": 1.5, "evidence_ids": ["evidence-alternator-article"]},
            ],
            images=[{"url": "https://source.test/alternator-diagram.svg", "alt": "Alternator diagram"}],
        ),
        article(
            "starter-article",
            "starter",
            [
                {"operation_id": "battery-isolation", "action": "Disconnect battery", "duration_hours": 0.25, "evidence_ids": ["evidence-starter-article"]},
                {"operation_id": "remove-starter", "action": "Remove starter", "duration_hours": 2.5, "evidence_ids": ["evidence-starter-article"]},
            ],
        ),
    ]

    result = plan_job(
        "replace the alternator and starter",
        VEHICLE,
        catalog=articles,
    )

    assert result["status"] == "ready"
    assert result["labor"] == {
        "basis": "one_technician_standard_hours",
        "standalone_hours": 4.5,
        "overlap_hours": 0.25,
        "total_labor_hours": 4.25,
        "confidence": 1.0,
        "assumptions": ["operations with the same stable operation_id are shared and counted once"],
        "operations": [
            {
                "operation_id": "battery-isolation",
                "action": "Disconnect battery",
                "duration_hours": 0.25,
                "components": ["alternator", "starter"],
                "evidence_ids": ["evidence-alternator-article", "evidence-starter-article"],
                "origin": "source_operation",
            },
            {
                "operation_id": "remove-alternator",
                "action": "Remove alternator",
                "duration_hours": 1.5,
                "components": ["alternator"],
                "evidence_ids": ["evidence-alternator-article"],
                "origin": "source_operation",
            },
            {
                "operation_id": "remove-starter",
                "action": "Remove starter",
                "duration_hours": 2.5,
                "components": ["starter"],
                "evidence_ids": ["evidence-starter-article"],
                "origin": "source_operation",
            },
        ],
    }
    assert result["procedure"]["requires_review"] is False
    assert result["procedure"]["steps"][0]["components"] == ["alternator", "starter"]
    assert result["procedure"]["steps"][0]["evidence_ids"] == ["evidence-alternator-article", "evidence-starter-article"]
    assert result["images"] == [{"url": "https://source.test/alternator-diagram.svg", "alt": "Alternator diagram", "article_id": "alternator-article"}]


def test_returns_review_state_when_a_requested_component_is_missing():
    result = plan_job(
        "replace the alternator and starter",
        VEHICLE,
        catalog=[article("alternator-article", "alternator", [{"action": "Replace alternator", "duration_hours": 1.0}])],
    )

    assert result["status"] == "needs_review"
    assert "missing_article:starter" in result["review_reasons"]


def test_recognizes_multiword_pump_and_belt_components_from_natural_language():
    catalog = [
        article("oil-pump-article", "oil_pump", [{"action": "Replace oil pump", "duration_hours": 2.0}]),
        article("water-pump-article", "water_pump", [{"action": "Replace water pump", "duration_hours": 2.5}]),
        article("timing-belt-article", "timing_belt", [{"action": "Replace timing belt", "duration_hours": 3.0}]),
        article("power-steering-pump-article", "power_steering_pump", [{"action": "Replace power steering pump", "duration_hours": 1.5}]),
    ]

    result = plan_job(
        "oil pump, water pump, timing belt, and power steering pump replacement",
        VEHICLE,
        catalog=catalog,
    )

    assert result["requested_components"] == [
        "oil_pump",
        "water_pump",
        "timing_belt",
        "power_steering_pump",
    ]
    assert result["status"] == "ready"
    assert result["selected_articles"] == [
        "oil-pump-article",
        "water-pump-article",
        "timing-belt-article",
        "power-steering-pump-article",
    ]


def test_prefers_procedure_article_over_same_named_labor_row():
    catalog = [
        {
            "article_id": "L:oil-pump",
            "title": "Engine Oil Pump R&R",
            "bucket": "Labor",
            "operations": [{"action": "Oil pump labor", "duration_hours": 2.0}],
        },
        {
            "article_id": "P:oil-pump",
            "title": "Engine Oil Pump R&R",
            "bucket": "Engine Service",
            "operations": [{"action": "Replace oil pump", "duration_hours": 2.0}],
        },
    ]

    result = plan_job("oil pump replacement", VEHICLE, catalog=catalog)

    assert result["selected_articles"] == ["P:oil-pump"]


def test_mercury_translation_returns_only_allowlisted_autodata_component_intents():
    class FakeMercury:
        def complete_json(self, _prompt):
            return {
                "components": ["oil_pump", "water_pump"],
                "source_queries": [
                    {"component": "oil_pump", "article_terms": ["oil pump replacement"]},
                    {"component": "water_pump", "article_terms": ["coolant pump service"]},
                ],
            }

    result = translate_job_query_with_llm(
        FakeMercury(),
        "the coolant pump and oil pump are both leaking; what is the job?",
        VEHICLE,
    )

    assert result == {
        "components": ["oil_pump", "water_pump"],
        "source_queries": [
            {"component": "oil_pump", "article_terms": ["oil pump replacement"]},
            {"component": "water_pump", "article_terms": ["coolant pump service"]},
        ],
        "generation": "mercury-2",
    }


def test_mercury_translation_normalizes_single_component_string_to_array():
    class FakeMercury:
        def complete_json(self, _prompt):
            return {"components": "water_pump", "source_queries": []}

    result = translate_job_query_with_llm(
        FakeMercury(),
        "what cooling system service does this vehicle need?",
        VEHICLE,
    )

    assert result == {
        "components": ["water_pump"],
        "source_queries": [],
        "generation": "mercury-2",
    }


def test_mercury_composition_accepts_labor_evidence_on_source_steps():
    class FakeMercury:
        def complete_json(self, _prompt):
            return {
                "title": "Water pump and oil pump service",
                "steps": [{
                    "action": "Complete the shared drive-belt work once.",
                    "components": ["oil_pump", "water_pump"],
                    "source_article_ids": ["P:oil", "P:water"],
                    "evidence_ids": ["labor-evidence"],
                    "requires_review": False,
                }],
                "warnings": [],
                "requires_review": False,
            }

    result = compose_procedure_with_llm(
        FakeMercury(),
        "replace the oil pump and water pump",
        VEHICLE,
        [
            {
                "article_id": "P:oil",
                "title": "Engine Oil Pump R&R",
                "operations": [{"action": "Oil pump labor", "evidence_ids": ["labor-evidence"]}],
                "evidence": [{"evidence_id": "article-evidence"}],
            },
            {
                "article_id": "P:water",
                "title": "Water Pump R&R",
                "operations": [],
                "evidence": [{"evidence_id": "water-evidence"}],
            },
        ],
        {"total_labor_hours": 5.0},
        {"title": "fallback", "steps": [], "warnings": [], "requires_review": True},
    )

    assert result["generation"] == "mercury-2"
    assert result["steps"][0]["evidence_ids"] == ["labor-evidence"]


def test_returns_review_state_without_fabricating_unknown_labor():
    result = plan_job(
        "replace the alternator",
        VEHICLE,
        catalog=[article("alternator-article", "alternator", [{"action": "Replace alternator"}])],
    )

    assert result["status"] == "needs_review"
    assert result["labor"]["total_labor_hours"] is None
    assert "unknown_duration:replace-alternator" in result["review_reasons"]


def test_persisted_combined_article_is_returned_without_replanning():
    cached = [{
        "kind": "article",
        "article": {
            "article_id": "combined:1999-chevrolet-silverado-1500:alternator+starter:v1",
            "title": "Alternator and starter service",
            "status": "ready",
            "derived_components": ["alternator", "starter"],
            "derived_revision_id": "revision-2",
            "source_version": "fixture-v1",
            "source_article_ids": ["alternator-article", "starter-article"],
            "evidence_ids": ["evidence-alternator", "evidence-starter"],
            "labor": {"total_labor_hours": 4.25, "overlap_hours": 0.25},
            "procedure": {"title": "Alternator and starter service", "steps": []},
            "images": [{"url": "https://source.test/combined.png"}],
        },
    }]

    result = _cached_derived_job_plan("replace alternator and starter", VEHICLE, cached)

    assert result is not None
    assert result["cache_hit"] is True
    assert result["labor"]["total_labor_hours"] == 4.25
    assert result["derived_article"]["revision_id"] == "revision-2"
    assert result["images"] == [{"url": "https://source.test/combined.png"}]
