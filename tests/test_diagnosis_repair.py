import json
import os

import pytest

from jitd.bench import golden_regression
from jitd.compiler import compile_workflow
from jitd.diagnosis import diagnose
from jitd.executor import Executor
from jitd.fixtures import make_truth
from jitd.manifest import Manifest
from jitd.oracle import expected_ledger
from jitd.repair import RepairProposal, attempt_repair, check_allowlist, current_rules, validate_isolated
from jitd.services import MockServices, capture_case

AS_OF = "2026-10-16T01:00:00Z"
AS_OF2 = "2026-10-16T02:00:00Z"


@pytest.fixture(scope="module")
def manifest():
    return compile_workflow()[0]


@pytest.fixture(scope="module")
def regression():
    return golden_regression(20)


def episode(manifest, behavior, n=6, **kw):
    ts = [make_truth("dr", i, "post", **kw) for i in range(n)]
    s = MockServices(ts, behavior)
    r = Executor(s).run(manifest, {"invoice_id": ts[0].invoice_id, "as_of": AS_OF})
    return ts, s, r, diagnose(manifest, r)


@pytest.mark.parametrize("beh,kw,status,name,op", [
    ("unit_cents", {}, "localized", "unit_scale", "normalize_money"),
    ("unit_mills", {}, "localized", "unit_scale", "normalize_money"),
    ("truncation", {"installments": 4}, "localized", "truncated_pagination", "payment.list"),
    ("malformed", {}, "localized", "malformed_response", "payment.list"),
    ("clean", {"short": True}, "business_exception", "business_exception", None),
    ("consistent_scale", {}, "provider_wide", "provider_wide_scale_shift", "invoice.get+payment.list"),
])
def test_localization(manifest, beh, kw, status, name, op):
    _, _, r, d = episode(manifest, beh, **kw)
    assert r.outcome in ("halted", "held")
    assert d["status"] == status and d["top"]["name"] == name and d["top"]["op"] == op
    assert "probability" in d["score_note"]
    top = d["suspects"][0]
    assert top["score"] == sum(f["weight"] for f in top["features"] if f["met"])        # transparent, reproducible score


def test_detection_point_differs_from_responsible_step(manifest):
    _, _, r, d = episode(manifest, "unit_cents")
    assert d["detected_at"]["step"] == "reconcile" and d["top"]["step"] == "normalize_amount"


def test_repair_accepted_for_cents_mills_and_truncation(manifest, regression):
    for beh, kw in [("unit_cents", {}), ("unit_mills", {}), ("truncation", {"installments": 4})]:
        ts, s, r, d = episode(manifest, beh, **kw)
        out = attempt_repair(manifest, d, s, [(ts[0].invoice_id, AS_OF, expected_ledger(ts[0]))], regression,
                             fresh=[(t.invoice_id, AS_OF2, expected_ledger(t)) for t in ts[1:]], isolated=False)
        assert out["accepted"], (beh, out["proposals"])
        v = out["proposals"][-1]["validation"]["groups"]
        assert v["regression"]["passed"] == v["regression"]["n"] == len(regression) and v["drift_cases"]["passed"] == v["drift_cases"]["n"]
        new = Manifest.model_validate(out["candidate"])
        assert new.version == "1.0.1" and new.meta["repaired_from"] == "1.0.0"


def test_repaired_workflow_still_correct_on_pre_drift_data(manifest, regression):
    ts, s, r, d = episode(manifest, "unit_cents")
    out = attempt_repair(manifest, d, s, [(ts[0].invoice_id, AS_OF, expected_ledger(ts[0]))], regression, isolated=False)
    new = Manifest.model_validate(out["candidate"])
    gt = [make_truth("g2", i, "pre") for i in range(15)]
    gs = MockServices(gt, "clean")
    for t in gt:
        res = Executor(gs).run(new, {"invoice_id": t.invoice_id, "as_of": "2026-10-02T00:00:00Z"})
        assert res.outcome == "posted"


def test_wrong_repair_is_rejected_by_validation(manifest, regression):
    ts, s, r, d = episode(manifest, "unit_cents")
    bad = RepairProposal(op="normalize_money", param="rules", source="operator_override",
                         value=current_rules(manifest) + [{"divisor": 10, "effective_from": AS_OF}])
    out = attempt_repair(manifest, d, s, [(ts[0].invoice_id, AS_OF, expected_ledger(ts[0]))], regression, override=bad, isolated=False)
    assert not out["accepted"] and out["proposals"][0]["status"] == "rejected_by_validation"
    assert out["proposals"][0]["validation"]["groups"]["drift_cases"]["passed"] == 0


