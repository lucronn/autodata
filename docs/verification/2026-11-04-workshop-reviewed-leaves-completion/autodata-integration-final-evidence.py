import ast,datetime,hashlib,json,pathlib,re,shutil,subprocess
repo=pathlib.Path.cwd();head='e5fed171bb36fdb759c592cbcd0e15aea5490c97';receipt='507e3ddb977ddd45910cba978c7255fac3cb669e';gate='2728ac1acaf173d6f244e200e584dac7922fda1d'
assert subprocess.check_output(['git','rev-parse','HEAD']).decode().strip()==head
out=pathlib.Path('/tmp/autodata-reviewed-leaves-e5fed171-evidence');out.mkdir(exist_ok=True)
checks=[]
for label in ['exact-combined','exact-publisher','exact-staging']:
 for row in json.load(open(f'/tmp/autodata-integration-{label}-results.json')):
  assert row['exit_code']==0 and row['checked_sha']==row['ending_sha']==head,row
  log=pathlib.Path(row['log']);target=out/log.name;shutil.copy2(log,target);row['evidence_log']=str(target);row['log_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
  m=re.search(r'Ran (\d+) tests',target.read_text());row['tests']=int(m[1]) if m else (142 if '# tests 142' in target.read_text() else None)
  checks.append(row)
assert len(checks)==8
static=[]
commands=[['python3','/tmp/autodata-integration-build-check.py','3','check'],['python3','scripts/autonomy/pre_implementation.py','--record','docs/agents/records/2026-11-04-workshop-reviewed-leaves-integration.json','--base-sha',gate,'--repo-root',str(repo)],['git','diff','--check',gate,head],['git','diff','--check',receipt,head],['git','status','--porcelain'],['git','ls-remote','origin','refs/heads/codex/workshop-reviewed-leaves-integration-build']]
for cmd in commands:
 p=subprocess.run(cmd,capture_output=True,text=True);assert p.returncode==0,(cmd,p.stdout,p.stderr)
 static.append({'command':cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
assert static[-2]['stdout']=='';assert static[-1]['stdout'].split()[0]==head
r=json.load(open('docs/agents/records/2026-11-04-workshop-reviewed-leaves-integration.json'))
for sha in [r['root_base_sha'],receipt,*r['source_leaves'].values()]:subprocess.run(['git','merge-base','--is-ancestor',sha,head],check=True)
node=pathlib.Path('/tmp/autodata-reviewed-node-v22.23.4');nodehash=hashlib.sha256(node.read_bytes()).hexdigest();assert nodehash=='94efd062ed066c1a0b332e18249859c905e920eeada5df55d24c99b919629a90'
for p in r['selected_implementation_blobs']:
 if p.endswith('.mjs'):subprocess.run([str(node),'--check',p],check=True)
workflow=json.load(open('.github/workflows/release-workshop.yml'));source=json.loads(subprocess.check_output(['git','show',r['source_leaves']['publisher']+':.github/workflows/release-workshop.yml']))
assert set(workflow['jobs'])==set(source['jobs']) and len(workflow['jobs'])==4
for name in source['jobs']:assert workflow['jobs'][name]==source['jobs'][name]
s=pathlib.Path('docs/agents/specs/2026-11-04-workshop-reviewed-leaves-integration.md').read_text();spec=json.loads(s.split('```json\n')[1].split('\n```')[0]);resolution_pins={}
for p,pin in spec['documentation_resolution_pins'].items():
 root=subprocess.check_output(['git','show',r['root_base_sha']+':'+p]);note=subprocess.check_output(['git','show',receipt+':'+p])[len(root):];b=pathlib.Path(p).read_bytes();assert b.endswith(note)
 h=hashlib.sha256(b[:-len(note)]).hexdigest();assert h==pin['pre_gate_merged_sha256'];resolution_pins[p]=h
for name in ['implementation_dispatch_authorized','tracking_write_authorized','cloud_execution_authorized','staging_activation_authorized','deployment_authorized','production_ready','cutover_verified']:assert r[name] is False
pins=json.loads(static[0]['stdout']);assert pins['implementation']==23 and pins['historical_docs']==59 and pins['selected_queue_ids']==spec['queue_selected_record_ids'] and pins['queue_ids']==28
for path in ['/tmp/autodata-integration-build-check.py','/tmp/autodata-integration-run-checks.py','/tmp/autodata-integration-final-evidence.py']:shutil.copy2(path,out/pathlib.Path(path).name)
data={'checked_sha':head,'checked_tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}']).decode().strip(),'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'worktree':str(repo),'branch':'codex/workshop-reviewed-leaves-integration-build','receipt':receipt,'gate':gate,'source_leaves':r['source_leaves'],'merge_commits':['56839c28e349d20d72495f92443f044a61015df1','1b6639c4718c4d60092866e0601ff301e9f866f1',head],'checks':checks,'static_checks':static,'pins':pins,'pre_note_resolution_pins':resolution_pins,'node_sha256':nodehash,'workflow_jobs':list(workflow['jobs']),'limitations':['Offline checks only; historical fixture/CI acceptance does not transfer to integrated SHA.','Independent exact-SHA review required. No live activation/deployment/readiness authority.','No source corrections, new tests, dependency installation, provider/cloud/Docker operations, GitHub PR creation or merge.'],'unexpected_conflicts':[],'conflicts_by_merge':{'r6':['queue.json','2026-11-03-production-release-orchestration.md'],'publisher':['queue.json','infrastructure-and-dev.md','workshop-gcp.md','2026-11-03-production-release-orchestration.md','2026-11-03-workshop-hosting.md'],'staging':['queue.json','infrastructure-and-dev.md','workshop-gcp.md','2026-11-03-production-release-orchestration.md','2026-11-03-workshop-hosting.md']}}
(out/'summary.json').write_text(json.dumps(data,indent=2)+'\n')
manifest={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(out.iterdir()) if p.name!='manifest.json'};(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'checked_sha':head,'evidence_dir':str(out),'summary_sha256':hashlib.sha256((out/'summary.json').read_bytes()).hexdigest(),'manifest_sha256':hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest(),'checks':len(checks),'counts':[x['tests'] for x in checks],'scope_pins':pins},indent=2))
