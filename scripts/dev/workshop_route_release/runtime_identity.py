import pathlib,subprocess,os,json
import identity_helpers as h
R=pathlib.Path(__file__).resolve().parent
def baseline():
 pid=subprocess.check_output(['/usr/bin/systemctl','show','autodata-api.service','-p','MainPID','--value'],text=True,env=h.CHILD_ENV,timeout=5).strip();exe=os.readlink('/proc/'+pid+'/exe')
 names=[h.ENV,h.OVERRIDE,h.DEPENDENCY,pathlib.Path(exe)];files={str(p):h.metadata(p) for p in names};assert pid=='1293423' and exe=='/usr/local/libexec/autodata/workshop-client-preview-a82b31d-a2/autodata-api','api_identity'
 assert files[exe]['sha256']=='bb11d963666e4fc44f6b0879ebb55a14cf7b2ca221bad6ffa8d3282d5360203e','binary_pin'
 assert files[str(h.DEPENDENCY)]['sha256']=='493beef2c5d9fe2190995c1b63ab9c3f094f58f3cda3930048031b6a57c5ecd3','dependency_pin'
 assert files[str(h.ENV)]['sha256']=='74a93e2198fe8b024fadce9a26845990f3c15cbc9681ddd873a704e13a16aa03' and files[str(h.OVERRIDE)]['sha256']=='b9d00378ce917cc53d515e7460774712c5e179ae9bfefed3bee7886b55b74c7c','env_override'
 assert h.running_binary_matches(pid,exe,files[exe]),'loaded_binary'
 cmd=['/usr/bin/docker','--config',str(R/'docker-cli-config'),'--host','unix:///var/run/docker.sock','inspect','17295fae5fe60b5b9c78b81206a3a0c8f3e202b811093f91ebb821babe648f3e']
 x=json.loads(subprocess.check_output(cmd,env=h.CHILD_ENV,timeout=5))[0];identity=h.private_identity(x);assert identity['running'] and identity['pid']==1552737 and identity['restart_count']==0,'private_identity'
 assert identity['id']=='17295fae5fe60b5b9c78b81206a3a0c8f3e202b811093f91ebb821babe648f3e' and identity['image']=='sha256:3132da4cdfa56a36240132e7c83e2bf260f679c0294c7dc06669cb607c6390f7','private_container_image_pin'
 assert identity['started_at']=='2026-11-15T04:15:19.01131429Z' and identity['env_sha256']=='cd689562807dab0e495a88105bbc66b54eaa97194fb1b02e5faa1ea7a119fe06','private_lifecycle_env_pin'
 root=pathlib.Path('/home/corp/autodata-candidate/private-configuration-budget-272aeea-20261115');m=json.loads((root/'manifest.json').read_text());assert h.sha((root/'source.tar').read_bytes())==m['archive_sha256']=='693a088572e589a33f59cf509550e072c81376d35050a63ed6dac5b9b397dabd','private_archive'
 assert m['source_sha']=='272aeeaad8399c305468e5d486cc391d7340f6a4','private_source_pin'
 for name,digest in m['files'].items():assert h.sha((root/'source'/name).read_bytes())==digest,'private_source_file'
 return {'api_pid':int(pid),'api_start_ticks':pathlib.Path('/proc',pid,'stat').read_text().split(') ')[1].split()[19],'api_exe':exe,'files':files,'ingestion':identity,'private_start_ticks':pathlib.Path('/proc',str(identity['pid']),'stat').read_text().split(') ')[1].split()[19],'private_source':{'root':str(root/'source'),'archive_path':str(root/'source.tar'),'archive_sha256':m['archive_sha256'],'source_sha':m['source_sha'],'guard_sha256':h.source_guard(root/'source')},'target_env_sha256':files[str(h.ENV)]['sha256']}
