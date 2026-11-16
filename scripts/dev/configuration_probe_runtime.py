#!/usr/bin/env python3
"""Sealed one-attempt probe adapter. Direct CLI validates only; launcher supplies authority.

Fixture mode uses an owned network-none container/socket trigger, never an HTTP
provider request. The supervisor lifecycle never runs SQL; final acceptance does.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('watchdog_core', HERE/'configuration_probe_watchdog.py')
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)
ENV = dict(core.CHILD_ENV)
PAYLOAD_PREFIX = 'catalog configuration budget '
LOG_PREFIXES = ('', 'WARNING:autodata_ingestion.catalog_service:')
HTTP=urllib.request.build_opener(urllib.request.ProxyHandler({}))


def bounded(argv, *, timeout=3, limit=524288):
    """No shell, inherited context, unbounded pipe buffer or raw failure output."""
    if not argv or not str(argv[0]).startswith('/'):
        raise core.Refused('absolute_child_required')
    process = subprocess.Popen(argv, env=ENV, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = bytearray()
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    deadline = time.monotonic()+timeout
    try:
        while selector.get_map():
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise core.Refused('child_deadline')
            for key, _ in selector.select(min(remaining,.1)):
                chunk = os.read(key.fileobj.fileno(),65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                output.extend(chunk)
                if len(output)>limit:
                    raise core.Refused('child_output_limit')
        if process.wait(timeout=max(.01,deadline-time.monotonic())) != 0:
            raise core.Refused('child_failed')
        return bytes(output)
    except (OSError, subprocess.SubprocessError):
        raise core.Refused('child_unknown') from None
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=1)
        process.stdout.close()


def digest(value):
    return hashlib.sha256(core.canonical(value)).hexdigest()


BASELINE_MAX_BYTES=128*1024*1024
BASELINE_NAMES=frozenset(('baseline-before','baseline-after'))


def put_baseline(store,name,value):
    """Exclusive bounded baseline and durable size/hash seal; markers stay64KiB."""
    if name not in BASELINE_NAMES or not isinstance(value,dict) or not isinstance(value.get('tables'),dict):
        raise core.Refused('baseline_name_or_shape_refused')
    data=core.canonical(value)+b'\n'
    if len(data)>BASELINE_MAX_BYTES:raise core.Refused('baseline_size_refused')
    try:
        fd=os.open(store.path(name),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as handle:
            handle.write(data);handle.flush();os.fsync(handle.fileno())
        directory=os.open(store.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(directory)
        finally:os.close(directory)
        store.put(name+'-seal',{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    except (OSError,ValueError,TypeError):
        raise core.Refused('baseline_write_refused') from None


def get_baseline(store,name):
    """Read only fixed baseline names with exact bounded sealed bytes, then decode."""
    import stat
    if name not in BASELINE_NAMES:raise core.Refused('baseline_name_refused')
    seal=store.get(name+'-seal')
    if (set(seal)!={'bytes','sha256'} or type(seal['bytes']) is not int
            or not 0<seal['bytes']<=BASELINE_MAX_BYTES or not isinstance(seal['sha256'],str)
            or re.fullmatch('[0-9a-f]{64}',seal['sha256']) is None):
        raise core.Refused('baseline_seal_refused')
    try:
        fd=os.open(store.path(name),os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,'rb') as handle:
            before=os.fstat(handle.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_mode&0o077 or before.st_uid!=os.geteuid()
                    or before.st_dev!=store.root.stat().st_dev or before.st_nlink!=1 or before.st_size!=seal['bytes']):
                raise core.Refused('baseline_file_refused')
            data=handle.read(seal['bytes']+1)
            after=os.fstat(handle.fileno())
            if (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns):
                raise core.Refused('baseline_changed_during_read')
        if len(data)!=seal['bytes'] or hashlib.sha256(data).hexdigest()!=seal['sha256']:
            raise core.Refused('baseline_hash_or_size_refused')
        value=json.loads(data)
        if not isinstance(value,dict) or not isinstance(value.get('tables'),dict):
            raise core.Refused('baseline_shape_refused')
        return value
    except (OSError,ValueError,TypeError):
        raise core.Refused('baseline_read_refused') from None


def parse_logs(raw, scope):
    """Docker timestamps plus exact logger formats; raw input never persisted."""
    lines=[];invalid=False
    try:
        text=raw.decode('utf-8',errors='strict')
    except UnicodeError:
        raise core.Refused('log_encoding_unknown') from None
    for row in text.splitlines():
        # Docker --timestamps is mandatory, including for the fixture container.
        match=re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{1,9}Z (.*)',row)
        if not match:
            if PAYLOAD_PREFIX in row: invalid=True
            continue
        message=match[1]
        for prefix in LOG_PREFIXES:
            if message.startswith(prefix+PAYLOAD_PREFIX):
                payload=message[len(prefix):]
                try:
                    events=core.safe_events([payload])
                except core.Refused:
                    invalid=True
                    break
                if events and events[0]['scope_hash']==scope:lines.append(payload)
                break
    return lines,invalid


def supervisor_matches(proof, properties, process):
    expected={'Id':proof['unit'],'LoadState':'loaded','ActiveState':'active','SubState':'running',
              'MainPID':str(proof['pid']),'User':'corp','KillMode':'control-group','Restart':'no',
              'RuntimeMaxUSec':'25s','TimeoutStopUSec':'15s','PrivateNetwork':'yes','ControlGroup':'/system.slice/'+proof['unit']}
    if any(properties.get(k)!=v for k,v in expected.items()):return False
    finalizer=' '.join(proof['argv'][:-1]+['finalize'])
    stop=properties.get('ExecStopPost','')
    if not stop.startswith('{ path=/usr/bin/python3 ; argv[]='+finalizer+' ; ignore_errors=no ;') or stop.count('{ path=')!=1:return False
    return (process.get('boot_id')==proof['boot_id'] and process.get('start_ticks')==proof['start_ticks']
            and process.get('executable_sha256')==proof['python_sha256']
            and process.get('argv')==proof['argv']
            and process.get('cgroup')=='0::'+properties.get('ControlGroup','')
            and properties.get('FragmentPath')=='/run/systemd/transient/'+proof['unit']
            and process.get('unit_file_sha256')==proof['unit_file_sha256'])


def baseline_delta(before,after):
    if set(before)!=set(after):raise core.Refused('baseline_inventory_drift')
    result={}
    for table,rows in before.items():
        new=after[table]
        changes={key:sorted(name for name in set(value['column_hashes'])|set(new[key]['column_hashes']) if value['column_hashes'].get(name)!=new[key]['column_hashes'].get(name))
                 for key,value in rows.items() if key in new and value['row_hash']!=new[key]['row_hash']}
        result[table]={'before_rows':len(rows),'after_rows':len(new),'additions':sorted(set(new)-set(rows)),
                       'deletions':sorted(set(rows)-set(new)),'changes':changes}
    return result


class Adapter:
    def __init__(self, config, authorize, runner=bounded):
        self.cfg=config
        self.authorize=authorize
        self.runner=runner
        self.launcher_hash=None
        self.root=Path(config['run_root'])
        self.store=core.Store(self.root)
        self.D=['/usr/bin/docker','--config',config['docker_config'],'--host','unix:///var/run/docker.sock']
        self.probe=core.Probe(config['core'],self.store,self,supervisor_verifier=self.supervisor_alive)

    def admit(self):
        self.package_seal=self.authorize()
        assert re.fullmatch('[0-9a-f]{64}',self.package_seal)
        core.validate_manifest(self.cfg['core'])
        assert self.cfg['kind'] in ('production','fixture')
        assert self.root.resolve()==self.root and self.root.is_dir()
        assert self.root.stat().st_dev==self.cfg['physical_device'] and not self.root.stat().st_mode&0o077
        path=Path(self.cfg['docker_config'])
        assert path.resolve()==path and path.is_dir() and not list(path.iterdir())
        assert path.stat().st_dev==self.cfg['physical_device'] and not path.stat().st_mode&0o077
        state=Path('/var/run/docker.sock').stat()
        import stat
        assert stat.S_ISSOCK(state.st_mode) and [state.st_dev,state.st_ino]==self.cfg['socket_identity']
        assert self.docker(['info','--format','{{.DockerRootDir}}']).decode().strip()=='/mnt/openfoam/docker'
        if self.cfg['kind']=='production':self.rollout().source_check()
        return True

    def docker(self,args,timeout=3,limit=524288):
        import stat
        config=Path(self.cfg['docker_config']);socket=Path('/var/run/docker.sock')
        state=socket.stat()
        assert config.resolve()==config and config.is_dir() and not list(config.iterdir())
        assert config.stat().st_dev==self.cfg['physical_device'] and not config.stat().st_mode&0o077
        assert socket.resolve()==Path('/run/docker.sock') and stat.S_ISSOCK(state.st_mode)
        assert [state.st_dev,state.st_ino]==self.cfg['socket_identity'],'local Docker socket drift'
        if args[0] in ('start','stop'):self.authorize()
        return self.runner(self.D+args,timeout=timeout,limit=limit)

    def raw_candidate(self):
        identifier=self.cfg['core']['candidate']['id']
        value=json.loads(self.docker(['inspect',identifier]))[0]
        assert value['Id']==identifier
        expected=self.cfg['container']
        assert value['Image']==expected['image']
        for name in ('Config','Mounts'):
            assert digest(value[name])==expected[name+'_sha256']
        state_hashes=expected.get('HostConfig_state_sha256')
        if state_hashes is None:
            assert self.cfg['kind']=='fixture','production requires state-bound HostConfig admission'
            host_hash=expected['HostConfig_sha256']
        else:
            assert set(state_hashes)=={'created','running','exited','dead'}
            host_hash=state_hashes.get(value['State']['Status'])
            assert host_hash is not None,'unreviewed container state'
        assert digest(value['HostConfig'])==host_hash,'exact lifecycle HostConfig drift'
        if self.cfg['kind']=='fixture':
            assert value['HostConfig']['NetworkMode']=='none' and not value['HostConfig']['PortBindings']
        return value

    def inspect(self,identifier):
        assert identifier==self.cfg['core']['candidate']['id'],'watchdog only controls its exact candidate'
        value=self.raw_candidate();state=value['State']
        return {'id':identifier,'fingerprint':digest(self.cfg['container']),
                'running':state['Running'],'pid':state['Pid'],'status':state['Status'],'restarting':state['Restarting']}

    def stop(self,identifier):
        self.admit();self.inspect(identifier)
        self.docker(['stop','--time','0',identifier],timeout=3)

    def start(self,identifier):
        self.admit();state=self.inspect(identifier)
        assert state['running'] is False and state['pid']==0 and state['restarting'] is False
        self.docker(['start',identifier],timeout=3)

    def logs(self):
        value=self.raw_candidate();running=self.store.get('running')
        if value['State']['StartedAt']!=running['started_at'] or value['RestartCount']!=0:
            raise core.Refused('candidate_process_changed')
        return parse_logs(self.docker(['logs','--timestamps',value['Id']],limit=524288),self.cfg['core']['scope_hash'])

    def fetch(self,url):
        assert url==core.URL
        if self.cfg['kind']=='fixture':
            # A single owned Unix-socket trigger substitutes for public GET.
            trigger="import socket;s=socket.socket(socket.AF_UNIX);s.settimeout(1);s.connect('/tmp/fixture.sock');s.sendall(b'go');assert s.recv(3)==b'200';s.close()"
            self.docker(['exec',self.cfg['core']['candidate']['id'],'/usr/local/bin/python','-B','-c',trigger],timeout=2)
            body=b'{"items":[],"complete":false,"hydrating":true}';status=200
        else:
            raw=self.runner(['/usr/bin/curl','-q','--silent','--show-error','--noproxy','*','--proxy','',
                             '--request','GET','--connect-timeout','3','--max-time','5','--max-filesize','1048576',
                             '--max-redirs','0','--proto','=https','--write-out','\n%{http_code}',core.URL],
                            timeout=6,limit=1048581)
            body,code=raw.rsplit(b'\n',1);status=int(code)
        value=json.loads(body)
        items=value.get('items',[])
        assert isinstance(items,list)
        safe={'status':status,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),
              'items':len(items),'complete':value.get('complete'),'hydrating':value.get('hydrating'),
              'item_complete':[item.get('complete') for item in items if isinstance(item,dict)]}
        self.store.put('response-safe',safe)
        return safe

    def properties(self):
        keys='Id,LoadState,ActiveState,SubState,MainPID,User,KillMode,Restart,RuntimeMaxUSec,TimeoutStopUSec,PrivateNetwork,ControlGroup,FragmentPath,ExecMainStartTimestampMonotonic,ExecStopPost'
        raw=self.runner(['/usr/bin/systemctl','show',self.cfg['unit'],'--property='+keys],timeout=2,limit=8192).decode()
        return dict(row.split('=',1) for row in raw.splitlines() if '=' in row)

    def supervisor_alive(self,proof):
        try:
            props=self.properties();pid=proof['pid'];proc=Path('/proc')/str(pid)
            fragment=Path(props['FragmentPath'])
            argv=proc.joinpath('cmdline').read_bytes().rstrip(b'\x00').decode().split('\x00')
            process={'boot_id':self.probe.boot(),'start_ticks':int(proc.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]),
                     'argv':argv,'cgroup':proc.joinpath('cgroup').read_text().strip(),
                     'executable_sha256':hashlib.sha256(proc.joinpath('exe').read_bytes()).hexdigest(),
                     'unit_file_sha256':hashlib.sha256(fragment.read_bytes()).hexdigest()}
            return supervisor_matches(proof,props,process)
        except Exception:return False

    def unit_command(self,launcher):
        assert re.fullmatch(r'/[A-Za-z0-9_/.-]+\.py',str(launcher)) and re.fullmatch(r'[a-zA-Z0-9-]+\.service',self.cfg['unit'])
        assert all(' ' not in str(p) for p in (launcher,self.root))
        base=['/usr/bin/python3','-I',str(launcher)]+([self.launcher_hash] if self.launcher_hash else [])
        return ['/usr/bin/sudo','-n','/usr/bin/systemd-run','--unit='+self.cfg['unit'],
                '--property=Type=exec','--property=User=corp','--property=Restart=no','--property=UMask=0077',
                '--property=KillMode=control-group','--property=NoNewPrivileges=yes','--property=PrivateNetwork=yes',
                '--property=RuntimeMaxSec=25s','--property=TimeoutStartSec=3s','--property=TimeoutStopSec=15s',
                '--property=StandardOutput=null','--property=StandardError=null',
                '--property=ExecStopPost='+' '.join(base+['finalize']),*base,'watch']

    def arm_and_dispatch(self,launcher):
        self.admit()
        assert self.launcher_hash and re.fullmatch('[0-9a-f]{64}',self.launcher_hash),'fixed-hash launcher required'
        assert not self.store.exists('running'),'one arm attempt per sealed root'
        value=self.raw_candidate()
        assert value['State']['Running'] and value['RestartCount']==0
        if self.cfg['kind']=='production':
            approval=json.loads(Path(self.cfg['approval_path']).read_text())
            assert approval=={'candidate_id':value['Id'],'source_sha':self.cfg['core']['source_sha'],'allow_one_get':True,'package_seal':self.package_seal}
            assert Path(self.cfg['activation_result']).is_file(),'coordinator activation must precede arm'
            self.before_observation()
        self.store.put('running',{'started_at':value['State']['StartedAt'],'pid':value['State']['Pid']})
        lines,invalid=self.logs()
        assert not lines and not invalid,'pre-existing target events/ambiguous history refuse GET'
        self.store.put('prearm-log-proof',{'observed_target_events':0,'complete_bounded_read':True})
        self.runner(self.unit_command(launcher),timeout=4,limit=8192)
        deadline=time.monotonic()+2
        while not self.store.exists('watch-ready') and time.monotonic()<deadline:time.sleep(.02)
        ready=self.store.get('watch-ready');props=self.properties()
        age=time.monotonic()-int(props['ExecMainStartTimestampMonotonic'])/1000000
        assert 0<=age<1,'watchdog arm is late'
        proof={**ready,'verified':True,'unit':self.cfg['unit'],'python_sha256':hashlib.sha256(Path('/usr/bin/python3').read_bytes()).hexdigest(),
               'unit_file_sha256':hashlib.sha256(Path(props['FragmentPath']).read_bytes()).hexdigest(),
               'argv':['/usr/bin/python3','-I',str(launcher),self.launcher_hash,'watch'],'run_id':self.cfg['core']['run_id'],
               'service_deadline_boottime':self.probe.clock()+25-age}
        assert self.supervisor_alive(proof),'independent watchdog not alive'
        self.probe.arm(proof)
        try:self.probe.dispatch_once()
        except core.Refused:
            self.store.put('dispatch-inconclusive',{'one_attempt_only':True})
        return {'attempted':self.store.exists('attempted'),'unit':self.cfg['unit'],'retry':False}

    def watch(self):
        self.admit()
        pid=os.getpid();ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
        self.store.put('watch-ready',{'pid':pid,'start_ticks':ticks,'boot_id':self.probe.boot()})
        wait=time.monotonic()+3
        while not self.store.exists('armed') and time.monotonic()<wait:time.sleep(.02)
        if not self.store.exists('armed'):return
        deadline=self.store.get('armed')['fence_at']
        while self.probe.clock()<deadline:
            if not self.store.exists('attempted'):
                time.sleep(.02);continue
            lines,invalid=self.logs()
            if invalid:raise core.Refused('malformed_budget_event')
            if core.finished(lines,self.cfg['core']['scope_hash']):
                self.probe.finish(lines);return
            time.sleep(.05)
        # Exit invokes independently supervised ExecStopPost. No SQL here.

    def finalize(self):
        self.admit()
        if not self.store.exists('armed') and not self.store.exists('attempted'):
            self.store.put('unit-unused',{'no_get':True})
            self.store.put('unit-finalized',{'manifest_hash':core.validate_manifest(self.cfg['core']),'provider_ended_proven':False,'no_get':True})
            return
        try:
            lines,_=self.logs()
            starts={row['attempt'] for row in core.safe_events(lines) if row['state']=='started'}
            start_seen=len(starts)==1
        except Exception:start_seen=False
        try:self.probe.recover(start_seen=start_seen)
        except Exception:
            # Exactly one intentional stop attempt. A prior unknown result is
            # never retried or represented as successful fencing.
            if self.store.exists('attempted') and not self.store.exists('fenced') and not self.store.exists('fence-attempted'):
                self.store.put('fence-attempted',{'emergency':True,'at':self.probe.clock()})
                try:
                    self.stop(self.cfg['core']['candidate']['id'])
                    self.probe.stopped_proof(self.cfg['core']['candidate'])
                    self.store.put('emergency-fenced',{'restart':False,'reason':'execution_proof_unknown'})
                except Exception:
                    pass
            if not self.store.exists('finalizer-inconclusive'):
                self.store.put('finalizer-inconclusive',{'restart_or_completion_unproven':True})
        try:ended=self.probe.disarm_proven(self.probe.binding()) is True
        except Exception:ended=False
        if not ended:
            self.store.put('recovery-hold',{'provider_ended_proven':False,'restart_authorized':False,
                'intentional_stop_attempts':int(self.store.exists('fence-attempted')),
                'termination_proven':self.store.exists('fenced') or self.store.exists('emergency-fenced'),
                'manual_exact_id_recovery_required':True,'candidate_id':self.cfg['core']['candidate']['id']})
        self.store.put('unit-finalized',{'manifest_hash':core.validate_manifest(self.cfg['core']),'provider_ended_proven':ended})
        if not ended:
            raise core.Refused('finalizer_recovery_hold_no_fence_claim')

    def before_observation(self):
        module=self.rollout()
        put_baseline(self.store,'baseline-before',module.combined_baseline())

    def rollout(self):
        spec=importlib.util.spec_from_file_location('sealed_rollout',self.cfg['rollout_path'])
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.APPROVED_SEAL_HASH=self.cfg['rollout_seal'];module.artifact_check()
        return module

    def remaining(self):
        return self.store.get('armed')['armed_at']+45-self.probe.clock()

    def local_health(self):
        healthy=True;purchase=None
        for url in ('http://127.0.0.1:3031/healthz','http://127.0.0.1:18080/healthz','http://127.0.0.1:18080/workshop/purchase-config.json'):
            if self.remaining()<1.2:raise core.Refused('health_observation_window_insufficient')
            with HTTP.open(url,timeout=1) as response:
                healthy=healthy and response.status==200
                if url.endswith('purchase-config.json'):
                    raw=response.read(65537)
                    assert len(raw)<=65536
                    purchase=json.loads(raw).get('enabled')
        return {'healthy':healthy,'purchase_enabled':purchase}

    def scope_safety(self):
        query=json.loads(Path(self.cfg['selector_safety_query']).read_text())['query']
        assert query.startswith('SELECT ') and ';' not in query and '\x00' not in query
        text="BEGIN READ ONLY; SET LOCAL statement_timeout='3s'; SET LOCAL lock_timeout='3s'; "+query+'; COMMIT'
        raw=self.docker(['exec','-e','PGOPTIONS=-c default_transaction_read_only=on',self.cfg['postgres_id'],
                         '/usr/lib/postgresql/17/bin/psql','-X','-A','-t','-q','-v','ON_ERROR_STOP=1',
                         '-U','autodata','-d','autodata','-c',text],timeout=4)
        return json.loads(raw)

    def postcheck(self,identifier):
        assert self.store.exists('disarmed') and self.probe.disarm_proven(self.probe.binding())
        finalized=self.store.get('unit-finalized')
        assert finalized['provider_ended_proven'] is True and finalized['manifest_hash']==core.validate_manifest(self.cfg['core'])
        self.store.put('postcheck-started',{'provider_ended_proven':True,'finalizer_completed_proof':True})
        if self.cfg['kind']=='fixture':
            time.sleep(self.cfg.get('fixture_sql_delay',0))
            return {'protected_unchanged':True,'catalog_baseline_preserved':True,'healthy':True,'purchase_enabled':False}
        module=self.rollout();after=module.combined_baseline();put_baseline(self.store,'baseline-after',after)
        before=get_baseline(self.store,'baseline-before')['tables'];tables=after['tables']
        self.store.put('baseline-delta',baseline_delta(before,tables))
        protected=self.cfg['protected_tables']
        if self.probe.clock()+3.2>self.store.get('armed')['armed_at']+45:raise core.Refused('scope_observation_window_insufficient')
        safety=self.scope_safety()
        self.store.put('selector-safety-after',safety)
        exact=all(before[name]==tables[name] for name in protected)
        preserved=all(set(rows)<=set(tables[name]) for name,rows in before.items())
        catalog_exact=all(before[name]==tables[name] for name in before if name not in protected)
        self.store.put('baseline-comparison',{'protected_tables_exact':exact,'baseline_rows_preserved':preserved,
            'catalog_exact':catalog_exact,'manual_scope_classification_required':not catalog_exact,'table_count':39})
        health=self.local_health()
        current=self.raw_candidate()
        health['healthy']=health['healthy'] and current['State']['Running'] and current['RestartCount']==0
        return {'protected_unchanged':exact,'catalog_baseline_preserved':preserved and catalog_exact,**health}

    def finish(self):
        self.admit();deadline=self.store.get('armed')['armed_at']+45
        while self.probe.clock()<deadline:
            if self.store.exists('unit-finalized'):break
            time.sleep(.05)
        else:raise core.Refused('supervisor_not_finished')
        assert self.probe.disarm_proven(self.probe.binding()),'provider execution termination is not proven'
        # SQL timeout is15s. Never extend the accepted observation window or rearm.
        if self.probe.clock()+15>deadline:raise core.Refused('postcheck_window_insufficient')
        self.probe.verify_outcome()
        return {'provider_ended':True,'verified':True,'get_retried':False}


if __name__=='__main__':
    # A sealed launcher is required for operational methods; direct CLI is passive.
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['validate']);parser.add_argument('manifest',type=Path)
    args=parser.parse_args();value=json.loads(args.manifest.read_text())
    print(json.dumps({'core_manifest_hash':core.validate_manifest(value['core']),'direct_live_execution':False}))
