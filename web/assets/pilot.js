/* Read-only pilot cases, durable review and explicit submission evidence gates. */
const previousNavigate = navigate;
navigate = page => {
  document.querySelector('#pilot').hidden = page !== 'pilot';
  previousNavigate(page);
  document.querySelector('#tabPilot').classList.toggle('on', page === 'pilot');
  if (page === 'pilot') {
    document.querySelector('#pageTitle').textContent = 'Pilot & readiness';
    loadPilot().catch(e => toast(e.message));
  }
};
document.querySelector('#tabPilot').onclick = () => navigate('pilot');
async function loadPilot() {
  const [data, readiness, paired] = await Promise.all([
    api('GET', '/api/pilot'), api('GET', '/api/readiness'), api('GET', '/api/research/paired')
  ]);
  const root = document.querySelector('#pilot');
  root.innerHTML = `<div class="page-heading"><div><div class="eyebrow">External evidence · read-only</div><h1>From recorded data to a reviewable decision.</h1><p class="subtitle">Import an authorized case, refresh missing proof and re-verify. Reviewer notes never override the posting gate.</p></div><a class="action" href="/api/pilot/export">Export pilot evidence</a></div>
  <div class="metric-grid">${metric('Imported cases',data.report.cases,'Provenance is importer-declared')}${metric('Verified shadow outputs',data.report.verified_shadow_outputs,'Authority agreement, not independent field accuracy')}${metric('Blocked cases',data.report.blocked,'Missing or contradictory proof')}${metric('Reported review time',data.report.reported_human_minutes+' min','Entered by reviewer')}</div>
  <section class="panel"><div class="panel-head"><h2>Import an incident bundle</h2><span class="pill unknown">No external writes</span></div><div class="panel-content"><p>JSON includes recording, authority, source and provenance. Missing proof is allowed and remains UNKNOWN. See docs/archive/RELEASE_P0_P2.md for the schema.</p><label class="action">Choose case JSON <input id="pilotFile" type="file" accept=".json,application/json"></label></div></section>
  ${data.cases.map((c,i)=>`<article class="incident-item"><div class="incident-top"><span class="pill ${c.result.outcome==='posted'?'':'warn'}">${esc(c.result.outcome==='posted'?'Verified shadow output':c.result.outcome)}</span><small>Revision ${c.revision} · ${esc(c.bundle.provenance.real_data?'Declared real data':'Synthetic / unspecified data')}</small></div><h2>${esc(c.bundle.recording.invoice_id)}</h2><p>Author: ${esc(c.bundle.provenance.author)} · ${esc(c.bundle.provenance.collection_method)}</p><p>${esc(c.result.halt?.reason||'Independent gate completed')} · ${c.reviews.length} review(s)</p><div class="actions"><button class="action" data-review-case="${i}">Review evidence & re-verify</button></div><details class="review-details"><summary>Verification and provenance</summary><pre>${esc(JSON.stringify({result:c.result,provenance:c.bundle.provenance,reviews:c.reviews},null,2))}</pre></details></article>`).join('')||'<div class="empty-state">No pilot cases imported. The execution demo remains available separately.</div>'}
  <section class="panel"><div class="panel-head"><h2>Submission evidence gates</h2><span class="pill unknown">No automatic winner claim</span></div><div class="table-scroll"><table class="op-table"><thead><tr><th>Priority / gate</th><th>Status</th><th>Evidence needed</th></tr></thead><tbody>${readiness.gates.map(g=>`<tr><td>${esc(g.priority)} · ${esc(g.id.replaceAll('_',' '))}</td><td>${esc(g.status.replaceAll('_',' '))}</td><td>${esc(g.why)}</td></tr>`).join('')}</tbody></table></div></section>
  ${paired.available?`<section class="panel"><div class="panel-head"><h2>Same-evidence recovery study</h2><span class="pill unknown">Synthetic</span></div><div class="panel-content"><p>Semantic slicing has not demonstrated superiority over equally guarded dependency replay on these cases.</p></div><div class="table-scroll"><table class="op-table"><thead><tr><th>Case / method</th><th>Correct</th><th>Blocked</th><th>Reused nodes</th></tr></thead><tbody>${paired.cells.map(c=>`<tr><td>${esc(c.case)}<small>${esc(c.method)}</small></td><td>${c.correct_outputs}/${c.trials}</td><td>${c.blocked}</td><td>${c.reused_nodes}</td></tr>`).join('')}</tbody></table></div></section>`:''}`;
  document.querySelector('#pilotFile').onchange=async e=>{
    const file=e.target.files[0];if(!file)return;if(file.size>2097152){toast('Case exceeds 2 MiB');return}
    await opsAction(async()=>{await api('POST','/api/pilot/import',JSON.parse(await file.text()));await loadPilot();toast('Case imported and verified in memory. No external write performed.')});
  };
  root.querySelectorAll('[data-review-case]').forEach(b=>b.onclick=()=>reviewPilot(data.cases[Number(b.dataset.reviewCase)]));
}
function reviewPilot(c) {
  const dialog=document.querySelector('#reviewDialog');
  document.querySelector('#reviewContent').innerHTML=`<div class="eyebrow">Evidence resolution · revision ${c.revision}</div><h2>${esc(c.bundle.recording.invoice_id)}</h2><p>Refresh the authority observation using its actual collection time. A reviewer note cannot establish independence or replace proof. The original source trust declaration remains in force.</p><label>Reviewer <input id="pilotReviewer" maxlength="100" required></label><label>Evidence note <textarea id="pilotNote" maxlength="2000" rows="3"></textarea></label><label>Human minutes spent <input id="pilotMinutes" type="number" min="0" max="1440" value="0"></label><label>Authority record JSON (blank keeps current) <textarea id="pilotAuthority" rows="8">${esc(c.bundle.authority?JSON.stringify(c.bundle.authority,null,2):'')}</textarea></label><div class="actions"><button class="action primary" id="pilotReverify">Record review & re-verify</button><button class="action" id="pilotClose">Close</button></div>`;
  document.querySelector('#pilotClose').onclick=()=>dialog.close();
  document.querySelector('#pilotReverify').onclick=()=>opsAction(async()=>{
    const text=document.querySelector('#pilotAuthority').value.trim();
    const result=await api('POST',`/api/pilot/${c.id}/review`,{revision:c.revision,reviewer:document.querySelector('#pilotReviewer').value,note:document.querySelector('#pilotNote').value,human_minutes:Number(document.querySelector('#pilotMinutes').value),authority:text?JSON.parse(text):null});
    dialog.close();await loadPilot();toast(result.result.outcome==='posted'?'Fresh verification passed. Shadow output accepted.':'Review recorded. Required evidence still blocks acceptance.');
  });
  dialog.showModal();
}

const measuredRefresh=refreshState;
refreshState=async()=>{await measuredRefresh();try{const o=await api('GET','/api/operations');const u=o.usage.filter(x=>x.source==='provider');if(u.length){const last=u[u.length-1];document.querySelector('#mode').textContent=`${last.model||'Model'} · ${o.meter.total_tokens} reported tokens · ${Number(last.latency_ms||0).toFixed(0)} ms last call`;}}catch(e){console.warn('Usage header unavailable')}};
