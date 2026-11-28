"""Finite or opt-in continuous pristine admission around the exact-job worker.

Reservations are deliberately never replayed: a crash may spend quota without
work, but cannot authorize another HTTP/model delivery for the same job.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import re
from select import select
import signal
from socket import socketpair
import stat
from threading import Event
from uuid import UUID, uuid4

from psycopg import DatabaseError, sql

STATE_DIRECTORY = Path('/var/lib/autodata/new-article-worker')
MAX_STATE_BYTES = 16384
CONTINUOUS_MAX_STATE_BYTES = 2 * 1024 * 1024
CONTINUOUS_MAX_RESERVATIONS = 10000
WINDOW = timedelta(hours=24)
PAID_SOURCE_INTERVAL = timedelta(seconds=30)
ARTICLE_ACTIVITY_POLL_SECONDS = 2


class WorkerBlocked(RuntimeError):
    """Content-free operational failure; never log configuration or SQL data."""


def _timestamp(value):
    try:
        result = datetime.fromisoformat(value)
        if result.utcoffset() != timedelta(0):
            raise ValueError()
        return result
    except (TypeError, ValueError):
        raise WorkerBlocked('ROLLOUT_TIMESTAMP_INVALID') from None


def _uuid(value):
    try:
        if str(UUID(value)) != value:
            raise ValueError()
    except (TypeError, ValueError, AttributeError):
        raise WorkerBlocked('ROLLOUT_UUID_INVALID') from None


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WorkerBlocked('ROLLOUT_DUPLICATE_KEY')
        result[key] = value
    return result


class RolloutState:
    """Fixed production directory; constructor injection is for isolated tests."""

    def __init__(self, directory=STATE_DIRECTORY, *, source_sha, owner_uid=0, continuous=False):
        if not re.fullmatch('[a-f0-9]{40}', source_sha):
            raise WorkerBlocked('ROLLOUT_SOURCE_INVALID')
        self.directory = Path(directory)
        self.source_sha = source_sha
        self.schema = 2 if continuous else 1
        self.max_bytes = CONTINUOUS_MAX_STATE_BYTES if continuous else MAX_STATE_BYTES
        self.owner_uid = owner_uid
        self.fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            self.identity = os.fstat(self.fd)
            self._metadata(self.identity, directory=True)
        except BaseException:
            os.close(self.fd)
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        os.close(self.fd)

    def _metadata(self, info, *, directory=False):
        expected_mode = 0o700 if directory else 0o600
        kind = stat.S_ISDIR if directory else stat.S_ISREG
        if (not kind(info.st_mode) or info.st_uid != self.owner_uid
                or stat.S_IMODE(info.st_mode) != expected_mode
                or (not directory and info.st_nlink != 1)):
            raise WorkerBlocked('ROLLOUT_METADATA_INVALID')

    def _directory(self):
        info = os.stat(self.directory, follow_symlinks=False)
        self._metadata(info, directory=True)
        if (info.st_dev, info.st_ino) != (self.identity.st_dev, self.identity.st_ino):
            raise WorkerBlocked('ROLLOUT_DIRECTORY_REPLACED')

    def _open(self, name, *, create=False):
        self._directory()
        fd = os.open(name, os.O_RDWR | os.O_NOFOLLOW | (os.O_CREAT if create else 0),
                     0o600, dir_fd=self.fd)
        try:
            self._metadata(os.fstat(fd))
            return fd
        except BaseException:
            os.close(fd)
            raise

    @contextmanager
    def _lock(self, name, *, nonblocking=False):
        fd = self._open(name, create=True)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0))
            except BlockingIOError:
                raise WorkerBlocked('WORKER_ALREADY_RUNNING') from None
            self._directory()
            current = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (os.fstat(fd).st_dev, os.fstat(fd).st_ino):
                raise WorkerBlocked('ROLLOUT_LOCK_REPLACED')
            yield
        finally:
            os.close(fd)

    def worker_lock(self):
        return self._lock('worker.lock', nonblocking=True)

    def _validate(self, value, *, source_shas=None):
        source_shas = (self.source_sha,) if source_shas is None else source_shas
        keys = {'schema', 'rollout_id', 'source_sha', 'cutoff', 'expires_at', 'providers',
                'max_jobs', 'enabled', 'reservations'}
        if self.schema == 2:
            keys.remove('expires_at')
        if not isinstance(value, dict) or set(value) != keys:
            raise WorkerBlocked('ROLLOUT_SHAPE_INVALID')
        if (type(value['schema']) is not int or value['schema'] != self.schema
                or value['source_sha'] not in source_shas
                or value['providers'] != ['bankone', 'banktwo']
                or type(value['max_jobs']) is not int or value['max_jobs'] != 10
                or type(value['enabled']) is not bool):
            raise WorkerBlocked('ROLLOUT_SCOPE_INVALID')
        _uuid(value['rollout_id'])
        cutoff = _timestamp(value['cutoff'])
        expiry = _timestamp(value['expires_at']) if self.schema == 1 else None
        if self.schema == 1 and expiry != cutoff + WINDOW:
            raise WorkerBlocked('ROLLOUT_EXPIRY_INVALID')
        reservations = value['reservations']
        if not isinstance(reservations, list) or len(reservations) > (10 if self.schema == 1 else CONTINUOUS_MAX_RESERVATIONS):
            raise WorkerBlocked('ROLLOUT_QUOTA_INVALID')
        seen = set()
        timestamps = []
        for item in reservations:
            if not isinstance(item, dict) or set(item) != {'job_id', 'reserved_at'}:
                raise WorkerBlocked('ROLLOUT_RESERVATION_INVALID')
            _uuid(item['job_id'])
            reserved_at = _timestamp(item['reserved_at'])
            if item['job_id'] in seen or reserved_at < cutoff or (expiry is not None and reserved_at >= expiry):
                raise WorkerBlocked('ROLLOUT_RESERVATION_INVALID')
            seen.add(item['job_id']); timestamps.append(reserved_at)
        if self.schema == 2:
            # Sort a copy: stored order and every spent UUID remain permanent.
            timestamps.sort()
            if any(timestamps[i] - timestamps[i-10] < WINDOW for i in range(10, len(timestamps))):
                raise WorkerBlocked('ROLLOUT_HISTORICAL_QUOTA_INVALID')
        return value

    def _read(self, *, source_shas=None):
        fd = self._open('rollout.json')
        try:
            raw = os.read(fd, self.max_bytes + 1)
            if len(raw) > self.max_bytes:
                raise WorkerBlocked('ROLLOUT_TOO_LARGE')
            value = json.loads(raw, object_pairs_hook=_object)
            current = os.stat('rollout.json', dir_fd=self.fd, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (os.fstat(fd).st_dev, os.fstat(fd).st_ino):
                raise WorkerBlocked('ROLLOUT_FILE_REPLACED')
            return self._validate(value, source_shas=source_shas)
        except (ValueError, UnicodeError):
            raise WorkerBlocked('ROLLOUT_JSON_INVALID') from None
        finally:
            os.close(fd)

    def _write(self, value):
        self._validate(value)
        self._directory()
        payload = json.dumps(value, sort_keys=True).encode() + b'\n'
        if len(payload) > self.max_bytes:
            raise WorkerBlocked('ROLLOUT_TOO_LARGE')
        temporary = '.rollout-' + uuid4().hex
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=self.fd)
        try:
            payload = json.dumps(value, sort_keys=True).encode() + b'\n'
            with os.fdopen(fd, 'wb') as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            self._directory()
            os.replace(temporary, 'rollout.json', src_dir_fd=self.fd, dst_dir_fd=self.fd)
            os.fsync(self.fd)
        finally:
            try:
                os.unlink(temporary, dir_fd=self.fd)
            except FileNotFoundError:
                pass

    def initialize(self, now):
        with self.worker_lock(), self._lock('state.lock'):
            try:
                os.stat('rollout.json', dir_fd=self.fd, follow_symlinks=False)
            except FileNotFoundError:
                value = {'schema': self.schema, 'rollout_id': str(uuid4()), 'source_sha': self.source_sha,
                    'cutoff': now.isoformat(), 'providers': ['bankone', 'banktwo'], 'max_jobs': 10,
                    'enabled': False, 'reservations': []}
                if self.schema == 1:
                    value['expires_at'] = (now + WINDOW).isoformat()
                self._write(value)
                return
            raise WorkerBlocked('ROLLOUT_ALREADY_INITIALIZED')

    def read(self):
        with self._lock('state.lock'):
            return self._read()

    def rebind_source(self, previous_sha):
        """Move a stopped continuous rollout to a new source pin."""
        if (self.schema != 2 or not re.fullmatch('[a-f0-9]{40}', previous_sha)
                or previous_sha == self.source_sha):
            raise WorkerBlocked('ROLLOUT_REBIND_INVALID')
        with self.worker_lock(), self._lock('state.lock'):
            value = self._read(source_shas=(previous_sha, self.source_sha))
            if value['source_sha'] == self.source_sha:
                return
            value['source_sha'] = self.source_sha
            self._write(value)

    def set_enabled(self, enabled):
        with self._lock('state.lock'):
            value = self._read()
            value['enabled'] = enabled
            self._write(value)

    @staticmethod
    def running(value, now):
        if value['schema'] == 1:
            return RolloutState.active(value, now)
        timestamps = [_timestamp(r['reserved_at']) for r in value['reservations']]
        if now < _timestamp(value['cutoff']) or (timestamps and now < max(timestamps)):
            raise WorkerBlocked('ROLLOUT_CLOCK_REGRESSION')
        if len(timestamps) >= CONTINUOUS_MAX_RESERVATIONS:
            raise WorkerBlocked('ROLLOUT_CAPACITY_EXHAUSTED')
        return value['enabled']

    @staticmethod
    def active(value, now):
        if value['schema'] == 2:
            return (RolloutState.running(value, now) and sum(
                now - WINDOW < _timestamp(r['reserved_at']) <= now for r in value['reservations']
            ) < value['max_jobs'])
        return (value['enabled'] and _timestamp(value['cutoff']) <= now < _timestamp(value['expires_at'])
                and len(value['reservations']) < value['max_jobs'])

    def reserve(self, job_id, now, *, stop=None):
        with self._lock('state.lock'):
            value = self._read()
            if ((stop is not None and stop.is_set()) or not self.active(value, now)
                    or str(job_id) in {r['job_id'] for r in value['reservations']}):
                return False
            value['reservations'].append({'job_id': str(job_id), 'reserved_at': now.isoformat()})
            self._write(value)
            return True


# These predicates intentionally exclude every history/recovery/resume lane.
_PRISTINE = """
    j.job_kind='article' AND j.status='pending' AND j.phase='queued'
    AND j.retry_count=0 AND j.lease_token=0 AND NOT j.retryable
    AND j.lease_owner IS NULL AND j.lease_expires_at IS NULL AND j.heartbeat_at IS NULL
    AND j.next_attempt_at IS NULL AND j.error_code IS NULL AND j.last_error IS NULL
    AND j.source_revision_id IS NULL AND j.transformation_key IS NULL
    AND j.request_generation=0 AND a.request_generation=0
    AND a.current_job_id=j.source_fetch_job_id
    AND a.provider_slug=j.provider_slug AND j.provider_slug=ANY(%(providers)s)
    AND a.created_at>%(cutoff)s AND j.created_at>%(cutoff)s
    AND a.target_normalization_version='ordered-article-v1' AND j.normalization_version=a.target_normalization_version
    AND a.target_rewrite_profile_version='full-prose-auto-v1' AND j.rewrite_profile_version=a.target_rewrite_profile_version
    AND a.membership_status='active' AND a.takedown_status='active'
    AND a.current_source_revision_id IS NULL AND a.current_canonical_revision_id IS NULL
    AND NOT EXISTS (SELECT 1 FROM source_fetch_jobs old WHERE old.canonical_article_id=a.canonical_article_id AND old.source_fetch_job_id<>j.source_fetch_job_id)
    AND NOT EXISTS (SELECT 1 FROM canonical_article_source_revisions s WHERE s.canonical_article_id=a.canonical_article_id)
    AND NOT EXISTS (SELECT 1 FROM canonical_article_source_observations o WHERE o.canonical_article_id=a.canonical_article_id)
    AND NOT EXISTS (SELECT 1 FROM canonical_article_revisions r WHERE r.canonical_article_id=a.canonical_article_id)
    AND NOT EXISTS (SELECT 1 FROM canonical_article_rewrite_attempts t JOIN source_fetch_jobs tj ON tj.source_fetch_job_id=t.source_fetch_job_id WHERE tj.canonical_article_id=a.canonical_article_id)
