/* Public provisional standings. Official snapshots/model forecasts are untouched. */
(()=>{
 const zones=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',weekday:'short',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
 function inWindow(date=new Date()){const p=Object.fromEntries(zones.formatToParts(date).map(x=>[x.type,x.value])),m=Number(p.hour)*60+Number(p.minute);return (p.weekday==='Sun'&&m>=780&&m<=1425)||(p.weekday==='Mon'&&m>=1200&&m<=1425)}
 function clock(seconds){const n=Math.max(0,Math.round(Number(seconds)||0));return Math.floor(n/60)+':'+String(n%60).padStart(2,'0')}
 const positionOrder=['QB','RB','WR','TE','PK','PN','DT','DE','LB','CB','S'];
 const alphabet=new Intl.Collator('en',{sensitivity:'base',numeric:true});
 function sortedStarters(players){const rank=p=>{const i=positionOrder.indexOf(p.position);return i<0?99:i},name=p=>String(p.name||'').split(',').map(x=>x.trim());return [...players].sort((a,b)=>rank(a)-rank(b)||alphabet.compare(name(a)[0],name(b)[0])||alphabet.compare(name(a).slice(1).join(','),name(b).slice(1).join(','))||alphabet.compare(a.id,b.id))}
 function allPlay(teams){return Object.fromEntries(teams.map(t=>{let w=0,l=0,ties=0;for(const other of teams)if(t.id!==other.id){if(t.score>other.score)w++;else if(t.score<other.score)l++;else ties++}return [t.id,{w,l,t:ties,ap:w+ties/2}]}))}
 function standings(snapshot,seasonRace=false,projected=false){
  if(projected)snapshot={...snapshot,teams:snapshot.teams.map(t=>({...t,score:t.projectedScore??t.score,potential:'projectedPotential' in t?t.projectedPotential:t.potential}))};
  if(snapshot.teams.length!==32||new Set(snapshot.teams.map(t=>t.id)).size!==32)throw Error('Live scoring is missing teams');
  const week=snapshot.week,start=seasonRace?1:3*Math.floor((week-1)/3)+1,history=new Map(snapshot.completed.map(w=>[w.week,w.teams]));history.set(week,snapshot.teams);
  const result=snapshot.teams.map(t=>({...t,w:0,l:0,t:0,ap:0,points:0,potentialTotal:0})),byId=Object.fromEntries(result.map(t=>[t.id,t]));
  for(let w=start;w<=week;w++){
   const scores=history.get(w);if(!scores||scores.length!==32)throw Error('Completed-week carry-forward is incomplete');const ap=allPlay(scores);
   for(const t of scores){const r=byId[t.id],a=ap[t.id];r.w+=a.w;r.l+=a.l;r.t+=a.t;r.ap+=a.ap;r.points+=Math.round(t.score*1e6);r.potentialTotal=r.potentialTotal===null||t.potential===null?null:r.potentialTotal+Math.round(t.potential*1e6)}
  }
  // If any potential value is unavailable at an APW/PF tie, keep that whole tie
  // unresolved rather than inventing a franchise-ID tiebreaker.
  const incomplete=new Set(result.filter(r=>r.potentialTotal===null).map(r=>r.ap+':'+r.points));
  const compare=(a,b)=>b.ap-a.ap||b.points-a.points||(incomplete.has(a.ap+':'+a.points)?0:b.potentialTotal-a.potentialTotal);
  result.sort((a,b)=>compare(a,b)||a.id.localeCompare(b.id));
  for(const r of result){r.rank=1+result.filter(o=>compare(o,r)<0).length;r.rankEnd=r.rank+result.filter(o=>compare(o,r)===0).length-1;r.weekly=allPlay(snapshot.teams)[r.id];r.result=r.rankEnd<=15?'Win':r.rank>=16&&r.rankEnd<=17?'Tie':r.rank>=18?'Loss':'Tied at cutoff'}
  for(const r of result)r.points/=1e6;
  return {rows:result,start,week,winCutoff:(result[14].ap+result[15].ap)/2,tieCutoff:(result[16].ap+result[17].ap)/2};
 }
 if(typeof document==='undefined'){globalThis.BonusLiveWatchCore={inWindow,clock,sortedStarters,allPlay,standings};return}

 let snapshot=null,busy=false,error='',lastAttempt=-1,view='current',refreshNotice='';
 let lineupTarget=null,lineupHideTimer;
 const lineup=document.createElement('div');lineup.id='bonus-live-lineup-popup';lineup.className='gm-popup gm-live-lineup';lineup.hidden=true;lineup.setAttribute('role','dialog');lineup.setAttribute('aria-label','Starting player projections');$('bonus-design').append(lineup);
 const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const sorts={quarter:{key:'rank',dir:1},season:{key:'rank',dir:1}};
 const nf=new Intl.NumberFormat('en-US',{maximumFractionDigits:2}),stamp=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',weekday:'short',hour:'numeric',minute:'2-digit',second:'2-digit',timeZoneName:'short'});
 const schedule='Sundays 1:00–11:45 PM ET · Mondays 8:00–11:45 PM ET';
 const container=document.createElement('section');container.id='bonus-live-panels';container.hidden=true;container.setAttribute('role','tabpanel');container.setAttribute('aria-labelledby','bonus-live-tab');
 container.innerHTML='<div class="gm-toolbar"><div class="gm-conferences" role="group" aria-label="Live standings view"><button type="button" data-live-view="current" aria-pressed="true">Current</button><button type="button" data-live-view="projected" aria-pressed="false">Projected</button></div><input id="gm-live-search" class="gm-search" type="search" aria-label="Find a live team" placeholder="Find a team"></div><div class="gm-live-grid">'+['quarter','season'].map(panel=>`<section class="gm-surface gm-live-panel"><header><h3 id="live-${panel}-title"></h3><div id="live-${panel}-summary" class="gm-live-cutoffs"></div></header><div class="gm-scroll"><table class="gm-live-standings" aria-label="${panel==='quarter'?'Current quarter':'Regular Season'} live Bonus standings"><colgroup><col style="width:7%"><col style="width:37%"><col style="width:21%"><col style="width:18%"><col style="width:17%"></colgroup><thead id="live-${panel}-head"></thead><tbody id="live-${panel}-rows"></tbody></table></div></section>`).join('')+'</div>';
 $('race-view').before(container);for(const scroll of container.querySelectorAll('.gm-scroll'))scroll.addEventListener('scroll',closePopup);
 $('gm-live-search').addEventListener('input',e=>{$('search').value=e.target.value;draw()});
 function leave(){closeLineup();document.querySelector('.gm-outlook-nav').hidden=false;document.querySelector('.gm-method').hidden=false;$('download').hidden=false;$('race-view').hidden=false;container.hidden=true}
 function panelMarkup(panel){
  const isSeason=panel==='season',s=standings(snapshot,isSeason,view==='projected'),label=isSeason?'Reg Season':'Q'+Math.ceil(snapshot.week/3),cfg=sorts[panel],names=Object.fromEntries(DATA.weeks[DATA.through_week].map(t=>[t.id,t]));
  $('live-'+panel+'-title').textContent=isSeason?'Reg Season '+(view==='projected'?'Projected':'Current')+' Standings':label+' '+(view==='projected'?'Projected':'Current')+' Standings';
  $('live-'+panel+'-summary').innerHTML=`<span>Weeks ${s.start}–${s.week} · ${view==='projected'?'projected':'live'} Week ${s.week}</span><span class="gm-outcome-win">Win Cutoff <strong>${nf.format(s.winCutoff)}</strong> APW</span><span class="gm-outcome-tie">Tie Cutoff <strong>${nf.format(s.tieCutoff)}</strong> APW</span>`;
  const head=(label,key)=>`<th><button type="button" class="gm-sort-heading" data-live-panel="${panel}" data-live-sort="${key}">${label} ${cfg.key===key?(cfg.dir===1?'↑':'↓'):'↕'}</button></th>`;
  $('live-'+panel+'-head').innerHTML='<tr>'+head('Rank','rank')+head('Team','name')+head('All-Play Record','ap')+head(view==='projected'?'Proj. Points For':'Points For','points')+head(view==='projected'?'Projected Bonus':'Current Bonus','result')+'</tr>';
  let rows=s.rows.filter(t=>names[t.id].name.toLowerCase().includes($('search').value.toLowerCase()));
  const value=t=>cfg.key==='name'?names[t.id].name:cfg.key==='result'?({Win:2,Tie:1,Loss:0}[t.result]??.5):t[cfg.key];rows.sort((a,b)=>{const x=value(a),y=value(b);return cfg.dir*(typeof x==='string'?x.localeCompare(y):x-y)||a.rank-b.rank});
  $('live-'+panel+'-rows').innerHTML=rows.map(t=>`<tr data-live-team="${t.id}" class="gm-conference-row ${CONFERENCES[t.id].toLowerCase()}${((cfg.key==='rank'&&cfg.dir===1)||(cfg.key==='ap'&&cfg.dir===-1))&&(t.rank===16||t.rank===18)?' gm-live-boundary':''}"><td>${t.rankEnd>t.rank?'T-':''}${t.rank}</td><td>${liveTeam(names[t.id],panel)}<div class="gm-live-small gm-live-meta"><span>${t.playing} Live</span><span>· ${t.yet} to Play</span><span>· ${clock(t.starters?t.starters.reduce((n,p)=>n+p.seconds,0):t.seconds)} Mins Rem</span></div></td><td><strong>${t.w}-${t.l}-${t.t}</strong><div class="gm-live-small">${nf.format(t.ap)} APW</div></td><td>${Number(t.points).toFixed(1)}<div class="gm-live-small">W${s.week}: ${Number(t.score).toFixed(1)}</div></td><td class="${t.result==='Win'?'gm-outcome-win':t.result==='Tie'?'gm-outcome-tie':'gm-outcome-loss'}">${t.result}</td></tr>`).join('');
 }
 function starterMarkup(t){
  const players=sortedStarters(t.starters||[]),fmt=v=>v===null||v===undefined?'—':Number(v).toFixed(1);
  return `<div class="gm-live-lineup-title">${t.logo?`<img src="${escape(t.logo)}" alt="">`:''}<div><strong>${escape(t.name)}</strong><span>Week ${snapshot.week} · Starting Lineup</span></div></div><div class="gm-live-player-wrap"><table class="gm-live-players" aria-label="${escape(t.id)} starting players"><colgroup><col style="width:32%"><col style="width:15%"><col style="width:15%"><col style="width:19%"><col style="width:19%"></colgroup><thead><tr><th>Starter</th><th>Curr. Pts.</th><th>Min Left</th><th>Pregame Proj.</th><th>Proj. Pts.</th></tr></thead><tbody>${players.map(p=>`<tr><td>${escape(p.name)}<div class="gm-live-small">${escape(p.position)} · ${escape(p.nflTeam)}${p.pregameProjection===null?' · No FS projection':''}</div></td><td>${fmt(p.score)}</td><td>${clock(p.seconds)}</td><td>${fmt(p.pregameProjection)}</td><td><strong>${fmt(p.liveProjection)}</strong></td></tr>`).join('')}</tbody><tfoot><tr><th>Starter Total</th><td>${fmt(players.reduce((n,p)=>n+p.score,0))}</td><td></td><td>${fmt(players.reduce((n,p)=>n+(p.pregameProjection??0),0))}</td><td><strong>${fmt(t.projectedScore)}</strong></td></tr></tfoot></table></div>`;
 }
 function liveTeam(t,panel){return team(t).replace('data-team=','data-live-lineup=').replace('aria-describedby="bonus-team-popup"','aria-controls="bonus-live-lineup-popup"').replace(': show details',': show starting lineup').replace('<button ',`<button data-live-panel="${panel}" `)}
 function closeLineup(){clearTimeout(lineupHideTimer);container.querySelectorAll('[data-live-lineup][aria-expanded="true"]').forEach(b=>b.setAttribute('aria-expanded','false'));lineup.hidden=true;lineupTarget=null}
 function delayLineupClose(){clearTimeout(lineupHideTimer);lineupHideTimer=setTimeout(closeLineup,180)}
 function showLineup(id,panel){
  if(state.race!=='Live'||!snapshot)return;clearTimeout(lineupHideTimer);closePopup();
  const button=container.querySelector(`[data-live-panel="${panel}"][data-live-lineup="${id}"]`),t=snapshot.teams.find(t=>t.id===id),named=DATA.weeks[DATA.through_week].find(t=>t.id===id);if(!button||!t)return;
  container.querySelectorAll('[data-live-lineup][aria-expanded="true"]').forEach(b=>b.setAttribute('aria-expanded','false'));button.setAttribute('aria-expanded','true');lineupTarget={id,panel};
  lineup.innerHTML=starterMarkup({...t,...named,starters:t.starters,projectedScore:t.projectedScore});lineup.hidden=false;
  const box=$('bonus-design').getBoundingClientRect(),target=button.getBoundingClientRect();lineup.style.width=Math.min(480,window.innerWidth-24)+'px';lineup.style.maxHeight=Math.min(660,window.innerHeight-24)+'px';
  const bounds=lineup.getBoundingClientRect();lineup.style.left=Math.max(12,Math.min(target.right+10,window.innerWidth-bounds.width-12))-box.left+'px';lineup.style.top=Math.max(12,Math.min(target.bottom+9,window.innerHeight-bounds.height-12))-box.top+'px';
 }
 container.addEventListener('mouseover',e=>{const b=e.target.closest('[data-live-lineup]');if(b&&!b.contains(e.relatedTarget))showLineup(b.dataset.liveLineup,b.dataset.livePanel)});
 container.addEventListener('mouseout',e=>{const b=e.target.closest('[data-live-lineup]');if(b&&!b.contains(e.relatedTarget)&&!lineup.contains(e.relatedTarget))delayLineupClose()});
 container.addEventListener('focusin',e=>{const b=e.target.closest('[data-live-lineup]');if(b)showLineup(b.dataset.liveLineup,b.dataset.livePanel)});
 container.addEventListener('focusout',e=>{if(e.target.closest('[data-live-lineup]')&&!lineup.contains(e.relatedTarget))delayLineupClose()});
 lineup.addEventListener('mouseenter',()=>clearTimeout(lineupHideTimer));lineup.addEventListener('mouseleave',delayLineupClose);lineup.addEventListener('focusin',()=>clearTimeout(lineupHideTimer));lineup.addEventListener('focusout',e=>{if(!lineup.contains(e.relatedTarget))delayLineupClose()});
 document.addEventListener('keydown',e=>{if(e.key==='Escape')closeLineup()});document.addEventListener('click',e=>{if(!e.target.closest('[data-live-lineup]')&&!lineup.contains(e.target))closeLineup()});
 const repositionLineup=()=>{if(lineupTarget)showLineup(lineupTarget.id,lineupTarget.panel)};window.addEventListener('resize',repositionLineup);window.addEventListener('scroll',repositionLineup,{passive:true});for(const scroll of container.querySelectorAll('.gm-scroll'))scroll.addEventListener('scroll',closeLineup);
 function draw(){
  if(state.race!=='Live')return;closePopup();container.hidden=false;$('race-view').hidden=true;document.querySelector('.gm-outlook-nav').hidden=true;document.querySelector('.gm-method').hidden=true;$('download').hidden=true;
  document.querySelectorAll('[data-race]').forEach(b=>{const yes=b.dataset.race==='Live';b.setAttribute('aria-selected',yes);b.tabIndex=yes?0:-1});container.querySelectorAll('[data-live-view]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.liveView===view));$('gm-live-search').value=$('search').value;
  $('outlook').textContent='Live Bonus Game Watch';$('through').textContent=snapshot?'Week '+snapshot.week+' · Provisional live standings':'Current MFL live scoring';$('race-caption').textContent=schedule;$('table-guide').textContent=view==='projected'?'Live Proj. = Current Score + (Minutes Remaining ÷ 60) × Pregame Fantasy Sharks Projection.':'';
  const age=snapshot?Date.now()-Date.parse(snapshot.fetchedAt):Infinity,stale=inWindow()&&age>150000;
  $('status-dot').className='gm-dot '+(error||stale?'preliminary':snapshot?'live':'');$('status').textContent=error?(snapshot?'Could not load newer scores · showing last update':'Live feed unavailable'):busy?'Checking MFL live scores…':refreshNotice?refreshNotice+(stale?' · Waiting for newer scores':''):snapshot?(stale?'Waiting for newer scores · ':'')+'Checked '+stamp.format(new Date(snapshot.fetchedAt)):'Loading live scores…';$('status').setAttribute('aria-live','polite');
  $('race-summary').hidden=false;$('race-summary').innerHTML=`<span>Hover over a team for starter projections.</span><div class="gm-live-refresh-controls"><div class="gm-live-refresh-copy"><span>Scores are checked about once a minute during live hours. Refresh loads the latest available update; new scores may take a few minutes to appear.</span><span class="gm-live-score-age">${snapshot?'Last successful score check: '+stamp.format(new Date(snapshot.fetchedAt))+' · '+(age<60000?Math.max(0,Math.floor(age/1000))+'s':Math.floor(age/60000)+'m')+' ago'+(stale?' · Waiting for newer scores.':''):''}</span></div><button type="button" class="gm-live-refresh" data-live-refresh ${busy?'disabled aria-busy="true"':''}>${busy?'Refreshing…':'Refresh'}</button></div>`;
  if(!snapshot){$('footer').textContent='Waiting for a complete 32-team MFL live snapshot. '+schedule;return}
  panelMarkup('quarter');panelMarkup('season');if(lineupTarget)showLineup(lineupTarget.id,lineupTarget.panel);
  $('footer').textContent=(view==='projected'?'Projections finish the current week only; later weeks are not added. Missing FS projections add zero remaining points. ':'')+(snapshot.complete?'Regular-season Bonus Games complete. ':'Provisional MFL live scores; official results remain in the quarterly tabs. ')+(inWindow()&&!snapshot.complete?'Automatic refresh every minute.':'Automatic refresh paused outside live-watch hours.')+(snapshot.teams.some(t=>t.potential===null)?' An unavailable Potential tiebreaker remains tied.':' Potential tiebreakers use the currently eligible roster’s scores in the selected view.');
 }
 async function refresh(force=false){
  if(busy||(!force&&!inWindow())||state.race!=='Live')return;const minute=Math.floor(Date.now()/60000);if(!force&&minute===lastAttempt)return;lastAttempt=minute;busy=true;error='';refreshNotice='';draw();
  try{const url=`https://raw.githubusercontent.com/TheMathNinja/${DATA.league}-GM-Dashboard/live-bonus-watch/live.json?${force?'refresh='+Date.now()+'-'+Math.random().toString(36).slice(2):'minute='+minute}`;const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(20000)});if(!r.ok)throw Error('Live snapshot unavailable');const data=await r.json();if(data.league!==DATA.league||data.season!==DATA.season)throw Error('Wrong scoring season');standings(data);standings(data,true);standings(data,false,true);standings(data,true,true);const unchanged=snapshot&&JSON.stringify(snapshot.teams)===JSON.stringify(data.teams)&&JSON.stringify(snapshot.completed)===JSON.stringify(data.completed);if(snapshot&&Date.parse(data.fetchedAt)<Date.parse(snapshot.fetchedAt))throw Error('Older live snapshot received');snapshot=data;if(force)refreshNotice='Refreshed '+stamp.format(new Date())+(unchanged?' · No score changes':'')}catch(e){error=String(e.message||e)}finally{busy=false;draw()}
 }
 function renderLive(){draw();if(!snapshot)refresh(true);else refresh(false)}
 window.BonusLiveWatch={render:renderLive,leave};
 document.addEventListener('click',e=>{if(state.race!=='Live')return;const b=e.target.closest('[data-live-refresh],[data-live-sort],[data-live-view],[data-live-lineup]');if(!b)return;if(b.hasAttribute('data-live-view')){view=b.dataset.liveView;draw()}else if(b.hasAttribute('data-live-lineup')){showLineup(b.dataset.liveLineup,b.dataset.livePanel)}else if(b.hasAttribute('data-live-refresh'))refresh(true);else{const cfg=sorts[b.dataset.livePanel],key=b.dataset.liveSort;cfg.dir=key===cfg.key?-cfg.dir:key==='rank'||key==='name'?1:-1;cfg.key=key;draw()}});
 document.addEventListener('visibilitychange',()=>{if(!document.hidden&&state.race==='Live')refresh(false)});
 function tick(){if(!document.hidden&&state.race==='Live'){draw();refresh(false)}setTimeout(tick,60100-Date.now()%60000)}setTimeout(tick,60100-Date.now()%60000);
 if(state.race==='Live')renderLive();
})();
