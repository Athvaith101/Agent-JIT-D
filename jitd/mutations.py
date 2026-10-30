"""Declarative provider mutations, so a third party can author a drift scenario as JSON without touching code.

A mutation is {"endpoint": "invoice.get"|"payment.list", "op": ..., ...}. Ops:
  scale     {"fields": ["total", "line_items[*].unit_price"], "factor": 100}   numbers become integers x factor
  null      {"fields": ["payments[*].amount"]}
  stringify {"fields": ["payments[*].amount"]}                                  numbers become "12.34"
  upper     {"fields": ["payments[*].status"]}
  add_field {"name": "meta", "value": {...}}                                    adds a top-level key
  page_size {"value": 2}                                                        payment.list returns that many per page
"""
from __future__ import annotations

import copy
import re
from decimal import Decimal

ENDPOINTS = ("invoice.get", "payment.list")
OPS = ("scale", "null", "stringify", "upper", "add_field", "page_size")
FACTORS = (10, 100, 1000, 10000)
_FIELD = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\[\*\])?(?:\.[A-Za-z_][A-Za-z0-9_]*(?:\[\*\])?)*$")


def validate(m: dict) -> dict:
    if not isinstance(m, dict) or m.get("endpoint") not in ENDPOINTS or m.get("op") not in OPS:
        raise ValueError(f"mutation needs endpoint in {ENDPOINTS} and op in {OPS}: {m!r}")
    op = m["op"]
    if op in ("scale", "null", "stringify", "upper"):
        f = m.get("fields")
        if not isinstance(f, list) or not f or not all(isinstance(x, str) and _FIELD.match(x) for x in f):
            raise ValueError(f"{op} needs a non-empty list of simple field paths")
    if op == "scale" and m.get("factor") not in FACTORS:
        raise ValueError(f"scale factor must be one of {FACTORS}")
    if op == "add_field" and not (isinstance(m.get("name"), str) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", m["name"])):
        raise ValueError("add_field needs a simple name")
    if op == "page_size" and not (isinstance(m.get("value"), int) and 1 <= m["value"] <= 50):
        raise ValueError("page_size value must be an integer 1..50")
    return m


def _tokens(path: str):
    return [(p[:-3], True) if p.endswith("[*]") else (p, False) for p in path.split(".")]


def _apply(node, toks, fn):
    if not toks:
        return fn(node)
    key, star = toks[0]
    if isinstance(node, dict) and key in node:
        v = node[key]
        node[key] = [_apply(x, toks[1:], fn) for x in v] if star and isinstance(v, list) else (_apply(v, toks[1:], fn) if not star else v)
    return node


def _num(v):
    return isinstance(v, (int, float, Decimal)) and not isinstance(v, bool)


def apply(endpoint: str, resp: dict, mutations) -> dict:
    out = copy.deepcopy(resp)
    for m in mutations:
        if m["endpoint"] != endpoint:
            continue
        op = m["op"]
        if op == "add_field":
            out[m["name"]] = copy.deepcopy(m.get("value"))
            continue
        if op == "page_size":
            continue
        fn = {"scale": lambda v, f=m.get("factor"): int(round(Decimal(str(v)) * f)) if _num(v) else v,
              "null": lambda v: None,
              "stringify": lambda v: f"{Decimal(str(v)):.2f}" if _num(v) else v,
              "upper": lambda v: v.upper() if isinstance(v, str) else v}[op]
        for f in m["fields"]:
            _apply(out, _tokens(f), fn)
    return out


def page_size_of(mutations):
    for m in mutations:
        if m["op"] == "page_size":
            return m["value"]
    return None
