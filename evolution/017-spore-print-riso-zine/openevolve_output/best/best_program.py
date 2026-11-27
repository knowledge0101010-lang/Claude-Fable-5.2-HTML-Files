"""Evolved candidate for 017-spore-print-riso-zine — built from scratch against its spec."""
# EVOLVE-BLOCK-START
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spore Print — A Two-Colour Riso Zine</title>
<style>
:root{--paper:#f4efe2;--pink:#ff48b0;--teal:#00838a;--ink:#3b2f5c}
html,body{margin:0;height:100%;overflow:hidden;background:var(--paper);color:var(--ink);
font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace}
#zine{display:block;width:100vw;height:100vh;touch-action:none;cursor:crosshair}
#ink{position:fixed;inset:0;width:100%;height:100%;pointer-events:none;
opacity:.55;mix-blend-mode:multiply}
.hint{position:fixed;left:14px;bottom:12px;margin:0;font-size:10px;letter-spacing:.14em;
text-transform:uppercase;opacity:.62;pointer-events:none}
</style>
</head>
<body>
<svg id="zine" viewBox="0 0 1000 1000" preserveAspectRatio="xMidYMid slice" role="img"
 aria-label="Riso-print spore print: pink and teal spores radiating from a violet mushroom cap on cream paper">
