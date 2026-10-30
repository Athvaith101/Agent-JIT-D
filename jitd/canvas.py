"""Typed, bounded visual pipelines. All sources are explicit JSON, all outputs local."""
import copy
import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from .lab import LabError


def digest(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def policy_hash():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


FAMILIES = {
 'invoice_reconciliation': ('Invoice reconciliation', {'invoice':'100.00','payments':['60','40'],'unit':'USD'}, {'amount':'100.00','currency':'USD'}),
 'invoice_discrepancy': ('Invoice discrepancy reporting', {'invoice':'100','payments':['90'],'unit':'USD'}, {'difference':'10.00','currency':'USD'}),
 'payout_reconciliation': ('Refund / payout reconciliation', {'expected':'25','actual_minor':2500,'minor_digits':2,'currency':'USD'}, {'actual':'25.00','currency':'USD'}),
 'shipment_reconciliation': ('Shipment reconciliation', {'declared_kg':'10','measured':'10','unit':'kg'}, {'weight_kg':'10.000'}),
 'inventory_reconciliation': ('Inventory reconciliation', {'opening':100,'received':20,'shipped':10,'counted':110}, {'closing':110}),
 'data_quality': ('Data-quality monitoring', {'rows':[{'id':'a','amount':'10'},{'id':'b','amount':'20'}],'complete':True,'unit':'USD'}, {'count':2,'total':'30.00','unit':'USD'}),
 'recurring_report': ('Recurring report generation', {'rows':[{'category':'A','amount':'10'},{'category':'A','amount':'20'},{'category':'B','amount':'5'}],'complete':True,'unit':'USD'}, {'groups':{'A':'30.00','B':'5.00'},'total':'35.00','unit':'USD'}),
 'ticket_triage': ('Ticket triage', {'tickets':[{'id':'T1','severity':'urgent'},{'id':'T2','severity':'normal'}],'policy_version':'1'}, {'routes':{'T1':'priority_review','T2':'standard_review'},'policy_version':'1'}),
 'document_change': ('Document-change monitoring', {'document_id':'guide','previous_hash':'a'*64,'current_hash':'b'*64,'dependent_claims':['claim-1']}, {'changed':True,'invalidated':['claim-1'],'current_hash':'b'*64}),
 'deployment_readiness': ('Deployment readiness', {'commit':'abc123','tested_commit':'abc123','config_hash':'a'*64,'tested_config_hash':'a'*64,'tests_passed':True}, {'ready':True,'commit':'abc123','config_hash':'a'*64}),
}
BLOCKS = {'source':('JSON source','start','raw'), 'normalize':('Compute / normalize','raw','candidate'),
          'verify':('Required authority gate','candidate','verified'), 'report':('Add review summary','verified','verified'),
          'output':('Local result','verified','end')}


class Node(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id: str=Field(pattern=r'^[a-z][a-z0-9_]{0,30}$')
    kind: Literal['source','normalize','verify','report','output']


class Graph(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name: str=Field(min_length=3,max_length=80)
    family: str=Field(max_length=60)
    nodes: list[Node]=Field(min_length=1,max_length=12)
    edges: list[tuple[str,str]]=Field(max_length=20)
    factor: str=Field(default='1',max_length=20)


def number(v):
    if isinstance(v,bool): raise ValueError('boolean is not a number')
    n=Decimal(str(v))
    if not n.is_finite() or abs(n)>Decimal('1e12'):raise ValueError('invalid numeric range')
    return n


def money(v):return str(number(v).quantize(Decimal('.01')))


def integer(v):
    if type(v) is not int or not 0<=v<=1000000:raise ValueError('bounded integer required')
    return v


def validate(graph):
    errors=[]
    if graph.family not in FAMILIES: errors.append('Unsupported template family.')
    ids=[n.id for n in graph.nodes]
    kinds=[n.kind for n in graph.nodes]
    if len(set(ids))!=len(ids):errors.append('Node IDs must be unique.')
    for kind in ('source','normalize','verify','output'):
        if kinds.count(kind)!=1:errors.append('Exactly one '+kind+' block is required.')
    if kinds.count('report')>1:errors.append('At most one summary block.')
    if len(graph.edges)!=len(graph.nodes)-1:errors.append('Connect one linear pipeline; branching is unsupported.')
    expected=list(zip(ids,ids[1:]))
    if graph.edges!=expected:errors.append('Edges must connect each displayed block to the next, in order.')
    if kinds and (kinds[0]!='source' or kinds[-1]!='output'):errors.append('Source first, local output last.')
    for a,b in zip(graph.nodes,graph.nodes[1:]):
        if BLOCKS[a.kind][2]!=BLOCKS[b.kind][1]:errors.append('Incompatible ports: '+a.id+' → '+b.id)
    try:
        if not Decimal('0.000001')<=number(graph.factor)<=Decimal('1000000'):raise ValueError()
    except (ValueError,InvalidOperation):errors.append('Factor must be finite, positive and bounded.')
    if graph.family in ('inventory_reconciliation','ticket_triage','document_change','deployment_readiness') and graph.factor != '1':
        errors.append('This template does not support a numeric factor; use 1.')
    return errors


def canonical(family,x,factor='1'):
    f=number(factor)
    if family in ('invoice_reconciliation','invoice_discrepancy'):
        if x['unit']!='USD' or not isinstance(x['payments'],list) or len(x['payments'])>1000:raise ValueError('USD payments required')
        paid=sum((number(v)*f for v in x['payments']),Decimal(0));total=number(x['invoice'])
        if family=='invoice_reconciliation':
            if abs(total-paid)>Decimal('.01'):raise ValueError('Invoice and payment mismatch')
            return {'amount':money(paid),'currency':'USD'}
        return {'difference':money(total-paid),'currency':'USD'}
    if family=='payout_reconciliation':
        digits=integer(x['minor_digits'])
        if digits>3 or x['currency'] not in ('USD','EUR','JPY','KWD'):raise ValueError('Unsupported currency')
        if digits!={'USD':2,'EUR':2,'JPY':0,'KWD':3}[x['currency']]:raise ValueError('Currency minor-unit policy mismatch')
        minor=number(x['actual_minor'])
        if minor<0 or minor!=minor.to_integral_value():raise ValueError('Nonnegative integer minor units required')
        actual=minor/(Decimal(10)**digits)*f
        if actual!=number(x['expected']):raise ValueError('Payout mismatch')
        return {'actual':str(actual.quantize(Decimal(1).scaleb(-digits))),'currency':x['currency']}
    if family=='shipment_reconciliation':
        if x['unit'] not in ('kg','lb'):raise ValueError('Unknown weight unit')
        if number(x['measured'])<=0 or number(x['declared_kg'])<=0:raise ValueError('Positive shipment weights required')
        kg=number(x['measured'])*(Decimal('0.45359237') if x['unit']=='lb' else 1)*f
        if abs(kg-number(x['declared_kg']))>Decimal('.001'):raise ValueError('Weight mismatch')
        return {'weight_kg':str(kg.quantize(Decimal('.001')))}
    if family=='inventory_reconciliation':
        closing=integer(x['opening'])+integer(x['received'])-integer(x['shipped'])
        if closing<0 or closing!=integer(x['counted']):raise ValueError('Inventory discrepancy')
        return {'closing':closing}
    if family in ('data_quality','recurring_report'):
        if x['complete'] is not True or x['unit']!='USD' or not 0<len(x['rows'])<=1000:raise ValueError('Incomplete or unsupported dataset')
        total=Decimal(0);groups={};ids=set()
        for row in x['rows']:
            amount=number(row['amount'])*f;total+=amount
            if family=='data_quality':
                if not isinstance(row['id'],str) or not row['id'] or row['id'] in ids:raise ValueError('Missing/duplicate row identity')
                ids.add(row['id'])
            else:
                k=row['category']
                if not isinstance(k,str) or not 1<=len(k)<=80:raise ValueError('Invalid category')
                groups[k]=groups.get(k,Decimal(0))+amount
        return ({'count':len(ids),'total':money(total),'unit':'USD'} if family=='data_quality' else
                {'groups':{k:money(v) for k,v in sorted(groups.items())},'total':money(total),'unit':'USD'})
    if family=='ticket_triage':
        if x['policy_version']!='1' or not 0<len(x['tickets'])<=1000:raise ValueError('Unsupported triage policy')
        routes={}
        for t in x['tickets']:
            if t['severity'] not in ('urgent','normal') or not isinstance(t['id'],str) or not t['id'] or t['id'] in routes:raise ValueError('Unknown severity or ticket identity')
            routes[t['id']]='priority_review' if t['severity']=='urgent' else 'standard_review'
        return {'routes':routes,'policy_version':'1'}
    if family=='document_change':
        import re
        if any(not isinstance(x[k],str) or not re.fullmatch('[a-f0-9]{64}',x[k]) for k in ('previous_hash','current_hash')):raise ValueError('SHA256 hashes required')
        claims=x['dependent_claims']
        if not isinstance(claims,list) or len(claims)>1000 or any(not isinstance(c,str) for c in claims):raise ValueError('Invalid claim IDs')
        changed=x['previous_hash']!=x['current_hash']
        return {'changed':changed,'invalidated':sorted(set(claims)) if changed else [],'current_hash':x['current_hash']}
    if family=='deployment_readiness':
        if x['tests_passed'] is not True or x['commit']!=x['tested_commit'] or x['config_hash']!=x['tested_config_hash']:raise ValueError('Tested revision differs or tests failed')
        if not isinstance(x['commit'],str) or not x['commit'] or not isinstance(x['config_hash'],str) or len(x['config_hash'])!=64:raise ValueError('Missing revision identity')
        return {'ready':True,'commit':x['commit'],'config_hash':x['config_hash']}
    raise ValueError('Unsupported family')


class RunInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    data: dict
    authority: dict


def execute(graph, body):
    problems=validate(graph)
    if problems:return {'outcome':'blocked','reason':'; '.join(problems),'model_calls':0}
    phase='normalize'
    try:
        candidate=canonical(graph.family,body.data,graph.factor)
        phase='verify'
        evidence=body.authority
        # Evidence is supplied JSON, not independently authenticated. Fresh observation
        # and snapshot identity are required but do not prove real-world source truth.
        timestamp=datetime.fromisoformat(evidence['observed_at'].replace('Z','+00:00'))
        age=(datetime.now(timezone.utc)-timestamp).total_seconds()
        if timestamp.tzinfo is None or not -5<=age<=300:raise ValueError('Authority evidence stale')
        if evidence['snapshot']!=digest(body.data):raise ValueError('Authority snapshot mismatch')
        if evidence['source_id']!='synthetic_control' and not str(evidence['source_id']).startswith('user_control:'):raise ValueError('Unregistered authority source')
        if evidence['expected']!=candidate:raise ValueError('Authority contradicts candidate')
        output=copy.deepcopy(candidate)
        if any(n.kind=='report' for n in graph.nodes):output={'result':candidate,'summary':FAMILIES[graph.family][0]+' checked against the supplied control record.'}
        return {'outcome':'accepted_local','output':output,'candidate':candidate,'model_calls':0,
                'evidence_status':'VALID','predicate_violation':False,'evidence_basis':'supplied control JSON; not independently authenticated'}
    except (KeyError,ValueError,TypeError,AttributeError,InvalidOperation,OverflowError) as exc:
        return {'outcome':'blocked','reason':str(exc)[:180],'failure_stage':phase,'predicate_violation':True if phase=='normalize' or str(exc)=='Authority contradicts candidate' else None,'evidence_status':'UNKNOWN_OR_INVALID','model_calls':0}


def example(family,mode='clean'):
    _,data,expected=FAMILIES[family];data=copy.deepcopy(data);expected=copy.deepcopy(expected)
    body={'data':data,'authority':{'source_id':'synthetic_control','observed_at':now(),'snapshot':digest(data),'expected':expected}}
    if mode=='missing':body['authority']={}
    elif mode=='drift':
        # Schema-valid, family-specific semantic changes; authority retains old truth.
        if family in ('invoice_reconciliation','invoice_discrepancy'):data['payments']=[str(number(v)*100) for v in data['payments']]
        elif family=='payout_reconciliation':data['minor_digits']=0
        elif family=='shipment_reconciliation':data['unit']='lb'
        elif family=='inventory_reconciliation':data['counted']+=1
        elif family in ('data_quality','recurring_report'):data['rows'][0]['amount']='1000'
        elif family=='ticket_triage':data['tickets'][0]['severity']='normal'
        elif family=='document_change':data['current_hash']=data['previous_hash']
        elif family=='deployment_readiness':data['commit']='changed'
        body['authority']['snapshot']=digest(data)
    return body


def default_graph(family):
    ids=['source','normalize','verify','output']
    return Graph(name=FAMILIES[family][0],family=family,nodes=[Node(id=k,kind=k) for k in ids],edges=list(zip(ids,ids[1:])))


class CanvasStore:
    def __init__(self,directory):
        self.path=Path(directory)/'canvas.sqlite3';self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock()
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS objects(id TEXT PRIMARY KEY,kind TEXT,payload TEXT)')
            db.execute("CREATE TRIGGER IF NOT EXISTS immutable_objects_update BEFORE UPDATE ON objects BEGIN SELECT RAISE(ABORT,'immutable'); END")
            db.execute("CREATE TRIGGER IF NOT EXISTS immutable_objects_delete BEFORE DELETE ON objects BEGIN SELECT RAISE(ABORT,'immutable'); END")
    def db(self):return sqlite3.connect(self.path,timeout=15)
    def put(self,kind,value):
        value={**value,'id':value.get('id',kind+'_'+uuid.uuid4().hex[:16]),'created_at':now()}
        with self.db() as db:db.execute('INSERT INTO objects VALUES(?,?,?)',(value['id'],kind,json.dumps(value,allow_nan=False)))
        return value
    def get(self,oid):
        with self.db() as db:row=db.execute('SELECT payload FROM objects WHERE id=?',(oid,)).fetchone()
        if not row:raise LabError('not_found','Canvas object not found',404)
        return json.loads(row[0])
    def all(self,kind):
        with self.db() as db:rows=db.execute('SELECT payload FROM objects WHERE kind=? ORDER BY rowid DESC LIMIT 100',(kind,)).fetchall()
        return [json.loads(r[0]) for r in rows]
    def test(self,graph,actor):
        problems=validate(graph);rows=[]
        if not problems:
            for mode in ('clean','drift','missing'):
                result=execute(graph,RunInput(**example(graph.family,mode)))
                rows.append({'case':mode,'outcome':result['outcome'],'passed':result['outcome']==('accepted_local' if mode=='clean' else 'blocked')})
        return self.put('validation',{'graph':graph.model_dump(),'graph_hash':digest(graph.model_dump()),'actor':actor,'problems':problems,'cases':rows,'passed':not problems and all(r['passed'] for r in rows),'runtime_policy_hash':policy_hash(),'scope':'3 authored synthetic cases, not generalization proof'})
    def publish(self,report_id,actor,separate):
        r=self.get(report_id)
        if not report_id.startswith('validation_') or not r['passed'] or r.get('runtime_policy_hash')!=policy_hash():raise LabError('validation_required','Passing validation required',409)
        if separate and actor==r['actor']:raise LabError('separate_reviewer','Publisher must differ from builder',409)
        return self.put('version',{'graph':r['graph'],'graph_hash':r['graph_hash'],'report_id':report_id,'reviewer':actor,'runtime_policy_hash':policy_hash()})
    def run(self,vid,body,actor):
        v=self.get(vid)
        if not vid.startswith('version_') or digest(v['graph'])!=v['graph_hash'] or v.get('runtime_policy_hash')!=policy_hash():raise LabError('version_invalid','Invalid version',409)
        import time
        started=time.monotonic()
        result=execute(Graph(**v['graph']),body)
        result['runtime_ms']=round((time.monotonic()-started)*1000,3)
        from .hybrid import Monitor,rank_causes
        rid='execution_'+uuid.uuid4().hex[:16]
        unknown=result.get('predicate_violation') is None
        steps=[n['id'] for n in v['graph']['nodes']]
        failure=next((n['id'] for n in v['graph']['nodes'] if n['kind']==result.get('failure_stage')),None)
        deps={n:[steps[i-1]] if i else [] for i,n in enumerate(steps)}
        hybrid=Monitor(self.path.parent).observe(rid,'canvas:'+vid+':'+v['graph_hash'],signals={'runtime_ms':result['runtime_ms']},
            label=result.get('predicate_violation'),label_basis='Supplied JSON predicate outcomes only; not independently authenticated correctness.',
            verified=result['outcome']=='accepted_local',unknown=unknown,known_local=False,ambiguous=result['outcome']!='accepted_local' and not unknown,
            causes=rank_causes(steps,deps,[failure] if failure else []),predicates={failure:True} if failure and not unknown else {})
        return self.put('execution',{'id':rid,'hybrid':hybrid,'version_id':vid,'graph_hash':v['graph_hash'],'inputs_hash':digest(body.model_dump()),'actor':actor,'result':result,'source_snapshot':digest(body.data),'graph':v['graph']})
