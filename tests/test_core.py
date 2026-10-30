import ast
from pathlib import Path

import pytest

from jitd.compiler import golden_plan
from jitd.manifest import Manifest, validate_manifest
from jitd.money import D, fmt, q
from jitd.paths import get_path, parse_ref

ROOT = Path(__file__).resolve().parent.parent


def test_money_is_exact():
    assert fmt(D("0.1") + D("0.2")) == "0.30"
    assert q("2.675") == D("2.68")
    for bad in (None, True, "abc", "NaN", float("inf")):
        with pytest.raises(ValueError):
            D(bad)


def test_paths_and_refs():
    v = {"a": [{"b": 1}, {"b": 2}], "c": {"d": 3}}
    assert get_path(v, "a[*].b") == [1, 2] and get_path(v, "c.d") == 3 and get_path(v, "a[1].b") == 2
    for bad in ("__class__", "c.__dict__", "a[5]", "zzz"):
        with pytest.raises((KeyError, ValueError)):
            get_path(v, bad)
    assert parse_ref("$input.invoice_id") == ("input", ".invoice_id")
    for bad in ("input.x", "$a b", "$x;rm", "$x.__init__()", "${x}", "$a.b['c']"):
        with pytest.raises(ValueError):
            parse_ref(bad)


def _plan(mut=None):
    p = golden_plan()
    if mut:
        mut(p)
    return Manifest.model_validate(p)


def test_golden_plan_is_valid():
    assert validate_manifest(_plan()) == []


def test_unknown_operation_rejected():
    def m(p): p["steps"][3]["operation"] = "os.system"
    assert any("not allowlisted" in e for e in validate_manifest(_plan(m)))


def test_forward_reference_rejected():
    def m(p): p["steps"][0]["inputs"]["invoice_id"] = "$post_ledger.x"
    assert any("not an earlier step" in e for e in validate_manifest(_plan(m)))


def test_bad_params_rejected():
    def m(p): p["steps"][2]["params"]["rules"] = [{"divisor": 7, "effective_from": None}]
    assert any("divisor" in e for e in validate_manifest(_plan(m)))
    def m2(p): p["steps"][1]["params"]["max_pages"] = 9999
    assert any("max_pages" in e for e in validate_manifest(_plan(m2)))
    def m3(p): p["steps"][1]["params"]["shell"] = "x"
    assert any("unknown param" in e for e in validate_manifest(_plan(m3)))


def test_missing_input_rejected():
    def m(p): del p["steps"][3]["inputs"]["amounts"]
    assert any("inputs must be exactly" in e for e in validate_manifest(_plan(m)))


def test_no_eval_or_exec_anywhere_in_the_package():
    for f in (ROOT / "jitd").glob("*.py"):
        tree = ast.parse(f.read_text())
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("eval", "exec", "compile", "__import__") and f.name != "server.py":
                pytest.fail(f"{f.name} calls {n.func.id}")


def test_oracle_is_independent_of_code_under_test():
    tree = ast.parse((ROOT / "jitd" / "oracle.py").read_text())
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not mods & {"jitd.executor", "jitd.ops", "jitd.contracts", "jitd.manifest", "jitd.diagnosis", "jitd.repair", "executor", "ops", "contracts"}
    assert mods <= {"__future__", "fixtures", "money", "jitd.fixtures", "jitd.money"} or all(m in ("__future__", "fixtures", "money", None) for m in mods)
