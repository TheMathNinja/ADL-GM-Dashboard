// Final step of the existing 2026 Elo/Bonus Games refresh. No separate time trigger.
// Store BONUS_MFL_USERNAME and BONUS_MFL_PASSWORD in Script Properties to enable.
const BONUS_MFL = {
  year:2026,
  due:{3:'2026-10-01',6:'2026-10-22',9:'2026-11-12',12:'2026-12-03'},
  credentialKeys:['BONUS_MFL_USERNAME','BONUS_MFL_PASSWORD']
};
function bonusMflRequire(ok,message) { if(!ok)throw new Error('Bonus Games: '+message); }
function bonusMflIds() { return Array.from({length:32},(_,i)=>String(i+1).padStart(4,'0')); }
function bonusMflRank(reports,first,last) {
  const ids=bonusMflIds();
  const out=ids.map(id=>({id:id,ap2:0,points:0,potential:0}));
  // Integer ten-thousandths avoid floating-point point-sum tiebreak errors.
  for(let week=first;week<=last;week++) {
    const scores=ids.map(id=>reports.TPF[id]?.[week-1]);
    bonusMflRequire(scores.every(Number.isFinite),'missing actual score in week '+week);
    for(let i=0;i<32;i++) {
      const pp=reports.PPF[ids[i]]?.[week-1];
      bonusMflRequire(Number.isFinite(pp),'missing potential points in week '+week);
      out[i].ap2+=scores.reduce((sum,score,j)=>sum+(j===i?0:scores[i]>score?2:scores[i]===score?1:0),0);
      out[i].points+=Math.round(scores[i]*10000);
      out[i].potential+=Math.round(pp*10000);
    }
  }
  out.sort((a,b)=>b.ap2-a.ap2||b.points-a.points||b.potential-a.potential);
  for(const cut of [15,17]) {
    const a=out[cut-1],b=out[cut];
    bonusMflRequire(a.ap2!==b.ap2||a.points!==b.points||a.potential!==b.potential,'unresolved tie across ranks '+cut+'/'+(cut+1));
  }
  return out.map((row,i)=>({...row,rank:i+1,result:i<15?'W':i<17?'T':'L'}));
}
function bonusMflPlan(reports,week) {
  bonusMflRequire([3,6,9,12].includes(week),'invalid bonus week');
  const quarter=bonusMflRank(reports,week-2,week);
  const season=week===12?Object.fromEntries(bonusMflRank(reports,1,12).map(r=>[r.id,r])):{};
  return quarter.map(row=>{
    const outcomes=[row.result];if(week===12)outcomes.push(season[row.id].result);
    return {id:row.id,week:week,W:outcomes.filter(v=>v==='W').length,
      L:outcomes.filter(v=>v==='L').length,T:outcomes.filter(v=>v==='T').length,
      note:week===12?'Q4 Bonus Game '+row.result+' + RS Bonus Game '+season[row.id].result:'Q'+(week/3)+' Bonus Game'};
  });
}
function bonusMflEligible(last,now) {
  if(Utilities.formatDate(now,ELO.timezone,'EEE')!=='Thu')return [];
  const day=Utilities.formatDate(now,ELO.timezone,'yyyy-MM-dd');
  bonusMflRequire(Number(Utilities.formatDate(now,ELO.timezone,'yyyy'))===BONUS_MFL.year,'season configuration needs updating');
  return [3,6,9,12].filter(w=>last>=w&&day>=BONUS_MFL.due[w]);
}
function bonusMflAttributes(tag) {
  return Object.fromEntries(Array.from(tag.matchAll(/([\w-]+)\s*=\s*["']([^"']*)["']/g),m=>[m[1].toLowerCase(),m[2].replace(/&amp;/g,'&').replace(/&quot;/g,'"').replace(/&#39;/g,"'")]));
}
function bonusMflForm(html,id) {
  const forms=Array.from(html.matchAll(/<form\b[^>]*>[\s\S]*?<\/form>/gi)).map(m=>m[0]).filter(f=>bonusMflAttributes(f.match(/<form\b[^>]*>/i)[0]).name==='sadj');
  bonusMflRequire(forms.length===1,'commissioner standings form unavailable');
  const f=forms[0],attr=bonusMflAttributes(f.match(/<form\b[^>]*>/i)[0]);
  bonusMflRequire(attr.action==='csetup'&&attr.method.toLowerCase()==='post','unexpected form action');
  const inputs={};for(const m of f.matchAll(/<input\b[^>]*>/gi)) {
    const a=bonusMflAttributes(m[0]);if(!a.name)continue;
    bonusMflRequire(!inputs[a.name],'duplicate form input');inputs[a.name]=a;
  }
  bonusMflRequire(inputs.LEAGUE_ID?.value===id&&inputs.C?.value==='STANDADJ'&&inputs.form_name?.value==='sadj','wrong league/form');
  bonusMflRequire(inputs.ASUBMIT?.value==='Adjust Standings'&&inputs.input_expires,'missing submit/expiry field');
  const selectors=Array.from(f.matchAll(/<select\b[^>]*>/gi),m=>bonusMflAttributes(m[0]).name).filter(n=>/^WEEK\d{4}$/.test(n)).sort();
  bonusMflRequire(JSON.stringify(selectors)===JSON.stringify(bonusMflIds().map(id=>'WEEK'+id)),'unexpected franchise selectors');
  for(const fid of bonusMflIds())for(const prefix of ['W','L','T','EXP'])bonusMflRequire(inputs[prefix+fid],'missing franchise field');
  const existing={};
  for(const m of f.matchAll(/<tr\b[^>]*>[\s\S]*?<\/tr>/gi)) {
    const row=m[0],rid=bonusMflAttributes(row.match(/<tr\b[^>]*>/i)[0]).id||'';
    if(!rid.startsWith('row_D_'))continue;
    const key=rid.match(/^row_D_(\d+)_(\d{4})$/),cells=Array.from(row.matchAll(/<td\b[^>]*>([\s\S]*?)<\/td>/gi),m=>cleanElo(m[1]).replace(/\s+/g,' ').trim());
    bonusMflRequire(key&&cells.length>=5&&Number(cells[2])===Number(key[1]),'unrecognized adjustment record');
    const name=Number(key[1])+'_'+key[2];bonusMflRequire(!existing[name],'duplicate existing adjustment');
    const value={id:key[2],week:Number(key[1]),W:0,L:0,T:0,note:cells[4]};
    const parts=cells[3].split(',').filter(x=>x.trim());bonusMflRequire(parts.length,'empty adjustment');
    for(const part of parts) {
      const x=part.trim().match(/^([+-]?\d+)\s+(Wins|Losses|Ties)$/);bonusMflRequire(x,'unknown W/L/T adjustment');
      value[x[2][0]]+=Number(x[1]);
    }
    existing[name]=value;
  }
  return {inputs:inputs,existing:existing};
}
function bonusMflEqual(a,b) { return ['id','week','W','L','T','note'].every(k=>a[k]===b[k]); }
function bonusMflMissing(existing,desired) {
  for(const old of Object.values(existing)) {
    const q=old.note.match(/\bQ([1-4]) Bonus Game\b/);
    bonusMflRequire(!q||old.week===Number(q[1])*3,'bonus note at incorrect week');
  }
  return desired.filter(row=>{
    const old=existing[row.week+'_'+row.id];
    bonusMflRequire(!old||bonusMflEqual(old,row),'conflicting adjustment at week '+row.week+', team '+row.id);
    return !old;
  });
}
function bonusMflRequest(url,cookies,payload) {
  const allowed=/^https:\/\/(api|www46|www43)\.myfantasyleague\.com\/2026\//;
  for(let redirect=0;redirect<5;redirect++) {
    bonusMflRequire(allowed.test(url),'unexpected request destination');
    const options={method:payload?'post':'get',followRedirects:false,muteHttpExceptions:true,
      headers:{Cookie:Object.entries(cookies).map(([k,v])=>k+'='+v).join('; '),'Cache-Control':'no-cache'}};
    // Use the browser form encoding explicitly. MFL dropped explanation fields
    // from Apps Script's object payload on the first official 2026 bonus run.
    if(payload) {
      options.contentType='application/x-www-form-urlencoded';
      options.payload=Object.entries(payload).map(([k,v])=>encodeURIComponent(k)+'='+encodeURIComponent(String(v))).join('&');
    }
    Utilities.sleep(1100);
    const response=UrlFetchApp.fetch(url,options),code=response.getResponseCode(),headers=response.getAllHeaders();
    const cookieKey=Object.keys(headers).find(k=>k.toLowerCase()==='set-cookie');
    const set=cookieKey?headers[cookieKey]:[];
    for(const line of (Array.isArray(set)?set:[set])) {
      const m=String(line).match(/^([^=;\s]+)=([^;]*)/);if(m)cookies[m[1]]=m[2];
    }
    if([301,302,303,307,308].includes(code)) {
      const locationKey=Object.keys(headers).find(k=>k.toLowerCase()==='location');
      let target=locationKey?String(headers[locationKey]):'';
      bonusMflRequire(target,'redirect without location');
      if(target.startsWith('/'))target=url.match(/^https:\/\/[^/]+/)[0]+target;
      else if(!target.startsWith('https://'))target=url.slice(0,url.lastIndexOf('/')+1)+target;
      url=target;if([301,302,303].includes(code))payload=null;
      continue;
    }
    bonusMflRequire(code===200,'MFL HTTP '+code);
    return response.getContentText();
  }
  throw new Error('Bonus Games: too many MFL redirects');
}
function bonusMflLogin() {
  const props=PropertiesService.getScriptProperties();
  const user=props.getProperty(BONUS_MFL.credentialKeys[0]),password=props.getProperty(BONUS_MFL.credentialKeys[1]);
  bonusMflRequire(user&&password,'MFL credentials have not been configured in Script Properties');
  const cookies={},xml=bonusMflRequest('https://api.myfantasyleague.com/2026/login',cookies,{USERNAME:user,PASSWORD:password,XML:'1'});
  const root=XmlService.parse(xml).getRootElement(),cookie=root.getAttribute('MFL_USER_ID');
  bonusMflRequire(root.getName()==='status'&&cookie,'MFL login failed');
  cookies.MFL_USER_ID=encodeURIComponent(cookie.getValue());return cookies;
}
function bonusMflGetForm(c,cookies) {
  const base='https://'+c.server+'.myfantasyleague.com/2026/';
  const url=base+'csetup?L='+c.id+'&C=STANDADJ';let html=bonusMflRequest(url,cookies);
  if(html.includes('Commissioner Access Required')) {
    const become=base+'logout?L='+c.id+'&BECOME=0000';
    bonusMflRequire(html.includes(become.replace(/&/g,'&amp;'))||html.includes(become),'commissioner switch unavailable');
    bonusMflRequest(become,cookies);html=bonusMflRequest(url,cookies);
  }
  return bonusMflForm(html,c.id);
}
function bonusMflSubmit(c,cookies,form,missing) {
  const body={};for(const [name,a] of Object.entries(form.inputs))if(a.type==='hidden')body[name]=a.value||'';
  for(const row of missing) {
    body['WEEK'+row.id]=String(row.week);body['EXP'+row.id]=row.note;
    for(const field of ['W','L','T'])body[field+row.id]=row[field]?String(row[field]):'';
  }
  body.ASUBMIT='Adjust Standings';
  // Never retry an uncertain POST. A later run reconciles against live MFL first.
  const response=bonusMflRequest('https://'+c.server+'.myfantasyleague.com/2026/csetup',cookies,body);
  bonusMflRequire(!response.includes('Error(s) Validating Input'),'MFL rejected the standings form; verify its input fields before retrying');
}
function bonusMflVerifySheet(c,source) {
  const id=c.name==='ADL'?'1S3NrGPEGdA3zR3-VNLLS1dAbMYFzH5rt1Z4ROoCzekU':'1X5DJD6K2mAL93DpPtHshVnOo4f_mJRc1CE2phcTFnTE';
  const sheet=SpreadsheetApp.openById(id).getSheetByName('Alphabetical');
  const ids=sheet.getRange('A3:A34').getDisplayValues().flat().map(n=>String(ELO.names.indexOf(n)+1).padStart(4,'0'));
  bonusMflRequire(JSON.stringify([...ids].sort())===JSON.stringify(bonusMflIds()),'spreadsheet franchise mapping changed');
  const actual=sheet.getRange(3,75,32,source.last).getValues();
  bonusMflRequire(actual.every((row,i)=>row.every((score,w)=>Number.isFinite(score)&&Math.abs(score-source.reports.TPF[ids[i]][w])<0.00001)),'Bonus Games sheet does not match the successful scrape');
}
function bonusMflAfterRefresh(c,source) {
  const props=PropertiesService.getScriptProperties(),now=new Date();
  const due=bonusMflEligible(source.last,now).filter(w=>!props.getProperty('bonus_mfl_done_2026_'+c.id+'_'+w));
  if(!due.length)return;
  bonusMflVerifySheet(c,source);
  const cookies=bonusMflLogin();
  for(const week of due) {
    const desired=bonusMflPlan(source.reports,week),key='bonus_mfl_done_2026_'+c.id+'_'+week;
    let form=bonusMflGetForm(c,cookies),missing=bonusMflMissing(form.existing,desired);
    if(missing.length) {
      form=bonusMflGetForm(c,cookies);missing=bonusMflMissing(form.existing,desired);
      if(missing.length)bonusMflSubmit(c,cookies,form,missing);
      const after=bonusMflGetForm(c,cookies);
      bonusMflRequire(bonusMflMissing(after.existing,desired).length===0,'submission incomplete; rerun to reconcile');
      for(const [key,row] of Object.entries(form.existing))bonusMflRequire(after.existing[key]&&bonusMflEqual(after.existing[key],row),'existing adjustment changed');
      const expected=new Set([...Object.keys(form.existing),...desired.map(r=>r.week+'_'+r.id)]);
      bonusMflRequire(Object.keys(after.existing).length===expected.size,'unexpected extra adjustments');
    }
    props.setProperty(key,JSON.stringify({at:now.toISOString(),week:week,rows:desired}));
    console.log(c.name+': verified week '+week+' bonus adjustments ('+missing.length+' newly entered).');
  }
}
function previewBonusMfl() {
  const props=PropertiesService.getScriptProperties();
  console.log('MFL credentials configured: '+BONUS_MFL.credentialKeys.every(k=>!!props.getProperty(k)));
  for(const c of ELO.leagues) {
    const source=fetchEloReports(c);
    for(const week of [3,6,9,12].filter(w=>w<=source.last))console.log(c.name+' week '+week+': '+JSON.stringify(bonusMflPlan(source.reports,week)));
    console.log(c.name+': '+source.last+' published weeks. No MFL standings changed.');
  }
}
function verifyBonusMflConnection() {
  for(const c of ELO.leagues) {
    const form=bonusMflGetForm(c,bonusMflLogin());
    console.log(c.name+': commissioner standings form verified; '+Object.keys(form.existing).length+' existing adjustments. No standings changed.');
  }
}
