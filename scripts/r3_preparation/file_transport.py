"""One owned descriptor-I/O worker with bounded local IPC.

The parent can stop waiting for an operation; it cannot undo an issued kernel
write or force an uninterruptible task to exit. Unconfirmed retirement requires
owner containment and quarantine. No deletion, repair or retry is performed.
"""
import errno
import hashlib
import os
import resource
import selectors
import signal
import socket
import stat
import struct
import threading
import time
from . import policy as p
from . import real_admission as a

_HEADER=struct.Struct('!BBQI')
_CHUNK=65536
_SECOND=10**9
_POLL=.05
_INVARIANT=('dev','inode','uid','gid','mode','nlink')


class TransportFault(Exception):
    def __init__(self,code='port_failure'):
        self.code=code if code in ('cancel','deadline','cap','storage','integrity','port_failure') else 'port_failure'
        super().__init__(self.code)


def _check(deadline,cancel):
    if cancel.is_set():raise TransportFault('cancel')
    if time.monotonic_ns()>=deadline:raise TransportFault('deadline')


def _io(sock,data,size,deadline,cancel):
    result=bytearray();sent=0
    with selectors.DefaultSelector() as selector:
        selector.register(sock,selectors.EVENT_WRITE if data is not None else selectors.EVENT_READ)
        while sent<size:
            _check(deadline,cancel)
            try:
                if data is None:
                    piece=sock.recv(min(_CHUNK,size-sent))
                    if not piece:raise TransportFault()
                    result.extend(piece);sent+=len(piece)
                else:
                    n=sock.send(memoryview(data)[sent:sent+_CHUNK])
                    if n<=0:raise TransportFault()
                    sent+=n
            except (BlockingIOError,InterruptedError):
                selector.select(min(_POLL,max(0,(deadline-time.monotonic_ns())/_SECOND)))
            except OSError:raise TransportFault() from None
    return bytes(result)


def _send(sock,kind,sequence,payload,deadline,cancel):
    if type(payload) is not bytes or len(payload)>_CHUNK:raise TransportFault('cap')
    _io(sock,_HEADER.pack(1,kind,sequence,len(payload)),_HEADER.size,deadline,cancel)
    _io(sock,payload,len(payload),deadline,cancel)


def _receive(sock,kind,sequence,deadline,cancel):
    header=_io(sock,None,_HEADER.size,deadline,cancel)
    version,actual_kind,actual_sequence,length=_HEADER.unpack(header)
    if version!=1 or actual_kind!=kind or actual_sequence!=sequence:raise TransportFault('integrity')
    if length>_CHUNK:raise TransportFault('cap')
    return _io(sock,None,length,deadline,cancel)


def _identity(st):
    return a.FileIdentity(st.st_dev,st.st_ino,st.st_uid,st.st_gid,st.st_mode,st.st_size,
                          st.st_mtime_ns,st.st_ctime_ns,st.st_nlink)


def _equal(actual,expected,*,directory=False):
    fields=_INVARIANT if directory else tuple(a.FileIdentity.__dataclass_fields__)
    return all(getattr(actual,k)==getattr(expected,k) for k in fields)


