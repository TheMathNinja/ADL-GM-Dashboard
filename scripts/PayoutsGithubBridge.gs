// Installed alongside the existing Payouts and PayoutLogos files.
// Sheets API cannot edit over-cell images. GitHub requests this display-only
// step through an authenticated sheet write, then waits for its acknowledgement.
// The same bridge also handles explicit official Bonus Games requests in Z12:Z13.
function installPayoutGithubBridge() {
  const handler = 'refreshGithubPayoutLogos';
  for (const t of ScriptApp.getProjectTriggers()) {
    if (t.getHandlerFunction() === handler) ScriptApp.deleteTrigger(t);
  }
  {
    ScriptApp.newTrigger(handler).timeBased().everyMinutes(5).create();
  }
  refreshGithubPayoutLogos();
  console.log('GitHub payout display bridge installed; no additional score scrape or Elo update is performed.');
}

function refreshGithubPayoutLogos() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    for (const league of Object.keys(PAYOUTS.books)) {
      const book = SpreadsheetApp.openById(PAYOUTS.books[league]);
      const ref = book.getSheetByName('Reference');
      refreshGithubEloChartRange(league, ref);
      refreshGithubBonusMfl(league, ref);
      const raw = ref.getRange('Z10').getValue();
      if (!raw) continue;
      const request = JSON.parse(raw);
      if (request.version !== 1 || request.league !== league || !/^\d+$/.test(request.run_id)) throw new Error('Invalid GitHub payout request');
      const prior = ref.getRange('Z11').getValue();
      if (prior) {
        const done = JSON.parse(prior);
        if (done.run_id === request.run_id && done.source_sha256 === request.source_sha256 && done.status === 'success') continue;
      }
      try {
        const display = book.getSheetByName('Display');
        if (display.getRange('A1').getValue() !== request.season) throw new Error('Payout year mismatch');
        const actual = ref.getRange('E2:V102').getValues();
        actual.forEach((row,r) => row.forEach((v,c) => {
          const expected = request.inputs[r][c];
          if (typeof expected === 'number' ? typeof v !== 'number' || Math.abs(v-expected)>0.000001 : v !== expected) throw new Error('Payout input changed before logo refresh');
        }));
        SpreadsheetApp.flush();
        const grid = display.getRange('B3:I25').getValues();
        const expected = display.getRange('A3:A25').getValues().map(r => request.awards[r[0]]);
        if (JSON.stringify(grid) !== JSON.stringify(expected)) throw new Error('Payout winners have not recalculated');
        payoutSyncLogos(display, grid);
        SpreadsheetApp.flush();
        const wanted = [];
        grid.forEach((row,r) => row.forEach((v,c) => {if(v)String(v).split(', ').forEach(a => wanted.push(PAYOUTS.prefix+(r+3)+':'+(c+2)+':'+a));}));
        const images = display.getImages().filter(i => i.getAltTextTitle().startsWith(PAYOUTS.prefix));
        const keys = images.map(i => i.getAltTextTitle());
        if (JSON.stringify(keys.sort()) !== JSON.stringify(wanted.sort())) throw new Error('Payout logo inventory mismatch');
        for (const img of images) {
          const bits = img.getAltTextTitle().split(':');
          if (img.getAnchorCell().getRow() !== Number(bits[1]) || img.getAnchorCell().getColumn() !== Number(bits[2])) throw new Error('Payout logo anchored to wrong cell');
        }
        // Reject acknowledgement if another workflow changed the request.
        if (ref.getRange('Z10').getValue() !== raw) throw new Error('Payout request changed during refresh');
        ref.getRange('Z11').setValue(JSON.stringify({status:'success',run_id:request.run_id,source_sha256:request.source_sha256,week:request.week,images:images.length,verified_at:new Date().toISOString()}));
        console.log(league+': payout logos verified through Week '+request.week+' for GitHub '+request.run_id);
      } catch(e) {
        ref.getRange('Z11').setValue(JSON.stringify({status:'failure',run_id:request.run_id,source_sha256:request.source_sha256,error:String(e),at:new Date().toISOString()}));
        console.error(league+': '+e);
      }
    }
  } finally {lock.releaseLock();}
}

// Uses BonusMFL.gs's existing commissioner connection, ranking and idempotent
// form reconciliation. Only explicit GitHub official requests can write MFL.
function refreshGithubBonusMfl(league, ref) {
  const raw = ref.getRange('Z12').getValue();
  if (!raw) return;
  const request = JSON.parse(raw), priorRaw = ref.getRange('Z13').getValue();
  const prior = priorRaw ? JSON.parse(priorRaw) : {};
  if (prior.run_id === request.run_id && prior.source_sha256 === request.source_sha256 && ['success','failure'].includes(prior.status)) return;
  const ack = {run_id:request.run_id,source_sha256:request.source_sha256,league:league,season:request.season,week:request.week,mode:request.mode};
  try {
    bonusMflRequire(request.version === 1 && request.league === league && request.season === BONUS_MFL.year && /^\d+$/.test(request.run_id), 'invalid GitHub request');
    bonusMflRequire(['official','preview'].includes(request.mode) && Number.isInteger(request.week) && request.week >= 1 && request.week <= 17, 'invalid request mode/week');
    const c = ELO.leagues.find(c => c.name === league);
    bonusMflRequire(c, 'unknown league');
    const due = [3,6,9,12].filter(w => w <= request.week);
    const now = new Date(), day = Utilities.formatDate(now, ELO.timezone, 'yyyy-MM-dd');
    const clock = Utilities.formatDate(now, ELO.timezone, 'HH:mm');
    if (request.mode === 'official') for (const week of due) {
      bonusMflRequire(day > BONUS_MFL.due[week] || day === BONUS_MFL.due[week] && clock >= '03:45', 'Bonus Games cannot be entered before Thursday 03:45 ET');
    }
    const source = {last:request.week,reports:request.reports};
    bonusMflVerifySheet(c, source);
    const cookies = bonusMflLogin();
    let form = bonusMflGetForm(c, cookies);
    const results = [];
    for (const week of due) {
      const desired = bonusMflPlan(source.reports, week);
      let missing = bonusMflMissing(form.existing, desired);
      if (request.mode === 'official' && missing.length) {
        form = bonusMflGetForm(c, cookies);
        missing = bonusMflMissing(form.existing, desired);
        if (missing.length) bonusMflSubmit(c, cookies, form, missing);
        const after = bonusMflGetForm(c, cookies);
        bonusMflRequire(bonusMflMissing(after.existing, desired).length === 0, 'submission incomplete; next workflow reconciles before retry');
        for (const [key,row] of Object.entries(form.existing)) bonusMflRequire(after.existing[key] && bonusMflEqual(after.existing[key], row), 'existing adjustment changed');
        const keys = new Set([...Object.keys(form.existing), ...desired.map(r => r.week+'_'+r.id)]);
        bonusMflRequire(Object.keys(after.existing).length === keys.size, 'unexpected extra adjustments');
        form = after;
      }
      results.push({week:week,rows:desired,missing_before:missing.length});
    }
    bonusMflRequire(ref.getRange('Z12').getValue() === raw, 'request changed during MFL entry');
    Object.assign(ack, {status:'success',due_weeks:due,results:results,verified_at:now.toISOString()});
    console.log(league+': GitHub MFL Bonus Games '+request.mode+' verified; due weeks '+due.join(', '));
  } catch(e) {
    Object.assign(ack, {status:'failure',error:String(e),verified_at:new Date().toISOString()});
    console.error(league+': MFL Bonus Games failed: '+e);
  }
  ref.getRange('Z13').setValue(JSON.stringify(ack));
}
