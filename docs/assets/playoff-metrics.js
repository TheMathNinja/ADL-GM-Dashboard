// Shared display contract for ADL and FAFL. Consumes published results only.
(function(global){
 'use strict';
 const num=v=>v===null||v===undefined||v===''?null:Number.isFinite(Number(v))?Number(v):null;
 const all=c=>Object.values(c.data).flat();
 const rank=(values,value)=>value===null?null:{rank:1+values.filter(v=>v!==null&&v>value+1e-6).length,tied:values.filter(v=>v!==null&&Math.abs(v-value)<=1e-6).length>1};
 const label=(c,r)=>r?(r.tied?'T-':'')+c.ordinal(r.rank):'&mdash;';
 const row=(c,name,value,r,ink,title='')=>`<div class="${c.prefix}-breakdown-row" style="--rank-ink:${ink||(r?c.rankInk(r.rank):'var(--'+c.prefix+'-muted)')}"${title?' title="'+title+'"':''}><span class="${c.prefix}-breakdown-name">${name}</span><strong>${value}</strong><span class="${c.prefix}-rank">${label(c,r)}</span></div>`;
 const fixed=(value,digits=1)=>num(value)===null?'&mdash;':Number(value).toFixed(digits);
 const forecast=(c,t)=>Object.values(c.draft).flat().find(r=>r.franchise_id&&r.franchise_id===t.franchise_id||r.name===t.name);
 function remainingPpg(c,t){const f=forecast(c,t),weeks=12-c.throughWeek;if(weeks<=0)return null;const end=num(f?.projectedPoints??t.projectedPoints),current=num(f?.currentPoints??t.pointsTotal);return end!==null&&current!==null?(end-current)/weeks:num(t.projectedPPG);}
 function winsSummary(c,t){
  const teams=all(c),potential=num(t.pot),strength=num(t.rosterStrength),sos=num(t.remainingSos),ppg=remainingPpg(c,t),ap=num(t.predPct);
  let top=row(c,'Potential PPG',fixed(potential),rank(teams.map(x=>num(x.pot)),potential));
  if(c.prefix!=='fafl')top+=row(c,'Roster Strength',fixed(strength),rank(teams.map(x=>num(x.rosterStrength)),strength),null,strength===null?'Independent roster-strength rating is unavailable in this published snapshot.':'');
  const sr=rank(teams.map(x=>num(x.remainingSos)),sos);top+=row(c,'Remaining SoS',sos===null?'&mdash;':fixed(sos)+'%',sr,sr?c.rankInk(33-sr.rank):null);
  let bottom=row(c,'Proj. Remaining PPG',fixed(ppg),rank(teams.map(x=>remainingPpg(c,x)),ppg));
  bottom+=row(c,'Proj. All-Play %',ap===null?'&mdash;':fixed(ap)+'%',rank(teams.map(x=>num(x.predPct)),ap));
  const seed=num(t.playoffSeed),outside=seed===null;bottom+=row(c,'Proj. Playoff Seed',outside?'Out':'#'+seed,null,outside?'var(--'+c.prefix+'-muted)':c.rankInk(seed,16));
  return top+`<div class="${c.prefix}-projection-divider" role="separator"></div>`+bottom;
 }
 function draftPotential(c,t){
  const f=forecast(c,t)||{},projected=c.state.draftPicture==='projected',pick=x=>num(projected?(x.projectedPotentialPPG??(num(x.potential)!==null?x.potential/12:null)):x.currentPotentialPPG),value=pick(f),r=rank(Object.values(c.draft).flat().map(pick),value),weeks=t.actualDetails?.weeks||[];
  const complete=weeks.length&&weeks.every(g=>num(g.potentialPoints)!==null),total=complete?weeks.reduce((n,g)=>n+Number(g.potentialPoints),0):num(t.potentialPointsTotal??f.currentPotential);
  return `<div class="${c.prefix}-popup-top">${c.featureMarkup(fixed(value),projected?'Projected Potential PPG':'Potential PPG',r)}<img class="${c.prefix}-popup-logo" src="${t.logo}" alt="${t.name}"></div><div class="${c.prefix}-breakdown-label">Breakdown <span>Rank</span></div>`+row(c,'Potential Points to Date',fixed(total),null)+`<button type="button" class="${c.prefix}-detail-expand" aria-expanded="false"><span>Show Weekly Details</span><span class="${c.prefix}-detail-arrow" aria-hidden="true">&#8600;</span></button><div class="${c.prefix}-win-details" hidden><div class="${c.prefix}-win-section ${c.prefix}-ppg-history-section"><span>Week</span><span>Potential Points</span><span>Rank</span></div>${weeks.map(g=>{const value=num(g.potentialPoints),r=value===null?null:c.weeklyRank(g.week,'potentialPoints',value),ink=r?c.rankInk(r.rank):'var(--'+c.prefix+'-muted)';return `<div class="${c.prefix}-history-row ${c.prefix}-ppg-history-row"><span>Week ${g.week}</span><strong style="color:${ink}">${fixed(value)}</strong><b style="color:${ink}">${label(c,r)}</b></div>`;}).join('')}</div>`;
 }
 function projectedAllPlay(c,t){
  const teams=all(c),value=num(t.predPct),r=rank(teams.map(x=>num(x.predPct)),value),current=num(t.apPct),currentRank=rank(teams.map(x=>num(x.apPct)),current);
  return `<div class="${c.prefix}-popup-top">${c.featureMarkup(value===null?'&mdash;':fixed(value)+'%','Projected All-Play %',r)}<img class="${c.prefix}-popup-logo" src="${t.logo}" alt="${t.name}"></div><div class="${c.prefix}-breakdown-label">Breakdown <span>Rank</span></div>`+row(c,'Current All-Play %',current===null?'&mdash;':fixed(current*100)+'%',currentRank)+row(c,'Projected All-Play %',value===null?'&mdash;':fixed(value)+'%',r);
 }
 global.GMPlayoffMetrics=Object.freeze({version:'20261112-parity-v1',winsSummary,draftPotential,projectedAllPlay});
})(window);

