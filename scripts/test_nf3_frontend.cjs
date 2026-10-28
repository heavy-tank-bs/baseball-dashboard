"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function loadPage(file, exports) {
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      innerHTML: "", textContent: "", classList: { toggle() {} },
      querySelectorAll() { return []; }, querySelector() { return null; },
      addEventListener() {},
    });
    return elements.get(id);
  }
  const fetchCalls = [];
  const context = vm.createContext({
    URLSearchParams,
    document: { getElementById: element, querySelectorAll() { return []; } },
    window: { location: { search: "" }, addEventListener() {}, scrollTo() {}, scrollX: 0, scrollY: 0 },
    requestAnimationFrame(callback) { callback(); },
    fetch: async (url) => {
      fetchCalls.push(url);
      return { ok: true, json: async () => ({ players: [] }) };
    },
  });
  const source = fs.readFileSync(path.join(__dirname, "..", "summary", file), "utf8")
    .replace(/\ninit\(\);\s*$/, "");
  vm.runInContext(`${source}\nglobalThis.api = {${exports.join(",")}};`, context, { filename: file });
  return { api: context.api, element, fetchCalls };
}

async function main() {
  const { api, element, fetchCalls } = loadPage("compare.js", [
    "state", "TYPE_CONFIG", "findHistoricalPlayer", "renderHistoricalTable", "sourceLink",
    "renderSeasonPanel", "renderComparePanel", "ensureHistoricalData", "aggregateBatterBucket", "aggregatePitcherBucket", "monthlySplits",
  ]);
  const sameNamePlayers = [
    { team: "オリックス", player: "山田 太郎", sourceUrl: "https://nf3.sakura.ne.jp/2025/player" },
    { team: "阪神", player: "山田太郎" },
  ];
  assert.equal(api.findHistoricalPlayer(sameNamePlayers, { year: "2025", team: "オリックス", player: "山田　太郎" }), sameNamePlayers[0]);
  assert.equal(api.findHistoricalPlayer(sameNamePlayers, { year: "2025", team: "巨人", player: "山田太郎" }), null);
  assert.equal(api.findHistoricalPlayer(sameNamePlayers, { year: "2026", team: "オリックス", player: "山田太郎" }), null);
  const rakuten = { team: "東北楽天", player: "Ｒ．選手" };
  assert.equal(api.findHistoricalPlayer([rakuten], { year: "2025", team: "楽天", player: "R. 選手" }), rakuten);
  assert.equal(api.findHistoricalPlayer(sameNamePlayers, { year: "2025", team: "中日", sourceTeams: ["阪神", "オリックス"], player: "山田太郎" }), null);

  const table = { title: "月別成績 <test>", headers: ["月", "打率", "OPS"], rows: [["4月", ".300"], ["5月", "<img>", "&"]] };
  const markup = api.renderHistoricalTable(table);
  assert.ok(markup.includes("月別成績 &lt;test&gt;"));
  assert.ok(markup.includes("&lt;img&gt;") && markup.includes("&amp;"));
  assert.ok(markup.includes('<th scope="row">4月</th><td>.300</td><td>-</td>'));
  assert.ok(!api.sourceLink("javascript:alert(1)", "source").includes("href="));

  api.state.config = api.TYPE_CONFIG.batter;
  api.state.currentRow = { year: "2025", team: "オリックス", player: "山田太郎", games: 80, plateAppearances: 300, atBats: 260, hits: 78, battingAverage: .3, ops: .8, wrc: null, wrcPlus: null };
  api.state.historical.loaded = true;
  api.state.historical.payload = { players: [{ ...sameNamePlayers[0], tables: [table] }] };
  api.renderSeasonPanel();
  assert.ok(element("seasonDetailWrap").innerHTML.includes("2025年度の基本成績"));
  assert.ok(element("seasonDetailWrap").innerHTML.includes("年度係数未収録のため未算出"));
  assert.ok(element("seasonDetailWrap").innerHTML.includes("historicalTableSelect"));
  assert.ok(element("seasonDetailWrap").innerHTML.includes("月別成績 &lt;test&gt;"));
  assert.equal(fetchCalls.length, 0);

  const monthly = api.aggregateBatterBucket([{ ...api.state.currentRow, month: "2025-04", wrc: null, wrcPlus: null }], { key: "04", label: "4月" });
  assert.equal(monthly.wrc, null);
  assert.equal(monthly.wrcPlus, null);
  api.state.currentRow.monthlySplits = [
    { ...api.state.currentRow, month: "2025-03/04", label: "3・4月", sourceGrouping: "3・4月" },
    { ...api.state.currentRow, month: "2025-05", monthLabel: "5月" },
  ];
  const groupedMonths = api.monthlySplits();
  assert.equal(groupedMonths[0].monthLabel, "3・4月", "combined source months must not be relabeled as April");
  assert.equal(groupedMonths[1].monthLabel, "5月");
  const unknownPitcherMonth = api.aggregatePitcherBucket([{ month: "2025-05", inningsOuts: 60, hits: 20, homeRuns: 1, strikeouts: 30, walks: 5, earnedRuns: 8, fipConstant: null }], { key: "05", label: "5月" });
  assert.equal(unknownPitcherMonth.battingAverageAllowed, null);
  assert.equal(unknownPitcherMonth.babipAllowed, null, "missing AB/SF must not manufacture a negative BABIP");
  assert.equal(unknownPitcherMonth.fip, null);
  assert.equal(unknownPitcherMonth.unintentionalWalks, null);

  api.state.previousRow = api.state.currentRow;
  api.state.currentRow = { ...api.state.currentRow, year: "2026" };
  api.state.activeMetricKeys = ["wrcPlus", "ops"];
  api.renderComparePanel();
  assert.ok(element("historicalCompareNote").innerHTML.includes("2025年の基本成績・条件別成績を見る"));
  assert.ok(element("historicalCompareNote").innerHTML.includes("year=2025"));
  assert.ok(element("compareCardGrid").innerHTML.includes(">-</strong>"));

  api.state.historical.loaded = false;
  api.state.historical.loading = false;
  await api.ensureHistoricalData();
  assert.equal(fetchCalls.length, 0, "2026 views must not fetch historical source tables");
  api.state.currentRow = { ...api.state.currentRow, year: "2025" };
  const firstRequest = api.ensureHistoricalData();
  await api.ensureHistoricalData();
  await firstRequest;
  assert.equal(fetchCalls.length, 1, "concurrent renders share a single source request");
  assert.ok(fetchCalls[0].includes("nf3_2025_batters.json"));

  const annual = loadPage("annual.js", ["state", "renderTable", "renderNote"]);
  const pitcher = { year: "2025", team: "オリックス", player: "投手A", games: 2, innings: "2", inningsOuts: 6, hasPitchCount: true, pitches: 30 };
  annual.api.state.year = "2025";
  annual.api.state.data = { players: [pitcher, { ...pitcher, player: "投手B", hasPitchCount: false, pitches: null }] };
  annual.api.renderTable();
  const annualMarkup = annual.element("annualTableWrap").innerHTML;
  const bodyRows = annualMarkup.match(/<tbody>([\s\S]*)<\/tbody>/)[1].match(/<tr>([\s\S]*?)<\/tr>/g);
  const columnCounts = bodyRows.map((row) => (row.match(/<td>/g) || []).length);
  assert.equal(columnCounts[0], columnCounts[1], "mixed pitch count coverage must preserve table columns");
  annual.api.renderNote();
  assert.ok(annual.element("annualNote").innerHTML.includes("nf3"));
  annual.api.state.year = "2026";
  annual.api.renderNote();
  assert.equal(annual.element("annualNote").innerHTML, "");
  for (const [kind, totalsFile] of [["pitchers", "player_totals.json"], ["batters", "batter_totals.json"]]) {
    const sourcePath = path.join(__dirname, "..", "summary", `nf3_2025_${kind}.json`);
    if (!fs.existsSync(sourcePath)) continue;
    const profiles = JSON.parse(fs.readFileSync(sourcePath, "utf8")).players;
    const totals = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "summary", totalsFile), "utf8")).players;
    const historicalRows = totals.filter((row) => row.year === "2025");
    for (const row of historicalRows) {
      assert.ok(api.findHistoricalPlayer(profiles, row), `missing frontend source match: ${kind} ${row.team} ${row.player}`);
    }
    if (kind === "pitchers") {
      for (const profile of profiles) {
        for (const month of profile.annual.monthlySplits || []) {
          const result = api.aggregatePitcherBucket([{ ...month, fipConstant: null }], { key: month.month, label: month.month });
          assert.equal(result.babipAllowed, null, `unknown monthly AB: ${profile.nf3Id}`);
          assert.equal(result.fip, null, `unknown monthly IBB: ${profile.nf3Id}`);
        }
      }
    }
    console.log(`PASS: all ${historicalRows.length} ${kind} match source; available monthly inputs remain truthful`);
  }
  console.log("PASS: nf3 matching, table escaping, 2025 summary, null metrics, lazy loading and mixed coverage columns");
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
