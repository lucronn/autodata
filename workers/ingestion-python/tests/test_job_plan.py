import json
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autodata_ingestion.job_plan import (  # noqa: E402
    build_quote_and_procedure,
    compose_procedure_revision,
    compose_procedure_with_llm,
    plan_job,
    translate_job_query_with_llm,
)
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


def test_shared_provider_bucket_does_not_assign_one_article_to_every_component():
    alternator = article(
        "P:alternator",
        "alternator",
        [{"operation_id": "replace-alternator", "action": "Alternator R&R", "duration_hours": 0.7}],
    )
    alternator["bucket"] = "Starter & Alternator Replacement Procedures"

    result = plan_job(
        "replace the alternator and starter",
        VEHICLE,
        catalog=[alternator],
    )

    assert result["selected_articles"] == ["P:alternator"]
    assert "missing_article:starter" in result["review_reasons"]


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
                    "operation_id": "shared-drive-belt",
                    "action": "Complete the shared drive-belt work once.",
                    "components": ["oil_pump", "water_pump"],
                    "category": "required",
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
        {
            "total_labor_hours": 5.0,
            "operations": [{
                    "operation_id": "shared-drive-belt",
                    "action": "Complete the shared drive-belt work once.",
                    "components": ["oil_pump", "water_pump"],
                    "category": "required",
                    "source_article_ids": ["P:oil", "P:water"],
                    "evidence_ids": ["labor-evidence"],
            }],
        },
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


def test_build_quote_separates_support_categories_and_explains_shared_labor_deduction():
    articles = [
        article(
            "brake-line",
            "brake_line",
            [
                {
                    "operation_id": "vehicle-access",
                    "action": "Raise and support vehicle",
                    "duration_hours": 0.4,
                    "category": "required",
                    "shared_work_scope": "vehicle-access",
                    "evidence_ids": ["evidence-brake-line"],
                },
                {
                    "operation_id": "replace-brake-line",
                    "action": "Replace brake line",
                    "duration_hours": 1.2,
                    "category": "required",
                    "evidence_ids": ["evidence-brake-line"],
                },
            ],
            images=[{"url": "https://source.test/brake-line.svg"}],
        )
        | {
            "parts": [{"part_id": "brake-line-kit", "name": "Brake line kit", "amount": 50.0, "currency": "USD"}],
            "safety_warnings": [{"message": "Depressurize the brake system before opening the line.", "evidence_ids": ["evidence-brake-line"]}],
        },
        article(
            "brake-bleeding",
            "brake_bleeding",
            [
                {
                    "operation_id": "vehicle-access",
                    "action": "Raise and support vehicle",
                    "duration_hours": 0.4,
                    "category": "required",
                    "shared_work_scope": "vehicle-access",
                    "evidence_ids": ["evidence-brake-bleeding"],
                },
                {
                    "operation_id": "bleed-brakes",
                    "action": "Bleed brake system",
                    "duration_hours": 0.6,
                    "category": "required",
                    "evidence_ids": ["evidence-brake-bleeding"],
                },
            ],
        )
        | {
            "supporting_for": ["brake_line"],
            "support_category": "required",
            "parts": [{"part_id": "brake-fluid", "name": "Brake fluid", "amount": 18.99, "currency": "USD"}],
        },
        article(
            "brake-inspection",
            "brake_inspection",
            [
                {
                    "operation_id": "vehicle-access",
                    "action": "Raise and support vehicle",
                    "duration_hours": 0.4,
                    "category": "recommended",
                    "shared_work_scope": "vehicle-access",
                    "evidence_ids": ["evidence-brake-inspection"],
                },
                {
                    "operation_id": "inspect-brake-system",
                    "action": "Inspect brake system",
                    "duration_hours": 0.4,
                    "category": "recommended",
                    "evidence_ids": ["evidence-brake-inspection"],
                },
            ],
        )
        | {"supporting_for": ["brake_line"], "support_category": "recommended"},
    ]

    result = build_quote_and_procedure("replace the brake line", VEHICLE, articles)

    assert result["status"] == "needs_review"
    quote = result["quote"]
    assert quote["required_hours"] == 2.6
    assert quote["recommended_hours"] == 0.8
    assert quote["total_hours"] == 2.6
    assert quote["overlap_hours_removed"] == 0.8
    assert quote["overlap_operations"] == [
        {
            "operation_id": "vehicle-access",
            "shared_work_scope": "vehicle-access",
            "counted_once_for": ["brake_bleeding", "brake_inspection", "brake_line"],
            "raw_hours": 1.2,
            "counted_hours": 0.4,
            "deducted_hours": 0.8,
        }
    ]
    assert result["parts"]["subtotal"] == 68.99
    assert result["parts"]["markup_applied"] is False
    assert "evidence-brake-line" in quote["evidence_ids"]
    assert result["procedure"]["review_state"] == "UNREVIEWED"
    assert any("Depressurize" in warning["message"] for warning in result["procedure"]["warnings"])


