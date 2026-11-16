"""Owned fixture orchestration core. Backend injection only; CLI is dry-only."""
import private_selector_adapter_contract as c

CHECKS = {'actual_image', 'source_readonly', 'rootfs_readonly', 'environment_names',
          'entrypoint_user_workdir', 'synthetic_network_only', 'synthetic_credentials_only',
          'child_import', 'two_bank_years_makes_models', 'partial_provenance', 'cooldown',
          'stall_kill_reap', 'configuration_budget_unchanged', 'purchase_false', 'quote_false',
          'grants_library_merchant', 'payment_denied', 'provider_none', 'svg_png',
          'no_article_recapture', 'no_supplier_or_payment_or_model_request'}
OWNED_POLICY = {'source_mount_readonly': True, 'rootfs_readonly': True,
                'no_host_ports': True, 'private_fixture_network': True,
                'synthetic_endpoints_only': True, 'credentials_substituted': True,
                'environment_names_verified': True, 'entrypoint_user_workdir_verified': True,
                'memory_limit': 768 * c.MIB, 'pids_limit': 128,
                'tmpfs_limit': 64 * c.MIB}


class Fixture:
    def __init__(self, manifest, backend):
        self.manifest, self.backend = manifest, backend

    def check(self):
        c.boundary(self.backend, self.manifest, 'fixture')

    def owned(self, identifier, role):
        c.require(c.full_id(identifier) and identifier not in (c.OLD, c.SECONDARY), 'fixture_id')
        value = self.backend.fixture_identity(identifier)
        c.require(c.typed_equal(value, {'id': identifier, 'run_id': self.manifest['run_id'], 'role': role,
                                        'image': c.TEST_IMAGE if role == 'bootstrap' else c.IMAGE,
                                        'source': c.SOURCE, 'owned_synthetic': True,
                                        'policy': OWNED_POLICY}), 'fixture_ownership')

    def run(self):
        self.check()
        c.incumbent(self.backend.inspect(c.OLD))
        before = self.backend.serving_snapshot()
        self.backend.record_once('fixture-attempt', {'manifest': c.digest(self.manifest)})
        owned = []
        result, failed, cleanup_failed = None, False, False
        try:
            for role in ('bootstrap', 'worker'):
                self.check()
                try:
                    identifier = self.backend.create_fixture(role, self.manifest)
                except Exception:
                    cleanup_failed = True
                    raise
                # An unverified returned ID is never stopped or removed.
                try:
                    self.owned(identifier, role)
                except Exception:
                    cleanup_failed = True
                    raise
                owned.append((identifier, role))
                self.backend.record_once('fixture-owned-' + role,
                                         {'id': identifier, 'role': role, 'run_id': self.manifest['run_id']})
                self.check(); self.owned(identifier, role)
                self.backend.start_fixture(identifier)
                if role == 'bootstrap': self.backend.wait_fixture_ready(identifier)
            result = self.backend.exercise_fixture(owned[-1][0], self.manifest)
            c.require(isinstance(result, dict) and set(result) == CHECKS
                      and all(v is True for v in result.values()), 'fixture_acceptance')
        except Exception:
            failed = True
        finally:
            for identifier, role in reversed(owned):
                try:
                    c.require(self.backend.fixture_cleanup_owned(identifier, role) is True, 'fixture_cleanup_ownership')
                    self.backend.stop_fixture(identifier)
                    c.require(self.backend.fixture_stopped(identifier) is True, 'fixture_stop_unknown')
                    c.require(self.backend.fixture_cleanup_owned(identifier, role) is True, 'fixture_cleanup_ownership')
                    self.backend.remove_fixture(identifier)
                    c.require(self.backend.fixture_absent(identifier) is True, 'fixture_remove_unknown')
                    self.backend.record_once('fixture-cleaned-' + role, {'id': identifier})
                except Exception:
                    cleanup_failed = True
            try:
                c.require(self.backend.owned_database_bucket_removed(self.manifest['run_id']) is True,
                          'synthetic_data_cleanup_unknown')
            except Exception:
                cleanup_failed = True
            # Boundary drift is acceptance evidence; it must never block owned cleanup.
            try:
                self.check()
                c.require(self.backend.serving_snapshot() == before, 'serving_changed')
            except Exception:
                failed = True
        if failed or cleanup_failed:
            self.backend.record_once('fixture-hold', {'acceptance_failed': failed,
                                                     'cleanup_unknown': cleanup_failed})
            raise c.Refused('fixture_failed_or_cleanup_unknown') from None
        receipt = {'checks': result, 'owned_cleanup': True, 'serving_unchanged': True,
                   'manifest': c.digest(self.manifest)}
        self.backend.record_once('fixture-result', receipt)
        return receipt


if __name__ == '__main__':
    raise SystemExit(c.cli('fixture'))
