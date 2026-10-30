"""Synthetic planner experiment: python -m jitd.assurance_bench."""
import json
from .assurance import Check, plan_checks


def main():
    checks = [Check('amount', frozenset(['amount']), 2),
              Check('currency', frozenset(['currency']), 2),
              Check('authority_bundle', frozenset(['amount', 'currency']), 3),
              Check('pagination', frozenset(['pagination']), 1)]
    rows = []
    for budget in range(9):
        result = plan_checks(['amount', 'currency', 'pagination'], checks, budget)
        assert result['estimated_cost_units'] <= budget
        assert not result['acceptance_authorized']
        rows.append(result)
    print(json.dumps({'scope': 'authored synthetic planner experiment; no execution or model calls',
                      'full_individual_cost_units': 5, 'rows': rows}, indent=2))


if __name__ == '__main__':
    main()