"""


# A fresh on-demand job may target an older untouched descriptor in schema2.
# All history, ownership, rights and job-created-after-activation guards stay exact.
_PRISTINE_CONTINUOUS = _PRISTINE.replace('a.created_at>%(cutoff)s AND ', '')


def admission_predicate(value):
    return _PRISTINE_CONTINUOUS if value['schema'] == 2 else _PRISTINE


def database_now(repo):
    with repo.connect() as conn:
        return conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']


# Current scope and full order/entitlement ownership are required for an
# on-demand capture that does not spend a legacy rollout reservation.
_PAID_SOURCE_SCOPE = """
    EXISTS (
        SELECT 1 FROM vehicle_configurations c
        JOIN vehicle_identity_bases b ON b.vehicle_identity_base_id=c.vehicle_identity_base_id
                                     AND b.vehicle_id=c.vehicle_id
        JOIN entitlements e ON e.configuration_id=c.vehicle_configuration_id AND e.region=b.region
        JOIN workshop_orders o ON o.order_id=e.commerce_order_id AND o.entitlement_id=e.entitlement_id
                               AND o.configuration_id=e.configuration_id AND o.region=e.region
                               AND o.customer_account_id=e.customer_account_id AND o.organization_id=e.organization_id
        JOIN customer_accounts acct ON acct.customer_account_id=e.customer_account_id
                                    AND acct.personal_organization_id=e.organization_id
        WHERE c.vehicle_configuration_id=a.vehicle_configuration_id AND c.vehicle_id=a.vehicle_id
          AND c.reviewer_state<>'rejected' AND b.reviewer_state<>'rejected'
          AND (c.engine_variant IS NULL OR c.engine_variant_market_verified)
          AND e.status='active' AND o.status='paid' AND acct.status='active'
    )
