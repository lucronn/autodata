"""Bounded Codex 0.162.1 stdio transport and pure configured-profile replay.

No upstream served/billed service tier is observed by this protocol. Real launch
requires the coordinator's protected disposable-container attestation.
"""
from __future__ import annotations

import hashlib
import json
import os
import selectors
import signal
import stat
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

VERSION = "codex-cli 0.162.1"
BOUNDARY = Path("/run/autodata/runtime-boundary.json")
MAX_LINE = 1024 * 1024
MAX_STREAM = 4 * 1024 * 1024
MAX_CAPTURE = 12 * 1024 * 1024
MAX_FRAMES = 10_000
PROFILE = {"model": "gpt-6.1-sol", "reasoning_effort": "medium", "service_tier": "fast"}
INFO = frozenset(("thread/status/changed", "thread/name/updated", "thread/tokenUsage/updated",
                  "turn/diff/updated", "turn/plan/updated", "item/started", "item/agentMessage/delta",
                  "item/commandExecution/outputDelta", "item/commandExecution/terminalInteraction",
                  "item/fileChange/outputDelta", "item/fileChange/patchUpdated", "item/reasoning/summaryTextDelta",
                  "item/reasoning/summaryPartAdded", "item/reasoning/textDelta", "account/rateLimits/updated"))
ITEMS = frozenset(("userMessage", "agentMessage", "reasoning", "commandExecution", "fileChange", "plan"))


class ProtocolError(ValueError):
    """The runtime evidence cannot establish the exact configured profile."""


def _require(condition, message):
    if not condition:
        raise ProtocolError(message)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def strict_json(raw):
    return json.loads(raw, object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ProtocolError("nonfinite JSON")))


def _wire(frame):
    return json.dumps(frame, ensure_ascii=False, separators=(",", ":")) + "\n"


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def context(expected):
    result = {k: v for k, v in expected.items() if k not in ("prompt", "schema")}
    result["prompt_sha256"] = hashlib.sha256(expected["prompt"].encode()).hexdigest()
    result["schema_sha256"] = hashlib.sha256(_canonical(expected["schema"])).hexdigest()
    return result


def provider_argv():
    return ["codex", "app-server", "--stdio", "--strict-config", "-c", 'model="gpt-6.1-sol"',
            "-c", 'model_reasoning_effort="medium"', "-c", 'service_tier="fast"',
            "-c", "features.fast_mode=true"]


