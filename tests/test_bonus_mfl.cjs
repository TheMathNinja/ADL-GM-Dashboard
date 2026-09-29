const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const context = vm.createContext({console, Date});
for (const file of ['BonusMFL.gs','PayoutsGithubBridge.gs']) vm.runInContext(fs.readFileSync(path.join(__dirname,'../scripts',file),'utf8'),context);
vm.runInContext(`
let stored = {}, posts = 0, ack, raw, currentDay = '2026-10-01';
const ELO = {timezone:'America/New_York',leagues:[{name:'ADL',id:'60206'}]};
const Utilities = {formatDate:(_,tz,format)=>format==='yyyy-MM-dd'?currentDay:'03:45'};
bonusMflVerifySheet = () => {};
bonusMflLogin = () => ({});
bonusMflGetForm = () => ({existing:JSON.parse(JSON.stringify(stored))});
bonusMflSubmit = (c,cookies,form,missing) => {posts++;for(const r of missing)stored[r.week+'_'+r.id]=r;};
const ref = {getRange:r=>({getValue:()=>r==='Z12'?raw:JSON.stringify(ack||{}),setValue:v=>{ack=JSON.parse(v);}})};
const reports = {TPF:{},PPF:{}};
for(let i=1;i<=32;i++){const id=String(i).padStart(4,'0');reports.TPF[id]=Array(12).fill(i);reports.PPF[id]=Array(12).fill(i+10);}
function request(mode='official',run='1',week=3){raw=JSON.stringify({version:1,league:'ADL',season:2026,week,run_id:run,source_sha256:run,mode,reports});refreshGithubBonusMfl('ADL',ref);}
`,context);
const value = code => vm.runInContext(code,context);
value("currentDay='2026-09-29';request()");
assert.equal(value('ack.status'),'failure'); assert.equal(value('posts'),0);
value("request('preview','2')");
assert.equal(value('ack.status'),'success'); assert.equal(value('posts'),0);
assert.equal(value('ack.results[0].missing_before'),32);
value("currentDay='2026-10-01';request('official','3')");
assert.equal(value('ack.status'),'success'); assert.equal(value('posts'),1);
assert.equal(value('Object.keys(stored).length'),32);
assert.equal(value("Object.values(stored).reduce((n,r)=>n+r.W,0)"),15);
assert.equal(value("Object.values(stored).reduce((n,r)=>n+r.T,0)"),2);
value("request('official','4')");
assert.equal(value('posts'),1); assert.equal(value('ack.status'),'success');
value("stored['3_0001'].W=1;request('official','5')");
assert.equal(value('ack.status'),'failure'); assert.equal(value('posts'),1);
value("stored={};currentDay='2026-12-03';request('official','6',12)");
assert.equal(value('ack.status'),'success');
assert.equal(value("Object.values(stored).filter(r=>r.week===12).every(r=>r.W+r.L+r.T===2)"),true);
assert.equal(value('Object.keys(stored).length'),128);
console.log('MFL bridge tests passed: date gate, preview, entry/readback, duplicate prevention, conflict, Q4 plus season.');
