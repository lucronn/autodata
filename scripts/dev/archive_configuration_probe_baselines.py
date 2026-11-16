#!/usr/bin/env python3
"""Exact historical v6 baseline archive. Copy and cleanup require independent review.

CLI paths/identities are fixed. Tests inject owned temporary fixtures into Archive.
No SQL, runtime, provider, subprocess, symlink replacement or automatic retry.
"""
import argparse
from contextlib import contextmanager
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat

NAMES=frozenset(('baseline-before.json','baseline-after.json'))
MAP='baseline-offload-map-v1.json'
ATTEMPT='baseline-offload-cleanup-attempt-v1.json'
DONE='baseline-offload-cleanup-v1.json'
RECEIPT='archive-receipt.json'
MANUAL='manual-classification-v6.json'
MAX_BYTES=128*1024*1024
ROOT='/home/corp/.local/state/autodata/configuration-budget-runtime-20261115/probe-17295-v6-20261115'
CONFIG={'source_root':ROOT,'destination':'/home/corp/autodata-evidence/configuration-budget-v6-baselines-20261115',
 'source_device':66315,'destination_device':1792,'uid':1000,'gid':1000,
 'manual_sha256':'1edb69ae5c56ea843d1831ddd7f2aaa8907557d76caa671bf0b2e174e1b829f0',
 'files':{name:{'bytes':91366487,'sha256':digest,'device':66315,'inode':inode,'uid':1000,'gid':1000,'mode':0o600,'links':1}
          for name,digest,inode in [('baseline-before.json','b27882c6050f526a74a747642a4743436aa39d777667779db4e8beb81871d95b',3543699),
                                    ('baseline-after.json','1bd88c300a6435ded790920b4468b13eb4781e3a47e84979ad3484bd58647d16',3543712)]}}

class Refused(Exception):pass

def require(condition):
    if not condition:raise Refused('archive_admission_refused')

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()+b'\n'

def digest(data):return hashlib.sha256(data).hexdigest()

def sync_dir(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)

def publish(source,destination):
    """Linux atomic no-replace directory publication, never replace a raced target."""
    libc=ctypes.CDLL(None,use_errno=True)
    rename=getattr(libc,'renameat2',None)
    require(rename is not None)
    rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
    rename.restype=ctypes.c_int
    if rename(-100,os.fsencode(source),-100,os.fsencode(destination),1)!=0:
        raise OSError(ctypes.get_errno(),'atomic_archive_publication_refused')

def metadata(s):
    return {'bytes':s.st_size,'device':s.st_dev,'inode':s.st_ino,'uid':s.st_uid,'gid':s.st_gid,
            'mode':stat.S_IMODE(s.st_mode),'links':s.st_nlink,'mtime_ns':s.st_mtime_ns,'ctime_ns':s.st_ctime_ns,
            'allocated_bytes':s.st_blocks*512}

def inspect_file(path,expected=None,limit=MAX_BYTES):
    require(path.resolve()==path)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as handle:
        s=os.fstat(handle.fileno());require(stat.S_ISREG(s.st_mode) and 0<s.st_size<=limit and s.st_nlink==1)
        before=metadata(s)
        if expected:
            for key,value in expected.items():
                if key!='sha256':require(before.get(key)==value)
        h=hashlib.sha256();count=0
        for chunk in iter(lambda:handle.read(1048576),b''):
            count+=len(chunk);require(count<=limit);h.update(chunk)
        require(metadata(os.fstat(handle.fileno()))==before and count==s.st_size)
    before['sha256']=h.hexdigest()
    if expected:require(before['sha256']==expected['sha256'])
    return before

def read_receipt(path,expected_hash):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as handle:data=handle.read(65537)
    require(len(data)<=65536 and digest(data)==expected_hash)
    return data


def save(path,value):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as handle:
        handle.write(canonical(value));handle.flush();os.fsync(handle.fileno())
    sync_dir(path.parent)

def unlink_checked(path,proof):
    s=path.lstat();require(stat.S_ISREG(s.st_mode) and metadata(s)=={k:v for k,v in proof.items() if k!='sha256'})
    path.unlink()

