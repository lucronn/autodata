#!/usr/bin/env python3
"""Bounded standard-library probes for one isolated synthetic lab fixture."""
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import socket
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from urllib.parse import quote

CHECKS = ("nats_connected", "nats_fixture", "nats_writer_denied", "nats_reader_denied",
          "s3_connected", "s3_fixture", "s3_reader_denied", "s3_anonymous_denied", "fixture_unchanged")
MEASUREMENTS = ("nats_message_count", "s3_object_bytes", "nats_payload_sha256", "s3_payload_sha256")
HOST = "172.31.250.40:9000"


class ProbeError(Exception):
    pass


class Denied(ProbeError):
    pass


class Missing(ProbeError):
    pass


def need(condition):
    if not condition:
        raise ProbeError()


def jdump(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True, allow_nan=False).encode()


def jload(data):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result)
            result[key] = value
        return result
    try:
        need(len(data) <= 1048576)
        value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ProbeError()))
        need(type(value) is dict)
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise ProbeError() from None


def sha(data):
    return hashlib.sha256(data).hexdigest()


def wrong(value):
    return ("1" if value[0] != "1" else "2") + value[1:]


class Budget:
    def __init__(self):
        self.end = time.monotonic() + 15
        self.events = 0

    def charge(self):
        need(time.monotonic() < self.end and self.events < 64)
        self.events += 1

    def timeout(self):
        remaining = self.end - time.monotonic()
        need(remaining > 0)
        return min(3, remaining)


class Stream:
    def __init__(self, budget, address):
        self.budget = budget
        try:
            self.sock = socket.create_connection(address, timeout=budget.timeout())
        except OSError:
            raise ProbeError() from None

    def read(self, count):
        need(0 <= count <= 1048576)
        data = bytearray()
        while len(data) < count:
            self.sock.settimeout(self.budget.timeout())
            try:
                block = self.sock.recv(count - len(data))
            except OSError:
                raise ProbeError() from None
            need(bool(block))
            data.extend(block)
        return bytes(data)

    def line(self):
        data = bytearray()
        while not data.endswith(b"\r\n"):
            need(len(data) < 16384)
            data.extend(self.read(1))
        return bytes(data[:-2])

    def send(self, data):
        self.budget.charge()
        need(len(data) <= 1048576 + 16384)
        self.sock.settimeout(self.budget.timeout())
        try:
            self.sock.sendall(data)
        except OSError:
            raise ProbeError() from None

    def close(self):
        self.sock.close()


class Nats(Stream):
    def __init__(self, budget, user=None, password=None):
        super().__init__(budget, ("172.31.250.30", 4222))
        self.subscribed = False
        try:
            info = self.frame()
            need(info[0] == "INFO")
            config = {"verbose": False, "pedantic": True, "protocol": 1, "lang": "python", "version": "1", "name": "autodata-lab"}
            if user is not None:
                config.update(user=user, **{"pass": password})
            self.send(b"CONNECT " + jdump(config) + b"\r\n")
            self.send(b"PING\r\n")
            need(self.frame()[0] == "PONG")
        except BaseException:
            self.close()
            raise

    def frame(self):
        self.budget.charge()
        line = self.line()
        if line.startswith(b"-ERR "):
            lower = line.lower()
            if b"authorization violation" in lower or b"permissions violation" in lower:
                raise Denied()
            raise ProbeError()
        if line.startswith(b"INFO "):
            jload(line[5:])
            return "INFO", None
        if line == b"PONG":
            return "PONG", None
        if line.startswith(b"MSG "):
            parts = line.split()
            need(len(parts) == 4 and parts[1:3] == [b"_INBOX.LAB", b"1"] and re.fullmatch(b"[0-9]{1,7}", parts[3]))
            length = int(parts[3])
            need(length <= 1048576)
            data = self.read(length)
            need(self.read(2) == b"\r\n")
            return "MSG", data
        # Unsolicited PING/+OK/HMSG are charged and fail this fixed transcript.
        raise ProbeError()

    def request(self, subject, value, message_id=None):
        need(subject.startswith("$JS.API.") or subject == "lab.probe")
        if not self.subscribed:
            self.send(b"SUB _INBOX.LAB 1\r\n")
            self.subscribed = True
        body = value if isinstance(value, bytes) else jdump(value)
        if message_id is None:
            prefix = b"PUB " + subject.encode() + b" _INBOX.LAB " + str(len(body)).encode() + b"\r\n"
            self.send(prefix + body + b"\r\n")
        else:
            header = b"NATS/1.0\r\nNats-Msg-Id: " + message_id.encode() + b"\r\n\r\n"
            self.send(b"HPUB " + subject.encode() + b" _INBOX.LAB " + str(len(header)).encode() + b" " + str(len(header) + len(body)).encode() + b"\r\n" + header + body + b"\r\n")
        kind, reply = self.frame()
        need(kind == "MSG")
        parsed = jload(reply)
        if "error" in parsed:
            error = parsed["error"]
            need(type(error) is dict and type(error.get("code")) is int)
            if error["code"] == 404:
                raise Missing()
            if error["code"] in (401, 403):
                raise Denied()
            raise ProbeError()
        return parsed

    def deny_publish(self):
        self.send(b"PUB lab.probe 0\r\n\r\n")
        self.send(b"PING\r\n")
        try:
            self.frame()
        except Denied:
            return
        raise ProbeError()


