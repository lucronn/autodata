"""Recorded-wire unit tests; sockets are always fake."""
import hashlib
import base64
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("stateful_probe", Path(__file__).with_name("stateful_probe.py"))
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)
RUN = "12345678-1234-4234-8234-123456789abc"


class Wire:
    def __init__(self, data):
        self.incoming, self.sent = io.BytesIO(data), bytearray()
    def recv(self, count):
        return self.incoming.read(count)
    def sendall(self, data):
        self.sent.extend(data)
    def settimeout(self, value):
        pass
    def close(self):
        pass


class ProtocolTests(unittest.TestCase):
    def test_global_budget_accepts_64_rejects_65(self):
        budget = probe.Budget()
        for _ in range(64):
            budget.charge()
        self.assertEqual(budget.events, 64)
        with self.assertRaises(probe.ProbeError):
            budget.charge()

    def test_shared_budget_cannot_reset_across_protocol_or_socket(self):
        b = probe.Budget()
        b.events = 63
        a = Wire(b"INFO {}\r\nPONG\r\n")
        with patch.object(probe.socket, "create_connection", return_value=a), self.assertRaises(probe.ProbeError):
            probe.Nats(b, "writer", "a" * 64)
        self.assertEqual(b.events, 64)

    def test_nats_wrong_auth_distinguished_from_transport_failure(self):
        a = Wire(b"INFO {}\r\n-ERR 'Authorization Violation'\r\n")
        with patch.object(probe.socket, "create_connection", return_value=a), self.assertRaises(probe.Denied):
            probe.Nats(probe.Budget(), "writer", "a" * 64)
        with patch.object(probe.socket, "create_connection", side_effect=TimeoutError), self.assertRaises(probe.ProbeError) as caught:
            probe.Nats(probe.Budget(), "writer", "a" * 64)
        self.assertNotIsInstance(caught.exception, probe.Denied)

    def test_nats_exact_stream_message_and_ack(self):
        body = b'{"streams":1}'
        wire = Wire(b"INFO {}\r\nPONG\r\nMSG _INBOX.LAB 1 " + str(len(body)).encode() + b"\r\n" + body + b"\r\n")
        with patch.object(probe.socket, "create_connection", return_value=wire):
            n = probe.Nats(probe.Budget(), "writer", "a" * 64)
            self.assertEqual(n.request("$JS.API.INFO", {}), {"streams": 1})
            n.close()
        self.assertIn(b"SUB _INBOX.LAB 1\r\n", wire.sent)
        self.assertIn(b"PUB $JS.API.INFO _INBOX.LAB 2\r\n{}\r\n", wire.sent)

    def test_protocol_size_time_and_malformed_reply_fail_closed(self):
        for data in (b"INFO " + b"x" * 16384 + b"\r\n", b"garbage\r\n", b"INFO {}\r\nMSG x 1 -1\r\n"):
            with patch.object(probe.socket, "create_connection", return_value=Wire(data)), self.assertRaises(probe.ProbeError):
                probe.Nats(probe.Budget(), "writer", "a" * 64)
        with patch.object(probe.time, "monotonic", side_effect=[0, 16]):
            b = probe.Budget()
            with self.assertRaises(probe.ProbeError):
                b.charge()

    def test_s3_no_redirect_or_external_host(self):
        with self.assertRaises(probe.ProbeError):
            probe.S3(probe.Budget(), "a", "b").request("GET", "https://example.com/private")
        response = b"HTTP/1.1 302 Found\r\nLocation: https://example.com/\r\nContent-Length: 0\r\n\r\n"
        with patch.object(probe.socket, "create_connection", return_value=Wire(response)), self.assertRaises(probe.ProbeError):
            probe.S3(probe.Budget(), "a", "b").request("GET", "/lab-stateful")

    def test_s3_canonical_request_has_fixed_host_time_hash_and_no_secret(self):
        headers, canonical = probe.sign("GET", "/lab-stateful/test.txt", b"", "key", "secret", "20261104T120000Z")
        expected = "GET\n/lab-stateful/test.txt\n\nhost:172.31.250.40:9000\nx-amz-content-sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\nx-amz-date:20261104T120000Z\n\nhost;x-amz-content-sha256;x-amz-date\ne3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        self.assertEqual(canonical, expected)
        self.assertNotIn("secret", str(headers))
        self.assertIn("Credential=key/20261104/us-east-1/s3/aws4_request", headers["authorization"])
        # Independently calculated from the literal canonical request above.
        self.assertTrue(headers["authorization"].endswith("Signature=fd5e6905f5805a456d969b85a62f00ec9915fc0a0e3b4e2ca6703504fa1b1ce7"))

    def test_probe_output_never_contains_bundle_or_payload(self):
        code, result = probe.probe_cli("invalid", RUN)
        self.assertEqual(code, 2)
        self.assertEqual(set(result), {"schema_version", "mode", "run_id", "status", "checks", "measurements"})
        self.assertNotIn("autodata-lab-v1:", json.dumps(result))
        self.assertTrue(all(value is None for value in result["checks"].values()))


