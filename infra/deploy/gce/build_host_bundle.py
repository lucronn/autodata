#!/usr/bin/python3 -I
"""Build a deterministic, credential-free directory from an exact clean commit."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

STATIC = ('release.schema.json', 'runtime-entrypoint.sh', 'deploy.sh', 'metadata-guard.nft',
          'autodata-metadata-guard.service', 'docker-autodata.conf', 'Caddyfile',
          'nats.conf.template', 'seaweedfs-s3.json.template', 'runtime-grants.sql', 'host-bootstrap-roles.sql')

def source_inventory(root):
    root = Path(root)
    names = ['infra/deploy/gce/' + name for name in STATIC]
    names += [str(path.relative_to(root)) for path in (root/'infra/deploy/gce').glob('*.py')
              if not path.name.startswith('test_') and path.name != 'build_host_bundle.py']
    names += [str(path.relative_to(root)) for path in (root/'db/migrations').glob('*.sql')]
    names += ['infra/compose/compose.production.yaml', 'scripts/dev/migrate_sql.sh']
    return sorted(names)

def destination(name):
    if name.startswith('infra/deploy/gce/'): return 'opt/autodata/bin/' + name.rsplit('/',1)[1]
    if name == 'infra/compose/compose.production.yaml': return 'opt/compose/compose.production.yaml'
    return 'opt/autodata/source/' + name

def build(root, sha, output):
    root, output = Path(root), Path(output)
    if type(sha) is not str or re.fullmatch('[0-9a-f]{40}',sha) is None: raise ValueError('invalid source')
    def git(*args): return subprocess.check_output(['/usr/bin/git','-C',str(root),*args],env={'PATH':'/usr/bin:/bin','LC_ALL':'C'}).strip()
    if git('rev-parse','HEAD').decode() != sha or git('status','--porcelain','--untracked-files=no'):
        raise ValueError('source must be the exact clean commit')
    entries, material = [], []
    for name in source_inventory(root):
        path = root/name
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1: raise ValueError('invalid source file')
        data = path.read_bytes()
        # Read the committed blob too, so ignored/untracked helpers cannot enter.
        if data != git_blob(root, sha, name): raise ValueError('source blob differs')
        if not 0 < len(data) <= 1048576: raise ValueError('invalid source size')
        target = destination(name); mode = 0o555 if name.endswith('.sh') else 0o444
        entries.append({'path':target,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'mode':mode})
        material.append((target,data,mode))
    entries.sort(key=lambda value:value['path'])
    output.mkdir(mode=0o755)  # O_EXCL semantics for directories, never merge output.
    for target,data,mode in material:
        path = output/target; path.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
        with path.open('xb') as handle: handle.write(data)
        path.chmod(mode)
    inventory = {'schema_version':1,'source_sha':sha,'files':entries}
    (output/'inventory.json').write_bytes(json.dumps(inventory,sort_keys=True,separators=(',',':')).encode()+b'\n')
    (output/'inventory.json').chmod(0o444)
    return inventory

def git_blob(root,sha,name):
    return subprocess.check_output(['/usr/bin/git','-C',str(root),'show',sha+':'+name],env={'PATH':'/usr/bin:/bin','LC_ALL':'C'})

if __name__ == '__main__':
    try:
        if len(sys.argv) != 3: raise ValueError()
        build(Path(__file__).resolve().parents[3],sys.argv[1],sys.argv[2])
    except Exception:
        print('host bundle rejected',file=sys.stderr); raise SystemExit(2)
