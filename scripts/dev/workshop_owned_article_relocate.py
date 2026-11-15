"""Fixed historical evidence relocation; real mutation requires root review.

No runtime/data/cache paths are accepted from CLI or environment. Copy preserves
source; cleanup is a separate command requiring complete target re-verification.
"""
from __future__ import annotations
import argparse
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
sys.dont_write_bytecode=True

SOURCE=Path('/home/corp/autodata-workshop-owned-article-data-20261115/held-ebed-package')
PARENT=Path('/home/corp/autodata-evidence/local-staging-runtime-draft-20261115')
TARGET=PARENT/'held-ebed-package'
APPROVED=PARENT/'held-ebed-relocation-approved.json'
APPROVED_HASH='efdeac101b2e1c775a6361aa59ceef152e30a66b722aa5d2e2d2427d8a68ac54'
COPY_RECEIPT=PARENT/'held-ebed-copy-verified.json'
CLEANUP_RECEIPT=PARENT/'held-ebed-relocated.json'
DIR_FLAGS=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW
FILE_FLAGS=os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK
MAX_FILE=100*1024**2
MAX_TOTAL=200*1024**2


def open_dir(path):
    path=Path(path)
    if not path.is_absolute():raise ValueError('absolute_directory_required')
    fd=os.open('/',DIR_FLAGS)
    try:
        for part in path.parts[1:]:
            if part in ('','.','..'):raise ValueError('directory_component')
            new=os.open(part,DIR_FLAGS,dir_fd=fd);os.close(fd);fd=new
        return fd
    except Exception:os.close(fd);raise


def relative_dir(root,relative):
    fd=os.dup(root)
    try:
        for part in Path(relative).parts:
            if part in ('','.','..') or '/' in part:raise ValueError('relative_directory')
            new=os.open(part,DIR_FLAGS,dir_fd=fd);os.close(fd);fd=new
        return fd
    except Exception:os.close(fd);raise


def metadata(info):
    return {'device':info.st_dev,'inode':info.st_ino,'uid':info.st_uid,'mode':stat.S_IMODE(info.st_mode),'bytes':info.st_size,'links':info.st_nlink}


def file_hash(fd):
    before=os.fstat(fd)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_uid!=os.getuid() or before.st_size>MAX_FILE:raise ValueError('regular_owned_single_link_file')
    h=hashlib.sha256();size=0
    while chunk:=os.read(fd,1024*1024):
        size+=len(chunk)
        if size>MAX_FILE:raise ValueError('file_bound')
        h.update(chunk)
    after=os.fstat(fd)
    if metadata(before)!=metadata(after) or before.st_mtime_ns!=after.st_mtime_ns or before.st_ctime_ns!=after.st_ctime_ns or size!=after.st_size:raise ValueError('file_changed')
    return h.hexdigest()


def inventory(path):
    root=open_dir(path)
    try:
        info=os.fstat(root)
        if info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:raise ValueError('private_root')
        result={'root':metadata(info),'files':{},'directories':{}};total=0
        def walk(fd,prefix=''):
            nonlocal total
            for name in sorted(os.listdir(fd)):
                rel=prefix+name;observed=os.stat(name,dir_fd=fd,follow_symlinks=False)
                if observed.st_dev!=info.st_dev or observed.st_uid!=os.getuid():raise ValueError('foreign_device_or_owner')
                if stat.S_ISDIR(observed.st_mode):
                    child=os.open(name,DIR_FLAGS,dir_fd=fd)
                    try:
                        if metadata(os.fstat(child))!=metadata(observed):raise ValueError('directory_changed')
                        result['directories'][rel]={k:metadata(observed)[k] for k in ('device','inode','uid','mode')};walk(child,rel+'/')
                    finally:os.close(child)
                elif stat.S_ISREG(observed.st_mode):
                    child=os.open(name,FILE_FLAGS,dir_fd=fd)
                    try:
                        if metadata(os.fstat(child))!=metadata(observed):raise ValueError('file_changed')
                        result['files'][rel]={**metadata(observed),'sha256':file_hash(child)}
                    finally:os.close(child)
                    total+=observed.st_size
                else:raise ValueError('unsupported_entry')
                if len(result['files'])+len(result['directories'])>10000 or total>MAX_TOTAL:raise ValueError('tree_bound')
        walk(root);return result
    finally:os.close(root)


