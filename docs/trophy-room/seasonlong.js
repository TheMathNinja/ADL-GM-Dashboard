/* Seasonlong views share the weekly source conventions and compact detail panel. */
let slData=null,slPromise=null,slScoring='native',slMetric='record',slPosition='QB',slTeamPhase='combined',slPlayerPhase='combined';
const slLabels={record:'Team Record',allplay:'All-Play Win%',total:'Total Points',offense:'Offensive Points',defense:'Defensive Points',potential:'Potential Points'};
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
 const value=r=>players?`${r.score.toFixed(1)}<small class="sl-player-average">${(r.average??r.score/r.games).toFixed(2)} PPG</small>`:!['record','allplay'].includes(slMetric)?r.score.toFixed(1):slMetric==='allplay'?slPercent(r.score):`${slRecord(r.record)}<small class="sl-record-parts">H2H ${slRecord(r.h2h)}<br>Bonus ${slRecord(r.bonus)}${slAdjustment(r.adjustment)?`<br>MFL adj ${slAdjustment(r.adjustment)}`:''}</small>`;
 return `<div class="table-scroll"><table class="performance-table"><thead><tr><th>Rank</th><th>${players?'Player':'Franchise'}</th><th>Season</th><th class="num">${players?'Points':slMetric==='record'?'Record':slMetric==='allplay'?'All-Play%':'Points'}</th></tr></thead><tbody>${rows.map(r=>`<tr><td class="performance-rank">${r.tied?'T-':''}${r.rank}</td><td>${trigger(r,players?`<strong>${esc(slIdentity(r))}</strong>`:`<span class="performance-team">${logo(r.franchise)}<span><strong>${esc(r.franchise)}</strong><small>${esc(r.gm.replace(/, /g,' / '))}</small></span></span>`)}</td><td class="sl-season"><strong>${r.year}</strong>${players||slTeamPhase!=='regular'?`<small class="sl-season-context">${r.partial?'Through W'+r.throughWeek:r.games+(players?' GP':' weeks')}</small>`:''}${r.partial?'<small class="sl-partial">Partial</small>':''}</td><td class="num">${trigger(r,`<strong>${value(r)}</strong>`)}</td></tr>`).join('')}</tbody></table></div>`;
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
 const value=player||!['record','allplay'].includes(d.metric)?d.score.toFixed(1):d.metric==='allplay'?slPercent(d.score):slRecord(d.record)+' · '+slPercent(d.score);
 if(!player)return seasonlongTeamMarkup(d,scoring,value);
 let rows=d.weeks.map(r=>{
  let total=player?(r.score===null?esc(r.status):r.score.toFixed(1)):d.metric==='record'?r.result||'—':d.metric==='allplay'?r.allplay?slPercent((r.allplay.wins+.5*r.allplay.ties)/31):'—':r[d.metric]?.toFixed(1)??'—';
  let opponent='';if(!player&&r.opponent){const entry=teamEntry(r.opponent),code=Object.entries(teams).find(([,v])=>v===entry)?.[0]||r.opponent;opponent=`<td>${esc(code)}</td>`;}else if(!player)opponent='<td>—</td>';
  return `<tr><td><a href="${esc(r.url)}" target="_blank" rel="noopener">${r.week}</a></td>${opponent}<td class="num">${total}</td>${player?`<td class="num">${r.cumulativeAverage===null?'—':r.cumulativeAverage.toFixed(2)}</td>`:''}</tr>`;
 }).join('');
 const bonus=!player&&d.metric==='record'?`<p class="performance-popup-context">H2H ${slRecord(d.h2h)}<br>Bonus ${slRecord(d.bonus)}${slAdjustment(d.adjustment)?`<br>MFL adjustment ${slAdjustment(d.adjustment)}`:''}</p>${d.bonusEvents.length?`<table class="performance-stat-line"><thead><tr><th>Bonus game</th><th class="num">Result</th></tr></thead><tbody>${d.bonusEvents.map(e=>`<tr><td>${esc(e.label)}</td><td class="num">${e.result}</td></tr>`).join('')}</tbody></table>`:''}${d.bonusAdjustment?'<p class="performance-popup-context">The published MFL record includes a separately recorded adjustment. Current Scoring uses the season’s standard bonus format.</p>':''}`:'';
 return `<div class="lineup-heading"><div><strong>${esc(player?slIdentity(d):d.franchise)}</strong><small>${d.year} · ${esc(slPhases[d.phase])} · ${esc(scoring)}</small></div></div><p class="performance-popup-context">${player?'Total Points':esc(slLabels[d.metric])} · <strong>${value}</strong>${player?`<small class="sl-player-average">${(d.average??d.score/d.games).toFixed(2)} PPG · ${d.games} GP</small>`:''}${d.partial?' · Partial season through Week '+d.throughWeek:''}</p>${bonus}<table class="performance-stat-line"><thead><tr><th>Week</th>${player?'':'<th>Opponent</th>'}<th class="num">${!player&&d.metric==='record'?'Result':!player&&d.metric==='allplay'?'All-Play%':'Points'}</th>${player?'<th class="num">Cum. Avg.</th>':''}</tr></thead><tbody>${rows}</tbody><tfoot><tr><th colspan="${player?1:2}">Total</th><td class="num">${value}</td>${player?`<td class="num">${(d.average??d.score/d.games).toFixed(2)}</td>`:''}</tr></tfoot></table><p class="performance-score-link"><a href="${esc(d.url)}" target="_blank" rel="noopener">${d.mode==='current'&&d.year!==slData.meta.scoringYear?'Original MFL season report':'MFL season report'} ↗</a></p>`;
}

