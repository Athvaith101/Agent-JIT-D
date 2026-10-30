"""Bounded verification planning. Plans never confer authority to accept an output."""
from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class Check:
    id: str
    covers: frozenset[str]
    cost: int


def plan_checks(required, checks, budget):
    """Exact weighted cover for <=16 independent, pre-registered check actions.

    Cost units are deterministic planning units, not tokens, milliseconds or money.
    Every action must be self-contained: prerequisite work is included in its cost.
    Selecting a check is not evidence that it passed.
    """
    required = frozenset(required)
    checks = tuple(checks)
    if type(budget) is not int or not 0 <= budget <= 1000000:
        raise ValueError('budget must be an integer from 0 to 1000000')
    if len(checks) > 16 or len({c.id for c in checks}) != len(checks):
        raise ValueError('at most 16 uniquely named checks supported')
    if any(type(c.cost) is not int or c.cost < 0 for c in checks):
        raise ValueError('check costs must be nonnegative integers')
    best = None
    # Exponential by design, bounded to 65536 subsets. Prefer complete coverage,
    # otherwise maximal obligation coverage; ties use cost then stable IDs.
    for n in range(len(checks) + 1):
        for subset in combinations(checks, n):
            cost = sum(c.cost for c in subset)
            if cost > budget:
                continue
            covered = required.intersection(frozenset().union(*(c.covers for c in subset)))
            key = (-len(covered), cost, tuple(c.id for c in subset))
            if best is None or key < best[0]:
                best = (key, subset, covered)
    _, selected, covered = best
    return {'selected_checks': [c.id for c in selected], 'estimated_cost_units': sum(c.cost for c in selected),
            'budget_units': budget, 'covered_obligations': sorted(covered),
            'uncovered_obligations': sorted(required - covered), 'coverage_complete': covered == required,
            'acceptance_authorized': False,
            'algorithm': 'exact bounded subset enumeration; O(2^K * (K + obligations))'}


def report(run, budget=4, changed_sources=()):
    """Read-only explanation against recorded evidence, never a live certificate.

    All mandatory obligations are rechecked. Existing saved VALID statuses are
    deliberately not reused: their validity at a later execution is unestablished.
    Source changes highlight consumers but cannot remove any required check.
    """
    obligations = [dict(a) for a in run.get('assumptions', []) if a.get('required')]
    ids = [a['id'] for a in obligations]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate obligation IDs')
    changed = set(changed_sources)
    affected = sorted({node for a in obligations if a.get('evidence_source') in changed
                       for node in a.get('consumers', [a.get('node')]) if node})
    checks = [Check(a['id'], frozenset([a['id']]), 1) for a in obligations]
    plan = plan_checks(ids, checks, budget)
    return {'mode': 'shadow_only', 'scope': 'recorded run; synthetic invoice family',
            'obligations': obligations, 'changed_sources': sorted(changed), 'affected_nodes': affected,
            'plan': plan, 'reused_evidence': [], 'model_calls': 0,
            'gate': 'Fresh strict execution is always required; budget cannot bypass required evidence.',
            'limitations': 'No continuous monitoring, signed authority, formal proof, live selective skipping or measured cost savings.'}
