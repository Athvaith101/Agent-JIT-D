"use strict";
const $ = s => document.querySelector(s);
const NS = "http://www.w3.org/2000/svg";
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const clip = (s, n) => (s = String(s ?? ""), s.length > n ? s.slice(0, n - 1) + "…" : s);
const S = { meta: null, state: null, run: null, diag: null, sel: null, nodes: {}, status: {}, events: [], busy: false, blocked: null, repaired: false, es: null };

async function api(method, url, body) {
  const r = await fetch(url, { method, headers: body ? { "content-type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined });
  let j = null; try { j = await r.json() } catch (e) { }
  if (!r.ok) { const m = (j && (j.error?.message || j.detail)) || r.statusText; throw new Error((typeof m === "string" ? m : JSON.stringify(m)) + " · request " + (r.headers.get("X-Request-ID") || "unknown")) }
  return j;
}
function banner(kind, text) { const b = $("#banner"); b.className = "banner " + kind; b.textContent = text }
function sys(text, cls) { const s = $("#sysstate"); s.textContent = text; s.className = "chip mono " + (cls || "") }
function setBusy(b) {
  S.busy = b; sys(b ? "working…" : "idle", b ? "busy" : "");
  ["bCompile", "bCompileM", "bRun", "bInject", "bReset", "bHard"].forEach(i => $("#" + i).disabled = b);
  updateButtons();
}
function updateButtons() {
  const r = S.run, hasModel = S.meta && S.meta.model_configured, blocked = r && ["halted", "held"].includes(r.outcome);
  $("#bCompileM").disabled = S.busy || !hasModel; $("#bCompileM").title = hasModel ? "" : "No Nebius model is configured on this server";
  $("#bDiag").disabled = S.busy || !blocked;
  const canRepair = !S.busy && blocked && !!S.diag && S.run && S.state && S.run.manifest_version === S.state.workflow.version;
  $("#bRepair").disabled = !canRepair; $("#bWrong").disabled = !canRepair; $("#bRepairM").disabled = !canRepair || !hasModel;
  $("#bRepairM").title = hasModel ? "" : "No Nebius model is configured on this server";
  $("#bRetry").disabled = S.busy || !S.blocked;
  if (S.identity?.profile === 'enterprise') {
    const operates = ['admin','operator'].includes(S.identity.role);
    ['bCompile','bCompileM','bRun','bInject','bDiag','bRepair','bRepairM','bRetry'].forEach(id=>{if(!operates) $('#'+id).disabled=true;});
    if(S.identity.role!=='admin') $('#bReset').disabled=true;
    ['evidenceMode','scn'].forEach(id=>$('#'+id).disabled=!operates);
  }
}

/* ------------------------------------------------------------------ graph */
function layout(steps) {
  const depth = {}; steps.forEach(s => depth[s.id] = s.deps.length ? 1 + Math.max(...s.deps.map(d => depth[d])) : 0);
  const cols = {}; steps.forEach(s => (cols[depth[s.id]] ||= []).push(s));
  const nCols = Math.max(...Object.keys(cols).map(Number)) + 1, pos = {};
  Object.entries(cols).forEach(([c, list]) => list.forEach((s, i) => { pos[s.id] = { x: 18 + c * (724 - 124) / Math.max(1, nCols - 1), y: 20 + i * 70 + (list.length < 3 ? (3 - list.length) * 28 : 0) } }));
  return pos;
}
function drawGraph() {
  const svg = $("#svg"); svg.innerHTML = ""; S.nodes = {};
  const steps = S.state.workflow.steps, pos = layout(steps);
  steps.forEach(s => s.deps.forEach(d => {
    const a = pos[d], b = pos[s.id], p = document.createElementNS(NS, "path");
    p.setAttribute("d", `M${a.x + 124} ${a.y + 17} C${(a.x + 124 + b.x) / 2} ${a.y + 17},${(a.x + 124 + b.x) / 2} ${b.y + 17},${b.x} ${b.y + 17}`);
    p.setAttribute("class", "edge"); p.dataset.from = d; p.dataset.to = s.id; svg.appendChild(p);
  }));
  steps.forEach(s => {
    const g = document.createElementNS(NS, "g"); g.setAttribute("class", "node"); g.setAttribute("transform", `translate(${pos[s.id].x},${pos[s.id].y})`);
    g.setAttribute("tabindex", "0"); g.setAttribute("role", "button"); g.setAttribute("aria-label", s.id);
    const p = Object.keys(s.params || {}).length ? " ·params" : "";
    g.innerHTML = `<rect width="124" height="34" rx="6"/><text x="8" y="15">${esc(clip(s.id, 17))}</text><text class="sub" x="8" y="27">${esc(s.operation)}${p}</text>`;
    g.onclick = () => { S.sel = s.id; paintStatus(); renderEvidence() };
    g.onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); g.onclick() } };
    svg.appendChild(g); S.nodes[s.id] = g;
  });
  paintStatus();
}
function paintStatus() {
  Object.entries(S.nodes).forEach(([id, g]) => {
    const st = S.status[id] || "";
    g.setAttribute("class", "node " + st + (S.sel === id ? " sel" : "") + (S.suspect === id ? " suspect" : ""));
  });
  document.querySelectorAll(".edge").forEach(e => e.classList.toggle("hot", S.suspect && (e.dataset.from === S.suspect || e.dataset.to === S.suspect)));
}

