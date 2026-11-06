"""Serial catalog-only admission through the existing exact-job lifecycle worker."""
import argparse
import os
import signal
from threading import Event
from urllib.parse import urlsplit
from uuid import uuid4

from .article_lifecycle import run_article_worker_once


def select_next_catalog_job(repo):
    """Read one current, eligible UUID; release the connection before any I/O."""
    with repo.connect() as conn:
        row = conn.execute(
            """SELECT j.source_fetch_job_id FROM source_fetch_jobs j
            JOIN catalog_article_provider_scopes s
              ON s.catalog_provider_scope_id=j.catalog_provider_scope_id
            WHERE j.job_kind=%s AND j.provider_slug=ANY(%s)
              AND s.provider_slug=j.provider_slug
              AND s.vehicle_id=j.canonical_vehicle_id
              AND s.current_job_id=j.source_fetch_job_id
              AND s.generation=j.request_generation
              AND ((j.status IN ('pending','failed') AND j.retry_count<j.max_attempts
                    AND COALESCE(j.next_attempt_at,'-infinity'::timestamptz)<=clock_timestamp())
                   OR (j.status='processing' AND j.lease_expires_at<clock_timestamp()))
            ORDER BY j.created_at,j.source_fetch_job_id LIMIT 1""",
            ('catalog_index', ['bankone', 'banktwo']),
        ).fetchone()
    return row['source_fetch_job_id'] if row else None


def dispatch_next(repo, *, worker_id, registry, object_store, stop=None):
    if stop is not None and stop.is_set():
        return False
    job_id = select_next_catalog_job(repo)
    if job_id is None or (stop is not None and stop.is_set()):
        return False
    return run_article_worker_once(
        repo, worker_id=worker_id, registry=registry, object_store=object_store,
        model_client=None, job_id=job_id,
    )


def run_catalog_worker(repo, *, registry, object_store, once=False, stop=None):
    """Signals stop between jobs; an active multi-page job may run much longer."""
    if stop is None:
        stop = Event()
    worker_id = uuid4()
    while not stop.is_set():
        claimed = dispatch_next(repo, worker_id=worker_id, registry=registry,
                                object_store=object_store, stop=stop)
        if once:
            break
        if not claimed:
            stop.wait(2)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args(argv)
    try:
        # Require explicit runtime configuration; never use development credentials.
        required = ('AUTODATA_DB_ADDRESS', 'AUTODATA_POSTGRES_DB',
                    'AUTODATA_POSTGRES_USER', 'AUTODATA_POSTGRES_PASSWORD',
                    'AUTODATA_S3_ENDPOINT', 'AUTODATA_S3_ACCESS_KEY',
                    'AUTODATA_S3_SECRET_KEY', 'AUTODATA_SOURCE_BUCKET',
                    'BANKONE_BASE_URL', 'AUTODATA_BANKONE_API_KEY',
                    'BANKTWO_BASE_URL', 'AUTODATA_BANKTWO_API_KEY')
        if any(not os.environ.get(name, '').strip() for name in required):
            raise ValueError('CONFIGURATION_REQUIRED')
        parsed = urlsplit(os.environ['AUTODATA_S3_ENDPOINT'])
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                or (parsed.port is None and parsed.netloc.endswith(':'))
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
            raise ValueError('OBJECT_STORE_CONFIGURATION_INVALID')
        from .worker import ArticleRepository, ArticleObjectStore
        from .source_connector_client import source_connector_registry
        objects = ArticleObjectStore(
            endpoint=parsed.netloc, secure=parsed.scheme == 'https',
            access_key=os.environ['AUTODATA_S3_ACCESS_KEY'],
            secret_key=os.environ['AUTODATA_S3_SECRET_KEY'],
            bucket=os.environ['AUTODATA_SOURCE_BUCKET'],
        )
        stop = Event()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        return run_catalog_worker(ArticleRepository(),
            registry=source_connector_registry(include_defaults=False),
            object_store=objects, once=args.once, stop=stop)
    except Exception:
        # Provider bodies, SQL and credentials never enter diagnostics.
        print('CATALOG_INDEX_WORKER_BLOCKED', flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
