"""Durable article worker. SQL phases, leases and saved results are authority."""
from contextlib import contextmanager
from dataclasses import replace
from threading import Event, Thread
from uuid import uuid4
from psycopg.rows import dict_row
from . import article_lifecycle_store as store
from .source_job_persistence import (claim_source_job, heartbeat_source_job, lock_live_lease,
                                     fail_source_job, LeaseLost)
from .article_lifecycle_types import ArticleKey, SourceArticleContext
from .procedure_rewrite import (rewrite_ordered_document, validate_article_rewrite,
                                build_rewrite_prompt, editable_slots)
from .source_connector_client import SourceConnectorError


@contextmanager
def _heartbeat(repo,lease):
    stop=Event();lost=Event()
    def renew():
        while not stop.wait(10):
            try: heartbeat_source_job(repo,lease)
            except Exception:
                lost.set();return
    thread=Thread(target=renew,daemon=True);thread.start()
    try:
        yield lost
        if lost.is_set():raise LeaseLost("worker heartbeat lost")
    finally:
        stop.set();thread.join(timeout=2)


def _live(repo,lease):
    with repo.connect() as conn,conn.cursor(row_factory=dict_row) as cur:
        row=lock_live_lease(cur,lease)
    return replace(lease,phase=row["phase"],source_revision_id=row["source_revision_id"],checkpoint=row["checkpoint"])


def _capture_context(repo,lease):
    with repo.connect() as conn,conn.cursor(row_factory=dict_row) as cur:
        job=lock_live_lease(cur,lease)
        row=cur.execute("""SELECT a.*,v.make,v.model,v.model_year,v.region,
            COALESCE(s.resolution_source_snapshot_id,(SELECT o.resolution_source_snapshot_id FROM canonical_article_source_observations o WHERE o.canonical_article_id=a.canonical_article_id ORDER BY o.request_generation DESC LIMIT 1)) AS resolution_source_snapshot_id FROM canonical_articles a JOIN vehicles v USING(vehicle_id)
            LEFT JOIN catalog_article_provider_scopes s ON s.scope_key=a.scope_key AND s.provider_slug=a.provider_slug
              AND s.source_vehicle_ref=a.source_vehicle_ref WHERE a.canonical_article_id=%s""",(lease.canonical_article_id,)).fetchone()
        if row is None or row["current_job_id"]!=lease.job_id or row["request_generation"]!=lease.generation:
            raise LeaseLost("source capture generation changed")
        if row["resolution_source_snapshot_id"] is None:raise ValueError("SOURCE_BINDING_REVIEW_REQUIRED")
        vehicle={"make":row["make"],"model":row["model"],"model_year":row["model_year"],"region":row["region"]}
        key=ArticleKey(row["provider_slug"],row["vehicle_id"],row["vehicle_configuration_id"],row["source_vehicle_ref"],row["source_article_ref"])
        return SourceArticleContext(key,vehicle,row["descriptor"],row["descriptor_source_snapshot_id"],row["resolution_source_snapshot_id"],(str(row["descriptor_source_snapshot_id"]),str(row["resolution_source_snapshot_id"])))


def _hook(hooks,point):
    if hooks is not None: hooks(point)


