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


def test_configuration_resolution_sends_human_selector_in_exact_scope(
    fresh_database, capture_fixture
):
    from lifecycle_support import seed_configuration
    from autodata_ingestion.catalog_coverage import (
        ensure_article_catalog_jobs,
        run_catalog_index_job,
        read_catalog_coverage,
    )

    repo = fresh_database()
    vehicle = seed_vehicle(repo)
    configuration = seed_configuration(repo, vehicle)
    with repo.connect() as conn:
        conn.execute(
            "UPDATE vehicle_configurations SET trim='Touring',engine_displacement_l=2.0 WHERE vehicle_configuration_id=%s",
            (configuration,),
        )
        conn.execute(
            "UPDATE vehicle_identity_bases SET drivetrain='AWD' WHERE vehicle_id=%s",
            (vehicle,),
        )
    ensure_article_catalog_jobs(
        repo, vehicle_id=vehicle, vehicle_configuration_id=configuration
    )
    for _ in range(2):
        run_catalog_index_job(
            repo,
            claim_source_job(repo, worker_id=uuid.uuid4()),
            registry=capture_fixture.registry,
            object_store=capture_fixture.objects,
        )
    expected = {
        "year": 2024,
        "make": "Example",
        "model": "Car",
        "region": "US",
        "configuration": "Touring 2.0L AWD",
    }
    for provider in ("bankone", "banktwo"):
        assert capture_fixture.servers[provider].resolution_requests == [expected]
    state = read_catalog_coverage(
        repo, vehicle_id=vehicle, vehicle_configuration_id=configuration
    )
    assert state["complete"] is True
    assert all(
        scope["vehicle_configuration_id"] == configuration
        for scope in state["coverage"].values()
    )


@pytest.mark.parametrize("verified_mapping", [False, True])
def test_configuration_without_selector_is_never_widened(
    fresh_database, capture_fixture, verified_mapping
):
    from lifecycle_support import seed_configuration
    from autodata_ingestion.catalog_coverage import (
        ensure_article_catalog_jobs,
        run_catalog_index_job,
        read_catalog_coverage,
    )

    repo = fresh_database()
    vehicle = seed_vehicle(repo)
    configuration = seed_configuration(repo, vehicle)
    if verified_mapping:
        with repo.connect() as conn:
            for provider in ("bankone", "banktwo"):
                conn.execute(
                    """INSERT INTO vehicle_provider_mappings(mapping_key,vehicle_id,vehicle_configuration_id,provider,entity_type,provider_id,source_snapshot_id,extraction_evidence_id,source_locator,evidence_locator,evidence_confidence,mapping_status)
                    SELECT %s,vehicle_id,vehicle_configuration_id,%s,'car','vehicle:fixture',source_snapshot_id,extraction_evidence_id,'fixture','fixture',1,'verified'
                    FROM vehicle_configurations WHERE vehicle_configuration_id=%s""",
                    (uuid.uuid4().hex, provider, configuration),
                )
    ensure_article_catalog_jobs(
        repo, vehicle_id=vehicle, vehicle_configuration_id=configuration
    )
    for _ in range(2):
        run_catalog_index_job(
            repo,
            claim_source_job(repo, worker_id=uuid.uuid4()),
            registry=capture_fixture.registry,
            object_store=capture_fixture.objects,
        )
    state = read_catalog_coverage(
        repo, vehicle_id=vehicle, vehicle_configuration_id=configuration
    )
    for provider in ("bankone", "banktwo"):
        assert capture_fixture.servers[provider].resolution_requests == []
        assert state["coverage"][provider]["status"] == (
            "complete" if verified_mapping else "needs_review"
        )
        if not verified_mapping:
            assert capture_fixture.calls(provider) == []
            assert (
                state["coverage"][provider]["error_code"] == "UNRESOLVED_CONFIGURATION"
            )
