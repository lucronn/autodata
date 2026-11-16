import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from private_selector_adapter_fakes import manifest, state, c
import private_selector_local_transport as m


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.root = self.base / 'execution'; self.root.mkdir(mode=0o700)
        self.package = self.base / 'package'; self.package.mkdir(mode=0o700)
        self.off = self.base / 'evidence'; self.off.mkdir(mode=0o700)
        self.source = self.package / 'source'; self.source.mkdir(mode=0o700)
        self.source_file = self.source / 'authored.py'; self.source_file.write_text('synthetic = True\n')
        self.source_file.chmod(0o444); self.source.chmod(0o555)
        archive = self.package / 'source.tar'; archive.write_bytes(b'authored archive'); archive.chmod(0o600)
        inventory = self.package / 'manifest.json'
        inventory.write_text(json.dumps({'source_sha': c.SOURCE, 'tree': c.TREE,
                                         'files': {'authored.py': sha(self.source_file)}})); inventory.chmod(0o600)
        self.transport_source = Path(m.__file__).read_bytes(); self.contract_source = Path(c.__file__).read_bytes()
        for key, value in [('ROOT', self.root), ('PACKAGE', self.package), ('EVIDENCE', self.base),
                           ('PHYSICAL_DEVICE', self.root.stat().st_dev), ('OFFLOADED_DEVICE', self.off.stat().st_dev),
                           ('ARCHIVE_SHA', sha(archive)), ('ARCHIVE_BYTES', archive.stat().st_size),
                           ('__file__', str(self.root / 'private_selector_local_transport.py'))]:
            item = patch.object(m, key, value); item.start(); self.addCleanup(item.stop)
        item = patch.object(c, '__file__', str(self.root / 'private_selector_adapter_contract.py'))
        item.start(); self.addCleanup(item.stop)
        original_regular = m.regular
        def owned_regular(path, **kwargs):
            kwargs.setdefault('device', self.root.stat().st_dev)
            return original_regular(path, **kwargs)
        item = patch.object(m, 'regular', side_effect=owned_regular); item.start(); self.addCleanup(item.stop)
        item = patch.object(m, 'SOURCE_EXECUTABLE_PATHS', {c.SOURCE: frozenset()})
        item.start(); self.addCleanup(item.stop)
        self.value = manifest('fixture')
        self.value['transport'] = {'offloaded_root': str(self.off), 'docker_start_free': 1000000000}
        self.backend = m.LocalTransport(self.value, dispatch_enabled=True, external_seal_sha='0' * 64,
                                        runner=Mock(return_value=b'/mnt/openfoam/docker\n'))
        self.addCleanup(self.backend.close)
        for name, path in self.backend.paths().items():
            if path.exists(): continue
            data = self.transport_source if name == 'transport' else self.contract_source if name == 'contract' else b'{}'
            path.write_bytes(data); path.chmod(0o600)
        (self.root / 'docker-config').mkdir(mode=0o700)
        self.reseal()

    def reseal(self):
        self.value['artifacts'] = {name: sha(path) for name, path in self.backend.paths().items()}
        seal = {'manifest_sha256': c.digest(self.value), 'artifacts': self.value['artifacts'],
                'rollback_manifests': {}}
        path = self.root / 'transport-execution-seal.json'; path.write_text(json.dumps(seal)); path.chmod(0o600)
        self.backend.external_seal_sha = sha(path)

    def test_default_transport_refuses_before_process_socket_http_or_write(self):
        backend = m.LocalTransport(self.value)
        with patch.object(m.subprocess, 'Popen', side_effect=AssertionError('unowned child')), \
             patch.object(m.socket, 'socket', side_effect=AssertionError('socket')), \
             patch.object(m.http.client, 'HTTPConnection', side_effect=AssertionError('HTTP')):
            for operation in [lambda: backend.docker('info'), lambda: backend.compact_snapshot(),
                              lambda: backend.loopback('/healthz'), lambda: backend.record_once('attempt', {}),
                              lambda: backend.create_payload('name', {})]:
                with self.assertRaises(c.Refused): operation()
        self.assertFalse((self.root / 'attempt.json').exists())

    def test_external_fixed_hash_required_even_with_dispatch_flag(self):
        self.backend.external_seal_sha = None
        with self.assertRaises(c.Refused): self.backend.seal()

    def test_valid_owned_seal_and_full_source_inventory(self):
        self.assertEqual(self.backend.seal()['manifest_sha256'], c.digest(self.value))

    def test_archive_pinned_readonly_executable_is_admitted(self):
        self.source.chmod(0o755)
        paths=('infra/deploy/gce/backup-host.sh','infra/deploy/gce/cloud-bootstrap.sh',
               'infra/deploy/gce/deploy.sh','infra/deploy/gce/restore.sh',
               'infra/deploy/gce/runtime-entrypoint.sh','scripts/dev/ingest_banktwo_service.py')
        m.SOURCE_EXECUTABLE_PATHS[c.SOURCE]=frozenset(paths)
        inventory=json.loads((self.package/'manifest.json').read_text())
        for name in paths:
            p=self.source/name;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text('authored archive executable\n');p.chmod(0o555)
            inventory['files'][name]=sha(p)
        for folder,dirs,files in os.walk(self.source,topdown=False):Path(folder).chmod(0o555)
        (self.package/'manifest.json').write_text(json.dumps(inventory))
        self.reseal()
        self.backend.seal()

    def test_executable_pin_rejects_lost_exec_unpinned_exec_or_writable_modes(self):
        self.test_archive_pinned_readonly_executable_is_admitted()
        executable=self.source/'infra/deploy/gce/backup-host.sh'
        for mode in (0o444,0o755,0o644):
            executable.chmod(mode)
            with self.assertRaises(c.Refused):self.backend.seal()
        executable.chmod(0o555)
        self.source_file.chmod(0o555)
        with self.assertRaises(c.Refused):self.backend.seal()

    def test_executable_pin_requires_all_paths_and_known_source(self):
        self.test_archive_pinned_readonly_executable_is_admitted()
        inventory=json.loads((self.package/'manifest.json').read_text())
        name='infra/deploy/gce/backup-host.sh'
        del inventory['files'][name]
        (self.package/'manifest.json').write_text(json.dumps(inventory));self.reseal()
        with self.assertRaisesRegex(c.Refused,'source_mode_pin'):self.backend.seal()
        inventory['source_sha']='a'*40
        (self.package/'manifest.json').write_text(json.dumps(inventory));self.reseal()
        with self.assertRaisesRegex(c.Refused,'source_mode_pin'):
            m.verify_inventory(self.package,sha(self.package/'manifest.json'),'a'*40,c.TREE)

    def test_source_edit_extra_file_and_writable_mode_refuse(self):
        self.source_file.chmod(0o644)
        with self.assertRaises(c.Refused): self.backend.seal()
        self.source_file.chmod(0o444)
        self.source.chmod(0o755); extra = self.source / 'extra'; extra.write_text('not approved'); extra.chmod(0o444)
        self.source.chmod(0o555)
        with self.assertRaises(c.Refused): self.backend.seal()

    def test_artifact_symlink_hardlink_or_hash_drift_refuses(self):
        target = self.root / 'fixture_client.py'; target.unlink(); target.symlink_to(self.root / 'fixture_bootstrap.py')
        with self.assertRaises(c.Refused): self.backend.seal()
        target.unlink(); target.write_bytes(b'{}'); target.chmod(0o600)
        link = self.root / 'hardlink'; os.link(target, link)
        with self.assertRaises(c.Refused): self.backend.seal()
        link.unlink(); target.write_bytes(b'drift')
        with self.assertRaises(c.Refused): self.backend.seal()

    def test_receipt_fsync_file_before_directory_and_no_replay(self):
        events = []; real = os.fsync
        def fsync(fd):
            events.append('directory' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'file'); real(fd)
        with patch.object(m.os, 'fsync', side_effect=fsync): self.backend.record_once('attempt', {'owned': True})
        self.assertEqual(events, ['file', 'directory'])
        with self.assertRaises(FileExistsError): self.backend.record_once('attempt', {})
        self.assertEqual(stat.S_IMODE((self.root / 'attempt.json').stat().st_mode), 0o600)

    def test_lifetime_flock_refuses_second_owner(self):
        self.backend.seal(); self.backend.lease()
        second = m.LocalTransport(self.value, external_seal_sha=self.backend.external_seal_sha,
                                  dispatch_enabled=True)
        try:
            with self.assertRaises(c.Refused): second.lease()
        finally: second.close()

    def test_replaced_lock_inode_refuses_mutation_receipt(self):
        self.backend.lease(); path = self.root / 'transport.lock'; path.unlink(); path.touch(mode=0o600)
        with self.assertRaises(c.Refused): self.backend.record_once('attempt', {})
        self.assertFalse((self.root / 'attempt.json').exists())

    def test_failed_file_fsync_leaves_attempt_and_never_overwrites(self):
        with patch.object(m.os, 'fsync', side_effect=OSError('authored failure')):
            with self.assertRaises(OSError): self.backend.record_once('attempt', {'intent': True})
        self.assertTrue((self.root / 'attempt.json').exists())
        with self.assertRaises(FileExistsError): self.backend.record_once('attempt', {})

    def test_hostile_context_uses_fixed_daemon_args_and_data_root(self):
        runner = Mock(side_effect=[b'/mnt/openfoam/docker\n', b'[]']); self.backend.runner = runner
        with patch.object(self.backend, 'socket_check'), patch.dict(os.environ, {'DOCKER_HOST': 'tcp://evil',
             'DOCKER_CONTEXT': 'evil', 'HTTP_PROXY': 'http://evil'}):
            self.backend.docker('inspect', 'a' * 64)
        for call in runner.call_args_list:
            argv = call.args[0]
            self.assertEqual(argv[:5], ['/usr/bin/docker', '--config', str(self.root / 'docker-config'),
                                       '--host', 'unix:///var/run/docker.sock'])

    def test_wrong_data_root_refuses_before_requested_command(self):
        self.backend.runner = Mock(return_value=b'/wrong\n')
        with patch.object(self.backend, 'socket_check'):
            with self.assertRaises(c.Refused): self.backend.docker('start', 'a' * 64)
        self.assertEqual(self.backend.runner.call_count, 1)

    def test_socket_drift_refuses_before_child(self):
        fake = Mock(); fake.stat.return_value = Mock(st_mode=stat.S_IFSOCK, st_dev=25, st_ino=1)
        fake.resolve.return_value = m.SOCKET_REAL
        with patch.object(m, 'SOCKET', fake):
            with self.assertRaises(c.Refused): self.backend.socket_check()
        self.backend.runner.assert_not_called()

    def test_unix_connection_checks_identity_before_actual_connect(self):
        checker = Mock(side_effect=c.Refused('drift'))
        with patch.object(m.socket, 'socket') as create:
            with self.assertRaises(c.Refused): m.UnixDocker(checker).connect()
        create.assert_not_called()

    def test_expired_unix_connection_refuses_before_socket_and_retains_response_socket(self):
        connection = m.UnixDocker(Mock()); owned = Mock()
        connection.owned_socket = owned; connection.sock = None
        connection.abort()
        owned.shutdown.assert_called_once_with(m.socket.SHUT_RDWR); owned.close.assert_called_once()
        with patch.object(m.socket, 'socket') as create:
            with self.assertRaises(c.Refused): connection.connect()
        create.assert_not_called()

    def test_raw_create_requires_exact_sealed_payload_before_connect(self):
        with patch.object(self.backend, 'socket_check'), patch.object(m, 'UnixDocker') as connection:
            name = 'autodata-selector-fixture-' + self.value['run_id'] + '-worker'
            with self.assertRaises(c.Refused): self.backend.create_payload(name, {'unapproved': True})
        connection.assert_not_called()

    def test_raw_connect_rechecks_after_payload_and_daemon_admission(self):
        name = 'autodata-selector-fixture-' + self.value['run_id'] + '-worker'
        checks = [None, None, c.Refused('socket changed before connect')]
        with patch.object(self.backend, 'socket_check', side_effect=checks), \
             patch.object(self.backend, 'docker'), patch.object(self.backend, 'validate_fixture_payload'), \
             patch.object(m.socket, 'socket') as connection:
            with self.assertRaises(c.Refused): self.backend.create_payload(name, {})
        connection.assert_not_called()

    def test_actual_inspect_preserves_created_running_normalization(self):
        identifier = 'a' * 64
        config = {'User': ''}; mounts = [{'Source': str(self.source), 'Destination': '/app', 'RW': False}]
        expected = {'id': identifier, 'image': c.IMAGE, 'source': c.SOURCE, 'config': c.digest(config),
                    'mounts': c.digest(mounts), 'hostconfig_by_status': {
                        'created': c.digest({'OomKillDisable': False}),
                        'running': c.digest({'OomKillDisable': None}),
                        'exited': c.digest({'OomKillDisable': None})}}
        self.value['candidate'] = expected
        for status in ('created', 'running', 'exited'):
            raw = {'Id': identifier, 'Image': c.IMAGE, 'Config': config, 'Mounts': mounts,
                   'HostConfig': {'OomKillDisable': False if status == 'created' else None},
                   'State': {'Status': status, 'Running': status == 'running', 'Restarting': False,
                             'Pid': 1 if status == 'running' else 0, 'StartedAt': 'authored'}, 'RestartCount': 0}
            with patch.object(self.backend, 'raw_inspect', return_value=raw):
                normalized = self.backend.inspect(identifier)
            self.assertEqual(c.identity(normalized, expected)['status'], status)
            if status == 'running':
                normalized['hostconfig'] = expected['hostconfig_by_status']['created']
                with self.assertRaises(c.Refused): c.identity(normalized, expected)

    def test_raw_inspect_normalizes_only_exact_requested_id(self):
        with patch.object(self.backend, 'docker', return_value=json.dumps([{'Id': 'b' * 64}]).encode()):
            with self.assertRaises(c.Refused): self.backend.raw_inspect('a' * 64)

    def test_runtime_stop_rechecks_full_identity(self):
        self.backend.phase = 'runtime'; self.value['candidate'] = manifest('runtime')['candidate']
        wrong = state(c.OLD_IDENTITY, 'running'); wrong['config'] = '0' * 64
        with patch.object(self.backend, 'inspect', return_value=wrong), patch.object(self.backend, 'docker') as docker:
            with self.assertRaises(c.Refused): self.backend.stop(c.OLD)
        docker.assert_not_called()

    def test_runtime_stop_preserves_immediate_fence_command(self):
        self.backend.phase='runtime'
        with patch.object(self.backend,'inspect',return_value=state(c.OLD_IDENTITY,'running')), \
             patch.object(self.backend,'docker') as docker:
            self.backend.stop(c.OLD)
        docker.assert_called_once_with('stop','--time','0',c.OLD,timeout=5,limit=4096)

    def test_sql_is_single_fixed_connection_readonly_bounded_and_no_user_input(self):
        query = m.combined_sql()
        self.assertEqual(query.count('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY'), 1)
        self.assertIn("transaction_timeout='12s'", query); self.assertEqual(len(m.TABLES), 39)
        value = {'inventory': list(m.TABLES),
                 'tables': {name: {'count': 0, 'rows': '0' * 32, 'schema': '1' * 32} for name in m.TABLES},
                 'connection': {'pid': 1, 'snapshot': '1:2:', 'isolation': 'repeatable read',
                                'read_only': 'on', 'default_read_only': 'on'}}
        database = {key: key for key in ('Id', 'Image', 'Config', 'HostConfig', 'Mounts')}
        self.backend.phase = 'runtime'; self.value['transport'].update(sql_approved=True,
                                                        postgres_identity_sha256=c.digest(database))
        with patch.object(self.backend, 'seal'), patch.object(self.backend, 'raw_inspect', return_value=database), \
             patch.object(self.backend, 'docker', return_value=json.dumps(value).encode()) as docker:
            self.assertEqual(self.backend.compact_snapshot(), value)
        argv = docker.call_args.args
        self.assertIn('PGOPTIONS=-c default_transaction_read_only=on', argv)
        self.assertEqual(argv.count('-c'), 1); self.assertEqual(docker.call_args.kwargs['timeout'], 15)
        self.assertEqual(argv[-1], query)

    def test_sql_not_approved_or_pg_identity_drift_never_executes_sql(self):
        self.backend.phase = 'runtime'; self.value['transport']['sql_approved'] = False
        with patch.object(self.backend, 'seal'), patch.object(self.backend, 'docker') as docker:
            with self.assertRaises(c.Refused): self.backend.compact_snapshot()
        docker.assert_not_called()

    def test_forbidden_selector_http_never_opens_connection(self):
        self.backend.phase = 'runtime'; self.value['transport']['http_approved'] = True
        with patch.object(self.backend, 'seal'), patch.object(m.http.client, 'HTTPConnection') as connection:
            with self.assertRaises(c.Refused): self.backend.loopback('/v1/catalog/years')
        connection.assert_not_called()

    def test_loopback_ignores_proxy_environment(self):
        self.backend.phase = 'runtime'; self.value['transport']['http_approved'] = True
        response = Mock(status=200); response.read.return_value = b'{}'
        connection = Mock(); connection.getresponse.return_value = response
        with patch.object(self.backend, 'seal'), patch.object(m, 'DeadlineLoopback', return_value=connection) as factory, \
             patch.dict(os.environ, {'HTTP_PROXY': 'http://evil', 'HTTPS_PROXY': 'http://evil'}):
            self.assertEqual(self.backend.loopback('/healthz'), b'{}')
        factory.assert_called_once_with()

    def test_deadline_keeps_socket_after_response_takes_ownership(self):
        connection = m.DeadlineLoopback(); owned = Mock(); connection.owned_socket = owned; connection.sock = None
        connection.abort()
        owned.shutdown.assert_called_once_with(m.socket.SHUT_RDWR); owned.close.assert_called_once()
        self.assertTrue(connection.expired.is_set())

    def test_expired_loopback_never_connects(self):
        connection = m.DeadlineLoopback(); connection.expired.set()
        with patch.object(m.http.client.HTTPConnection, 'connect') as connect:
            with self.assertRaises(c.Refused): connection.connect()
        connect.assert_not_called()

    def test_delayed_bootstrap_metadata_waits_and_preserves_validated_receipt(self):
        identifier='b'*64;self.backend.created[identifier]='bootstrap'
        metadata={'database':'lifecycle_test_'+self.value['run_id'],
                  **dict.fromkeys(('configuration','foreign_configuration','owner','organization','entitlement'),
                                  '00000000-0000-4000-8000-000000000001')}
        with patch.object(self.backend,'fixture_identity'),patch.object(self.backend,'raw_inspect',return_value={'State':{'Running':True}}), \
             patch.object(self.backend,'docker',side_effect=[b'',json.dumps(metadata).encode()]) as docker, \
             patch.object(self.backend,'pause') as pause:
            self.backend.wait_fixture_ready(identifier)
        pause.assert_called_once_with(.2)
        self.assertEqual(self.backend.fixture_metadata,metadata)
        self.assertEqual(docker.call_count,2)

    def test_exited_bootstrap_never_reads_logs_or_claims_readiness(self):
        identifier='b'*64;self.backend.created[identifier]='bootstrap'
        with patch.object(self.backend,'fixture_identity'),patch.object(self.backend,'raw_inspect',return_value={'State':{'Running':False}}), \
             patch.object(self.backend,'docker') as docker:
            with self.assertRaises(c.Refused):self.backend.wait_fixture_ready(identifier)
        docker.assert_not_called();self.assertIsNone(self.backend.fixture_metadata)

    def test_bootstrap_readiness_deadline_and_wrong_database_refuse(self):
        identifier='b'*64;self.backend.created[identifier]='bootstrap'
        with patch.object(self.backend,'fixture_identity'),patch.object(m.time,'monotonic',side_effect=[0,61]), \
             patch.object(self.backend,'docker') as docker:
            with self.assertRaises(c.Refused):self.backend.wait_fixture_ready(identifier)
        docker.assert_not_called()
        with patch.object(self.backend,'fixture_identity'),patch.object(self.backend,'raw_inspect',return_value={'State':{'Running':True}}), \
             patch.object(self.backend,'docker',return_value=b'{"database":"protected"}'):
            with self.assertRaises(c.Refused):self.backend.wait_fixture_ready(identifier)
        self.assertIsNone(self.backend.fixture_metadata)

    def test_graceful_bootstrap_stop_requires_positive_cleanup_log(self):
        identifier='b'*64;self.backend.created[identifier]='bootstrap'
        for removed in (True,False):
            receipt={'cleanup':{'database_removed':removed,'bucket_removed':True}}
            with patch.object(self.backend,'fixture_identity'), \
                 patch.object(self.backend,'docker',side_effect=[b'',json.dumps(receipt).encode()]) as docker:
                if removed:self.backend.stop_fixture(identifier)
                else:
                    with self.assertRaises(c.Refused):self.backend.stop_fixture(identifier)
            self.assertEqual(self.backend.fixture_cleanup,removed)
            self.assertEqual(docker.call_args_list[0].args,('stop','--time','65',identifier))

    def test_cli_is_metadata_only_even_for_approved_mock_manifest(self):
        p = self.base / 'dry.json'; p.write_text(json.dumps(self.value)); p.chmod(0o600)
        with patch.object(m, 'LocalTransport', side_effect=AssertionError('must not construct')), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(m.main(['--validate-only', '--phase', 'fixture', '--manifest', str(p)]), 0)
        self.assertFalse(json.loads(out.getvalue())['live_dispatch_enabled'])

    def test_owned_child_output_and_timeout_are_bounded_and_redacted(self):
        for program, timeout, limit in [("print('SENTINEL_SECRET'*10000)", 1, 32),
                                         ('import time;time.sleep(10)', .05, 100)]:
            with self.assertRaises(c.Refused) as error:
                m.bounded(['/usr/bin/python3', '-I', '-c', program], timeout=timeout, limit=limit)
            self.assertNotIn('SENTINEL_SECRET', str(error.exception))

    def test_child_environment_has_no_host_credentials_or_proxy(self):
        with patch.dict(os.environ, {'DOCKER_HOST': 'tcp://secret', 'HTTPS_PROXY': 'http://secret',
                                     'PYTHONPATH': '/secret', 'AWS_SECRET_ACCESS_KEY': 'secret'}):
            value = json.loads(m.bounded(['/usr/bin/python3', '-I', '-c',
                                         'import os,json;print(json.dumps(dict(os.environ)))']))
        self.assertEqual(value, m.CHILD_ENV)


if __name__ == '__main__': unittest.main()
