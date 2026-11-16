"""Read-only runtime identity functions; no executable dispatch entrypoint."""
import hashlib,itertools,json,pathlib,os
CHILD_ENV={"PATH":"/usr/bin:/bin","LANG":"C.UTF-8","LC_ALL":"C.UTF-8"}
ENV=pathlib.Path("/etc/autodata/preview/api-public-preview.env")
OVERRIDE=pathlib.Path("/etc/systemd/system/autodata-api.service.d/99-public-preview.conf")
DEPENDENCY=pathlib.Path("/etc/systemd/system/autodata-api.service.d/10-docker-dependency.conf")
def sha(data):
    return hashlib.sha256(data).hexdigest()

def require(condition, code):
    if not condition:
        raise RuntimeError(code)

def metadata(path):
    require(not path.is_symlink(),'unexpected_symlink')
    stat = path.stat()
    return {'sha256':sha(path.read_bytes()),'uid':stat.st_uid,'gid':stat.st_gid,'mode':oct(stat.st_mode & 0o777)}

def private_identity(x):
    return {'id':x['Id'],'image':x['Image'],'name':x['Name'],'mounts':x['Mounts'],
            'restart':x['HostConfig']['RestartPolicy'],'readonly_root':x['HostConfig']['ReadonlyRootfs'],
            'network':x['HostConfig']['NetworkMode'],'running':x['State']['Running'],
            'started_at':x['State']['StartedAt'],'pid':x['State']['Pid'],'restart_count':x['RestartCount'],
            'env_sha256':sha(json.dumps(x['Config']['Env'],separators=(',',':')).encode())}

def source_guard(root):
    root=pathlib.Path(root)
    require(not root.is_symlink() and root.is_dir(),'source_symlink_or_missing')
    paths=list(itertools.islice(root.rglob('*'),10000))
    require(len(paths)<10000,'source_inventory_limit')
    entries=[]
    for path in [root,*sorted(paths)]:
        require(len(entries)<10000,'source_inventory_limit')
        require(not path.is_symlink(),'source_symlink')
        st=path.stat()
        require(path.is_file() or path.is_dir(),'source_special_file')
        entries.append([str(path.relative_to(root)),st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns,st.st_mode,
                        sha(path.read_bytes()) if path.is_file() else None])
    return sha(json.dumps(entries,separators=(',',':')).encode())

def running_binary_matches(pid, executable, expected):
    if not isinstance(pid,str) or not pid.isdecimal() or int(pid)<=0:return False
    try:
        proc=pathlib.Path('/proc')/pid/'exe'; installed=pathlib.Path(executable)
        if os.readlink(proc)!=executable or metadata(installed)!=expected:return False
        actual=proc.stat();wanted=installed.stat()
        return (actual.st_dev,actual.st_ino)==(wanted.st_dev,wanted.st_ino) and sha(proc.read_bytes())==expected['sha256']
    except (OSError,ValueError):return False
