"""Configuration-only dispatch budgets, including real connector repair paths."""
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from autodata_ingestion import catalog_service as service
from autodata_ingestion.source_connector_client import SourceConnectorClient


class Response:
    def __init__(self, request, body, status=200):
        self.url=request.full_url;self.status=status
        self.headers={'Content-Type':'application/json'}
        self.body=json.dumps(body).encode();self.offset=0
    def geturl(self):return self.url
    def read1(self, length):
        chunk=self.body[self.offset:self.offset+length];self.offset+=len(chunk);return chunk
    def read(self, length=-1):return self.read1(len(self.body) if length<0 else length)
    def __enter__(self):return self
    def __exit__(self,*args):return False


def envelope(bank,scope,*,complete=True,cursor=None,items=None):
    result={'request_id':'00000000-0000-4000-8000-000000000001','provider':bank,'source_revision':'fixture-v1','fetched_at':'2026-11-15T00:00:00Z','scope':scope,'complete':complete,'items':items or []}
    if cursor is not None:result['next_cursor']=cursor
    return result


def request(key='budget-fixture'):
    return {'idempotency_key':key,'scope':'configurations','year':2024,'make':'acura','model':'integra','region':'US'}


@pytest.fixture(autouse=True)
def isolated_memory(monkeypatch):
    monkeypatch.setattr(service,'_HYDRATION_RESULTS',{})
    monkeypatch.setattr(service,'_persist_resolved_catalog_rows',Mock(return_value={'status':'persisted'}))
    monkeypatch.setattr(service,'_persist_hydration_scope',Mock(side_effect=lambda req,result:{'status':'persisted' if result.complete else 'not_complete'}))


def configure(monkeypatch,openers):
    clients={bank:SourceConnectorClient('https://'+bank+'.test',provider=bank,opener=opener) for bank,opener in openers.items()}
    monkeypatch.setattr('autodata_ingestion.source_connector_client.source_connector_registry',lambda:clients)


def assert_no_persistence():
    service._persist_resolved_catalog_rows.assert_not_called()
    service._persist_hydration_scope.assert_not_called()
    assert service._HYDRATION_RESULTS["budget-fixture"][1]["complete"] is False


def test_shared_twelve_attempt_cap_includes_both_banks_parent_pages_and_repair(monkeypatch,caplog):
    calls=[];bank_counts={'bankone':0,'banktwo':0};page_counts={}
    def opener(bank):
        def read(req,timeout):
            calls.append((bank,req.full_url));bank_counts[bank]+=1
            scope=urlsplit(req.full_url).path.rsplit('/',1)[1];query=parse_qs(urlsplit(req.full_url).query)
            if bank=='bankone':
                n=bank_counts[bank]
                return Response(req,envelope(bank,scope,complete=n==5,cursor=None if n==5 else str(n)))
            if scope=='configurations' and query.get('make')!=['Acura']:return Response(req,{},404)
            if scope in {'makes','models'}:
                key=(scope,query.get('cursor',[None])[0]);page_counts[key]=page_counts.get(key,0)+1
                second='cursor' in query
                item={'opaque_ref':scope,'label':scope,'year':2024,'make':'Acura'}
                if scope=='models':item['model']='Integra'
                return Response(req,envelope(bank,scope,complete=second,cursor=None if second else 'parent-2',items=[item] if second else []))
            return Response(req,envelope(bank,scope,complete=False,cursor='next-configuration'))
        return read
    configure(monkeypatch,{bank:opener(bank) for bank in bank_counts})
    with pytest.raises(service._ConfigurationHydrationStopped) as caught:
        service.ensure_catalog_hydration(json.dumps(request()))
    assert caught.value.reason=='request_limit'
    assert len(calls)==12 and bank_counts=={'bankone':5,'banktwo':7}
    assert any('/makes?' in url for _,url in calls) and any('/models?' in url for _,url in calls)
    assert any('make=Acura' in url and '/configurations?' in url for _,url in calls)
    assert_no_persistence()
    assert 'stage=provider_resolution outcome=failed' not in caplog.text
    assert 'stop_reason=request_limit' in caplog.text


