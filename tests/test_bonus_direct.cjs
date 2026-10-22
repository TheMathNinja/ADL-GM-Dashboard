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