<defs>
<filter id="grain" x="-15%" y="-15%" width="130%" height="130%">
<feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="3" seed="11" result="n"/>
<feDisplacementMap in="SourceGraphic" in2="n" scale="7" xChannelSelector="R" yChannelSelector="G"/>
</filter>
<filter id="fibre" x="0" y="0" width="100%" height="100%">
<feTurbulence type="fractalNoise" baseFrequency="0.7" numOctaves="4" seed="5"/>
<feColorMatrix values="0 0 0 0 0.23 0 0 0 0 0.18 0 0 0 0 0.36 0 0 0 0.16 0"/>
</filter>
<radialGradient id="pinkhalo">
<stop offset="0" stop-color="#ff48b0" stop-opacity=".5"/>
<stop offset="1" stop-color="#ff48b0" stop-opacity="0"/>
</radialGradient>
</defs>
<rect width="1000" height="1000" fill="#f4efe2"/>
<circle id="halo" cx="500" cy="500" r="360" fill="url(#pinkhalo)"/>
<g id="spores" filter="url(#grain)" style="mix-blend-mode:multiply"></g>
<g id="cap" style="mix-blend-mode:multiply"></g>
<rect width="1000" height="1000" filter="url(#fibre)" opacity=".55" pointer-events="none"/>
</svg>
<canvas id="ink" aria-hidden="true"></canvas>
<p class="hint">Drag to drift · ← → rotate · ↑ ↓ density · Space reroll · R reset</p>
<script>
(function(){
"use strict";
const NS='http://www.w3.org/2000/svg';
const svg=document.getElementById('zine');
const gSpores=document.getElementById('spores');
const gCap=document.getElementById('cap');
const halo=document.getElementById('halo');
const reduce=matchMedia('(prefers-reduced-motion: reduce)');
const PINK='#ff48b0',TEAL='#00838a',INK='#3b2f5c',INKS=[PINK,TEAL,INK];
const st={cx:500,cy:500,rot:0,dens:26,seed:7.31,salt:0};
let raf=0,t0=0;

function rng(){st.seed=(st.seed*16807)%2147483647;return st.seed/2147483647;}
function el(n,a){const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);return e;}

/* riso misregistration speckle drawn on a real canvas plane (static, so
   prefers-reduced-motion is satisfied without a second code path) */
const cv=document.getElementById('ink'),ctx=cv.getContext('2d');
const INKS_3=[PINK,TEAL,INK];
function speckle(){
  const dpr=Math.min(2,window.devicePixelRatio||1);
  const w=Math.max(1,window.innerWidth),h=Math.max(1,window.innerHeight);
  cv.width=Math.round(w*dpr);cv.height=Math.round(h*dpr);
  ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
  let s=(Math.round(Math.abs(st.seed))+17)%2147483647;
  const n=Math.min(2400,Math.round(w*h/1100));
  for(let i=0;i<n;i++){
    s=(s*16807)%2147483647;const a=s/2147483647;
    s=(s*16807)%2147483647;const b=s/2147483647;
    s=(s*16807)%2147483647;const k=s/2147483647;
    ctx.globalAlpha=0.05+k*0.12;
    ctx.fillStyle=INKS_3[(a*3)|0];
    ctx.beginPath();ctx.arc(a*w,b*h,0.4+b*1.6,0,6.2832);ctx.fill();
  }
  ctx.globalAlpha=1;
}

function build(){
  st.seed=Math.round(st.rot*97+st.dens*131+st.cx*7+st.cy*13+st.salt*1013)||3.7;
  gSpores.textContent='';gCap.textContent='';
  halo.setAttribute('cx',st.cx);halo.setAttribute('cy',st.cy);
  const N=760,R=420*(0.7+st.dens/90),frag=document.createDocumentFragment();
  for(let i=0;i<N;i++){
    const a=i*2.39996+st.rot*2;
    const rad=26+Math.pow(i/N,0.62)*R*(0.62+rng()*0.7);
    const x=st.cx+Math.cos(a)*rad,y=st.cy+Math.sin(a)*rad*0.94;
    const ink=INKS[rng()>0.72?2:(i%2)];
    frag.appendChild(el('circle',{cx:x.toFixed(1),cy:y.toFixed(1),
      r:(1.1+rng()*4.6).toFixed(2),fill:ink,opacity:(0.16+rng()*0.62).toFixed(2)}));
  }
  gSpores.appendChild(frag);
  gCap.appendChild(el('ellipse',{cx:st.cx,cy:st.cy-6,rx:62,ry:44,fill:INK,opacity:.92}));
  gCap.appendChild(el('ellipse',{cx:st.cx-18,cy:st.cy-24,rx:26,ry:14,fill:PINK,opacity:.55}));
  gCap.appendChild(el('rect',{x:st.cx-9,y:st.cy+28,width:18,height:74,rx:9,fill:TEAL,opacity:.85}));
  gCap.appendChild(el('ellipse',{cx:st.cx,cy:st.cy+30,rx:34,ry:9,fill:INK,opacity:.5}));
  gSpores.setAttribute('transform','rotate('+(st.rot*57.2958).toFixed(2)+' '+st.cx+' '+st.cy+')');
}

function frame(t){
  if(!t0)t0=t;
  const dt=Math.min(64,t-t0);t0=t;
  if(!reduce.matches){
    st.rot+=dt*0.00009;
    gSpores.setAttribute('transform','rotate('+(st.rot*57.2958).toFixed(2)+' '+st.cx+' '+st.cy+')');
  }
  raf=requestAnimationFrame(frame);
}

build();speckle();
let rt=0;
addEventListener('resize',function(){clearTimeout(rt);rt=setTimeout(speckle,120);});
if(!reduce.matches)raf=requestAnimationFrame(frame);
reduce.addEventListener('change',function(){
  if(reduce.matches){cancelAnimationFrame(raf);raf=0;}
  else if(!raf){t0=0;raf=requestAnimationFrame(frame);}
});

let drag=false,px=0,py=0;
svg.addEventListener('pointerdown',function(e){
  drag=true;px=e.clientX;py=e.clientY;
  if(svg.setPointerCapture)svg.setPointerCapture(e.pointerId);
});
svg.addEventListener('pointermove',function(e){
  if(!drag)return;
  const s=1000/(svg.getBoundingClientRect().width||1000);
  st.cx=Math.max(180,Math.min(820,st.cx+(e.clientX-px)*s));
  st.cy=Math.max(180,Math.min(820,st.cy+(e.clientY-py)*s));
  px=e.clientX;py=e.clientY;build();
});
svg.addEventListener('pointerup',function(){drag=false;});
svg.addEventListener('pointercancel',function(){drag=false;});

addEventListener('keydown',function(e){
  const k=e.key;
  if(k==='ArrowLeft'){st.rot-=0.12;build();}
  else if(k==='ArrowRight'){st.rot+=0.12;build();}
  else if(k==='ArrowUp'){st.dens=Math.min(70,st.dens+6);build();}
  else if(k==='ArrowDown'){st.dens=Math.max(6,st.dens-6);build();}
  else if(k===' '){st.salt=Math.floor(Math.random()*99991)+1;st.cx=500;st.cy=500;build();speckle();}
  else if(k==='r'||k==='R'){st.salt=0;st.rot=0;st.dens=26;st.cx=500;st.cy=500;build();speckle();}
  else return;
  e.preventDefault();
});
})();
</script>
</body>
</html>
"""
# EVOLVE-BLOCK-END
