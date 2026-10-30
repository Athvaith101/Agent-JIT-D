"""Deterministic executor. Takes no model client, so the replay path cannot call one."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import contracts as C
from .assumptions import verify, evidence_from
from .ops import OPS, Ctx
from .manifest import Manifest, validate_manifest
from .paths import get_path, parse_ref
from .schemas import SchemaError


def summarize(v, n: int = 220) -> str:
    s = json.dumps(v, default=str, separators=(",", ":"))
    return s if len(s) <= n else s[: n - 1] + "…"


def digest(v) -> str:
    return hashlib.sha256(json.dumps(v, default=str, sort_keys=True).encode()).hexdigest()[:12]


@dataclass
class RunResult:
    run_id: str
    workflow_id: str
    version: str
    inputs: dict
    outcome: str = "running"           # posted | held | halted | error
    halt: dict | None = None
    flagged: bool = False
    steps: list = field(default_factory=list)
    contract_results: list = field(default_factory=list)
    values: dict = field(default_factory=dict)
    ledger_entry: dict | None = None
    duration_ms: float = 0.0
    model_calls: int = 0
    assumptions: list = field(default_factory=list)
    recovery: dict | None = None
    snapshot_token: str | None = None
    verification_ms: float = 0.0
    verification_policy: str = "legacy_comparison"

    def posted_entry(self):
        return self.ledger_entry if self.outcome == "posted" else None

    def to_dict(self, with_values: bool = False) -> dict:
        d = {"run_id": self.run_id, "workflow_id": self.workflow_id, "version": self.version, "inputs": self.inputs, "outcome": self.outcome,
             "halt": self.halt, "flagged": self.flagged, "steps": self.steps, "contract_results": self.contract_results,
             "ledger_entry": self.ledger_entry, "duration_ms": round(self.duration_ms, 3), "model_calls": self.model_calls,
             "assumptions": self.assumptions, "recovery": self.recovery, "snapshot_token": self.snapshot_token, "verification_ms": round(self.verification_ms, 4), "verification_policy": self.verification_policy}
        if with_values:
            d["values"] = self.values
        return d


class Executor:
    def __init__(self, services, meter=None, emit=None, contracts_enabled: bool = True, schema_enabled: bool = True, strict: bool = False):
        self.services, self.meter, self.emit = services, meter, emit
        self.contracts_enabled, self.schema_enabled = contracts_enabled, schema_enabled
        self.strict = strict

    def _e(self, type_, run_id, **kw):
        if self.emit:
            self.emit({"type": type_, "run_id": run_id, "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), **kw})

    def run(self, manifest: Manifest, inputs: dict, run_id: str | None = None, *, reuse: dict | None = None, recovery: dict | None = None) -> RunResult:
        problems = validate_manifest(manifest)
        rid = run_id or "run_" + uuid.uuid4().hex[:10]
        res = RunResult(rid, manifest.workflow_id, manifest.version, dict(inputs))
        if problems:
            res.outcome, res.halt = "error", {"step": None, "reason": "invalid manifest", "detail": problems}
            return res
        t_run = time.perf_counter()
        snapshot = getattr(self.services, "snapshot_token", None)
        try:
            res.snapshot_token = snapshot(inputs["invoice_id"]) if snapshot else None
        except Exception:
            res.snapshot_token = None
        res.recovery = recovery
        if reuse and recovery and res.snapshot_token != recovery.get("expected_snapshot_token"):
            reuse = {}
            recovery["reused_nodes"] = []
            recovery["snapshot_matched"] = False
            recovery["fallback_reasons"].append("source snapshot changed at executor entry; full reread required")
        res.verification_policy = "strict_aair" if self.strict else "legacy_comparison"
        t_evidence = time.perf_counter()
        evidence = evidence_from(self.services, inputs["invoice_id"])
        res.verification_ms += (time.perf_counter() - t_evidence) * 1000
        def verify_now():
            t_verify = time.perf_counter()
            records = verify(manifest, res.values, evidence)
            res.verification_ms += (time.perf_counter() - t_verify) * 1000
            return records
        before = self.meter.snapshot()["total_model_calls"] if self.meter else 0
        ctx = Ctx(self.services, self.schema_enabled)
        scope = {"input": inputs}
        by_step = {}
        for c in manifest.contracts:
            s = manifest.step_for_op(c["after_op"])
            if s:
                by_step.setdefault(s.id, []).append(c)
        self._e("run_started", rid, workflow=manifest.workflow_id, version=manifest.version, inputs=inputs)
        halted = False
        verification_emitted = False
        for step in manifest.steps:
            rec = {"id": step.id, "operation": step.operation, "kind": step.kind, "status": "pending", "duration_ms": 0.0,
                   "output_hash": None, "summary": "", "model_calls": 0}
            res.steps.append(rec)
            if halted:
                rec["status"] = "skipped"
                continue
            if self.strict and step.kind == "sink":
                res.assumptions = verify_now()
                for a in res.assumptions:
                    self._e("assumption_verified", rid, step=a["node"], assumption=a)
                verification_emitted = True
                unsatisfied = [a for a in res.assumptions if a.get("required") and a["status"] != "VALID"]
                if unsatisfied:
                    first = next((a for a in unsatisfied if a["status"] == "INVALID"), unsatisfied[0])
                    rec["status"] = "skipped"
                    res.outcome, halted = "halted", True
                    res.halt = {"step": first["node"], "reason": "assumption_" + first["status"].lower(),
                                "assumption": first["id"], "message": first["reason"]}
                    self._e("run_halted", rid, **res.halt)
                    continue
                failed_warnings = [c for c in res.contract_results if not c['ok']]
                if res.flagged and failed_warnings and all(c['severity'] == 'warning' and c['type'] == 'range_log' for c in failed_warnings):
                    # Distribution range is an alert, not a unit proof. Independent monetary evidence
                    # can resolve it for this output; enum/schema/business failures are never overridden.
                    res.flagged = False
                    for warning in failed_warnings:
                        warning['resolution'] = 'resolved for this output by independent billing/settlement evidence'
                    self._e('warning_resolved', rid, step=step.id, reason='Independent monetary authority and business invariants agree; range alerts retained in trace.')
            self._e("step_started", rid, step=step.id, operation=step.operation)
            o = OPS[step.operation]
            t0 = time.perf_counter()
            try:
                kwargs = {}
                for name, ref in step.inputs.items():
                    root, path = parse_ref(ref)
                    kwargs[name] = get_path(scope[root], path) if path else scope[root]
                params = {k: v[1] for k, v in o.params.items()}
                params.update(step.params)
                ctx.flagged = res.flagged
                if reuse is not None and step.id in reuse and step.kind != "sink":
                    out = reuse[step.id]
                    rec["reused"] = True
                    self._e("checkpoint_reused", rid, step=step.id, output_hash=digest(out))
                else:
                    out = o.fn(ctx, **kwargs, **params)
            except SchemaError as e:
                rec.update(status="failed", duration_ms=(time.perf_counter() - t0) * 1000)
                res.halt = {"step": step.id, "reason": "schema_invalid", "detail": e.errors, "message": str(e)}
                self._e("schema_validation", rid, step=step.id, ok=False, errors=e.errors)
                res.outcome, halted = "halted", True
                self._e("run_halted", rid, step=step.id, reason="schema_invalid", message=str(e))
                continue
            except Exception as e:                      # a visible crash is not a silent error
                rec.update(status="failed", duration_ms=(time.perf_counter() - t0) * 1000, summary=f"{type(e).__name__}: {e}")
                res.halt = {"step": step.id, "reason": "exception", "message": f"{type(e).__name__}: {e}"}
                res.outcome, halted = "error", True
                self._e("run_halted", rid, step=step.id, reason="exception", message=rec["summary"])
                continue
            scope[step.id] = out
            res.values[step.id] = out
            rec.update(status="passed", duration_ms=(time.perf_counter() - t0) * 1000, output_hash=digest(out), summary=summarize(out))
            if step.kind == "mock_api" and self.schema_enabled:
                self._e("schema_validation", rid, step=step.id, ok=True)
            self._e("step_finished", rid, step=step.id, duration_ms=round(rec["duration_ms"], 3), summary=rec["summary"], output_hash=rec["output_hash"])
            if step.kind == "sink":
                res.ledger_entry = out
                self._e("ledger_posted", rid, step=step.id, entry=out)
            if self.contracts_enabled:
                for c in by_step.get(step.id, []):
                    r = C.evaluate(c, out)
                    r["step"] = step.id
                    if r.get("skipped"):
                        continue
                    res.contract_results.append(r)
                    self._e("contract_result", rid, step=step.id, **{k: r[k] for k in ("id", "kind", "severity", "ok", "observed", "expected", "message")})
                    if not r["ok"]:
                        if r["severity"] == "critical":
                            rec["status"] = "failed"
                            res.halt = {"step": step.id, "reason": "contract_failed", "contract": c["id"], "message": r["message"]}
                            res.outcome, halted = "halted", True
                            self._e("run_halted", rid, step=step.id, reason="contract_failed", contract=c["id"], message=r["message"])
                            break
                        res.flagged = True
                        self._e("run_flagged", rid, step=step.id, contract=c["id"], message=r["message"])
        res.assumptions = verify_now()
        if not verification_emitted:
            for a in res.assumptions:
                self._e("assumption_verified", rid, step=a["node"], assumption=a)
        if res.outcome == "running":
            res.outcome = "held" if (res.ledger_entry and res.ledger_entry.get("disposition") == "held") else "posted"
        res.duration_ms = (time.perf_counter() - t_run) * 1000
        res.model_calls = (self.meter.snapshot()["total_model_calls"] - before) if self.meter else 0
        self._e("run_finished", rid, outcome=res.outcome, flagged=res.flagged, duration_ms=round(res.duration_ms, 3), model_calls=res.model_calls)
        return res