/* Team season details follow the Playoff module's chronological game/result layout. */
const slFinalRosters=new Map(),slRosterErrors=new Set();
const slOutcome=result=>`<span class="sl-game-result ${result==='W'?'sl-win':result==='L'?'sl-loss':'sl-tie'}">${esc(result||'—')}</span>`;
const slTeamCode=name=>Object.entries(teams).find(([,value])=>value===teamEntry(name))?.[0]||name;
const slGamePoints=game=>`${slOutcome(game.result)} <span class="sl-game-score">${game.score==null?'—':game.score.toFixed(1)}–${game.opponentScore==null?'—':game.opponentScore.toFixed(1)}</span>`;
function slTeamTimeline(d){
 const isRecord=d.metric==='record',rows=[];
 for(const week of d.weeks.slice().sort((a,b)=>a.week-b.week)){
  const games=week.matchups||[],opponents=games.map(game=>`<span class="sl-game-line">${game.isHome===true?'v. ':game.isHome===false?'@ ':''}${esc(slTeamCode(game.opponent))}${isRecord?'':`<small>${slGamePoints(game)}</small>`}</span>`).join('')||'Bye';
  const value=isRecord?games.map(game=>`<span class="sl-game-line">${slGamePoints(game)}</span>`).join('')||'—':d.metric==='allplay'?week.allplay?slPercent((week.allplay.wins+.5*week.allplay.ties)/31):'—':week[d.metric]?.toFixed(1)??'—';
  rows.push(`<tr><td><a href="${esc(week.url)}" target="_blank" rel="noopener">${week.week}</a></td><td>${opponents}</td><td class="num">${value}</td></tr>`);
  for(const event of d.bonusEvents.filter(event=>event.end===week.week))rows.push(`<tr class="sl-bonus-event"><td>Bonus ${esc(event.label==='Regular Season'?'RS':event.label)}</td><td></td><td class="num">${slOutcome(event.result)}</td></tr>`);
 }
 return rows.join('');
}
function slFinalRoster(d){
 const season=slFinalRosters.get(d.year);
 if(!season)return `<section class="sl-final-roster"><h3>Final Roster</h3><p class="performance-popup-context" role="status">${slRosterErrors.has(d.year)?'Final roster could not be loaded. Reopen this performance to try again.':'Loading final roster…'}</p></section>`;
 const markup=rosterMarkup(season,d.franchise),table=markup.slice(markup.indexOf('<div class="roster-table-scroll">'));
 return `<section class="sl-final-roster"><h3>Final Roster</h3>${d.mode==='current'&&d.year!==slData.meta.scoringYear?'<p class="performance-popup-context">Native season statistics</p>':''}${table}</section>`;
}
async function loadSeasonlongRoster(trigger,key){
 const d=slData?.details[key];if(!d||d.kind!=='season-team'||slFinalRosters.has(d.year))return;
 try{slFinalRosters.set(d.year,await fetchRoster(String(d.year)));slRosterErrors.delete(d.year);}
 catch{slRosterErrors.add(d.year);}
 if(lineupTrigger===trigger&&!lineupPanel.hidden){const scroll=lineupPanel.scrollTop;lineupPanel.innerHTML=seasonlongMarkup(key);placeLineups();lineupPanel.scrollTop=scroll;}
}
function seasonlongTeamMarkup(d,scoring,value){
 const summary=d.metric==='record'?`<p class="performance-popup-context">H2H ${slRecord(d.h2h)} · Bonus ${slRecord(d.bonus)}${slAdjustment(d.adjustment)?`<br>MFL adjustment ${slAdjustment(d.adjustment)}`:''}</p>`:'';
 return `<div class="lineup-heading"><div><strong>${esc(d.franchise)}</strong><small>${d.year} · ${esc(slPhases[d.phase])} · ${esc(scoring)}</small></div></div><p class="performance-popup-context">${esc(slLabels[d.metric])} · <strong>${value}</strong></p>${summary}<table class="performance-stat-line sl-team-timeline"><thead><tr><th>Week</th><th>Matchup</th><th class="num">${d.metric==='record'?'Score':d.metric==='allplay'?'All-Play%':'Points'}</th></tr></thead><tbody>${slTeamTimeline(d)}</tbody><tfoot><tr><th colspan="2">Total</th><td class="num">${value}</td></tr></tfoot></table><p class="performance-score-link"><a href="${esc(d.url)}" target="_blank" rel="noopener">${d.mode==='current'&&d.year!==slData.meta.scoringYear?'Original MFL season report':'MFL season report'} ↗</a></p>${slFinalRoster(d)}`;
}
