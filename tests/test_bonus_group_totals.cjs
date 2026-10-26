const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.resolve(__dirname,'..'),html=fs.readFileSync(path.join(root,'docs/bonus-games/index.html'),'utf8');
for(const file of ['docs/bonus-games/index.html','scripts/bonus_template.html']){
 const text=fs.readFileSync(path.join(root,file),'utf8');for(const m of text.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))if(m[1].trim())new vm.Script(m[1].replace('__DATA__','{}').replace('__CONFERENCES__','{}'));
 assert(!text.includes('All teams included. Records are W-L-T; projected wins count ties as Â½ win.'));
 assert(text.includes('table .gm-group-record'));assert(text.includes('white-space:nowrap!important'));
}
const literal=(start,end)=>JSON.parse(html.slice(html.indexOf(start)+start.length,html.indexOf(end,html.indexOf(start))));
const data=literal('const DATA=',';const CONFERENCES='),conferences=literal('const CONFERENCES=',';const DIVISIONS='),divisions=literal('const DIVISIONS=',';const $=');
const ctx=vm.createContext({console,DATA:data,CONFERENCES:conferences,DIVISIONS:divisions,state:{race:'Overview'},selectedWeek:data.through_week,esc:v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))});
vm.runInContext('function $(id){return {value:String(selectedWeek)}}',ctx);
for(const name of ['conferenceRecord','conferenceGroups','conferenceTable','conferenceRecordButton','quarterAllPlay','cumulativeBonusRecord','weeklyPerformance','projectedWins','conferenceSummary']){
 let start=html.indexOf('function '+name+'('),end=html.indexOf('\nfunction ',start+1);assert(start>=0);vm.runInContext(html.slice(start,end),ctx);
}
vm.runInContext('const originalConferenceTable=conferenceTable;conferenceTable=(headers,rows,note)=>{captured={headers,rows,note};return originalConferenceTable(headers,rows,note)}',ctx);
const get=x=>JSON.parse(JSON.stringify(vm.runInContext(x,ctx)));
for(let week=1;week<=data.through_week;week++)for(const race of ['Overview','Q1','Q2','Q3','Q4','All-Season']){
 ctx.selectedWeek=week;ctx.state.race=race;const rendered=vm.runInContext('conferenceSummary(DATA.weeks[selectedWeek])',ctx),summary=get('captured');
 assert.equal(summary.rows.length,10);assert.equal((rendered.match(/data-total-conference=/g)||[]).length,2);assert.equal((rendered.match(/class="gm-division-name"/g)||[]).length,8);
 const groups=get('conferenceGroups(DATA.weeks[selectedWeek])');assert.equal(groups.filter(g=>!g.isDivision).length,2);
 for(const conf of ['NFC','AFC']){
  const parent=groups.find(g=>g.key===conf),children=groups.filter(g=>g.isDivision&&g.conference===conf);assert.equal(parent.ids.length,16);assert(children.every(g=>g.ids.length===4));assert.deepEqual(children.flatMap(g=>g.ids).sort(),parent.ids.slice().sort());
  const rows=summary.rows.filter(row=>row[0].conference===conf),record=text=>text.match(/\d+-\d+-\d+/)[0].split('-').map(Number),sumRecord=(values)=>values.reduce((a,b)=>a.map((n,i)=>n+b[i]),[0,0,0]);
  if(race==='Overview'){
   assert.equal(summary.note,'');assert.deepEqual(record(rows[0][1]),sumRecord(rows.slice(1).map(row=>record(row[1]))));assert(rows.every(row=>/^<strong>\d+\.\d<\/strong>$/.test(row.at(-1))));
   for(const t of data.weeks[week])assert(/^\d+\.\d$/.test(vm.runInContext('projectedWins('+JSON.stringify(t)+')',ctx)));
  }else{
   assert.deepEqual(record(rows[0].at(-1)),sumRecord(rows.slice(1).map(row=>record(row.at(-1)))));
   assert(rows.slice(1).every(row=>row[1].includes('data-group-label="'+row[0].fullLabel+'"')));
  }
 }
}
console.log(data.league+': all outlooks and Overview/Q1-Q4/Reg Season group totals, division sums, hover labels, precision and record wrapping passed.');
// Live Current and Projected views use the exact same group memberships.
const live=fs.readFileSync(path.join(root,'docs/assets/bonus-live-watch.js'),'utf8');new vm.Script(live);assert(live.includes('conferenceGroups(s.rows).map(group=>'));assert(live.includes('members=scores.filter(t=>group.ids.includes(t.id))'));assert(live.includes('weeks,group.fullLabel'));
const nf=new Intl.NumberFormat('en-US',{maximumFractionDigits:1});ctx.nf=nf;
vm.runInContext(live,ctx);ctx.allPlay=vm.runInContext("BonusLiveWatchCore.allPlay",ctx);
const observations=data.observations[String(data.through_week)];
ctx.snapshot={week:data.through_week+1,completed:Array.from({length:data.through_week},(_,i)=>({week:i+1,teams:observations[i+1].map(t=>({id:t.id,score:t.points,potential:t.potential}))})),liveBonusProbabilityBasis:'final_event_outcome',teams:data.weeks[data.through_week].map((t,i)=>({id:t.id,score:i*3.1,potential:i*4.1,projectedScore:i*3.3,projectedPotential:i*4.4,liveBonusProbabilities:{quarter:{win:i/32,tie:0,loss:1-i/32},season:{win:i/32,tie:0,loss:1-i/32}}}))};
const statement=live.split('\n').find(line=>line.includes('const composites=conferenceGroups(s.rows)'));assert(statement);
for(const projected of [false,true])for(const seasonRace of [false,true]){
 ctx.view=projected?'projected':'current';ctx.panel=seasonRace?'season':'quarter';ctx.s=vm.runInContext('BonusLiveWatchCore.standings(snapshot,'+seasonRace+','+projected+')',ctx);
 const rows=JSON.parse(JSON.stringify(vm.runInContext('(function(){'+statement+';return composites})()',ctx)));assert.equal(rows.length,10);
 const record=text=>text.match(/\d+-\d+-\d+/)[0].split('-').map(Number);
 for(const conf of ['NFC','AFC']){
  const parent=rows.find(row=>row[0].key===conf),children=rows.filter(row=>row[0].conference===conf&&row[0].isDivision);
  assert.deepEqual(record(parent[1]),children.map(row=>record(row[1])).reduce((a,b)=>a.map((n,i)=>n+b[i]),[0,0,0]));
  assert(Math.abs(Number(parent[2].replaceAll(',',''))-children.reduce((n,row)=>n+Number(row[2].replaceAll(',','')),0))<.3);
  assert.deepEqual(record(parent[4]),children.map(row=>record(row[4])).reduce((a,b)=>a.map((n,i)=>n+b[i]),[0,0,0]));
 }
}
console.log(data.league+': Live Current/Projected quarter and Reg Season division roll-ups passed.');
