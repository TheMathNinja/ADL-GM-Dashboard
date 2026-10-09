const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const template = fs.readFileSync('scripts/bonus_template.html', 'utf8');
const functions = ['recordCredit', 'sortConfig', 'sortValue', 'sortTeams']
  .map(name => template.split(/\r?\n/).find(line => line.startsWith(`function ${name}(`)));
assert(functions.every(Boolean));
const state = {race: 'Overview', sorts: {Overview: {key: 'race:Q2', dir: -1}}};
const context = vm.createContext({state});
vm.runInContext(functions.join('\n'), context);
const team = (name, win, tie, completed = false) => ({name, bonus: '0-0-0', events: [
  {event: 'Q2', p_win: win, p_tie: tie, completed}
]});
const rows = [team('Low', .1, .2), team('High', .8, .1), team('Middle', .4, .2)];
context.sortTeams(rows);
assert.deepEqual(rows.map(t => t.name), ['High', 'Middle', 'Low']);
state.sorts.Overview.dir = 1;
context.sortTeams(rows);
assert.deepEqual(rows.map(t => t.name), ['Low', 'Middle', 'High']);
assert.equal(context.sortValue(team('Tie', 0, 1, true), 'race:Q2'), .5);
assert.equal(context.sortValue(team('Win', 1, 0, true), 'race:Q2'), 1);
state.sorts.Overview = {key: 'team', dir: 1};
context.sortTeams(rows);
assert.deepEqual(rows.map(t => t.name), ['High', 'Low', 'Middle']);
console.log('Bonus sorting tests passed: projections, both directions, completed wins/ties, and names.');
