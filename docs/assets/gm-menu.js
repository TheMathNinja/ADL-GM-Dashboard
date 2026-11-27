/* Native details menu with keyboard and outside-click dismissal. */
(()=>{const menus=[...document.querySelectorAll('[data-gm-menu]')];for(const menu of menus){const button=menu.querySelector('summary');button.setAttribute('aria-expanded',String(menu.open));menu.addEventListener('toggle',()=>{button.setAttribute('aria-expanded',String(menu.open));if(menu.open)for(const other of menus)if(other!==menu)other.open=false});menu.addEventListener('click',e=>{if(e.target.closest('nav a'))menu.open=false})}document.addEventListener('click',e=>{for(const menu of menus)if(!menu.contains(e.target))menu.open=false});document.addEventListener('keydown',e=>{if(e.key==='Escape')for(const menu of menus)if(menu.open){menu.open=false;menu.querySelector('summary').focus()}})})();

// Load the directory shared with the hosted EXT Calculator.
(() => {
  const directory = document.createElement('script');
  directory.src = 'https://themathninja.github.io/ADL-GM-Dashboard/assets/gm-module-directory.js';
  directory.dataset.gmDirectoryLeague = 'ADL';
  document.head.append(directory);
})();

// Keep the current shared module and tab when changing leagues.
(()=>{
 const initial=new URL(location.href),match=initial.pathname.match(/\/(ADL|FAFL)-GM-Dashboard\/(bonus-games|gameday|payouts|playoff-picture|trophy-room)(?:\/|$)/i);
 if(!match)return;
 const league=match[1].toUpperCase(),module=match[2].toLowerCase(),switches=[];
 function tabs(){return [...document.querySelectorAll(module==='bonus-games'?'[role="tab"][data-race]':module==='playoff-picture'?'[role="tab"][data-view]':'.tabs [role="tab"]')];}
 function tabId(button){return module==='bonus-games'?button.dataset.race:module==='playoff-picture'?button.dataset.view:button.id.replace(/-tab$/,'');}
 function selected(){
  if(['trophy-room','payouts'].includes(module)){const hash=location.hash.slice(1);if(tabs().some(b=>tabId(b)===hash))return hash;}
  const button=tabs().find(b=>b.getAttribute('aria-selected')==='true');return button?tabId(button):null;
 }
 function syncLinks(){
  const here=new URL(location.href),tab=selected();
  for(const toggle of switches)for(const link of toggle.querySelectorAll('a')){
   const value=link.dataset.league;
   if(value===league){link.href=here.href;continue;}
   const target=new URL(`https://themathninja.github.io/${value}-GM-Dashboard/${module}/`);target.search=here.search;target.hash=here.hash;
   if(['trophy-room','payouts'].includes(module)){target.searchParams.delete('leagueTab');if(tab)target.hash=tab;}
   else if(tab)target.searchParams.set('leagueTab',tab);
   link.href=target.href;
  }
 }
 function rememberSelection(){
  const here=new URL(location.href),tab=selected();
  if(!['trophy-room','payouts'].includes(module)&&tab&&here.searchParams.has('leagueTab')){here.searchParams.set('leagueTab',tab);history.replaceState(history.state,'',here);}
  syncLinks();
 }
 for(const menu of document.querySelectorAll('[data-gm-menu]')){
  const header=menu.closest('header');if(!header||header.querySelector('[data-gm-league-switch]'))continue;
  const group=document.createElement('div');group.className='gm-header-actions';
  const toggle=document.createElement('nav');toggle.className='gm-league-switch';toggle.setAttribute('data-gm-league-switch','');toggle.setAttribute('aria-label','League');
  for(const value of ['ADL','FAFL']){
   const link=document.createElement('a');link.textContent=value;link.dataset.league=value;
   link.setAttribute('aria-label',value+' '+({'bonus-games':'Bonus Games',gameday:'Gameday','playoff-picture':'Playoff Picture','trophy-room':'Trophy Room','payouts':'Payouts'}[module]));
   if(value===league)link.setAttribute('aria-current','page');toggle.append(link);
  }
  menu.before(group);group.append(toggle,menu);header.classList.add('gm-league-header');switches.push(toggle);
 }
 function restore(){
  const requested=new URL(location.href).searchParams.get('leagueTab');
  if(!['trophy-room','payouts'].includes(module)&&requested){const button=tabs().find(b=>tabId(b)===requested);if(button&&button.getAttribute('aria-selected')!=='true')button.click();}
  rememberSelection();
 }
 syncLinks();
 // Later deferred scripts install the Weekly Matchups/Live handlers, so restore
 // only after every deferred script has finished, not merely DOM parsing.
 if(document.readyState==='complete')restore();else document.addEventListener('DOMContentLoaded',restore,{once:true});
 for(const event of ['click','keydown'])document.addEventListener(event,e=>{if(e.target.closest?.('[role="tab"]'))queueMicrotask(rememberSelection);});
 window.addEventListener('hashchange',syncLinks);
})();