class _Session:
    def __init__(self, expected):
        self.expected = expected
        self.ready = []
        self.pending = {}
        self.next_id = 1
        self.cursor = None
        self.cursors = set()
        self.models = []
        self.pages = 0
        self.thread = None
        self.turn = None
        self.thread_events = []
        self.scopes = []
        self.completed = []
        self.answers = {}
        self.completed_items = set()
        self.finished = False
        self.request("initialize", {"clientInfo": {"name": "autodata-r0", "title": "AutoData R0", "version": "1"},
                                    "capabilities": {"experimentalApi": False, "optOutNotificationMethods": []}})

    def request(self, method, params):
        self.ready.append({"id": self.next_id, "method": method, "params": params})
        self.next_id += 1

    def feed(self, direction, frame):
        _require(type(frame) is dict, "protocol frame must be object")
        if direction == "client":
            _require("id" not in frame or type(frame["id"]) is int, "client id must be integer")
            _require(bool(self.ready) and frame == self.ready[0], "unexpected/out-of-order client request")
            want = self.ready.pop(0)
            if "id" in want:
                self.pending[want["id"]] = want["method"]
            return
        _require(direction == "server", "invalid protocol direction")
        if "id" in frame:
            _require("method" not in frame, "unexpected server request")
            rid = frame["id"]
            _require(type(rid) is int and rid in self.pending, "unknown/duplicate response id")
            method = self.pending.pop(rid)
            _require("error" not in frame and type(frame.get("result")) is dict, "server request failed")
            self.response(method, frame["result"])
            return
        method = frame.get("method")
        params = frame.get("params")
        _require(type(method) is str and type(params) is dict, "malformed notification")
        for key in ("threadId", "turnId"):
            if key in params:
                _require(type(params[key]) is str and params[key], "invalid notification identity")
        if method == "thread/started":
            _require(self.thread is not None or "thread/start" in self.pending.values(), "thread event before request")
            self.thread_events.append(params["thread"]["id"])
            _require(len(self.thread_events) == 1, "second thread event")
        elif method in ("turn/started", "turn/completed"):
            _require(self.turn is not None or "turn/start" in self.pending.values(), "turn event before request")
            turn = params["turn"]
            _require(type(params["threadId"]) is str and type(turn.get("id")) is str and turn["id"], "invalid turn identity")
            self.scopes.append((params["threadId"], turn["id"]))
            _require(turn.get("status") in ("inProgress", "completed"), "turn failed/interrupted")
            if method == "turn/completed":
                _require(turn.get("status") == "completed" and "error" in turn and turn["error"] is None,
                         "turn did not complete cleanly")
                self.completed.append(turn)
                _require(len(self.completed) == 1, "duplicate turn completion")
        elif method in INFO or method == "item/completed":
            if method.startswith(("item/", "turn/")):
                _require(type(params.get("threadId")) is str and type(params.get("turnId")) is str, "missing item/turn scope")
            self.scopes.append((params.get("threadId"), params.get("turnId")))
            if method in ("item/started", "item/completed"):
                item = params["item"]
                _require(item.get("type") in ITEMS and type(item.get("id")) is str, "unsupported item")
                if item["type"] == "userMessage":
                    _require(item.get("content") == self.input(), "conflicting user message")
                if method == "item/completed":
                    _require(item["id"] not in self.completed_items, "duplicate completed item")
                    self.completed_items.add(item["id"])
                    if item["type"] == "agentMessage":
                        _require(type(item.get("text")) is str, "missing agent text")
                        self.answers[item["id"]] = item
        else:
            raise ProtocolError("unsupported/error notification: " + str(method))
        self.check_scope()

    def check_scope(self):
        if self.thread is not None:
            _require(all(t == self.thread for t in self.thread_events), "thread identity mismatch")
            _require(all(t in (None, self.thread) for t, _ in self.scopes), "foreign thread")
        if self.turn is not None:
            _require(all(t in (None, self.turn) for _, t in self.scopes), "foreign turn")

    def input(self):
        return [{"type": "text", "text": self.expected["prompt"], "text_elements": []}]

    def response(self, method, result):
        e = self.expected
        if method == "initialize":
            _require(all(type(result.get(k)) is str and result[k] for k in ("userAgent", "codexHome", "platformFamily", "platformOs")), "invalid initialize result")
            _require(result["codexHome"] == e["codex_home"], "wrong disposable Codex home")
            self.ready.append({"method": "initialized"})
            self.request("model/list", {"cursor": None, "limit": 100, "includeHidden": True})
        elif method == "model/list":
            self.pages += 1
            data = result.get("data")
            _require(type(data) is list and len(data) <= 100 and self.pages <= 16 and "nextCursor" in result, "unbounded catalog")
            self.models.extend(data)
            _require(len(self.models) <= 1600 and all(type(m) is dict and type(m.get("id")) is str and m["id"] for m in self.models), "invalid catalog model")
            _require(len({m["id"] for m in self.models}) == len(self.models), "duplicate catalog id")
            cursor = result["nextCursor"]
            if cursor is not None:
                _require(type(cursor) is str and cursor and cursor not in self.cursors and self.pages < 16, "unproven/repeated catalog cursor")
                self.cursors.add(cursor)
                self.request("model/list", {"cursor": cursor, "limit": 100, "includeHidden": True})
                return
            matches = [m for m in self.models if m.get("model") == "gpt-6.1-sol"]
            _require(len(matches) == 1, "exact requested model unavailable/ambiguous")
            m = matches[0]
            _require(type(m.get("supportedReasoningEfforts")) is list and any(type(x) is dict and x.get("reasoningEffort") == "medium" for x in m["supportedReasoningEfforts"]), "medium effort unavailable")
            _require(type(m.get("serviceTiers")) is list and any(type(x) is dict and x.get("id") == "priority" for x in m["serviceTiers"]), "priority tier unavailable")
            self.request("thread/start", {"model": "gpt-6.1-sol", "modelProvider": "openai", "serviceTier": "priority", "cwd": e["cwd"], "approvalPolicy": "never", "sandbox": "danger-full-access", "ephemeral": True, "config": {"model_reasoning_effort": "medium", "features.fast_mode": True}})
        elif method == "thread/start":
            for key, value in {"model": "gpt-6.1-sol", "modelProvider": "openai", "reasoningEffort": "medium", "serviceTier": "priority", "cwd": e["cwd"], "approvalPolicy": "never", "sandbox": {"type": "dangerFullAccess"}}.items():
                _require(result.get(key) == value, "resolved runtime setting mismatch: " + key)
            self.thread = result["thread"]["id"]
            _require(type(self.thread) is str and self.thread, "invalid thread id")
            self.check_scope()
            self.request("turn/start", {"threadId": self.thread, "input": self.input(), "outputSchema": e["schema"]})
        elif method == "turn/start":
            turn = result["turn"]
            self.turn = turn["id"]
            _require(type(self.turn) is str and self.turn and turn.get("status") in ("inProgress", "completed") and turn.get("error") is None, "invalid turn response")
            self.check_scope()
        else:
            raise ProtocolError("unexpected response method")

    def finish(self):
        _require(not self.ready and not self.pending and self.thread and self.turn and len(self.completed) == 1, "incomplete protocol")
        self.check_scope()
        answers = list(self.answers.values())
        finals = [x for x in answers if x.get("phase") == "final_answer"]
        selected = finals if finals else [x for x in answers if x.get("phase") is None]
        _require(len(selected) == 1 and (bool(finals) or len(answers) == 1), "missing/ambiguous final response")
        answer = selected[0]
        parsed = strict_json(answer["text"])
        _require(type(parsed) is dict and type(parsed.get("schema_version")) is int and parsed["schema_version"] == 2, "final response is not strict v2 JSON")
        for item in self.completed[0].get("items", []):
            _require(type(item) is dict and item.get("type") in ITEMS, "unsupported completed turn item")
            if item["type"] == "userMessage":
                _require(item.get("content") == self.input(), "conflicting completed user message")
            if item["type"] == "agentMessage":
                known = self.answers.get(item.get("id"))
                _require(known is not None and item.get("text") == known["text"] and
                         ("phase" not in item or item["phase"] == known.get("phase")), "contradictory completed turn item")
        return {"profile": dict(PROFILE), "thread_id": self.thread, "turn_id": self.turn,
                "response_text": answer["text"], "completed": True}


