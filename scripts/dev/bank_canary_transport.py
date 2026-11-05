"""Bounded original-byte capture. No urllib redirects, proxies, or decompression.

The direct HTTPS worker is available for a separately authorized future run;
this milestone's controller accepts only explicitly offline transports.
"""
from __future__ import annotations
import hashlib
import http.client
import io
import json
import multiprocessing
import os
from pathlib import Path
import re
import ssl
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit

HEADERS = frozenset(x.lower() for x in ('Content-Type','Content-Length','Retry-After',
    'X-Request-Id','X-Provider','X-Source-Revision','X-Fetched-At','X-Source-Locator',
    'X-Source-SHA256','X-Source-Media-Type'))
SECRET_PATTERN = re.compile(rb'(?:[?&]|["\s])(?:token|sig(?:nature)?|password|auth(?:orization)?|api[_-]?key|secret|session|cookie)["\s]*[=:]', re.I)

class CaptureFailure(RuntimeError):
    def __init__(self, code): self.code=code; super().__init__(code)


def exclusive(path):
    return os.fdopen(os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600),'wb',buffering=0)


def private_json(path, value):
    with exclusive(path) as file:
        file.write(json.dumps(value,sort_keys=True,separators=(',',':')).encode());os.fsync(file.fileno())


def sensitive(data, credentials=()):
    return bool(SECRET_PATTERN.search(data) or any(token and token in data for token in credentials))


class CapturedResponse(io.BytesIO):
    def __init__(self, raw, status, headers, url):
        super().__init__(raw);self.status=status;self.headers=headers;self.url=url
    def geturl(self): return self.url


def _stream(response, url, raw_path, journal_path, allowance, credentials, tls=None):
    """Never read a sentinel beyond allowance; unknown exact ceilings are partial."""
    headers={k:v for k,v in response.headers.items() if k.lower() in HEADERS}
    status=int(getattr(response,'status',getattr(response,'code',0)))
    final=response.geturl() if hasattr(response,'geturl') else url
    meta={'status':status,'headers':headers,'final_url':final,'tls':tls,'state':'partial','reason':'INTERRUPTED'}
    with exclusive(journal_path) as journal, exclusive(raw_path) as raw:
        def log(value):
            journal.write(json.dumps(value,separators=(',',':')).encode()+b'\n');os.fsync(journal.fileno())
        log(meta)
        size=0;state='partial';reason='BYTE_LIMIT'
        declared=next((v for k,v in headers.items() if k.lower()=='content-length'),None)
        length=int(declared) if declared is not None and str(declared).isdigit() else None
        while size<allowance:
            chunk=response.read(min(65536,allowance-size))
            if not chunk:
                state='complete';reason=None;break
            if not isinstance(chunk,bytes) or len(chunk)>min(65536,allowance-size):
                raise CaptureFailure('TRANSPORT_PROTOCOL')
            raw.write(chunk);os.fsync(raw.fileno());size+=len(chunk)
            log({'persisted_bytes':size})
        if length is not None:
            if size==length: state='complete';reason=None
            elif size<length and state=='complete': state='partial';reason='FRAMING'
            elif size>length: state='partial';reason='FRAMING'
        meta.update(state=state,reason=reason,byte_count=size)
        log(meta)
    return meta


def _https_child(spec):
    """One connection in a disposable child; system TLS trust and no proxy lookup."""
    conn=None
    try:
        parsed=urlsplit(spec['url'])
        conn=http.client.HTTPSConnection(parsed.hostname,parsed.port or 443,timeout=25,context=ssl.create_default_context())
        conn.connect()
        sock=conn.sock
        cert=sock.getpeercert(binary_form=True)
        tls={'version':sock.version(),'cipher':sock.cipher(),'certificate_sha256':hashlib.sha256(cert).hexdigest(),'peer':sock.getpeername()[0]}
        headers=dict(spec['headers']);headers['Accept-Encoding']='identity';headers['Connection']='close'
        conn.request(spec['method'],parsed.path+('?' + parsed.query if parsed.query else ''),body=spec['data'],headers=headers)
        response=conn.getresponse()
        _stream(response,spec['url'],spec['raw_path'],spec['journal_path'],spec['allowance'],(),tls)
    except BaseException:
        # Failure stages are recorded without exception strings or invented status.
        if not Path(spec['journal_path']).exists():
            with exclusive(spec['journal_path']) as file:
                file.write(b'{"state":"absent","reason":"CONNECT_TLS"}\n')
    finally:
        if conn is not None: conn.close()