/* ------------------------------------------------------------------ timeline */
function addEvent(ev) {
  const tl = $("#timeline"); tl.querySelector(".empty")?.remove();
  const t = ev.type, cls = t === "run_halted" || (t === "contract_result" && !ev.ok && ev.severity === "critical") ? "bad" : t === "run_flagged" || (t === "contract_result" && !ev.ok) ? "warn" : t === "run_finished" || (t === "contract_result" && ev.ok) ? "good" : "";
  const d = document.createElement("div"); d.className = "ev " + cls;
  const detail = t === "contract_result" ? `${ev.id} · ${ev.ok ? "pass" : "FAIL " + ev.severity}` : t === "step_finished" ? `${clip(ev.summary, 70)} · ${ev.duration_ms} ms` :
    t === "run_halted" ? clip(ev.message, 110) : t === "run_flagged" ? clip(ev.message, 110) : t === "run_finished" ? `${ev.outcome} · model calls ${ev.model_calls}` : t === "schema_validation" ? (ev.ok ? "schema valid" : "SCHEMA INVALID") : t === "ledger_posted" ? `${ev.entry.disposition}: ${ev.entry.amount_usd} USD` : "";
  d.innerHTML = `<span>${esc((ev.ts || "").slice(11, 23))}</span><b>${esc(t)}${ev.step ? " · " + esc(ev.step) : ""}</b><span>${esc(detail)}</span>`;
  tl.appendChild(d); tl.scrollTop = 1e9;
}
function note(text, cls) { addEvent({ type: text, ts: new Date().toISOString(), _cls: cls }) }