@pytest.mark.parametrize("p", [
    RepairProposal(op="post_ledger", param="status", value="paid"),
    RepairProposal(op="normalize_money", param="code", value="import os"),
    RepairProposal(op="payment.list", param="max_pages", value=500),
    RepairProposal(op="payment.list", param="max_pages", value="10"),
    RepairProposal(op="normalize_money", param="rules", value=[{"divisor": 3, "effective_from": None}]),
])
def test_allowlist_blocks_everything_else(p):
    assert check_allowlist(p)


def test_repair_must_append_exactly_one_rule(manifest, regression):
    ts, s, r, d = episode(manifest, "unit_cents")
    rewrite = RepairProposal(op="normalize_money", param="rules", source="operator_override", value=[{"divisor": 100, "effective_from": None}])
    out = attempt_repair(manifest, d, s, [(ts[0].invoice_id, AS_OF, None)], regression, override=rewrite, isolated=False)
    assert not out["accepted"] and out["proposals"][0]["status"] == "rejected_by_allowlist"


def test_no_repair_for_business_exception_provider_wide_or_malformed(manifest, regression):
    for beh, kw in [("clean", {"short": True}), ("consistent_scale", {}), ("malformed", {})]:
        ts, s, r, d = episode(manifest, beh, **kw)
        out = attempt_repair(manifest, d, s, [(ts[0].invoice_id, AS_OF, expected_ledger(ts[0]))], regression, isolated=False)
        assert not out["accepted"] and out["proposals"] == [] and "stays halted" in out["reason"]


def test_compound_fault_is_not_repaired(manifest, regression):
    ts, s, r, d = episode(manifest, "cents_truncation", installments=4)
    out = attempt_repair(manifest, d, s, [(ts[0].invoice_id, AS_OF, expected_ledger(ts[0]))], regression,
                         fresh=[(t.invoice_id, AS_OF2, expected_ledger(t)) for t in ts[1:]], isolated=False)
    assert not out["accepted"]


def test_noop_candidate_rejected(manifest, regression):
    ts, s, r, d = episode(manifest, "unit_cents")
    noop = RepairProposal(op="payment.list", param="max_pages", value=1, source="operator_override")
    out = attempt_repair(manifest, d, s, [(ts[0].invoice_id, AS_OF, None)], regression, override=noop, isolated=False)
    assert not out["accepted"]


def test_isolated_worker_matches_in_process_and_has_no_secrets(manifest, regression, monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "sk-SENTINEL-must-not-reach-worker-123456")
    ts, s, r, d = episode(manifest, "unit_cents")
    args = (manifest, d, s, [(ts[0].invoice_id, AS_OF, expected_ledger(ts[0]))], regression)
    a = attempt_repair(*args, isolated=True)
    b = attempt_repair(*args, isolated=False)
    assert a["accepted"] and b["accepted"]
    va, vb = a["proposals"][-1]["validation"], b["proposals"][-1]["validation"]
    assert va["isolated"] and va["groups"] == vb["groups"]
    assert not any("NEBIUS" in k or "KEY" in k for k in va["worker"]["env_keys"])
    assert "SENTINEL" not in json.dumps(va)


def test_isolated_worker_timeout_fails_closed(manifest):
    rep = validate_isolated({"manifest": manifest.model_dump(), "groups": {}}, timeout_s=0.001)
    assert rep["ok"] is False


def test_validation_requires_cases(manifest):
    from jitd.validation import run_validation
    assert run_validation({"manifest": manifest.model_dump(), "groups": {"x": []}})["ok"] is False


def test_model_proposal_is_validated_like_any_other(manifest, regression):
    class Liar:
        model = "fake"
        def complete(self, phase, system, user, max_tokens=0):
            return '```json\n{"op":"normalize_money","param":"rules","value":[{"divisor":1,"effective_from":null},{"divisor":10,"effective_from":"2026-10-16T01:00:00Z"}],"rationale":"trust me"}\n```'
    ts, s, r, d = episode(manifest, "unit_cents")
    out = attempt_repair(manifest, d, s, [(ts[0].invoice_id, AS_OF, expected_ledger(ts[0]))], regression, llm=Liar(), isolated=False)
    assert [p["source"] for p in out["proposals"]] == ["nemotron", "deterministic"]
    assert out["proposals"][0]["status"] == "rejected_by_validation" and out["proposals"][1]["status"] == "accepted"


def test_unusable_model_reply_falls_back_without_crashing(manifest, regression):
    class Junk:
        model = "fake"
        def complete(self, *a, **k):
            return "I think you should rewrite the function."
    ts, s, r, d = episode(manifest, "unit_cents")
    out = attempt_repair(manifest, d, s, [(ts[0].invoice_id, AS_OF, expected_ledger(ts[0]))], regression, llm=Junk(), isolated=False)
    assert out["proposals"][0]["status"] == "unusable" and out["accepted"]
