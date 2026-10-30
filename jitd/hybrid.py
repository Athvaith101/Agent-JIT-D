"""Persistent cheap monitoring and auditable expected-risk routing, never an acceptance gate."""
import json
import math
import sqlite3
import statistics
import uuid
from pathlib import Path
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


class Policy(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    enabled: bool=False
    minimum_verified: int=Field(default=8,ge=0,le=10000)
    warmup: int=Field(default=8,ge=4,le=128)
    cusum_k: float=Field(default=1.5,ge=0,le=100)
    cusum_h: float=Field(default=8,gt=0,le=1000)
    loss_usd: float=Field(default=100,ge=0,le=1000000)
    model_cost_usd: float=Field(default=.01,ge=0,le=1000)
    residual_probability: float=Field(default=.01,ge=0,le=1)
    human_cost_usd: float=Field(default=5,ge=0,le=100000)
    local_cost_usd: float=Field(default=.001,ge=0,le=1000)
    slot: str=Field(default='primary',pattern='^(primary|secondary)$')


def stamp():return datetime.now(timezone.utc).isoformat()


def robust_score(value,baseline):
    center=statistics.median(baseline)
    mad=statistics.median(abs(v-center) for v in baseline)
    # Explicit engineering floor avoids division by near-zero for constant signals.
    scale=max(1.4826*mad,abs(center)*.05,.01)
    return max(-20,min(20,(value-center)/scale)),center,scale


def rank_causes(steps,deps,failed):
    """Deterministic graph ranking. Scores are not posterior probabilities."""
    positions={s:i for i,s in enumerate(steps)}
    failed=set(failed);rows=[]
    for step in failed:
        direct_failed=sorted(set(deps.get(step,[])) & failed)
        rows.append({'step':step,'upstream_inputs_failed':direct_failed,
                     'score':2 if not direct_failed else 1,
                     'reason':'Output check failed with no directly failed input dependency.' if not direct_failed else 'May be a downstream symptom of failed inputs.'})
    return sorted(rows,key=lambda r:(-r['score'],positions.get(r['step'],9999)))


def route(policy,beta,*,verified,unknown,known_local,ambiguous,alarm,model_ready,budget_remaining):
    p=beta['alpha']/(beta['alpha']+beta['beta'])
    before=p*policy.loss_usd;after=policy.model_cost_usd+policy.residual_probability*policy.loss_usd
    eligible_model=(policy.enabled and model_ready and budget_remaining>0 and beta['verified']>=policy.minimum_verified
                    and ambiguous and not unknown and not known_local and before>after and after<policy.human_cost_usd)
    if unknown:action='block_missing_evidence'
    elif known_local:action='propose_local_repair' if policy.local_cost_usd<=policy.human_cost_usd else 'human_review'
    elif verified and not alarm:action='accept_verified_fast_path'
    elif verified:action='review_operational_drift'
    elif eligible_model:action='model_diagnosis'
    else:action='human_review'
    return {'action':action,'model_eligible':eligible_model,'model_calls_dispatched':0,
            'acceptance_authorized':False,'risk_proxy':p,'risk_basis':'Beta mean of verified predicate violations; NOT calibrated output error probability',
            'acceptance_risk_proxy_usd':before,'model_plus_residual_assumption_usd':after,
            'human_cost_assumption_usd':policy.human_cost_usd,'estimated_benefit_usd':before-after,
            'requirements':{'enabled':policy.enabled,'minimum_verified_met':beta['verified']>=policy.minimum_verified,
                            'model_configured':model_ready,'attempt_budget_remaining':budget_remaining,'ambiguous':ambiguous,
                            'required_evidence_available':not unknown},
            'note':'Expected costs/residual risk are administrator assumptions. Missing evidence always blocks. Model assistance never changes a saved result.'}


class Monitor:
    def __init__(self,directory):
        self.path=Path(directory)/'hybrid.sqlite3';self.path.parent.mkdir(exist_ok=True,parents=True)
        with self.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS policy(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT);
            CREATE TABLE IF NOT EXISTS state(context TEXT PRIMARY KEY,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS observations(run_id TEXT PRIMARY KEY,context TEXT NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,created TEXT,actor TEXT,payload TEXT);
            CREATE TABLE IF NOT EXISTS dispatch(run_id TEXT PRIMARY KEY,status TEXT,payload TEXT);
            CREATE TABLE IF NOT EXISTS regime(id INTEGER PRIMARY KEY CHECK(id=1),generation TEXT NOT NULL);
            ''')
        with self.db() as db:db.execute('INSERT OR IGNORE INTO regime VALUES(1,?)',(uuid.uuid4().hex,))
    def db(self):return sqlite3.connect(self.path,timeout=15)
    def policy(self):
        with self.db() as db:r=db.execute('SELECT payload FROM policy WHERE id=1').fetchone()
        return Policy(**json.loads(r[0])) if r else Policy()
    def configure(self,policy,actor):
        # Parameter changes begin a new statistical regime; no mixed-threshold CUSUM.
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT OR REPLACE INTO policy VALUES(1,?)',(policy.model_dump_json(),))
            db.execute('DELETE FROM state')
            db.execute('UPDATE regime SET generation=? WHERE id=1',(uuid.uuid4().hex,))
            db.execute('INSERT INTO events(created,actor,payload) VALUES(?,?,?)',(stamp(),actor,policy.model_dump_json()))
        return {'policy':policy.model_dump(),'reset':'New monitoring regime; prior observation records retained.'}
    def observe(self,run_id,context,*,signals,label,label_basis,verified,unknown,known_local,ambiguous,causes,model_ready=False,budget_remaining=0,predicates=None):
        if label is not None and type(label) is not bool:raise ValueError('verified predicate label must be bool or None')
        safe={}
        for k,v in signals.items():
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):continue
            safe[k]=float(v)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT payload,context FROM observations WHERE run_id=?',(run_id,)).fetchone()
            if prior:
                if prior[1]!=context:raise ValueError('Run already observed in another context')
                return json.loads(prior[0])
            row=db.execute('SELECT payload FROM policy WHERE id=1').fetchone();policy=Policy(**json.loads(row[0])) if row else Policy()
            row=db.execute('SELECT payload FROM state WHERE context=?',(context,)).fetchone()
            state=json.loads(row[0]) if row else {'alpha':1,'beta':1,'verified':0,'signals':{},'steps':{}}
            signal_rows=[]
            for name,value in safe.items():
                s=state['signals'].setdefault(name,{'baseline':[],'g':0})
                baseline=s['baseline'];ready=len(baseline)>=policy.warmup
                z=center=scale=None
                if ready:
                    z,center,scale=robust_score(value,baseline)
                    s['g']=max(0,min(1000000,s['g']+abs(z)-policy.cusum_k))
                alarm=ready and s['g']>policy.cusum_h
                signal_rows.append({'name':name,'value':value,'baseline_count':len(baseline),'z':z,'median':center,'scale':scale,'cusum':s['g'],'alarm':alarm,'status':'monitoring' if ready else 'warming_up'})
                # Freeze after warmup. Failed/unknown cases never train a clean reference.
                if label is False and verified and not ready:baseline.append(value)
            # label=True means an observed predicate violation, not a silent error.
            if label is not None:
                state['alpha' if label else 'beta']+=1;state['verified']+=1
            for step,violation in (predicates or {}).items():
                if violation is None:continue
                b=state['steps'].setdefault(step,{'alpha':1,'beta':1,'verified':0})
                b['alpha' if violation else 'beta']+=1;b['verified']+=1
            beta={k:state[k] for k in ('alpha','beta','verified')}
            alarm=any(r['alarm'] for r in signal_rows)
            generation=db.execute('SELECT generation FROM regime WHERE id=1').fetchone()[0]
            result={'regime_id':generation,'run_id':run_id,'context':context,'created':stamp(),'signals':signal_rows,'alarm':alarm,
                    'label':{'predicate_violation':label,'basis':label_basis,'scope':'Verified predicate results, not independent real-world correctness'},
                    'reliability':{**beta,'mean':beta['alpha']/(beta['alpha']+beta['beta']),'prior':'Beta(1,1)',
                                   'warning':'No IID, stationarity or calibrated silent-error bound is claimed.'},
                    'step_reliability':state['steps'],'cause_ranking':causes,'routing_inputs':{'verified':verified,'unknown':unknown,'known_local':known_local,'ambiguous':ambiguous,'alarm':alarm},
                    'policy':policy.model_dump(),'route':route(policy,beta,verified=verified,unknown=unknown,known_local=known_local,
                                                               ambiguous=ambiguous,alarm=alarm,model_ready=model_ready,budget_remaining=budget_remaining),
                    'monitoring_order':'Post-run monitoring. Strict mandatory evidence gates acceptance before any local output. Statistical alerts do not certify semantic correctness.'}
            db.execute('INSERT OR REPLACE INTO state VALUES(?,?)',(context,json.dumps(state)))
            db.execute('INSERT INTO observations VALUES(?,?,?)',(run_id,context,json.dumps(result)))
            return result
    def get(self,rid):
        with self.db() as db:r=db.execute('SELECT payload FROM observations WHERE run_id=?',(rid,)).fetchone()
        return json.loads(r[0]) if r else None
    def generation(self):
        with self.db() as db:return db.execute('SELECT generation FROM regime WHERE id=1').fetchone()[0]
    def claim(self,rid,policy,generation):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT payload FROM policy WHERE id=1').fetchone()
            current=Policy(**json.loads(row[0])) if row else Policy()
            if current!=policy or db.execute('SELECT generation FROM regime WHERE id=1').fetchone()[0]!=generation:return False
            return db.execute('INSERT OR IGNORE INTO dispatch VALUES(?,?,?)',(rid,'reserved','{}')).rowcount==1
    def complete(self,rid,payload):
        with self.db() as db:db.execute('UPDATE dispatch SET status=?,payload=? WHERE run_id=?',('finished',json.dumps(payload),rid))
    def dispatch(self,rid):
        with self.db() as db:r=db.execute('SELECT status,payload FROM dispatch WHERE run_id=?',(rid,)).fetchone()
        return {'status':r[0],'result':json.loads(r[1])} if r else None
    def overview(self):
        with self.db() as db:
            states=[{'context':c,**json.loads(p)} for c,p in db.execute('SELECT context,payload FROM state')]
            rows=[json.loads(r[0]) for r in db.execute('SELECT payload FROM observations ORDER BY rowid DESC LIMIT 100')]
        return {'policy':self.policy().model_dump(),'states':states,'observations':rows,'scope':'latest 100 observations; complete labels in SQLite; no LLM confidence used'}


def studio_observation(directory,vid,result,manifest,run_result):
    from .diagnosis import diagnose
    from .studio import fingerprint
    required=[a for a in result['assumptions'] if a.get('required')]
    unknown=any(a['status']=='UNKNOWN' and a['node'] in run_result.values for a in required)
    invalid=any(a['status']=='INVALID' for a in required)
    hard=[c for c in result['contract_results'] if not c['ok'] and c.get('severity')!='warning']
    verified=result['outcome']=='posted' and bool(required) and all(a['status']=='VALID' for a in required)
    schema_failure=(result.get('halt') or {}).get('reason')=='schema_invalid'
    label=True if invalid or hard or schema_failure else False if verified else None
    diagnosis=diagnose(manifest,run_result) if result['outcome'] in ('halted','held') else {}
    known=diagnosis.get('status')=='localized' and (diagnosis.get('top') or {}).get('name') in ('unit_scale','truncated_pagination')
    failed={c['step'] for c in hard}|{a['node'] for a in required if a['status']=='INVALID'}
    if schema_failure and (result.get('halt') or {}).get('step'):failed.add(result['halt']['step'])
    signals={s['id']+'.latency_ms':s['duration_ms'] for s in result['steps'] if s['status']=='passed' and not s.get('reused')}
    for key,value in run_result.values.items():
        if isinstance(value,dict) and isinstance(value.get('payments'),list):signals[key+'.record_count']=len(value['payments'])
    causes=rank_causes([s.id for s in manifest.steps],manifest.deps(),failed)
    for c in causes:c['diagnosis']=diagnosis.get('status','not_required')
    predicates={}
    grouped={}
    for a in required:grouped.setdefault(a['node'],[]).append(a['status'])
    for node,statuses in grouped.items():
        predicates[node]=True if 'INVALID' in statuses else False if all(x=='VALID' for x in statuses) else None
    for c in hard:predicates[c['step']]=True
    if schema_failure and (result.get('halt') or {}).get('step'):predicates[result['halt']['step']]=True
    try:
        from decimal import Decimal
        inv=run_result.values[manifest.step_for_op('invoice.get').id]
        pay=run_result.values[manifest.step_for_op('payment.list').id]
        total=Decimal(str(inv['total']))
        if total>0:signals['raw_payment_invoice_ratio']=float(sum((Decimal(str(p['amount'])) for p in pay['payments']),Decimal(0))/total)
    except (KeyError,ValueError,TypeError,AttributeError,ArithmeticError):pass
    report=Monitor(directory).observe(result['run_id'],'studio:'+vid+':'+fingerprint(manifest.model_dump()),signals=signals,label=label,
            label_basis='Deterministic contracts and simulated authority predicates; not the model diagnosis.',verified=verified,
            unknown=unknown,known_local=known,ambiguous=not verified and not unknown and not known,causes=causes,predicates=predicates)
    report['diagnosis']=diagnosis
    return report