class _State:
    def __init__(self,anchors,recipes,root):
        self.anchors={v.reference:v for v in anchors};self.recipes={v.id:v for v in recipes}
        self.root=self.anchors[root];self.metadata=0;self.inputs=0;self.input_bytes=0
        self.output_bytes=0;self.outputs={};self.active=None;self.active_name=None
        self.active_bytes=0;self.active_digest=None;self.active_identity=None

    def charge(self,n=1):
        self.metadata+=n
        if self.metadata>40000:raise TransportFault('cap')

    def directory(self,fd,expected):
        self.charge();actual=_identity(os.fstat(fd))
        mutable_root=(actual.dev,actual.inode)==(self.root.identity.dev,self.root.identity.inode)
        if not stat.S_ISDIR(actual.mode) or actual.mode&0o022 or not _equal(actual,expected,directory=mutable_root):
            raise TransportFault('integrity')
        return actual

    def parent(self,recipe):
        anchor=self.anchors[recipe.anchor];fd=os.dup(anchor.fd)
        try:
            self.directory(fd,anchor.identity)
            for index,name in enumerate(recipe.components[:-1]):
                nextfd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
                os.close(fd);fd=nextfd;self.directory(fd,recipe.parents[index+1])
            return fd
        except BaseException:
            os.close(fd);raise

    def space(self):
        self.directory(self.root.fd,self.root.identity)
        v=os.fstatvfs(self.root.fd);free=v.f_bavail*v.f_frsize
        if free<1024**3:raise TransportFault('storage')
        return {'available_bytes':free}

    def inventory(self,expected):
        self.directory(self.root.fd,self.root.identity)
        # Only the preparation root is enumerated. Stop at entry18; never sort an
        # unbounded list, recurse, or inspect unrelated directories.
        names=[]
        with os.scandir(self.root.fd) as entries:
            for entry in entries:
                self.charge()
                if entry.name in ('home','artifacts','minio'):
                    anchor=self.anchors.get(entry.name)
                    if anchor is None or not _equal(_identity(entry.stat(follow_symlinks=False)),anchor.identity,directory=True):raise TransportFault('integrity')
                    self.directory(anchor.fd,anchor.identity)
                    continue
                if len(names)>=17 or entry.name not in p.OUTPUT_NAMES:raise TransportFault('integrity')
                names.append(entry.name)
        if set(names)!=set(expected) or len(names)!=len(expected):raise TransportFault('integrity')
        return {'count':len(names)}


def _observe(state,recipe):
    parent=state.parent(recipe)
    try:
        name=recipe.components[-1];state.charge()
        if recipe.kind=='absence':
            try:os.stat(name,dir_fd=parent,follow_symlinks=False)
            except FileNotFoundError:return {'absent':True}
            raise TransportFault('integrity')
        before=_identity(os.stat(name,dir_fd=parent,follow_symlinks=False))
        if not _equal(before,recipe.identity):raise TransportFault('integrity')
        if recipe.kind=='socket':
            if not stat.S_ISSOCK(before.mode):raise TransportFault('integrity')
            return {'socket_metadata':True}
        if not stat.S_ISREG(before.mode) or before.mode&0o022 or before.nlink!=1:raise TransportFault('integrity')
        # O_NONBLOCK prevents a swapped FIFO from blocking before fstat rejects it.
        fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=parent)
        try:
            opened=_identity(os.fstat(fd));state.charge()
            if not _equal(opened,before):raise TransportFault('integrity')
            state.inputs+=1
            if state.inputs>20000 or opened.size>64*1024**2:raise TransportFault('cap')
            total=0;digest=hashlib.sha256();literal_offset=0
            while True:
                chunk=os.read(fd,_CHUNK)
                if not chunk:break
                if total+len(chunk)>64*1024**2 or state.input_bytes+len(chunk)>1024**3:raise TransportFault('cap')
                total+=len(chunk);state.input_bytes+=len(chunk);digest.update(chunk)
                if recipe.literal is not None:
                    if chunk!=recipe.literal[literal_offset:literal_offset+len(chunk)]:raise TransportFault('integrity')
                    literal_offset+=len(chunk)
            state.charge(2)
            if total!=opened.size or not _equal(_identity(os.fstat(fd)),opened) or not _equal(_identity(os.stat(name,dir_fd=parent,follow_symlinks=False)),opened):raise TransportFault('integrity')
            if recipe.literal is not None and literal_offset!=len(recipe.literal):raise TransportFault('integrity')
            if digest.hexdigest()!=recipe.sha256:raise TransportFault('integrity')
            # Re-resolve each admitted parent from its anchor after hashing.
            again=state.parent(recipe)
            try:
                if not _equal(_identity(os.fstat(again)),_identity(os.fstat(parent))):raise TransportFault('integrity')
            finally:os.close(again)
            return {'sha256':digest.hexdigest(),'size':total,'complete':True}
        finally:os.close(fd)
    finally:os.close(parent)


def _output_start(state,name):
    if name not in p.OUTPUT_NAMES[2:-1] or state.active is not None or name in state.outputs:
        raise TransportFault('integrity')
    state.space();state.directory(state.root.fd,state.root.identity)
    fd=os.open(name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=state.root.fd)
    st=_identity(os.fstat(fd));state.charge()
    if not stat.S_ISREG(st.mode) or st.uid!=state.root.identity.uid or st.gid!=state.root.identity.gid or st.dev!=state.root.identity.dev or st.mode&0o777!=0o600 or st.nlink!=1:
        os.close(fd);raise TransportFault('integrity')
    state.active=fd;state.active_name=name;state.active_bytes=0;state.active_digest=hashlib.sha256();state.active_identity=st
    return {'started':True}


