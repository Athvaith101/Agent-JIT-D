'use strict';
(()=>{
 const reduced=matchMedia('(prefers-reduced-motion: reduce)'),fine=matchMedia('(hover: hover) and (pointer: fine)');let frame=0,latest=null,card=null,button=null;
 const eligible=()=>!reduced.matches&&fine.matches;
 function reset(){if(card){card.classList.remove('pointer-lit');card.style.removeProperty('--tilt-x');card.style.removeProperty('--tilt-y');card=null;}if(button){button.style.removeProperty('--magnet-x');button.style.removeProperty('--magnet-y');button=null;}}
 function update(){frame=0;if(!eligible()||!latest)return;const e=latest;
  const target=e.target instanceof Element?e.target:null;if(!target)return;
  const next=target.closest('.workspace-preview,.receipt-art,.process-art,.panel,.metric,.review-card');
  if(next!==card){if(card){card.classList.remove('pointer-lit');card.style.removeProperty('--tilt-x');card.style.removeProperty('--tilt-y');}card=next;}
  if(card){const box=card.getBoundingClientRect(),x=e.clientX-box.left,y=e.clientY-box.top;card.style.setProperty('--pointer-x',x+'px');card.style.setProperty('--pointer-y',y+'px');if(card.matches('.workspace-preview,.receipt-art,.process-art')){card.style.setProperty('--tilt-x',((.5-y/box.height)*3).toFixed(2)+'deg');card.style.setProperty('--tilt-y',((x/box.width-.5)*3).toFixed(2)+'deg');}}
  const nextButton=target.closest('.roll-button');if(nextButton!==button&&button){button.style.removeProperty('--magnet-x');button.style.removeProperty('--magnet-y');}button=nextButton;if(button){const b=button.getBoundingClientRect();button.style.setProperty('--magnet-x',((e.clientX-b.left-b.width/2)*.035).toFixed(2)+'px');button.style.setProperty('--magnet-y',((e.clientY-b.top-b.height/2)*.07).toFixed(2)+'px');}
  const hero=target.closest('.hero');if(hero){const b=hero.getBoundingClientRect();hero.style.setProperty('--fallback-x',((e.clientX-b.left)/b.width*12-6).toFixed(1)+'px');hero.style.setProperty('--fallback-y',((e.clientY-b.top)/b.height*12-6).toFixed(1)+'px');}
 }
 document.addEventListener('pointermove',e=>{if(!eligible()||e.buttons)return;latest=e;if(!frame)frame=requestAnimationFrame(update);},{passive:true});document.documentElement.addEventListener('pointerleave',reset);document.addEventListener('dragstart',reset);document.addEventListener('visibilitychange',()=>{if(document.hidden)reset();});window.addEventListener('blur',reset);reduced.addEventListener('change',reset);fine.addEventListener('change',reset);
 // Only editorial sections reveal; interactive forms and workflow nodes never move.
 const items=[...document.querySelectorAll('.about .section-tag,.about h2,.about-grid>* , .workspaces .heading-row,.workspace-grid>article,.scope-strip')];
 let observer;
 if(!reduced.matches&&'IntersectionObserver'in window){observer=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){e.target.classList.add('in-view');observer.unobserve(e.target);}},{threshold:.08});for(const [i,item]of items.entries()){item.classList.add('scroll-reveal');item.style.setProperty('--reveal-delay',(i%3)*50+'ms');observer.observe(item);}}
 reduced.addEventListener('change',()=>{if(reduced.matches){observer?.disconnect();items.forEach(e=>e.classList.add('in-view'));}});
 window.addEventListener('pagehide',()=>{cancelAnimationFrame(frame);observer?.disconnect();reset();});
})();
