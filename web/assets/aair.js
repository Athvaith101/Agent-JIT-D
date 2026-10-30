/* Assumptions, invalidation and checkpoint reuse are rendered only from backend records. */
function renderAssumptions(run){
 const records=run?.assumptions||S.state?.workflow.assumptions||[];
 $('#assumptionsPanel').innerHTML=`<div class="verify-title"><strong>Verification console</strong><span class="pill ${records.some(a=>a.status==='INVALID')?'invalid':records.every(a=>a.status==='VALID')&&run?'':'unknown'}">${run?'Observed evidence':'Not yet evaluated'}</span></div>${records.map(a=>`<div class="assumption-row"><div><span class="pill ${a.status==='VALID'?'':a.status==='INVALID'?'invalid':'unknown'}">${a.status==='VALID'?'✓':a.status==='INVALID'?'×':'?'} ${esc(a.status)}</span></div><div><strong>${esc(a.semantic_contract)}</strong><p>${esc(a.reason||'Run the workflow to collect evidence.')}</p><small>${esc(a.id)} · ${esc(a.node)} · ${esc(a.evidence?.source_id||a.evidence_source)}<br>${esc(a.verified_at||'No verification timestamp')}${a.evidence?.expected_usd!=null?` · expected USD ${esc(a.evidence.expected_usd)} · observed ${esc(a.evidence.observed_usd)}`:''}</small></div></div>`).join('')||'<div class="empty">No assumption registry available.</div>'}`;
 const r=run?.recovery;
 $('#recoveryPanel').innerHTML=r?`<div class="recovery-report"><strong>AAIR recovery · ${r.accepted_output?'output re-verified':'output not accepted'}</strong><div>Changed: <code>${esc(r.changed_nodes.join(', '))}</code></div><div>Invalidated: <code>${esc(r.invalidated_nodes.join(' → '))}</code></div><div>Safe checkpoints reused: <code>${esc(r.reused_nodes.join(', ')||'none')}</code></div><div>Executed: <code>${esc(r.executed_nodes.join(' → '))}</code></div><p class="scope-note">${esc(r.checkpoint_rule)}. ${r.fallback_reasons.map(esc).join(' ')}</p></div>`:'';
 paintAAIR(run);
}
function paintAAIR(run){
 const invalid=new Set((run?.assumptions||[]).filter(a=>a.status==='INVALID').map(a=>a.node));
 const unknown=new Set((run?.assumptions||[]).filter(a=>a.status==='UNKNOWN').map(a=>a.node));
 const reused=new Set(run?.recovery?.reused_nodes||[]),changed=new Set(run?.recovery?.invalidated_nodes||[]);
 Object.entries(S.nodes).forEach(([id,g])=>{g.classList.toggle('assumption-invalid',invalid.has(id));g.classList.toggle('assumption-unknown',unknown.has(id));g.classList.toggle('reused',reused.has(id));g.classList.toggle('repaired',changed.has(id)&&!!run?.recovery?.accepted_output)});
}
const baseFinish=finishRun;
finishRun=async v=>{await baseFinish(v);renderAssumptions(v);if(v.halt?.reason?.startsWith('assumption_'))banner('warn',`${v.halt.reason.toUpperCase()} · ${v.halt.assumption} · ${v.halt.message} No posting allowed.`);if(v.recovery)banner(v.recovery.accepted_output?'ok':'warn',`AAIR · ${v.recovery.reused_nodes.length} safe checkpoints reused · ${v.recovery.executed_nodes.length} nodes re-executed · ${v.recovery.accepted_output?'independent re-verification passed':'output not accepted'}`)};
const basePaint=paintStatus;paintStatus=()=>{basePaint();paintAAIR(S.run)};
const baseOnEvent=onEvent;onEvent=ev=>{baseOnEvent(ev);if(ev.type==='checkpoint_reused'&&S.nodes[ev.step])S.nodes[ev.step].classList.add('reused');if(ev.type==='recovery_planned')$('#recoveryPanel').innerHTML='<div class="recovery-report"><strong>Invalidating affected region…</strong>'+esc(ev.recovery.invalidated_nodes.join(' → '))+'</div>'};
$('#evidenceMode').onchange=()=>act(async()=>{const r=await api('POST','/api/evidence-mode',{mode:$('#evidenceMode').value});await refreshState();banner('warn',r.note)});
const beforeRefresh=refreshState;refreshState=async()=>{await beforeRefresh();$('#evidenceMode').value=S.state.evidence_mode||'independent';renderAssumptions(S.run)};
const beforeReset=resetRunUi;resetRunUi=()=>{beforeReset();S.run=null;renderAssumptions(null)};
// Wait for the existing initialization request; no fabricated status is supplied meanwhile.
api('GET','/api/state').then(state=>{if(!S.state)S.state=state;renderAssumptions(S.run)}).catch(()=>{});
