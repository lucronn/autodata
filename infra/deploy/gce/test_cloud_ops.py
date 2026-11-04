"""Offline B boundary tests: all provider events are finite fake transcripts."""
import copy
import binascii
import struct
import zipfile
import zlib
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
import random
import socket
import subprocess
import tarfile
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import test_host_runtime as host_test

HERE = Path(__file__).resolve().parent
RUN = '12345678-1234-4234-8234-123456789abc'
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)


def load_ops():
    path = HERE / 'cloud-ops.py'
    if not path.is_file():
        raise AssertionError('offline cloud operation definitions are missing')
    spec = importlib.util.spec_from_file_location('cloud_ops', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CloudTests(unittest.TestCase):
    def setUp(self):
        # Shared reviewed A fixtures retain their literal config/image contract.
        fixture = host_test.ContractTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.rt, self.config, self.manifest = fixture.rt, fixture.config, fixture.manifest
        self.ops = load_ops()
        self.rt = self.ops.rt
        self.policy = {'repository': 'lucronn/autodata', 'repository_id': '123456',
                       'repository_owner_id': '987654', 'environment': 'staging',
                       'ref': 'refs/heads/release-reviewed',
                       'workflow_ref': 'lucronn/autodata/.github/workflows/backup-workshop.yml@refs/heads/release-reviewed'}
        self.claims = dict(self.policy)
        self.dump = b'PGDMP synthetic offline dump'
        self.dump_hash = hashlib.sha256(self.dump).hexdigest()
        self.base = {'state': 'quiesced', 'lease_expires_at': '2026-11-03T12:25:00Z',
                     'dump_sha256': self.dump_hash, 'dump_bytes': len(self.dump),
                     'manifest_sha256': self.rt.sha256(self.manifest),
                     'disk_uuid': self.config['resources']['data_disk_filesystem_uuid']}
        self.begin = self.host('begin', 'quiesced')
        self.resumed = self.host('resume', 'resumed')
        self.status = self.host('status', 'resumed')
        self.disk = 'https://www.googleapis.com/compute/v1/projects/autodata-host/zones/us-central1-a/disks/workshop-data'
        self.snapshot = {'self_link': 'https://www.googleapis.com/compute/v1/projects/autodata-backup/global/snapshots/autodata-' + RUN,
                         'operation': 'https://www.googleapis.com/compute/v1/projects/autodata-backup/global/operations/op-123',
                         'source_disk': self.disk, 'status': 'READY',
                         'cutoff_at': '2026-11-03T12:01:00Z', 'completed_at': '2026-11-03T12:02:00Z'}
        self.archive = self.tar()
        self.upload = {name: {'bucket': 'autodata-private-backup', 'name': RUN + '/' + name, 'generation': str(100 + i), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
                       for i, (name, data) in enumerate(self.members())}
        self.events = {'begin': self.begin, 'snapshot': self.snapshot, 'resume': self.resumed,
                       'status': self.status, 'export': self.archive, 'upload': self.upload, 'cleanup': True}

    def host(self, verb, state):
        result = self.rt.operation_receipt('backup-host.sh ' + verb, self.manifest['source_sha'], RUN,
                                          0, {'services': True, 'no_work': True})
        result.update(self.base, state=state)
        result.update(started_at='2026-11-03T12:00:00Z' if verb == 'begin' else '2026-11-03T12:03:00Z',
                      finished_at='2026-11-03T12:00:00Z' if verb == 'begin' else '2026-11-03T12:03:00Z')
        if state == 'resumed': result.update(writers_resumed=True, stateful_resumed=True)
        return result

    def members(self):
        return [('postgres.dump', self.dump), ('release.json', self.rt.canonical_bytes(self.manifest)),
                ('backup.json', self.rt.canonical_bytes(self.status))]

    def tar(self, extra=None):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w', format=tarfile.USTAR_FORMAT) as archive:
            for name, data in self.members() + (extra or []):
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        return buffer.getvalue()

    def evaluate(self, events=None):
        calls = []
        transcript = copy.deepcopy(self.events if events is None else events)
        def fake_cli(step):
            calls.append(step)
            value = transcript[step['name']]
            if isinstance(value, Exception): raise value
            return value
        result = self.ops.evaluate_backup(self.manifest, self.config, RUN, self.policy, self.claims,
                                          fake_cli, now=NOW)
        return result, calls

    def published_fixture(self):
        payload = self.rt.canonical_bytes(self.manifest)
        binding = {'published_run_id': '1234', 'artifact_id': '5678',
                   'artifact_digest': 'sha256:' + hashlib.sha256(payload).hexdigest(),
                   'manifest_sha256': hashlib.sha256(payload).hexdigest()}
        policy = dict(self.policy, workflow_ref='lucronn/autodata/.github/workflows/release-workshop.yml@refs/heads/release-reviewed')
        transcript = {
            'run': {'id': '1234', 'repository': 'lucronn/autodata',
                    'source_sha': self.manifest['source_sha'], 'workflow_ref': policy['workflow_ref'],
                    'event': 'workflow_dispatch', 'status': 'completed', 'conclusion': 'success'},
            'artifact': {'id': '5678', 'run_id': '1234', 'name': 'workshop-release-' + self.manifest['source_sha'],
                         'expired': False, 'digest': binding['artifact_digest'], 'bytes': len(payload)},
            'manifest': payload,
            'images': {role: dict(image, platform='linux/amd64') for role, image in self.manifest['images'].items()}}
        return binding, policy, transcript

    def published(self, transcript=None, binding=None):
        default_binding, policy, default_transcript = self.published_fixture()
        transcript = default_transcript if transcript is None else transcript
        calls = []
        def fake_cli(step):
            calls.append(step)
            value = transcript[step['name']]
            if isinstance(value, Exception): raise value
            return value
        self.assertTrue(hasattr(self.ops, 'evaluate_published_release'), 'published transcript verifier is missing')
        result = self.ops.evaluate_published_release(self.manifest, self.config,
                                                     default_binding if binding is None else binding,
                                                     policy, dict(policy), fake_cli)
        return result, calls

    def test_published_transcript_binds_exact_ids_bytes_and_images_without_authorizing_deploy(self):
        result, calls = self.published()
        self.assertEqual(result['status'], 'transcript_consistent')
        self.assertTrue(result['simulation'])
        self.assertFalse(result['deployment_authorized'])
        self.assertNotIn('passed', result)
        self.assertEqual(result['consistent_binding'], self.published_fixture()[0])
        self.assertEqual([step['name'] for step in calls], ['run', 'artifact', 'manifest', 'images'])
        self.assertTrue(all(not step['argv'] for step in calls))
        self.assertLessEqual(sum(step['timeout_seconds'] for step in calls), 2700)
        self.assertLessEqual(len(self.rt.canonical_bytes(result)), 65536)

    def test_published_transcript_rejects_wrong_missing_extra_expired_and_ambiguous_metadata(self):
        mutations = [lambda x: x['run'].update(id='9999'),
                     lambda x: x['run'].update(repository='attacker/autodata'),
                     lambda x: x['run'].update(source_sha='d' * 40),
                     lambda x: x['run'].update(workflow_ref='wrong'),
                     lambda x: x['run'].update(event='pull_request'),
                     lambda x: x['run'].update(status='in_progress'),
                     lambda x: x['run'].update(conclusion='failure'),
                     lambda x: x['run'].update(extra='FAKE_SECRET'),
                     lambda x: x['artifact'].update(id='9999'),
                     lambda x: x['artifact'].update(run_id='9999'),
                     lambda x: x['artifact'].update(name='latest'),
                     lambda x: x['artifact'].update(expired=True),
                     lambda x: x['artifact'].update(expired=0),
                     lambda x: x['artifact'].update(bytes=True),
                     lambda x: x['artifact'].pop('digest'),
                     lambda x: x['artifact'].update(digest='sha256:' + '0' * 64),
                     lambda x: x['artifact'].update(bytes=1048577),
                     lambda x: x['artifact'].update(extra='FAKE_SECRET'),
                     lambda x: x['images'].pop('api'),
                     lambda x: x['images'].update(extra={})]
        for mutate in mutations:
            _, _, transcript = self.published_fixture(); mutate(transcript)
            result, _ = self.published(transcript)
            self.assertEqual(result['status'], 'failed')
            self.assertIsNone(result['consistent_binding'])
            self.assertFalse(result['deployment_authorized'])
            self.assertNotIn('FAKE_SECRET', str(result))

    def test_published_transcript_rejects_corrupt_or_type_drifted_manifest_and_image_evidence(self):
        for payload in (b'{}', b'FAKE_SECRET', b'x' * (1048576 + 1),
                        self.rt.canonical_bytes(self.manifest)[:-1] + b' '):
            _, _, transcript = self.published_fixture(); transcript['manifest'] = payload
            result, _ = self.published(transcript)
            self.assertEqual(result['status'], 'failed')
        for field, value in [('platform', 'linux/arm64'), ('reference', 'tag:latest'),
                             ('image_id', 'sha256:' + '0' * 64), ('sbom_uri', 'https://wrong'),
                             ('provenance_uri', 'https://wrong'), ('extra', 'FAKE_SECRET')]:
            _, _, transcript = self.published_fixture(); transcript['images']['api'][field] = value
            result, _ = self.published(transcript)
            self.assertEqual(result['status'], 'failed')
            self.assertIsNone(result['consistent_binding'])
        # Rebind the raw digest to the tampered bytes, retaining the approved
        # canonical manifest hash: JSON true must not collapse into integer 1.
        binding, _, transcript = self.published_fixture()
        candidate = copy.deepcopy(self.manifest); candidate['schema_version'] = True
        payload = self.rt.canonical_bytes(candidate)
        binding['artifact_digest'] = 'sha256:' + hashlib.sha256(payload).hexdigest()
        transcript['manifest'] = payload
        transcript['artifact'].update(digest=binding['artifact_digest'], bytes=len(payload))
        result, _ = self.published(transcript, binding)
        self.assertEqual(result['status'], 'failed')
        # Duplicate keys must fail even when both values agree and the raw
        # artifact digest/byte count have been rebound to the duplicate JSON.
        binding, _, transcript = self.published_fixture()
        payload = transcript['manifest'].replace(b'{', b'{"schema_version":1,', 1)
        binding['artifact_digest'] = 'sha256:' + hashlib.sha256(payload).hexdigest()
        transcript['manifest'] = payload
        transcript['artifact'].update(digest=binding['artifact_digest'], bytes=len(payload))
        result, _ = self.published(transcript, binding)
        self.assertEqual(result['status'], 'failed')

    def test_published_transcript_timeout_and_exception_remain_diagnostic_and_redacted(self):
        for error in (TimeoutError('FAKE_SECRET'), RuntimeError('FAKE_SECRET'), EOFError('FAKE_SECRET')):
            _, _, transcript = self.published_fixture(); transcript['manifest'] = error
            result, calls = self.published(transcript)
            self.assertEqual(result['status'], 'timed_out' if isinstance(error, TimeoutError) else 'failed')
            self.assertEqual([step['name'] for step in calls], ['run', 'artifact', 'manifest'])
            self.assertFalse(result['deployment_authorized'])
            self.assertIsNone(result['consistent_binding'])
            self.assertNotIn('FAKE_SECRET', str(result))

    def test_published_transcript_rejects_unbound_ids_and_identity_before_fake_cli(self):
        binding, policy, _ = self.published_fixture()
        self.assertTrue(hasattr(self.ops, 'evaluate_published_release'), 'published transcript verifier is missing')
        def forbidden(step): raise AssertionError('unexpected fake CLI')
        for field, value in [('published_run_id', 'latest'), ('artifact_id', True),
                             ('artifact_digest', 'sha256:bad'), ('manifest_sha256', '0' * 64),
                             ('extra', 'bad')]:
            candidate = dict(binding, **{field: value})
            with self.assertRaises(self.rt.ContractError):
                self.ops.evaluate_published_release(self.manifest, self.config, candidate, policy, dict(policy), forbidden)
        wrong = dict(policy, repository_id='1')
        with self.assertRaises(self.rt.ContractError):
            self.ops.evaluate_published_release(self.manifest, self.config, binding, policy, wrong, forbidden)

    def bootstrap(self):
        path = HERE / 'cloud-bootstrap.sh'
        if not path.is_file():
            raise AssertionError('offline bootstrap definition is missing')
        # The shell launcher has one fixed isolated Python heredoc. Execute only
        # that pure definition body; subprocess/network remain forbidden by A.
        body = path.read_text().split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
        namespace = {'__name__': 'offline_bootstrap_definition'}
        exec(compile(body, str(path), 'exec'), namespace)
        return namespace

    def test_bootstrap_default_plan_binds_exact_resource_projects_disk_and_platform(self):
        bootstrap = self.bootstrap()
        with patch.object(self.rt, 'read_private_json', return_value=self.config) as read:
            code, receipt = bootstrap['main']([], runtime=self.rt)
        self.assertEqual(code, 0)
        self.assertEqual(read.call_args.args, ('/etc/autodata/host.json',))
        self.assertEqual(receipt['operation'], 'cloud-bootstrap.sh plan')
        self.assertTrue(receipt['definition_only'])
        plan = receipt['plan']
        self.assertFalse(plan['execution_enabled'])
        self.assertEqual(plan['service_config_sha256'], self.rt.sha256(self.config))
        self.assertEqual(plan['vm']['project'], 'autodata-host')
        self.assertEqual(plan['vm']['platform'], 'linux/amd64')
        self.assertEqual(plan['data_disk']['name'], 'workshop-data')
        self.assertEqual(plan['data_disk']['filesystem_uuid'], RUN)
        self.assertFalse(plan['data_disk']['format_authorized'])
        self.assertEqual(plan['backup_bucket']['project'], 'autodata-backup')
        self.assertEqual(plan['backup_bucket']['name'], 'autodata-private-backup')
        self.assertEqual(plan['artifact_repository']['name'], 'us-central1-docker.pkg.dev/autodata-host/workshop')
        self.assertLessEqual(len(self.rt.canonical_bytes(receipt)), 65536)
        self.assertTrue(plan['unresolved_inputs'])

    def test_bootstrap_attached_identity_has_only_firebase_read_and_no_default_adc_roles(self):
        plan = self.bootstrap()['build_plan'](self.config, self.rt)
        attached = plan['attached_identity']
        self.assertEqual(attached['email'], 'autodata-api-firebase@autodata-host.iam.gserviceaccount.com')
        self.assertEqual(attached['permissions'], ['firebaseauth.users.get'])
        self.assertEqual(attached['permission_project'], 'firebase-stage')
        self.assertEqual(attached['access_scopes'], ['https://www.googleapis.com/auth/cloud-platform',
                                                   'https://www.googleapis.com/auth/userinfo.email',
                                                   'https://www.googleapis.com/auth/identitytoolkit'])
        self.assertEqual(plan['external_authorities']['monitor']['privileged_helpers'], ['/opt/autodata/bin/runtime-check.py metrics --release SHA'])
        self.assertFalse(plan['external_authorities']['backup']['delete_authority'])
        self.assertFalse(plan['external_authorities']['backup']['host_administrator'])
        self.assertTrue(plan['external_authorities']['deploy']['host_administrator'])
        self.assertEqual(plan['wif_requirements']['exact_claims'], ['repository', 'repository_id', 'repository_owner_id', 'environment', 'ref', 'workflow_ref'])
        self.assertFalse(plan['wif_requirements']['binding_resolved'])

    def test_bootstrap_network_restricts_ssh_to_iap_and_keeps_storage_private(self):
        plan = self.bootstrap()['build_plan'](self.config, self.rt)
        self.assertEqual(plan['ingress'], [{'ports': [80, 443], 'source_ipv4': '0.0.0.0/0', 'target_instance': 'workshop-stage'},
                                          {'ports': [22], 'source_ipv4': '35.235.240.0/20', 'target_instance': 'workshop-stage'}])
        self.assertEqual(plan['host_guards']['api_metadata_address'], '172.30.10.10')
        self.assertEqual(plan['host_guards']['storage_address'], '172.30.20.40')
        self.assertEqual(plan['host_guards']['storage_allowed_tcp_ports'], [9000])
        self.assertEqual(plan['host_guards']['trusted_host_metadata_uid'], 0)
        self.assertFalse(plan['host_guards']['ipv6_enabled'])
        self.assertFalse(plan['host_guards']['verified'])

    def test_bootstrap_apply_and_unknown_argv_fail_without_reading_config(self):
        bootstrap = self.bootstrap()
        with patch.object(self.rt, 'read_private_json', side_effect=AssertionError('unexpected config read')):
            code, receipt = bootstrap['main'](['apply'], runtime=self.rt)
            self.assertEqual(code, 3)
            self.assertEqual(receipt['operation'], 'cloud-bootstrap.sh apply')
            self.assertEqual(receipt['failure_code'], 'missing_dependency')
            for args in (['apply', '--yes'], ['plan', 'extra'], ['--config', '/tmp/evil'], ['shell'], ['plan;echo unsafe']):
                with self.subTest(args=args):
                    code, receipt = bootstrap['main'](args, runtime=self.rt)
                    self.assertEqual(code, 2)
                    self.assertEqual(receipt['status'], 'failed')

    def test_bootstrap_rejects_invalid_config_and_ignores_ambient_credentials(self):
        bootstrap = self.bootstrap()
        for mutate in (lambda x: x.update(environment='development'),
                       lambda x: x['resources'].update(host_project_id='other-host'),
                       lambda x: x['resources'].update(data_disk_name='$(touch bad)'),
                       lambda x: x.update(platform='linux/arm64')):
            candidate = copy.deepcopy(self.config); mutate(candidate)
            with patch.object(self.rt, 'read_private_json', return_value=candidate):
                code, receipt = bootstrap['main'](['plan'], runtime=self.rt)
            self.assertEqual(code, 2)
            self.assertEqual(receipt['failure_code'], 'invalid_input')
        with patch.object(self.rt, 'read_private_json', side_effect=self.rt.ContractError('FAKE_SECRET')):
            code, receipt = bootstrap['main'](['plan'], runtime=self.rt)
        self.assertEqual(code, 3)
        self.assertEqual(receipt['failure_code'], 'missing_dependency')
        self.assertNotIn('FAKE_SECRET', str(receipt))
        with patch.dict(self.rt.os.environ, {'GOOGLE_APPLICATION_CREDENTIALS': '/tmp/FAKE_SECRET', 'CLOUDSDK_CORE_PROJECT': 'ambient-project'}):
            plan = bootstrap['build_plan'](self.config, self.rt)
        text = self.rt.canonical_bytes(plan)
        self.assertNotIn(b'FAKE_SECRET', text)
        self.assertNotIn(b'ambient-project', text)
        shared = copy.deepcopy(self.config)
        shared['resources']['backup_project_id'] = shared['resources']['host_project_id']
        shared['firebase']['project_id'] = shared['resources']['host_project_id']
        apis = bootstrap['build_plan'](shared, self.rt)['apis']
        self.assertEqual(list(apis), ['autodata-host'])
        self.assertIn('identitytoolkit.googleapis.com', apis['autodata-host'])
        self.assertIn('storage.googleapis.com', apis['autodata-host'])
        self.assertEqual(len(apis['autodata-host']), len(set(apis['autodata-host'])))

    def test_cli_is_fail_closed_and_rejects_extra_or_unknown_arguments(self):
        for args in ([], ['backup', RUN, 'extra'], ['shell', RUN], ['backup', '../bad'], ['publish', RUN]):
            with self.subTest(args=args):
                code, receipt = self.ops.cli(args)
                self.assertEqual(code, 2)
                self.assertEqual(receipt['status'], 'failed')
        for verb, value in [('publish', 'a' * 40), ('deploy', 'a' * 40), ('monitor', 'a' * 40), ('backup', RUN), ('restore', RUN)]:
            code, receipt = self.ops.cli([verb, value])
            self.assertEqual(code, 3)
            self.assertEqual(receipt['failure_code'], 'missing_dependency')
            self.assertNotIn('passed', receipt)

    def test_wif_requires_exact_numeric_owner_repo_workflow_ref_environment(self):
        self.assertTrue(self.ops.validate_identity('backup', self.policy, self.claims, 'staging'))
        for field, value in [('repository_id', '123457'), ('repository_owner_id', '987655'),
                             ('repository', 'attacker/autodata'), ('environment', 'production'),
                             ('ref', 'refs/pull/1/merge'), ('workflow_ref', self.policy['workflow_ref'] + '/extra')]:
            candidate = dict(self.claims, **{field: value})
            with self.subTest(field=field), self.assertRaises(self.rt.ContractError):
                self.ops.validate_identity('backup', self.policy, candidate, 'staging')
        for field, value in [('repository_id', '*'), ('repository_owner_id', ''), ('ref', 'refs/heads/*'),
                             ('workflow_ref', 'lucronn/autodata/.github/workflows/release-workshop.yml@refs/heads/release-reviewed')]:
            candidate = dict(self.policy, **{field: value})
            with self.subTest(policy=field), self.assertRaises(self.rt.ContractError):
                self.ops.validate_identity('backup', candidate, candidate, 'staging')
        for verb in ('publish', 'deploy', 'monitor', 'restore'):
            with self.subTest(verb=verb), self.assertRaises(self.rt.ContractError):
                self.ops.validate_identity(verb, self.policy, self.claims, 'staging')

    def test_private_input_refuses_wrong_owner_mode_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'
            path.write_bytes(b'{}')
            path.chmod(0o600)
            with patch.object(self.rt.os, 'fstat', return_value=type('Stat', (), {'st_mode': 0o100600, 'st_uid': 1234, 'st_size': 2})()):
                with self.assertRaises(self.rt.ContractError): self.ops.read_input(path)
            path.chmod(0o644)
            with self.assertRaises(self.rt.ContractError): self.ops.read_input(path)
            link = Path(directory) / 'link'
            link.symlink_to(path)
            with self.assertRaises(self.rt.ContractError): self.ops.read_input(link)

    def test_valid_backup_binds_immutable_objects_and_only_then_advances(self):
        receipt, calls = self.evaluate()
        self.assertEqual(receipt['status'], 'passed')
        self.assertEqual(receipt['last_verified_backup'], '2026-11-03T12:02:00Z')
        self.assertEqual(receipt['snapshot'], self.snapshot)
        self.assertTrue(receipt['simulation'])
        self.assertTrue(receipt['cleanup'])
        self.assertTrue(receipt['resumed'])
        self.assertEqual(receipt['dump_sha256'], self.dump_hash)
        self.assertEqual(receipt['dump_bytes'], len(self.dump))
        self.assertEqual(receipt['manifest_sha256'], self.rt.sha256(self.manifest))
        self.assertEqual(receipt['migrations'], self.manifest['migrations'])
        self.assertTrue(receipt['checks']['services'])
        self.assertTrue(receipt['checks']['no_work'])
        self.assertEqual(receipt['objects']['postgres.dump']['generation'], '100')
        self.assertEqual(receipt['object_prefix'], 'gs://autodata-private-backup/' + RUN + '/')
        self.assertEqual([step['name'] for step in calls], ['begin', 'snapshot', 'resume', 'status', 'export', 'upload', 'cleanup'])
        for step in calls:
            self.assertIs(type(step['timeout_seconds']), int)
            self.assertGreater(step['timeout_seconds'], 0)
            self.assertLessEqual(step['timeout_seconds'], 600)
            self.assertLessEqual(step['max_output_bytes'], 1048576 if step['name'] != 'export' else 1073741824)
        self.assertEqual(calls[0]['argv'], ['/opt/autodata/bin/backup-host.sh', 'begin', RUN])
        self.assertEqual(calls[2]['argv'], ['/opt/autodata/bin/backup-host.sh', 'resume', RUN])

    def test_wrong_manifest_image_disk_or_identity_stops_before_fake_cli(self):
        for change in ('image', 'config', 'identity'):
            before = []
            manifest, config, claims = copy.deepcopy(self.manifest), copy.deepcopy(self.config), dict(self.claims)
            if change == 'image': manifest['images']['api']['reference'] = 'registry.example/evil@sha256:' + 'b' * 64
            if change == 'config': config['resources']['data_disk_name'] = 'other-disk'
            if change == 'identity': claims['repository_owner_id'] = '0'
            with self.subTest(change=change), self.assertRaises(self.rt.ContractError):
                self.ops.evaluate_backup(manifest, config, RUN, self.policy, claims, lambda step: before.append(step), now=NOW)
            self.assertEqual(before, [])

    def test_bad_quiesced_receipt_never_snapshots_and_attempts_resume(self):
        for field, value in [('disk_uuid', '00000000-0000-4000-8000-000000000000'), ('run_id', '87654321-1234-4234-8234-123456789abc'),
                             ('state', 'preparing'), ('lease_expires_at', '2026-11-03T11:59:00Z'),
                             ('lease_expires_at', '2026-11-03T13:00:00Z'), ('source_sha', 'd' * 40),
                             ('manifest_sha256', 'f' * 64), ('operation', 'backup-host.sh status')]:
            events = copy.deepcopy(self.events)
            events['begin'][field] = value
            receipt, calls = self.evaluate(events)
            with self.subTest(field=field, value=value):
                self.assertNotEqual(receipt['status'], 'passed')
                self.assertNotIn('snapshot', [step['name'] for step in calls])
                self.assertIn('resume', [step['name'] for step in calls])
                self.assertIsNone(receipt['last_verified_backup'])

    def test_wrong_snapshot_identity_disk_cutoff_or_completion_is_not_verified(self):
        for field, value in [('source_disk', self.disk + '-wrong'), ('status', 'CREATING'),
                             ('self_link', self.snapshot['self_link'].replace(RUN, 'another')),
                             ('operation', 'https://evil.example/op'), ('cutoff_at', '2026-11-03T11:59:00Z'),
                             ('completed_at', '2026-11-03T12:26:00Z')]:
            events = copy.deepcopy(self.events)
            events['snapshot'][field] = value
            receipt, calls = self.evaluate(events)
            with self.subTest(field=field):
                self.assertNotEqual(receipt['status'], 'passed')
                self.assertIsNone(receipt['last_verified_backup'])
                self.assertIn('resume', [step['name'] for step in calls])
                self.assertNotIn('upload', [step['name'] for step in calls])

    def test_failed_upload_resume_interrupted_stream_timeout_and_cleanup_do_not_certify(self):
        for step, value in [('snapshot', RuntimeError('secret error detail')), ('snapshot', TimeoutError()),
                            ('resume', RuntimeError('secret error detail')), ('export', EOFError('secret error detail')),
                            ('upload', RuntimeError('secret error detail')), ('cleanup', False)]:
            events = copy.deepcopy(self.events)
            events[step] = value
            receipt, calls = self.evaluate(events)
            with self.subTest(step=step, value=type(value).__name__):
                self.assertNotEqual(receipt['status'], 'passed')
                self.assertIsNone(receipt['last_verified_backup'])
                self.assertNotIn('secret error detail', str(receipt))
                self.assertEqual(sum(x['name'] == 'resume' for x in calls), 1)
                self.assertEqual(calls[-1]['name'], 'cleanup')
                if step == 'snapshot' and isinstance(value, TimeoutError): self.assertEqual(receipt['status'], 'timed_out')
                if step in ('resume', 'cleanup'): self.assertEqual(receipt['status'], 'incomplete')

    def test_resume_requires_matching_lease_and_no_work_readiness(self):
        for field, value in [('run_id', '87654321-1234-4234-8234-123456789abc'), ('writers_resumed', False),
                             ('stateful_resumed', False), ('state', 'resuming'), ('checks', {'services': True, 'no_work': False}),
                             ('finished_at', '2026-11-03T12:26:00Z')]:
            events = copy.deepcopy(self.events)
            events['resume'][field] = value
            receipt, calls = self.evaluate(events)
            with self.subTest(field=field):
                self.assertEqual(receipt['status'], 'incomplete')
                self.assertNotIn('export', [step['name'] for step in calls])

    def test_unknown_or_nonboolean_host_receipts_do_not_certify(self):
        for verb in ('begin', 'resume', 'status'):
            for field, value in [('unknown', True), ('schema_version', True), ('checks', {'services': 1})]:
                events = copy.deepcopy(self.events)
                events[verb][field] = value
                receipt, _ = self.evaluate(events)
                with self.subTest(verb=verb, field=field):
                    self.assertNotEqual(receipt['status'], 'passed')
                    self.assertIsNone(receipt['last_verified_backup'])

    def test_upload_generation_hash_size_and_member_set_must_match(self):
        for field, value in [('bucket', 'wrong-backup-bucket'), ('name', 'another/' + 'postgres.dump'), ('generation', 'latest'), ('generation', '0'), ('sha256', '0' * 64), ('bytes', 1)]:
            events = copy.deepcopy(self.events)
            events['upload']['postgres.dump'][field] = value
            receipt, _ = self.evaluate(events)
            with self.subTest(field=field): self.assertNotEqual(receipt['status'], 'passed')
        events = copy.deepcopy(self.events)
        events['upload']['extra'] = events['upload']['postgres.dump']
        self.assertNotEqual(self.evaluate(events)[0]['status'], 'passed')

    def test_export_rejects_duplicate_escape_link_sparse_unknown_and_corrupt_members(self):
        self.assertEqual(self.ops.verify_export(self.archive, self.manifest, self.status), dict(self.members()))
        for name in ('postgres.dump', '../escape', '/absolute', './postgres.dump', 'dir/file'):
            with self.subTest(name=name), self.assertRaises(self.rt.ContractError):
                self.ops.verify_export(self.tar([(name, b'bad')]), self.manifest, self.status)
        for member_type in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.DIRTYPE, tarfile.GNUTYPE_SPARSE):
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode='w') as archive:
                member = tarfile.TarInfo('postgres.dump'); member.type = member_type; member.linkname = '../escape'
                archive.addfile(member)
            with self.subTest(member_type=member_type), self.assertRaises(self.rt.ContractError):
                self.ops.verify_export(buffer.getvalue(), self.manifest, self.status)
        corrupted = bytearray(self.archive); corrupted[512] ^= 1
        for archive in (bytes(corrupted), self.archive[:100], self.archive + b'junk'):
            with self.assertRaises(self.rt.ContractError): self.ops.verify_export(archive, self.manifest, self.status)

    def rejected_archived_status(self, archived):
        # Update upload evidence to match the changed bytes: rejection must come
        # from the receipt contract, rather than a conveniently stale checksum.
        with patch.object(self, 'status', archived):
            archive = self.tar()
        events = copy.deepcopy(self.events)
        events['export'] = archive
        payload = self.rt.canonical_bytes(archived)
        events['upload']['backup.json'].update(sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload))
        receipt, _ = self.evaluate(events)
        self.assertNotEqual(receipt['status'], 'passed')
        self.assertIsNone(receipt['last_verified_backup'])
        with self.assertRaises(self.rt.ContractError):
            self.ops.verify_export(archive, self.manifest, self.status)

    def test_archived_receipt_rejects_boolean_as_integer(self):
        self.rejected_archived_status(dict(self.status, schema_version=True))

    def test_archived_receipt_rejects_float_as_integer(self):
        self.rejected_archived_status(dict(self.status, dump_bytes=float(len(self.dump))))

    def test_archived_receipt_rejects_nested_scalar_type_drift(self):
        for field, value in [('services', 1), ('no_work', 1.0)]:
            archived = copy.deepcopy(self.status)
            archived['checks'][field] = value
            with self.subTest(field=field, value=value):
                self.rejected_archived_status(archived)

    def test_export_rejects_wrong_release_and_status_bytes_and_bounded_stream(self):
        wrong = copy.deepcopy(self.manifest); wrong['source_sha'] = 'd' * 40
        with self.assertRaises(self.rt.ContractError): self.ops.verify_export(self.archive, wrong, self.status)
        wrong_status = dict(self.status, dump_bytes=len(self.dump) + 1)
        with self.assertRaises(self.rt.ContractError): self.ops.verify_export(self.archive, self.manifest, wrong_status)
        class Unbounded:
            def read(self, count): self.last = count; return b'x' * count
        stream = Unbounded()
        with self.assertRaises(self.rt.ContractError): self.ops.read_stream(stream, limit=100)
        self.assertLessEqual(stream.last, 101)

    def test_metrics_consumer_rejects_dynamic_labels_duplicates_nonfinite_and_wrong_release(self):
        metrics = self.rt.metrics_receipt(self.manifest['source_sha'], [{'name': 'disk_free_bytes', 'value': 1024, 'unit': 'By', 'state': 'ok'}])
        self.assertEqual(self.ops.validate_metrics(metrics, self.manifest['source_sha']), metrics)
        self.assertEqual(self.ops.validate_metrics(self.rt.metrics_receipt(self.manifest['source_sha'], []), self.manifest['source_sha'])['metrics'], [])
        for mutate in (lambda x: x['metrics'][0].update(labels={'customer': 'bad'}),
                       lambda x: x['metrics'].append(dict(x['metrics'][0])),
                       lambda x: x['metrics'][0].update(value=float('inf')),
                       lambda x: x.update(source_sha='d' * 40)):
            candidate = copy.deepcopy(metrics); mutate(candidate)
            with self.assertRaises(self.rt.ContractError): self.ops.validate_metrics(candidate, self.manifest['source_sha'])



