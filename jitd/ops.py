"""Allowlisted operations. A manifest can only reference these; nothing is ever evaluated from text."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable

from .money import D, fmt, q
from .schemas import InvoiceResp, PaymentsResp, validate

DIVISORS = (1, 10, 100, 1000, 10000)


class Ctx:
    """Per-run context handed to ops: the provider handle and run flags. Ops cannot reach a model from here."""
    def __init__(self, services, schema_enabled: bool = True, flagged: bool = False):
        self.services, self.schema_enabled, self.flagged = services, schema_enabled, flagged

    def check_schema(self, model, data, what):
        return validate(model, data, what) if self.schema_enabled else data


@dataclass
class Op:
    name: str
    kind: str                       # mock_api | transform | check | sink
    inputs: tuple
    fn: Callable
    params: dict = field(default_factory=dict)   # name -> (validator, default)
    doc: str = ""


OPS: dict[str, Op] = {}


def op(name, kind, inputs, params=None, doc=""):
    def deco(fn):
        OPS[name] = Op(name, kind, tuple(inputs), fn, params or {}, doc)
        return fn
    return deco


def _max_pages(v):
    if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 20:
        raise ValueError("max_pages must be an integer 1..20")
    return v


def _rules(v):
    if not isinstance(v, list) or not 1 <= len(v) <= 8:
        raise ValueError("rules must be a list of 1..8 rules")
    out = []
    for r in v:
        if not isinstance(r, dict) or set(r) - {"divisor", "effective_from"}:
            raise ValueError("rule keys: divisor, effective_from")
        d, e = r.get("divisor"), r.get("effective_from")
        if d not in DIVISORS or isinstance(d, bool):
            raise ValueError(f"divisor must be one of {DIVISORS}")
        if e is not None and not (isinstance(e, str) and len(e) == 20 and e.endswith("Z")):
            raise ValueError("effective_from must be an ISO UTC timestamp like 2026-10-16T00:00:00Z")
        out.append({"divisor": d, "effective_from": e})
    return out


@op("invoice.get", "mock_api", ["invoice_id"], doc="Fetch an invoice from the provider.")
def invoice_get(ctx, invoice_id):
    return ctx.check_schema(InvoiceResp, ctx.services.invoice_get(invoice_id), "invoice.get")


@op("payment.list", "mock_api", ["invoice_id"], {"max_pages": (_max_pages, 1)}, doc="List payments (follows up to max_pages pages).")
def payment_list(ctx, invoice_id, max_pages=1):
    pages, cursor, merged = 0, None, []
    while pages < max_pages:
        page = ctx.check_schema(PaymentsResp, ctx.services.payment_list(invoice_id, cursor), "payment.list")
        merged.extend(page["payments"])
        pages += 1
        cursor = page.get("next_cursor")
        if not cursor:
            break
    return {"invoice_id": invoice_id, "payments": merged, "next_cursor": cursor, "pages": pages}


@op("normalize_money", "transform", ["payments", "as_of"], {"rules": (_rules, [{"divisor": 1, "effective_from": None}])},
    doc="Convert provider payment amounts to USD dollars using the divisor rule in force at as_of.")
def normalize_money(ctx, payments, as_of, rules):
    div = 1
    for r in sorted(rules, key=lambda r: r["effective_from"] or ""):
        if r["effective_from"] is None or as_of >= r["effective_from"]:
            div = r["divisor"]
    return [fmt(D(p["amount"]) / Decimal(div)) for p in payments]


@op("sum_money", "transform", ["amounts"], doc="Exact sum of USD amounts.")
def sum_money(ctx, amounts):
    return fmt(sum((D(a) for a in amounts), Decimal("0")))


@op("invoice_total", "transform", ["invoice"], doc="Recompute the invoice total from its line items, tax and discount.")
def invoice_total(ctx, invoice):
    sub = sum((D(li["unit_price"]) * D(li["quantity"]) for li in invoice["line_items"]), Decimal("0"))
    return fmt(sub + D(invoice["tax"]) - D(invoice["discount"]))


@op("provider_status", "transform", ["payments"], doc="Overall provider status: 'paid' only if every payment is paid.")
def provider_status(ctx, payments):
    return "paid" if payments and all(str(p["status"]).lower() == "paid" for p in payments) else "other"


@op("reconcile_amounts", "check", ["invoice_total", "computed_total", "paid_total", "provider_status"],
    doc="Residuals between the invoice, its own arithmetic, and the payments.")
def reconcile_amounts(ctx, invoice_total, computed_total, paid_total, provider_status):
    return {"invoice_residual": fmt(abs(D(invoice_total) - D(computed_total))),
            "payment_residual": fmt(abs(D(paid_total) - D(invoice_total))),
            "provider_status": provider_status}


@op("post_ledger", "sink", ["invoice_id", "paid_total", "invoice_total", "status"], doc="Post a ledger entry ('held' if the run was flagged).")
def post_ledger(ctx, invoice_id, paid_total, invoice_total, status):
    entry = {"invoice_id": invoice_id, "amount_usd": fmt(paid_total), "invoice_total_usd": fmt(invoice_total), "status": status,
             "disposition": "held" if ctx.flagged else "posted"}
    ctx.services.ledger_post(entry)
    return entry


def catalogue() -> list[dict]:
    return [{"operation": o.name, "kind": o.kind, "inputs": list(o.inputs), "params": sorted(o.params), "doc": o.doc} for o in OPS.values()]
