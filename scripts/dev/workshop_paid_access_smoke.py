"""Immutable-candidate collector for twelve real paid catalog fixture cases."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import xml.etree.ElementTree as ET
from production_access_smoke import ROOT, ARTIFACTS, check_inputs, digest, now, write_json

GO_NAMES=(
 'TestPostgresPaidCatalogGrantBeforeWork',
 'TestPostgresPaidCatalogExactScopeAndOwnerIsolation',
 'TestPostgresPaidCatalogPrepareSourceThenCanonicalReuse',
 'TestPostgresPaidCatalogContextualMediaAndRevocation',
 'TestPostgresPaidCatalogHistoricalSourceAndRights',
 'TestPostgresPaidCatalogCustomerLegacyRoutesDenied')
CASE_IDS=tuple(name+'-'+provider for name in GO_NAMES for provider in ('bankone','banktwo'))
CASE_ASSERTIONS=dict(zip(GO_NAMES,(
 ('public_selectors_metadata_only','unpaid_denied_before_work','expired_session_denied_before_work','paid_gets_observational','unavailable_grant_denied_before_work'),
 ('exact_scope_grants','owner_region_configuration_isolation','canonical_only','revoked_and_legacy_denied'),
 ('explicit_prepare_only','shared_article_job','actual_model_response_held','source_readable_during_hold','source_content_search_current_projection','canonical_content_search_current_projection','canonical_reused_two_owners','canonical_steps_preserved','payment_grants_persist'),
 ('actual_s3_reader','invalid_media_zero_reader','current_grant_identity_rechecked','stale_context_zero_reader','media_security_headers'),
 ('source_html_json_media','content_search_before_rights_change','historical_source_selected','rights_denied_before_reader','source_sanitizer_no_private_leak'),
 ('thirteen_routes_denied_before_work','unauthenticated_401','explicit_local_compatibility'))))
MIGRATION_ASSERTIONS=('fresh_manifest_applied_001_040','empty_replay_noop_001_040','populated_replay_noop_001_040')
RAW_FILES=('workshop-paid-access-tests.xml','workshop-paid-access-pytest.stdout.log','workshop-paid-access-pytest.stderr.log','runner-input-before.json','runner-input-after.json','runner-git-before.json','runner-git-after.json')

def go_valid(events,name):
    if not events or any(e.get('Action') in {'skip','fail'} or (e.get('Test') is not None and e['Test']!=name) for e in events):return False
    actions=[e.get('Action') for e in events if e.get('Test')==name]
    packages=[e.get('Action') for e in events if 'Test' not in e]
    return actions.count('run')==actions.count('pass')==1 and packages.count('pass')==1 and events[-1].get('Action')=='pass' and 'Test' not in events[-1]

def junit_valid(path):
    try:
        cases=ET.parse(path).getroot().findall('.//testcase')
        names=[c.get('name') for c in cases]
        expected=['test_required_paid_catalog_access['+case+']' for case in CASE_IDS]
        return (len(cases)==12 and sorted(names)==sorted(expected)
            and all(c.get('classname')=='tests.test_paid_catalog_api_integration' and not any(c.find(tag) is not None for tag in ('skipped','failure','error')) for c in cases))
    except (OSError,ET.ParseError):return False

def success(code,timed_out,flags):
    return code==0 and not timed_out and set(flags)==set(CASE_IDS) and all(v is True for v in flags.values())

def collect(candidate,output):
    started=now();flags={case:False for case in CASE_IDS};failures=[];provenance={};code=-1;timed_out=False;case_results={}
    try:
        if os.getenv('AUTODATA_LIFECYCLE_TEST')!='1' or not re.fullmatch('[a-f0-9]{40}',candidate):raise RuntimeError('explicit lifecycle fixture and exact candidate required')
        os.environ['AUTODATA_R3_CANDIDATE_SHA']=candidate
        provenance=check_inputs('before')
        allowed=('PATH','PYTHONPATH','PYTHONDONTWRITEBYTECODE','AUTODATA_LIFECYCLE_TEST','AUTODATA_R3_CANDIDATE_SHA','GOTOOLCHAIN','GOPROXY','GOFLAGS','CGO_ENABLED','GOMODCACHE','GOCACHE','GOTMPDIR')
        env={key:os.environ[key] for key in allowed if key in os.environ}
        env.update(AUTODATA_CATALOG_INTEGRATION_REQUIRED='1',AUTODATA_REQUIRE_PAID_CATALOG_INTEGRATION='1',PYTHONDONTWRITEBYTECODE='1')
        command=[sys.executable,'-m','pytest','-q','-p','no:cacheprovider','--junitxml='+str(ARTIFACTS/'workshop-paid-access-tests.xml'),'workers/ingestion-python/tests/test_paid_catalog_api_integration.py']
        with (ARTIFACTS/'workshop-paid-access-pytest.stdout.log').open('wb') as stdout,(ARTIFACTS/'workshop-paid-access-pytest.stderr.log').open('wb') as stderr:
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
            try:code=process.wait(timeout=1800)
            except subprocess.TimeoutExpired:
                timed_out=True;os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=3)
                code=process.returncode
        after=check_inputs('after')
        if any(provenance[k]!=after[k] for k in ('candidate_sha','candidate_origin','host_before_sha256','input_manifest_sha256')):raise RuntimeError('candidate provenance changed')
        if not junit_valid(ARTIFACTS/'workshop-paid-access-tests.xml'):failures.append('required exact twelve-case JUnit inventory failed')
        for name in GO_NAMES:
            for provider in ('bankone','banktwo'):
                case=name+'-'+provider;directory=ARTIFACTS/'paid-access'/provider/name
                result=json.loads((directory/'result.json').read_text());case_results[case]=result
                keys=set(CASE_ASSERTIONS[name]+MIGRATION_ASSERTIONS)
                events=[json.loads(line) for line in (directory/'go-events.jsonl').read_text().splitlines()]
                valid=(result['candidate_sha']==candidate and all(result.get(key)==provenance[key] for key in ('candidate_origin','host_before_sha256','input_manifest_sha256')) and result['provider']==provider and result['go_test_name']==name
                    and result['go_exit_code']==0 and result['timed_out'] is False and result['passed'] is True and result['failures']==[]
                    and set(result['assertion_results'])==keys and all(v is True for v in result['assertion_results'].values()) and go_valid(events,name))
                inventory={p.name:digest(p.read_bytes()) for p in directory.iterdir() if p.is_file() and p.name!='result.json'}
                flags[case]=valid and inventory==result['artifact_sha256']
    except Exception as error:failures.append(type(error).__name__+': '+str(error))
    hashes={}
    for name in RAW_FILES:
        path=ARTIFACTS/name
        if path.is_file():path.chmod(0o644);hashes[name]=digest(path.read_bytes())
        else:failures.append('missing artifact: '+name)
    failures.extend('failed case: '+case for case,value in flags.items() if not value)
    if code!=0:failures.append('required pytest exit: '+str(code))
    passed=success(code,timed_out,flags) and not failures
    result=dict(provenance,schema_version=1,candidate_sha=candidate,candidate_origin='coordinator-host-plain-clone',started_at=started,finished_at=now(),pytest_exit_code=code,timed_out=timed_out,pytest_test_count=12 if junit_valid(ARTIFACTS/'workshop-paid-access-tests.xml') else 0,case_results=case_results,assertion_results=flags,passed=passed,failures=failures,artifact_sha256=hashes)
    write_json(output,result);return 0 if passed else 1

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['fixture'],required=True);parser.add_argument('--candidate-sha',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();return collect(args.candidate_sha,args.output)
if __name__=='__main__':raise SystemExit(main())
