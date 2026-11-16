#!/usr/bin/env python3
"""Offline-tested watchdog core; CLI deliberately has no live execution action.

Production supervision, source/runtime admission and actual-image fixtures require
an independent merged-source gate. Importing this module performs no I/O.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

URL = 'https://autodata.cars.tk/v1/catalog/years/2024/makes/acura/models/integra/configurations?region=US'
CHILD_ENV = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
EVENT = re.compile(
    r'catalog configuration budget scope_hash=([0-9a-f]{16}) '
    r'attempt=([0-9a-f]{16}) state=(started|finished) '
    r'stop_reason=(none|request_limit|elapsed|cancelled|rate_limited) '
    r'attempted_requests=([0-9]{1,2}) elapsed_ms=([0-9]{1,8})\Z'
)


class Refused(RuntimeError):
    """Fixed safe error; raw child/HTTP/exception output is never included."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def validate_manifest(value):
    if not isinstance(value, dict):
        raise Refused('invalid_manifest')
    if not isinstance(value.get('source_sha'), str) or not re.fullmatch('[0-9a-f]{40}', value['source_sha']):
        raise Refused('unresolved_product_source')
    if value.get('runtime_reviewed') is not True:
        raise Refused('runtime_review_required')
    if not isinstance(value.get('run_id'), str) or not re.fullmatch('[a-z0-9-]{8,64}', value['run_id']):
        raise Refused('invalid_run_id')
    if not isinstance(value.get('scope_hash'), str) or not re.fullmatch('[0-9a-f]{16}', value['scope_hash']):
        raise Refused('invalid_scope_hash')
    for name in ('candidate', 'predecessor'):
        target = value.get(name, {})
        if (not isinstance(target, dict) or not isinstance(target.get('id'), str)
                or not isinstance(target.get('fingerprint'), str)
                or not HEX64.fullmatch(target['id']) or not HEX64.fullmatch(target['fingerprint'])):
            raise Refused('invalid_container_identity')
    if value['candidate']['id'] == value['predecessor']['id']:
        raise Refused('distinct_predecessor_required')
    return hashlib.sha256(canonical(value)).hexdigest()


