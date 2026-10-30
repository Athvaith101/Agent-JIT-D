"""Typed, versioned workflow manifest + static validation against the op registry."""
from __future__ import annotations

import copy
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .ops import OPS
from .paths import parse_ref

ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,40}$")


class Step(BaseModel):
    id: str
    kind: str
    operation: str
    inputs: dict[str, str] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _id(cls, v):
        if not ID_RE.match(v):
            raise ValueError("bad step id")
        return v


class Manifest(BaseModel):
    workflow_id: str
    version: str
    steps: list[Step]
    contracts: list[dict] = Field(default_factory=list)
    assumptions: list[dict] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

    def step_for_op(self, operation: str) -> Step | None:
        return next((s for s in self.steps if s.operation == operation), None)

    def step(self, step_id: str) -> Step | None:
        return next((s for s in self.steps if s.id == step_id), None)

    def deps(self) -> dict[str, list[str]]:
        out = {}
        for s in self.steps:
            out[s.id] = sorted({parse_ref(r)[0] for r in s.inputs.values()} - {"input"})
        return out

    def clone(self) -> "Manifest":
        return Manifest.model_validate(copy.deepcopy(self.model_dump()))


def validate_manifest(m: Manifest) -> list[str]:
    """Returns a list of problems (empty = valid)."""
    errs, seen = [], set()
    if not m.steps:
        errs.append("no steps")
    for s in m.steps:
        if s.id in seen:
            errs.append(f"duplicate step id {s.id}")
        o = OPS.get(s.operation)
        if o is None:
            errs.append(f"{s.id}: operation {s.operation!r} is not allowlisted")
            seen.add(s.id)
            continue
        if o.kind != s.kind:
            errs.append(f"{s.id}: kind {s.kind!r} does not match operation kind {o.kind!r}")
        if set(s.inputs) != set(o.inputs):
            errs.append(f"{s.id}: inputs must be exactly {list(o.inputs)}")
        for name, ref in s.inputs.items():
            try:
                root, _ = parse_ref(ref)
            except ValueError as e:
                errs.append(f"{s.id}.{name}: {e}")
                continue
            if root != "input" and root not in seen:
                errs.append(f"{s.id}.{name}: references {root!r} which is not an earlier step")
        for pname, pval in s.params.items():
            if pname not in o.params:
                errs.append(f"{s.id}: unknown param {pname!r}")
                continue
            try:
                o.params[pname][0](pval)
            except ValueError as e:
                errs.append(f"{s.id}.{pname}: {e}")
        seen.add(s.id)
    return errs
