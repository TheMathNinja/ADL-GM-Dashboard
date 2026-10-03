const fs=require('fs'), path=require('path'), assert=require('assert/strict');
const repo=path.resolve('work/adl-gm-dashboard');
const cache=process.env.ADL_GM_HISTORY_CACHE;
if(!cache)throw Error('Set ADL_GM_HISTORY_CACHE to archived ADL-{year}-weeklyResults.json and ADL-{year}-schedule.json files.');
const rows=JSON.parse(fs.readFileSync(repo+'/data/gm_career_seasons.json'));
const arr=x=>x==null?[]:Array.isArray(x)?x:[x];
for(let y=2016;y<=2025;y++){
 const end=y<2021?16:17;
 const raw=JSON.parse(fs.readFileSync(`${cache}/ADL-${y}-weeklyResults.json`));
 const weeks=arr(raw.allWeeklyResults.weeklyResults).filter(w=>+w.week<=end);
 const scores=new Map();
 for(const w of weeks){
  const map=new Map();
  for(const f of [...arr(w.franchise),...arr(w.matchup).flatMap(m=>arr(m.franchise))]){
   if(f.id==='BYE')continue;
   assert(Number.isFinite(Number(f.score))&&f.score!=='',`${y} ${w.week} missing score`);
   if(map.has(f.id))assert.equal(map.get(f.id),+f.score);
   map.set(f.id,+f.score);
  }
  assert.equal(map.size,32); scores.set(+w.week,map);
 }
 assert.equal(scores.size,end);
 const schedule=JSON.parse(fs.readFileSync(`${cache}/ADL-${y}-schedule.json`)).schedule.weeklySchedule;
 for(const r of rows.filter(r=>r.season===y)){
  let wins=0,ties=0,rswins=0,rsties=0;
  for(const [w,s] of scores)for(const [id,v] of s)if(id!==r.franchise_id){
   wins+=s.get(r.franchise_id)>v;ties+=s.get(r.franchise_id)===v;
   if(w<=12){rswins+=s.get(r.franchise_id)>v;rsties+=s.get(r.franchise_id)===v;}
  }
  assert.equal(r.wins,wins);assert.equal(r.ties,ties);assert.equal(r.losses,end*31-wins-ties);
  Object.assign(r,{rs_wins:rswins,rs_ties:rsties,rs_losses:372-rswins-rsties,h2h_wins:0,h2h_losses:0,h2h_ties:0});
  for(const w of arr(schedule).filter(w=>+w.week<=end))for(const m of arr(w.matchup)){
   const f=arr(m.franchise);if(f.length!==2||f.some(t=>t.id==='BYE'))continue;
   const own=f.find(t=>t.id===r.franchise_id);if(!own)continue;
   assert(['W','L','T'].includes(own.result),`${y} ${w.week} ${r.franchise_id} result missing`);
   r[{W:'h2h_wins',L:'h2h_losses',T:'h2h_ties'}[own.result]]++;
  }
 }
}
fs.writeFileSync(repo+'/data/gm_career_seasons.json',JSON.stringify(rows,null,2)+'\n');
fs.mkdirSync(repo+'/data/trophy_room',{recursive:true});

console.log('Validated and enriched all 320 canonical team-seasons; original all-play counts unchanged.');