def test_compose_procedure_revision_rejects_a_step_with_an_unsupported_component():
    quote = build_quote_and_procedure(
        "replace the alternator",
        VEHICLE,
        [article("alternator-article", "alternator", [{"operation_id": "replace-alternator", "action": "Replace alternator", "duration_hours": 1.0}])],
    )

    class FakeMercury:
        def complete_json(self, _prompt):
            return {
                "title": "Alternator service",
                "steps": [{
                    "action": "Replace the unsupported transmission",
                    "operation_id": "replace-alternator",
                    "components": ["transmission"],
                    "category": "required",
                    "source_article_ids": ["alternator-article"],
                    "evidence_ids": ["evidence-alternator-article"],
                }],
                "warnings": [],
            }

    with pytest.raises(ValueError, match="unsupported"):
        compose_procedure_revision(quote, [article("alternator-article", "alternator", [{"operation_id": "replace-alternator", "action": "Replace alternator", "duration_hours": 1.0}])], mercury_client=FakeMercury())


def test_deduplicates_one_article_that_covers_multiple_requested_components():
    combined = {
        "article_id": "combined-brake-article",
        "title": "Alternator and starter service",
        "components": ["alternator", "starter"],
        "operations": [{
            "operation_id": "shared-bench-setup",
            "action": "Set up the shared work area",
            "duration_hours": 0.5,
            "components": ["alternator", "starter"],
            "evidence_ids": ["combined-evidence"],
        }],
        "evidence_ids": "combined-evidence",
    }

    result = build_quote_and_procedure(
        "replace the alternator and starter",
        VEHICLE,
        [combined],
    )

    assert result["selected_articles"] == ["combined-brake-article"]
    assert result["labor"]["total_hours"] == 0.5
    assert len(result["procedure"]["steps"]) == 1
    assert result["procedure"]["steps"][0]["components"] == ["alternator", "starter"]


def test_category_subtotals_expose_raw_and_counted_values_for_reconstruction():
    result = build_quote_and_procedure(
        "replace the alternator and starter",
        VEHICLE,
        [
            article("alternator-article", "alternator", [{
                "operation_id": "battery-isolation",
                "action": "Disconnect battery",
                "duration_hours": 0.25,
                "evidence_ids": ["alternator-evidence"],
            }]),
            article("starter-article", "starter", [{
                "operation_id": "battery-isolation",
                "action": "Disconnect battery",
                "duration_hours": 0.25,
                "evidence_ids": ["starter-evidence"],
            }]),
        ],
    )

    labor = result["labor"]
    assert labor["category_subtotals"] == {
        "required": {
            "raw_hours": 0.5,
            "counted_hours": 0.25,
            "overlap_hours_removed": 0.25,
        },
        "recommended": {
            "raw_hours": 0.0,
            "counted_hours": 0.0,
            "overlap_hours_removed": 0.0,
        },
    }
    assert labor["required_hours"] + labor["recommended_hours"] == labor["standalone_hours"]
    assert sum(labor["category_hours_after_overlap"].values()) == labor["total_hours"]


