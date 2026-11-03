"""Offline B boundary tests: all provider events are finite fake transcripts."""
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
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


if __name__ == '__main__': unittest.main()
