"""Catalog-only admission through the existing exact-job lifecycle worker."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import os
import signal
from threading import Event
from time import monotonic
from urllib.parse import urlsplit
from uuid import uuid4

from psycopg import Error, OperationalError, sql

from .article_lifecycle import run_article_worker_once
from .catalog_coverage import PROVIDERS
from .commerce_service import WORKSHOP_PREPARATION_CHANNEL, reconcile_workshop_preparation


def select_next_catalog_job(repo, *, provider=None):
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
            ('catalog_index', list(PROVIDERS) if provider is None else [provider]),
        ).fetchone()
    return row['source_fetch_job_id'] if row else None


def dispatch_next(repo, *, worker_id, registry, object_store, stop=None, provider=None):
    if stop is not None and stop.is_set():
        return False
    job_id = select_next_catalog_job(repo) if provider is None else select_next_catalog_job(repo, provider=provider)
    if job_id is None or (stop is not None and stop.is_set()):
        return False
    return run_article_worker_once(
        repo, worker_id=worker_id, registry=registry, object_store=object_store,
        model_client=None, job_id=job_id,
    )


def _listen_for_preparation(repo):
    listener = None
    try:
        listener = repo.connect()
        listener.autocommit = True
        listener.execute(sql.SQL('LISTEN {}').format(sql.Identifier(WORKSHOP_PREPARATION_CHANNEL)))
        return listener
    except (Error, OSError):
        if listener is not None:
            listener.close()
        return None


def _run_provider_catalog_worker(repo, *, provider, registry, object_store, wake, stop):
    worker_id = uuid4()
    while not stop.is_set():
        wake.clear()
        if not dispatch_next(repo, worker_id=worker_id, registry=registry,
                             object_store=object_store, stop=stop, provider=provider):
            wake.wait(2)


def _stop_provider_catalog_workers(stop, wakes):
    stop.set()
    for wake in wakes.values():
        wake.set()


def run_catalog_worker(repo, *, registry, object_store, once=False, prepare_orders=False, stop=None):
    """Signals stop between jobs; an active multi-page job may run much longer."""
    if stop is None:
        stop = Event()
    worker_id = uuid4()
    wake_on_checkout = prepare_orders and not once
    with ExitStack() as workers:
        wakes = {}
        provider_workers = []
        if wake_on_checkout and all(provider in registry for provider in PROVIDERS):
            # Each bank keeps serial exact-job dispatch, with preparation independent of supplier I/O.
            pool = workers.enter_context(ThreadPoolExecutor(max_workers=len(PROVIDERS),
                                                            thread_name_prefix="catalog-index"))
            wakes = {provider: Event() for provider in PROVIDERS}
            workers.callback(_stop_provider_catalog_workers, stop, wakes)
            provider_workers = [
                pool.submit(_run_provider_catalog_worker, repo, provider=provider, registry=registry,
                            object_store=object_store, wake=wake, stop=stop)
                for provider, wake in wakes.items()
            ]
        _run_catalog_preparation_loop(
            repo, worker_id, registry, object_store, once, prepare_orders, stop, wakes, provider_workers
        )
    return 0


def _run_catalog_preparation_loop(repo, worker_id, registry, object_store, once, prepare_orders, stop,
                                  wakes, provider_workers):
    next_preparation = 0.0
    wake_on_checkout = prepare_orders and not once
    listener = None
    try:
        while not stop.is_set():
            for future in provider_workers:
                if future.done():
                    future.result()
            if prepare_orders and monotonic() >= next_preparation:
                # Subscribe before reading the durable queue, including on reconnect.
                if wake_on_checkout and listener is None:
                    listener = _listen_for_preparation(repo)
                try:
                    with repo.connect() as connection:
                        prepared = reconcile_workshop_preparation(connection)
                    if prepared:
                        for wake in wakes.values():
                            wake.set()
                except OperationalError:
                    print('CATALOG_ORDER_PREPARATION_RETRY', flush=True)
                next_preparation = monotonic() + 2
            claimed = not provider_workers and dispatch_next(
                repo, worker_id=worker_id, registry=registry, object_store=object_store, stop=stop
            )
            if once or stop.is_set():
                break
            if claimed:
                continue
            if listener is not None:
                try:
                    for _ in listener.notifies(timeout=2, stop_after=1):
                        next_preparation = 0.0
                except (Error, OSError):
                    listener.close()
                    listener = None
                else:
                    continue
            stop.wait(2)
    finally:
        if listener is not None:
            listener.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--prepare-workshop-orders', action='store_true',
                        help='Schedule catalog indexes for paid Workshop orders without calling Stripe.')
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
            object_store=objects, once=args.once, prepare_orders=args.prepare_workshop_orders, stop=stop)
    except Exception:
        # Provider bodies, SQL and credentials never enter diagnostics.
        print('CATALOG_INDEX_WORKER_BLOCKED', flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