def test_exact_twelfth_attempt_can_complete_both_banks_and_persist_marker(monkeypatch,caplog):
    calls=[];counts={'bankone':0,'banktwo':0}
    def opener(bank):
        def read(req,timeout):
            calls.append(bank);counts[bank]+=1;n=counts[bank]
            return Response(req,envelope(bank,'configurations',complete=n==6,cursor=None if n==6 else str(n)))
        return read
    configure(monkeypatch,{bank:opener(bank) for bank in counts})
    result=service.ensure_catalog_hydration(json.dumps(request()))
    assert result['complete'] is True and len(calls)==12
    service._persist_hydration_scope.assert_called_once()
    assert service._persist_hydration_scope.call_args.args[1].complete is True
    events=[line for line in caplog.text.splitlines() if 'catalog configuration budget ' in line]
    assert len(events)==2 and 'state=started' in events[0] and 'state=finished' in events[1]
    tokens=[re.search(r'attempt=([0-9a-f]{16})',line).group(1) for line in events]
    assert tokens[0]==tokens[1] and 'attempted_requests=12' in events[1]


def test_elapsed_wrapped_connector_error_becomes_local_stop_before_next_bank(monkeypatch,caplog):
    clock=[1.0];calls=[]
    monkeypatch.setattr(service.time,'monotonic',lambda:clock[0])
    def first(req,timeout):
        calls.append('bankone');assert 0<timeout<=20;clock[0]+=21
        return Response(req,envelope('bankone','configurations'))
    def forbidden(req,timeout):raise AssertionError('late next-bank dispatch')
    configure(monkeypatch,{'bankone':first,'banktwo':forbidden})
    with pytest.raises(service._ConfigurationHydrationStopped) as caught:service.ensure_catalog_hydration(json.dumps(request()))
    assert caught.value.reason=='elapsed' and calls==['bankone']
    assert_no_persistence()
    assert 'stage=provider_resolution outcome=failed' not in caplog.text
    assert 'stop_reason=elapsed' in caplog.text


def test_genuine_upstream_failure_with_remaining_budget_keeps_supplier_diagnostic(monkeypatch,caplog):
    calls=[]
    def unavailable(req,timeout):calls.append('bankone');raise URLError('SECRET-FIXTURE-SENTINEL')
    def usable(req,timeout):calls.append('banktwo');return Response(req,envelope('banktwo','configurations'))
    configure(monkeypatch,{'bankone':unavailable,'banktwo':usable})
    result=service.ensure_catalog_hydration(json.dumps(request()))
    assert result['complete'] is False and calls==['bankone','banktwo']
    assert 'provider=bankone stage=provider_resolution outcome=failed error_type=SourceConnectorError' in caplog.text
    assert 'SECRET-FIXTURE-SENTINEL' not in caplog.text
    assert service._persist_hydration_scope.call_args.args[1].complete is False


def test_rate_limit_stops_without_retry_or_second_bank(monkeypatch,caplog):
    calls=[]
    def limited(req,timeout):calls.append('bankone');return Response(req,{},429)
    def forbidden(req,timeout):raise AssertionError('rate-limit retry storm')
    configure(monkeypatch,{'bankone':limited,'banktwo':forbidden})
    with pytest.raises(service._ConfigurationHydrationStopped) as caught:service.ensure_catalog_hydration(json.dumps(request()))
    assert caught.value.reason=='rate_limited' and calls==['bankone']
    assert_no_persistence()
    assert 'stop_reason=rate_limited' in caplog.text
    assert 'stage=provider_resolution outcome=failed' not in caplog.text


def test_configuration_failures_reuse_incomplete_ttl(monkeypatch):
    clock = [1.0]
    calls = []

    def opener(req, timeout):
        calls.append(req)
        if len(calls) == 1:
            return Response(req, {}, 429)
        return Response(req, envelope('bankone', 'configurations'))

    monkeypatch.setattr(service.time, "monotonic", lambda: clock[0])
    configure(monkeypatch, {'bankone': opener})
    body = json.dumps(request())

    with pytest.raises(service._ConfigurationHydrationStopped) as caught:
        service.ensure_catalog_hydration(body)
    assert caught.value.reason == 'rate_limited'
    clock[0] += service._HYDRATION_INCOMPLETE_TTL_SECONDS - 1
    assert service.ensure_catalog_hydration(body)['complete'] is False
    assert len(calls) == 1

    clock[0] += 2
    assert service.ensure_catalog_hydration(body)['complete'] is True
    assert len(calls) == 2


