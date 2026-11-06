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


@pytest.mark.parametrize("base_region", ["US", "CA"])
def test_configuration_resolution_sends_human_selector_in_exact_scope(
    fresh_database, capture_fixture, base_region
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
            "UPDATE vehicle_identity_bases SET drivetrain='AWD',region=%s WHERE vehicle_id=%s",
            (base_region, vehicle),
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
        "region": base_region,
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


@pytest.mark.parametrize('state,eligible', [
    ('pending', True), ('failed_due', True), ('failed_future', False),
    ('pending_exhausted', False), ('processing_expired', True),
    ('processing_exhausted', True), ('processing_live', False),
    ('completed', False), ('dead_letter', False), ('needs_review', False),
    ('stale_generation', False), ('no_current_job', False),
])
def test_catalog_consumer_real_eligibility(fresh_database, state, eligible):
    from autodata_ingestion.catalog_coverage import ensure_article_catalog_jobs
    from autodata_ingestion.catalog_index_worker import select_next_catalog_job

    repo = fresh_database()
    ensure_article_catalog_jobs(repo, vehicle_id=seed_vehicle(repo), vehicle_configuration_id=None)
    with repo.connect() as conn:
        jobs = conn.execute('SELECT * FROM source_fetch_jobs ORDER BY created_at,source_fetch_job_id').fetchall()
        first, other = jobs
        conn.execute("UPDATE source_fetch_jobs SET status='completed' WHERE source_fetch_job_id=%s", (other['source_fetch_job_id'],))
        job_id = first['source_fetch_job_id']
        if state.startswith('processing'):
            expiry = "interval '1 hour'" if state == 'processing_live' else "interval '-1 hour'"
            conn.execute("""UPDATE source_fetch_jobs SET status='processing',lease_owner=%s,
                lease_token=1,heartbeat_at=clock_timestamp(),lease_expires_at=clock_timestamp()+""" + expiry + """,
                retry_count=%s WHERE source_fetch_job_id=%s""",
                (uuid.uuid4(), 3 if state == 'processing_exhausted' else 1, job_id))
        elif state.startswith('failed'):
            delay = 3600 if state == 'failed_future' else -3600
            conn.execute("UPDATE source_fetch_jobs SET status='failed',next_attempt_at=clock_timestamp()+make_interval(secs=>%s) WHERE source_fetch_job_id=%s", (delay, job_id))
        elif state == 'pending_exhausted':
            conn.execute('UPDATE source_fetch_jobs SET retry_count=max_attempts WHERE source_fetch_job_id=%s', (job_id,))
        elif state == 'stale_generation':
            conn.execute('UPDATE catalog_article_provider_scopes SET generation=generation+1 WHERE current_job_id=%s', (job_id,))
        elif state == 'no_current_job':
            conn.execute('UPDATE catalog_article_provider_scopes SET current_job_id=NULL WHERE current_job_id=%s', (job_id,))
        else:
            conn.execute('UPDATE source_fetch_jobs SET status=%s WHERE source_fetch_job_id=%s', (state, job_id))
    assert select_next_catalog_job(repo) == (job_id if eligible else None)


def test_catalog_consumer_preserves_earlier_article_jobs_and_attempts(fresh_database, capture_fixture):
    from autodata_ingestion.article_lifecycle_types import ArticleKey
    from autodata_ingestion.catalog_coverage import ensure_article_catalog_jobs, read_catalog_coverage
    from autodata_ingestion.catalog_index_worker import dispatch_next
    from lifecycle_support import insert_descriptor
    from autodata_ingestion.source_job_persistence import ensure_article_job

    repo = fresh_database()
    vehicle = seed_vehicle(repo)
    # A generic claim would choose pending article work or sweep exhausted articles.
    for index, status in enumerate(('pending', 'processing', 'processing')):
        article = insert_descriptor(repo, ArticleKey('bankone', vehicle, None, 'fixture-car', f'article-{index}'))
        result = ensure_article_job(repo, article, normalization_version='ordered-article-v1', rewrite_profile_version='technical-prose-v1')
        with repo.connect() as conn:
            conn.execute("UPDATE source_fetch_jobs SET created_at=clock_timestamp()-interval '2 days',checkpoint='{}' WHERE source_fetch_job_id=%s", (result.job_id,))
            if status == 'processing':
                conn.execute("""UPDATE source_fetch_jobs SET status='processing',retry_count=%s,
                    lease_owner=%s,lease_token=1,heartbeat_at=clock_timestamp()-interval '1 hour',
                    lease_expires_at=clock_timestamp()-interval '1 hour' WHERE source_fetch_job_id=%s""",
                    (1 if index == 1 else 3, uuid.uuid4(), result.job_id))
    ensure_article_catalog_jobs(repo, vehicle_id=vehicle, vehicle_configuration_id=None)
    with repo.connect() as conn:
        before = conn.execute("SELECT * FROM source_fetch_jobs WHERE job_kind='article' ORDER BY source_fetch_job_id").fetchall()
        attempts_before = conn.execute('SELECT * FROM canonical_article_rewrite_attempts').fetchall()
    for provider in ('bankone', 'banktwo'):
        capture_fixture.servers[provider].pages = [page(provider)]
    for _ in range(2):
        assert dispatch_next(repo, worker_id=uuid.uuid4(), registry=capture_fixture.registry, object_store=capture_fixture.objects)
    assert not dispatch_next(repo, worker_id=uuid.uuid4(), registry=capture_fixture.registry, object_store=capture_fixture.objects)
    coverage = read_catalog_coverage(repo, vehicle_id=vehicle, vehicle_configuration_id=None)
    assert coverage['complete']
    assert {'bankone', 'banktwo'} <= {row['source_article_ref'] for row in coverage['items']}
    with repo.connect() as conn:
        assert conn.execute("SELECT * FROM source_fetch_jobs WHERE job_kind='article' ORDER BY source_fetch_job_id").fetchall() == before
        assert conn.execute('SELECT * FROM canonical_article_rewrite_attempts').fetchall() == attempts_before
        assert conn.execute('SELECT count(*) AS n FROM catalog_article_index_pages').fetchone()['n'] == 2
        catalog = conn.execute("SELECT * FROM source_fetch_jobs WHERE job_kind='catalog_index'").fetchall()
        assert all(row['status'] == 'completed' and row['checkpoint'] and row['lease_owner'] is None for row in catalog)
    assert capture_fixture.objects.data
    assert all('/resources/' not in call for provider in ('bankone', 'banktwo') for call in capture_fixture.calls(provider))


def test_catalog_consumer_competing_claim_and_exhaustion_are_exact(fresh_database, monkeypatch):
    from autodata_ingestion.catalog_coverage import ensure_article_catalog_jobs
    from autodata_ingestion import catalog_index_worker as consumer
    repo = fresh_database()
    ensure_article_catalog_jobs(repo, vehicle_id=seed_vehicle(repo), vehicle_configuration_id=None)
    selected = consumer.select_next_catalog_job(repo)
    lease = claim_source_job(repo, worker_id=uuid.uuid4(), job_id=selected)
    assert lease.job_id == selected
    # A consumer which already selected the same UUID loses claim without a fallback.
    monkeypatch.setattr(consumer, 'select_next_catalog_job', lambda _: selected)
    assert not consumer.dispatch_next(repo, worker_id=uuid.uuid4(), registry={}, object_store=None)
    with repo.connect() as conn:
        conn.execute("UPDATE source_fetch_jobs SET retry_count=max_attempts,lease_expires_at=clock_timestamp()-interval '1 second' WHERE source_fetch_job_id=%s", (selected,))
        other_before = conn.execute('SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id<>%s', (selected,)).fetchall()
    assert not consumer.dispatch_next(repo, worker_id=uuid.uuid4(), registry={}, object_store=None)
    with repo.connect() as conn:
        row = conn.execute('SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s', (selected,)).fetchone()
        assert row['status'] == 'dead_letter' and row['error_code'] == 'LEASE_ATTEMPTS_EXHAUSTED'
        assert conn.execute('SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id<>%s', (selected,)).fetchall() == other_before
