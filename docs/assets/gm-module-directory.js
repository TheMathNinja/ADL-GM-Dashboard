/* Add GM modules here. ADL, FAFL, and the hosted calculator use this directory. */
(() => {
  const groups = [
    { title: 'Team Management', modules: [
      { label: 'Compensatory Picks Tracker', tab: 'comp', leagues: ['ADL'], art: 'picks.svg' },
      { label: 'EXT Calculator', tab: 'ext', leagues: ['ADL'], art: 'ext.svg' },
      { label: 'Salary Cap Manager', tab: 'cap', leagues: ['ADL'], art: 'cap.svg' }
    ] },
    { title: 'Team Tracking', modules: [
      { label: 'Bonus Games', slug: 'bonus-games', art: 'bonus.svg', description: 'Quarterly and All-Season races, projected cutoffs, and each team’s win, tie and loss probabilities.' },
      { label: 'Gameday', slug: 'gameday', art: 'gameday.svg?v=score-slate-1', description: 'Live scores, projections, and full lineups for every weekly matchup.' },
      { label: 'Payouts', slug: 'payouts', description: 'Conference award winners, prize amounts and each team’s payout balance.' },
      { label: 'Playoff Picture', slug: 'playoff-picture', art: 'playoff.svg', description: 'Explore the current playoff field, projected wins and each team’s chances of reaching the playoffs, winning its division and earning the #1 seed.' },
      { label: 'Trophy Room', slug: 'trophy-room', art: 'trophy.svg', history: true, description: 'Celebrate FAFL champions, conference honors, prize earnings and all-time GM stats.' }
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

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function artwork(item) {
    const image = element('img');
    image.src = new URL('assets/tools/' + item.art, dashboard).href;
    image.alt = '';
    return image;
  }

  function moduleTile(item, layout, season) {
    const tile = moduleLink(item);
    tile.replaceChildren();
    if (layout === 'cards') {
      tile.className = 'card';
      if (item.slug === 'gameday' && item.art) {
        const image = artwork(item);
        image.className = 'gameday-card-icon';
        tile.append(image);
      }
      tile.append(element('span', 'tag', item.history ? 'LEAGUE HISTORY' : season + ' SEASON'),
        element('h2', '', item.label));
      if (item.description) tile.append(element('p', '', item.description));
      tile.append(element('span', 'button', 'Open ' + item.label + ' →'));
    } else {
      tile.className = 'tool';
      if (item.art) {
        const art = element('div', 'tool-art');
        art.append(artwork(item));
        tile.append(art);
      }
      const label = element('div', 'tool-label');
      const arrow = element('span', '', '↗');
      arrow.setAttribute('aria-hidden', 'true');
      label.append(element('h3', '', item.label), arrow);
      tile.append(label);
    }
    return tile;
  }

  for (const tiles of document.querySelectorAll('[data-gm-module-tiles]')) {
    const { gmModuleTiles: layout, season } = tiles.dataset;
    const sections = groups.flatMap((group, index) => {
      const modules = itemsFor(group);
      if (!modules.length) return [];
      if (layout === 'cards') return modules.map(item => moduleTile(item, layout, season));
      const section = element('section', 'tool-group');
      const heading = element('div', 'group-heading');
      const title = element('h2', '', group.title);
      title.id = 'group-' + index;
      section.setAttribute('aria-labelledby', title.id);
      heading.append(title);
      const list = element('div', 'tool-list');
      list.append(...modules.map(item => moduleTile(item, layout, season)));
      section.append(heading, list);
      return [section];
    });
    tiles.replaceChildren(...sections);
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