"""
_SOURCE_COOLDOWN = """
    NOT EXISTS (
        SELECT 1 FROM source_fetch_jobs previous
        WHERE previous.provider_slug=j.provider_slug AND previous.job_kind='article'
          AND (previous.checkpoint->>'source_cooldown_until')::timestamptz>%(now)s
    )
"""
_PAID_SOURCE_READY = _PAID_SOURCE_SCOPE + " AND " + _SOURCE_COOLDOWN + """ AND NOT EXISTS (
    SELECT 1 FROM source_fetch_jobs previous
    WHERE previous.provider_slug=j.provider_slug AND previous.job_kind='article'
      AND (previous.checkpoint->>'paid_source_reserved_at')::timestamptz>%(available_since)s
)"""


def _reserve_next_article(repo, state, *, providers=None, stop=None, paid_overflow=False):
    """Persist quota first, then commit cap1; any exception prevents dispatch."""
    from psycopg.types.json import Jsonb
    snapshot = state.read()
    if stop is not None and stop.is_set():
        return None
    allowed = [item for item in snapshot['providers'] if providers is None or item in providers]
    if not allowed:
        return None
    with repo.connect() as conn:
        now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        if paid_overflow:
            if snapshot['schema'] != 2 or not state.running(snapshot, now):
                return None
            eligibility = _PAID_SOURCE_READY
        else:
            if not state.active(snapshot, now):
                return None
            eligibility = _SOURCE_COOLDOWN
        params = {'providers': allowed, 'cutoff': _timestamp(snapshot['cutoff']),
                  'reserved': [UUID(r['job_id']) for r in snapshot['reservations']],
                  'now': now, 'available_since': now - PAID_SOURCE_INTERVAL}
        predicate = admission_predicate(snapshot) + ' AND ' + eligibility
        row = conn.execute('''SELECT j.source_fetch_job_id,j.provider_slug FROM source_fetch_jobs j
            JOIN canonical_articles a ON a.canonical_article_id=j.canonical_article_id WHERE ''' + predicate + '''
            AND j.checkpoint='{}'::jsonb AND NOT (j.source_fetch_job_id=ANY(%(reserved)s::uuid[]))
            ORDER BY j.created_at,j.source_fetch_job_id LIMIT 1 FOR UPDATE OF j,a SKIP LOCKED''', params).fetchone()
        if row is None:
            return None
        job_id = row['source_fetch_job_id']
        provider = row['provider_slug']
        # Re-evaluate after both locks: a concurrent scheduler may have changed
        # an owning row while PostgreSQL was acquiring the joined locks.
        params.update(job_id=job_id, providers=[provider])
        eligible = conn.execute('''SELECT 1 FROM source_fetch_jobs j JOIN canonical_articles a
            ON a.canonical_article_id=j.canonical_article_id WHERE ''' + predicate + '''
            AND j.checkpoint='{}'::jsonb AND j.source_fetch_job_id=%(job_id)s''', params).fetchone()
        if eligible is None:
            return None
        now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        if stop is not None and stop.is_set():
            return None
        if paid_overflow:
            if not state.running(state.read(), now):
                return None
        elif not state.reserve(job_id, now, stop=stop):
            return None
        marker = {'new_article_rollout': {'rollout_id': snapshot['rollout_id'],
            'source_sha': snapshot['source_sha'], 'cutoff': snapshot['cutoff'], 'max_model_attempts': 1}}
        if paid_overflow:
            # Persist the reservation under the existing row locks. The legacy
            # ledger is unchanged and a rollback skips this non-pristine row.
            marker['paid_source_reserved_at'] = now.isoformat()
        conn.execute('''UPDATE source_fetch_jobs SET max_attempts=1,checkpoint=%s,
            updated_at=clock_timestamp() WHERE source_fetch_job_id=%s''', (Jsonb(marker), job_id))
    # Connection context has committed before this UUID escapes to dispatch.
    return job_id, provider


def reserve_next_job(repo, state, *, stop=None):
    reserved = _reserve_next_article(repo, state, stop=stop)
    return reserved[0] if reserved is not None else None


def dispatch_next(repo, state, *, worker_id, registry, object_store, model_client, hooks=None, stop=None):
    if stop is not None and stop.is_set():
        return False
    if model_client is None:
        raise WorkerBlocked('MODEL_NOT_CONFIGURED')
    job_id = reserve_next_job(repo, state, stop=stop)
    if job_id is None:
        return False
    return _dispatch_reserved_job(repo, state, job_id, worker_id=worker_id, registry=registry,
        object_store=object_store, model_client=model_client, hooks=hooks, stop=stop)


class _CooldownConnector:
    """Remember a provider's 429 even when only an optional resource failed."""

    def __init__(self, connector, repo, job_id):
        self._connector = connector
        self.provider = connector.provider
        self._repo = repo
        self._job_id = job_id

    def read_resource(self, resource_ref, *, timeout):
        from .source_connector_client import SourceConnectorError
        try:
            return self._connector.read_resource(resource_ref, timeout=timeout)
        except SourceConnectorError as error:
            if error.code == "RATE_LIMITED":
                delay = min(900, max(1, error.retry_after_seconds or 60))
                with self._repo.connect() as conn:
                    conn.execute("""UPDATE source_fetch_jobs
                        SET checkpoint=checkpoint||jsonb_build_object('source_cooldown_until',
                            GREATEST((checkpoint->>'source_cooldown_until')::timestamptz,
                                     clock_timestamp()+make_interval(secs=>%s)))
                        WHERE source_fetch_job_id=%s""", (delay, self._job_id))
            raise


