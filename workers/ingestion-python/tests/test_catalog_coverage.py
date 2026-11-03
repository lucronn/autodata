from pathlib import Path
import sys
import uuid
import pytest
from lifecycle_support import fresh_database, seed_vehicle
from test_source_article_capture import capture_fixture
from autodata_ingestion.source_job_persistence import claim_source_job


def run_catalog(repo, fixture):
    from autodata_ingestion.catalog_coverage import (
        ensure_article_catalog_jobs,
        run_catalog_index_job,
    )

    vehicle = seed_vehicle(repo)
    ensure_article_catalog_jobs(repo, vehicle_id=vehicle, vehicle_configuration_id=None)
    for i in range(2):
        lease = claim_source_job(repo, worker_id=uuid.uuid4())
        run_catalog_index_job(
            repo, lease, registry=fixture.registry, object_store=fixture.objects
        )
    return vehicle


def page(ref, complete=True, cursor=None, title="Pump"):
    return {
        "complete": complete,
        "next_cursor": cursor,
        "articles": [{"opaque_ref": ref, "title": title, "resource_ref": "body"}],
    }


def test_bankone_success_cannot_hide_banktwo_failure(fresh_database, capture_fixture):
    from autodata_ingestion.catalog_coverage import read_catalog_coverage

    repo = fresh_database()
    capture_fixture.servers["bankone"].pages = [page("one")]
    capture_fixture.servers["banktwo"].error = 503
    vehicle = run_catalog(repo, capture_fixture)
    state = read_catalog_coverage(
        repo, vehicle_id=vehicle, vehicle_configuration_id=None
    )
    assert [r["source_article_ref"] for r in state["items"]] == ["one"]
    assert state["coverage"]["bankone"]["status"] == "complete"
    assert state["coverage"]["banktwo"]["status"] == "failed"
    assert state["complete"] is False
    assert not any(
        "/resources/" in call
        for p in ("bankone", "banktwo")
        for call in capture_fixture.calls(p)
    )


@pytest.mark.parametrize("banktwo_empty", [False, True])
def test_both_banks_are_required_for_complete_union(
    fresh_database, capture_fixture, banktwo_empty
):
    from autodata_ingestion.catalog_coverage import read_catalog_coverage

    repo = fresh_database()
    capture_fixture.servers["bankone"].pages = [page("same")]
    capture_fixture.servers["banktwo"].pages = (
        [{"complete": True, "articles": []}] if banktwo_empty else [page("same")]
    )
    vehicle = run_catalog(repo, capture_fixture)
    state = read_catalog_coverage(
        repo, vehicle_id=vehicle, vehicle_configuration_id=None
    )
    assert state["complete"] is True
    assert len(state["items"]) == (1 if banktwo_empty else 2)
    with repo.connect() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM catalog_article_index_pages"
            ).fetchone()["n"]
            == 2
        )


def test_partial_scan_cannot_retire_previous_rows(fresh_database, capture_fixture):
    from autodata_ingestion.catalog_coverage import (
        run_catalog_index_job,
        read_catalog_coverage,
        refresh_catalog_jobs,
    )

    repo = fresh_database()
    capture_fixture.servers["bankone"].pages = [page("old")]
    vehicle = run_catalog(repo, capture_fixture)
    refresh_catalog_jobs(
        repo,
        vehicle_id=vehicle,
        vehicle_configuration_id=None,
        actor="fixture",
        reason="rescan",
    )
    capture_fixture.servers["bankone"].pages = [page("new", False, "0")]
    for i in range(2):
        lease = claim_source_job(repo, worker_id=uuid.uuid4())
        if lease:
            run_catalog_index_job(
                repo,
                lease,
                registry=capture_fixture.registry,
                object_store=capture_fixture.objects,
            )
    state = read_catalog_coverage(
        repo, vehicle_id=vehicle, vehicle_configuration_id=None
    )
    assert {"old", "new"} <= {r["source_article_ref"] for r in state["items"]}
    assert state["coverage"]["bankone"]["status"] == "partial"


@pytest.mark.parametrize(
    "candidates,status",
    [
        ([], "complete"),
        (
            [
                {"opaque_ref": "v1", "label": "One", "confidence": 1},
                {"opaque_ref": "v2", "label": "Two", "confidence": 1},
            ],
            "needs_review",
        ),
    ],
)
def test_resolution_empty_and_ambiguity_are_distinct(
    fresh_database, capture_fixture, candidates, status
):
    from autodata_ingestion.catalog_coverage import read_catalog_coverage

    repo = fresh_database()
    capture_fixture.servers["banktwo"].candidates = candidates
    vehicle = run_catalog(repo, capture_fixture)
    state = read_catalog_coverage(
        repo, vehicle_id=vehicle, vehicle_configuration_id=None
    )
    assert state["coverage"]["banktwo"]["status"] == status
    assert not any("/articles" in call for call in capture_fixture.calls("banktwo"))


def test_unconfigured_bank_is_not_empty_success(fresh_database, capture_fixture):
    from autodata_ingestion.catalog_coverage import (
        ensure_article_catalog_jobs,
        run_catalog_index_job,
        read_catalog_coverage,
    )

    repo = fresh_database()
    vehicle = seed_vehicle(repo)
    ensure_article_catalog_jobs(repo, vehicle_id=vehicle, vehicle_configuration_id=None)
    for i in range(2):
        run_catalog_index_job(
            repo,
            claim_source_job(repo, worker_id=uuid.uuid4()),
            registry={"bankone": capture_fixture.registry["bankone"]},
            object_store=capture_fixture.objects,
        )
    state = read_catalog_coverage(
        repo, vehicle_id=vehicle, vehicle_configuration_id=None
    )
    assert state["coverage"]["banktwo"]["status"] == "not_configured"
    assert state["complete"] is False


def test_conflicting_descriptor_requires_review_and_preserves_rows(
    fresh_database, capture_fixture
):
    from autodata_ingestion.catalog_coverage import read_catalog_coverage

    repo = fresh_database()
    capture_fixture.servers["bankone"].pages = [
        page("same", False, "1", "First"),
        page("same", True, None, "Second"),
    ]
    vehicle = run_catalog(repo, capture_fixture)
    state = read_catalog_coverage(
        repo, vehicle_id=vehicle, vehicle_configuration_id=None
    )
    assert state["coverage"]["bankone"]["status"] == "needs_review"
    assert state["coverage"]["bankone"]["error_code"] == "CONFLICTING_DESCRIPTOR"
    assert [r["title"] for r in state["items"]] == ["First"]


def test_ambiguous_resolution_retains_exact_evidence(fresh_database, capture_fixture):
    from autodata_ingestion.catalog_coverage import read_catalog_coverage

    repo = fresh_database()
    capture_fixture.servers["banktwo"].candidates = [
        {"opaque_ref": "one", "label": "One", "confidence": 1},
        {"opaque_ref": "two", "label": "Two", "confidence": 1},
    ]
    vehicle = run_catalog(repo, capture_fixture)
    state = read_catalog_coverage(
        repo, vehicle_id=vehicle, vehicle_configuration_id=None
    )
    assert state["coverage"]["banktwo"]["resolution_source_snapshot_id"] is not None
