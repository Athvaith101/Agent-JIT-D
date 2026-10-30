"""Controlled drift scenarios and seeded run streams. `split` records whether a scenario was used while developing the
contracts/hypotheses ('dev') or only evaluated afterwards ('heldout'). Thresholds were fixed before heldout was run."""
from __future__ import annotations

import random
from dataclasses import dataclass

from .fixtures import Truth, make_truth
from .oracle import expected_ledger


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    behavior: str                 # provider behaviour after onset
    truth_mod: str | None         # None | "short" | "big"
    kind: str                     # benign | drift | business_exception | hard
    split: str                    # dev | heldout
    fault_op: str | None          # where the responsible assumption lives (None = no step is at fault)
    repairable: bool
    desc: str
    truth_p: float = 1.0          # probability a post-onset invoice carries truth_mod
    installments: int | None = None
    mutations: tuple = ()         # declarative provider mutations (behavior must be "mutated")
    author: str = "builtin"
    independent: bool = False     # True only if someone other than the JIT-D authors wrote the scenario


SCENARIOS = {s.id: s for s in [
    Scenario("clean", "Clean provider", "clean", None, "benign", "dev", None, False, "Nothing changes."),
    Scenario("cosmetic", "Cosmetic change", "cosmetic", None, "benign", "dev", None, False,
             "Key order, an extra metadata field, upper-case status and string amounts. Meaning is unchanged: must NOT be blocked."),
    Scenario("big_invoice", "Legitimately huge invoices", "clean", "big", "benign", "heldout", None, False,
             "15% of invoices are 5-30x larger than anything in the golden runs. Arithmetic is consistent. Blocking them is a false positive.", truth_p=0.15),
    Scenario("unit_cents", "Dollars -> cents (silent)", "unit_cents", None, "drift", "dev", "normalize_money", True,
             "payment.amount stays numeric but now means cents. The schema still passes."),
    Scenario("truncation", "Pagination truncation", "truncation", None, "drift", "dev", "payment.list", True,
             "Provider starts returning 2 payments per page; the compiled plan reads one page.", installments=None),
    Scenario("unit_mills", "Dollars -> mills (unseen variant)", "unit_mills", None, "drift", "heldout", "normalize_money", True,
             "A scale factor (1000x) that appears nowhere in the compile-time corpus or the code."),
    Scenario("malformed", "Malformed responses", "malformed", None, "drift", "heldout", "payment.list", False,
             "payment.amount arrives as null. Schema validation catches it; no automated repair exists."),
    Scenario("underpayment", "Genuine under-payment", "clean", "short", "business_exception", "heldout", None, False,
             "25% of invoices are paid 3.7% short while the provider says 'paid'. This is a business exception, not drift: a repair would be wrong.", truth_p=0.25),
    Scenario("compound", "Cents AND truncation together", "cents_truncation", None, "drift", "heldout", "payment.list", False,
             "Two independent faults at once. A single bounded repair cannot fix both, so the correct behaviour is to stay halted.", installments=4),
    Scenario("consistent_scale", "Both services switch to cents", "consistent_scale", None, "hard", "heldout", "invoice.get+payment.list", False,
             "Invoice and payments both move to cents together, so every arithmetic check still passes. Only magnitude invariants can notice."),
]}


@dataclass
class Run:
    index: int
    truth: Truth
    behavior: str
    as_of: str
    post: bool
    expected: dict | None


def as_of_for(i: int, post: bool) -> str:
    base_day = 16 if post else 1
    return f"2026-10-{base_day + (i // 1440):02d}T{(i % 1440) // 60:02d}:{i % 60:02d}:00Z"


def build_stream(scenario_id: str, seed: int, n_runs: int = 120) -> tuple[list[Run], int]:
    sc = SCENARIOS[scenario_id]
    rng = random.Random(f"stream:{scenario_id}:{seed}")
    onset = rng.randint(30, 60)
    runs = []
    for i in range(n_runs):
        post = i >= onset
        mod = sc.truth_mod if (post and sc.truth_mod and rng.random() < sc.truth_p) else None
        t = make_truth(f"{scenario_id}-{seed}", i, "post" if post else "pre", installments=sc.installments, short=(mod == "short"), big=(mod == "big"))
        runs.append(Run(i, t, sc.behavior if post else "clean", as_of_for(i, post), post, expected_ledger(t)))
    return runs, onset