def test_singular_article_and_operation_evidence_ids_are_normalized():
    result = build_quote_and_procedure(
        "replace the alternator",
        VEHICLE,
        [{
            "article_id": "alternator-singular-evidence",
            "title": "Alternator replacement",
            "component": "alternator",
            "evidence_id": "article-evidence",
            "operations": [{
                "operation_id": "replace-alternator",
                "action": "Replace alternator",
                "duration_hours": 1.0,
                "evidence_id": "operation-evidence",
            }],
        }],
    )

    assert result["procedure"]["steps"][0]["evidence_ids"] == [
        "article-evidence",
        "operation-evidence",
    ]
    assert result["quote"]["evidence_ids"] == ["article-evidence", "operation-evidence"]


def test_mercury_prompt_contains_selected_evidence_context_not_only_ids():
    captured = {}

    class FakeMercury:
        def complete_json(self, prompt):
            captured["payload"] = json.loads(prompt)
            return {
                "title": "Alternator service",
                "steps": [{
                    "operation_id": "replace-alternator",
                    "action": "Replace alternator",
                    "components": ["alternator"],
                    "category": "required",
                    "source_article_ids": ["alternator-context"],
                    "evidence_ids": ["evidence-context"],
                    "requires_review": False,
                }],
                "warnings": [],
                "requires_review": False,
            }

    source = {
        "article_id": "alternator-context",
        "title": "Alternator replacement",
        "component": "alternator",
        "operations": [{
            "operation_id": "replace-alternator",
            "action": "Replace alternator",
            "duration_hours": 1.0,
            "evidence_ids": ["evidence-context"],
        }],
        "evidence": [{
            "evidence_id": "evidence-context",
            "excerpt": "Remove the alternator after isolating the battery.",
            "locator": "body.steps[2]",
            "source_uri": "https://source.test/alternator.html",
            "source_watermark": "source-v7",
            "artifact_key": "source/alternator.html",
        }],
    }

    result = compose_procedure_with_llm(
        FakeMercury(),
        "replace the alternator",
        VEHICLE,
        [source],
        {
            "operations": [{
                "operation_id": "replace-alternator",
                "action": "Replace alternator",
                "components": ["alternator"],
                "category": "required",
                "source_article_ids": ["alternator-context"],
                "evidence_ids": ["evidence-context"],
            }],
        },
        {"title": "fallback", "steps": [], "warnings": [], "requires_review": True},
    )

    assert result["generation"] == "mercury-2"
    assert captured["payload"]["articles"][0]["evidence"] == [{
        "evidence_id": "evidence-context",
        "excerpt": "Remove the alternator after isolating the battery.",
        "locator": "body.steps[2]",
        "source_article_id": "alternator-context",
        "source_uri": "https://source.test/alternator.html",
        "source_watermark": "source-v7",
        "artifact_key": "source/alternator.html",
    }]


def test_mercury_rejects_operation_id_not_bound_to_a_source_operation():
    class FakeMercury:
        def complete_json(self, _prompt):
            return {
                "title": "Alternator service",
                "steps": [{
                    "operation_id": "unbound-operation",
                    "action": "Replace alternator",
                    "components": ["alternator"],
                    "category": "required",
                    "source_article_ids": ["alternator-source"],
                    "evidence_ids": ["alternator-evidence"],
                }],
                "warnings": [],
            }

    with pytest.raises(ValueError, match="source-bound"):
        compose_procedure_with_llm(
            FakeMercury(),
            "replace the alternator",
            VEHICLE,
            [{
                "article_id": "alternator-source",
                "title": "Alternator replacement",
                "component": "alternator",
                "operations": [{
                    "operation_id": "actual-operation",
                    "action": "Replace alternator",
                    "evidence_ids": ["alternator-evidence"],
                }],
                "evidence_ids": ["alternator-evidence"],
            }],
            {
                "operations": [{
                    "operation_id": "unbound-operation",
                    "action": "Replace alternator",
                    "components": ["alternator"],
                    "category": "required",
                    "source_article_ids": ["alternator-source"],
                    "evidence_ids": ["alternator-evidence"],
                }],
            },
            {"title": "fallback", "steps": [], "warnings": [], "requires_review": True},
        )


