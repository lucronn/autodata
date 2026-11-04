import datetime,json,os,pathlib,subprocess,sys,time
repo=pathlib.Path.cwd(); phase=sys.argv[1]; label=os.environ.get('AUTODATA_INTEGRATION_CHECK_LABEL',phase); checked_sha=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(); node='/tmp/autodata-reviewed-node-v22.23.4'; env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
commands={
'publisher':[(repo/'infra/deploy/gce',['python3','-m','unittest','test_publisher_adapters','test_cloud_ops','test_host_runtime','test_release_workshop_contract','-q']),(repo,[node,'--test','infra/deploy/gce/test_publisher_artifact.mjs','infra/deploy/gce/test_publisher_policy.mjs','infra/deploy/gce/test_publisher_identity.mjs'])],
'staging':[(repo,['python3','-m','unittest','discover','-s','infra/deploy/gce','-p','test_host_install.py','-v']),(repo,['python3','-m','unittest','discover','-s','infra/deploy/gce','-p','test_staging_bootstrap.py','-v']),(repo,['bash','-n','infra/deploy/gce/deploy.sh','infra/deploy/gce/cloud-bootstrap.sh'])],
'combined':[(repo,['python3','-m','unittest','scripts/dev/test_release_acceptance.py','-v']),(repo,['python3','-m','unittest','discover','-s','scripts/dev','-p','test_*.py']),(repo,['python3','-m','unittest','discover','-s','scripts/autonomy','-p','test_*.py'])]}
results=[]
for i,(cwd,cmd) in enumerate(commands[phase]):
 log=pathlib.Path(f'/tmp/autodata-integration-{label}-{i}.log');start=time.monotonic();print('RUN',cmd,flush=True)
 with log.open('w') as f:p=subprocess.run(cmd,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT)
 result={'checked_sha':checked_sha,'ending_sha':subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),'command':cmd,'cwd':str(cwd),'exit_code':p.returncode,'duration_seconds':round(time.monotonic()-start,2),'log':str(log),'tail':'\n'.join(log.read_text().splitlines()[-8:])};results.append(result)
 print(json.dumps(result),flush=True)
 pathlib.Path(f'/tmp/autodata-integration-{label}-results.json').write_text(json.dumps(results,indent=2)+'\n')
 if p.returncode:sys.exit(p.returncode)
