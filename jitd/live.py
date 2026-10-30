"""Live-evidence harness: exercises the REAL Nebius/Nemotron path and writes an inspectable record.

    NEBIUS_API_KEY=... NEBIUS_MODEL_ID=... python -m jitd.live [--compiles 3]

Writes evidence/live_<stamp>.json and .md. The API key is never written; errors are sanitized.
This file only records what happened. If the model fails, the failure is the evidence.
"""
from __future__ import annotations

import argparse
import json
import tempfile
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

from . import llm as llm_mod
from .compiler import compile_workflow
from .lab import Lab, LabError
from .meter import ModelMeter

ROOT = Path(__file__).resolve().parent.parent
REPAIR_SCENARIOS = ("unit_cents", "unit_mills", "truncation")


def _utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def collect(client_factory, model_id: str, compiles: int = 3, *, source_mode="injected_client", checkpoint=None) -> dict:
    if not 1 <= compiles <= 10:
        raise ValueError("compiles must be between 1 and 10")
    ev = {"kind": "jitd_live_evidence", "started_utc": _utc(), "model_id": model_id, "smoke": None, "compiles": [], "repairs": [],
          "source_mode": source_mode, "honesty": "Collected from the configured client. Only source_mode=nebius_api denotes real provider calls. Financial fixtures are synthetic. Failures and fallbacks are retained."}
    meter = ModelMeter()
    try:
        c = client_factory(meter)
        txt = c.complete("compile", "Reply with the single word OK.", "ping", max_tokens=8)
        ev["smoke"] = {"ok": True, "expected_reply": txt.strip() == "OK", "latency_s": round(c.latency_s[-1], 2)}
    except Exception as e:
        ev["smoke"] = {"ok": False, "error": llm_mod.sanitize(e)}
        ev["smoke_meter"] = meter.snapshot()
        ev["smoke_usage"] = meter.usage
        ev["finished_utc"] = _utc()
        ev["summary"] = summarize(ev)
        if checkpoint:
            checkpoint(ev)
        return ev
    ev["smoke_meter"] = meter.snapshot()
    ev["smoke_usage"] = meter.usage
    if checkpoint:
        checkpoint(ev)
    for i in range(compiles):
        m = ModelMeter()
        try:
            manifest, rep = compile_workflow(client_factory(m), m)
            ev["compiles"].append({"attempt": i + 1, "plan_source": rep["plan_source"], "model": rep.get("model"), "rejections": rep["rejections"],
                                   "used_model_plan": rep["plan_source"].startswith("nemotron"), "manifest": manifest.model_dump(), "meter": m.snapshot(), "provider_usage": m.usage})
        except Exception as e:
            ev["compiles"].append({"attempt": i + 1, "error": llm_mod.sanitize(e), "meter": m.snapshot(), "provider_usage": m.usage})
        if checkpoint:
            checkpoint(ev)
    for sid in REPAIR_SCENARIOS:
        row = {"scenario": sid}
        lab = None
        try:
            with tempfile.TemporaryDirectory() as td:
                lab = Lab(Path(td), llm_factory=client_factory)
                for _ in range(3):
                    lab.run()
                lab.inject(sid)
                run = None
                for _ in range(12):
                    run = lab.run()
                    if run["outcome"] in ("halted", "held"):
                        break
                row["run_id"], row["outcome"] = run["run_id"], run["outcome"]
                if run["outcome"] in ("halted", "held"):
                    d = lab.diagnose(run["run_id"])
                    row["diagnosis"] = {"status": d["status"], "top": d["top"] and {k: d["top"][k] for k in ("name", "op", "score")}}
                    rep = lab.repair(run["run_id"], mode="model")
                    row["repair"] = {k: rep.get(k) for k in ("decision", "accepted", "proposals", "repair_model_calls", "guard_id")}
                    if rep.get("accepted"):
                        retry = lab.run(invoice_id=run["inputs"]["invoice_id"])
                        row["aair_retry"] = {k: retry[k] for k in ("run_id", "outcome", "oracle_verdict", "assumptions", "recovery", "duration_ms", "verification_ms")}
                    props = rep.get("proposals") or []
                    row["nemotron_proposal_accepted"] = any(p.get("source") == "nemotron" and p.get("status") == "accepted" for p in props)
                    row["deterministic_fallback_accepted"] = any(p.get("source") != "nemotron" and p.get("status") == "accepted" for p in props)
                row["meter"] = lab.meter.snapshot()
                row["provider_usage"] = lab.meter.usage
        except Exception as e:
            row["error"] = llm_mod.sanitize(e)
            if lab is not None:
                row["meter"] = lab.meter.snapshot()
                row["provider_usage"] = lab.meter.usage
        ev["repairs"].append(row)
        if checkpoint:
            checkpoint(ev)
    ev["finished_utc"] = _utc()
    ev["summary"] = summarize(ev)
    if checkpoint:
        checkpoint(ev)
    return ev


