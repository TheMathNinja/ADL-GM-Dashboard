const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const teams={ARI:['Arizona Cardinals','ari'],ATL:['Atlanta Falcons','atl'],BAL:['Baltimore Ravens','bal'],BUF:['Buffalo Bills','buf'],CAR:['Carolina Panthers','car'],CHI:['Chicago Bears','chi'],CIN:['Cincinnati Bengals','cin'],CLE:['Cleveland Browns','cle'],DAL:['Dallas Cowboys','dal'],DEN:['Denver Broncos','den'],DET:['Detroit Lions','det'],GBP:['Green Bay Packers','gb'],HOU:['Houston Texans','hou'],IND:['Indianapolis Colts','ind'],JAC:['Jacksonville Jaguars','jax'],KCC:['Kansas City Chiefs','kc'],LAC:['Los Angeles Chargers','lac'],LAR:['Los Angeles Rams','lar'],LVR:['Las Vegas Raiders','lv'],MIA:['Miami Dolphins','mia'],MIN:['Minnesota Vikings','min'],NEP:['New England Patriots','ne'],NOS:['New Orleans Saints','no'],NYG:['New York Giants','nyg'],NYJ:['New York Jets','nyj'],PHI:['Philadelphia Eagles','phi'],PIT:['Pittsburgh Steelers','pit'],SEA:['Seattle Seahawks','sea'],SFO:['San Francisco 49ers','sf'],TBB:['Tampa Bay Buccaneers','tb'],TEN:['Tennessee Titans','ten'],WAS:['Washington Commanders','wsh']};
const historical={'Oakland Raiders':'LVR','San Diego Chargers':'LAC','Washington Redskins':'WAS','Washington Football Team':'WAS','St. Louis Rams':'LAR'};
const teamEntry=name=>teams[name==='OAK'?'LVR':name==='NOR'?'NOS':name]||teams[historical[name]]||Object.values(teams).find(x=>x[0]===name);
function nflTeamCode(value){const code=String(value||'').toUpperCase();const aliases={LA:'LAR',STL:'LAR',SD:'LAC',SDG:'LAC',OAK:'LVR'};return aliases[code]||Object.entries(teams).find(([key,team])=>key===code||team[1].toUpperCase()===code)?.[0]||code;}
function logo(name){const t=teamEntry(name);return t?`<img src="https://a.espncdn.com/i/teamlogos/nfl/500/${t[1]}.png" alt="" loading="lazy">`:'';}
function seasonRanges(years,history=[],franchise){
 const sorted=[...new Set(years)].sort((a,b)=>a-b),ranges=[];
 const code=name=>Object.entries(teams).find(([,team])=>team===teamEntry(name))?.[0]||name;
 const displayed=code(franchise),byYear=new Map(history.map(s=>[s.year,code(s.franchise)]));
 for(let i=0;i<sorted.length;i++){
  const start=sorted[i],team=byYear.get(start);let end=start;
  while(sorted[i+1]===end+1&&byYear.get(sorted[i+1])===team)end=sorted[++i];
  ranges.push((start===end?String(start):start+'–'+end)+(team&&team!==displayed?' ('+team+')':''));
 }
 return ranges.join(', ')||'—';
}
const pct=n=>n==null?'—':(n*100).toFixed(1)+'%';
const trophy='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M7 3h10v6a5 5 0 0 1-10 0V3ZM7 5H3v3a4 4 0 0 0 5 4m9-7h4v3a4 4 0 0 1-5 4M12 14v5m-5 2h10m-8-2h6"/></svg>';
let data,status='active',sort='allTimeAllPlay',direction=-1;
function renderChampion(year){
 closeLineups();
 const c=data.champions.find(c=>c.year===+year);if(!c)return;
 $('season').value=c.year;
 const scores=c.score.split(' - ');
 $('champion-stage').innerHTML=`<div class="stage"><div><div class="winner-tag">${trophy}${c.year} Super Bowl champion</div><div class="team-line">${rosterTeam(c.champion,c.year,`${logo(c.champion)}<span><span class="team-name">${esc(c.champion)}</span><span class="team-record">${esc(c.championRecord)}</span></span>`)}</div><div class="champ-gm">GM <strong>${esc(c.gm)}</strong></div></div><button type="button" class="match-score score-trigger" data-lineup-year="${c.year}" aria-label="${c.year} Super Bowl final score: ${esc(c.score)}. Show lineups and points" aria-haspopup="dialog" aria-controls="super-bowl-lineups" aria-expanded="false"><span>Final</span><strong>${esc(scores[0])}</strong><span>—</span><strong>${esc(scores[1])}</strong></button><div class="runner"><div class="winner-tag">Super Bowl runner-up</div><div class="team-line">${rosterTeam(c.runner,c.year,`${logo(c.runner)}<span><span class="team-name">${esc(c.runner)}</span><span class="team-record">${esc(c.runnerRecord)}</span></span>`)}</div></div></div>`;
 $('award-year').textContent=c.year;
 const labels={HC:'Head Coach',OC:'Offensive Coordinator',DC:'Defensive Coordinator',GM:'General Manager'};
 $('awards').innerHTML=['NFC','AFC'].map(conf=>`<section class="conference ${conf.toLowerCase()}"><h3>${conf} AWARDS</h3><div class="award-grid">${Object.entries(labels).map(([key,label])=>{const raw=c.awards[conf+' '+key];const m=raw.match(/^(\S+)\s+\(([^)]+)\)$/);return `<div class="award"><span>${label}</span>${m?rosterTeam(m[1],c.year,`${logo(m[1])}<strong>${esc(m[1])}</strong>`):`<strong>${esc(raw)}</strong>`}<span class="award-value">${m?(key==='HC'?(Number(m[2])*100).toFixed(1)+'%':esc(m[2])):''}</span><span>${key==='HC'?'All-Play%':key==='GM'?'Potential PPG':key==='OC'?'Offensive PPG':'Defensive PPG'}</span></div>`;}).join('')}</div></section>`).join('');

 renderPayouts(c.year);
}
const money=value=>value==null?'—':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',minimumFractionDigits:Number.isInteger(value)?0:2,maximumFractionDigits:2}).format(value);
const shortAward=label=>label.replace(/Head Coach/gi,'HC').replace(/Offensive Coordinator/gi,'OC').replace(/Defensive Coordinator/gi,'DC').replace(/General Manager/gi,'GM');
function earningsRank(rows,value,key){const rank=1+rows.filter(row=>row[key]>value).length;return (rows.filter(row=>row[key]===value).length>1?'T-':'')+rank;}
function renderPayouts(year){
 const p=data.payouts.find(p=>p.year===year);
 const ranked=p.teams.slice().sort((a,b)=>b.totalEarnings-a.totalEarnings||a.franchise.localeCompare(b.franchise));
 $('payout-teams').innerHTML=ranked.map(t=>`<tr><td>${earningsRank(ranked,t.totalEarnings,'totalEarnings')}</td><td>${rosterTeam(t.franchise,year,`<span class="owner-detail">${logo(t.franchise)}<span><strong>${esc(t.franchise)}</strong><small>${esc(t.gm)}</small></span></span>`)}</td><td class="num"><strong>${money(t.totalEarnings)}</strong></td><td class="earnings-breakdown">${t.earnedBreakdown.length?t.earnedBreakdown.map(item=>`${esc(shortAward(item.label))} (${money(item.amount)})`).join(', '):''}</td></tr>`).join('');
 const winner=value=>value?`<span class="award-winners">${value.split(/\s*\/\s*/).map(code=>{const team=teamEntry(code.trim());return team?rosterTeam(code.trim(),year,`<img src="https://a.espncdn.com/i/teamlogos/nfl/500/${team[1]}.png" alt="${esc(team[0])}" title="${esc(team[0])}" loading="lazy">`):esc(code);}).join('')}</span>`:'—';
 let details=p.prizes.length?`<details class="method payout-detail"><summary>Prize Breakdown</summary><div class="surface table-scroll"><table><thead><tr><th>Prize</th><th>NFC</th><th>AFC</th><th class="num">Prize Amount</th></tr></thead><tbody>${p.prizes.map(r=>`<tr><td>${esc(shortAward(r.prize))}</td><td>${winner(r.nfc)}</td><td>${winner(r.afc)}</td><td class="num">${money(r.amount)}</td></tr>`).join('')}</tbody></table></div></details>`:'';
 if(p.periods.some(r=>r.winners.some(Boolean)))details+=`<details class="method payout-detail"><summary>Weekly &amp; Quarterly Honors</summary>${p.missingAwardCells?'<p>— indicates an unavailable value in the source sheet.</p>':''}<div class="period-honors">${['NFC','AFC'].map((conf,i)=>`<section><h3>${conf}</h3><div class="surface table-scroll"><table><thead><tr><th>Period</th><th><abbr title="Head Coach">HC</abbr></th><th><abbr title="Offensive Coordinator">OC</abbr></th><th><abbr title="Defensive Coordinator">DC</abbr></th><th><abbr title="General Manager">GM</abbr></th></tr></thead><tbody>${p.periods.map(r=>`<tr><td>${esc(r.period)}</td>${r.winners.slice(i*4,i*4+4).map(w=>`<td>${winner(w)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></section>`).join('')}</div></details>`;
 $('payout-details').innerHTML=details;
}
function rankValue(o){return sort==='owner'?o.owner:o[sort];}
function renderOwners(){
 const search=$('search').value.trim().toLowerCase(), minimum=+$('minimum').value;
 const pool=data.owners.filter(o=>(status==='all'||o.active)&&o.seasons>=minimum);
 pool.sort((a,b)=>{const x=rankValue(a),y=rankValue(b);if(x==null)return y==null?a.owner.localeCompare(b.owner):1;if(y==null)return -1;return direction*(typeof x==='string'?x.localeCompare(y):x-y)||a.owner.localeCompare(b.owner);});
 const rankKey=sort==='owner'?'allTimeAllPlay':sort;
 const ranked=pool.map(o=>({o,rank:o[rankKey]==null?'—':1+pool.filter(x=>x[rankKey]!=null&&x[rankKey]>o[rankKey]).length}));
 const filtered=ranked.filter(({o})=>`${o.owner} ${o.franchise}`.toLowerCase().includes(search));
 $('owners').innerHTML=filtered.map(({o,rank})=>`<tr class="${status==='all'&&o.active?'current-gm-row':''}"><td class="muted">${rank}</td><td><div class="owner-detail">${logo(o.franchise)}<div><button class="gm-button" style="font-weight:${o.active?700:400}" data-owner="${esc(o.owner)}" aria-haspopup="dialog">${esc(o.owner)}</button><small>${esc(o.franchise)}</small></div></div></td><td class="muted gm-years">${esc(seasonRanges(o.years,o.history,o.franchise))}</td><td class="num">${o.seasons}</td><td class="num">${o.seasons?esc(o.record):'—'}</td><td class="num"><span class="percent"><i aria-hidden="true"><b style="width:${(o.allTimeAllPlay??0)*100}%"></b></i>${pct(o.allTimeAllPlay)}</span></td></tr>`).join('')||'<tr><td colspan="6" class="empty">No GMs match these filters. Try a different name or season minimum.</td></tr>';
 $('results').textContent=`${filtered.length} of ${pool.length} GMs · ${sort==='seasons'?'Seasons played':'All-time all-play'} ranks · Ties share rank`;
 document.querySelectorAll('[data-sort]').forEach(b=>{const active=b.dataset.sort===sort;b.closest('th').setAttribute('aria-sort',active?(direction<0?'descending':'ascending'):'none');const labels={owner:'GM / Franchise',seasons:'Seasons',allTimeAllPlay:'All-Time All-Play%'};b.textContent=labels[b.dataset.sort]+(active?(direction<0?' ↓':' ↑'):'');});
}
function showCareer(name){const o=data.owners.find(o=>o.owner===name);$('career-title').textContent=o.owner;$('career-context').textContent=`${o.seasons} completed seasons · ${pct(o.allTimeAllPlay)} career all-play · Shared team seasons count once`;$('career-rows').innerHTML=o.history.slice().reverse().map(s=>`<tr><td>${s.year}</td><td>${esc(s.franchise)}</td><td>${esc(s.record)}</td><td>${pct(s.rs)}</td><td>${pct(s.all)}</td><td>${s.finish}</td></tr>`).join('')||'<tr><td colspan="6">No completed seasons in the archive.</td></tr>';$('career').showModal();}
const tabNames=['halloffame','champions','performances','seasonlong','alltime'].filter(name=>$(name)&&$(name+'-tab'));
function renderEarningsLeaderboard(){
 const franchises=new Map();
 for(const season of data.payouts)for(const team of season.teams){
  const identity=teamEntry(team.franchise),name=identity?.[0]||team.franchise;
  if(!franchises.has(name))franchises.set(name,{name,cents:0,seasons:[]});
  const row=franchises.get(name),cents=Math.round(team.totalEarnings*100);
  row.cents+=cents;row.seasons.push({year:season.year,gm:team.gm,cents});
 }
 const rows=[...franchises.values()].sort((a,b)=>b.cents-a.cents||a.name.localeCompare(b.name));
 $('alltime-earnings').innerHTML=rows.map(row=>`<tr><td>${earningsRank(rows,row.cents,'cents')}</td><td><div class="mini-team">${logo(row.name)}<strong>${esc(row.name)}</strong></div></td><td class="num"><strong>${money(row.cents/100)}</strong></td><td><details class="earnings-history"><summary>Breakdown by Season</summary><table><thead><tr><th>Season</th><th>GM</th><th class="num">Earnings</th></tr></thead><tbody>${row.seasons.sort((a,b)=>b.year-a.year).map(s=>`<tr><td>${s.year}</td><td class="earnings-gm">${esc(s.gm)}</td><td class="num">${money(s.cents/100)}</td></tr>`).join('')}</tbody></table></details></td></tr>`).join('');
}
function renderAwardCounts(){
 const categories={HC:'Head Coach of the Year',OC:'Offensive Coordinator of the Year',DC:'Defensive Coordinator of the Year',GM:'General Manager of the Year'};
 $('award-counts').innerHTML=Object.entries(categories).flatMap(([key,label])=>['NFC','AFC'].map(conf=>{
  const counts=new Map();
  for(const season of data.champions){
   const code=season.awards[conf+' '+key].split(' ')[0],entry=teamEntry(code);
   const owner=data.payouts.find(p=>p.year===season.year).teams.find(t=>teamEntry(t.franchise)?.[1]===entry?.[1]);
   if(!entry||!owner)throw new Error(`Missing award owner: ${season.year} ${conf} ${key}`);
   if(!counts.has(entry[0]))counts.set(entry[0],[]);
   counts.get(entry[0]).push({year:season.year,gm:owner.gm});
  }
  return `<section class="surface title-cabinet award-count-card"><h3>${conf} ${label}</h3>${[...counts].sort((a,b)=>b[1].length-a[1].length||b[1][0].year-a[1][0].year||a[0].localeCompare(b[0])).map(([name,wins])=>`<div class="title-row">${logo(name)}<div><strong>${esc(name)}</strong>${wins.map(w=>`<small class="title-season">${w.year} · ${esc(w.gm)}</small>`).join('')}</div><b>${wins.length}</b></div>`).join('')}</section>`;
 })).join('');
}
function selectTab(id){closeLineups();for(const name of tabNames){const selected=id===name;$(name).hidden=!selected;$(name+'-tab').setAttribute('aria-selected',String(selected));$(name+'-tab').tabIndex=selected?0:-1;}history.replaceState(null,'','#'+id);if(id==='performances')loadTopPerformances();if(id==='seasonlong')loadSeasonlong();}

let lineupPromise,lineupTrigger,lineupTimer;
const lineupPanel=document.createElement('div');
lineupPanel.id='super-bowl-lineups';lineupPanel.className='lineup-popover';lineupPanel.hidden=true;
lineupPanel.setAttribute('role','dialog');lineupPanel.setAttribute('aria-label','ADL Super Bowl lineups and points');
document.body.append(lineupPanel);
function closeLineups(){clearTimeout(lineupTimer);lineupPanel.hidden=true;if(lineupTrigger)lineupTrigger.setAttribute('aria-expanded','false');lineupTrigger=null;}
function placeLineups(){
 if(!lineupTrigger||lineupPanel.hidden)return;
 const r=lineupTrigger.getBoundingClientRect();
 if(lineupPanel.classList.contains('roster-popover')){
  // Match Playoff Picture's team popup width, side placement and 10px gap.
  const margin=10,gap=10,width=Math.min(lineupPanel.classList.contains('season-player-popover')?240:300,innerWidth-margin*2);
  lineupPanel.style.width=width+'px';
  lineupPanel.style.maxHeight=Math.max(160,Math.min(320,innerHeight-margin*2))+'px';
  const height=lineupPanel.offsetHeight;
  let left=r.right+gap;
  if(left+width>innerWidth-margin)left=r.left-width-gap;
  lineupPanel.style.left=Math.max(margin,Math.min(left,innerWidth-width-margin))+'px';
  let top=r.bottom+gap;
  if(top+height>innerHeight-margin){
   const above=r.top-height-gap;
   top=above>=margin?above:innerHeight-height-margin;
  }
  lineupPanel.style.top=Math.max(margin,Math.min(top,innerHeight-height-margin))+'px';return;
 }
 lineupPanel.style.width='';
 const width=lineupPanel.offsetWidth;
 lineupPanel.style.left=Math.max(12,Math.min(r.left+r.width/2-width/2,innerWidth-width-12))+'px';
 const below=innerHeight-r.bottom-20,above=r.top-20;
 const height=Math.min(620,Math.max(below,above),innerHeight-32);
 lineupPanel.style.maxHeight=Math.max(160,height)+'px';
 lineupPanel.style.top=(below>=Math.min(350,above)?Math.min(r.bottom+8,innerHeight-lineupPanel.offsetHeight-12):Math.max(12,r.top-lineupPanel.offsetHeight-8))+'px';
}
function lineupMarkup(game){
 const order=['QB','RB','WR','TE','PK','K','PN','P','DT','DE','DL','LB','CB','S','DB'];
 const points=n=>Number(n).toFixed(1);
 return `<div class="lineup-heading"><div><strong>${game.year} ADL Super Bowl</strong></div><button type="button" aria-label="Close lineup breakdown">×</button></div><div class="lineup-teams">${game.teams.map(team=>{
  const players=team.players.slice().sort((a,b)=>(order.indexOf(a.position)<0?99:order.indexOf(a.position))-(order.indexOf(b.position)<0?99:order.indexOf(b.position)));
  const differs=points(team.starterTotal)!==points(team.total);
  return `<section><div class="lineup-team">${logo(team.franchise)}<strong>${esc(team.franchise)}</strong><b>${points(team.total)}</b></div><table><thead><tr><th>Pos</th><th>Player</th><th class="num">Pts</th></tr></thead><tbody>${players.map(p=>`<tr><td>${esc(p.position)}</td><td>${esc(p.name.includes(', ')?p.name.split(', ').slice(1).join(' ')+' '+p.name.split(', ')[0]:p.name)}<small>${esc(nflTeamCode(p.nflTeam))}</small></td><td class="num">${points(p.points)}</td></tr>`).join('')}</tbody><tfoot><tr><th colspan="2">Starter points</th><th class="num">${points(team.starterTotal)}</th></tr></tfoot></table>${differs?`<p class="lineup-note">MFL final: ${points(team.total)}. MFL starter points sum to ${points(team.starterTotal)}. The stored matchup result differs from the individual player scores.</p>`:''}</section>`;
 }).join('')}</div>`;
}
function rosterTeam(name,year,content){
 const team=data.payouts.find(p=>p.year===+year)?.teams.find(t=>teamEntry(t.franchise)===teamEntry(name));
 if(!team)return content;
 return `<button type="button" class="roster-trigger" data-roster-year="${year}" data-roster-team="${esc(team.franchise)}" aria-label="${year} ${esc(team.franchise)} ending roster" aria-haspopup="dialog" aria-controls="super-bowl-lineups" aria-expanded="false">${content}</button>`;
}
const rosterPromises=new Map();
function rosterMarkup(season,franchise){
 const team=Object.values(season.franchises).find(t=>t.franchise===franchise);
 if(!team)throw Error('Roster unavailable');
 const order=['QB','RB','WR','TE','PK','K','PN','P','DT','DE','DL','LB','CB','S','DB'];
 const rows=team.players.map(p=>({...season.players[p.id],status:p.status})).sort((a,b)=>(order.indexOf(a.position)<0?99:order.indexOf(a.position))-(order.indexOf(b.position)<0?99:order.indexOf(b.position))||b.points-a.points||a.name.localeCompare(b.name));
 const value=n=>n==null?'—':Number(n).toFixed(1);
 const reserve=s=>s==='INJURED_RESERVE'?'IR':s==='TAXI_SQUAD'?'Taxi':'';
 return `<div class="lineup-heading"><div class="roster-heading">${logo(franchise)}<div><strong>${season.year} ${esc(franchise)}</strong><small>Final Roster</small></div></div></div><div class="roster-table-scroll"><table class="roster-stats"><thead><tr><th>Pos</th><th>Player</th><th class="num"><abbr title="Games played, including games with zero points">GP</abbr></th><th class="num">Pts</th><th class="num"><abbr title="Season points divided by games played">PPG</abbr></th><th class="num">Starter Pts</th><th class="num"><abbr title="Starter points divided by games started across all teams">Starter PPG</abbr></th></tr></thead><tbody>${rows.map(p=>`<tr><td class="roster-position">${esc(p.position)}</td><td><span class="roster-player-line"><span class="roster-player" title="${esc(p.name)}">${esc(p.name.includes(', ')?p.name.split(', ').slice(1).join(' ')+' '+p.name.split(', ')[0]:p.name)}</span><small>${esc(nflTeamCode(p.nflTeam))}${reserve(p.status)?` · ${reserve(p.status)}`:''}</small></span></td><td class="num">${p.gp}</td><td class="num">${value(p.points)}</td><td class="num">${value(p.ppg)}</td><td class="num">${value(p.starterPoints)}</td><td class="num" title="${p.starts} ${p.starts===1?'game':'games'} started">${value(p.starterPpg)}</td></tr>`).join('')}</tbody></table></div>`;
}
async function loadRoster(trigger){
 const year=trigger.dataset.rosterYear;
 if(!rosterPromises.has(year))rosterPromises.set(year,fetch(`rosters/${year}.json`,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('Roster unavailable');return r.json();}).catch(e=>{rosterPromises.delete(year);throw e;}));
 const season=await rosterPromises.get(year);
 if(lineupTrigger===trigger&&!lineupPanel.hidden){lineupPanel.innerHTML=rosterMarkup(season,trigger.dataset.rosterTeam);placeLineups();}
}

async function showLineups(trigger){
 clearTimeout(lineupTimer);
 if(lineupTrigger===trigger&&!lineupPanel.hidden)return;
 if(lineupTrigger&&lineupTrigger!==trigger)lineupTrigger.setAttribute('aria-expanded','false');
 lineupTrigger=trigger;trigger.setAttribute('aria-expanded','true');lineupPanel.hidden=false;
 const performance=trigger.hasAttribute('data-performance-key');
 lineupPanel.classList.toggle('season-player-popover',performance&&trigger.dataset.performanceKey.startsWith('seasonlong:')&&trigger.dataset.performanceKey.includes(':season-player:'));
 const roster=trigger.hasAttribute('data-roster-year');lineupPanel.classList.toggle('performance-popover',performance);lineupPanel.classList.toggle('roster-popover',roster||performance);lineupPanel.setAttribute('aria-label',roster?'Ending roster and season statistics':'ADL Super Bowl lineups and points');
 lineupPanel.innerHTML='<p class="lineup-loading" role="status">Loading ADL Super Bowl lineups…</p>';placeLineups();
 try{
  if(performance){lineupPanel.setAttribute('aria-label','Performance details');lineupPanel.innerHTML=performanceMarkup(trigger.dataset.performanceKey);placeLineups();return;}
  if(roster){lineupPanel.innerHTML='<p class="lineup-loading" role="status">Loading ending roster…</p>';await loadRoster(trigger);return;}
  lineupPromise??=fetch('lineups.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('Lineups unavailable');return r.json();}).catch(e=>{lineupPromise=null;throw e;});
  const games=await lineupPromise;
  if(lineupTrigger!==trigger||lineupPanel.hidden)return;
  const game=games[trigger.dataset.lineupYear];if(!game)throw Error('Season unavailable');
  lineupPanel.innerHTML=lineupMarkup(game);placeLineups();
 }catch(e){if(lineupTrigger===trigger){lineupPanel.innerHTML='<div class="lineup-heading"><p>The breakdown could not be loaded. Please try again.</p><button type="button" aria-label="Close lineup breakdown">×</button></div>';placeLineups();}}
}
document.addEventListener('pointerover',e=>{const trigger=e.target.closest('[data-lineup-year],[data-roster-year],[data-performance-key]');if(trigger&&!trigger.contains(e.relatedTarget))showLineups(trigger);});
document.addEventListener('pointerout',e=>{const trigger=e.target.closest('[data-lineup-year],[data-roster-year],[data-performance-key]');if(trigger&&!trigger.contains(e.relatedTarget)&&!lineupPanel.contains(e.relatedTarget))lineupTimer=setTimeout(closeLineups,250);});
document.addEventListener('focusin',e=>{const trigger=e.target.closest('[data-lineup-year],[data-roster-year],[data-performance-key]');if(trigger)showLineups(trigger);else if(!lineupPanel.contains(e.target))closeLineups();});
document.addEventListener('click',e=>{const trigger=e.target.closest('[data-lineup-year],[data-roster-year],[data-performance-key]');if(trigger)showLineups(trigger);else if(!lineupPanel.contains(e.target))closeLineups();});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!lineupPanel.hidden){e.preventDefault();const trigger=lineupTrigger;closeLineups();trigger?.focus();closeLineups();}});
lineupPanel.addEventListener('pointerenter',()=>clearTimeout(lineupTimer));
lineupPanel.addEventListener('pointerleave',()=>{if(!lineupPanel.contains(document.activeElement))lineupTimer=setTimeout(closeLineups,250);});
lineupPanel.addEventListener('click',e=>{if(e.target.closest('button')){const trigger=lineupTrigger;closeLineups();trigger?.focus();closeLineups();}});
window.addEventListener('resize',placeLineups);
window.addEventListener('scroll',e=>{if(!lineupPanel.contains(e.target))placeLineups();},true);