def sign(method, path, body, access, secret, timestamp):
    need(method in ("GET", "HEAD", "PUT") and path.startswith("/lab-stateful") and "\r" not in path and "\n" not in path and "#" not in path)
    raw_path, separator, query = path.partition("?")
    uri = quote(raw_path, safe="/-_.~")
    need(not separator or query == "list-type=2")
    payload_hash = sha(body)
    headers = {"host": HOST, "x-amz-content-sha256": payload_hash, "x-amz-date": timestamp}
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    request = "\n".join((method, uri, query, "".join(k + ":" + headers[k] + "\n" for k in sorted(headers)), signed_headers, payload_hash))
    day = timestamp[:8]
    scope = day + "/us-east-1/s3/aws4_request"
    message = "AWS4-HMAC-SHA256\n" + timestamp + "\n" + scope + "\n" + sha(request.encode())
    key = ("AWS4" + secret).encode()
    for part in (day, "us-east-1", "s3", "aws4_request"):
        key = hmac.new(key, part.encode(), hashlib.sha256).digest()
    signature = hmac.new(key, message.encode(), hashlib.sha256).hexdigest()
    headers["authorization"] = "AWS4-HMAC-SHA256 Credential=" + access + "/" + scope + ", SignedHeaders=" + signed_headers + ", Signature=" + signature
    return headers, request


class S3:
    def __init__(self, budget, access=None, secret=None):
        self.budget, self.access, self.secret = budget, access, secret

    def request(self, method, path, body=b""):
        need(method in ("GET", "HEAD", "PUT") and re.fullmatch(r"/lab-stateful(?:/[a-z0-9./-]+)?(?:\?list-type=2)?", path) and ".." not in path)
        timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        headers = {"host": HOST}
        if self.access is not None:
            headers, _ = sign(method, path, body, self.access, self.secret, timestamp)
        headers.update({"connection": "close", "content-length": str(len(body))})
        wire = Stream(self.budget, ("172.31.250.40", 9000))
        try:
            wire.send((method + " " + path + " HTTP/1.1\r\n" + "".join(k + ": " + v + "\r\n" for k, v in headers.items()) + "\r\n").encode() + body)
            self.budget.charge()
            status = wire.line().split()
            need(len(status) >= 2 and status[0] == b"HTTP/1.1" and re.fullmatch(b"[0-9]{3}", status[1]))
            code = int(status[1])
            need(200 <= code < 300 or code in (400, 401, 403, 404, 409))
            received, total = {}, 0
            while True:
                line = wire.line()
                total += len(line) + 2
                need(total <= 16384)
                if not line:
                    break
                name, delimiter, value = line.partition(b":")
                need(delimiter and re.fullmatch(b"[a-zA-Z0-9-]+", name))
                name = name.decode().lower()
                need(name not in received)
                received[name] = value.decode("ascii").strip()
            need("transfer-encoding" not in received and "content-length" in received)
            need(re.fullmatch("[0-9]{1,7}", received["content-length"]))
            length = int(received["content-length"])
            need(length <= 1048576)
            result = b"" if method == "HEAD" else wire.read(length)
            return code, received, result
        finally:
            wire.close()

    def success(self, method, path, body=b""):
        code, headers, result = self.request(method, path, body)
        need(code in (200, 204))
        return headers, result