class CaptureTransport:
    """Capture before returning a BytesIO-compatible adapter to the source client."""
    def __init__(self, spool_dir, *, opener=None, clock=time, deadline=None,
                 allowance=20_000_000, child_target=None, credentials=()):
        self.root=Path(spool_dir);self.opener=opener;self.clock=clock
        self.deadline=deadline if deadline is not None else clock.monotonic()+900
        self.allowance=min(20_000_000,allowance);self.child_target=child_target or _https_child
        self.credentials=tuple(credentials);self.sequence=0;self.last=None;self.child_pid=None

    def __call__(self, request, timeout=25):
        self.sequence+=1
        stem=f'{self.sequence:04d}'
        raw_path=self.root/(stem+'.raw');journal_path=self.root/(stem+'.journal')
        if self.allowance<=0: raise CaptureFailure('BYTE_LIMIT')
        spec=dict(url=request.full_url,method=request.get_method(),headers=dict(request.header_items()),data=request.data,
                  raw_path=str(raw_path),journal_path=str(journal_path),allowance=self.allowance)
        forced=None
        try:
            if self.opener is not None:
                try: response=self.opener(request,timeout=min(25,timeout))
                except HTTPError as error: response=error
                try: _stream(response,request.full_url,raw_path,journal_path,self.allowance,self.credentials)
                finally: response.close()
            else:
                ctx=multiprocessing.get_context('fork')
                child=ctx.Process(target=self.child_target,args=(spec,),daemon=True)
                child.start();self.child_pid=child.pid
                try:
                    while child.is_alive() and self.clock.monotonic()<self.deadline:
                        child.join(min(.025,max(0,self.deadline-self.clock.monotonic())))
                    if child.is_alive():
                        forced='DEADLINE';child.terminate();child.join(.2)
                        if child.is_alive(): child.kill();child.join(1)
                    if child.is_alive(): raise CaptureFailure('CLEANUP')
                    child.join()
                finally:
                    if child.is_alive(): child.kill();child.join(1)
                    child.close()
        except OSError:
            forced='OUTPUT_FAILURE'
        except (TimeoutError,ConnectionError):
            forced='CONNECT_TLS'
        finally:
            meta={'status':None,'headers':{},'final_url':None,'tls':None,'state':'absent','reason':forced or 'CONNECT_TLS'}
            if journal_path.exists():
                for line in journal_path.read_bytes().splitlines():
                    try:
                        row=json.loads(line)
                        if 'state' in row: meta.update(row)
                    except ValueError: pass
            raw=raw_path.read_bytes() if raw_path.exists() else b''
            if raw_path.exists() and meta['state']=='absent': meta['state']='partial'
            if forced: meta.update(state='partial' if raw_path.exists() else 'absent',reason=forced)
            meta.update(byte_count=len(raw),sha256=hashlib.sha256(raw).hexdigest() if raw_path.exists() else None,
                        raw_ref=raw_path.name if raw_path.exists() else None,journal_ref=journal_path.name if journal_path.exists() else None,
                        sealing='local_unsealed')
            header_bytes=json.dumps(meta.get('headers',{})).encode()
            if sensitive(raw,self.credentials) or sensitive(header_bytes,self.credentials):
                meta.update(state='quarantined',reason='SECRET_INCIDENT')
            self.last=meta
        if meta['state']!='complete': raise CaptureFailure(meta['reason'] or 'TRANSPORT')
        if meta['final_url']!=request.full_url: raise CaptureFailure('REDIRECT')
        if 300<=meta['status']<400: raise CaptureFailure('REDIRECT')
        return CapturedResponse(raw,meta['status'],meta['headers'],meta['final_url'])