def content(value):
    return {'root_mode':value['root']['mode'],'files':{k:{f:v[f] for f in ('mode','bytes','sha256')} for k,v in value['files'].items()},'directories':{k:v['mode'] for k,v in value['directories'].items()}}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def rename_noreplace(source_fd,source,target_fd,target):
    libc=ctypes.CDLL(None,use_errno=True)
    function=libc.renameat2
    function.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint];function.restype=ctypes.c_int
    if function(source_fd,os.fsencode(source),target_fd,os.fsencode(target),1):
        code=ctypes.get_errno();raise OSError(code,'atomic_noreplace_failed')


def acquire_lock(parent):
    root=open_dir(parent)
    try:
        info=os.fstat(root)
        if info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:raise ValueError('private_parent')
        fd=os.open('held-ebed-relocation.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600,dir_fd=root)
    finally:os.close(root)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o600:raise ValueError('private_lock')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);return fd
    except Exception:os.close(fd);raise


def copy_verified(source,target,expected):
    source=Path(source);target=Path(target)
    if inventory(source)!=expected:raise ValueError('source_inventory')
    parent=open_dir(target.parent);root=open_dir(source);pending='.'+target.name+'.copying';destination=None
    try:
        for name in (target.name,pending):
            try:os.stat(name,dir_fd=parent,follow_symlinks=False)
            except FileNotFoundError:pass
            else:raise ValueError('occupied_target')
        if os.statvfs(target.parent).f_bavail*os.statvfs(target.parent).f_frsize<MAX_TOTAL+64*1024**2:raise ValueError('target_capacity')
        os.mkdir(pending,0o700,dir_fd=parent);destination=os.open(pending,DIR_FLAGS,dir_fd=parent)
        for rel in sorted(expected['directories'],key=lambda p:(p.count('/'),p)):
            p=Path(rel);fd=relative_dir(destination,p.parent)
            try:os.mkdir(p.name,0o700,dir_fd=fd)
            finally:os.close(fd)
        for rel,wanted in expected['files'].items():
            p=Path(rel);src_parent=relative_dir(root,p.parent);dst_parent=relative_dir(destination,p.parent);src=dst=None
            try:
                src=os.open(p.name,FILE_FLAGS,dir_fd=src_parent)
                if metadata(os.fstat(src))!={k:v for k,v in wanted.items() if k!='sha256'}:raise ValueError('source_file_identity')
                dst=os.open(p.name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=dst_parent);h=hashlib.sha256();size=0
                while chunk:=os.read(src,1024*1024):
                    size+=len(chunk)
                    if size>wanted['bytes']:raise ValueError('source_file_growth')
                    h.update(chunk);view=memoryview(chunk)
                    while view:
                        written=os.write(dst,view)
                        if written<=0:raise ValueError('copy_write')
                        view=view[written:]
                if size!=wanted['bytes'] or h.hexdigest()!=wanted['sha256']:raise ValueError('copy_hash')
                os.fchmod(dst,wanted['mode']);os.fsync(dst)
            finally:
                for fd in (src,dst,src_parent,dst_parent):
                    if fd is not None:os.close(fd)
        for rel in sorted(expected['directories'],key=lambda p:(p.count('/'),p),reverse=True):
            fd=relative_dir(destination,rel)
            try:os.fchmod(fd,expected['directories'][rel]['mode']);os.fsync(fd)
            finally:os.close(fd)
        os.fsync(destination)
        if inventory(source)!=expected or content(inventory(target.parent/pending))!=content(expected):raise ValueError('copy_recheck')
        rename_noreplace(parent,pending,parent,target.name);os.fsync(parent)
        actual=inventory(target)
        if content(actual)!=content(expected):raise ValueError('published_recheck')
        return {'source_preserved':True,'approved_inventory_sha256':fingerprint(expected),'target_root':actual['root'],'content_sha256':fingerprint(content(actual))}
    finally:
        for fd in (destination,root,parent):
            if fd is not None:os.close(fd)