/* ------------------------------------------------------------------ run */
function resetRunUi() {
  S.status = {}; S.suspect = null; S.diag = null; S.events = []; $("#timeline").innerHTML = '<div class="empty">Running…</div>';
  ["sOut", "sOracle", "sRunCalls", "sMs"].forEach(i => $("#" + i).textContent = "–");
}
function onEvent(ev) {
  S.events.push(ev); const T = ev.type;
  if (T === "step_started") S.status[ev.step] = "running";
  else if (T === "step_finished") S.status[ev.step] = "passed";
  else if (T === "contract_result" && !ev.ok && ev.severity === "warning") S.status[ev.step] = "flagged";
  else if (T === "run_flagged") S.status[ev.step] = "flagged";
  else if (T === "run_halted") S.status[ev.step] = "failed";
  else if (T === "run_view") { finishRun(ev.run); return }
  else if (T === "error") { banner("bad", `${ev.code}: ${ev.message}`); return }
  if (T !== "stream_end") addEvent(ev);
  paintStatus();
}
async function streamRun(invoice) {
  if (S.busy) return; resetRunUi(); setBusy(true);
  const key = 'run-' + (globalThis.crypto?.randomUUID?.() || Date.now() + '-' + Math.random().toString(36).slice(2));
  try {
    const response = await fetch('/api/executions', {method:'POST', headers:{'content-type':'application/json','Idempotency-Key':key},body:JSON.stringify({invoice_id:invoice||null})});
    const view = await response.json();
    if (!response.ok) throw new Error((view.error?.message || view.detail || 'Execution failed') + ' · request ' + (response.headers.get('X-Request-ID') || 'unknown'));
    for (const event of view.events || []) onEvent(event);
    await finishRun(view);
  } catch(e) {banner('bad', e.message + '. Inspect history before retrying an uncertain request.');}
  finally {setBusy(false);}
}
async function finishRun(v) {
  S.run = v; S.diag = v.diagnosis; S.sel = (v.halt && v.halt.step) || null;
  v.steps.forEach(s => { S.status[s.id] = s.status === "passed" ? (S.status[s.id] === "flagged" ? "flagged" : "passed") : s.status === "failed" ? "failed" : s.status === "skipped" ? "skipped" : "" });
  if (v.outcome === "halted" || v.outcome === "held") S.blocked = v.inputs.invoice_id;
  else if (v.outcome === "posted") S.blocked = null;
  $("#sOut").textContent = v.outcome.toUpperCase(); $("#sOut").className = v.outcome === "posted" ? "good" : v.outcome === "halted" ? "bad" : "amber";
  $("#sOracle").textContent = v.oracle_verdict; $("#sOracle").className = v.oracle_verdict === "silent_error" ? "bad" : v.oracle_verdict === "correct_post" || v.oracle_verdict === "correct_block" ? "good" : "amber";
  $("#sVer").textContent = v.manifest_version; $("#sRunCalls").textContent = v.model_calls; $("#sMs").textContent = v.duration_ms + " ms";
  const sch = v.steps.filter(s => s.kind === "mock_api").length;
  if (v.outcome === "posted" && v.oracle_verdict === "correct_post") banner("ok", `Output matches the independent oracle · ${v.model_calls} model calls during this replay`);
  else if (v.outcome === "posted") banner("bad", "SILENT ERROR: a wrong ledger entry was posted and nothing flagged it");
  else if (v.outcome === "halted" && v.halt.reason === "schema_invalid") banner("bad", `HALTED at ${v.halt.step}: provider response failed schema validation. No ledger entry was posted.`);
  else if (v.outcome === "halted") banner("bad", `HALTED before posting · ${sch} schema checks passed, but contract "${v.halt.contract}" failed at ${v.halt.step}`);
  else if (v.outcome === "held") banner("warn", "HELD for review: the entry was not posted because a magnitude invariant was violated (arithmetic still agrees)");
  else banner("warn", `Run ended: ${v.outcome}`);
  await refreshState(); paintStatus(); renderEvidence(); updateButtons();
  const ex = $("#bExport"); ex.hidden = false; ex.href = `/api/runs/${v.run_id}/export`;
}

