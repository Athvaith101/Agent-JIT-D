import pytest

from jitd import llm as llm_mod
from jitd.compiler import compile_workflow
from jitd.executor import Executor
from jitd.fixtures import make_truth
from jitd.meter import ModelMeter
from jitd.oracle import entry_matches, expected_ledger
from jitd.schemas import InvoiceResp, PaymentsResp
from jitd.services import MockServices

AS_OF = "2026-10-16T01:00:00Z"


@pytest.fixture(scope="module")
def manifest():
    return compile_workflow()[0]


def run(manifest, behavior="clean", **kw):
    t = make_truth("rt", kw.pop("idx", 3), "post", **kw)
    s = MockServices([t], behavior)
    return Executor(s).run(manifest, {"invoice_id": t.invoice_id, "as_of": AS_OF}), t, s


def test_clean_replay_matches_oracle_with_zero_model_calls(manifest, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a model was called during replay")
    monkeypatch.setattr(llm_mod.NebiusClient, "complete", boom)
    meter = ModelMeter()
    t = make_truth("rt", 1, "post")
    r = Executor(MockServices([t]), meter).run(manifest, {"invoice_id": t.invoice_id, "as_of": AS_OF})
    assert r.outcome == "posted" and entry_matches(r.posted_entry(), expected_ledger(t))
    assert r.model_calls == 0 and meter.snapshot()["replay_model_calls"] == 0 and meter.snapshot()["total_model_calls"] == 0


def test_executor_has_no_model_handle():
    import inspect
    from jitd import executor
    assert "llm" not in inspect.signature(executor.Executor.__init__).parameters
    src = inspect.getsource(executor)
    assert "openai" not in src and "NebiusClient" not in src and "complete(" not in src


@pytest.mark.parametrize("beh,kw", [("unit_cents", {}), ("unit_mills", {})])
def test_silent_unit_drift_passes_schema_but_halts_before_posting(manifest, beh, kw):
    t = make_truth("rt", 3, "post")
    s = MockServices([t], beh)
    InvoiceResp.model_validate(s.invoice_get(t.invoice_id))
    PaymentsResp.model_validate(s.payment_list(t.invoice_id))              # the schema alone cannot see the drift
    r = Executor(s).run(manifest, {"invoice_id": t.invoice_id, "as_of": AS_OF})
    assert r.outcome == "halted" and r.halt["contract"] == "payment-matches-invoice"
    assert s.ledger == [] and s.calls["ledger.post"] == 0                    # no downstream side effect
    assert [x["status"] for x in r.steps if x["id"] == "post_ledger"] == ["skipped"]


def test_truncation_halts_at_the_fetch_boundary(manifest):
    r, t, s = run(manifest, "truncation", installments=4)
    assert r.outcome == "halted" and r.halt["contract"] == "mined-payments-complete" and r.halt["step"] == "fetch_payments"
    assert s.ledger == []


def test_malformed_response_is_a_schema_halt(manifest):
    r, t, s = run(manifest, "malformed")
    assert r.outcome == "halted" and r.halt["reason"] == "schema_invalid" and s.ledger == []


def test_cosmetic_change_is_not_blocked(manifest):
    for i in range(20):
        r, t, s = run(manifest, "cosmetic", idx=i)
        if r.flagged:                                                         # mined-range tail cases are warnings, never halts
            assert r.outcome == "held"
            continue
        assert r.outcome == "posted" and entry_matches(r.posted_entry(), expected_ledger(t))


def test_consistent_scale_is_held_not_posted_when_magnitude_is_off(manifest):
    r, t, s = run(manifest, "consistent_scale", idx=5)
    assert r.outcome in ("held", "posted")
    if r.outcome == "held":
        assert s.ledger[0]["disposition"] == "held" and not entry_matches(r.posted_entry(), expected_ledger(t))


def test_big_invoice_is_held_for_review(manifest):
    r, t, s = run(manifest, "clean", big=True)
    assert r.outcome == "held" and r.flagged


def test_short_payment_halts(manifest):
    r, t, s = run(manifest, "clean", short=True)
    assert r.outcome == "halted" and expected_ledger(t) is None and s.ledger == []


def test_crash_is_visible_when_checks_are_off(manifest):
    t = make_truth("rt", 3, "post")
    s = MockServices([t], "malformed")
    r = Executor(s, contracts_enabled=False, schema_enabled=False).run(manifest, {"invoice_id": t.invoice_id, "as_of": AS_OF})
    assert r.outcome == "error"


def test_unknown_invoice_is_an_error_not_a_post(manifest):
    r = Executor(MockServices([])).run(manifest, {"invoice_id": "nope", "as_of": AS_OF})
    assert r.outcome == "error"


def test_invalid_manifest_never_runs(manifest):
    bad = manifest.clone()
    bad.steps[0].operation = "shell"
    s = MockServices([])
    r = Executor(s).run(bad, {"invoice_id": "x", "as_of": AS_OF})
    assert r.outcome == "error" and r.halt["reason"] == "invalid manifest"


def test_events_are_emitted_in_order(manifest):
    ev = []
    t = make_truth("rt", 1, "post")
    Executor(MockServices([t]), emit=ev.append).run(manifest, {"invoice_id": t.invoice_id, "as_of": AS_OF})
    types = [e["type"] for e in ev]
    assert types[0] == "run_started" and types[-1] == "run_finished" and types.index("ledger_posted") < len(types) - 1
    assert "contract_result" in types and all(e["run_id"] == ev[0]["run_id"] for e in ev)


def test_meter_phases():
    m = ModelMeter()
    m.record("compile", 10)
    m.record("repair", 5)
    s = m.snapshot()
    assert s["compile_model_calls"] == 1 and s["repair_model_calls"] == 1 and s["replay_model_calls"] == 0 and s["total_tokens"] == 15
    with pytest.raises(ValueError):
        m.record("nope")