class Store:
    """Exclusive, file-then-directory fsync receipts under an existing private root.

    Physical filesystem/device/source admission is a future runtime integration
    prerequisite, not something this offline core infers from a pathname.
    """
    def __init__(self, root):
        self.root = Path(root)
        if self.root.is_symlink() or not self.root.is_dir():
            raise Refused('invalid_receipt_root')

    def path(self, name):
        if not re.fullmatch('[a-z][a-z0-9-]{0,63}', name):
            raise Refused('invalid_receipt_name')
        return self.root / (name + '.json')

    @contextmanager
    def lock(self):
        try:
            fd = os.open(self.root / "operation.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                yield
            finally:
                os.close(fd)
        except OSError:
            raise Refused("operation_busy_or_unknown") from None

    def exists(self, name):
        # lexists also treats a malicious symlink/incomplete marker as present.
        return os.path.lexists(self.path(name))

    def put(self, name, value):
        path = self.path(name)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as handle:
                handle.write(canonical(value) + b'\n')
                handle.flush()
                os.fsync(handle.fileno())
            directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except (OSError, ValueError, TypeError):
            # An incomplete marker intentionally blocks another attempt.
            raise Refused('receipt_write_refused') from None

    def get(self, name):
        try:
            fd = os.open(self.path(name), os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as handle:
                if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                    raise Refused('invalid_receipt')
                data = handle.read(65537)
            if len(data) > 65536:
                raise Refused('invalid_receipt')
            value = json.loads(data)
            if not isinstance(value, dict):
                raise Refused('invalid_receipt')
            return value
        except (OSError, ValueError):
            raise Refused('receipt_unavailable') from None


class FixedRunner:
    """Explicit daemon boundary; never invoke a shell or return raw failure text.

    Caller must first admit the physical, empty Docker config and socket identity.
    No CLI command in this file invokes this runner.
    """
    def __init__(self, docker_config):
        self.docker_config = str(docker_config)
        if not self.docker_config.startswith('/'):
            raise Refused('absolute_config_required')

    def docker(self, arguments, timeout=3):
        command = ['/usr/bin/docker', '--config', self.docker_config,
                   '--host', 'unix:///var/run/docker.sock', *arguments]
        try:
            result = subprocess.run(command, env=dict(CHILD_ENV), stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=timeout, check=True)
            if len(result.stdout) > 1024 * 1024:
                raise Refused('child_output_limit')
            return result.stdout
        except (OSError, subprocess.SubprocessError):
            raise Refused('child_operation_unknown') from None


def safe_events(lines):
    """Input is in-memory only; output contains fixed-field events, never raw logs.

    The runtime adapter must strip Docker framing/timestamps and bind log stream
    to the exact candidate and arm cursor. Malformed budget lines invalidate the
    entire batch rather than disappearing and allowing false disarm.
    """
    result = []
    for line in lines:
        if not isinstance(line, str) or len(line) > 1024:
            raise Refused('invalid_budget_log')
        match = EVENT.fullmatch(line)
        if not match:
            if 'catalog configuration budget ' in line:
                raise Refused('invalid_budget_log')
            continue
        scope, attempt, state, reason, count, elapsed = match.groups()
        count, elapsed = int(count), int(elapsed)
        if count > 12 or (state == 'started' and (reason != 'none' or count != 0)):
            raise Refused('invalid_budget_log')
        result.append({'scope_hash': scope, 'attempt': attempt, 'state': state,
                       'stop_reason': reason, 'attempted_requests': count, 'elapsed_ms': elapsed})
    return result


def finished(lines, scope_hash):
    try:
        events = [row for row in safe_events(lines) if row['scope_hash'] == scope_hash]
    except Refused:
        return False
    return (len(events) == 2 and events[0]['state'] == 'started'
            and events[1]['state'] == 'finished'
            and events[0]['attempt'] == events[1]['attempt']
            and events[1]['elapsed_ms'] >= events[0]['elapsed_ms'])


def serialized(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        with self.store.lock():
            return method(self, *args, **kwargs)
    return guarded


class Probe:
    """State machine with injected backend/clock; no subprocesses by itself.

    Backend inspect returns sanitized id/fingerprint/running/pid only; fingerprint
    commits to full reviewed image/Config/HostConfig/source. Backend stop means
    exact-ID intentional docker stop --time0 with a bounded result. Backend fetch
    is a single no-retry/no-redirect, proxy-free <=5s/1MiB request. Those adapters
    and independently supervised failure finalizer are intentionally NOT wired
    by this helper-only milestone.
    """
    def __init__(self, manifest, store, backend, clock=None, boot=None, supervisor_verifier=None, pause=None):
        self.manifest = manifest
        self.store = store
        self.backend = backend
        self.verify_supervisor = supervisor_verifier
        self.pause = pause or time.sleep
        self.clock = clock or (lambda: time.clock_gettime(time.CLOCK_BOOTTIME))
        self.boot = boot or (lambda: Path('/proc/sys/kernel/random/boot_id').read_text().strip())

    def identity(self, target, running=None):
        try:
            actual = self.backend.inspect(target['id'])
        except Exception:
            raise Refused('container_identity_unknown') from None
        if actual.get('id') != target['id'] or actual.get('fingerprint') != target['fingerprint']:
            raise Refused('container_identity_drift')
        if running is not None and actual.get('running') is not running:
            raise Refused('container_state_drift')
        if actual.get('running') is False and actual.get('pid') != 0:
            raise Refused('container_termination_unknown')
        if running is False and (actual.get('restarting') is not False or actual.get('status') not in ('created', 'exited', 'dead')):
            raise Refused('container_restart_state_unknown')
        return actual

    def stopped_proof(self, target):
        first = self.identity(target, running=False)
        self.pause(.4)
        second = self.identity(target, running=False)
        self.pause(.8)
        third = self.identity(target, running=False)
        if not first == second == third:
            raise Refused('container_post_stop_drift')
        return third

    @serialized
    def arm(self, supervisor):
        digest = validate_manifest(self.manifest)
        if (supervisor.get('verified') is not True or supervisor.get('boot_id') != self.boot()
                or supervisor.get('run_id') != self.manifest['run_id']
                or type(supervisor.get('pid')) is not int or supervisor['pid'] <= 0
                or type(supervisor.get('start_ticks')) is not int or supervisor['start_ticks'] <= 0):
            raise Refused('watchdog_not_verified')
        self.identity(self.manifest['candidate'], running=True)
        now = self.clock()
        fence_at = min(now+25, supervisor.get('service_deadline_boottime', now+25))
        if not now+24 <= fence_at <= now+25:
            raise Refused('watchdog_arm_window_insufficient')
        self.store.put('armed', {'manifest_hash': digest, 'boot_id': self.boot(),
                                'armed_at': now, 'fence_at': fence_at, 'supervisor': supervisor})

    def binding(self):
        digest = validate_manifest(self.manifest)
        arm = self.store.get('armed')
        if arm.get('manifest_hash') != digest or arm.get('boot_id') != self.boot():
            raise Refused('arm_binding_drift')
        return arm

    @serialized
    def dispatch_once(self):
        arm = self.binding()
        if self.store.exists('disarmed') or self.store.exists('fence-attempted'):
            raise Refused('attempt_closed')
        now = self.clock()
        if now < arm['armed_at'] or now - arm['armed_at'] > 1 or arm['fence_at'] - now < 24:
            raise Refused('arm_expired')
        self.identity(self.manifest['candidate'], running=True)
        try:
            alive = (callable(self.verify_supervisor)
                     and self.verify_supervisor(dict(arm['supervisor'])) is True)
        except Exception:
            alive = False
        if not alive:
            raise Refused('watchdog_liveness_not_proven')
        # Liveness verification itself may have consumed the admission window.
        now = self.clock()
        if now < arm['armed_at'] or now - arm['armed_at'] > 1 or arm['fence_at'] - now < 24:
            raise Refused('arm_expired')
        self.store.put('attempted', {'manifest_hash': arm['manifest_hash'], 'at': now})
        try:
            result = self.backend.fetch(URL)
        except Exception:
            self.store.put('response', {'outcome': 'unknown'})
            raise Refused('request_outcome_unknown') from None
        # Never persist a raw body, URL, backend exception or arbitrary extra keys.
        if (type(result.get('status')) is not int or not 100 <= result['status'] <= 599
                or type(result.get('bytes')) is not int or not 0 <= result['bytes'] <= 1048576
                or not HEX64.fullmatch(result.get('sha256', ''))):
            self.store.put('response', {'outcome': 'invalid'})
            raise Refused('invalid_response_receipt')
        safe = {key: result[key] for key in ('status', 'bytes', 'sha256')}
        self.store.put('response', safe)
        return safe

    def postcheck(self, target):
        self.identity(target, running=True)
        try:
            result = self.backend.postcheck(target['id'])
        except Exception:
            raise Refused('postcheck_unknown') from None
        if (result.get('protected_unchanged') is not True
                or result.get('catalog_baseline_preserved') is not True
                or result.get('healthy') is not True or result.get('purchase_enabled') is not False):
            raise Refused('postcheck_failed')
        return {key: result[key] for key in ('protected_unchanged', 'catalog_baseline_preserved', 'healthy', 'purchase_enabled')}

    def disarm_proven(self, arm):
        try:
            receipt = self.store.get('disarmed')
            if receipt.get('manifest_hash') != arm['manifest_hash']:
                return False
            reason = receipt.get('reason')
            if reason == 'unused_arm':
                return not self.store.exists('attempted')
            name = {'worker_finished': 'worker-finished', 'fenced_restarted': 'provider-restarted'}.get(reason)
            if name is None:
                return False
            proof = self.store.get(name)
            if proof.get('manifest_hash') != arm['manifest_hash']:
                return False
            if hashlib.sha256(canonical(proof)).hexdigest() != receipt.get('proof_hash'):
                return False
            if reason == 'fenced_restarted':
                return (proof.get('id') == self.manifest['candidate']['id']
                        and proof.get('fingerprint') == self.manifest['candidate']['fingerprint']
                        and proof.get('running') is True and self.store.exists('fenced'))
            rows = proof.get('events', [])
            lines = ['catalog configuration budget scope_hash={scope_hash} attempt={attempt} state={state} stop_reason={stop_reason} attempted_requests={attempted_requests} elapsed_ms={elapsed_ms}'.format(**row) for row in rows]
            return finished(lines, self.manifest['scope_hash'])
        except (Refused, KeyError, TypeError, ValueError):
            return False

    @serialized
    def finish(self, lines):
        arm = self.binding()
        if self.store.exists('fence-attempted'):
            raise Refused('fence_already_started')
        attempt = self.store.get('attempted')
        if attempt.get('manifest_hash') != arm['manifest_hash']:
            raise Refused('attempt_binding_drift')
        if not finished(lines, self.manifest['scope_hash']):
            raise Refused('worker_finish_not_proven')
        self.identity(self.manifest['candidate'], running=True)
        events = [row for row in safe_events(lines) if row['scope_hash'] == self.manifest['scope_hash']]
        proof = {'manifest_hash': arm['manifest_hash'], 'events': events}
        self.store.put('worker-finished', proof)
        # Provider-return proof is durable before disarm; slow SQL acceptance is
        # a separate phase and cannot hold up the external deadline fence.
        self.store.put('disarmed', {'reason': 'worker_finished', 'manifest_hash': arm['manifest_hash'], 'proof_hash': hashlib.sha256(canonical(proof)).hexdigest()})

    @serialized
    def verify_outcome(self):
        arm = self.binding()
        if not self.store.exists('attempted') or not self.disarm_proven(arm):
            raise Refused('provider_execution_end_unproven')
        check = self.postcheck(self.manifest['candidate'])
        self.store.put('verified', {'manifest_hash': arm['manifest_hash'], 'postcheck': check})

    @serialized
    def recover(self, *, start_seen):
        arm = self.binding()
        if self.store.exists('disarmed'):
            if self.disarm_proven(arm):
                return
            # A malformed receipt cannot cancel the fence.
            start_seen = False
        if not self.store.exists('attempted'):
            self.store.put('disarmed', {'reason': 'unused_arm', 'manifest_hash': arm['manifest_hash']})
            return
        self.store.put('fence-attempted', {'manifest_hash': arm['manifest_hash'], 'at': self.clock()})
        target = self.manifest['candidate']
        self.identity(target)
        try:
            # Intentional stop inhibits unless-stopped auto-restart, even when
            # initially exited/created/restarting. A timeout is never success.
            self.backend.stop(target['id'])
            self.stopped_proof(target)
        except Exception:
            self.store.put('fence-refused', {'reason': 'intentional_stop_unproven'})
            raise Refused('stop_outcome_unknown_hold') from None
        self.store.put('fenced', {'id': target['id']})
        if start_seen is not True:
            raise Refused('worker_start_unknown_hold_stopped')
        try:
            self.backend.start(target['id'])
        except Exception:
            raise Refused('restart_unknown') from None
        restarted = self.identity(target, running=True)
        proof = {'manifest_hash': arm['manifest_hash'], 'id': restarted['id'], 'fingerprint': restarted['fingerprint'], 'running': True}
        self.store.put('provider-restarted', proof)
        self.store.put('disarmed', {'reason': 'fenced_restarted', 'manifest_hash': arm['manifest_hash'], 'proof_hash': hashlib.sha256(canonical(proof)).hexdigest()})

    @serialized
    def rollback(self):
        validate_manifest(self.manifest)
        self.store.put('rollback-attempted', {'source_sha': self.manifest['source_sha']})
        target, old = self.manifest['candidate'], self.manifest['predecessor']
        try:
            self.identity(old)
        except Refused:
            self.store.put('rollback-refused', {'reason': 'predecessor_unverified', 'candidate_termination_proven': False})
            raise
        try:
            self.identity(target)
            self.backend.stop(target['id'])
            self.stopped_proof(target)
        except Exception:
            self.store.put('rollback-refused', {'reason': 'candidate_intentional_stop_unproven', 'candidate_termination_proven': False})
            raise Refused('rollback_hold_candidate_termination_unknown') from None
        self.store.put('rollback-fenced', {'id': target['id'], 'pid': 0, 'intentional_stop_confirmed': True})
        try:
            predecessor = self.identity(old)
            if not predecessor['running']:
                self.backend.start(old['id'])
            check = self.postcheck(old)
            self.store.put('rollback-restarted', {'id': old['id'], 'already_running': predecessor['running'], 'postcheck': check})
        except Exception:
            self.store.put('rollback-refused', {'reason': 'predecessor_recovery_unknown', 'candidate_termination_proven': True})
            raise Refused('rollback_recovery_unknown') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['validate'])
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    try:
        digest = validate_manifest(json.loads(args.manifest.read_text()))
    except (OSError, ValueError, Refused):
        parser.exit(2, 'manifest_refused; live execution unavailable\n')
    print(json.dumps({'manifest_hash': digest, 'live_execution_available': False}))


if __name__ == '__main__':
    main()
