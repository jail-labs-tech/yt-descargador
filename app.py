#!/usr/bin/env python3
"""Descargador local de YouTube (MP3/MP4). Uso: python3 app.py  ->  http://localhost:8765"""
import json, os, re, secrets, shutil, signal, subprocess, sys, tempfile, threading, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import quote, urlparse

TMP = tempfile.TemporaryDirectory(prefix="yt-")  # se borra solo al cerrar el server
PORT = 8765
HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}

PAGE = r"""<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark light">
<title>Descargador de YouTube</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,800&display=swap">
<style>
:root{--bg:#0b0a14;--ink:#f4f2ff;--mute:#b9b3d9;--glass:rgba(24,20,42,.62);--line:rgba(255,255,255,.14);--field:rgba(255,255,255,.06);--b1:#7c3aed;--b2:#ec4899;--b3:#06b6d4;--blob:.5;--err:#ffb4ba;--errbg:rgba(190,30,60,.22);--okc:#5eead4;--sh:0 30px 80px -20px rgba(0,0,0,.7);--disp:"Bricolage Grotesque",system-ui,"Segoe UI",sans-serif}
@media(prefers-color-scheme:light){:root{--bg:#f7f4ff;--ink:#1b1536;--mute:#575078;--glass:rgba(255,255,255,.7);--line:rgba(60,40,120,.16);--field:rgba(255,255,255,.8);--blob:.38;--err:#9f1239;--errbg:rgba(244,63,94,.12);--okc:#0f766e;--sh:0 30px 70px -25px rgba(80,50,160,.35)}}
*{box-sizing:border-box}
html{background:var(--bg)}
body{margin:0;min-height:100dvh;color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased;position:relative;overflow-x:hidden}
.bg{position:fixed;inset:0;z-index:-1;overflow:hidden;pointer-events:none}
.bg i{position:absolute;border-radius:50%;filter:blur(70px);opacity:var(--blob);will-change:transform}
.bg i:nth-child(1){width:60vmax;height:60vmax;left:-20vmax;top:-22vmax;background:var(--b1);animation:d1 22s ease-in-out infinite alternate}
.bg i:nth-child(2){width:50vmax;height:50vmax;right:-18vmax;top:10vh;background:var(--b2);animation:d2 26s ease-in-out infinite alternate}
.bg i:nth-child(3){width:44vmax;height:44vmax;left:10vw;bottom:-24vmax;background:var(--b3);animation:d3 30s ease-in-out infinite alternate}
@keyframes d1{to{transform:translate(12vmax,10vmax) scale(1.15)}}
@keyframes d2{to{transform:translate(-14vmax,8vmax) scale(.9)}}
@keyframes d3{to{transform:translate(10vmax,-8vmax) scale(1.2)}}
.bg::after{content:"";position:absolute;inset:0;opacity:.16;mix-blend-mode:overlay;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
main{max-width:640px;margin:0 auto;padding:clamp(28px,9vh,88px) 16px 56px}
.in{animation:up .7s cubic-bezier(.2,.8,.2,1) backwards;animation-delay:calc(var(--i,0)*90ms)}
@keyframes up{from{opacity:0;transform:translateY(18px)}}
.tag{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border:1px solid var(--line);border-radius:99px;background:var(--glass);font-size:.8125rem;font-weight:600;letter-spacing:.02em;backdrop-filter:blur(10px)}
.tag b{width:8px;height:8px;border-radius:50%;background:var(--okc);animation:pulse 2s ease-in-out infinite}
@keyframes pulse{50%{transform:scale(1.6);opacity:.5}}
h1{font:800 clamp(2.9rem,11.5vw,5.2rem)/.95 var(--disp);letter-spacing:-.045em;margin:18px 0 14px}
h1 em{font-style:normal;display:inline-block;background:linear-gradient(100deg,#a78bfa,#f472b6 55%,#fb923c);-webkit-background-clip:text;background-clip:text;color:transparent;padding-bottom:.08em}
@media(prefers-color-scheme:light){h1 em{background-image:linear-gradient(100deg,#6d28d9,#db2777 55%,#c2410c);-webkit-background-clip:text;background-clip:text}}
.sub{margin:0 0 28px;color:var(--mute);font-size:1.0625rem;max-width:34ch}
.card{background:var(--glass);border:1px solid var(--line);border-radius:28px;padding:24px;box-shadow:var(--sh);backdrop-filter:blur(22px) saturate(1.4);-webkit-backdrop-filter:blur(22px) saturate(1.4)}
@media(max-width:440px){.card{padding:16px;border-radius:24px}}
label,legend{display:block;font-size:.8125rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--mute);margin:0 0 10px;padding:0}
.field{display:flex;gap:8px;padding:6px;border:1px solid var(--line);border-radius:18px;background:var(--field);transition:border-color .2s,box-shadow .2s}
.field:focus-within{border-color:var(--b2);box-shadow:0 0 0 4px color-mix(in srgb,var(--b2) 28%,transparent)}
textarea{flex:1;min-width:0;min-height:84px;max-height:220px;padding:12px;font:inherit;line-height:1.45;color:var(--ink);background:transparent;border:0;outline:0;resize:vertical}
textarea:focus-visible{outline:0}
textarea::placeholder{color:var(--mute);opacity:.8}
button{font:inherit;cursor:pointer}
:focus-visible{outline:3px solid var(--b3);outline-offset:3px}
.paste{display:flex;align-items:center;gap:6px;height:48px;align-self:flex-start;padding:0 14px;border:0;border-radius:13px;background:var(--glass);color:var(--ink);font-weight:600;box-shadow:inset 0 0 0 1px var(--line);transition:transform .15s ease-out,background .2s}
.paste:hover{background:var(--field)}.paste:active{transform:scale(.95)}
svg{display:block;flex:none}
.ic{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
fieldset{border:0;margin:24px 0 0;padding:0;min-width:0}
.seg{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.seg label{position:relative;margin:0;text-transform:none;letter-spacing:0;font-size:1rem;color:var(--ink);cursor:pointer;display:block}
.seg input{position:absolute;inset:0;margin:0;opacity:0;cursor:pointer;z-index:1}
.seg label:nth-child(1){--c:#a78bfa;--c2:#ec4899}.seg label:nth-child(2){--c:#fb923c;--c2:#f43f5e}
.tile{position:relative;display:block;padding:16px;min-height:148px;border-radius:20px;background:var(--field);border:1px solid var(--line);overflow:hidden;transition:transform .25s cubic-bezier(.2,.8,.2,1),box-shadow .25s}
.tile::before{content:"";position:absolute;inset:0;background:linear-gradient(145deg,color-mix(in srgb,var(--c) 38%,transparent),color-mix(in srgb,var(--c2) 22%,transparent));opacity:0;transition:opacity .25s}
.tile>*{position:relative}
.seg label:hover .tile{transform:translateY(-3px)}
.seg label:active .tile{transform:scale(.97)}
.ico{display:grid;place-items:center;width:52px;height:52px;border-radius:16px;color:#fff;background:linear-gradient(135deg,var(--c),var(--c2));margin-bottom:14px;transition:transform .35s cubic-bezier(.34,1.56,.64,1)}
.ico svg{width:28px;height:28px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.tile b{display:block;font:800 1.5rem/1.1 var(--disp);letter-spacing:-.02em}
.tile small{display:block;color:var(--mute);font-size:.875rem;margin-top:2px}
.tick{position:absolute!important;right:12px;top:12px;width:24px;height:24px;border-radius:50%;display:grid;place-items:center;background:#fff;color:#111;transform:scale(0);transition:transform .3s cubic-bezier(.34,1.56,.64,1)}
.tick svg{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:3.5;stroke-linecap:round;stroke-linejoin:round}
.seg input:checked~.tile{box-shadow:0 0 0 2px var(--c),0 18px 40px -16px var(--c)}
.seg input:checked~.tile::before{opacity:1}
.seg input:checked~.tile .ico{transform:scale(1.12) rotate(-6deg)}
.seg input:checked~.tile .tick{transform:scale(1)}
.seg input:focus-visible~.tile{outline:3px solid var(--b3);outline-offset:3px}
.go{position:relative;overflow:hidden;display:flex;align-items:center;justify-content:center;gap:10px;width:100%;height:60px;margin-top:24px;border:0;border-radius:18px;color:#fff;font:800 1.1875rem var(--disp);letter-spacing:-.01em;background:linear-gradient(100deg,#6d28d9,#be185d 60%,#c2410c);box-shadow:0 14px 34px -10px #be185d,inset 0 1px 0 rgba(255,255,255,.35);transition:transform .15s ease-out,box-shadow .2s}
.go::after{content:"";position:absolute;inset:0;background:linear-gradient(100deg,transparent 30%,rgba(255,255,255,.4) 50%,transparent 70%);transform:translateX(-120%)}
.go:hover:not(:disabled)::after{transition:transform .7s ease;transform:translateX(120%)}
.go:hover:not(:disabled){transform:translateY(-2px);box-shadow:0 20px 40px -12px #be185d,inset 0 1px 0 rgba(255,255,255,.35)}
.go:active:not(:disabled){transform:scale(.97)}
.go.busy::after{animation:sweep 1.4s ease-in-out infinite}
@keyframes sweep{to{transform:translateX(120%)}}
.go svg{width:22px;height:22px;transition:transform .2s}
.go:hover:not(:disabled) svg{transform:translateY(2px)}
:disabled{cursor:not-allowed}
fieldset.qf{margin-top:20px}
.q{display:flex;flex-wrap:wrap;gap:8px}
.q label{position:relative;margin:0;text-transform:none;letter-spacing:0;font-size:.9375rem;font-weight:700;color:var(--ink);cursor:pointer}
.q input{position:absolute;inset:0;margin:0;opacity:0;cursor:pointer;z-index:1}
.q span{display:flex;align-items:center;min-height:44px;padding:0 16px;border-radius:99px;border:1px solid var(--line);background:var(--field);transition:transform .15s ease-out,background .2s,box-shadow .2s}
.q label:hover span{transform:translateY(-2px)}.q label:active span{transform:scale(.95)}
.q input:checked+span{color:#fff;border-color:transparent;background:linear-gradient(100deg,#6d28d9,#be185d);box-shadow:0 8px 20px -8px #be185d}
.q input:focus-visible+span{outline:3px solid var(--b3);outline-offset:3px}
.q input:disabled+span{opacity:.55}
.hint{margin:10px 2px 0;color:var(--mute);font-size:.8125rem;min-height:1.2em}
#dls{margin-top:36px}
#dls h2{font:800 1.25rem var(--disp);letter-spacing:-.02em;margin:0 4px 12px}
#list{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.dl{padding:14px 16px;border:1px solid var(--line);border-radius:20px;background:var(--glass);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);animation:up .45s cubic-bezier(.2,.8,.2,1)}
.dl-top{display:flex;align-items:center;gap:12px}
.dl-ic{flex:none;width:40px;display:grid;place-items:center}
.dl-main{flex:1;min-width:0}
.dl-title{font-weight:700;overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.dl-meta{display:flex;align-items:center;flex-wrap:wrap;gap:4px 10px;margin-top:4px;font-size:.875rem;color:var(--mute)}
.bdg{font-style:normal;font-size:.75rem;font-weight:800;letter-spacing:.05em;padding:3px 10px;border-radius:99px;color:#fff;background:linear-gradient(135deg,#6d28d9,#be185d)}
.bdg.mp4{background:linear-gradient(135deg,#c2410c,#be123c)}
.dl-pct{font:800 1.75rem/1 var(--disp);letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.dl-x{flex:none;width:44px;height:44px;margin:-8px -10px -8px 0;border:0;border-radius:50%;background:transparent;color:var(--mute);display:grid;place-items:center}
.dl-x:hover{background:var(--field);color:var(--ink)}
.dl-x svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:2.4;stroke-linecap:round}
.dl-det{margin-top:8px;color:var(--mute);font-size:.8125rem;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.dl-det:empty{display:none}
.track{position:relative;height:8px;margin-top:12px;border-radius:99px;background:var(--line);overflow:hidden}
.track i{position:absolute;inset:0;border-radius:99px;background:linear-gradient(90deg,var(--b1),var(--b2),#fb923c);transform-origin:left;transform:scaleX(0);transition:transform .45s cubic-bezier(.2,.8,.2,1)}
.track.ind i{width:40%;transform:none;transition:none;animation:ind 1.3s ease-in-out infinite}
@keyframes ind{from{transform:translateX(-100%)}to{transform:translateX(250%)}}
.dl.queue .track i,.dl.done .track,.dl.err .track{display:none}
.dl.queue .track{opacity:.6}
.dl.queue .eq i{animation:none;transform:scaleY(.35);opacity:.5}
.dl.err{background:var(--errbg);border-color:color-mix(in srgb,var(--err) 45%,transparent);animation:shake .4s}
.dl.err .dl-title,.dl.err .dl-meta,.dl.err .dl-det{color:var(--err)}
.retry{margin-top:10px;min-height:44px;padding:0 18px;border:0;border-radius:99px;color:#fff;font-weight:700;background:linear-gradient(100deg,#6d28d9,#be185d);transition:transform .15s ease-out}
.retry:active{transform:scale(.95)}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.eq{display:flex;align-items:center;gap:4px;height:32px;flex:none}
.eq i{width:5px;height:100%;border-radius:3px;background:linear-gradient(var(--b2),var(--b1));transform:scaleY(.35);animation:eq 1s ease-in-out infinite}
.eq i:nth-child(2){animation-delay:-.2s}.eq i:nth-child(3){animation-delay:-.5s}.eq i:nth-child(4){animation-delay:-.7s}.eq i:nth-child(5){animation-delay:-.35s}
@keyframes eq{50%{transform:scaleY(1)}}
@keyframes shake{20%{transform:translateX(-6px)}45%{transform:translateX(5px)}70%{transform:translateX(-3px)}}
.badge{position:relative;display:grid;place-items:center;width:40px;height:40px;border-radius:50%;flex:none;background:var(--okc);color:#06251f}
.badge svg{width:22px;height:22px;fill:none;stroke:currentColor;stroke-width:3.2;stroke-linecap:round;stroke-linejoin:round;animation:pop .5s .1s cubic-bezier(.34,1.56,.64,1) backwards}
.badge::after{content:"";position:absolute;inset:0;border-radius:50%;border:2px solid var(--okc);animation:ring .9s .1s ease-out backwards}
@keyframes pop{from{transform:scale(0) rotate(-30deg)}}
@keyframes ring{from{transform:scale(1);opacity:.9}to{transform:scale(2.1);opacity:0}}
.xb{display:grid;place-items:center;width:40px;height:40px;border-radius:50%;flex:none;background:var(--err);color:var(--bg)}
.xb svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:3.2;stroke-linecap:round}
[hidden]{display:none!important}
@media(prefers-reduced-motion:reduce){.track.ind i{width:100%;opacity:.5}*,*::before,*::after{animation:none!important;transition:none!important}.eq i:nth-child(odd){transform:scaleY(.8)}}
</style>
<div class="bg" aria-hidden="true"><i></i><i></i><i></i></div>
<main>
<div class="tag in"><b></b>Corre en tu equipo</div>
<h1 class="in" style="--i:1">YouTube,<br><em>a tu disco.</em></h1>
<p class="sub in" style="--i:2">Pega un enlace, elige audio o video y se guarda en tu equipo.</p>
<form class="card in" id="f" style="--i:3" novalidate>
 <label for="u">Enlaces de video</label>
 <div class="field">
  <textarea id="u" rows="3" autocomplete="off" spellcheck="false" placeholder="Pega uno o varios enlaces, uno por línea" autofocus></textarea>
  <button type="button" class="paste" id="p" aria-label="Pegar enlaces desde el portapapeles"><svg class="ic" viewBox="0 0 24 24"><rect x="8" y="3" width="8" height="4" rx="1"/><path d="M16 5h2a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h2"/></svg>Pegar</button>
 </div>
 <fieldset>
  <legend>Formato</legend>
  <div class="seg">
   <label><input type="radio" name="fmt" value="mp3" checked><span class="tile"><span class="ico"><svg viewBox="0 0 24 24"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg></span><b>MP3</b><small>Solo audio</small><span class="tick"><svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7"/></svg></span></span></label>
   <label><input type="radio" name="fmt" value="mp4"><span class="tile"><span class="ico"><svg viewBox="0 0 24 24"><path d="M4 11h16v9H4z"/><path d="M3.5 6.8l16.2-2.9.8 4.4L4.3 11.2z"/><path d="M8.6 5.9l2.4 3.8M13.8 5l2.4 3.8"/></svg></span><b>MP4</b><small>Video con audio</small><span class="tick"><svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7"/></svg></span></span></label>
  </div>
 </fieldset>
 <fieldset class="qf">
  <legend>Calidad</legend>
  <div class="q" id="q"></div>
  <p class="hint" id="hint"></p>
 </fieldset>
 <button class="go" id="g" type="submit"><span id="gl">Descargar</span><svg class="ic" viewBox="0 0 24 24"><path d="M12 4v12m0 0l-5-5m5 5l5-5M5 20h14"/></svg></button>
 <p class="hint" id="kb">Ctrl o Cmd + Enter para descargar. Cada enlace es una descarga independiente.</p>
 <span class="sr" id="live" role="status" aria-live="polite"></span>
</form>
<section id="dls" hidden>
 <h2>Descargas</h2>
 <ul id="list"></ul>
</section>
</main>
<template id="ic-eq"><div class="eq" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div></template>
<template id="ic-ok"><div class="badge" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7"/></svg></div></template>
<template id="ic-x"><div class="xb" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></div></template>
<template id="x-ic"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></template>
<script>
const $=id=>document.getElementById(id),u=$('u'),g=$('g'),p=$('p');
const Q={mp3:[['best','Máxima'],['320','320 kbps'],['192','192 kbps'],['128','128 kbps']],
 mp4:[['best','Máxima'],['1080','1080p'],['720','720p'],['480','480p'],['360','360p']]};
const DEF={mp3:'best',mp4:'1080'};
const HINT={mp3:'Máxima usa calidad variable (VBR), la mejor posible.',mp4:'Máxima es la mejor calidad que abre en cualquier reproductor (normalmente 1080p).'};
const fmt=()=>document.querySelector('[name=fmt]:checked').value;
const qual=()=>document.querySelector('[name=q]:checked').value;
function drawQ(){
  const f=fmt();$('q').replaceChildren(...Q[f].map(([v,t])=>{
    const l=document.createElement('label'),i=document.createElement('input'),s=document.createElement('span');
    i.type='radio';i.name='q';i.value=v;i.checked=v===DEF[f];s.textContent=t;l.append(i,s);return l}));
  $('hint').textContent=HINT[f];
}
document.querySelectorAll('[name=fmt]').forEach(r=>r.onchange=drawQ);drawQ();
const live=$('live'),list=$('list');
const MB=n=>n>=1073741824?(n/1073741824).toFixed(2)+' GB':n>=1048576?(n/1048576).toFixed(1)+' MB':Math.max(1,Math.round(n/1024))+' KB';
const T=s=>Math.floor(s/60)+':'+String(Math.floor(s%60)).padStart(2,'0');
const tpl=id=>$(id).content.firstElementChild.cloneNode(true);
function el(tag,cls,txt){const e=document.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e}
function announce(t){
  live.append(el('div',null,t));
  while(live.children.length>4)live.firstChild.remove();
}
const links=()=>[...new Set(u.value.split(/[\s,]+/).filter(Boolean))];
function count(){const n=links().length;$('gl').textContent=n>1?'Descargar '+n:'Descargar'}
u.addEventListener('input',count);
u.addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.metaKey||e.ctrlKey)){e.preventDefault();$('f').requestSubmit()}});
p.onclick=async()=>{
  try{const t=(await navigator.clipboard.readText()).trim();
    if(t)u.value=(u.value.trim()?u.value.trim()+'\n':'')+t+'\n';count();u.focus()}
  catch(e){u.focus();announce('No pude leer el portapapeles. Pega con Ctrl+V o Cmd+V.')}
};
const items=new Set();let timer=null,busy=false;
function setIcon(it,id){it.ic.replaceChildren(tpl(id))}
function render(it,s){
  const c=it.card;
  const state=it.state;
  c.className='dl '+state;
  const pc=s&&typeof s.percent==='number'?Math.max(0,Math.min(100,s.percent)):null;
  it.title.textContent=state==='done'&&s&&s.name?s.name:(s&&s.title)||it.url;
  const tr=it.track;
  if(state==='running'||state==='queue'){
    it.stage.textContent=(s&&s.label)||'Preparando...';
    const ind=pc===null&&state==='running';
    tr.classList.toggle('ind',ind);
    if(pc===null){tr.removeAttribute('aria-valuenow');it.fill.style.transform='';it.pct.textContent=''}
    else{tr.setAttribute('aria-valuenow',Math.round(pc));it.pct.textContent=Math.round(pc)+'%';it.fill.style.transform='scaleX('+pc/100+')'}
    it.ic.hidden=pc!==null&&state==='running';
    if(it.iconShown!=='eq'){setIcon(it,'ic-eq');it.iconShown='eq'}
    const d=[];
    if(s){
      if(s.downloaded!=null)d.push(s.total!=null?MB(s.downloaded)+' de '+MB(s.total):MB(s.downloaded));
      if(s.speed!=null)d.push(MB(s.speed)+'/s');
      if(s.eta!=null)d.push('quedan '+T(s.eta));
    }
    it.det.textContent=d.join(' · ');
    it.retry.hidden=true;it.x.hidden=true;
  }else if(state==='done'){
    it.stage.textContent='Descargado';it.pct.textContent='';tr.removeAttribute('aria-valuenow');
    tr.setAttribute('aria-valuenow','100');
    it.ic.hidden=false;it.iconShown='ok';setIcon(it,'ic-ok');it.det.textContent='Tu navegador lo está descargando. Lo encuentras en tus Descargas.';
    it.save.href='/file/'+it.id;it.save.download=it.name||'';it.save.hidden=false;
    it.retry.hidden=true;it.x.hidden=false;
  }else{
    it.stage.textContent='Error';it.pct.textContent='';tr.removeAttribute('aria-valuenow');
    it.ic.hidden=false;it.iconShown='x';setIcon(it,'ic-x');it.det.textContent=it.err;
    it.retry.hidden=false;it.x.hidden=false;it.save.hidden=true;
  }
}
function make(url,f,q){
  const it={url,f,q,state:'running',id:null,err:'',iconShown:''};
  const c=el('li','dl running'),top=el('div','dl-top');
  it.ic=el('div','dl-ic');it.title=el('div','dl-title');it.stage=el('span','dl-stage');
  it.pct=el('div','dl-pct');it.pct.setAttribute('aria-hidden','true');
  const bd=el('em','bdg '+f,f.toUpperCase()+' · '+(q==='best'?'Máxima':f==='mp4'?q+'p':q));
  const meta=el('div','dl-meta');meta.append(bd,it.stage);
  const main=el('div','dl-main');main.append(it.title,meta);
  it.x=el('button','dl-x');it.x.type='button';it.x.setAttribute('aria-label','Quitar de la lista');it.x.append(tpl('x-ic'));it.x.hidden=true;
  it.x.onclick=()=>{items.delete(it);c.remove();if(!list.children.length)$('dls').hidden=true};
  top.append(it.ic,main,it.pct,it.x);
  it.track=el('div','track ind');it.track.setAttribute('role','progressbar');
  it.track.setAttribute('aria-valuemin','0');it.track.setAttribute('aria-valuemax','100');
  it.track.setAttribute('aria-label','Progreso de la descarga');
  it.fill=el('i');it.track.append(it.fill);
  it.det=el('div','dl-det');
  it.retry=el('button','retry','Reintentar');it.retry.type='button';it.retry.hidden=true;
  it.retry.onclick=()=>launch(it);
  it.save=el('a','retry','¿No empezó? Guardar archivo');it.save.hidden=true;
  c.append(top,it.track,it.det,it.retry,it.save);it.card=c;
  list.prepend(c);$('dls').hidden=false;
  return it;
}
async function launch(it){
  it.state='running';it.id=null;it.miss=0;it.save.hidden=true;items.add(it);
  render(it,{label:'Preparando...',percent:null});
  announce('Agregada: '+it.url);
  try{
    const r=await fetch('/download',{method:'POST',body:JSON.stringify({url:it.url,format:it.f,quality:it.q})});
    const j=await r.json();
    if(!j.ok)return fail(it,j.error);
    it.id=j.id;poll();
  }catch(x){fail(it,'No se pudo conectar con el servidor')}
}
function fail(it,msg){
  it.state='err';it.err=msg||'Error desconocido';items.delete(it);render(it);
  announce('Error: '+it.err);
}
function poll(){if(!timer)timer=setInterval(tick,600)}
async function tick(){
  if(busy)return;busy=true;
  try{
    await Promise.all([...items].filter(it=>it.id).map(async it=>{
      try{
        const s=await (await fetch('/status/'+it.id)).json();it.miss=0;
        if(s.state==='error'){it.err=s.error;fail(it,s.error)}
        else if(s.state==='done'){
          it.state='done';it.name=s.name;items.delete(it);render(it,s);
          const a=document.createElement('a');a.href='/file/'+it.id;a.download=s.name;
          document.body.append(a);a.click();a.remove();
          announce('Descargado: '+s.name);
        }else{it.state=s.stage==='queue'?'queue':'running';render(it,s)}
      }catch(x){if(++it.miss>=3)fail(it,'No se pudo consultar el estado de la descarga')}
    }));
  }finally{busy=false}
  if(!items.size){clearInterval(timer);timer=null}
}
$('f').onsubmit=e=>{
  e.preventDefault();
  const ls=links();
  if(!ls.length){announce('Falta el enlace');u.focus();return}
  const f=fmt(),q=qual();
  u.value='';count();u.focus();
  ls.forEach(l=>launch(make(l,f,q)));
};
</script></html>"""


