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
