const el = id => document.getElementById(id);
const conferences = ['NFC', 'AFC'];
const currency = new Intl.NumberFormat('en-US', {
  style: 'currency', currency: 'USD', minimumFractionDigits: 0, maximumFractionDigits: 2
});
const cash = value => currency.format(value);
const escapeText = value => String(value).replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[char]));
const pending = '<span class="muted" aria-label="Pending">—</span>';

function teamChip(team) {
  return `<span class="team-chip" title="${escapeText(team.name)}">
    <img src="${escapeText(team.logo)}" alt="" width="28" height="28" loading="lazy">
    <strong>${escapeText(team.code)}</strong>
  </span>`;
}

function renderAwards({ awards }, teams) {
  const roles = ['Head Coach ($)', 'Off. Coordinator', 'Def. Coordinator', 'General Manager'];
  const headings = conferences.map(conf => roles.map(role =>
    `<th scope="col" class="${conf.toLowerCase()}">${role}</th>`).join('')).join('');
  const rows = awards.map(({ period, settled, winners }) => {
    const cashAward = period === 'Regular Season ($)';
    const summary = !period.startsWith('Week');
    return `<tr class="${summary ? 'period-total' : ''}${cashAward ? ' prize-period' : ''}${settled ? '' : ' future'}">
      <th scope="row">${escapeText(period)}</th>
      ${winners.map((codes, index) => `<td${index % roles.length === 0 ? ' class="prize-award"' : ''}>${codes.map(code => teamChip(teams.get(code))).join('') || pending}</td>`).join('')}
    </tr>`;
  }).join('');
  el('awards-table').innerHTML = `<table class="awards-grid">
    <colgroup span="1"></colgroup><colgroup span="4"></colgroup><colgroup span="4"></colgroup>
    <thead><tr><th rowspan="2" scope="col">Period</th>
      <th colspan="4" scope="colgroup" class="nfc">NFC</th>
      <th colspan="4" scope="colgroup" class="afc">AFC</th></tr>
    <tr>${headings}</tr></thead><tbody>${rows}</tbody></table>`;
}

function renderMoney(snapshot, teams) {
  const amounts = [
    ['Payout balance', 'payout'], ['Earned', 'earned'], ['Adjustments', 'adjustments'],
    ['Prize pool', 'pool'], ['Still to award', 'remaining'], ['League pay-in', 'payIn']
  ];
  el('money-summary').innerHTML = amounts.map(([label, key]) =>
    `<div><dt>${label}</dt><dd>${cash(snapshot.totals[key])}</dd></div>`).join('');

  el('team-ledger').innerHTML = conferences.map(conf => {
    const rows = snapshot.teams.filter(team => team.conference === conf)
      .sort((a, b) => b.payout - a.payout || b.earned - a.earned || a.code.localeCompare(b.code));
    return `<div class="surface scroll" role="region" tabindex="0" aria-label="${conf} team balances">
      <table class="ledger">
      <caption class="${conf.toLowerCase()}">${conf}</caption>
      <thead><tr><th scope="col">Team</th><th scope="col">Earned</th>
      <th scope="col"><abbr title="Adjustment">Adj.</abbr></th><th scope="col">Payout</th></tr></thead>
      <tbody>${rows.map(team => `<tr>
        <th scope="row">${teamChip(team)}</th><td>${cash(team.earned)}</td>
        <td>${team.adjustment ? cash(team.adjustment) : '<span class="muted">—</span>'}</td>
        <td class="payout-value">${cash(team.payout)}</td></tr>`).join('')}</tbody>
      <tfoot><tr><th scope="row">Total</th>
        ${['earned', 'adjustment', 'payout'].map(key => `<td>${cash(rows.reduce((sum, row) => sum + row[key], 0))}</td>`).join('')}
      </tr></tfoot></table></div>`;
  }).join('');

  const prizeRows = group => {
    const prizes = snapshot.prizes.filter(prize => prize.group === group);
    return `<tbody aria-label="${group} prizes">
      <tr class="prize-group"><th scope="rowgroup" colspan="4">${group}</th></tr>
      ${prizes.map(prize => `<tr class="prize-row"><th scope="row">${escapeText(prize.label)}
        ${prize.scope === 'league' ? '<small>League-wide</small>' : ''}</th>
        ${conferences.map(conf => `<td>${prize.recipients[conf].map(code => teamChip(teams.get(code))).join('')
          || (prize.settled ? '<span class="muted" aria-label="No recipient">—</span>' : pending)}</td>`).join('')}
        <td>${cash(prize.amount)}</td></tr>`).join('')}</tbody>`;
  };
  const prizeTable = (groups, label) => `<div class="surface scroll" role="region" tabindex="0" aria-label="${label}">
    <table class="prizes"><thead>
    <tr><th scope="col">Prize</th><th scope="col" class="nfc">NFC</th>
    <th scope="col" class="afc">AFC</th><th scope="col">Amount</th></tr>
    </thead>${groups.map(prizeRows).join('')}</table></div>`;
  el('prize-schedule').innerHTML = prizeTable(['Postseason', 'Regular Season'], 'Postseason and regular-season prizes')
    + prizeTable(['Weekly'], 'Weekly prizes');
}

function setTab(tab) {
  document.body.classList.toggle('money-active', tab.id === 'money-tab');
  for (const button of document.querySelectorAll('[role="tab"]')) {
    const active = button === tab;
    button.setAttribute('aria-selected', active);
    button.tabIndex = active ? 0 : -1;
    el(button.getAttribute('aria-controls')).hidden = !active;
  }
}

const tabs = [...document.querySelectorAll('[role="tab"]')];
for (const [index, tab] of tabs.entries()) {
  tab.addEventListener('click', () => {
    setTab(tab);
    history.replaceState(null, '', '#' + tab.getAttribute('aria-controls'));
  });
  tab.addEventListener('keydown', event => {
    const next = { ArrowLeft: (index + tabs.length - 1) % tabs.length,
      ArrowRight: (index + 1) % tabs.length, Home: 0, End: tabs.length - 1 }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    tabs[next].click();
    tabs[next].focus();
  });
}

fetch('payouts-data.json', { cache: 'no-cache' })
  .then(response => {
    if (!response.ok) throw new Error('Payout data request failed');
    return response.json();
  })
  .then(snapshot => {
    const teams = new Map(snapshot.teams.map(team => [team.code, team]));
    renderAwards(snapshot, teams);
    renderMoney(snapshot, teams);
    el('mast-season').textContent = snapshot.season;
    el('coverage').textContent = `${snapshot.season} season · Through Week ${snapshot.throughWeek}`;
    setTab(location.hash === '#money' ? el('money-tab') : el('awards-tab'));
    el('views').hidden = false;
  })
  .catch(error => {
    console.error(error);
    el('coverage').textContent = '';
    el('load-error').hidden = false;
  });
