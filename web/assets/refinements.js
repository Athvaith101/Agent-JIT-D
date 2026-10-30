"use strict";
(()=>{
 const isStudio=!!document.querySelector('.app-nav .brand-dot'), isBuilder=!!document.querySelector('.builder-nav');
 const footer=document.createElement('footer');footer.className='jd-footer';footer.innerHTML='<div><strong>JIT-D</strong><p>Reason once. Verify what matters. Recover cheaply.</p></div><nav aria-label="Footer navigation"><a href="/">Home</a><a href="/builder">Builder</a><a href="/studio">Studio</a><a href="/operations">System & access</a></nav>';
 const existing=document.querySelector('footer');if(existing&&document.querySelector('.builder-nav')){existing.remove();document.querySelector('body>.shell').append(footer)}else if(!existing)(document.querySelector('.app-body')||document.querySelector('body>.shell')||document.body).append(footer);
 document.querySelectorAll('.primary-nav,.builder-nav,.nav-links').forEach(nav=>{
 const indicator=document.createElement('span');indicator.className='jd-nav-fluid';indicator.setAttribute('aria-hidden','true');nav.prepend(indicator);
 const items=[...nav.querySelectorAll('button,a')];let hovered=null;
 function move(item){if(!item){indicator.style.opacity='0';return}const a=item.getBoundingClientRect(),b=nav.getBoundingClientRect();indicator.style.width=a.width+'px';indicator.style.height=a.height+'px';indicator.style.transform=`translate(${a.left-b.left+nav.scrollLeft}px,${a.top-b.top+nav.scrollTop}px)`;indicator.style.opacity='1'}
 function restore(){hovered=null;move(items.find(e=>e.matches('.on,.active')))}
 items.forEach(item=>{item.addEventListener('pointerenter',()=>{hovered=item;move(item)});item.addEventListener('focus',()=>move(item));item.addEventListener('blur',restore)});nav.addEventListener('pointerleave',restore);nav.addEventListener('focusout',e=>{if(!nav.contains(e.relatedTarget))restore()});
 new MutationObserver(()=>move(hovered||items.find(e=>e.matches('.on,.active')))).observe(nav,{subtree:true,attributes:true,attributeFilter:['class']});new ResizeObserver(restore).observe(nav);restore();
 });
 if(!isStudio&&!isBuilder)return;
 const steps=isBuilder?[
 ['Choose a starting point','Select a template or use “Start from a sentence” to describe the task. Drafting with a model requires a connection in Models & keys.'],
 ['Arrange the workflow','Add typed blocks, connect their inputs, and inspect each block’s settings. Keep required verification steps in the workflow.'],
 ['Test before publishing','Open Test & operate, supply sample JSON, and inspect the result and its checks. Fix missing inputs or failed checks before publishing.'],
 ['Inspect model use','Cost evidence shows recorded model calls and token usage. Connecting a key does not itself draft or diagnose a workflow.'],
 ['Enable assistance deliberately','Use Hybrid assurance to review the controller policy before enabling model assistance. Keep the call budget appropriate for your project.']
 ]:[
 ['Build your first agent','Use Build to create an invoice reconciliation agent. Inspect its draft and required evidence before continuing.'],
 ['Test the draft','Open Test and inspect the result and validation evidence. A passing example helps you review the draft before publication.'],
 ['Review a version','Use Versions & review to inspect and publish a validated version. Check the changes before approving them.'],
 ['Run and demonstrate recovery','Open Runs & recovery to run the workflow and try a drift scenario. Inspect the failed evidence, validate the proposed repair, review it, then retry.'],
 ['Check actual model usage','Open Cost & model usage for recorded calls and receipts. Model drafting and repair need a configured key; displayed projections are estimates.']
 ];
 const dialog=document.createElement('section');dialog.className='jd-guide';dialog.setAttribute('aria-labelledby','jd-guide-title');dialog.hidden=true;dialog.innerHTML='<div class="jd-guide-head"><div><small>JIT-D / QUICK START</small><h2 id="jd-guide-title">'+(isBuilder?'Your first visual workflow':'Welcome to Agent Studio')+'</h2><p>A short guide to your first complete run.</p></div><button class="jd-guide-close" aria-label="Close user guide"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg></button></div><ol>'+steps.map(([title,body])=>'<li><strong>'+title+'</strong><p>'+body+'</p></li>').join('')+'</ol><div class="jd-guide-note">This workspace demonstrates bounded workflows with synthetic services or supplied data. Inspect the evidence and model receipts for each run.</div><div class="jd-guide-bottom"><span>Reopen this anytime using User guide.</span><button class="jd-guide-done">Start exploring ↗</button></div>';document.body.append(dialog);
 const trigger=document.createElement('button');trigger.className='jd-guide-trigger';trigger.textContent='User guide';trigger.setAttribute('aria-expanded','false');trigger.setAttribute('aria-controls','jd-guide');dialog.id='jd-guide';
 const launch=document.createElement('div');launch.className='jd-guide-launch';launch.append(trigger);const container=document.querySelector('.app-body')||document.querySelector('body>.shell');container.querySelector('header').append(trigger);launch.remove();container.querySelector('header').after(dialog);
 const key='jitd-guide-glass-v1-'+(isBuilder?'builder':'studio');let returnFocus=null;
 function open(){if(!dialog.hidden)return;returnFocus=document.activeElement;dialog.hidden=false;trigger.setAttribute('aria-expanded','true')}
 function dismiss(){dialog.hidden=true;trigger.setAttribute('aria-expanded','false');try{localStorage.setItem(key,'seen')}catch{}if(returnFocus instanceof HTMLElement&&returnFocus!==document.body)returnFocus.focus();else trigger.focus()}
 trigger.addEventListener('click',open);dialog.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();dismiss()}});dialog.querySelector('.jd-guide-close').addEventListener('click',dismiss);dialog.querySelector('.jd-guide-done').addEventListener('click',dismiss);dialog.addEventListener('cancel',e=>{e.preventDefault();dismiss()});
 let seen=false;try{seen=localStorage.getItem(key)==='seen'}catch{seen=true}if(!seen)open();
})();
