// Missing values must not enter a leaderboard as zero; signed metrics must
// draw inside the plot, on the appropriate side of the zero axis.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '..', 'summary/ranking.js'), 'utf8');
const scope = {
  currentMetric: () => ({field: 'metric', label: 'wRC+', kind: 'decimal', digits: 1}),
  config: {idKey: 'batterId'},
  state: {pitchType: 'all'},
  rowDenominator: () => 10,
  eligibleBaseRows: () => [null, undefined, '', 0, 0.25].map((metric, i) => ({metric, player: String(i)})),
};
vm.createContext(scope);
for (const name of ['parseNumber', 'escapeHtml', 'formatMetricValue', 'truncateLabel', 'chartAxisMax', 'metricRows', 'renderChart']) {
  const start = source.indexOf(`function ${name}(`);
  assert(start >= 0, `Missing function ${name}`);
  const next = source.indexOf('\nfunction ', start + 1);
  vm.runInContext(source.slice(start, next < 0 ? source.length : next), scope);
}
for (const missing of [null, undefined, '', '  ', NaN, Infinity, 'NaN']) {
  assert.equal(scope.parseNumber(missing), null);
}
assert.equal(scope.parseNumber(0), 0);
assert.equal(scope.parseNumber('0'), 0);
assert.equal(scope.parseNumber(-20), -20);
assert.deepEqual(Array.from(scope.metricRows(), row => row.value), [0, 0.25]);

function chart(values) {
  const markup = scope.renderChart(values.map((value, i) => ({value, player: `Player${i}`})));
  assert(!/NaN|Infinity/.test(markup));
  assert.match(markup, /class="ranking-chart-y-label">0\.0<\/text>/);
  const bars = [...markup.matchAll(/<rect[^>]*y="([\d.-]+)"[^>]*height="([\d.-]+)"[^>]*class="ranking-chart-bar"/g)]
    .map(match => ({y: Number(match[1]), height: Number(match[2])}));
  const axes = [...markup.matchAll(/<line[^>]*y1="([\d.-]+)"[^>]*y2="([\d.-]+)"[^>]*class="ranking-chart-axis-line"/g)];
  const zero = Number(axes[1][1]);
  for (const bar of bars) {
    assert(bar.y >= 21.9 && bar.y + bar.height <= 252.1, JSON.stringify(bar));
    assert(bar.height >= 0);
  }
  return {bars, zero};
}
const mixed = chart([-20, 0, 40]);
assert.equal(mixed.bars[0].y, mixed.zero);
assert(mixed.bars[0].height > 0);
assert.equal(mixed.bars[1].height, 0);
assert(mixed.bars[2].y < mixed.zero);
const negatives = chart([-20, -1]);
assert.equal(negatives.zero, 22);
assert(negatives.bars.every(bar => bar.y === negatives.zero));
const positives = chart([10, 20]);
assert.equal(positives.zero, 252);
assert(chart([0, 0]).bars.every(bar => bar.height === 0));
assert.equal(chart([null, 10]).bars.length, 1);
assert(scope.renderChart([{value: null}]).includes('グラフデータがありません'));
console.log('Ranking missing values and positive/negative/zero chart regression checks: PASS');
