"""Fault localization by hypothesis testing over the workflow's dependency graph.

Each hypothesis names an *assumption* a step makes (e.g. "amounts are in dollars"), lists transparent evidence features with
weights, and is scored by which features hold. Scores are heuristic suspicion scores, NOT probabilities and are not calibrated.
The step where a check *fires* is often not the step whose assumption broke; the ranking can move blame upstream or downstream.
"""
from __future__ import annotations

import math
from decimal import Decimal

from .money import D

STRONG = 4.0      # a top hypothesis below this is "unexplained"
MARGIN = 1.5      # top must beat the runner-up (at a different location) by this much, else "ambiguous"


def _feat(name, weight, met, detail=""):
    return {"name": name, "weight": weight, "met": bool(met), "detail": detail}


def _pow10(ratio: Decimal):
    """k if ratio is within 1% of 10**k (k != 0, |k| <= 4), else None."""
    if ratio <= 0:
        return None
    k = round(math.log10(float(ratio)))
    if k == 0 or abs(k) > 4:
        return None
    return k if abs(float(ratio) / (10 ** k) - 1) <= 0.01 else None


def _cr(run, cid):
    return next((c for c in run.contract_results if c["id"] == cid), None)


def _failed(run, cid):
    c = _cr(run, cid)
    return bool(c) and not c["ok"]


def _evidence(manifest, run) -> dict:
    inv_s, pay_s = manifest.step_for_op("invoice.get"), manifest.step_for_op("payment.list")
    inv, pay = run.values.get(inv_s.id) if inv_s else None, run.values.get(pay_s.id) if pay_s else None
    ev = {"inv_step": inv_s.id if inv_s else None, "pay_step": pay_s.id if pay_s else None, "ratio": None, "raw_total": None, "invoice_total": None}
    try:
        if inv and pay:
            ev["invoice_total"] = D(inv["total"])
            ev["raw_total"] = sum((D(p["amount"]) for p in pay["payments"]), Decimal("0"))
            ev["cursor"] = pay.get("next_cursor")
            if ev["invoice_total"] > 0:
                ev["ratio"] = ev["raw_total"] / ev["invoice_total"]
    except (ValueError, KeyError, TypeError):
        pass
    return ev


