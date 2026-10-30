"""Compile: a model-assisted plan is parsed into a typed manifest, validated against the op allowlist, executed on golden
fixtures against the independent oracle, then contracts are attached/mined. A plan that fails any step is rejected."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from . import contracts as C
from .assumptions import registry
from .executor import Executor
from .fixtures import golden_truths
from .llm import extract_json, sanitize
from .manifest import Manifest, validate_manifest
from .meter import ModelMeter
from .oracle import entry_matches, expected_ledger
from .ops import catalogue
from .services import MockServices

TASK = ("Reconcile one invoice. Fetch the invoice and its payments, normalize payment amounts to USD, sum them, recompute the "
        "invoice total from its line items, classify the provider status, reconcile the amounts, and post a ledger entry.")
REQUIRED_OPS = {"invoice.get", "payment.list", "normalize_money", "sum_money", "invoice_total", "provider_status", "reconcile_amounts", "post_ledger"}
GOLDEN_AS_OF = "2026-09-30T00:00:00Z"


def golden_plan() -> dict:
    return {"workflow_id": "invoice-reconciliation", "version": "1.0.0", "steps": [
        {"id": "fetch_invoice", "kind": "mock_api", "operation": "invoice.get", "inputs": {"invoice_id": "$input.invoice_id"}},
        {"id": "fetch_payments", "kind": "mock_api", "operation": "payment.list", "inputs": {"invoice_id": "$input.invoice_id"}, "params": {"max_pages": 1}},
        {"id": "normalize_amount", "kind": "transform", "operation": "normalize_money",
         "inputs": {"payments": "$fetch_payments.payments", "as_of": "$input.as_of"}, "params": {"rules": [{"divisor": 1, "effective_from": None}]}},
        {"id": "sum_payments", "kind": "transform", "operation": "sum_money", "inputs": {"amounts": "$normalize_amount"}},
        {"id": "expected_total", "kind": "transform", "operation": "invoice_total", "inputs": {"invoice": "$fetch_invoice"}},
        {"id": "classify_status", "kind": "transform", "operation": "provider_status", "inputs": {"payments": "$fetch_payments.payments"}},
        {"id": "reconcile", "kind": "check", "operation": "reconcile_amounts",
         "inputs": {"invoice_total": "$fetch_invoice.total", "computed_total": "$expected_total", "paid_total": "$sum_payments", "provider_status": "$classify_status"}},
        {"id": "post_ledger", "kind": "sink", "operation": "post_ledger",
         "inputs": {"invoice_id": "$input.invoice_id", "paid_total": "$sum_payments", "invoice_total": "$fetch_invoice.total", "status": "$classify_status"}},
    ]}


PLAN_SYSTEM = """You compile a workflow plan as strict JSON. Output ONLY a JSON object: {"steps":[{"id","kind","operation","inputs","params"}]}.
Rules: use only operations from the catalogue; every input of an operation must be supplied exactly as listed; an input is a reference string:
"$input.invoice_id", "$input.as_of", or "$<earlier_step_id>" or "$<earlier_step_id>.<field>" (dotted fields, "[*]" to map a list). Steps are ordered; a step
may only reference earlier steps. Step ids are lowercase_with_underscores. Use each operation once. No prose."""


def propose_plan_with_model(llm) -> dict:
    user = f"Task: {TASK}\n\nOperation catalogue:\n{json.dumps(catalogue(), indent=1)}"
    d = extract_json(llm.complete("compile", PLAN_SYSTEM, user, max_tokens=1400))
    if not isinstance(d, dict) or not isinstance(d.get("steps"), list):
        raise ValueError("reply has no steps list")
    return {"workflow_id": "invoice-reconciliation", "version": "1.0.0", "steps": d["steps"]}


def _golden_cases(n: int):
    truths = golden_truths(n)
    return truths, MockServices(truths, "clean")


def run_golden(manifest: Manifest, n: int = 400):
    """Run on golden fixtures. Returns (values_per_run, mismatches vs oracle)."""
    truths, svc = _golden_cases(n)
    ex = Executor(svc, contracts_enabled=False)
    vals, bad = [], []
    for t in truths:
        r = ex.run(manifest, {"invoice_id": t.invoice_id, "as_of": GOLDEN_AS_OF})
        if r.outcome != "posted" and r.outcome != "held" or not entry_matches(r.ledger_entry, expected_ledger(t)):
            bad.append(t.invoice_id)
        vals.append(r.values)
    return vals, bad


def compile_workflow(llm=None, meter: ModelMeter | None = None, n_golden: int = 400) -> tuple[Manifest, dict]:
    """Returns (manifest, report). report says who produced the plan and why a model plan was rejected, if it was."""
    report = {"plan_source": "deterministic (no model configured)", "model": None, "rejections": [], "golden_runs": n_golden}
    plan = None
    if llm is not None:
        report["model"] = getattr(llm, "model", None)
        for attempt in (1, 2):
            try:
                cand = propose_plan_with_model(llm)
                m = Manifest.model_validate(cand)
                problems = validate_manifest(m)
                if not problems and {s.operation for s in m.steps} != REQUIRED_OPS:
                    problems = [f"plan must use exactly these operations: {sorted(REQUIRED_OPS)}"]
                if not problems:
                    _, bad = run_golden(m, n_golden)
                    if bad:
                        problems = [f"plan disagreed with the independent oracle on {len(bad)} of {n_golden} golden invoices"]
                if problems:
                    report["rejections"].append({"attempt": attempt, "problems": problems[:6]})
                    continue
                plan, report["plan_source"] = cand, "nemotron (validated against allowlist, schema and oracle)"
                break
            except Exception as e:
                report["rejections"].append({"attempt": attempt, "problems": [sanitize(e)]})
        if plan is None:
            report["plan_source"] = "deterministic fallback (model plan rejected, see rejections)"
    if plan is None:
        plan = golden_plan()
    m = Manifest.model_validate(plan)
    assert not validate_manifest(m), validate_manifest(m)
    vals, bad = run_golden(m, n_golden)
    if bad:
        raise RuntimeError(f"golden plan disagrees with oracle on {bad[:3]}")
    m.contracts = C.declared_contracts() + C.mine_contracts(m, vals)
    m.meta = {"plan_source": report["plan_source"], "model": report["model"], "compiled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "mined_from_golden_runs": n_golden, "compile_model_calls": meter.snapshot()["compile_model_calls"] if meter else 0}
    m.assumptions = registry(m)
    report["assumptions"] = m.assumptions
    report["contracts"] = [{"id": c["id"], "kind": c["kind"], "severity": c["severity"], "desc": c["desc"]} for c in m.contracts]
    return m, report
