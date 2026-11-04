"""Bounded capture and cancellation of one owned Linux process group.

Callers must separately authenticate commands and provide exclusive child-reap
ownership and suitable containment. A process group is not a security boundary.
Spawn, OS scheduling and uninterruptible kernel tasks have no absolute Python
latency guarantee. An unconfirmed cleanup stops the ledger conservatively.
"""
from dataclasses import dataclass, field
import os
import re
import selectors
import signal
import subprocess
import sys
import threading
import time

MiB = 1024 * 1024
_COMMAND_BYTES = 16 * MiB
_CHUNK = 64 * 1024
_POLL_NS = 50_000_000
_SECOND = 1_000_000_000


@dataclass(frozen=True, slots=True)
class RunRequest:
    command_id: str
    executable: str
    argv: tuple[str, ...]
    cwd: str
    env: tuple[tuple[str, str], ...]
    kind: str


@dataclass(frozen=True, slots=True)
class RunResult:
    status: str
    returncode: int | None
    stdout: bytes
    stderr: bytes
    captured_bytes: int
    cleanup: str
    elapsed_ns: int
    primary_fault: str | None


class _Ledger:
    def __init__(self, deadline, maximum):
        self.deadline = deadline
        self.maximum = maximum
        self.remaining = maximum
        self.stopped = False
        self.active = False
        self.lock = threading.Lock()


@dataclass(frozen=True, slots=True)
class CaptureBudget:
    outer_deadline_ns: int
    max_bytes: int = 128 * MiB
    _state: _Ledger = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        now = time.monotonic_ns()
        if type(self.outer_deadline_ns) is not int or type(self.max_bytes) is not int:
            raise TypeError('invalid_budget')
        if not now < self.outer_deadline_ns <= now + 1800 * _SECOND:
            raise ValueError('invalid_budget')
        if not 1 <= self.max_bytes <= 128 * MiB:
            raise ValueError('invalid_budget')
        object.__setattr__(self, '_state', _Ledger(self.outer_deadline_ns, self.max_bytes))

    @property
    def remaining_bytes(self):
        with self._state.lock:
            return self._state.remaining

    def __copy__(self):
        raise TypeError('noncopyable_budget')

    def __deepcopy__(self, memo):
        raise TypeError('noncopyable_budget')


def _text(value, *, empty=False):
    return type(value) is str and (empty or bool(value)) and '\x00' not in value


def _valid_request(request):
    if type(request) is not RunRequest:
        return False
    try:
        if not _text(request.command_id) or re.fullmatch(r'[a-z][a-z0-9_]{0,63}', request.command_id) is None:
            return False
        if request.kind not in ('ordinary', 'source') or type(request.kind) is not str:
            return False
        if not all(_text(p) and os.path.isabs(p) for p in (request.executable, request.cwd)):
            return False
        argv, env = request.argv, request.env
        if type(argv) is not tuple or not 1 <= len(argv) <= 128:
            return False
        if not all(_text(a) for a in argv) or argv[0] != request.executable:
            return False
        if sum(len(a.encode('utf-8')) for a in argv) > 64 * 1024:
            return False
        if type(env) is not tuple or len(env) > 64:
            return False
        names = set()
        size = 0
        for pair in env:
            if type(pair) is not tuple or len(pair) != 2:
                return False
            name, value = pair
            if not _text(name) or re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name) is None:
                return False
            if name in names or not _text(value, empty=True):
                return False
            names.add(name)
            size += len(name.encode('utf-8')) + len(value.encode('utf-8'))
        return size <= 64 * 1024
    except (AttributeError, TypeError, UnicodeError):
        return False


def _valid_budget(budget):
    if type(budget) is not CaptureBudget:
        return False
    try:
        state = budget._state
        return (type(state) is _Ledger and type(budget.outer_deadline_ns) is int
                and type(budget.max_bytes) is int
                and budget.outer_deadline_ns == state.deadline
                and budget.max_bytes == state.maximum
                and type(state.remaining) is int and 0 <= state.remaining <= state.maximum)
    except AttributeError:
        return False


