"""Bounded operator selection and real isolated refresh transaction regressions."""
import importlib.util
import json
from pathlib import Path
import sys
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workers/ingestion-python/src"))
sys.path.insert(0, str(ROOT / "workers/ingestion-python/tests"))
from lifecycle_support import fresh_database
from test_source_article_capture import capture_fixture


def module():
    path = ROOT / "scripts/dev/automatic_article_refresh.py"
    spec = importlib.util.spec_from_file_location("automatic_article_refresh", path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


@pytest.mark.parametrize("value", [[], [{}], [{"canonical_article_id":"invalid","expected_source_revision_id":"invalid"}],
    [{"canonical_article_id":str(uuid4()),"expected_source_revision_id":str(uuid4()),"extra":True}]])
def test_invalid_selection_never_reaches_repository(value):
    with pytest.raises(ValueError): module().selection(value)


def test_duplicate_or_unbounded_selection_rejected():
    row = {"canonical_article_id":str(uuid4()), "expected_source_revision_id":str(uuid4())}
    with pytest.raises(ValueError): module().selection([row, row])
    with pytest.raises(ValueError): module().selection([row] * 101)


def historical_source(repo, fixture):
    from test_article_transform import prepare_transform
    lease, source = prepare_transform(repo, fixture)
    with repo.connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET status='needs_review',lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL WHERE source_fetch_job_id=%s", (lease.job_id,))
    return lease


def test_preview_is_read_only_then_apply_schedules_once(fresh_database, capture_fixture):
    repo = fresh_database(); lease = historical_source(repo, capture_fixture)
    target = [{"canonical_article_id":str(lease.canonical_article_id), "expected_source_revision_id":str(lease.source_revision_id)}]
    refresh = module()
    before = refresh.refresh_selected(repo, target, actor="fixture-operator", reason="Automatic rewrite", apply=False)
    assert before[0]["action"] == "would_refresh"
    with repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM source_fetch_jobs").fetchone()["n"] == 1
    result = refresh.refresh_selected(repo, target, actor="fixture-operator", reason="Automatic rewrite", apply=True)
    assert result[0]["action"] == "scheduled"
    assert refresh.refresh_selected(repo, target, actor="fixture-operator", reason="Automatic rewrite", apply=True)[0]["action"] == "already_automatic"
    with repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM source_fetch_jobs").fetchone()["n"] == 2
        assert conn.execute("SELECT count(*) AS n FROM canonical_article_source_revisions").fetchone()["n"] == 1


def test_changed_expected_source_refuses_mutation(fresh_database, capture_fixture):
    repo = fresh_database(); lease = historical_source(repo, capture_fixture)
    target = [{"canonical_article_id":str(lease.canonical_article_id), "expected_source_revision_id":str(uuid4())}]
    with pytest.raises(ValueError, match="SOURCE_CHANGED"):
        module().refresh_selected(repo, target, actor="fixture-operator", reason="Automatic rewrite", apply=True)
    with repo.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM source_fetch_jobs").fetchone()["n"] == 1
