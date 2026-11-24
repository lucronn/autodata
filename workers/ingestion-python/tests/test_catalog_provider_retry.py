"""A paid configuration can recover one failed provider through the catalog worker."""

from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier
from uuid import uuid4

import pytest

from autodata_ingestion import catalog_coverage as catalog
from autodata_ingestion import commerce_service as commerce
from autodata_ingestion.article_lifecycle import run_article_worker_once
from autodata_ingestion.article_lifecycle_store import load_article_state
from autodata_ingestion.article_lifecycle_types import AUTOMATIC_REWRITE_PROFILE, NORMALIZATION_VERSION
from autodata_ingestion.catalog_index_worker import dispatch_next, select_next_catalog_job
from autodata_ingestion.catalog_service import _ensure_lifecycle_catalog
from autodata_ingestion.source_job_persistence import claim_source_job, ensure_article_job
from lifecycle_support import fresh_database, seed_configuration, seed_vehicle
from test_catalog_coverage import page
from test_commerce_simulation import ORIGIN, account, call
from test_source_article_capture import capture_fixture


def _catalog_jobs(repo):
    with repo.connect() as conn:
        return {row["provider_slug"]: row for row in conn.execute(
            """SELECT j.* FROM catalog_article_provider_scopes s
            JOIN source_fetch_jobs j ON j.source_fetch_job_id=s.current_job_id"""
        ).fetchall()}


def _banktwo_publication(repo, article_id):
    with repo.connect() as conn:
        rows = {
            "scope": conn.execute(
                "SELECT * FROM catalog_article_provider_scopes WHERE provider_slug='banktwo'"
            ).fetchone(),
            "jobs": conn.execute(
                "SELECT * FROM source_fetch_jobs WHERE provider_slug='banktwo' ORDER BY source_fetch_job_id"
            ).fetchall(),
            "pages": conn.execute(
                """SELECT p.* FROM catalog_article_index_pages p
                JOIN catalog_article_provider_scopes s USING(catalog_provider_scope_id)
                WHERE s.provider_slug='banktwo' ORDER BY p.generation,p.page_number"""
            ).fetchall(),
            "descriptor": conn.execute(
                "SELECT * FROM canonical_articles WHERE canonical_article_id=%s", (article_id,),
            ).fetchone(),
            "revision": conn.execute(
                """SELECT r.* FROM canonical_articles a JOIN canonical_article_revisions r
                ON r.canonical_article_revision_id=a.current_canonical_revision_id WHERE a.canonical_article_id=%s""",
                (article_id,),
            ).fetchone(),
        }
    return rows, load_article_state(repo, article_id)


@pytest.fixture
def blocked_paid_catalog(fresh_database, capture_fixture):
    repo = fresh_database()
    vehicle_id = seed_vehicle(repo)
    configuration = seed_configuration(repo, vehicle_id)
    with repo.connect() as conn:
        conn.execute(
            """UPDATE vehicle_configurations SET trim='Touring',engine_displacement_l=2.0
            WHERE vehicle_configuration_id=%s""",
            (configuration,),
        )
        conn.execute("UPDATE vehicle_identity_bases SET drivetrain='AWD' WHERE vehicle_id=%s", (vehicle_id,))

    service = commerce.SimulationCommerceService(
        repo.connect, commerce.CommerceConfig("stripe_test", "acct_fixture", "price_fixture"),
        commerce._simulation_configuration(ORIGIN),
    )
    owner = account(repo)
    order = call(service, "checkouts", dict(
        owner, configuration_id=str(configuration), region="US", expected_mode="simulation",
        terms_version=commerce.TERMS, idempotency_key=str(uuid4()),
    ))
    assert order["state"] == "owned"

    def schedule(raw):
        return _ensure_lifecycle_catalog(json.loads(raw), repo=repo)

    with repo.connect() as conn:
        scheduled = commerce.reconcile_workshop_preparation(conn, scheduler=schedule)
    assert scheduled == [{"order_id": order["order_id"], "preparation_state": "index_queued"}]
    jobs = _catalog_jobs(repo)
    old_job = jobs["bankone"]["source_fetch_job_id"]
    banktwo = capture_fixture.servers["banktwo"]
    banktwo.pages = [page("retained", title="Cover references")]
    lease = claim_source_job(repo, worker_id=uuid4(), job_id=jobs["banktwo"]["source_fetch_job_id"])
    catalog.run_catalog_index_job(repo, lease, registry=capture_fixture.registry, object_store=capture_fixture.objects)

    bankone = capture_fixture.servers["bankone"]
    bankone.error = 503
    for attempt in range(1, jobs["bankone"]["max_attempts"] + 1):
        if attempt > 1:
            # Move the fixture clock's due time while using the normal claim and failure paths.
            with repo.connect() as conn:
                conn.execute(
                    """UPDATE source_fetch_jobs SET next_attempt_at=clock_timestamp()-interval '1 second'
                    WHERE source_fetch_job_id=%s""",
                    (old_job,),
                )
        lease = claim_source_job(repo, worker_id=uuid4(), job_id=old_job)
        assert lease.token == attempt
        catalog.run_catalog_index_job(repo, lease, registry=capture_fixture.registry, object_store=capture_fixture.objects)
    failed = _catalog_jobs(repo)["bankone"]
    assert failed["status"] == "dead_letter" and failed["error_code"] == "UPSTREAM_UNAVAILABLE"
    assert failed["retry_count"] == failed["max_attempts"] and failed["retryable"] is False
    with repo.connect() as conn:
        conn.execute("UPDATE workshop_orders SET preparation_next_attempt_at=clock_timestamp() WHERE order_id=%s",
                     (order["order_id"],))
    with repo.connect() as conn:
        scheduled = commerce.reconcile_workshop_preparation(conn, scheduler=schedule)
    assert scheduled == [{"order_id": order["order_id"], "preparation_state": "blocked"}]
    return repo, dict(
        vehicle_id=vehicle_id, vehicle_configuration_id=configuration, provider="bankone",
        expected_job_id=old_job, actor="fixture-operator", reason="Recover the expired provider resolution.",
    ), failed


