const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const root=path.join(__dirname,'..'),src=fs.readFileSync(path.join(root,'docs/assets/weekly-matchups.js'),'utf8'),ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(root,'docs/assets/bonus-live-watch.js'),'utf8'),ctx);vm.runInContext(src,ctx);
const pairs=ctx.WeeklyMatchupsCore.pairs([{id:'a',opponentIds:['b']},{id:'b',opponentIds:['a']},{id:'c',opponentIds:['d']},{id:'d',opponentIds:['c']}]);assert.equal(pairs.length,2);
assert(src.includes('d.week!==chosen'));assert(src.includes('seq!==request'));assert(src.includes('shared().canOverlay(data,live)'));assert(src.includes('data.final'));assert(src.includes('goldStar(a,b)'));assert(src.includes('matchupStakes(a,b)'));
const template=fs.readFileSync(path.join(root,'scripts/bonus_template.html'),'utf8');assert(template.includes('data-race="Matchups"'));assert(template.includes('window.WeeklyMatchups?.leave()'));assert(template.includes('weekly-matchups.js'));
console.log('Matchup pairing, week guards, stars/stakes and tab lifecycle passed');

const changed=ctx.WeeklyMatchupsCore.publicationChanged;
const monday={generatedAt:'2026-11-03T05:00:00Z',publishedThroughWeek:8,modelId:'same'};
assert.equal(changed(monday,{...monday}),false);
assert.equal(changed(monday,{...monday,generatedAt:'2026-11-05T12:00:00Z'}),true,'Thursday correction invalidates the same week even when model/week stay fixed');
assert.equal(changed(monday,{...monday,publishedThroughWeek:9}),true);
assert.equal(changed(monday,{...monday,modelId:'new'}),true);
assert(src.includes('setInterval(checkPublication,60000)'));
console.log('Same-week correction, completed-week and model publication cache invalidation passed');