def diagnose(manifest, run) -> dict:
    ev = _evidence(manifest, run)
    halt = run.halt or {}
    schema_bad = halt.get("reason") == "schema_invalid"
    structure_ok = not schema_bad and ev.get("cursor") is None and not _failed(run, "mined-payments-complete") and not _failed(run, "mined-payment-keys")
    arith_ok = not _failed(run, "invoice-arithmetic")
    pay_range_bad = _failed(run, "mined-payment-amount-range")
    inv_range_bad = _failed(run, "mined-invoice-total-range")
    ratio = ev["ratio"]
    k = _pow10(ratio) if ratio is not None else None
    H = []

    if schema_bad:
        stp = manifest.step(halt["step"])
        H.append({"op": stp.operation, "name": "malformed_response", "assumption": "the provider returns schema-valid responses", "features": [
            _feat("response failed boundary schema validation", 5, True, "; ".join(f"{e['loc']}: {e['msg']}" for e in halt.get("detail", [])[:2]))],
            "hint": None})
    if ratio is not None and not schema_bad:
        H.append({"op": "normalize_money", "name": "unit_scale", "assumption": "provider amounts are in dollars", "features": [
            _feat("raw payment total / invoice total is an exact power of ten", 4, k is not None, f"ratio = {ratio:.4f}" if ratio is not None else ""),
            _feat("response structure valid (no next page, keys intact)", 1, structure_ok),
            _feat("invoice arithmetic consistent, so the invoice is a trustworthy reference", 1, arith_ok),
            _feat("raw amounts outside the range learned at compile time", 1, pay_range_bad)],
            "hint": {"divisor": 10 ** k} if (k is not None and k > 0) else None})
        H.append({"op": "payment.list", "name": "truncated_pagination", "assumption": "one page contains every payment", "features": [
            _feat("provider returned a next_cursor", 4, ev.get("cursor") is not None, f"next_cursor = {ev.get('cursor')!r}"),
            _feat("payments seen sum to less than the invoice total", 2, ratio < Decimal("0.999")),
            _feat("invoice arithmetic consistent", 1, arith_ok)],
            "hint": {"max_pages": 10} if ev.get("cursor") is not None else None})
        H.append({"op": "invoice.get", "name": "invoice_side_drift", "assumption": "invoice amounts are internally consistent", "features": [
            _feat("invoice total disagrees with its own line items", 4, not arith_ok),
            _feat("invoice total outside learned range while payments are inside", 2, inv_range_bad and not pay_range_bad)], "hint": None})
        H.append({"op": "invoice.get+payment.list", "name": "provider_wide_scale_shift", "assumption": "both services keep the same unit", "features": [
            _feat("invoice AND payment magnitudes both outside learned ranges", 3, inv_range_bad and pay_range_bad),
            _feat("every internal arithmetic check still passes", 2, arith_ok and not _failed(run, "payment-matches-invoice")),
            ], "hint": None})
        H.append({"op": None, "name": "business_exception", "assumption": "(not a drift) the customer really paid a different amount", "features": [
            _feat("structure valid and invoice arithmetic consistent", 1, structure_ok and arith_ok),
            _feat("payment is close to the invoice (0.5x-1.5x) but not a power-of-ten ratio", 4, 0.5 < float(ratio) < 1.5 and k is None and _failed(run, "payment-matches-invoice"), f"ratio = {ratio:.4f}"),
            _feat("no magnitude anomaly at either boundary", 1, not pay_range_bad and not inv_range_bad)], "hint": None})
    for h in H:
        h["score"] = sum(f["weight"] for f in h["features"] if f["met"])
        h["max_score"] = sum(f["weight"] for f in h["features"])
        h["step"] = (manifest.step_for_op(h["op"]).id if h["op"] and "+" not in h["op"] and manifest.step_for_op(h["op"]) else None)
    H.sort(key=lambda h: -h["score"])
    top = H[0] if H else None
    if top is None:
        status = "unexplained"
    elif top["score"] < STRONG:
        status = "unexplained"
    elif len(H) > 1 and H[1]["score"] > 0 and top["score"] - H[1]["score"] < MARGIN and H[1]["op"] != top["op"]:
        status = "ambiguous"
    elif top["name"] == "business_exception":
        status = "business_exception"
    elif top["name"] == "provider_wide_scale_shift":
        status = "provider_wide"
    else:
        status = "localized"
    detected = {"step": halt.get("step"), "contract": halt.get("contract"), "reason": halt.get("reason")} if halt else \
        {"step": None, "contract": next((c["id"] for c in run.contract_results if not c["ok"]), None), "reason": "flagged"}
    return {"status": status, "detected_at": detected, "suspects": [{k_: h[k_] for k_ in ("op", "step", "name", "assumption", "score", "max_score", "features", "hint")} for h in H[:4]],
            "top": ({k_: top[k_] for k_ in ("op", "step", "name", "score", "hint")} if top else None), "score_note": "heuristic suspicion score, not a probability"}


def explain(d: dict) -> str:
    """Deterministic plain-language explanation."""
    t = d["top"]
    det = d["detected_at"]
    where = f"The check that fired was {det.get('contract') or det.get('reason')} at step {det.get('step')}. "
    if d["status"] == "localized":
        met = [f["name"] for f in d["suspects"][0]["features"] if f["met"]]
        return where + f"Most likely broken assumption: '{d['suspects'][0]['assumption']}' ({t['name']}) at step {t['step']}. Evidence: " + "; ".join(met) + "."
    if d["status"] == "business_exception":
        return where + "Structure and arithmetic are intact and the amount is simply different: this looks like a real business exception (a short payment), not provider drift. No repair is attempted; a human should review it."
    if d["status"] == "provider_wide":
        return where + "Invoice and payment magnitudes both moved while every internal check still agrees. This looks like a provider-wide unit shift that no allowlisted repair covers; the run is held for review."
    if d["status"] == "ambiguous":
        return where + f"Two hypotheses are too close to separate ({d['suspects'][0]['name']} vs {d['suspects'][1]['name']}). Operator review required."
    return where + "No hypothesis explains the evidence well enough. The workflow stays halted for human review."