def run_article_job(repo,lease,*,registry,object_store,model_client,hooks=None):
    """Resume one fenced job; hooks are injected local test barriers, never env code."""
    if lease.kind!="article":raise ValueError("article job required")
    with _heartbeat(repo,lease) as lost:
        try:
            lease=_live(repo,lease)
            if lease.source_revision_id is None:
                from .source_article_capture import capture_source_article
                context=_capture_context(repo,lease)
                if context.key.provider not in registry:raise ValueError("SOURCE_NOT_CONFIGURED")
                _hook(hooks,"before_source_request")
                captured=capture_source_article(context,registry=registry,object_store=object_store)
                if lost.is_set():raise LeaseLost("heartbeat lost during source IO")
                _hook(hooks,"before_source_commit")
                store.store_captured_source(repo,lease,captured)
                _hook(hooks,"after_source_commit")
                # Refresh inspection can have completed by reusing an existing
                # publication or exhausted transformation without owning its key.
                with repo.connect() as conn:
                    status=conn.execute("SELECT status FROM source_fetch_jobs WHERE source_fetch_job_id=%s",(lease.job_id,)).fetchone()["status"]
                if status=="completed":return
                lease=_live(repo,lease)
            from .article_lifecycle_types import NORMALIZATION_VERSION
            if lease.normalization_version!=NORMALIZATION_VERSION:raise ValueError("NORMALIZATION_VERSION_UNSUPPORTED")
            source=store.load_source_revision(repo,lease.source_revision_id)
            candidate=store.load_candidate(repo,lease)
            if candidate is None:
                from .procedure_normalize import normalize_procedure_article
                normalized=normalize_procedure_article(source.as_article())
                store.save_normalized_input(repo,lease,normalized)
                document=normalized["normalized_document"]
                if model_client is None:raise ValueError("MODEL_NOT_CONFIGURED")
                if not editable_slots(document):raise ValueError("REWRITE_NOT_APPLICABLE")
                prompt=build_rewrite_prompt(document,context=source.vehicle,profile_version=lease.rewrite_profile_version)
                if len(prompt.encode())>200*1024:raise ValueError("REWRITE_INPUT_LIMIT")
                attempt=store.prepare_rewrite_attempt(repo,lease,document,context=source.vehicle,model=getattr(model_client,"_model","mercury-2"))
                store.mark_rewrite_dispatched(repo,lease,attempt)
                _hook(hooks,"after_model_dispatch")
                result=rewrite_ordered_document(document,client=model_client,context=source.vehicle,profile_version=lease.rewrite_profile_version)
                if lost.is_set():raise LeaseLost("heartbeat lost during model IO")
                store.store_rewrite_result(repo,lease,result)
                _hook(hooks,"after_model_result_commit")
                candidate=store.load_candidate(repo,lease)
            validation=validate_article_rewrite(candidate["normalized_source_document"],candidate["canonical_document"],profile_version=lease.rewrite_profile_version)
            store.store_validation(repo,lease,validation)
            lease=_live(repo,lease)
            if not validation.passed or lease.checkpoint.get("rewrite_error_code"):
                fail_source_job(repo,lease,code=lease.checkpoint.get("rewrite_error_code") or validation.error_codes[0],retryable=False)
                return
            _hook(hooks,"before_publication")
            store.publish_article_revision(repo,lease,candidate["canonical_article_revision_id"],hooks=hooks)
            _hook(hooks,"after_publication_commit")
        except LeaseLost:
            return
        except SourceConnectorError as error:
            code="SOURCE_NOT_FOUND" if error.code=="NOT_FOUND" else error.code
            fail_source_job(repo,lease,code=code,retryable=error.retryable,retry_after_seconds=error.retry_after_seconds)
        except (TimeoutError,OSError) as error:
            # Timeout after dispatch cannot prove whether the upstream model ran.
            status=getattr(error,"code",None)
            retryable=status not in (400,401,403,404)
            store.record_rewrite_failure(repo,lease,code="MODEL_DELIVERY_AMBIGUOUS",ambiguous=True)
            fail_source_job(repo,lease,code="MODEL_TRANSPORT_FAILED" if retryable else "MODEL_CONFIGURATION_INVALID",retryable=retryable)
        except ValueError as error:
            code=str(error)
            if not code.isupper() or len(code)>96 or any(not(c.isalnum() or c=="_") for c in code):code="REWRITE_RESPONSE_INVALID"
            store.record_rewrite_failure(repo,lease,code=code)
            fail_source_job(repo,lease,code=code,retryable=False)


def run_article_worker_once(repo,*,worker_id,registry,object_store,model_client,hooks=None):
    lease=claim_source_job(repo,worker_id=worker_id)
    if lease is None:return False
    try:
        if lease.kind=="catalog_index":
            from .catalog_coverage import run_catalog_index_job
            with _heartbeat(repo,lease):
                run_catalog_index_job(repo,lease,registry=registry,object_store=object_store)
        else:
            run_article_job(repo,lease,registry=registry,object_store=object_store,model_client=model_client,hooks=hooks)
    except LeaseLost:
        # The lease can expire while an error handler or heartbeat is recording
        # a failure. A stale claim must not stop this process from polling.
        pass
    return True