def _dispatch_reserved_job(repo, state, job_id, *, worker_id, registry, object_store, model_client,
                           provider=None, hooks=None, stop=None, model_slot=None, paid_overflow=False):
    # Rollout disable prevents new reservations. An admitted job can drain.
    snapshot = state.read()
    if stop is not None and stop.is_set():
        return False
    providers = [item for item in snapshot['providers'] if provider is None or item == provider]
    params = {'providers': providers, 'cutoff': _timestamp(snapshot['cutoff']), 'job_id': job_id}
    from psycopg.types.json import Jsonb
    params['marker'] = Jsonb({'new_article_rollout': {'rollout_id': snapshot['rollout_id'],
        'source_sha': snapshot['source_sha'], 'cutoff': snapshot['cutoff'], 'max_model_attempts': 1}})
    predicate = "j.checkpoint=%(marker)s"
    if paid_overflow:
        predicate = ("j.checkpoint - 'paid_source_reserved_at'::text=%(marker)s"
                     " AND j.checkpoint ? 'paid_source_reserved_at' AND " + _PAID_SOURCE_SCOPE)
    with repo.connect() as conn:
        permitted = conn.execute('''SELECT 1 FROM source_fetch_jobs j JOIN canonical_articles a
            ON a.canonical_article_id=j.canonical_article_id WHERE ''' + admission_predicate(snapshot) + '''
            AND j.source_fetch_job_id=%(job_id)s AND j.max_attempts=1 AND ''' + predicate, params).fetchone()
    if permitted is None:
        return False
    from .article_lifecycle import run_article_worker_once
    if stop is not None and stop.is_set():
        return False
    if snapshot['schema'] == 2 and provider in registry:
        registry = {provider: _CooldownConnector(registry[provider], repo, job_id)}
    return run_article_worker_once(repo, worker_id=worker_id, registry=registry,
        object_store=object_store, model_client=model_client, hooks=hooks, job_id=job_id, model_slot=model_slot)


