// Installed alongside the existing Payouts and PayoutLogos files.
// Sheets API cannot edit over-cell images. GitHub requests this display-only
// step through an authenticated sheet write, then waits for its acknowledgement.
// The same bridge also handles explicit official Bonus Games requests in Z12:Z13.
function installPayoutGithubBridge() {
  const handlers = new Set(['refreshGithubPayoutLogos', 'refreshGithubPayoutBridgeScheduled_']);
  for (const t of ScriptApp.getProjectTriggers()) {
    if (handlers.has(t.getHandlerFunction())) ScriptApp.deleteTrigger(t);
  }
  refreshGithubPayoutBridgeScheduled_();
  ScriptApp.newTrigger('refreshGithubPayoutBridgeScheduled_').timeBased().everyMinutes(5).create();
  console.log('GitHub Sheets bridge configured with event-driven dispatch and a five-minute recovery trigger.');
}

// GitHub calls this after writing an explicit Sheet request. Queue the work and
// return immediately so the web request cannot time out while Sheets refreshes.
function doPost(e) {
  const result = ContentService.createTextOutput().setMimeType(ContentService.MimeType.JSON);
  try {
    const payload = JSON.parse(e && e.postData && e.postData.contents || '{}');
    const expected = PropertiesService.getScriptProperties().getProperty('GITHUB_WORKFLOW_TOKEN');
    if (!expected || payload.token !== expected || payload.action !== 'refreshGithubPayoutLogos') {
      throw new Error('Unauthorized bridge request');
    }
    if (payload.operation === 'bonus_audit') return result.setContent(JSON.stringify(auditGithubBonusMfl_()));
    if (payload.operation === 'bonus_mfl') return result.setContent(JSON.stringify(runGithubBonusMflNow_(payload)));
    if (payload.operation === 'elo_chart') {
      return result.setContent(JSON.stringify(runEloChartBridgeRepair_(payload)));
    }
    queueGithubPayoutBridge_();
    return result.setContent(JSON.stringify({status:'success', queued:true}));
  } catch (error) {
    return result.setContent(JSON.stringify({status:'failure', error:String(error)}));
  }
}

function queueGithubPayoutBridge_() {
  const lock = LockService.getUserLock();
  if (!lock.tryLock(5000)) {
    // A bridge worker is already processing another request. Accept this
    // request and schedule a later pass instead of making GitHub retry/fail.
    ScriptApp.newTrigger('refreshGithubPayoutBridgeScheduled_').timeBased().after(30000).create();
    console.log('GitHub bridge was busy; accepted the request for a retry in 30 seconds.');
    return false;
  }
  try {
    const handler = 'refreshGithubPayoutBridgeScheduled_';
    const queued = ScriptApp.getProjectTriggers().some(t => t.getHandlerFunction() === handler);
    if (!queued) ScriptApp.newTrigger(handler).timeBased().after(1000).create();
  } finally {
    lock.releaseLock();
  }
}

function refreshGithubPayoutBridgeScheduled_() {
  const lock = LockService.getUserLock();
  if (!lock.tryLock(5000)) {
    ScriptApp.newTrigger('refreshGithubPayoutBridgeScheduled_').timeBased().after(30000).create();
    console.log('GitHub bridge was busy; queued a retry in 30 seconds.');
    return false;
  }
  try {
    for (const league of Object.keys(PAYOUTS.books)) {
      const book = SpreadsheetApp.openById(PAYOUTS.books[league]);
      const ref = book.getSheetByName('Reference');

      // Authoritative acknowledgements must never wait behind over-cell image
      // work. Process the small, time-sensitive requests before payout logos.
      refreshGithubBonusMfl(league, ref);
      refreshGithubEloChartRangeBridge_(league, ref);

      const raw = ref.getRange('Z10').getValue();
      if (raw) {
        const request = JSON.parse(raw);
        if (request.version !== 1 || request.league !== league || !/^\d+$/.test(request.run_id)) throw new Error('Invalid GitHub payout request');
        const prior = ref.getRange('Z11').getValue();
        const done = prior ? JSON.parse(prior) : {};
        if (!(done.run_id === request.run_id && done.source_sha256 === request.source_sha256 && done.status === 'success')) {
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
            if (ref.getRange('Z10').getValue() !== raw) throw new Error('Payout request changed during refresh');
            ref.getRange('Z11').setValue(JSON.stringify({status:'success',run_id:request.run_id,source_sha256:request.source_sha256,week:request.week,images:images.length,verified_at:new Date().toISOString()}));
            console.log(league+': payout logos verified through Week '+request.week+' for GitHub '+request.run_id);
          } catch(e) {
            ref.getRange('Z11').setValue(JSON.stringify({status:'failure',run_id:request.run_id,source_sha256:request.source_sha256,error:String(e),at:new Date().toISOString()}));
            console.error(league+': '+e);
          }
        }
      }
    }
    return true;
  } finally {lock.releaseLock();}
}

