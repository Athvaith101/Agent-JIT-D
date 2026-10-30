import pytest

from jitd import llm
from jitd.llm import BudgetExceeded, NebiusClient
from jitd.meter import ModelMeter


class _Msg:
    content = "OK"


class _Choice:
    message = _Msg()


class _Usage:
    total_tokens = 7


class _Resp:
    choices = [_Choice()]
    usage = _Usage()


class _Fake:
    def __init__(self):
        self.calls = 0
        self.chat = self
        self.completions = self

    def create(self, **kw):
        self.calls += 1
        return _Resp()


def test_budget_blocks_before_any_provider_call(monkeypatch):
    monkeypatch.setenv("JITD_MAX_MODEL_CALLS", "2")
    fake, meter = _Fake(), ModelMeter()
    c = NebiusClient(meter=meter, model="m", client=fake)
    c.complete("compile", "s", "u")
    c.complete("compile", "s", "u")
    with pytest.raises(BudgetExceeded):
        c.complete("compile", "s", "u")
    assert fake.calls == 2                      # the third call never reached the provider
    assert meter.snapshot()["total_model_calls"] == 2
    assert llm.budget() == {"limit": 2, "used": 2, "remaining": 0}


def test_budget_zero_disables_all_calls(monkeypatch):
    monkeypatch.setenv("JITD_MAX_MODEL_CALLS", "0")
    fake = _Fake()
    with pytest.raises(BudgetExceeded):
        NebiusClient(model="m", client=fake).complete("compile", "s", "u")
    assert fake.calls == 0


def test_bad_env_value_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("JITD_MAX_MODEL_CALLS", "not-a-number")
    assert llm.budget_limit() == 300


def test_budget_is_reported_by_api():
    from fastapi.testclient import TestClient
    from jitd.server import app
    b = TestClient(app).get("/api/meta").json()["model_call_budget"]
    assert set(b) == {"limit", "used", "remaining"}


def test_exhausted_budget_falls_back_to_labelled_deterministic_plan(monkeypatch):
    from jitd.compiler import compile_workflow
    monkeypatch.setenv("JITD_MAX_MODEL_CALLS", "0")
    meter = ModelMeter()
    fake = _Fake()
    manifest, rep = compile_workflow(NebiusClient(meter=meter, model="m", client=fake), meter)
    assert fake.calls == 0
    assert not rep["plan_source"].startswith("nemotron")
    assert rep["rejections"]                      # the failure is recorded, not hidden