def mp4(h=None):  # siempre H.264 + AAC si existe: AV1/Opus no abren en QuickTime (solo se oye el audio)
    f = f"[height<={h}]" if h else ""
    return ["-f", f"bv*{f}[vcodec^=avc1]+ba[ext=m4a]/bv*{f}[ext=mp4]+ba[ext=m4a]/b{f}[ext=mp4]/bv*{f}+ba/b",
            "--merge-output-format", "mp4"]


MP3 = ["-x", "--audio-format", "mp3", "--audio-quality"]
QUALITY = {
    "mp3": {"best": MP3 + ["0"], "320": MP3 + ["320K"], "192": MP3 + ["192K"], "128": MP3 + ["128K"]},
    "mp4": {"best": mp4(), "1080": mp4(1080), "720": mp4(720), "480": mp4(480), "360": mp4(360)},
}
JOBS = {}  # id -> estado de la descarga
SLOTS = threading.Semaphore(3)  # ponytail: 3 descargas a la vez, el resto espera "En cola"
PROG = "download:PROG %(progress.downloaded_bytes)s %(progress.total_bytes)s %(progress.total_bytes_estimate)s %(progress.speed)s %(progress.eta)s"
POSTPROC = ("[Merger]", "[ExtractAudio]", "[VideoConvertor]", "[VideoRemuxer]", "[Fixup")


