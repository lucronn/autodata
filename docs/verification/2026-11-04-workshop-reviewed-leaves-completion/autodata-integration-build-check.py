import ast,hashlib,json,pathlib,subprocess,sys
ROOT='eddcf724028683dbb083191e4f8c42064b866bf0'
RECEIPT='507e3ddb977ddd45910cba978c7255fac3cb669e'
GATE='2728ac1acaf173d6f244e200e584dac7922fda1d'
record='docs/agents/records/2026-11-04-workshop-reviewed-leaves-integration.json'
def git(*a):return subprocess.check_output(['git',*a])
def blob(sha,path):return git('show',sha+':'+path)
r=json.loads(blob(RECEIPT,record)); sources=list(r['source_leaves'].values()); n=int(sys.argv[1]); action=sys.argv[2]
queue='docs/agents/tasks/2026-11-03-production-release/queue.json'
docs=['docs/architecture/infrastructure-and-dev.md','docs/superpowers/plans/2026-11-03-production-release-orchestration.md','docs/superpowers/plans/2026-11-03-workshop-hosting.md','docs/operations/workshop-gcp.md']
expected={}
for p in docs:
 base=blob(ROOT,p); checkpoint=blob(RECEIPT,p); assert checkpoint.startswith(base),p
 note=checkpoint[len(base):]; result=base
 for i,sha in enumerate(sources[:n]):
  leaf=blob(sha,p)
  if p=='docs/operations/workshop-gcp.md' and i==1:
   result=leaf
  else:
   assert leaf.startswith(base),(sha,p)
   result+=leaf[len(base):]
 expected[p]=result+note
base=json.loads(blob(ROOT,queue)); check=json.loads(blob(RECEIPT,queue)); outside=lambda d:{k:v for k,v in d.items() if k!='tasks'}
assert outside(base)==outside(check)
def index(d):
 ids=[x['id'] for x in d['tasks']]; assert len(ids)==len(set(ids));return {x['id']:x for x in d['tasks']}
bi=index(base); selected=dict(bi); modified={}
for sha in sources[:n]:
 leaf=json.loads(blob(sha,queue));assert outside(base)==outside(leaf);li=index(leaf);assert set(bi)<=set(li)
 for k,v in li.items():
  if k not in bi or v!=bi[k]:
   assert k not in modified or modified[k]==v,k
   modified[k]=v;selected[k]=v
ci=index(check);assert set(ci)-set(bi)=={'workshop-reviewed-leaves-integration'}
for k in bi:assert ci[k]==bi[k]
selected['workshop-reviewed-leaves-integration']=ci['workshop-reviewed-leaves-integration']
base['tasks']=list(selected.values());expected[queue]=(json.dumps(base,indent=2)+'\n').encode()
if action=='resolve':
 conflicts=set(git('diff','--name-only','--diff-filter=U').decode().splitlines());assert conflicts<=set(expected),conflicts
 for p,b in expected.items():pathlib.Path(p).write_bytes(b)
 subprocess.run(['git','add',*expected],check=True)
for p,b in expected.items():assert pathlib.Path(p).read_bytes()==b,p
pins={**r['selected_implementation_blobs'],**r['historical_document_pins']}
active={p:v for p,v in pins.items() if v['source_sha'] in sources[:n]}
for p,v in active.items():
 b=pathlib.Path(p).read_bytes();entry=git('ls-files','-s','--',p).decode().split()
 assert len(b)==v['bytes'] and hashlib.sha256(b).hexdigest()==v['sha256'],p
 assert entry[:2]==[v['git_mode'],v['git_blob_oid']],(p,entry)
 assert b==blob(v['source_sha'],p),p
 if p.endswith('.py'):ast.parse(b,filename=p)
changed=set(git('diff','--name-only',RECEIPT).decode().splitlines());assert changed<=set(active)|set(expected),(changed-set(active)-set(expected))
assert not git('ls-files','-u')
for p in changed:
 if p.endswith('.json'):
  def pairs(ps):
   d={}
   for k,v in ps:assert k not in d,(p,k);d[k]=v
   return d
  json.loads(pathlib.Path(p).read_bytes(),object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
subprocess.run(['git','diff','--check',GATE],check=True)
print(json.dumps({'milestone':n,'pins':len(active),'implementation':sum(p in r['selected_implementation_blobs'] for p in active),'historical_docs':sum(p in r['historical_document_pins'] for p in active),'changed_paths':len(changed),'queue_ids':len(selected),'selected_queue_ids':list(modified),'conflict_resolution_sha256':{p:hashlib.sha256(b).hexdigest() for p,b in expected.items()}},indent=2))