@pytest.mark.parametrize('failure', ['rows', 'coverage'])
def test_complete_configuration_results_require_durable_persistence_for_long_cache(monkeypatch, failure):
    clock = [1.0]
    monkeypatch.setattr(service.time, "monotonic", lambda: clock[0])
    provider = Mock(return_value={"complete": True, "rows": [
        {"year": 2024, "make": "Acura", "model": "Integra", "region": "US", "engine": "1.5L"},
    ]})
    monkeypatch.setattr(service, "_configured_catalog_providers", lambda **kwargs: (provider,))
    if failure == 'rows':
        service._persist_resolved_catalog_rows.side_effect = [{"status": "disabled"}, {"status": "persisted"}]
    else:
        service._persist_hydration_scope.side_effect = [{"status": "not_complete"}, {"status": "persisted"}]
    body = json.dumps(request())

    result = service.ensure_catalog_hydration(body)
    assert result['complete'] is True and result['missing_scopes'] == []
    assert len(result['rows']) == 1
    assert result['coverage']['status'] == 'not_complete'
    if failure == 'rows':
        service._persist_hydration_scope.assert_not_called()
    assert service.ensure_catalog_hydration(body) == result and provider.call_count == 1

    clock[0] += service._HYDRATION_INCOMPLETE_TTL_SECONDS + 1
    durable = service.ensure_catalog_hydration(body)
    assert durable['complete'] is True and durable['coverage']['status'] == 'persisted'
    assert provider.call_count == 2
    clock[0] += service._HYDRATION_INCOMPLETE_TTL_SECONDS + 1
    assert service.ensure_catalog_hydration(body) == durable and provider.call_count == 2


def test_configuration_coverage_commit_error_allows_retry(monkeypatch):
    clock = [1.0]
    monkeypatch.setattr(service.time, "monotonic", lambda: clock[0])
    provider = Mock(return_value={"complete": True, "rows": []})
    monkeypatch.setattr(service, "_configured_catalog_providers", lambda **kwargs: (provider,))
    service._persist_hydration_scope.side_effect = [OSError("coverage commit failed"), {"status": "persisted"}]
    body = json.dumps(request())

    with pytest.raises(OSError, match="coverage commit failed"):
        service.ensure_catalog_hydration(body)
    assert service.ensure_catalog_hydration(body)['complete'] is False and provider.call_count == 1

    clock[0] += service._HYDRATION_INCOMPLETE_TTL_SECONDS + 1
    assert service.ensure_catalog_hydration(body)['complete'] is True
    assert provider.call_count == 2


def test_configuration_progress_uses_budget_before_next_provider(monkeypatch):
    clock = [1.0]
    monkeypatch.setattr(service.time, "monotonic", lambda: clock[0])
    first = Mock(return_value={"complete": True, "rows": [
        {"year": 2024, "make": "Acura", "model": "Integra", "region": "US", "engine": "1.5L"},
    ], "provenance": [{"provider": "bankone", "source_uri": "fixture://configurations"}]})
    second = Mock(side_effect=AssertionError("second provider dispatched after the budget"))
    monkeypatch.setattr(service, "_configured_catalog_providers", lambda **kwargs: (first, second))

    def persist(*args, **kwargs):
        clock[0] += 21
        return {"status": "persisted"}

    service._persist_resolved_catalog_rows.side_effect = persist
    with pytest.raises(service._ConfigurationHydrationStopped) as stopped:
        service.ensure_catalog_hydration(json.dumps(request()))
    assert stopped.value.reason == 'elapsed'
    first.assert_called_once()
    second.assert_not_called()
    service._persist_resolved_catalog_rows.assert_called_once()
    service._persist_hydration_scope.assert_not_called()


def test_cancellation_after_response_stops_before_next_dispatch(monkeypatch):
    control=service._ConfigurationHydrationControl();calls=[]
    monkeypatch.setattr(service,'_ConfigurationHydrationControl',lambda:control)
    def first(req,timeout):
        calls.append('bankone');control.cancelled.set()
        return Response(req,envelope('bankone','configurations',complete=False,cursor='next'))
    configure(monkeypatch,{'bankone':first})
    with pytest.raises(service._ConfigurationHydrationStopped) as caught:service.ensure_catalog_hydration(json.dumps(request()))
    assert caught.value.reason=='cancelled' and calls==['bankone']
    assert_no_persistence()


def test_elapsed_before_first_attempt_dispatches_nothing(monkeypatch):
    control=service._ConfigurationHydrationControl();control.deadline=0
    monkeypatch.setattr(service,'_ConfigurationHydrationControl',lambda:control)
    client=SimpleNamespace(provider='bankone',catalog=Mock(side_effect=AssertionError('late dispatch')))
    monkeypatch.setattr('autodata_ingestion.source_connector_client.source_connector_registry',lambda:{'bankone':client})
    with pytest.raises(service._ConfigurationHydrationStopped):service.ensure_catalog_hydration(json.dumps(request()))
    client.catalog.assert_not_called();assert_no_persistence()


