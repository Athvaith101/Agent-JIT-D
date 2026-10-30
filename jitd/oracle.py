"""Independent oracle. It sees only fixture truth. It must never import the executor, ops or contracts."""
from __future__ import annotations

from .fixtures import Truth
from .money import fmt


def expected_ledger(t: Truth) -> dict | None:
    """The entry a correct system posts, or None when a human must review (a short payment is not auto-postable)."""
    if t.short:
        return None
    return {"invoice_id": t.invoice_id, "amount_usd": fmt(t.paid_total), "invoice_total_usd": fmt(t.total), "status": "paid"}


def entry_matches(entry: dict | None, expected: dict | None) -> bool:
    """entry is a ledger entry that was POSTED (not held). None means nothing was posted."""
    if expected is None:
        return entry is None
    return entry is not None and all(entry.get(k) == v for k, v in expected.items())