def stream_config(config):
    need(config.get("name") == "LAB_STATEFUL" and config.get("subjects") == ["lab.probe"] and config.get("storage") == "file" and
         config.get("retention") == "limits" and type(config.get("max_msgs")) is int and config["max_msgs"] == 1 and config.get("discard") == "new")


def nats_fixture(client, run):
    info = client.request("$JS.API.STREAM.INFO.LAB_STATEFUL", {})
    stream_config(info.get("config", {}))
    state = info.get("state", {})
    need(type(state.get("messages")) is int and state["messages"] == 1 and state.get("first_seq") == 1 and state.get("last_seq") == 1)
    reply = client.request("$JS.API.STREAM.MSG.GET.LAB_STATEFUL", {"seq": 1})
    message = reply.get("message", {})
    need(message.get("subject") == "lab.probe" and type(message.get("seq")) is int and message["seq"] == 1)
    try:
        body = base64.b64decode(message["data"], validate=True)
    except (KeyError, ValueError):
        raise ProbeError() from None
    need(body == ("autodata-lab-v1:" + run).encode())
    return sha(body)


def s3_fixture(client, run):
    path = "/lab-stateful/" + run + "/sentinel.txt"
    headers, _ = client.success("HEAD", path)
    _, body = client.success("GET", path)
    need(body == ("autodata-lab-v1:" + run).encode() and int(headers["content-length"]) == len(body))
    _, listing = client.success("GET", "/lab-stateful?list-type=2")
    try:
        root = ET.fromstring(listing)
        keys = [e.text for e in root.iter() if e.tag.rsplit("}", 1)[-1] == "Key"]
        truncated = [e.text for e in root.iter() if e.tag.rsplit("}", 1)[-1] == "IsTruncated"]
        need(keys == [run + "/sentinel.txt"] and truncated == ["false"])
    except ET.ParseError:
        raise ProbeError() from None
    return len(body), sha(body)


def seed_nats(client, run):
    try:
        info = client.request("$JS.API.STREAM.INFO.LAB_STATEFUL", {})
    except Missing:
        info = client.request("$JS.API.STREAM.CREATE.LAB_STATEFUL", {"name": "LAB_STATEFUL", "subjects": ["lab.probe"], "storage": "file", "retention": "limits", "max_msgs": 1, "discard": "new"})
    stream_config(info.get("config", {}))
    state = info.get("state", {})
    need(type(state.get("messages")) is int and state["messages"] in (0, 1))
    if state["messages"] == 0:
        need(state.get("last_seq") == 0)
        ack = client.request("lab.probe", ("autodata-lab-v1:" + run).encode(), run)
        need(ack.get("stream") == "LAB_STATEFUL" and type(ack.get("seq")) is int and ack["seq"] == 1 and not ack.get("duplicate", False))
    return nats_fixture(client, run)


def seed_s3(client, run):
    code, _, _ = client.request("HEAD", "/lab-stateful")
    need(code in (200, 404))
    new_bucket = code == 404
    if new_bucket:
        client.success("PUT", "/lab-stateful")
    path = "/lab-stateful/" + run + "/sentinel.txt"
    code = 404 if new_bucket else client.request("HEAD", path)[0]
    need(code in (200, 404))
    if code == 404:
        # Never fill a missing slot in a nonempty/unowned bucket.
        if not new_bucket:
            _, data = client.success("GET", "/lab-stateful?list-type=2")
            try:
                root = ET.fromstring(data)
                need(not any(e.tag.rsplit("}", 1)[-1] == "Key" for e in root.iter()))
            except ET.ParseError:
                raise ProbeError() from None
        client.success("PUT", path, ("autodata-lab-v1:" + run).encode())
    return s3_fixture(client, run)


def deny(call):
    try:
        value = call()
    except Denied:
        return
    if isinstance(value, tuple) and value[0] in (401, 403):
        # Require a parsed S3 authorization error, never transport/non-auth errors.
        try:
            root = ET.fromstring(value[2])
            codes = [e.text for e in root.iter() if e.tag.rsplit("}", 1)[-1] == "Code"]
            need(len(codes) == 1 and codes[0] in ("AccessDenied", "SignatureDoesNotMatch", "InvalidAccessKeyId"))
            return
        except ET.ParseError:
            pass
    raise ProbeError()