def _output_chunk(state,raw):
    if state.active is None:raise TransportFault('integrity')
    if state.active_bytes+len(raw)>16*1024**2 or state.output_bytes+len(raw)>128*1024**2:raise TransportFault('cap')
    state.space();offset=0
    # Interrupted and partial writes resume the same owned descriptor, not a new
    # operation, pathname or allowance. Parent time continues to run.
    while offset<len(raw):
        try:n=os.write(state.active,raw[offset:])
        except InterruptedError:continue
        if n<=0:raise TransportFault()
        offset+=n
    state.active_bytes+=len(raw);state.output_bytes+=len(raw);state.active_digest.update(raw)
    return {'written':len(raw)}


def _verify_fd(state,fd,expected,digest,size):
    before=_identity(os.fstat(fd));state.charge()
    if not _equal(before,expected,directory=True) or not stat.S_ISREG(before.mode) or before.size!=size:raise TransportFault('integrity')
    os.lseek(fd,0,os.SEEK_SET);h=hashlib.sha256();count=0
    while True:
        chunk=os.read(fd,_CHUNK)
        if not chunk:break
        if count+len(chunk)>16*1024**2:raise TransportFault('cap')
        count+=len(chunk);h.update(chunk)
    state.charge()
    if count!=size or h.hexdigest()!=digest or not _equal(_identity(os.fstat(fd)),before):raise TransportFault('integrity')
    return before


def _output_finish(state):
    if state.active is None:raise TransportFault('integrity')
    fd=state.active
    try:
        os.fsync(fd);digest=state.active_digest.hexdigest();size=state.active_bytes
        final=_verify_fd(state,fd,state.active_identity,digest,size)
        state.charge()
        if not _equal(_identity(os.stat(state.active_name,dir_fd=state.root.fd,follow_symlinks=False)),final):raise TransportFault('integrity')
        state.outputs[state.active_name]=(final,digest,size)
        return {'sha256':digest,'size':size,'complete':True}
    finally:os.close(fd);state.active=None


def _output_verify(state,name):
    if name not in state.outputs:raise TransportFault('integrity')
    expected,digest,size=state.outputs[name]
    state.directory(state.root.fd,state.root.identity)
    fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=state.root.fd)
    try:
        final=_verify_fd(state,fd,expected,digest,size)
        if not _equal(final,expected):raise TransportFault('integrity')
        state.charge()
        if not _equal(_identity(os.stat(name,dir_fd=state.root.fd,follow_symlinks=False)),expected):raise TransportFault('integrity')
        return {'sha256':digest,'size':size,'complete':True}
    finally:os.close(fd)


