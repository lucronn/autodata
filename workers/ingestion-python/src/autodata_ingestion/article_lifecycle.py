"""Durable article worker. SQL phases, leases and saved results are authority."""
from contextlib import contextmanager
from dataclasses import replace
from threading import Event, Thread
from uuid import uuid4
from psycopg import Error as DatabaseError
from psycopg.errors import ConnectionTimeout, LockNotAvailable, QueryCanceled
from psycopg.rows import dict_row
from . import article_lifecycle_store as store
from .source_job_persistence import (claim_source_job, heartbeat_source_job, lock_live_lease,
                                     fail_source_job, park_automatic_for_model, LeaseLost)
from .article_lifecycle_types import (
    AUTOMATIC_REWRITE_PROFILES, ArticleKey, BANKONE_HTML_FLOW_LAYOUT, HTML_DOCUMENT_LINK_LAYOUT,
    HTML_FIGURE_CAPTION_LAYOUT, HTML_FLOW_FIGURE_CAPTION_LAYOUT,
    HTML_MULTILINE_FIGURE_CAPTION_LAYOUT, HTML_SECTION_TITLE_LAYOUT, HTML_TABLE_CAPTION_LAYOUT,
    PDF_BLANK_PAGE_LAYOUT, PDF_COMPACT_FIGURE_LAYOUT, PDF_FAST_PNG_ENCODING,
    PDF_LEGACY_FIGURE_LAYOUT, PDF_REPEAT_MARGIN_LAYOUT, SourceArticleContext,
    SOURCE_BOUND_CORRECTION_PROFILE, SOURCE_BOUND_REWRITE_PROFILE, SOURCE_PROJECTION_VERSIONS,
)
from .procedure_rewrite import (rewrite_ordered_document, validate_article_rewrite,
                                build_rewrite_prompt, editable_slots)
