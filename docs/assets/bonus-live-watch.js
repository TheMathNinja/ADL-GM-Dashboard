/* Public provisional standings. Official snapshots/model forecasts are untouched. */
(()=>{
 const zones=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',weekday:'short',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
 function inWindow(date=new Date()){const p=Object.fromEntries(zones.formatToParts(date).map(x=>[x.type,x.value])),m=Number(p.hour)*60+Number(p.minute);return (p.weekday==='Sun'&&m>=780&&m<=1425)||(p.weekday==='Mon'&&m>=1200&&m<=1425)}
 function allPlay(teams){return Object.fromEntries(teams.map(t=>{let w=0,l=0,ties=0;for(const other of teams)if(t.id!==other.id){if(t.score>other.score)w++;else if(t.score<other.score)l++;else ties++}return [t.id,{w,l,t:ties,ap:w+ties/2}]}))}
 function standings(snapshot,seasonRace=false){
  if(snapshot.teams.length!==32||new Set(snapshot.teams.map(t=>t.id)).size!==32)throw Error('Live scoring is missing teams');
  const week=snapshot.week,start=seasonRace?1:3*Math.floor((week-1)/3)+1,history=new Map(snapshot.completed.map(w=>[w.week,w.teams]));history.set(week,snapshot.teams);
  const result=snapshot.teams.map(t=>({...t,w:0,l:0,t:0,ap:0,points:0,potentialTotal:0})),byId=Object.fromEntries(result.map(t=>[t.id,t]));
  for(let w=start;w<=week;w++){
   const scores=history.get(w);if(!scores||scores.length!==32)throw Error('Completed-week carry-forward is incomplete');const ap=allPlay(scores);
   for(const t of scores){const r=byId[t.id],a=ap[t.id];r.w+=a.w;r.l+=a.l;r.t+=a.t;r.ap+=a.ap;r.points+=Math.round(t.score*10);r.potentialTotal=r.potentialTotal===null||t.potential===null?null:r.potentialTotal+Math.round(t.potential*10)}
  }
  // If any potential value is unavailable at an APW/PF tie, keep that whole tie
  // unresolved rather than inventing a franchise-ID tiebreaker.
  const incomplete=new Set(result.filter(r=>r.potentialTotal===null).map(r=>r.ap+':'+r.points));
  const compare=(a,b)=>b.ap-a.ap||b.points-a.points||(incomplete.has(a.ap+':'+a.points)?0:b.potentialTotal-a.potentialTotal);
  result.sort((a,b)=>compare(a,b)||a.id.localeCompare(b.id));
  for(const r of result){r.rank=1+result.filter(o=>compare(o,r)<0).length;r.rankEnd=r.rank+result.filter(o=>compare(o,r)===0).length-1;r.weekly=allPlay(snapshot.teams)[r.id];r.result=r.rankEnd<=15?'Win':r.rank>=16&&r.rankEnd<=17?'Tie':r.rank>=18?'Loss':'Tied at cutoff'}
  for(const r of result)r.points/=10;
  return {rows:result,start,week,winCutoff:(result[14].ap+result[15].ap)/2,tieCutoff:(result[16].ap+result[17].ap)/2};
 }
 if(typeof document==='undefined'){globalThis.BonusLiveWatchCore={inWindow,allPlay,standings};return}

 let snapshot=null,busy=false,error='',lastAttempt=-1;
 const sorts={quarter:{key:'rank',dir:1},season:{key:'rank',dir:1}};
 const nf=new Intl.NumberFormat('en-US',{maximumFractionDigits:2}),stamp=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',weekday:'short',hour:'numeric',minute:'2-digit',second:'2-digit',timeZoneName:'short'});
 const schedule='Sundays 1:00–11:45 PM ET · Mondays 8:00–11:45 PM ET';
 const container=document.createElement('section');container.id='bonus-live-panels';container.hidden=true;container.setAttribute('role','tabpanel');container.setAttribute('aria-labelledby','bonus-live-tab');
 container.innerHTML='<div class="gm-toolbar"><div class="gm-conferences" role="group" aria-label="Filter live teams by conference"><button type="button" data-conf="All">All</button><button type="button" data-conf="NFC">NFC</button><button type="button" data-conf="AFC">AFC</button></div><input id="gm-live-search" class="gm-search" type="search" aria-label="Find a live team" placeholder="Find a team"></div><div class="gm-live-grid">'+['quarter','season'].map(panel=>`<section class="gm-surface gm-live-panel"><header><h3 id="live-${panel}-title"></h3><div id="live-${panel}-summary" class="gm-live-cutoffs"></div></header><div class="gm-scroll"><table aria-label="${panel==='quarter'?'Current quarter':'Regular Season'} live Bonus standings"><thead id="live-${panel}-head"></thead><tbody id="live-${panel}-rows"></tbody></table></div></section>`).join('')+'</div>';
 $('race-view').before(container);for(const scroll of container.querySelectorAll('.gm-scroll'))scroll.addEventListener('scroll',closePopup);
 $('gm-live-search').addEventListener('input',e=>{$('search').value=e.target.value;draw()});
 function leave(){document.querySelector('.gm-outlook-nav').hidden=false;document.querySelector('.gm-method').hidden=false;$('download').hidden=false;$('race-view').hidden=false;container.hidden=true}
 function panelMarkup(panel){
  const isSeason=panel==='season',s=standings(snapshot,isSeason),label=isSeason?'Reg Season':'Q'+Math.ceil(snapshot.week/3),cfg=sorts[panel],names=Object.fromEntries(DATA.weeks[DATA.through_week].map(t=>[t.id,t]));
  $('live-'+panel+'-title').textContent=isSeason?'Reg Season Bonus Standings':label+' Bonus Standings';
  $('live-'+panel+'-summary').innerHTML=`<span>Weeks ${s.start}–${s.week} · includes live Week ${s.week}</span><span class="gm-outcome-win">Win Cutoff <strong>${nf.format(s.winCutoff)}</strong> APW</span><span class="gm-outcome-tie">Tie Cutoff <strong>${nf.format(s.tieCutoff)}</strong> APW</span>`;
  const head=(label,key)=>`<th><button type="button" class="gm-sort-heading" data-live-panel="${panel}" data-live-sort="${key}">${label} ${cfg.key===key?(cfg.dir===1?'↑':'↓'):'↕'}</button></th>`;
  $('live-'+panel+'-head').innerHTML='<tr>'+head('Rank','rank')+head('Team','name')+head('All-Play Record','ap')+head('Points For','points')+head('Current Bonus','result')+'</tr>';
  let rows=s.rows.filter(t=>(state.conf==='All'||CONFERENCES[t.id]===state.conf)&&names[t.id].name.toLowerCase().includes($('search').value.toLowerCase()));
  const value=t=>cfg.key==='name'?names[t.id].name:cfg.key==='result'?({Win:2,Tie:1,Loss:0}[t.result]??.5):t[cfg.key];rows.sort((a,b)=>{const x=value(a),y=value(b);return cfg.dir*(typeof x==='string'?x.localeCompare(y):x-y)||a.rank-b.rank});
  $('live-'+panel+'-rows').innerHTML=rows.map(t=>`<tr class="gm-conference-row ${CONFERENCES[t.id].toLowerCase()}${((cfg.key==='rank'&&cfg.dir===1)||(cfg.key==='ap'&&cfg.dir===-1))&&(t.rank===16||t.rank===18)?' gm-live-boundary':''}"><td>${t.rankEnd>t.rank?'T-':''}${t.rank}</td><td>${team(names[t.id])}<div class="gm-live-small">${t.yet} to play · ${t.playing} live</div></td><td><strong>${t.w}-${t.l}-${t.t}</strong><div class="gm-live-small">${nf.format(t.ap)} APW</div></td><td>${Number(t.points).toFixed(1)}<div class="gm-live-small">W${s.week}: ${Number(t.score).toFixed(1)}</div></td><td class="${t.result==='Win'?'gm-outcome-win':t.result==='Tie'?'gm-outcome-tie':'gm-outcome-loss'}">${t.result}</td></tr>`).join('');
 }
 function draw(){
  if(state.race!=='Live')return;closePopup();container.hidden=false;$('race-view').hidden=true;document.querySelector('.gm-outlook-nav').hidden=true;document.querySelector('.gm-method').hidden=true;$('download').hidden=true;
  document.querySelectorAll('[data-race]').forEach(b=>{const yes=b.dataset.race==='Live';b.setAttribute('aria-selected',yes);b.tabIndex=yes?0:-1});document.querySelectorAll('[data-conf]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.conf===state.conf));$('gm-live-search').value=$('search').value;
  $('outlook').textContent='Live Bonus Game Watch';$('through').textContent=snapshot?'Week '+snapshot.week+' · Provisional live standings':'Current MFL live scoring';$('race-caption').textContent=schedule;$('table-guide').textContent='';
  const age=snapshot?Date.now()-Date.parse(snapshot.fetchedAt):Infinity,stale=inWindow()&&age>150000;
  $('status-dot').className='gm-dot '+(error||stale?'preliminary':snapshot?'live':'');$('status').textContent=error?(snapshot?'Update delayed · retaining last scores':'Live feed unavailable'):busy?'Checking MFL live scores…':snapshot?(stale?'Delayed · ':'')+'Checked '+stamp.format(new Date(snapshot.fetchedAt)):'Loading live scores…';$('status').setAttribute('aria-live','polite');
  $('race-summary').hidden=false;$('race-summary').innerHTML='<span>Both races include the same live scores.</span><button type="button" class="gm-download" data-live-refresh '+(busy?'disabled':'')+'>Refresh</button>';
  if(!snapshot){$('footer').textContent='Waiting for a complete 32-team MFL live snapshot. '+schedule;return}
  panelMarkup('quarter');panelMarkup('season');
  $('footer').textContent=(snapshot.complete?'Regular-season Bonus Games complete. ':'Provisional MFL live scores; official results remain in the quarterly tabs. ')+(inWindow()&&!snapshot.complete?'Automatic refresh every minute.':'Automatic refresh paused outside live-watch hours.')+(snapshot.teams.some(t=>t.potential===null)?' An unavailable Potential tiebreaker remains tied.':' Live Potential tiebreakers use the currently eligible roster’s live scores.');
 }
 async function refresh(force=false){
  if(busy||(!force&&!inWindow())||state.race!=='Live')return;const minute=Math.floor(Date.now()/60000);if(!force&&minute===lastAttempt)return;lastAttempt=minute;busy=true;error='';draw();
  try{const url=`https://raw.githubusercontent.com/TheMathNinja/${DATA.league}-GM-Dashboard/live-bonus-watch/live.json?minute=${minute}`;const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(20000)});if(!r.ok)throw Error('Live snapshot unavailable');const data=await r.json();if(data.league!==DATA.league||data.season!==DATA.season)throw Error('Wrong scoring season');standings(data);standings(data,true);snapshot=data}catch(e){error=String(e.message||e)}finally{busy=false;draw()}
 }
 function renderLive(){draw();if(!snapshot)refresh(true);else refresh(false)}
 window.BonusLiveWatch={render:renderLive,leave};
 document.addEventListener('click',e=>{if(state.race!=='Live')return;const b=e.target.closest('[data-live-refresh],[data-live-sort]');if(!b)return;if(b.hasAttribute('data-live-refresh'))refresh(true);else{const cfg=sorts[b.dataset.livePanel],key=b.dataset.liveSort;cfg.dir=key===cfg.key?-cfg.dir:key==='rank'||key==='name'?1:-1;cfg.key=key;draw()}});
 document.addEventListener('visibilitychange',()=>{if(!document.hidden&&state.race==='Live')refresh(false)});
 function tick(){if(!document.hidden&&state.race==='Live'){draw();refresh(false)}setTimeout(tick,60100-Date.now()%60000)}setTimeout(tick,60100-Date.now()%60000);
 if(state.race==='Live')renderLive();
})();