def read_credentials(run):
    fd = os.open("/run/lab/probe.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        data = os.read(fd, 16385)
    finally:
        os.close(fd)
    need(len(data) <= 16384)
    value = jload(data)
    fields = {"nats_writer_password", "nats_reader_password", "s3_writer_access", "s3_writer_secret", "s3_reader_access", "s3_reader_secret"}
    need(set(value) == fields | {"schema_version", "run_id"} and type(value["schema_version"]) is int and value["schema_version"] == 1 and value["run_id"] == run)
    need(all(type(value[k]) is str and re.fullmatch("[0-9a-f]{64}", value[k]) for k in fields))
    need(len({value[k] for k in fields}) == len(fields))
    return value


def probe_cli(mode, run_id):
    result = dict(schema_version=1, mode=mode, run_id=run_id, status="failed",
                  checks={k: None for k in CHECKS}, measurements={k: None for k in MEASUREMENTS})
    writer = reader = None
    try:
        need(mode in ("ready", "seed", "check", "deny") and str(uuid.UUID(run_id)) == run_id and uuid.UUID(run_id).version == 4)
        credentials = read_credentials(run_id)
        budget = Budget()
        writer = Nats(budget, "writer", credentials["nats_writer_password"])
        s3 = S3(budget, credentials["s3_writer_access"], credentials["s3_writer_secret"])
        checks = result["checks"]
        checks["nats_connected"] = True
        if mode == "ready":
            writer.request("$JS.API.INFO", {})
            code, _, _ = s3.request("HEAD", "/lab-stateful")
            need(code in (200, 404))
            bad = S3(budget, credentials["s3_writer_access"], wrong(credentials["s3_writer_secret"]))
            need(bad.request("HEAD", "/lab-stateful")[0] == 403)
            checks["s3_connected"] = True
        else:
            n_hash = seed_nats(writer, run_id) if mode == "seed" else nats_fixture(writer, run_id)
            size, s_hash = seed_s3(s3, run_id) if mode == "seed" else s3_fixture(s3, run_id)
            baseline = n_hash, size, s_hash
            checks.update(nats_fixture=True, s3_connected=True, s3_fixture=True)
            if mode == "deny":
                deny(lambda: Nats(budget))
                deny(lambda: Nats(budget, "writer", wrong(credentials["nats_writer_password"])))
                checks["nats_writer_denied"] = True
                reader = Nats(budget, "reader", credentials["nats_reader_password"])
                reader.request("$JS.API.INFO", {})
                deny(lambda: reader.request("$JS.API.STREAM.CREATE.LAB_STATEFUL", {"name": "LAB_STATEFUL", "subjects": ["lab.probe"]}))
                reader.deny_publish()
                checks["nats_reader_denied"] = True
                path = "/lab-stateful/" + run_id + "/sentinel.txt"
                deny(lambda: S3(budget).request("GET", path))
                deny(lambda: S3(budget, credentials["s3_writer_access"], wrong(credentials["s3_writer_secret"])).request("GET", path))
                checks["s3_anonymous_denied"] = True
                ro = S3(budget, credentials["s3_reader_access"], credentials["s3_reader_secret"])
                _, body = ro.success("GET", path)
                need(sha(body) == s_hash)
                deny(lambda: ro.request("PUT", path, b"denied"))
                checks["s3_reader_denied"] = True
            # All seed/check/deny modes measure an unchanged second read.
            after = (nats_fixture(writer, run_id),) + s3_fixture(s3, run_id)
            need(after == baseline)
            checks["fixture_unchanged"] = True
            result["measurements"].update(nats_message_count=1, s3_object_bytes=size, nats_payload_sha256=n_hash, s3_payload_sha256=s_hash)
        need(time.monotonic() < budget.end)
        result["status"] = "passed"
        return 0, result
    except (ProbeError, OSError, ValueError, TypeError, KeyError, RecursionError):
        return (2 if mode not in ("ready", "seed", "check", "deny") else 4), result
    finally:
        for client in (writer, reader):
            if client is not None:
                client.close()


if __name__ == "__main__":
    os.environ.clear()
    code, result = probe_cli(*sys.argv[1:]) if len(sys.argv) == 3 else probe_cli("invalid", "")
    data = jdump(result) + b"\n"
    if len(data) > 32768:
        raise SystemExit(4)
    sys.stdout.buffer.write(data)
    raise SystemExit(code)
