"""Semantic contracts. Data-only (JSON-serialisable) so they can be mined, versioned and diffed.

Two kinds:
  declared  hand-written business invariants (invoice arithmetic, payment == invoice)
  mined     learned from the golden runs at compile time (value ranges, structure, enums)
Severity: critical -> halt before any downstream effect.  warning -> flag the run, hold the ledger entry for review.
"""
from __future__ import annotations

import math
from decimal import Decimal

from .money import D
from .paths import get_path

RANGE_MARGIN = Decimal(3)     # mined ranges are widened by this factor on each side (fixed up-front, not tuned)


def declared_contracts() -> list[dict]:
    return [
        {"id": "invoice-arithmetic", "kind": "declared", "type": "residual_within", "after_op": "reconcile_amounts",
         "path": "invoice_residual", "tol": "0.01", "severity": "critical",
         "desc": "Invoice total equals sum(quantity x unit price) + tax - discount."},
        {"id": "payment-matches-invoice", "kind": "declared", "type": "residual_within", "after_op": "reconcile_amounts",
         "path": "payment_residual", "tol": "0.01", "severity": "critical",
         "when": {"path": "provider_status", "equals": "paid"},
         "desc": "When the provider says paid, payments in USD equal the invoice total."},
    ]


def _values(output, path):
    v = get_path(output, path) if path else output
    return v if isinstance(v, list) else [v]


def evaluate(c: dict, output) -> dict:
    """Evaluate one contract against the output of the step it is attached to."""
    res = {"id": c["id"], "kind": c["kind"], "type": c["type"], "severity": c["severity"], "ok": True, "observed": None,
           "expected": None, "message": ""}
    try:
        w = c.get("when")
        if w and get_path(output, w["path"]) != w["equals"]:
            res.update(skipped=True, message="condition not met")
            return res
        t = c["type"]
        if t == "residual_within":
            r, tol = D(get_path(output, c["path"])), D(c["tol"])
            res.update(ok=r <= tol, observed=str(r), expected=f"<= {tol}", message=f"{c['desc']} Residual {r} (tolerance {tol}).")
        elif t == "range_log":
            vals = [D(x) for x in _values(output, c["path"])]
            lo, hi = D(c["lo"]), D(c["hi"])
            out = [v for v in vals if not (lo <= abs(v) <= hi)]
            res.update(ok=not out, observed={"n": len(vals), "n_out_of_range": len(out), "max": str(max(vals)) if vals else None},
                       expected=f"{lo} <= |x| <= {hi}", message=f"{c['desc']} {len(out)} of {len(vals)} value(s) outside the learned range.")
        elif t == "must_be_null":
            v = get_path(output, c["path"])
            res.update(ok=v is None, observed=v, expected=None, message=f"{c['desc']} Observed {v!r}.")
        elif t == "enum":
            vals = {str(x).lower() for x in _values(output, c["path"])}
            extra = sorted(vals - set(c["allowed"]))
            res.update(ok=not extra, observed=sorted(vals), expected=sorted(c["allowed"]), message=f"{c['desc']} Unseen values: {extra}." if extra else c["desc"])
        elif t == "keyset":
            items = output if not c.get("path") else get_path(output, c["path"])
            items = items if isinstance(items, list) else [items]
            missing = sorted({k for it in items for k in set(c["required"]) - set(it)})
            res.update(ok=not missing, observed=sorted({k for it in items for k in it}), expected=sorted(c["required"]),
                       message=f"{c['desc']} Missing: {missing}." if missing else c["desc"])
        else:
            res.update(ok=False, message=f"unknown contract type {t!r}")
    except (KeyError, ValueError, TypeError, ArithmeticError) as e:
        res.update(ok=False, observed=f"{type(e).__name__}: {e}", message=f"{c['desc'] if 'desc' in c else c['id']} could not be evaluated: {e}")
    return res


def _log_range(vals):
    vals = [abs(D(v)) for v in vals if D(v) != 0]
    return min(vals) / RANGE_MARGIN, max(vals) * RANGE_MARGIN


def mine_contracts(manifest, golden_values: list[dict]) -> list[dict]:
    """Learn boundary invariants from step outputs of known-good runs. Returns contract dicts.
    golden_values: list of {step_id: output}. Margins/tolerances are fixed constants, not tuned on any drift scenario."""
    inv, pay, norm = manifest.step_for_op("invoice.get"), manifest.step_for_op("payment.list"), manifest.step_for_op("normalize_money")
    out = []
    if inv:
        totals = [g[inv.id]["total"] for g in golden_values]
        lo, hi = _log_range(totals)
        out.append({"id": "mined-invoice-total-range", "kind": "mined", "type": "range_log", "after_op": "invoice.get", "path": "total",
                    "lo": str(lo), "hi": str(hi), "severity": "warning", "desc": f"invoice.total stays within the range seen in {len(golden_values)} golden runs (x{RANGE_MARGIN} margin)."})
        # Only constrain fields consumed by the invoice workflow or boundary schema.
        # Auxiliary golden-run metadata (for example issued_at) is not a contract.
        invoice_fields = {"invoice_id", "currency", "line_items", "tax", "discount", "total"}
        keys = sorted(set.intersection(*[set(g[inv.id]) for g in golden_values]) & invoice_fields)
        out.append({"id": "mined-invoice-keys", "kind": "mined", "type": "keyset", "after_op": "invoice.get", "path": "",
                    "required": keys, "severity": "critical", "desc": "invoice response keeps fields consumed by this workflow and its boundary schema."})
    if norm:
        amts = [a for g in golden_values for a in g[norm.id]]
        lo, hi = _log_range(amts)
        out.append({"id": "mined-payment-amount-range", "kind": "mined", "type": "range_log", "after_op": "normalize_money", "path": "",
                    "lo": str(lo), "hi": str(hi), "severity": "warning",
                    "desc": f"normalized USD payment amounts stay within the range seen in golden runs (x{RANGE_MARGIN} margin)."})
    if pay:
        out.append({"id": "mined-payments-complete", "kind": "mined", "type": "must_be_null", "after_op": "payment.list", "path": "next_cursor",
                    "severity": "critical", "desc": "payment list is complete: no further page (golden runs never had a next_cursor)."})
        statuses = sorted({str(p["status"]).lower() for g in golden_values for p in g[pay.id]["payments"]})
        out.append({"id": "mined-payment-status-enum", "kind": "mined", "type": "enum", "after_op": "payment.list", "path": "payments[*].status",
                    "allowed": statuses, "severity": "warning", "desc": "payment status stays within the values seen in golden runs."})
        pkeys = sorted(set.intersection(*[set(p) for g in golden_values for p in g[pay.id]["payments"]]))
        out.append({"id": "mined-payment-keys", "kind": "mined", "type": "keyset", "after_op": "payment.list", "path": "payments[*]",
                    "required": pkeys, "severity": "critical", "desc": "each payment keeps every field seen in golden runs."})
    return out