/* ------------------------------------------------------------------ evidence */
function contractTable(list) {
  if (!list.length) return "";
  return `<table class="t"><tr><th style="width:38%">contract</th><th>expected</th><th>observed</th></tr>${list.map(c => `<tr><td><span class="tag2 ${c.ok ? "green" : c.severity === "critical" ? "red" : "amber"}">${c.ok ? "pass" : c.severity}</span> <code>${esc(c.id)}</code></td><td><code>${esc(typeof c.expected === "object" ? JSON.stringify(c.expected) : c.expected ?? "")}</code></td><td><code>${esc(clip(typeof c.observed === "object" ? JSON.stringify(c.observed) : c.observed ?? "", 80))}</code></td></tr>`).join("")}</table>`;
}
function renderEvidence() {
  const el = $("#evidence"), v = S.run; if (!v) { el.innerHTML = '<div class="empty">Select a step, or run something.</div>'; return }
  const parts = [];
  if (v.repair) parts.push(repairCard(v.repair));
  if (S.diag) parts.push(diagCard(S.diag));
  if (v.halt) parts.push(`<div class="card bad"><h4>Why it stopped</h4><div>${esc(v.halt.message || v.halt.reason)}</div>${v.halt.detail ? `<div class="kv"><span>schema</span><span><code>${esc(JSON.stringify(v.halt.detail))}</code></span></div>` : ""}</div>`);
  parts.push(rawCard(v));
  const failed = v.contract_results.filter(c => !c.ok);
  if (failed.length) parts.push(`<div class="card warn"><h4>Failed contracts</h4>${contractTable(failed)}</div>`);
  const sel = S.sel && v.steps.find(s => s.id === S.sel);
  if (sel) {
    const mc = v.contract_results.filter(c => c.step === sel.id);
    parts.push(`<div class="card"><h4>Step <code>${esc(sel.id)}</code> <span class="tag2">${esc(sel.operation)}</span> <span class="tag2 ${sel.status === "failed" ? "red" : sel.status === "passed" ? "green" : ""}">${esc(sel.status)}</span></h4>
      <div class="kv"><span>duration</span><span>${sel.duration_ms.toFixed(2)} ms</span><span>model calls</span><span>${sel.model_calls}</span><span>output hash</span><span><code>${esc(sel.output_hash || "–")}</code></span><span>output</span><span><code>${esc(sel.summary)}</code></span></div>${contractTable(mc)}</div>`);
  }
  if (v.oracle_verdict) parts.push(`<div class="card"><h4>Independent oracle</h4><div class="kv"><span>verdict</span><span>${esc(v.oracle_verdict)}</span><span>expected</span><span><code>${esc(JSON.stringify(v.expected))}</code></span><span>posted</span><span><code>${esc(JSON.stringify(v.outcome === "posted" ? v.ledger_entry : null))}</code></span></div><div class="dim">The oracle reads fixture truth only; it never calls the code under test.</div></div>`);
  el.innerHTML = parts.join("") || '<div class="empty">Nothing to show for this step.</div>';
  el.parentElement.scrollTop = 0;
}
function rawCard(v) {
  const rs = v.raw_samples || {}, inv = rs.fetch_invoice, pay = rs.fetch_payments;
  if (!inv || !pay || !Array.isArray(pay.payments)) return "";
  const norm = Array.isArray(rs.normalize_amount) ? rs.normalize_amount : [];
  const rows = pay.payments.map((p, i) => `<tr><td><code>${esc(p.payment_id)}</code></td><td><code>${esc(p.amount)}</code></td><td><code>${esc(norm[i] ?? "–")}</code></td></tr>`).join("");
  const res = rs.reconcile || {};
  const bad = v.contract_results.filter(c => !c.ok).map(c => c.id);
  return `<div class="card ${bad.length ? "warn" : ""}"><h4>Raw vs normalized</h4>
    <table class="t"><tr><th>payment</th><th>raw from provider</th><th>normalized USD</th></tr>${rows}</table>
    <div class="kv"><span>invoice.total (raw)</span><span><code>${esc(inv.total)}</code></span><span>sum of payments (normalized)</span><span><code>${esc(rs.sum_payments ?? "–")}</code></span><span>expected total</span><span><code>${esc(rs.expected_total ?? "–")}</code></span><span>residuals</span><span><code>${esc(JSON.stringify(res))}</code></span><span>failed invariant${bad.length === 1 ? "" : "s"}</span><span>${bad.length ? bad.map(b => `<code>${esc(b)}</code>`).join(" ") : "none"}</span></div>
    ${v.diagnosis && v.diagnosis.top ? `<div class="dim">suspect node: <b>${esc(v.diagnosis.top.step || v.diagnosis.top.op)}</b> (${esc(v.diagnosis.top.name)})</div>` : ""}</div>`;
}
function hardCard(h) {
  const rows = h.rows.map(r => `<tr><td><code>${esc(r.invoice_id)}</code></td><td><code>${esc(r.raw_invoice_total)}</code></td><td>$${esc(r.true_total_usd)}</td><td class="${r.arithmetic_ok && r.payment_match_ok ? "bad" : "good"}">${r.arithmetic_ok && r.payment_match_ok ? "both pass (blind)" : "caught"}</td><td>${r.magnitude_flagged ? "flagged" : "<span class=bad>not flagged</span>"}</td><td class="${r.oracle_verdict === "silent_error" ? "bad" : "good"}">${esc(r.outcome)}${r.oracle_verdict === "silent_error" ? " · WRONG" : ""}</td></tr>`).join("");
  return `<div class="card bad"><h4>The hard case: both sources scale together</h4><div>${esc(h.explanation)}</div>
   <div class="kv"><span>held for human review</span><span>${h.held}/${h.n}</span><span>posted wrong, silently</span><span class="bad">${h.posted_wrong}/${h.n}${h.posted_wrong ? "" : " in this sample (not zero in general: see Benchmark studio)"}</span><span>repair offered</span><span>no</span></div>
   <table class="t"><tr><th>invoice</th><th>raw total</th><th>true total</th><th>reconciliation</th><th>magnitude contract</th><th>outcome</th></tr>${rows}</table></div>`;
}
function diagCard(d) {
  const kind = d.status === "localized" ? "warn" : d.status === "business_exception" ? "ok" : "bad";
  return `<div class="card ${kind}"><h4>Diagnosis · <span class="tag2">${esc(d.status)}</span></h4><div>${esc(d.explanation || "")}</div>
    ${d.suspects.map((s, i) => `<div style="margin-top:8px"><b>${i + 1}. ${esc(s.name)}</b> <span class="dim">${esc(s.step || s.op || "no step")} · suspicion ${s.score}/${s.max_score}</span>
      <div class="bar"><div style="width:${100 * s.score / Math.max(1, s.max_score)}%"></div></div>
      ${s.features.map(f => `<div class="feat ${f.met ? "met" : ""}"><i>${f.met ? "✓" : "·"}</i><span>${esc(f.name)} <span class="dim">(+${f.weight}${f.detail ? " · " + esc(f.detail) : ""})</span></span></div>`).join("")}</div>`).join("")}
    <div class="dim" style="margin-top:6px">${esc(d.score_note)}</div></div>`;
}
function repairCard(r) {
  const ok = r.accepted;
  let h = `<div class="card ${ok ? "ok" : "bad"}"><h4>Repair · <span class="tag2 ${ok ? "green" : "red"}">${esc(r.decision)}</span></h4><div>${esc(r.reason || "")}</div>`;
  (r.proposals || []).forEach(p => {
    h += `<div style="margin-top:8px"><b>${esc(p.source)}</b> → ${esc(p.op)}.${esc(p.param)} <span class="tag2 ${p.status === "accepted" ? "green" : "red"}">${esc(p.status)}</span><div class="dim">${esc(p.rationale || "")}</div>`;
    if (p.problems) h += `<div class="bad">${esc(p.problems.join("; "))}</div>`;
    if (p.diff) h += p.diff.map(d => `<pre class="diff"><span class="del">- ${esc(JSON.stringify(d.param_before))}</span>\n<span class="add">+ ${esc(JSON.stringify(d.param_after))}</span></pre>`).join("");
    if (p.validation && p.validation.groups) {
      h += `<table class="t"><tr><th>validation set</th><th>passed</th><th>oracle mismatches</th></tr>${Object.entries(p.validation.groups).map(([k, g]) => `<tr><td>${esc(k)}</td><td class="${g.passed === g.n ? "good" : "bad"}">${g.passed}/${g.n}</td><td>${g.oracle_mismatches}/${g.oracle_checked}</td></tr>`).join("")}</table>
        <div class="dim">${p.validation.isolated ? "ran in a separate process with a scrubbed environment (no API keys)" : ""}</div>`;
      const f = Object.values(p.validation.groups).flatMap(g => g.failures || [])[0];
      if (f) h += `<div class="dim">first failure: ${esc(f.invoice_id)} → ${esc(f.outcome)} (${esc((f.failed_contracts || []).join(", "))})</div>`;
    }
    h += `</div>`;
  });
  if (r.guard_id) h += `<div style="margin-top:8px">Regression guard saved: <code>${esc(r.guard_id)}</code> · version ${esc(r.candidate_version)}</div>`;
  if (r.repair_model_calls) h += `<div class="dim">repair model calls: ${r.repair_model_calls}</div>`;
  return h + "</div>";
}

