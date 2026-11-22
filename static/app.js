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
const isPl=l=>{try{const x=new URL(l),v=x.searchParams.get('list');return /^https?:$/.test(x.protocol)&&!!v&&!(v.startsWith('RD')&&!v.startsWith('RDCLAK'))}catch(e){return false}};
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
  it.title.textContent=state==='done'&&s&&s.name?s.name:(s&&s.title)||it.t||it.url;
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
    it.retry.hidden=true;it.x.hidden=true;it.helpa.hidden=true;
  }else if(state==='done'){
    it.stage.textContent='Descargado';it.pct.textContent='';tr.setAttribute('aria-valuenow','100');
    it.ic.hidden=false;it.iconShown='ok';setIcon(it,'ic-ok');it.det.textContent='Tu navegador lo está descargando. Lo encuentras en tus Descargas.';
    it.save.href='/file/'+it.id;it.save.download=it.name||'';it.save.hidden=false;
    it.retry.hidden=true;it.helpa.hidden=true;it.x.hidden=false;
  }else{
    it.stage.textContent='Error';it.pct.textContent='';tr.removeAttribute('aria-valuenow');
    it.ic.hidden=false;it.iconShown='x';setIcon(it,'ic-x');it.det.textContent=it.err;
    it.retry.hidden=false;it.x.hidden=false;it.save.hidden=true;it.helpa.hidden=!it.help;if(it.help)it.helpa.href='#'+it.help;
  }
}
const lab=(f,q)=>f.toUpperCase()+' · '+(q==='best'?'Máxima':f==='mp4'?q+'p':q);
function make(url,f,q,t){
  const it={url,f,q,t,state:'running',id:null,err:'',iconShown:''};
  const c=el('li','dl running'),top=el('div','dl-top');
  it.ic=el('div','dl-ic');it.title=el('div','dl-title');it.stage=el('span','dl-stage');
  it.pct=el('div','dl-pct');it.pct.setAttribute('aria-hidden','true');
  const bd=el('em','bdg '+f,lab(f,q));
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
  it.helpa=el('a','retry alt','Cómo solucionarlo');it.helpa.hidden=true;
  it.helpa.onclick=e=>{e.preventDefault();openHelp(it.help)};
  c.append(top,it.track,it.det,it.retry,it.helpa,it.save);it.card=c;
  list.prepend(c);$('dls').hidden=false;
  return it;
}
async function launch(it,quiet){
  it.state='running';it.id=null;it.miss=0;it.help='';it.save.hidden=true;items.add(it);
  render(it,{label:'Preparando...',percent:null});
  if(!quiet)announce('Agregada: '+it.url);
  try{
    const r=await fetch('/download',{method:'POST',body:JSON.stringify({url:it.url,format:it.f,quality:it.q})});
    const j=await r.json();
    if(!j.ok)return fail(it,j.error,j.help);
    it.id=j.id;poll();
  }catch(x){fail(it,'No se pudo conectar con el servidor')}
}
function fail(it,msg,help){
  it.state='err';it.err=msg||'Error desconocido';it.help=$(help)&&$(help).closest('#help')?help:'';items.delete(it);render(it);
  announce('Error: '+it.err);
}
function poll(){if(!timer)timer=setInterval(tick,600)}
async function tick(){
  if(busy)return;busy=true;
  try{
    await Promise.all([...items].filter(it=>it.id).map(async it=>{
      try{
        const s=await (await fetch('/status/'+it.id)).json();it.miss=0;
        if(s.state==='error'){fail(it,s.error,s.help)}
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
  if(g.disabled)return;
  const ls=links();
  if(!ls.length){announce('Falta el enlace');u.focus();return}
  const f=fmt(),q=qual();
  u.value='';count();u.focus();
  ls.forEach(l=>isPl(l)?makePl(l):launch(make(l,f,q)));
};

// Listas de reproducción: tarjeta para elegir videos
const D=s=>{s=Math.floor(s);const h=Math.floor(s/3600),m=Math.floor(s%3600/60),r=String(s%60).padStart(2,'0');return h?h+':'+String(m).padStart(2,'0')+':'+r:m+':'+r};
const pls=new Set();
function refreshPl(){const t='Se usará '+lab(fmt(),qual())+' (lo elegido arriba).';pls.forEach(it=>it.info&&(it.info.textContent=t))}
$('f').addEventListener('change',refreshPl);
function makePl(url){
  const it={url,help:'',err:''},c=el('li','dl pl loading'),top=el('div','dl-top');
  it.ic=el('div','dl-ic');it.title=el('div','dl-title');it.stage=el('span','dl-stage');
  const meta=el('div','dl-meta');meta.append(el('em','bdg pl','LISTA'),it.stage);
  const main=el('div','dl-main');main.append(it.title,meta);
  it.x=el('button','dl-x');it.x.type='button';it.x.setAttribute('aria-label','Quitar de la lista');it.x.append(tpl('x-ic'));
  it.x.onclick=()=>{pls.delete(it);c.remove();if(!list.children.length)$('dls').hidden=true};
  top.append(it.ic,main,it.x);
  it.body=el('div','pl-body');
  it.retry=el('button','retry','Reintentar');it.retry.type='button';it.retry.onclick=()=>loadPl(it);
  it.helpa=el('a','retry alt','Cómo solucionarlo');it.helpa.onclick=e=>{e.preventDefault();openHelp(it.help)};
  it.det=el('div','dl-det');
  it.track=el('div','track ind');it.track.setAttribute('role','progressbar');it.track.setAttribute('aria-label','Cargando la lista');it.track.append(el('i'));
  it.card=c;c.append(top,it.body);list.prepend(c);$('dls').hidden=false;pls.add(it);
  loadPl(it);return it;
}
async function loadPl(it){
  it.card.className='dl pl loading';it.title.textContent=it.url;it.stage.textContent='Cargando lista…';
  it.ic.hidden=false;it.ic.replaceChildren(tpl('ic-eq'));it.x.hidden=false;it.info=null;
  it.refocus=it.card.contains(document.activeElement);
  it.body.replaceChildren(it.track);announce('Cargando lista de reproducción');
  try{
    const r=await fetch('/playlist',{method:'POST',body:JSON.stringify({url:it.url})});
    const j=await r.json();
    if(!pls.has(it))return;
    if(!j.ok)return plErr(it,j.error,j.help);
    if(!Array.isArray(j.entries)||!j.entries.length)return plErr(it,'La lista no tiene videos disponibles');
    plReady(it,j);
  }catch(x){if(pls.has(it))plErr(it,'No se pudo conectar con el servidor')}
}
function plErr(it,msg,help){
  it.err=msg||'Error desconocido';it.help=$(help)&&$(help).closest('#help')?help:'';
  it.card.className='dl pl err';it.stage.textContent='Error';it.ic.replaceChildren(tpl('ic-x'));
  it.det.textContent=it.err;it.helpa.hidden=!it.help;if(it.help)it.helpa.href='#'+it.help;
  it.body.replaceChildren(it.det,it.retry,it.helpa);announce('Error: '+it.err);
  if(it.refocus)it.retry.focus();
}
function plReady(it,j){
  const es=j.entries,n=es.length,tot=Number.isFinite(j.count)?j.count:n;
  it.card.className='dl pl ready';it.ic.replaceChildren();it.ic.hidden=true;
  it.title.textContent=j.title||'Lista de reproducción';
  it.stage.textContent=j.truncated?'Se muestran los primeros '+n+' de '+tot:tot+(tot===1?' video':' videos');
  const boxes=[],cnt=el('span','pl-n'),go=el('button','retry','');go.type='button';
  const upd=()=>{const k=boxes.filter(b=>b.checked).length;cnt.textContent=k+' de '+n+' seleccionados';
    go.textContent='Descargar '+k;go.disabled=!k;return k};
  const all=v=>()=>{boxes.forEach(b=>b.checked=v);announce(upd()+' de '+n+' seleccionados')};
  const bA=el('button','pl-btn','Todos'),bN=el('button','pl-btn','Ninguno');bA.type=bN.type='button';
  bA.onclick=all(true);bN.onclick=all(false);
  const tools=el('div','pl-tools');tools.append(bA,bN,cnt);
  const fs=el('fieldset','pl-box'),lg=el('legend','sr','Videos de la lista para descargar'),box=el('div','pl-list');
  es.forEach(e=>{
    const row=el('label','pl-row'),cb=document.createElement('input');cb.type='checkbox';cb.checked=true;cb.onchange=upd;
    boxes.push(cb);
    const th=el('span','pl-th');
    if(typeof e.thumb==='string'&&e.thumb.startsWith('https://i.ytimg.com/')){
      const im=document.createElement('img');im.loading='lazy';im.alt='';im.src=e.thumb;th.append(im)}
    if(typeof e.duration==='number')th.append(el('i',null,D(e.duration)));
    row.append(cb,th,el('span','pl-t',e.title||e.url));box.append(row);
  });
  fs.append(lg,box);
  it.info=el('p','pl-info');
  const cancel=el('button','retry alt','Cancelar');cancel.type='button';cancel.onclick=it.x.onclick;
  go.onclick=()=>{
    const f=fmt(),q=qual(),pick=es.filter((e,i)=>boxes[i].checked);if(!pick.length)return;
    it.x.onclick();
    pick.reverse().forEach(e=>launch(make(e.url,f,q,e.title),true));
    announce(pick.length+(pick.length===1?' video agregado':' videos agregados'));
    const h=$('dls').querySelector('h2');h.tabIndex=-1;h.focus({preventScroll:true});
  };
  const act=el('div','pl-act');act.append(go,cancel);
  it.body.replaceChildren(tools,fs,it.info,act);upd();refreshPl();
  announce('Lista cargada: '+n+(n===1?' video':' videos'));if(it.refocus)bA.focus();
}

// Ayuda: abrir y enfocar un <details>, aunque ya esté abierto
function openHelp(id){
  const d=$(id);if(!d)return;
  d.open=true;
  const reduce=matchMedia('(prefers-reduced-motion:reduce)').matches;
  d.scrollIntoView({behavior:reduce?'auto':'smooth',block:'start'});
  d.querySelector('summary').focus({preventScroll:true});
}
document.querySelectorAll('#help .cp').forEach(b=>b.onclick=async()=>{
  try{await navigator.clipboard.writeText(b.parentNode.querySelector('code').textContent);
    b.textContent='Copiado';announce('Comando copiado');setTimeout(()=>b.textContent='Copiar',1500)}
  catch(e){announce('No pude copiar. Selecciona el comando y cópialo a mano.')}
});
// Dependencias: avisa si falta algo
fetch('/deps').then(r=>r.ok?r.json():null).then(d=>{
  if(!d||typeof d!=='object')return;
  const need=[['yt-dlp','falta-ytdlp','sin él no se puede descargar nada'],['ffmpeg','falta-ffmpeg','sin él no se convierte a MP3 ni se une el video con el audio']].filter(x=>d[x[0]]===false);
  if(!need.length)return;
  const n=$('dep');n.hidden=false;
  n.append(el('strong',null,need.length>1?'Faltan programas en tu equipo':'Falta un programa en tu equipo'));
  const ul=el('ul');
  need.forEach(([name,id,why])=>{
    const li=el('li'),a=el('a',null,'Cómo instalarlo');a.href='#'+id;a.onclick=e=>{e.preventDefault();openHelp(id)};
    li.append(el('b',null,name),' ('+why+'). ',a);ul.append(li);
  });
  n.append(ul);
  if(d['yt-dlp']===false){
    g.disabled=true;g.setAttribute('aria-describedby','dep');
    $('kb').textContent='Descargar se activa cuando instales yt-dlp y vuelvas a abrir el descargador.';
  }
}).catch(()=>{});
