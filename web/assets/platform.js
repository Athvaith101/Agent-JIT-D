'use strict';
const select = s => document.querySelector(s);
function text(id, value){select('#'+id).textContent=value??'Unknown';}
async function get(url){const r=await fetch(url);const data=await r.json();if(!r.ok)throw new Error(data.error?.message||'Status request failed');return data;}
async function load(){
 select('#refresh').disabled=true;select('#error').hidden=true;
 try{
  const [me,s,r]=await Promise.all([get('/api/platform/me'),get('/api/platform/status'),get('/api/platform/ready')]);
  text('identity',me.name+' · '+me.role);text('role',me.role);text('profile',s.profile==='enterprise'?'Named-user profile':'Local sandbox');
  text('ready',r.ready?'Ready':'Not ready');text('remaining',s.budget.remaining);text('budgetNote',s.budget.used+' reserved / '+s.budget.limit+' allowed attempts');
  text('chain',s.audit.valid?'Verified':'Invalid');text('auditCount',s.audit.verified_events+' receipts verified');text('paused',s.paused?'Paused':'Running');
  text('auth',s.authentication);text('promotion',s.promotion);text('storage',s.storage);text('modelState',s.model_configured?'Configured':'Offline');text('model',s.model_id||'No provider configured');
  text('inputs',s.usage.reported_input_tokens);text('outputs',s.usage.reported_output_tokens);text('unknown',s.usage.usage_unknown_calls);text('persistent',s.budget_persistent?'Yes':'No — use the supplied launcher');
  text('head','Verified chain head: '+s.audit.head);
  const rows=select('#receipts');rows.replaceChildren();
  if(me.role==='admin'){
   select('#export').hidden=false;
   const a=await get('/api/platform/audit');
   text('receiptNote','Most recent 500 security receipts. Request bodies, credentials and query strings are excluded.');
   for(const e of a.events.slice(0,40)){
    const tr=document.createElement('tr');
    for(const value of [e.created.slice(0,19).replace('T',' ')+' UTC · '+e.action,e.actor||'—',[(e.method||''),(e.path||e.target||'')].join(' '),e.status??'—',e.request_id||'—']){
     const td=document.createElement('td');td.textContent=value;tr.append(td);
    }rows.append(tr);
   }
   if(!a.events.length)text('receiptNote','No security receipts yet. Perform an operation in the workflow workspace.');
  }else{text('receiptNote','Your role can view service status. Detailed security receipts are restricted to administrators.');}
 }catch(e){text('error',e.message);select('#error').hidden=false;}
 finally{select('#refresh').disabled=false;}
}
select('#refresh').onclick=load;load();
