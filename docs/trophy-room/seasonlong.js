/* Seasonlong views share the weekly source conventions and compact detail panel. */
let slData=null,slPromise=null,slScoring='native',slMetric='record',slPosition='QB',slTeamPhase='combined',slPlayerPhase='combined';
const slLabels={record:'Team Record',allplay:'All-Play Win%',total:'Total PPG',offense:'Offensive PPG',defense:'Defensive PPG',potential:'Potential PPG'};
const slPhases={regular:'Regular Season',playoffs:'Playoffs',combined:'All'};
const slRecord=r=>`${r.wins}–${r.losses}${r.ties?`–${r.ties}`:''}`;
const slPercent=n=>(n*100).toFixed(1)+'%';
const slAdjustment=r=>r&&Object.values(r).some(Boolean)?Object.entries(r).filter(([,n])=>n).map(([k,n])=>(n>0?'+':'')+n+({wins:'W',losses:'L',ties:'T'}[k])).join(' / '):'';
function slIdentity(row){return [performancePlayerName(row.name),nflTeamCode(row.nflTeam),row.position].filter(Boolean).join(' ');}
function setupSeasonlong(){
 for(const mode of ['native','current']){
  $('sl-scoring-'+mode).addEventListener('click',()=>{slScoring=mode;renderSeasonlong();});
  $('sl-scoring-'+mode).addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();slScoring=e.key==='Home'?'native':e.key==='End'?'current':slScoring==='native'?'current':'native';renderSeasonlong();$('sl-scoring-'+slScoring).focus();}});
 }
 $('sl-metric').addEventListener('change',e=>{slMetric=e.target.value;renderSeasonlong();});
 $('sl-position').addEventListener('change',e=>{slPosition=e.target.value;renderSeasonlong();});
 document.querySelectorAll('[data-sl-team-phase]').forEach(button=>button.addEventListener('click',()=>{slTeamPhase=button.dataset.slTeamPhase;renderSeasonlong();}));
 document.querySelectorAll('[data-sl-player-phase]').forEach(button=>button.addEventListener('click',()=>{slPlayerPhase=button.dataset.slPlayerPhase;renderSeasonlong();}));
 window.addEventListener('resize',()=>requestAnimationFrame(slSizeIndividual));
}
function slSizeIndividual(){
 const individual=$('sl-players'),nfc=$('sl-nfc'),afc=$('sl-afc');
 if(innerWidth<=1050){for(const node of [individual,nfc,afc]){node.style.height='';node.style.minHeight='';}return;}
 const height=Math.max(...[nfc,afc].map(node=>node.querySelector('table')?.getBoundingClientRect().height||node.scrollHeight));
 for(const node of [nfc,afc])node.style.minHeight=Math.ceil(height+2)+'px';
 individual.style.height=Math.ceil(height+2)+'px';
}
async function loadSeasonlong(){
 if(slData){renderSeasonlong();return;}
 try{slPromise??=fetch('seasonlong-performances.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('Seasonlong archive unavailable');return r.json();}).catch(e=>{slPromise=null;throw e;});slData=await slPromise;renderSeasonlong();}
 catch{$('sl-status').textContent='The seasonlong archive could not be loaded. Please reload to try again.';}
}
function slTable(rows,players=false){
 if(!rows.length)return '<p class="performance-empty">No complete eligible seasons in this view.</p>';
 const trigger=(r,content)=>`<button type="button" class="performance-trigger" data-performance-key="seasonlong:${esc(r.detail)}" aria-haspopup="dialog" aria-controls="super-bowl-lineups" aria-expanded="false" aria-label="${esc(players?slIdentity(r):r.franchise)}, ${r.year} ${esc(slPhases[players?slPlayerPhase:slTeamPhase])}. Show season breakdown">${content}</button>`;
 const value=r=>players?`${r.score.toFixed(1)}<small class="sl-player-average">${(r.average??r.score/r.games).toFixed(2)} PPG</small>`:!['record','allplay'].includes(slMetric)?r.score.toFixed(2):slMetric==='allplay'?slPercent(r.score):`${slRecord(r.record)}<small class="sl-record-parts">H2H ${slRecord(r.h2h)}<br>Bonus ${slRecord(r.bonus)}${slAdjustment(r.adjustment)?`<br>MFL adj ${slAdjustment(r.adjustment)}`:''}</small>`;
 return `<div class="table-scroll"><table class="performance-table"><thead><tr><th>Rank</th><th>${players?'Player':'Franchise'}</th><th>Season</th><th class="num">${players?'Points':slMetric==='record'?'Record':slMetric==='allplay'?'All-Play%':'PPG'}</th></tr></thead><tbody>${rows.map(r=>`<tr><td class="performance-rank">${r.tied?'T-':''}${r.rank}</td><td>${trigger(r,players?`<strong>${esc(slIdentity(r))}</strong>`:`<span class="performance-team">${logo(r.franchise)}<span><strong>${esc(r.franchise)}</strong><small>${esc(r.gm.replace(/, /g,' / '))}</small></span></span>`)}</td><td class="sl-season"><strong>${r.year}</strong>${players||slTeamPhase!=='regular'?`<small class="sl-season-context">${r.partial?'Through W'+r.throughWeek:r.games+(players?' GP':' weeks')}</small>`:''}${r.partial?'<small class="sl-partial">Partial</small>':''}</td><td class="num">${trigger(r,`<strong>${value(r)}</strong>`)}</td></tr>`).join('')}</tbody></table></div>`;
}
function renderSeasonlong(){
 if(!slData)return;closeLineups();
 const source=slData.modes[slScoring],meta=slData.meta;
 $('sl-status').textContent=`${meta.firstSeason}–${meta.completedThroughSeason??meta.throughSeason-1} completed seasons`;
 for(const mode of ['native','current']){const active=mode===slScoring;$('sl-scoring-'+mode).setAttribute('aria-selected',String(active));$('sl-scoring-'+mode).tabIndex=active?0:-1;}
 $('sl-view').setAttribute('aria-labelledby','sl-scoring-'+slScoring);
 $('sl-note').textContent=slScoring==='current'?'Earlier seasons use reconstructed estimates.':'Native Scoring uses MFL’s recorded results and each season’s scoring rules.';
 for(const conf of ['NFC','AFC']){$('sl-'+conf.toLowerCase()).innerHTML=slTable(source.teams[slTeamPhase][conf][slMetric]);$('sl-'+conf.toLowerCase()+'-phase').textContent=slPhases[slTeamPhase];}
 $('sl-players').innerHTML=slScoring==='current'&&slPosition==='KR'?'<p class="performance-empty">KR has no current-scoring equivalent. Select Native Scoring for historical returner seasons.</p>':slTable(source.positions[slPlayerPhase][slPosition],true);
 for(const kind of ['team','player'])document.querySelectorAll(`[data-sl-${kind}-phase]`).forEach(button=>button.setAttribute('aria-pressed',String(button.dataset[kind==='team'?'slTeamPhase':'slPlayerPhase']===(kind==='team'?slTeamPhase:slPlayerPhase))));
 requestAnimationFrame(slSizeIndividual);
}
function seasonlongMarkup(key){
 const d=slData?.details[key];if(!d)throw Error('Season breakdown unavailable');
 const player=d.kind==='season-player',scoring=d.mode==='native'?'Native Scoring':d.year===slData.meta.scoringYear?'Current Scoring':'Current Scoring · Reconstructed';
 const value=player?d.score.toFixed(1):!['record','allplay'].includes(d.metric)?d.score.toFixed(2):d.metric==='allplay'?slPercent(d.score):slRecord(d.record)+' · '+slPercent(d.score);
 if(!player)return seasonlongTeamMarkup(d,scoring,value);
 return seasonlongPlayerMarkup(d,scoring,value);
}

/* Team season details follow the Playoff module's chronological game/result layout. */
const slFinalRosters=new Map(),slRosterErrors=new Set();
const slOutcome=result=>`<span class="sl-game-result ${result==='W'?'sl-win':result==='L'?'sl-loss':'sl-tie'}">${esc(result||'—')}</span>`;
const slTeamCode=name=>Object.entries(teams).find(([,value])=>value===teamEntry(name))?.[0]||name;
const slGamePoints=game=>`${slOutcome(game.result)} <span class="sl-game-score">${game.score==null?'—':game.score.toFixed(1)}–${game.opponentScore==null?'—':game.opponentScore.toFixed(1)}</span>`;
function slTeamTimeline(d){
 const rows=[],isRecord=d.metric==='record',isAllPlay=d.metric==='allplay';let cumulative=0,count=0;
 for(const week of d.weeks.slice().sort((a,b)=>a.week-b.week)){
  const label=`<a href="${esc(week.url)}" target="_blank" rel="noopener">${week.week}</a>`;
  if(isRecord){
   const games=week.matchups||[],opponents=games.map(game=>`<span class="sl-game-line">${game.isHome===true?'v. ':game.isHome===false?'@ ':''}${esc(slTeamCode(game.opponent))}</span>`).join('')||'Bye';
   rows.push(`<tr><td>${label}</td><td>${opponents}</td><td class="num">${games.map(game=>`<span class="sl-game-line">${slGamePoints(game)}</span>`).join('')||'—'}</td></tr>`);
   for(const event of d.bonusEvents.filter(event=>event.end===week.week))rows.push(`<tr class="sl-bonus-event"><td>Bonus ${esc(event.label==='Regular Season'?'RS':event.label)}</td><td></td><td class="num">${slOutcome(event.result)}</td></tr>`);
  }else if(isAllPlay){
   const ap=week.allplay,comparisons=ap?ap.wins+ap.losses+ap.ties:0;
   rows.push(`<tr><td>${label}</td><td>${ap?slRecord(ap):'—'}</td><td class="num">${comparisons?slPercent((ap.wins+.5*ap.ties)/comparisons):'—'}</td></tr>`);
  }else{
   const points=week[d.metric];if(points!=null){cumulative+=Math.round(points*10);count++;}
   rows.push(`<tr><td>${label}</td><td class="num">${points?.toFixed(1)??'—'}</td><td class="num">${count?(cumulative/10/count).toFixed(2):'—'}</td></tr>`);
  }
 }
 return rows.join('');
}
function slFinalRoster(d){
 const season=slFinalRosters.get(d.year),title=d.metric==='offense'?'Final Offensive Roster':d.metric==='defense'?'Final Defensive Roster':'Final Roster';
 if(!season)return `<section class="sl-final-roster"><h3>${title}</h3><p class="performance-popup-context" role="status">${slRosterErrors.has(d.year)?'Final roster could not be loaded. Reopen this performance to try again.':'Loading final roster…'}</p></section>`;
 const markup=rosterMarkup(season,d.franchise,{positions:d.metric==='offense'?['QB','RB','WR','TE','PK','K','PN','P','KR']:d.metric==='defense'?['DT','DE','DL','LB','CB','S','DB']:null,starterStats:d.metric!=='potential'}),table=markup.slice(markup.indexOf('<div class="roster-table-scroll">'));
 return `<section class="sl-final-roster"><h3>${title}</h3>${d.mode==='current'&&d.year!==slData.meta.scoringYear?'<p class="performance-popup-context">Native season statistics</p>':''}${table}</section>`;
}
async function loadSeasonlongRoster(trigger,key){
 const d=slData?.details[key];if(!d||d.kind!=='season-team'||slFinalRosters.has(d.year))return;
 try{slFinalRosters.set(d.year,await fetchRoster(String(d.year)));slRosterErrors.delete(d.year);}
 catch{slRosterErrors.add(d.year);}
 if(lineupTrigger===trigger&&!lineupPanel.hidden){const scroll=lineupPanel.scrollTop;lineupPanel.innerHTML=seasonlongMarkup(key);placeLineups();lineupPanel.scrollTop=scroll;}
}
function seasonlongTeamMarkup(d,scoring,value){
 const isRecord=d.metric==='record',isAllPlay=d.metric==='allplay';
 const summary=isRecord?`<p class="performance-popup-context">H2H ${slRecord(d.h2h)} · Bonus ${slRecord(d.bonus)}${slAdjustment(d.adjustment)?`<br>MFL adjustment ${slAdjustment(d.adjustment)}`:''}</p>`:'';
 const pointLabel={total:'Points',offense:'Off. Points',defense:'Def. Points',potential:'Potential'}[d.metric];
 const headers=isRecord?'<th>Matchup</th><th class="num">Score</th>':isAllPlay?'<th>All-Play Record</th><th class="num">Win%</th>':`<th class="num">${pointLabel}</th><th class="num">Cum. PPG</th>`;
 const ap=isAllPlay?d.weeks.reduce((sum,w)=>{for(const k of ['wins','losses','ties'])sum[k]+=w.allplay?.[k]||0;return sum;},{wins:0,losses:0,ties:0}):null;
 const footer=isAllPlay?`<th>Total</th><td>${slRecord(ap)}</td><td class="num">${value}</td>`:`<th colspan="2">${isRecord?'Total':'PPG'}</th><td class="num">${value}</td>`;
 return `<div class="lineup-heading"><div><strong>${esc(d.franchise)}</strong><small>${d.year} · ${esc(slPhases[d.phase])} · ${esc(scoring)}</small></div></div><p class="performance-popup-context">${esc(slLabels[d.metric])} · <strong>${value}</strong>${!isRecord&&!isAllPlay?`<small class="sl-player-average">${d.games} games · ${d.weeks.reduce((sum,w)=>sum+w[d.metric],0).toFixed(1)} total points</small>`:''}</p>${summary}<table class="performance-stat-line sl-team-timeline"><thead><tr><th>Week</th>${headers}</tr></thead><tbody>${slTeamTimeline(d)}</tbody><tfoot><tr>${footer}</tr></tfoot></table><p class="performance-score-link"><a href="${esc(d.url)}" target="_blank" rel="noopener">${d.mode==='current'&&d.year!==slData.meta.scoringYear?'Original MFL season report':'MFL season report'} ↗</a></p>${slFinalRoster(d)}`;
}

/* Year shards load only when a player season is opened. */
const slPlayerBanks=new Map(),slPlayerPromises=new Map();
async function loadSeasonlongPlayerGames(trigger,key){
 const d=slData.details[key];if(slPlayerBanks.has(d.year))return;
 try{
  if(!slPlayerPromises.has(d.year))slPlayerPromises.set(d.year,fetch(`player-game-breakdowns/${d.year}.json`).then(r=>{if(!r.ok)throw Error('Player games unavailable');return r.json();}));
  slPlayerBanks.set(d.year,await slPlayerPromises.get(d.year));
 }catch{slPlayerPromises.delete(d.year);}
 if(lineupTrigger===trigger&&!lineupPanel.hidden){lineupPanel.innerHTML=seasonlongMarkup(key);placeLineups();}
}
function seasonlongPlayerMarkup(d,scoring,value){
 const bank=slPlayerBanks.get(d.year),played=d.weeks.filter(w=>w.score!==null),games=played.map(w=>bank?.games[`${w.week}:${d.playerId}`]),complete=games.every(g=>g?.[d.mode]);
 let aggregate='';
 if(complete){
  const rows=new Map();for(const g of games)for(const row of g[d.mode].rows){const key=row.eventCode==='FG'?'FG:'+row.value:row.category||row.eventCode;const old=rows.get(key)||{...row,value:0,points:0};old.value+=row.eventCode==='FG'?1:row.value;old.points=Math.round((old.points+row.points)*10)/10;rows.set(key,old);}
  const all=[...rows.values()].map(r=>({...r,event:r.eventCode==='FG'?`${r.value} Field Goals (${r.event.match(/^[\d.]+/)[0]} yd)`:`${Number(r.value.toFixed(2))} ${r.label}`}));
  const preferred=slStatOrder[d.position==='QB'?'QB':['RB','WR','TE'].includes(d.position)?'skill':['DT','DE','LB','CB','S'].includes(d.position)?'defense':'']||[];const rank=r=>{const code=r.eventCode==='#D'?'#DR':r.eventCode;return preferred.includes(code)?preferred.indexOf(code):1000+slGeneralStatOrder.indexOf(code);};all.sort((a,b)=>rank(a)-rank(b));
  const total=Math.round(all.reduce((s,r)=>s+r.points,0)*10)/10;
  aggregate=`<details class="sl-scoring-details"><summary>Season Scoring Breakdown</summary>${playerScoringMarkup({rows:all,total,reconstructed:games.some(g=>g[d.mode].reconstructed)},d.score)}</details>`;
 }
 const rows=d.weeks.map(w=>{
  const game=bank?.games[`${w.week}:${d.playerId}`],score=w.score===null?esc(w.status):w.score.toFixed(1);
  return `<tr><td>${w.week}</td><td class="num">${game?.[d.mode]?`<button class="sl-week-toggle" data-player-game-toggle aria-expanded="false" aria-label="Week ${w.week}, ${score} points. Show scoring breakdown">${score} ▸</button>`:score}</td><td class="num">${w.cumulativeAverage===null?'—':w.cumulativeAverage.toFixed(2)}</td></tr>${game?.[d.mode]?`<tr class="sl-week-details" hidden><td colspan="3">${playerScoringMarkup(game[d.mode],w.score,game.owners)}<p class="performance-score-link"><a href="${esc(w.url)}" target="_blank" rel="noopener">MFL scoring page ↗</a></p></td></tr>`:''}`;
 }).join('');
 return `<div class="lineup-heading"><div><strong>${esc(slIdentity(d))}</strong><small>${d.year} · ${esc(slPhases[d.phase])} · ${esc(scoring)}</small></div></div><p class="performance-popup-context">Total Points · <strong>${value}</strong><small class="sl-player-average">${d.average.toFixed(2)} PPG · ${d.games} GP</small></p>${complete?'':'<p class="performance-popup-context" role="status">Loading game stat lines… Reopen to retry if unavailable.</p>'}${aggregate}<p class="performance-popup-context">Select a week for its stat line.</p><table class="performance-stat-line"><thead><tr><th>Week</th><th class="num">Points</th><th class="num">Cum. Avg.</th></tr></thead><tbody>${rows}</tbody><tfoot><tr><th>Total</th><td class="num">${value}</td><td class="num">${d.average.toFixed(2)}</td></tr></tfoot></table>`;
}

const slStatOrder={"QB": ["PC", "PA", "PY", "#P", "P2", "IN", "TSK", "TSY", "RA", "RY", "#R", "R2", "FD", "FUO", "FL", "FUS", "OFC", "OFCY", "#FR", "FR"], "skill": ["RA", "RY", "#R", "R2", "CC", "TGT", "CY", "#C", "C2", "FD", "FUO", "FL", "FUS", "FUD", "OFC", "OFCY", "#FR", "FR", "FC", "FCY", "#DR", "TK", "AS", "TKL"], "defense": ["TK", "AS", "TKL", "QH", "SK", "SKY", "PD", "FF", "FC", "FCY", "#DR", "IC", "ICY", "#IR", "F", "FY"]};
const slGeneralStatOrder=["#P", "P2", "#IT", "IT", "#R", "R2", "#C", "C2", "#F", "FG", "#M", "EP", "EM", "#N", "PNY", "PI", "HBP", "FUO", "FUS", "FUD", "FL", "#DR", "FCY", "#FR", "FR", "OFC", "OFCY", "#IR", "IC", "ICY", "PD", "#BF", "BLF", "#BP", "BLP", "BLE", "TK", "AS", "FF", "FC", "QH", "SK", "SKY", "TKL", "SF", "TPA", "TYA", "D2", "SF1", "#T", "FY", "F", "PA", "PC", "PY", "IN", "TSK", "TSY", "RY", "RA", "CY", "CC", "TGT", "FD"];
