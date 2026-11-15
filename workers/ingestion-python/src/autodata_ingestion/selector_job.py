"""Owned, bounded initial selector work. This module has no persistence path."""
from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import sys
import time
from threading import RLock

MAX_OUTPUT = 4 * 1024 * 1024
STOP_REASONS = frozenset({'elapsed', 'request_limit', 'byte_limit', 'response_limit', 'row_limit',
                          'rate_limited', 'output_limit', 'child_failed', 'invalid_result'})


class SelectorJobStopped(Exception):
    def __init__(self, reason):
        self.reason = reason if reason in STOP_REASONS else 'child_failed'
        super().__init__(self.reason)


class SelectorJobControl:
    initial_selector_budget = True

    def __init__(self, deadline, *, clock=time.monotonic, sleep=time.sleep, dispatch_interval=6):
        self.deadline = deadline
        self.clock, self.sleep = clock, sleep
        self.dispatch_interval = dispatch_interval
        self.next_dispatch = 0.0
        self.requests = self.bytes = self.rows = 0

    def stop(self, reason):
        raise SelectorJobStopped(reason)

    def remaining(self):
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            self.stop('elapsed')
        return remaining

    def before_request(self):
        self.remaining()
        if self.requests >= 12:
            self.stop('request_limit')
        delay = max(0, self.next_dispatch - self.clock())
        if delay >= self.remaining():
            self.stop('elapsed')
        if delay:
            self.sleep(delay)
        remaining = self.remaining()
        self.requests += 1
        self.next_dispatch = self.clock() + self.dispatch_interval
        return remaining

    def consume_bytes(self, count):
        self.remaining()
        self.bytes += count
        if self.bytes > 4 * 1024 * 1024:
            self.stop('byte_limit')

    def consume_rows(self, count):
        self.remaining()
        self.rows += count
        if self.rows > 5000:
            self.stop('row_limit')


def scope_key(request):
    scope = request['scope']
    return (scope, int(request.get('year', 2000)) if scope != 'years' else 0,
            str(request.get('make', '')).strip().casefold() if scope == 'models' else '',
            str(request.get('region', 'US')).strip().upper())


class SelectorAdmission:
    """Process-global admission, independent of caller-controlled idempotency keys."""
    def __init__(self, *, clock=time.monotonic):
        self.clock, self.lock = clock, RLock()
        self.active = None
        self.next_attempt = 0.0
        self.cooldowns = {}

    def acquire(self, request):
        key = scope_key(request)
        with self.lock:
            now = self.clock()
            self.cooldowns = {k: v for k, v in self.cooldowns.items() if v > now}
            if self.active is not None or now < self.next_attempt or key in self.cooldowns:
                return None
            token = (object(), key)
            self.active = token
            return token

    def release(self, token, *, complete):
        with self.lock:
            if self.active is not token:
                raise RuntimeError('selector admission ownership mismatch')
            now = self.clock()
            self.next_attempt = now + 6
            if not complete:
                self.cooldowns[token[1]] = now + 30
            self.active = None


ADMISSION = SelectorAdmission()


def run_owned(request, absolute_deadline, *, command=None):
    """Bound IPC and reap only our process group, including resolver stalls.

    command is a Python-only fixture seam; it is never accepted from HTTP input.
    stderr is discarded rather than accumulating or exposing supplier diagnostics.
    """
    encoded = json.dumps({'request': request, 'deadline': absolute_deadline}, separators=(',', ':')).encode()
    if len(encoded) > 16384:
        raise SelectorJobStopped('invalid_result')
    if time.monotonic() >= absolute_deadline:
        raise SelectorJobStopped('elapsed')
    process = subprocess.Popen(command or [sys.executable, '-c', 'from autodata_ingestion.selector_job import _main; _main()'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, start_new_session=True)
    output = bytearray()
    try:
        # Both pipes are nonblocking; even a child that never reads stdin is bounded.
        os.set_blocking(process.stdin.fileno(), False)
        os.set_blocking(process.stdout.fileno(), False)
        offset = 0
        with selectors.DefaultSelector() as events:
            events.register(process.stdin, selectors.EVENT_WRITE, 'in')
            events.register(process.stdout, selectors.EVENT_READ, 'out')
            while events.get_map():
                remaining = absolute_deadline - time.monotonic()
                if remaining <= 0:
                    raise SelectorJobStopped('elapsed')
                for key, _ in events.select(remaining):
                    if key.data == 'in':
                        try:
                            offset += os.write(key.fd, encoded[offset:])
                        except BrokenPipeError:
                            offset = len(encoded)
                        if offset == len(encoded):
                            events.unregister(key.fileobj)
                            key.fileobj.close()
                    else:
                        block = os.read(key.fd, min(65536, MAX_OUTPUT + 1 - len(output)))
                        if not block:
                            events.unregister(key.fileobj)
                        output.extend(block)
                        if len(output) > MAX_OUTPUT:
                            raise SelectorJobStopped('output_limit')
        try:
            code = process.wait(timeout=max(.001, absolute_deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            raise SelectorJobStopped('elapsed') from None
        if code != 0:
            raise SelectorJobStopped('child_failed')
        if time.monotonic() >= absolute_deadline:
            raise SelectorJobStopped('elapsed')
        try:
            result = json.loads(output)
            if not isinstance(result, dict):
                raise ValueError()
            if set(result) == {'stopped'}:
                raise SelectorJobStopped(result['stopped'])
            if (set(result) != {'rows', 'complete', 'provenance', 'missing_scopes'}
                    or type(result['complete']) is not bool
                    or not isinstance(result['rows'], list) or len(result['rows']) > 5000
                    or not isinstance(result['provenance'], list)
                    or not isinstance(result['missing_scopes'], list)):
                raise ValueError()
            return result
        except (ValueError, TypeError):
            raise SelectorJobStopped('invalid_result') from None
    finally:
        # Kill even after a nominal exit: a descendant may still own a pipe/socket.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=2)
        if not process.stdin.closed:
            process.stdin.close()
        process.stdout.close()


def _main():
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (22, 22))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        envelope = json.loads(sys.stdin.buffer.read(16385))
        request = envelope['request']
        control = SelectorJobControl(float(envelope['deadline']))
        control.remaining()
        from .catalog_service import CatalogRequest, CacheFirstCatalogService, _configured_catalog_providers
        if request['scope'] not in {'years', 'makes', 'models'}:
            raise ValueError()
        model = CatalogRequest(int(request.get('year', 2000)), str(request.get('make', 'unknown')),
                               'unknown', str(request.get('region', 'US')), scope=request['scope'])
        resolved = CacheFirstCatalogService(cache_reader=lambda _: None,
                    providers=_configured_catalog_providers(deepening_control=control)).resolve(model)
        control.remaining()
        result = {'rows': list(resolved.rows), 'complete': resolved.complete,
                  'provenance': list(resolved.provenance), 'missing_scopes': list(resolved.missing_scopes)}
        encoded = json.dumps(result, separators=(',', ':')).encode()
        if len(encoded) > MAX_OUTPUT:
            raise SelectorJobStopped('output_limit')
        sys.stdout.buffer.write(encoded)
    except SelectorJobStopped as error:
        sys.stdout.write(json.dumps({'stopped': error.reason}))
    except Exception:
        sys.stdout.write('{"stopped":"child_failed"}')


if __name__ == '__main__':
    _main()