def test_configuration_control_does_not_use_selector_global_six_second_floor(monkeypatch):
    monkeypatch.setattr(service,'_DEEPEN_NEXT_DISPATCH',10**20)
    control=service._ConfigurationHydrationControl()
    for _ in range(12):assert 0<control.before_request()<=20
    with pytest.raises(service._ConfigurationHydrationStopped) as caught:control.before_request()
    assert caught.value.reason=='request_limit' and service._DEEPEN_NEXT_DISPATCH==10**20


@pytest.mark.parametrize('scope',['years','makes','models'])
def test_other_selector_scope_provider_wiring_unchanged(monkeypatch,scope):
    monkeypatch.setattr(service,'_ConfigurationHydrationControl',Mock(side_effect=AssertionError('other scope got config budget')))
    providers=Mock(return_value=());monkeypatch.setattr(service,'_configured_catalog_providers',providers)
    result=service.ensure_catalog_hydration(json.dumps({**request(scope),'scope':scope}))
    assert result['complete'] is False;providers.assert_called_once_with()


@pytest.mark.parametrize('scope',['article','articles'])
def test_article_lifecycle_path_unchanged(monkeypatch,scope):
    monkeypatch.setattr(service,'_ConfigurationHydrationControl',Mock(side_effect=AssertionError('article got config budget')))
    lifecycle=Mock(return_value={'status':'fixture-lifecycle'});monkeypatch.setattr(service,'_ensure_lifecycle_catalog',lifecycle)
    req={**request(scope),'scope':scope}
    assert service.ensure_catalog_hydration(json.dumps(req))=={'status':'fixture-lifecycle'}
    lifecycle.assert_called_once_with(req)