def configured_model():
    """Validate reviewed rewrite settings; Mercury transport performs no retries."""
    if (not os.getenv('INCEPTION_API_KEY', '').strip()
            or os.getenv('INCEPTION_MODEL') != 'mercury-3'
            or os.getenv('INCEPTION_MAX_TOKENS') != '32768'
            or os.getenv('INCEPTION_API_TIMEOUT_SECONDS') != '60'):
        raise WorkerBlocked('MODEL_CONFIGURATION_NOT_APPROVED')
    from .mercury2 import Mercury2Client
    return Mercury2Client.from_environment()


def _subscribe_to_article_jobs(repo):
    from .source_job_persistence import ARTICLE_JOB_CHANNEL

    listener = None
    try:
        listener = repo.connect()
        listener.autocommit = True
        listener.execute(sql.SQL("LISTEN {}").format(sql.Identifier(ARTICLE_JOB_CHANNEL)))
        return listener
    except (DatabaseError, OSError):
        if listener is not None:
            listener.close()
        return None


def _paid_source_poll_timeout(repo, providers):
    """Wake near the next supplier gate while retaining normal idle polling."""
    with repo.connect() as conn:
        row = conn.execute("""
            SELECT MIN(ready_at) - statement_timestamp() AS remaining
            FROM (
                SELECT GREATEST(
                    MAX((checkpoint->>'paid_source_reserved_at')::timestamptz) + %(interval)s,
                    MAX((checkpoint->>'source_cooldown_until')::timestamptz)
                ) AS ready_at
                FROM source_fetch_jobs
                WHERE job_kind='article' AND provider_slug=ANY(%(providers)s)
                  AND ((checkpoint->>'paid_source_reserved_at')::timestamptz >
                       statement_timestamp() - %(interval)s
                       OR (checkpoint->>'source_cooldown_until')::timestamptz > statement_timestamp())
                GROUP BY provider_slug
            ) deadlines
            WHERE ready_at > statement_timestamp()
        """, {"providers": providers, "interval": PAID_SOURCE_INTERVAL}).fetchone()
    remaining = row["remaining"]
    if remaining is None:
        return ARTICLE_ACTIVITY_POLL_SECONDS
    return max(0.01, min(ARTICLE_ACTIVITY_POLL_SECONDS, remaining.total_seconds()))