def test_missing_article_id_cannot_produce_a_ready_lineage():
    result = build_quote_and_procedure(
        "replace the alternator",
        VEHICLE,
        [{
            "title": "Alternator replacement",
            "component": "alternator",
            "operations": [{
                "operation_id": "replace-alternator",
                "action": "Replace alternator",
                "duration_hours": 1.0,
            }],
            "evidence_ids": ["alternator-evidence"],
        }],
    )

    assert result["status"] == "needs_review"
    assert "missing_article_id_lineage" in result["review_reasons"]
    assert result["selected_articles"] == []


def test_missing_operation_scope_does_not_infer_an_article_component_union():
    result = build_quote_and_procedure(
        "replace the alternator and starter",
        VEHICLE,
        [{
            "article_id": "multi-component-source",
            "title": "Alternator and starter service",
            "components": ["alternator", "starter"],
            "operations": [{
                "operation_id": "shared-work",
                "action": "Perform the shared service",
                "duration_hours": 1.0,
                "evidence_ids": ["multi-component-evidence"],
            }],
            "evidence_ids": ["multi-component-evidence"],
        }],
    )

    assert result["status"] == "needs_review"
    assert "ambiguous_operation_scope:shared-work" in result["review_reasons"]


def test_duplicate_visual_source_merges_all_article_and_evidence_lineage():
    image_bytes = b"\x89PNG\r\n\x1a\nvisual-fixture"
    articles = [
        article(
            "alternator-visual-source",
            "alternator",
            [{
                "operation_id": "replace-alternator",
                "action": "Replace alternator",
                "duration_hours": 1.0,
                "evidence_ids": ["alternator-visual-evidence"],
            }],
            images=[{
                "source_bytes": image_bytes,
                "source_uri": "https://source.test/shared.png",
                "evidence_ids": ["alternator-visual-evidence"],
            }],
        ),
        article(
            "starter-visual-source",
            "starter",
            [{
                "operation_id": "replace-starter",
                "action": "Replace starter",
                "duration_hours": 1.0,
                "evidence_ids": ["starter-visual-evidence"],
            }],
            images=[{
                "source_bytes": image_bytes,
                "source_uri": "https://source.test/shared.png",
                "evidence_ids": ["starter-visual-evidence"],
            }],
        ),
    ]

    result = build_quote_and_procedure(
        "replace the alternator and starter", VEHICLE, articles
    )

    assert len(result["visual_artifacts"]) == 1
    artifact = result["visual_artifacts"][0]
    assert artifact["source_article_ids"] == [
        "alternator-visual-source",
        "starter-visual-source",
    ]
    assert artifact["evidence_ids"] == [
        "alternator-visual-evidence",
        "evidence-alternator-visual-source",
        "evidence-starter-visual-source",
        "starter-visual-evidence",
    ]


def test_conflicting_part_currencies_have_no_numeric_subtotal():
    result = build_quote_and_procedure(
        "replace the alternator and starter",
        VEHICLE,
        [
            article(
                "alternator-currency",
                "alternator",
                [{"operation_id": "replace-alternator", "action": "Replace alternator", "duration_hours": 1.0}],
            ) | {"parts": [{"part_id": "alternator-kit", "amount": 10, "currency": "USD"}]},
            article(
                "starter-currency",
                "starter",
                [{"operation_id": "replace-starter", "action": "Replace starter", "duration_hours": 1.0}],
            ) | {"parts": [{"part_id": "starter-kit", "amount": 20, "currency": "EUR"}]},
        ],
    )

    assert result["parts"]["currency"] == "MULTI"
    assert result["parts"]["subtotal"] is None
    assert "conflicting_currencies" in result["review_reasons"]


