const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),dir=path.join(root,'docs/trophy-room');
const context=vm.createContext({esc:s=>String(s),logo:()=>'',nflTeamCode:s=>s,teamEntry:s=>s,teams:{}});
const trophy=fs.readFileSync(path.join(dir,'trophy.js'),'utf8');
vm.runInContext(trophy.slice(trophy.indexOf('function rosterMarkup('),trophy.indexOf('function fetchRoster(')),context);
vm.runInContext(fs.readFileSync(path.join(dir,'seasonlong.js'),'utf8'),context);
const payload=JSON.parse(fs.readFileSync(path.join(dir,'seasonlong-performances.json')));
context.payload=payload;vm.runInContext('slData=payload',context);
let tested=0;
for(const mode of ['native','current'])for(const phase of ['regular','playoffs','combined'])for(const metric of ['record','allplay','total','offense','defense','potential'])for(const conf of ['NFC','AFC']){
 const row=payload.modes[mode].teams[phase][conf][metric][0];if(!row)continue;
 const d=payload.details[row.detail],roster=JSON.parse(fs.readFileSync(path.join(dir,'rosters',d.year+'.json')));
 context.d=d;context.roster=roster;
 vm.runInContext('slFinalRosters.set(d.year,roster)',context);
 const html=vm.runInContext("seasonlongTeamMarkup(d,'test',d.score.toFixed(2))",context);
 const timeline=vm.runInContext('slTeamTimeline(d)',context);
 if(metric==='record'){
  assert.match(html,/>Matchup</);assert.match(html,/sl-game-result/);
  if(phase!=='playoffs')assert.match(timeline,/sl-bonus-event/);
 }else{
  assert.doesNotMatch(timeline,/sl-game-result|sl-game-score|sl-bonus-event|v\. |@ /);
  assert.doesNotMatch(html,/>Matchup<|H2H /);
  if(metric==='allplay')assert.match(html,/All-Play Record/);
  else {assert.match(html,/Cum\. PPG/);assert.match(html,/games ·/);assert.match(timeline,new RegExp(d.score.toFixed(2).replace('.','\\.')));}
 }
 const positions=[...html.matchAll(/class="roster-position">([^<]+)/g)].map(m=>m[1]);assert.ok(positions.length);
 if(metric==='offense')assert.ok(positions.every(p=>['QB','RB','WR','TE','PK','K','PN','P','KR'].includes(p)));
 if(metric==='defense')assert.ok(positions.every(p=>['DT','DE','DL','LB','CB','S','DB'].includes(p)));
 if(metric==='potential')assert.doesNotMatch(html,/Starter Pts|Starter PPG/);
 else assert.match(html,/Starter Pts/);
 tested++;
}
const defaultRoster=vm.runInContext('rosterMarkup(roster,d.franchise)',context);assert.match(defaultRoster,/Starter Pts/);
console.log('Verified metric-specific timeline and roster rendering:',tested,'mode/phase/conference views; default roster preserved.');
