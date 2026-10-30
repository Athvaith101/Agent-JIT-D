import json
import threading
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
import httpx
import pytest
from jitd.fixtures import make_truth
from jitd.services import MockServices
from jitd.http_connector import HTTPProvider, HTTPAuthority, ConnectorError, ReadClient, origin
from jitd.shadow import shadow_run


@contextmanager
def endpoint(callback):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed=urlsplit(self.path)
            status, value, headers=callback(parsed.path,parse_qs(parsed.query),self.headers)
            raw=value if isinstance(value,bytes) else json.dumps(value,default=str).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)))
            for k,v in headers.items(): self.send_header(k,v)
            self.end_headers();self.wfile.write(raw)
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try: yield 'http://127.0.0.1:'+str(server.server_port)
    finally: server.shutdown();server.server_close();worker.join()


@pytest.mark.parametrize('fault',['none','changed_snapshot','cycle','duplicate','missing_cursor','wrong_identity',
                                  'stale','wrong_amount','wrong_source','wrong_authority_invoice','bad_authority_snapshot',
                                  'unavailable','malformed','redirect'])
def test_socket_shadow(fault):
    t=make_truth('http',0); svc=MockServices([t]); seen=[]
    invoice=svc.invoice_get(t.invoice_id); payment=svc.payment_list(t.invoice_id)
    def provider(path,q,headers):
        seen.append(('provider',headers.get('Authorization')))
        snap='v1'
        if path=='/invoice':return 200,invoice,{'X-JITD-Snapshot':snap}
        page=dict(payment)
        if q.get('cursor')==['second']:
            page['payments']=[];page['next_cursor']=None
        else:page['next_cursor']='second'
        if fault=='changed_snapshot':snap='v2'
        if fault=='cycle':page['next_cursor']='second'
        if fault=='duplicate' and q.get('cursor'):page['payments']=payment['payments']
        if fault=='missing_cursor':page.pop('next_cursor')
        if fault=='wrong_identity':page['invoice_id']='other'
        return 200,page,{'X-JITD-Snapshot':snap}
    def authority(path,q,headers):
        seen.append(('authority',headers.get('Authorization')))
        row=dict(invoice_id=t.invoice_id,provider_snapshot='v1',source_id='finance-control',currency='USD',
                 observed_at=datetime.now(timezone.utc).isoformat(),invoice_total_usd=str(t.total),settled_total_usd=str(t.paid_total))
        if fault=='stale':row['observed_at']=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
        if fault=='wrong_amount':row['settled_total_usd']=str(t.paid_total+10)
        if fault=='wrong_source':row['source_id']='other'
        if fault=='wrong_authority_invoice':row['invoice_id']='other'
        if fault=='bad_authority_snapshot':row['provider_snapshot']='v2'
        if fault=='unavailable':return 503,{'error':'SECRET'},{}
        if fault=='malformed':return 200,b'bad SECRET',{}
        if fault=='redirect':return 302,{}, {'Location':'http://127.0.0.1:1/secret'}
        return 200,row,{}
    with endpoint(provider) as p, endpoint(authority) as a:
        pc=HTTPProvider(p,'provider-secret',allow_local_http=True)
        ac=HTTPAuthority(a,'authority-secret',allow_local_http=True)
        try:
            if fault in {'changed_snapshot','cycle','duplicate','missing_cursor','wrong_identity'}:
                with pytest.raises(ValueError):shadow_run(pc,ac,t.invoice_id,'2026-09-30T00:00:00Z','finance-control')
                assert ac.calls==0
            else:
                result=shadow_run(pc,ac,t.invoice_id,'2026-09-30T00:00:00Z','finance-control')
                assert (result['outcome']=='posted')==(fault=='none')
                assert result['external_writes']==0 and result['captured_pages']==2
                assert 'secret' not in json.dumps(result).lower()
                if fault=='none':assert all(x['status']=='VALID' for x in result['assumptions'])
        finally:pc.close();ac.close()
    assert all(token==('Bearer provider-secret' if role=='provider' else 'Bearer authority-secret') for role,token in seen)


def test_timeout_sanitized():
    def fail(request):raise httpx.ReadTimeout('secret-token',request=request)
    c=ReadClient('https://example.test',transport=httpx.MockTransport(fail))
    try:
        with pytest.raises(ConnectorError,match='Read request failed') as e:c.get('/invoice')
        assert 'secret-token' not in str(e.value)
    finally:c.close()


@pytest.mark.parametrize('url',['http://example.com','https://user:pass@example.com','https://example.com?token=x','file:///tmp/a'])
def test_unsafe_base_url(url):
    with pytest.raises(ConnectorError):origin(url)


def test_same_origin_disallowed():
    p=HTTPProvider('https://example.test');a=HTTPAuthority('https://example.test/authority')
    try:
        with pytest.raises(ConnectorError,match='origins'):shadow_run(p,a,'id','date','source')
        assert p.calls==a.calls==0
    finally:p.close();a.close()


def test_http_capture_respects_executor_page_limit():
    t=make_truth('limit',0);svc=MockServices([t]);seen=[]
    def serve(request):
        seen.append(request)
        if request.url.path=='/invoice':value=svc.invoice_get(t.invoice_id)
        else:
            value={'invoice_id':t.invoice_id,'payments':[],'next_cursor':str(len(seen))}
        return httpx.Response(200,json=value,headers={'X-JITD-Snapshot':'v1'})
    p=HTTPProvider('https://provider.test',transport=httpx.MockTransport(serve))
    try:
        with pytest.raises(ConnectorError,match='page limit'):p.capture(t.invoice_id,'2026-10-16T00:00:00Z')
        assert len(seen)==21  # One invoice plus twenty payment pages, no twenty-first payment read.
    finally:p.close()
