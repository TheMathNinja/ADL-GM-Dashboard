/* Read the published Playoff report, without executing its scripts. */
(()=>{
 const root=document.getElementById('bonus-design');if(!root)return;
 const popup=document.createElement('div');popup.id='wm-strength-popup';popup.className='wm-strength-popup';popup.hidden=true;popup.setAttribute('role','tooltip');root.append(popup);
 const escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const cache=new Map();let anchor=null,timer=null,sequence=0;
 function close(){clearTimeout(timer);sequence++;if(anchor)anchor.setAttribute('aria-expanded','false');anchor=null;popup.hidden=true}
 function position(){if(!anchor?.isConnected){close();return}const r=anchor.getBoundingClientRect(),w=popup.offsetWidth,h=popup.offsetHeight;popup.style.left=Math.max(8,Math.min(innerWidth-w-8,r.right+10))+'px';popup.style.top=Math.max(8,Math.min(innerHeight-h-8,r.top))+'px'}
 function ordinal(n){const m=n%100;return n+(m>=11&&m<=13?'th':({1:'st',2:'nd',3:'rd'}[n%10]||'th'))}
 function rankInk(n,total=32){const hue=120*(total-n)/Math.max(1,total-1);return `light-dark(hsl(${hue} 65% 28%),hsl(${hue} 68% 72%))`}
 function rank(rows,t,key){const v=Number(t[key]);if(t[key]==null||!Number.isFinite(v))return null;const vals=rows.filter(r=>r[key]!=null).map(r=>Number(r[key]));return {rank:1+vals.filter(v2=>v2>v+1e-8).length,tied:vals.filter(v2=>Math.abs(v2-v)<1e-8).length>1}}
 function gamesBack(team,leader){const parse=r=>{const m=String(r??'').match(/^(\d+)-(\d+)(?:-(\d+))?$/);return m?{w:Number(m[1])+Number(m[3]||0)/2,l:Number(m[2])+Number(m[3]||0)/2}:null},a=parse(team.record),b=parse(leader?.record);return a&&b?Math.max(0,((b.w-a.w)+(a.l-b.l))/2):null}
 function markup(t,rows,through,draftRows=[]){
  const num=v=>v==null||!Number.isFinite(Number(v))?'—':Number(v).toFixed(1);
  const metric=(label,key,value)=>{const r=t.ranks?.[key]||rank(rows,t,key);return `<div class="wm-strength-row" style="--rank-ink:${r?rankInk(r.rank,rows.length):'var(--gm-muted)'}"><span>${label}</span><strong>${value}</strong><span class="wm-strength-rank">${r?(r.tied?'T-':'')+ordinal(r.rank):'—'}</span></div>`};
  const ahead=r=>Number(r.apPct)>Number(t.apPct)+1e-8||(Math.abs(Number(r.apPct)-Number(t.apPct))<1e-8&&(Number(r.pointsTotal)>Number(t.pointsTotal)+1e-8||(Math.abs(Number(r.pointsTotal)-Number(t.pointsTotal))<1e-8&&Number(r.pot)>Number(t.pot)+1e-8)));
  const teamRank=1+rows.filter(ahead).length,ink=rankInk(teamRank,rows.length);
  const draft=draftRows.find(r=>r.franchise_id===t.franchise_id||r.name===t.name),divisionId=r=>Math.floor((Number(r.franchise_id)-1)/4),divisionRank=draft?.currentDivisionRank??(1+rows.filter(r=>divisionId(r)===divisionId(t)&&Number(r.seed)<Number(t.seed)).length);
  const divisionTeams=rows.filter(r=>divisionId(r)===divisionId(t)),leader=divisionTeams.find(r=>draftRows.some(d=>(d.franchise_id===r.franchise_id||d.name===r.name)&&Number(d.currentDivisionRank)===1))||divisionTeams.reduce((a,b)=>Number(a.seed)<Number(b.seed)?a:b),gb=gamesBack(t,leader),divisionLabel=ordinal(Number(divisionRank))+(Number(divisionRank)===1?' (— GB)':gb==null?'':` (${gb} GB)`);
  const odds=t.playoffProbability==null?parseFloat(t.odds):100*Number(t.playoffProbability),seed=Number(t.seed);
  const post=(label,value,color)=>`<div class="wm-strength-post-row"><span>${label}</span><strong style="color:${color}">${value}</strong></div>`;
  return `<header><div><strong>${escape(t.name)}</strong></div>${t.logo?`<img src="${escape(t.logo)}" alt="">`:''}</header><div class="wm-strength-feature" style="--rank-ink:${ink}"><strong>${t.apPct==null?'—':(100*Number(t.apPct)).toFixed(1)+'%'}</strong><b>${ordinal(teamRank)}</b><span>All-Play</span><small>Team rank</small></div><div class="wm-strength-label"><span>Scoring</span><span>League rank</span></div>${metric('PPG','ppg',num(t.ppg))}${metric('Offensive PPG','off',num(t.off))}${metric('Defensive PPG','deff',num(t.deff))}${metric('Potential PPG','pot',num(t.pot))}<div class="wm-strength-label"><span>Postseason</span></div>${post('Division rank',divisionLabel,rankInk(Number(divisionRank),4))}${post('Seed',Number.isFinite(seed)?'#'+String(seed):'—',Number.isFinite(seed)?rankInk(seed,16):'var(--gm-muted)')}${post('Playoff odds',Number.isFinite(odds)?Math.round(odds)+'%':'—',Number.isFinite(odds)?`light-dark(hsl(${1.2*odds} 65% 28%),hsl(${1.2*odds} 68% 72%))`:'var(--gm-muted)')}`;
 }
 async function show(el){
  clearTimeout(timer);if(anchor===el&&!popup.hidden)return;close();anchor=el;el.setAttribute('aria-expanded','true');const seq=++sequence;
  const selected=Number(document.getElementById('matchup-week')?.value),through=Math.min(12,selected-1,Number(DATA.through_week));
  popup.innerHTML='<span class="wm-strength-note">Loading team strengths…</span>';popup.hidden=false;position();
  if(!(through>0)){popup.innerHTML='<span class="wm-strength-note">No current-season results before Week 1.</span>';position();return}
  const current=through===Number(DATA.through_week),file=current?'index.html':`${DATA.league}_${DATA.season}_W${String(through).padStart(2,'0')}_playoff_and_draft_forecast.html`,url='../playoff-picture/'+file;
  try{
   let saved=cache.get(url);if(!saved||Date.now()-saved.at>300000){const response=await fetch(url+'?v='+Math.floor(Date.now()/60000),{cache:'no-cache',signal:AbortSignal.timeout(15000)});if(!response.ok)throw Error('Report unavailable');const html=await response.text(),match=html.match(/const data=(\{[\s\S]*?\});const draft=/);if(!match)throw Error('Metrics unavailable');const rows=Object.values(JSON.parse(match[1])).flat(),draftMatch=html.match(/const draft=(\{[\s\S]*?\});const /),draftRows=draftMatch?Object.values(JSON.parse(draftMatch[1])).flat():[];saved={at:Date.now(),rows,draftRows};cache.set(url,saved)}
   if(seq!==sequence||anchor!==el)return;const t=saved.rows.find(t=>t.franchise_id===el.dataset.wmStrength||t.name===el.dataset.wmStrengthName);if(!t)throw Error('Team unavailable');popup.innerHTML=markup(t,saved.rows,through,saved.draftRows);position();
  }catch{if(seq===sequence){popup.innerHTML='<span class="wm-strength-note">Team strength metrics are unavailable for this outlook.</span>';position()}}
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
