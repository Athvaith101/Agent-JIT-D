'use strict';
(()=>{
 const clock=()=>{const value=new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kolkata'}).format(new Date())+' in India';document.querySelectorAll('[data-clock]').forEach(e=>e.textContent=value);};clock();const timer=setInterval(clock,30000);
 const toggle=document.querySelector('#menuToggle'),menu=document.querySelector('#mobileMenu'),close=document.querySelector('#closeMenu');let lastFocus;
 function setMenu(open){if(open){lastFocus=document.activeElement;menu.hidden=false;document.body.style.overflow='hidden';requestAnimationFrame(()=>menu.classList.add('open'));close.focus();}else{menu.classList.remove('open');menu.hidden=true;document.body.style.overflow='';lastFocus?.focus();}toggle.setAttribute('aria-expanded',String(open));}
 toggle.onclick=()=>setMenu(menu.hidden);close.onclick=()=>setMenu(false);document.querySelector('.menu-backdrop').onclick=()=>setMenu(false);menu.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>setMenu(false)));
 document.addEventListener('keydown',e=>{if(menu.hidden)return;if(e.key==='Escape'){e.preventDefault();setMenu(false);}if(e.key==='Tab'){const items=[close,...menu.querySelectorAll('a')],first=items[0],last=items.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
 window.addEventListener('resize',()=>{if(innerWidth>800&&!menu.hidden)setMenu(false);});
 const canvas=document.querySelector('#fluid'),art=document.querySelector('.hero-art');const reduced=matchMedia('(prefers-reduced-motion: reduce)');let raf=0,visible=true,last=-Infinity,lost=false;const gl=canvas.getContext('webgl',{alpha:false,antialias:false,powerPreference:'low-power'});if(!gl)return;
 const vertex='attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';
 const fragment=`precision mediump float;uniform vec2 resolution;uniform float time;uniform vec2 pointer;
 float grain(vec2 p){return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453);}
 void main(){vec2 uv=gl_FragCoord.xy/resolution;float t=time*.13;vec2 p=uv;
 float ripple=exp(-distance(uv,pointer)*7.0);
 float ridges=sin((uv.x+uv.y*.43)*96.0+.4*sin(t)+ripple*1.7);
 p.x+=.023*ridges;p.y+=.01*cos(uv.x*83.0);
 vec2 q=p-(vec2(.77,.61)+(pointer-vec2(.5))*.12);q.x*=resolution.x/resolution.y;
 float r=length(q);float a=atan(q.y,q.x)+1.6*exp(-r*2.0)+.13*sin(t);
 vec2 swirl=vec2(cos(a),sin(a))*r;
 vec2 c=swirl-vec2(.06*sin(t),.05*cos(t));
 float bloom=exp(-dot(c*vec2(1.0,1.45),c*vec2(1.0,1.45))*5.0);
 float wave=.5+.5*sin(4.5*a+9.*r-t);float mask=bloom*(.65+.35*wave);
 mask*=smoothstep(.34,.72,uv.x);vec3 orange=vec3(1.,.365,.055);
 vec3 color=mix(vec3(.938),orange,clamp(mask*.93,0.,1.));
 float glass=.035*ridges+.025*sin((uv.x+uv.y*.43)*96.0+1.2);
 color+=glass*mix(.3,1.,bloom);color+=vec3((grain(gl_FragCoord.xy)-.5)*.024);
 gl_FragColor=vec4(clamp(color,0.,1.),1.);}`;
 function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)){gl.deleteShader(s);return null;}return s;}
 const vs=shader(gl.VERTEX_SHADER,vertex),fs=shader(gl.FRAGMENT_SHADER,fragment);if(!vs||!fs)return;const program=gl.createProgram();gl.attachShader(program,vs);gl.attachShader(program,fs);gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))return;gl.useProgram(program);
 const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);const position=gl.getAttribLocation(program,'p');gl.enableVertexAttribArray(position);gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);const size=gl.getUniformLocation(program,'resolution'),time=gl.getUniformLocation(program,'time'),pointer=gl.getUniformLocation(program,'pointer');let targetX=.5,targetY=.5,currentX=.5,currentY=.5;const fine=matchMedia('(hover: hover) and (pointer: fine)');const hero=document.querySelector('.hero');hero.addEventListener('pointermove',e=>{if(!fine.matches||reduced.matches)return;const rect=hero.getBoundingClientRect();targetX=Math.max(0,Math.min(1,(e.clientX-rect.left)/rect.width));targetY=1-Math.max(0,Math.min(1,(e.clientY-rect.top)/rect.height));},{passive:true});hero.addEventListener('pointerleave',()=>{targetX=targetY=.5;});
 function resize(){const rect=canvas.getBoundingClientRect(),scale=Math.min(devicePixelRatio||1,1.25)*.8;canvas.width=Math.max(1,Math.round(rect.width*scale));canvas.height=Math.max(1,Math.round(rect.height*scale));gl.viewport(0,0,canvas.width,canvas.height);gl.uniform2f(size,canvas.width,canvas.height);}
 function draw(ms){raf=0;if(lost||document.hidden||!visible)return;if(ms-last>=1000/(fine.matches?24:18)||reduced.matches){last=ms;currentX+=(targetX-currentX)*.15;currentY+=(targetY-currentY)*.15;gl.uniform2f(pointer,reduced.matches ? .5 : currentX,reduced.matches ? .5 : currentY);gl.uniform1f(time,reduced.matches?0:ms/1000);gl.drawArrays(gl.TRIANGLES,0,6);art.classList.add('ready');}if(!reduced.matches)raf=requestAnimationFrame(draw);}
 function start(){if(!raf&&!lost&&visible&&!document.hidden)raf=requestAnimationFrame(draw);}
 resize();start();window.addEventListener('resize',()=>{resize();start();});document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(raf);raf=0;}else start();});const observer=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible)start();else{cancelAnimationFrame(raf);raf=0;}},{threshold:0});observer.observe(canvas);reduced.addEventListener('change',()=>{cancelAnimationFrame(raf);raf=0;start();});canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();lost=true;cancelAnimationFrame(raf);art.classList.remove('ready');});window.addEventListener('pagehide',()=>{clearInterval(timer);cancelAnimationFrame(raf);observer.disconnect();});
})();