/* ------------------------------------------------------------------ actions */
async function refreshState() {
  S.state = await api("GET", "/api/state");
  const w = S.state.workflow; $("#wfTag").textContent = `${w.id} · v${w.version} · ${S.state.compile_mode} plan`;
  const m = S.state.meter; $("#calls").textContent = `model calls: compile ${m.compile_model_calls} · replay ${m.replay_model_calls} · repair ${m.repair_model_calls}`;
  $("#compileNote").textContent = `${w.meta.plan_source || ""} · ${w.contracts.length} contracts (${w.contracts.filter(c => c.kind === "mined").length} mined from ${w.meta.mined_from_golden_runs} golden runs)`;
  if (!S.nodes.fetch_invoice || Object.keys(S.nodes).length !== w.steps.length) drawGraph();
  else { document.querySelectorAll(".node").forEach((g, i) => { const s = w.steps[i]; if (s) g.querySelector(".sub").textContent = s.operation + (Object.keys(s.params || {}).length ? " ·params" : "") }) }
}
async function act(fn) { try { setBusy(true); await fn() } catch (e) { banner("bad", e.message) } finally { setBusy(false) } }
$("#bCompile").onclick = () => act(async () => { const r = await api("POST", "/api/lab/compile", { use_model: false }); await refreshState(); banner("ok", `Compiled ${r.version}: ${r.report.contracts.length} contracts attached. Replay path takes no model client.`) });
$("#bCompileM").onclick = () => act(async () => { const r = await api("POST", "/api/lab/compile", { use_model: true }); await refreshState(); banner(r.report.rejections.length ? "warn" : "ok", `Plan source: ${r.report.plan_source}${r.report.rejections.length ? " · " + r.report.rejections.length + " rejection(s), see compile note" : ""}`); $("#compileNote").textContent += " · " + JSON.stringify(r.report.rejections).slice(0, 200) });
$("#bHard").onclick = () => act(async () => { const h = await api("POST", "/api/lab/hard-case?n=10"); await refreshState(); $("#evidence").innerHTML = hardCard(h); banner("bad", `Hard case: ${h.posted_wrong} of ${h.n} posted wrong silently, ${h.held} held for a human. No automatic repair.`) });
$("#bRun").onclick = () => streamRun(null);
$("#bRetry").onclick = () => streamRun(S.blocked);
$("#bInject").onclick = () => act(async () => { const r = await api("POST", "/api/lab/inject", { scenario: $("#scn").value }); await refreshState(); banner("warn", `Provider behaviour: ${r.title}. Now run an invoice.`) });
$("#bDiag").onclick = () => act(async () => { S.diag = await api("POST", `/api/runs/${S.run.run_id}/diagnose`); const t = S.diag.top; S.suspect = t && t.step; S.sel = S.suspect || S.sel; S.run.diagnosis = S.diag; paintStatus(); renderEvidence() });
async function doRepair(mode) {
  await act(async () => {
    if (mode === 'model') {
      const proposal = await api('POST', `/api/runs/${S.run.run_id}/propose-model`);
      showProposal(proposal); banner('warn', S.identity?.profile==='enterprise'?'Model proposal validated. A different reviewer must approve it.':'Inspect the validated proposal before approval.'); return;
    }
    const r = await api("POST", `/api/runs/${S.run.run_id}/repair`, { mode }); S.run.repair = r; await refreshState();
    banner(r.accepted ? "ok" : "bad", r.accepted ? `Repair accepted → workflow v${r.candidate_version}. Retry the blocked invoice.` : `Repair rejected: ${r.reason}`);
    renderEvidence();
  });
}
$("#bRepair").onclick = () => doRepair("auto"); $("#bWrong").onclick = () => doRepair("wrong"); $("#bRepairM").onclick = () => doRepair("model");
$("#bReset").onclick = () => act(async () => { await api("POST", "/api/lab/reset"); S.run = S.diag = S.blocked = null; S.status = {}; S.suspect = null; S.sel = null; $("#timeline").innerHTML = '<div class="empty">No run yet.</div>'; $("#evidence").innerHTML = '<div class="empty">Select a step, or run something.</div>'; $("#bExport").hidden = true; await refreshState(); drawGraph(); banner("neutral", "Lab reset.") });
$("#scn").onchange = () => { const s = S.meta.scenarios.find(x => x.id === $("#scn").value); $("#scnDesc").textContent = s.desc + (s.repairable ? "" : " (no automated repair exists for this case)") };

