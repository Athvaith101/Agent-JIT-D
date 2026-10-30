import json

from jitd.bench import STRATEGIES, aggregate, run_benchmark, summary_csv, wilson


def test_wilson():
    assert wilson(0, 0) is None
    lo, hi = wilson(0, 96)
    assert lo == 0 and 0.03 < hi < 0.05
    lo, hi = wilson(50, 100)
    assert lo < 0.5 < hi


def test_benchmark_is_deterministic_and_internally_consistent():
    a = run_benchmark(seeds=2, scenarios=["clean", "unit_cents", "underpayment"])
    b = run_benchmark(seeds=2, scenarios=["clean", "unit_cents", "underpayment"])
    strip = lambda d: json.dumps(d["cells"], sort_keys=True, default=str)
    key = lambda d: [{k: v for k, v in c.items() if not k.startswith("latency")} for c in d["cells"]]
    assert json.dumps(key(a), sort_keys=True) == json.dumps(key(b), sort_keys=True)
    for c in a["cells"]:
        n = c["counts"]
        assert sum(n.values()) == c["post_onset_runs"] == c["silent_error_rate"]["n"]
        assert c["silent_error_rate"]["k"] == n["silent_error"]


def test_strategy_ordering_on_unit_drift():
    d = run_benchmark(seeds=3, scenarios=["unit_cents"])
    cell = {c["strategy"]: c for c in d["cells"]}
    assert cell["naive_replay"]["silent_error_rate"]["k"] == cell["naive_replay"]["post_onset_runs"]
    assert cell["schema_only"]["silent_error_rate"]["k"] == cell["schema_only"]["post_onset_runs"]           # schema cannot see it
    assert cell["agent_every_run"]["silent_error_rate"]["k"] == 0 and cell["agent_every_run"]["model_calls_per_run"] == 1
    assert cell["jitd_guarded"]["silent_error_rate"]["k"] == 0 and cell["jitd_guarded"]["model_calls_per_run"] == 0
    assert cell["fixed_audit_25"]["silent_error_rate"]["k"] > cell["fixed_audit_10"]["silent_error_rate"]["k"] > 0


def test_reports_false_positives_and_misses_honestly():
    d = run_benchmark(seeds=4, scenarios=["big_invoice", "consistent_scale", "compound"], strategies=["naive_replay", "jitd_guarded"])
    cell = {(c["scenario"], c["strategy"]): c for c in d["cells"]}
    assert cell[("big_invoice", "jitd_guarded")]["false_block_rate"]["k"] > 0                                  # whales get held
    assert cell[("consistent_scale", "jitd_guarded")]["silent_error_rate"]["k"] > 0                            # small invoices slip through
    assert cell[("compound", "jitd_guarded")]["repair"]["accepted"] == 0 and cell[("compound", "jitd_guarded")]["silent_error_rate"]["k"] == 0
    assert d["meta"]["caveats"] and d["meta"]["assumptions"]["note"].startswith("ASSUMPTIONS")


def test_csv_export():
    d = run_benchmark(seeds=1, scenarios=["clean"], strategies=["naive_replay"])
    csv = summary_csv(d)
    assert csv.splitlines()[0].startswith("scenario,split,strategy") and "naive_replay" in csv