// Keep the web endpoint self-contained. Apps Script web deployments have
// occasionally omitted the sibling EloChartRange.gs global from the deployed
// execution context even though ordinary editor and trigger runs can see it.
function refreshGithubEloChartRangeBridge_(league, ref) {
  const raw = ref.getRange('Z14').getValue();
  if (!raw) return;
  const q = JSON.parse(raw);
  try {return runEloChartBridgeRepair_({league:league,operation:'elo_chart',run_id:q.request_id});}
  catch (error) {console.error(league+': chart request deferred: '+error);}
}

function refreshGithubBonusMfl(league,ref) {
  // Serialize MFL writes independently of the slow payout-logo worker.
  const lock=LockService.getUserLock();
  if (!lock.tryLock(1000)) return {queued:true};
  try {return refreshGithubBonusMflLocked_(league,ref);}
  finally {lock.releaseLock();}
}
function refreshGithubBonusMflLocked_(league, ref) {
  const raw = ref.getRange('Z12').getValue();
  if (!raw) return;
  const request = JSON.parse(raw), priorRaw = ref.getRange('Z13').getValue();
  const prior = priorRaw ? JSON.parse(priorRaw) : {};
  if (prior.run_id === request.run_id && prior.source_sha256 === request.source_sha256 && prior.status === 'success') return;
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
    for (const field of ['TPF','PPF']) {
      const report=request.reports[field];
      bonusMflRequire(report && JSON.stringify(Object.keys(report).sort())===JSON.stringify(bonusMflIds()), 'incomplete published Bonus Games source');
      bonusMflRequire(Object.values(report).every(values=>Array.isArray(values)&&values.length>=request.week&&values.slice(0,request.week).every(Number.isFinite)), 'invalid published Bonus Games scores');
    }
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



function runGithubBonusMflNow_(payload) {
  bonusMflRequire(['ADL','FAFL'].includes(payload.league) && /^\d+$/.test(payload.run_id||''), 'invalid direct Bonus Games request');
  const ref=SpreadsheetApp.openById(PAYOUTS.books[payload.league]).getSheetByName('Reference');
  const request=JSON.parse(ref.getRange('Z12').getValue()||'{}');
  bonusMflRequire(request.run_id===payload.run_id && request.league===payload.league,'Bonus Games request changed before dispatch');
  const result=refreshGithubBonusMfl(payload.league,ref);
  return {status:'success',queued:!!result?.queued};
}

// Authenticated, read-only audit: exposes readiness flags, never credentials.
function auditGithubBonusMfl_() {
  const props=PropertiesService.getScriptProperties();
  const names=ScriptApp.getProjectTriggers().map(t=>t.getHandlerFunction());
  const stamp=Number(props.getProperty('CLOUD_SCHEDULER_LAST_RUN')||0);
  return {status:'success',audit_version:1,season:BONUS_MFL.year,due:BONUS_MFL.due,
    mfl_credentials_configured:BONUS_MFL.credentialKeys.every(k=>!!props.getProperty(k)),
    handler_present:typeof refreshGithubBonusMflLocked_==='function',
    scheduler_installed:names.includes('runCloudLeagueScheduler'),
    scheduler_last_run:stamp?new Date(stamp).toISOString():null,
    legacy_elo_trigger_count:names.filter(n=>n==='updateElo').length};
}
