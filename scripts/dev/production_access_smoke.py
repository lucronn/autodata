"""Fixture-only bounded collector; the coordinator owns the candidate and services."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = Path('/artifacts')
GO_ROOT = 'TestPostgresAuthSessionsIntegration'
GO_NAMES = ('ConcurrentCustomerProvisionAndRotation', 'SharedSessionRevocation',
            'ExpiryAndPersistedSecrecy', 'FirebaseExchangeAndUserRevocation',
            'FirebaseStartupRequiresMigratedPostgres')
GO_IDS = tuple(GO_ROOT + '/' + name for name in GO_NAMES)
ASSERTION_KEYS = GO_NAMES + ('fresh_migration_head_039', 'unmigrated_fixture_stays_038',
                            'required_pytest_no_skips', 'candidate_input_provenance')
RAW_FILES = ('r5-access-migrations.xml', 'r5-access-go-events.jsonl',
             'r5-access-go-stderr.log', 'r5-access-migration-rows.json',
             'runner-input-before.json', 'runner-input-after.json',
             'runner-git-before.json', 'runner-git-after.json')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, payload):
    path.write_text(json.dumps(payload, default=str, sort_keys=True, indent=2) + '\n')
    path.chmod(0o644)


def now():
    return datetime.now(timezone.utc).isoformat()


def bounded(argv, *, env=None, timeout=30, cwd=ROOT):
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=timeout, check=False)


def check_inputs(phase):
    manifest_bytes = (ARTIFACTS / 'inputs.sha256.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    host = json.loads((ARTIFACTS / 'host-before.json').read_bytes())
    candidate = os.environ['AUTODATA_R3_CANDIDATE_SHA']
    assert re.fullmatch(r'[a-f0-9]{40}', candidate)
    assert manifest['schema_version'] == 1
    assert manifest['candidate_sha'] == host['candidate_sha'] == candidate
    assert manifest['candidate_origin'] == 'coordinator-host-plain-clone'
    assert host['input_manifest_sha256'] == digest(manifest_bytes)
    assert host['git_status_porcelain'] == '' and host['remotes'] == []
    assert host['checkout_kind'] == 'plain-clone'
    paths = []
    for entry in manifest['files']:
        relative = entry['path']
        assert not relative.startswith('/') and '..' not in Path(relative).parts
        assert entry['git_mode'] in ('100644', '100755')
        path = ROOT / relative
        assert path.is_file() and not path.is_symlink()
        assert digest(path.read_bytes()) == entry['sha256'], relative
        assert bool(path.stat().st_mode & 0o111) == (entry['git_mode'] == '100755')
        paths.append(relative)
    assert paths == sorted(set(paths))
    actual = []
    for directory, dirs, names in os.walk(ROOT):
        if Path(directory) == ROOT:
            dirs[:] = [name for name in dirs if name != '.git']
        for name in names:
            path = Path(directory) / name
            assert path.is_file() and not path.is_symlink()
            actual.append(path.relative_to(ROOT).as_posix())
    assert sorted(actual) == paths, 'mounted checkout has missing or additional inputs'
    observation = {'schema_version': 1, 'phase': phase,
                   'origin': 'runner-filesystem-hash-comparison',
                   'input_manifest_sha256': digest(manifest_bytes),
                   'candidate_sha': candidate, 'comparison_ok': True, 'file_count': len(paths)}
    write_json(ARTIFACTS / f'runner-input-{phase}.json', observation)
    prefix = ['git', '--no-optional-locks', '-c', 'safe.directory=/workspace',
              '-c', 'core.hooksPath=/dev/null', '-C', str(ROOT)]
    observed = []
    for args in (['rev-parse', 'HEAD'], ['status', '--porcelain=v1', '--untracked-files=all'], ['remote']):
        process = bounded(prefix + args)
        assert process.returncode == 0, process.stderr.decode()
        observed.append(process.stdout.decode().strip())
    assert observed == [candidate, '', '']
    git_observation = {'schema_version': 1, 'phase': phase, 'candidate_sha': observed[0],
                       'git_status_porcelain': observed[1], 'remotes': [],
                       'origin': 'runner-git-observed'}
    write_json(ARTIFACTS / f'runner-git-{phase}.json', git_observation)
    return {'candidate_sha': candidate, 'candidate_origin': manifest['candidate_origin'],
            'host_before_sha256': digest((ARTIFACTS / 'host-before.json').read_bytes()),
            'input_manifest_sha256': digest(manifest_bytes),
            'runner_git_observation': git_observation}


def go_results(events):
    # A pass alone is insufficient: actual execution, no skips/failures, root pass.
    def passed(name):
        actions = [e.get('Action') for e in events if e.get('Test') == name]
        return 'run' in actions and actions.count('pass') == 1 and not {'skip', 'fail'} & set(actions)
    root_ok = passed(GO_ROOT)
    return {name: root_ok and passed(GO_ROOT + '/' + name) for name in GO_NAMES}


def junit_results(path):
    try:
        cases = ET.parse(path).getroot().findall('.//testcase')
        return len(cases), bool(cases) and all(not any(c.find(tag) is not None for tag in ('skipped', 'failure', 'error')) for c in cases)
    except (OSError, ET.ParseError):
        return 0, False


def success(code, timed_out, assertions):
    return code == 0 and not timed_out and set(assertions) == set(ASSERTION_KEYS) and all(value is True for value in assertions.values())


def collect(candidate, output):
    started = now()
    assertions = {key: False for key in ASSERTION_KEYS}
    failures = []
    provenance = {}
    code, timed_out, count, go_code = -1, False, 0, -1
    try:
        if os.getenv('AUTODATA_LIFECYCLE_TEST') != '1' or not re.fullmatch('[a-f0-9]{40}', candidate):
            raise RuntimeError('explicit private lifecycle fixture and exact candidate required')
        os.environ['AUTODATA_R3_CANDIDATE_SHA'] = candidate
        provenance = check_inputs('before')
        env = dict(os.environ, AUTODATA_REQUIRE_AUTH_INTEGRATION='1', PYTHONDONTWRITEBYTECODE='1')
        command = [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                   '--junitxml=' + str(ARTIFACTS / 'r5-access-migrations.xml'),
                   'scripts/dev/test_migrations.py',
                   'workers/ingestion-python/tests/test_article_lifecycle_migrations.py',
                   'scripts/dev/test_production_access_smoke.py']
        try:
            code = subprocess.run(command, cwd=ROOT, env=env, timeout=900, check=False).returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            failures.append('required pytest timed out')
        after = check_inputs('after')
        assertions['candidate_input_provenance'] = all(provenance[key] == after[key] for key in ('candidate_sha', 'candidate_origin', 'host_before_sha256', 'input_manifest_sha256'))
        count, assertions['required_pytest_no_skips'] = junit_results(ARTIFACTS / 'r5-access-migrations.xml')
        events = [json.loads(line) for line in (ARTIFACTS / 'r5-access-go-events.jsonl').read_text().splitlines()]
        assertions.update(go_results(events))
        rows = json.loads((ARTIFACTS / 'r5-access-migration-rows.json').read_text())
        go_code = rows['go_exit_code']
        if go_code != 0 or rows['go_timed_out']:
            failures.append('required Go suite failed or timed out')
        expected = [p.stem for p in sorted((ROOT / 'db/migrations').glob('*.sql'))]
        assertions['fresh_migration_head_039'] = (len(expected) == 39 and expected[-1] == '039_production_identity_sessions'
            and [r['version'] for r in rows['schema_migrations']] == expected
            and bool(rows['customer_accounts']) and bool(rows['auth_sessions']))
        assertions['unmigrated_fixture_stays_038'] = [r['version'] for r in rows['unmigrated_schema_migrations']] == expected[:38]
    except Exception as error:
        failures.append(type(error).__name__ + ': ' + str(error))
    hashes = {}
    for name in RAW_FILES:
        path = ARTIFACTS / name
        if path.is_file():
            path.chmod(0o644)
            hashes[name] = digest(path.read_bytes())
        else:
            failures.append('missing artifact: ' + name)
    failures.extend('failed assertion: ' + key for key, value in assertions.items() if not value)
    if code != 0:
        failures.append('required pytest exit: ' + str(code))
    passed = success(code, timed_out, assertions) and go_code == 0 and not failures
    result = dict(provenance, schema_version=1, candidate_sha=candidate,
                  candidate_origin='coordinator-host-plain-clone', started_at=started, finished_at=now(),
                  pytest_exit_code=code, timed_out=timed_out, pytest_test_count=count,
                  go_root=GO_ROOT, go_subtests=list(GO_IDS), go_exit_code=go_code,
                  migration_head='039_production_identity_sessions', assertion_results=assertions,
                  passed=passed, failures=failures, artifact_sha256=hashes)
    result.pop('runner_git_observation', None)
    write_json(output, result)
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['fixture'], required=True)
    parser.add_argument('--candidate-sha', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output != ARTIFACTS / 'r5-access.json':
        parser.error('fixture output must be /artifacts/r5-access.json')
    return collect(args.candidate_sha, args.output)


if __name__ == '__main__':
    raise SystemExit(main())
