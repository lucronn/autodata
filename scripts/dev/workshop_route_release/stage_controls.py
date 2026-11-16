"""Copy reviewed controls only; no SQL, restart, install or public request."""
import argparse,hashlib,importlib.util,json,os,pathlib,stat
R=pathlib.Path(__file__).resolve().parent
EXPECTED=pathlib.Path('/home/corp/autodata-evidence/workshop-route-preview-09524db-release-20261116')
PHYSICAL=pathlib.Path('/home/corp/.local/state/autodata-workshop-route-preview-09524db-release-20261116')
FILES={'release-manifest.json','workshop_public_release.py','workshop_public_probe.py','LOCAL-FIXTURE-PASS.json','LOCAL-BROWSER-PASS.json','LOCAL-ASSET-PASS.json','LOCAL-FIXTURE-OUTCOME.json','ROOT-APPROVAL.json','docker-cli-config/config.json'}
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def sync(p):
 fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:os.fsync(fd)
 finally:os.close(fd)
def inventory(seal,device=1792,uid=1000):
 for name,row in seal['files'].items():
  p=R/name;st=p.lstat()
  assert p.resolve()==p and stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_uid==uid and st.st_dev==device,'packet_metadata'
  assert st.st_size==row['bytes'] and digest(p)==row['sha256'],'packet_bytes'
def main():
 p=argparse.ArgumentParser();p.add_argument('--reviewed-packet-sha256',required=True);p.add_argument('--copy-reviewed-controls',action='store_true');a=p.parse_args()
 assert R==EXPECTED and R.resolve()==R and R.stat().st_dev==1792,'offloaded_packet_path'
 assert digest(R/'PACKET-SEAL.json')==a.reviewed_packet_sha256,'reviewed_seal'
 seal=json.loads((R/'PACKET-SEAL.json').read_text());inventory(seal)
 assert FILES<=set(seal['files']) and 'stage_controls.py' in seal['files'],'copy_inventory'
 assert PHYSICAL.parent.resolve()==PHYSICAL.parent and PHYSICAL.parent.stat().st_dev==pathlib.Path('/home').stat().st_dev,'physical_parent'
 assert not PHYSICAL.exists() and not PHYSICAL.is_symlink(),'fresh_physical_control_path'
 spec=importlib.util.spec_from_file_location('release',R/'workshop_public_release.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
 m=json.loads((R/'release-manifest.json').read_text());assert m['physical_control']==str(PHYSICAL),'physical_manifest'
 c.payload_check(m);c.dry_baseline(m);c.private_check(m,True);before=c.capacity(m)
 assert sum((R/name).stat().st_size+4096 for name in FILES)<4194304,'physical_control_cap'
 if not a.copy_reviewed_controls:
  print(json.dumps({'status':'NO_COPY_DRY_PASS','source_verified':True,'physical_path_absent':True,'capacity':before}));return
 assert os.geteuid()==0,'root_required'
 PHYSICAL.mkdir(mode=0o700);sync(PHYSICAL.parent)
 (PHYSICAL/'docker-cli-config').mkdir(mode=0o700)
 for name in sorted(FILES):
  c.capacity(m);src=R/name;dest=PHYSICAL/name
  fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'wb') as out:
   data=src.read_bytes();assert len(data)<=1048576,'control_file_bound';out.write(data);out.flush();os.fchmod(out.fileno(),0o500 if name.endswith('.py') else 0o600);os.fsync(out.fileno())
  assert digest(dest)==seal['files'][name]['sha256'],'copy_hash'
 sync(PHYSICAL/'docker-cli-config');sync(PHYSICAL);sync(PHYSICAL.parent)
 c.dry_baseline(m);c.private_check(m,True);after=c.capacity(m)
 print(json.dumps({'status':'CONTROLS_COPIED_ONLY_NO_SERVICE_OR_SQL','physical_control':str(PHYSICAL),'files':sorted(FILES),'capacity':after}))
if __name__=='__main__':main()
