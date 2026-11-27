/* Add GM modules here. ADL, FAFL, and the hosted calculator use this directory. */
(() => {
  const groups = [
    { title: 'Team Management', modules: [
      { label: 'Compensatory Picks Tracker', tab: 'comp', leagues: ['ADL'] },
      { label: 'EXT Calculator', tab: 'ext', leagues: ['ADL'] },
      { label: 'Salary Cap Manager', tab: 'cap', leagues: ['ADL'] }
    ] },
    { title: 'Team Tracking', modules: [
      { label: 'Bonus Games', slug: 'bonus-games' },
      { label: 'Gameday', slug: 'gameday' },
      { label: 'Payouts', slug: 'payouts' },
      { label: 'Playoff Picture', slug: 'playoff-picture' },
      { label: 'Trophy Room', slug: 'trophy-room' }
    ] }
  ];
  const league = document.currentScript.dataset.gmDirectoryLeague;
  const dashboard = `https://themathninja.github.io/${league}-GM-Dashboard/`;
  const currentPath = location.pathname.split('/');
  const itemsFor = group => group.modules.filter(item => !item.leagues || item.leagues.includes(league));

  function moduleLink(item) {
    const link = document.createElement('a');
    link.href = item.tab ? `https://analyticsff.shinyapps.io/adl-ext-calculator/?tool=${item.tab}` : new URL(item.slug + '/', dashboard).href;
    link.textContent = item.label;
    return link;
  }

  for (const nav of document.querySelectorAll('[data-gm-menu] nav')) {
    const overview = nav.querySelector('.gm-overview-link');
    nav.replaceChildren();
    if (overview) nav.append(overview);
    for (const group of groups) {
      const modules = itemsFor(group).filter(item => !currentPath.includes(item.slug));
      if (!modules.length) continue;
      const section = document.createElement('div');
      section.className = 'gm-menu-section';
      section.setAttribute('role', 'group');
      section.setAttribute('aria-label', group.title);
      const heading = document.createElement('h2');
      heading.className = 'gm-menu-heading';
      heading.textContent = group.title;
      section.append(heading, ...modules.map(moduleLink));
      nav.append(section);
    }
    if (league === 'FAFL') {
      const home = document.createElement('a');
      home.href = 'https://www43.myfantasyleague.com/2026/home/22686';
      home.textContent = 'FAFL league ↗';
      (nav.lastElementChild || nav).append(home);
    }
  }

  for (const marker of document.querySelectorAll('[data-gm-shiny-directory]')) {
    const menu = marker.closest('.dropdown-menu');
    const placeholder = marker.closest('li');
    if (!menu || !placeholder) continue;
    for (const group of groups) {
      const external = itemsFor(group).filter(item => {
        if (!item.tab) return true;
        const nativeTab = menu.querySelector(`[data-value="${item.tab}"]`);
        if (nativeTab) nativeTab.textContent = item.label;
        return false;
      });
      if (!external.length) continue;
      if (!itemsFor(group).some(item => item.tab)) {
        const row = document.createElement('li');
        const heading = document.createElement('h6');
        heading.className = 'dropdown-header';
        heading.textContent = group.title;
        row.append(heading);
        placeholder.before(row);
      }
      for (const item of external) {
        const row = document.createElement('li');
        const link = moduleLink(item);
        link.className = 'dropdown-item';
        row.append(link);
        placeholder.before(row);
      }
    }
    placeholder.remove();
  }
})();