def _supported():
    return (sys.platform == 'linux' and os.name == 'posix'
            and all(hasattr(os, name) for name in ('waitid', 'P_PID', 'WNOWAIT', 'WEXITED', 'WNOHANG', 'killpg', 'set_blocking'))
            and signal.getsignal(signal.SIGCHLD) == signal.SIG_DFL)


class _Backend:
    """Private syscall seam for synthetic fault tests; real time is never injected."""
    def spawn(self, request):
        return subprocess.Popen(request.argv, executable=request.executable,
                                cwd=request.cwd, env=dict(request.env), shell=False,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, close_fds=True,
                                start_new_session=True, bufsize=0)

    def selector(self):
        return selectors.DefaultSelector()

    def nonblocking(self, pipe):
        os.set_blocking(pipe.fileno(), False)

    def read(self, pipe, count):
        return os.read(pipe.fileno(), count)

    def observe(self, proc):
        return os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)

    def reap(self, proc):
        pid, status = os.waitpid(proc.pid, os.WNOHANG)
        if pid == proc.pid:
            proc.returncode = os.waitstatus_to_exitcode(status)
            return proc.returncode
        return None

    def send(self, proc, sig):
        os.killpg(proc.pid, sig)


def _returncode(info):
    if info is None:
        return None
    return info.si_status if info.si_code == os.CLD_EXITED else -info.si_status


def _signal_owned(backend, proc, sig):
    try:
        backend.send(proc, sig)
        return 'sent'
    except ProcessLookupError:
        return 'missing'
    except OSError:
        return 'failed'


def _observe(backend, proc):
    try:
        return backend.observe(proc), False
    except InterruptedError:
        return None, False
    except (OSError, ValueError):
        return None, True


def _cleanup(backend, proc, outer_deadline, pipes_eof):
    """Signal before reap; all stages share one absolute cleanup allowance."""
    start = time.monotonic_ns()
    end = min(start + 4 * _SECOND, outer_deadline)
    term_end = min(start + 2 * _SECOND, end)
    signal_failed = _signal_owned(backend, proc, signal.SIGTERM) == 'failed'
    info = None
    observe_failed = False
    while time.monotonic_ns() < term_end:
        info, failed = _observe(backend, proc)
        observe_failed |= failed
        if info is not None or failed:
            break
        time.sleep(min(_POLL_NS, max(0, term_end-time.monotonic_ns())) / _SECOND)
    # Closed local read ends do not establish descendant pipe EOF. Preserve the
    # unreaped leader until KILL when pipe holders may have survived TERM.
    if info is None or not pipes_eof:
        signal_failed |= _signal_owned(backend, proc, signal.SIGKILL) == 'failed'
    code = _returncode(info)
    while True:
        info, failed = _observe(backend, proc)
        observe_failed |= failed
        if info is not None:
            code = _returncode(info)
        try:
            reaped = backend.reap(proc)
        except InterruptedError:
            reaped = None
        except (OSError, ValueError):
            return code, False
        if reaped is not None:
            return reaped, not (signal_failed or observe_failed)
        if time.monotonic_ns() >= end:
            return code, False
        time.sleep(min(_POLL_NS, max(0, end-time.monotonic_ns())) / _SECOND)


def run(request: RunRequest, budget: CaptureBudget, cancel: threading.Event) -> RunResult:
    """Capture opaque bytes; completed means direct-child/pipe lifecycle only."""
    return _run(request, budget, cancel, _Backend())


