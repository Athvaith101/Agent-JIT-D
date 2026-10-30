"""Bounded repair: a typed proposal -> allowlist check -> candidate manifest -> isolated validation -> accept or reject.
The model may propose; only independent validation may accept. Repairs are data (op parameters), never generated code."""
from __future__ import annotations

import json
import os
import site
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from .executor import Executor
from .llm import extract_json, sanitize
from .manifest import Manifest, validate_manifest
from .ops import DIVISORS, OPS
from .services import capture_case
from .validation import run_validation

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = {"normalize_money": "rules", "payment.list": "max_pages"}


class RepairProposal(BaseModel):
    op: str
    param: str
    value: object
    rationale: str = ""
    source: Literal["deterministic", "nemotron", "operator_override"] = "deterministic"


def check_allowlist(p: RepairProposal) -> list[str]:
    errs = []
    if p.op not in ALLOWED or ALLOWED[p.op] != p.param:
        errs.append(f"repair of {p.op}.{p.param} is not allowlisted (allowed: {ALLOWED})")
        return errs
    try:
        OPS[p.op].params[p.param][0](p.value)
    except ValueError as e:
        errs.append(str(e))
    return errs


def current_rules(manifest: Manifest) -> list[dict]:
    st = manifest.step_for_op("normalize_money")
    return list((st.params.get("rules") if st else None) or [{"divisor": 1, "effective_from": None}])


def synthesize(diagnosis: dict, cutover: str, existing_rules: list[dict] | None = None) -> RepairProposal | None:
    """Deterministic repair from diagnosis evidence. Returns None when no allowlisted repair applies."""
    top = diagnosis.get("top")
    if diagnosis.get("status") != "localized" or not top or not top.get("hint"):
        return None
    if top["name"] == "unit_scale":
        d = top["hint"]["divisor"]
        if d not in DIVISORS or d == 1:
            return None
        return RepairProposal(op="normalize_money", param="rules", source="deterministic",
                              value=list(existing_rules or [{"divisor": 1, "effective_from": None}]) + [{"divisor": d, "effective_from": cutover}],
                              rationale=f"payment amounts arrive {d}x too large since {cutover}; divide by {d} from that instant, leave earlier data untouched")
    if top["name"] == "truncated_pagination":
        return RepairProposal(op="payment.list", param="max_pages", value=top["hint"]["max_pages"], source="deterministic",
                              rationale="provider now paginates; follow next_cursor (bounded to 10 pages)")
    return None


REPAIR_SYSTEM = """You propose ONE bounded repair as strict JSON: {"op","param","value","rationale"}. Allowed repairs only:
- op "normalize_money", param "rules": the CURRENT rules (given below) plus exactly one appended rule {"divisor": one of [10,100,1000,10000], "effective_from": the cutover timestamp}.
- op "payment.list", param "max_pages": integer 2..20.
Output ONLY JSON. Do not write code."""


def propose_with_model(llm, diagnosis: dict, cutover: str, existing_rules: list[dict] | None = None) -> RepairProposal:
    ev = {"current_rules": existing_rules, "status": diagnosis["status"], "detected_at": diagnosis["detected_at"], "cutover_candidate": cutover,
          "suspects": [{k: s[k] for k in ("op", "name", "assumption", "score")} | {"met": [f["name"] + (" (" + f["detail"] + ")" if f["detail"] else "") for f in s["features"] if f["met"]]} for s in diagnosis["suspects"][:3]]}
    d = extract_json(llm.complete("repair", REPAIR_SYSTEM, json.dumps(ev, indent=1), max_tokens=500))
    return RepairProposal(op=d.get("op", ""), param=d.get("param", ""), value=d.get("value"), rationale=str(d.get("rationale", ""))[:300], source="nemotron")


def apply(manifest: Manifest, p: RepairProposal) -> Manifest:
    new = manifest.clone()
    s = new.step_for_op(p.op)
    if s is None:
        raise ValueError(f"no step for {p.op}")
    s.params[p.param] = p.value
    a, b, c = (int(x) for x in manifest.version.split("."))
    new.version = f"{a}.{b}.{c + 1}"
    new.meta = {**new.meta, "repaired_from": manifest.version, "repair": {"op": p.op, "param": p.param, "value": p.value, "source": p.source, "rationale": p.rationale}}
    return new


