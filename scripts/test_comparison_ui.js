"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(root, "summary/compare.js"), "utf8").replace(/\ninit\(\);\s*$/, "");
const exportNames = [
  "init", "state", "TYPE_CONFIG", "comparisonPair", "availableComparisonYears", "comparisonMetricKeys",
  "comparisonMetrics", "comparisonValue", "differenceMarkup", "comparisonBarMarkup", "compareCardsMarkup",
  "renderComparePanel", "renderMetricToggles", "metricValue", "formatMetricDelta", "formatInningsFromOuts",
  "monthlySplits", "comparisonSeasonMarkup", "renderMonthlyPanel", "renderMonthlyTable", "renderMonthlyCharts",
];

function loadPage(payload, search) {
  const elements = new Map();
  function makeElement(dataset = {}) {
    const listeners = new Map();
    const attributes = new Map();
    const classes = new Set();
    let html = "";
    let childButtons = null;
    return {
      dataset, textContent: "", open: false,
      get innerHTML() { return html; },
      set innerHTML(value) { html = value; childButtons = null; },
      classList: {
        toggle(name, on) { if (on) classes.add(name); else classes.delete(name); },
        contains(name) { return classes.has(name); },
      },
      setAttribute(name, value) { attributes.set(name, value); },
      getAttribute(name) { return attributes.get(name); },
      addEventListener(type, callback) { listeners.set(type, callback); },
      click() { listeners.get("click")?.({ target: this }); },
      change(value) { this.value = value; listeners.get("change")?.({ target: this }); },
      querySelectorAll(selector) {
        const attribute = selector === "[data-mode]" ? "mode" : selector === "[data-metric-key]" ? "metric-key" : null;
        if (!attribute) return [];
        if (!childButtons) {
          childButtons = [...html.matchAll(new RegExp(`data-${attribute}="([^\"]+)"`, "g"))]
            .map((match) => makeElement({ [attribute === "mode" ? "mode" : "metricKey"]: match[1] }));
        }
        return childButtons;
      },
      querySelector() { return null; },
    };
  }
  function element(id) {
    if (!elements.has(id)) elements.set(id, makeElement());
    return elements.get(id);
  }
  const buttons = {
    preset: ["main", "all"].map((comparePreset) => makeElement({ comparePreset })),
    view: ["table", "bars"].map((compareView) => makeElement({ compareView })),
    monthlyPreset: ["main", "all"].map((monthlyPreset) => makeElement({ monthlyPreset })),
    monthlyView: ["table", "line"].map((monthlyView) => makeElement({ monthlyView })),
  };
  const fetchCalls = [];
  const window = { location: { search }, addEventListener() {}, scrollTo() {} };
  window.parent = window;
  const context = vm.createContext({
    URLSearchParams, window,
    document: {
      getElementById: element,
      body: makeElement(),
      querySelector() { return null; },
      querySelectorAll(selector) {
        if (selector === "[data-compare-preset]") return buttons.preset;
        if (selector === "[data-compare-view]") return buttons.view;
        if (selector === "[data-monthly-preset]") return buttons.monthlyPreset;
        if (selector === "[data-monthly-view]") return buttons.monthlyView;
        return [];
      },
    },
    fetch: async (url) => {
      fetchCalls.push(url);
      return { ok: true, json: async () => url.includes("nf3_2025") ? { players: [] } : payload };
    },
  });
  vm.runInContext(`${source}\nglobalThis.api = {${exportNames.join(",")}};`, context, { filename: "compare.js" });
  return { api: context.api, element, buttons, fetchCalls };
}

function bodyRows(markup) {
  return [...(markup.match(/<tbody>([\s\S]*?)<\/tbody>/)?.[1] || "").matchAll(/<tr>([\s\S]*?)<\/tr>/g)].map((match) => match[1]);
}

function tableRow(markup, label) {
  const row = bodyRows(markup).find((value) => value.includes(`<th scope="row">${label}</th>`));
  assert.ok(row, `missing metric row ${label}`);
  return [...row.matchAll(/<td>([\s\S]*?)<\/td>/g)].map((match) => match[1].replace(/<[^>]*>/g, ""));
}

function barPositions(markup) {
  return [...markup.matchAll(/style="left:([\d.]+)%;width:([\d.]+)%"/g)].map((match) => ({ left: Number(match[1]), width: Number(match[2]) }));
}

