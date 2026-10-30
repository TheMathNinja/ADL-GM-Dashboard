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
   const box=el.getBoundingClientRect(),target=el.querySelector('.gm-live-primary,strong,button')||el,range=document.createRange();range.selectNodeContents(target);
   const text=range.getBoundingClientRect(),bounds=text.width&&text.height?text:box;
   el.style.setProperty('--score-burst-x',(bounds.left+bounds.width/2-box.left)+'px');
   el.style.setProperty('--score-burst-y',(bounds.top+bounds.height/2-box.top)+'px');
   el.style.setProperty('--score-burst-size',Math.max(36,Math.min(80,bounds.height*2.5,bounds.width+30))+'px');
   el.classList.add('gm-score-sunburst');
   const frames=reduced?[{opacity:.8},{opacity:.8}]:[{opacity:0,transform:'translate(-50%,-50%) scale(.65)'},{opacity:1,transform:'translate(-50%,-50%) scale(1)',offset:.12},{opacity:.75,transform:'translate(-50%,-50%) scale(1.08)',offset:.38},{opacity:0,transform:'translate(-50%,-50%) scale(1.2)'}];
   const animation=el.animate(frames,{duration:reduced?1000:3000,easing:'ease-out',pseudoElement:'::before'});
   active.set(el,animation);
   const clear=()=>{if(active.get(el)!==animation)return;el.classList.remove('gm-score-sunburst');active.delete(el)};
   animation.onfinish=clear;animation.oncancel=clear;
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


