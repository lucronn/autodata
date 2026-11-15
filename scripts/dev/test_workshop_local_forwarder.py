"""Synthetic socket/identity tests; no Docker or provider access."""
import importlib.util
from pathlib import Path
import socket
import threading
import time
import unittest
import tempfile
import json
from unittest.mock import patch
from contextlib import redirect_stdout
import io
import hashlib
import copy
from contextlib import ExitStack
import test_workshop_local_admission as policy_tests

spec=importlib.util.spec_from_file_location("forwarder",Path(__file__).with_name("workshop_local_forwarder.py"))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)


def fixture():
    marker={"source_sha":"a"*40,"network_id":"net1","containers":{"api1":"api","pg1":"postgres"}}
    network={"Id":"net1","Name":f.a.PROJECT+"_internal","Driver":"bridge","Internal":True,"Labels":{"com.docker.compose.project":f.a.PROJECT,"com.docker.compose.network":"internal"},"Containers":{"api1":{},"pg1":{}},"IPAM":{"Config":[{"Subnet":"172.27.0.0/16","Gateway":"172.27.0.1"}]}}
    api={"Id":"api1","Name":"/"+f.a.PROJECT+"-api-1","Image":f.a.IMAGES["api"],"State":{"Running":True,"Status":"running","StartedAt":"2026-11-15T00:00:00.000000000Z","Pid":1234},"RestartCount":0,"Config":{"User":"1000:1000","Cmd":["/runtime/autodata-api"],"Entrypoint":[],"Labels":{"com.docker.compose.project":f.a.PROJECT,"com.docker.compose.service":"api"}},"HostConfig":{"ReadonlyRootfs":True,"Privileged":False,"CapDrop":["ALL"],"CapAdd":[],"SecurityOpt":["no-new-privileges:true"],"PortBindings":{},"ExtraHosts":[],"Devices":[],"Memory":512*1024**2},"Mounts":[{"Type":"bind","Source":str(f.a.ROOT/"bin/autodata-api"),"Destination":"/runtime/autodata-api","RW":False}],"NetworkSettings":{"Ports":{},"Networks":{f.a.PROJECT+"_internal":{"NetworkID":"net1","IPAddress":"172.27.0.6"}}}}
    return api,network,marker


