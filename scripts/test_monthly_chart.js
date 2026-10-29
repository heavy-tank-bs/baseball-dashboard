"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(root, "summary/compare.js"), "utf8").replace(/\ninit\(\);\s*$/, "");
const scope = vm.createContext({ document: { getElementById: () => ({}) } });
vm.runInContext(`${source}\nglobalThis.api = { chartSvg, TYPE_CONFIG };`, scope, { filename: "compare.js" });
const { chartSvg, TYPE_CONFIG } = scope.api;
const countMetric = { key: "games", label: "試合", kind: "number", digits: 0 };
const inningsMetric = { key: "inningsOuts", label: "投球回", kind: "innings" };
const averageMetric = { key: "battingAverage", label: "打率", kind: "average", digits: 3 };

function rows(values, key = "games") {
  return values.map((value, index) => ({ monthLabel: `${index + 3}月`, [key]: value }));
}

function circles(markup) {
  return [...markup.matchAll(/<circle cx="([\d.]+)" cy="([\d.]+)"[^>]*><title>(.*?)<\/title><\/circle>/g)]
    .map((match) => ({ x: Number(match[1]), y: Number(match[2]), title: match[3] }));
}

function textLabels(markup, className) {
  return [...markup.matchAll(new RegExp(`<text[^>]*class="${className}(?: [^"]*)?"[^>]*>([\\s\\S]*?)<\\/text>`, "g"))]
    .map((match) => match[1].trim());
}

const gaps = chartSvg(countMetric, rows([5, null, 0, undefined, 8]));
assert.deepEqual(circles(gaps).map((point) => point.x), [60, 202, 344], "missing months retain their positions on the time axis");
assert.deepEqual(circles(gaps).map((point) => point.title), ["3月: 5", "5月: 0", "7月: 8"], "a known zero remains a plotted value");
const gapPath = gaps.match(/<path d="([^"]+)"/)[1];
assert.equal((gapPath.match(/M /g) || []).length, 3, "each gap starts a new path segment");
assert.ok(!gapPath.includes("L "), "never imply a continuous trend across missing data");
assert.deepEqual(textLabels(gaps, "monthly-chart-axis-label"), ["3月", "4月", "5月", "6月", "7月"]);
assert.ok(gaps.includes('aria-label="試合の月別推移。3月: 5、4月: データなし、5月: 0、6月: データなし、7月: 8"'), "the accessible description includes each month and its availability");

const connected = chartSvg(countMetric, rows([2, 4, null, 3, 0]));
assert.match(connected, /<path d="M [\d.]+ [\d.]+ L [\d.]+ [\d.]+ M [\d.]+ [\d.]+ L [\d.]+ [\d.]+"/, "adjacent known months connect within separate contiguous segments");

const single = chartSvg(countMetric, rows([5]));
assert.deepEqual(circles(single), [{ x: 202, y: 88, title: "3月: 5" }], "one month is centered in the plot");
assert.match(single, /<text x="202.00" y="170" text-anchor="middle" class="monthly-chart-axis-label/);
assert.deepEqual(textLabels(single, "monthly-chart-range-label"), ["6", "4"]);

const zeros = chartSvg(countMetric, rows([0, 0, 0]));
assert.deepEqual(textLabels(zeros, "monthly-chart-range-label"), ["1", "0"], "constant zero counts use a nonnegative, nondegenerate range");
assert.equal(circles(zeros).length, 3);
assert.ok(circles(zeros).every((point) => point.y === 146));

const tinyAverage = chartSvg(averageMetric, rows([0.01], "battingAverage"));
assert.deepEqual(textLabels(tinyAverage, "monthly-chart-range-label"), ["0.110", "0.000"], "padding a nonnegative rate never creates a negative axis");

const constantInnings = chartSvg(inningsMetric, rows([61, 61], "inningsOuts"));
assert.deepEqual(textLabels(constantInnings, "monthly-chart-range-label"), ["22.2", "18"], "constant innings are padded using whole outs, formatted in baseball notation");
assert.ok(circles(constantInnings).every((point) => point.title.endsWith("20.1")));
const variedInnings = chartSvg(inningsMetric, rows([61, 62], "inningsOuts"));
assert.deepEqual(textLabels(variedInnings, "monthly-chart-range-label"), ["20.2", "20.1"]);
const zeroInnings = chartSvg(inningsMetric, rows([0], "inningsOuts"));
assert.deepEqual(textLabels(zeroInnings, "monthly-chart-range-label"), ["0.1", "0"]);

const missing = chartSvg(countMetric, rows([null, undefined, "", NaN, Infinity]));
assert.ok(missing.includes("データなし") && !missing.includes("<svg"));
assert.ok(missing.includes("7月: データなし"), "fully missing series still expose monthly availability");
const noAtBats = chartSvg({ key: "ops", label: "OPS", kind: "average" }, [{ monthLabel: "4月", atBats: 0, ops: 0 }]);
assert.ok(!noAtBats.includes("<circle"), "an undefined rate with no at-bats must not turn into a known zero");

const crowded = chartSvg(averageMetric, rows(Array(12).fill(0.3), "battingAverage"));
assert.equal(circles(crowded).length, 12, "label thinning must never discard plotted points");
const pointLabels = [...crowded.matchAll(/<text[^>]*class="monthly-chart-point-label([^"]*)"[^>]*>/g)];
assert.ok(pointLabels.length < 12, "crowded desktop value labels are thinned");
assert.equal(pointLabels.filter((match) => !match[1].includes("monthly-chart-label-mobile-hidden")).length, 2, "mobile keeps endpoint values readable");

const lateOnly = chartSvg(countMetric, rows([null, null, 8]));
assert.deepEqual(circles(lateOnly).map((point) => point.x), [344], "a lone observed month among missing months keeps its calendar position");
assert.match(lateOnly, /<text x="344.00"[^>]*text-anchor="end" class="monthly-chart-point-label/, "a lone endpoint value stays inside the chart");
const escaped = chartSvg({ ...countMetric, label: '<試合 "数">' }, [{ monthLabel: "<4月>", games: 2 }]);
assert.ok(!escaped.includes("<試合") && !escaped.includes("<4月>"), "labels and accessible descriptions are escaped");

for (const [type, file] of [["pitcher", "player_totals.json"], ["batter", "batter_totals.json"]]) {
  const payload = JSON.parse(fs.readFileSync(path.join(root, "summary", file), "utf8"));
  const annualRows = payload.players || payload.rows || payload;
  assert.ok(Array.isArray(annualRows), `${type} annual data is an array`);
  let monthlySeries = 0;
  for (const row of annualRows) {
    const splits = row.monthlySplits || [];
    if (!splits.length) continue;
    for (const metric of TYPE_CONFIG[type].metrics) {
      const markup = chartSvg(metric, splits);
      assert.ok(!/\b(?:NaN|Infinity)\b/.test(markup), `${type} ${row.year} ${row.player} ${metric.key} must have finite geometry`);
      monthlySeries += 1;
    }
  }
  assert.ok(monthlySeries > 0, `${type} actual monthly series were exercised`);
}

console.log("Monthly chart regressions passed: gaps, zero, ranges, innings, accessible values, and dense labels.");