class LabModel:
    """An external peer model: protocol frames, fixed resources, real client code."""
    def __init__(self, seeded=True):
        self.stream = seeded
        self.bucket = seeded
        self.message = ("autodata-lab-v1:" + RUN).encode() if seeded else None
        self.object = self.message
        self.publishes = 0
        self.puts = 0
        self.bundle = dict(schema_version=1, run_id=RUN, **{k: format(i + 1, "064x") for i, k in enumerate(("nats_writer_password", "nats_reader_password", "s3_writer_access", "s3_writer_secret", "s3_reader_access", "s3_reader_secret"))})

    def socket(self, address, timeout):
        return Peer(self, address)


class Peer:
    def __init__(self, model, address):
        self.model, self.nats, self.user = model, address[1] == 4222, None
        self.incoming = bytearray(b"INFO {}\r\n" if self.nats else b"")
        self.bad_auth = False

    def recv(self, size):
        result = bytes(self.incoming[:size])
        del self.incoming[:size]
        return result

    def settimeout(self, value):
        pass

    def close(self):
        pass

    def sendall(self, data):
        m = self.model
        if self.nats:
            line, _, rest = data.partition(b"\r\n")
            if line.startswith(b"CONNECT "):
                config = json.loads(line[8:])
                self.user = config.get("user")
                self.bad_auth = self.user not in ("writer", "reader") or config.get("pass") != m.bundle.get("nats_" + str(self.user) + "_password")
            elif line == b"PING":
                self.incoming += b"-ERR 'Authorization Violation'\r\n" if self.bad_auth else b"PONG\r\n"
            elif line.startswith(b"SUB "):
                pass
            elif line.startswith((b"PUB ", b"HPUB ")):
                subject = line.split()[1].decode()
                if self.user == "reader" and subject != "$JS.API.INFO":
                    self.incoming += b'-ERR \'Permissions Violation for Publish\'\r\n'
                    return
                if subject == "$JS.API.INFO":
                    reply = {"streams": 1 if m.stream else 0}
                elif subject.startswith("$JS.API.STREAM.INFO."):
                    reply = {"config": {"name": "LAB_STATEFUL", "subjects": ["lab.probe"], "storage": "file", "retention": "limits", "max_msgs": 1, "discard": "new"}, "state": {"messages": 1 if m.message else 0, "first_seq": 1 if m.message else 0, "last_seq": 1 if m.message else 0}} if m.stream else {"error": {"code": 404}}
                elif subject.startswith("$JS.API.STREAM.CREATE."):
                    m.stream = True
                    reply = {"config": {"name": "LAB_STATEFUL", "subjects": ["lab.probe"], "storage": "file", "retention": "limits", "max_msgs": 1, "discard": "new"}, "state": {"messages": 0, "first_seq": 0, "last_seq": 0}}
                elif subject.startswith("$JS.API.STREAM.MSG.GET."):
                    reply = {"message": {"subject": "lab.probe", "seq": 1, "data": base64.b64encode(m.message).decode()}}
                elif subject == "lab.probe":
                    m.publishes += 1
                    m.message = rest.split(b"\r\n\r\n", 1)[1][:-2]
                    reply = {"stream": "LAB_STATEFUL", "seq": 1}
                else:
                    raise AssertionError("unexpected modeled subject")
                body = json.dumps(reply).encode()
                self.incoming += b"MSG _INBOX.LAB 1 " + str(len(body)).encode() + b"\r\n" + body + b"\r\n"
            else:
                raise AssertionError("unexpected modeled NATS command")
        else:
            header, _, body = data.partition(b"\r\n\r\n")
            lines = header.decode().split("\r\n")
            method, path, _ = lines[0].split()
            headers = dict(line.split(": ", 1) for line in lines[1:])
            auth = headers.get("authorization", "")
            writer = "Credential=" + m.bundle["s3_writer_access"] + "/" in auth
            reader = "Credential=" + m.bundle["s3_reader_access"] + "/" in auth
            expected = None
            if writer or reader:
                role = "writer" if writer else "reader"
                expected = probe.sign(method, path, body, m.bundle["s3_" + role + "_access"], m.bundle["s3_" + role + "_secret"], headers["x-amz-date"])[0]["authorization"]
            code, response = 200, b""
            if auth != expected or (reader and method == "PUT"):
                code, response = 403, b"<Error><Code>AccessDenied</Code></Error>"
            elif path == "/lab-stateful":
                if method == "PUT":
                    m.bucket = True
                elif not m.bucket:
                    code = 404
            elif path.endswith("?list-type=2"):
                response = ("<ListBucketResult><IsTruncated>false</IsTruncated>" + ("<Contents><Key>" + RUN + "/sentinel.txt</Key></Contents>" if m.object else "") + "</ListBucketResult>").encode()
            elif method == "PUT":
                m.puts += 1
                m.object = body
            elif m.object is None:
                code = 404
            else:
                response = m.object
            self.incoming += ("HTTP/1.1 " + str(code) + " Result\r\nContent-Length: " + str(len(response)) + "\r\n\r\n").encode() + (b"" if method == "HEAD" else response)


