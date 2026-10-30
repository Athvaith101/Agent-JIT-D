import pytest

from jitd import external, mutations as mut


def test_mutation_apply_and_validation():
    out = mut.apply("invoice.get", {"tax": 5, "total": 10}, [{"op": "scale", "endpoint": "invoice.get", "fields": ["tax"], "factor": 100}])
    assert out["tax"] == 500 and out["total"] == 10
    assert mut.apply("payment.list", {"tax": 5}, [{"op": "scale", "endpoint": "invoice.get", "fields": ["tax"], "factor": 100}]) == {"tax": 5}
    with pytest.raises(ValueError):
        mut.validate({"op": "exec", "endpoint": "invoice.get", "fields": ["x"]})


def test_external_loader_rejects_bad_specs():
    base = {"title": "t", "author": "a", "kind": "drift", "fault_op": "invoice.get",
            "mutations": [{"op": "scale", "endpoint": "invoice.get", "fields": ["tax"], "factor": 100}]}
    with pytest.raises(ValueError):
        external.parse({"id": "x", "title": "t"})
    with pytest.raises(ValueError):
        external.parse({**base, "id": "clean"})                       # collides with a built-in
    with pytest.raises(ValueError):
        external.parse({**base, "id": "noauthor", "author": ""})


def test_examples_load_and_are_labelled_not_independent():
    scs = external.load_dir("benchmark/external")
    assert {"tax_in_cents", "three_per_page"} <= set(scs)
    assert all(not s.independent and s.split == "external" for s in scs.values())


def test_external_scenarios_run_in_bench():
    from jitd import bench
    external.register(external.load_dir("benchmark/external"))
    d = bench.run_benchmark(seeds=2, n_runs=60, scenarios=["three_per_page"], strategies=["naive_replay", "jitd_guarded"])
    by = {c["strategy"]: c for c in d["cells"]}
    assert by["naive_replay"]["silent_error_rate"]["k"] > 0 and by["jitd_guarded"]["silent_error_rate"]["k"] == 0
    assert d["meta"]["scenarios"]["three_per_page"]["independent"] is False
