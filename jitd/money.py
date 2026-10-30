"""Exact money arithmetic. Never use floats for amounts."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")


def D(x) -> Decimal:
    if isinstance(x, Decimal):
        d = x
    elif isinstance(x, bool) or x is None:
        raise ValueError(f"not a number: {x!r}")
    else:
        try:
            d = Decimal(str(x).strip())
        except InvalidOperation:
            raise ValueError(f"not a number: {x!r}") from None
    if not d.is_finite():
        raise ValueError(f"not finite: {x!r}")
    return d


def q(x) -> Decimal:
    return D(x).quantize(CENT, ROUND_HALF_UP)


def fmt(x) -> str:
    return format(q(x), "f")
