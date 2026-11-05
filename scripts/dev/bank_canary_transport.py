"""Bounded original-byte capture. No urllib redirects, proxies, or decompression.

The direct HTTPS worker is available for a separately authorized future run;
this milestone's controller accepts only explicitly offline transports.
"""
from __future__ import annotations
import hashlib
import base64
import binascii
import http.client
import io
import json
import multiprocessing
import os
from pathlib import Path
import re
import ssl
import socket
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit, unquote_to_bytes

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
    normalized=unquote_to_bytes(data)
    return bool(SECRET_PATTERN.search(data) or SECRET_PATTERN.search(normalized) or any(token and (token in data or token in normalized) for token in credentials))


def sensitive_payload(data,credentials=()):
    """Inspect bounded resource bytes even when later schema/hash validation fails."""
    if sensitive(data,credentials):return True
    try:value=json.loads(data)
    except (ValueError,UnicodeError,RecursionError):return False
    # Inspect semantic strings before product validation. A rejected hash or
    # schema must not bypass scanning of JSON escape sequences.
    pending=[value]
    while pending:
        item=pending.pop()
        if isinstance(item,str) and sensitive(item.encode('utf-8',errors='surrogatepass'),credentials):return True
        if isinstance(item,dict):
            if sensitive(json.dumps(dict.fromkeys(item),ensure_ascii=False).encode('utf-8',errors='surrogatepass'),credentials):return True
            pending.extend(item.values())
        elif isinstance(item,list):pending.extend(item)
    if isinstance(value,dict) and isinstance(value.get('content_base64'),str):
        try:decoded=base64.b64decode(value['content_base64'],validate=True)
        except (ValueError,binascii.Error):return False
        return sensitive(decoded,credentials)
    return False


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
            try: chunk=response.read(min(65536,allowance-size))
            except OSError: raise CaptureFailure('READ') from None
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
    conn=None;stage='CONNECT'
    try:
        parsed=urlsplit(spec['url'])
        conn=http.client.HTTPSConnection(parsed.hostname,parsed.port or 443,timeout=25,context=ssl.create_default_context())
        conn.connect()
        sock=conn.sock
        cert=sock.getpeercert(binary_form=True)
        tls={'version':sock.version(),'cipher':sock.cipher(),'certificate_sha256':hashlib.sha256(cert).hexdigest(),'peer':sock.getpeername()[0]}
        headers=dict(spec['headers']);headers['Accept-Encoding']='identity';headers['Connection']='close'
        stage='READ'
        try:
            conn.request(spec['method'],parsed.path+('?' + parsed.query if parsed.query else ''),body=spec['data'],headers=headers)
            response=conn.getresponse()
        except OSError:raise CaptureFailure('READ') from None
        stage='CAPTURE'
        _stream(response,spec['url'],spec['raw_path'],spec['journal_path'],spec['allowance'],(),tls)
        spec['completion'].send(None)
    except BaseException as error:
        reason=('CANCELLED' if isinstance(error,KeyboardInterrupt) else 'DNS' if isinstance(error,socket.gaierror) else 'TLS' if isinstance(error,ssl.SSLError)
                else error.code if isinstance(error,CaptureFailure) else 'OUTPUT_FAILURE' if isinstance(error,OSError) and stage=='CAPTURE' else stage)
        # Only a fixed enum crosses IPC. No raw exception or response text.
        try: spec['completion'].send(reason)
        except (OSError,EOFError): pass
    finally:
        spec['completion'].close()
        if conn is not None:
            try:conn.close()
            except BaseException:pass


def _opener_child(spec,opener):
    """Offline injected openers obey the same parent watchdog as HTTPS."""
    response=None;stage='CONNECT'
    try:
        from urllib.request import Request
        request=Request(spec['url'],data=spec['data'],headers=spec['headers'],method=spec['method'])
        try:response=opener(request,timeout=spec['timeout'])
        except HTTPError as error:response=error
        stage='CAPTURE'
        _stream(response,spec['url'],spec['raw_path'],spec['journal_path'],spec['allowance'],())
        spec['completion'].send(None)
    except BaseException as error:
        reason=('CANCELLED' if isinstance(error,KeyboardInterrupt) else error.code if isinstance(error,CaptureFailure) else 'DNS' if isinstance(error,socket.gaierror)
                else 'TLS' if isinstance(error,ssl.SSLError) else 'OUTPUT_FAILURE' if stage=='CAPTURE' else 'CONNECT')
        try:spec['completion'].send(reason)
        except (OSError,EOFError):pass
    finally:
        if response is not None:
            try:response.close()
            except BaseException:pass
        spec['completion'].close()


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
        forced=None;phase='OPEN'
        try:
            ctx=multiprocessing.get_context('fork')
            receive,send=ctx.Pipe(duplex=False);spec['completion']=send
            spec['timeout']=min(25,timeout)
            target=self.child_target if self.opener is None else _opener_child
            args=(spec,) if self.opener is None else (spec,self.opener)
            child=ctx.Process(target=target,args=args,daemon=True)
            child.start();send.close();self.child_pid=child.pid
            try:
                while child.is_alive() and self.clock.monotonic()<self.deadline:
                    child.join(min(.025,max(0,self.deadline-self.clock.monotonic())))
                if child.is_alive():
                    forced='DEADLINE';child.terminate();child.join(.2)
                    if child.is_alive():child.kill();child.join(1)
                if child.is_alive():raise CaptureFailure('CLEANUP')
                child.join()
                if forced is None and receive.poll():
                    try:forced=receive.recv()
                    except EOFError:pass
            finally:
                receive.close()
                if child.is_alive():child.kill();child.join(1)
                child.close()
        except KeyboardInterrupt:
            forced='CANCELLED'
        except OSError:
            forced='CONNECT_TLS' if phase=='OPEN' and self.opener is not None else 'OUTPUT_FAILURE'
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
            # Publish persisted inventory before inspection, and fail closed if
            # inspection itself cannot finish. Never promote uninspected bytes.
            self.last=meta
            try:
                header_bytes=json.dumps(meta.get('headers',{})).encode()
                flagged=(sensitive_payload(raw,self.credentials) or sensitive(header_bytes,self.credentials)
                    or any(sensitive(str(value).encode('utf-8',errors='surrogatepass'),self.credentials) for value in meta.get('headers',{}).values()))
                if flagged:meta.update(state='quarantined',reason='SECRET_INCIDENT',headers={},final_url=None)
            except BaseException as error:
                meta.update(state='quarantined',reason='CANCELLED' if isinstance(error,KeyboardInterrupt) else 'INSPECTION_FAILURE',headers={},final_url=None)
        if meta['state']!='complete': raise CaptureFailure(meta['reason'] or 'TRANSPORT')
        if meta['final_url']!=request.full_url: raise CaptureFailure('REDIRECT')
        if 300<=meta['status']<400: raise CaptureFailure('REDIRECT')
        return CapturedResponse(raw,meta['status'],meta['headers'],meta['final_url'])