def _worker(sock,anchors,recipes,root,outer):
    os.setsid()
    null=os.open('/dev/null',os.O_RDWR|os.O_CLOEXEC)
    for fd in (0,1,2):os.dup2(null,fd)
    keep={0,1,2,sock.fileno(),*(v.fd for v in anchors)}
    maximum=resource.getrlimit(resource.RLIMIT_NOFILE)[1]
    if maximum==resource.RLIM_INFINITY:raise TransportFault()
    start=0
    for fd in sorted(keep):
        if fd>start:os.closerange(start,fd)
        start=fd+1
    os.closerange(start,maximum)
    state=_State(anchors,recipes,root);cancel=threading.Event()
    for anchor in anchors:
        state.directory(anchor.fd,anchor.identity)
        if not _equal(_identity(os.fstat(anchor.fd)),anchor.identity):raise TransportFault('integrity')
    _send(sock,2,0,b'{"ready":true}',min(outer,time.monotonic_ns()+5*_SECOND),cancel)
    seq=1
    try:
        while True:
            raw=_receive(sock,1,seq,outer,cancel)
            try:
                request=a._parse(raw)
                if type(request) is not dict or set(request)!={'op','id'}:raise TransportFault('integrity')
                op,reference=request['op'],request['id']
                if op in ('observe_regular','observe_absence','observe_socket_metadata','revalidate'):
                    if reference not in state.recipes:raise TransportFault('integrity')
                    recipe=state.recipes[reference]
                    required={'regular':'observe_regular','absence':'observe_absence','socket':'observe_socket_metadata'}[recipe.kind]
                    if op not in (required,'revalidate'):raise TransportFault('integrity')
                    result=_observe(state,recipe)
                elif op=='space' and reference=='root':result=state.space()
                elif op=='inventory_outputs' and type(reference) is list and len(reference)<=17 and all(type(x) is str and x in p.OUTPUT_NAMES for x in reference):result=state.inventory(reference)
                elif op=='create_output':result=_output_start(state,reference)
                elif op=='verify_output':result=_output_verify(state,reference)
                elif op=='finish_output' and reference==state.active_name:result=_output_finish(state)
                else:raise TransportFault('integrity')
                _send(sock,2,seq,a.serialize({'ok':result}),outer,cancel);seq+=1
                if op=='create_output':
                    while True:
                        chunk=_receive(sock,3,seq,outer,cancel)
                        if not chunk:break
                        result=_output_chunk(state,chunk)
                        _send(sock,2,seq,a.serialize({'ok':result}),outer,cancel);seq+=1
                    _send(sock,2,seq,b'{"ok":{"ended":true}}',outer,cancel);seq+=1
            except (OSError,TransportFault,a._Rejected,MemoryError,KeyError,TypeError,ValueError) as error:
                code=error.code if type(error) is TransportFault else 'storage' if isinstance(error,OSError) and error.errno in (errno.ENOSPC,errno.EDQUOT) else 'integrity'
                _send(sock,2,seq,a.serialize({'fault':code}),outer,cancel)
                return
    finally:
        if state.active is not None:os.close(state.active)


