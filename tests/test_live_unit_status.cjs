const assert=require('node:assert/strict');require('../docs/assets/bonus-live-watch.js');const {unitOnFieldProgress,unitOnFieldMarkup}=globalThis.BonusLiveWatchCore;
const player=(position,unitOnField,gameStatus='3Q 10:00')=>({position,unitOnField,gameStatus,seconds:1500});
let t={starters:[player('QB',true),player('LB',true),player('WR',false),player('PK',null),player('TE',false,'Final')]};
assert.deepEqual(unitOnFieldProgress(t),{count:2,unknown:0});assert.match(unitOnFieldMarkup(t),/\[2 on Field\]/);assert.match(unitOnFieldMarkup(t),/On field means their NFL unit/);
t.starters.push(player('CB',null));assert.deepEqual(unitOnFieldProgress(t),{count:2,unknown:1});assert.match(unitOnFieldMarkup(t),/\[2 on Field\]/);assert.match(unitOnFieldMarkup({starters:[]}),/\[0 on Field\]/);
console.log('On Field labels, unit totals, unknown possession and special-teams exclusions passed.');

assert.match(unitOnFieldMarkup({starters:[player('QB',null)]}),/\[0 on Field\]/);
