"""Render saved authority results and an explicitly assumed human-cost break-even table."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path('benchmark/final');d=json.loads((root/'authority.json').read_text());out=Path('docs/figures');out.mkdir(parents=True,exist_ok=True)
fig,ax=plt.subplots(1,2,figsize=(11,4))
for mode in sorted({c['mode'] for c in d['cells']}):
 rows=[c for c in d['cells'] if c['mode']==mode]
 for axis,key in zip(ax,['silent','false_block']):
  axis.plot([r['epsilon'] for r in rows],[r[key]['mean_rate'] for r in rows],marker='o',label=mode)
  axis.set(xlabel='Injected authority fault probability',ylabel=key.replace('_',' ')+' rate',ylim=(-.02,1.02))
ax[0].legend(fontsize=7);fig.suptitle('Synthetic trust-boundary sensitivity — not measured authority reliability');fig.tight_layout();fig.savefig(out/'authority-sensitivity.svg');plt.close(fig)
rows=[]
for minutes in (1,5,15):
 for hold in (.001,.01,.1):
  rows.append({'review_minutes':minutes,'hold_rate':hold,'hourly_usd_assumed':30,
               'replay_and_verification_usd_assumed':.0001,'break_even_agent_usd_per_run':.0001+hold*minutes*30/60})
(root/'break_even_assumptions.json').write_text(json.dumps({'scope':'Illustrative assumptions only; no measured customer savings or agent billing. Equal correctness and other operational costs must also hold.','rows':rows},indent=2))
