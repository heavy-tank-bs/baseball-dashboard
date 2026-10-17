const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'summary/compare.js'), 'utf8');
const start = source.indexOf('function normalizePlayerName(');
const end = source.indexOf('function summaryItems(', start);
const scope = {URLSearchParams};
vm.createContext(scope);
vm.runInContext(source.slice(start, end), scope);
for (const idKey of ['pitcherId', 'batterId']) {
  const rows = ['DeNA', 'ソフトバンク'].map(team => ({year:'2026', player:'Test', team, [idKey]:'123'}));
  for (const row of rows) {
    const params = new URLSearchParams({year:'2026',playerId:'123',team:row.team});
    assert.equal(scope.findCurrentRow(rows, params, {idKey}), row);
  }
}
console.log('Cross-league player links select the requested team: PASS');