def test_mercury_step_must_match_exact_operation_provenance():
    source = article(
        "alternator-article",
        "alternator",
        [{
            "operation_id": "replace-alternator",
            "action": "Replace alternator",
            "duration_hours": 1.0,
            "evidence_ids": ["evidence-alternator-article"],
        }],
    ) | {"body": "Remove the alternator and install the replacement."}
    quote = build_quote_and_procedure("replace the alternator", VEHICLE, [source])

    class FakeMercury:
        def complete_json(self, _prompt):
            return {
                "title": "Alternator service",
                "steps": [{
                    "operation_id": "replace-alternator",
                    "action": "Replace the transmission",
                    "components": ["alternator"],
                    "category": "required",
                    "source_article_ids": ["alternator-article"],
                    "evidence_ids": ["evidence-alternator-article"],
                }],
                "warnings": [],
            }

    with pytest.raises(ValueError, match="action provenance"):
        compose_procedure_revision(quote, [source], mercury_client=FakeMercury())


def test_mercury_required_operation_exclusion_forces_review():
    source = article(
        "alternator-article",
        "alternator",
        [{
            "operation_id": "replace-alternator",
            "action": "Replace alternator",
            "duration_hours": 1.0,
            "evidence_ids": ["evidence-alternator-article"],
        }],
    ) | {"body": "Remove the alternator and install the replacement."}
    quote = build_quote_and_procedure("replace the alternator", VEHICLE, [source])

    class FakeMercury:
        def complete_json(self, _prompt):
            return {
                "title": "Alternator service",
                "steps": [],
                "warnings": [],
                "excluded_operation_ids": ["replace-alternator"],
                "requires_review": False,
            }

    result = compose_procedure_revision(quote, [source], mercury_client=FakeMercury())

    assert result["excluded_operation_ids"] == ["replace-alternator"]
    assert result["requires_review"] is True


def test_mercury_rejects_step_with_nonmatching_article_or_evidence_provenance():
    source = article(
        "alternator-article",
        "alternator",
        [{
            "operation_id": "replace-alternator",
            "action": "Replace alternator",
            "duration_hours": 1.0,
            "evidence_ids": ["evidence-alternator-article"],
        }],
    )
    quote = build_quote_and_procedure("replace the alternator", VEHICLE, [source])

    class FakeMercury:
        def complete_json(self, _prompt):
            return {
                "title": "Alternator service",
                "steps": [{
                    "operation_id": "replace-alternator",
                    "action": "Replace alternator",
                    "components": ["alternator"],
                    "category": "required",
                    "source_article_ids": ["another-article"],
                    "evidence_ids": ["another-evidence"],
                }],
                "warnings": [],
            }

    with pytest.raises(ValueError, match="provenance"):
        compose_procedure_revision(quote, [source], mercury_client=FakeMercury())


def test_mercury_rejects_unbound_or_unstructured_safety_warning():
    source = article(
        "alternator-article",
        "alternator",
        [{
            "operation_id": "replace-alternator",
            "action": "Replace alternator",
            "duration_hours": 1.0,
            "evidence_ids": ["evidence-alternator-article"],
        }],
    ) | {
        "safety_warnings": [{
            "warning_id": "alternator-safety",
            "message": "Disconnect the battery first.",
            "evidence_ids": ["evidence-alternator-article"],
        }]
    }
    quote = build_quote_and_procedure("replace the alternator", VEHICLE, [source])

    class FakeMercury:
        def complete_json(self, _prompt):
            return {
                "title": "Alternator service",
                "steps": [{
                    "operation_id": "replace-alternator",
                    "action": "Replace alternator",
                    "components": ["alternator"],
                    "category": "required",
                    "source_article_ids": ["alternator-article"],
                    "evidence_ids": ["evidence-alternator-article"],
                }],
                "warnings": ["Disconnect the battery first."],
            }

    with pytest.raises(ValueError, match="structured"):
        compose_procedure_revision(quote, [source], mercury_client=FakeMercury())