def _run(request, budget, cancel, backend):
    start = time.monotonic_ns()

    def result(status, code=None, out=b'', err=b'', cleanup='not_started', fault=None):
        return RunResult(status, code, out, err, len(out)+len(err), cleanup,
                         max(0, time.monotonic_ns()-start), fault)

    if not _valid_budget(budget) or not _valid_request(request) or type(cancel) is not threading.Event:
        return result('invalid_request')
    if not _supported():
        return result('unsupported_platform')
    state = budget._state
    with state.lock:
        if state.active:
            return result('busy')
        state.active = True
    proc = None
    selector = None
    pipes = []
    streams = [bytearray(), bytearray()]
    open_pipes = set()
    fault = None
    code = None
    reaped = False
    closed = True
    try:
        with state.lock:
            stopped = state.stopped
        if stopped:
            return result('budget_stopped')
        if cancel.is_set():
            fault = 'cancelled'
        elif time.monotonic_ns() >= state.deadline:
            fault = 'deadline'
        if fault:
            with state.lock:
                state.stopped = True
            return result(fault, fault=fault)
        deadline = min(start + (10 if request.kind == 'ordinary' else 30) * _SECOND, state.deadline)
        try:
            proc = backend.spawn(request)
        except (OSError, ValueError, subprocess.SubprocessError):
            fault = 'spawn_failed'
        if proc is not None:
            # Retain both handles before any fallible selector setup.
            pipes = [proc.stdout, proc.stderr]
            open_pipes = set(pipes)
            selector = backend.selector()
            for index, pipe in enumerate(pipes):
                backend.nonblocking(pipe)
                selector.register(pipe, selectors.EVENT_READ, index)
            while fault is None:
                if cancel.is_set():
                    fault = 'cancelled'
                    break
                now = time.monotonic_ns()
                if now >= deadline:
                    fault = 'deadline'
                    break
                info, failed = _observe(backend, proc)
                if failed:
                    fault = 'capture_failed'
                    break
                if info is not None:
                    code = _returncode(info)
                    if not open_pipes:
                        # No future group signal after this successful branch.
                        code = backend.reap(proc)
                        if code is None:
                            fault = 'capture_failed'
                        else:
                            reaped = True
                        break
                try:
                    events = selector.select(min(_POLL_NS, deadline-now) / _SECOND)
                except InterruptedError:
                    continue
                # A single read per ready stream keeps both descriptors fair.
                for key, _ in events:
                    if cancel.is_set():
                        fault = 'cancelled'
                        break
                    if time.monotonic_ns() >= deadline:
                        fault = 'deadline'
                        break
                    retained = len(streams[0]) + len(streams[1])
                    with state.lock:
                        allowance = min(_COMMAND_BYTES-retained, state.remaining)
                    try:
                        data = backend.read(key.fileobj, min(_CHUNK, allowance+1))
                    except (BlockingIOError, InterruptedError):
                        continue
                    if not data:
                        selector.unregister(key.fileobj)
                        open_pipes.remove(key.fileobj)
                        key.fileobj.close()
                        continue
                    count = min(len(data), allowance)
                    with state.lock:
                        state.remaining -= count
                    streams[key.data].extend(data[:count])
                    if len(data) > allowance:
                        fault = 'output_limit'
                        break
    except Exception:
        # Exceptions are deliberately never formatted or copied to the result.
        if fault is None:
            fault = 'capture_failed'
    finally:
        # Close before termination; never drain unbounded data after a fault.
        for pipe in pipes:
            try:
                pipe.close()
            except OSError:
                closed = False
        if selector is not None:
            try:
                selector.close()
            except OSError:
                closed = False
        if proc is not None and not reaped:
            try:
                code, reaped = _cleanup(backend, proc, state.deadline, not open_pipes)
            except Exception:
                reaped = False
        if fault is not None or (proc is not None and (not reaped or not closed)):
            with state.lock:
                state.stopped = True
        with state.lock:
            state.active = False
    out, err = bytes(streams[0]), bytes(streams[1])
    if proc is not None and (not reaped or not closed):
        return result('cleanup_unconfirmed', code, out, err, 'unconfirmed', fault)
    return result(fault or 'completed', code, out, err,
                  'reaped' if proc is not None else 'not_started', fault)