async function testMonthlyControls(payload, type, player, year) {
  const page = loadPage(payload, `?${new URLSearchParams({ type, player, year, team: "オリックス", mode: "monthly" })}`);
  await page.api.init();
  const { api, element, buttons } = page;
  const defaults = Array.from(api.state.config.metrics.filter((metric) => metric.default), (metric) => metric.key);
  const allKeys = Array.from(api.state.config.metrics, (metric) => metric.key);
  assert.equal(api.state.currentRow.year, year, "monthly entry retains the requested season");
  assert.equal(api.state.monthlyView, "line", "monthly results open with line charts");
  assert.equal(api.state.monthlyPreset, "main");
  assert.deepEqual(Array.from(api.state.activeMetricKeys), defaults);
  assert.equal(buttons.monthlyView[1].getAttribute("aria-pressed"), "true");
  assert.equal(buttons.monthlyPreset[0].getAttribute("aria-pressed"), "true");
  assert.equal(element("monthlyTableWrap").classList.contains("is-hidden"), true);
  assert.equal(element("monthlyChartGrid").classList.contains("is-hidden"), false);
  assert.equal((element("monthlyChartGrid").innerHTML.match(/<article class="[^"]*\bmonthly-chart-card\b[^"]*"/g) || []).length, defaults.length);

  const splitsBefore = JSON.stringify(api.monthlySplits());
  const comparisonKeysBefore = Array.from(api.comparisonMetricKeys());
  const comparisonYearBefore = api.state.comparisonYear;
  buttons.monthlyPreset[1].click();
  assert.equal(api.state.monthlyPreset, "all");
  assert.deepEqual(Array.from(api.state.activeMetricKeys), allKeys);
  assert.deepEqual(Array.from(api.comparisonMetricKeys()), comparisonKeysBefore, "monthly presets do not replace comparison metrics");
  assert.equal(api.state.comparisonYear, comparisonYearBefore);
  assert.equal(buttons.monthlyPreset[1].getAttribute("aria-pressed"), "true");
  buttons.monthlyView[0].click();
  assert.equal(api.state.monthlyView, "table");
  assert.equal(element("monthlyTableWrap").classList.contains("is-hidden"), false);
  assert.equal(element("monthlyChartGrid").classList.contains("is-hidden"), true);
  assert.deepEqual(Array.from(api.state.activeMetricKeys), allKeys, "view changes retain the selected monthly metrics");
  const table = element("monthlyTableWrap").innerHTML;
  assert.ok(/<caption[^>]*>[\s\S]*?<\/caption>/.test(table) && table.includes(year), "the monthly table identifies its season");
  assert.equal(bodyRows(table).length, allKeys.length, "table metrics use rows rather than expanding into dozens of columns");
  for (const metric of api.state.config.metrics) {
    assert.equal(tableRow(table, metric.label).length, api.monthlySplits().length, "each metric has one value per source month");
  }
  if (year === "2025") {
    assert.ok(table.includes("3・4月"), "the source's combined March/April category remains combined");
    assert.ok(!table.includes(">3月</th>") && !table.includes(">4月</th>"));
    if (type === "pitcher") {
      assert.ok(tableRow(table, "球数").every((value) => value === "—"), "unrecorded 2025 pitch counts never become measured zeroes");
    } else {
      assert.ok(tableRow(table, "wRC+").every((value) => value === "—"), "unrecorded historical coefficients remain unavailable");
    }
  }
  buttons.monthlyPreset[0].click();
  assert.deepEqual(Array.from(api.state.activeMetricKeys), defaults);
  assert.equal(bodyRows(element("monthlyTableWrap").innerHTML).length, defaults.length);
  const extra = api.state.config.metrics.find((metric) => !metric.default);
  element("metricToggleGroup").querySelectorAll("[data-metric-key]")
    .find((button) => button.dataset.metricKey === extra.key).click();
  assert.equal(api.state.monthlyPreset, "custom");
  assert.ok(Array.from(api.state.activeMetricKeys).includes(extra.key));
  assert.deepEqual(Array.from(api.comparisonMetricKeys()), comparisonKeysBefore, "custom monthly metrics leave comparison selection unchanged");
  assert.ok(buttons.monthlyPreset.every((button) => button.getAttribute("aria-pressed") === "false"));

  const monthlySelection = Array.from(api.state.activeMetricKeys);
  buttons.preset[1].click();
  assert.deepEqual(Array.from(api.state.activeMetricKeys), monthlySelection, "comparison presets leave monthly metrics unchanged");
  assert.equal(api.state.monthlyPreset, "custom");
  buttons.monthlyView[1].click();
  assert.equal(api.state.monthlyView, "line");
  assert.deepEqual(Array.from(api.state.activeMetricKeys), monthlySelection);
  assert.equal(JSON.stringify(api.monthlySplits()), splitsBefore, "neither controls nor comparison year selection change monthly data");
  assert.equal(api.state.currentRow.year, year);

  const selectedButtons = element("metricToggleGroup").querySelectorAll("[data-metric-key]")
    .filter((button) => api.state.activeMetricKeys.includes(button.dataset.metricKey));
  selectedButtons.forEach((button) => button.click());
  assert.equal(api.state.activeMetricKeys.length, 0);
  assert.ok(element("monthlyTableWrap").innerHTML.includes("指標を選択"));
  assert.ok(element("monthlyChartGrid").innerHTML.includes("指標を選択"));
  assert.ok(!element("monthlyTableWrap").innerHTML.includes("<table"), "an empty metric selection never falls back to all metrics");
  buttons.monthlyPreset[0].click();
  assert.deepEqual(Array.from(api.state.activeMetricKeys), defaults, "the main preset recovers an empty selection");
  api.state.currentRow = { ...api.state.currentRow, monthlySplits: [] };
  api.renderMonthlyPanel();
  assert.ok(element("monthlyTableWrap").innerHTML.includes("月別データはありません"));
  assert.ok(element("monthlyChartGrid").innerHTML.includes("月別データはありません"));
  return page;
}