def test_complete_cache_does_not_start_budget_or_call_provider(monkeypatch,caplog):
    clock = [1.0]
    monkeypatch.setattr(service.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(service,'_ConfigurationHydrationControl',Mock(side_effect=AssertionError('complete cache started budget')))
    req={**request(),'cache':{'complete':True,'rows':[]}}
    result = service.ensure_catalog_hydration(json.dumps(req))
    assert result['complete'] is True and result['status'] == 'cache_hit'
    clock[0] += service._HYDRATION_INCOMPLETE_TTL_SECONDS + 1
    assert service.ensure_catalog_hydration(json.dumps(request())) == result
    assert 'catalog configuration budget ' not in caplog.text


def test_budget_logs_allowlisted_fields_without_selector_or_exception_text(monkeypatch,caplog):
    control=service._ConfigurationHydrationControl();control.cancelled.set()
    monkeypatch.setattr(service,'_ConfigurationHydrationControl',lambda:control)
    monkeypatch.setattr('autodata_ingestion.source_connector_client.source_connector_registry',lambda:{'bankone':SimpleNamespace(provider='bankone')})
    req={**request(),'make':'SECRET-MAKE-SENTINEL','model':'SECRET-MODEL-SENTINEL'}
    with pytest.raises(service._ConfigurationHydrationStopped):service.ensure_catalog_hydration(json.dumps(req))
    assert 'SECRET-' not in caplog.text
    assert 'scope_hash=' in caplog.text and 'state=finished' in caplog.text and 'stop_reason=cancelled' in caplog.text


def test_deadline_after_row_persistence_cannot_write_complete_coverage(monkeypatch,caplog):
    clock=[1.0];monkeypatch.setattr(service.time,'monotonic',lambda:clock[0])
    configure(monkeypatch,{'bankone':lambda req,timeout:Response(req,envelope('bankone','configurations'))})
    def persist(*args,**kwargs):clock[0]+=21;return {'status':'persisted'}
    service._persist_resolved_catalog_rows.side_effect=persist
    with pytest.raises(service._ConfigurationHydrationStopped) as caught:service.ensure_catalog_hydration(json.dumps(request()))
    assert caught.value.reason=='elapsed'
    assert 'stage=coverage_persistence outcome=incomplete' in caplog.text
    assert 'stage=provider_resolution outcome=incomplete' not in caplog.text
    service._persist_resolved_catalog_rows.assert_called_once()
    service._persist_hydration_scope.assert_not_called()
    assert service._HYDRATION_RESULTS["budget-fixture"][1]["complete"] is False


def test_truthful_committed_scope_is_not_relabelled_after_deadline(monkeypatch):
    clock=[1.0];monkeypatch.setattr(service.time,'monotonic',lambda:clock[0])
    configure(monkeypatch,{'bankone':lambda req,timeout:Response(req,envelope('bankone','configurations'))})
    def commit(req,result):
        assert result.complete;clock[0]+=21;return {'status':'persisted'}
    service._persist_hydration_scope.side_effect=commit
    result=service.ensure_catalog_hydration(json.dumps(request()))
    assert result['complete'] is True and result['coverage']['status']=='persisted'
    assert next(iter(service._HYDRATION_RESULTS.values()))[1]['complete'] is True


def test_budget_logging_failure_cannot_change_success(monkeypatch):
    configure(monkeypatch,{'bankone':lambda req,timeout:Response(req,envelope('bankone','configurations'))})
    monkeypatch.setattr(service._LOG,'warning',Mock(side_effect=RuntimeError('SECRET-LOG-SENTINEL')))
    assert service.ensure_catalog_hydration(json.dumps(request()))['complete'] is True
    service._persist_hydration_scope.assert_called_once()


def test_http_budget_stop_is_generic_502_and_never_false_complete(monkeypatch):
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from urllib.error import HTTPError
    from urllib.request import Request,build_opener,ProxyHandler
    from autodata_ingestion.http_service import make_handler
    control=service._ConfigurationHydrationControl();control.cancelled.set()
    monkeypatch.setattr(service,'_ConfigurationHydrationControl',lambda:control)
    monkeypatch.setattr('autodata_ingestion.source_connector_client.source_connector_registry',lambda:{'bankone':SimpleNamespace(provider='bankone')})
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler('synthetic-internal'))
    thread=Thread(target=lambda:server.serve_forever(poll_interval=.02),daemon=True);thread.start()
    req=Request(f'http://127.0.0.1:{server.server_port}/v1/catalog/ensure',data=json.dumps(request()).encode(),headers={'Content-Type':'application/json','X-Autodata-Internal-Token':'synthetic-internal'},method='POST')
    try:
        with pytest.raises(HTTPError) as caught:build_opener(ProxyHandler({})).open(req,timeout=2)
        assert caught.value.code==502
        assert json.loads(caught.value.read())=={'error':'ingestion dependency failed'}
        assert_no_persistence()
    finally:
        server.shutdown();server.server_close();thread.join(1);assert not thread.is_alive()


def test_configuration_body_deadline_closes_trickled_transport_and_stops_next_bank(monkeypatch,caplog):
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    from threading import Event,Thread
    from urllib.request import build_opener,ProxyHandler
    import time
    stopped=Event();handler_finished=Event();calls=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append('bankone')
            body=json.dumps(envelope('bankone','configurations')).encode()+b' '*4096
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers()
            try:
                for offset in range(0,len(body),8):
                    self.wfile.write(body[offset:offset+8]);self.wfile.flush()
                    if stopped.wait(.04):break
            except (BrokenPipeError,ConnectionResetError):pass
            finally:handler_finished.set()
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=lambda:server.serve_forever(poll_interval=.02),daemon=True);thread.start()
    control=service._ConfigurationHydrationControl();control.deadline=time.monotonic()+.25
    monkeypatch.setattr(service,'_ConfigurationHydrationControl',lambda:control)
    first=SourceConnectorClient(f'http://127.0.0.1:{server.server_port}',provider='bankone',opener=build_opener(ProxyHandler({})).open)
    second=SimpleNamespace(provider='banktwo',catalog=Mock(side_effect=AssertionError('late bank dispatch')))
    monkeypatch.setattr('autodata_ingestion.source_connector_client.source_connector_registry',lambda:{'bankone':first,'banktwo':second})
    try:
        started=time.monotonic()
        with pytest.raises(service._ConfigurationHydrationStopped) as caught:service.ensure_catalog_hydration(json.dumps(request()))
        assert time.monotonic()-started<2 and caught.value.reason=='elapsed'
        assert calls==['bankone'];second.catalog.assert_not_called();assert_no_persistence()
        assert 'stage=provider_resolution outcome=failed' not in caplog.text
    finally:
        stopped.set();server.shutdown();server.server_close();thread.join(1)
        assert not thread.is_alive() and handler_finished.wait(.5)
