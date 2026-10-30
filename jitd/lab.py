"""Stateful demo lab: one workflow, one mock provider whose behaviour can be switched, runs, diagnoses, repairs, guards.
Every UI/API action calls a method here; nothing is animated without a backend event."""
from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from .bench import golden_regression
from .compiler import compile_workflow
from .diagnosis import diagnose, explain
from .executor import Executor, RunResult
from .fixtures import make_truth, Truth
from .manifest import Manifest
from .meter import ModelMeter
from .oracle import entry_matches, expected_ledger
from .repair import RepairProposal, attempt_repair, current_rules
from .scenarios import SCENARIOS, as_of_for
from .services import MockServices, capture_case
from .storage import Store
from .recovery import recover
from .escalation import choose
from .assumptions import registry

ROOT = Path(__file__).resolve().parent.parent


def _utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_write(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{uuid.uuid4().hex[:6]}.tmp")
    tmp.write_text(json.dumps(data, indent=1, default=str))
    os.replace(tmp, path)


class LabError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


class Lab:
    def __init__(self, data_dir: Path | None = None, llm_factory=None, run_cap: int = 200):
        self.dir = Path(data_dir or os.getenv("JITD_DATA_DIR") or ROOT / "data")
        self.llm_factory = llm_factory
        self.lock = threading.RLock()
        self.run_cap = run_cap
        self.store = Store(self.dir)
        snapshot = self.store.load()
        if snapshot:
            self._restore(snapshot)
        else:
            self.reset()

    # ---------------------------------------------------------------- lifecycle
    def reset(self):
        with self.lock:
            if getattr(self, "repairing", False):
                raise LabError("busy", "a repair is in progress", 409)
            self.paused = False
            self.meter = ModelMeter()
            self.services = MockServices([], "clean")
            self.scenario_id, self.n = "clean", 0
            self.injected_at = None
            self.runs: OrderedDict[str, dict] = OrderedDict()
            self.guards: list[dict] = []
            self.regression = golden_regression(20)
            started = time.perf_counter()
            self.manifest, self.compile_report = compile_workflow(None, self.meter)
            self.meter.record_runtime("compile", (time.perf_counter()-started)*1000)
            self.compile_mode = "deterministic"
            self.repairing = False
            self._persist_manifest()
            self._checkpoint("reset")

    def _persist_manifest(self):
        atomic_write(self.dir / "workflows" / self.manifest.workflow_id / f"{self.manifest.version}.json", self.manifest.model_dump())

    def _checkpoint(self, action, detail=None):
        payload = {
            "manifest": self.manifest.model_dump(), "compile_report": self.compile_report,
            "compile_mode": self.compile_mode, "scenario": self.scenario_id, "n": self.n,
            "injected_at": self.injected_at, "regression": self.regression, "guards": self.guards,
            "paused": self.paused, "meter": {"calls": self.meter.calls, "tokens": self.meter.tokens,
                "usage": self.meter.usage, "runtime_ms": self.meter.runtime_ms},
            "truths": [asdict(t) for t in self.services.truths.values()],
            "ledger": self.services.ledger, "calls": self.services.calls, "evidence_mode": self.services.evidence_mode,
            "runs": [{**{k: v for k, v in r.items() if k not in ("manifest", "result")},
                      "manifest": r["manifest"].model_dump(), "result": asdict(r["result"])} for r in self.runs.values()]
        }
        self.store.save(payload, action, detail)

    def _restore(self, p):
        self.manifest = Manifest.model_validate(p["manifest"])
        if not self.manifest.assumptions:
            self.manifest.assumptions = registry(self.manifest)
        self.compile_report, self.compile_mode = p["compile_report"], p["compile_mode"]
        self.scenario_id, self.n, self.injected_at = p["scenario"], p["n"], p["injected_at"]
        self.regression, self.guards = p["regression"], p["guards"]
        self.paused, self.repairing = p.get("paused", False), False
        self.meter = ModelMeter()
        self.meter.calls, self.meter.tokens = p["meter"]["calls"], p["meter"]["tokens"]
        self.meter.usage = p["meter"].get("usage", [])
        self.meter.runtime_ms.update(p["meter"].get("runtime_ms", {}))
        truths = []
        for raw in p["truths"]:
            t = dict(raw)
            t["line_items"] = tuple((sku, qty, Decimal(price)) for sku, qty, price in t["line_items"])
            t["payments"] = tuple((pid, Decimal(amount), at) for pid, amount, at in t["payments"])
            for k in ("tax", "discount", "total"):
                t[k] = Decimal(t[k])
            truths.append(Truth(**t))
        self.services = MockServices(truths, SCENARIOS[self.scenario_id].behavior)
        self.services.ledger, self.services.calls = p["ledger"], p["calls"]
        self.services.evidence_mode = p.get("evidence_mode", "independent")
        self.runs = OrderedDict()
        for r in p["runs"]:
            r["manifest"] = Manifest.model_validate(r["manifest"])
            r["result"] = RunResult(**r["result"])
            self.runs[r["run_id"]] = r

    def _mutable(self):
        if self.repairing:
            raise LabError("busy", "a repair is in progress", 409)

    def compile(self, use_model: bool = False) -> dict:
        with self.lock:
            self._mutable()
            if self.manifest.version != "1.0.0" or self.guards:
                raise LabError("already_repaired", "Reset the sandbox before compiling a new initial plan.", 409)
            llm = None
            if use_model:
                if self.llm_factory is None:
                    raise LabError("model_unavailable", "No Nebius model is configured on this server (set NEBIUS_API_KEY and NEBIUS_MODEL_ID).", 400)
                llm = self.llm_factory(self.meter)
            started = time.perf_counter()
            self.manifest, self.compile_report = compile_workflow(llm, self.meter)
            self.meter.record_runtime("compile", (time.perf_counter()-started)*1000)
            self.compile_mode = "model" if llm is not None else "deterministic"
            self._persist_manifest()
            self._checkpoint("compile", {"mode": self.compile_mode})
            return {"version": self.manifest.version, "report": self.compile_report, "meter": self.meter.snapshot()}

    def inject(self, scenario_id: str) -> dict:
        with self.lock:
            self._mutable()
            sc = SCENARIOS.get(scenario_id)
            if sc is None:
                raise LabError("unknown_scenario", f"unknown scenario {scenario_id!r}")
            self.scenario_id = scenario_id
            self.services.set_behavior(sc.behavior)
            if self.injected_at is None and sc.behavior != "clean" or (sc.truth_mod and self.injected_at is None):
                self.injected_at = self.n
            if scenario_id == "clean" and self.injected_at is None:
                pass
            self._checkpoint("scenario_changed", {"scenario": scenario_id})
            return {"scenario": scenario_id, "behavior": sc.behavior, "title": sc.title, "desc": sc.desc}

    # ---------------------------------------------------------------- runs
    def _truth(self):
        sc = SCENARIOS[self.scenario_id]
        post = self.injected_at is not None
        kw = {}
        if sc.truth_mod == "short":
            kw["short"] = True
        if sc.truth_mod == "big":
            kw["big"] = True
        if sc.installments or sc.behavior in ("truncation", "cents_truncation"):
            kw["installments"] = 4
        t = make_truth(f"lab{self._gen}", self.n, "post" if post else "pre", **kw)
        self.services.add_truth(t)
        return t, post

    _gen = 0

    def run(self, emit=None, invoice_id: str | None = None, *, strict: bool = True) -> dict:
        with self.lock:
            self._mutable()
            if self.paused:
                raise LabError("paused", "Workflow is paused. Resume it from Overview.", 409)
            if invoice_id:
                if invoice_id not in self.services.truths:
                    raise LabError("unknown_invoice", "unknown invoice id")
                t, post = self.services.truths[invoice_id], self.injected_at is not None
            else:
                t, post = self._truth()
            as_of = as_of_for(self.n, post)
            self.n += 1
            manifest = self.manifest
            source = next((rec for rec in reversed(list(self.runs.values()))
                           if invoice_id and rec["invoice_id"] == invoice_id and rec["result"].outcome in ("halted", "held")
                           and (rec.get("repair") or {}).get("accepted")), None)
            if source and strict:
                recovery_started = time.perf_counter()
                res = recover(source["manifest"], manifest, source["result"], self.services, self.meter, emit)
                self.meter.record_runtime("repair", max(0, (time.perf_counter()-recovery_started)*1000-res.duration_ms))
                as_of = res.inputs["as_of"]
            else:
                res = Executor(self.services, self.meter, emit, strict=strict).run(manifest, {"invoice_id": t.invoice_id, "as_of": as_of})
            self.meter.record_runtime("execution", res.duration_ms-res.verification_ms)
            self.meter.record_runtime("verification", res.verification_ms)
            exp = expected_ledger(t)
            correct = (res.outcome == "posted" and entry_matches(res.posted_entry(), exp))
            verdict = ("correct_post" if correct else "silent_error" if res.outcome == "posted" else
                       "correct_block" if exp is None and res.outcome != "posted" else "blocked")
            rec = {"run_id": res.run_id, "scenario": self.scenario_id, "behavior": self.services.behavior, "invoice_id": t.invoice_id, "as_of": as_of, "manifest": manifest,
                   "result": res, "expected": exp, "oracle_verdict": verdict, "truth_total": str(t.total), "created": _utc(), "diagnosis": None, "repair": None}
            self.runs[res.run_id] = rec
            while len(self.runs) > self.run_cap:
                self.runs.popitem(last=False)
            self._checkpoint("run_completed", {"run_id": res.run_id, "outcome": res.outcome, "oracle_verdict": verdict})
            return self.run_view(rec)

    def hard_case(self, n: int = 10) -> dict:
        """Inject consistent_scale and run n invoices. Reports, per invoice, what each check saw. Never repairs."""
        n = max(1, min(int(n), 30))
        with self.lock:
            self.inject("consistent_scale")
            rows = []
            for _ in range(n):
                v = self.run(strict=False)
                cr = {c["id"]: c for c in v["contract_results"]}
                rng = cr.get("mined-invoice-total-range")
                raw_total = (v["raw_samples"].get("fetch_invoice") or {})
                rows.append({"run_id": v["run_id"], "invoice_id": v["inputs"]["invoice_id"],
                             "raw_invoice_total": raw_total.get("total") if isinstance(raw_total, dict) else None,
                             "true_total_usd": self.runs[v["run_id"]]["truth_total"],
                             "arithmetic_ok": cr.get("invoice-arithmetic", {}).get("ok"),
                             "payment_match_ok": cr.get("payment-matches-invoice", {}).get("ok"),
                             "magnitude_flagged": bool(rng and not rng["ok"]), "learned_range": rng and rng["expected"],
                             "outcome": v["outcome"], "oracle_verdict": v["oracle_verdict"]})
            held = sum(1 for r in rows if r["outcome"] == "held")
            wrong = sum(1 for r in rows if r["oracle_verdict"] == "silent_error")
            return {"scenario": "consistent_scale", "n": n, "rows": rows, "held": held, "posted_wrong": wrong,
                    "reconciliation_blind": all(r["arithmetic_ok"] and r["payment_match_ok"] for r in rows),
                    "repair_offered": False,
                    "explanation": ("Invoice and payments both moved to cents, so invoice-arithmetic and payment-matches-invoice still pass: "
                                    "reconciliation cannot see this. Only the learned magnitude range can, and it is a warning. "
                                    "Large invoices leave the learned range and are held for a human; a small invoice can stay inside the range even after x100 and post wrong silently (the benchmark measures how often; a sample this small may show none). "
                                    "No repair is offered: with both sources moving together there is no independent evidence of the correct divisor, so a human decides."),
                    "meter": self.meter.snapshot()}

    def run_view(self, rec: dict) -> dict:
        r = rec["result"]
        d = r.to_dict()
        d.update(scenario=rec["scenario"], behavior=rec["behavior"], as_of=rec["as_of"], oracle_verdict=rec["oracle_verdict"], expected=rec["expected"],
                 created=rec["created"], model_calls=r.model_calls, meter=self.meter.snapshot(), diagnosis=rec["diagnosis"],
                 repair=self._repair_view(rec["repair"]), manifest_version=rec["manifest"].version,
                 raw_samples={k: v for k, v in r.values.items() if k in ("fetch_invoice", "fetch_payments", "normalize_amount", "sum_payments", "expected_total", "reconcile")})
        return json.loads(json.dumps(d, default=str))

    @staticmethod
    def _repair_view(rep):
        if not rep:
            return None
        return {k: v for k, v in rep.items() if k not in ("candidate", "drift_cases")}

    def get_run(self, run_id: str) -> dict:
        rec = self.runs.get(run_id)
        if rec is None:
            raise LabError("run_not_found", "run not found (only recent runs are kept in memory)", 404)
        return rec

    # ---------------------------------------------------------------- diagnose / repair
    def diagnose(self, run_id: str) -> dict:
        with self.lock:
            rec = self.get_run(run_id)
            r = rec["result"]
            if r.outcome not in ("halted", "held"):
                raise LabError("nothing_to_diagnose", f"run outcome is {r.outcome!r}; only halted or held runs are diagnosed", 409)
            d = diagnose(rec["manifest"], r)
            d["explanation"] = explain(d)
            d["escalation"] = choose(r, d, self.llm_factory is not None)
            rec["diagnosis"] = d
            self._checkpoint("diagnosed", {"run_id": run_id, "status": d["status"]})
            return d

    def repair(self, run_id: str, mode: str = "auto", preview: bool = False, proposal_override: RepairProposal | None = None) -> dict:
        with self.lock:
            rec = self.get_run(run_id)
            if rec["diagnosis"] is None:
                self.diagnose(run_id)
            if rec["manifest"].version != self.manifest.version:
                raise LabError("stale_run", "this run used an older workflow version; run again before repairing", 409)
            if self.repairing:
                raise LabError("busy", "a repair is already in progress", 409)
            self.repairing = True
        try:
            llm = None
            if mode == "model":
                if self.llm_factory is None:
                    raise LabError("model_unavailable", "No Nebius model is configured on this server.", 400)
                llm = self.llm_factory(self.meter)
            override = proposal_override
            if mode == "wrong":
                rules = current_rules(self.manifest)
                override = RepairProposal(op="normalize_money", param="rules", source="operator_override",
                                          value=rules + [{"divisor": 10, "effective_from": rec["as_of"]}],
                                          rationale="DEMO: a deliberately wrong divisor (10) to show that validation rejects bad repairs")
            if mode not in ("auto", "model", "wrong"):
                raise LabError("bad_mode", "mode must be auto, model or wrong")
            if rec["scenario"] != self.scenario_id:
                raise LabError("scenario_changed", "Provider behaviour changed since this run; run it again before repairing.", 409)
            fresh = []
            for _ in range(4):
                t, post = self._truth()
                fresh.append((t.invoice_id, as_of_for(self.n, post), expected_ledger(t)))     # same clock rule as run(): one tick per invoice
                self.n += 1
            failing = [(rec["invoice_id"], rec["as_of"], rec["expected"])]
            before = self.meter.snapshot()["repair_model_calls"]
            repair_started = time.perf_counter()
            out = attempt_repair(self.manifest, rec["diagnosis"], self.services, failing, self.regression, llm=llm, override=override, isolated=True, fresh=fresh)
            self.meter.record_runtime("repair", (time.perf_counter()-repair_started)*1000)
            out["repair_model_calls"] = self.meter.snapshot()["repair_model_calls"] - before
            with self.lock:
                if preview and out["accepted"]:
                    pid = "proposal_" + uuid.uuid4().hex[:10]
                    pending = {"id": pid, "run_id": run_id, "version": self.manifest.version,
                               "scenario": self.scenario_id, "created": _utc(), "record": out}
                    self.store.proposal(pid, pending)
                    self._checkpoint("repair_proposed", {"proposal_id": pid, "run_id": run_id})
                    return {"proposal_id": pid, "status": "pending", "validated": True,
                            "repair": self._repair_view(out)}
                rec["repair"] = out
                if out["accepted"]:
                    old = self.manifest
                    self.manifest = Manifest.model_validate(out["candidate"])
                    self._persist_manifest()
                    cases = out.get("drift_cases") and [capture_case(self.services, i, a, e) for i, a, e in failing + fresh] or []
                    self.regression = self.regression + cases
                    guard = {"guard_id": "grd_" + uuid.uuid4().hex[:8], "created": _utc(), "workflow_id": old.workflow_id, "from_version": old.version,
                             "to_version": self.manifest.version, "signature": {"detected_contract": rec["diagnosis"]["detected_at"].get("contract"),
                                                                                  "hypothesis": rec["diagnosis"]["top"]["name"], "fault_op": rec["diagnosis"]["top"]["op"]},
                             "repair": {k: v for k, v in out["proposals"][-1].items() if k != "validation"}, "validation": out["proposals"][-1]["validation"],
                             "regression_cases_added": len(cases), "regression_cases_total": len(self.regression), "decision": "accepted"}
                    atomic_write(self.dir / "guards" / f"{guard['guard_id']}.json", guard)
                    atomic_write(self.dir / "regression" / f"{old.workflow_id}.json", {"cases": self.regression})
                    self.guards.append(guard)
                    out["guard_id"] = guard["guard_id"]
                self._checkpoint("repair_accepted" if out["accepted"] else "repair_rejected", {"run_id": run_id, "version": self.manifest.version})
            return self._repair_view(out)
        finally:
            with self.lock:
                self.repairing = False

    def decide(self, proposal_id, approve):
        with self.lock:
            self._mutable()
            p = self.store.proposal(proposal_id)
            if p is None:
                raise LabError("proposal_not_found", "Proposal not found.", 404)
            if p["status"] != "pending":
                raise LabError("proposal_decided", "This proposal already has a decision.", 409)
            if not approve:
                self.store.proposal(proposal_id, p, "rejected")
                self._checkpoint("proposal_rejected", {"proposal_id": proposal_id})
                return {"status": "rejected"}
            if p["version"] != self.manifest.version or p["scenario"] != self.scenario_id:
                raise LabError("stale_proposal", "Workflow or provider changed; propose a repair from a new run.", 409)
            # Revalidate against fresh inputs at approval time. Never trust the old report alone.
            accepted = [x for x in p['record']['proposals'] if x.get('status') == 'accepted']
            if len(accepted) != 1:
                raise LabError('invalid_proposal', 'Saved proposal does not contain one accepted bounded repair.', 409)
            exact = RepairProposal.model_validate({k: accepted[0][k] for k in ('op', 'param', 'value', 'rationale', 'source')})
            result = self.repair(p["run_id"], "auto", proposal_override=exact)
            self.store.proposal(proposal_id, p, "approved" if result["accepted"] else "validation_failed")
            self._checkpoint("proposal_decided", {"proposal_id": proposal_id, "accepted": result["accepted"]})
            return result

    def pause(self, paused):
        with self.lock:
            self._mutable()
            self.paused = paused
            self._checkpoint("paused" if paused else "resumed")
            return {"paused": paused}

    def rollback(self, target_version):
        with self.lock:
            self._mutable()
            if not self.paused:
                raise LabError("pause_required", "Pause the workflow before rolling back.", 409)
            if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", target_version):
                raise LabError("bad_version", "Invalid workflow version.")
            path = self.dir / "workflows" / self.manifest.workflow_id / (target_version + ".json")
            if not path.exists():
                raise LabError("version_not_found", "Version not found.", 404)
            old = self.manifest.version
            candidate = Manifest.model_validate(json.loads(path.read_text(encoding="utf-8")))
            if target_version == old:
                raise LabError("same_version", "Workflow already uses this version.", 409)
            major, minor, patch = map(int, old.split("."))
            candidate.version = f"{major}.{minor}.{patch + 1}"
            candidate.meta = {**candidate.meta, "rollback_of": old, "restored_from": target_version}
            self.manifest = candidate
            self._persist_manifest()
            self._checkpoint("rollback", {"from": old, "restored_from": target_version, "version": candidate.version})
            return {"version": candidate.version, "paused": True, "restored_from": target_version}

    # ---------------------------------------------------------------- views
    def state(self) -> dict:
        with self.lock:
            sc = SCENARIOS[self.scenario_id]
            return {"paused": self.paused, "scenario": self.scenario_id, "scenario_title": sc.title, "behavior": self.services.behavior, "workflow": {
                        "id": self.manifest.workflow_id, "version": self.manifest.version, "meta": self.manifest.meta,
                        "steps": [{"id": s.id, "operation": s.operation, "kind": s.kind, "params": s.params, "deps": d}
                                  for s, d in zip(self.manifest.steps, self.manifest.deps().values())],
                        "contracts": [{k: v for k, v in c.items()} for c in self.manifest.contracts], "assumptions": self.manifest.assumptions},
                    "compile_mode": self.compile_mode, "compile_report": self.compile_report, "meter": self.meter.snapshot(), "runs": self.n,
                    "ledger": self.services.ledger[-8:], "guards": [{k: g[k] for k in ("guard_id", "created", "from_version", "to_version", "signature", "regression_cases_total")} for g in self.guards],
                    "repairing": self.repairing, "evidence_mode": self.services.evidence_mode, "regression_cases": len(self.regression)}

    def export_run(self, run_id: str) -> dict:
        rec = self.get_run(run_id)
        v = self.run_view(rec)
        return {"kind": "jitd_run_export", "schema": "jitd.export/1", "exported_utc": _utc(), "mode": "mock_services",
                "note": "Synthetic data. Provider behaviour was injected by the demo lab. Not a production trace.", "run": v, "manifest": rec["manifest"].model_dump()}
