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
  "monthlySplits", "comparisonSeasonMarkup",
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

  console.log("PASS: real 2025 entries open 2025/2026 pairs; table/bar controls, arithmetic, missing values, units, baselines and escaping");
  console.log("PASS: comparison years, presets and custom metrics preserve annual/monthly season and selected charts");
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