def replay_protocol(records: list[dict], *, expected: dict) -> dict:
    _require(type(records) is list and len(records) <= MAX_FRAMES, "protocol frame bound")
    session = _Session(expected)
    try:
        for seq, record in enumerate(records, 1):
            _require(type(record) is dict and set(record) == {"seq", "direction", "raw"} and type(record["seq"]) is int and record["seq"] == seq, "invalid frame sequence")
            raw = record["raw"]
            _require(type(raw) is str and raw.endswith("\n") and len(raw.encode()) <= MAX_LINE, "invalid/oversized JSON line")
            session.feed(record["direction"], strict_json(raw))
        return session.finish()
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError) as error:
        raise ProtocolError("malformed protocol shape") from error


def _proof_shape(proof, *, cwd, codex_home):
    required = {"version": 1, "purpose": "r0-disposable-provider",
                "network_policy": "standard-docker-bridge-unrestricted-outbound",
                "github_credentials_or_integrations": False, "bank_credentials_or_integrations": False,
                "production_credentials_or_integrations": False, "codex_auth_delivery": "authorized-readonly-file"}
    _require(type(proof) is dict and all(type(proof.get(k)) is type(v) and proof[k] == v for k, v in required.items()), "invalid disposable boundary assertion")
    for field in ("worktree_root", "output_root", "codex_home", "codex_auth_mount"):
        value = proof.get(field)
        _require(type(value) is str and Path(value).is_absolute() and Path(value) != Path("/") and str(Path(value)) == value and ".." not in Path(value).parts, "invalid boundary path")
    _require(proof["codex_home"] == codex_home and Path(cwd).is_relative_to(proof["worktree_root"]) and Path(cwd).parent.is_relative_to(proof["output_root"]), "boundary worktree/home mismatch")
    _require(type(proof.get("namespaces")) is dict and set(proof["namespaces"]) == {"mnt", "net", "pid"} and all(type(v) is str and v for v in proof["namespaces"].values()), "missing namespace assertion")


def _readonly_mount(path):
    candidates = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        fields = line.split()
        if len(fields) < 6:
            continue
        mount = fields[4].replace("\\040", " ").replace("\\134", "\\")
        if path.is_relative_to(mount):
            candidates.append((len(mount), "ro" in fields[5].split(",")))
    return bool(candidates) and max(candidates)[1]


def codex_home(env):
    return env.get("CODEX_HOME") or str(Path(env.get("HOME") or str(Path.home())) / ".codex")


