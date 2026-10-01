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

// Exercise the real transport and form builder, not the bridge's mocked submit.
const wire = vm.createContext({console});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../scripts/BonusMFL.gs'),'utf8'),wire);
vm.runInContext(`
const requests=[];
const Utilities={sleep:()=>{}};
let responseBody='32 Standings Adjustment(s) Added.';
const UrlFetchApp={fetch:(url,options)=>{requests.push({url,options});return {
 getResponseCode:()=>200,getAllHeaders:()=>({}),getContentText:()=>responseBody
};}};
const inputs=Object.fromEntries(Object.entries({form_name:'sadj',LEAGUE_ID:'60206',C:'STANDADJ',input_expires:'2000000000',PREFIX:''}).map(([name,value])=>[name,{type:'hidden',value}]));
const desired=bonusMflIds().map((id,i)=>({id,week:3,W:i<15?1:0,T:i>=15&&i<17?1:0,L:i>=17?1:0,note:'Q1 Bonus Game'}));
bonusMflSubmit({server:'www46'}, {}, {inputs}, desired);
`,wire);
const options=vm.runInContext('requests[0].options',wire);
assert.equal(options.contentType,'application/x-www-form-urlencoded');
assert.equal(typeof options.payload,'string');
const fields=new URLSearchParams(options.payload);
assert.equal([...fields].length,166);
for(let i=1;i<=32;i++) {
 const id=String(i).padStart(4,'0');
 assert.equal(fields.get('EXP'+id),'Q1 Bonus Game');
 assert.equal(fields.get('WEEK'+id),'3');
 assert.equal(['W','L','T'].reduce((n,k)=>n+Number(fields.get(k+id)),0),1);
}
vm.runInContext("bonusMflRequest('https://api.myfantasyleague.com/2026/login',{}, {USERNAME:'test + & =',PASSWORD:'fake%+&='})",wire);
const login=new URLSearchParams(vm.runInContext('requests[1].options.payload',wire));
assert.equal(login.get('USERNAME'),'test + & =');
assert.equal(login.get('PASSWORD'),'fake%+&=');
vm.runInContext("responseBody='Error(s) Validating Input'",wire);
assert.throws(()=>vm.runInContext("bonusMflSubmit({server:'www46'},{},{inputs},desired)",wire),/MFL rejected the standings form/);
console.log('MFL form transport tests passed: all 166 fields, explanations, escaping, server rejection.');
