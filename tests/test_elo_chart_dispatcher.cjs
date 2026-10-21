const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../scripts/PayoutsGithubBridge.gs'),'utf8');
const start=source.indexOf('function doPost('),end=source.indexOf('\nfunction ',start+1);
const handler=source.slice(start,end<0?source.length:end);
function run(payload){
 let queued=0,charted=0;
 const result={setMimeType(){return this},setContent(s){return JSON.parse(s)}};
 const context={ContentService:{MimeType:{JSON:'json'},createTextOutput:()=>result},
  PropertiesService:{getScriptProperties:()=>({getProperty:()=> 'expected-token'})},
  runEloChartBridgeRepair_(p){charted++;return {status:'success',league:p.league,operation:p.operation,request_id:p.run_id}},
  queueGithubPayoutBridge_(){queued++},refreshGithubPayoutBridgeScheduled_(){queued++;return true}};
 vm.createContext(context);vm.runInContext(handler,context);
 return {response:context.doPost({postData:{contents:JSON.stringify(payload)}}),get queued(){return queued},get charted(){return charted}};
}
test('chart work bypasses the generic queue after authentication',()=>{
 const r=run({token:'expected-token',action:'refreshGithubPayoutLogos',league:'FAFL',operation:'elo_chart',run_id:'a'.repeat(32)});
 assert.equal(r.response.status,'success');assert.equal(r.response.operation,'elo_chart');assert.equal(r.charted,1);assert.equal(r.queued,0);
});
test('unauthorized chart requests cannot execute either path',()=>{
 const r=run({token:'incorrect',action:'refreshGithubPayoutLogos',operation:'elo_chart'});
 assert.equal(r.response.status,'failure');assert.equal(r.charted,0);assert.equal(r.queued,0);
});
test('ordinary authenticated requests retain their existing queue path',()=>{
 const r=run({token:'expected-token',action:'refreshGithubPayoutLogos'});
 assert.equal(r.response.status,'success');assert.equal(r.charted,0);assert.equal(r.queued,1);
});
