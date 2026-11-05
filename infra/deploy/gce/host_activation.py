#!/usr/bin/python3 -I
"""Fixed local release lifecycle; provisioning and credentials remain external."""
from contextlib import ExitStack
import fcntl
import importlib.util
import json
import os
import re
import selectors
import signal
import stat
import subprocess
import time
import uuid

OPT = '/opt/autodata'
RELEASES = OPT + '/releases'
DATA = '/var/lib/autodata'
RUN = '/run/autodata'
HELPER = OPT + '/bin/runtime-check.py'
DOCKER = ['/usr/bin/docker', '--host', 'unix:///var/run/docker.sock']
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C', 'LC_ALL': 'C', 'HOME': '/nonexistent'}
MAXIMUM = 1048576
SHA = r'[0-9a-f]{40}'
MAINTENANCE = b'respond "Maintenance" 503\n'
APPS = ('api', 'ingestion-http', 'article-worker', 'payment-reconciler')
STATEFUL = ('postgres', 'nats', 'minio')


class ActivationError(ValueError):
    def __init__(self): super().__init__('local activation failed')


def require(value):
    if not value: raise ActivationError()


def bounded_command(argv, timeout=5, deadline=None, maximum=MAXIMUM, input_data=None):
    """Streaming bounded capture; exceptions never contain command output.

    Start a session so timeout/cancellation also kills CLI descendants. Docker
    daemon operations have their own bounded stop/reload timeouts as well.
    """
    end = min(time.monotonic() + timeout, deadline if deadline is not None else float('inf'))
    if time.monotonic() >= end: raise subprocess.TimeoutExpired('local operation', timeout)
    require(input_data is None or type(input_data) is bytes and len(input_data) <= maximum)
    process = subprocess.Popen(argv, stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd='/', env=dict(ENV), start_new_session=True)
    selector = selectors.DefaultSelector()
    output = bytearray()
    retained = 0
    try:
        for pipe in (process.stdout, process.stderr):
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ)
        if input_data is not None:
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE)
        pending = memoryview(input_data or b'')
        while selector.get_map():
            remaining = end - time.monotonic()
            if remaining <= 0: raise subprocess.TimeoutExpired('local operation', timeout)
            events = selector.select(remaining)
            if not events: raise subprocess.TimeoutExpired('local operation', timeout)
            for key, _ in events:
                pipe = key.fileobj
                if pipe is process.stdin:
                    if pending:
                        count = os.write(pipe.fileno(), pending[:4096]); pending = pending[count:]
                    if not pending:
                        selector.unregister(pipe); pipe.close()
                    continue
                chunk = os.read(pipe.fileno(), min(4096, maximum + 1 - retained))
                if not chunk:
                    selector.unregister(pipe); continue
                retained += len(chunk)
                require(retained <= maximum)
                if pipe is process.stdout: output.extend(chunk)
        remaining = end - time.monotonic()
        if remaining <= 0: raise subprocess.TimeoutExpired('local operation', timeout)
        require(process.wait(timeout=remaining) == 0)
        return bytes(output)
    finally:
        # Even a reaped parent can leave children holding a pipe open.
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        finally:
            selector.close()
            for pipe in (process.stdin, process.stdout, process.stderr):
                if pipe is not None: pipe.close()
            process.wait(timeout=1)


def ident(value): return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid)


class Pins:
    """Pin every ancestor descriptor and reject replaced/untrusted entries."""
    def __init__(self): self.stack = ExitStack(); self.dirs = {}; self.files = []
    def __enter__(self): return self
    def __exit__(self, *args): return self.stack.__exit__(*args)
    def directory(self, path, mode=None, create=False):
        require(path.startswith('/'))
        if path in self.dirs:
            fd = self.dirs[path][0]
        else:
            if path == '/':
                parent, name = None, '/'
            else:
                prefix, name = path.rsplit('/', 1)
                parent = self.directory(prefix or '/')
                if create:
                    try: os.mkdir(name, 0o700, dir_fd=parent); os.fsync(parent)
                    except FileExistsError: pass
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
            self.stack.callback(os.close, fd)
            self.dirs[path] = (fd, parent, name, ident(os.fstat(fd)))
        value = os.fstat(fd)
        require(stat.S_ISDIR(value.st_mode) and value.st_uid == 0 and value.st_gid == 0 and not value.st_mode & 0o022)
        if mode is not None: require(stat.S_IMODE(value.st_mode) == mode)
        return fd
    def read(self, parent, name, mode=0o600, maximum=MAXIMUM, empty=False):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_uid == 0 and before.st_gid == 0 and before.st_nlink == 1)
            require(stat.S_IMODE(before.st_mode) == mode and (0 if empty else 1) <= before.st_size <= maximum)
            data = bytearray()
            while len(data) <= maximum:
                chunk = os.read(fd, min(65536, maximum + 1 - len(data)))
                if not chunk: break
                data.extend(chunk)
            require(len(data) == before.st_size and before == os.fstat(fd))
            require(ident(os.stat(name, dir_fd=parent, follow_symlinks=False)) == ident(before))
            return bytes(data)
        finally: os.close(fd)
    def pin(self, parent, name, mode=0o600):
        data = self.read(parent, name, mode)
        self.files.append((parent, name, mode, ident(os.stat(name, dir_fd=parent, follow_symlinks=False)), data))
        return data
    def recheck(self):
        for fd, parent, name, original in self.dirs.values():
            require(ident(os.fstat(fd)) == original)
            if parent is not None: require(ident(os.stat(name, dir_fd=parent, follow_symlinks=False)) == original)
        for parent, name, mode, original, data in self.files:
            require(ident(os.stat(name, dir_fd=parent, follow_symlinks=False)) == original and self.read(parent, name, mode) == data)


def materialize(pins, directory, name, data):
    require(type(data) is bytes and 0 < len(data) <= MAXIMUM and b'${' not in data)
    try:
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory)
    except FileExistsError:
        require(pins.read(directory, name) == data)
    else:
        try:
            os.fchmod(fd, 0o600)
            offset = 0
            while offset < len(data): offset += os.write(fd, data[offset:])
            os.fsync(fd)
        finally: os.close(fd)
        os.fsync(directory)
    require(pins.pin(directory, name) == data)
    pins.recheck()


def selection(pins):
    directory = pins.directory(OPT)
    try: value = os.stat('current', dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError: return None
    require(stat.S_ISLNK(value.st_mode) and value.st_uid == 0 and value.st_gid == 0)
    target = os.readlink('current', dir_fd=directory)
    require(re.fullmatch(re.escape(RELEASES) + '/' + SHA, target) is not None)
    return (target.rsplit('/', 1)[1], ident(value))


def select(pins, source_sha, previous):
    require(re.fullmatch(SHA, source_sha) is not None and selection(pins) == previous)
    pins.recheck()
    directory = pins.directory(OPT)
    name = '.current-' + uuid.uuid4().hex
    os.symlink(RELEASES + '/' + source_sha, name, dir_fd=directory)
    try:
        require(selection(pins) == previous)
        os.replace(name, 'current', src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    finally:
        try: os.unlink(name, dir_fd=directory)
        except FileNotFoundError: pass