class BindingTests(unittest.TestCase):
    def test_valid_binding_and_fixed_limits(self):
        api,net,state=fixture();self.assertEqual(f.binding_errors(api,net,state),[])
        self.assertEqual(f.LISTEN,("127.0.0.1",3041));self.assertEqual(f.MAX_CONCURRENT,16);self.assertEqual(f.MAX_TOTAL,256);self.assertEqual(f.MAX_LIFETIME,600);self.assertLessEqual(f.BUFFER_SIZE,65536)

    def test_unsafe_identity_lifecycle_network_mount_publication(self):
        changes=[lambda a,n,s:a.update(Id="other"),lambda a,n,s:a.update(Image="other"),lambda a,n,s:a["State"].update(Running=False),lambda a,n,s:a["Config"].update(User="0"),lambda a,n,s:a["HostConfig"].update(ReadonlyRootfs=False),lambda a,n,s:a["HostConfig"].update(PortBindings={"8080/tcp":[]}),lambda a,n,s:a["NetworkSettings"].update(Ports={"8080/tcp":[{}]}),lambda a,n,s:a["NetworkSettings"]["Networks"].update(other={}),lambda a,n,s:a["NetworkSettings"]["Networks"][f.a.PROJECT+"_internal"].update(IPAddress="127.0.0.1"),lambda a,n,s:a["NetworkSettings"]["Networks"][f.a.PROJECT+"_internal"].update(IPAddress="172.28.0.2"),lambda a,n,s:n.update(Internal=False),lambda a,n,s:n["Containers"].update(outsider={}),lambda a,n,s:a["Mounts"][0].update(RW=True),lambda a,n,s:a["Config"]["Labels"].update({"com.docker.compose.project":"other"})]
        for number,change in enumerate(changes):
            with self.subTest(case=number):
                api,net,state=fixture();change(api,net,state);self.assertTrue(f.binding_errors(api,net,state))

    def test_inspect_error_output_is_constant(self):
        self.assertEqual(f.safe_error(ValueError("synthetic-secret-sentinel")),"forwarder_failed")

    def test_changed_binding_closes_listener_and_active_clients(self):
        calls=[]
        class Peer:
            def shutdown(self,*args):calls.append("shutdown")
            def close(self):calls.append("close")
        relay=f.Forwarder(("api1","net1","172.27.0.6"),lambda:("api1","net1","172.27.0.7"))
        relay.listener=Peer();relay.peers.add(Peer())
        self.assertFalse(relay.revalidate());self.assertTrue(relay.stop_event.is_set());self.assertIn("close",calls)

    def test_connection_and_lifetime_bounds(self):
        relay=f.Forwarder(("api1","net1","172.27.0.6"),lambda:("api1","net1","172.27.0.6"))
        for _ in range(f.MAX_CONCURRENT):self.assertTrue(relay.reserve())
        self.assertFalse(relay.reserve());relay.release();self.assertTrue(relay.reserve())
        relay.total=f.MAX_TOTAL;self.assertFalse(relay.reserve())
        relay.started=time.monotonic()-f.MAX_LIFETIME-1;self.assertFalse(relay.within_lifetime())

    def test_same_id_ip_restart_changes_lifecycle_identity_and_fences(self):
        api,net,state=fixture();identity=f.binding_identity(api,net,state)
        for field,value in [("StartedAt","2026-11-15T00:00:01.000000000Z"),("Pid",5678),("RestartCount",1)]:
            changed=__import__("copy").deepcopy(api)
            (changed if field=="RestartCount" else changed["State"])[field]=value
            updated=f.binding_identity(changed,net,state)
            self.assertNotEqual(updated,identity)
            relay=f.Forwarder(identity,lambda:updated)
            self.assertFalse(relay.revalidate());self.assertTrue(relay.stop_event.is_set())

    def test_local_engine_ignores_ambient_remote_docker_and_proxies(self):
        from unittest.mock import Mock
        result=Mock(returncode=0,stdout="[{}]")
        with patch.dict(f.os.environ,{"DOCKER_HOST":"synthetic-remote-engine","DOCKER_CONTEXT":"remote","DOCKER_CONFIG":"remote-config","HTTPS_PROXY":"synthetic-proxy"}),patch.object(f.subprocess,"run",return_value=result) as run:
            self.assertEqual(f.docker_json(["inspect","api1"],time.monotonic()+2),{})
            args,kwargs=run.call_args
            self.assertEqual(args[0][0],"/usr/bin/docker")
            self.assertIn("unix:///var/run/docker.sock",args[0])
            self.assertFalse(set(kwargs["env"])&{"DOCKER_HOST","DOCKER_CONTEXT","DOCKER_CONFIG","HTTPS_PROXY"})

    def test_upstream_connect_rechecks_before_any_request_bytes(self):
        identity=("api1","net1","172.27.0.6")
        relay=f.Forwarder(identity,lambda:("api1","net1","172.27.0.7"))
        left,client=socket.socketpair();upstream,right=socket.socketpair()
        left.sendall(b"synthetic-request-must-not-reach-changed-target")
        with patch.object(f.socket,"create_connection",return_value=upstream):relay.handle(client)
        right.settimeout(1);self.assertEqual(right.recv(65536),b"")
        self.assertTrue(relay.stop_event.is_set());left.close();right.close()

    def test_source_guard_detects_content_replacement_and_new_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/"source";source.mkdir();(root/"bin").mkdir()
            archive=root/"source.tar";archive.write_bytes(b"archive")
            binary=root/"bin/autodata-api";binary.write_bytes(b"binary")
            item=source/"app.py";item.write_text("first")
            with patch.object(f.a,"ROOT",root):
                original=f.source_guard();item.write_text("other")
                self.assertNotEqual(f.source_guard(),original)
                original=f.source_guard();(source/"new.py").write_text("new")
                self.assertNotEqual(f.source_guard(),original)
                original=f.source_guard();replacement=root/"replacement";replacement.write_bytes(b"binary");replacement.replace(binary)
                self.assertNotEqual(f.source_guard(),original)

    def test_exclusive_lifetime_lock_rejects_simultaneous_owner(self):
        with tempfile.TemporaryDirectory() as temp:
            private=Path(temp);private.chmod(0o700)
            with patch.object(f,"PRIVATE",private):
                first=f.acquire_lock()
                try:
                    with self.assertRaises(BlockingIOError):f.acquire_lock()
                finally:f.os.close(first)
                second=f.acquire_lock();f.os.close(second)

    def test_make_checker_full_startup_rejects_missing_extra_other_image_and_env(self):
        for mutation in [None,"missing","extra","other_image","api_env","other_env"]:
            with self.subTest(mutation=mutation):
                config,containers=policy_tests.runtime_fixture();network_id="f"*64
                for i,c in enumerate(containers,1):
                    name=c["Config"]["Labels"]["com.docker.compose.service"]
                    c.update(Id=f"{i:064x}",Name="/"+f.a.PROJECT+"-"+name+"-1",RestartCount=0,State={"Running":name!="migration-runner","Status":"exited" if name=="migration-runner" else "running","StartedAt":"2026-11-15T00:00:00.000000000Z","Pid":100+i})
                    c["Config"]["Labels"]["com.docker.compose.project"]=f.a.PROJECT
                    c["NetworkSettings"]={"Ports":{},"Networks":{f.a.PROJECT+"_internal":{"NetworkID":network_id,"IPAddress":f"172.27.0.{i+1}"}}}
                marker={"source_sha":"a"*40,"network_id":network_id,"containers":{c["Id"]:c["Config"]["Labels"]["com.docker.compose.service"] for c in containers},"storage":{name:[1,1] for name in f.a.DATA_DIRS}}
                api=next(c for c in containers if c["Config"]["Labels"]["com.docker.compose.service"]=="api")
                _,network,_=fixture();network.update(Id=network_id,Containers={c["Id"]:{} for c in containers if c["State"]["Running"]})
                manifest={"source_sha":"a"*40,"source_tree":"b"*40,"archive_sha256":"c"*64,"binary_sha256":hashlib.sha256(b"binary").hexdigest(),"config_sha256":hashlib.sha256(json.dumps(config,sort_keys=True,separators=(",",":")).encode()).hexdigest(),"dependency_compatible":True}
                if mutation=="missing":containers.pop(0)
                if mutation=="extra":containers.append({"Id":"e"*64})
                if mutation=="other_image":containers[0]["Image"]="unexpected"
                if mutation=="api_env":api["Config"]["Env"].append("AUTODATA_STRIPE_SECRET_KEY=synthetic-secret-sentinel")
                if mutation=="other_env":containers[0]["Config"]["Env"].append("NEW_PROVIDER_SECRET=synthetic-secret-sentinel")
                calls=[]
                def output(command,deadline):
                    calls.append(command)
                    if command[0]=="compose":return json.dumps(config)
                    if command[:2]==["network","ls"]:return network_id
                    if command[0]=="ps":return "\n".join(c["Id"] for c in containers)
                    if command[:2]==["network","inspect"]:return json.dumps([network])
                    if command[0]=="inspect":return json.dumps([c for c in containers if c["Id"] in command[1:]])
                    self.fail("unexpected read command")
                class Space:
                    f_bavail=20*1024**3;f_frsize=1;f_favail=10000
                with ExitStack() as stack:
                    stack.enter_context(patch.object(f,"read_private",side_effect=lambda path:(marker,"state") if path.name=="accepted-state.json" else (manifest,"manifest")))
                    stack.enter_context(patch.object(f,"source_guard",return_value={"stable":1}))
                    stack.enter_context(patch.object(f,"private_bytes",return_value=b"synthetic"))
                    stack.enter_context(patch.object(f.a,"archive_errors",return_value=[]))
                    stack.enter_context(patch.object(f.a,"path_errors",return_value=[]))
                    stack.enter_context(patch.object(f,"storage_identity",return_value=marker["storage"]))
                    stack.enter_context(patch.object(f.os,"statvfs",return_value=Space()))
                    stack.enter_context(patch.object(f.Path,"read_bytes",return_value=b"binary"))
                    stack.enter_context(patch.object(f,"docker_output",side_effect=output))
                    if mutation is None:
                        checker,_,_=f.make_checker();self.assertEqual(checker()[0],api["Id"])
                        self.assertTrue(any(command[0]=="inspect" and len(command)==7 for command in calls))
                    else:
                        with self.assertRaises(ValueError):f.make_checker()

    def test_private_receipt_mode_symlink_and_missing_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);private=root/"private-config";private.mkdir(mode=0o700)
            receipt=private/"fixture.json";receipt.write_text("{}");receipt.chmod(0o600)
            with patch.object(f.a,"ROOT",root),patch.object(f,"PRIVATE",private):
                self.assertEqual(f.read_private(receipt)[0],{})
                receipt.chmod(0o644)
                with self.assertRaises(ValueError):f.read_private(receipt)
                receipt.chmod(0o600);link=private/"link.json";link.symlink_to(receipt)
                with self.assertRaises(ValueError):f.read_private(link)
                with self.assertRaises(FileNotFoundError):f.read_private(private/"absent.json")

    def test_cli_target_and_read_failure_fail_closed(self):
        out=io.StringIO()
        with redirect_stdout(out):self.assertEqual(f.main(["arbitrary-target"]),1)
        self.assertEqual(json.loads(out.getvalue()),{"code":"forwarder_failed"})
        relay=f.Forwarder(("api1","net1","172.27.0.6"),lambda:(_ for _ in ()).throw(ValueError("synthetic-secret-sentinel")))
        self.assertFalse(relay.revalidate());self.assertTrue(relay.stop_event.is_set())

    def test_lifetime_watchdog_and_occupied_listener_fence(self):
        relay=f.Forwarder(("api1","net1","172.27.0.6"),lambda:("api1","net1","172.27.0.6"))
        relay.started-=f.MAX_LIFETIME+1
        thread=threading.Thread(target=relay.watchdog);thread.start();thread.join(1)
        self.assertTrue(relay.stop_event.is_set());self.assertFalse(thread.is_alive())
        class Occupied:
            def setsockopt(self,*args):pass
            def bind(self,address):
                self.address=address;raise OSError("synthetic-bind-error")
            def shutdown(self,*args):pass
            def close(self):pass
        peer=Occupied();relay=f.Forwarder(("api1","net1","172.27.0.6"),lambda:None)
        with patch.object(f.socket,"socket",return_value=peer):
            with self.assertRaises(OSError):relay.serve()
        self.assertEqual(peer.address,("127.0.0.1",3041));self.assertTrue(relay.stop_event.is_set())

    def test_http_headers_and_response_bytes_are_transparent(self):
        client,ingress=socket.socketpair();upstream,server=socket.socketpair();stop=threading.Event()
        thread=threading.Thread(target=f.relay_bytes,args=(ingress,upstream,stop),daemon=True);thread.start()
        request=b"POST /fixture HTTP/1.1\r\nHost: localhost:3041\r\nOrigin: fixture-origin\r\nX-CSRF-Token: fixture-csrf\r\nCookie: fixture=session\r\nContent-Length: 4\r\n\r\nbody"
        response=b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nSet-Cookie: fixture=value; SameSite=Strict\r\n\r\nok"
        client.sendall(request);server.settimeout(2);self.assertEqual(server.recv(65536),request)
        server.sendall(response);client.settimeout(2);self.assertEqual(client.recv(65536),response)
        client.close();server.close();thread.join(2);self.assertFalse(thread.is_alive());ingress.close();upstream.close()

    def test_buffers_forward_large_payload_without_loss(self):
        left,ingress=socket.socketpair();upstream,right=socket.socketpair();stop=threading.Event();payload=b"x"*(f.BUFFER_SIZE*3+7)
        thread=threading.Thread(target=f.relay_bytes,args=(ingress,upstream,stop),daemon=True);thread.start()
        sender=threading.Thread(target=left.sendall,args=(payload,),daemon=True);sender.start()
        right.settimeout(2);received=b""
        while len(received)<len(payload):received+=right.recv(f.BUFFER_SIZE)
        self.assertEqual(received,payload);sender.join(1);left.close();right.close();thread.join(2);ingress.close();upstream.close()


if __name__=="__main__":unittest.main()
