"""Load externally authored scenarios from JSON. See benchmark/external/README.md for the format."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import mutations as mut
from .scenarios import SCENARIOS, Scenario

KINDS = ("benign", "drift", "business_exception", "hard")
FAULT_OPS = (None, "invoice.get", "payment.list", "normalize_money", "invoice.get+payment.list")
KEYS = {"id", "title", "kind", "fault_op", "repairable", "desc", "mutations", "truth_mod", "truth_p", "installments", "author", "independent"}


def parse(spec: dict) -> Scenario:
    extra = set(spec) - KEYS
    if extra:
        raise ValueError(f"unknown keys: {sorted(extra)}")
    if not re.match(r"^[a-z][a-z0-9_]{1,40}$", str(spec.get("id", ""))):
        raise ValueError("id must be lowercase letters, digits, underscores")
    if spec["id"] in SCENARIOS and SCENARIOS[spec["id"]].split != "external":
        raise ValueError(f"id {spec['id']!r} collides with a built-in scenario")
    if spec.get("kind") not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if spec.get("fault_op") not in FAULT_OPS:
        raise ValueError(f"fault_op must be one of {FAULT_OPS}")
    if not str(spec.get("author", "")).strip():
        raise ValueError("author is required (say who wrote this scenario)")
    ms = tuple(mut.validate(m) for m in spec.get("mutations", []))
    tm = spec.get("truth_mod")
    if tm not in (None, "short", "big"):
        raise ValueError("truth_mod must be null, 'short' or 'big'")
    if not ms and not tm:
        raise ValueError("a scenario needs mutations or a truth_mod")
    p = float(spec.get("truth_p", 1.0))
    if not 0 < p <= 1:
        raise ValueError("truth_p must be in (0, 1]")
    return Scenario(spec["id"], spec["title"], "mutated" if ms else "clean", tm, spec["kind"], "external", spec["fault_op"], bool(spec.get("repairable", False)),
                    spec.get("desc", ""), p, spec.get("installments"), ms, str(spec["author"]), bool(spec.get("independent", False)))


def load_dir(path) -> dict[str, Scenario]:
    out = {}
    for f in sorted(Path(path).glob("*.json")):
        try:
            sc = parse(json.loads(f.read_text()))
        except (ValueError, KeyError, TypeError) as e:
            raise ValueError(f"{f.name}: {e}") from None
        out[sc.id] = sc
    return out


def register(scs: dict[str, Scenario]):
    SCENARIOS.update(scs)