def num(x):
    try:
        return float(x)
    except ValueError:
        return None  # "NA"


def label(job):
    if job["stage"] == "convert":
        return "Convirtiendo a MP3" if job["format"] == "mp3" else "Uniendo video y audio"
    if job["stage"] == "download":
        return "Descargando video" if job["format"] == "mp4" and job["part"] == 1 else "Descargando audio"
    return "Preparando..."


def run(job, url, opts, out):
    cmd = ["yt-dlp", "--no-playlist", "--playlist-items", "1", "--encoding", "utf-8", "--newline", "--progress-template", PROG,
           *opts, "-o", str(Path(out) / "%(title)s.%(ext)s"), "--", url]
    SLOTS.acquire()
    job.update(stage="start", label="Preparando...")
    try:
        for attempt in range(1, 4):  # YouTube a veces da 403 a un enlace; reintentar saca enlaces nuevos
            err = yt_dlp(job, cmd)
            if not err:
                break
            print(f"[intento {attempt}] {url}: {err}", flush=True)
            if "403" not in err or attempt == 3:
                raise RuntimeError(err)
        f = next((f for f in Path(out).iterdir() if f.suffix == "." + job["format"]), None)
        if not f:
            raise RuntimeError("yt-dlp terminó pero no generó el archivo")
        job.update(state="done", percent=100, file=str(f), name=f.name, label="Listo")
    except Exception as e:
        job.update(state="error", error=str(e))
        shutil.rmtree(out, ignore_errors=True)
    finally:
        SLOTS.release()