def test_provider_retry_restores_only_the_failed_side_of_a_paid_index(blocked_paid_catalog, capture_fixture):
    repo, args, failed = blocked_paid_catalog
    scope = {key: args[key] for key in ("vehicle_id", "vehicle_configuration_id")}
    before = catalog.read_catalog_coverage(repo, **scope)
    assert not before["complete"]
    assert [row["source_article_ref"] for row in before["items"]] == ["retained"]
    article_id = before["items"][0]["canonical_article_id"]
    capture_fixture.servers["banktwo"].body(
        b'<maintenance_schedule title="Cover references"><operation id="OP-1" name="Inspection">'
        b'<component id="CP-1" name="Cover"><notes>Source inspection reference.</notes></component>'
        b'</operation></maintenance_schedule>',
        media_type="application/xml",
    )
    article_job = ensure_article_job(
        repo, article_id, normalization_version=NORMALIZATION_VERSION,
        rewrite_profile_version=AUTOMATIC_REWRITE_PROFILE,
    )
    assert run_article_worker_once(
        repo, worker_id=uuid4(), registry=capture_fixture.registry, object_store=capture_fixture.objects,
        model_client=None, job_id=article_job.job_id,
    )
    preserved = _banktwo_publication(repo, article_id)
    assert preserved[0]["revision"] is not None and preserved[1]["content_origin"] == "canonical"
    call_counts = {provider: tuple(capture_fixture.calls(provider)) for provider in catalog.PROVIDERS}
    assert select_next_catalog_job(repo) is None

    barrier = Barrier(2, timeout=5)

    def retry():
        barrier.wait()
        return catalog.retry_failed_catalog_provider(repo, **args)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(retry), pool.submit(retry)]
        results = [future.result(timeout=10) for future in futures]
    first, replay = sorted(results, key=lambda item: not item.created)
    assert first.created and not replay.created and first.job_id == replay.job_id != failed["source_fetch_job_id"]
    assert call_counts == {provider: tuple(capture_fixture.calls(provider)) for provider in catalog.PROVIDERS}
    assert select_next_catalog_job(repo) == first.job_id
    pending = catalog.read_catalog_coverage(repo, **scope)
    assert pending["coverage"]["bankone"]["generation"] == failed["request_generation"] + 1
    assert not pending["complete"] and [row["source_article_ref"] for row in pending["items"]] == ["retained"]
    assert _banktwo_publication(repo, article_id) == preserved

    bankone = capture_fixture.servers["bankone"]
    bankone.error = None
    bankone.pages = [page("recovered", title="Recovered procedure")]
    assert dispatch_next(repo, worker_id=uuid4(), registry=capture_fixture.registry, object_store=capture_fixture.objects)
    after = catalog.read_catalog_coverage(repo, **scope)
    assert after["complete"] and {row["source_article_ref"] for row in after["items"]} == {"retained", "recovered"}
    assert bankone.resolution_requests[-1] == {
        "year": 2024, "make": "Example", "model": "Car", "region": "US", "configuration": "Touring 2.0L AWD",
    }
    assert tuple(capture_fixture.calls("banktwo")) == call_counts["banktwo"]
    assert all("/resources/" not in path for path in capture_fixture.calls("bankone"))
    assert _banktwo_publication(repo, article_id) == preserved
    completed_replay = catalog.retry_failed_catalog_provider(repo, **args)
    assert not completed_replay.created and completed_replay.job_id == first.job_id
    assert completed_replay.state == "completed"
    assert select_next_catalog_job(repo) is None
    with repo.connect() as conn:
        assert conn.execute(
            "SELECT * FROM source_fetch_jobs WHERE source_fetch_job_id=%s", (failed["source_fetch_job_id"],),
        ).fetchone() == failed
        assert conn.execute(
            "SELECT count(*) AS n FROM source_fetch_jobs WHERE job_kind='catalog_index' AND provider_slug='bankone'"
        ).fetchone()["n"] == 2


def test_provider_retry_rejects_wrong_generation_and_lost_grant(blocked_paid_catalog, capture_fixture):
    from autodata_ingestion.payment_reconciliation import revoke_entitlement

    repo, args, failed = blocked_paid_catalog
    calls = tuple(capture_fixture.calls("bankone"))
    before = _catalog_jobs(repo)
    for invalid in (
        dict(args, expected_job_id=uuid4()),
        dict(args, provider="banktwo", expected_job_id=before["banktwo"]["source_fetch_job_id"]),
    ):
        with pytest.raises(ValueError):
            catalog.retry_failed_catalog_provider(repo, **invalid)
    with repo.connect() as conn:
        owned = conn.execute("SELECT entitlement_id FROM workshop_orders WHERE status='paid'").fetchone()
        revoke_entitlement(conn, owned["entitlement_id"], "fixture scope no longer owned")
    with pytest.raises(ValueError):
        catalog.retry_failed_catalog_provider(repo, **args)
    assert tuple(capture_fixture.calls("bankone")) == calls
    assert _catalog_jobs(repo) == before and before["bankone"] == failed
    assert select_next_catalog_job(repo) is None
