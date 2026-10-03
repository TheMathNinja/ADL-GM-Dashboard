'use strict';
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const teams={ARI:['Arizona Cardinals','ari'],ATL:['Atlanta Falcons','atl'],BAL:['Baltimore Ravens','bal'],BUF:['Buffalo Bills','buf'],CAR:['Carolina Panthers','car'],CHI:['Chicago Bears','chi'],CIN:['Cincinnati Bengals','cin'],CLE:['Cleveland Browns','cle'],DAL:['Dallas Cowboys','dal'],DEN:['Denver Broncos','den'],DET:['Detroit Lions','det'],GBP:['Green Bay Packers','gb'],HOU:['Houston Texans','hou'],IND:['Indianapolis Colts','ind'],JAC:['Jacksonville Jaguars','jax'],KCC:['Kansas City Chiefs','kc'],LAC:['Los Angeles Chargers','lac'],LAR:['Los Angeles Rams','lar'],LVR:['Las Vegas Raiders','lv'],MIA:['Miami Dolphins','mia'],MIN:['Minnesota Vikings','min'],NEP:['New England Patriots','ne'],NOS:['New Orleans Saints','no'],NYG:['New York Giants','nyg'],NYJ:['New York Jets','nyj'],PHI:['Philadelphia Eagles','phi'],PIT:['Pittsburgh Steelers','pit'],SEA:['Seattle Seahawks','sea'],SFO:['San Francisco 49ers','sf'],TBB:['Tampa Bay Buccaneers','tb'],TEN:['Tennessee Titans','ten'],WAS:['Washington Commanders','wsh']};
const historical={'Oakland Raiders':'LVR','San Diego Chargers':'LAC','Washington Redskins':'WAS','Washington Football Team':'WAS','St. Louis Rams':'LAR'};
const teamEntry=name=>teams[name==='OAK'?'LVR':name==='NOR'?'NOS':name]||teams[historical[name]]||Object.values(teams).find(x=>x[0]===name);
function logo(name){const t=teamEntry(name);return t?`<img src="https://a.espncdn.com/i/teamlogos/nfl/500/${t[1]}.png" alt="" loading="lazy">`:'';}
const pct=n=>n==null?'—':(n*100).toFixed(1)+'%';
const trophy='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M7 3h10v6a5 5 0 0 1-10 0V3ZM7 5H3v3a4 4 0 0 0 5 4m9-7h4v3a4 4 0 0 1-5 4M12 14v5m-5 2h10m-8-2h6"/></svg>';
let data,status='active',sort='allTimeAllPlay',direction=-1;
function renderChampion(year){
 const c=data.champions.find(c=>c.year===+year);if(!c)return;
 $('season').value=c.year;
 const scores=c.score.split(' - ');
 $('champion-stage').innerHTML=`<div class="stage"><div><div class="winner-tag">${trophy}${c.year} Super Bowl champion</div><div class="team-line">${logo(c.champion)}<div><div class="team-name">${esc(c.champion)}</div><div class="team-record">${esc(c.championRecord)}</div></div></div><div class="champ-gm">GM <strong>${esc(c.gm)}</strong></div></div><div class="match-score"><span>Final</span><strong>${esc(scores[0])}</strong><span>—</span><strong>${esc(scores[1])}</strong></div><div class="runner"><div class="winner-tag">Super Bowl runner-up</div><div class="team-line">${logo(c.runner)}<div><div class="team-name">${esc(c.runner)}</div><div class="team-record">${esc(c.runnerRecord)}</div></div></div></div></div>`;
 $('award-year').textContent=c.year;
 const labels={HC:'Head Coach',OC:'Offensive Coordinator',DC:'Defensive Coordinator',GM:'General Manager'};
 $('awards').innerHTML=['NFC','AFC'].map(conf=>`<section class="conference ${conf.toLowerCase()}"><h3>${conf} AWARDS</h3><div class="award-grid">${Object.entries(labels).map(([key,label])=>{const raw=c.awards[conf+' '+key];const m=raw.match(/^(\S+)\s+\(([^)]+)\)$/);return `<div class="award"><span>${label}</span>${m?logo(m[1]):''}<strong>${esc(m?.[1]||raw)}</strong><span class="award-value">${m?(key==='HC'?(Number(m[2])*100).toFixed(1)+'%':esc(m[2])):''}</span><span>${key==='HC'?'All-Play%':key==='GM'?'Potential PPG':key==='OC'?'Offensive PPG':'Defensive PPG'}</span></div>`;}).join('')}</div></section>`).join('');

 renderPayouts(c.year);
}
const money=value=>value==null?'—':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',minimumFractionDigits:Number.isInteger(value)?0:2,maximumFractionDigits:2}).format(value);
const shortAward=label=>label.replace(/Head Coach/gi,'HC').replace(/Offensive Coordinator/gi,'OC').replace(/Defensive Coordinator/gi,'DC').replace(/General Manager/gi,'GM');
function earningsRank(rows,value,key){const rank=1+rows.filter(row=>row[key]>value).length;return (rows.filter(row=>row[key]===value).length>1?'T-':'')+rank;}
function renderPayouts(year){
 const p=data.payouts.find(p=>p.year===year);
 const ranked=p.teams.slice().sort((a,b)=>b.totalEarnings-a.totalEarnings||a.franchise.localeCompare(b.franchise));
 $('payout-teams').innerHTML=ranked.map(t=>`<tr><td>${earningsRank(ranked,t.totalEarnings,'totalEarnings')}</td><td><div class="owner-detail">${logo(t.franchise)}<div><strong>${esc(t.franchise)}</strong><small>${esc(t.gm)}</small></div></div></td><td class="num"><strong>${money(t.totalEarnings)}</strong></td><td class="earnings-breakdown">${t.earnedBreakdown.length?t.earnedBreakdown.map(item=>`${esc(shortAward(item.label))} (${money(item.amount)})`).join(', '):''}</td></tr>`).join('');
 const winner=value=>value?`<span class="award-winners">${value.split(/\s*\/\s*/).map(code=>{const team=teamEntry(code.trim());return team?`<img src="https://a.espncdn.com/i/teamlogos/nfl/500/${team[1]}.png" alt="${esc(team[0])}" title="${esc(team[0])}" loading="lazy">`:esc(code);}).join('')}</span>`:'—';
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
 $('owners').innerHTML=filtered.map(({o,rank})=>`<tr class="${status==='all'&&o.active?'current-gm-row':''}"><td class="muted">${rank}</td><td><div class="owner-detail">${logo(o.franchise)}<div><button class="gm-button" style="font-weight:${o.active?700:400}" data-owner="${esc(o.owner)}" aria-haspopup="dialog">${esc(o.owner)}</button><small>${esc(o.franchise)}</small></div></div></td><td class="muted">${o.years.length?(o.years.length===1?o.years[0]:o.years[0]+'–'+o.years.at(-1)):'—'}</td><td class="num">${o.seasons}</td><td class="num">${o.seasons?esc(o.record):'—'}</td><td class="num"><span class="percent"><i aria-hidden="true"><b style="width:${(o.allTimeAllPlay??0)*100}%"></b></i>${pct(o.allTimeAllPlay)}</span></td></tr>`).join('')||'<tr><td colspan="6" class="empty">No GMs match these filters. Try a different name or season minimum.</td></tr>';
 $('results').textContent=`${filtered.length} of ${pool.length} GMs · ${sort==='seasons'?'Seasons played':'All-time all-play'} ranks · Ties share rank`;
 document.querySelectorAll('[data-sort]').forEach(b=>{const active=b.dataset.sort===sort;b.closest('th').setAttribute('aria-sort',active?(direction<0?'descending':'ascending'):'none');const labels={owner:'GM / Franchise',seasons:'Seasons',allTimeAllPlay:'All-Time All-Play%'};b.textContent=labels[b.dataset.sort]+(active?(direction<0?' ↓':' ↑'):'');});
}
function showCareer(name){const o=data.owners.find(o=>o.owner===name);$('career-title').textContent=o.owner;$('career-context').textContent=`${o.seasons} completed seasons · ${pct(o.allTimeAllPlay)} career all-play · Shared team seasons count once`;$('career-rows').innerHTML=o.history.slice().reverse().map(s=>`<tr><td>${s.year}</td><td>${esc(s.franchise)}</td><td>${esc(s.record)}</td><td>${pct(s.rs)}</td><td>${pct(s.all)}</td><td>${s.finish}</td></tr>`).join('')||'<tr><td colspan="6">No completed seasons in the archive.</td></tr>';$('career').showModal();}
const tabNames=['halloffame','champions','alltime'];
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
function selectTab(id){for(const name of tabNames){const selected=id===name;$(name).hidden=!selected;$(name+'-tab').setAttribute('aria-selected',String(selected));$(name+'-tab').tabIndex=selected?0:-1;}history.replaceState(null,'','#'+id);}
async function init(){try{
 const response=await fetch('data.json');if(!response.ok)throw new Error('Data unavailable');data=await response.json();
 data.champions.sort((a,b)=>b.year-a.year);
 const firstSeason=Math.min(...data.champions.map(c=>c.year)),years=data.completedThrough-firstSeason+1;
 $('coverage').textContent=`Celebrating ${years} ${years===1?'year':'years'} of ADL glory (${firstSeason}-${data.completedThrough})`;
 $('footer-coverage').textContent=`ADL historical archive · Results through ${data.completedThrough}`;
 $('season').innerHTML=data.champions.map(c=>`<option>${c.year}</option>`).join('');
 $('archive').innerHTML=data.champions.map(c=>`<tr data-year="${c.year}"><td>${c.year}</td><td><div class="mini-team">${logo(c.champion)}<strong>${esc(c.champion)}</strong></div></td><td class="bowl-score">${esc(c.score)}</td><td><div class="mini-team">${logo(c.runner)}<span>${esc(c.runner)}</span></div></td></tr>`).join('');
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
