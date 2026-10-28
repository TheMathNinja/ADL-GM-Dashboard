/* Published-week selection; shared Live Watch player formatting and model. */
(()=>{
 const escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const fmt=v=>v==null?'—':Number(v).toFixed(1),percent=v=>v==null?'—':(100*v).toFixed(1)+'%';
 function pairs(teams){const byId=new Map(teams.map(t=>[t.id,t])),seen=new Set(),out=[];for(const t of teams)for(const id of t.opponentIds||[]){const other=byId.get(id),key=[t.id,id].sort().join('-');if(other&&id!==t.id&&!seen.has(key)){seen.add(key);out.push([t,other])}}return out}
 if(typeof document==='undefined'){globalThis.WeeklyMatchupsCore={pairs};return}
 const panel=document.createElement('section');panel.id='weekly-matchups';panel.hidden=true;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-label','Weekly Matchups');$('race-view').after(panel);
 let stakes={weeks:{},gamesOfTheWeek:[]};
 let manifest=null,week=null,data=null,error='',busy=false,request=0;const cache=new Map(),expanded=new Set();
 const shared=()=>window.BonusLiveLineup;
 function matchupStakes(a,b){
  const row=(stakes.weeks?.[week]||[]).find(r=>r.teamIds.includes(a.id)&&r.teamIds.includes(b.id));
  return `<div class="wm-stakes" title="The sum of both teams’ playoff-probability changes between winning and losing this matchup, using the published email forecast.">Combined playoff probability at stake: <strong>${row?fmt(row.combinedSwing)+' percentage points · #'+row.rank+' of 16':'Not archived'}</strong>${row?.teamSwings?`<span class="wm-stakes-teams">${escape(a.name)}: <b>${fmt(row.teamSwings[a.id])} pp</b> · ${escape(b.name)}: <b>${fmt(row.teamSwings[b.id])} pp</b></span>`:''}</div>`;
 }
 function goldStar(a,b){return stakes.gamesOfTheWeek?.some(r=>r.week===week&&[r.team_a,r.team_b].includes(a.name)&&[r.team_a,r.team_b].includes(b.name))?'<span class="wm-gotw"><svg width="15" height="15" viewBox="0 0 24 24" role="img" aria-label="Game of the Week"><path d="m12 2 3 6.3 7 .9-5.1 4.9 1.3 6.9-6.2-3.3L5.8 21l1.3-6.9L2 9.2l7-.9Z" fill="#c7911e"/></svg> Game of the Week</span>':''}
 function seasonRank(t){
  const rows=(DATA.weeks?.[String(week-1)]||[]).map(t=>({id:t.id,e:(t.events||[]).find(e=>e.event==='All-Season')})).filter(t=>t.e&&t.e.elapsed>0);
  rows.sort((a,b)=>b.e.ap-a.e.ap||b.e.points-a.e.points||b.e.potential_points-a.e.potential_points);
  const ix=rows.findIndex(r=>r.id===t.id);if(ix<0)return '';
  const e=rows[ix].e,rank=1+rows.filter(r=>r.e.ap>e.ap||(r.e.ap===e.ap&&(r.e.points>e.points||(r.e.points===e.points&&r.e.potential_points>e.potential_points)))).length;
  return `<span class="wm-rank" title="Seasonlong All-Play rank entering Week ${week}; PF, then Potential Points break ties">${rank}</span>`;
 }
 function cardTeam(t,other){
  const final=data.final,prob=(final?t.pregameMatchups:t.liveMatchups)?.[other.id],projection=final?t.pregameProjectedScore:t.projectedScore,hue=120*Math.max(0,Math.min(1,prob?.win??.5));
  return `<div class="wm-team"><div class="wm-team-heading">${seasonRank(t)}${t.logo?`<img src="${escape(t.logo)}" alt="">`:''}<div><strong>${escape(t.name)}</strong><span class="wm-muted" title="Record and Elo entering this week">${escape(t.record)} · Elo ${t.elo==null?'—':Math.round(t.elo)}</span></div></div><div class="wm-numbers">${final?`<strong class="wm-score">${fmt(t.score)} <small>Final</small></strong>`:`<strong class="wm-score">${fmt(t.projectedScore)} <small>Proj. points</small></strong>`}<span>${final?'Pregame proj. '+fmt(projection):'Points '+fmt(t.score)}</span><span class="wm-win" style="color:light-dark(hsl(${hue} 65% 28%),hsl(${hue} 68% 72%))">${final?'Pregame win':'Win probability'} <b>${percent(prob?.win)}</b>${prob?.tie>=.0005?` <small>· Tie ${percent(prob.tie)}</small>`:''}</span></div></div>`;
 }
 function lineup(t){
  const players=shared().sortedStarters(t.starters||[]),bench=shared().sortedStarters(t.bench||[]),final=data.final;
  // A table cell is plain text here; the live hover owns its nested stat popup.
  const rows=players.map(p=>shared().playerRowMarkup(p,fmt).replace(/<button\b[^>]*>/g,'<span>').replace(/<\/button>/g,'</span>')).join('');
  const benchRows=bench.map(p=>shared().playerRowMarkup(p,fmt).replace(/<button\b[^>]*>/g,'<span>').replace(/<\/button>/g,'</span>')).join('');
  return `<section class="wm-lineup"><h3>${t.logo?`<img src="${escape(t.logo)}" alt="">`:''}${escape(t.name)}</h3><div class="wm-muted">${players.length} starters${players.length?'':' · No starting lineup available'}</div><table class="gm-live-players" aria-label="${escape(t.name)} starting lineup"><colgroup><col style="width:36%"><col style="width:12%"><col style="width:24%"><col style="width:15%"><col style="width:13%"></colgroup><thead><tr><th>Starter</th><th>Points</th><th>Mins Rem</th><th>FS Pregame Proj.</th><th>Proj. Pts.</th></tr></thead><tbody>${rows||'<tr><td colspan="5">MFL has not supplied a starting lineup yet.</td></tr>'}${Math.abs(t.scoreAdjustment||0)>.05?`<tr><td>Team scoring adjustment</td><td data-player-label="Points">${fmt(t.scoreAdjustment)}</td><td></td><td></td><td></td></tr>`:''}</tbody><tfoot><tr><th>Total Points</th><td data-player-label="Points">${final?'<strong>':''}${fmt(t.score)}${final?'</strong>':''}</td><td data-player-label="Mins Rem">${shared().clock(players.reduce((n,p)=>n+(p.seconds||0),0))}</td><td data-player-label="FS Pregame Proj.">${fmt(players.reduce((n,p)=>n+(p.pregameProjection||0),0))}</td><td data-player-label="Proj. Pts."><em>${fmt(t.projectedScore)}</em></td></tr></tfoot></table><details class="wm-bench" open><summary>Bench (${bench.length})</summary><table class="gm-live-players" aria-label="${escape(t.name)} bench"><thead><tr><th>Player</th><th>Points</th><th>Mins Rem</th><th>FS Pregame Proj.</th><th>Proj. Pts.</th></tr></thead><tbody>${benchRows||'<tr><td colspan="5">No bench players supplied for this week.</td></tr>'}</tbody></table></details>${players.concat(bench).some(p=>p.projectionSource==='YTD PPG')?'<p class="wm-muted">† No Fantasy Sharks projection available; using calibrated YTD PPG fallback</p>':''}</section>`;
 }
 function draw(){
  if(state.race!=='Matchups')return;
  closePopup();panel.hidden=false;$('race-view').hidden=true;document.querySelector('.gm-outlook-nav').hidden=true;document.querySelector('.gm-method').hidden=true;$('download').hidden=true;
  document.querySelectorAll('[data-race]').forEach(b=>{const selected=b.dataset.race==='Matchups';b.setAttribute('aria-selected',selected);b.tabIndex=selected?0:-1});
  $('outlook').textContent='Weekly Matchups';$('through').textContent=week?'Week '+week+' · '+(data?.final?'Final results':'Matchup preview & live scores'):'Loading weekly matchups…';$('race-caption').textContent='';$('race-summary').hidden=true;$('table-guide').textContent='';
  $('status-dot').className='gm-dot '+(error?'preliminary':data?.final?'official':'live');$('status').textContent=busy?'Loading matchups…':error|| (data?'Updated '+new Date(data.fetchedAt).toLocaleString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})+' ET':'');
  panel.innerHTML=`<div class="wm-toolbar"><label>Week <select id="matchup-week" aria-label="Matchup week">${(manifest?.weeks||[]).map(w=>`<option value="${w}" ${w===week?'selected':''}>Week ${w}${w===manifest.currentWeek?' · Current':''}</option>`).reverse().join('')}</select></label><span class="wm-muted">Click a matchup to see starters and benches.</span><button class="gm-live-refresh" type="button" data-wm-refresh ${busy?'disabled':''}>${busy?'Loading…':'Refresh'}</button></div>${error?`<p role="alert">${escape(error)}</p>`:''}<div class="wm-grid">${data?pairs(data.teams).map(([a,b])=>{const key=[a.id,b.id].sort().join('-'),caption=data.final?'Final scores':shared().matchupCaption([a,b]);return `<details class="wm-card" data-wm-match="${key}" ${expanded.has(week+':'+key)?'open':''}><summary><div class="wm-caption">Week ${week} · ${caption}${goldStar(a,b)}<span class="wm-expand">Lineups <span aria-hidden="true">⌄</span></span></div><div class="wm-preview">${cardTeam(a,b)}<span class="wm-vs">vs.</span>${cardTeam(b,a)}</div>${matchupStakes(a,b)}</summary><div class="wm-lineups">${lineup(a)}${lineup(b)}</div></details>`}).join(''):busy?'<p>Loading matchups…</p>':'<p>Matchups are unavailable. Use Refresh to try again.</p>'}</div>`;
  $('footer').textContent=data?.final?'Pregame estimates use the current calibration and historical starting lineups. Record and Elo are entering the selected week.':'Projections and probabilities use the same player model as Live Bonus Game Watch. MFL starting lineups can change before kickoff.';
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
   if(chosen===manifest.currentWeek&&!d.final){
    try{const live=await getJSON(`https://raw.githubusercontent.com/TheMathNinja/${DATA.league}-GM-Dashboard/live-bonus-watch/live.json?weekly=${Date.now()}`);if(live.week===chosen&&live.league===DATA.league&&live.season===DATA.season&&Date.parse(live.fetchedAt)>Date.parse(d.fetchedAt)){const names=new Map(d.teams.map(t=>[t.id,t]));d={...d,fetchedAt:live.fetchedAt,teams:live.teams.map(t=>({...names.get(t.id),...t}))}}}catch{/* Keep the published preview if the live relay is unavailable. */}
   }
   if(seq!==request)return;cache.set(chosen,d);data=d;
  }catch(e){if(seq===request)error=String(e.message||e)}finally{if(seq===request){busy=false;draw()}}
 }
 panel.addEventListener('change',e=>{if(e.target.id==='matchup-week'){week=Number(e.target.value);data=null;load()}});
 panel.addEventListener('click',e=>{if(e.target.closest('[data-wm-refresh]'))load(true)});
 panel.addEventListener('toggle',e=>{const key=e.target.dataset?.wmMatch;if(key){const id=week+':'+key;if(e.target.open)expanded.add(id);else expanded.delete(id)}},true);
 window.WeeklyMatchups={render(){draw();if(!data&&!busy)load()},leave(){panel.hidden=true}};
 setInterval(()=>{if(state.race==='Matchups'&&!document.hidden&&week===manifest?.currentWeek&&!busy)load(true)},60000);
 if(state.race==='Matchups')window.WeeklyMatchups.render();
})();
