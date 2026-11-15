"""Bounded host-only TCP ingress for the fixed empty M1 fixture. No CLI target."""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import select
import signal
import socket
import stat
import subprocess
import threading
import time
import workshop_local_admission as a

LISTEN = ("127.0.0.1", 3041)
MAX_CONCURRENT = 16
MAX_TOTAL = 256
MAX_LIFETIME = 600
BUFFER_SIZE = 65536
IDLE_TIMEOUT = 15
PRIVATE = a.ROOT / "private-config"


def safe_error(error):
    return "forwarder_failed"


def binding_errors(api, network, marker):
    errors=[]
    labels=api.get("Config",{}).get("Labels") or {}
    ids=[key for key,value in marker.get("containers",{}).items() if value=="api"]
    if ids!=[api.get("Id")] or labels.get("com.docker.compose.project")!=a.PROJECT or labels.get("com.docker.compose.service")!="api":errors.append("api_identity")
    config=api.get("Config",{});host=api.get("HostConfig",{})
    if api.get("Image")!=a.IMAGES["api"] or api.get("Name")!="/"+a.PROJECT+"-api-1":errors.append("api_image_name")
    if not api.get("State",{}).get("Running") or api.get("State",{}).get("Status")!="running":errors.append("api_stopped")
    if config.get("User")!="1000:1000" or config.get("Cmd")!=["/runtime/autodata-api"] or config.get("Entrypoint") not in [[],None]:errors.append("api_process")
    if host.get("ReadonlyRootfs") is not True or host.get("Privileged") or host.get("CapDrop")!=["ALL"] or host.get("CapAdd") or host.get("SecurityOpt")!=["no-new-privileges:true"] or host.get("ExtraHosts") or host.get("Devices") or host.get("Memory")!=512*1024**2:errors.append("api_security")
    if host.get("PortBindings") or api.get("NetworkSettings",{}).get("Ports"):errors.append("docker_publication")
    mounts=api.get("Mounts",[])
    if len(mounts)!=1 or mounts[0].get("Type")!="bind" or mounts[0].get("Source")!=str(a.ROOT/"bin/autodata-api") or mounts[0].get("Destination")!="/runtime/autodata-api" or mounts[0].get("RW") is not False:errors.append("api_binary_mount")
    nl=network.get("Labels") or {}
    if network.get("Id")!=marker.get("network_id") or network.get("Name")!=a.PROJECT+"_internal" or network.get("Driver")!="bridge" or network.get("Internal") is not True or nl.get("com.docker.compose.project")!=a.PROJECT or nl.get("com.docker.compose.network")!="internal":errors.append("network_identity")
    attached=set(network.get("Containers",{}))
    if attached-set(marker.get("containers",{})) or api.get("Id") not in attached:errors.append("foreign_or_missing_attachment")
    nets=api.get("NetworkSettings",{}).get("Networks",{})
    if set(nets)!={a.PROJECT+"_internal"}:return errors+["api_network_set"]
    selected=nets[a.PROJECT+"_internal"]
    if selected.get("NetworkID")!=marker.get("network_id"):errors.append("api_network_id")
    try:
        address=ipaddress.ip_address(selected["IPAddress"])
        subnets=[ipaddress.ip_network(item["Subnet"]) for item in network["IPAM"]["Config"] if item.get("Subnet")]
        gateways={item.get("Gateway") for item in network["IPAM"]["Config"]}
        if address.version!=4 or not address.is_private or address.is_loopback or address.is_multicast or selected["IPAddress"] in gateways or not any(address in subnet for subnet in subnets):errors.append("api_address")
    except (KeyError,ValueError,TypeError):errors.append("api_address")
    return sorted(set(errors))


def read_private(path):
    if path.parent!=PRIVATE or path.is_symlink():raise ValueError("private_path")
    if any(part.is_symlink() for part in [path,*path.parents]):raise ValueError("private_symlink")
    for directory in [PRIVATE,a.ROOT]:
        info=directory.stat()
        if directory.is_symlink() or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:raise ValueError("private_directory")
    info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o600 or info.st_size>65536:raise ValueError("private_file")
    data=path.read_bytes()
    return json.loads(data),hashlib.sha256(data).hexdigest()


def docker_json(command, deadline):
    remaining=deadline-time.monotonic()
    if remaining<=0:raise TimeoutError("inspect_deadline")
    result=subprocess.run(["docker",*command],capture_output=True,text=True,timeout=remaining)
    if result.returncode or len(result.stdout)>1024*1024:raise ValueError("inspect_failed")
    return json.loads(result.stdout)[0]


def make_checker():
    marker,marker_hash=read_private(PRIVATE/"accepted-state.json")
    manifest,manifest_hash=read_private(PRIVATE/"manifest.json")
    if a.manifest_errors(manifest) or marker.get("source_sha")!=manifest["source_sha"]:raise ValueError("source_pin")
    if set(marker.get("containers",{}).values())!=set(a.IMAGES) or len(marker["containers"])!=6:raise ValueError("resource_set")
    if a.archive_errors(a.ROOT/"source.tar",a.ROOT/"source",manifest):raise ValueError("source_archive")
    if hashlib.sha256((a.ROOT/"bin/autodata-api").read_bytes()).hexdigest()!=manifest["binary_sha256"]:raise ValueError("binary_pin")
    api_id=next(key for key,value in marker["containers"].items() if value=="api")
    def check():
        if read_private(PRIVATE/"accepted-state.json")[1]!=marker_hash or read_private(PRIVATE/"manifest.json")[1]!=manifest_hash:raise ValueError("receipt_changed")
        deadline=time.monotonic()+2
        api=docker_json(["inspect",api_id],deadline)
        network=docker_json(["network","inspect",marker["network_id"]],deadline)
        if binding_errors(api,network,marker):raise ValueError("binding_changed")
        return api_id,network["Id"],api["NetworkSettings"]["Networks"][a.PROJECT+"_internal"]["IPAddress"]
    return check,manifest_hash,marker_hash