class Archive:
    def __init__(self,config):
        self.cfg=config;self.src=Path(config['source_root']);self.dst=Path(config['destination'])
        self.stage=self.dst.with_name('.'+self.dst.name+'.partial')

    def admit(self):
        c=self.cfg;require(set(c['files'])==NAMES and os.geteuid()==c['uid'])
        for path,device,private in ((self.src,c['source_device'],True),(self.dst.parent,c['destination_device'],False)):
            require(path.resolve()==path and path.is_dir())
            s=path.stat();require(s.st_dev==device and s.st_uid==c['uid'] and s.st_gid==c['gid'])
            if private:require(stat.S_IMODE(s.st_mode)==0o700)
        require(self.src!=self.dst and self.src not in self.dst.parents and self.dst not in self.src.parents)
        inspect_file(self.src/MANUAL,{'sha256':c['manual_sha256'],'device':c['source_device'],'uid':c['uid'],'gid':c['gid'],'mode':0o600,'links':1},65536)

    @contextmanager
    def locked(self):
        self.admit()
        fd=os.open(self.src/'.baseline-archive.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        try:
            s=os.fstat(fd);require(stat.S_ISREG(s.st_mode) and stat.S_IMODE(s.st_mode)==0o600 and s.st_uid==self.cfg['uid'] and s.st_gid==self.cfg['gid'] and s.st_dev==self.cfg['source_device'] and s.st_nlink==1)
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);yield
        except (OSError,ValueError,TypeError,KeyError):raise Refused('archive_operation_inconclusive') from None
        finally:os.close(fd)

    def sources(self):return {name:inspect_file(self.src/name,self.cfg['files'][name]) for name in sorted(NAMES)}

    def plan(self):
        try:
            self.admit();proofs=self.sources()
            return {'files':2,'allocated_bytes':sum(p['allocated_bytes'] for p in proofs.values()),'source_files_unchanged':True,'mutation':False}
        except (OSError,ValueError,TypeError,KeyError):raise Refused('archive_plan_refused') from None

    def copy(self):
        with self.locked():
            proofs=self.sources()
            require(not os.path.lexists(self.dst) and not os.path.lexists(self.stage) and not os.path.lexists(self.src/MAP))
            available=os.statvfs(self.dst.parent);require(available.f_bavail*available.f_frsize>sum(p['bytes'] for p in proofs.values())+1048576)
            self.stage.mkdir(mode=0o700);sync_dir(self.stage.parent)
            targets={}
            for name in sorted(NAMES):
                source=self.src/name;target=self.stage/name
                fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW)
                with os.fdopen(fd,'rb') as inp:
                    require(metadata(os.fstat(inp.fileno()))=={k:v for k,v in proofs[name].items() if k!='sha256'})
                    outfd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                    with os.fdopen(outfd,'wb') as out:
                        h=hashlib.sha256();count=0
                        for chunk in iter(lambda:inp.read(1048576),b''):
                            count+=len(chunk);require(count<=proofs[name]['bytes']);out.write(chunk);h.update(chunk)
                        require(count==proofs[name]['bytes'] and h.hexdigest()==proofs[name]['sha256'])
                        require(metadata(os.fstat(inp.fileno()))=={k:v for k,v in proofs[name].items() if k!='sha256'})
                        out.flush();os.fsync(out.fileno())
                targets[name]=inspect_file(target,{'bytes':proofs[name]['bytes'],'sha256':proofs[name]['sha256'],'device':self.cfg['destination_device'],'uid':self.cfg['uid'],'gid':self.cfg['gid'],'mode':0o600,'links':1})
            receipt={'version':1,'source_root':str(self.src),'destination':str(self.dst),'source_files':proofs,'archive_files':targets,
                     'manual_classification_sha256':self.cfg['manual_sha256'],'scope':'exact_two_historical_baselines','serving_rollback_authority':False}
            save(self.stage/RECEIPT,receipt);sync_dir(self.stage);publish(self.stage,self.dst);sync_dir(self.dst.parent)
            mapping={'archive_receipt_sha256':digest(canonical(receipt)),'receipt':receipt,'originals_removed':False}
            save(self.src/MAP,mapping)
            return {'mapping_path':str(self.src/MAP),'mapping_sha256':digest(canonical(mapping)),'originals_removed':False}

    def cleanup(self,mapping_hash):
        with self.locked():
            require(isinstance(mapping_hash,str) and re.fullmatch('[0-9a-f]{64}',mapping_hash))
            require(not os.path.lexists(self.src/ATTEMPT) and not os.path.lexists(self.src/DONE))
            expected={'sha256':mapping_hash,'device':self.cfg['source_device'],'uid':self.cfg['uid'],'gid':self.cfg['gid'],'mode':0o600,'links':1}
            inspect_file(self.src/MAP,expected,65536)
            mapping=json.loads(read_receipt(self.src/MAP,mapping_hash));receipt=mapping['receipt']
            require(mapping['originals_removed'] is False and receipt['source_root']==str(self.src) and receipt['destination']==str(self.dst))
            require(receipt['manual_classification_sha256']==self.cfg['manual_sha256'] and set(receipt['archive_files'])==NAMES)
            require(self.dst.resolve()==self.dst and self.dst.is_dir() and stat.S_IMODE(self.dst.stat().st_mode)==0o700)
            require(self.dst.stat().st_dev==self.cfg['destination_device'] and self.dst.stat().st_uid==self.cfg['uid'])
            inspect_file(self.dst/RECEIPT,{'sha256':mapping['archive_receipt_sha256'],'device':self.cfg['destination_device'],'uid':self.cfg['uid'],'gid':self.cfg['gid'],'mode':0o600,'links':1},65536)
            require(read_receipt(self.dst/RECEIPT,mapping['archive_receipt_sha256'])==canonical(receipt))
            proofs=self.sources()
            for name in NAMES:
                require(proofs[name]==receipt['source_files'][name]);inspect_file(self.dst/name,receipt['archive_files'][name])
            save(self.src/ATTEMPT,{'mapping_sha256':mapping_hash,'archive_verified':True,'files':sorted(NAMES)})
            for name in sorted(NAMES):
                unlink_checked(self.src/name,proofs[name]);sync_dir(self.src)
            save(self.src/DONE,{'mapping_sha256':mapping_hash,'removed_files':sorted(NAMES),'reclaimed_allocated_bytes':sum(p['allocated_bytes'] for p in proofs.values()),'manual_receipt_preserved':True})
            return {'originals_removed':True,'files':2,'reclaimed_allocated_bytes':sum(p['allocated_bytes'] for p in proofs.values())}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('plan','copy','cleanup'))
    parser.add_argument('--reviewed-helper-sha256');parser.add_argument('--mapping-sha256')
    args=parser.parse_args()
    try:
        if args.action!='plan':require(args.reviewed_helper_sha256==digest(Path(__file__).read_bytes()))
        archive=Archive(CONFIG)
        result=archive.plan() if args.action=='plan' else archive.copy() if args.action=='copy' else archive.cleanup(args.mapping_sha256)
        print(json.dumps(result))
    except (Refused,OSError,ValueError,TypeError,KeyError):
        print(json.dumps({'status':'INCONCLUSIVE','automatic_retry':False,'scope':'historical_baseline_archive'}));return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