def test_public_builder_retains_deterministic_procedure_when_mercury_fails():
    source = article(
        "alternator-article",
        "alternator",
        [{
            "operation_id": "replace-alternator",
            "action": "Replace alternator",
            "duration_hours": 1.0,
            "evidence_ids": ["evidence-alternator-article"],
        }],
    )

    class FailingMercury:
        def complete_json(self, _prompt):
            raise RuntimeError("provider failed")

    result = build_quote_and_procedure(
        "replace the alternator",
        VEHICLE,
        [source],
        mercury_client=FailingMercury(),
    )

    assert result["status"] == "needs_review"
    assert "procedure_composition_failed" in result["review_reasons"]
    assert result["procedure"]["generation"] == "deterministic"
    assert result["procedure"]["steps"][0]["operation_id"] == "replace-alternator"


def test_public_builder_passes_complete_validated_context_to_mercury():
    source = article(
        "alternator-article",
        "alternator",
        [{
            "operation_id": "replace-alternator",
            "action": "Replace alternator",
            "duration_hours": 1.0,
            "evidence_ids": ["evidence-alternator-article"],
        }],
    ) | {"body": "Remove the alternator and install the replacement."}

    class InspectingMercury:
        def complete_json(self, prompt):
            import json

            self.payload = json.loads(prompt)
            return {
                "title": "Alternator service",
                "steps": [{
                    "operation_id": "replace-alternator",
                    "action": "Replace alternator",
                    "components": ["alternator"],
                    "category": "required",
                    "source_article_ids": ["alternator-article"],
                    "evidence_ids": ["evidence-alternator-article"],
                }],
                "warnings": [],
            }

    client = InspectingMercury()
    result = build_quote_and_procedure(
        "replace the alternator",
        VEHICLE,
        [source],
        mercury_client=client,
    )

    assert result["status"] == "ready"
    assert client.payload["quote"]["required_hours"] == 1.0
    assert client.payload["quote"]["quote_identity"] == result["quote_identity"]
    assert client.payload["quote"]["procedure"]["steps"][0]["operation_id"] == "replace-alternator"
    assert client.payload["articles"][0]["evidence_ids"] == ["evidence-alternator-article"]


def test_public_builder_vectorizes_source_images_and_returns_linked_refs():
    source = article(
        "alternator-article",
        "alternator",
        [{
            "operation_id": "replace-alternator",
            "action": "Replace alternator",
            "duration_hours": 1.0,
            "evidence_ids": ["evidence-alternator-article"],
        }],
    ) | {
        "images": [{
            "source_bytes": b"\x89PNG\r\n\x1a\nsource-image",
            "source_uri": "https://source.test/alternator.png",
            "evidence_id": "evidence-alternator-article",
        }]
    }

    class FakeVectorizer:
        def __init__(self):
            self.calls = []

        def redraw(self, source_bytes, *, source_uri):
            self.calls.append((source_bytes, source_uri))
            return {
                "derived_bytes": b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
                "media_type": "image/svg+xml",
                "source_uri": source_uri,
                "source_object_key": "source/image.png",
                "derived_object_key": "derived/image.svg",
                "source_artifact_id": "visual-source-1",
                "derived_artifact_id": "visual-derived-1",
                "review_state": "pending",
                "label": "AI-enhanced / UNREVIEWED",
            }

    vectorizer = FakeVectorizer()
    result = build_quote_and_procedure(
        "replace the alternator",
        VEHICLE,
        [source],
        vectorizer=vectorizer,
    )

    assert vectorizer.calls == [(b"\x89PNG\r\n\x1a\nsource-image", "https://source.test/alternator.png")]
    artifact = result["visual_artifacts"][0]
    uuid.UUID(artifact["source_ref"]["artifact_id"])
    uuid.UUID(artifact["derived_ref"]["artifact_id"])
    assert artifact["source_ref"]["provider_artifact_id"] == "visual-source-1"
    assert artifact["derived_ref"]["provider_artifact_id"] == "visual-derived-1"
    assert artifact["source_ref"]["article_id"] == "alternator-article"
    assert artifact["derived_ref"]["review_state"] == "pending"
    assert result["source_visual_refs"] == [artifact["source_ref"]]
    assert result["derived_visual_refs"] == [artifact["derived_ref"]]
    assert result["status"] == "needs_review"


