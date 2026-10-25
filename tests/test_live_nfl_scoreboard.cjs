const assert=require('node:assert/strict');require('../docs/assets/bonus-live-watch.js');
const {nflScoreMarkup}=globalThis.BonusLiveWatchCore;
const p={seconds:600,gameStatus:'4Q 10:00',nflScoreboard:[{team:'KCC',score:17,possession:true},{team:'SEA',score:14,possession:false}]};
let html=nflScoreMarkup(p);assert.match(html,/KCC 17/);assert.match(html,/SEA 14/);assert.match(html,/aria-label="KCC has possession"/);assert.equal((html.match(/<svg /g)||[]).length,1);
assert.equal(nflScoreMarkup({...p,gameStatus:'Final',seconds:0}),'');assert.equal(nflScoreMarkup({...p,gameStatus:'Pregame',seconds:3600}),'');assert.equal(nflScoreMarkup({...p,nflScoreboard:[]}),'');
assert.doesNotMatch(nflScoreMarkup({...p,nflScoreboard:p.nflScoreboard.map(t=>({...t,possession:false}))}),/<svg /);
assert.equal(nflScoreMarkup({...p,nflScoreboard:[{team:'<img>',score:10},p.nflScoreboard[1]]}),'');
console.log('Live NFL score and possession rendering passed; missing/stale possession is not invented.');
