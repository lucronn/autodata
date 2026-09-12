import os
import sys
import types
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autodata_ingestion.derived_article_persistence import (  # noqa: E402
    _visual_lineage_keys,
    derived_article_identity,
    persist_derived_article,
)


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


def test_visual_lineage_contains_both_source_and_derived_keys():
    artifacts = [{
        "source_artifact_key": "source/diagram.png",
        "derived_artifact_key": "derived/diagram.svg",
        "source_object_key": "source/diagram.png",
        "derived_object_key": "derived/diagram.svg",
    }]

    assert _visual_lineage_keys(artifacts) == ["derived/diagram.svg", "source/diagram.png"]


class _RecordingCursor:
    def __init__(self):
        self.statements = []
        self._next_row = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params=()):
        self.statements.append((query, params))
        if "SELECT vehicle_id::text FROM vehicles" in query:
            self._next_row = ("00000000-0000-0000-0000-000000000001",)
        elif "INSERT INTO derived_articles" in query:
            self._next_row = ("00000000-0000-0000-0000-000000000002",)
        elif "SELECT derived_article_revision_id::text" in query:
            self._next_row = None
        elif "SELECT COALESCE(MAX(revision_number)" in query:
            self._next_row = (0,)
        else:
            self._next_row = None

    def fetchone(self):
        return self._next_row


class _RecordingConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        pass


def test_persistence_downgrades_reviewed_procedure_and_visual_and_serializes_revision_number():
    cursor = _RecordingCursor()
    connection = _RecordingConnection(cursor)
    fake_psycopg = types.ModuleType("psycopg")
    fake_psycopg.connect = lambda **_kwargs: connection
    fake_json = types.ModuleType("psycopg.types.json")
    fake_json.Jsonb = lambda value: value
    fake_types = types.ModuleType("psycopg.types")
    fake_types.json = fake_json

    result = {
        "status": "ready",
        "canonical_vehicle": {
            "vehicle_id": "00000000-0000-0000-0000-000000000001",
            "year": 1997,
            "make": "Toyota",
            "model": "RAV4",
        },
        "derived_article": {"article_id": "combined:vehicle:brake_line:v2"},
        "selected_articles": ["brake-line"],
        "labor": {"operations": []},
        "procedure": {
            "title": "Brake line service",
            "steps": [],
            "warnings": [{
                "warning_id": "warning-1",
                "message": "Verify the system is depressurized.",
                "source_article_ids": ["brake-line"],
                "evidence_ids": ["evidence-1"],
                "requires_review": True,
            }],
            "requires_review": True,
            "review_state": "UNREVIEWED",
            "review_label": "UNREVIEWED — human review pending",
            "excluded_operation_ids": ["operation-1"],
            "excluded_operation_reasons": {"operation-1": "required operation needs review"},
        },
        "review_state": "pending",
        "review_label": "pending human review",
        "requires_review": True,
        "review_reasons": ["procedure_requires_review"],
        "source": {"source_watermark": "source-v9"},
        "visual_artifacts": [{
            "source_artifact_key": "source/diagram.png",
            "derived_artifact_key": "derived/diagram.svg",
            "source_object_key": "source/diagram.png",
            "derived_object_key": "derived/diagram.svg",
            "review_state": "pending",
            "requires_review": True,
        }],
    }

    with patch.dict(
        sys.modules,
        {"psycopg": fake_psycopg, "psycopg.types": fake_types, "psycopg.types.json": fake_json},
    ), patch.dict(os.environ, {"AUTODATA_POSTGRES_PASSWORD": "test-password"}, clear=False):
        persisted = persist_derived_article(result, vehicle=result["canonical_vehicle"])

    revision_insert = next(
        params for query, params in cursor.statements if "INSERT INTO derived_article_revisions" in query
    )
    assert persisted["status"] == "persisted"
    assert revision_insert[12] == "needs_review"
    assert revision_insert[13] is None
    assert revision_insert[4] == "source-v9"
    provenance = revision_insert[9]
    assert provenance["procedure"]["warnings"][0]["warning_id"] == "warning-1"
    assert provenance["procedure"]["review_state"] == "UNREVIEWED"
    assert provenance["procedure"]["review_label"] == "UNREVIEWED — human review pending"
    assert provenance["procedure"]["requires_review"] is True
    assert provenance["procedure"]["excluded_operation_ids"] == ["operation-1"]
    assert provenance["procedure"]["excluded_operation_reasons"] == {
        "operation-1": "required operation needs review",
    }
    assert provenance["review_state"] == "pending"
    assert provenance["review_label"] == "pending human review"
    assert provenance["requires_review"] is True
    assert provenance["review_reasons"] == ["procedure_requires_review"]
    assert any("pg_advisory_xact_lock" in query for query, _ in cursor.statements)
    image_lineage_params = [
        params for query, params in cursor.statements
        if "lineage_role)" in query and "'image'" in query
    ]
    assert {params[2] for params in image_lineage_params} == {
        "derived/diagram.svg",
        "source/diagram.png",
    }


def test_procedure_unreviewed_state_downgrades_persistence_even_without_boolean_flag():
    from autodata_ingestion.derived_article_persistence import _persistence_status

    assert _persistence_status(
        {"status": "ready"},
        {"review_state": "UNREVIEWED", "requires_review": False},
        [],
    ) == "needs_review"


def test_replaying_non_current_revision_does_not_publish_parent_state():
    class ReplayCursor(_RecordingCursor):
        def execute(self, query, params=()):
            self.statements.append((query, params))
            if "SELECT vehicle_id::text FROM vehicles" in query:
                self._next_row = ("00000000-0000-0000-0000-000000000001",)
            elif "FROM derived_articles" in query and "SELECT" in query:
                self._next_row = (
                    "00000000-0000-0000-0000-000000000002",
                    4,
                    "source-current",
                )
            elif "SELECT derived_article_revision_id::text" in query:
                self._next_row = ("00000000-0000-0000-0000-000000000003", 3)
            else:
                self._next_row = None

    cursor = ReplayCursor()
    connection = _RecordingConnection(cursor)
    fake_psycopg = types.ModuleType("psycopg")
    fake_psycopg.connect = lambda **_kwargs: connection
    fake_json = types.ModuleType("psycopg.types.json")
    fake_json.Jsonb = lambda value: value
    fake_types = types.ModuleType("psycopg.types")
    fake_types.json = fake_json
    result = {
        "status": "ready",
        "canonical_vehicle": {"vehicle_id": "00000000-0000-0000-0000-000000000001", "make": "Toyota", "model": "RAV4"},
        "derived_article": {"article_id": "combined:replay"},
        "selected_articles": ["source-1"],
        "source_watermarks": ["source-current"],
        "procedure": {"title": "Replay", "steps": [], "warnings": []},
        "labor": {"operations": []},
    }
    with patch.dict(sys.modules, {"psycopg": fake_psycopg, "psycopg.types": fake_types, "psycopg.types.json": fake_json}), patch.dict(os.environ, {"AUTODATA_POSTGRES_PASSWORD": "test-password"}, clear=False):
        persisted = persist_derived_article(result, vehicle=result["canonical_vehicle"])

    assert persisted["status"] == "replayed"
    assert not any("INSERT INTO derived_articles" in query for query, _ in cursor.statements)
    assert not any("UPDATE derived_articles SET current_revision_number" in query for query, _ in cursor.statements)