def test_nonfinite_or_conflicting_parts_force_review_without_nonfinite_subtotal():
    source = article("alternator-article", "alternator", [{
        "operation_id": "replace-alternator",
        "action": "Replace alternator",
        "duration_hours": 1.0,
        "evidence_ids": ["evidence-alternator-article"],
    }]) | {
        "parts": [
            {"part_id": "belt", "name": "Belt", "amount": "NaN"},
            {"part_id": "filter", "name": "Filter", "amount": 10.0},
        ]
    }
    conflicting = article("starter-article", "starter", [{
        "operation_id": "replace-starter",
        "action": "Replace starter",
        "duration_hours": 1.0,
        "evidence_ids": ["evidence-starter-article"],
    }]) | {"parts": [{"part_id": "filter", "name": "Filter", "amount": 12.0}]}

    result = build_quote_and_procedure(
        "replace the alternator and starter",
        VEHICLE,
        [source, conflicting],
    )

    assert result["status"] == "needs_review"
    assert "invalid_part_price:belt" in result["review_reasons"]
    assert "conflicting_part_price:filter" in result["review_reasons"]
    assert result["parts"]["subtotal"] == 0.0


def test_composed_procedure_includes_source_instructions_not_only_labor_label():
    source_article = article(
        "brake-line-source",
        "brake_line",
        [{
            "operation_id": "replace-brake-line",
            "action": "Replace brake line",
            "duration_hours": 1.2,
            "evidence_ids": ["evidence-brake-line-source"],
        }],
    ) | {
        "body": "Remove the damaged line and clean the fittings before installation.",
        "content_evidence_id": "evidence-brake-line-content",
        "steps": [
            "Raise and support the vehicle.",
            "Remove the damaged line.",
            "Bleed the brake system and check for leaks.",
        ],
    }

    result = build_quote_and_procedure(
        "brake line replacement procedure",
        VEHICLE,
        [source_article],
    )

    procedure = result["procedure"]
    assert procedure["content_status"] == "complete"
    assert procedure["steps"][0]["action"] == "Replace brake line"
    assert procedure["steps"][0]["instructions"] == source_article["steps"]
    assert procedure["steps"][0]["source_article_ids"] == ["brake-line-source"]
    assert procedure["steps"][0]["evidence_ids"] == [
        "evidence-brake-line-content",
        "evidence-brake-line-source",
    ]


def test_title_only_article_is_partial_and_explains_missing_procedure_content():
    result = build_quote_and_procedure(
        "brake line replacement procedure",
        VEHICLE,
        [article(
            "brake-line-title-only",
            "brake_line",
            [{
                "operation_id": "replace-brake-line",
                "action": "Replace brake line",
                "duration_hours": 1.2,
                "evidence_ids": ["evidence-brake-line-title-only"],
            }],
        )],
    )

    procedure = result["procedure"]
    assert procedure["content_status"] == "partial"
    assert procedure["requires_review"] is True
    assert procedure["steps"][0]["instructions"] == []
    assert "procedure_content_unavailable" in result["review_reasons"]
    assert any(
        warning["warning_id"] == "procedure_content_unavailable"
        for warning in procedure["warnings"]
    )
