"""Durable read-only cases and evidence resolution. Review never overrides the strict gate."""
import copy
import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from .compiler import compile_workflow
from .evidence_csv import evidence_record
from .executor import Executor
from .integrate import recording_snapshot
from .sdk import check_recording
from .services import RecordedServices


def now(): return datetime.now(timezone.utc).isoformat()


def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()


def validate_bundle(bundle):
    if not isinstance(bundle,dict):raise ValueError('Case bundle must be an object')
    check_recording(bundle['recording'])
    if len(bundle['recording']['pages'])>20:raise ValueError('At most twenty payment pages supported')
    payments=[p for page in bundle['recording']['pages'].values() for p in page['payments']]
    ids=[p['payment_id'] for p in payments]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate payment identities')
    p=bundle.get('provenance',{})
    if not isinstance(p,dict) or not str(p.get('author','')).strip() or not str(p.get('collection_method','')).strip():
        raise ValueError('Author and collection method required')
    if not isinstance(p.get('real_data',False),bool) or not isinstance(p.get('independent_authority',False),bool):
        raise ValueError('Provenance flags must be booleans')
    if bundle.get('authority') is not None and not isinstance(bundle['authority'],dict):raise ValueError('Authority must be an object or null')
    if bundle.get('authority') and not isinstance(bundle.get('source'),str):raise ValueError('Configured source required')
    # Customer recordings may contain business data; credential-bearing payloads must not be imported.
    def walk(v):
        if isinstance(v,dict):
            for k,x in v.items():
                if str(k).lower() in {'authorization','api_key','password','access_token','refresh_token'}:raise ValueError('Remove credentials before importing')
                walk(x)
        elif isinstance(v,list):
            for x in v:walk(x)
    walk(bundle)
    return bundle


def bundle_evidence(bundle):
    try:
        if not bundle.get('provenance',{}).get('independent_authority'):return {}
        case=bundle['recording'];row=bundle.get('authority')
        snapshot=recording_snapshot(case)
        if bundle.get('provenance',{}).get('snapshot_kind')=='provider_version':
            if bundle['provenance'].get('recording_sha256')!=snapshot:return {}
            snapshot=case.get('provider_snapshot')
        if not row:return {}
        return evidence_record(row,case['invoice_id'],snapshot,bundle.get('source'),fingerprint(row))
    except (ValueError,KeyError,TypeError,ArithmeticError):return {}


class PilotServices(RecordedServices):
    def __init__(self,bundle,evidence):
        super().__init__(copy.deepcopy(bundle['recording']));self.evidence=copy.deepcopy(evidence)
    def snapshot_token(self,invoice_id):
        return recording_snapshot(self.case) if invoice_id==self.case['invoice_id'] else None
    def verification_evidence(self,invoice_id):return copy.deepcopy(self.evidence)


def evaluate(bundle,manifest=None):
    validate_bundle(bundle)
    if os.getenv('JITD_AUTHORITY_CSV'):raise ValueError('Unset JITD_AUTHORITY_CSV before pilot verification')
    if manifest is None:manifest=compile_workflow()[0]
    else:manifest=manifest.clone()
    manifest.step_for_op('payment.list').params['max_pages']=len(bundle['recording']['pages'])
    svc=PilotServices(bundle,bundle_evidence(bundle))
    r=Executor(svc,strict=True).run(manifest,{k:svc.case[k] for k in ('invoice_id','as_of')})
    return {'outcome':r.outcome,'halt':r.halt,'assumptions':r.assumptions,'entry':r.posted_entry(),
            'duration_ms':r.duration_ms,'workflow_version':manifest.version,'external_writes':0,'verification_basis':'configured authority; provenance is operator-declared'}


