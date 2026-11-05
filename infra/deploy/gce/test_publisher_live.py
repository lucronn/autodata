"""Executable publisher boundary and real local process tests; no cloud mutation."""
import importlib.util
import base64
import http.server
import io
import os
from pathlib import Path
import subprocess
import socket
import ssl
import sys
import tempfile
import time
import threading
import unittest
import zipfile

HERE = Path(__file__).resolve().parent


def load():
    spec = importlib.util.spec_from_file_location('publisher_live_test', HERE / 'publisher_live.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LiveTests(unittest.TestCase):
    def test_cli_rejects_flags_urls_and_missing_source_without_credentials(self):
        for args in ([], ['staging-build-candidate'], ['verify-publication', 'https://evil.example'],
                     ['staging-finalize', 'a'*40, '--command', 'id'], ['production', 'a'*40]):
            result = subprocess.run([sys.executable, '-I', str(HERE/'publisher_cli.py'), *args],
                                    capture_output=True, timeout=5,
                                    env={'PATH': '/usr/bin:/bin', 'GITHUB_TOKEN': 'secret-sentinel'})
            self.assertEqual(result.returncode, 2)
            self.assertNotIn(b'secret-sentinel', result.stdout + result.stderr)

    def test_import_performs_no_process_or_credential_discovery(self):
        import unittest.mock
        with unittest.mock.patch('subprocess.Popen', side_effect=AssertionError('import process')):
            module = load()
        self.assertEqual(str(module.INPUT), '/run/autodata-publisher/input')

    def test_private_input_rejects_symlink_hardlink_and_duplicate_json(self):
        p = load()
        with p.a.private_workspace() as root:
            p.a.private_write(root, 'config.json', b'{"x":1,"x":2}')
            with self.assertRaises(p.a.AdapterError): p.read_json(root, 'config.json')
            os.symlink(root/'config.json', root/'alias.json')
            with self.assertRaises(p.a.AdapterError): p.read_json(root, 'alias.json')
            os.link(root/'config.json', root/'linked.json')
            with self.assertRaises(p.a.AdapterError): p.read_json(root, 'config.json')

    def test_process_uses_pin_and_redacts_errors(self):
        p = load()
        binary = Path('/usr/bin/printf').resolve()
        pin = {'path': str(binary), 'sha256': p.a.digest(binary.read_bytes()), 'version': 'test'}
        with p.a.private_workspace() as root:
            runner = p.ToolRunner({'printf': pin}, root, p.a.Budget(60))
            self.assertEqual(runner.run('printf', ['hello']), b'hello')
            with self.assertRaises(p.a.AdapterError): runner.run('printf', ['%Y', 'credential-sentinel'])
            pin['sha256'] = '0'*64
            with self.assertRaises(p.a.AdapterError): runner.run('printf', ['hello'])

    def test_real_process_deadline_and_output_bound(self):
        p = load()
        with p.a.private_workspace() as root:
            with self.assertRaises(p.a.AdapterError):
                p.a.bounded_process([sys.executable, '-c', 'import time;time.sleep(10)'],
                                    cwd=root, deadline=time.monotonic()+.1)
            with self.assertRaises(p.a.AdapterError):
                p.a.bounded_process([sys.executable, '-c', 'print("x"*10000)'],
                                    cwd=root, deadline=time.monotonic()+3, maximum=100)

    def test_missing_inputs_cli_returns_redacted_failure(self):
        result = subprocess.run([sys.executable, '-I', str(HERE/'publisher_cli.py'),
                                 'staging-build-candidate', 'a'*40], capture_output=True, timeout=5,
                                env={'PATH':'/usr/bin:/bin', 'GITHUB_TOKEN':'secret-sentinel'})
        self.assertEqual(result.returncode, 3)
        self.assertNotIn(b'secret-sentinel', result.stdout+result.stderr)
        self.assertIn(b'"deployment_authorized":false', result.stderr)

    def test_real_tls_rest_redirect_raw_zip_and_credential_separation(self):
        p = load()
        inner = b'original release archive bytes'
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive: archive.writestr('release.zip', inner)
        outer = output.getvalue()
        received = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                received.append((self.path, self.headers.get('Authorization')))
                if self.path.endswith('/zip'):
                    self.send_response(302)
                    self.send_header('Location', 'https://storage.example/original?signature=bounded')
                    self.end_headers()
                else:
                    self.send_response(200); self.send_header('Content-Length', str(len(outer)))
                    self.end_headers(); self.wfile.write(outer)
            def log_message(self, *args): pass

        # Test-only socket routing preserves the production public-peer check,
        # while exercising an actual local TLS handshake, certificate signature,
        # HTTP headers, redirect, complete bytes and exact ZIP parser.
        class LocalSocket(socket.socket):
            def getpeername(self): return ('93.184.216.34', 443)

        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            cert, key = root/'ca.pem', root/'key.pem'
            subprocess.run(['/usr/bin/openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                            '-subj','/CN=api.github.com','-addext','subjectAltName=DNS:api.github.com,DNS:storage.example',
                            '-keyout',str(key),'-out',str(cert)], check=True, capture_output=True, timeout=10)
            server = http.server.ThreadingHTTPServer(('127.0.0.1',0), Handler)
            tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); tls.load_cert_chain(cert,key)
            server.socket = tls.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            def connect(peer, timeout):
                sock = LocalSocket(); sock.settimeout(timeout); sock.connect(server.server_address); return sock
            try:
                transport = p.a.PinnedHTTPS(str(cert), lambda host, deadline:['93.184.216.34'], connect_factory=connect)
                actual = p.a.download_actions_outer(transport, '123', 'rest-sentinel', ['storage.example'],
                                                    deadline=time.monotonic()+5)
                self.assertEqual(actual, outer)
                self.assertEqual(p.a.decode_actions_outer_zip(actual, p.a.digest(inner),len(inner)),inner)
                self.assertEqual(received, [('/repos/lucronn/autodata/actions/artifacts/123/zip','Bearer rest-sentinel'),
                                            ('/original?signature=bounded',None)])
                with self.assertRaises(p.a.AdapterError):
                    transport.get('https://storage.example/x', origins={'storage.example'},
                             deadline=time.monotonic()+5, maximum=100, token='rest-sentinel')
                with self.assertRaises(p.a.AdapterError):
                    transport.get('https://storage.example/x', origins={'storage.example'},
                             deadline=time.monotonic()+5, maximum=3)
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=3)

    def test_real_signed_certificate_exact_run_extensions(self):
        p = load()
        context = {'workflow_ref':p.a.WORKFLOW, 'workflow_sha':'d'*40,'run_id':'42','run_attempt':2}
        expected = {'run_invocation_uri':'https://github.com/lucronn/autodata/actions/runs/42/attempts/2',
                    'workflow_ref':p.a.WORKFLOW,'workflow_sha':'d'*40}
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); cert, key = root/'certificate.pem', root/'key.pem'
            args = ['/usr/bin/openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                    '-subj','/CN=test-only-issuer','-keyout',str(key),'-out',str(cert)]
            for number, value in ((8,'https://token.actions.githubusercontent.com'),
                                  (18,'https://github.com/'+p.a.WORKFLOW), (19,'d'*40),
                                  (21,expected['run_invocation_uri'])):
                args += ['-addext','1.3.6.1.4.1.57264.1.'+str(number)+'=ASN1:UTF8String:'+value]
            subprocess.run(args, check=True,capture_output=True,timeout=10)
            subprocess.run(['/usr/bin/openssl','verify','-CAfile',str(cert),str(cert)],
                           check=True,capture_output=True,timeout=5)
            raw = subprocess.run(['/usr/bin/openssl','x509','-in',str(cert),'-outform','DER'],
                                 check=True,capture_output=True,timeout=5).stdout
            bundle = {'verificationMaterial':{'certificate':{'rawBytes':base64.b64encode(raw).decode()}}}
            self.assertEqual(p.certificate_identity(bundle, context), expected)
            for changed in (dict(context,run_attempt=1),dict(context,workflow_sha='e'*40),dict(context,run_id='43')):
                with self.assertRaises(p.a.AdapterError): p.certificate_identity(bundle,changed)

    def test_real_registry_download_file_limit_and_stream_cleanup(self):
        p = load()
        # A real accepted test executable writes bytes as ORAS would. The
        # process file-size limit must bound disk output independently of stdout.
        with p.a.private_workspace() as root:
            executable = p.a.private_write(root,'oras-test',
                b'#!/usr/bin/python3\nimport sys\np=sys.argv[sys.argv.index("--output")+1]\nopen(p,"wb").write(b"x"*(5*1048576))\n')
            executable.chmod(0o700)
            pin = {'path':str(executable),'sha256':p.a.digest(executable.read_bytes()),'version':'test'}
            deps = p.LiveDependencies(root, {'tools':{'oras':pin}}, {key:None for key in p.a.CONTEXT_FIELDS}, {})
            with p.a.private_workspace() as files:
                with self.assertRaises(p.a.AdapterError):
                    deps._registry_file('registry.example/repo@sha256:'+'a'*64,'blobs','sha256:'+'b'*64,files,1024)
                self.assertLessEqual((files/'object').stat().st_size,1024)
            stream = deps._layer_stream('registry.example/repo@sha256:'+'a'*64,'sha256:'+'b'*64,5*p.a.MiB)
            self.assertEqual(len(next(stream)),p.a.MiB)
            stream.close()

    def test_image_evidence_rejects_different_source_and_empty_inventory(self):
        p = load()
        provenance = {'buildType':'https://mobyproject.org/buildkit@v1',
                      'invocation':{'configSource':{'uri':'https://github.com/lucronn/autodata.git',
                                                    'digest':{'sha1':'a'*40},'entryPoint':'apps/api-go/Dockerfile'}}}
        p.image_predicate('provenance',provenance,'api','a'*40)
        with self.assertRaises(p.a.AdapterError): p.image_predicate('provenance',provenance,'api','b'*40)
        with self.assertRaises(p.a.AdapterError): p.image_predicate('sbom',{'spdxVersion':'SPDX-2.3','packages':[]},'api','a'*40)

    def test_local_context_uses_actual_buildkit_vcs_metadata(self):
        p = load()
        predicate = {'buildType':'https://mobyproject.org/buildkit@v1',
                     'invocation':{'configSource':{'entryPoint':'Dockerfile'}},
                     'metadata':{'https://mobyproject.org/buildkit@v1#metadata':{
                         'vcs':{'source':'https://github.com/lucronn/autodata.git','revision':'a'*40}}}}
        p.image_predicate('provenance',predicate,'api','a'*40)
        predicate['metadata']['https://mobyproject.org/buildkit@v1#metadata']['vcs']['revision'] += '-dirty'
        with self.assertRaises(p.a.AdapterError): p.image_predicate('provenance',predicate,'api','a'*40)


if __name__ == '__main__': unittest.main()
