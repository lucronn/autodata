"""Executable publisher boundary and real local process tests; no cloud mutation."""
import importlib.util
import base64
import http.server
import io
import os
from pathlib import Path
import subprocess
import socket
import signal
import ssl
import stat
import sys
import tempfile
import time
import threading
import unittest
import zipfile

HERE = Path(__file__).resolve().parent
BUILDKIT_IMAGE = 'moby/buildkit@sha256:c5f8862f52499773af85bc07695b2379ef08e8002352b0df2c4864c91d78dabe'


def load():
    spec = importlib.util.spec_from_file_location('publisher_live_test', HERE / 'publisher_live.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LiveTests(unittest.TestCase):
    def require_real_docker(self, *, buildkit=False):
        # A Docker executable does not imply daemon access: the required host
        # CI runs as an unprivileged UID with all supplementary groups removed.
        # Required local validation must fail, rather than silently skip.
        probes = [('Docker daemon unavailable',['version','--format','{{.Server.Version}}']),
                  ('Buildx unavailable',['buildx','version'])]
        if buildkit:
            probes.append(('pinned BuildKit image unavailable locally',['image','inspect',BUILDKIT_IMAGE]))
        for reason,arguments in probes:
            try:
                result = subprocess.run(['/usr/bin/docker',*arguments],capture_output=True,timeout=10)
                available = result.returncode == 0
            except (OSError,subprocess.TimeoutExpired): available = False
            if not available:
                if os.environ.get('AUTODATA_REQUIRE_PUBLISHER_DOCKER') == '1': self.fail(reason)
                self.skipTest(reason)

    def buildx_owner_fixture(self, p, root):
        import hashlib
        import test_publisher_adapters
        context = test_publisher_adapters.context_fixture()
        context['run_id'] = str(int.from_bytes(os.urandom(6),'big'))
        builder = 'workshop-'+context['run_id']+'-'+str(context['run_attempt'])
        image = BUILDKIT_IMAGE
        owner = {'protocol_version':1,'context_sha256':p.a.digest(p.a.canonical(context)),
                 'builder_name':builder,'container_name':'buildx_buildkit_'+builder+'0',
                 'owner_nonce':os.urandom(32).hex(),'buildkit_image':image}
        creds = root/'credentials'; creds.mkdir(mode=0o700)
        (creds/'docker').mkdir(mode=0o700)
        p.a.private_write(creds,'buildx-owner.json',p.a.canonical(owner))
        pin = {'path':'/usr/bin/docker','version':'28.5.2',
               'sha256':hashlib.sha256(Path('/usr/bin/docker').read_bytes()).hexdigest()
                         if Path('/usr/bin/docker').is_file() else '0'*64}
        policy = {'tools':{'docker':pin,'buildkit-image':pin|{'version':image}}}
        return p.LiveDependencies(root,policy,context,{},budget=p.a.Budget()),creds,owner

    def test_real_buildx_owned_nonce_container_and_labeled_volume_cleanup(self):
        self.require_real_docker(buildkit=True)
        import unittest.mock
        p = load()
        with p.a.private_workspace() as root:
            deps,creds,owner = self.buildx_owner_fixture(p,root)
            with unittest.mock.patch.object(p,'CREDS',creds):
                try:
                    deps.create_builder(deps.context)
                    inspected = subprocess.run(['/usr/bin/docker','container','inspect',owner['container_name']],
                                               capture_output=True,check=True,timeout=10)
                    actual = p.a.strict_json(inspected.stdout)[0]
                    self.assertIn('AUTODATA_PUBLISHER_OWNER='+owner['owner_nonce'],actual['Config']['Env'])
                    self.assertEqual(actual['Config']['Image'],owner['buildkit_image'])
                    deps.budget.end = time.monotonic()-1
                    deps.cleanup()
                    remaining = subprocess.run(['/usr/bin/docker','container','ls','--all','--quiet',
                        '--filter','name=^/'+owner['container_name']+'$'],capture_output=True,check=True,timeout=10)
                    self.assertEqual(remaining.stdout,b'')
                    volumes = subprocess.run(['/usr/bin/docker','volume','ls','--quiet',
                        '--filter','name=^'+owner['container_name']+'_state$'],capture_output=True,check=True,timeout=10)
                    self.assertEqual(volumes.stdout,b'')
                finally:
                    deps.cleanup()

    def test_real_buildx_preexisting_daemon_resources_are_never_adopted_or_removed(self):
        self.require_real_docker(buildkit=True)
        import unittest.mock
        p = load()
        for collision in ('container','volume'):
            with self.subTest(collision=collision),p.a.private_workspace() as root:
                deps,creds,owner = self.buildx_owner_fixture(p,root)
                name = owner['container_name'] if collision == 'container' else owner['container_name']+'_state'
                args = (['container','create','--name',name,owner['buildkit_image']] if collision == 'container'
                        else ['volume','create',name])
                original = subprocess.run(['/usr/bin/docker',*args],capture_output=True,check=True,timeout=10).stdout.strip()
                try:
                    with unittest.mock.patch.object(p,'CREDS',creds):
                        with self.assertRaisesRegex(p.a.AdapterError,'builder_collision'): deps.create_builder(deps.context)
                        deps.cleanup()
                    observed = subprocess.run(['/usr/bin/docker',collision,'inspect',name],capture_output=True,check=True,timeout=10)
                    item = p.a.strict_json(observed.stdout)[0]
                    self.assertEqual((item['Id'] if collision == 'container' else item['Name']).encode(),original)
                finally:
                    subprocess.run(['/usr/bin/docker',collision,'rm','--force',name] if collision == 'container'
                                   else ['/usr/bin/docker','volume','rm',name],capture_output=True,check=True,timeout=10)

    def test_real_buildx_failed_creation_retains_owner_for_cleanup(self):
        self.require_real_docker(buildkit=True)
        import unittest.mock
        p = load()
        for phase in ('volume','bootstrap'):
            with self.subTest(phase=phase),p.a.private_workspace() as root:
                deps,creds,owner = self.buildx_owner_fixture(p,root)
                original = deps.tools.run
                def lose_create_reply(tool, arguments, **kwargs):
                    result = original(tool,arguments,**kwargs)
                    if (phase == 'volume' and arguments[:2] == ['volume','create'] or
                        phase == 'bootstrap' and arguments[:3] == ['buildx','inspect','--bootstrap']):
                        raise p.a.AdapterError('operation_failed')
                    return result
                with unittest.mock.patch.object(p,'CREDS',creds):
                    try:
                        with unittest.mock.patch.object(deps.tools,'run',lose_create_reply):
                            with self.assertRaisesRegex(p.a.AdapterError,'operation_failed'): deps.create_builder(deps.context)
                        deps.cleanup()
                        for kind,name in (('container',owner['container_name']),('volume',owner['container_name']+'_state')):
                            observed = subprocess.run(['/usr/bin/docker',kind,'ls','--quiet','--filter',
                                        'name=^'+('/' if kind == 'container' else '')+name+'$'],
                                        capture_output=True,check=True,timeout=10)
                            self.assertEqual(observed.stdout,b'')
                    finally: deps.cleanup()

    def test_real_buildx_cleanup_refuses_replacement_container_with_wrong_nonce(self):
        self.require_real_docker(buildkit=True)
        import unittest.mock
        p = load()
        with p.a.private_workspace() as root:
            deps,creds,owner = self.buildx_owner_fixture(p,root)
            replacement = None
            with unittest.mock.patch.object(p,'CREDS',creds):
                try:
                    deps.create_builder(deps.context)
                    actual = deps.owned_builder_container(owner)
                    subprocess.run(['/usr/bin/docker','container','rm','--force',actual],capture_output=True,check=True,timeout=10)
                    replacement = subprocess.run(['/usr/bin/docker','container','create','--name',owner['container_name'],
                        '--env','AUTODATA_PUBLISHER_OWNER='+'0'*64,owner['buildkit_image']],
                        capture_output=True,check=True,timeout=10).stdout.strip().decode()
                    with self.assertRaisesRegex(p.a.AdapterError,'builder_ownership'): deps.cleanup()
                    observed = subprocess.run(['/usr/bin/docker','container','inspect',replacement],capture_output=True,check=True,timeout=10)
                    self.assertEqual(p.a.strict_json(observed.stdout)[0]['Id'],replacement)
                finally:
                    if replacement is not None:
                        subprocess.run(['/usr/bin/docker','container','rm','--force',replacement],capture_output=True,check=True,timeout=10)
                    deps.cleanup()

    def test_real_buildx_cleanup_refuses_replacement_volume_without_owner_label(self):
        self.require_real_docker(buildkit=True)
        import unittest.mock
        p = load()
        with p.a.private_workspace() as root:
            deps,creds,owner = self.buildx_owner_fixture(p,root)
            volume = owner['container_name']+'_state'
            replacement = False
            with unittest.mock.patch.object(p,'CREDS',creds):
                try:
                    deps.create_builder(deps.context)
                    identity = deps.owned_builder_container(owner)
                    subprocess.run(['/usr/bin/docker','container','rm','--force',identity],capture_output=True,check=True,timeout=10)
                    subprocess.run(['/usr/bin/docker','volume','rm',volume],capture_output=True,check=True,timeout=10)
                    subprocess.run(['/usr/bin/docker','volume','create',volume],capture_output=True,check=True,timeout=10)
                    replacement = True
                    with self.assertRaisesRegex(p.a.AdapterError,'builder_ownership'): deps.cleanup()
                    observed = subprocess.run(['/usr/bin/docker','volume','inspect',volume],capture_output=True,check=True,timeout=10)
                    self.assertEqual(p.a.strict_json(observed.stdout)[0]['Name'],volume)
                finally:
                    if replacement:
                        subprocess.run(['/usr/bin/docker','volume','rm',volume],capture_output=True,check=True,timeout=10)
                    deps.cleanup()

    def test_buildx_changed_owner_record_denies_before_daemon_mutation(self):
        import unittest.mock
        p = load()
        with p.a.private_workspace() as root:
            deps,creds,owner = self.buildx_owner_fixture(p,root)
            (creds/'buildx-owner.json').unlink()
            p.a.private_write(creds,'buildx-owner.json',p.a.canonical(owner|{'context_sha256':'f'*64}))
            with unittest.mock.patch.object(p,'CREDS',creds),unittest.mock.patch.object(
                    deps.tools,'run',side_effect=AssertionError('daemon contacted before owner validation')):
                with self.assertRaisesRegex(p.a.AdapterError,'builder_ownership'): deps.create_builder(deps.context)

    def test_unresolved_runtime_fields_fail_before_trust_tokens_or_processes(self):
        import unittest.mock
        import test_host_runtime
        import test_publisher_adapters
        fixture = test_host_runtime.ContractTests(); fixture.setUp()
        try: config = fixture.config
        finally: fixture.doCleanups()
        p = load()
        context = test_publisher_adapters.context_fixture()
        context['service_config_sha256'] = p.a.digest(p.a.canonical(config))
        resources = config['resources']
        runtime = {'project_id':resources['host_project_id'],'region':resources['region'],'zone':resources['zone'],
                   'maximum_monthly_budget_usd':20,'staging_origin':config['public_origin'],
                   'wif_provider':'projects/123456/locations/global/workloadIdentityPools/staging/providers/github',
                   'publisher_service_account':'publisher@autodata-host.iam.gserviceaccount.com',
                   'registry':resources['artifact_repository'],
                   'toolchain_image_digest':'registry.example/toolchain@sha256:'+'a'*64}
        p.runtime_config(runtime,config)
        with p.a.private_workspace() as root:
            p.a.private_write(root,'context.json',p.a.canonical(context))
            p.a.private_write(root,'config.json',p.a.canonical(config))
            with unittest.mock.patch.object(p,'INPUT',root), unittest.mock.patch.object(p,'OUTPUT',root/'output'), \
                 unittest.mock.patch.object(p,'bridge',side_effect=AssertionError('trust process before resolved config')), \
                 unittest.mock.patch.object(p,'credentials',side_effect=AssertionError('credential read before resolved config')):
                for key in p.RUNTIME_FIELDS:
                    with self.subTest(field=key):
                        path = root/'runtime.json'
                        if path.exists(): path.unlink()
                        p.a.private_write(root,'runtime.json',p.a.canonical(runtime|{key:None}))
                        with self.assertRaises(p.a.AdapterError): p.execute('staging-build-candidate',context['source_sha'])
                        self.assertFalse((root/'output').exists())

    def test_sigint_popen_assignment_race_and_repeated_cleanup_cancel(self):
        import unittest.mock
        p = load()
        spec = importlib.util.spec_from_file_location('publisher_cli_signal_test',HERE/'publisher_cli.py')
        cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)
        interrupt = cli._forward_interrupt
        children = []; second = None
        original = subprocess.Popen
        def stop(signum, frame): raise p.a.AdapterError('operation_cancelled')
        old_term = signal.signal(signal.SIGTERM,stop)
        old_int = signal.signal(signal.SIGINT,interrupt)
        def launch(*args, **kwargs):
            nonlocal second
            child = original(*args, **kwargs); children.append(child)
            self.assertEqual(child.stdout.readline(),b'ready\n')
            # The real child exists, but bounded_process has not received its
            # Popen result. A raising SIGINT handler leaks this child.
            os.kill(os.getpid(),signal.SIGINT)
            def again():
                time.sleep(.1); os.kill(os.getpid(),signal.SIGINT)
            second = threading.Thread(target=again); second.start()
            return child
        try:
            with p.a.private_workspace() as root, unittest.mock.patch.object(p.a.subprocess,'Popen',launch):
                with self.assertRaisesRegex(p.a.AdapterError,'operation_cancelled'):
                    p.a.bounded_process([sys.executable,'-u','-c',
                        'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);print("ready");time.sleep(30)'],
                        cwd=root,deadline=time.monotonic()+10)
            self.assertEqual(len(children),1)
            self.assertIsNotNone(children[0].poll())
            self.assertFalse(p.a._process_owner)
        finally:
            if second is not None: second.join(timeout=3)
            for child in children:
                if child.poll() is None:
                    os.killpg(child.pid,signal.SIGKILL); child.wait(timeout=3)
            signal.signal(signal.SIGINT,old_int); signal.signal(signal.SIGTERM,old_term)

    def test_real_buildx_metadata_explicit0644_is_adopted_privately(self):
        self.require_real_docker()
        p = load()
        with p.a.private_workspace() as root:
            source = root/'source'; source.mkdir(mode=0o700)
            (source/'Dockerfile').write_text('FROM scratch\nLABEL review=metadata-mode\n')
            metadata = root/'metadata.json'
            result = subprocess.run(['/usr/bin/docker','buildx','build','--metadata-file',str(metadata),
                                     '--output','type=cacheonly',str(source)], capture_output=True,
                                    timeout=60, umask=0o077)
            self.assertEqual(result.returncode, 0, result.stderr.decode()[-2000:])
            self.assertEqual(stat.S_IMODE(metadata.stat().st_mode), 0o644)
            original = metadata.read_bytes()
            with self.assertRaises(p.a.AdapterError): p.a.private_read(root,'metadata.json',p.a.MiB)
            value = p.read_tool_json(root,'metadata.json')
            self.assertEqual(value,p.a.strict_json(original))
            self.assertEqual(metadata.read_bytes(),original)
            self.assertEqual(stat.S_IMODE(metadata.stat().st_mode),0o600)

    def test_tool_metadata_adoption_rejects_links_writable_and_oversized_output(self):
        p = load()
        with p.a.private_workspace() as root:
            path = p.a.private_write(root,'metadata.json',b'{}')
            os.symlink(path,root/'alias.json')
            with self.assertRaises(p.a.AdapterError): p.read_tool_json(root,'alias.json')
            os.link(path,root/'linked.json')
            with self.assertRaises(p.a.AdapterError): p.read_tool_json(root,'metadata.json')
            (root/'linked.json').unlink()
            path.chmod(0o666)
            with self.assertRaises(p.a.AdapterError): p.read_tool_json(root,'metadata.json')
            path.chmod(0o644)
            with self.assertRaises(p.a.AdapterError): p.read_tool_json(root,'metadata.json',1)

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