class ReleaseArchiveTests(unittest.TestCase):
    def setUp(self):
        fixture = host_test.ContractTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.ops = load_ops()
        self.rt, self.manifest = self.ops.rt, fixture.manifest
        self.payloads = {
            'release.json': self.rt.canonical_bytes(self.manifest),
            'images.json': self.rt.canonical_bytes({role: dict(image, platform=self.manifest['platform'])
                                                  for role, image in self.manifest['images'].items()})}

    def archive(self, payloads=None, *, method=0, flags=0, descriptor='signed',
                local=None, central=None, compressed=None, padding=b''):
        # Independent fixture writer, including deliberately inconsistent records.
        payloads = self.payloads if payloads is None else payloads
        body, directory = bytearray(), bytearray()
        for name, data in payloads.items():
            encoded = name.encode('utf-8')
            packed = data
            if method == 8:
                compressor = zlib.compressobj(wbits=-15)
                packed = compressor.compress(data) + compressor.flush()
            if compressed is not None:
                packed = compressed
            crc = binascii.crc32(data)
            version = 20 if flags & 8 or method == 8 else 10
            offset = len(body)
            values = dict(version=version, flags=flags, method=method, time=0, date=33,
                          crc=crc, compressed=len(packed), size=len(data))
            l = dict(values)
            if flags & 8:
                l.update(crc=0, compressed=0, size=0)
            l.update(local or {})
            c = dict(values, creator=0x314, disk=0, internal=0, external=0o100600 << 16,
                     offset=offset)
            c.update(central or {})
            body += struct.pack('<4s5H3I2H', b'PK\x03\x04', *(l[k] for k in
                                ('version', 'flags', 'method', 'time', 'date', 'crc', 'compressed', 'size')),
                                len(encoded), 0) + encoded + packed
            if flags & 8:
                if descriptor == 'signed': body += b'PK\x07\x08'
                body += struct.pack('<3I', crc, len(packed), len(data))
            body += padding
            directory += struct.pack('<4s6H3I5H2I', b'PK\x01\x02', *(c[k] for k in
                                     ('creator', 'version', 'flags', 'method', 'time', 'date', 'crc', 'compressed', 'size')),
                                     len(encoded), 0, 0, c['disk'], c['internal'], c['external'], c['offset']) + encoded
        return bytes(body + directory + struct.pack('<4s4H2IH', b'PK\x05\x06', 0, 0,
                     len(payloads), len(payloads), len(directory), len(body), 0))

    def verify(self, archive=None, payloads=None, **kwargs):
        payloads = self.payloads if payloads is None else payloads
        archive = self.archive(payloads) if archive is None else archive
        self.assertTrue(hasattr(self.ops, 'verify_release_archive'), 'archive verifier is missing')
        return self.ops.verify_release_archive(archive, self.manifest,
            expected_archive_sha256=kwargs.get('archive_hash', hashlib.sha256(archive).hexdigest()),
            expected_member_sha256=kwargs.get('member_hashes', {
                name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()}))

    def reject(self, archive=None, payloads=None, **kwargs):
        with self.assertRaises(self.ops.ContractError) as caught:
            self.verify(archive, payloads, **kwargs)
        self.assertEqual(str(caught.exception), 'invalid release archive')

    def test_standard_library_zip_archives_and_descriptor_variants_are_consistency_only(self):
        self.assertTrue(hasattr(self.ops, 'verify_release_archive'), 'archive verifier is missing')
        for method in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w', compression=method) as writer:
                for name, data in self.payloads.items(): writer.writestr(name, data)
            archives = [output.getvalue()]
            for flags in (0, 8, 2048, 2056):
                for descriptor in ('signed', 'unsigned'):
                    archives.append(self.archive(method=method, flags=flags, descriptor=descriptor))
            for archive in archives:
                with self.subTest(method=method, digest=hashlib.sha256(archive).hexdigest()):
                    result = self.verify(archive)
                    self.assertEqual(set(result), {'schema_version', 'status', 'simulation',
                        'provenance_authenticated', 'deployment_authorized', 'archive_sha256',
                        'member_sha256', 'member_bytes', 'manifest_sha256', 'checks'})
                    self.assertEqual(result['status'], 'archive_consistent')
                    self.assertTrue(result['simulation'])
                    self.assertFalse(result['provenance_authenticated'])
                    self.assertFalse(result['deployment_authorized'])
                    self.assertEqual(result['archive_sha256'], hashlib.sha256(archive).hexdigest())
                    self.assertEqual(result['manifest_sha256'], self.rt.sha256(self.manifest))
                    self.assertEqual(result['member_bytes'], {n: len(b) for n, b in self.payloads.items()})
                    self.assertEqual(result['member_sha256'], {n: hashlib.sha256(b).hexdigest()
                                                             for n, b in self.payloads.items()})

    def test_independent_archive_and_member_bindings_and_input_types(self):
        archive = self.archive(method=8)
        with patch.object(zlib, 'decompressobj', side_effect=AssertionError('must not decode')):
            self.reject(archive, archive_hash='0' * 64)
        for bad in (None, True, '', 'A' * 64, 'sha256:' + 'a' * 64):
            self.reject(archive, archive_hash=bad)
        hashes = {n: hashlib.sha256(b).hexdigest() for n, b in self.payloads.items()}
        for name in hashes:
            self.reject(archive, member_hashes=dict(hashes, **{name: '0' * 64}))
        for bad in ({}, dict(hashes, extra='0' * 64), dict(hashes, **{'images.json': True}), None):
            self.reject(archive, member_hashes=bad)
        for bad in (b'', b'x', bytearray(archive), b'x' * 8388609):
            self.reject(bad)

    def test_raw_member_digest_differs_from_canonical_manifest_digest(self):
        payloads = dict(self.payloads, **{'release.json': json.dumps(self.manifest, indent=2).encode()})
        result = self.verify(payloads=payloads)
        self.assertNotEqual(result['member_sha256']['release.json'], result['manifest_sha256'])
        self.assertEqual(result['manifest_sha256'], self.rt.sha256(self.manifest))

    def test_strict_json_and_image_shapes_are_not_authenticated_observations(self):
        for name in self.payloads:
            for data in (b'FAKE_SECRET', b'[]', b'null', b'{"x":NaN}', b'{"x":1e999}', b'{"x":0,"x":0}',
                         b'{"x":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}'):
                self.reject(payloads=dict(self.payloads, **{name: data}))
        manifest = dict(self.manifest, schema_version=True)
        self.reject(payloads=dict(self.payloads, **{'release.json': self.rt.canonical_bytes(manifest)}))
        self.reject(payloads=dict(self.payloads, **{'release.json': b'{"schema_version":1,' + self.payloads['release.json'][1:]}))
        observations = self.rt.strict_json(self.payloads['images.json'])
        for mutate in (lambda x: x.pop('api'), lambda x: x.update(extra={}),
                       lambda x: x['api'].update(platform='linux/arm64'),
                       lambda x: x['api'].update(image_id=True),
                       lambda x: x['api'].update(extra='FAKE_SECRET')):
            candidate = copy.deepcopy(observations); mutate(candidate)
            self.reject(payloads=dict(self.payloads, **{'images.json': self.rt.canonical_bytes(candidate)}))

    def test_central_and_local_metadata_disagreement_and_unsupported_features(self):
        for field, values in {'version': (45,), 'flags': (1, 2, 16, 64, 4096),
                              'method': (12, 99), 'time': (1,), 'date': (34,),
                              'crc': (0,), 'compressed': (0, 1048577, 0xffffffff),
                              'size': (0, 1048577, 0xffffffff)}.items():
            for value in values:
                for target in ('local', 'central'):
                    with self.subTest(field=field, value=value, target=target):
                        self.reject(self.archive(**{target: {field: value}}))
        for field, value in [('creator', 0x714), ('disk', 1), ('internal', 1),
                             ('external', 0o120600 << 16), ('external', 0x10),
                             ('external', 0x08), ('offset', 1), ('offset', 0xffffffff)]:
            self.reject(self.archive(central={field: value}))
        # Even agreeing local/central records cannot enable unsupported methods/flags/versions.
        for flags in (1, 2, 16, 64, 4096): self.reject(self.archive(flags=flags))
        for field, value in [('version', 45), ('method', 99)]:
            self.reject(self.archive(local={field: value}, central={field: value}))
        for name in ('../release.json', '/release.json', 'release.json/', 'release\x00.json', 'réléase.json'):
            self.reject(self.archive({name: self.payloads['release.json'], 'images.json': self.payloads['images.json']}))
        self.reject(self.archive(dict(reversed(list(self.payloads.items())))))
        self.reject(self.archive(dict(self.payloads, extra=b'{}')))
        self.reject(self.archive(padding=b'PK\x06\x06'))

    def test_eocd_local_central_names_extras_and_offsets_are_structurally_bound(self):
        good = self.archive()
        for offset, fmt, value in [(4, 'H', 1), (6, 'H', 1), (8, 'H', 1), (10, 'H', 3),
                                   (12, 'I', 0xffffffff), (16, 'I', 0xffffffff), (20, 'H', 1)]:
            bad = bytearray(good); struct.pack_into('<'+fmt, bad, len(bad)-22+offset, value); self.reject(bytes(bad))
        for bad in (good[:-1], good+b'x', b'x'+good, good[:-22], b'PK\x06\x06'+good): self.reject(bad)
        central = good.index(b'PK\x01\x02'); second = good.index(b'PK\x01\x02', central+1)
        for position in (0, central):
            bad = bytearray(good); bad[position] = 0; self.reject(bytes(bad))
            bad = bytearray(good); bad[position+(30 if position == 0 else 46)] = ord('x'); self.reject(bytes(bad))
            bad = bytearray(good); struct.pack_into('<H', bad, position+(28 if position == 0 else 30), 1); self.reject(bytes(bad))
        bad=bytearray(good);struct.pack_into('<H',bad,central+32,1);self.reject(bytes(bad))
        # Duplicate second central name and alias the first local offset.
        bad=bytearray(good);bad[second+46:second+57]=b'release.json'
        struct.pack_into('<H',bad,second+28,12)
        struct.pack_into('<I',bad,len(bad)-10,len(bad)-22-central)
        self.reject(bytes(bad))
        bad=bytearray(good);struct.pack_into('<I',bad,second+42,0);self.reject(bytes(bad))
        self.reject(self.archive(central={'size': 0xffffffff, 'compressed': 0xffffffff}))

    def test_descriptors_are_parsed_by_bounded_length_and_exact_values(self):
        good = self.archive(flags=8)
        first_descriptor = good.index(b'PK\x07\x08')
        for relative in (0, 4, 8, 12):
            bad=bytearray(good);bad[first_descriptor+relative]^=1;self.reject(bytes(bad))
        for flags in (0, 2048):
            self.reject(self.archive(flags=flags, padding=b'PK\x07\x08'+b'\0'*12))
        self.reject(self.archive(flags=8, local={'crc': 1}))
        # Full local values with flag3 are allowed; mixed placeholders are not.
        # Per-member CRC values differ, so patch the actual independent fixture records.
        full=bytearray(good); central=full.index(b'PK\x01\x02')
        for _ in range(2):
            offset=struct.unpack_from('<I',full,central+42)[0]
            full[offset+14:offset+26]=full[central+16:central+28]
            central+=46+struct.unpack_from('<H',full,central+28)[0]
        self.verify(bytes(full))
        self.reject(self.archive(flags=8, padding=b'\0'))

    def test_crc_size_ratio_and_deflate_stream_boundaries(self):
        good=bytearray(self.archive()); good[30+len('release.json')]^=1;self.reject(bytes(good))
        for packed in (b'broken FAKE_SECRET', b'', b'\x03\x00garbage'):
            self.reject(self.archive(method=8, compressed=packed))
        data=self.payloads['release.json']; compressor=zlib.compressobj(wbits=-15)
        packed=compressor.compress(data)+compressor.flush()
        for broken in (packed[:-1], packed+b'garbage', packed+packed):
            self.reject(self.archive(method=8, compressed=broken))
        self.reject(self.archive({'release.json': b'x'*1048577, 'images.json': b'{}'}))
        self.reject(self.archive({'release.json': b'x'*1048576, 'images.json': b'{}'}, method=8))
        # Declared plausible size/ratio cannot hide larger actual decoded output.
        payloads={'release.json': bytes(range(256))*100, 'images.json': b'{}'}
        self.reject(self.archive(payloads, method=8, central={'size': 100}, local={'size': 100}))

    def test_output_limit_streaming_calls_and_exact_member_maximum(self):
        # Incompressible whitespace preserves JSON semantics while crossing the
        # compressed input chunk boundary; both outputs reach the permitted cap.
        noise = random.Random(19).randbytes(1048576)
        whitespace = noise.translate(bytes(b' \t\r\n'[i % 4] for i in range(256)))
        payloads = {name: body + whitespace[:1048576-len(body)] for name, body in self.payloads.items()}
        archive = self.archive(payloads, method=8)
        original = zlib.decompressobj
        calls = []
        class MeasuredDecoder:
            def __init__(self, mode): self.decoder = original(mode)
            def decompress(self, chunk, maximum):
                calls.append((len(chunk), maximum))
                if maximum <= 0: raise AssertionError('unbounded output request')
                return self.decoder.decompress(chunk, maximum)
            def __getattr__(self, name):
                if name == 'flush': raise AssertionError('unbounded flush')
                return getattr(self.decoder, name)
        with patch.object(zlib, 'decompressobj', side_effect=MeasuredDecoder):
            result = self.verify(archive, payloads)
        self.assertEqual(result['member_bytes'], {'release.json': 1048576, 'images.json': 1048576})
        self.assertGreater(len(calls), 2)
        self.assertTrue(all(0 < n <= 65536 and 0 < maximum <= 1048577 for n, maximum in calls))
        # Oversized actual output with plausible declared sizes must still use a
        # finite small request instead of allocating the decompression bomb.
        calls.clear()
        with patch.object(zlib, 'decompressobj', side_effect=MeasuredDecoder):
            self.reject(self.archive({'release.json': bytes(range(256))*100, 'images.json': b'{}'},
                                     method=8, central={'size': 100}, local={'size': 100}))
        self.assertTrue(calls)
        self.assertLessEqual(max(maximum for _, maximum in calls), 101)

    def test_unsigned_descriptor_crc_equal_to_signature_has_no_boundary_guessing(self):
        archive = bytearray(self.archive(flags=8, descriptor='unsigned'))
        central = archive.index(b'PK\x01\x02')
        for _ in range(2):
            offset = struct.unpack_from('<I', archive, central+42)[0]
            packed_size = struct.unpack_from('<I', archive, central+20)[0]
            name_size = struct.unpack_from('<H', archive, offset+26)[0]
            descriptor = offset + 30 + name_size + packed_size
            struct.pack_into('<I', archive, descriptor, 0x08074b50)
            struct.pack_into('<I', archive, central+16, 0x08074b50)
            central += 46 + struct.unpack_from('<H', archive, central+28)[0]
        # Framing accepts the 12-byte unsigned form despite the CRC's value;
        # content verification subsequently rejects its deliberately wrong CRC.
        self.assertEqual([span[0] for span in self.ops._release_zip_members(bytes(archive))],
                         ['release.json', 'images.json'])
        self.reject(bytes(archive))