/* ------------------------------------------------------------------ benchmark studio */
function wilson(k, n) { if (!n) return [0, 1]; const z = 1.96, p = k / n, d = 1 + z * z / n, c = (p + z * z / (2 * n)) / d, h = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return [Math.max(0, c - h), Math.min(1, c + h)] }
const pct = x => x == null ? "–" : (100 * x).toFixed(1) + "%";
const NAMES = { agent_every_run: "Repeated agent reasoning", naive_replay: "Naive replay", schema_only: "Schema-only replay", fixed_audit_10: "Fixed audit (every 10)", fixed_audit_25: "Fixed audit (every 25)", jitd_guarded: "JIT-D guarded replay" };
const kn = o => o ? `${o.k}/${o.n}<small>Descriptive run counts; not independent trials</small>` : "–";
function chart(points) {
  const W = 640, H = 300, L = 56, B = 40, T = 14, R = 20, maxX = Math.max(...points.map(p => p.x)) * 1.15 || 1;
  const X = v => L + v / maxX * (W - L - R), Y = v => T + (1 - v) * (H - T - B);
  let s = `<svg viewBox="0 0 ${W} ${H}" style="height:auto;max-width:720px" role="img" aria-label="Estimated cost per run versus silent error rate">`;
  for (let i = 0; i <= 4; i++) { const v = i / 4; s += `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="#d7e3de"/><text x="${L - 8}" y="${Y(v) + 4}" fill="#5d7068" font-size="10" text-anchor="end" font-family="monospace">${(v * 100).toFixed(0)}%</text>` }
  s += `<text x="${(L + W) / 2}" y="${H - 6}" fill="#5d7068" font-size="11" text-anchor="middle">estimated model cost per run (USD, ASSUMED prices)</text><text transform="rotate(-90)" x="${-H / 2}" y="14" fill="#5d7068" font-size="11" text-anchor="middle">silent-error rate</text>`;
  const used = [];
  points.forEach(p => {
    const [lo, hi] = wilson(p.k, p.n), dy = used.filter(u => Math.abs(u.x - p.x) < maxX * .05 && Math.abs(u.y - p.k / p.n) < .06).length * 14; used.push({ x: p.x, y: p.k / p.n });
    const col = p.id === "jitd_guarded" ? "#116466" : "#D9B08C";
    s += `<line x1="${X(p.x)}" x2="${X(p.x)}" y1="${Y(lo)}" y2="${Y(hi)}" stroke="${col}" opacity=".6"/><circle cx="${X(p.x)}" cy="${Y(p.k / p.n)}" r="6" fill="${col}"/>
      <text x="${X(p.x) + (p.x > maxX * .6 ? -10 : 10)}" y="${Y(p.k / p.n) - 8 + dy}" fill="#2C3531" font-size="10.5" text-anchor="${p.x > maxX * .6 ? "end" : "start"}">${esc(NAMES[p.id])} (${p.k}/${p.n})</text>`;
  });
  return s + "</svg>";
}
async function loadBench() {
  const el = $("#bench"); el.innerHTML = "<section><p>Loading…</p></section>";
  const list = (await api("GET", "/api/benchmarks")).benchmarks;
  if (!list.length) { el.innerHTML = '<section><div class="warnbox">No benchmark results saved. Run <code>python -m jitd.bench</code>.</div></section>'; return }
  const d = await api("GET", "/api/benchmarks/" + list[0].id), m = d.meta, cells = d.cells;
  const sc = m.scenarios, drift = Object.keys(sc).filter(k => sc[k].kind !== "benign");
  const pts = m.strategies.map(st => {
    const cs = cells.filter(c => c.strategy === st && drift.includes(c.scenario));
    return { id: st, k: cs.reduce((a, c) => a + c.silent_error_rate.k, 0), n: cs.reduce((a, c) => a + c.silent_error_rate.n, 0), x: cs.reduce((a, c) => a + c.est_cost_usd_per_run, 0) / cs.length };
  });
  let rows = ""; Object.keys(sc).forEach(k => {
    rows += `<tr class="grp"><td colspan="7">${esc(sc[k].title)} <span class="tag2">${esc(sc[k].kind)}</span> <span class="tag2">${esc(sc[k].split)}</span>${sc[k].split === "external" ? `<span class="tag2 ${sc[k].independent ? "green" : "amber"}">${sc[k].independent ? "independent author" : "NOT independent: " + esc(sc[k].author)}</span>` : ""}</td></tr>`;
    m.strategies.forEach(st => { const c = cells.find(x => x.scenario === k && x.strategy === st); if (!c) return;
      rows += `<tr><td>${esc(NAMES[st])}</td><td class="${c.silent_error_rate.k ? "bad" : "good"}">${kn(c.silent_error_rate)}</td><td>${kn(c.detection_rate)}</td><td class="${c.false_block_rate && c.false_block_rate.k ? "amber" : ""}">${kn(c.false_block_rate)}</td><td>${c.model_calls_per_run}</td><td>${c.latency_ms_median_measured ?? "modelled"}</td><td>${c.localized_correctly ? `loc ${c.localized_correctly.k}/${c.localized_correctly.n}` : ""}${c.repair ? ` · repair ${c.repair.accepted}/${c.repair.attempted}` : ""}</td></tr>` });
  });
  const jc = cells.filter(c => c.strategy === "jitd_guarded");
  const weak = jc.filter(c => (c.silent_error_rate.k > 0) || (c.false_block_rate && c.false_block_rate.k / c.false_block_rate.n > 0.05)).map(c => {
    const fb = c.false_block_rate, se = c.silent_error_rate, bad = se.k > 0 ? "silent" : "false-block";
    return `<tr><td>${esc(sc[c.scenario].title)} <span class="tag2">${esc(sc[c.scenario].split)}</span></td><td class="bad">${bad === "silent" ? "posts wrong, silently" : "blocks runs that were fine"}</td><td>${bad === "silent" ? kn(se) : kn(fb)}</td></tr>`; }).join("");
  el.innerHTML = `<section><h2>Benchmark studio</h2><p>${esc(m.seeds)} seeded streams × ${esc(m.runs_per_stream)} runs per scenario and strategy · ${esc(m.mode)} · code ${esc(m.code_version)} · ${esc(m.started_utc)} · <a class="link" href="/api/benchmarks/${d.id}/csv">CSV</a></p>
    <div class="warnbox"><b>Read this first.</b> ${m.caveats.map(esc).join(" ")}</div>
    <div class="warnbox"><h2>Where JIT-D is weak (read before the chart)</h2><table class="bt"><tr><th>Scenario</th><th>Failure</th><th>Rate (k/n, 95% CI)</th></tr>${weak || "<tr><td colspan=3>none above threshold</td></tr>"}</table><p>Only scenarios with any silent error or a false-block rate above 5% are listed. Each is a real limitation, not noise. Raw per-trial outputs for JIT-D and naive replay are saved next to the result file (<code>*.trials.jsonl.gz</code>).</p></div>
    <h2>Cost vs silent errors (all non-benign scenarios pooled)</h2><p>Each point is a strategy; whiskers are 95% Wilson intervals. JIT-D's false blocks are not in this chart: see the table (for example, legitimately huge invoices are held for review). Cost uses assumed token counts and prices (${esc(JSON.stringify({ in: m.assumptions.agent_tokens_in, out: m.assumptions.agent_tokens_out, usd_per_M_in: m.assumptions.price_in_usd_per_m_tokens, usd_per_M_out: m.assumptions.price_out_usd_per_m_tokens }))}).</p>${chart(pts)}</section>
    <section><h2>Every scenario, every strategy</h2><p>Silent error = a wrong entry was posted. Detection = share of runs needing protection that were handled (recovered or correctly blocked). False block = a run that needed no protection was halted or held. <b>dev</b> scenarios were used while building contracts and hypotheses; <b>heldout</b> were evaluated afterwards without changing thresholds.</p>
    <table class="bt"><tr><th>Strategy</th><th>Silent errors</th><th>Detection</th><th>False blocks</th><th>Model calls / run</th><th>Median ms (measured)</th><th>JIT-D episodes</th></tr>${rows}</table></section>`;
}
$("#tabA").onclick = () => { $("#console").style.display = "grid"; $("#strip").style.display = "grid"; $("#bench").hidden = true; $("#tabA").classList.add("on"); $("#tabB").classList.remove("on") };
$("#tabB").onclick = () => { $("#console").style.display = "none"; $("#strip").style.display = "none"; $("#bench").hidden = false; $("#tabB").classList.add("on"); $("#tabA").classList.remove("on"); loadBench().catch(e => { $("#bench").innerHTML = `<section><div class="warnbox">${esc(e.message)}</div></section>` }) };

async function init() {
  S.identity = await api('GET','/api/platform/me');
  if(S.identity.profile === 'enterprise') {
    $('#bHard').hidden=true; $('#bWrong').hidden=true; $('#bRepairM').textContent='Propose repair with Nemotron';
    document.querySelector('.nav-status').textContent=S.identity.name+' · '+S.identity.role;
  }
  S.meta = await api("GET", "/api/meta");
  const m = $("#mode"); m.textContent = S.meta.mode; m.className = "chip mode " + (S.meta.model_configured ? "live" : "sim");
  m.title = S.meta.model_configured ? "Nebius model: " + S.meta.model : "Provider data is simulated. No Nebius model is configured on this server.";
  $("#scn").innerHTML = S.meta.scenarios.map(s => `<option value="${s.id}">${esc(s.title)}</option>`).join(""); $("#scn").onchange();
  await refreshState(); drawGraph(); updateButtons();
}
init().catch(e => { banner("bad", "Failed to load: " + e.message) });
