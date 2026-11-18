/* Seasonlong views share the weekly source conventions and compact detail panel. */
let slData=null,slPromise=null,slScoring='native',slMetric='record',slPosition='QB',slTeamPhase='regular',slPlayerPhase='regular';
const slLabels={record:'Team Record',allplay:'All-Play Win%',total:'Total Points',offense:'Offensive Points',defense:'Defensive Points',potential:'Potential Points'};
const slPhases={regular:'Regular Season',playoffs:'Playoffs',combined:'Combined'};
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
 const value=r=>players||!['record','allplay'].includes(slMetric)?r.score.toFixed(1):slMetric==='allplay'?slPercent(r.score):`${slRecord(r.record)}<small class="sl-record-parts">H2H ${slRecord(r.h2h)}<br>Bonus ${slRecord(r.bonus)}${slAdjustment(r.adjustment)?`<br>MFL adj ${slAdjustment(r.adjustment)}`:''}</small>`;
 return `<div class="table-scroll"><table class="performance-table"><thead><tr><th>Rank</th><th>${players?'Player':'Franchise'}</th><th>Season</th><th class="num">${players?'Points':slMetric==='record'?'Record':slMetric==='allplay'?'All-Play%':'Points'}</th></tr></thead><tbody>${rows.map(r=>`<tr><td class="performance-rank">${r.tied?'T-':''}${r.rank}</td><td>${trigger(r,players?`<strong>${esc(slIdentity(r))}</strong>`:`<span class="performance-team">${logo(r.franchise)}<span><strong>${esc(r.franchise)}</strong><small>${esc(r.gm.replace(/, /g,' / '))}</small></span></span>`)}</td><td class="muted">${r.year}<small>${r.partial?'Through W'+r.throughWeek:r.games+(players?' GP':' weeks')}</small>${r.partial?'<small class="sl-partial">Partial</small>':''}</td><td class="num">${trigger(r,`<strong>${value(r)}</strong>`)}</td></tr>`).join('')}</tbody></table></div>`;
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
 let rows=d.weeks.map(r=>{
  let total=player?r.score.toFixed(1):d.metric==='record'?r.result||'—':d.metric==='allplay'?r.allplay?slPercent((r.allplay.wins+.5*r.allplay.ties)/31):'—':r[d.metric]?.toFixed(1)??'—';
  let opponent='';if(!player&&r.opponent){const entry=teamEntry(r.opponent),code=Object.entries(teams).find(([,v])=>v===entry)?.[0]||r.opponent;opponent=`<td>${esc(code)}</td>`;}else if(!player)opponent='<td>—</td>';
  return `<tr><td><a href="${esc(r.url)}" target="_blank" rel="noopener">${r.week}</a></td>${opponent}<td class="num">${total}</td></tr>`;
 }).join('');
 const bonus=!player&&d.metric==='record'?`<p class="performance-popup-context">H2H ${slRecord(d.h2h)}<br>Bonus ${slRecord(d.bonus)}${slAdjustment(d.adjustment)?`<br>MFL adjustment ${slAdjustment(d.adjustment)}`:''}</p>${d.bonusEvents.length?`<table class="performance-stat-line"><thead><tr><th>Bonus game</th><th class="num">Result</th></tr></thead><tbody>${d.bonusEvents.map(e=>`<tr><td>${esc(e.label)}</td><td class="num">${e.result}</td></tr>`).join('')}</tbody></table>`:''}${d.bonusAdjustment?'<p class="performance-popup-context">The published MFL record includes an additional adjustment matching Q4. Contemporaneous league discussion describes five bonus games. No sixth-bonus rule was found. Current Scoring excludes the recorded adjustment.</p>':''}`:'';
 return `<div class="lineup-heading"><div><strong>${esc(player?slIdentity(d):d.franchise)}</strong><small>${d.year} · ${esc(slPhases[d.phase])} · ${esc(scoring)}</small></div></div><p class="performance-popup-context">${player?'Total Points':esc(slLabels[d.metric])} · <strong>${value}</strong>${d.partial?' · Partial season through Week '+d.throughWeek:''}</p>${bonus}<table class="performance-stat-line"><thead><tr><th>Week</th>${player?'':'<th>Opponent</th>'}<th class="num">${!player&&d.metric==='record'?'Result':!player&&d.metric==='allplay'?'All-Play%':'Points'}</th></tr></thead><tbody>${rows}</tbody><tfoot><tr><th colspan="${player?1:2}">Total</th><td class="num">${value}</td></tr></tfoot></table><p class="performance-score-link"><a href="${esc(d.url)}" target="_blank" rel="noopener">${d.mode==='current'&&d.year!==slData.meta.scoringYear?'Original MFL season report':'MFL season report'} ↗</a></p>`;
}
