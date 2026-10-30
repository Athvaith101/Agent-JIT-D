"""Validation of a candidate manifest against recorded cases. Runs in an isolated process (validate_worker) in production
paths, and in-process for the high-volume benchmark (same function). Pure: no network, no services other than recorded ones."""
from __future__ import annotations

from .executor import Executor
from .manifest import Manifest, validate_manifest
from .oracle import entry_matches
from .services import RecordedServices


def run_validation(payload: dict) -> dict:
    m = Manifest.model_validate(payload["manifest"])
    problems = validate_manifest(m)
    if problems:
        return {"ok": False, "static_problems": problems, "groups": {}}
    groups, ok = {}, bool(payload["groups"])
    for gname, cases in payload["groups"].items():
        passed, fails, oracle_checked, oracle_fail = 0, [], 0, 0
        for case in cases:
            svc = RecordedServices(case)
            r = Executor(svc).run(m, {"invoice_id": case["invoice_id"], "as_of": case["as_of"]})
            clean = r.outcome == "posted" and not r.flagged
            exp = case.get("expected", "unknown")
            o_ok = True
            if exp != "unknown":
                oracle_checked += 1
                o_ok = entry_matches(r.posted_entry(), exp)
                oracle_fail += 0 if o_ok else 1
            good = clean and o_ok if (exp == "unknown" or exp is not None) else (r.outcome != "posted")
            if good:
                passed += 1
            else:
                fails.append({"invoice_id": case["invoice_id"], "outcome": r.outcome, "flagged": r.flagged,
                              "failed_contracts": [c["id"] for c in r.contract_results if not c["ok"]], "halt": (r.halt or {}).get("reason")})
        groups[gname] = {"n": len(cases), "passed": passed, "oracle_checked": oracle_checked, "oracle_mismatches": oracle_fail, "failures": fails[:3]}
        ok = ok and passed == len(cases) and len(cases) > 0
    return {"ok": ok, "static_problems": [], "groups": groups}
