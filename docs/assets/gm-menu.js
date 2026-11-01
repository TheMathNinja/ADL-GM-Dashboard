/* Native details menu with keyboard and outside-click dismissal. */
(()=>{const menus=[...document.querySelectorAll('[data-gm-menu]')];for(const menu of menus){const button=menu.querySelector('summary');button.setAttribute('aria-expanded',String(menu.open));menu.addEventListener('toggle',()=>{button.setAttribute('aria-expanded',String(menu.open));if(menu.open)for(const other of menus)if(other!==menu)other.open=false});menu.addEventListener('click',e=>{if(e.target.closest('nav a'))menu.open=false})}document.addEventListener('click',e=>{for(const menu of menus)if(!menu.contains(e.target))menu.open=false});document.addEventListener('keydown',e=>{if(e.key==='Escape')for(const menu of menus)if(menu.open){menu.open=false;menu.querySelector('summary').focus()}})})();

// One grouped, alphabetized directory for current modules and archived reports.
document.querySelectorAll('[data-gm-menu] nav').forEach(nav=>{
  const overview=nav.querySelector('.gm-overview-link');
  nav.replaceChildren();if(overview)nav.append(overview);
  const groups=[["Team Management", [["Compensatory Picks Tracker", "https://analyticsff.shinyapps.io/adl-ext-calculator/?tool=comp"], ["EXT Calculator", "https://analyticsff.shinyapps.io/adl-ext-calculator/?tool=ext"], ["Salary Cap Manager", "https://analyticsff.shinyapps.io/adl-ext-calculator/?tool=cap"]]], ["Team Tracking", [["Bonus Games", "https://themathninja.github.io/ADL-GM-Dashboard/bonus-games/"], ["Playoff Picture", "https://themathninja.github.io/ADL-GM-Dashboard/playoff-picture/"], ["Trophy Room", "https://themathninja.github.io/ADL-GM-Dashboard/trophy-room/"]]]];
  for(const [title,items] of groups){
    const section=document.createElement('div');section.className='gm-menu-section';section.setAttribute('role','group');section.setAttribute('aria-label',title);
    const heading=document.createElement('h2');heading.className='gm-menu-heading';heading.textContent=title;section.append(heading);
    for(const [name,url] of items){const link=document.createElement('a');link.href=url;link.textContent=name;section.append(link)}
    nav.append(section);
  }
});

// Stay in the same shared module when changing leagues.
(()=>{
 const current=new URL(location.href),match=current.pathname.match(/\/(ADL|FAFL)-GM-Dashboard\/(bonus-games|playoff-picture|trophy-room)(?:\/|$)/i);
 if(!match)return;
 const league=match[1].toUpperCase(),module=match[2].toLowerCase();
 for(const menu of document.querySelectorAll('[data-gm-menu]')){
  const header=menu.closest('header');if(!header||header.querySelector('[data-gm-league-switch]'))continue;
  const group=document.createElement('div');group.className='gm-header-actions';
  const toggle=document.createElement('nav');toggle.className='gm-league-switch';toggle.setAttribute('data-gm-league-switch','');toggle.setAttribute('aria-label','League');
  for(const value of ['ADL','FAFL']){
   const link=document.createElement('a');link.textContent=value;
   link.href=`https://themathninja.github.io/${value}-GM-Dashboard/${module}/${current.search}${current.hash}`;
   link.setAttribute('aria-label',value+' '+({'bonus-games':'Bonus Games','playoff-picture':'Playoff Picture','trophy-room':'Trophy Room'}[module]));
   if(value===league){link.setAttribute('aria-current','page');link.href=current.href;}
   toggle.append(link);
  }
  menu.before(group);group.append(toggle,menu);header.classList.add('gm-league-header');
 }
})();