def yt_dlp(job, cmd):
    """Corre yt-dlp actualizando el progreso de job. Devuelve None si salió bien o el mensaje de error."""
    err = "yt-dlp falló"
    job["part"] = 0
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace") as p:
        for line in p.stdout:
            if line.startswith("PROG "):
                done, total, est, speed, eta = map(num, line.split()[1:6])
                total = total or est
                job.update(downloaded=done, total=total, speed=speed, eta=eta,
                           percent=round(min(done / total, 1) * 100, 1) if done and total else 0)
            elif line.startswith("[download] Destination:"):
                job["title"] = re.sub(r"(\.f\d+)?\.\w+$", "", Path(line.split(": ", 1)[1].strip()).name)
                job.update(stage="download", part=job["part"] + 1, percent=0, speed=None, eta=None)
            elif line.startswith(POSTPROC):
                job.update(stage="convert", percent=None, speed=None, eta=None)
            elif line.startswith("ERROR:"):
                err = line.strip()
            job["label"] = label(job)
    return err if p.returncode else None

def start(url, fmt, quality):
    u = urlparse(url)
    if u.scheme not in ("http", "https") or u.hostname not in HOSTS:
        raise ValueError("Solo enlaces de YouTube")
    if u.path.startswith(("/playlist", "/@", "/channel/", "/c/", "/user/")):
        raise ValueError("Pega el enlace de un video, no de una lista o canal")
    opts = QUALITY.get(fmt, {}).get(quality)
    if not opts:
        raise ValueError("Formato o calidad inválidos")
    jid = secrets.token_urlsafe(16)
    JOBS[jid] = job = {"state": "running", "format": fmt, "stage": "queue", "part": 0, "label": "En cola", "title": None,
                       "percent": 0, "downloaded": None, "total": None, "speed": None, "eta": None}
    threading.Thread(target=run, args=(job, url, opts, tempfile.mkdtemp(dir=TMP.name)), daemon=True).start()
    return jid


