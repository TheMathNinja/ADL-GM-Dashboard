const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
for(const league of ['ADL','FAFL']) {
 const c=vm.createContext({console,Date,LockService:{getUserLock:()=>({tryLock:()=>true,releaseLock:()=>{}})}});
 for(const file of ['BonusMFL.gs','PayoutsGithubBridge.gs'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../scripts',file),'utf8'),c);
 const run=code=>vm.runInContext(code,c);
 run(`let stored={},posts=0,ack,raw,currentDay='2026-11-12',clock='03:45',interrupt=false,dropReadback=false;
 const ELO={timezone:'America/New_York',leagues:[{name:'${league}',id:'${league==='ADL'?'60206':'22686'}'}]};
 const Utilities={formatDate:(_,tz,format)=>format==='yyyy-MM-dd'?currentDay:clock};
 bonusMflLogin=()=>({});
 bonusMflGetForm=()=>({existing:JSON.parse(JSON.stringify(stored))});
 bonusMflSubmit=(c,cookies,form,missing)=>{posts++;for(const row of missing)stored[row.week+'_'+row.id]=row;if(interrupt){interrupt=false;throw new Error('Response lost after MFL accepted POST');}if(dropReadback){delete stored[missing[0].week+'_'+missing[0].id];dropReadback=false;}};
 const reports={TPF:{},PPF:{}};
 for(let i=1;i<=32;i++){const id=String(i).padStart(4,'0');reports.TPF[id]=Array(12).fill(i);reports.PPF[id]=Array(12).fill(i+10);}
 const ref={getRange:r=>({getValue:()=>r==='Z12'?raw:JSON.stringify(ack||{}),setValue:v=>{ack=JSON.parse(v);}})};
 function request(mode='official',run='1',week=9){raw=JSON.stringify({version:1,league:'${league}',season:2026,week,run_id:run,source_sha256:'a'.repeat(64),mode,reports});refreshGithubBonusMfl('${league}',ref);}
 function seed(week,n=32){for(const row of bonusMflPlan(reports,week).slice(0,n))stored[row.week+'_'+row.id]=row;}
 seed(3);seed(6);const previous=JSON.stringify(stored);`);
 run("clock='03:44';request()");assert.equal(run('ack.status'),'failure');assert.equal(run('posts'),0);
 run("request('preview','2')");assert.equal(run('ack.status'),'success');assert.equal(run('posts'),0);assert.equal(run('ack.results[2].missing_before'),32);
 run("clock='03:45';seed(9,9);request('official','3')");assert.equal(run('ack.status'),'success');assert.equal(run('posts'),1);assert.equal(run('ack.results[2].missing_before'),23);assert.equal(run('Object.keys(stored).length'),96);
 assert.equal(run('JSON.stringify(Object.fromEntries(Object.entries(stored).filter(([k])=>!k.startsWith("9_"))))===previous'),true);
 assert.equal(run('ack.results[2].rows.reduce((n,r)=>n+r.W,0)'),15);assert.equal(run('ack.results[2].rows.reduce((n,r)=>n+r.T,0)'),2);assert.equal(run('ack.results[2].rows.reduce((n,r)=>n+r.L,0)'),15);
 assert.equal(run('ack.results[2].rows.every(r=>r.note.startsWith("Q3 Bonus Game (#"))'),true);
 run("request('official','4')");assert.equal(run('posts'),1);
 // A lost response or partial MFL application must reconcile, not duplicate.
 run("stored=JSON.parse(previous);interrupt=true;request('official','5')");assert.equal(run('ack.status'),'failure');assert.equal(run('posts'),2);
 run("request('official','5')");assert.equal(run('ack.status'),'success');assert.equal(run('posts'),2);
 run("stored=JSON.parse(previous);dropReadback=true;request('official','6')");assert.equal(run('ack.status'),'failure');assert.equal(run('posts'),3);
 run("request('official','6')");assert.equal(run('ack.status'),'success');assert.equal(run('posts'),4);assert.equal(run('Object.keys(stored).length'),96);
 run("stored['3_0001'].W=1;request('official','7')");assert.equal(run('ack.status'),'failure');assert.equal(run('posts'),4);
 // Full PF/Potential ties at an outcome boundary require review, never ID sorting.
 run("for(const id of bonusMflIds()){reports.TPF[id]=Array(12).fill(10);reports.PPF[id]=Array(12).fill(20);}");
 assert.throws(()=>run('bonusMflPlan(reports,9)'),/unresolved tie/);
 // PF breaks all-play ties, Potential breaks an exact APW/PF tie.
 run("for(let i=1;i<=32;i++){const id=String(i).padStart(4,'0');reports.TPF[id]=Array(12).fill(i);reports.PPF[id]=Array(12).fill(i+10);} reports.TPF['0017'][6]=16;reports.TPF['0017'][7]=16;reports.TPF['0017'][8]=16;");
 assert.equal(run("bonusMflPlan(reports,9).find(r=>r.id==='0017').T"),1);
 console.log(league+': Q3 date gate, preview, partial resume, uncertain POST, same-request retry, Q1/Q2 preservation and boundary-tie checks passed.');
}
