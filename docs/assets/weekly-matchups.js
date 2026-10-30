/* Published-week selection; shared Live Watch player formatting and model. */
(()=>{
 const escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const fmt=v=>v==null?'—':Number(v).toFixed(1),percent=v=>v==null?'—':(100*v).toFixed(1)+'%';
 function pairs(teams){const byId=new Map(teams.map(t=>[t.id,t])),seen=new Set(),out=[];for(const t of teams)for(const id of t.opponentIds||[]){const other=byId.get(id),key=[t.id,id].sort().join('-');if(other&&id!==t.id&&!seen.has(key)){seen.add(key);out.push([t,other])}}return out}
 function nextKickoff(teams,now=Date.now()){
  const eligible=p=>p.gameStatus==='Pregame'&&!['H','S','O','I','IR','IR-R','IR-PUP','IR-NFI','PUP','NFI'].includes(String(p.injuryStatus||'').toUpperCase())&&Number.isFinite(Number(p.kickoff))&&Number(p.kickoff)*1000>now;
  const times=teams.flatMap(t=>(t.starters||[]).filter(eligible).map(p=>Number(p.kickoff)));if(!times.length)return null;
  const at=Math.min(...times);return {at,seconds:Math.max(0,Math.ceil(at-now/1000)),counts:teams.map(t=>(t.starters||[]).filter(p=>eligible(p)&&Number(p.kickoff)===at).length)};
 }
 function kickoffClock(seconds){seconds=Math.max(0,Math.ceil(seconds));const days=Math.floor(seconds/86400),hours=Math.floor(seconds%86400/3600),minutes=Math.floor(seconds%3600/60),rest=seconds%60;return `${days?days+'d ':''}${String(hours).padStart(2,'0')}:${String(minutes).padStart(2,'0')}:${String(rest).padStart(2,'0')}`;}
 function stakeStanding(rows,id){
  const teams=new Map();for(const row of rows||[])for(const [team,value] of Object.entries(row.teamSwings||{})){if(value!=null&&Number.isFinite(Number(value)))teams.set(team,Number(value));}
  if(!teams.has(id))return null;const shift=teams.get(id),values=[...teams.values()],rounded=v=>Math.round(v*1e6)/1e6;
  return {shift,rank:1+values.filter(v=>rounded(v)>rounded(shift)).length,total:teams.size,hue:120*Math.max(0,shift)/Math.max(1e-9,...values)};
 }
 const {submissionTime,activeLineup,matchupStarted,teamAbbr}=globalThis.BonusLiveWatchCore||window.BonusLiveLineup;
 if(typeof document==='undefined'){globalThis.WeeklyMatchupsCore={pairs,submissionTime,nextKickoff,kickoffClock,activeLineup,stakeStanding,matchupStarted};return}
 const panel=document.createElement('section');panel.id='weekly-matchups';panel.hidden=true;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-label','Weekly Matchups');$('race-view').after(panel);
 let stakes={weeks:{},gamesOfTheWeek:[]};
 let manifest=null,week=null,data=null,error='',busy=false,request=0;const cache=new Map(),expanded=new Set();
 const shared=()=>window.BonusLiveLineup;
 const liveService=()=>window.BonusLiveWatch;
 const isLiveWeek=()=>week===manifest?.currentWeek&&!data?.final;
 function applyLive(){
  const live=liveService()?.getSnapshot();if(!isLiveWeek()||!shared().canOverlay(data,live))return false;
  const names=new Map(data.teams.map(t=>[t.id,t]));data={...data,fetchedAt:live.fetchedAt,liveProbabilityModel:live.liveProbabilityModel,teams:live.teams.map(t=>({...names.get(t.id),...t}))};cache.set(week,data);return true;
 }

 function matchupStakes(a,b){
  const row=(stakes.weeks?.[week]||[]).find(r=>r.teamIds.includes(a.id)&&r.teamIds.includes(b.id));
  return `<div class="wm-stakes"><button type="button" class="wm-stakes-trigger" data-wm-stakes="${a.id},${b.id}" aria-describedby="wm-stakes-popup">Playoff Percentage Points on the Line: ${row?`<strong>${fmt(row.combinedSwing)}</strong>`:'Not archived'}</button>${row?`${Number(fmt(row.combinedSwing))!==0&&row.teamSwings?` (${escape(teamAbbr(a))}: ${fmt(row.teamSwings[a.id])} | ${escape(teamAbbr(b))}: ${fmt(row.teamSwings[b.id])})`:''}`:''}</div>`;
 }
 const stakesPopup=document.createElement('div');stakesPopup.id='wm-stakes-popup';stakesPopup.className='wm-stakes-popup';stakesPopup.setAttribute('role','tooltip');stakesPopup.hidden=true;panel.parentElement.append(stakesPopup);
 let stakesAnchor=null,stakesTimer=null;
 function hideStakes(){clearTimeout(stakesTimer);stakesPopup.hidden=true;stakesAnchor=null;}
 function delayHideStakes(){clearTimeout(stakesTimer);stakesTimer=setTimeout(hideStakes,120);}
 function showStakes(anchor){
  clearTimeout(stakesTimer);stakesAnchor=anchor;
  const ids=anchor.dataset.wmStakes.split(','),row=(stakes.weeks?.[week]||[]).find(r=>ids.every(id=>r.teamIds.includes(id)));
  stakesPopup.innerHTML=`<strong class="wm-stakes-title">Playoff odds · Week ${week}</strong><table><thead><tr><th>Team</th><th>With win</th><th>With loss</th><th>Shift</th></tr></thead><tbody>${ids.map(id=>{const t=data.teams.find(t=>t.id===id),o=row?.teamPlayoffOdds?.[id],shift=o?o.ifWin-o.ifLoss:null,standing=stakeStanding(stakes.weeks?.[week],id);return `<tr><th>${t?.logo?`<img src="${escape(t.logo)}" alt="">`:''}${escape(teamAbbr(t||{id}))}</th><td>${o?fmt(o.ifWin)+'%':'—'}</td><td>${o?fmt(o.ifLoss)+'%':'—'}</td><td>${shift==null?'—':`<span class="wm-stakes-shift" style="color:light-dark(hsl(${standing?.hue||0} 65% 28%),hsl(${standing?.hue||0} 68% 72%))"${standing?` title="Weekly league rank: ${standing.rank} of ${standing.total}; largest shift first"`:''}>${fmt(shift)}${standing?` <span class="wm-stakes-rank">(#${standing.rank})</span>`:''}</span>`}</td></tr>`}).join('')}</tbody></table>${ids.every(id=>row?.teamPlayoffOdds?.[id])?'':'<small>Conditional odds were not archived for this week.</small>'}`;
  stakesPopup.hidden=false;const r=anchor.getBoundingClientRect(),w=stakesPopup.offsetWidth,h=stakesPopup.offsetHeight;
  stakesPopup.style.left=Math.max(8,Math.min(innerWidth-w-8,r.left+r.width/2-w/2))+'px';stakesPopup.style.top=Math.max(8,r.bottom+h+8<=innerHeight?r.bottom+8:r.top-h-8)+'px';
 }
 panel.addEventListener('pointerover',e=>{const a=e.target.closest('[data-wm-stakes]');if(a&&a!==stakesAnchor)showStakes(a);});
 panel.addEventListener('pointerout',e=>{if(e.target.closest('[data-wm-stakes]')&&!e.relatedTarget?.closest?.('[data-wm-stakes]'))delayHideStakes();});
 panel.addEventListener('focusin',e=>{const a=e.target.closest('[data-wm-stakes]');if(a)showStakes(a);});
 panel.addEventListener('focusout',e=>{if(e.target.closest('[data-wm-stakes]'))delayHideStakes();});
 panel.addEventListener('click',e=>{const a=e.target.closest('[data-wm-stakes]');if(a){e.preventDefault();e.stopPropagation();showStakes(a);}});
 stakesPopup.addEventListener('pointerenter',()=>clearTimeout(stakesTimer));stakesPopup.addEventListener('pointerleave',delayHideStakes);
 document.addEventListener('keydown',e=>{if(e.key==='Escape')hideStakes();});document.addEventListener('pointerdown',e=>{if(!e.target.closest('[data-wm-stakes],#wm-stakes-popup'))hideStakes();});window.addEventListener('resize',hideStakes);window.addEventListener('scroll',hideStakes,true);
 function goldStar(a,b){return stakes.gamesOfTheWeek?.some(r=>r.week===week&&[r.team_a,r.team_b].includes(a.name)&&[r.team_a,r.team_b].includes(b.name))?'<span class="wm-gotw"><svg width="15" height="15" viewBox="0 0 24 24" role="img" aria-label="Game of the Week"><path d="m12 2 3 6.3 7 .9-5.1 4.9 1.3 6.9-6.2-3.3L5.8 21l1.3-6.9L2 9.2l7-.9Z" fill="#c7911e"/></svg> Game of the Week</span>':''}
 function seasonRank(t){
  const rows=(DATA.weeks?.[String(Math.min(week-1,12))]||[]).map(t=>({id:t.id,e:(t.events||[]).find(e=>e.event==='All-Season')})).filter(t=>t.e&&t.e.elapsed>0);
  rows.sort((a,b)=>b.e.ap-a.e.ap||b.e.points-a.e.points||b.e.potential_points-a.e.potential_points);
  const ix=rows.findIndex(r=>r.id===t.id);if(ix<0)return '';
  const e=rows[ix].e,rank=1+rows.filter(r=>r.e.ap>e.ap||(r.e.ap===e.ap&&(r.e.points>e.points||(r.e.points===e.points&&r.e.potential_points>e.potential_points)))).length;
  return `<span class="wm-rank" title="${week>12?'Final regular-season':'Seasonlong'} All-Play rank${week>12?'':' entering Week '+week}; PF, then Potential Points break ties">${rank}</span>`;
 }
 function kickoffMarkup(a,b){
  if(data?.final||[a,b].some(t=>shared().teamProgress(t).playing>0))return '';const next=nextKickoff([a,b]);if(!next)return '';
  const hue=140-100*Math.min(1,next.seconds/21600),color=next.seconds>86400?'var(--gm-muted,#687386)':`light-dark(hsl(${hue} 80% 33%),hsl(${hue} 85% 72%))`;
  const when=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',weekday:'short',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(new Date(next.at*1000));
  return `<span class="wm-kickoff" style="--wm-kickoff-color:${color}" title="Scheduled NFL kickoff: ${escape(when)}. Counts include available starters, not bench players."><span>Next Kickoff: <strong>${kickoffClock(next.seconds)}</strong></span><small>${escape(teamAbbr(a))}: ${next.counts[0]} · ${escape(teamAbbr(b))}: ${next.counts[1]} starters kicking off</small></span>`;
 }
 function updateKickoffs(){if(panel.hidden||state.race!=='Matchups'||!data)return;for(const [a,b] of pairs(data.teams)){const key=[a.id,b.id].sort().join('-'),node=panel.querySelector(`[data-wm-kickoff="${key}"]`);if(node)node.innerHTML=kickoffMarkup(a,b);const card=panel.querySelector(`[data-wm-match="${key}"]`);if(card&&card.dataset.wmStarted!==String(data.final||matchupStarted([a,b]))){draw();return;}}}
 const lineupDot=t=>shared().lineupDot(t);
 function progressMarkup(t,other){
  if(data.final||!matchupStarted([t,other]))return '';const p=shared().teamProgress(t),live=shared().matchupLive([t,other]);
  return `<div class="wm-team-progress" data-wm-progress="${escape(t.id)}">${shared().activityMarkup(t,[t,other])}</div>`;
 }
 function cardTeam(t,other){
  const final=data.final,started=final||matchupStarted([t,other]),prob=(final?t.pregameMatchups:t.liveMatchups)?.[other.id],projection=final?t.pregameProjectedScore:t.projectedScore,hue=120*Math.max(0,Math.min(1,prob?.win??.5));
  return `<div class="wm-team"><div class="wm-team-heading">${seasonRank(t)}${t.logo?`<img src="${escape(t.logo)}" alt="">`:''}<div><strong>${escape(t.name)}</strong><span class="wm-muted" title="${week>12?'Regular-season record; Elo entering this week':'Record and Elo entering this week'}">${escape(t.record)} · Elo ${t.elo==null?'—':Math.round(t.elo)}</span></div></div>${progressMarkup(t,other)}<div class="wm-numbers">${started?`<strong class="wm-score"><span class="wm-projection-anchor" data-score-key="team:${t.id}" data-score-value="${fmt(t.score)}">${fmt(t.score)}${lineupDot(t)}</span><small>${final?'Final':'Points'}</small></strong>`:`<strong class="wm-score"><span class="wm-projection-anchor">${fmt(t.projectedScore)}${lineupDot(t)}</span><small>Proj. points</small></strong>`}<span>${final?'Pregame proj. '+fmt(projection):started?'Proj. points '+fmt(t.projectedScore):'Points '+fmt(t.score)}</span><span class="wm-win" style="color:light-dark(hsl(${hue} 65% 28%),hsl(${hue} 68% 72%))">${final?'Pregame win':'Win probability'} <b>${shared().probabilityText(prob?.win,!final&&shared().matchupDone([t,other]))}</b>${shared().tieMarkup(prob)}</span></div></div>`;
 }
 const lineupColumns='<colgroup><col style="width:36%"><col style="width:12%"><col style="width:24%"><col style="width:15%"><col style="width:13%"></colgroup>';
 function lineup(t){
  const players=shared().sortedStarters(t.starters||[]),bench=shared().sortedStarters(t.bench||[]),final=data.final,info=activeLineup(players);
  const rows=players.map(p=>shared().playerRowMarkup(p,fmt)).join('');
  const benchRows=bench.map(p=>shared().playerRowMarkup(p,fmt)).join('');
  return `<section class="wm-lineup" data-lineup-team="${t.id}"><h3>${t.logo?`<img src="${escape(t.logo)}" alt="">`:''}${escape(t.name)}</h3>${shared().lineupInfo(t)}<table class="gm-live-players" aria-label="${escape(t.name)} starting lineup">${lineupColumns}<thead><tr><th>Starter</th><th>Points</th><th>Mins Rem</th><th>FS Pregame Proj.</th><th>Proj. Pts.</th></tr></thead><tbody>${rows||'<tr><td colspan="5">MFL has not supplied a starting lineup yet.</td></tr>'}${Math.abs(t.scoreAdjustment||0)>.05?`<tr><td>Team scoring adjustment</td><td data-player-label="Points">${fmt(t.scoreAdjustment)}</td><td></td><td></td><td></td></tr>`:''}</tbody><tfoot><tr><th>Total Points</th><td data-player-label="Points" data-score-key="total:${t.id}" data-score-value="${fmt(t.score)}">${final?'<strong>':''}${fmt(t.score)}${final?'</strong>':''}</td><td data-player-label="Mins Rem">${shared().clock(players.reduce((n,p)=>n+(p.seconds||0),0))}</td><td data-player-label="FS Pregame Proj.">${fmt(players.reduce((n,p)=>n+(p.pregameProjection||0),0))}</td><td data-player-label="Proj. Pts."><em>${fmt(t.projectedScore)}</em></td></tr></tfoot></table><details class="wm-bench" open><summary>Bench (${bench.length})</summary><table class="gm-live-players" aria-label="${escape(t.name)} bench">${lineupColumns}<thead><tr><th>Bench</th><th>Points</th><th>Mins Rem</th><th>FS Pregame Proj.</th><th>Proj. Pts.</th></tr></thead><tbody>${benchRows||'<tr><td colspan="5">No bench players supplied for this week.</td></tr>'}</tbody>${shared().benchTotal(bench)}</table></details>${shared().projectionNotes(players.concat(bench))}</section>`;
 }
 function draw(){
  if(state.race!=='Matchups')return;
  hideStakes();shared().closeStats();closePopup();panel.hidden=false;$('race-view').hidden=true;document.querySelector('.gm-outlook-nav').hidden=true;document.querySelector('.gm-method').hidden=true;$('download').hidden=true;
  document.querySelectorAll('[data-race]').forEach(b=>{const selected=b.dataset.race==='Matchups';b.setAttribute('aria-selected',selected);b.tabIndex=selected?0:-1});
  $('outlook').textContent='Weekly Matchups';$('through').textContent=week?'Week '+week+' · '+(data?.final?'Final results':'Matchup preview & live scores'):'Loading weekly matchups…';$('race-caption').textContent='';$('race-summary').hidden=true;$('table-guide').textContent='';
  $('status-dot').className='gm-dot '+(error?'preliminary':data?.final?'official':'live');$('status').textContent=busy?'Loading matchups…':error|| (data?'Updated '+new Date(data.fetchedAt).toLocaleString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})+' ET':'');
  panel.innerHTML=`<div class="wm-toolbar"><label>Week <select id="matchup-week" aria-label="Matchup week">${(manifest?.weeks||[]).map(w=>`<option value="${w}" ${w===week?'selected':''}>Week ${w}${w===manifest.currentWeek?' · Current':''}</option>`).reverse().join('')}</select></label><span class="wm-muted">Click a matchup to see full lineups.</span><button class="gm-live-refresh" type="button" data-wm-refresh ${busy||liveService()?.getBusy()?'disabled':''}>${busy?'Loading…':'Refresh'}</button></div>${error?`<p role="alert">${escape(error)}</p>`:''}<div class="wm-grid">${data?pairs(data.teams).map(([a,b])=>{const key=[a.id,b.id].sort().join('-'),caption=data.final?'Final scores':shared().matchupCaption([a,b]),liveIndicator=caption.match(/<span class="gm-live-live-key">.*<\/span>$/)?.[0]||'',statusCaption=caption.replace(liveIndicator,'').trim();return `<details class="wm-card" data-wm-match="${key}" data-wm-started="${data.final||matchupStarted([a,b])}" ${expanded.has(week+':'+key)?'open':''}><summary><div class="wm-caption"><span>Week ${week} · ${statusCaption}</span><span class="wm-caption-center">${goldStar(a,b)}<span data-wm-kickoff="${key}">${kickoffMarkup(a,b)}</span></span><span class="wm-caption-actions">${liveIndicator}</span></div><div class="wm-preview">${cardTeam(a,b)}<span class="wm-vs">vs.</span>${cardTeam(b,a)}</div>${matchupStakes(a,b)}</summary><div class="wm-lineups">${lineup(a)}${lineup(b)}</div></details>`}).join(''):busy?'<p>Loading matchups…</p>':'<p>Matchups are unavailable. Use Refresh to try again.</p>'}</div>`;
  $('footer').textContent=data?.final?'Pregame estimates use the current calibration and historical starting lineups. Record and Elo are entering the selected week.':'Projections and probabilities use the same player model as Live Bonus Game Watch. MFL starting lineups can change before kickoff.';
  if(data&&isLiveWeek()){
   const live=liveService().getSnapshot();
   liveService().paintStatus('',data);$('race-caption').textContent=liveService().schedule;const button=panel.querySelector('[data-wm-refresh]');if(button)button.hidden=true;
   $('footer').textContent='Uses the same score snapshot and refresh process as Live Bonus Game Watch. '+(liveService().inWindow()?'Automatic refresh every minute.':'Automatic refresh paused outside live-watch hours.');
  }

 }
 async function getJSON(url){const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(20000)});if(!r.ok)throw Error('Matchup data could not be loaded');return r.json()}
 async function load(force=false){
  const seq=++request;busy=true;error='';draw();
  try{
   if(!manifest||force){const m=await getJSON('matchups/index.json?v='+Date.now());if(seq!==request)return;if(m.league!==DATA.league||m.season!==DATA.season)throw Error('Wrong matchup season');manifest=m;if(!week||!m.weeks.includes(week))week=m.currentWeek}
   try{stakes=await getJSON('matchups/stakes.json?v='+Date.now())}catch{/* Unarchived stakes remain explicitly unavailable. */}
   if(seq!==request)return;
   const chosen=week;let d=!force&&cache.get(chosen);if(!d)d=await getJSON(`matchups/week-${String(chosen).padStart(2,'0')}.json?v=${Date.now()}`);
   if(seq!==request)return;if(d.week!==chosen||d.league!==DATA.league||d.season!==DATA.season)throw Error('Wrong matchup week');
   if(seq!==request)return;cache.set(chosen,d);data=d;if(isLiveWeek()){applyLive();await liveService().refresh(force||!liveService().getSnapshot());applyLive();}
  }catch(e){if(seq===request)error=String(e.message||e)}finally{if(seq===request){busy=false;draw()}}
 }
 function playerStats(anchor){const club=data?.teams.find(t=>t.id===anchor.closest('[data-lineup-team]')?.dataset.lineupTeam);if(club)shared().showStats(anchor.dataset.liveStats,{club,anchor,snapshot:data})}
 panel.addEventListener('pointerover',e=>{const a=e.target.closest('[data-live-stats]');if(a&&!a.contains(e.relatedTarget))playerStats(a)});
 panel.addEventListener('pointerout',e=>{const a=e.target.closest('[data-live-stats]');if(a&&!a.contains(e.relatedTarget))shared().delayStatsClose()});
 panel.addEventListener('focusin',e=>{const a=e.target.closest('[data-live-stats]');if(a)playerStats(a)});
 panel.addEventListener('focusout',e=>{if(e.target.closest('[data-live-stats]'))shared().delayStatsClose()});
 panel.addEventListener('click',e=>{const a=e.target.closest('[data-live-stats]');if(a){e.preventDefault();e.stopPropagation();playerStats(a)}});
 panel.addEventListener('scroll',()=>shared().closeStats(),true);
 panel.addEventListener('change',e=>{if(e.target.id==='matchup-week'){week=Number(e.target.value);data=null;load()}});
 panel.addEventListener('click',e=>{if(e.target.closest('[data-wm-refresh]'))load(true)});
 panel.addEventListener('toggle',e=>{const key=e.target.dataset?.wmMatch;if(key){const id=week+':'+key;if(e.target.open)expanded.add(id);else expanded.delete(id)}},true);
 window.WeeklyMatchups={isLiveWeek,render(){applyLive();draw();if(!data&&!busy)load();else if(isLiveWeek())liveService().refresh(!liveService().getSnapshot())},leave(){hideStakes();shared().closeStats();panel.hidden=true}};
 setInterval(updateKickoffs,1000);
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)updateKickoffs()});
 document.addEventListener('bonus-live-update',()=>{applyLive();if(state.race==='Matchups')draw()});
 document.addEventListener('click',e=>{if(state.race==='Matchups'&&e.target.closest('[data-live-refresh]'))liveService().refresh(true)});
 if(state.race==='Matchups')window.WeeklyMatchups.render();
})();
