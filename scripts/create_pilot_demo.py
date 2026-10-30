"""Generate explicitly synthetic fresh bundles for demonstrating evidence resolution."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import argparse
import json
from datetime import datetime, timezone
from jitd.fixtures import make_truth
from jitd.services import MockServices,capture_case
from jitd.integrate import recording_snapshot


def demo_bundle():
    t=make_truth('pilot-demo',0);svc=MockServices([t]);case=capture_case(svc,t.invoice_id,'2026-09-30T00:00:00Z','unknown')
    authority={'invoice_id':t.invoice_id,'invoice_total_usd':str(t.total),'settled_total_usd':str(t.paid_total),
               'source_id':'demo-control','currency':'USD','observed_at':datetime.now(timezone.utc).isoformat(),
               'provider_snapshot':recording_snapshot(case)}
    bundle={'recording':case,'authority':authority,'source':'demo-control',
            'provenance':{'author':'JIT-D synthetic demo generator','collection_method':'Fixture-derived demonstration, not independent field evidence',
                          'real_data':False,'independent_authority':True}}
    return bundle


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',default='data/pilot-demo');args=ap.parse_args()
    root=Path(args.out);root.mkdir(parents=True,exist_ok=True);bundle=demo_bundle()
    (root/'ready.json').write_text(json.dumps(bundle,indent=2,default=str))
    (root/'authority.json').write_text(json.dumps(bundle['authority'],indent=2,default=str))
    bundle['authority']=None;(root/'missing.json').write_text(json.dumps(bundle,indent=2,default=str))
    print('Synthetic demo files:',root,'; authority observation expires in five minutes.')
