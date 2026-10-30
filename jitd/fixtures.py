"""Seeded synthetic invoices. Ground truth lives here and is never produced by the code under test."""
from __future__ import annotations

import random
from dataclasses import dataclass
from decimal import Decimal

from .money import q

SKUS = ["WIDGET-A", "WIDGET-B", "GADGET-X", "SERVICE-HR", "SUPPORT-PLAN", "CABLE-3M", "LICENSE-SEAT"]


@dataclass(frozen=True)
class Truth:
    invoice_id: str
    line_items: tuple            # (sku, qty:int, unit_price:Decimal)
    tax: Decimal
    discount: Decimal
    total: Decimal
    payments: tuple              # (payment_id, amount:Decimal, paid_at)
    issued_at: str
    short: bool = False          # customer paid less than the invoice total while the provider says "paid"
    big: bool = False            # legitimately very large invoice

    @property
    def paid_total(self) -> Decimal:
        return sum((p[1] for p in self.payments), Decimal("0"))


def make_truth(seed, idx: int, epoch: str = "pre", installments: int | None = None, short: bool = False, big: bool = False) -> Truth:
    rng = random.Random(f"jitd:{seed}:{idx}:{epoch}")
    items = [(rng.choice(SKUS), rng.randint(1, 10), q(rng.uniform(5, 250))) for _ in range(rng.randint(1, 5))]
    if big:
        items.append(("ENTERPRISE-LICENSE", rng.randint(30, 40), q(rng.uniform(700, 900))))
    subtotal = sum((qty * price for _, qty, price in items), Decimal("0"))
    tax = q(subtotal * Decimal(str(rng.choice([0, 0.05, 0.07, 0.1]))))
    discount = q(subtotal * Decimal(str(rng.choice([0, 0, 0.05, 0.1]))))
    total = subtotal + tax - discount
    k = installments or rng.choices([1, 2, 3, 4], [30, 30, 25, 15])[0]
    target = q(total * Decimal("0.963")) if short else total
    w = [rng.uniform(0.5, 1.5) for _ in range(k)]
    parts = [q(target * Decimal(str(x)) / Decimal(str(sum(w)))) for x in w[:-1]]
    parts.append(target - sum(parts, Decimal("0")))
    day = (lambda: rng.randint(1, 28)) if epoch == "pre" else (lambda: rng.randint(16, 28))
    month = "09" if epoch == "pre" else "10"
    pays = tuple((f"PAY-{idx:04d}-{j}", amt, f"2026-{month}-{day():02d}T{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:00Z")
                 for j, amt in enumerate(parts))
    return Truth(f"INV-{seed}-{idx:04d}", tuple(items), tax, discount, q(total), pays, f"2026-{month}-01T00:00:00Z", short, big)


def golden_truths(n: int = 400, seed: str = "golden") -> list[Truth]:
    return [make_truth(seed, i, "pre") for i in range(n)]
