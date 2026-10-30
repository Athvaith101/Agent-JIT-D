import json
import types

import pytest

from jitd.compiler import compile_workflow, golden_plan
from jitd.llm import NebiusClient, extract_json, sanitize
from jitd.meter import ModelMeter


class Scripted:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self.create))

    def create(self, **kw):
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        m = types.SimpleNamespace(content=r)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=m)], usage=types.SimpleNamespace(total_tokens=42))


def client(*replies, meter=None):
    return NebiusClient(meter=meter, model="m", client=Scripted(*replies))


def test_valid_model_plan_is_accepted_and_counted():
    meter = ModelMeter()
    m, rep = compile_workflow(client(json.dumps({"steps": golden_plan()["steps"]}), meter=meter), meter, n_golden=40)
    assert rep["plan_source"].startswith("nemotron") and rep["model"] == "m" and not rep["rejections"]
    assert meter.snapshot()["compile_model_calls"] == 1 and m.meta["compile_model_calls"] == 1 and meter.snapshot()["replay_model_calls"] == 0


def test_fenced_json_reply_is_parsed():
    meter = ModelMeter()
    reply = "Here is the plan:\n```json\n" + json.dumps({"steps": golden_plan()["steps"]}) + "\n```"
    _, rep = compile_workflow(client(reply, meter=meter), meter, n_golden=30)
    assert rep["plan_source"].startswith("nemotron")


def test_plan_with_unknown_operation_is_rejected_then_fallback():
    plan = golden_plan()["steps"]
    plan[3]["operation"] = "run_python"
    meter = ModelMeter()
    m, rep = compile_workflow(client(json.dumps({"steps": plan}), json.dumps({"steps": plan}), meter=meter), meter, n_golden=30)
    assert len(rep["rejections"]) == 2 and "fallback" in rep["plan_source"] and any("allowlisted" in p for r in rep["rejections"] for p in r["problems"])
    assert m.steps[3].operation == "sum_money"


def test_plan_that_disagrees_with_the_oracle_is_rejected():
    plan = golden_plan()["steps"]
    plan[3]["inputs"]["amounts"] = "$fetch_payments.payments"                 # sums raw objects: wrong wiring, would crash or mis-sum
    meter = ModelMeter()
    _, rep = compile_workflow(client(json.dumps({"steps": plan}), json.dumps({"steps": plan}), meter=meter), meter, n_golden=30)
    assert "fallback" in rep["plan_source"]


def test_plan_missing_a_required_operation_is_rejected():
    plan = [s for s in golden_plan()["steps"] if s["operation"] != "reconcile_amounts"]
    plan[-1]["inputs"]["status"] = "$classify_status"
    meter = ModelMeter()
    _, rep = compile_workflow(client(json.dumps({"steps": plan}), json.dumps({"steps": plan}), meter=meter), meter, n_golden=30)
    assert "fallback" in rep["plan_source"]


@pytest.mark.parametrize("err", [RuntimeError("429 rate limited"), TimeoutError("timeout"), ValueError("500")])
def test_model_errors_fall_back_and_never_leak_the_key(monkeypatch, err):
    monkeypatch.setenv("NEBIUS_API_KEY", "sk-SECRET-abcdefghijklmnop1234")
    err.args = (str(err) + " key=sk-SECRET-abcdefghijklmnop1234",)
    meter = ModelMeter()
    m, rep = compile_workflow(client(err, err, meter=meter), meter, n_golden=30)
    assert "fallback" in rep["plan_source"] and "sk-SECRET" not in json.dumps(rep)


def test_malformed_json_reply_falls_back():
    meter = ModelMeter()
    _, rep = compile_workflow(client("not json at all", "{broken", meter=meter), meter, n_golden=30)
    assert "fallback" in rep["plan_source"] and len(rep["rejections"]) == 2


def test_extract_json_edge_cases():
    assert extract_json('x {"a": {"b": "}"}} y') == {"a": {"b": "}"}}
    for bad in ("", "no braces", '{"a": 1'):
        with pytest.raises(ValueError):
            extract_json(bad)


def test_sanitize_redacts_the_configured_key(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "super-secret-value-xyz")
    assert "super-secret" not in sanitize(RuntimeError("boom super-secret-value-xyz"))


def test_mined_contracts_come_from_golden_runs_not_constants():
    m, rep = compile_workflow(n_golden=40)
    kinds = {c["id"]: c["kind"] for c in m.contracts}
    assert kinds["mined-payment-amount-range"] == "mined" and kinds["invoice-arithmetic"] == "declared"
    assert m.meta["mined_from_golden_runs"] == 40
