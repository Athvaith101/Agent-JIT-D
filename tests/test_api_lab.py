import json

import pytest
from fastapi.testclient import TestClient

from jitd import server
from jitd.lab import Lab, LabError

c = TestClient(server.app)


@pytest.fixture(autouse=True)
def fresh():
    server._hits.clear()
    server.LAB.reset()
    yield


def stream(path="/api/run/stream"):
    r = c.get(path)
    return [json.loads(l[6:]) for l in r.text.split("\n\n") if l.startswith("data:")]


def view(evs):
    return next(e["run"] for e in evs if e["type"] == "run_view")


def test_health_meta_state():
    assert c.get("/api/health").json()["status"] == "ok"
    m = c.get("/api/meta").json()
    assert m["mode"] == "SIMULATED SERVICES" and m["model_configured"] is False and len(m["scenarios"]) >= 9
    assert c.get("/api/state").json()["workflow"]["version"] == "1.0.0"


def test_run_stream_is_real_events_and_ends():
    evs = stream()
    types = [e["type"] for e in evs]
    assert types[0] == "run_started" and "run_view" in types and types[-1] == "stream_end"
    v = view(evs)
    assert v["outcome"] == "posted" and v["oracle_verdict"] == "correct_post" and v["meter"]["replay_model_calls"] == 0


def test_full_story_over_http():
    assert c.post("/api/lab/inject", json={"scenario": "unit_cents"}).status_code == 200
    v = view(stream())
    assert v["outcome"] == "halted"
    rid = v["run_id"]
    d = c.post(f"/api/runs/{rid}/diagnose").json()
    assert d["status"] == "localized" and d["top"]["step"] == "normalize_amount"
    bad = c.post(f"/api/runs/{rid}/repair", json={"mode": "wrong"}).json()
    assert bad["accepted"] is False
    ok = c.post(f"/api/runs/{rid}/repair", json={"mode": "auto"}).json()
    assert ok["accepted"] and ok["guard_id"] and c.get("/api/state").json()["workflow"]["version"] == "1.0.1"
    v2 = view(stream(f"/api/run/stream?invoice_id={v['inputs']['invoice_id']}"))
    assert v2["outcome"] == "posted" and v2["oracle_verdict"] == "correct_post"
    exp = c.get(f"/api/runs/{rid}/export")
    assert exp.status_code == 200 and exp.json()["schema"] == "jitd.export/1"


def test_illegal_transitions():
    v = view(stream())                                                          # a posted run
    assert c.post(f"/api/runs/{v['run_id']}/diagnose").status_code == 409
    assert c.post("/api/runs/run_unknown/diagnose").status_code == 404
    assert c.post("/api/lab/inject", json={"scenario": "nope"}).status_code == 400
    c.post("/api/lab/inject", json={"scenario": "unit_cents"})
    v = view(stream())
    c.post(f"/api/runs/{v['run_id']}/repair", json={"mode": "auto"})
    stale = c.post(f"/api/runs/{v['run_id']}/repair", json={"mode": "auto"})   # already repaired: this run used an older version
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_run"


def test_model_endpoints_fail_clearly_without_credentials():
    r = c.post("/api/lab/compile", json={"use_model": True})
    assert r.status_code == 400 and r.json()["error"]["code"] == "model_unavailable"
    c.post("/api/lab/inject", json={"scenario": "unit_cents"})
    v = view(stream())
    assert c.post(f"/api/runs/{v['run_id']}/repair", json={"mode": "model"}).status_code == 400


def test_input_validation():
    assert c.post("/api/runs/x/repair", json={"mode": "rm -rf"}).status_code == 422
    assert c.post("/api/lab/inject", json={"scenario": "../../etc"}).status_code == 422
    assert c.get("/api/runs/..%2f..%2fetc").status_code in (400, 404)
    assert c.get("/api/benchmarks/..%2f..%2fx").status_code in (400, 404)
    assert c.get("/api/run/stream", params={"invoice_id": "a b;c"}).status_code == 400


def test_unknown_invoice_returns_error_event():
    evs = stream("/api/run/stream?invoice_id=INV-nope")
    assert any(e["type"] == "error" and e["code"] == "unknown_invoice" for e in evs)


def test_rate_limit():
    got = [c.get("/api/health").status_code for _ in range(3)]
    assert got == [200] * 3
    server._hits.clear()
    codes = [c.post("/api/lab/inject", json={"scenario": "clean"}).status_code for _ in range(server.RATE[0] + 3)]
    assert codes[-1] == 429


