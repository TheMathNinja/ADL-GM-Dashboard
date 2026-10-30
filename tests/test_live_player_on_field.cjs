const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../docs/assets/bonus-live-watch.js'),'utf8'),ctx);
const c=ctx.BonusLiveWatchCore,p={seconds:900,gameStatus:'4Q 15:00',nflGamePhase:'live',position:'LB',unitOnField:true};
assert(c.playerOnField(p));assert(c.playerOnFieldBall(p).includes('<svg'));assert(c.playerOnField({...p,position:'WR'}));
for(const change of [{unitOnField:false},{unitOnField:null},{gameStatus:'Pregame'},{gameStatus:'Final'},{gameStatus:'Halftime'},{gameStatus:'Awaiting OT',seconds:0},{nflGamePhase:'between_periods'},{position:'PK'}]){assert(!c.playerOnField({...p,...change}));assert.equal(c.playerOnFieldBall({...p,...change}),'')}
assert.equal(c.unitOnFieldProgress({starters:[p,{...p,unitOnField:false},{...p,nflGamePhase:'halftime'}]}).count,1);
const source=fs.readFileSync(path.join(__dirname,'../docs/assets/bonus-live-watch.js'),'utf8');assert(source.includes('gm-live-player-on-field'));assert(source.includes('${playerOnFieldBall(p)}${escape(displayPlayerName(p.name))}'));
console.log('Player on-field icon, pause guards, defensive units, and row styling tests passed');