def validate_isolated(payload: dict, timeout_s: float = 30.0) -> dict:
    """Run validation in a separate Python process with a scrubbed environment and a temp working dir."""
    # -s suppresses user-site dependencies, including pip --user installs on Windows.
    # Pass only the parent's installation roots as literal data; never PYTHONPATH.
    roots = list(dict.fromkeys([str(ROOT), *site.getsitepackages(), site.getusersitepackages()]))
    env = {k: os.environ[k] for k in ("PATH", "SystemRoot", "WINDIR") if k in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    bootstrap = (f"import sys; sys.path[:0] = {roots!r}; "
                 "from jitd.validate_worker import main; main()")
    with tempfile.TemporaryDirectory() as td:
        try:
            cp = subprocess.run([sys.executable, "-I", "-c", bootstrap],
                                input=json.dumps(payload), capture_output=True, text=True,
                                encoding="utf-8", timeout=timeout_s, env=env, cwd=td)
        except subprocess.TimeoutExpired:
            return {"ok": False, "static_problems": [], "groups": {}, "worker": {"error": "timeout"}}
        except OSError as e:
            return {"ok": False, "static_problems": [], "groups": {}, "worker": {"error": sanitize(e)}}
    if cp.returncode != 0:
        return {"ok": False, "static_problems": [], "groups": {}, "worker": {"error": sanitize(RuntimeError(cp.stderr[-500:]))}}
    try:
        rep = json.loads(cp.stdout)
        if not isinstance(rep, dict) or type(rep.get("ok")) is not bool or not isinstance(rep.get("groups"), dict):
            raise ValueError("invalid worker report")
    except (ValueError, TypeError):
        return {"ok": False, "static_problems": [], "groups": {}, "worker": {"error": "invalid worker report"}}
    rep["isolated"] = True
    return rep


def cutover_from(cases: list[dict]) -> str:
    return min(c["as_of"] for c in cases)


def attempt_repair(manifest: Manifest, diagnosis: dict, services, failing: list[tuple[str, str, object]], regression: list[dict],
                   llm=None, override: RepairProposal | None = None, isolated: bool = True, fresh: list[tuple[str, str, object]] | None = None) -> dict:
    """failing / fresh: [(invoice_id, as_of, expected_or_'unknown')]. Returns a full, inspectable repair record."""
    rec = {"proposals": [], "accepted": False, "decision": "rejected", "reason": "", "candidate_version": None}
    drift_cases = [capture_case(services, i, a, e) for i, a, e in (failing + (fresh or []))][:12]
    if not drift_cases:
        rec["reason"] = "no failing inputs to validate against"
        return rec
    cutover = cutover_from(drift_cases)
    rec["cutover"] = cutover
    cands: list[RepairProposal] = []
    if override is not None:
        cands.append(override)
    else:
        if llm is not None:
            try:
                cands.append(propose_with_model(llm, diagnosis, cutover, current_rules(manifest)))
            except Exception as e:
                rec["proposals"].append({"source": "nemotron", "status": "unusable", "problems": [sanitize(e)]})
        d = synthesize(diagnosis, cutover, current_rules(manifest))
        if d is not None:
            cands.append(d)
    if not cands:
        rec["reason"] = "no allowlisted repair applies to this diagnosis; workflow stays halted for human review"
        return rec
    for p in cands[:2]:
        entry = {"source": p.source, "op": p.op, "param": p.param, "value": p.value, "rationale": p.rationale}
        probs = check_allowlist(p)
        if probs:
            entry.update(status="rejected_by_allowlist", problems=probs)
            rec["proposals"].append(entry)
            continue
        if p.op == "normalize_money":
            ex = current_rules(manifest)
            if not isinstance(p.value, list) or p.value[: len(ex)] != ex or len(p.value) != len(ex) + 1:
                entry.update(status="rejected_by_allowlist", problems=["a repair may only append exactly one rule to the existing rules"])
                rec["proposals"].append(entry)
                continue
        try:
            cand = apply(manifest, p)
        except ValueError as e:
            entry.update(status="rejected", problems=[str(e)])
            rec["proposals"].append(entry)
            continue
        probs = validate_manifest(cand)
        if probs or cand.model_dump(exclude={"version", "meta"}) == manifest.model_dump(exclude={"version", "meta"}):
            entry.update(status="rejected_static", problems=probs or ["candidate is identical to the current manifest"])
            rec["proposals"].append(entry)
            continue
        payload = {"manifest": cand.model_dump(), "groups": {"drift_cases": drift_cases, "regression": regression}}
        rep = validate_isolated(payload) if isolated else run_validation(payload)
        entry.update(status="accepted" if rep["ok"] else "rejected_by_validation", validation=rep, diff=_diff(manifest, cand))
        rec["proposals"].append(entry)
        if rep["ok"]:
            rec.update(accepted=True, decision="accepted", reason="all drift cases and all regression cases pass; independent oracle agrees" , candidate_version=cand.version, candidate=cand.model_dump(),
                       accepted_proposal=entry["source"], drift_cases=len(drift_cases))
            return rec
    rec["reason"] = "no candidate passed validation; the original manifest is kept and the workflow stays halted"
    return rec


def _diff(a: Manifest, b: Manifest) -> list[dict]:
    out = []
    for sa, sb in zip(a.steps, b.steps):
        if sa.params != sb.params:
            out.append({"step": sa.id, "param_before": sa.params, "param_after": sb.params})
    return out
