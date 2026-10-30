"""One-command walkthrough of the whole story on the command line (no browser, no network, no model)."""
import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jitd.lab import Lab  # noqa: E402


def show(title, **kv):
    print(f"\n== {title}")
    for k, v in kv.items():
        print(f"   {k}: {v}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="all", choices=["all", "clean", "unit_cents"])
    a = ap.parse_args()
    lab = Lab(Path(tempfile.mkdtemp(prefix="jitd-demo-")))
    r = lab.run()
    show("clean replay", outcome=r["outcome"], oracle=r["oracle_verdict"], replay_model_calls=r["meter"]["replay_model_calls"], model_calls_this_run=r["model_calls"])
    if a.scenario == "clean":
        return
    lab.inject("unit_cents")
    r = lab.run()
    sch = [s for s in r["steps"] if s["operation"] == "payment.list"][0]
    show("unit drift injected (schema still valid)", outcome=r["outcome"], halted_at=r["halt"]["step"], contract=r["halt"].get("contract"), message=r["halt"]["message"][:110])
    d = lab.diagnose(r["run_id"])
    show("diagnosis", status=d["status"], top=d["top"]["name"], step=d["top"]["step"], score=d["top"]["score"], explanation=d["explanation"][:200])
    w = lab.repair(r["run_id"], "wrong")
    show("deliberately wrong repair (divisor 10)", decision=w["decision"], reason=w["reason"])
    g = lab.repair(r["run_id"], "auto")
    p = g["proposals"][-1]
    show("bounded repair", decision=g["decision"], diff=p["diff"], groups={k: f"{v['passed']}/{v['n']}" for k, v in p["validation"]["groups"].items()}, isolated=p["validation"].get("isolated"))
    r2 = lab.run(invoice_id=r["inputs"]["invoice_id"])
    show("retry the blocked invoice with the repaired workflow", outcome=r2["outcome"], oracle=r2["oracle_verdict"], version=r2["manifest_version"])
    lab.inject("unit_mills")
    r3 = lab.run()
    d3 = lab.diagnose(r3["run_id"])
    g3 = lab.repair(r3["run_id"], "auto")
    show("unseen 1000x variant", outcome=r3["outcome"], diagnosis=d3["top"]["name"], repair=g3["decision"], groups={k: f"{v['passed']}/{v['n']}" for k, v in g3["proposals"][-1]["validation"]["groups"].items()})
    lab.inject("underpayment")
    r4 = lab.run()
    d4 = lab.diagnose(r4["run_id"]) if r4["outcome"] in ("halted", "held") else None
    g4 = lab.repair(r4["run_id"], "auto") if d4 else None
    show("genuine under-payment (a business exception, not drift)", outcome=r4["outcome"], diagnosis=d4 and d4["status"], repair=g4 and g4["decision"], reason=g4 and g4["reason"])
    show("totals", model_calls=lab.meter.snapshot(), workflow_version=lab.manifest.version, guards=len(lab.guards))


if __name__ == "__main__":
    main()