def relay_bytes(client, upstream, stop):
    """Two bounded nonblocking buffers, including partial sends and half-close."""
    peers={client:upstream,upstream:client}
    pending={client:bytearray(),upstream:bytearray()}
    reading={client:True,upstream:True}
    shut=set();last=time.monotonic()
    for peer in peers:peer.setblocking(False)
    while not stop.is_set() and time.monotonic()-last<IDLE_TIMEOUT:
        for source,destination in peers.items():
            if not reading[source] and not pending[destination] and destination not in shut:
                try:destination.shutdown(socket.SHUT_WR)
                except OSError:pass
                shut.add(destination)
        if not any(reading.values()) and not any(pending.values()):return
        reads=[p for p in peers if reading[p] and len(pending[peers[p]])<BUFFER_SIZE]
        writes=[p for p in peers if pending[p]]
        try:ready_r,ready_w,_=select.select(reads,writes,[],0.2)
        except (OSError,ValueError):return
        for peer in ready_r:
            try:data=peer.recv(min(16384,BUFFER_SIZE-len(pending[peers[peer]])))
            except BlockingIOError:continue
            except OSError:return
            if data:pending[peers[peer]].extend(data);last=time.monotonic()
            else:reading[peer]=False
        for peer in ready_w:
            try:sent=peer.send(pending[peer])
            except BlockingIOError:continue
            except OSError:return
            if sent:del pending[peer][:sent];last=time.monotonic()


class Forwarder:
    def __init__(self,binding,checker):
        self.binding=binding;self.checker=checker
        self.stop_event=threading.Event();self.lock=threading.RLock()
        self.peers=set();self.listener=None;self.total=0;self.concurrent=0
        self.started=time.monotonic()

    def within_lifetime(self):return time.monotonic()-self.started<MAX_LIFETIME

    def reserve(self):
        with self.lock:
            if self.stop_event.is_set() or self.total>=MAX_TOTAL or not self.within_lifetime():return False
            self.total+=1
            if self.concurrent>=MAX_CONCURRENT:return False
            self.concurrent+=1;return True

    def release(self):
        with self.lock:self.concurrent=max(0,self.concurrent-1)

    def fence(self):
        self.stop_event.set()
        with self.lock:
            for peer in [self.listener,*self.peers]:
                if peer is None:continue
                try:peer.shutdown(socket.SHUT_RDWR)
                except OSError:pass
                try:peer.close()
                except OSError:pass

    def revalidate(self):
        try:
            if self.checker()!=self.binding:raise ValueError("identity_changed")
            return True
        except Exception:
            self.fence();return False

    def watchdog(self):
        while not self.stop_event.wait(0.5):
            if not self.within_lifetime() or not self.revalidate():self.fence();return

    def handle(self,client):
        upstream=None
        try:
            if self.stop_event.is_set():return
            upstream=socket.create_connection((self.binding[2],8080),timeout=2)
            with self.lock:self.peers.add(upstream)
            if not self.stop_event.is_set():relay_bytes(client,upstream,self.stop_event)
        except OSError:self.fence()
        finally:
            for peer in [client,upstream]:
                if peer is not None:
                    with self.lock:self.peers.discard(peer)
                    try:peer.close()
                    except OSError:pass
            self.release()

    def serve(self):
        try:
            self.listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            self.listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            self.listener.bind(LISTEN);self.listener.listen(MAX_CONCURRENT);self.listener.settimeout(0.2)
            threading.Thread(target=self.watchdog,daemon=True).start()
            while not self.stop_event.is_set() and self.within_lifetime() and self.total<MAX_TOTAL:
                try:client,_=self.listener.accept()
                except socket.timeout:continue
                except OSError:break
                if not self.reserve():client.close();continue
                with self.lock:self.peers.add(client)
                if not self.revalidate():self.release();break
                threading.Thread(target=self.handle,args=(client,),daemon=True).start()
        finally:self.fence()


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    try:
        if argv:raise ValueError("no_configuration_arguments")
        checker,manifest_hash,marker_hash=make_checker();binding=checker()
        relay=Forwarder(binding,checker)
        signal.signal(signal.SIGTERM,lambda *_:relay.fence())
        signal.signal(signal.SIGINT,lambda *_:relay.fence())
        record={"pid":os.getpid(),"process_start":Path("/proc/self/stat").read_text().split()[21],"script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"executable_sha256":hashlib.sha256(Path("/proc/self/exe").read_bytes()).hexdigest(),"manifest_sha256":manifest_hash,"state_sha256":marker_hash,"api_id":binding[0],"network_id":binding[1],"max_concurrent":MAX_CONCURRENT,"max_total":MAX_TOTAL,"max_lifetime_seconds":MAX_LIFETIME}
        path=PRIVATE/"forwarder-process.json"
        if path.exists():
            previous,_=read_private(path)
            proc=Path("/proc")/str(previous["pid"])/"stat"
            if proc.exists() and proc.read_text().split()[21]==previous["process_start"]:raise ValueError("forwarder_already_recorded")
        if path.is_symlink():raise ValueError("process_receipt_path")
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"w") as stream:json.dump(record,stream,sort_keys=True)
        os.chmod(path,0o600)
        print(json.dumps({"code":"forwarder_starting","pid":os.getpid()}),flush=True)
        relay.serve()
        print(json.dumps({"code":"forwarder_stopped","connections":relay.total}),flush=True)
        return 0
    except Exception as error:
        print(json.dumps({"code":safe_error(error)}),flush=True);return 1


if __name__=="__main__":sys.exit(main())
