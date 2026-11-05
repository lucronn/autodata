#!/usr/bin/env python3
"""Fixed authenticated staging publication entry point; imports perform no I/O."""
import importlib.util
import os
from pathlib import Path
import re
import signal
import sys


def _forward_interrupt(signum, frame):
    # bounded_process owns SIGTERM, including the Popen return/assignment
    # boundary and deferred cleanup. SIGINT must enter that same protocol.
    os.kill(os.getpid(),signal.SIGTERM)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if (len(argv) != 2 or argv[0] not in ('staging-build-candidate','staging-finalize','verify-publication')
            or re.fullmatch(r'[0-9a-f]{40}', argv[1]) is None):
        sys.stderr.write('usage: publisher_cli.py staging-build-candidate|staging-finalize|verify-publication SOURCE_SHA\n')
        return 2
    spec = importlib.util.spec_from_file_location('publisher_cli_live', Path(__file__).resolve().with_name('publisher_live.py'))
    live = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(live)
    def cancelled(signum, frame): raise live.a.AdapterError('operation_cancelled')
    old_handlers = {signal.SIGTERM:signal.signal(signal.SIGTERM,cancelled),
                    signal.SIGINT:signal.signal(signal.SIGINT,_forward_interrupt)}
    try:
        result = live.execute(*argv)
        sys.stdout.buffer.write(live.a.canonical(result)+b'\n')
        return 0
    except Exception as error:
        codes = {'invalid_input','missing_dependency','operation_failed','operation_timed_out','operation_cancelled',
                 'cleanup_failed','output_overflow','output_collision','tool_mismatch','identity_mismatch',
                 'registry_mismatch','credential_scope','approval_signature_invalid'}
        code = str(error) if isinstance(error, live.a.AdapterError) and str(error) in codes else 'operation_failed'
        sys.stderr.buffer.write(live.a.canonical({'protocol_version':3,'status':'failed','failure_code':code,
                                                'deployment_authorized':False})+b'\n')
        return 5 if code in ('operation_timed_out','operation_cancelled') else 3
    finally:
        for number, handler in old_handlers.items(): signal.signal(number, handler)


if __name__ == '__main__': raise SystemExit(main())
