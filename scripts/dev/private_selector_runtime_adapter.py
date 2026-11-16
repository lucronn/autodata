"""Separate activation/recovery core. Backend injection only; CLI is dry-only."""
import private_selector_adapter_contract as c

POSTCHECK = {'health': 200, 'purchase_enabled': False, 'quote_purchasable': False,
             'provider_none': True, 'protected27_equal': True, 'catalog12_equal': True,
             'public_unchanged': True}


class Runtime:
    def __init__(self, manifest, backend):
        self.manifest, self.backend = manifest, backend

    def check(self):
        c.boundary(self.backend, self.manifest, 'runtime')

    def old(self):
        return c.identity(self.backend.inspect(c.OLD), c.OLD_IDENTITY)

    def candidate(self):
        return c.identity(self.backend.inspect(self.manifest['candidate']['id']),
                          self.manifest['candidate'])

    def postcheck(self, identifier):
        result = self.backend.postcheck(identifier)
        c.require(isinstance(result, dict) and set(result) == set(POSTCHECK)
                  and all(type(result[k]) is type(value) and result[k] == value
                          for k, value in POSTCHECK.items()), 'postcheck')

    def activate(self):
        self.check()
        old, new = self.old(), self.candidate()
        c.incumbent(old)
        c.require(new.get('status') == 'created' and new.get('running') is False
                  and new.get('pid') == 0 and new.get('restart_count') == 0, 'candidate_not_created')
        self.backend.record_once('activation-attempt', {'candidate': new['id'], 'old': c.OLD})
        try:
            self.check(); c.require(self.old() == old, 'old_changed_before_stop')
            self.backend.stop(c.OLD)
            c.stopped(self.backend, c.OLD, c.OLD_IDENTITY)
            self.check(); self.candidate()
            self.backend.start(new['id'])
            state = self.candidate()
            c.require(state.get('running') is True and state.get('pid', 0) > 0, 'candidate_not_running')
            self.check()
            self.postcheck(new['id'])
            self.backend.record_once('activation-result', {'candidate_serving': new['id'],
                                                         'old_retained': c.OLD, 'database_restored': False})
        except Exception:
            self.backend.record_once('activation-failed', {'recovery_required': True})
            self.rollback()
            raise c.Refused('activation_failed_recovered') from None

    def rollback(self):
        self.check()
        self.backend.record_once('rollback-attempt', {'old': c.OLD, 'database_restore': False})
        try:
            self.old()  # Never start a drifted predecessor.
            candidate = self.candidate()
            self.check(); self.candidate()
            # Always intentional, even for Created/crashed candidates; suppress restart policy.
            self.backend.stop(candidate['id'])
            c.stopped(self.backend, candidate['id'], self.manifest['candidate'])
            self.backend.record_once('rollback-fenced', {'candidate': candidate['id'],
                                                       'intentional_stop': True, 'pid': 0})
            self.check()
            old = self.old()
            already_running = old.get('running') is True and old.get('pid', 0) > 0
            if not already_running:
                c.require(old.get('running') is False and old.get('pid') == 0, 'old_state_unknown')
                self.backend.start(c.OLD)
            state = self.old()
            c.require(state.get('running') is True and state.get('pid', 0) > 0, 'old_not_running')
            self.check()
            self.postcheck(c.OLD)
        except Exception:
            self.backend.record_once('rollback-hold', {'termination_or_identity_or_postcheck_unknown': True,
                                                     'automatic_database_restore': False})
            raise c.Refused('rollback_manual_hold_no_unverified_start') from None
        self.backend.record_once('rollback-result', {'old_serving': c.OLD,
                                                    'old_already_running': already_running,
                                                    'candidate_termination_proven': True,
                                                    'database_restored': False})


if __name__ == '__main__':
    raise SystemExit(c.cli('runtime'))