from .source_connector_client import SourceConnectorError
from .mercury2 import MercuryResponseError


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
    pdf_repeats_version = "source-projection-v10"
    guarded_pdf_versions = SOURCE_PROJECTION_VERSIONS[:SOURCE_PROJECTION_VERSIONS.index(pdf_repeats_version) + 1]
    with repo.connect() as conn,conn.cursor(row_factory=dict_row) as cur:
        job=lock_live_lease(cur,lease)
        row=cur.execute("""SELECT a.*,v.make,v.model,v.model_year,v.region,
            ARRAY(SELECT DISTINCT entry->>'sha256'
                FROM canonical_article_source_revisions retained
                CROSS JOIN LATERAL jsonb_array_elements(retained.resource_manifest) entries(entry)
                WHERE retained.canonical_article_id=a.canonical_article_id
                  AND entry->>'role'='document_asset' AND entry->>'media_type'='application/pdf'
                  AND entry->>'pdf_figure_encoding'=%s AND jsonb_typeof(entry->'sha256')='string'
            ) AS fast_png_roots,
            prior.projection_version AS prior_projection_version,
            prior.resource_manifest AS prior_published_resources, prior_body.content_sha256 AS prior_published_body,
            EXISTS (SELECT 1 FROM canonical_article_revisions published
                WHERE published.canonical_article_revision_id=a.current_canonical_revision_id
                  AND published.source_revision_id=prior.source_revision_id AND published.status='published'
            ) AS prior_is_published,
            COALESCE(s.resolution_source_snapshot_id,(SELECT o.resolution_source_snapshot_id FROM canonical_article_source_observations o WHERE o.canonical_article_id=a.canonical_article_id ORDER BY o.request_generation DESC LIMIT 1)) AS resolution_source_snapshot_id FROM canonical_articles a JOIN vehicles v USING(vehicle_id)
            LEFT JOIN catalog_article_provider_scopes s ON s.scope_key=a.scope_key AND s.provider_slug=a.provider_slug
              AND s.source_vehicle_ref=a.source_vehicle_ref
            LEFT JOIN canonical_article_source_revisions prior ON prior.source_revision_id=a.current_source_revision_id
              AND a.current_canonical_revision_id IS NOT NULL AND prior.projection_version=ANY(%s)
            LEFT JOIN source_snapshots prior_body ON prior_body.source_snapshot_id=prior.body_source_snapshot_id
            WHERE a.canonical_article_id=%s""",
            (PDF_FAST_PNG_ENCODING, list(guarded_pdf_versions), lease.canonical_article_id),
        ).fetchone()
        if row is None or row["current_job_id"]!=lease.job_id or row["request_generation"]!=lease.generation:
            raise LeaseLost("source capture generation changed")
        if row["resolution_source_snapshot_id"] is None:raise ValueError("SOURCE_BINDING_REVIEW_REQUIRED")
        # The bound adapter normalizes both source year aliases to `year`.
        vehicle={"make":row["make"],"model":row["model"],"year":row["model_year"],"model_year":row["model_year"],"region":row["region"]}
        evidence=[str(row["descriptor_source_snapshot_id"]),str(row["resolution_source_snapshot_id"])]
        if row["vehicle_configuration_id"] is not None:
            configuration=cur.execute("""SELECT c.trim,c.engine_displacement_l,c.engine_variant,b.body_style,b.drivetrain,b.region,
                c.source_snapshot_id,c.extraction_evidence_id,b.source_snapshot_id AS base_snapshot_id,
                b.extraction_evidence_id AS base_evidence_id FROM vehicle_configurations c
                JOIN vehicle_identity_bases b ON b.vehicle_identity_base_id=c.vehicle_identity_base_id AND b.vehicle_id=c.vehicle_id
                WHERE c.vehicle_configuration_id=%s AND c.vehicle_id=%s""",
                (row["vehicle_configuration_id"],row["vehicle_id"])).fetchone()
            if configuration is None:raise ValueError("SOURCE_BINDING_REVIEW_REQUIRED")
            for name in ("trim","body_style","drivetrain"):
                if configuration[name] is not None:vehicle[name]=configuration[name]
            displacement=configuration["engine_displacement_l"]
            if displacement is not None:vehicle["engine_displacement_l"]=float(displacement)
            variant = configuration["engine_variant"]
            if variant is not None:
                vehicle["engine_variant"] = variant
                vehicle["region"] = configuration["region"]
            label=" ".join(str(value).strip() for value in (
                configuration["trim"],f"{displacement:.1f}L" if displacement is not None else None,
                variant,configuration["drivetrain"]) if value not in (None,""))
            if label:vehicle["configuration"]=label
            evidence.extend(str(configuration[name]) for name in ("source_snapshot_id","extraction_evidence_id","base_snapshot_id","base_evidence_id"))
        key=ArticleKey(row["provider_slug"],row["vehicle_id"],row["vehicle_configuration_id"],row["source_vehicle_ref"],row["source_article_ref"])
        previous_body = row["prior_published_body"]
        legacy_figure_body = previous_body
        legacy_flow_figure_body = previous_body
        legacy_multiline_figure_body = previous_body
        legacy_table_caption_body = previous_body
        legacy_document_link_body = previous_body
        legacy_section_title_body = previous_body
        legacy_bankone_flow_body = previous_body
        previous_pdf_roots = {previous_body} if previous_body is not None else set()
        legacy_blank_pdf_roots = set()
        compact_layout_roots = set()
        margin_layout_roots = set()
        legacy_layout_roots = set()
        legacy_bankone_html = False
        legacy_bankone_svg_refs = set()
        for resource in row["prior_published_resources"] or []:
            if not isinstance(resource, dict):
                continue
            ref = resource.get("opaque_ref")
            if (resource.get("role") == "asset" and resource.get("failure_code") == "UNSUPPORTED_ASSET_MEDIA"
                    and isinstance(ref, str) and ref):
                legacy_bankone_svg_refs.add(ref)
            if not isinstance(resource.get("sha256"), str):
                continue
            digest = resource["sha256"]
            if resource.get("role") == "body" and digest == previous_body:
                if resource.get("html_figure_caption_layout") == HTML_FIGURE_CAPTION_LAYOUT:
                    legacy_figure_body = None
                if resource.get("html_flow_figure_caption_layout") == HTML_FLOW_FIGURE_CAPTION_LAYOUT:
                    legacy_flow_figure_body = None
                if resource.get("html_multiline_figure_caption_layout") == HTML_MULTILINE_FIGURE_CAPTION_LAYOUT:
                    legacy_multiline_figure_body = None
                if resource.get("html_table_caption_layout") == HTML_TABLE_CAPTION_LAYOUT:
                    legacy_table_caption_body = None
                if resource.get("html_document_link_layout") == HTML_DOCUMENT_LINK_LAYOUT:
                    legacy_document_link_body = None
                if resource.get("html_section_title_layout") == HTML_SECTION_TITLE_LAYOUT:
                    legacy_section_title_body = None
                if resource.get("bankone_html_flow_layout") == BANKONE_HTML_FLOW_LAYOUT:
                    legacy_bankone_flow_body = None
                legacy_bankone_html = resource.get("media_type") == "text/html"
            is_pdf = resource.get("role") == "document_asset" and resource.get("media_type") == "application/pdf"
            if is_pdf:
                previous_pdf_roots.add(digest)
                if resource.get("pdf_blank_page_layout") != PDF_BLANK_PAGE_LAYOUT:
                    legacy_blank_pdf_roots.add(digest)
            if is_pdf or (resource.get("role") == "body" and digest == previous_body):
                if resource.get("pdf_compact_figure_layout") == PDF_COMPACT_FIGURE_LAYOUT:
                    compact_layout_roots.add(digest)
                layout = resource.get("pdf_figure_layout")
                if layout == PDF_REPEAT_MARGIN_LAYOUT:
                    margin_layout_roots.add(digest)
                elif layout == PDF_LEGACY_FIGURE_LAYOUT:
                    legacy_layout_roots.add(digest)
        previous_has_repeats = row["prior_projection_version"] == pdf_repeats_version
        # The manifest records the selected algorithm per root, so a refresh
        # preserves the earlier v10 layout of unchanged PDFs in mixed articles.
        return SourceArticleContext(
            key, vehicle, row["descriptor"], row["descriptor_source_snapshot_id"],
            row["resolution_source_snapshot_id"], tuple(dict.fromkeys(evidence)),
            legacy_published_pdf_roots=frozenset() if previous_has_repeats else frozenset(previous_pdf_roots),
            legacy_published_pdf_margin_roots=(
                frozenset(previous_pdf_roots - margin_layout_roots) if previous_has_repeats else frozenset()
            ),
            published_legacy_pdf_layout_roots=frozenset(legacy_layout_roots) if previous_has_repeats else frozenset(),
            legacy_published_pdf_compact_roots=frozenset(previous_pdf_roots - compact_layout_roots),
            legacy_published_pdf_blank_roots=frozenset(legacy_blank_pdf_roots),
            legacy_published_html_figure_body=legacy_figure_body,
            legacy_published_html_flow_figure_body=legacy_flow_figure_body,
            legacy_published_html_multiline_figure_body=legacy_multiline_figure_body,
            legacy_published_html_table_caption_body=legacy_table_caption_body,
            legacy_published_html_document_link_body=legacy_document_link_body,
            legacy_published_html_section_title_body=legacy_section_title_body,
            legacy_published_bankone_flow_body=legacy_bankone_flow_body,
            legacy_published_bankone_svg_refs=(
                frozenset(legacy_bankone_svg_refs)
                if key.provider == "bankone" and legacy_bankone_html and row["prior_is_published"]
                and legacy_bankone_flow_body is not None else frozenset()
            ),
            has_stored_source=row["current_source_revision_id"] is not None,
            # Preserve the encoding even after an intervening partial refresh
            # whose manifest contains an attachment failure without a digest.
            fast_linked_pdf_png_roots=frozenset(row["fast_png_roots"]),
        )


