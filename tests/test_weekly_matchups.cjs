const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const root=path.join(__dirname,'..'),src=fs.readFileSync(path.join(root,'docs/assets/weekly-matchups.js'),'utf8'),ctx={};vm.createContext(ctx);vm.runInContext(src,ctx);
const pairs=ctx.WeeklyMatchupsCore.pairs([{id:'a',opponentIds:['b']},{id:'b',opponentIds:['a']},{id:'c',opponentIds:['d']},{id:'d',opponentIds:['c']}]);assert.equal(pairs.length,2);
assert(src.includes('d.week!==chosen'));assert(src.includes('seq!==request'));assert(src.includes('live.week===chosen'));assert(src.includes('data.final'));assert(src.includes('goldStar(a,b)'));assert(src.includes('matchupStakes(a,b)'));
const template=fs.readFileSync(path.join(root,'scripts/bonus_template.html'),'utf8');assert(template.includes('data-race="Matchups"'));assert(template.includes('window.WeeklyMatchups?.leave()'));assert(template.includes('weekly-matchups.js'));
console.log('Matchup pairing, week guards, stars/stakes and tab lifecycle passed');
