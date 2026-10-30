/* Read the published Playoff report, without executing its scripts. */
(()=>{
 const root=document.getElementById('bonus-design');if(!root)return;
 const popup=document.createElement('div');popup.id='wm-strength-popup';popup.className='wm-strength-popup';popup.hidden=true;popup.setAttribute('role','tooltip');root.append(popup);
 const escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const cache=new Map();let anchor=null,timer=null,sequence=0;
 function close(){clearTimeout(timer);sequence++;if(anchor)anchor.setAttribute('aria-expanded','false');anchor=null;popup.hidden=true}
 function position(){if(!anchor?.isConnected){close();return}const r=anchor.getBoundingClientRect(),w=popup.offsetWidth,h=popup.offsetHeight;popup.style.left=Math.max(8,Math.min(innerWidth-w-8,r.right+10))+'px';popup.style.top=Math.max(8,Math.min(innerHeight-h-8,r.top))+'px'}
 function rank(rows,t,key){const v=Number(t[key]);if(t[key]==null||!Number.isFinite(v))return '';const n=1+rows.filter(r=>r[key]!=null&&Number(r[key])>v+1e-8).length;return ` <small>(#${n})</small>`}
 function markup(t,rows,through){
  const num=v=>v==null||!Number.isFinite(Number(v))?'—':Number(v).toFixed(1);
  const metric=(label,key,value)=>`<div class="wm-strength-row"><span>${label}</span><strong>${value}${rank(rows,t,key)}</strong></div>`;
  return `<header>${t.logo?`<img src="${escape(t.logo)}" alt="">`:''}<div><strong>${escape(t.name)}</strong><small>Playoff report · Through Week ${through}</small></div></header><div class="wm-strength-feature"><span>Playoff odds</span><strong>${escape(t.odds??'—')}</strong></div>${metric('Points For','pointsTotal',num(t.pointsTotal))}${metric('All-Play %','apPct',t.apPct==null?'—':(100*Number(t.apPct)).toFixed(1)+'%')}${metric('PPG','ppg',num(t.ppg))}${metric('Offensive PPG','off',num(t.off))}${metric('Defensive PPG','deff',num(t.deff))}${metric('Potential PPG','pot',num(t.pot))}<div class="wm-strength-projection">${metric('Projected wins','wins',num(t.wins))}</div>`;
 }
 async function show(el){
  clearTimeout(timer);if(anchor===el&&!popup.hidden)return;close();anchor=el;el.setAttribute('aria-expanded','true');const seq=++sequence;
  const selected=Number(document.getElementById('matchup-week')?.value),through=Math.min(12,selected-1,Number(DATA.through_week));
  popup.innerHTML='<span class="wm-strength-note">Loading team strengths…</span>';popup.hidden=false;position();
  if(!(through>0)){popup.innerHTML='<span class="wm-strength-note">No current-season results before Week 1.</span>';position();return}
  const current=through===Number(DATA.through_week),file=current?'index.html':`${DATA.league}_${DATA.season}_W${String(through).padStart(2,'0')}_playoff_and_draft_forecast.html`,url='../playoff-picture/'+file;
  try{
   let saved=cache.get(url);if(!saved||Date.now()-saved.at>300000){const response=await fetch(url+'?v='+Math.floor(Date.now()/60000),{cache:'no-cache',signal:AbortSignal.timeout(15000)});if(!response.ok)throw Error('Report unavailable');const html=await response.text(),match=html.match(/const data=(\{[\s\S]*?\});const draft=/);if(!match)throw Error('Metrics unavailable');const rows=Object.values(JSON.parse(match[1])).flat();saved={at:Date.now(),rows};cache.set(url,saved)}
   if(seq!==sequence||anchor!==el)return;const t=saved.rows.find(t=>t.franchise_id===el.dataset.wmStrength||t.name===el.dataset.wmStrengthName);if(!t)throw Error('Team unavailable');popup.innerHTML=markup(t,saved.rows,through);position();
  }catch{if(seq===sequence){popup.innerHTML='<span class="wm-strength-note">Playoff strength metrics are unavailable for this outlook.</span>';position()}}
 }
 function later(){clearTimeout(timer);timer=setTimeout(close,140)}
 root.addEventListener('pointerover',e=>{const el=e.target.closest('[data-wm-strength]');if(el)show(el)});
 root.addEventListener('pointerout',e=>{if(e.target.closest('[data-wm-strength]')&&!e.relatedTarget?.closest?.('[data-wm-strength]'))later()});
 root.addEventListener('focusin',e=>{const el=e.target.closest('[data-wm-strength]');if(el)show(el)});
 root.addEventListener('focusout',e=>{if(e.target.closest('[data-wm-strength]'))later()});
 root.addEventListener('click',e=>{const el=e.target.closest('[data-wm-strength]');if(el){e.preventDefault();e.stopPropagation();show(el)}});
 popup.addEventListener('pointerenter',()=>clearTimeout(timer));popup.addEventListener('pointerleave',later);
 document.addEventListener('keydown',e=>{if(e.key==='Escape')close()});document.addEventListener('pointerdown',e=>{if(!e.target.closest('[data-wm-strength],#wm-strength-popup'))close()});
 window.addEventListener('scroll',close,true);window.addEventListener('resize',close);document.addEventListener('bonus-live-update',close);
})();