class FileWorker:
    """Internal capability constructed only after actual admission by the adapter."""
    def __init__(self,anchors,recipes,root_reference,outer_deadline_ns,cancel):
        self._pid=None;self._session=False;self._socket=None;self._sequence=1
        self._closed=False;self._cleanup=None;self._fault=None;self.quarantine_required=False
        self.outer=outer_deadline_ns;self.cancel=cancel;self._file_ns=0;self._output_ns=0
        self._json_ns=0;self.limits=p.Limits();self._operation_deadline=outer_deadline_ns
        if (type(anchors) is not tuple or not anchors or any(type(v) is not a.Anchor or type(v.fd) is not int or v.fd<3 for v in anchors)
            or len({v.fd for v in anchors})!=len(anchors) or root_reference not in {v.reference for v in anchors}
            or type(recipes) is not tuple or any(type(v) is not a.FileRecipe for v in recipes)
            or type(outer_deadline_ns) is not int or threading.active_count()!=1
            or signal.getsignal(signal.SIGCHLD)!=signal.SIG_DFL
            or not all(hasattr(os,n) for n in ('fork','O_NOFOLLOW','O_CLOEXEC','WNOWAIT','waitid'))):raise TransportFault('integrity')
        _check(self.outer,cancel)
        parent,child=socket.socketpair();parent.setblocking(False);child.setblocking(False)
        start=time.monotonic_ns();deadline=min(self.outer,start+5*_SECOND)
        try:
            pid=os.fork()
            if pid==0:
                parent.close()
                try:_worker(child,anchors,recipes,root_reference,self.outer)
                except BaseException:pass
                finally:os._exit(0)
            self._pid=pid;child.close();self._socket=parent
            ready=_receive(parent,2,0,deadline,cancel)
            if ready!=b'{"ready":true}' or os.getpgid(pid)!=pid:raise TransportFault('integrity')
            self._session=True
        except BaseException:
            child.close();parent.close();self.close();raise TransportFault('port_failure') from None
        finally:self._file_ns+=time.monotonic_ns()-start

    @property
    def ipc_closed(self):return self._socket is None

    def check_json(self):
        _check(self._operation_deadline,self.cancel)
        if self._json_ns>60*_SECOND:raise TransportFault('cap')

    def _exchange(self,op,reference,*,output=False):
        if self._closed or self._fault:raise TransportFault(self._fault or 'port_failure')
        start=time.monotonic_ns();ledger=self._output_ns if output else self._file_ns
        total=(60 if output else 300)*_SECOND
        deadline=min(self.outer,start+5*_SECOND,start+max(0,total-ledger));self._operation_deadline=deadline
        try:
            _check(deadline,self.cancel)
            _send(self._socket,1,self._sequence,a.serialize({'op':op,'id':reference}),deadline,self.cancel)
            raw=_receive(self._socket,2,self._sequence,deadline,self.cancel);self._sequence+=1
            result=a._parse(raw)
            if type(result) is not dict or len(result)!=1:raise TransportFault('integrity')
            if 'fault' in result:raise TransportFault(result['fault'])
            if set(result)!={'ok'} or type(result['ok']) is not dict:raise TransportFault('integrity')
            return result['ok']
        except BaseException as error:
            self._fault=error.code if type(error) is TransportFault else 'port_failure';self.cancel.set();self.close()
            raise TransportFault(self._fault) from None
        finally:
            elapsed=time.monotonic_ns()-start
            if output:self._output_ns+=elapsed
            else:self._file_ns+=elapsed

    def observe(self,reference):return self._exchange('revalidate',reference)
    def space(self):return self._exchange('space','root')
    def inventory_outputs(self,names):return self._exchange('inventory_outputs',list(names))
    def verify_output(self,name):return self._exchange('verify_output',name)

    def create_output(self,name,data):
        if type(data) is not bytes or len(data)>16*1024**2:
            self._fault='cap';self.cancel.set();self.close();raise TransportFault('cap')
        self._exchange('create_output',name,output=True)
        for offset in range(0,len(data),_CHUNK):self._chunk(data[offset:offset+_CHUNK])
        self._chunk(b'')
        return self._exchange('finish_output',name,output=True)

    def _chunk(self,data):
        start=time.monotonic_ns();deadline=min(self.outer,start+5*_SECOND,start+max(0,60*_SECOND-self._output_ns))
        try:
            _check(deadline,self.cancel)
            _send(self._socket,3,self._sequence,data,deadline,self.cancel)
            result=a._parse(_receive(self._socket,2,self._sequence,deadline,self.cancel));self._sequence+=1
            if type(result) is dict and set(result)=={'fault'}:raise TransportFault(result['fault'])
            if type(result) is not dict or set(result)!={'ok'}:raise TransportFault('integrity')
            expected={'written':len(data)} if data else {'ended':True}
            if result['ok']!=expected:raise TransportFault('integrity')
        except BaseException as error:
            self._fault=error.code if type(error) is TransportFault else 'port_failure';self.cancel.set();self.close()
            raise TransportFault(self._fault) from None
        finally:self._output_ns+=time.monotonic_ns()-start

    def close(self):
        if self._cleanup is not None:return self._cleanup
        self._closed=True
        if self._socket is not None:self._socket.close();self._socket=None
        if self._pid is None:self._cleanup='not_started';return self._cleanup
        start=time.monotonic_ns();term=min(self.outer,start+2*_SECOND);kill=min(self.outer,start+4*_SECOND)
        confirmed=True;reaped=False;kill_sent=False
        try:
            # This PID is an unreaped direct child. WNOWAIT preserves identity
            # through group signalling even when the leader has already exited.
            def send(sig):
                nonlocal confirmed,kill_sent
                if sig==signal.SIGKILL:
                    if kill_sent:return
                    kill_sent=True
                try:
                    if self._session:os.killpg(self._pid,sig)
                    else:os.kill(self._pid,sig)
                except ProcessLookupError:pass
                except OSError:confirmed=False
            send(signal.SIGTERM)
            for deadline in (term,kill):
                while time.monotonic_ns()<deadline:
                    info=os.waitid(os.P_PID,self._pid,os.WEXITED|os.WNOHANG|os.WNOWAIT)
                    if info is not None:
                        send(signal.SIGKILL)
                        while True:
                            try:
                                waited,_=os.waitpid(self._pid,os.WNOHANG)
                                reaped=waited==self._pid
                                break
                            except InterruptedError:
                                if time.monotonic_ns()>=kill:break
                        break
                    time.sleep(min(_POLL,max(0,(deadline-time.monotonic_ns())/_SECOND)))
                if reaped:break
                send(signal.SIGKILL)
        except (OSError,ChildProcessError):confirmed=False
        self._cleanup='reaped' if reaped and confirmed else 'unconfirmed'
        self.quarantine_required=self._cleanup=='unconfirmed'
        return self._cleanup