def summarize(ev):
    usage = list(ev.get('smoke_usage', []))
    for row in ev.get('compiles', []) + ev.get('repairs', []):
        usage.extend(row.get('provider_usage', []))
    model_plans = sum(bool(r.get('used_model_plan')) for r in ev.get('compiles', []))
    return {'source_mode': ev.get('source_mode'), 'recorded_requests': len(usage),
            'failed_requests': sum(u.get('status') == 'failed_usage_unknown' for u in usage),
            'usage_complete': bool(usage) and all(u.get('source') == 'provider' and u.get('status', 'succeeded') == 'succeeded' for u in usage),
            'reported_input_tokens': sum(u.get('input_tokens') or 0 for u in usage),
            'reported_output_tokens': sum(u.get('output_tokens') or 0 for u in usage),
            'reported_total_tokens': sum(u.get('total_tokens') or 0 for u in usage),
            'model_plans_validated': model_plans,
            'model_repairs_validated': sum(bool(r.get('nemotron_proposal_accepted')) for r in ev.get('repairs', [])),
            'fallback_repairs_validated': sum(bool(r.get('deterministic_fallback_accepted')) for r in ev.get('repairs', [])),
            'correct_recoveries': sum(r.get('aair_retry', {}).get('oracle_verdict') == 'correct_post' for r in ev.get('repairs', [])),
            'estimated_usd': None,
            'limits': 'Reported tokens are a lower bound when usage is missing; unknown is not zero billing. Synthetic financial data; no paired real-agent or field accuracy claim.'}


def preflight(compiles):
    if not 1 <= compiles <= 10:
        raise ValueError('compiles must be between 1 and 10')
    code = hashlib.sha256()
    for p in sorted((ROOT / 'jitd').glob('*.py')):
        code.update(p.name.encode()); code.update(p.read_bytes())
    return {'kind': 'live_preflight_no_calls', 'compiles': compiles,
            'configured': llm_mod.available(), 'budget': llm_mod.budget(),
            'conservative_request_bound': 2*compiles+10,
            'sdk_automatic_retries': 0, 'code_sha256': code.hexdigest(),
            'note': 'Request ceiling, not a dollar ceiling. Failed requests can consume quota and have unknown billing.'}


def to_markdown(ev: dict) -> str:
    L = [f"# JIT-D live evidence", "", f"- model: `{ev['model_id']}`", f"- started: {ev['started_utc']}  finished: {ev.get('finished_utc')}",
         f"- smoke call: {ev['smoke']}", "", "## Compiles", ""]
    for c in ev["compiles"]:
        if "error" in c:
            L.append(f"- attempt {c['attempt']}: ERROR {c['error']}")
        else:
            L.append(f"- attempt {c['attempt']}: **{c['plan_source']}**; rejections: {json.dumps(c['rejections'])}; calls: {c['meter']['total_model_calls']}")
    L += ["", "## Repairs", ""]
    for r in ev["repairs"]:
        L.append(f"- `{r['scenario']}`: run `{r.get('run_id')}` outcome={r.get('outcome')} repair={r.get('repair', {}).get('decision') if r.get('repair') else None} "
                 f"nemotron_accepted={r.get('nemotron_proposal_accepted')} fallback_accepted={r.get('deterministic_fallback_accepted')} {('ERROR ' + r['error']) if r.get('error') else ''}")
    L += ["", "## Accounting", "", "```json", json.dumps(ev.get('summary', {}), indent=2), "```", ""]
    L += ["", "Plan sources and proposal sources are labelled above; a 'deterministic fallback' line means the model's output was NOT what ran.", ""]
    return "\n".join(L)


def main():
    import os
    ap = argparse.ArgumentParser()
    ap.add_argument("--compiles", type=int, default=3)
    ap.add_argument("--out", default=str(ROOT / "evidence"))
    ap.add_argument("--ask-api-key", action="store_true", help="Hidden terminal prompt; never saved")
    ap.add_argument("--plan", action="store_true", help="Print configuration and conservative request bound without provider calls")
    a = ap.parse_args()
    from .launch import load_env
    load_env(ROOT / '.env')
    if a.ask_api_key:
        import getpass
        os.environ['NEBIUS_API_KEY'] = getpass.getpass('Nebius API key (hidden): ').strip()
    from .platform import data_dir
    os.environ.setdefault('JITD_MAX_MODEL_CALLS', '0')
    try:
        if not 0 <= int(os.environ['JITD_MAX_MODEL_CALLS']) <= 10000:
            raise ValueError()
    except ValueError:
        ap.error('JITD_MAX_MODEL_CALLS must be an integer from 0 to 10000; no provider call was made')
    os.environ.setdefault('JITD_BUDGET_DB', str(data_dir() / 'platform.sqlite3'))
    try:
        plan = preflight(a.compiles)
    except ValueError as e:
        ap.error(str(e))
    if a.plan:
        print(json.dumps(plan, indent=2))
        return
    if not llm_mod.available():
        raise SystemExit("Set NEBIUS_API_KEY and NEBIUS_MODEL_ID first. Nothing was run.")
    model = os.environ["NEBIUS_MODEL_ID"]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = out / f"live_{stamp}.json"
    def save_progress(ev):
        snapshot = dict(ev, preflight=plan, summary=summarize(ev))
        temp = target.with_suffix('.tmp')
        temp.write_text(json.dumps(snapshot, indent=1, default=str), encoding='utf-8')
        temp.replace(target)
    ev = collect(lambda meter: llm_mod.NebiusClient(meter, model), model, a.compiles,
                 source_mode="nebius_api", checkpoint=save_progress)
    ev["preflight"] = plan
    (out / f"live_{stamp}.md").write_text(to_markdown(ev), encoding='utf-8')
    print("wrote", out / f"live_{stamp}.json", "| smoke ok:", ev["smoke"].get("ok"))


if __name__ == "__main__":
    main()
