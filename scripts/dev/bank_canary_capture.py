"""Finite offline dual-bank canary executor. Authenticated execution is gated off."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
from urllib.parse import quote, urlsplit

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'workers/ingestion-python/src'))
from autodata_ingestion.source_connector_client import SourceConnectorClient, SourceConnectorError
from bank_canary_transport import CaptureTransport, CaptureFailure, exclusive, private_json, sensitive

BANKS=('bankone','banktwo')
LIMITS=dict(bank_requests=58,global_requests=116,pages=10,response_bytes=20_000_000,
            bank_bytes=100_000_000,socket_seconds=25,bank_seconds=900,global_seconds=1800,
            cleanup_seconds=10,start_interval=1)
TOP=set('run_id window_start window_end product_sha product_tree executor_sha client_sha256 operator_ref reviewer_ref custodian_ref execution_approval_ref protected_storage_ref retention_delete_at rights_ref banks'.split())
BANK=set('origin owner_identity_ref deployment_revision key_version_ref egress_identity_ref license_ref revision_attestation_ref expected_source_revision minimum_fetched_at maximum_fetched_at selector source_vehicle_ref article_ref body_ref resources applicability_mapping procedure_content_rule incident_procedure_ref'.split())
REFS=set('operator_ref reviewer_ref custodian_ref execution_approval_ref protected_storage_ref rights_ref'.split())
BANKREFS=set('owner_identity_ref deployment_revision key_version_ref egress_identity_ref license_ref revision_attestation_ref expected_source_revision source_vehicle_ref article_ref body_ref incident_procedure_ref'.split())

STOP_CODES={'CANCELLED','VALIDATION','NOT_FOUND','INVALID_INPUT','AMBIGUOUS','PAGE_LIMIT','PAGINATION','SELECTOR','IDENTITY','FETCHED_AT','CAPABILITIES','DEADLINE','REQUEST_LIMIT','BYTE_LIMIT','GRAPH','CATALOG_MEMBERSHIP','APPLICABILITY','VEHICLE_MEMBERSHIP','ARTICLE_MEMBERSHIP','RESOURCE_MEMBERSHIP','RESOURCE_CONTENT','PROCEDURE_CONTENT','SECRET_INCIDENT','OUTPUT_FAILURE','CONNECT_TLS','REDIRECT','FRAMING','INTERRUPTED','CLEANUP','TRANSPORT_PROTOCOL','UPSTREAM_UNAVAILABLE','INVALID_UPSTREAM_RESPONSE','RATE_LIMITED','UNAUTHORIZED','FORBIDDEN','TRANSPORT','DNS','TLS','CONNECT','READ'}

def _require(condition, code='ENROLLMENT'):
    if not condition: raise ValueError(code)


def _fields(value, keys): _require(isinstance(value,dict) and set(value)==set(keys))


def _text(value,maximum=2048):
    _require(isinstance(value,str) and bool(value.strip()) and len(value)<=maximum and not any(ord(c)<32 or ord(c)==127 for c in value))


def _utc(value):
    _require(isinstance(value,str) and value.endswith('Z'))
    try: parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError: raise ValueError('ENROLLMENT') from None
    _require(parsed.utcoffset().total_seconds()==0)
    return parsed


def validate_enrollment(document):
    """Validate schema only; references do not attest to authorization or rights.

    Nested resource membership and applicability mappings have explicit schemas;
    no implicit absent resource roles or inferred field mappings are accepted.
    """
    _fields(document,TOP)
    for k in REFS: _text(document[k])
    _require(isinstance(document['run_id'],str) and bool(re.fullmatch(r'[A-Za-z0-9_-]{1,80}',document['run_id'])))
    for k in ('product_sha','product_tree','executor_sha'): _require(isinstance(document[k],str) and bool(re.fullmatch('[a-f0-9]{40}',document[k])))
    _require(isinstance(document['client_sha256'],str) and bool(re.fullmatch('[a-f0-9]{64}',document['client_sha256'])))
    start,end,delete=map(_utc,(document['window_start'],document['window_end'],document['retention_delete_at']))
    _require(start<end<delete)
    _fields(document['banks'],BANKS)
    origins=[];keys=[]
    for bank in BANKS:
        b=document['banks'][bank];_fields(b,BANK)
        for k in BANKREFS: _text(b[k])
        try: origin=urlsplit(b['origin']);port=origin.port
        except (ValueError,TypeError,AttributeError): raise ValueError('ENROLLMENT') from None
        _require(origin.scheme=='https' and origin.hostname and not origin.username and not origin.password and origin.path=='' and not origin.query and not origin.fragment and (port is None or 1<=port<=65535))
        _require(b['origin']==f'https://{origin.netloc}')
        origins.append((origin.hostname.lower(),port or 443));keys.append(b['key_version_ref'])
        minimum,maximum=map(_utc,(b['minimum_fetched_at'],b['maximum_fetched_at']))
        _require(start<=minimum<=maximum<=end)
        selector=b['selector'];_fields(selector,('year','make','model','configuration','region'))
        _require(type(selector['year']) is int and 1886<=selector['year']<=2200)
        for k,limit in (('make',160),('model',160),('configuration',512),('region',64)): _text(selector[k],limit)
        resources=b['resources'];_fields(resources,('items','absent_roles','membership_attestation_ref'))
        _text(resources['membership_attestation_ref'])
        _require(isinstance(resources['items'],list) and 1<=len(resources['items'])<=134)
        _require(isinstance(resources['absent_roles'],list) and all(role in ('asset','labor') for role in resources['absent_roles']) and len(set(resources['absent_roles']))==len(resources['absent_roles']))
        roles={role:[] for role in ('body','asset','labor')};seen={}
        for resource in resources['items']:
            _require(isinstance(resource,dict))
            frozen=set('ref role media_type required source_revision expected_bytes'.split())
            first='first_observed' in resource
            _fields(resource,frozen|({'first_observed','provider_revision_attestation_ref'} if first else {'sha256'}))
            for k in ('ref','media_type','source_revision'): _text(resource[k])
            _require(isinstance(resource['role'],str) and resource['role'] in roles and type(resource['required']) is bool)
            _require(type(resource['expected_bytes']) is int and 0<resource['expected_bytes']<=20_000_000)
            _require(resource['source_revision']==b['expected_source_revision'])
            if first:
                _require(resource['first_observed'] is True);_text(resource['provider_revision_attestation_ref'])
            else: _require(isinstance(resource['sha256'],str) and bool(re.fullmatch('[a-f0-9]{64}',resource['sha256'])))
            roles[resource['role']].append(resource['ref'])
            descriptor={k:v for k,v in resource.items() if k!='role'}
            _require(resource['ref'] not in seen or seen[resource['ref']]==descriptor)
            seen[resource['ref']]=descriptor
        _require(roles['body']==[b['body_ref']] and next(r for r in resources['items'] if r['role']=='body')['required'])
        _require(len({r['ref'] for r in resources['items'] if r['role']=='asset' and r['required']})<=4 and len({r['ref'] for r in resources['items'] if r['role']=='labor' and r['required']})<=1)
        _require(set(resources['absent_roles'])=={role for role in ('asset','labor') if not roles[role]})
        mapping=b['applicability_mapping'];_fields(mapping,('configuration_field','region_field','source_field','expected_source','owner_approval_ref'))
        _require(mapping['configuration_field']=='configuration' and mapping['region_field']=='region' and mapping['source_field']=='source_label')
        _text(mapping['expected_source']);_text(mapping['owner_approval_ref'])
        rule=b['procedure_content_rule'];_fields(rule,('markers','minimum_text_length','owner_approval_ref'))
        _text(rule['owner_approval_ref']);_require(isinstance(rule['markers'],list) and 1<=len(rule['markers'])<=32)
        for marker in rule['markers']: _text(marker,512)
        _require(type(rule['minimum_text_length']) is int and 1<=rule['minimum_text_length']<=10_000_000)
    _require(len(set(origins))==2 and len(set(keys))==2)
    return copy.deepcopy(document)


def validate_summary(summary):
    """Reject unknown fields and non-conserving public counters."""
    _fields(summary,('schema','run_ref','evidence_ref','banks'))
    _require(summary['schema']==1)
    for key in ('run_ref','evidence_ref'):
        _require(isinstance(summary[key],str) and bool(re.fullmatch(r'[A-Za-z0-9_-]{1,80}',summary[key])))
    _fields(summary['banks'],BANKS)
    for row in summary['banks'].values():
        _fields(row,('state','stop_code','review_state','intended','attempted','successful'))
        _require(row['state'] in {'pending','failed','incomplete','withdrawn','observed_complete'})
        _require(row['review_state'] in {'pending','accepted','rejected'})
        _require(row['stop_code'] is None or row['stop_code'] in STOP_CODES)
        _fields(row['intended'],('selected_articles','required_resources'))
        _require(row['intended']['selected_articles']==1 and type(row['intended']['required_resources']) is int and 1<=row['intended']['required_resources']<=6)
        for field in ('attempted','successful'):
            _fields(row[field],('requests','selected_articles','required_resources'))
            _require(all(type(v) is int and v>=0 for v in row[field].values()))
        _require(row['successful']['requests']<=row['attempted']['requests']<=58)
        for field in ('selected_articles','required_resources'):
            _require(row['successful'][field]<=row['attempted'][field]<=row['intended'][field])
    return summary


class Clock:
    monotonic=staticmethod(time.monotonic)
    sleep=staticmethod(time.sleep)
    @staticmethod
    def utcnow(): return datetime.now(timezone.utc)


def _canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


def _digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Evidence:
    def __init__(self,root,doc,clock):
        root=Path(os.path.abspath(root))
        _require(root.is_dir() and all(not p.is_symlink() for p in (root,*root.parents)) and not stat.S_IMODE(root.stat().st_mode)&0o077 and root.stat().st_uid==os.getuid(),'OUTPUT_FAILURE')
        # Open parent with O_NOFOLLOW and create relative to the held descriptor.
        parent=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try: os.mkdir(doc['run_id'],0o700,dir_fd=parent)
        finally: os.close(parent)
        self.root=root/doc['run_id'];self.clock=clock;self.inventory=[]
        for bank in BANKS:
            (self.root/bank).mkdir(mode=0o700)
            (self.root/bank/'quarantine').mkdir(mode=0o700)
        private_json(self.root/'run.json',dict(schema=1,enrollment_sha256=hashlib.sha256(_canonical(doc)).hexdigest(),
            enrollment=doc,executor_bytes={Path(p).name:_digest(p) for p in (__file__,Path(__file__).with_name('bank_canary_transport.py'))},
            actual_client_sha256=_digest(sys.modules[SourceConnectorClient.__module__].__file__),
            runtime={'python':sys.version.split()[0],'platform':sys.platform},limits=LIMITS,started_at=clock.utcnow().isoformat(),
            intended={bank:{'selected_articles':1,'required_resources':len({r['ref'] for r in doc['banks'][bank]['resources']['items'] if r['required']})} for bank in BANKS}))
        self.attempts=exclusive(self.root/'attempts.jsonl')
        try:
            for bank in BANKS:
                b=doc['banks'][bank]
                self.attempt(dict(event='planned',bank=bank,capabilities=1,
                    catalog_branches=['years','makes','models','configurations'],pages_per_branch=10,
                    resolution_posts=1,selector=b['selector'],article_index_pages=10,
                    source_vehicle_ref=b['source_vehicle_ref'],article_ref=b['article_ref'],
                    resources=b['resources']['items'],utc=clock.utcnow().isoformat()))
        except OSError:
            self.attempts.close()
            raise
    def attempt(self,row):
        self.attempts.write(_canonical(row)+b'\n');os.fsync(self.attempts.fileno())
    def capture(self,bank,sequence,transport):
        meta=transport.last
        if meta is None: return None
        item=dict(meta,bank=bank,sequence=sequence,object_kind='raw')
        # All uninspected originals begin in incident-isolated quarantine.
        for name in ('raw_ref','journal_ref'):
            if item.get(name):
                source=self.root/bank/'quarantine'/item[name]
                if item['state']!='quarantined':
                    target=self.root/bank/item[name]
                    os.rename(source,target)
                else: target=source
                item[name]=str(target.relative_to(self.root))
        self.inventory.append(item)
        return item
    def quarantine(self,bank,sequence):
        for item in self.inventory:
            if item['bank']==bank and item['sequence']==sequence:
                item.update(state='quarantined',reason='SECRET_INCIDENT',headers={},final_url=None)
                for name in ('raw_ref','journal_ref'):
                    if item.get(name):
                        source=self.root/item[name];target=self.root/bank/'quarantine'/source.name
                        os.rename(source,target);item[name]=str(target.relative_to(self.root))
    def decoded(self,bank,ref,payload,sequence):
        path=self.root/bank/f'{sequence:04d}.decoded'
        with exclusive(path) as file: file.write(payload);os.fsync(file.fileno())
        self.inventory.append(dict(bank=bank,sequence=sequence,object_kind='decoded',resource_ref=ref,
            state='complete',byte_count=len(payload),sha256=hashlib.sha256(payload).hexdigest(),
            raw_ref=str(path.relative_to(self.root)),sealing='local_unsealed'))
    def finish(self,result):
        self.attempts.close()
        private_json(self.root/'inventory.json',{'schema':1,'objects':self.inventory})
        private_json(self.root/'result.json',result)
        summary=dict(schema=1,run_ref=result['run_ref'],evidence_ref=result['run_ref'],banks={bank:{
            'state':row['state'],'stop_code':row['stop_code'],'review_state':row['review_state'],
            'intended':row['intended'],'attempted':row['attempted'],'successful':row['successful']} for bank,row in result['banks'].items()})
        private_json(self.root/'summary.json',validate_summary(summary))


def run_capture(enrollment,transport_factory,clock,evidence_root):
    """Run only synthetic reserved-origin fixtures; never reads credentials/env.

    A future enrolled real execution boundary must be independently reviewed and
    committed. Merely supplying a callable does not authorize real origins.
    """
    doc=validate_enrollment(enrollment)
    _require(getattr(transport_factory,'offline',False) is True,'OFFLINE_REQUIRED')
    _require(all(urlsplit(b['origin']).hostname.endswith('.invalid') for b in doc['banks'].values()),'OFFLINE_REQUIRED')
    now=clock.utcnow();_require(_utc(doc['window_start'])<=now<_utc(doc['window_end']) and now<_utc(doc['retention_delete_at']),'WINDOW')
    try:
        evidence=Evidence(evidence_root,doc,clock)
    except (OSError,ValueError):
        return {'schema':1,'run_ref':doc['run_id'],'banks':{bank:dict(state='incomplete',stop_code='OUTPUT_FAILURE',review_state='pending',intended={'selected_articles':1,'required_resources':len({r['ref'] for r in doc['banks'][bank]['resources']['items'] if r['required']})},attempted={'requests':0,'selected_articles':0,'required_resources':0},successful={'requests':0,'selected_articles':0,'required_resources':0},resource_coverage=[]) for bank in BANKS}}
    run_start=clock.monotonic();last_start=None;total=0;shared=None
    result={'schema':1,'run_ref':doc['run_id'],'banks':{}}
    for bank in BANKS:
        b=doc['banks'][bank];resources=b['resources']['items'];required={r['ref']:r for r in resources if r['required']}
        row=dict(state='pending',stop_code=None,review_state='pending',
            intended={'selected_articles':1,'required_resources':len(required)},attempted={'requests':0,'selected_articles':0,'required_resources':0},
            successful={'requests':0,'selected_articles':0,'required_resources':0},resource_coverage=[])
        result['banks'][bank]=row
        if shared:
            row.update(state='withdrawn',stop_code=shared);continue
        bank_start=clock.monotonic();bank_bytes=0;step={};transport=None
        deadline=min(bank_start+900,run_start+1790)
        try:
            _require(clock.monotonic()<deadline,'DEADLINE')
            fixture=transport_factory(bank,copy.deepcopy(b))
            transport=CaptureTransport(evidence.root/bank/'quarantine',opener=fixture,clock=clock,deadline=deadline)
            def open_request(request,timeout):
                nonlocal total,last_start,bank_bytes
                _require(clock.monotonic()<deadline,'DEADLINE')
                if last_start is not None: clock.sleep(max(0,last_start+1-clock.monotonic()))
                _require(clock.monotonic()<deadline,'DEADLINE')
                _require(row['attempted']['requests']<58 and total<116,'REQUEST_LIMIT')
                _require(bank_bytes<100_000_000,'BYTE_LIMIT')
                _require(urlsplit(request.full_url).netloc==urlsplit(b['origin']).netloc and request.full_url==step['url'] and request.get_method()==step['method'],'GRAPH')
                total+=1;row['attempted']['requests']+=1;last_start=clock.monotonic()
                sequence=row['attempted']['requests'];started=clock.utcnow().isoformat()
                evidence.attempt(dict(event='attempt',bank=bank,sequence=sequence,method=request.get_method(),path=request.selector,step=step,
                    utc=started,monotonic=last_start-run_start))
                transport.allowance=min(20_000_000,100_000_000-bank_bytes);transport.last=None
                try: response=transport(request,timeout=min(25,timeout));return response
                finally:
                    item=evidence.capture(bank,sequence,transport)
                    if item: bank_bytes+=item['byte_count']
                    evidence.attempt(dict(event='capture',bank=bank,sequence=sequence,utc=clock.utcnow().isoformat(),
                        monotonic=clock.monotonic()-run_start,raw_inventory_sequence=sequence if item else None,
                        http_status=item.get('status') if item else None,outcome=item.get('reason') if item else 'CONNECT_TLS'))
            client=SourceConnectorClient(b['origin'],provider=bank,opener=open_request)
            def call(operation,method,path,fn,**details):
                nonlocal step
                step=dict(operation=operation,method=method,url=b['origin']+path,**details)
                env=fn()
                _require(clock.monotonic()<deadline,'DEADLINE')
                _require(env.provider==bank and env.source_revision==b['expected_source_revision'],'IDENTITY')
                fetched=_utc(env.fetched_at)
                _require(_utc(b['minimum_fetched_at'])<=fetched<=_utc(b['maximum_fetched_at']),'FETCHED_AT')
                row['successful']['requests']+=1
                evidence.attempt(dict(event='validation',bank=bank,sequence=row['attempted']['requests'],outcome='VALIDATED',
                    expected_provider=bank,observed_provider=env.provider,expected_revision=b['expected_source_revision'],observed_revision=env.source_revision,
                    observed_fetched_at=env.fetched_at,request_id=env.request_id,safe_locator=env.source_locator))
                return env
            env=call('capabilities','GET','/v1/capabilities',client.capabilities)
            _require({'catalog','vehicle_resolution','article_list','resource_read'}<=set(env.body['capabilities']),'CAPABILITIES')
            def pages(operation,scope=None,selector=None):
                from urllib.parse import urlencode
                cursor=None;seen=set();items=[]
                for page in range(1,11):
                    if scope:
                        query=dict(selector or {})
                        if cursor is not None: query['cursor']=cursor
                        suffix='?'+urlencode(query) if query else ''
                        path='/v1/catalog/'+scope+suffix
                        env=call(operation,'GET',path,lambda:client.catalog(scope,selector,cursor),page=page,cursor_predecessor=cursor)
                        items.extend(env.body['items'])
                    else:
                        path='/v1/vehicles/'+quote(b['source_vehicle_ref'],safe='')+'/articles'
                        if cursor is not None:path+='?'+urlencode({'cursor':cursor})
                        env=call(operation,'GET',path,lambda:client.list_articles(b['source_vehicle_ref'],cursor),page=page,cursor_predecessor=cursor)
                        items.extend(env.body['articles'])
                    if env.complete:
                        _require('next_cursor' not in env.body,'PAGINATION');return items
                    following=env.next_cursor
                    _require(following and following not in seen and following!=cursor,'PAGINATION')
                    seen.add(following);cursor=following
                raise ValueError('PAGE_LIMIT')
            selector=b['selector']
            for scope,key,keys in (('years','year',()),('makes','make',('year',)),('models','model',('year','make')),('configurations','configuration',('year','make','model'))):
                items=pages('catalog',scope,{k:selector[k] for k in keys})
                matches=[item for item in items if item.get(key)==selector[key]]
                _require(matches,'CATALOG_MEMBERSHIP')
                if scope=='configurations':
                    mapping=b['applicability_mapping']
                    _require(any(item.get(mapping['region_field'])==selector['region'] and item.get(mapping['source_field'])==mapping['expected_source'] for item in matches),'APPLICABILITY')
            env=call('resolution','POST','/v1/vehicle-resolutions',lambda:client.resolve_vehicle(selector),selector=selector)
            _require(dict(env.body['selector'])==selector,'SELECTOR')
            candidates=[c for c in env.body['candidates'] if c['opaque_ref']==b['source_vehicle_ref']]
            _require(len(candidates)==1,'VEHICLE_MEMBERSHIP')
            articles=pages('articles');selected=[a for a in articles if a['opaque_ref']==b['article_ref']]
            _require(len(selected)==1,'ARTICLE_MEMBERSHIP')
            article=selected[0];row['attempted']['selected_articles']=1
            _require(article.get('resource_ref')==b['body_ref'],'RESOURCE_MEMBERSHIP')
            assets={r['ref'] for r in resources if r['role']=='asset'}
            labor={r['ref'] for r in resources if r['role']=='labor'}
            _require(set(article.get('asset_resource_refs',[]))==assets and ({article['labor_resource_ref']} if 'labor_resource_ref' in article else set())==labor,'RESOURCE_MEMBERSHIP')
            for ref,r in required.items():
                row['attempted']['required_resources']+=1
                env=call('resource','GET','/v1/resources/'+quote(ref,safe=''),lambda:client.read_resource(ref),resource_ref=ref)
                payload=env.raw_resource
                if payload is not None and sensitive(payload):
                    evidence.quarantine(bank,row['attempted']['requests'])
                    raise CaptureFailure('SECRET_INCIDENT')
                _require(payload is not None and len(payload)==r['expected_bytes'] and env.body['media_type']==r['media_type'],'RESOURCE_CONTENT')
                _require('sha256' not in r or hashlib.sha256(payload).hexdigest()==r['sha256'],'RESOURCE_CONTENT')
                if ref==b['body_ref']:
                    _require(set(env.body.get('asset_resource_refs',[]))==assets,'RESOURCE_MEMBERSHIP')
                    try: text=payload.decode('utf-8')
                    except UnicodeError: raise ValueError('PROCEDURE_CONTENT') from None
                    rule=b['procedure_content_rule']
                    _require(len(text)>=rule['minimum_text_length'] and all(marker in text for marker in rule['markers']),'PROCEDURE_CONTENT')
                evidence.decoded(bank,ref,payload,row['attempted']['requests'])
                row['successful']['required_resources']+=1;row['resource_coverage'].append(ref)
            row['successful']['selected_articles']=1;row.update(state='observed_complete')
        except (Exception,KeyboardInterrupt) as error:
            code='CANCELLED' if isinstance(error,KeyboardInterrupt) else error.code if isinstance(error,(CaptureFailure,SourceConnectorError)) else (str(error) if isinstance(error,ValueError) else ('OUTPUT_FAILURE' if isinstance(error,OSError) else 'TRANSPORT'))

            code=code if code in STOP_CODES else 'VALIDATION'
            row.update(state='incomplete' if code in {'DEADLINE','BYTE_LIMIT','PAGE_LIMIT','OUTPUT_FAILURE','CONNECT_TLS','DNS','TLS','CONNECT','READ'} else 'failed',stop_code=code)
            if code in {'SECRET_INCIDENT','OUTPUT_FAILURE','CLEANUP','CANCELLED'}:shared=code
            try:evidence.attempt(dict(event='validation',bank=bank,sequence=row['attempted']['requests'],outcome=code))
            except OSError: shared='OUTPUT_FAILURE';row.update(state='incomplete',stop_code=shared)
    result['ended_at']=clock.utcnow().isoformat();result['monotonic_seconds']=clock.monotonic()-run_start
    try:evidence.finish(result)
    except OSError:
        for row in result['banks'].values(): row.update(state='incomplete',stop_code='OUTPUT_FAILURE')
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    validate=commands.add_parser('validate');validate.add_argument('--enrollment',required=True)
    commands.add_parser('offline-selftest')
    capture=commands.add_parser('capture')
    for flag in ('enrollment','approval','bankone-key-fd','banktwo-key-fd','evidence-root'):capture.add_argument('--'+flag,required=True)
    try:
        args=parser.parse_args(argv)
        if args.command=='capture':
            # No receipt exists at this tooling-only gate; do not open descriptors.
            print('{"schema":1,"outcome":"blocked","reason":"EXECUTION_GATE_REQUIRED"}')
            return 2
        if args.command=='validate':
            validate_enrollment(json.loads(Path(args.enrollment).read_bytes()))
            print('{"schema":1,"outcome":"syntax_valid","review_state":"pending"}');return 0
        import unittest
        suite=unittest.defaultTestLoader.discover(str(Path(__file__).parent/'tests'),pattern='test_bank_canary_capture.py')
        return 0 if unittest.TextTestRunner(stream=sys.stderr).run(suite).wasSuccessful() else 1
    except (ValueError,OSError):
        print('{"schema":1,"outcome":"blocked","reason":"INVALID_INPUT"}');return 2

if __name__=='__main__':raise SystemExit(main())
