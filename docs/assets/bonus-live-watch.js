/* Public provisional standings. Official snapshots/model forecasts are untouched. */
(()=>{
/* Official NFL headshots keyed by MFL identity, shared across leagues. */

 const zones=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',weekday:'short',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
 function inWindow(date=new Date()){const p=Object.fromEntries(zones.formatToParts(date).map(x=>[x.type,x.value])),m=Number(p.hour)*60+Number(p.minute);return (p.weekday==='Sun'&&m>=540)||(['Mon','Thu'].includes(p.weekday)&&m>=1200)||(['Mon','Tue','Fri'].includes(p.weekday)&&m<=30)}
 function clock(seconds){const n=Math.max(0,Math.round(Number(seconds)||0));return Math.floor(n/60)+':'+String(n%60).padStart(2,'0')}
 function liveWeekLabel(snapshot,published,projected=false){
  if(projected)return 'Projected End of Week '+snapshot.week;
  // The live feed remains unofficial even when archived results are official.
  const posted=published.league===snapshot.league&&Number(published.season)===Number(snapshot.season)&&Number(published.through_week)>=snapshot.week&&Array.isArray(published.weeks?.[snapshot.week]);
  return posted?'unofficial Week '+snapshot.week+' results':'live Week '+snapshot.week;
 }
 const positionOrder=['QB','RB','WR','TE','PK','PN','DT','DE','LB','CB','S'];
 const alphabet=new Intl.Collator('en',{sensitivity:'base',numeric:true});
 function displayPlayerName(value){const name=String(value??'').trim(),comma=name.indexOf(',');return comma<0?name:(name.slice(comma+1).trim()+' '+name.slice(0,comma).trim()).trim()}
 function sortedStarters(players){const rank=p=>{const i=positionOrder.indexOf(p.position);return i<0?99:i},name=p=>String(p.name||'').split(',').map(x=>x.trim());return [...players].sort((a,b)=>rank(a)-rank(b)||alphabet.compare(name(a)[0],name(b)[0])||alphabet.compare(name(a).slice(1).join(','),name(b).slice(1).join(','))||alphabet.compare(a.id,b.id))}
 function playerLive(p){return (p.seconds>0||p.gameStatus?.startsWith('Awaiting'))&&p.gameStatus!=='Pregame'&&p.gameStatus!=='Final'&&p.gameStatus!=='Bye'&&(!!p.gameStatus||p.seconds<3600)}
 function playerToPlay(p){return p.seconds>0&&(p.gameStatus==='Pregame'||(!p.gameStatus&&p.seconds>=3600))}
 function teamProgress(t){if(!Array.isArray(t.starters))return {completed:t.completed||0,playing:t.playing||0,yet:t.yet||0,seconds:t.seconds||0};return {completed:t.starters.filter(p=>p.gameStatus==='Final').length,playing:t.starters.filter(playerLive).length,yet:t.starters.filter(playerToPlay).length,seconds:t.starters.reduce((n,p)=>n+Number(p.seconds||0),0)}}
 function activityMarkup(t,clubs,split=false){const p=teamProgress(t);if(!matchupLive(clubs))return `<span>${p.completed} Completed</span><span>· ${p.yet} to Play</span>`;if(split)return `<span>${p.playing} Live ${unitOnFieldMarkup(t)} · ${clock((t.starters||[]).filter(playerLive).reduce((n,p)=>n+p.seconds,0))} rem.</span><span>${p.yet} to Play · ${clock((t.starters||[]).filter(playerToPlay).reduce((n,p)=>n+p.seconds,0))} rem.</span>`;return `<span>${p.playing} Live ${unitOnFieldMarkup(t)}</span><span>· ${p.yet} to Play</span><span>· ${clock(p.seconds)} rem.</span>`}
 function matchupLive(clubs){return clubs.some(t=>teamProgress(t).playing>0)}
 function playerOnField(p){return playerLive(p)&&p.unitOnField===true&&['QB','RB','WR','TE','DT','DE','DL','EDGE','LB','CB','S','DB'].includes(p.position)&&!['halftime','between_periods','awaiting_overtime','awaiting_final'].includes(p.nflGamePhase)&&!(/^(Halftime|Awaiting|Between)/).test(p.gameStatus||'')}
 function playerOnFieldBall(p){return playerOnField(p)?'<svg class="gm-live-unit-ball" width="12" height="9" viewBox="0 0 20 14" role="img" aria-label="Unit on field" style="vertical-align:-1px;margin-right:4px"><title>Player’s unit is on field</title><path d="M1 7Q10-5 19 7Q10 19 1 7Z" fill="#87512f"/><path d="M5 7h10M8 5v4m4-4v4" fill="none" stroke="#fff" stroke-width="1.3"/></svg>':''}
 function unitOnFieldProgress(t){const live=(t.starters||[]).filter(playerLive).filter(p=>['QB','RB','WR','TE','DT','DE','DL','EDGE','LB','CB','S','DB'].includes(p.position));return {count:live.filter(playerOnField).length,unknown:live.filter(p=>p.unitOnField==null).length}}
 function unitOnFieldMarkup(t){const p=unitOnFieldProgress(t);return `<span class="gm-live-on-field" title="On field means their NFL unit: offense with possession, defense without possession. Kickers and punters are excluded. Zero can mean a paused game, the other unit on field, or unavailable possession; snapshots keep these states separate.">[${p.count} on Field]</span>`}
 function bonusPercentages(p){if(!p)return null;const raw=[p.win,p.tie,p.loss].map(v=>100*v),rounded=raw.map(Math.floor),order=[0,1,2].sort((a,b)=>(raw[b]-rounded[b])-(raw[a]-rounded[a])||a-b);const rest=100-rounded.reduce((a,b)=>a+b,0);for(let k=0;k<rest;k++)rounded[order[k%3]]++;return rounded}
 function matchingScoringDetails(p,week){const d=p.scoringDetails;if(d?.week!==week||!Number.isFinite(Number(d.total))||!Array.isArray(d.rows))return null;const total=Number(d.total),sum=d.rows.reduce((n,r)=>n+Number(r.points),0);return Math.abs(total-Number(p.score))<.05&&Math.abs(sum-total)<.05?d:null}
 function sameStatsRegion(a,b){const x=a?.closest?.('[data-live-stats]'),y=b?.closest?.('[data-live-stats]');return !!x&&!!y&&x.dataset.liveStats===y.dataset.liveStats&&x.closest('tr')===y.closest('tr');}
 function projectedPointsStanding(teams,id,conferences={},final=false){
  const value=t=>{const v=final?t.pregameProjectedScore:t.projectedScore;return v==null||v===''||!Number.isFinite(Number(v))?null:Math.round(Number(v)*10)},rows=(teams||[]).map(t=>({id:t.id,value:value(t)})).filter(t=>t.value!==null),team=rows.find(t=>t.id===id);if(!team)return null;
  const rank=1+rows.filter(t=>t.value>team.value).length,tied=rows.filter(t=>t.value===team.value).length>1,conference=conferences[id],group=['NFC','AFC'].includes(conference)?rows.filter(t=>conferences[t.id]===conference):[];
  return {rank,total:rows.length,tied,conference,conferenceLeader:group.length>0&&team.value===Math.max(...group.map(t=>t.value))};
 }
 function projectedPointsMarkup(t,teams,conferences={},final=false,inheritFont=false){
  const s=projectedPointsStanding(teams,t.id,conferences,final);if(!s)return '';const n=s.rank,suffix=n%100>=11&&n%100<=13?'th':({1:'st',2:'nd',3:'rd'}[n%10]||'th'),label=(s.tied?'T-':'')+n+suffix,hue=120*(s.total-s.rank)/Math.max(1,s.total-1);
  return `<span class="wm-projected-standing" style="display:inline-flex;align-items:baseline;gap:4px;margin-left:${inheritFont?0:5}px;white-space:nowrap;${inheritFont?'font:inherit':'font-size:11px;font-weight:600'}"><span style="color:light-dark(hsl(${hue} 65% 28%),hsl(${hue} 68% 72%))" title="${final?'Pregame projected':'Projected'} points rank among ${s.total} league teams${s.tied?'; tied at displayed precision':''}">(${label}${s.conferenceLeader?`<span style="color:light-dark(#218447,#71d991);${inheritFont?'font:inherit':'font-size:13px;font-weight:750'}" role="img" aria-label="${s.conference} projected weekly scoring leader" title="${s.conference} projected weekly scoring leader">$</span>`:''})</span></span>`;
 }
 function weeklyMoneyLeaders(rows,conferences){const leaders=new Set();for(const conf of ['NFC','AFC']){const teams=rows.filter(t=>conferences[t.id]===conf);if(!teams.length)continue;const best=Math.max(...teams.map(t=>t.weekly.ap));for(const t of teams)if(t.weekly.ap===best)leaders.add(t.id)}return leaders}
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
 function nflScoreMarkup(p){
  if(!playerLive(p)||!Array.isArray(p.nflScoreboard)||p.nflScoreboard.length!==2)return '';
  const teams=p.nflScoreboard;if(teams.some(t=>!(/^[A-Z]{2,4}$/).test(t.team)||!Number.isInteger(t.score)||t.score<0))return '';
  const ball=team=>`<svg class="gm-live-possession" width="10" height="8" viewBox="0 0 20 14" role="img" aria-label="${team} has possession" style="vertical-align:-1px;margin-right:2px"><title>${team} has possession</title><path d="M1 7Q10-5 19 7Q10 19 1 7Z" fill="#87512f"/><path d="M5 7h10M8 5v4m4-4v4" fill="none" stroke="#fff" stroke-width="1.3"/></svg>`;
  return `<span class="gm-live-nfl-score" style="display:block;font-size:10px;font-weight:400;line-height:1.35;white-space:nowrap">${teams.map(t=>`<span>${t.possession?ball(t.team):''}${t.team} ${t.score}</span>`).join(' · ')}</span>`;
 }
 function submissionTime(value){if(!value)return 'Not available';const date=new Date(value);if(Number.isNaN(date.getTime()))return 'Not available';const parts=Object.fromEntries(new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',weekday:'short',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',hour12:true}).formatToParts(date).map(p=>[p.type,p.value]));return `${parts.weekday} ${parts.month} ${parts.day} ${parts.hour}:${parts.minute} ${parts.dayPeriod.toLowerCase()} ET`;}
 const LINEUP_RULES={"count":21,"positions":{"QB":[1,1],"RB":[1,2],"WR":[2,4],"TE":[1,2],"PK":[1,1],"PN":[1,1],"DT":[2,3],"DE":[2,3],"LB":[1,3],"CB":[2,4],"S":[2,3]},"groups":{"offensive":{"positions":["QB","RB","WR","TE"],"total":7},"defensive":{"positions":["DT","DE","LB","CB","S"],"total":12}}};
 function lineupEfficiency(team){
  const starters=team.starters||[], starting=new Set(starters.map(p=>p.id));
  const score=p=>Number(p.score)||0;
  const byPoints=(a,b)=>score(b)-score(a)||Number(starting.has(b.id))-Number(starting.has(a.id))||String(a.id).localeCompare(String(b.id));
  const roster=[...new Map([...starters,...(team.bench||[])].map(p=>[p.id,p])).values()];
  const official=team.optimalLineup;
  const optimalIds=new Set(official?.ids||[]);
  const units=[...Object.values(LINEUP_RULES.groups),{positions:['PK'],total:1},{positions:['PN'],total:1}];
  const swaps=[];let potential=Number(team.scoreAdjustment)||0,complete=true;
  for(const {positions,total} of units){
   let chosen=[];const flex=[];
   for(const pos of positions){
    const candidates=roster.filter(p=>p.position===pos&&(starting.has(p.id)||score(p)!==0||(p.gameStatus!=='Bye'&&!['H','S','O','I','IR','PUP','NFI'].includes(p.injuryStatus)))).sort(byPoints);
    const [min,max]=LINEUP_RULES.positions[pos];
    if(candidates.length<min)complete=false;
    chosen.push(...candidates.slice(0,min));flex.push(...candidates.slice(min,max));
   }
   chosen.push(...flex.sort(byPoints).slice(0,total-chosen.length));
   if(official)chosen=roster.filter(p=>positions.includes(p.position)&&optimalIds.has(p.id));
   if(chosen.length!==total)complete=false;
   potential+=chosen.reduce((n,p)=>n+score(p),0);
   const selected=new Set(chosen.map(p=>p.id));
   const out=starters.filter(p=>positions.includes(p.position)&&!selected.has(p.id)).sort(byPoints);
   const incoming=chosen.filter(p=>!starting.has(p.id)).sort(byPoints);
   const pair=(p,index)=>swaps.push({up:p,down:index<0?null:out.splice(index,1)[0]});
   const unmatched=[];
   for(const p of incoming){const index=out.findIndex(q=>q.position===p.position);if(index>=0)pair(p,index);else unmatched.push(p);}
   for(const p of unmatched)pair(p,out.length?0:-1);
   for(const p of out)swaps.push({up:null,down:p});
  }
  if(official){potential=official.points;complete=true;}
  const unitPoints=unit=>starters.filter(p=>LINEUP_RULES.groups[unit].positions.includes(p.position)).reduce((n,p)=>n+score(p),0);
  const special=starters.filter(p=>['PK','PN'].includes(p.position)).reduce((n,p)=>n+score(p),0);
  return {special,offense:unitPoints('offensive'),defense:unitPoints('defensive'),potential:complete?potential:null,efficiency:complete&&potential>0?100*team.score/potential:null,swaps};
 }

 function activeLineup(players=[]){
  // Mirrors commissioner_alerts.R: position bounds, group totals, then minimum-first flex shortages.
  const rules=LINEUP_RULES,counts=Object.fromEntries(Object.keys(rules.positions).map(p=>[p,0]));
  const activePlayers=players.filter(p=>String(p.gameStatus||'').toLowerCase()!=='bye'&&!['H','S','O','I','IR','IR-R','IR-PUP','IR-NFI','PUP','NFI'].includes(String(p.injuryStatus||'').trim().toUpperCase()));
  let unknown=0;for(const p of activePlayers){const pos=String(p.position||'').toUpperCase();if(pos in counts)counts[pos]++;else unknown++;}
  const needs=[],corrections=[],adjusted={...counts};
  for(const [pos,[min,max]] of Object.entries(rules.positions)){
   if(counts[pos]<min){needs.push(`${min-counts[pos]} ${pos}`);adjusted[pos]=min;}
   if(counts[pos]>max)corrections.push(`remove ${counts[pos]-max} excess ${pos}`);
  }
  for(const [group,{positions,total}] of Object.entries(rules.groups)){
   const count=positions.reduce((n,p)=>n+counts[p],0),remaining=total-positions.reduce((n,p)=>n+adjusted[p],0);
   if(remaining>0){const eligible=positions.filter(p=>adjusted[p]<rules.positions[p][1]);needs.push(`${remaining} ${eligible.join('/')}`);}
   if(count>total)corrections.push(`remove ${count-total} excess ${group} starter${count-total===1?'':'s'}`);
  }
  if(unknown)corrections.push(`verify ${unknown} unrecognized position${unknown===1?'':'s'}`);
  const active=activePlayers.length,complete=players.length===rules.count&&active===rules.count&&!needs.length&&!corrections.length;
  if(!complete&&!needs.length&&!corrections.length)corrections.push('remove unavailable or extra submitted starters');
  return {active,complete,needs,corrections};
 }
 function weekStarted(data,now=Date.now()){return !!data&&(data.final===true||matchupStarted((data.teams||[]).map(t=>({starters:[...(t.starters||[]),...(t.bench||[])]})),now))}
 function matchupStarted(teams,now=Date.now()){
  return teams.some(t=>(t.starters||[]).some(p=>p.gameStatus!=='Bye'&&(p.gameStatus==='Final'||/^(?:[1-4]Q|OT|Awaiting|Halftime|Live)/.test(p.gameStatus||'')||(Number(p.kickoff)>0&&Number(p.kickoff)*1000<=now))));
 }
 const mflAbbreviations={"0001":"DAL","0002":"NYG","0003":"PHI","0004":"WAS","0005":"CHI","0006":"DET","0007":"GBP","0008":"MIN","0009":"ATL","0010":"CAR","0011":"NOS","0012":"TBB","0013":"ARI","0014":"LAR","0015":"SFO","0016":"SEA","0017":"BUF","0018":"MIA","0019":"NEP","0020":"NYJ","0021":"BAL","0022":"CIN","0023":"CLE","0024":"PIT","0025":"HOU","0026":"IND","0027":"JAC","0028":"TEN","0029":"DEN","0030":"KCC","0031":"LVR","0032":"LAC"};
 function teamAbbr(t){return mflAbbreviations[t.id]||t.abbrev||t.name;}

 function matchupDone(clubs){const ps=clubs.flatMap(t=>t.starters||[]);return ps.length>0&&ps.every(p=>p.gameStatus==='Final'||p.gameStatus==='Bye')}
 function probabilityText(p,done=false){return p==null?'—':!done&&p<.0005?'&lt;0.1%':!done&&p>.9995?'&gt;99.9%':(100*p).toFixed(1)+'%'}
 function tieMarkup(p){return p?.tie>=.001?`<small class="gm-h2h-tie">Tie ${(100*p.tie).toFixed(1)}%</small>`:''}
 function canOverlay(data,live){return !!(data&&live&&!data.final&&live.week===data.week&&live.league===data.league&&live.season===data.season&&live.liveProbabilityModel?.id===data.modelId&&Number.isFinite(Date.parse(live.fetchedAt))&&Date.parse(live.fetchedAt)>=Date.parse(data.fetchedAt))}
 function bonusView(s){return s?.week>12?s.bonusSnapshot:s}
 function applyMflRefresh(prior,fresh){
  if(!prior||fresh.league!==prior.league||fresh.season!==prior.season||fresh.week!==prior.week||fresh.teams?.length!==32||fresh.rosters?.length!==32||!Number.isFinite(Date.parse(fresh.checkedAt)))throw Error('Incomplete or mismatched MFL refresh');
  const known=new Map(prior.teams.flatMap(t=>[...(t.starters||[]),...(t.bench||[])]).map(p=>[p.id,p])),live=new Map(fresh.teams.map(t=>[t.id,t])),rosters=new Map(fresh.rosters.map(t=>[t.id,t]));
  const teams=prior.teams.map(t=>{
   const feed=live.get(t.id),roster=rosters.get(t.id);if(!feed||!roster)throw Error('Missing team in MFL refresh');
   const old=new Map([...(t.starters||[]),...(t.bench||[])].map(p=>[p.id,p])),reported=new Map(feed.players.map(p=>[p.id,p])),owned=new Set(roster.players.map(p=>p.id));
   if(feed.players.some(p=>p.status==='starter'&&!owned.has(p.id)))throw Error('MFL lineup and roster changed during refresh; please retry');
   const starters=[],bench=[];
   for(const id of owned){const p=reported.get(id),previous=old.get(id)||known.get(id),meta=fresh.profiles[id];if(!meta&&!previous)throw Error('MFL player identity missing');
    const detail=fresh.scoringDetails?.[id],score=detail?.total??p?.score??fresh.scores?.[id]??0,seconds=p?.gameSecondsRemaining??previous?.seconds??0;
    let gameStatus=previous?.gameStatus||'Pregame';if(seconds!==previous?.seconds)gameStatus=seconds<=0?'Awaiting final status':seconds>=3600?'Pregame':(4-Math.floor((seconds-1)/900))+'Q '+clock(seconds-(4-(4-Math.floor((seconds-1)/900)))*900);
    const player={...previous,id,name:meta?.name||previous.name,position:meta?.position||previous.position,nflTeam:meta?.team||previous.nflTeam,score,seconds,gameStatus,mflReportedScore:p?.score??null,scoreSource:detail?'MFL live raw stats':'MFL liveScoring',scoreUpdatedAt:detail?.sourceUpdatedAt??fresh.scoresCheckedAt,scoringDetails:detail||null};
    if(seconds!==previous?.seconds){player.unitOnField=false;player.nflGamePhase=null;}
    (p?.status==='starter'?starters:bench).push(player);
   }
   const changed=[...starters.map(p=>p.id)].sort().join(',')!==[...(t.starters||[]).map(p=>p.id)].sort().join(',');
   // Keep published model outputs unaltered. The next complete collector snapshot
   // restores current projections/odds; never invent a new projection by scaling it.
   return {...t,starters,bench,score:Math.round(starters.reduce((s,p)=>s+p.score,0)*10)/10,mflReportedScore:feed.score,lineupSubmittedAt:changed?null:t.lineupSubmittedAt,projectedScore:null,projectedPotential:null,liveMatchups:{},liveBonusProbabilities:{},forecastsPending:true,potential:null,potentialComplete:false};
  });
  return {...prior,teams,fetchedAt:fresh.checkedAt,scoresCheckedAt:fresh.scoresCheckedAt,lineupsCheckedAt:fresh.lineupsCheckedAt,forecastAsOf:prior.forecastAsOf||prior.fetchedAt,forecastsPending:true,manualFreshAt:fresh.checkedAt,liveProbabilityUnavailable:true,liveBonusProbabilityBasis:null,source:fresh.source};
 }
 async function readMflRefresh(base,fetcher=fetch){
  const r=await fetcher('https://mfl-live-refresh.dreamytang7.chatgpt.site/live?'+new URLSearchParams({league:base.league,week:String(base.week),refresh:String(Date.now())}),{cache:'no-store',signal:AbortSignal.timeout(35000)}),fresh=await r.json();if(!r.ok)throw Error(fresh.error||'Fresh MFL scrape unavailable');return applyMflRefresh(base,fresh);
 }
 if(typeof document==='undefined'){globalThis.BonusLiveWatchCore={sameStatsRegion,projectedPointsStanding,projectedPointsMarkup,readMflRefresh,applyMflRefresh,weekStarted,activityMarkup,matchupLive,displayPlayerName,submissionTime,activeLineup,matchupStarted,teamAbbr,matchupDone,probabilityText,tieMarkup,canOverlay,bonusView,inWindow,clock,liveWeekLabel,sortedStarters,playerLive,playerToPlay,teamProgress,weeklyMoneyLeaders,matchingScoringDetails,allPlay,standings,bonusPercentages,nflScoreMarkup,unitOnFieldProgress,unitOnFieldMarkup,playerOnField,playerOnFieldBall};return}

 let snapshot=null,busy=false,error='',lastAttempt=-1,view='current',refreshNotice='';
 let lineupTarget=null,lineupHideTimer;const expandedBenches=new Set();
 const nflPhotoPromise=fetch('https://raw.githubusercontent.com/TheMathNinja/ADL-GM-Dashboard/main/docs/assets/nfl-player-photo-urls.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error('Photo directory unavailable');return r.json()}).catch(()=>({}));
 const lineup=document.createElement('div');lineup.id='bonus-live-lineup-popup';lineup.className='gm-popup gm-live-lineup';lineup.hidden=true;lineup.setAttribute('role','dialog');lineup.setAttribute('aria-label','Starting player projections');$('bonus-design').append(lineup);
 const statPopup=document.createElement('div');statPopup.id='bonus-live-stat-popup';statPopup.className='gm-live-stat-popup';statPopup.hidden=true;statPopup.setAttribute('role','dialog');statPopup.setAttribute('aria-label','Player scoring breakdown');$('bonus-design').append(statPopup);let statTarget=null,statHideTimer;

 const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const sorts={quarter:{key:'rank',dir:1},season:{key:'rank',dir:1}};
 const nf=new Intl.NumberFormat('en-US',{maximumFractionDigits:2}),stamp=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',weekday:'short',hour:'numeric',minute:'2-digit',second:'2-digit',timeZoneName:'short'});
 const schedule='Updated Live · Thu & Mon 8 PM–12:30 AM ET · Sun 9 AM–12:30 AM ET';
 const container=document.createElement('section');container.id='bonus-live-panels';container.hidden=true;container.setAttribute('role','tabpanel');container.setAttribute('aria-labelledby','bonus-live-tab');
 container.innerHTML='<div class="gm-toolbar"><div class="gm-conferences" role="group" aria-label="Live standings view"><button type="button" data-live-view="current" aria-pressed="true">Current</button><button type="button" data-live-view="projected" aria-pressed="false">Projected</button></div><input id="gm-live-search" class="gm-search" type="search" aria-label="Find a live team" placeholder="Find a team"></div><div class="gm-live-grid">'+['quarter','season'].map(panel=>`<section class="gm-surface gm-live-panel"><header><h3 id="live-${panel}-title"></h3><div id="live-${panel}-summary" class="gm-live-cutoffs"></div></header><div class="gm-scroll"><table class="gm-live-standings" aria-label="${panel==='quarter'?'Current quarter':'Regular Season'} live Bonus standings"><colgroup><col style="width:5%"><col style="width:35%"><col style="width:17%"><col style="width:14%"><col style="width:20%"><col style="width:9%"></colgroup><thead id="live-${panel}-head"></thead><tbody id="live-${panel}-rows"></tbody></table></div><div id="live-${panel}-conference"></div></section>`).join('')+'</div>';
 $('race-view').before(container);for(const scroll of container.querySelectorAll('.gm-scroll'))scroll.addEventListener('scroll',closePopup);
 $('gm-live-search').addEventListener('input',e=>{$('search').value=e.target.value;draw()});
 function leave(){closeLineup();document.querySelector('.gm-outlook-nav').hidden=false;document.querySelector('.gm-method').hidden=false;$('download').hidden=false;$('race-view').hidden=false;container.hidden=true}
 function panelMarkup(panel){
  const snapshot=bonusView(window.BonusLiveWatch.getSnapshot());
  const isSeason=panel==='season',s=standings(snapshot,isSeason,view==='projected'),label=isSeason?'Reg Season':'Q'+Math.ceil(snapshot.week/3),cfg=sorts[panel],names=Object.fromEntries(DATA.weeks[DATA.through_week].map(t=>[t.id,t]));
  $('live-'+panel+'-title').textContent=isSeason?'Reg Season '+(view==='projected'?'Projected':'Current')+' Standings':label+' '+(view==='projected'?'Projected':'Current')+' Standings';
  $('live-'+panel+'-summary').innerHTML=`<span>${Number(s.start)===Number(s.week)?`Week ${s.start} only`:`Weeks ${s.start}–${s.week}`} · ${liveWeekLabel(snapshot,DATA,view==='projected')}</span><span class="gm-outcome-win">Win Cutoff <strong>${nf.format(s.winCutoff)}</strong> APW</span><span class="gm-outcome-tie">Tie Cutoff <strong>${nf.format(s.tieCutoff)}</strong> APW</span>`;
  const head=(label,key)=>`<th><button type="button" class="gm-sort-heading" data-live-panel="${panel}" data-live-sort="${key}">${label} ${cfg.key===key?(cfg.dir===1?'↑':'↓'):'↕'}</button></th>`;
  $('live-'+panel+'-head').innerHTML='<tr>'+head('Rank','rank')+head('Team','name')+head('All-Play Record','ap')+head(view==='projected'?'Proj. Points':'Points','points')+head('W/T/L Prob','bonusProb')+head('Result','result')+'</tr>';
  const moneyLeaders=weeklyMoneyLeaders(s.rows,CONFERENCES);
  let rows=s.rows.filter(t=>names[t.id].name.toLowerCase().includes($('search').value.toLowerCase()));
  const value=t=>cfg.key==='bonusProb'?((t.liveBonusProbabilities?.[panel]?.win??-1)+.5*(t.liveBonusProbabilities?.[panel]?.tie??0)):cfg.key==='name'?names[t.id].name:cfg.key==='result'?({Win:2,Tie:1,Loss:0}[t.result]??.5):t[cfg.key];rows.sort((a,b)=>{const x=value(a),y=value(b);return cfg.dir*(typeof x==='string'?x.localeCompare(y):x-y)||a.rank-b.rank});
  const composites=conferenceGroups(s.rows).map(group=>{const conf=group.conference,ts=s.rows.filter(t=>group.ids.includes(t.id)),sum=k=>ts.reduce((n,t)=>n+t[k],0),probs=ts.map(t=>t.liveBonusProbabilities?.[panel]),known=snapshot.liveBonusProbabilityBasis==='final_event_outcome'&&probs.every(Boolean),count=result=>ts.filter(t=>t.result===result).length;const weeks=[];for(let week=s.start;week<=s.week;week++){const scores=week===snapshot.week?snapshot.teams.map(t=>({...t,score:view==='projected'?(t.projectedScore??t.score):t.score})):snapshot.completed.find(w=>w.week===week).teams,ap=allPlay(scores),members=scores.filter(t=>group.ids.includes(t.id));weeks.push({week,record:conferenceRecord(members.map(t=>`${ap[t.id].w}-${ap[t.id].l}-${ap[t.id].t}`)),points:members.reduce((n,t)=>n+t.score,0),projected:week===snapshot.week&&view==='projected'})}return [group,conferenceRecordButton(conf,`${sum('w')}-${sum('l')}-${sum('t')}`,weeks,group.fullLabel),sum('points').toLocaleString(undefined,{minimumFractionDigits:1,maximumFractionDigits:1}),known?['win','tie','loss'].map(k=>probs.reduce((n,p)=>n+p[k],0).toFixed(2)).join(' / '):'—',`${count('Win')}-${count('Loss')}-${count('Tie')}${count('Tied at cutoff')?' + '+count('Tied at cutoff')+' unresolved':''}`]});
  $('live-'+panel+'-conference').innerHTML=conferenceTable(['Group','All-Play Record',view==='projected'?'Proj. Points':'Points','Exp. W / T / L','Result W-L-T'],composites,'');
  $('live-'+panel+'-rows').innerHTML=rows.map(t=>`<tr data-live-team="${t.id}" class="gm-conference-row ${CONFERENCES[t.id].toLowerCase()}${((cfg.key==='rank'&&cfg.dir===1)||(cfg.key==='ap'&&cfg.dir===-1))&&(t.rank===16||t.rank===18)?' gm-live-boundary':''}"><td><span class="gm-live-primary">${t.rankEnd>t.rank?'T-':''}${t.rank}</span></td><td>${liveTeam(names[t.id],panel)}${weekStarted(snapshot)?`<div class="gm-live-small gm-live-meta">${activityMarkup(t,[t,...snapshot.teams.filter(o=>(t.opponentIds||[]).includes(o.id))])}</div>`:""}</td><td><strong class="gm-live-primary">${t.w}-${t.l}-${t.t}</strong><div class="gm-live-small gm-live-weekly-apw"><span>W${s.week}: ${nf.format(t.weekly.ap)} APW</span>${moneyLeaders.has(t.id)?`<span class="gm-live-weekly-money" data-weekly-money="${CONFERENCES[t.id]}" role="img" aria-label="${view==='projected'?'Projected':'Current'} ${CONFERENCES[t.id]} weekly money leader" title="${view==='projected'?'Projected':'Current'} ${CONFERENCES[t.id]} weekly money leader">$</span>`:''}</div></td><td ${view==='current'?`data-score-key="race:${panel}:${t.id}" data-score-value="${Number(t.points).toFixed(1)}"`:""}><span class="gm-live-primary">${Number(t.points).toFixed(1)}</span><div class="gm-live-small">W${s.week}: ${Number(t.score).toFixed(1)}</div></td><td><span class="gm-live-primary gm-live-bonus-prob" data-live-bonus-prob title="Final ${isSeason?'Reg Season':label} Bonus Win / Tie / Loss probabilities, including all remaining weeks">${bonusPercentages(snapshot.liveBonusProbabilityBasis==='final_event_outcome'?t.liveBonusProbabilities?.[panel]:null)?.map((v,i)=>`<span class="${['gm-outcome-win','gm-outcome-tie','gm-outcome-loss'][i]}">${v}%</span>`).join('/')??'—'}</span></td><td class="${t.result==='Win'?'gm-outcome-win':t.result==='Tie'?'gm-outcome-tie':'gm-outcome-loss'}"><strong class="gm-live-primary">${t.result}</strong></td></tr>`).join('');
 }
 function fallbackGameStatus(seconds){if(seconds<=0)return 'Awaiting final status';if(seconds>=3600)return 'Pregame';const quarter=4-Math.floor((seconds-1)/900);return quarter+'Q '+clock(seconds-(4-quarter)*900)}
 const kickoffTime=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',weekday:'short',hour:'numeric',minute:'2-digit'});
 function playerGameLabel(p){const status=p.gameStatus||fallbackGameStatus(p.seconds);return status==='Pregame'?(p.kickoff?kickoffTime.format(new Date(p.kickoff*1000)).replace(/,/g,'').replace(/\s+(AM|PM)/,(_,period)=>period.toLowerCase())+' ET':'Kickoff pending'):status}
 // Official NFL club acronyms and primary colors from ESPN teams metadata.
 const clubStyles={"Arizona Cardinals": {"abbr": "ARI", "color": "#a40227"}, "Atlanta Falcons": {"abbr": "ATL", "color": "#a71930"}, "Baltimore Ravens": {"abbr": "BAL", "color": "#29126f"}, "Buffalo Bills": {"abbr": "BUF", "color": "#00338d"}, "Carolina Panthers": {"abbr": "CAR", "color": "#0085ca"}, "Chicago Bears": {"abbr": "CHI", "color": "#0b1c3a"}, "Cincinnati Bengals": {"abbr": "CIN", "color": "#fb4f14"}, "Cleveland Browns": {"abbr": "CLE", "color": "#472a08"}, "Dallas Cowboys": {"abbr": "DAL", "color": "#002a5c"}, "Denver Broncos": {"abbr": "DEN", "color": "#0a2343"}, "Detroit Lions": {"abbr": "DET", "color": "#0076b6"}, "Green Bay Packers": {"abbr": "GB", "color": "#204e32"}, "Houston Texans": {"abbr": "HOU", "color": "#021018"}, "Indianapolis Colts": {"abbr": "IND", "color": "#003b75"}, "Jacksonville Jaguars": {"abbr": "JAX", "color": "#007487"}, "Kansas City Chiefs": {"abbr": "KC", "color": "#e31837"}, "Las Vegas Raiders": {"abbr": "LV", "color": "#000000"}, "Los Angeles Chargers": {"abbr": "LAC", "color": "#0080c6"}, "Los Angeles Rams": {"abbr": "LAR", "color": "#003594"}, "Miami Dolphins": {"abbr": "MIA", "color": "#008e97"}, "Minnesota Vikings": {"abbr": "MIN", "color": "#4f2683"}, "New England Patriots": {"abbr": "NE", "color": "#002a5c"}, "New Orleans Saints": {"abbr": "NO", "color": "#d3bc8d"}, "New York Giants": {"abbr": "NYG", "color": "#003c7f"}, "New York Jets": {"abbr": "NYJ", "color": "#115740"}, "Philadelphia Eagles": {"abbr": "PHI", "color": "#06424d"}, "Pittsburgh Steelers": {"abbr": "PIT", "color": "#000000"}, "San Francisco 49ers": {"abbr": "SF", "color": "#aa0000"}, "Seattle Seahawks": {"abbr": "SEA", "color": "#002a5c"}, "Tampa Bay Buccaneers": {"abbr": "TB", "color": "#bd1c36"}, "Tennessee Titans": {"abbr": "TEN", "color": "#4495d2"}, "Washington Commanders": {"abbr": "WSH", "color": "#5a1414"}};
 function liveWinMarkup(c,clubs){
  const other=clubs.find(x=>x.id!==c.id),p=other&&c.liveMatchups?.[other.id];
  if(!p)return '<div class="gm-live-h2h-win gm-live-small" data-h2h-win>Win Prob. —</div>';
  const value=probabilityText(p.win,matchupDone(clubs)),hue=120*Math.max(0,Math.min(1,p.win)),ink=`light-dark(hsl(${hue} 65% 28%),hsl(${hue} 68% 72%))`;
  return `<div class="gm-live-h2h-win" data-h2h-win title="Chance of winning this week's head-to-head matchup from the shared game-state scoring simulation. Tie probability is separate."><span>Win probability</span> <strong style="color:${ink}">${value}</strong>${tieMarkup(p)}</div>`;
 }
 function matchupCaption(clubs,weekData){
  const teams=weekData?.teams||clubs,players=teams.flatMap(c=>c.starters||[]),finished=p=>p.gameStatus==='Final'||p.gameStatus==='Bye';
  if(players.length&&players.every(finished))return 'Unofficial results';
  if(weekStarted(weekData||{teams}))return 'Live scores'+(clubs.some(c=>(c.starters||[]).some(playerLive))?' <span class="gm-live-live-key"><span class="gm-live-status-dot" aria-hidden="true">●</span> Game live</span>':'');
  return 'Pregame';
 }
 function lineupDot(t){const info=activeLineup(t.starters||[]),label=info.complete?'Complete Lineup':'Incomplete Lineup',detail=info.needs.length?' · Needs: '+info.needs.join(', '):'';return `<span class="wm-lineup-dot ${info.complete?'wm-complete':'wm-incomplete'}" role="img" aria-label="${escape(label+detail)}" title="${escape(label+detail)}"></span>`;}
 function lineupInfo(t){const info=activeLineup(t.starters||[]);return `<div class="wm-lineup-status"><span class="wm-muted">${info.active} active starters</span><span class="wm-lineup-flag ${info.complete?'wm-complete':'wm-incomplete'}">${lineupDot(t)} ${info.complete?'Complete Lineup':'Incomplete Lineup'}</span>${info.needs.length?`<span class="wm-lineup-needs">Needs: ${escape(info.needs.join(', '))}</span>`:''}${info.corrections.length?`<span class="wm-lineup-needs">${escape(info.corrections.join('; '))}</span>`:''}</div><div class="wm-muted wm-lineup-submitted">Lineup Submitted: ${escape(submissionTime(t.lineupSubmittedAt))}</div>`}
 function matchupHeader(t){
  const original=snapshot.teams.find(c=>c.id===lineupTarget?.anchorId)||t,ids=[original.id,...(original.opponentIds||[])];
  const clubs=ids.map(id=>{const named=DATA.weeks[DATA.through_week].find(c=>c.id===id),live=snapshot.teams.find(c=>c.id===id);return named&&live?{...named,...live}:null}).filter(Boolean);
  const tabs=clubs.map(c=>{const style=clubStyles[c.name]||{abbr:c.name,color:'#235789'},rgb=style.color.slice(1).match(/../g).map(h=>parseInt(h,16)),ink=rgb[0]*.299+rgb[1]*.587+rgb[2]*.114>160?'#111':'#fff',selected=c.id===t.id;return `<button type="button" role="tab" id="live-lineup-tab-${c.id}" class="gm-live-match-tab" style="--team-color:${style.color};--team-ink:${ink}" data-live-opponent="${c.id}" aria-label="${escape(c.name)} lineup" aria-selected="${selected}" aria-controls="live-starter-lineup-panel" tabindex="${selected?0:-1}">${escape(teamAbbr(c))}</button>`}).join('');
  const cards=clubs.map(c=>`<section class="gm-live-h2h-card" data-h2h-team="${c.id}">${c.logo?`<img src="${escape(c.logo)}" alt="">`:''}<div class="gm-live-h2h-name">${escape(c.name)}</div><strong class="gm-live-h2h-score" data-h2h-score><span class="wm-projection-anchor" ${weekStarted(snapshot)?`data-score-key="team:${c.id}" data-score-value="${Number(c.score).toFixed(1)}"`:""}>${Number(weekStarted(snapshot)?c.score:c.projectedScore??c.score).toFixed(1)}${weekStarted(snapshot)?'':projectedPointsMarkup(c,snapshot.teams,CONFERENCES)}${lineupDot(c)}</span><small>${weekStarted(snapshot)?"Points":"Proj. points"}</small></strong><span class="gm-live-h2h-proj" data-h2h-projection>${snapshot.forecastsPending?'Forecast updating…':weekStarted(snapshot)?"Proj. points "+Number(c.projectedScore??c.score).toFixed(1)+projectedPointsMarkup(c,snapshot.teams,CONFERENCES):"Points "+Number(c.score).toFixed(1)}</span>${liveWinMarkup(c,clubs)}${weekStarted(snapshot)?`<div class="gm-live-h2h-progress" data-h2h-progress>${activityMarkup(c,clubs,true)}</div>`:""}</section>`).join('<span class="gm-live-h2h-versus" aria-hidden="true">vs.</span>');
  return `<header class="gm-live-match-header"><div class="gm-live-h2h-caption">Week ${snapshot.week} · ${matchupCaption(clubs,snapshot)}</div><div class="gm-live-h2h-board" style="grid-template-columns:${clubs.map(()=> 'minmax(0,1fr)').join(' 18px ')}">${cards}</div><div class="gm-live-lineup-tabs" role="tablist" aria-label="Choose team lineup">${tabs}</div></header>`;
 }
 function playerRowMarkup(p,fmt){return `<tr class="${playerLive(p)?'gm-live-player-active':''}${playerOnField(p)?' gm-live-player-on-field':''}"><td class="gm-live-player-name" data-live-stats="${escape(p.id)}"><button type="button" class="gm-live-player-stat-name" data-live-stats="${escape(p.id)}" aria-label="${escape(displayPlayerName(p.name))} scoring breakdown" aria-haspopup="dialog" aria-controls="bonus-live-stat-popup" aria-expanded="false" style="border:0;background:none;padding:0;text-align:left;font:inherit;color:inherit;cursor:pointer;white-space:inherit">${playerOnFieldBall(p)}${escape(displayPlayerName(p.name))} ${escape(p.nflTeam)} ${escape(p.position)}${p.injuryStatus?` (<span class="gm-live-injury" title="${escape(p.injuryDetails||p.injuryStatus)}">${escape(p.injuryStatus)}</span>)`:''}</button></td><td data-player-label="Points" data-live-stats="${escape(p.id)}"><button type="button" class="gm-live-points" data-score-key="player:${escape(p.id)}" data-score-value="${Number(p.score).toFixed(1)}" data-live-stats="${escape(p.id)}" aria-label="${escape(displayPlayerName(p.name))} scoring breakdown" aria-haspopup="dialog" aria-controls="bonus-live-stat-popup" aria-expanded="false">${p.gameStatus==='Final'?`<strong>${fmt(p.score)}</strong>`:fmt(p.score)}</button></td><td data-player-label="Mins Rem">${clock(p.seconds)} <span class="gm-live-game-clock">[${escape(playerGameLabel(p))}]</span>${nflScoreMarkup(p)}</td><td data-player-label="FS Pregame Proj.">${fmt(p.pregameProjection)}${p.projectionSource==='YTD PPG'?'<span class="gm-live-no-fs" title="Uses YTD PPG because no Fantasy Sharks projection is available">†</span>':p.pregameProjection===null?' <span class="gm-live-no-fs" title="No Fantasy Sharks projection or YTD PPG available; adds zero remaining projected points">*</span>':''}</td><td data-player-label="Proj. Pts." title="${escape(p.pregameCalibrationId?`Calibrated pregame: ${fmt(p.calibratedPregameProjection)}. Expected final points use current scoring, calibrated pregame projection, game clock and NFL score context.`:`Expected final points use the shared game-state scoring model.`)}"><em>${fmt(p.liveProjection)}</em></td></tr>`}
 window.BonusLiveLineup={lineupEfficiency,sameStatsRegion,projectedPointsStanding,projectedPointsMarkup,weekStarted,activityMarkup,matchupLive,lineupDot,lineupInfo,projectionNotes,benchTotal,submissionTime,activeLineup,matchupStarted,teamAbbr,matchupDone,probabilityText,tieMarkup,canOverlay,bonusView,showStats,showTeamStats,closeStats,delayStatsClose,playerRowMarkup,sortedStarters,clock,matchupCaption,teamProgress,unitOnFieldMarkup};
 function projectionNotes(players){return `${players.some(p=>p.gameStatus?.startsWith('Awaiting'))?'<p class="gm-live-small">Awaiting NFL status confirmation. Projections and odds provisionally allow up to 10 minutes of overtime; the displayed clock is unchanged.</p>':''}${players.some(p=>p.projectionSource==='YTD PPG')?'<p class="gm-live-small">† No Fantasy Sharks projection available; using calibrated YTD PPG fallback</p>':''}${players.some(p=>p.pregameProjection===null)?'<p class="gm-live-small">* No FS projection or YTD PPG; zero additional projected points.</p>':''}`}
 function benchTotal(players){const fmt=v=>Number(v).toFixed(1);return `<tfoot><tr><th>Bench Total</th><td data-player-label="Points" data-score-key="bench-total" data-score-value="${fmt(players.reduce((n,p)=>n+p.score,0))}">${fmt(players.reduce((n,p)=>n+p.score,0))}</td><td data-player-label="Mins Rem">${clock(players.reduce((n,p)=>n+p.seconds,0))}</td><td data-player-label="FS Pregame Proj.">${fmt(players.reduce((n,p)=>n+(p.pregameProjection??0),0))}</td><td data-player-label="Proj. Pts."><em>${fmt(players.reduce((n,p)=>n+p.liveProjection,0))}</em></td></tr></tfoot>`}
 function benchMarkup(t){
  const players=sortedStarters(t.bench||[]),open=expandedBenches.has(t.id),fmt=v=>v===null||v===undefined?'—':Number(v).toFixed(1);
  return `<button type="button" class="gm-live-bench-toggle" data-live-bench="${t.id}" aria-expanded="${open}" aria-controls="live-bench-panel-${t.id}">${open?'Hide bench':'Show bench'}</button><div id="live-bench-panel-${t.id}" class="gm-live-bench-panel" ${open?'':'hidden'}><table class="gm-live-players" aria-label="Bench players"><colgroup><col><col style="width:55px"><col style="width:125px"><col style="width:78px"><col style="width:65px"></colgroup><thead><tr><th>Bench</th><th>Points</th><th>Mins Rem</th><th>FS Pregame Proj.</th><th>Proj. Pts.</th></tr></thead><tbody>${players.length?players.map(p=>playerRowMarkup(p,fmt)).join(''):'<tr><td colspan="5">No bench players reported.</td></tr>'}</tbody>${benchTotal(players)}</table>${players.some(p=>p.projectionSource==='YTD PPG')?'<p class="gm-live-small">† No Fantasy Sharks projection available; using calibrated YTD PPG fallback</p>':''}</div>`;
 }
 function starterMarkup(t){
  const players=sortedStarters(t.starters||[]),fmt=v=>v===null||v===undefined?'—':Number(v).toFixed(1);
  return `${matchupHeader(t)}<div class="gm-live-player-wrap" id="live-starter-lineup-panel" role="tabpanel" aria-labelledby="live-lineup-tab-${t.id}">${lineupInfo(t)}<table class="gm-live-players" aria-label="${escape(t.id)} starting players"><colgroup><col><col style="width:55px"><col style="width:125px"><col style="width:78px"><col style="width:65px"></colgroup><thead><tr><th>Starter</th><th>Points</th><th>Mins Rem</th><th>FS Pregame Proj.</th><th>Proj. Pts.</th></tr></thead><tbody>${players.map(p=>playerRowMarkup(p,fmt)).join('')}</tbody><tfoot><tr><th>Total Points</th><td data-player-label="Points" data-score-key="total:${t.id}" data-score-value="${Number(t.score).toFixed(1)}">${players.every(p=>p.gameStatus==='Final'||p.gameStatus==='Bye')?`<strong>${fmt(players.reduce((n,p)=>n+p.score,0))}</strong>`:fmt(players.reduce((n,p)=>n+p.score,0))}</td><td data-player-label="Mins Rem">${clock(players.reduce((n,p)=>n+p.seconds,0))}</td><td data-player-label="FS Pregame Proj.">${fmt(players.reduce((n,p)=>n+(p.pregameProjection??0),0))}</td><td data-player-label="Proj. Pts."><em>${fmt(t.projectedScore)}</em></td></tr></tfoot></table>${benchMarkup(t)}${projectionNotes(players)}</div>`;
 }
 function liveTeam(t,panel){return team(t).replace('data-team=','data-live-lineup=').replace('aria-describedby="bonus-team-popup"','aria-controls="bonus-live-lineup-popup"').replace(': show details',': show starting lineup').replace('<button ',`<button data-live-panel="${panel}" `)}
 function closeStats(){clearTimeout(statHideTimer);document.querySelectorAll('[data-live-stats][aria-expanded="true"]').forEach(b=>b.setAttribute('aria-expanded','false'));statPopup.hidden=true;statTarget=null}
 function delayStatsClose(){clearTimeout(statHideTimer);statHideTimer=setTimeout(closeStats,180)}
 // Position-specific event ordering from CHI Weekly Projections (lib/scoring-order.ts).
 const orderedScoreEvents = (() => {
 const labels = {"PC":"Completions","#FR":"Offensive Fumble Recovery TDs","#N":"Punts","BLP":"Blocked Punts","QH":"QB Hits","EM":"Extra Points Missed","FY":"Penalty Yards","EP":"Extra Points","FL":"Fumbles Lost (to Opponent)","C2":"Receiving 2 Pointers","FCY":"Opponent Fumble Recovery Yards","RY":"Rushing Yards","CC":"Receptions","PD":"Passes Defended","RA":"Rushes","TYA":"Total Net Yards Allowed","P2":"Passing 2 Pointers","ICY":"Interception Return Yards","#IR":"Interception Return TDs","TKL":"Tackles for a Loss","F":"Penalties","FF":"Forced Fumbles","#P":"Passing TDs","#R":"Rushing TDs","HBP":"Punts Had Blocked","#M":"Field Goals Missed","BLF":"Blocked Field Goals","SKY":"Sack Yards","SF":"Safeties","#T":"Defensive/Special Teams TDs","FUD":"Fumbles on Defense","TSK":"Sacks Against","#C":"Receiving TDs","CY":"Receiving Yards","TSY":"Sack Yards Lost","FD":"First Downs","FR":"yd Offensive Fumble Recovery TD","#F":"Field Goals Made","FUO":"Fumbles on Offense","BLE":"Blocked Extra Points","PA":"Pass Attempts","IT":"yd Int Had Returned for TD","FG":"yd Field Goal","FC":"Fumble Recoveries (from Opponent)","PI":"Punts Inside 20","PY":"Passing Yards","#IT":"Had Pass Ints Returned TDs","TPA":"Total Points Allowed","R2":"Rushing 2 Pointers","#BP":"Blocked Punt TDs","IC":"Interceptions","FUS":"Fumbles on Special Teams","D2":"Defensive Conversion Returns","IN":"Interceptions","OFC":"Number of Own Fumble Recoveries","#DR":"Defensive Fumble Recovery TDs","SK":"Sacked a QB","TK":"Tackles","#BF":"Blocked Field Goal TDs","AS":"Assists","TGT":"Targets","OFCY":"Own Fumble Recovery Yardage","PNY":"Punt Yards","SF1":"Safeties for 1 Point"};
 const display = {order:["#P","#IT","IT","P2","#R","R2","#C","C2","#F","FG","#M","EP","EM","#N","PNY","PI","HBP","FUO","FUS","FUD","FL","#DR","FCY","#FR","FR","OFC","OFCY","#IR","IC","ICY","PD","#BF","BLF","#BP","BLP","BLE","TK","AS","FF","FC","QH","SK","SKY","TKL","SF","TPA","TYA","D2","SF1","#T","FY","F","PA","PC","PY","IN","TSK","TSY","RY","RA","CY","CC","TGT","FD"]};
const order = new Map(display.order.map((code, index) => [code, index]));
const names = Object.entries(labels).sort((a, b) => b[1].length - a[1].length);
function scoringEventCode(row, passing = false) {
    if (row.eventCode)
        return row.eventCode;
    if (String(row.event).endsWith(' Interceptions'))
        return passing ? 'IN' : 'IC';
    // Historical browser caches predate eventCode; reorder them without refetching.
    return names.find(([, label]) => String(row.event).endsWith(' ' + label))?.[0];
}
const qbCodes = ['PC', 'PA', 'PY', '#P', 'IN', 'TSK', 'TSY', 'RA', 'RY', '#R', 'R2', 'FD', 'FUO', 'FL', 'FUS', 'OFC', 'OFCY', '#FR', 'FR'];
const qbOrder = new Map(qbCodes.map((code, index) => [code, index]));
const skillCodes = ['RA', 'RY', '#R', 'R2', 'CC', 'TGT', 'CY', '#C', 'C2', 'FD', 'FUO', 'FL', 'FUS', 'FUD', 'OFC', 'OFCY', '#FR', 'FR', 'FC', 'FCY', '#DR', 'TK', 'AS', 'TKL'];
const skillOrder = new Map(skillCodes.map((code, index) => [code, index]));
const defenseCodes = ['TK', 'AS', 'TKL', 'QH', 'SK', 'SKY', 'PD', 'FF', 'FC', 'FCY', '#DR', 'IC', 'ICY', '#IR', 'F', 'FY'];
const defenseOrder = new Map(defenseCodes.map((code, index) => [code, index]));
function orderScoringRows(rows, position) {
    const passing = rows.some(row => ['PA', 'PC', 'PY', 'IN'].includes(row.eventCode) || / (?:Pass Attempts|Completions|Passing Yards)$/.test(String(row.event)));
    const skill = ['RB', 'WR', 'TE'].includes(position ?? '') || (!position && !passing && rows.some(row => ['RA', 'RY', '#R', 'CC', 'TGT', 'CY', '#C'].includes(scoringEventCode(row, false) ?? '')));
    const defense = ['DT', 'DE', 'LB', 'CB', 'S'].includes(position ?? '') || (!position && !passing && !skill && rows.some(row => defenseCodes.includes(scoringEventCode(row, false) ?? '')));
    const selected = position === 'QB' || (!position && passing) ? qbOrder : skill ? skillOrder : defense ? defenseOrder : null;
    return rows.map((row, index) => { const code = scoringEventCode(row, passing) ?? ''; return { row, index, rank: selected ? (selected.get(code) ?? 1000 + (order.get(code) ?? 1000)) : (order.get(code) ?? Number.MAX_SAFE_INTEGER) }; })
        .sort((a, b) => a.rank - b.rank || a.index - b.index).map(x => x.row);
}
const teamSections = {
 'Passing': ['PC','PA','PY','#P','IN','TSK','TSY','P2','#IT','IT'],
 'Rushing': ['RA','RY','#R','R2'],
 'Receiving': ['CC','TGT','CY','#C','C2'],
 'First Downs': ['FD'],
 'Fumbles': ['FUO','FL','FUS','FUD','OFC','OFCY','#FR','FR'],
 'Defense': ['TK','AS','TKL','QH','SK','SKY','PD','FF','FC','FCY','#DR','IC','ICY','#IR','SF','SF1','D2','TPA','TYA'],
 'Special Teams': ['#F','FG','#M','EP','EM','#N','PNY','PI','HBP','BLF','#BF','BLP','#BP','BLE','#T'],
 'Penalties': ['F','FY']
};
const sectionForCode = new Map(Object.entries(teamSections).flatMap(([section,codes])=>codes.map(code=>[code,section])));
function teamStatRows(team,week){
 const groups=new Map(),missing=[];
 for(const player of team.starters||[]){
  const detail=matchingScoringDetails(player,week);
  if(!detail){
   if(Number(player.score)||player.gameStatus==='Final')missing.push(player);
   continue;
  }
  const passing=player.position==='QB'||detail.rows.some(r=>/ (?:Pass Attempts|Completions|Passing Yards)$/.test(r.event));
  for(const row of detail.rows){
   const match=String(row.event).match(/^([+-]?(?:\d+\.?\d*|\.\d+))\s+(.+)$/);
   const code=scoringEventCode(row,passing),label=match?.[2]||row.event,key=code||label;
   const item=groups.get(key)||{key,label:code==='IN'?'Interceptions thrown':code==='IC'?'Defensive interceptions':label,values:[],points:0};
   if(match)item.values.push(Number(match[1]));
   item.points+=Math.round(row.points*10);
   groups.set(key,item);
  }
 }
 const sequence=Array.from(sectionForCode.keys());
 const rank=key=>{const i=sequence.indexOf(key);return i<0?sequence.length:i;};
 const rows=Array.from(groups.values()).sort((a,b)=>rank(a.key)-rank(b.key)).map(item=>{
  const amount=item.values.reduce((sum,v)=>sum+v,0);
  const event=item.key==='FG'?('Field goals made ('+item.values.join(', ')+' yd)'):((item.values.length?Number(amount.toFixed(2))+' ':'')+item.label);
  return {event,points:item.points/10,section:sectionForCode.get(item.key)||'Other scoring'};
 });
 const adjustment=Number(team.scoreAdjustment)||0;
 if(adjustment)rows.push({section:'Scoring adjustments',event:'Team scoring adjustment',points:adjustment});
 const pending=missing.reduce((total,p)=>total+Number(p.score||0),0);
 if(pending)rows.push({section:'Scoring adjustments',event:'Starter points awaiting detail',points:pending});
 const difference=Math.round((team.score-rows.reduce((s,r)=>s+r.points,0))*10)/10;
 if(difference)rows.push({section:'Scoring adjustments',event:'Team total awaiting reconciliation',points:difference});
 return {rows,missing};
}
 orderScoringRows.teamStatRows=teamStatRows;
 return orderScoringRows;
 })();
 function showStats(pid,context=null){
  const sourceSnapshot=context?.snapshot||snapshot;
  const club=context?.club||snapshot?.teams.find(t=>t.id===lineupTarget?.id),p=[...(club?.starters||[]),...(club?.bench||[])].find(p=>p.id===pid),anchor=context?.anchor||lineup.querySelector(`[data-live-stats="${pid}"]`);if(!p||!anchor){closeStats();return}
  clearTimeout(statHideTimer);clearTimeout(lineupHideTimer);document.querySelectorAll('[data-live-stats][aria-expanded="true"]').forEach(b=>b.setAttribute('aria-expanded','false'));for(const trigger of anchor.closest('tr')?.querySelectorAll('[data-live-stats]')||[anchor])if(trigger.dataset.liveStats===String(pid))trigger.setAttribute('aria-expanded','true');statTarget={id:pid,teamId:club.id};statPopup.dataset.playerId=pid;
  const rawDetails=p.scoringDetails?.week===sourceSnapshot.week?p.scoringDetails:null,d=matchingScoringDetails(p,sourceSnapshot.week),source=`https://api.myfantasyleague.com/${sourceSnapshot.season}/player?L=${DATA.league==='ADL'?'60206':'22686'}&P=${encodeURIComponent(pid)}`;
  const gameIsLive=playerLive(p)&&!/^Awaiting/i.test(p.gameStatus||'');
  statPopup.innerHTML=`<header><div class="gm-live-stat-heading"><img class="gm-live-stat-photo" data-nfl-photo-id="${escape(pid)}" style="visibility:hidden" alt="${escape(displayPlayerName(p.name))}" width="40" height="54" onerror="this.style.visibility='hidden'"><div class="gm-live-stat-identity"><strong>${escape(displayPlayerName(p.name))} ${escape(p.nflTeam)} ${escape(p.position)}</strong><span>Week ${sourceSnapshot.week} · Scoring Details${gameIsLive?' · <span aria-hidden="true" style="color:#2563eb">●</span> Live':''}</span><div class="gm-live-stat-game" style="margin-top:5px;font-size:11px;line-height:1.4">${clock(p.seconds)} rem. <span class="gm-live-game-clock">[${escape(playerGameLabel(p))}]</span>${nflScoreMarkup(p)}</div></div><div class="gm-live-stat-total"><strong data-score-key="player:${pid}" data-score-value="${Number(p.score).toFixed(1)}">${Number(p.score).toFixed(1)}</strong><span>Points</span>${gameIsLive?`<div class="gm-live-stat-projected" style="display:grid;gap:2px;margin-top:5px"><strong style="font-size:13px;font-weight:600">${p.liveProjection==null?'—':Number(p.liveProjection).toFixed(1)}</strong><span style="font-size:9px">Proj. Points</span></div>`:''}</div></div>${d?.context?.map(text=>`<small>${escape(text)}</small>`).join('')||''}</header>${d?`<table aria-label="Player scoring events"><colgroup><col style="width:57px"><col></colgroup><thead><tr><th>Points</th><th>Event</th></tr></thead><tbody>${orderedScoreEvents(d.rows,p.position).map(r=>`<tr><td>${Number(r.points).toFixed(1)}</td><td>${escape(r.event)}</td></tr>`).join('')}</tbody><tfoot><tr><th>${Number(d.total).toFixed(1)}</th><th>Total</th></tr></tfoot></table>${Math.abs(d.total-p.score)>.05?'<p class="gm-live-stat-note">Scoring details are catching up to live Points.</p>':''}`:`<p class="gm-live-stat-note">${rawDetails?'MFL’s scoring breakdown is updating to match the current score.':p.score===0?'No scoring events reported yet.':'Detailed scoring is unavailable right now.'}</p>`}<footer>${d?.fetchedAt?`<span>MFL checked ${escape(stamp.format(new Date(d.fetchedAt)))}</span>`:''}<a href="${escape(source)}" target="_blank" rel="noopener noreferrer">Player page on MFL ↗</a></footer>`;
  nflPhotoPromise.then(photos=>{const img=statPopup.querySelector('[data-nfl-photo-id]');if(img?.dataset.nflPhotoId===String(pid)&&photos[pid]){img.src=photos[pid].replace('/f_auto,q_auto/','/f_auto,q_auto,w_160,h_160,c_fill/');img.style.visibility='visible'}});positionStatsPopup(anchor);
 }
 function showTeamStats(club,anchor,week){
  closeStats();clearTimeout(lineupHideTimer);
  for(const trigger of anchor.closest('tr').querySelectorAll('button[data-live-stats]'))trigger.setAttribute('aria-expanded','true');
  const {rows,missing}=orderedScoreEvents.teamStatRows(club,week);
  const groups=new Map();
  for(const row of rows){
   if(!groups.has(row.section))groups.set(row.section,[]);
   groups.get(row.section).push(row);
  }
  const body=Array.from(groups,([section,events])=>{
   const heading='<tr><th colspan="2" scope="rowgroup" style="text-align:left;padding:3px 7px;background:#eaf0f5;color:#354b5c;font-size:11px">'+escape(section)+'</th></tr>';
   const lines=events.map(r=>'<tr><td>'+Number(r.points).toFixed(1)+'</td><td>'+escape(r.event)+'</td></tr>').join('');
   return '<tbody>'+heading+lines+'</tbody>';
  }).join('');
  const metrics=lineupEfficiency(club);
  const name=p=>p?escape(displayPlayerName(p.name))+' '+escape(p.position)+' ('+Number(p.score||0).toFixed(1)+')':'Open slot';
  const swaps=metrics.potential==null?'A full legal lineup is unavailable.':metrics.potential<=club.score+.05?'The submitted lineup earned all available points.':metrics.swaps.map(({up,down})=>'<tr><td style="width:50%;text-align:left;white-space:normal">'+name(up)+'</td><td>'+name(down)+'</td></tr>').join('');
  const hasSwaps=metrics.potential>club.score+.05&&metrics.swaps.length;
  const swapPanel='<section><strong>Potential lineup'+(club.optimalLineup?' · MFL':' · provisional')+'</strong>'+(hasSwaps?'<table aria-label="Lineup changes"><thead><tr><th style="width:50%;text-align:left">Start instead</th><th>Move to bench</th></tr></thead><tbody>'+swaps+'</tbody></table>':'<p>'+swaps+'</p>')+'</section>';
  const logo=club.logo?'<img src="'+escape(club.logo)+'" alt="" width="32" height="32" style="object-fit:contain;vertical-align:middle;margin-right:7px">':'';
  statPopup.innerHTML='<header><strong>'+logo+escape(club.name)+'</strong><small>Week '+escape(week)+' · Starting lineup</small></header>'+swapPanel+'<table aria-label="Team scoring breakdown"><thead><tr><th>Points</th><th>Team stat line</th></tr></thead>'+(body||'<tbody><tr><td colspan="2">No scoring events reported yet.</td></tr></tbody>')+'<tfoot><tr><th>'+Number(club.score).toFixed(1)+'</th><th>Total Points</th></tr></tfoot></table>'+(missing.length?'<p class="gm-live-stat-note">Awaiting detail for '+missing.map(p=>escape(displayPlayerName(p.name))).join(', ')+'.</p>':'');
  positionStatsPopup(anchor);
 }
 function positionStatsPopup(anchor){statPopup.style.maxHeight='calc(100vh - 16px)';statPopup.style.overflowY='auto';statPopup.hidden=false;const cells=anchor.closest('tr')?.cells,nameBox=cells?.[0]?.getBoundingClientRect(),scoreBox=cells?.[1]?.getBoundingClientRect(),a=nameBox&&scoreBox?{left:Math.min(nameBox.left,scoreBox.left),right:Math.max(nameBox.right,scoreBox.right),top:Math.min(nameBox.top,scoreBox.top)}:anchor.getBoundingClientRect(),b=statPopup.getBoundingClientRect();statPopup.style.left=Math.max(8,Math.min(a.right+7+b.width<=innerWidth-8?a.right+7:a.left-b.width-7,innerWidth-b.width-8))+'px';statPopup.style.top=Math.max(8,Math.min(a.top-8,innerHeight-b.height-8))+'px';
 }
 function closeLineup(){closeStats();clearTimeout(lineupHideTimer);container.querySelectorAll('[data-live-lineup][aria-expanded="true"]').forEach(b=>b.setAttribute('aria-expanded','false'));lineup.hidden=true;lineupTarget=null}
 function delayLineupClose(){clearTimeout(lineupHideTimer);lineupHideTimer=setTimeout(closeLineup,180)}
 function showLineup(id,panel,anchorId=id){
  if(state.race!=='Live'||!snapshot)return;clearTimeout(lineupHideTimer);closePopup();
  const button=container.querySelector(`[data-live-panel="${panel}"][data-live-lineup="${anchorId}"]`),t=snapshot.teams.find(t=>t.id===id),named=DATA.weeks[DATA.through_week].find(t=>t.id===id);if(!button||!t)return;
  container.querySelectorAll('[data-live-lineup][aria-expanded="true"]').forEach(b=>b.setAttribute('aria-expanded','false'));button.setAttribute('aria-expanded','true');lineupTarget={id,panel,anchorId};lineup.dataset.teamId=id;lineup.dataset.anchorId=anchorId;
  lineup.innerHTML=starterMarkup({...named,...t,starters:t.starters,bench:t.bench,projectedScore:t.projectedScore,opponentIds:t.opponentIds});lineup.hidden=false;
  const box=$('bonus-design').getBoundingClientRect(),target=button.getBoundingClientRect();const cells=[...lineup.querySelectorAll('.gm-live-player-name')],ctx=document.createElement('canvas').getContext('2d');ctx.font=cells.length?getComputedStyle(cells[0]).font:'10px sans-serif';const starterWidth=Math.ceil(Math.max(0,...cells.map(c=>{ctx.font=getComputedStyle(c).font;const text=c.cloneNode(true);text.querySelectorAll('svg').forEach(n=>n.remove());return ctx.measureText(text.textContent).width+(c.querySelector('svg')?16:0)})))+10;lineup.querySelectorAll('.gm-live-players col:first-child').forEach(c=>c.style.width=starterWidth+'px');const scrollbarWidth=Math.max(0,lineup.offsetWidth-lineup.clientWidth-2);lineup.style.width=Math.min(starterWidth+349+scrollbarWidth,window.innerWidth-24)+'px';lineup.style.maxHeight=Math.min(660,window.innerHeight-24)+'px';
  const bounds=lineup.getBoundingClientRect();lineup.style.left=Math.max(12,Math.min(target.right+10,window.innerWidth-bounds.width-12))-box.left+'px';lineup.style.top=Math.max(12,Math.min(target.bottom+9,window.innerHeight-bounds.height-12))-box.top+'px';
  if(statTarget){if(statTarget.teamId===id)showStats(statTarget.id);else closeStats()}
 }
 container.addEventListener('mouseover',e=>{const b=e.target.closest('[data-live-lineup]');if(b&&!b.contains(e.relatedTarget))showLineup(b.dataset.liveLineup,b.dataset.livePanel)});
 container.addEventListener('mouseout',e=>{const b=e.target.closest('[data-live-lineup]');if(b&&!b.contains(e.relatedTarget)&&!lineup.contains(e.relatedTarget))delayLineupClose()});
 container.addEventListener('focusin',e=>{const b=e.target.closest('[data-live-lineup]');if(b)showLineup(b.dataset.liveLineup,b.dataset.livePanel)});
 container.addEventListener('focusout',e=>{if(e.target.closest('[data-live-lineup]')&&!lineup.contains(e.relatedTarget))delayLineupClose()});
 lineup.addEventListener('click',e=>{const b=e.target.closest('[data-live-bench]');if(!b)return;e.preventDefault();e.stopPropagation();const id=b.dataset.liveBench,open=!expandedBenches.has(id);if(open)expandedBenches.add(id);else expandedBenches.delete(id);b.setAttribute('aria-expanded',String(open));b.textContent=open?'Hide bench':'Show bench';const panel=lineup.querySelector(`#live-bench-panel-${id}`);if(panel)panel.hidden=!open;lineup.style.maxHeight=Math.min(660,Math.max(180,window.innerHeight-lineup.getBoundingClientRect().top-12))+'px';clearTimeout(lineupHideTimer)});
 lineup.addEventListener('click',e=>{const b=e.target.closest('[data-live-opponent]');if(!b||!lineupTarget)return;e.preventDefault();e.stopPropagation();const {panel,anchorId}=lineupTarget;showLineup(b.dataset.liveOpponent,panel,anchorId);lineup.querySelector('[data-live-opponent][aria-selected="true"]')?.focus({preventScroll:true})});
 lineup.addEventListener('keydown',e=>{const tab=e.target.closest('.gm-live-match-tab');if(!tab||!['ArrowLeft','ArrowRight','Home','End'].includes(e.key)||!lineupTarget)return;e.preventDefault();e.stopPropagation();const tabs=[...lineup.querySelectorAll('.gm-live-match-tab')],i=tabs.indexOf(tab),next=e.key==='Home'?0:e.key==='End'?tabs.length-1:(i+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length,{panel,anchorId}=lineupTarget;showLineup(tabs[next].dataset.liveOpponent,panel,anchorId);lineup.querySelector('[aria-selected="true"]')?.focus({preventScroll:true})});
 lineup.addEventListener('mouseenter',()=>clearTimeout(lineupHideTimer));lineup.addEventListener('mouseleave',e=>{if(!statPopup.contains(e.relatedTarget))delayLineupClose()});lineup.addEventListener('focusin',()=>clearTimeout(lineupHideTimer));lineup.addEventListener('focusout',e=>{if(!lineup.contains(e.relatedTarget)&&!statPopup.contains(e.relatedTarget))delayLineupClose()});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'){if(!statPopup.hidden)closeStats();else closeLineup()}});document.addEventListener('click',e=>{if(!e.target.closest('[data-live-lineup],[data-live-stats]')&&!lineup.contains(e.target)&&!statPopup.contains(e.target))closeLineup()});
 lineup.addEventListener('mouseover',e=>{const b=e.target.closest('[data-live-stats]');if(b&&!sameStatsRegion(b,e.relatedTarget))showStats(b.dataset.liveStats)});
 lineup.addEventListener('mouseout',e=>{const b=e.target.closest('[data-live-stats]');if(b&&!sameStatsRegion(b,e.relatedTarget)&&!statPopup.contains(e.relatedTarget))delayStatsClose()});
 lineup.addEventListener('focusin',e=>{const b=e.target.closest('[data-live-stats]');if(b)showStats(b.dataset.liveStats)});
 lineup.addEventListener('click',e=>{const b=e.target.closest('[data-live-stats]');if(b){e.preventDefault();e.stopPropagation();showStats(b.dataset.liveStats)}});
 lineup.addEventListener('scroll',closeStats,true);
 statPopup.addEventListener('mouseenter',()=>{clearTimeout(statHideTimer);clearTimeout(lineupHideTimer)});statPopup.addEventListener('mouseleave',e=>{delayStatsClose();if(!lineup.contains(e.relatedTarget))delayLineupClose()});
 statPopup.addEventListener('focusin',()=>{clearTimeout(statHideTimer);clearTimeout(lineupHideTimer)});statPopup.addEventListener('focusout',e=>{if(!statPopup.contains(e.relatedTarget)){delayStatsClose();if(!lineup.contains(e.relatedTarget))delayLineupClose()}});
 const repositionLineup=()=>{if(lineupTarget)showLineup(lineupTarget.id,lineupTarget.panel,lineupTarget.anchorId)};window.addEventListener('resize',repositionLineup);window.addEventListener('scroll',repositionLineup,{passive:true});for(const scroll of container.querySelectorAll('.gm-scroll'))scroll.addEventListener('scroll',closeLineup);
 function paintStatus(intro='Hover over a team for live scoring details',displaySnapshot=snapshot){
  const shown=displaySnapshot,notice=shown?.fetchedAt===snapshot?.fetchedAt?refreshNotice:'';
  const age=shown?Date.now()-Date.parse(shown.fetchedAt):Infinity,stale=inWindow()&&age>150000;
  $('status-dot').className='gm-dot '+(error||stale?'preliminary':shown?'live':'');$('status').textContent=error?(shown?'Could not load newer scores · showing last update':'Live feed unavailable'):busy?'Refreshing MFL lineups and scores…':notice?notice+(stale?' · Waiting for newer scores':''):shown?(stale?'Waiting for newer scores · ':'')+'Checked '+stamp.format(new Date(shown.fetchedAt)):'Loading live scores…';$('status').setAttribute('aria-live','polite');
  $('race-summary').hidden=false;$('race-summary').innerHTML=`<span>${intro}</span><div class="gm-live-refresh-controls"><div class="gm-live-refresh-copy"><span>${shown?.forecastsPending?'Lineups and scores are fresh · model projections and odds await the next complete collector update.':'Scores re-scraped about once per minute during live hours.'}</span><span class="gm-live-score-age">${shown?'MFL lineups & scores checked: '+stamp.format(new Date(shown.fetchedAt))+' · '+(age<60000?Math.max(0,Math.floor(age/1000))+'s':Math.floor(age/60000)+'m')+' ago'+(stale?' · Waiting for newer scores.':''):''}</span></div><button type="button" class="gm-live-refresh" data-live-refresh ${busy?'disabled aria-busy="true"':''}>${busy?'Refreshing…':'Refresh'}</button></div>`;
 }
 const activeLiveTab=()=>state.race==='Live'||(state.race==='Matchups'&&window.WeeklyMatchups?.isLiveWeek());
 const announce=()=>document.dispatchEvent(new CustomEvent('bonus-live-update'));
 function draw(){
  if(state.race!=='Live')return;if(snapshot?.forecastsPending&&view==='projected')view='current';closePopup();container.hidden=false;$('race-view').hidden=true;document.querySelector('.gm-outlook-nav').hidden=true;document.querySelector('.gm-method').hidden=true;$('download').hidden=true;
  document.querySelectorAll('[data-race]').forEach(b=>{const yes=b.dataset.race==='Live';b.setAttribute('aria-selected',yes);b.tabIndex=yes?0:-1});container.querySelectorAll('[data-live-view]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.liveView===view));$('gm-live-search').value=$('search').value;
  $('outlook').textContent='Live Bonus Game Watch';$('through').textContent=snapshot?.bonusComplete?'Bonus Games complete · Live matchups: Week '+snapshot.week:snapshot?'Week '+snapshot.week+' · '+(matchupCaption(snapshot.teams,snapshot)==='Unofficial results'?'Unofficial results':'Provisional live standings'):'Current MFL live scoring';$('race-caption').textContent=schedule;$('table-guide').textContent=view==='projected'?'Projected points use current scoring, calibrated pregame estimates, game clock and NFL score context.':'';
  paintStatus();
  if(!snapshot){$('footer').textContent='Waiting for a complete 32-team MFL live snapshot. '+schedule;return}
  panelMarkup('quarter');panelMarkup('season');if(lineupTarget)showLineup(lineupTarget.id,lineupTarget.panel,lineupTarget.anchorId);
  $('footer').textContent=(view==='projected'?'Projections finish the current week only; later weeks are not added. Missing FS projections use YTD PPG when available. ':'')+(snapshot.bonusComplete||snapshot.complete?'Regular-season Bonus Games complete. ':'Provisional MFL live scores; official results remain in the quarterly tabs. ')+(inWindow()&&!snapshot.complete?'Automatic refresh every minute.':'Automatic refresh paused outside live-watch hours.')+(snapshot.teams.some(t=>t.potential===null)?' An unavailable Potential tiebreaker remains tied.':'');
 }
 async function refresh(force=false,full=false){
  if(busy||(!force&&!inWindow())||!activeLiveTab())return;const minute=Math.floor(Date.now()/60000);if(!force&&minute===lastAttempt)return;lastAttempt=minute;busy=true;error='';refreshNotice='';draw();announce();
  try{if(full&&snapshot){snapshot=await readMflRefresh(snapshot);error='';refreshNotice='Lineups and scores refreshed from MFL at '+stamp.format(new Date(snapshot.fetchedAt));return;}const url=`https://raw.githubusercontent.com/TheMathNinja/${DATA.league}-GM-Dashboard/live-bonus-watch/live.json?${force?'refresh='+Date.now()+'-'+Math.random().toString(36).slice(2):'minute='+minute}`;const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(20000)});if(!r.ok)throw Error('Live snapshot unavailable');let data=await r.json();if((inWindow()&&Date.now()-Date.parse(data.fetchedAt)>90000)||(snapshot&&Date.parse(data.fetchedAt)<Date.parse(snapshot.fetchedAt))){
    // Raw branch URLs can serve an older CDN copy despite cache-busting. Use
    // the public contents API only when that copy is stale or moves backward.
    try{const latest=await fetch(`https://api.github.com/repos/TheMathNinja/${DATA.league}-GM-Dashboard/contents/live.json?ref=live-bonus-watch&check=${Date.now()}`,{cache:'no-store',headers:{Accept:'application/vnd.github.raw+json'},signal:AbortSignal.timeout(15000)});if(!latest.ok)throw Error('Newest score check unavailable');let candidate=await latest.json();if(candidate.encoding==='base64'&&candidate.content)candidate=JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(candidate.content.replace(/\s/g,'')),c=>c.charCodeAt(0))));if(Date.parse(candidate.fetchedAt)>=Date.parse(data.fetchedAt))data=candidate}catch(e){error=String(e.message||e)}
   }if(data.league!==DATA.league||data.season!==DATA.season)throw Error('Wrong scoring season');const races=bonusView(data);if(!races)throw Error('Completed Bonus standings unavailable');standings(races);standings(races,true);standings(races,false,true);standings(races,true,true);const unchanged=snapshot&&JSON.stringify(snapshot.teams)===JSON.stringify(data.teams)&&JSON.stringify(snapshot.completed)===JSON.stringify(data.completed);if(!force&&snapshot?.forecastsPending&&Date.parse(data.fetchedAt)<Date.parse(snapshot.fetchedAt)){refreshNotice='Lineups and scores are fresh · waiting for updated model forecasts';return;}if(full&&snapshot&&Date.parse(data.fetchedAt)<Date.parse(snapshot.fetchedAt))data=snapshot;if(snapshot&&Date.parse(data.fetchedAt)<Date.parse(snapshot.fetchedAt))throw Error('Older live snapshot received');if(full){data=await readMflRefresh(data);error='';}snapshot=data;if(full)refreshNotice='Lineups and scores refreshed from MFL at '+stamp.format(new Date(data.fetchedAt));else if(force)refreshNotice='Loaded published MFL snapshot from '+stamp.format(new Date(data.fetchedAt))}catch(e){error=String(e.message||e)}finally{busy=false;draw();announce()}
 }
 function renderLive(){draw();if(!snapshot)refresh(true);else refresh(false)}
 window.BonusLiveWatch={render:renderLive,leave,refresh,paintStatus,getSnapshot:()=>snapshot,getBusy:()=>busy,schedule,inWindow};
 document.addEventListener('click',e=>{if(state.race!=='Live')return;const b=e.target.closest('[data-live-refresh],[data-live-sort],[data-live-view],[data-live-lineup]');if(!b)return;if(b.hasAttribute('data-live-view')){view=b.dataset.liveView;draw()}else if(b.hasAttribute('data-live-lineup')){showLineup(b.dataset.liveLineup,b.dataset.livePanel)}else if(b.hasAttribute('data-live-refresh'))refresh(true,true);else{const cfg=sorts[b.dataset.livePanel],key=b.dataset.liveSort;cfg.dir=key===cfg.key?-cfg.dir:key==='rank'||key==='name'?1:-1;cfg.key=key;draw()}});
 document.addEventListener('visibilitychange',()=>{if(!document.hidden&&activeLiveTab())refresh(false)});
 function tick(){if(!document.hidden&&activeLiveTab()){draw();announce();refresh(false)}setTimeout(tick,60100-Date.now()%60000)}setTimeout(tick,60100-Date.now()%60000);
 if(state.race==='Live')renderLive();
})();