def validate_boundary(path: Path, *, cwd: Path, env: dict) -> dict:
    """Read nonsecret supervisor metadata only; never inspect authentication."""
    try:
        _require(os.geteuid() != 0, "provider workload must be non-root")
        info = path.lstat()
        _require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022 and info.st_size <= 16384, "unprotected boundary proof")
        _require(path.resolve() == path and _readonly_mount(path), "boundary proof must be on a read-only mount")
        with path.open("rb") as stream:
            _require(os.fstat(stream.fileno()) == info, "boundary proof changed")
            proof = strict_json(stream.read(16385))
        _proof_shape(proof, cwd=str(cwd.resolve()), codex_home=codex_home(env))
        _require(all(os.readlink("/proc/self/ns/" + name) == value for name, value in proof["namespaces"].items()), "boundary namespace mismatch")
        _require(Path(proof["codex_home"]).resolve() == Path(proof["codex_home"]) and Path(proof["output_root"]).resolve() == Path(proof["output_root"]), "boundary root alias")
        return proof
    except (OSError, TypeError, KeyError, json.JSONDecodeError) as error:
        raise ProtocolError("disposable boundary unavailable") from error


def capture_context(protocol: bytes) -> dict:
    _require(len(protocol) <= MAX_CAPTURE, "oversized protocol capture")
    first = protocol.split(b"\n", 1)[0]
    header = strict_json(first)
    _require(type(header) is dict and header.get("type") == "adapter_start", "missing adapter header")
    return header["context"]


def replay_capture(protocol: bytes, *, stdout: bytes, expected: dict) -> dict:
    try:
        _require(len(protocol) <= MAX_CAPTURE and len(stdout) <= MAX_STREAM, "protocol output bound")
        lines = protocol.splitlines(keepends=True)
        _require(2 <= len(lines) <= MAX_FRAMES + 2 and all(x.endswith(b"\n") for x in lines), "incomplete capture")
        records = [strict_json(x) for x in lines]
        header, footer = records[0], records[-1]
        _require(header.get("type") == "adapter_start" and header.get("adapter_version") == 1 and header.get("cli_version") == VERSION and header.get("argv") == provider_argv(), "unsupported adapter/runtime version")
        _require(header.get("context") == context(expected), "retained invocation context mismatch")
        _proof_shape(header.get("boundary"), cwd=expected["cwd"], codex_home=expected["codex_home"])
        _require(footer == {"type": "adapter_exit", "status": "completed", "exit_code": 0, "output_budget_exhausted": False}, "provider did not exit cleanly")
        frames = records[1:-1]
        _require(b"".join(x["raw"].encode() for x in frames if x.get("direction") == "server") == stdout, "server transcript differs from stdout")
        return replay_protocol(frames, expected=expected)
    except (KeyError, TypeError, AttributeError, UnicodeError, json.JSONDecodeError) as error:
        raise ProtocolError("malformed capture") from error


def _stop(process):
    """Kill the entire process group even after its leader has exited."""
    if process is None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=0.5)


def _version(cwd, env, deadline, cancelled):
    process = None
    output = bytearray()
    try:
        process = subprocess.Popen(["codex", "--version"], cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        with selectors.DefaultSelector() as selector:
            for pipe in (process.stdout, process.stderr):
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, selectors.EVENT_READ)
            end = min(deadline, time.monotonic() + 5)
            while selector.get_map():
                _require(not cancelled(), "caller interrupted during CLI version probe")
                _require(time.monotonic() < end, "CLI version probe timed out")
                for key, _ in selector.select(min(0.05, max(0, end - time.monotonic()))):
                    data = os.read(key.fd, 16384)
                    if not data:
                        selector.unregister(key.fileobj)
                    elif key.fileobj is process.stdout:
                        output.extend(data)
                    else:
                        _require(not data.strip(), "CLI version probe wrote stderr")
                    _require(len(output) <= 16384, "CLI version output bound")
            _require(process.wait(timeout=max(0.01, min(0.5, end-time.monotonic()))) == 0 and output.decode().strip() == VERSION, "unsupported Codex CLI version")
        return output.decode().strip()
    finally:
        _stop(process)
        if process:
            process.stdout.close()
            process.stderr.close()


