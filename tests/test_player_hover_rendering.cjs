const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),dir=path.join(root,'docs/trophy-room');
const c=vm.createContext({esc:s=>String(s),performancePlayerName:s=>s,nflTeamCode:s=>s});
const trophy=fs.readFileSync(path.join(dir,'trophy.js'),'utf8');vm.runInContext(trophy.slice(trophy.indexOf('function playerScoringMarkup(')),c);
vm.runInContext(fs.readFileSync(path.join(dir,'seasonlong.js'),'utf8'),c);
c.scoring={rows:[{value:0,event:'0 Fumbles on Offense',points:0},{value:0,event:'0 Penalty Yards',points:0},{value:10,event:'10 Passing Yards',points:2},{value:1,event:'1 Actual Event',points:0},{value:1,event:'1 Penalty',points:-1}],total:1};
let html=vm.runInContext('playerScoringMarkup(scoring,1)',c);
assert.doesNotMatch(html,/0 Fumbles|0 Penalty Yards/);assert.match(html,/10 Passing Yards/);assert.match(html,/1 Penalty/);assert.match(html,/1 Actual Event/);assert.match(html,/>Total</);
assert.equal(c.scoring.rows.length,5,'Filtering must not mutate source stat rows');
const data=JSON.parse(fs.readFileSync(path.join(dir,'seasonlong-performances.json')));c.data=data;vm.runInContext('slData=data',c);
for(const mode of ['native','current']){
 const d=Object.values(data.details).find(d=>d.kind==='season-player'&&d.mode===mode&&d.phase==='combined'&&d.position==='QB');
 c.d=d;c.bank=JSON.parse(fs.readFileSync(path.join(dir,'player-game-breakdowns',d.year+'.json')));vm.runInContext('slPlayerBanks.set(d.year,bank)',c);
 html=vm.runInContext("seasonlongPlayerMarkup(d,'test',d.score.toFixed(1))",c);
 for(const w of d.weeks){
  if(w.score!==null){const score=w.score.toFixed(1);assert.ok(html.includes(`<tr><td>${w.week}</td><td class="num"><button`));assert.ok(html.includes(`>${score} ▸</button>`));}
  else assert.ok(html.includes(`<tr><td>${w.week}</td><td class="num">${w.status}</td>`));
 }
 assert.doesNotMatch(html,/>0 (?:Fumbles on Offense|Penalty Yards|Passing 2 Pointers)</);
}
console.log('Verified zero stat rows hidden, meaningful stats/totals retained, source unchanged, and score-column expansion in both scoring modes.');
