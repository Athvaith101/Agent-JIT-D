import json
from pathlib import Path
from fastapi.testclient import TestClient
from jitd.presentation_api import evidence_summary


def test_recorded_evidence_excludes_injected_clients_and_private_fields(tmp_path):
    evidence = tmp_path / 'evidence'; evidence.mkdir()
    base = {'kind':'jitd_live_evidence','model_id':'test-model','source_mode':'injected_client','compiles':[], 'repairs':[]}
    (evidence / 'live_fake.json').write_text(json.dumps(base))
    assert not evidence_summary(tmp_path)['available']
    base.update(source_mode='nebius_api', api_key='do-not-project-this', raw_output='private response')
    (evidence / 'live_real.json').write_text(json.dumps(base))
    value = evidence_summary(tmp_path)
    assert value['available'] and value['replay_only']
    assert 'do-not-project-this' not in json.dumps(value) and 'private response' not in json.dumps(value)
    assert len(value['records']) == 1


def test_demo_and_presentation_routes_are_read_only():
    from jitd.server import app
    with TestClient(app) as client:
        assert client.get('/demo').status_code == 200
        response = client.get('/api/presentation/evidence')
        assert response.status_code == 200 and response.json()['replay_only']
        csv = client.get('/api/presentation/usage.csv')
        assert csv.status_code == 200 and 'receipt_id,role,model_id' in csv.text
        assert client.get('/missing-page', headers={'Accept':'text/html'}).status_code == 404


def test_fonts_and_close_svg_are_bundled():
    root = Path(__file__).resolve().parent.parent
    for name in ('Geist-Variable.woff2','GeistMono-Variable.woff2'):
        assert (root/'web/assets/fonts'/name).read_bytes().startswith(b'wOF2')
    script = (root/'web/assets/refinements.js').read_text()
    assert 'viewBox="0 0 24 24"' in script
    assert '.showModal()' not in script
