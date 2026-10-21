const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../scripts/EloChartBridgeRepair.gs'),'utf8');
function setup(){
 const names=Array.from({length:32},(_,i)=>'Team '+i),ratings=names.map((_,i)=>i===0?1395.397:1500);
 const style={colors:Array(16).fill('#003594'),background:'#FFFFFF'};
 for(const key of ['title','hAxis','vAxis','legend'])style[key]={fontName:'Verdana',fontSize:10,color:'#333333'};
 const request={version:1,request_id:'a'.repeat(32),league:'FAFL',season:2026,week:6,lower:1350,upper:1650,
  teams:Object.fromEntries(names.map((n,i)=>[n,ratings[i]])),charts:['AFC','NFC'].map((c,i)=>({chart_id:i,title:`FAFL ${c} Elo Ratings`,style}))};
 const cells={Z14:JSON.stringify(request),Z15:''},writes=[],updated=[];
 const charts=request.charts.map(p=>({id:p.chart_id,title:p.title,original:true,getChartId(){return this.id},getOptions(){return {get:()=>this.title}},modify(){
  const result={id:this.id,title:this.title,colors:[],options:{},original:false};const b={asLineChart(){return this},setColors(c){result.colors=c;return this},setOption(k,v){result.options[k]=v;return this},build(){return result}};return b;
 }}));
 const env={cells,writes,updated,request,busy:false,released:0,failSecond:false};
 const ref={getRange(c){return {getValue:()=>cells[c],setValue(v){writes.push(c);cells[c]=v}}}};
 const readout={getRange(c){return {getValues:()=> (c==='C2:C33'?names:ratings).map(v=>[v])}},getCharts:()=>charts,updateChart(c){if(env.failSecond&&c.id===1&&!c.original)throw Error('Injected chart failure');updated.push(c)}};
 const context={console:{log(){},error(){}},LockService:{getUserLock:()=>({tryLock:()=>!env.busy,releaseLock(){env.released++}})},SpreadsheetApp:{openById(id){return {getSheetByName:name=>name==='Reference'?ref:readout}},flush(){}}};
 vm.createContext(context);vm.runInContext(source,context);env.run=()=>context.runEloChartBridgeRepair_({league:'FAFL',operation:'elo_chart',run_id:'a'.repeat(32)});return env;
}
test('updates both ranges, preserves palette and writes only the receipt',()=>{
 const s=setup(),r=s.run();assert.equal(r.receipt.status,'success');assert.equal(s.updated.length,2);
 for(const c of s.updated){assert.equal(c.options['vAxis.viewWindow.min'],1350);assert.equal(c.options['vAxis.viewWindow.max'],1650);assert.equal(c.options['vAxis.gridlines.count'],7);assert.equal(c.colors[0],'#003594')}
 assert.deepEqual(s.writes,['Z15']);assert.equal(s.released,1);
});
test('replaying a completed request does not change charts again',()=>{const s=setup();s.run();s.updated.length=0;s.writes.length=0;assert.equal(s.run().receipt.status,'success');assert.equal(s.updated.length,0);assert.deepEqual(s.writes,[])});
test('stale ratings produce a failure receipt without chart changes',()=>{const s=setup();const q=s.request;q.teams['Team 0']=1401;s.cells.Z14=JSON.stringify(q);assert.equal(s.run().receipt.status,'failure');assert.equal(s.updated.length,0);assert.deepEqual(s.writes,['Z15'])});
test('a failed second chart rolls back the first chart',()=>{const s=setup();s.failSecond=true;const r=s.run();assert.equal(r.receipt.status,'failure');assert.equal(s.updated.at(-1).original,true);assert.equal(s.updated.at(-1).id,0);assert.equal(s.released,1)});
test('a busy lock leaves the request untouched for retry',()=>{const s=setup();s.busy=true;assert.throws(s.run,/busy/);assert.deepEqual(s.writes,[]);assert.equal(s.updated.length,0)});
test('a different webhook request cannot process the current sheet request',()=>{const s=setup();s.request.request_id='b'.repeat(32);s.cells.Z14=JSON.stringify(s.request);assert.throws(s.run,/differs/);assert.deepEqual(s.writes,[]);assert.equal(s.released,1)});