class H(BaseHTTPRequestHandler):
    def send(self, code, body, ctype):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # sin spam de /status cada segundo
        pass

    def trusted(self):
        """Solo esta misma página: bloquea que otro sitio abierto en tu navegador use el server (CSRF / DNS rebinding)."""
        port = self.server.server_address[1]
        allowed = {f"localhost:{port}", f"127.0.0.1:{port}"}
        origin = self.headers.get("Origin")
        if self.headers.get("Host") in allowed and (origin is None or origin.split("://", 1)[-1] in allowed):
            return True
        self.send(403, "Prohibido", "text/plain; charset=utf-8")
        return False

    def do_GET(self):
        if not self.trusted():
            return
        if self.path.startswith("/status/"):
            job = JOBS.get(self.path[8:])
            if not job:
                return self.send(404, '{"state": "error", "error": "No existe"}', "application/json")
            return self.send(200, json.dumps({k: v for k, v in job.items() if k != "file"}), "application/json")
        if not self.path.startswith("/file/"):
            return self.send(200, PAGE, "text/html; charset=utf-8")
        jid = self.path[6:]
        if JOBS.get(jid, {}).get("state") != "done":
            return self.send(404, "No encontrado", "text/plain; charset=utf-8")
        path = JOBS.pop(jid, {}).get("file")  # un solo uso
        if not path:  # otra petición ganó la carrera
            return self.send(404, "No encontrado", "text/plain; charset=utf-8")
        try:
            name = Path(path).name
            ascii_name = name.encode("ascii", "replace").decode().replace('"', "'")
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(os.path.getsize(path)))
            self.send_header("Content-Disposition",
                             f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}")
            self.end_headers()
            with open(path, "rb") as f:
                shutil.copyfileobj(f, self.wfile)
        finally:
            shutil.rmtree(Path(path).parent, ignore_errors=True)  # no se guarda nada

    def do_POST(self):
        if not self.trusted():
            return
        if self.path != "/download":
            return self.send(404, "{}", "application/json")
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            res = {"ok": True, "id": start(req.get("url", ""), req.get("format"), req.get("quality", "best"))}
        except Exception as e:
            res = {"ok": False, "error": str(e)}
        self.send(200, json.dumps(res), "application/json")


if __name__ == "__main__":
    for sig in ("SIGHUP", "SIGTERM"):  # cerrar la terminal también borra los temporales
        if hasattr(signal, sig):
            signal.signal(getattr(signal, sig), lambda *a: sys.exit(0))
    print(f"Abierto en http://localhost:{PORT}")
    webbrowser.open(f"http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()  # solo tu máquina
