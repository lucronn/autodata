"""Fixed GET-only source canaries. No browser, catalog, auth or provider request."""
import hashlib
import json
import re
import signal
import time
import urllib.request
import urllib.error
from urllib.parse import urlsplit

class Refused(RuntimeError):pass
PUBLIC='https://autodata.cars.tk'
LOCAL='http://127.0.0.1:18080'
APEX='https://cars.tk'
ASSETS={'app.mjs','article-read.mjs','auth.mjs','bootstrap.mjs','catalog.mjs','commerce.mjs','demo.mjs','firebase-web.mjs','firebase-web.mjs.LEGAL.txt','firebase-web.provenance.json','fonts/InstrumentSans.ttf','fonts/OFL.txt','index.html','progress.mjs','styles.css'}

STATE_HASHES={'health':'6489d6d7a33c5d40e18fc61eeb6c34c341279ee61816394dde5189aa4ad8fae5','ready':'e1cba4d9da3f3f29614701fb954fa1cd897c09b2c6f5cd1defc52603b5d86570','demo':'7187d1e8e2a4d61b1dc5dfedb22d703a462df21470e0c145365b20fb3ed467c3','purchase':'0ec1954c8310fe552df12071f29b10188570ce2446cdfaba5ceede1f8147a024'}

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def allowed(url):
 u=urlsplit(url)
 if u.username or u.password or u.fragment:raise Refused('probe_route')
 origin=u.scheme+'://'+u.netloc
 if origin=='http://127.0.0.1:3031' and u.path=='/healthz' and not u.query:return
 if origin==APEX and u.path=='/workshop' and u.query in ('','x=1'):return
 if origin not in (PUBLIC,LOCAL) or u.query:raise Refused('probe_route')
 if u.path in ('/healthz','/readyz','/workshop','/workshop/','/workshop/purchase-config.json','/workshop/demo-mode.json'):return
 if u.path.startswith('/workshop/') and u.path[len('/workshop/'):] in ASSETS-{'index.html'}:return
 raise Refused('probe_route')

def routes(m,phase):
 if phase not in ('baseline','candidate','rollback'):raise Refused('probe_phase')
 assets=m['assets' if phase=='candidate' else 'baseline_assets'];
 if set(assets)!=ASSETS or any(set(v)!={'sha256','bytes'} or not isinstance(v['sha256'],str) or re.fullmatch('[a-f0-9]{64}',v['sha256']) is None or type(v['bytes']) is not int or not 0<v['bytes']<=1048576 for v in assets.values()):raise Refused('asset_inventory')
 result=[{'url':'http://127.0.0.1:3031/healthz','kind':'health','status':200}]
 for origin in (LOCAL,PUBLIC):
  for path,kind in [('/healthz','health'),('/readyz','ready'),('/workshop/purchase-config.json','purchase'),('/workshop/demo-mode.json','demo')]:result.append({'url':origin+path,'kind':kind,'status':200,'sha256':STATE_HASHES[kind]})
 for url,status,loc in [(PUBLIC+'/workshop/',308,'/workshop'),(APEX+'/workshop',307,PUBLIC+'/workshop/'),(APEX+'/workshop?x=1',307,PUBLIC+'/workshop/?x=1')]:result.append({'url':url,'kind':'redirect','status':status,'location':loc})
 for name,item in m['assets' if phase=='candidate' else 'baseline_assets'].items():
  for origin in (LOCAL,PUBLIC):result.append({'url':origin+('/workshop/' if origin==LOCAL else '/workshop') if name=='index.html' else origin+'/workshop/'+name,'kind':'asset','status':200,'asset':name,**item})
 return result

def validate(rule,status,location,body):
 if status!=rule['status'] or len(body)>1048576:return False
 if rule['kind']=='redirect':return location==rule['location']
 if location:return False
 if rule.get('sha256') and hashlib.sha256(body).hexdigest()!=rule['sha256']:return False
 if rule['kind']=='asset':return len(body)==rule['bytes'] and hashlib.sha256(body).hexdigest()==rule['sha256']
 try:value=json.loads(body)
 except (ValueError,UnicodeError):return False
 if rule['kind']=='health':return value=={'status':'ok'}
 if rule['kind']=='ready':return isinstance(value,dict) and set(value)=={'database','nats','object_storage'} and set(value.values())=={'ready'}
 if rule['kind']=='demo':return value=={'enabled':False}
 return value=={'enabled':False,'terms_version':'workshop-v1','terms_url':None,'privacy_url':None,'refund_url':None,'contact_url':None,'tax_notice':None}

def fetch(rule,deadline):
 allowed(rule['url']);remaining=deadline-time.monotonic()
 if remaining<=0:raise Refused('probe_deadline')
 # Disable ambient proxies for HTTPS as well as loopback. Never follow redirects.
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
 req=urllib.request.Request(rule['url'],headers={'Accept-Encoding':'identity','User-Agent':'autodata-source-canary'},method='GET')
 try:response=opener.open(req,timeout=min(5,remaining))
 except urllib.error.HTTPError as error:response=error
 with response:
  data=response.read(1048577);status=response.status;location=response.headers.get('Location')
 return {'kind':rule['kind'],'asset':rule.get('asset'),'status':status,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'passed':validate(rule,status,location,data)}

def run(m,phase):
 # SIGALRM covers DNS and slowly streamed bodies; caller also enforces210s.
 previous=signal.getsignal(signal.SIGALRM)
 def expired(*args):raise Refused('probe_deadline')
 signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,205)
 try:
  deadline=time.monotonic()+205;proof=[]
  for rule in routes(m,phase):
   try:item=fetch(rule,deadline)
   except Exception:item={'kind':rule.get('kind','route'),'asset':rule.get('asset'),'status':0,'passed':False,'failure':'transport_or_deadline'}
   proof.append(item)
   if not item['passed']:return {'phase':phase,'passed':False,'checks':proof,'requests':len(proof),'provider_requests':0}
  return {'phase':phase,'passed':True,'checks':proof,'requests':len(proof),'provider_requests':0}
 finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)


def main():
 import argparse,os,stat
 from pathlib import Path
 parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['baseline','candidate','rollback'],required=True);parser.add_argument('--manifest-sha256',required=True);args=parser.parse_args()
 root=Path(__file__).resolve().parent
 try:
  if os.geteuid()!=0 or root!=Path('/home/corp/.local/state/autodata-workshop-route-preview-09524db-release-20261116') or root.stat().st_uid!=0 or stat.S_IMODE(root.stat().st_mode)!=0o700:raise Refused('physical_root_required')
  raw=(root/'release-manifest.json').read_bytes()
  if hashlib.sha256(raw).hexdigest()!=args.manifest_sha256:raise Refused('manifest_drift')
  print(json.dumps(run(json.loads(raw),args.phase),sort_keys=True));return 0
 except Exception:print(json.dumps({'phase':args.phase,'passed':False,'checks':[],'failure':'probe_refused'}));return 1
if __name__=='__main__':raise SystemExit(main())
