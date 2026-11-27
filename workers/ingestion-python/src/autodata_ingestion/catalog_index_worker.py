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

from .article_lifecycle import _heartbeat
from .catalog_coverage import PROVIDERS, next_catalog_job, run_catalog_index_job
from .commerce_service import WORKSHOP_PREPARATION_CHANNEL, reconcile_workshop_preparation
from .source_job_persistence import LeaseLost, claim_source_job


def select_next_catalog_job(repo, *, provider=None):
    """Read one current, eligible UUID; release the connection before any I/O."""
    with repo.connect() as conn:
        return next_catalog_job(conn, PROVIDERS if provider is None else (provider,))


def dispatch_next(repo, *, worker_id, registry, object_store, stop=None, provider=None):
    if stop is not None and stop.is_set():
        return False
    job_id = select_next_catalog_job(repo) if provider is None else select_next_catalog_job(repo, provider=provider)
    if job_id is None or (stop is not None and stop.is_set()):
        return False
    lease = claim_source_job(repo, worker_id=worker_id, model_ready=False, job_id=job_id)
    if lease is None:
        return False
    try:
        with _heartbeat(repo, lease):
            run_catalog_index_job(repo, lease, registry=registry, object_store=object_store,
                                  yield_for_waiting_job=provider is not None)
    except LeaseLost:
        # A stale lease cannot update rows or advance a cursor.
        pass
    return True


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
    """Stop between dispatches. A supplier lane can hand off after a stored page."""
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
