// Installed alongside the existing Payouts and PayoutLogos files.
// Sheets API cannot edit over-cell images. GitHub requests this display-only
// step through an authenticated sheet write, then waits for its acknowledgement.
function installPayoutGithubBridge() {
  const handler = 'refreshGithubPayoutLogos';
  if (!ScriptApp.getProjectTriggers().some(t => t.getHandlerFunction() === handler)) {
    ScriptApp.newTrigger(handler).timeBased().everyMinutes(1).create();
  }
  refreshGithubPayoutLogos();
  console.log('GitHub payout display bridge installed; no MFL scrape or Elo update is performed.');
}

function refreshGithubPayoutLogos() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    for (const league of Object.keys(PAYOUTS.books)) {
      const book = SpreadsheetApp.openById(PAYOUTS.books[league]);
      const ref = book.getSheetByName('Reference');
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
