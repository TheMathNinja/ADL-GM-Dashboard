const el = id => document.getElementById(id);
const conferences = ['NFC', 'AFC'];
const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
const cash = value => currency.format(value);
const escapeText = value => String(value).replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[char]));
const pending = '<span class="muted" aria-label="Pending">—</span>';

function teamChip(team, fullName = false) {
  return `<span class="team-chip" title="${escapeText(team.name)}">
    <img src="${escapeText(team.logo)}" alt="" width="28" height="28" loading="lazy">
    <strong>${escapeText(team.code)}</strong>${fullName ? `<span>${escapeText(team.name)}</span>` : ''}
  </span>`;
}

function renderAwards({ awards }, teams) {
  const roles = ['Head Coach', 'Off. Coordinator', 'Def. Coordinator', 'General Manager'];
  const headings = conferences.map(conf => roles.map(role =>
    `<th scope="col" class="${conf.toLowerCase()}">${role}</th>`).join('')).join('');
  const rows = awards.map(({ period, settled, winners }) => {
    const label = period.replace(' ($)', '');
    const summary = !period.startsWith('Week');
    return `<tr class="${summary ? 'period-total' : ''}${settled ? '' : ' future'}">
      <th scope="row">${escapeText(label)}</th>
      ${winners.map(codes => `<td>${codes.map(code => teamChip(teams.get(code))).join('') || pending}</td>`).join('')}
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
  const totals = snapshot.totals;
  const cards = [
    ['Current payout balance', totals.payout, `${cash(totals.earned)} prize earnings · ${cash(totals.adjustments)} adjustments`],
    ['Season prize pool', totals.pool, `${cash(totals.remaining)} in prizes still to award`],
    ['League pay-in', totals.payIn, 'Total listed league fees']
  ];
  el('money-summary').innerHTML = cards.map(([label, value, detail]) => `<article class="money-card">
    <h2>${label}</h2><strong>${cash(value)}</strong><p>${detail}</p></article>`).join('');

  el('money-leaders').innerHTML = conferences.map(conf => {
    const members = snapshot.teams.filter(team => team.conference === conf);
    const amount = Math.max(...members.map(team => team.earned));
    const leaders = members.filter(team => team.earned === amount && amount > 0);
    return `<article class="leader ${conf.toLowerCase()}"><div><h2>${conf} earnings ${leaders.length === 1 ? 'leader' : 'leaders'}</h2>
      <div>${leaders.length ? leaders.map(team => teamChip(team)).join('') : '<span class="muted">No prizes awarded</span>'}</div></div>
      <strong class="number">${cash(amount)}</strong></article>`;
  }).join('');

  const renderLedger = () => {
    const conf = el('conference').value;
    const rows = snapshot.teams.filter(team => !conf || team.conference === conf)
      .sort((a, b) => b.payout - a.payout || b.earned - a.earned || a.code.localeCompare(b.code));
    el('team-ledger').innerHTML = `<table class="ledger">
      <thead><tr><th scope="col">Team</th><th scope="col">Conf.</th><th scope="col">Earned</th>
      <th scope="col">Adjustment</th><th scope="col">Payout balance</th></tr></thead>
      <tbody>${rows.map(team => `<tr>
        <th scope="row">${teamChip(team, true)}</th><td>${team.conference}</td>
        <td>${cash(team.earned)}</td><td>${team.adjustment ? cash(team.adjustment) : '<span class="muted">—</span>'}</td>
        <td class="payout-value">${cash(team.payout)}</td></tr>`).join('')}</tbody>
      <tfoot><tr><th scope="row" colspan="2">${conf || 'League'} total</th>
        ${['earned', 'adjustment', 'payout'].map(key => `<td>${cash(rows.reduce((sum, row) => sum + row[key], 0))}</td>`).join('')}
      </tr></tfoot>
    </table>`;
  };
  el('conference').addEventListener('change', renderLedger);
  renderLedger();

  el('prize-schedule').innerHTML = ['Weekly', 'Regular Season', 'Postseason'].map(group => {
    const prizes = snapshot.prizes.filter(prize => prize.group === group);
    return `<details class="surface prize-group" ${group === 'Weekly' ? 'open' : ''}>
      <summary>${group} prizes <small>${prizes.filter(prize => prize.settled).length} of ${prizes.length} decided</small></summary>
      <div class="scroll" role="region" tabindex="0" aria-label="${group} prize table">
      <table class="prizes"><thead><tr><th scope="col">Prize</th><th scope="col">NFC</th>
      <th scope="col">AFC</th><th scope="col">Prize amount</th></tr></thead>
      <tbody>${prizes.map(prize => `<tr><th scope="row">${escapeText(prize.label)}
        ${prize.scope === 'league' ? '<small>League-wide</small>' : ''}</th>
        ${conferences.map(conf => `<td>${prize.recipients[conf].map(code => teamChip(teams.get(code))).join('')
          || (prize.settled ? '<span class="muted" aria-label="No recipient">—</span>' : pending)}</td>`).join('')}
        <td>${cash(prize.amount)}</td></tr>`).join('')}</tbody></table></div></details>`;
  }).join('');
}

function setTab(tab) {
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
    el('coverage').textContent = `${snapshot.season} season · Through Week ${snapshot.throughWeek}`;
    setTab(location.hash === '#money' ? el('money-tab') : el('awards-tab'));
    el('views').hidden = false;
  })
  .catch(error => {
    console.error(error);
    el('coverage').textContent = '';
    el('load-error').hidden = false;
  });