class WorkflowTests(unittest.TestCase):
    """Execute actual inline dispatch validators; inspect authority declarations.

    Removing an enable guard, accepting an unbound deploy input, granting a
    shared cloud identity, or swallowing the missing adapter must fail here.
    JSON is a YAML 1.2 subset, so no third-party YAML parser is required.
    """
    def workflow(self, name):
        path = HERE.parents[2] / '.github' / 'workflows' / (name + '-workshop.yml')
        self.assertTrue(path.is_file(), 'workflow definition is missing: ' + name)
        return json.loads(path.read_text())

    def environment(self, operation):
        return {'PATH': os.defpath, 'EVENT_NAME': 'workflow_dispatch',
                'REPOSITORY': 'lucronn/autodata', 'REPOSITORY_ID': '123456',
                'REPOSITORY_OWNER_ID': '987654', 'EXPECTED_REPOSITORY_ID': '123456',
                'EXPECTED_OWNER_ID': '987654', 'WORKFLOW_REF':
                'lucronn/autodata/.github/workflows/' + ('release' if operation in ('publish', 'deploy') else operation) + '-workshop.yml@refs/heads/master',
                'REF': 'refs/heads/master', 'OPERATION': operation,
                'SOURCE_SHA': 'a' * 40, 'CONFIG_SHA256': 'b' * 64,
                'PUBLISHED_RUN_ID': '1234' if operation == 'deploy' else '',
                'ARTIFACT_ID': '5678' if operation == 'deploy' else '',
                'ARTIFACT_DIGEST': 'sha256:' + 'c' * 64 if operation == 'deploy' else '',
                'MANIFEST_SHA256': 'd' * 64 if operation == 'deploy' else '',
                'RUN_ID': RUN if operation == 'backup' else '',
                'WIF_PROVIDER': 'projects/123456/locations/global/workloadIdentityPools/workshop/providers/github',
                'SERVICE_ACCOUNT': 'workshop-' + operation + '@autodata-host.iam.gserviceaccount.com',
                'OTHER_SERVICE_ACCOUNT': 'workshop-deploy@autodata-host.iam.gserviceaccount.com' if operation == 'publish' else 'workshop-publish@autodata-host.iam.gserviceaccount.com',
                **{name.upper() + '_SERVICE_ACCOUNT': 'workshop-' + name + '@autodata-host.iam.gserviceaccount.com'
                   for name in ('publish', 'deploy', 'backup', 'monitor')}}

    def validate(self, workflow, operation, **overrides):
        env = self.environment(operation); env.update(overrides)
        job = workflow['jobs'][operation]
        script = next(step['run'] for step in job['steps'] if step.get('id') == 'validate')
        return subprocess.run(['bash', '--noprofile', '--norc', '-e', '-o', 'pipefail', '-c', script],
                              env=env, capture_output=True, text=True, timeout=5)

    def test_release_dispatch_rejects_mutable_missing_and_cross_authority_inputs(self):
        workflow = self.workflow('release')
        for operation in ('publish', 'deploy'):
            self.assertEqual(self.validate(workflow, operation).returncode, 0)
            for field, value in [('SOURCE_SHA', 'master'), ('CONFIG_SHA256', ''),
                                 ('REF', 'refs/heads/other'), ('EXPECTED_OWNER_ID', '1'),
                                 ('WORKFLOW_REF', 'lucronn/autodata/.github/workflows/evil.yml@refs/heads/master'),
                                 ('SERVICE_ACCOUNT', ''), ('WIF_PROVIDER', 'unknown'),
                                 ('OTHER_SERVICE_ACCOUNT', self.environment(operation)['SERVICE_ACCOUNT'])]:
                with self.subTest(operation=operation, field=field):
                    result = self.validate(workflow, operation, **{field: value})
                    self.assertEqual(result.returncode, 2)
                    self.assertNotIn(value, result.stderr) if value else None
        for field, value in [('PUBLISHED_RUN_ID', ''), ('ARTIFACT_ID', 'latest'),
                             ('ARTIFACT_DIGEST', 'sha256:bad'), ('MANIFEST_SHA256', ''),
                             ('EVENT_NAME', 'workflow_run')]:
            with self.subTest(field=field):
                self.assertEqual(self.validate(workflow, 'deploy', **{field: value}).returncode, 2)
        self.assertEqual(self.validate(workflow, 'publish', ARTIFACT_ID='123').returncode, 2)

    def test_scheduled_helpers_require_fixed_release_identity_and_manual_backup_uuid(self):
        for operation in ('backup', 'monitor'):
            workflow = self.workflow(operation)
            self.assertEqual(self.validate(workflow, operation).returncode, 0)
            self.assertEqual(self.validate(workflow, operation, EVENT_NAME='schedule', RUN_ID='').returncode, 0)
            self.assertEqual(self.validate(workflow, operation, SOURCE_SHA='latest').returncode, 2)
            self.assertEqual(self.validate(workflow, operation, OPERATION='deploy').returncode, 2)
            self.assertEqual(self.validate(workflow, operation, SERVICE_ACCOUNT='workshop-publish@autodata-host.iam.gserviceaccount.com').returncode, 2)
            self.assertEqual(self.validate(workflow, operation, MONITOR_SERVICE_ACCOUNT='workshop-backup@autodata-host.iam.gserviceaccount.com').returncode, 2)
        self.assertEqual(self.validate(self.workflow('backup'), 'backup', RUN_ID='../escape').returncode, 2)

    def test_every_cloud_job_is_explicitly_enabled_separate_bounded_and_fail_closed(self):
        environments, accounts = set(), set()
        for name in ('release', 'backup', 'monitor'):
            workflow = self.workflow(name)
            self.assertEqual(workflow['permissions'], {'contents': 'read'})
            self.assertNotIn('push', workflow['on'])
            self.assertNotIn('workflow_run', workflow['on'])
            self.assertFalse(workflow['concurrency']['cancel-in-progress'])
            for operation, job in workflow['jobs'].items():
                self.assertIn("vars.WORKSHOP_" + operation.upper() + "_ENABLED == 'true'", job['if'])
                self.assertIn("github.ref == 'refs/heads/master'", job['if'])
                self.assertEqual(job['permissions'], {'contents': 'read'})
                self.assertNotIn(job['environment'], environments); environments.add(job['environment'])
                account = job['env']['SERVICE_ACCOUNT']
                self.assertNotIn(account, accounts); accounts.add(account)
                self.assertLessEqual(job['timeout-minutes'], {'publish': 45, 'deploy': 30, 'backup': 30, 'monitor': 1}[operation])
                self.assertTrue(all('uses' not in step for step in job['steps']))
                blocked = job['steps'][-1]
                result = subprocess.run(['bash', '-e', '-c', blocked['run']], env={'PATH': os.defpath},
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 3)
                self.assertIn('missing_dependency', result.stderr)
                self.assertNotIn('success', result.stdout)