let topPerformanceData,topPerformancePromise,topScoring='native',topMetric='total',topPosition='QB',topConferences='separate';
const performanceLabels={total:'Total Team Points',offense:'Offensive Points',defense:'Defensive Points',potential:'Potential Points'};
const performancePositions={QB:'Quarterback',RB:'Running Back',WR:'Wide Receiver',TE:'Tight End',PK:'Kicker',PN:'Punter',KR:'Kick Returner (historical)',DT:'Defensive Tackle',DE:'Defensive End',LB:'Linebacker',CB:'Cornerback',S:'Safety'};
function performancePlayerName(name){return name.includes(', ')?name.split(', ').slice(1).join(' ')+' '+name.split(', ')[0]:name;}
function performancePlayerIdentifier(row){const detail=topPerformanceData?.details[row.detail]||row;return [performancePlayerName(row.name),nflTeamCode(detail.stats?.team||row.nflTeam), row.position||detail.position].filter(Boolean).join(' ');}
function setupTopPerformances(){
 for(const mode of ['native','current']){
  $('scoring-'+mode).addEventListener('click',()=>{topScoring=mode;renderTopPerformances();});
  $('scoring-'+mode).addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();topScoring=e.key==='Home'?'native':e.key==='End'?'current':topScoring==='native'?'current':'native';renderTopPerformances();$('scoring-'+topScoring).focus();}});
 }
 $('performance-metric').addEventListener('change',e=>{topMetric=e.target.value;closeLineups();renderTopPerformances();});
 document.querySelectorAll('[data-weekly-conferences]').forEach(button=>button.addEventListener('click',()=>{topConferences=button.dataset.weeklyConferences;renderTopPerformances();}));
 $('performance-position').addEventListener('change',e=>{topPosition=e.target.value;closeLineups();renderTopPerformances();});
}
async function loadTopPerformances(){
 if(topPerformanceData){renderTopPerformances();return;}
 try{
  topPerformancePromise??=fetch('top-performances.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('Performance archive unavailable');return r.json();}).catch(e=>{topPerformancePromise=null;throw e;});
  topPerformanceData=await topPerformancePromise;renderTopPerformances();
 }catch(error){$('performance-status').textContent='The performance archive could not be loaded. Please reload to try again.';}
}
function performanceWinningTrophy(row){
 const detail=topPerformanceData?.details[row.detail];if(detail?.kind!=='team'||detail.phase!=='playoffs')return '';
 const champion=data.champions.find(c=>c.year===row.year);if(!champion)return '';
 const week=Number(new URL(champion.source).searchParams.get('W'));
 if(row.week!==week||!(row.franchise===champion.champion||(teamEntry(row.franchise)&&teamEntry(row.franchise)===teamEntry(champion.champion))))return '';
 return '<svg class="performance-winning-trophy" viewBox="0 0 24 24" role="img" aria-label="Super Bowl-winning performance"><title>Super Bowl-winning performance</title><path d="M7 3h10v6a5 5 0 0 1-10 0V3ZM7 5H3v3a5 5 0 0 0 5 5m9-8h4v3a5 5 0 0 1-5 5M12 14v5m-4 2h8m-8-2h8v2H8z"/></svg>';
}
function performanceTable(rows,players=false){
 if(!rows.length)return '<p class="performance-empty">No qualifying games in the available data.</p>';
 const trigger=(r,content)=>`<button class="performance-trigger" type="button" data-performance-key="${esc(r.detail)}" aria-label="${esc(players?performancePlayerIdentifier(r):r.franchise)}, ${r.year} Week ${r.week}, ${r.score.toFixed(1)} points. Show performance details" aria-haspopup="dialog" aria-controls="super-bowl-lineups" aria-expanded="false">${content}</button>`;
 return `<div class="table-scroll"><table class="performance-table"><thead><tr><th>Rank</th><th>${players?'Player':'Franchise'}</th><th>Season</th><th class="num">Points</th></tr></thead><tbody>${rows.map(r=>`<tr><td class="performance-rank">${r.tied?'T-':''}${r.rank}</td><td>${trigger(r,players?`<strong>${esc(performancePlayerIdentifier(r))}</strong>`:`<span class="performance-team">${logo(r.franchise)}<span><strong>${esc(r.franchise)}${performanceWinningTrophy(r)}</strong><small>${esc(r.gm.replace(/, /g,' / '))}</small></span></span>`)}</td><td class="muted">${r.year}<small>Week ${r.week}</small></td><td class="num">${trigger(r,`<strong>${r.score.toFixed(1)}</strong>`)}</td></tr>`).join('')}</tbody></table></div>`;
}
function combinedWeeklyTeams(teams,metric){
 // Each conference already retains its top ten and all cutoff ties, sufficient for a league top ten.
 const rows=[...teams.NFC[metric],...teams.AFC[metric]].map(row=>({...row})).sort((a,b)=>Math.round(b.score*10)-Math.round(a.score*10)||a.year-b.year||a.week-b.week||a.franchise.localeCompare(b.franchise));
 const counts=new Map();for(const row of rows){const score=Math.round(row.score*10);counts.set(score,(counts.get(score)||0)+1);}
 let rank=0,previous=null;return rows.map((row,index)=>{const score=Math.round(row.score*10);if(score!==previous)rank=index+1;previous=score;return {...row,rank,tied:counts.get(score)>1};}).filter(row=>row.rank<=10);
}
function renderTopPerformances(){
 if(!topPerformanceData)return;
 closeLineups();
 const source=topPerformanceData.modes[topScoring],meta=topPerformanceData.meta;
 for(const mode of ['native','current']){const active=topScoring===mode;$('scoring-'+mode).setAttribute('aria-selected',String(active));$('scoring-'+mode).tabIndex=active?0:-1;}
 $('performance-view').setAttribute('aria-labelledby','scoring-'+topScoring);
 $('performance-status').textContent=`${meta.firstSeason}–${meta.throughSeason-1} completed seasons · ${meta.throughSeason} through Week ${meta.throughWeek}`;
 const together=topConferences==='together',nfcPane=$('performance-nfc').closest('.performance-pane');
 nfcPane.classList.toggle('weekly-combined-pane',together);$('performance-afc').closest('.performance-pane').hidden=together;
 $('performance-nfc-title').textContent=together?'ADL':'NFC';
 document.querySelectorAll('[data-weekly-conferences]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.weeklyConferences===topConferences)));
 for(const conf of ['AFC','NFC'])$('performance-'+conf.toLowerCase()).innerHTML=['regular','playoffs'].map(phase=>`${phase==='playoffs'?'<h3 class="performance-playoff-title">Playoffs</h3>':''}<section class="surface performance-card">${performanceTable(together&&conf==='NFC'?combinedWeeklyTeams(source.teams[phase],topMetric):source.teams[phase][conf][topMetric])}</section>`).join('');
 $('performance-players').innerHTML=topScoring==='current'&&topPosition==='KR'?'<p class="performance-empty">KR was a historical roster position with no 2026 scoring equivalent. Select Native Scoring to view kick-returner records.</p>':performanceTable(source.positions[topPosition],true);


 const coverage=meta.coverage,counts=[];
 if(topScoring==='current'){
  for(const phase of ['regular','playoffs']){
   const rows=['NFC','AFC'].map(c=>coverage[`current:${phase}:${c}:${topMetric}`]).filter(Boolean),eligible=rows.reduce((a,r)=>a+r.eligible,0),covered=rows.reduce((a,r)=>a+r.covered,0);
   if(covered<eligible)counts.push(`${phase==='regular'?'regular-season':'playoff'} team coverage ${covered.toLocaleString()} / ${eligible.toLocaleString()}`);
  }
  const p=coverage['current:player:'+topPosition];if(p&&p.covered<p.eligible)counts.push(`${topPosition} game coverage ${p.covered.toLocaleString()} / ${p.eligible.toLocaleString()}`);
 }
 $('performance-scoring-note').textContent=topScoring==='native'?'Native Scoring uses MFL’s recorded results and the scoring rules from each season.':'Earlier seasons use reconstructed estimates.';
 $('performance-position').value=topPosition;
}
function performanceMarkup(key){
 if(key.startsWith('seasonlong:'))return seasonlongMarkup(key.slice(11));
 const d=topPerformanceData?.details[key];if(!d)throw Error('Performance unavailable');
 const scoring=d.mode==='native'?'Native Scoring':d.year===topPerformanceData.meta.scoringYear?'Current Scoring':'Current Scoring · Reconstructed';
 let body='';
 if(d.kind==='team'){
  const rows=d.players.slice().sort((a,b)=>Object.keys(performancePositions).indexOf(a.position)-Object.keys(performancePositions).indexOf(b.position)||b.score-a.score);
  body=`<p class="performance-popup-context">${esc(performanceLabels[d.metric])} · <strong>${d.score.toFixed(1)}</strong>${d.opponent?`<br>vs ${esc(d.opponent)}`:''}</p><table class="performance-lineup"><thead><tr><th>Pos</th><th>${d.metric==='potential'?'Optimal lineup':'Starters'}</th><th class="num">Pts</th></tr></thead><tbody>${rows.map(p=>`<tr><td>${esc(p.position)}</td><td>${esc(performancePlayerName(p.name))}<small>${esc(nflTeamCode(p.nflTeam))}</small></td><td class="num">${p.score.toFixed(1)}</td></tr>`).join('')}</tbody></table>${Math.round(d.playerSum*10)!==Math.round(d.score*10)?`<p class="performance-popup-context">MFL stored total: ${d.score.toFixed(1)}. Listed player points: ${d.playerSum.toFixed(1)}.</p>`:''}`;
 }else{
  const scoring=d.scoring||{rows:[{event:'Published total (event details not supplied)',points:d.score}],total:d.score,referenceOnly:true};
  body=`<p class="performance-popup-context">${esc(d.position)}${d.stats?.team?` · ${esc(nflTeamCode(d.stats.team))} vs ${esc(nflTeamCode(d.stats.opponent))}`:''}</p><table class="performance-stat-line" aria-label="Game scoring breakdown"><thead><tr><th>Event</th><th class="num">Points</th></tr></thead><tbody>${scoring.rows.map(row=>`<tr><td>${esc(row.event)}</td><td class="num">${row.points.toFixed(1)}</td></tr>`).join('')}</tbody><tfoot><tr><th>Total</th><td class="num">${scoring.total.toFixed(1)}</td></tr></tfoot></table>${scoring.referenceOnly?'<p class="performance-popup-context">Event details were not supplied; only the recorded total is available.</p>':scoring.reconstructed?'<p class="performance-popup-context">Reconstructed scoring breakdown.</p>':''}${Math.abs(scoring.total-d.score)>.05?`<p class="performance-popup-context">The scoring events total ${scoring.total.toFixed(1)}; MFL’s published total is ${d.score.toFixed(1)}. The ranking preserves the published total.</p>`:''}<p class="performance-popup-context">${d.startedBy.length?'Started by '+esc(d.startedBy.join(' / ')):'Not started by a league team that week.'}</p>`;
 }
 return `<div class="lineup-heading"><div><strong>${esc(d.kind==='team'?d.franchise:performancePlayerName(d.name))}</strong><small>${d.year} · Week ${d.week} · ${esc(scoring)}</small></div></div><p class="performance-score-link"><a href="${esc(d.url)}" target="_blank" rel="noopener">${d.mode==='current'&&d.year!==topPerformanceData.meta.scoringYear?'Original MFL scoring page':'MFL scoring page'} ↗</a></p>${body}`;
}

async function init(){try{
 const response=await fetch('data.json',{cache:'no-store'});if(!response.ok)throw new Error('Data unavailable');data=await response.json();
 setupTopPerformances();if(typeof setupSeasonlong==='function'&&$('seasonlong'))setupSeasonlong();
 data.champions.sort((a,b)=>b.year-a.year);
 const firstSeason=Math.min(...data.champions.map(c=>c.year)),years=data.completedThrough-firstSeason+1;
 $('coverage').textContent=`Celebrating ${years} ${years===1?'year':'years'} of ADL glory (${firstSeason}-${data.completedThrough})`;
 $('footer-coverage').textContent=`ADL historical archive · Results through ${data.completedThrough}`;
 $('season').innerHTML=data.champions.map(c=>`<option>${c.year}</option>`).join('');
 $('archive').innerHTML=data.champions.map(c=>`<tr data-year="${c.year}"><td>${c.year}</td><td><div class="mini-team">${logo(c.champion)}<strong>${esc(c.champion)}</strong></div></td><td class="bowl-score"><button type="button" class="score-trigger" data-lineup-year="${c.year}" aria-label="${c.year} Super Bowl final score: ${esc(c.score)}. Show lineups and points" aria-haspopup="dialog" aria-controls="super-bowl-lineups" aria-expanded="false">${esc(c.score)}</button></td><td><div class="mini-team">${logo(c.runner)}<span>${esc(c.runner)}</span></div></td></tr>`).join('');
 const titles=new Map();for(const c of data.champions){if(!titles.has(c.champion))titles.set(c.champion,[]);titles.get(c.champion).push(c);}
 $('titles').innerHTML=[...titles].sort((a,b)=>b[1].length-a[1].length||b[1][0].year-a[1][0].year).map(([name,wins])=>`<div class="title-row">${logo(name)}<div><strong>${esc(name)}</strong>${wins.map(c=>`<small class="title-season">${c.year} · ${esc(c.gm.replace(/, /g,' / '))}</small>`).join('')}</div><b>${wins.length}</b></div>`).join('');
 renderEarningsLeaderboard();renderAwardCounts();renderChampion(data.champions[0].year);renderOwners();selectTab(tabNames.includes(location.hash.slice(1))?location.hash.slice(1):'halloffame');
 $('season').addEventListener('change',e=>renderChampion(e.target.value));
 $('owners').addEventListener('click',e=>{const b=e.target.closest('[data-owner]');if(b)showCareer(b.dataset.owner);});
 $('close-career').addEventListener('click',()=>$('career').close());
 for(const id of ['search','minimum'])$(id).addEventListener(id==='search'?'input':'change',renderOwners);
 document.querySelectorAll('[data-status]').forEach(b=>b.addEventListener('click',()=>{status=b.dataset.status;document.querySelectorAll('[data-status]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));renderOwners();}));
 document.querySelectorAll('[data-sort]').forEach(b=>b.addEventListener('click',()=>{if(sort===b.dataset.sort)direction*=-1;else{sort=b.dataset.sort;direction=sort==='owner'?1:-1;}renderOwners();}));
 for(const name of tabNames){$(name+'-tab').addEventListener('click',()=>selectTab(name));$(name+'-tab').addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?tabNames[0]:e.key==='End'?tabNames.at(-1):tabNames[(tabNames.indexOf(name)+(e.key==='ArrowRight'?1:-1)+tabNames.length)%tabNames.length];selectTab(next);$(next+'-tab').focus();}});}
}catch(error){$('load-error').hidden=false;$('coverage').textContent='Archive unavailable';console.error(error);}}
init();
