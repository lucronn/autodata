"""Isolation boundary tests; no Docker/provider access."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import unittest
import tempfile
import tarfile
import hashlib
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("admission", Path(__file__).with_name("workshop_owned_article_admission.py"))
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)


def candidate():
    text = (ROOT / "infra/compose/compose.workshop-owned-article.yaml").read_text()
    text = text.replace("${M2A_ROOT:?required}", str(a.ROOT))
    for key in ("DB_PASSWORD", "S3_ACCESS", "S3_SECRET", "INTERNAL_TOKEN", "IMAGE_KEY"):
        text = text.replace("${M2A_" + key + ":?required}", "m2a_" + "a" * 48)
    return json.loads(text)


def runtime_fixture():
    config=candidate();actual=[]
    for name,svc in config["services"].items():
        actual.append({"Image":svc["image"],"Config":{"Labels":{"com.docker.compose.service":name},"User":svc["user"],"Cmd":svc["command"],"Env":[k+"="+v for k,v in svc["environment"].items()],"WorkingDir":svc.get("working_dir","")},"HostConfig":{"ReadonlyRootfs":True,"Privileged":False,"CapDrop":["ALL"],"CapAdd":[],"SecurityOpt":["no-new-privileges:true"],"ExtraHosts":[],"Devices":[],"Memory":int(svc["mem_limit"][:-1])*1024**2,"NanoCpus":1000000000,"LogConfig":{"Type":svc["logging"]["driver"],"Config":svc["logging"]["options"]},"Tmpfs":dict(item.split(":",1) for item in svc["tmpfs"]),"PortBindings":{}},"Mounts":[{"Type":"bind","Source":m["source"],"Destination":m["target"],"RW":not m["read_only"]} for m in svc["volumes"]]})
    return config,actual


class AdmissionTests(unittest.TestCase):
    def test_valid_six_service_candidate(self):
        self.assertEqual(a.validate_config(candidate()), [])

    def test_compose_renderer_harmless_defaults(self):
        c=candidate();c["networks"]["internal"]["ipam"]={}
        for service in c["services"].values():
            service["mem_limit"]=str(int(service["mem_limit"][:-1])*1024**2)
            service["networks"]={"internal":None}
            if "entrypoint" not in service:service["entrypoint"]=None
            if service.get("environment")=={}:service.pop("environment")
            if service.get("tmpfs")==[]:service.pop("tmpfs")
            for volume in service["volumes"]:
                volume["bind"].pop("create_host_path")
                if not volume["read_only"]:volume.pop("read_only")
        self.assertEqual(a.validate_config(c),[])

    def test_network_and_exposure_mutants(self):
        changes = [
            lambda c: c["services"]["api"].update(ports=[{"target":8080,"published":"3042","host_ip":"0.0.0.0"}]),
            lambda c: c["services"]["api"].update(ports=[{"target":8080,"published":"3042","host_ip":"127.0.0.1"}]),
            lambda c: c["services"]["postgres"].update(ports=[{"target":5432,"published":"5432"}]),
            lambda c: c["networks"]["internal"].update(internal=False),
            lambda c: c["networks"]["internal"].update(external=True),
            lambda c: c["services"]["api"].update(network_mode="host"),
            lambda c: c["services"]["api"].update(extra_hosts=["host:host-gateway"]),
            lambda c: c["services"].update(worker=copy.deepcopy(c["services"]["api"])),
        ]
        self.assertRejected(changes)

    def assertRejected(self, changes):
        for number, change in enumerate(changes):
            with self.subTest(case=number):
                c = candidate(); change(c)
                self.assertTrue(a.validate_config(c))

    def test_credentials_and_hydration_fail_closed(self):
        changes = [
            lambda c: c["services"]["api"]["environment"].update(AUTODATA_COMMERCE_MODE="stripe_test"),
            lambda c: c["services"]["api"]["environment"].update(AUTODATA_INGESTION_URL="synthetic-secret-sentinel"),
            lambda c: c["services"]["api"]["environment"].update(AUTODATA_ENV="staging"),
            lambda c: c["services"]["api"]["environment"].update(AUTODATA_AUTH_MODE="firebase"),
            lambda c: c["services"]["ingestion-http"]["environment"].update(BANKONE_BASE_URL="synthetic-secret-sentinel"),
            lambda c: c["services"]["ingestion-http"]["environment"].update(AUTODATA_STRIPE_SECRET_KEY="synthetic-secret-sentinel"),
            lambda c: c["services"]["api"].update(env_file=["/run/base44/app.env"]),
            lambda c: c["services"]["api"]["environment"].update(AUTODATA_READINESS_MODE="static"),
        ]
        self.assertRejected(changes)

    def test_image_mount_and_write_mutants(self):
        self.assertRejected([
            lambda c: c["services"]["api"].update(image="golang:latest"),
            lambda c: c["services"]["api"].update(build="."),
            lambda c: c["services"]["api"].update(pull_policy="always"),
            lambda c: c["services"]["api"].update(privileged=True),
            lambda c: c["services"]["api"].update(read_only=False),
            lambda c: c["services"]["api"].update(devices=["/dev/sda"]),
            lambda c: c["services"]["api"]["volumes"][0].update(read_only=False),
            lambda c: c["services"]["api"]["volumes"][0].update(source="/home/corp/Documents/ChatGPT/autodata"),
            lambda c: c["services"]["api"]["volumes"][0].update(source=str(a.ROOT / "../escape")),
            lambda c: c["services"]["api"]["logging"]["options"].update({"max-size":"1g"}),
            lambda c: c["services"]["minio"]["volumes"][1].update(target="/elsewhere"),
            lambda c: c["services"]["api"].pop("tmpfs"),
        ])

    def test_redaction_never_echoes_mutated_values(self):
        c = candidate(); c["services"]["api"]["environment"]["evil"] = "synthetic-secret-sentinel"
        self.assertNotIn("sentinel", json.dumps(a.validate_config(c)))
        self.assertNotIn("sentinel", a.safe_failure(ValueError("synthetic-secret-sentinel")))

    def test_capacity_requires_known_growth_and_reserves(self):
        good = dict(docker_free=1024*1024*1024, home_free=10*1024**3, docker_inodes=10000, home_inodes=10000, growth_bytes=64*1024**2)
        self.assertEqual(a.capacity_errors(**good), [])
        for field, value in [("docker_free", 600*1024**2),("home_free",1024**3),("docker_inodes",2),("home_inodes",2),("growth_bytes",None),("growth_bytes",-1),("growth_bytes",512*1024**2)]:
            with self.subTest(field=field,value=value):
                bad={**good,field:value}; self.assertTrue(a.capacity_errors(**bad))

    def test_source_manifest_is_exact_and_complete(self):
        valid={key:"a"*length for key,length in a.HASH_FIELDS.items()}
        valid["dependency_compatible"]=True
        self.assertEqual(a.manifest_errors(valid),[])
        for key in valid:
            bad=valid.copy(); bad.pop(key)
            self.assertTrue(a.manifest_errors(bad))
        self.assertTrue(a.manifest_errors({**valid,"dependency_compatible":False}))
        self.assertTrue(a.manifest_errors({**valid,"source_sha":"HEAD"}))

    def test_path_device_and_symlink_rejected(self):
        self.assertTrue(a.path_errors(a.ROOT / "..", lambda p: {"device":"wrong","fstype":"ext4","symlink":False}))
        self.assertTrue(a.path_errors(a.ROOT, lambda p: {"device":a.DEVICE,"fstype":"ext4","symlink":True}))
        self.assertTrue(a.path_errors(a.ROOT, lambda p: {"device":"wrong","fstype":"ext4","symlink":False}))
        self.assertEqual(a.path_errors(a.ROOT, lambda p: {"device":a.DEVICE,"fstype":"ext4","symlink":False}),[])

    def test_archive_binding_rejects_tampered_extra_and_wrong_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/"source"; source.mkdir()
            live=source/"app.py"; live.write_bytes(b"fixture")
            archive=root/"source.tar"
            with tarfile.open(archive,"w",format=tarfile.PAX_FORMAT,pax_headers={"comment":"a"*40}) as tf:
                tf.add(live,arcname="app.py")
            manifest={"source_sha":"a"*40,"archive_sha256":hashlib.sha256(archive.read_bytes()).hexdigest()}
            self.assertEqual(a.archive_errors(archive,source,manifest),[])
            live.write_bytes(b"tampered")
            self.assertTrue(a.archive_errors(archive,source,manifest))
            live.write_bytes(b"fixture"); (source/"extra").write_text("unexpected")
            self.assertTrue(a.archive_errors(archive,source,manifest))
            (source/"extra").unlink()
            self.assertTrue(a.archive_errors(archive,source,{**manifest,"source_sha":"b"*40}))

    def test_first_start_rejects_existing_resources_or_nonempty_data(self):
        self.assertTrue(a.ownership_errors([{"Id":"unknown"}],[],None))
        self.assertTrue(a.ownership_errors([],[{"Id":"unknown"}],None))
        self.assertEqual(a.ownership_errors([],[],None),[])
        self.assertTrue(a.fresh_data_errors({"pgdata":False,"nats-data":True,"s3-data":True,"s3-work":True},None))
        self.assertEqual(a.fresh_data_errors({k:True for k in a.DATA_DIRS},None),[])

    def test_restart_rejects_external_attachment_wrong_owner_or_identity(self):
        marker={"network_id":"network1","containers":{"container1":"api"},"storage":{"pgdata":[1,2]},"source_sha":"a"*40}
        net={"Id":"network1","Name":a.PROJECT+"_internal","Internal":True,"Labels":{"com.docker.compose.project":a.PROJECT,"com.docker.compose.network":"internal"},"Containers":{"container1":{}}}
        con={"Id":"container1","Name":"/"+a.PROJECT+"-api-1","Image":a.IMAGES["api"],"Config":{"Labels":{"com.docker.compose.project":a.PROJECT,"com.docker.compose.service":"api"}},"HostConfig":{"ReadonlyRootfs":True},"NetworkSettings":{"Networks":{a.PROJECT+"_internal":{"NetworkID":"network1"}}}}
        self.assertEqual(a.ownership_errors([net],[con],marker),[])
        bad=copy.deepcopy(net);bad["Containers"]["outsider"]={}
        self.assertTrue(a.ownership_errors([bad],[con],marker))
        bad=copy.deepcopy(con);bad["Config"]["Labels"]["com.docker.compose.project"]="other"
        self.assertTrue(a.ownership_errors([net],[bad],marker))
        bad=copy.deepcopy(con);bad["NetworkSettings"]["Networks"]["other"]={}
        self.assertTrue(a.ownership_errors([net],[bad],marker))
        self.assertTrue(a.fresh_data_errors({k:False for k in a.DATA_DIRS},marker,{"pgdata":[7,8]}))
        self.assertTrue(a.private_mode_errors(0o755,[0o600]))
        self.assertTrue(a.private_mode_errors(0o700,[0o644]))
        self.assertEqual(a.private_mode_errors(0o700,[0o600]),[])

    def test_image_declared_volumes_require_explicit_bounded_targets(self):
        metadata={"Config":{"Volumes":{"/var/lib/postgresql/data":{}}}}
        self.assertTrue(a.image_volume_errors(metadata,{"volumes":[],"tmpfs":[]}))
        self.assertTrue(a.image_volume_errors(metadata,{"volumes":[],"tmpfs":["/var/lib/postgresql/data:rw"]}))
        self.assertEqual(a.image_volume_errors(metadata,{"volumes":[],"tmpfs":["/var/lib/postgresql/data:rw,noexec,nosuid,size=1m"]}),[])
        self.assertEqual(a.image_volume_errors(metadata,{"volumes":[{"type":"bind","target":"/var/lib/postgresql/data"}],"tmpfs":[]}),[])
        self.assertEqual(a.image_volume_errors({"Config":{"Volumes":None}},{"volumes":[],"tmpfs":[]}),[])
        self.assertTrue(a.image_volume_errors({"Config":{"Volumes":{"/unexpected":{}}}},candidate()["services"]["api"]))

    def test_effective_image_env_requires_explicit_review_and_blanks(self):
        metadata={"Config":{"Env":["PATH=/usr/bin","AUTODATA_BANKONE_API_KEY=synthetic-secret-sentinel","AUTODATA_MINIO_ROOT_PASSWORD=synthetic-secret-sentinel"]}}
        self.assertTrue(a.image_env_errors(metadata,{"environment":{}}))
        safe={"environment":{"AUTODATA_BANKONE_API_KEY":"","AUTODATA_MINIO_ROOT_PASSWORD":""}}
        self.assertEqual(a.image_env_errors(metadata,safe),[])
        bad=copy.deepcopy(safe);bad["environment"]["AUTODATA_BANKONE_API_KEY"]="synthetic-secret-sentinel"
        self.assertTrue(a.image_env_errors(metadata,bad))
        for key in ["NEW_PROVIDER_SECRET","AUTODATA_INNOCENT_CONFIG","BANKONE_NEW_FLAG","GOOGLE_NEW_FLAG","AWS_NEW_FLAG"]:
            extra=copy.deepcopy(metadata);extra["Config"]["Env"].append(key+"=synthetic-secret-sentinel")
            errors=a.image_env_errors(extra,safe)
            self.assertTrue(errors);self.assertNotIn("sentinel",json.dumps(errors))
        self.assertTrue(a.image_env_errors({"Config":{"Env":["AUTODATA_IMAGE_URL_KEY="]}},{"environment":{}}))

    def test_new_explicit_provider_secrets_still_must_be_empty(self):
        for key in ["AUTODATA_INCEPTION_API_KEY","STRIPE_SECRET_KEY","GOOGLE_APPLICATION_CREDENTIALS","FIREBASE_NEW_TOKEN","BANKONE_ACCESS_KEY","AUTODATA_BANKTWO_PASSWORD"]:
            with self.subTest(key=key):
                meta={"Config":{"Env":[key+"=synthetic-secret-sentinel"]}}
                self.assertTrue(a.image_env_errors(meta,{"environment":{key:"synthetic-secret-sentinel"}}))
                self.assertEqual(a.image_env_errors(meta,{"environment":{key:""}}),[])

    def test_actual_resource_policy_rejects_security_env_and_mount_drift(self):
        config,actual=runtime_fixture()
        self.assertEqual(a.runtime_policy_errors(actual,config),[])
        for mutate in [lambda c:c[0]["HostConfig"].update(Memory=1),lambda c:c[0]["HostConfig"].update(CapAdd=["ALL"]),lambda c:c[0]["HostConfig"].update(PortBindings={"8080/tcp":[]}),lambda c:c[0]["HostConfig"].update(Tmpfs={"/tmp":"rw"}),lambda c:c[0]["Mounts"][0].update(RW=False),lambda c:c[0]["Config"]["Env"].append("NEW_PROVIDER_SECRET=synthetic-secret-sentinel")]:
            changed=copy.deepcopy(actual);mutate(changed)
            self.assertTrue(a.runtime_policy_errors(changed,config))

    def test_helper_contains_no_docker_mutation_or_general_shell(self):
        self.assertEqual(a.DOCKER_READ_COMMANDS, {"image-inspect", "compose-config", "network-list-inspect", "container-list-inspect"})
        code = Path(a.__file__).read_text()
        self.assertNotIn("shell=True",code)


if __name__ == "__main__":
    unittest.main()