function testMonthlyMissingValues(page, type) {
  const { api, element } = page;
  const splits = type === "pitcher" ? [
    { monthLabel: "3月", era: 0, inningsOuts: 1, strikeouts: 0, fip: null },
    { monthLabel: "4月", era: null, inningsOuts: null, strikeouts: null, fip: null },
    { monthLabel: "5月", era: 2.5, inningsOuts: 3, strikeouts: 2, fip: null },
  ] : [
    { monthLabel: "3月", atBats: 10, ops: 0, homeRuns: 0, wrcPlus: null },
    { monthLabel: "4月", atBats: 0, ops: 0, homeRuns: null, wrcPlus: null },
    { monthLabel: "5月", atBats: 10, ops: .85, homeRuns: 2, wrcPlus: null },
  ];
  api.state.activeMetricKeys = type === "pitcher" ? ["era", "inningsOuts", "strikeouts", "fip"] : ["ops", "homeRuns", "wrcPlus"];
  api.renderMonthlyTable(splits);
  const table = element("monthlyTableWrap").innerHTML;
  if (type === "pitcher") {
    assert.deepEqual(tableRow(table, "防御率"), ["0.00", "—", "2.50"]);
    assert.deepEqual(tableRow(table, "投球回"), ["0.1", "—", "1"]);
    assert.deepEqual(tableRow(table, "奪三振"), ["0", "—", "2"]);
    assert.deepEqual(tableRow(table, "FIP"), ["—", "—", "—"]);
  } else {
    assert.deepEqual(tableRow(table, "OPS"), ["0.000", "—", "0.850"], "a no-at-bat month is undefined while a measured zero remains zero");
    assert.deepEqual(tableRow(table, "本塁打"), ["0", "—", "2"]);
    assert.deepEqual(tableRow(table, "wRC+"), ["—", "—", "—"]);
  }
  api.renderMonthlyCharts(splits);
  const charts = element("monthlyChartGrid").innerHTML;
  assert.ok(charts.includes("データなし"), "entirely unavailable metrics explain the missing series");
  assert.ok(!/NaN|Infinity|undefined/.test(charts));
}