def test_benchmark_endpoints_if_results_exist():
    lst = c.get("/api/benchmarks").json()["benchmarks"]
    if not lst:
        pytest.skip("no saved benchmark")
    d = c.get(f"/api/benchmarks/{lst[0]['id']}").json()
    assert d["cells"] and "caveats" in d["meta"] and c.get(f"/api/benchmarks/{lst[0]['id']}/csv").text.startswith("scenario,")


def test_responses_never_contain_keys(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "sk-LEAKCHECK-abcdefghijklmnop")
    blob = c.get("/api/meta").text + c.get("/api/state").text + "".join(json.dumps(e) for e in stream())
    assert "LEAKCHECK" not in blob


def test_guard_and_regression_persist_and_reload(tmp_path):
    lab = Lab(tmp_path)
    lab.inject("unit_cents")
    r = lab.run()
    lab.diagnose(r["run_id"])
    out = lab.repair(r["run_id"], "auto")
    assert out["accepted"]
    g = json.loads(next((tmp_path / "guards").glob("*.json")).read_text())
    assert g["decision"] == "accepted" and g["from_version"] == "1.0.0" and g["to_version"] == "1.0.1" and g["validation"]["ok"]
    reg = json.loads((tmp_path / "regression" / "invoice-reconciliation.json").read_text())["cases"]
    assert len(reg) > 20                                                        # golden + the confirmed drift cases
    assert (tmp_path / "workflows" / "invoice-reconciliation" / "1.0.1.json").exists()
    assert not list(tmp_path.rglob("*.tmp"))                                    # atomic writes leave no temp files


def test_second_drift_keeps_first_repair_working():
    lab = Lab(__import__("tempfile").mkdtemp())
    lab.inject("unit_cents")
    r = lab.run(); lab.diagnose(r["run_id"]); assert lab.repair(r["run_id"], "auto")["accepted"]
    lab.inject("unit_mills")
    r2 = lab.run(); assert r2["outcome"] == "halted"
    lab.diagnose(r2["run_id"]); out = lab.repair(r2["run_id"], "auto")
    assert out["accepted"] and lab.manifest.version == "1.0.2"
    rules = lab.manifest.step_for_op("normalize_money").params["rules"]
    assert [x["divisor"] for x in rules] == [1, 100, 1000]


def test_business_exception_is_never_repaired():
    lab = Lab(__import__("tempfile").mkdtemp())
    lab.inject("underpayment")
    r = lab.run(); assert r["outcome"] == "halted"
    d = lab.diagnose(r["run_id"]); assert d["status"] == "business_exception"
    out = lab.repair(r["run_id"], "auto")
    assert out["accepted"] is False and lab.manifest.version == "1.0.0"


def test_concurrent_repair_is_refused():
    lab = Lab(__import__("tempfile").mkdtemp())
    lab.inject("unit_cents"); r = lab.run(); lab.diagnose(r["run_id"])
    lab.repairing = True
    with pytest.raises(LabError) as e:
        lab.repair(r["run_id"], "auto")
    assert e.value.status == 409


def test_hard_case_is_honest_no_repair_and_reconciliation_blind():
    from jitd.lab import Lab
    import tempfile
    lab = Lab(tempfile.mkdtemp())
    for _ in range(3):
        lab.run()
    h = lab.hard_case(20)
    assert h["reconciliation_blind"] and h["repair_offered"] is False and h["n"] == 20
    assert all(r["arithmetic_ok"] and r["payment_match_ok"] for r in h["rows"])
    assert h["held"] + h["posted_wrong"] <= 20 and h["held"] >= 1
    assert h["posted_wrong"] >= 1, "small invoices should slip through the magnitude warning; if not, the doc claim is wrong"
    rid = next(r["run_id"] for r in h["rows"] if r["outcome"] == "held")
    rep = lab.repair(rid)
    assert rep["accepted"] is False
    assert lab.manifest.version == "1.0.0"


def test_hard_case_endpoint():
    from fastapi.testclient import TestClient
    from jitd.server import app
    c = TestClient(app)
    c.post("/api/lab/reset")
    r = c.post("/api/lab/hard-case?n=6")
    assert r.status_code == 200 and r.json()["repair_offered"] is False
