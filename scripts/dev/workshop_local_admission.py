"""Read-only admission for the fixed, empty, local M1 Workshop fixture.

No Docker mutation, application imports, provider calls or secret-bearing output.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile

ROOT = Path("/home/corp/autodata-workshop-test-data-20261115/m1")
DEVICE = "/dev/nvme0n1p11"
PROJECT = "autodata-workshop-local-m1-20261115"
DOCKER_READ_COMMANDS = {"image-inspect", "compose-config", "network-list-inspect", "container-list-inspect"}
DATA_DIRS = ("pgdata", "nats-data", "s3-data", "s3-work")
HASH_FIELDS = {"source_sha":40,"source_tree":40,"archive_sha256":64,"binary_sha256":64,"config_sha256":64}
IMAGES = dict(zip(("postgres","nats","minio","migration-runner","ingestion-http","api"), (
"sha256:151aa1c2e849e7828ed8aef2183ae15f692cbe887d2f28921d8b44b26e154d7e",
"sha256:8b9f712ae2148dcbd9d7f3d16a942d515e290526e5d018500931eab62b18e045",
"sha256:7b5ca1f11aa4c91593612d2d4a9e253ec9152a4bd13a19e551290a042a4c52f5",
"sha256:ab20e934b27ba3ff927c1b4c9ff8cf6c32f315f743efe68dd3441182a87fb085",
"sha256:5c8e79b93db464da854ad33dc499e25c153bbcd52757569b1f2a4e5072acecb4",
"sha256:93c9cc81d720d1ff82111b60a91820a263f3735a4dbb1efe189e63ec3a76e578")))
SECRET_KEYS = {"POSTGRES_PASSWORD","PGPASSWORD","AUTODATA_POSTGRES_PASSWORD","AWS_ACCESS_KEY_ID","AWS_SECRET_ACCESS_KEY","AUTODATA_S3_ACCESS_KEY","AUTODATA_S3_SECRET_KEY","AUTODATA_INGESTION_INTERNAL_TOKEN","AUTODATA_IMAGE_URL_KEY"}


def policy_services():
    # Fixed commands/env/mounts are part of the reviewed boundary, not user input.
    db={"AUTODATA_DB_ADDRESS":"postgres:5432","AUTODATA_POSTGRES_DB":"workshop_local_m1","AUTODATA_POSTGRES_USER":"workshop_local_m1","AUTODATA_POSTGRES_PASSWORD":"${M1_DB_PASSWORD:?required}"}
    s3={"AUTODATA_S3_ADDRESS":"minio:9000","AUTODATA_S3_ENDPOINT":"minio:9000","AUTODATA_S3_ACCESS_KEY":"${M1_S3_ACCESS:?required}","AUTODATA_S3_SECRET_KEY":"${M1_S3_SECRET:?required}","AUTODATA_SOURCE_BUCKET":"workshop-local-m1-sources"}
    base={**db,**s3,"AUTODATA_NATS_ADDRESS":"nats:4222","AUTODATA_ENV":"test","AUTODATA_COMMERCE_MODE":"disabled","AUTODATA_PUBLIC_ORIGIN":"http://localhost:3041"}
    def mount(child,target,ro=False):
        return {"type":"bind","source":"${M1_ROOT:?required}/"+child,"target":target,"read_only":ro,"bind":{"create_host_path":False}}
    def service(name,env,command,mounts,tmpfs,memory,user="1000:1000",entrypoint=None):
        d={"image":IMAGES[name],"pull_policy":"never","environment":env,"command":command,"volumes":mounts,"tmpfs":tmpfs,"mem_limit":str(memory)+"m","cpus":1.0,"user":user,"read_only":True,"cap_drop":["ALL"],"security_opt":["no-new-privileges:true"],"restart":"no","networks":["internal"],"logging":{"driver":"json-file","options":{"max-size":"5m","max-file":"2"}}}
        if entrypoint is not None:d["entrypoint"]=entrypoint
        return d
    services={}
    services["postgres"]=service("postgres",{"POSTGRES_DB":"workshop_local_m1","POSTGRES_USER":"workshop_local_m1","POSTGRES_PASSWORD":"${M1_DB_PASSWORD:?required}"},["postgres"],[mount("pgdata","/var/lib/postgresql/data")],["/tmp:rw,noexec,nosuid,size=32m","/run/postgresql:rw,noexec,nosuid,size=16m,uid=999,gid=999"],768,"999:999")
    services["nats"]=service("nats",{},["-js","-sd","/data","-m","8222"],[mount("nats-data","/data")],["/tmp:rw,noexec,nosuid,size=16m"],128)
    services["minio"]=service("minio",{"AWS_ACCESS_KEY_ID":"${M1_S3_ACCESS:?required}","AWS_SECRET_ACCESS_KEY":"${M1_S3_SECRET:?required}","S3_BUCKET":"workshop-local-m1-sources"},["mini","-dir=/data","-s3.port=9000"],[mount("s3-data","/data"),mount("s3-work","/tmp")],[],256)
    services["migration-runner"]=service("migration-runner",{"PGHOST":"postgres","PGPORT":"5432","PGDATABASE":"workshop_local_m1","PGUSER":"workshop_local_m1","PGPASSWORD":"${M1_DB_PASSWORD:?required}"},["sh","/src/scripts/dev/migrate_sql.sh"],[mount("source","/src",True)],["/tmp:rw,noexec,nosuid,size=32m","/var/lib/postgresql/data:rw,noexec,nosuid,size=1m"],256)
    private={**base,"AUTODATA_INGESTION_HTTP_ADDR":":8081","AUTODATA_INGESTION_INTERNAL_TOKEN":"${M1_INTERNAL_TOKEN:?required}","BANKONE_BASE_URL":"","BANKTWO_BASE_URL":"","INCEPTION_API_BASE_URL":"","AUTODATA_KNOWLEDGE_SOURCE_URI_TEMPLATE":"","AUTODATA_KNOWLEDGE_SOURCE_URL_TEMPLATE":"","AUTODATA_FAST_CONSUMER_ENABLED":"0","AUTODATA_KNOWLEDGE_CONSUMER_ENABLED":"0","AUTODATA_MERCURY2_EXTRACTION_ENABLED":"0","AUTODATA_MERCURY2_JOB_PLANS_ENABLED":"0","AUTODATA_MERCURY2_PROCEDURE_COMPOSITION_ENABLED":"0","AUTODATA_DERIVED_ARTICLE_CACHE_ENABLED":"0","PYTHONDONTWRITEBYTECODE":"1","PYTHONPATH":"/src/workers/ingestion-python/src:/src/packages/contracts/python:/src/workers/enrichment-python/src","HOME":"/tmp"}
    services["ingestion-http"]=service("ingestion-http",private,["python","-m","autodata_ingestion.http_service"],[mount("source","/src",True)],["/tmp:rw,noexec,nosuid,size=64m"],768,entrypoint=[])
    services["ingestion-http"]["working_dir"]="/src"
    api={**base,"AUTODATA_API_ADDR":":8080","AUTODATA_AUTH_MODE":"local","AUTODATA_PROJECTION_STORE":"postgres","AUTODATA_INGESTION_URL":"","AUTODATA_IMAGE_URL_KEY":"${M1_IMAGE_KEY:?required}"}
    services["api"]=service("api",api,["/runtime/autodata-api"],[mount("bin/autodata-api","/runtime/autodata-api",True)],["/tmp:rw,noexec,nosuid,size=32m"],512,entrypoint=[])
    services["api"]["ports"]=[{"target":8080,"published":"3041","host_ip":"127.0.0.1","protocol":"tcp"}]
    for name,cmd in {"postgres":["pg_isready","-U","workshop_local_m1","-d","workshop_local_m1"],"nats":["wget","-q","-O","/dev/null","http://127.0.0.1:8222/healthz"],"minio":["wget","-q","-O","/dev/null","http://127.0.0.1:9333/cluster/status"],"ingestion-http":["python","-c","import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/healthz',timeout=2)"]}.items():
        services[name]["healthcheck"]={"test":["CMD",*cmd],"interval":"3s","timeout":"3s","retries":20}
    return services


def _substitute(value):
    if isinstance(value,str):return value.replace("${M1_ROOT:?required}",str(ROOT))
    if isinstance(value,list):return [_substitute(v) for v in value]
    if isinstance(value,dict):return {k:_substitute(v) for k,v in value.items()}
    return value


def _normalize(service):
    service=json.loads(json.dumps(service))
    for key in ["environment"]:
        service.setdefault(key,{})
    service.setdefault("tmpfs",[])
    if service.get("entrypoint","missing") is None:service.pop("entrypoint")
    nets=service.get("networks")
    if isinstance(nets,dict) and nets=={"internal":None}:service["networks"]=["internal"]
    if "mem_limit" in service:
        v=service["mem_limit"]
        if isinstance(v,str):service["mem_limit"]=int(v[:-1])*1024**2 if v.endswith("m") else int(v)
    service.pop("container_name",None) if service.get("container_name")=="" else None
    for v in service.get("volumes",[]):
        v.setdefault("read_only",False)
        v.setdefault("bind",{}).setdefault("create_host_path",False)
    for port in service.get("ports",[]):
        port.pop("mode",None) if port.get("mode")=="ingress" else None
    return service


def validate_config(config):
    errors=[]
    if set(config)-{"name","services","networks"} or config.get("name")!=PROJECT:return ["config_shape"]
    networks=json.loads(json.dumps(config.get("networks",{})))
    if networks.get("internal",{}).get("ipam")=={}:networks["internal"].pop("ipam")
    expected_net={"internal":True,"name":PROJECT+"_internal"}
    if networks!={"internal":expected_net}:errors.append("network_contract")
    services=config.get("services",{})
    expected=policy_services()
    if set(services)!=set(expected):return errors+["service_set"]
    for name,wanted in expected.items():
        actual=_normalize(services[name]);want=_normalize(_substitute(wanted))
        env=actual.get("environment",{})
        if set(env)!=set(want["environment"]):errors.append("environment_keys_"+name)
        for key,value in want["environment"].items():
            if key in SECRET_KEYS:
                if not isinstance(env.get(key),str) or not re.fullmatch(r"m1_[0-9a-f]{48}",env[key]):errors.append("local_material_"+name)
                else:want["environment"][key]=env[key]
        if actual!=want:errors.append("service_contract_"+name)
    # Require each shared local value to match between only its intended services.
    envs=[s.get("environment",{}) for s in services.values()]
    for keys in [{"POSTGRES_PASSWORD","PGPASSWORD","AUTODATA_POSTGRES_PASSWORD"},{"AWS_ACCESS_KEY_ID","AUTODATA_S3_ACCESS_KEY"},{"AWS_SECRET_ACCESS_KEY","AUTODATA_S3_SECRET_KEY"}]:
        if len({v for e in envs for k,v in e.items() if k in keys})!=1:errors.append("local_material_mismatch")
    return sorted(set(errors))


def image_volume_errors(metadata, service):
    explicit={v["target"] for v in service.get("volumes",[]) if v.get("type")=="bind"}
    for mount in service.get("tmpfs",[]):
        target,_,options=mount.partition(":")
        if re.search(r"(?:^|,)size=[1-9][0-9]*[mk](?:,|$)",options) and "noexec" in options.split(",") and "nosuid" in options.split(","):explicit.add(target)
    declared=set((metadata.get("Config",{}).get("Volumes") or {}).keys())
    return [] if declared<=explicit else ["unmasked_image_volume"]


def capacity_errors(*,docker_free,home_free,docker_inodes,home_inodes,growth_bytes):
    if not isinstance(growth_bytes,int) or isinstance(growth_bytes,bool) or growth_bytes<0:return ["growth_unknown"]
    errors=[]
    if docker_free <= (512+128+72)*1024**2+growth_bytes:errors.append("docker_reserve")
    if home_free <= (2048+4096+512+64)*1024**2:errors.append("home_reserve")
    if min(docker_inodes,home_inodes)<1000:errors.append("inode_reserve")
    return errors


def manifest_errors(manifest):
    errors=[]
    if set(manifest)!=set(HASH_FIELDS)|{"dependency_compatible"}:errors.append("manifest_shape")
    for field,length in HASH_FIELDS.items():
        if not isinstance(manifest.get(field),str) or re.fullmatch("[0-9a-f]{"+str(length)+"}",manifest[field]) is None:errors.append("manifest_"+field)
    if manifest.get("dependency_compatible") is not True:errors.append("dependency_compatibility")
    return errors


def archive_errors(archive, source, manifest):
    errors=[]
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=manifest["archive_sha256"]:return ["archive_hash"]
    with tarfile.open(archive,"r:") as tf:
        if tf.pax_headers.get("comment")!=manifest["source_sha"]:errors.append("archive_source")
        tracked=set()
        for member in tf:
            path=source/member.name
            if not path.is_relative_to(source) or ".." in Path(member.name).parts:return ["archive_path"]
            if member.isdir():continue
            tracked.add(member.name)
            if not member.isfile() or path.is_symlink() or not path.is_file():return ["source_file_type"]
            if hashlib.sha256(tf.extractfile(member).read()).digest()!=hashlib.sha256(path.read_bytes()).digest():return ["source_file_hash"]
        actual={str(p.relative_to(source)) for p in source.rglob("*") if p.is_file() or p.is_symlink()}
        if actual!=tracked:errors.append("source_file_set")
    return errors


def private_mode_errors(root_mode, file_modes):
    return [] if root_mode==0o700 and all(m==0o600 for m in file_modes) else ["private_mode"]


def fresh_data_errors(empty, marker, storage=None):
    if set(empty)!=set(DATA_DIRS):return ["data_directory_set"]
    if marker is None:return [] if all(empty.values()) else ["data_not_fresh"]
    return [] if marker.get("storage")==storage else ["data_identity"]


def ownership_errors(networks, containers, marker):
    if marker is None:return [] if not networks and not containers else ["preexisting_resources"]
    errors=[]
    if len(networks)!=1:return ["owned_network_missing"]
    net=networks[0]
    labels=net.get("Labels") or {}
    if (net.get("Id")!=marker.get("network_id") or net.get("Name")!=PROJECT+"_internal" or net.get("Internal") is not True or labels.get("com.docker.compose.project")!=PROJECT or labels.get("com.docker.compose.network")!="internal"):errors.append("network_owner")
    accepted=marker.get("containers",{})
    if {c.get("Id") for c in containers}!=set(accepted):errors.append("container_set")
    if set(net.get("Containers",{}))-set(accepted):errors.append("network_foreign_attachment")
    for c in containers:
        label=c.get("Config",{}).get("Labels") or {};name=label.get("com.docker.compose.service")
        if name not in IMAGES or accepted.get(c.get("Id"))!=name or label.get("com.docker.compose.project")!=PROJECT or c.get("Image")!=IMAGES.get(name):errors.append("container_owner")
        if c.get("Name")!="/"+PROJECT+"-"+str(name)+"-1":errors.append("container_name")
        nets=c.get("NetworkSettings",{}).get("Networks",{})
        if set(nets)!={PROJECT+"_internal"} or nets.get(PROJECT+"_internal",{}).get("NetworkID")!=marker.get("network_id"):errors.append("container_attachment")
        if c.get("HostConfig",{}).get("ReadonlyRootfs") is not True:errors.append("container_root_writable")
    return sorted(set(errors))


def runtime_resources():
    net_ids=_capture(["docker","network","ls","-q","--filter","name=^"+PROJECT+"_internal$"]).split()
    # Union catches both mismatched labels and same-name unlabelled resources.
    ids=set(_capture(["docker","ps","-aq","--filter","label=com.docker.compose.project="+PROJECT]).split())
    ids.update(_capture(["docker","ps","-aq","--filter","name="+PROJECT]).split())
    nets=json.loads(_capture(["docker","network","inspect",*net_ids])) if net_ids else []
    containers=json.loads(_capture(["docker","inspect",*sorted(ids)])) if ids else []
    return nets,containers


def _path_evidence(path):
    parts=[path,*path.parents]
    symlink=any(p.is_symlink() for p in parts)
    mounted=json.loads(_capture(["findmnt","-J","-T",str(path),"-o","SOURCE,FSTYPE"]))["filesystems"][0]
    return {"device":mounted["source"],"fstype":mounted["fstype"],"symlink":symlink}


def path_errors(path,probe=_path_evidence):
    if path!=ROOT and ROOT not in path.parents:return ["path_escape"]
    info=probe(path)
    if info!={"device":DEVICE,"fstype":"ext4","symlink":False}:return ["path_backing"]
    if path.resolve()!=path:return ["path_canonical"]
    return []


def _capture(command):
    # Capture stderr too: it can include interpolated private configuration.
    result=subprocess.run(command,capture_output=True,text=True,timeout=30,check=False)
    if result.returncode:raise RuntimeError("read_command_failed")
    return result.stdout


def safe_failure(error):
    return "admission_internal_error"


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose",type=Path,required=True)
    parser.add_argument("--env-file",type=Path,required=True)
    parser.add_argument("--manifest",type=Path,required=True)
    parser.add_argument("--state-receipt",type=Path,help="exact private accepted M1 resource/state receipt; omit only for fresh first start")
    parser.add_argument("--growth-bytes",type=int,required=True,help="measured upper allowance over bounded local window")
    args=parser.parse_args(argv)
    try:
        if args.env_file.parent!=ROOT/"private-config" or args.manifest.parent!=ROOT/"private-config":raise RuntimeError("private_paths")
        modes=[args.env_file.stat().st_mode&0o777,args.manifest.stat().st_mode&0o777]
        if private_mode_errors(ROOT.stat().st_mode&0o777,modes):raise RuntimeError("private_modes")
        if (ROOT/"private-config").stat().st_mode&0o777!=0o700:raise RuntimeError("private_directory_mode")
        config=json.loads(_capture(["docker","compose","--project-name",PROJECT,"--file",str(args.compose),"--env-file",str(args.env_file),"config","--format","json"]))
        errors=validate_config(config)
        manifest=json.loads(args.manifest.read_text());errors+=manifest_errors(manifest)
        marker=None
        if args.state_receipt:
            if args.state_receipt!=ROOT/"private-config/accepted-state.json" or args.state_receipt.stat().st_mode&0o777!=0o600:raise RuntimeError("state_receipt_path")
            marker=json.loads(args.state_receipt.read_text())
            if set(marker)!={"network_id","containers","storage","source_sha"} or marker["source_sha"]!=manifest["source_sha"]:errors.append("state_receipt_contract")
        storage={name:[(ROOT/name).stat().st_dev,(ROOT/name).stat().st_ino] for name in DATA_DIRS}
        empty={name:True if marker is not None else not any((ROOT/name).iterdir()) for name in DATA_DIRS}
        errors+=fresh_data_errors(empty,marker,storage)
        nets,containers=runtime_resources();errors+=ownership_errors(nets,containers,marker)
        for p in [ROOT,*[Path(v["source"]) for s in config["services"].values() for v in s.get("volumes",[])]]:errors+=path_errors(p)
        errors+=archive_errors(ROOT/"source.tar", ROOT/"source", manifest)
        actual_tree=_capture(["git","-C",str(Path(__file__).resolve().parents[2]),"show","-s","--format=%T",manifest["source_sha"]]).strip()
        if actual_tree!=manifest["source_tree"]:errors.append("source_tree")
        binary=ROOT/"bin/autodata-api"
        if hashlib.sha256(binary.read_bytes()).hexdigest()!=manifest["binary_sha256"]:errors.append("binary_hash")
        if hashlib.sha256(json.dumps(config,sort_keys=True,separators=(",",":")).encode()).hexdigest()!=manifest["config_sha256"]:errors.append("config_hash")
        for service,image in IMAGES.items():
            meta=json.loads(_capture(["docker","image","inspect",image]))[0]
            if meta["Id"]!=image or meta["Os"]!="linux" or meta["Architecture"]!="amd64":errors.append("cached_image")
            errors+=image_volume_errors(meta,config["services"][service])
        d=os.statvfs("/mnt/openfoam/docker");h=os.statvfs(ROOT)
        errors+=capacity_errors(docker_free=d.f_bavail*d.f_frsize,home_free=h.f_bavail*h.f_frsize,docker_inodes=d.f_favail,home_inodes=h.f_favail,growth_bytes=args.growth_bytes)
        print(json.dumps({"admitted":not errors,"errors":sorted(set(errors)),"service_count":len(config["services"]),"docker_free_bytes":d.f_bavail*d.f_frsize,"home_free_bytes":h.f_bavail*h.f_frsize},sort_keys=True))
        return bool(errors)
    except Exception as error:
        print(json.dumps({"admitted":False,"errors":[safe_failure(error)]}))
        return 1


if __name__=="__main__":sys.exit(main())