def _hook(hooks,point):
    if hooks is not None: hooks(point)


def run_article_job(repo,lease,*,registry,object_store,model_client,hooks=None):
    """Resume one fenced job; hooks are injected local test barriers, never env code."""
    if lease.kind!="article":raise ValueError("article job required")
    with _heartbeat(repo,lease) as lost:
        try:
            lease=_live(repo,lease)
            profile = lease.rewrite_profile_version
            automatic = profile in AUTOMATIC_REWRITE_PROFILES
            correction = profile == SOURCE_BOUND_CORRECTION_PROFILE
            bound = lease.checkpoint.get("source_bound_rewrite")
            if (correction or "source_bound_rewrite" in lease.checkpoint) and (
                profile not in (SOURCE_BOUND_REWRITE_PROFILE, SOURCE_BOUND_CORRECTION_PROFILE)
                or lease.source_revision_id is None
                or not isinstance(bound, dict)
                or bound.get("version") != (2 if correction else 1)
                or (correction and "new_article_rollout" in lease.checkpoint)
            ):
                fail_source_job(repo, lease, code="SOURCE_BOUND_REWRITE_BINDING_INVALID", retryable=False)
                return
            if lease.source_revision_id is None:
                from .source_article_capture import capture_source_article
                context=_capture_context(repo,lease)
                if context.key.provider not in registry:raise ValueError("SOURCE_NOT_CONFIGURED")

                def save_body_preview(resource, document, **linked):
                    for _ in range(2):
                        if lost.is_set():
                            raise LeaseLost("heartbeat lost during body preview")
                        try:
                            store.store_source_body_preview(repo, lease, context, resource, document, **linked)
                            return
                        except (ConnectionTimeout, LockNotAvailable, QueryCanceled):
                            # Retry the same uploaded body under the same lease.
                            continue
                        except DatabaseError:
                            # A preview-only failure leaves the full source commit available.
                            return

                _hook(hooks,"before_source_request")
                captured = capture_source_article(
                    context, registry=registry, object_store=object_store,
                    on_body_preview=save_body_preview if context.key.vehicle_configuration_id is not None else None,
                    on_linked_preview=(
                        save_body_preview
                        if context.key.vehicle_configuration_id is not None and not context.has_stored_source
                        else None
                    ),
                    keep_embedded_pdf=True, keep_html_headings=True, keep_bound_pdf_iframes=True,
                    keep_pdf_figure_order=True, keep_multiple_pdf_figures=True,
                    keep_html_table_image_order=True, keep_repeated_pdf_figures=True,
                    keep_pdf_figures_with_margins=True,
                    keep_compact_pdf_figures=True,
                    keep_single_line_pdf_figures=True,
                    skip_blank_linked_pdf_pages=True,
                    keep_wordless_linked_pdf_figures=True,
                    keep_html_figure_captions=True,
                    keep_html_flow_figure_captions=True,
                    keep_html_multiline_figure_captions=True,
                    keep_html_table_captions=True,
                    keep_html_media_table_headers=True,
                    keep_html_table_spans=True,
                    keep_html_nested_tables=True,
                    keep_structured_table_columns=True,
                    keep_structured_table_cell_order=True,
                    keep_structured_table_column_order=True,
                    keep_image_only_headings=True,
                    keep_ordered_step_instructions=True,
                    keep_image_only_step_instructions=True,
                    keep_leading_decimals=True,
                    keep_html_numeric_superscripts=True,
                    keep_html_document_links=True,
                    keep_html_section_titles=True,
                    keep_bankone_html_flow=True,
                    keep_mixed_html_pdf_embeds=True,
                    keep_bound_html_images=True,
                )
                if lost.is_set():raise LeaseLost("heartbeat lost during source IO")
                _hook(hooks,"before_source_commit")
                try:
                    store.store_captured_source(repo,lease,captured)
                except (ConnectionTimeout, LockNotAvailable, QueryCanceled):
                    if lost.is_set():
                        raise LeaseLost("heartbeat lost during source storage")
                    # The failed transaction rolled back. Retry the same capture
                    # under the same lease without fetching or writing media again.
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
                normalized=normalize_procedure_article(source.as_article(), resource_manifest=source.resource_manifest)
                store.save_normalized_input(repo,lease,normalized)
                document=normalized["normalized_document"]
                from .procedure_rewrite_full import prose_slots
                if correction:
                    if model_client is None:
                        park_automatic_for_model(repo,lease)
                        return
                    store.run_source_bound_correction(repo,lease,document,model_client=model_client,hooks=hooks)
                    _hook(hooks,"after_model_result_commit")
                elif automatic and not prose_slots(document, include_cell_blocks=True):
                    store.store_source_preserving_candidate(repo,lease)
                    _hook(hooks,"after_source_preserving_candidate_commit")
                else:
                    if model_client is None:
                        if automatic:
                            park_automatic_for_model(repo,lease)
                            return
                        raise ValueError("MODEL_NOT_CONFIGURED")
                    if profile == "technical-prose-v2":
                        from .procedure_rewrite_v2 import plan_v2
                        plan = plan_v2(document)
                        if not plan["eligible"]:raise ValueError(plan["error_code"])
                    elif not automatic and profile not in ("technical-prose-v1", "full-prose-review-v1"):
                        raise ValueError("REWRITE_PROFILE_UNSUPPORTED")
                    if not automatic and profile != "full-prose-review-v1" and not editable_slots(document, profile_version=profile):raise ValueError("REWRITE_NOT_APPLICABLE")
                    prompt=build_rewrite_prompt(document,context=source.vehicle,profile_version=profile)
                    if len(prompt.encode())>200*1024:raise ValueError("REWRITE_INPUT_LIMIT")
                    attempt=store.prepare_rewrite_attempt(repo,lease,document,context=source.vehicle,model=getattr(model_client,"_model","mercury-2"))
                    store.mark_rewrite_dispatched(repo,lease,attempt)
                    _hook(hooks,"after_model_dispatch")
                    result=rewrite_ordered_document(document,client=model_client,context=source.vehicle,profile_version=profile)
                    if lost.is_set():raise LeaseLost("heartbeat lost during model IO")
                    store.store_rewrite_result(repo,lease,result)
                    _hook(hooks,"after_model_result_commit")
                    if profile == "full-prose-review-v1" and not result.error_code:
                        return
                candidate=store.load_candidate(repo,lease)
            if automatic or profile == "full-prose-review-v1":
                # A saved failed response is original evidence, not a successful
                # draft to reconstruct; retain its specific mechanical failure.
                lease=_live(repo,lease)
                if lease.checkpoint.get("rewrite_error_code"):
                    fail_source_job(repo,lease,code=lease.checkpoint["rewrite_error_code"],retryable=False)
                    return
            validation=store.validate_saved_candidate(repo,lease,candidate)
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
            if lease.source_revision_id is None:
                fail_source_job(repo,lease,code="SOURCE_TRANSPORT_FAILED",retryable=retryable)
            else:
                store.record_rewrite_failure(repo,lease,code="MODEL_DELIVERY_AMBIGUOUS",ambiguous=True)
                fail_source_job(repo,lease,code="MODEL_TRANSPORT_FAILED" if retryable else "MODEL_CONFIGURATION_INVALID",retryable=retryable)
        except (MercuryResponseError,store.RewriteStorageError) as error:
            code="REWRITE_RESPONSE_INVALID" if isinstance(error,MercuryResponseError) else error.code
            store.record_rewrite_failure(repo,lease,code=code,failure=error)
            fail_source_job(repo,lease,code=code,retryable=False)
        except ValueError as error:
            code=str(error)
            if not code.isupper() or len(code)>96 or any(not(c.isalnum() or c=="_") for c in code):code="REWRITE_RESPONSE_INVALID"
            if lease.source_revision_id is not None:
                store.record_rewrite_failure(repo,lease,code=code)
            fail_source_job(repo,lease,code=code,retryable=False)


def run_article_worker_once(repo,*,worker_id,registry,object_store,model_client,hooks=None,job_id=None):
    lease=claim_source_job(repo,worker_id=worker_id,model_ready=model_client is not None,job_id=job_id)
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
