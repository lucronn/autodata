"""Bounded immutable-candidate collector for the fourteen real PG commerce cases."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from production_access_smoke import ROOT, ARTIFACTS, check_inputs, digest, now, write_json

GO_ROOT='TestWorkshopCommercePythonIntegration'
CASE_NAMES = (
    'test_orders_create_and_owner_scope','test_same_key_replay_and_conflict',
    'test_concurrent_keys_share_one_checkout','test_scope_races_single_active_grant',
    'test_lost_create_response_and_retention_boundary','test_expiry_requires_remote_nonchargeable_proof',
    'test_completion_races_expiry_without_recharge','test_webhook_before_create_response',
    'test_settlement_binds_financial_owner_scope','test_duplicate_and_distinct_events_grant_once',
    'test_refund_chargeback_ordering_and_monotonic_revocation','test_payment_survives_source_unavailable_and_restart',
    'test_library_is_owner_only_and_paginated','test_grant_check_exact_scope_legacy_and_revoked')
ASSERTION_KEYS = CASE_NAMES + ('fresh_migration_head_040','required_pytest_no_skips','candidate_input_provenance')
RAW_FILES = ('workshop-commerce-tests.xml','workshop-commerce-pytest.stdout.log',
    'workshop-commerce-pytest.stderr.log','workshop-commerce-migration-rows.json',
    'workshop-commerce-go-events.jsonl','workshop-commerce-go-stderr.log',
    'runner-input-before.json','runner-input-after.json','runner-git-before.json','runner-git-after.json')


def junit_results(path):
    try:
        root=ET.parse(path).getroot()
        cases=root.findall('.//testcase')
        clean=bool(cases) and all(not any(c.find(tag) is not None for tag in ('skipped','failure','error')) for c in cases)
        # Reject duplicate and unexpected commerce IDs, including nested/parameter variants.
        commerce=[c for c in cases if c.get('classname')=='tests.test_commerce_postgres']
        names=[c.get('name') for c in commerce]
        exact=len(names)==len(CASE_NAMES) and set(names)==set(CASE_NAMES)
        flags={name: clean and exact and sum(c.get('name')==name for c in commerce)==1 for name in CASE_NAMES}
        return len(cases),clean,flags
    except (OSError,ET.ParseError):
        return 0,False,{name:False for name in CASE_NAMES}


def go_results(events):
    if any(e.get('Action') in {'skip','fail'} or (e.get('Test') is not None and e['Test']!=GO_ROOT) for e in events):
        return False
    actions=[e.get('Action') for e in events if e.get('Test')==GO_ROOT]
    packages=[e.get('Action') for e in events if 'Test' not in e]
    return actions.count('run')==actions.count('pass')==1 and packages.count('pass')==1


def success(code,timed_out,assertions):
    return code==0 and not timed_out and set(assertions)==set(ASSERTION_KEYS) and all(v is True for v in assertions.values())


def collect(candidate,output):
    started=now();assertions={key:False for key in ASSERTION_KEYS};failures=[];provenance={}
    code,timed_out,count=-1,False,0
    go_code,go_timeout=-1,False
    try:
        if os.getenv('AUTODATA_LIFECYCLE_TEST')!='1' or not re.fullmatch('[a-f0-9]{40}',candidate):
            raise RuntimeError('explicit isolated lifecycle fixture and exact candidate required')
        os.environ['AUTODATA_R3_CANDIDATE_SHA']=candidate
        provenance=check_inputs('before')
        # The fixture receives no inherited provider/payment/cloud credentials.
        allowed=('PATH','PYTHONPATH','PYTHONDONTWRITEBYTECODE','AUTODATA_LIFECYCLE_TEST','AUTODATA_R3_CANDIDATE_SHA')
        env={key:os.environ[key] for key in allowed if key in os.environ}
        env.update(AUTODATA_REQUIRE_COMMERCE_INTEGRATION='1',PYTHONDONTWRITEBYTECODE='1')
        command=[sys.executable,'-m','pytest','-q','-p','no:cacheprovider',
            '--junitxml='+str(ARTIFACTS/'workshop-commerce-tests.xml'),'scripts/dev/test_migrations.py',
            'workers/ingestion-python/tests/test_article_lifecycle_migrations.py',
            'workers/ingestion-python/tests/test_commerce_postgres.py']
        with (ARTIFACTS/'workshop-commerce-pytest.stdout.log').open('wb') as stdout, (ARTIFACTS/'workshop-commerce-pytest.stderr.log').open('wb') as stderr:
            try:
                code=subprocess.run(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr,timeout=900,check=False).returncode
            except subprocess.TimeoutExpired:
                timed_out=True;failures.append('required pytest timed out')
        after=check_inputs('after')
        assertions['candidate_input_provenance']=all(provenance[key]==after[key] for key in ('candidate_sha','candidate_origin','host_before_sha256','input_manifest_sha256'))
        count,assertions['required_pytest_no_skips'],case_flags=junit_results(ARTIFACTS/'workshop-commerce-tests.xml')
        rows=json.loads((ARTIFACTS/'workshop-commerce-migration-rows.json').read_text())
        assert rows['schema_version']==1 and rows['candidate_sha']==candidate
        go_code,go_timeout=rows['go_exit_code'],rows['go_timed_out']
        go_events=[json.loads(line) for line in (ARTIFACTS/'workshop-commerce-go-events.jsonl').read_text().splitlines()]
        go_ok=rows['go_root']==GO_ROOT and go_code==0 and go_timeout is False and go_results(go_events)
        case_flags[CASE_NAMES[0]]=case_flags[CASE_NAMES[0]] and go_ok
        expected=[p.stem for p in sorted((ROOT/'db/migrations').glob('*.sql'))]
        complete=set(rows['cases'])==set(CASE_NAMES)
        assertions.update({name:case_flags[name] and name in rows['cases'] for name in CASE_NAMES})
        assertions['fresh_migration_head_040']=(complete and len(expected)==40 and expected[-1]=='040_workshop_commerce'
            and all([r['version'] for r in case['schema_migrations']]==expected for case in rows['cases'].values()))
    except Exception as error:
        failures.append(type(error).__name__+': '+str(error))
    hashes={}
    for name in RAW_FILES:
        path=ARTIFACTS/name
        if path.is_file():
            path.chmod(0o644);hashes[name]=digest(path.read_bytes())
        else:failures.append('missing artifact: '+name)
    failures.extend('failed assertion: '+key for key,value in assertions.items() if not value)
    if code!=0:failures.append('required pytest exit: '+str(code))
    passed=success(code,timed_out,assertions) and not failures
    result=dict(provenance,schema_version=1,candidate_sha=candidate,candidate_origin='coordinator-host-plain-clone',
        started_at=started,finished_at=now(),pytest_exit_code=code,timed_out=timed_out,pytest_test_count=count,
        go_root=GO_ROOT,go_exit_code=go_code,go_timed_out=go_timeout,
        migration_head='040_workshop_commerce',assertion_results=assertions,passed=passed,failures=failures,artifact_sha256=hashes)
    result.pop('runner_git_observation',None)
    write_json(output,result)
    return 0 if passed else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['fixture'],required=True)
    parser.add_argument('--candidate-sha',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output!=ARTIFACTS/'workshop-commerce.json':parser.error('fixture output must be /artifacts/workshop-commerce.json')
    return collect(args.candidate_sha,args.output)


if __name__=='__main__':raise SystemExit(main())