def _wait_for_article_activity(listener, completions, has_active_job, stop, *, timeout=ARTICLE_ACTIVITY_POLL_SECONDS):
    if has_active_job:
        watched = [completions] if listener is None else [completions, listener]
        ready, _, _ = select(watched, [], [], timeout)
        if completions in ready:
            completions.recv(4096)
        if listener not in ready:
            return
        timeout = 0
    elif listener is None:
        stop.wait(timeout)
        return
    with closing(listener.notifies(timeout=timeout, stop_after=1)) as notifications:
        next(notifications, None)


def _dispatch_parked_model(repo, lease, *, model_client, read_retained_object):
    from .article_lifecycle import run_article_job

    # The current source is already durable. The claimed rewrite can drain on
    # shutdown and this lane has no supplier access.
    run_article_job(
        repo, lease, registry={}, object_store=None, model_client=model_client,
        read_retained_object=read_retained_object,
    )


def _run_continuous_articles(repo, state, *, registry, object_store, model_client, stop):
    """Capture per supplier and resume admitted model work on a separate lane."""
    from .rollout_model_lane import claim_rollout_model_job

    in_flight = {}
    model_future = None
    listener = None
    completions, wake = socketpair()
    with (completions, wake, ThreadPoolExecutor(max_workers=2) as captures,
          ThreadPoolExecutor(max_workers=1) as rewrites):
        wake.setblocking(False)

        def completed(_):
            try:
                wake.send(b'\0')
            except BlockingIOError:
                pass  # An unread wake already tells the coordinator to recheck.

        try:
            while not stop.is_set():
                for provider, future in tuple(in_flight.items()):
                    if future.done():
                        future.result()
                        del in_flight[provider]
                if model_future is not None and model_future.done():
                    model_future.result()
                    model_future = None
                snapshot = state.read()
                now = database_now(repo)
                if len(snapshot['reservations']) == CONTINUOUS_MAX_RESERVATIONS:
                    # The final admitted capture is still allowed to finish.
                    for future in in_flight.values():
                        future.result()
                if not state.running(snapshot, now) or stop.is_set():
                    break
                available = [item for item in snapshot['providers'] if item not in in_flight]
                paid_overflow = not state.active(snapshot, now)
                # Subscribe before checking the durable queue to cover a racing enqueue.
                if available and listener is None:
                    listener = _subscribe_to_article_jobs(repo)
                elif not available and listener is not None:
                    listener.close()
                    listener = None
                if available:
                    reserved = _reserve_next_article(repo, state, providers=available, stop=stop,
                                                     paid_overflow=paid_overflow)
                    if reserved is not None:
                        job_id, provider = reserved
                        future = captures.submit(_dispatch_reserved_job, repo, state, job_id, worker_id=uuid4(),
                            provider=provider, registry=registry, object_store=object_store, model_client=None,
                            stop=stop, paid_overflow=paid_overflow)
                        in_flight[provider] = future
                        future.add_done_callback(completed)
                        continue
                if model_client is not None and model_future is None and not stop.is_set():
                    lease = claim_rollout_model_job(repo, snapshot, worker_id=uuid4())
                    if lease is not None:
                        model_future = rewrites.submit(
                            _dispatch_parked_model, repo, lease, model_client=model_client,
                            read_retained_object=getattr(object_store, "get_object", None),
                        )
                        model_future.add_done_callback(completed)
                if stop.is_set():
                    break
                has_active_job = bool(in_flight) or model_future is not None
                try:
                    timeout = (_paid_source_poll_timeout(repo, available) if paid_overflow and available
                               else ARTICLE_ACTIVITY_POLL_SECONDS)
                    _wait_for_article_activity(listener, completions, has_active_job, stop, timeout=timeout)
                except (DatabaseError, OSError):
                    if listener is not None:
                        listener.close()
                        listener = None
                    _wait_for_article_activity(None, completions, has_active_job, stop)
            # Keep the lifetime lock until every admitted job has unwound.
            for future in in_flight.values():
                future.result()
            if model_future is not None:
                model_future.result()
        except BaseException:
            stop.set()
            raise
        finally:
            if listener is not None:
                listener.close()