class PublisherProducerTests(unittest.TestCase):
    def setUp(self):
        fixture = host_test.ContractTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.ops = load_ops()
        self.rt, self.config, self.manifest = self.ops.rt, fixture.config, fixture.manifest
    # A missing digest/type/config check would allow altered release bytes.
    def producer_images(self):
        return {role: dict(image, platform='linux/amd64') for role, image in self.manifest['images'].items()}

    def test_producer_is_deterministic_and_compatible_with_reviewed_inner_zip(self):
        self.assertTrue(hasattr(self.ops, 'produce_release_archive'), 'producer missing')
        archive, envelope = self.ops.produce_release_archive(self.manifest, self.config, self.producer_images())
        again, repeated = self.ops.produce_release_archive(self.manifest, self.config, self.producer_images())
        self.assertEqual((archive, envelope), (again, repeated))
        self.assertEqual(envelope['archive_sha256'], hashlib.sha256(archive).hexdigest())
        self.assertEqual(envelope['source_sha'], self.manifest['source_sha'])
        self.assertEqual(envelope['protocol_version'], 2)
        result = self.ops.verify_release_archive(archive, self.manifest,
            expected_archive_sha256=envelope['archive_sha256'], expected_member_sha256=envelope['member_sha256'])
        self.assertEqual(result['status'], 'archive_consistent')
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            self.assertEqual(z.namelist(), ['release.json', 'images.json'])
            self.assertEqual(z.read('release.json'), self.rt.canonical_bytes(self.manifest))
            for info in z.infolist():
                self.assertEqual((info.create_system, info.extract_version, info.flag_bits, info.compress_type,
                                  info.extra, info.comment, info.internal_attr, info.external_attr),
                                 (0, 10, 0, 0, b'', b'', 0, 0))
                self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual(envelope['member_bytes'][info.filename], info.file_size)
                self.assertEqual(envelope['member_sha256'][info.filename], hashlib.sha256(z.read(info)).hexdigest())

    def test_producer_rejects_image_shape_platform_and_config_drift(self):
        self.assertTrue(hasattr(self.ops, 'produce_release_archive'), 'producer missing')
        for field, value in [('platform', 'linux/arm64'), ('image_id', 'sha256:'+'0'*64), ('extra', True)]:
            images = self.producer_images(); images['api'][field] = value
            with self.subTest(field=field), self.assertRaises(self.ops.ContractError):
                self.ops.produce_release_archive(self.manifest, self.config, images)
        images=self.producer_images(); images.pop('api')
        with self.assertRaises(self.ops.ContractError):
            self.ops.produce_release_archive(self.manifest, self.config, images)
        manifest=copy.deepcopy(self.manifest);manifest['service_config_sha256']='0'*64
        with self.assertRaises(self.ops.ContractError):
            self.ops.produce_release_archive(manifest,self.config,self.producer_images())
        manifest=copy.deepcopy(self.manifest);manifest['rollback_source_sha']='d'*40
        with self.assertRaises(self.ops.ContractError):
            self.ops.produce_release_archive(manifest,self.config,self.producer_images())




    def test_producer_rejects_nonliteral_dto_mapping_types(self):
        class Mapping(dict):
            pass
        for images in (Mapping(self.producer_images()), self.producer_images()):
            if type(images) is dict:images['api']=Mapping(images['api'])
            with self.subTest(nested=type(images) is dict),self.assertRaises(self.ops.ContractError):
                self.ops.produce_release_archive(self.manifest,self.config,images)


