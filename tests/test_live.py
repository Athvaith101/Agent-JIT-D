import json

from jitd import live
from jitd.compiler import golden_plan


class Fake:
    model = "fake-model"

    def __init__(self, meter):
        self.meter, self.latency_s = meter, [0.01]

    def complete(self, phase, system, user, max_tokens=900):
        self.meter.record(phase, 5)
        if phase == "compile" and "ping" not in user:
            return json.dumps({"steps": golden_plan()["steps"]})
        if phase == "repair":
            return "I cannot help: sk-LEAKCHECK0123456789abcdef"      # unusable: must fall back, and must not leak
        return "OK"


def test_live_harness_records_everything_and_labels_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "sk-LEAKCHECK0123456789abcdef")
    ev = live.collect(lambda m: Fake(m), "fake-model", compiles=1)
    assert ev["smoke"]["ok"] and ev["compiles"][0]["used_model_plan"] and ev["compiles"][0]["manifest"]["steps"]
    assert len(ev["repairs"]) == 3
    for r in ev["repairs"]:
        assert r.get("run_id") and r["outcome"] in ("halted", "held"), r
        assert r["nemotron_proposal_accepted"] is False
    blob = json.dumps(ev) + live.to_markdown(ev)
    assert "LEAKCHECK" not in blob
    assert "deterministic fallback" in live.to_markdown(ev) or "fallback_accepted" in live.to_markdown(ev)


def test_smoke_failure_is_recorded_not_raised():
    class Boom:
        def __init__(self, m): pass
        def complete(self, *a, **k): raise RuntimeError("down")
    ev = live.collect(lambda m: Boom(m), "x")
    assert ev["smoke"]["ok"] is False and not ev["compiles"]
