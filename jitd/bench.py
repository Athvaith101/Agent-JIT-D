"""Reproducible benchmark of five strategies on identical seeded streams.

    python -m jitd.bench                 # 30 seeds x 120 runs per scenario  -> benchmark/results/runs/
    python -m jitd.bench --seeds 5       # quick smoke run

Everything here is MOCK SERVICES + a deterministic repair synthesizer. Agent strategies are MODELLED (cost/latency are
assumptions below; the agent is assumed to be correct on every run, which is generous to those baselines).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import SUITE_VERSION
from .compiler import GOLDEN_AS_OF, compile_workflow
from .diagnosis import diagnose
from .executor import Executor
from .fixtures import golden_truths
from .oracle import entry_matches, expected_ledger
from .repair import attempt_repair
from .scenarios import SCENARIOS, build_stream
from .services import MockServices, capture_case

ROOT = Path(__file__).resolve().parent.parent
ASSUMPTIONS = {
    "agent_tokens_in": 4000, "agent_tokens_out": 600, "price_in_usd_per_m_tokens": 0.20, "price_out_usd_per_m_tokens": 0.60,
    "agent_latency_s_per_call": 3.0,
    "note": "ASSUMPTIONS, not measurements: per-call token counts, prices and latency for an LLM agent run. Edit jitd/bench.py to change them. "
            "Agent strategies are assumed correct on every run (generous to the baselines).",
}
STRATEGIES = ["agent_every_run", "naive_replay", "schema_only", "fixed_audit_10", "fixed_audit_25", "jitd_guarded"]
DEFINITIONS = {
    "silent_error": "A ledger entry was POSTED that differs from the independent oracle (or was posted when the oracle says a human must review). Held, halted and crashed runs are not silent.",
    "silent_error_rate": "silent_error / post-onset runs. Lower is better.",
    "needs_protection": "A post-onset run where unguarded naive replay does not produce the oracle-correct posted entry (wrong entry, entry that should not exist, or a crash).",
    "detection_rate": "Share of needs_protection runs the strategy handled: correct entry posted (recovered), or correctly blocked/held. Higher is better.",
    "false_block": "A run where naive replay was correct (so no protection was needed) but the strategy halted or held it. Held-for-review counts: it costs an operator.",
    "false_block_rate": "false_block / post-onset runs where naive replay is correct.",
    "localization": "On the first halted/flagged run of a stream: the top-ranked hypothesis names the scenario's true fault location (or correctly says 'business exception').",
    "repair": "A repair is accepted only if every drift case and regression case passes in an isolated validation run and the oracle agrees.",
}
GLYPH = {"correct_post": "C", "silent_error": "S", "false_block": "F", "blocked_drift": "B", "correct_block": "K", "recovered": "R"}


def code_version() -> str:
    h = hashlib.sha256()
    for p in sorted((ROOT / "jitd").glob("*.py")):
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0, c - h), 4), round(min(1, c + h), 4)]


def agent_call_cost(calls: int) -> float:
    a = ASSUMPTIONS
    return calls * (a["agent_tokens_in"] * a["price_in_usd_per_m_tokens"] + a["agent_tokens_out"] * a["price_out_usd_per_m_tokens"]) / 1e6


def golden_regression(n: int = 20):
    gt = golden_truths(n)
    gs = MockServices(gt, "clean")
    return [capture_case(gs, t.invoice_id, GOLDEN_AS_OF, expected_ledger(t)) for t in gt]


def _classify(status: str, entry, expected, naive_ok: bool) -> str:
    """status: posted | blocked"""
    if status == "posted":
        return "correct_post" if entry_matches(entry, expected) else "silent_error"
    if expected is None:
        return "correct_block"
    return "false_block" if naive_ok else "blocked_drift"


def _exec(services, manifest, run, **kw):
    services.set_behavior(run.behavior)
    t0 = time.perf_counter()
    r = Executor(services, **kw).run(manifest, {"invoice_id": run.truth.invoice_id, "as_of": run.as_of})
    return r, (time.perf_counter() - t0) * 1000


def simulate_stream(strategy: str, runs, manifest, regression, naive_ok: list[bool], scenario_id: str) -> dict:
    sc = SCENARIOS[scenario_id]
    services = MockServices([r.truth for r in runs], "clean", mutations=sc.mutations)
    glyphs, lat, calls, episodes = [], [], 0, []
    agent_mode, repaired, attempts = False, False, 0
    cur = manifest
    audit_n = int(strategy.split("_")[-1]) if strategy.startswith("fixed_audit") else None
    for run in runs:
        if not run.post:
            glyphs.append(".")
            if strategy in ("agent_every_run",):
                calls += 1
            elif agent_mode:
                calls += 1
            continue
        ok = naive_ok[run.index]
        exp = run.expected
        if strategy == "agent_every_run" or agent_mode:
            calls += 1
            status, entry = ("posted", exp) if exp is not None else ("blocked", None)
            glyphs.append(_g(status, entry, exp, ok, run, naive_ok))
            continue
        if strategy == "naive_replay":
            r, ms = _exec(services, cur, run, contracts_enabled=False, schema_enabled=False)
        elif strategy == "schema_only":
            r, ms = _exec(services, cur, run, contracts_enabled=False, schema_enabled=True)
        elif strategy.startswith("fixed_audit"):
            r, ms = _exec(services, cur, run, contracts_enabled=False, schema_enabled=False)
            if run.index % audit_n == 0:
                calls += 1
                agent_entry = exp
                mismatch = (r.outcome == "posted" and not entry_matches(r.posted_entry(), agent_entry)) or (r.outcome == "posted" and agent_entry is None)
                if mismatch:
                    agent_mode = True
                    glyphs.append(_g("blocked", None, exp, ok, run, naive_ok))
                    lat.append(ms)
                    continue
        else:                                                    # jitd_guarded
            r, ms = _exec(services, cur, run)
            if r.outcome in ("halted", "held") and attempts < 2 and not repaired:
                d = diagnose(cur, r)
                ep = {"run_index": run.index, "diagnosis": d["status"], "top": d["top"]["name"] if d["top"] else None,
                      "top_op": d["top"]["op"] if d["top"] else None, "expected_fault_op": sc.fault_op, "scenario_kind": sc.kind}
                attempts += 1
                if d["status"] == "localized" and d["top"]["name"] in ("unit_scale", "truncated_pagination"):
                    nxt = [x for x in runs[run.index + 1: run.index + 6] if x.post]
                    services.set_behavior(run.behavior)
                    rep = attempt_repair(cur, d, services, [(run.truth.invoice_id, run.as_of, exp)], regression, isolated=False,
                                         fresh=[(x.truth.invoice_id, x.as_of, x.expected) for x in nxt])
                    ep.update(repair=rep["decision"], proposals=[p["status"] for p in rep["proposals"]])
                    if rep["accepted"]:
                        from .manifest import Manifest
                        cur = Manifest.model_validate(rep["candidate"])
                        repaired = True
                        r, ms2 = _exec(services, cur, run)
                        ms += ms2
                else:
                    ep["repair"] = "none_applicable"
                episodes.append(ep)
        lat.append(ms)
        status = "posted" if r.outcome == "posted" else "blocked"
        glyphs.append(_g(status, r.posted_entry(), exp, ok, run, naive_ok))
    return {"trace": "".join(GLYPH.get(g, g) for g in glyphs), "model_calls": calls, "latency_ms": lat, "episodes": episodes,
            "final_version": cur.version}


def _g(status, entry, exp, naive_ok_run, run, naive_ok):
    c = _classify(status, entry, exp, naive_ok_run)
    if c == "correct_post" and not naive_ok_run:
        c = "recovered"
    return c


def run_benchmark(seeds: int = 30, n_runs: int = 120, scenarios=None, strategies=None, progress=None, raw_trials: list | None = None) -> dict:
    scenarios, strategies = scenarios or list(SCENARIOS), strategies or STRATEGIES
    manifest, creport = compile_workflow()
    regression = golden_regression()
    t0 = time.time()
    streams = []
    for sid in scenarios:
        for seed in range(seeds):
            runs, onset = build_stream(sid, seed, n_runs)
            naive_svc = MockServices([r.truth for r in runs], "clean", mutations=SCENARIOS[sid].mutations)
            naive_ok = []
            for r_ in runs:
                naive_svc.set_behavior(r_.behavior)
                nr = Executor(naive_svc, contracts_enabled=False, schema_enabled=False).run(manifest, {"invoice_id": r_.truth.invoice_id, "as_of": r_.as_of})
                naive_ok.append(nr.outcome == "posted" and entry_matches(nr.posted_entry(), r_.expected))
            for strat in strategies:
                s = simulate_stream(strat, runs, manifest, regression, naive_ok, sid)
                streams.append({"scenario": sid, "strategy": strat, "seed": seed, "onset": onset, **s})
                if raw_trials is not None and strat in ("jitd_guarded", "naive_replay"):
                    for r_, g in zip(runs, s["trace"]):
                        raw_trials.append({"scenario": sid, "strategy": strat, "seed": seed, "idx": r_.index, "post": r_.post,
                                           "behavior": r_.behavior, "glyph": g,
                                           "expected": {k: str(v) for k, v in r_.expected.items() if k in ("invoice_id","total","paid","amount","balance")} if r_.expected else None})
        if progress:
            progress(sid)
    cells = aggregate(streams, n_runs)
    return {"meta": {"kind": "bench", "suite_version": SUITE_VERSION, "code_version": code_version(), "mode": "mock_services (simulated provider) + deterministic repair synthesizer",
                     "run_id": "bench_" + uuid.uuid4().hex[:8], "started_utc": datetime.fromtimestamp(t0, timezone.utc).isoformat(timespec="seconds"),
                     "seeds": seeds, "runs_per_stream": n_runs, "scenarios": {s: {"title": SCENARIOS[s].title, "kind": SCENARIOS[s].kind, "split": SCENARIOS[s].split, "author": SCENARIOS[s].author, "independent": SCENARIOS[s].independent} for s in scenarios},
                     "strategies": strategies, "assumptions": ASSUMPTIONS, "definitions": DEFINITIONS, "compile": {"plan_source": creport["plan_source"], "contracts": len(manifest.contracts)},
                     "wall_s": round(time.time() - t0, 1),
                     "caveats": ["Mock provider authored by the same team as the contracts; held-out scenarios were not used to set thresholds but this is not an external benchmark.",
                                 "Agent baselines are modelled, not run, and assumed correct.", "Repair uses the deterministic synthesizer; Nemotron-assisted repair is not measured here.",
                                 "Repair validation here runs in-process (same function as the isolated worker).",
                                 "Process note: the golden corpus used for mining was raised from 60 to 400 runs after false positives appeared on the dev 'clean' scenario (a tail-estimation problem); the heldout scenarios were visible in that same run. The x3 range margin and 0.01 tolerance were never changed.",
                                 "JIT-D holds legitimately huge invoices for review (see big_invoice): magnitude warnings cannot tell a whale invoice from a unit shift on a single run."]},
            "cells": cells, "streams": [{k: v for k, v in s.items() if k != "latency_ms"} for s in streams]}


def aggregate(streams, n_runs) -> list[dict]:
    out = []
    keys = sorted({(s["scenario"], s["strategy"]) for s in streams})
    for sc, st in keys:
        ss = [s for s in streams if s["scenario"] == sc and s["strategy"] == st]
        cnt = {g: 0 for g in "CSFBKR"}
        for s in ss:
            for ch in s["trace"]:
                if ch in cnt:
                    cnt[ch] += 1
        from .stream_stats import summarize_streams
        stream_statistics = summarize_streams([s["trace"].count("S") / max(1,len(s["trace"])) for s in ss])
        post_runs = sum(cnt.values())
        needs = cnt["B"] + cnt["K"] + cnt["R"] + cnt["S"]          # runs where naive was not correct-posted
        benign = cnt["C"] + cnt["F"]
        handled = cnt["B"] + cnt["K"] + cnt["R"]
        calls = sum(s["model_calls"] for s in ss)
        lat = [x for s in ss for x in s["latency_ms"]]
        ep = [e for s in ss for e in s["episodes"]]
        loc_ok = sum(1 for e in ep if (e["diagnosis"] == "business_exception" and e["scenario_kind"] == "business_exception")
                     or (e["diagnosis"] in ("localized", "provider_wide") and e["top_op"] == e["expected_fault_op"] and e["expected_fault_op"]))
        rep_acc = sum(1 for e in ep if e.get("repair") == "accepted")
        rep_try = sum(1 for e in ep if e.get("repair") in ("accepted", "rejected"))
        out.append({"scenario": sc, "strategy": st, "streams": len(ss), "post_onset_runs": post_runs, "stream_statistics": stream_statistics, "counts": {
            "correct_post": cnt["C"], "silent_error": cnt["S"], "false_block": cnt["F"], "blocked_drift": cnt["B"], "correct_block": cnt["K"], "recovered": cnt["R"]},
            "silent_error_rate": {"k": cnt["S"], "n": post_runs, "ci95": None, "interval_note": "Pooled counts are descriptive; use stream_statistics"},
            "detection_rate": {"k": handled, "n": needs, "ci95": None} if needs else None,
            "false_block_rate": {"k": cnt["F"], "n": benign, "ci95": None} if benign else None,
            "model_calls_total": calls, "model_calls_per_run": round(calls / max(1, len(ss) * n_runs), 4),
            "est_cost_usd_per_run": round(agent_call_cost(calls) / max(1, len(ss) * n_runs), 6),
            "latency_ms_median_measured": round(statistics.median(lat), 3) if lat and not st == "agent_every_run" else None,
            "latency_ms_p95_measured": round(sorted(lat)[int(0.95 * (len(lat) - 1))], 3) if lat and not st == "agent_every_run" else None,
            "modelled_agent_latency_s_per_run": round(calls * ASSUMPTIONS["agent_latency_s_per_call"] / max(1, len(ss) * n_runs), 4),
            "episodes": len(ep), "localized_correctly": {"k": loc_ok, "n": len(ep)} if ep else None,
            "repair": {"attempted": rep_try, "accepted": rep_acc} if rep_try else None})
    return out


def summary_csv(data: dict) -> str:
    import csv, io
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["scenario", "split", "strategy", "post_onset_runs", "silent_error_k", "streams_with_silent_error_ci_lo", "streams_with_silent_error_ci_hi", "detection_k", "detection_n",
                "false_block_k", "false_block_n", "model_calls_per_run", "est_cost_usd_per_run", "latency_ms_median_measured"])
    for c in data["cells"]:
        se, dr, fb = c["silent_error_rate"], c["detection_rate"], c["false_block_rate"]
        w.writerow([c["scenario"], data["meta"]["scenarios"][c["scenario"]]["split"], c["strategy"], c["post_onset_runs"], se["k"], (c.get("stream_statistics") or {}).get("stream_event_wilson_ci95", [None,None])[0], (c.get("stream_statistics") or {}).get("stream_event_wilson_ci95", [None,None])[1],
                    dr["k"] if dr else "", dr["n"] if dr else "", fb["k"] if fb else "", fb["n"] if fb else "", c["model_calls_per_run"], c["est_cost_usd_per_run"], c["latency_ms_median_measured"]])
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--runs", type=int, default=120)
    ap.add_argument("--out", default=str(ROOT / "benchmark" / "results"))
    ap.add_argument("--external", default=None, help="directory of external scenario JSON files")
    a = ap.parse_args()
    if a.external:
        from . import external
        external.register(external.load_dir(a.external))
    raw: list = []
    data = run_benchmark(a.seeds, a.runs, progress=lambda s: print("  done", s, flush=True), raw_trials=raw)
    out = Path(a.out) / "runs"
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    p = out / f"bench_{stamp}_{data['meta']['run_id'][-8:]}.json"
    p.write_text(json.dumps(data, separators=(",", ":")))
    p.with_suffix(".csv").write_text(summary_csv(data))
    import gzip
    with gzip.open(p.with_suffix(".trials.jsonl.gz"), "wt") as f:
        for t in raw:
            f.write(json.dumps(t, separators=(",", ":")) + "\n")
    print("raw trials:", len(raw))
    print(f"wrote {p} ({p.stat().st_size // 1024} KB) in {data['meta']['wall_s']}s")


if __name__ == "__main__":
    main()
