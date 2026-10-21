// Called only by the authenticated doPost handler for operation=elo_chart.
// Chart-only work stays synchronous; the existing payout/bonus queue is unchanged.
function runEloChartBridgeRepair_(payload) {
  const books = {
    ADL: {elo:'1iu7oJUQ8IEhHDTp5RiArK7oTD4-DmjTbI1xtOwuwRBI',payouts:'1oh7P9TRUj356U7xjC26X5a6lunYI73zpSPjT11t1Vok'},
    FAFL: {elo:'1yWEzFx8hKhhlTQ47gacHSQXmZtPsX9k7hB2s6D6-g3k',payouts:'1E-N1YK-udh88c7LFbB57itbMIEAzt6z1N4M5s_J1XBA'}
  };
  const league = payload.league;
  const check = (ok, message) => {if (!ok) throw new Error(message);};
  check(payload.operation === 'elo_chart' && books[league], 'Invalid chart bridge operation or league');
  check(/^[a-f0-9]{32}$/.test(payload.run_id || ''), 'Invalid chart request identifier');
  // Separate chart work from the payout queue's long-held script lock.
  const lock = LockService.getUserLock();
  if (!lock.tryLock(1000)) throw new Error('Bridge busy; retry this request');
  try {
    const ref = SpreadsheetApp.openById(books[league].payouts).getSheetByName('Reference');
    const raw = ref.getRange('Z14').getValue();
    const q = JSON.parse(raw || '{}');
    check(q.request_id === payload.run_id, 'Chart request differs from webhook request');
    const priorRaw = ref.getRange('Z15').getValue();
    const prior = priorRaw ? JSON.parse(priorRaw) : {};
    if (prior.request_id === q.request_id && prior.league === league && ['success','failure'].includes(prior.status)) {
      return {status:'success',league:league,operation:'elo_chart',request_id:q.request_id,receipt:prior};
    }
    const receipt = {request_id:q.request_id,league:league,at:new Date().toISOString()};
    const originals = [], written = [];
    let sheet;
    try {
      check(q.version === 1 && q.league === league && q.season === 2026, 'Invalid chart range request');
      check(Number.isInteger(q.week) && q.week >= 0 && q.week <= 17, 'Invalid chart range week');
      sheet = SpreadsheetApp.openById(books[league].elo).getSheetByName('Readout');
      const names = sheet.getRange('C2:C33').getValues().flat();
      const ratings = sheet.getRange('E2:E33').getValues().flat();
      check(names.length === 32 && new Set(names).size === 32 && ratings.length === 32 && ratings.every(Number.isFinite), 'Incomplete Elo ratings');
      check(q.teams && Object.keys(q.teams).length === 32 && ratings.every((v,i)=>Number.isFinite(q.teams[names[i]]) && Math.abs(v-q.teams[names[i]])<0.000001), 'Elo changed after range request');
      const x = Math.max(50,50*Math.ceil(Math.max(...ratings.map(v=>Math.abs(v-1500)))/50));
      check(q.lower === 1500-x && q.upper === 1500+x, 'Requested axis is not the smallest symmetric window');
      check(Array.isArray(q.charts) && q.charts.length >= 1 && q.charts.length <= 2 && new Set(q.charts.map(p=>p.chart_id)).size === q.charts.length, 'Invalid chart list');
      const charts = sheet.getCharts();
      const plans = q.charts.map(p=>{
        const chart = charts.find(c=>c.getChartId() === p.chart_id);
        check(chart && chart.getOptions().get('title') === p.title && [league+' NFC Elo Ratings',league+' AFC Elo Ratings'].includes(p.title), 'Wrong chart identity');
        const style = p.style;
        check(style && Array.isArray(style.colors) && style.colors.length === 16 && style.colors.every(s=>/^#[0-9A-Fa-f]{6}$/.test(s)), 'Invalid preserved palette');
        for (const key of ['title','hAxis','vAxis','legend']) {
          check(style[key] && typeof style[key].fontName === 'string' && Number.isFinite(style[key].fontSize) && /^#[0-9A-Fa-f]{6}$/.test(style[key].color), 'Invalid preserved text style');
        }
        const builder = chart.modify().asLineChart().setColors(style.colors)
          .setOption('vAxis.viewWindow.min',q.lower).setOption('vAxis.viewWindow.max',q.upper)
          .setOption('vAxis.gridlines.count',2*x/50+1)
          .setOption('titleTextStyle',style.title).setOption('hAxis.textStyle',style.hAxis)
          .setOption('vAxis.textStyle',style.vAxis).setOption('legend.textStyle',style.legend);
        if (style.background) builder.setOption('chartArea.backgroundColor',style.background);
        originals.push(chart);
        return builder.build();
      });
      check(ref.getRange('Z14').getValue() === raw, 'Range request changed');
      for (let i=0;i<plans.length;i++) {written.push(i);sheet.updateChart(plans[i]);}
      SpreadsheetApp.flush();
      Object.assign(receipt,{status:'success',lower:q.lower,upper:q.upper,charts:plans.length});
      console.log(league+': chart range verified at '+q.lower+' to '+q.upper);
    } catch (error) {
      try {for (const i of written.reverse()) sheet.updateChart(originals[i]);SpreadsheetApp.flush();}
      catch (rollback) {receipt.rollback_error=String(rollback);}
      Object.assign(receipt,{status:'failure',error:String(error)});
      console.error(league+': chart range failed: '+error);
    }
    ref.getRange('Z15').setValue(JSON.stringify(receipt));
    return {status:'success',league:league,operation:'elo_chart',request_id:q.request_id,receipt:receipt};
  } finally {lock.releaseLock();}
}
