import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autodata_ingestion.derived_article_persistence import derived_article_identity  # noqa: E402


def test_derived_article_identity_is_stable_and_does_not_use_llm_chosen_id():
    result = {
        "derived_article": {"article_id": "combined:vehicle:alternator+starter:v1"},
        "selected_articles": ["starter", "alternator"],
        "labor": {"total_labor_hours": 4.25},
        "procedure": {"title": "Alternator and starter service", "steps": []},
        "images": [{"url": "https://source.test/diagram.svg"}],
    }

    first = derived_article_identity(result)
    second = derived_article_identity(result)

    assert first == second
    assert first[0] == "combined:vehicle:alternator+starter:v1"
    assert len(first[1]) == 64


def test_derived_article_identity_includes_vehicle_categories_watermarks_and_visuals():
    base = {
        "derived_article": {"article_id": "combined:vehicle:brake_line:v2"},
        "vehicle": {"vehicle_id": "vehicle-1", "year": 1997, "make": "Toyota", "model": "RAV4", "region": "US"},
        "requested_components": ["brake_line"],
        "selected_articles": ["brake-line"],
        "labor": {
            "required_hours": 2.0,
            "recommended_hours": 0.5,
            "overlap_hours_removed": 0.25,
            "required_operations": [{"operation_id": "replace-line"}],
            "recommended_operations": [{"operation_id": "inspect"}],
        },
        "source_watermarks": ["source-v1"],
        "quote_identity": "quote-v1",
        "procedure_revision": "procedure-v1",
        "procedure": {"title": "Brake line service", "steps": []},
        "visual_artifacts": [{"source_artifact_key": "source/line.png", "derived_artifact_key": "derived/line.svg"}],
    }

    same = dict(base)
    changed = {**base, "source_watermarks": ["source-v2"]}

    assert derived_article_identity(base) == derived_article_identity(same)
    assert derived_article_identity(base)[1] != derived_article_identity(changed)[1]
