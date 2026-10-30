"""Versioned mock provider with controlled behaviours. Synthetic data only; no network."""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone

from .fixtures import Truth
from . import mutations as mut
from .money import q

BEHAVIORS = ("clean", "cosmetic", "unit_cents", "unit_mills", "truncation", "malformed", "consistent_scale", "cents_truncation", "mutated")


PAGED = ("truncation", "cents_truncation")


class ServiceError(Exception):
    pass


def _scaled(x: Decimal, factor: int):
    """A JSON number. Dollars are floats; scaled units are integers (same numeric schema either way)."""
    return float(x) if factor == 1 else int(q(x) * factor)


class MockServices:
    def __init__(self, truths, behavior: str = "clean", page_size: int | None = None, mutations=()):
        if behavior not in BEHAVIORS:
            raise ValueError(f"unknown behavior {behavior!r}")
        self.evidence_mode = "independent"
        self.truths = {t.invoice_id: t for t in truths}
        self.behavior = behavior
        self.mutations = tuple(mutations)
        self.page_size = page_size or self._default_page(behavior)
        self.ledger: list[dict] = []
        self.calls = {"invoice.get": 0, "payment.list": 0, "ledger.post": 0}

    def _default_page(self, behavior):
        if behavior == "mutated":
            return mut.page_size_of(self.mutations) or 100
        return 2 if behavior in PAGED else 100

    def set_behavior(self, behavior: str):
        if behavior not in BEHAVIORS:
            raise ValueError(f"unknown behavior {behavior!r}")
        self.behavior = behavior
        self.page_size = self._default_page(behavior)

    def add_truth(self, t: Truth):
        self.truths[t.invoice_id] = t

    def _truth(self, invoice_id) -> Truth:
        try:
            return self.truths[invoice_id]
        except KeyError:
            raise ServiceError(f"unknown invoice {invoice_id!r}") from None

    def invoice_get(self, invoice_id: str) -> dict:
        self.calls["invoice.get"] += 1
        t, b = self._truth(invoice_id), self.behavior
        f = 100 if b == "consistent_scale" else 1
        r = {"invoice_id": t.invoice_id, "currency": "USD", "issued_at": t.issued_at,
             "line_items": [{"sku": s, "quantity": n, "unit_price": _scaled(p, f)} for s, n, p in t.line_items],
             "tax": _scaled(t.tax, f), "discount": _scaled(t.discount, f), "total": _scaled(t.total, f)}
        if b == "cosmetic":
            r = {k: r[k] for k in reversed(list(r))}
            r["meta"] = {"request_id": "req-" + t.invoice_id[-4:], "region": "eu-west"}
        if b == "mutated":
            r = mut.apply("invoice.get", r, self.mutations)
        return r

    def payment_list(self, invoice_id: str, cursor: str | None = None) -> dict:
        self.calls["payment.list"] += 1
        t, b = self._truth(invoice_id), self.behavior
        f = {"unit_cents": 100, "unit_mills": 1000, "consistent_scale": 100, "cents_truncation": 100}.get(b, 1)
        start = int(cursor[1:]) if cursor else 0
        chunk = t.payments[start:start + self.page_size]
        nxt = f"c{start + self.page_size}" if start + self.page_size < len(t.payments) else None
        pays = []
        for pid, amt, at in chunk:
            p = {"payment_id": pid, "amount": _scaled(amt, f), "status": "paid", "paid_at": at}
            if b == "cosmetic":
                p = {"paid_at": at, "status": "PAID", "amount": f"{amt:.2f}", "payment_id": pid, "method": "ach"}
            pays.append(p)
        if b == "malformed" and pays:
            pays[0]["amount"] = None
        resp = {"invoice_id": t.invoice_id, "payments": pays, "next_cursor": nxt}
        return mut.apply("payment.list", resp, self.mutations) if b == "mutated" else resp

    def snapshot_token(self, invoice_id):
        # An immutable read snapshot is available only in the synthetic adapter.
        # Real adapters must supply equivalent versioned snapshot semantics or recovery falls back to a full read.
        data = {"truth": asdict(self._truth(invoice_id)), "behavior": self.behavior,
                "page_size": self.page_size, "mutations": self.mutations, "evidence_mode": self.evidence_mode}
        return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()

    def verification_evidence(self, invoice_id):
        if self.evidence_mode == "missing":
            return {}
        truth = self._truth(invoice_id)
        now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        source = "provider" if self.evidence_mode == "correlated" else "independent"
        factor = 100 if self.evidence_mode == "correlated" and self.behavior == "consistent_scale" else 1
        common = {"currency": "USD", "observed_at": now, "simulated": True,
                  "independent_of": "provider" if source != "provider" else None}
        return {"snapshot_bound": True,
                "billing_authority": {**common, "source_id": source + ":billing" if source != "provider" else "provider", "invoice_total_usd": str(truth.total * factor)},
                "settlement_authority": {**common, "source_id": source + ":settlement" if source != "provider" else "provider", "settled_total_usd": str(truth.paid_total * factor)}}

    def ledger_post(self, entry: dict) -> dict:
        self.calls["ledger.post"] += 1
        # A successful retry may repeat a request; it must not create another posting.
        for previous in self.ledger:
            if previous["invoice_id"] == entry["invoice_id"] and previous["disposition"] == "posted":
                if previous != entry:
                    raise ServiceError("idempotency conflict: invoice already posted with different values")
                return {"ok": True, "idempotent": True}
        self.ledger.append(dict(entry))
        return {"ok": True}


class RecordedServices:
    """Replays captured raw responses (used by isolated validation). Cannot reach anything else."""
    def __init__(self, case: dict):
        self.case, self.ledger = case, []

    def invoice_get(self, invoice_id):
        return self.case["invoice"]

    def payment_list(self, invoice_id, cursor=None):
        return self.case["pages"][cursor or ""]

    def ledger_post(self, entry):
        self.ledger.append(dict(entry))
        return {"ok": True}


def capture_case(services, invoice_id: str, as_of: str, expected=None, max_pages: int = 50) -> dict:
    """Read-only shadow fetch of every page for one invoice. Never posts to the ledger."""
    pages, cursor = {}, None
    for _ in range(max_pages):
        page = services.payment_list(invoice_id, cursor)
        pages[cursor or ""] = page
        cursor = page.get("next_cursor")
        if not cursor:
            break
    return {"invoice_id": invoice_id, "as_of": as_of, "invoice": services.invoice_get(invoice_id), "pages": pages, "expected": expected}
