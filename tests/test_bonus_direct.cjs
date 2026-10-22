const fs=require('fs'),vm=require('vm'),assert=require('assert');const source=fs.readFileSync(require('path').join(__dirname,'../scripts/PayoutsGithubBridge.gs'),'utf8');
const ctx=vm.createContext({console});vm.runInContext(source,ctx);vm.runInContext(`
var calls=0,busy=false,request={run_id:'123',league:'ADL'};
var PAYOUTS={books:{ADL:'book'}};
var LockService={getUserLock:()=>({tryLock:()=>!busy,releaseLock:()=>{}})};
var SpreadsheetApp={openById:id=>({getSheetByName:name=>({getRange:cell=>({getValue:()=>JSON.stringify(request)})})})};
function bonusMflRequire(ok,message){if(!ok)throw Error(message)}
refreshGithubBonusMflLocked_=(league,ref)=>{calls++};
`,ctx);
assert.equal(vm.runInContext("runGithubBonusMflNow_({league:'ADL',run_id:'123'}).queued",ctx),false);assert.equal(vm.runInContext('calls',ctx),1);
assert.throws(()=>vm.runInContext("runGithubBonusMflNow_({league:'ADL',run_id:'999'})",ctx),/changed/);assert.equal(vm.runInContext('calls',ctx),1);
vm.runInContext('busy=true',ctx);assert.equal(vm.runInContext("runGithubBonusMflNow_({league:'ADL',run_id:'123'}).queued",ctx),true);assert.equal(vm.runInContext('calls',ctx),1);
console.log('Direct Bonus dispatch tests passed: correct request, changed request blocked, lock preserved.');

vm.runInContext(`
var BONUS_MFL={year:2026,due:{9:'2026-11-12'},credentialKeys:['user','password']};
var PropertiesService={getScriptProperties:()=>({getProperty:k=>k==='CLOUD_SCHEDULER_LAST_RUN'?'1792700000000':'configured'})};
var ScriptApp={getProjectTriggers:()=>[{getHandlerFunction:()=>'runCloudLeagueScheduler'}]};
`,ctx);
const health=vm.runInContext('auditGithubBonusMfl_()',ctx);
assert.equal(health.status,'success');assert.equal(health.mfl_credentials_configured,true);assert.equal(health.scheduler_installed,true);assert.equal(health.legacy_elo_trigger_count,0);
assert.equal(Object.values(health).includes('configured'),false);
console.log('Authenticated readiness audit exposes flags without credentials.');
