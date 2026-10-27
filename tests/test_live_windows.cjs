const assert = require('node:assert/strict');
require('../docs/assets/bonus-live-watch.js');
const cases = require('./fixtures/live_watch_windows.json');
for (const [iso, expected] of cases) {
  assert.equal(globalThis.BonusLiveWatchCore.inWindow(new Date(iso)), expected, iso);
}
console.log('Thursday, international Sunday, Monday, midnight and DST windows passed');
