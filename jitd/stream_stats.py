"""Uncertainty over seed streams, never independent-run Bernoulli claims."""
import random
from .bench import wilson


def summarize_streams(rates, samples=2000):
    if not rates:return None
    rng=random.Random(2026);n=len(rates)
    means=sorted(sum(rng.choices(rates,k=n))/n for _ in range(samples))
    return {'streams':n,'mean_rate':sum(rates)/n,'min_rate':min(rates),'max_rate':max(rates),
            'cluster_bootstrap_ci95':[means[int(.025*samples)],means[int(.975*samples)]],
            'streams_with_event':sum(r>0 for r in rates),
            'stream_event_wilson_ci95':wilson(sum(r>0 for r in rates),n),
            'per_stream_rates':rates,
            'note':'Bootstrap resamples whole streams. All-zero bootstrap intervals are degenerate, not proof of zero population risk; consult stream-event Wilson bounds.'}


def enrich(report):
    for cell in report['cells']:
        rows=[r for r in report['trials'] if r['scenario']==cell['scenario'] and r['strategy']==cell['strategy'] and r['post']]
        seeds=sorted({r['seed'] for r in rows})
        cell['stream_statistics']={key:summarize_streams([sum(bool(r[key]) for r in rows if r['seed']==s)/sum(r['seed']==s for r in rows) for s in seeds]) for key in ('correct','silent','safe_halt')}
    return report
