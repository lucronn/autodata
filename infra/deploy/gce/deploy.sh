#!/bin/sh
# Bounded passive check only. No caller env, config path, command or deployment.
set +x
set -eu
exec /usr/bin/env -i /usr/bin/python3 -I - "$@" <<'PY'
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone


def receipt(operation, source_sha, code):
    now = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    return {'schema_version': 1, 'operation': operation, 'run_id': None, 'source_sha': source_sha,
            'status': 'failed', 'started_at': now, 'finished_at': now,
            'checks': {} if code == 2 else {'runtime_evidence': False},
            'failure_code': 'invalid_input' if code == 2 else 'missing_dependency'}


def load_runtime():
    # This directory and module are installed root-owned by trusted bootstrap.
    # -I plus env -i prevents caller Python path/home/site/environment injection.
    spec = importlib.util.spec_from_file_location('autodata_runtime', '/opt/autodata/bin/runtime-check.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv):
    verbs = ('install', 'check', 'start', 'stop', 'maintenance', 'resume')
    if len(argv) != 2 or argv[0] not in verbs or re.fullmatch('[0-9a-f]{40}', argv[1]) is None:
        return 2, receipt('deploy.sh check', None, 2)
    operation = 'deploy.sh ' + argv[0]
    if argv[0] != 'check':
        return 3, receipt(operation, argv[1], 3)
    try:
        return load_runtime().deploy_cli(argv)
    except Exception:
        # Redact import, filesystem and unexpected implementation details.
        return 3, receipt(operation, argv[1], 3)


if __name__ == '__main__':
    code, output = main(sys.argv[1:])
    sys.stdout.write(json.dumps(output, sort_keys=True, separators=(',', ':')) + '\n')
    raise SystemExit(code)
PY
