"""Rebuild active synthetic tables. python scripts/reproduce.py [--quick]"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import argparse,json
from jitd.aair_bench import benchmark
from jitd.stream_stats import enrich
from jitd.authority_study import study
from jitd.paired_study import study as paired
ap=argparse.ArgumentParser();ap.add_argument('--quick',action='store_true');args=ap.parse_args()
n=3 if args.quick else 30
root=Path('benchmark/final');root.mkdir(parents=True,exist_ok=True)
d=enrich(benchmark(seeds=n,n_runs=12));(root/'aair.json').write_text(json.dumps(d))
(root/'authority.json').write_text(json.dumps(study(streams=n)))
(root/'paired.json').write_text(json.dumps(paired(seeds=n)))
print('Saved active studies:',root,'; streams:',n)

import subprocess
subprocess.run([sys.executable,'scripts/report_figures.py'],check=True)
