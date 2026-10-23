/* Native details menu with keyboard and outside-click dismissal. */
(()=>{const menus=[...document.querySelectorAll('[data-gm-menu]')];for(const menu of menus){const button=menu.querySelector('summary');button.setAttribute('aria-expanded',String(menu.open));menu.addEventListener('toggle',()=>{button.setAttribute('aria-expanded',String(menu.open));if(menu.open)for(const other of menus)if(other!==menu)other.open=false});menu.addEventListener('click',e=>{if(e.target.closest('nav a'))menu.open=false})}document.addEventListener('click',e=>{for(const menu of menus)if(!menu.contains(e.target))menu.open=false});document.addEventListener('keydown',e=>{if(e.key==='Escape')for(const menu of menus)if(menu.open){menu.open=false;menu.querySelector('summary').focus()}})})();

// Keep every module and archived report's common menu current.
document.querySelectorAll('[data-gm-menu] nav').forEach(nav=>{
  if(nav.querySelector('a[href*="tool=cap"]'))return;
  const link=document.createElement('a');
  link.href='https://analyticsff.shinyapps.io/adl-ext-calculator/?tool=cap';
  link.textContent='Salary Cap Manager';
  nav.insertBefore(link,nav.querySelector('a[href*="tool=comp"]'));
});
