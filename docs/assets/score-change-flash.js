/* Flash changed actual scores only; initial renders and view/week switches establish a baseline. */
(()=>{
 const root=document.getElementById('bonus-design');if(!root)return;
 let previous=new Map(),scheduled=false;
 const active=new WeakMap(),armed=new Set();
 function collect(){
  scheduled=false;const next=new Map(),items=[];
  for(const el of root.querySelectorAll('[data-score-key]')){
   if(!el.getClientRects().length||el.closest('[hidden]'))continue;
   const weekly=el.closest('#weekly-matchups'),surface=weekly||el.closest('#bonus-live-lineup-popup')||el.closest('#bonus-live-stat-popup')||el.closest('#bonus-live-panels');
   if(!surface)continue;
   const week=weekly?document.getElementById('matchup-week')?.value:window.BonusLiveWatch?.getSnapshot()?.week;
   const scope=surface.id+':'+week+':'+(surface.dataset.teamId||''),key=scope+':'+(el.closest('[data-lineup-team]')?.dataset.lineupTeam||'')+':'+el.dataset.scoreKey,value=el.dataset.scoreValue;
   if(value==null||!Number.isFinite(Number(value)))continue;
   next.set(key,value);items.push({el,key,value,scope});
  }
  for(const {el,key,value,scope} of items){
   if(document.hidden||!armed.has(scope)||!previous.has(key)||previous.get(key)===value)continue;
   active.get(el)?.cancel();
   const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
   const frames=reduced?[{backgroundColor:'rgba(255,198,45,.75)'},{backgroundColor:'rgba(255,198,45,.75)'}]:[{backgroundColor:'rgba(255,198,45,.85)'},{backgroundColor:'rgba(255,211,91,.65)',offset:.18},{backgroundColor:'transparent'}];
   active.set(el,el.animate(frames,{duration:reduced?1000:2000,easing:'ease-out'}));
  }
  if(!window.BonusLiveWatch?.getBusy())for(const {scope} of items)armed.add(scope);
  previous=next;
 }
 function schedule(){if(!scheduled){scheduled=true;requestAnimationFrame(collect)}}
 new MutationObserver(records=>{
  if(records.some(r=>r.type==='attributes'||r.target.nodeType===1&&r.target.closest('[data-score-key]')||[...r.addedNodes,...r.removedNodes].some(n=>n.nodeType===1&&(n.matches('[data-score-key]')||n.querySelector('[data-score-key]')))))schedule();
 }).observe(root,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['data-score-value','hidden']});
 root.addEventListener('toggle',schedule,true);document.addEventListener('visibilitychange',schedule);
 collect();
})();


