// Native range bridge: only Readout chart bounds and preserved styling are set.
// Requests/receipts use Payouts Reference!Z14:Z15; no new scrape or time trigger.
function refreshGithubEloChartRanges() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) throw new Error('Another league update is running');
  try {
    for (const league of Object.keys(PAYOUTS.books)) {
      refreshGithubEloChartRange(league, SpreadsheetApp.openById(PAYOUTS.books[league]).getSheetByName('Reference'));
    }
  } finally { lock.releaseLock(); }
}

function refreshGithubEloChartRange(league, ref) {
  const raw = ref.getRange('Z14').getValue();
  if (!raw) return;
  const q = JSON.parse(raw), prior = ref.getRange('Z15').getValue();
  if (prior && JSON.parse(prior).request_id === q.request_id) return;
  const receipt = {request_id:q.request_id, league:league, at:new Date().toISOString()};
  const originals = [], written = [];
  let sheet;
  try {
    requireElo(q.version === 1 && q.league === league && q.season === 2026 && /^[a-f0-9]{32}$/.test(q.request_id), 'Invalid chart range request');
    requireElo(Number.isInteger(q.week) && q.week >= 0 && q.week <= 17, 'Invalid chart range week');
    const c = ELO.leagues.find(c=>c.name===league);
    sheet = SpreadsheetApp.openById(c.book).getSheetByName('Readout');
    const names = sheet.getRange('C2:C33').getValues().flat();
    const ratings = sheet.getRange('E2:E33').getValues().flat();
    requireElo(new Set(names).size===32 && Object.keys(q.teams).length===32 && ratings.every(Number.isFinite), 'Incomplete Elo ratings');
    requireElo(ratings.every((v,i)=>Number.isFinite(q.teams[names[i]]) && Math.abs(v-q.teams[names[i]])<0.000001), 'Elo changed after range request');
    const x = Math.max(50,50*Math.ceil(Math.max(...ratings.map(v=>Math.abs(v-1500)))/50));
    requireElo(q.lower===1500-x && q.upper===1500+x, 'Requested axis is not the smallest symmetric window');
    requireElo(Array.isArray(q.charts) && q.charts.length>=1 && q.charts.length<=2 && new Set(q.charts.map(p=>p.chart_id)).size===q.charts.length, 'Invalid chart list');
    const charts = sheet.getCharts();
    const plans = q.charts.map(p=>{
      const chart = charts.find(c=>c.getChartId()===p.chart_id);
      requireElo(chart && chart.getOptions().get('title')===p.title && [league+' NFC Elo Ratings',league+' AFC Elo Ratings'].includes(p.title), 'Wrong chart identity');
      const style=p.style;
      requireElo(style.colors.length===16 && style.colors.every(s=>/^#[0-9A-Fa-f]{6}$/.test(s)), 'Invalid preserved palette');
      for (const key of ['title','hAxis','vAxis','legend']) {
        requireElo(style[key] && typeof style[key].fontName==='string' && Number.isFinite(style[key].fontSize) && /^#[0-9A-Fa-f]{6}$/.test(style[key].color), 'Invalid preserved text style');
      }
      const builder=chart.modify().asLineChart().setColors(style.colors)
        .setOption('vAxis.viewWindow.min',q.lower).setOption('vAxis.viewWindow.max',q.upper)
        .setOption('vAxis.gridlines.count',2*x/50+1)
        .setOption('titleTextStyle',style.title).setOption('hAxis.textStyle',style.hAxis)
        .setOption('vAxis.textStyle',style.vAxis).setOption('legend.textStyle',style.legend);
      if(style.background)builder.setOption('chartArea.backgroundColor',style.background);
      originals.push(chart);
      return builder.build();
    });
    requireElo(ref.getRange('Z14').getValue()===raw, 'Range request changed');
    for (let i=0;i<plans.length;i++) {written.push(i);sheet.updateChart(plans[i]);}
    SpreadsheetApp.flush();
    Object.assign(receipt,{status:'success',lower:q.lower,upper:q.upper,charts:plans.length});
    console.log(league+': charts set to '+q.lower+'–'+q.upper+'; original team colors retained.');
  } catch(e) {
    try {for(const i of written.reverse())sheet.updateChart(originals[i]);SpreadsheetApp.flush();}
    catch(rollback) {receipt.rollback_error=String(rollback);}
    Object.assign(receipt,{status:'failure',error:String(e)});
    console.error(league+': range check failed: '+e);
  }
  ref.getRange('Z15').setValue(JSON.stringify(receipt));
}
