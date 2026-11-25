"""Bounded operator selection and real isolated refresh transaction regressions."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
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


def test_source_bound_cli_passes_the_exact_job_and_source(tmp_path, monkeypatch, capsys):
    article, source, prior_job, new_job = (uuid4() for _ in range(4))
    path = tmp_path / "selection.json"
    path.write_text(json.dumps([{"canonical_article_id": str(article), "expected_source_revision_id": str(source)}]))
    refresh = module()
    expected_repo = object()
    calls = []

    def schedule(repo, article_id, **kwargs):
        calls.append((repo, article_id, kwargs))
        return SimpleNamespace(job_id=new_job, created=True)

    monkeypatch.setattr(refresh, "schedule_source_bound_rewrite", schedule)
    args = ["--selection", str(path), "--actor", "operator", "--reason", "Regenerate draft",
            "--source-bound-from", str(prior_job)]
    with pytest.raises(SystemExit):
        refresh.main(args, repo=expected_repo)
    assert not calls
    assert refresh.main([*args, "--apply"], repo=expected_repo) == 0
    assert calls == [(expected_repo, article, {"expected_job_id": prior_job,
                      "expected_source_revision_id": source, "actor": "operator", "reason": "Regenerate draft"})]
    assert json.loads(capsys.readouterr().out)["items"][0]["job_id"] == str(new_job)


@pytest.mark.parametrize(("by_sentence", "first_draft", "budget"), [(False, False, 8), (True, False, 2), (True, True, 1)])
def test_correction_cli_requires_explicit_budget_and_exact_job(
    tmp_path, monkeypatch, capsys, by_sentence, first_draft, budget,
):
    article, source, prior, current = (uuid4() for _ in range(4))
    path = tmp_path / "selection.json"
    path.write_text(json.dumps([{"canonical_article_id": str(article), "expected_source_revision_id": str(source)}]))
    refresh = module()
    repo = object()
    calls = []

    def schedule(repository, article_id, **kwargs):
        calls.append((repository, article_id, kwargs))
        return SimpleNamespace(job_id=current, created=True)

    monkeypatch.setattr(refresh, "schedule_source_bound_correction", schedule)
    flag = "--correct-first-draft-from" if first_draft else "--correct-from"
    args = ["--selection", str(path), "--actor", "operator", "--reason", "Correct the draft", flag, str(prior), "--apply"]
    if by_sentence:
        bare = args[:6]
        with pytest.raises(SystemExit):
            refresh.main([*bare, "--by-sentence"], repo=repo)
        if not first_draft:
            args.append("--by-sentence")
        with pytest.raises(SystemExit):
            refresh.main([*args, "--model-call-budget", "3"], repo=repo)
    with pytest.raises(SystemExit):
        refresh.main(args, repo=repo)
    with pytest.raises(SystemExit):
        refresh.main([*args, "--model-call-budget", "13"], repo=repo)
    assert not calls
    assert refresh.main([*args, "--model-call-budget", str(budget)], repo=repo) == 0
    expected = {"expected_job_id": prior, "expected_source_revision_id": source, "actor": "operator",
                "reason": "Correct the draft", "model_call_budget": budget, "by_sentence": by_sentence}
    if first_draft:
        expected["first_draft"] = True
    assert calls == [(repo, article, expected)]
    assert json.loads(capsys.readouterr().out)["items"][0]["job_id"] == str(current)


def test_publish_first_draft_cli_requires_a_method_and_recovered_document_hash(tmp_path, monkeypatch, capsys):
    article, source, prior, current, revision = (uuid4() for _ in range(5))
    path = tmp_path / "selection.json"
    target = {"canonical_article_id": str(article), "expected_source_revision_id": str(source)}
    path.write_text(json.dumps([target]))
    refresh = module()
    repo = object()
    calls = []

    def publish(repository, article_id, **kwargs):
        calls.append((repository, article_id, kwargs))
        return SimpleNamespace(job_id=current, published_revision_id=revision, created=len(calls) == 1)

    monkeypatch.setattr(refresh, "publish_source_bound_first_draft", publish)
    base = ["--selection", str(path), "--actor", "operator", "--reason", "Publish the saved draft"]
    apply_args = ["--recover-first-draft-from", str(prior), "--apply"]
    method = refresh.FIRST_DRAFT_RECOVERY_METHODS[0]
    method_args = ["--first-draft-recovery-method", method]
    output_hash = "1" * 64
    hash_args = ["--expected-first-draft-recovery-hash", output_hash]
    for incomplete in (apply_args + method_args, apply_args + hash_args, method_args + hash_args,
                       apply_args[:-1] + method_args + hash_args):
        with pytest.raises(SystemExit):
            refresh.main([*base, *incomplete], repo=repo)
    assert calls == []

    args = [*base, *apply_args, *method_args, *hash_args]
    for action in ("published", "joined_existing"):
        assert refresh.main(args, repo=repo) == 0
        assert json.loads(capsys.readouterr().out)["items"] == [{
            **target, "prior_job_id": str(prior), "job_id": str(current), "revision_id": str(revision), "action": action,
        }]
    assert calls == [(repo, article, {
        "expected_job_id": prior, "expected_source_revision_id": source,
        "recovery_method": method, "expected_recovery_hash": output_hash,
        "actor": "operator", "reason": "Publish the saved draft",
    })] * 2


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