class PilotStore:
    def __init__(self,directory):
        self.path=Path(directory)/'pilot.sqlite3';self.path.parent.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock()
        with self.connect() as db:db.executescript('CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,revision INTEGER,payload TEXT);CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,created TEXT,case_id TEXT,action TEXT,detail TEXT);')
    def connect(self):return sqlite3.connect(self.path,timeout=10)
    def rows(self):
        with self.connect() as db:return [json.loads(r[0]) for r in db.execute('SELECT payload FROM cases ORDER BY rowid DESC')]
    def get(self,cid):
        with self.connect() as db:row=db.execute('SELECT payload FROM cases WHERE id=?',(cid,)).fetchone()
        if not row:raise KeyError('Unknown pilot case')
        return json.loads(row[0])
    def create(self,bundle,manifest=None):
        result=evaluate(bundle,manifest)
        row={'id':'case_'+uuid.uuid4().hex[:12],'revision':1,'created':now(),'updated':now(),
             'observations':[{'at':now(),'authority':copy.deepcopy(bundle.get('authority')),'result':copy.deepcopy(result)}],
             'bundle':copy.deepcopy(bundle),'input_sha256':fingerprint(bundle),'result':result,'reviews':[]}
        with self.lock,self.connect() as db:
            db.execute('INSERT INTO cases VALUES(?,?,?)',(row['id'],1,json.dumps(row,default=str)))
            self._event(db,row['id'],'import',{'input_sha256':row['input_sha256'],'outcome':result['outcome']})
        return row
    def _event(self,db,cid,action,detail):db.execute('INSERT INTO events(created,case_id,action,detail) VALUES(?,?,?,?)',(now(),cid,action,json.dumps(detail)))
    def resolve(self,cid,revision,reviewer,note,human_minutes,authority,manifest=None):
        if not reviewer.strip() or not note.strip() or len(reviewer)>100 or len(note)>2000:raise ValueError('Reviewer and concise evidence note required')
        if not 0<=human_minutes<=1440:raise ValueError('Human minutes outside 0..1440')
        with self.lock:
            row=self.get(cid)
            if row['revision']!=revision:raise RuntimeError('Case changed; reload before reviewing')
            bundle=copy.deepcopy(row['bundle'])
            if authority is not None:bundle['authority']=authority
            # A note does not make provenance independent or bypass any verification condition.
            result=evaluate(bundle,manifest)
            row.update(bundle=bundle,result=result,revision=revision+1,updated=now())
            review={'reviewer':reviewer,'note':note,'human_minutes':human_minutes,'at':now(),
                    'authority_sha256':fingerprint(bundle.get('authority')),'outcome':result['outcome']}
            row['reviews'].append(review)
            row.setdefault('observations',[]).append({'at':now(),'authority':copy.deepcopy(bundle.get('authority')),'result':copy.deepcopy(result)})
            with self.connect() as db:
                cursor=db.execute('UPDATE cases SET revision=?,payload=? WHERE id=? AND revision=?',(row['revision'],json.dumps(row,default=str),cid,revision))
                if cursor.rowcount!=1:raise RuntimeError('Case changed; reload before reviewing')
                self._event(db,cid,'review_and_reverify',review)
            return row
    def report(self):
        rows=self.rows();reviews=[x for r in rows for x in r['reviews']]
        accepted=sum(r['result']['outcome']=='posted' for r in rows)
        return {'cases':len(rows),'verified_shadow_outputs':accepted,'blocked':len(rows)-accepted,
                'declared_real_cases':sum(bool(r['bundle']['provenance'].get('real_data')) for r in rows),
                'review_count':len(reviews),'reported_human_minutes':sum(x['human_minutes'] for x in reviews),
                'evidence_coverage':sum(all(a['status']!='UNKNOWN' for a in r['result']['assumptions'] if a.get('required')) for r in rows)/len(rows) if rows else None,
                'scope':'Shadow acceptance, not independently measured correctness or false-block rate. Provenance and human time are declared by the importer/reviewer.',
                'external_writes':0,'cost_per_correct_usd':None}
    def events(self):
        with self.connect() as db:return [dict(seq=a,created=b,case_id=c,action=d,detail=json.loads(e)) for a,b,c,d,e in db.execute('SELECT seq,created,case_id,action,detail FROM events ORDER BY seq')]