def cleanup_verified(source,target,expected,receipt):
    source=Path(source);target=Path(target);actual=inventory(target)
    if receipt!={'source_preserved':True,'approved_inventory_sha256':fingerprint(expected),'target_root':actual['root'],'content_sha256':fingerprint(content(expected))} or content(actual)!=content(expected):raise ValueError('target_receipt')
    if inventory(source)!=expected:raise ValueError('cleanup_source_inventory')
    parent=open_dir(source.parent);quarantine='.'+source.name+'.relocated';root=None
    try:
        rename_noreplace(parent,source.name,parent,quarantine);os.fsync(parent)
        if inventory(source.parent/quarantine)!=expected:raise ValueError('quarantine_inventory')
        root=os.open(quarantine,DIR_FLAGS,dir_fd=parent)
        for rel,wanted in expected['files'].items():
            p=Path(rel);fd=relative_dir(root,p.parent);file=None
            try:
                file=os.open(p.name,FILE_FLAGS,dir_fd=fd)
                if metadata(os.fstat(file))!={k:v for k,v in wanted.items() if k!='sha256'} or file_hash(file)!=wanted['sha256']:raise ValueError('cleanup_file_identity')
                if metadata(os.stat(p.name,dir_fd=fd,follow_symlinks=False))!={k:v for k,v in wanted.items() if k!='sha256'}:raise ValueError('cleanup_replacement')
                os.unlink(p.name,dir_fd=fd);os.fsync(fd)
            finally:
                if file is not None:os.close(file)
                os.close(fd)
        for rel,wanted in sorted(expected['directories'].items(),key=lambda kv:(kv[0].count('/'),kv[0]),reverse=True):
            p=Path(rel);fd=relative_dir(root,p.parent);child=os.open(p.name,DIR_FLAGS,dir_fd=fd)
            try:
                if any(metadata(os.fstat(child))[k]!=v for k,v in wanted.items()) or os.listdir(child):raise ValueError('cleanup_directory_identity')
                os.rmdir(p.name,dir_fd=fd);os.fsync(fd)
            finally:os.close(child);os.close(fd)
        if os.listdir(root):raise ValueError('cleanup_extra_entry')
        os.rmdir(quarantine,dir_fd=parent);os.fsync(parent)
        if content(inventory(target))!=content(expected):raise ValueError('final_target_recheck')
    finally:
        if root is not None:os.close(root)
        os.close(parent)


def private_json(path):
    fd=os.open(path,FILE_FLAGS)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o600 or info.st_nlink!=1 or info.st_size>1024**2:raise ValueError('private_json')
        data=os.read(fd,1024**2+1);return data,json.loads(data)
    finally:os.close(fd)


def write_receipt(path,value):
    parent=open_dir(path.parent)
    try:
        if stat.S_IMODE(os.fstat(parent).st_mode)!=0o700:raise ValueError('receipt_parent')
        fd=os.open(path.name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
        with os.fdopen(fd,'w') as out:json.dump(value,out,sort_keys=True);out.write('\n');out.flush();os.fsync(out.fileno())
        os.fsync(parent)
    finally:os.close(parent)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('plan','copy','cleanup'));args=parser.parse_args();lock=None
    try:
        data,expected=private_json(APPROVED)
        if hashlib.sha256(data).hexdigest()!=APPROVED_HASH or expected['root']['device']!=66315 or expected['root']['inode']!=3038805:raise ValueError('approved_pin')
        parent=open_dir(PARENT)
        try:
            info=os.fstat(parent)
            if info.st_dev!=1792 or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:raise ValueError('target_parent_pin')
        finally:os.close(parent)
        backing=os.statvfs('/mnt/win_p4')
        if args.action=='copy' and backing.f_bavail*backing.f_frsize<MAX_TOTAL+64*1024**2:raise ValueError('backing_capacity')
        if args.action=='plan':
            if inventory(SOURCE)!=expected:raise ValueError('plan_source_inventory')
        else:
            lock=acquire_lock(PARENT)
            if args.action=='copy':write_receipt(COPY_RECEIPT,copy_verified(SOURCE,TARGET,expected))
            else:
                _,receipt=private_json(COPY_RECEIPT);cleanup_verified(SOURCE,TARGET,expected,receipt)
                write_receipt(CLEANUP_RECEIPT,{'source':str(SOURCE),'target':str(TARGET),'approved_file_sha256':APPROVED_HASH,'content_sha256':fingerprint(content(expected)),'source_removed':True,'target_verified':True})
        h=os.statvfs(SOURCE.parent);e=os.statvfs(PARENT);d=os.statvfs('/mnt/openfoam/docker')
        print(json.dumps({'ok':True,'action':args.action,'source_exists':SOURCE.exists(),'target_exists':TARGET.exists(),'files':len(expected['files']),'home_free':h.f_bavail*h.f_frsize,'evidence_free':e.f_bavail*e.f_frsize,'backing_free':backing.f_bavail*backing.f_frsize,'docker_free':d.f_bavail*d.f_frsize,'home_full_floor':7046430720,'home_build_abort_floor':7180648448,'docker_floor':813694976},sort_keys=True));return 0
    except Exception:
        print(json.dumps({'ok':False,'action':args.action,'error':'relocation_failed_preserve_for_review'}));return 1
    finally:
        if lock is not None:os.close(lock)
if __name__=='__main__':raise SystemExit(main())