def run_new_article_worker(repo, state, *, registry, object_store, model_client, stop=None):
    stop = stop or Event()
    with state.worker_lock():
        if state.schema == 2:
            _run_continuous_articles(repo, state, registry=registry, object_store=object_store,
                                     model_client=model_client, stop=stop)
            return 0
        worker_id = uuid4()
        while not stop.is_set():
            snapshot = state.read()
            now = database_now(repo)
            if not state.running(snapshot, now) or stop.is_set():
                break
            dispatch_next(repo, state, worker_id=worker_id, registry=registry,
                          object_store=object_store, model_client=model_client, stop=stop)
            stop.wait(2)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    control = parser.add_mutually_exclusive_group()
    control.add_argument('--initialize', action='store_true')
    control.add_argument('--enable', action='store_true')
    control.add_argument('--disable', action='store_true')
    control.add_argument('--rebind-source-from', metavar='SHA', help='Move a stopped continuous rollout to the configured source SHA')
    parser.add_argument('--continuous', action='store_true', help='Require opt-in rolling-quota schema2 state')
    args = parser.parse_args(argv)
    try:
        source_sha = os.environ.get('AUTODATA_NEW_ARTICLE_SOURCE_SHA', '')
        with RolloutState(source_sha=source_sha, continuous=args.continuous) as state:
            if args.rebind_source_from is not None:
                state.rebind_source(args.rebind_source_from)
                return 0
            from .worker import ArticleRepository, ArticleObjectStore
            repo = ArticleRepository()
            if args.initialize:
                state.initialize(database_now(repo))
                return 0
            if args.enable or args.disable:
                state.set_enabled(args.enable)
                return 0
            try:
                model = configured_model()
            except (WorkerBlocked, ValueError):
                if not args.continuous:
                    raise
                model = None
                print('NEW_ARTICLE_MODEL_PAUSED', flush=True)
            from urllib.parse import urlsplit
            from .source_connector_client import source_connector_registry
            parsed = urlsplit(os.environ['AUTODATA_S3_ENDPOINT'])
            if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.path not in ('', '/'):
                raise WorkerBlocked('OBJECT_STORE_CONFIGURATION_INVALID')
            objects = ArticleObjectStore(endpoint=parsed.netloc, secure=parsed.scheme == 'https',
                access_key=os.environ['AUTODATA_S3_ACCESS_KEY'], secret_key=os.environ['AUTODATA_S3_SECRET_KEY'],
                bucket=os.environ['AUTODATA_SOURCE_BUCKET'])
            stop = Event()
            signal.signal(signal.SIGTERM, lambda *_: stop.set())
            signal.signal(signal.SIGINT, lambda *_: stop.set())
            return run_new_article_worker(repo, state, registry=source_connector_registry(include_defaults=False),
                object_store=objects, model_client=model, stop=stop)
    except Exception:
        # Credentials, provider response text and SQL are deliberately absent.
        print('NEW_ARTICLE_WORKER_BLOCKED', flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
