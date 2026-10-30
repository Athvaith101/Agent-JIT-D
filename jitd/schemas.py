"""Boundary schemas for provider responses. Deliberately lax about meaning: dollars and cents both pass."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, ValidationError


class Line(BaseModel):
    model_config = ConfigDict(extra="allow")
    sku: str
    quantity: int
    unit_price: Decimal


class InvoiceResp(BaseModel):
    model_config = ConfigDict(extra="allow")
    invoice_id: str
    currency: str
    line_items: list[Line]
    tax: Decimal
    discount: Decimal
    total: Decimal


class Pay(BaseModel):
    model_config = ConfigDict(extra="allow")
    payment_id: str
    amount: Decimal
    status: str
    paid_at: str


class PaymentsResp(BaseModel):
    model_config = ConfigDict(extra="allow")
    invoice_id: str
    payments: list[Pay]
    next_cursor: str | None = None


class SchemaError(Exception):
    def __init__(self, what: str, errors: list[dict]):
        super().__init__(f"{what}: response does not match schema")
        self.what, self.errors = what, errors


def validate(model, data, what: str):
    try:
        model.model_validate(data)
    except ValidationError as e:
        raise SchemaError(what, [{"loc": ".".join(str(x) for x in er["loc"]), "msg": er["msg"]} for er in e.errors()[:5]]) from None
    return data