class EndToEndWireTests(unittest.TestCase):
    def run_mode(self, model, mode):
        budget = probe.Budget()
        with patch.object(probe, "read_credentials", return_value=model.bundle), patch.object(probe.socket, "create_connection", side_effect=model.socket), patch.object(probe, "Budget", return_value=budget):
            code, result = probe.probe_cli(mode, RUN)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "passed")
        self.assertLessEqual(budget.events, 64)
        return result, budget.events

    def test_full_negative_transcript_and_fixture_unchanged_within_global_budget(self):
        model = LabModel()
        before = model.message, model.object
        result, events = self.run_mode(model, "deny")
        self.assertEqual((model.message, model.object), before)
        self.assertEqual((model.publishes, model.puts), (0, 0))
        self.assertTrue(all(v is True for v in result["checks"].values()))
        self.assertGreater(events, 40)

    def test_partial_seed_does_not_republish_or_overwrite(self):
        model = LabModel(False)
        self.run_mode(model, "seed")
        self.assertEqual((model.publishes, model.puts), (1, 1))
        self.run_mode(model, "seed")
        self.assertEqual((model.publishes, model.puts), (1, 1))
        model.object = None
        self.run_mode(model, "seed")
        self.assertEqual((model.publishes, model.puts), (1, 2))

    def test_unknown_empty_stream_is_not_published_into(self):
        class Client:
            def __init__(self):
                self.writes = 0
            def request(self, subject, value, message_id=None):
                if subject == "lab.probe":
                    self.writes += 1
                    raise probe.ProbeError()
                return {"config": {"name": "FOREIGN"}, "state": {"messages": 0, "last_seq": 0}}
        client = Client()
        with self.assertRaises(probe.ProbeError):
            probe.seed_nats(client, RUN)
        self.assertEqual(client.writes, 0)


if __name__ == "__main__":
    unittest.main()
