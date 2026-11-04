"""Offline authenticated-v3 boundary tests. No provider credentials or network."""
import hashlib
import importlib.util
import io
from pathlib import Path
import unittest
import zipfile

HERE = Path(__file__).resolve().parent


def load():
    path = HERE / 'publisher_adapters.py'
    if not path.exists(): return None
    spec = importlib.util.spec_from_file_location('publisher_adapters', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def context_fixture():
    return {'protocol_version': 3, 'environment': 'staging', 'repository': 'lucronn/autodata',
            'repository_id': '123456', 'repository_owner_id': '987654', 'run_id': '42', 'run_attempt': 2,
            'workflow_ref': 'lucronn/autodata/.github/workflows/release-workshop.yml@refs/heads/master',
            'workflow_sha': 'd' * 40, 'source_sha': 'a' * 40, 'service_config_sha256': 'b' * 64,
            'protected_environment': 'workshop-staging-publish', 'activation_sha256': 'c' * 64,
            'toolchain_sha256': 'e' * 64, 'trust_policy_sha256': 'f' * 64}


def run_fixture(context):
    return {'id': int(context['run_id']), 'run_attempt': context['run_attempt'], 'event': 'workflow_dispatch',
            'head_branch': 'master', 'head_sha': context['workflow_sha'], 'path': '.github/workflows/release-workshop.yml',
            'status': 'completed', 'conclusion': 'success',
            'repository': {'id': int(context['repository_id']), 'full_name': context['repository'],
                           'owner': {'id': int(context['repository_owner_id'])}},
            'run_started_at': '2026-11-03T12:00:00Z', 'updated_at': '2026-11-03T12:05:00Z'}


class BoundaryTests(unittest.TestCase):
    def setUp(self): self.p = load()

    def needed(self):
        self.assertIsNotNone(self.p, 'authenticated adapter library is missing')
        return self.p

    def test_strict_wire_rejects_duplicates_depth_and_nonfinite(self):
        p = self.needed()
        for data in (b'{"x":1,"x":2}', b'{"x":NaN}', b'[' * 33 + b'0' + b']' * 33):
            with self.subTest(data=data[:20]), self.assertRaises(p.AdapterError): p.strict_json(data)
        self.assertEqual(p.strict_json(b'{"x":true}'), {'x': True})

    def test_outer_envelope_returns_original_inner_and_denies_aliases(self):
        p = self.needed()
        inner = b'PK inner bytes'
        for method in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            out = io.BytesIO()
            with zipfile.ZipFile(out, 'w', compression=method) as archive: archive.writestr('release.zip', inner)
            data = out.getvalue()
            self.assertEqual(p.decode_actions_outer_zip(data, hashlib.sha256(inner).hexdigest(), len(inner)), inner)
            self.assertNotEqual(hashlib.sha256(data).hexdigest(), hashlib.sha256(inner).hexdigest())
            for bad in (b'prefix' + data, data + b'trailer', data.replace(b'release.zip', b'release.zap')):
                with self.assertRaises(p.AdapterError): p.decode_actions_outer_zip(bad, hashlib.sha256(inner).hexdigest(), len(inner))

    def test_context_separates_workflow_source_and_attempt(self):
        p = self.needed()
        context = context_fixture()
        self.assertEqual(p.validate_context(context), context)
        run = run_fixture(context)
        p.validate_run(run, context, completed=True)
        for key, value in [('head_sha', context['source_sha']), ('run_attempt', True), ('event', 'push')]:
            with self.assertRaises(p.AdapterError): p.validate_run(dict(run, **{key: value}), context, completed=True)

    def test_url_policy_rejects_ambiguous_and_private_destinations(self):
        p = self.needed()
        for url in ('http://api.github.com/x', 'https://api.github.com:444/x', 'https://user@api.github.com/x',
                    'https://127.0.0.1/x', 'https://api.github.com/x#frag', 'https://api.github.com\\@evil.example/x'):
            with self.assertRaises(p.AdapterError): p.validate_url(url, {'api.github.com'})
        self.assertEqual(p.validate_url('https://api.github.com/x', {'api.github.com'}).hostname, 'api.github.com')

    def test_missing_owner_policy_fails_before_dependencies(self):
        p = self.needed()
        calls = []
        with self.assertRaises(p.AdapterError):
            p.build_authenticated_candidate({}, {}, context_fixture(), {}, dependencies=lambda: calls.append(1))
        self.assertEqual(calls, [])


if __name__ == '__main__': unittest.main()

class ExecutionTests(unittest.TestCase):
    def setUp(self): self.p = load()

    def test_process_bounds_and_private_output_reject_links(self):
        import os
        import time
        with self.p.private_workspace() as directory:
            path = self.p.private_write(directory, 'output.json', b'{}')
            self.assertEqual(self.p.private_read(directory, path.name, 10), b'{}')
            os.link(path, directory / 'alias')
            with self.assertRaises(self.p.AdapterError): self.p.private_read(directory, path.name, 10)
            code, out, err = self.p.bounded_process(['/usr/bin/python3', '-c', 'print("ok")'], cwd=directory,
                                                   deadline=time.monotonic() + 3)
            self.assertEqual((code, out, err), (0, b'ok\n', b''))
            with self.assertRaises(self.p.AdapterError):
                self.p.bounded_process(['/usr/bin/python3', '-c', 'print("x"*2000)'], cwd=directory,
                                       deadline=time.monotonic() + 3, maximum=100)
            with self.assertRaises(self.p.AdapterError):
                self.p.bounded_process(['/usr/bin/python3', '-c', 'import time; time.sleep(10)'], cwd=directory,
                                       deadline=time.monotonic() + .1)

    def test_build_argv_pins_migration_base_and_source_epoch(self):
        for role in ('api', 'ingestion', 'migration'):
            self.assertTrue(hasattr(self.p, 'build_argv'), 'fixed build argv missing')
            argv = self.p.build_argv(role, '/usr/bin/docker', '/work/source', 'staging.example/repo',
                                     context_fixture(), 123, 'docker.io/library/postgres@sha256:' + 'b' * 64,
                                     'workshop-42-2')
            self.assertIn('--platform=linux/amd64', argv)
            self.assertIn('SOURCE_DATE_EPOCH=123', argv)
            if role == 'migration':
                position = argv.index('--file')
                self.assertEqual(argv[position-2:position], ['--build-arg', 'POSTGRES_IMAGE=docker.io/library/postgres@sha256:' + 'b' * 64])
            self.assertIn('--provenance=mode=max', argv)
            self.assertIn('--sbom=true', argv)

    def test_registry_verifies_actual_index_manifest_and_config_chain(self):
        p = self.p
        self.assertTrue(hasattr(p, 'verify_registry_image'), 'registry verifier missing')
        config = p.canonical({'architecture': 'amd64', 'os': 'linux'})
        manifest = p.canonical({'schemaVersion': 2, 'mediaType': 'application/vnd.oci.image.manifest.v1+json',
                               'config': {'digest': 'sha256:' + p.digest(config), 'size': len(config)}, 'layers': []})
        objects = {'sha256:' + p.digest(config): config, 'sha256:' + p.digest(manifest): manifest}
        result = p.verify_registry_image('registry.example/repo/api@sha256:' + p.digest(manifest),
                                         lambda reference, kind, value: objects[value])
        self.assertEqual(result['image_id'], 'sha256:' + p.digest(config))
        bad = dict(objects); bad['sha256:' + p.digest(config)] = p.canonical({'architecture': 'arm64', 'os': 'linux'})
        with self.assertRaises(p.AdapterError):
            p.verify_registry_image('registry.example/repo/api@sha256:' + p.digest(manifest), lambda r,k,v: bad[v])
