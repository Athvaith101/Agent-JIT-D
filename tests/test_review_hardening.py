from fastapi.testclient import TestClient
from jitd import server
from jitd.stream_stats import summarize_streams


def test_tls_proxy_origin_and_cross_host():
    c=TestClient(server.app,base_url='http://demo.example')
    assert c.post('/api/workflow/pause',json={'paused':True},headers={'Origin':'https://demo.example'}).status_code==200
    assert c.post('/api/workflow/pause',json={'paused':False},headers={'Origin':'https://evil.example'}).status_code==403
    r=c.get('/');assert r.headers['x-frame-options']=='DENY' and "frame-ancestors 'none'" in r.headers['content-security-policy']
    server.LAB.pause(False)


def test_zero_stream_events_keep_nonzero_uncertainty():
    r=summarize_streams([0]*30)
    assert r['streams']==30 and r['stream_event_wilson_ci95'][1]>0
    assert len(r['per_stream_rates'])==30
