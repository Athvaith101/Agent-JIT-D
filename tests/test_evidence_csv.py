import csv
from datetime import datetime, timezone, timedelta
import pytest
from jitd.evidence_csv import FIELDS
from jitd.compiler import compile_workflow
from jitd.executor import Executor
from jitd.fixtures import make_truth
from jitd.services import MockServices


@pytest.mark.parametrize('fault', ['none','missing','snapshot','source','stale','wrong','nan','duplicate'])
def test_external_evidence_gate(tmp_path, monkeypatch, fault):
    t=make_truth('csv',0); svc=MockServices([t]); p=tmp_path/'authority.csv'
    row=dict(invoice_id=t.invoice_id, invoice_total_usd=str(t.total), settled_total_usd=str(t.paid_total),
             currency='USD', observed_at=datetime.now(timezone.utc).isoformat(), source_id='bank-export',
             provider_snapshot=svc.snapshot_token(t.invoice_id))
    if fault=='snapshot': row['provider_snapshot']='wrong'
    if fault=='source': row['source_id']='other-bank'
    if fault=='stale': row['observed_at']=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
    if fault=='wrong': row['invoice_total_usd']=str(t.total+10)
    if fault=='nan': row['invoice_total_usd']='NaN'
    with p.open('w', newline='') as f:
        w=csv.DictWriter(f,fieldnames=sorted(FIELDS));w.writeheader();w.writerow(row)
    if fault=='missing': p.unlink()
    if fault=='duplicate':
        lines=p.read_text().splitlines();p.write_text('\n'.join(lines+[lines[1]])+'\n')
    monkeypatch.setenv('JITD_AUTHORITY_CSV',str(p));monkeypatch.setenv('JITD_AUTHORITY_SOURCE','bank-export')
    m,_=compile_workflow()
    r=Executor(svc,strict=True).run(m,{'invoice_id':t.invoice_id,'as_of':'2026-09-30T00:00:00Z'})
    assert (r.outcome=='posted') == (fault=='none')
    if fault=='none':
        proof=next(a['evidence'] for a in r.assumptions if a['id']=='invoice-unit')
        assert proof['record_sha256'] and proof['basis']=='adapter-supplied trusted authority'
    else:
        assert svc.calls['ledger.post']==0


def test_recording_cli_uses_external_authority(tmp_path, monkeypatch, capsys):
    import json
    import sys
    from jitd.integrate import main, recording_snapshot
    from jitd.services import capture_case
    t=make_truth('recorded',0); svc=MockServices([t])
    case=capture_case(svc,t.invoice_id,'2026-09-30T00:00:00Z','unknown')
    p=tmp_path/'authority.csv'; recording=tmp_path/'recording.json'
    recording.write_text(json.dumps(case,default=str))
    case=json.loads(recording.read_text())
    row=dict(invoice_id=t.invoice_id,invoice_total_usd=str(t.total),settled_total_usd=str(t.paid_total),
             currency='USD',observed_at=datetime.now(timezone.utc).isoformat(),source_id='bank-export',
             provider_snapshot=recording_snapshot(case))
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=sorted(FIELDS));w.writeheader();w.writerow(row)
    monkeypatch.setattr(sys,'argv',['integrate','--recording',str(recording),'--authority',str(p),'--source','bank-export'])
    with pytest.raises(SystemExit) as e: main()
    report=json.loads(capsys.readouterr().out)
    assert e.value.code==0 and report['external_writes']==0 and report['outcome']=='posted'
    case['invoice']['total']=str(t.total+1)
    assert recording_snapshot(case)!=row['provider_snapshot']