class PublisherV2Tests(unittest.TestCase):
    setUp = PublisherProducerTests.setUp
    producer_images = PublisherProducerTests.producer_images

    def fixtures(self):
        provider='projects/123456/locations/global/workloadIdentityPools/workshop/providers/github'
        workflow='lucronn/autodata/.github/workflows/release-workshop.yml@refs/heads/master'
        self.trust={'repository':'lucronn/autodata','repository_id':'123456','repository_owner_id':'987654',
            'environment':'staging','ref':'refs/heads/master','workflow_ref':workflow,
            'oidc_issuer':'https://token.actions.githubusercontent.com',
            'oidc_audience':'https://iam.googleapis.com/'+provider,'wif_provider':provider,
            'publish_service_account':'workshop-publish@autodata-host.iam.gserviceaccount.com',
            'deploy_service_account':'workshop-deploy@autodata-host.iam.gserviceaccount.com',
            'builder_id':'https://github.com/'+workflow}
        self.archive,self.envelope=self.ops.produce_release_archive(self.manifest,self.config,self.producer_images())
        outer=io.BytesIO()
        with zipfile.ZipFile(outer,'w') as z:z.writestr('release.zip',self.archive)
        self.outer=outer.getvalue()
        self.binding=dict(self.envelope,published_run_id='1234',artifact_id='5678',
            artifact_name='workshop-release-'+self.manifest['source_sha'],
            artifact_digest='sha256:'+hashlib.sha256(self.outer).hexdigest(),artifact_bytes=len(self.outer))
        self.metadata={'id':'5678','run_id':'1234','name':self.binding['artifact_name'],
            'expired':False,'digest':self.binding['artifact_digest'],'bytes':len(self.outer)}
        identity={k:v for k,v in self.trust.items() if k not in ('publish_service_account','deploy_service_account','wif_provider')}
        identity.update(signer_workflow_ref=workflow,source_sha=self.manifest['source_sha'])
        self.subjects={role:self.subject(role) for role in ('api','ingestion','migration')}
        self.transcript={
            'run':{'id':'1234','repository':'lucronn/autodata','repository_id':'123456',
                'repository_owner_id':'987654','source_sha':self.manifest['source_sha'],'workflow_ref':workflow,
                'event':'workflow_dispatch','status':'completed','conclusion':'success'},
            'artifact':self.metadata,'archive':{'transport_archive':self.outer,'release_archive':self.archive},
            'images':self.producer_images(),'provenance':{'protocol_version':2,'simulation':True,
                'identity':identity,'subjects':self.subjects}}
        self.execution={'run_id':'1234','source_epoch':1700000000,
            'tool_sha256':{'git':'1'*64,'docker':'2'*64,'syft':'3'*64}}
        self.sbom=b'{"spdxVersion":"SPDX-2.3","documentNamespace":"https://sbom.example/doc","name":"synthetic","packages":[]}'

    def subject(self,role):
        image=self.manifest['images'][role]
        return {'image_digest':image['reference'].split('@')[1],'image_id':image['image_id'],
            'source_sha':self.manifest['source_sha'],'service_config_sha256':self.manifest['service_config_sha256'],
            'platform':'linux/amd64','provenance_uri':image['provenance_uri'],'sbom_uri':image['sbom_uri'],
            'signature_valid':True,'sbom_digest_valid':True}

    def evaluate(self,transcript=None,binding=None,trust=None):
        calls=[]; events=self.transcript if transcript is None else transcript
        def transport(request):
            calls.append(request)
            value=events[request['name']]
            if isinstance(value,Exception):raise value
            return copy.deepcopy(value)
        result=self.ops.evaluate_publication_v2(self.manifest,self.config,
            self.binding if binding is None else binding,self.trust if trust is None else trust,transport)
        return result,calls

    def test_publication_binds_independent_wrapper_inner_and_provenance(self):
        self.assertTrue(hasattr(self.ops,'evaluate_publication_v2'),'v2 evaluator missing')
        self.fixtures();result,calls=self.evaluate()
        self.assertEqual(result['status'],'transcript_consistent')
        self.assertTrue(result['simulation']);self.assertFalse(result['provenance_authenticated'])
        self.assertFalse(result['deployment_authorized'])
        self.assertEqual(result['binding_sha256'],hashlib.sha256(self.rt.canonical_bytes(self.binding)).hexdigest())
        self.assertEqual([r['name'] for r in calls],['run','artifact','archive','images','provenance'])
        self.assertNotEqual(self.binding['artifact_digest'],'sha256:'+self.binding['archive_sha256'])
        self.assertEqual(calls[0],{'name':'run','method':'GET','url':'https://api.github.com/repos/lucronn/autodata/actions/runs/1234',
            'argv':[],'body':None,'timeout_seconds':30,'max_output_bytes':65536})
        self.assertEqual(calls[2]['max_output_bytes'],16777216)
        for call in calls[3:]:self.assertIsNone(call['url']);self.assertEqual(call['argv'],[])

    def test_publication_rejects_unbound_inputs_before_observation(self):
        self.assertTrue(hasattr(self.ops,'evaluate_publication_v2'),'v2 evaluator missing')
        self.fixtures()
        mutations=[('protocol_version',True),('archive_bytes',True),('artifact_bytes',1.0),
            ('member_bytes',{'release.json':True,'images.json':1}),('artifact_name','latest'),
            ('manifest_sha256','0'*64),('service_config_sha256','0'*64),('source_sha','0'*40),('extra',1)]
        for key,value in mutations:
            binding=copy.deepcopy(self.binding);binding[key]=value
            with self.subTest(key=key),self.assertRaises(self.ops.ContractError):self.evaluate(binding=binding)
        for key,value in [('repository','evil/autodata'),('repository_id','0'),('repository_owner_id',True),
            ('environment','production'),('ref','refs/heads/other'),('oidc_issuer','https://evil.example'),
            ('oidc_audience','evil'),('builder_id','evil'),('wif_provider','evil'),
            ('publish_service_account',self.trust['deploy_service_account']),('extra',True)]:
            trust=dict(self.trust);trust[key]=value
            with self.subTest(key=key),self.assertRaises(self.ops.ContractError):self.evaluate(trust=trust)

    def test_publication_rejects_each_observation_before_later_calls(self):
        self.assertTrue(hasattr(self.ops,'evaluate_publication_v2'),'v2 evaluator missing')
        self.fixtures()
        mutations=[('run',lambda x:x.update(repository_owner_id='1')),('run',lambda x:x.update(conclusion='failure')),
            ('run',lambda x:x.update(extra=True)),('artifact',lambda x:x.update(expired=True)),
            ('artifact',lambda x:x.update(bytes=True)),('artifact',lambda x:x.update(run_id='1')),
            ('archive',lambda x:x.update(transport_archive=b'changed')),('archive',lambda x:x.update(release_archive=b'changed')),
            ('images',lambda x:x['api'].update(platform='linux/arm64')),
            ('provenance',lambda x:x.update(simulation=False)),
            ('provenance',lambda x:x['identity'].update(oidc_issuer='https://evil.example'))]
        for key,value in [('source_sha','0'*40),('image_digest','sha256:'+'0'*64),('image_id','sha256:'+'0'*64),
            ('signature_valid',False),('signature_valid',1),('sbom_digest_valid',False),('sbom_uri','https://evil.example/latest')]:
            mutations.append(('provenance',lambda x,k=key,v=value:x['subjects']['api'].update({k:v})))
        for stage,mutate in mutations:
            transcript=copy.deepcopy(self.transcript);mutate(transcript[stage])
            result,calls=self.evaluate(transcript)
            with self.subTest(stage=stage):
                self.assertEqual(result['status'],'failed');self.assertEqual(calls[-1]['name'],stage)
                self.assertNotIn('evil',str(result));self.assertIsNone(result.get('binding'))

    def test_publication_timeouts_oversize_and_exception_are_redacted(self):
        self.assertTrue(hasattr(self.ops,'evaluate_publication_v2'),'v2 evaluator missing')
        self.fixtures()
        for stage in self.transcript:
            for error in [TimeoutError('secret-token'),RuntimeError('secret-token')]:
                transcript=copy.deepcopy(self.transcript);transcript[stage]=error
                result,calls=self.evaluate(transcript)
                self.assertEqual(result['status'],'timed_out' if isinstance(error,TimeoutError) else 'failed')
                self.assertEqual(calls[-1]['name'],stage);self.assertNotIn('secret-token',str(result))
        transcript=copy.deepcopy(self.transcript);transcript['run']['extra']='X'*65536
        self.assertEqual(self.evaluate(transcript)[0]['status'],'failed')

    def orchestrate(self,alter=None):
        calls=[]
        def fake(kind):
            def call(request):
                calls.append((kind,copy.deepcopy(request)));name=request['name']
                if kind=='executor':
                    stdout=b''
                    if name=='verify_tools':stdout=self.rt.canonical_bytes(self.execution['tool_sha256'])
                    elif name=='checkout_identity':stdout=(self.manifest['source_sha']+'\n1700000000\n').encode()
                    elif name.startswith('sbom_'):stdout=self.sbom
                    elif name not in ('checkout_init','checkout_fetch','checkout_select','build_api','build_ingestion','build_migration'):
                        raise AssertionError('unknown executable operation')
                    response={'exit_code':0,'stdout':stdout}
                elif kind=='registry':
                    role=request['role'];image=self.manifest['images'][role]
                    response={'reference':image['reference'],'image_id':image['image_id'],'platform':'linux/amd64',
                        'build_source_sha':self.manifest['source_sha'],'build_config_sha256':self.manifest['service_config_sha256']}
                elif kind=='evidence':
                    response=dict(self.subjects[request['role']],simulation=True,
                        sbom_sha256=hashlib.sha256(self.sbom).hexdigest(),oidc_issuer=self.trust['oidc_issuer'],
                        oidc_audience=self.trust['oidc_audience'],signer_workflow_ref=self.trust['workflow_ref'],builder_id=self.trust['builder_id'])
                elif kind=='artifact' and name=='upload':
                    response=dict(self.metadata);response['artifact_id']=response.pop('id');response['simulation']=True
                elif kind=='artifact' and name=='readback':
                    response={'metadata':dict(self.metadata),'transport_archive':self.outer,'release_archive':self.archive}
                    response['metadata']['artifact_id']=response['metadata'].pop('id')
                else:raise AssertionError('unknown transport operation')
                if alter is not None:response=alter(kind,request,response)
                if isinstance(response,Exception):raise response
                return response
            return call
        result=self.ops.orchestrate_publication(self.manifest,self.config,self.trust,self.execution,
            executor=fake('executor'),registry_transport=fake('registry'),evidence_transport=fake('evidence'),artifact_transport=fake('artifact'))
        return result,calls

    def test_concrete_orchestration_drives_build_evidence_upload_and_separate_check(self):
        self.assertTrue(hasattr(self.ops,'orchestrate_publication'),'orchestrator missing')
        self.fixtures();result,calls=self.orchestrate()
        self.assertEqual(result['status'],'transcript_consistent');self.assertEqual(result['binding'],self.binding)
        self.assertFalse(result['provenance_authenticated']);self.assertFalse(result['deployment_authorized'])
        self.assertEqual([x[1]['name'] for x in calls],['verify_tools','checkout_init','checkout_fetch','checkout_select','checkout_identity',
            'build_api','image','build_ingestion','image','build_migration','image',
            'sbom_api','publish_and_verify','sbom_ingestion','publish_and_verify','sbom_migration','publish_and_verify','upload','readback'])
        self.assertEqual(calls[2][1]['argv'],['/usr/bin/git','-C','/work/workshop-release/source','-c','core.hooksPath=/dev/null',
            'fetch','--no-tags','--depth=1','https://github.com/lucronn/autodata.git',self.manifest['source_sha']])
        for role,dockerfile in [('api','apps/api-go/Dockerfile'),('ingestion','workers/ingestion-python/Dockerfile'),('migration','infra/deploy/gce/migration.Dockerfile')]:
            command=next(r for k,r in calls if r['name']=='build_'+role)
            self.assertEqual(command['argv'],['/usr/bin/docker','buildx','build','--platform','linux/amd64','--provenance=mode=max',
                '--sbom=true','--push','--build-arg','SOURCE_DATE_EPOCH=1700000000','--file',dockerfile,'--tag',
                self.config['resources']['artifact_repository']+'/'+role+':source-'+self.manifest['source_sha'],
                '--metadata-file','/work/workshop-release/'+role+'-build.json','.'])
            self.assertEqual(command['timeout_seconds'],1800)
        upload=next(r for k,r in calls if r['name']=='upload')
        self.assertEqual(upload['members'],{'release.zip':self.archive})
        host,calls=self.host(result)
        self.assertEqual(host['status'],'unavailable');self.assertEqual(len(calls),1)

    def test_orchestrator_failures_at_every_stage_never_publish_success(self):
        self.assertTrue(hasattr(self.ops,'orchestrate_publication'),'orchestrator missing')
        self.fixtures();_,reference=self.orchestrate()
        for position in range(len(reference)):
            for error in [RuntimeError('sensitive'),TimeoutError('sensitive')]:
                count=[0]
                def alter(kind,request,response):
                    index=count[0];count[0]+=1
                    return error if index==position else response
                result,calls=self.orchestrate(alter)
                with self.subTest(position=position,error=type(error)):
                    self.assertEqual(len(calls),position+1)
                    self.assertEqual(result['status'],'timed_out' if isinstance(error,TimeoutError) else 'failed')
                    self.assertIsNone(result['binding']);self.assertNotIn('sensitive',str(result))

    def test_orchestrator_rejects_checkout_build_sbom_evidence_and_artifact_drift(self):
        self.assertTrue(hasattr(self.ops,'orchestrate_publication'),'orchestrator missing')
        self.fixtures()
        cases=[('verify_tools',lambda x:x.update(stdout=b'{}')),
            ('checkout_identity',lambda x:x.update(stdout=(self.manifest['source_sha']+'\n1\n').encode())),
            ('build_ingestion',lambda x:x.update(exit_code=1)),('build_api',lambda x:x.update(exit_code=True)),
            ('build_api',lambda x:x.update(stdout=b'X'*65537)),
            ('image',lambda x:x.update(image_id='sha256:'+'0'*64)),('image',lambda x:x.update(build_config_sha256='0'*64)),
            ('image',lambda x:x.update(build_source_sha='0'*40)),
            ('sbom_api',lambda x:x.update(stdout=b'{"spdxVersion":"SPDX-2.3","spdxVersion":"SPDX-2.3"}')),
            ('sbom_api',lambda x:x.update(stdout=b'X'*4194305)),
            ('publish_and_verify',lambda x:x.update(signature_valid=False)),
            ('publish_and_verify',lambda x:x.update(oidc_audience='evil')),
            ('publish_and_verify',lambda x:x.update(sbom_sha256='0'*64)),
            ('upload',lambda x:x.update(bytes=True)),('upload',lambda x:x.update(run_id='9')),
            ('readback',lambda x:x.update(release_archive=b'changed')),
            ('readback',lambda x:x.update(transport_archive=b'changed'))]
        for name,mutate in cases:
            def alter(kind,request,response):
                if request['name']==name:mutate(response)
                return response
            result,calls=self.orchestrate(alter)
            with self.subTest(name=name):self.assertEqual(result['status'],'failed');self.assertIsNone(result['binding'])

    def test_orchestrator_invalid_policy_causes_no_operations(self):
        self.assertTrue(hasattr(self.ops,'orchestrate_publication'),'orchestrator missing')
        self.fixtures()
        for key,value in [('source_epoch',True),('run_id','0'),('extra',1),('tool_sha256',{'git':'1'*64})]:
            execution=dict(self.execution);execution[key]=value
            def forbidden(*args):self.fail('operation on invalid input')
            with self.subTest(key=key),self.assertRaises(self.ops.ContractError):
                self.ops.orchestrate_publication(self.manifest,self.config,self.trust,execution,
                    executor=forbidden,registry_transport=forbidden,evidence_transport=forbidden,artifact_transport=forbidden)

    def host(self,publication=None,response=None):
        if publication is None:publication=self.evaluate()[0]
        checks={k:True for k in ('config','manifest','disk_uuid','metadata_guard','storage_guard','secrets','cached_images','migration_tree')}
        checks.update(schema=False,services=False,runtime_evidence=False)
        receipt={'schema_version':1,'operation':'deploy.sh check','run_id':None,'source_sha':self.manifest['source_sha'],
            'status':'failed','started_at':'2026-11-03T12:00:00Z','finished_at':'2026-11-03T12:00:01Z','checks':checks,'failure_code':'missing_dependency'}
        value={'exit_code':3,'receipt':receipt} if response is None else response
        calls=[]
        def transport(request):
            calls.append(request)
            if isinstance(value,Exception):raise value
            return copy.deepcopy(value)
        result=self.ops.evaluate_host_check(self.manifest,self.config,self.binding,self.trust,publication,transport)
        return result,calls

    def test_host_check_fixed_argv_cannot_promote_catalog_readiness(self):
        self.assertTrue(hasattr(self.ops,'evaluate_host_check'),'host check missing')
        self.fixtures();result,calls=self.host()
        self.assertEqual(result['status'],'unavailable');self.assertEqual(result['failure_code'],'missing_dependency')
        self.assertEqual(result['checks'],{'publication_consistent':True,'host_reply_valid':True,'schema':False,'services':False,'runtime_evidence':False})
        self.assertEqual(calls[0],{'name':'host_check','method':None,'url':None,'body':None,'timeout_seconds':30,'max_output_bytes':65536,
            'argv':['/usr/bin/gcloud','compute','ssh','workshop-stage','--project','autodata-host','--zone','us-central1-a',
                '--tunnel-through-iap','--quiet','--command','sudo -n /opt/autodata/bin/deploy.sh check '+self.manifest['source_sha']]})
        self.assertFalse(result['deployment_authorized'])

    def test_host_rejects_success_unknown_fields_readiness_and_wrong_source(self):
        self.assertTrue(hasattr(self.ops,'evaluate_host_check'),'host check missing')
        self.fixtures();_,calls=self.host()
        # Obtain fixture by independently defining the deployed reply contract.
        checks={k:False for k in ('config','manifest','disk_uuid','metadata_guard','storage_guard','secrets','cached_images','migration_tree','schema','services','runtime_evidence')}
        base={'exit_code':3,'receipt':{'schema_version':1,'operation':'deploy.sh check','run_id':None,'source_sha':self.manifest['source_sha'],
            'status':'failed','started_at':'2026-11-03T12:00:00Z','finished_at':'2026-11-03T12:00:01Z','checks':checks,'failure_code':'missing_dependency'}}
        cases=[lambda x:x.update(exit_code=0),lambda x:x.update(exit_code=True),lambda x:x.update(extra=True),
            lambda x:x['receipt'].update(source_sha='0'*40),lambda x:x['receipt'].update(schema_version=True),
            lambda x:x['receipt'].update(finished_at='2026-11-03T11:59:59Z'),lambda x:x['receipt']['checks'].update(schema=True),
            lambda x:x['receipt']['checks'].update(services=True),lambda x:x['receipt']['checks'].update(runtime_evidence=True),
            lambda x:x['receipt']['checks'].update(unknown=False),lambda x:x['receipt']['checks'].update(config=1)]
        for mutate in cases:
            response=copy.deepcopy(base);mutate(response)
            self.assertEqual(self.host(response=response)[0]['status'],'failed')
        response=copy.deepcopy(base);response['exit_code']=5;response['receipt']['failure_code']='operation_timed_out'
        self.assertEqual(self.host(response=response)[0]['status'],'timed_out')
        self.assertEqual(self.host(response=TimeoutError('hidden'))[0]['status'],'timed_out')
        publication=self.evaluate()[0]
        for key,value in [('provenance_authenticated',True),('simulation',False),('deployment_authorized',True),('binding_sha256','0'*64)]:
            altered=dict(publication);altered[key]=value
            with self.subTest(key=key),self.assertRaises(self.ops.ContractError):self.host(altered)


if __name__ == '__main__': unittest.main()