def run_app_server(*, argv: list[str], cwd: Path, env: dict[str, str], prompt: str,
                   schema: dict, expected: dict, boundary_proof: Path = BOUNDARY,
                   timeout_seconds: int, progress=None) -> dict:
    proof = validate_boundary(boundary_proof, cwd=cwd, env=env)
    _require(argv == provider_argv(), "unexpected provider argv")
    _require(type(timeout_seconds) is int and 3 < timeout_seconds <= 1800, "insufficient provider/cleanup budget")
    _require(expected["cwd"] == str(cwd.resolve()) and expected["prompt"] == prompt and expected["schema"] == schema and expected["codex_home"] == codex_home(env), "invocation context mismatch")
    _require(len(prompt.encode()) + len(_canonical(schema)) <= MAX_LINE, "prompt/schema output bound")
    start = datetime.now(timezone.utc).isoformat()
    deadline = time.monotonic() + timeout_seconds - 3
    records = []
    protocol_size = 0
    outputs = [bytearray(), bytearray()]
    buffer = bytearray()
    process = None
    status = "failed"
    budget = False
    error = None
    replay = None
    session = _Session(expected)
    cancelled = []
    previous_handlers = {}
    def request_cancel(signum, frame):
        cancelled.append(signum)
    for signum in (signal.SIGTERM, signal.SIGINT):
        try:
            previous_handlers[signum] = signal.signal(signum, request_cancel)
        except ValueError:  # Library use outside the main thread still has deadlines.
            break
    header_emitted = False
    def emit(value):
        if progress is not None:
            progress(_wire(value).encode())
    header = {"type": "adapter_start", "adapter_version": 1, "cli_version": None,
              "argv": argv, "context": context(expected), "boundary": proof}

    def record(direction, raw):
        nonlocal protocol_size
        frame = {"seq": len(records)+1, "direction": direction, "raw": raw}
        protocol_size += len(_wire(frame).encode())
        _require(len(records) < MAX_FRAMES and protocol_size <= MAX_CAPTURE-65536, "protocol capture budget exhausted")
        records.append(frame)
        emit(frame)

    def best_effort(frame, selector, until):
        raw = _wire(frame).encode()
        offset = 0
        while process.poll() is None and time.monotonic() < until:
            try:
                count = os.write(process.stdin.fileno(), raw[offset:])
                offset += count
                if offset == len(raw):
                    record("client", raw.decode())
                    return True
            except (BlockingIOError, BrokenPipeError):
                pass
            # Bounded wait; normal transport already drains both streams.
            selector.select(0.01)
        return False

    def drain_interrupt(selector, until):
        """Retain genuine cancellation frames without interpreting them as success."""
        while time.monotonic() < until:
            while b"\n" in buffer:
                raw, _, tail = buffer.partition(b"\n")
                buffer[:] = tail
                _require(len(raw)+1 <= MAX_LINE, "protocol line budget exhausted")
                line = (raw+b"\n").decode()
                record("server", line)
                frame = strict_json(line)
                if (type(frame) is dict and frame.get("method") == "turn/completed"
                        and frame.get("params", {}).get("threadId") == session.thread
                        and frame["params"].get("turn", {}).get("id") == session.turn):
                    return
            _require(len(buffer) <= MAX_LINE, "partial protocol line budget exhausted")
            readable = [key for key in selector.get_map().values() if key.data in (0, 1)]
            if not readable:
                return
            for key, _ in selector.select(min(0.02, max(0, until-time.monotonic()))):
                if key.data not in (0, 1):
                    continue
                data = os.read(key.fd, 65536)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                stream = outputs[key.data]
                room = MAX_STREAM - len(stream)
                stream.extend(data[:room])
                _require(len(data) <= room, "provider output budget exhausted")
                if key.data == 0:
                    buffer.extend(data)

    try:
        header["cli_version"] = _version(cwd, env, deadline, lambda: bool(cancelled))
        _require(not cancelled, "caller interrupted before provider startup")
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        header["process_id"] = process.pid
        emit(header)
        header_emitted = True
        for pipe in (process.stdin, process.stdout, process.stderr):
            os.set_blocking(pipe.fileno(), False)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, 0)
            selector.register(process.stderr, selectors.EVENT_READ, 1)
            writing = None
            write_offset = 0
            client_size = 0
            completion_deadline = None
            try:
                while True:
                    now = time.monotonic()
                    _require(not cancelled, "caller interrupted by signal")
                    _require(now < deadline, "provider timed out")
                    if writing is None and session.ready and not process.stdin.closed:
                        writing = _wire(session.ready[0]).encode()
                        _require(len(writing) <= MAX_LINE and client_size + len(writing) <= MAX_STREAM, "client protocol budget exhausted")
                        selector.register(process.stdin, selectors.EVENT_WRITE, 2)
                    if session.completed and not session.ready and not session.pending and completion_deadline is None:
                        replay = session.finish()
                        process.stdin.close()
                        completion_deadline = now + 2
                    if completion_deadline is not None:
                        _require(now < completion_deadline or process.poll() is not None, "server did not exit after completion")
                    if process.poll() is not None and not any(k.data in (0, 1) for k in selector.get_map().values()):
                        _require(not buffer and replay is not None and process.returncode == 0, "provider exited without clean completed turn")
                        replay = session.finish()
                        status = "completed"
                        break
                    for key, _ in selector.select(0.02):
                        if key.data == 2:
                            count = os.write(key.fd, writing[write_offset:])
                            write_offset += count
                            if write_offset == len(writing):
                                raw = writing.decode()
                                record("client", raw)
                                session.feed("client", strict_json(raw))
                                client_size += len(writing)
                                writing = None
                                write_offset = 0
                                selector.unregister(key.fileobj)
                            continue
                        data = os.read(key.fd, 65536)
                        if not data:
                            selector.unregister(key.fileobj)
                            continue
                        stream = outputs[key.data]
                        room = MAX_STREAM - len(stream)
                        stream.extend(data[:room])
                        _require(len(data) <= room, "provider output budget exhausted")
                        if key.data == 0:
                            buffer.extend(data)
                            while b"\n" in buffer:
                                raw, _, tail = buffer.partition(b"\n")
                                buffer[:] = tail
                                _require(len(raw)+1 <= MAX_LINE, "protocol line budget exhausted")
                                line = (raw+b"\n").decode()
                                record("server", line)
                                frame = strict_json(line)
                                if type(frame) is dict and "method" in frame and "id" in frame:
                                    decision = {"id": frame["id"], "result": {"decision": "cancel"}} if frame["method"] in ("item/commandExecution/requestApproval", "item/fileChange/requestApproval") else {"id": frame["id"], "error": {"code": -32601, "message": "Unsupported server request"}}
                                    best_effort(decision, selector, min(deadline+1, time.monotonic()+0.2))
                                    raise ProtocolError("unexpected server request; cancelled")
                                session.feed("server", frame)
                            _require(len(buffer) <= MAX_LINE, "partial protocol line budget exhausted")
            except (ProtocolError, OSError, ValueError, KeyError, TypeError, AttributeError, KeyboardInterrupt) as failure:
                error = str(failure) or "caller interrupted"
                budget = "budget" in error
                status = "timed_out" if "timed out" in error else "interrupted" if isinstance(failure, KeyboardInterrupt) or "interrupted" in error else "failed"
                if session.thread and session.turn and process.poll() is None and not process.stdin.closed:
                    # Abort an incomplete write before sending another JSON frame.
                    if writing is None or write_offset == 0:
                        try:
                            sent = best_effort({"id": session.next_id, "method": "turn/interrupt", "params": {"threadId": session.thread, "turnId": session.turn}}, selector, time.monotonic()+0.2)
                            if sent:
                                drain_interrupt(selector, time.monotonic()+0.25)
                        except (ProtocolError, OSError, ValueError, KeyError, TypeError, UnicodeError):
                            # Cancellation evidence is best effort; preserve the original failure.
                            pass
                raise ProtocolError(error) from failure
    except (OSError, ProtocolError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired, UnicodeError) as failure:
        error = str(failure)
        if "interrupted" in error:
            status = "interrupted"
    finally:
        _stop(process)
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
        if process:
            for pipe in (process.stdin, process.stdout, process.stderr):
                pipe.close()
    footer = {"type": "adapter_exit", "status": status, "exit_code": process.returncode if process else None,
              "output_budget_exhausted": budget}
    if not header_emitted:
        emit(header)
    emit(footer)
    protocol = (_wire(header) + "".join(_wire(x) for x in records) + _wire(footer)).encode()
    return {"started_at": start, "finished_at": datetime.now(timezone.utc).isoformat(), "status": status,
            "exit_code": footer["exit_code"], "stdout": bytes(outputs[0]), "stderr": bytes(outputs[1]),
            "protocol": protocol, "response": replay["response_text"].encode() if replay and status == "completed" else b"",
            "output_budget_exhausted": budget, "error": error}