async function main() {
  const pitcherData = JSON.parse(fs.readFileSync(path.join(root, "summary/player_totals.json"), "utf8"));
  const page = loadPage(pitcherData, "?type=pitcher&year=2025&player=宮城大弥&team=オリックス&mode=compare");
  await page.api.init();
  const { api, element, buttons } = page;
  assert.equal(api.state.currentRow.year, "2025", "opening a historical season retains its annual and monthly context");
  assert.equal(api.state.comparisonYear, "2026", "historical entry opens an available 2025/2026 pair");
  assert.deepEqual(Array.from(api.availableComparisonYears()), ["2026", "2025"]);
  const pair = api.comparisonPair();
  assert.equal(pair.previous.year, "2025");
  assert.equal(pair.current.year, "2026");
  assert.equal(pair.previous.player, "宮城 大弥");
  assert.equal(pair.current.player, "宮城 大弥");
  assert.ok(element("comparisonYearSelect").innerHTML.includes('value="2026" selected'));

  let markup = element("compareCardGrid").innerHTML;
  assert.ok(markup.includes("2025年") && markup.includes("2026年") && markup.includes("前年差"));
  assert.equal(bodyRows(markup).length, api.TYPE_CONFIG.pitcher.metrics.filter((metric) => metric.default).length);
  const gamesDelta = pair.current.games - pair.previous.games;
  assert.deepEqual(tableRow(markup, "試合"), [`${pair.previous.games}`, `${pair.current.games}`, `${gamesDelta > 0 ? "+" : ""}${gamesDelta}`]);
  assert.deepEqual(tableRow(markup, "防御率").slice(0, 2), [pair.previous.era.toFixed(2), pair.current.era.toFixed(2)]);
  const outsDelta = pair.current.inningsOuts - pair.previous.inningsOuts;
  const signedInnings = `${outsDelta < 0 ? "-" : outsDelta > 0 ? "+" : ""}${api.formatInningsFromOuts(Math.abs(outsDelta))}`;
  assert.deepEqual(tableRow(markup, "投球回"), [api.formatInningsFromOuts(pair.previous.inningsOuts), api.formatInningsFromOuts(pair.current.inningsOuts), signedInnings]);
  assert.equal(api.formatMetricDelta({ kind: "innings" }, 2), "+0.2");
  assert.equal(api.formatMetricDelta({ kind: "innings" }, -4), "-1.1");
  assert.equal(api.formatMetricDelta({ kind: "percent", digits: 1 }, 10.25), "+10.3pt");
  assert.equal(api.formatMetricDelta({ kind: "decimal", digits: 2 }, -0.00001), "0.00", "rounding never displays negative zero");

  api.state.activeMetricKeys = ["era", "whip"];
  const historicalMonths = JSON.stringify(api.monthlySplits());
  buttons.preset.find((button) => button.dataset.comparePreset === "all").click();
  assert.equal(api.state.comparisonPreset, "all");
  assert.equal(bodyRows(element("compareCardGrid").innerHTML).length, api.TYPE_CONFIG.pitcher.metrics.length);
  assert.deepEqual(Array.from(api.state.activeMetricKeys), ["era", "whip"], "comparison presets do not replace selected monthly charts");
  assert.equal(buttons.preset[1].getAttribute("aria-pressed"), "true");
  buttons.preset.find((button) => button.dataset.comparePreset === "main").click();
  assert.equal(api.state.comparisonPreset, "main");
  assert.equal(bodyRows(element("compareCardGrid").innerHTML).length, api.TYPE_CONFIG.pitcher.metrics.filter((metric) => metric.default).length);
  assert.equal(buttons.preset[0].getAttribute("aria-pressed"), "true");

  const selectedMetricsBefore = Array.from(api.state.activeMetricKeys);
  const customButton = element("metricToggleGroup").querySelectorAll("[data-metric-key]").find((button) => button.dataset.metricKey === "wins");
  customButton.click();
  assert.equal(api.state.comparisonPreset, "custom");
  assert.ok(Array.from(api.comparisonMetricKeys()).includes("wins"));
  assert.deepEqual(Array.from(api.state.activeMetricKeys), selectedMetricsBefore);
  element("comparisonYearSelect").change("2025");
  assert.equal(api.comparisonPair().current.year, "2025");
  assert.equal(api.comparisonPair().previous, null, "the 2024 gap remains a missing season");
  assert.equal(api.state.currentRow.year, "2025");
  assert.equal(JSON.stringify(api.monthlySplits()), historicalMonths, "comparison year changes never change selected annual/monthly data");
  element("comparisonYearSelect").change("2026");
  buttons.view.find((button) => button.dataset.compareView === "bars").click();
  assert.equal(api.state.comparisonView, "bars");
  assert.ok(element("compareCardGrid").innerHTML.includes("comparison-bars"));
  buttons.view.find((button) => button.dataset.compareView === "table").click();
  assert.ok(element("compareCardGrid").innerHTML.includes("comparison-table"));

  const metric = { key: "fip", label: "FIP", kind: "decimal", digits: 2 };
  const signedBars = api.comparisonBarMarkup(metric, { year: "2025", fip: -2 }, { year: "2026", fip: 6 });
  const [negative, positive] = barPositions(signedBars);
  assert.deepEqual(negative, { left: 0, width: 25 });
  assert.deepEqual(positive, { left: 25, width: 75 });
  assert.equal(negative.left + negative.width, positive.left, "signed bars meet at the same zero baseline");
  const [smaller, larger] = barPositions(api.comparisonBarMarkup(metric, { year: "2025", fip: 2 }, { year: "2026", fip: 4 }));
  assert.deepEqual(smaller, { left: 0, width: 50 });
  assert.deepEqual(larger, { left: 0, width: 100 });
  const missingBar = api.comparisonBarMarkup(metric, { year: "2025", fip: null }, { year: "2026", fip: 4 });
  assert.equal(barPositions(missingBar)[0].width, 0);
  assert.ok(missingBar.includes("<strong>—</strong>"));
  assert.ok(!missingBar.includes("NaN") && !missingBar.includes("Infinity"));
  const zeroBars = api.comparisonBarMarkup(metric, { year: "2025", fip: 0 }, { year: "2026", fip: 0 });
  assert.ok(barPositions(zeroBars).every((position) => position.width === 0));

  const batterData = JSON.parse(fs.readFileSync(path.join(root, "summary/batter_totals.json"), "utf8"));
  const batter = loadPage(batterData, "?type=batter&year=2025&player=若月健矢&team=オリックス&mode=compare");
  await batter.api.init();
  batter.buttons.preset.find((button) => button.dataset.comparePreset === "all").click();
  const batterMarkup = batter.element("compareCardGrid").innerHTML;
  const batterPair = batter.api.comparisonPair();
  assert.equal(batterPair.current.year, "2026");
  assert.deepEqual(tableRow(batterMarkup, "wRC+"), ["—", batterPair.current.wrcPlus.toFixed(1), "—"]);
  assert.deepEqual(tableRow(batterMarkup, "ボールゾーンスイング率"), ["—", `${batterPair.current.ballZoneSwingRate.toFixed(1)}%`, "—"]);
  assert.deepEqual(tableRow(batterMarkup, "OPS").slice(0, 2), [batterPair.previous.ops.toFixed(3), batterPair.current.ops.toFixed(3)]);
  for (const key of ["ops", "isoDiscipline", "isoPower"]) {
    const config = batter.api.TYPE_CONFIG.batter.metrics.find((item) => item.key === key);
    assert.equal(batter.api.metricValue(config, { atBats: 0, [key]: 0 }), null, `${key} has no value with zero at-bats`);
    assert.equal(batter.api.comparisonValue(config, { atBats: 0, [key]: 1 }), "—");
    assert.ok(batter.api.differenceMarkup(config, { atBats: 0, [key]: 0 }, { atBats: 10, [key]: .3 }).includes(">—</span>"));
    assert.equal(batter.api.comparisonValue(config, { atBats: 10, [key]: 0 }), "0.000", "a genuine measured zero remains zero");
  }

  const hostileMetric = { ...metric, label: '<img src=x onerror="bad"> &' };
  const hostile = api.comparisonBarMarkup(hostileMetric, { year: '<script>bad()</script>', fip: -1 }, { year: "2026", fip: 2 });
  assert.ok(!hostile.includes("<img") && !hostile.includes("<script>"));
  assert.ok(hostile.includes("&lt;img") && hostile.includes("&lt;script&gt;") && hostile.includes("&amp;"));
  const season = api.comparisonSeasonMarkup({ team: '<img src=x> &', games: 3, inningsOuts: 40 }, '<script>');
  assert.ok(!season.includes("<img") && !season.includes("<script>"));

  const monthlyPitcher = await testMonthlyControls(pitcherData, "pitcher", "宮城大弥", "2025");
  const monthlyBatter = await testMonthlyControls(batterData, "batter", "若月健矢", "2025");
  await testMonthlyControls(pitcherData, "pitcher", "宮城大弥", "2026");
  await testMonthlyControls(batterData, "batter", "若月健矢", "2026");
  testMonthlyMissingValues(monthlyPitcher, "pitcher");
  testMonthlyMissingValues(monthlyBatter, "batter");

  console.log("PASS: real 2025 entries open 2025/2026 pairs; table/bar controls, arithmetic, missing values, units, baselines and escaping");
  console.log("PASS: comparison years, presets and custom metrics preserve annual/monthly season and selected charts");
  console.log("PASS: monthly line/table controls, independent presets and custom metrics, source grouping, units, zero/null and empty states for 2025/2026 pitchers and batters");
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
