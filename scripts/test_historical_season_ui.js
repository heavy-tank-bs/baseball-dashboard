"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const root = path.resolve(__dirname, "..");
const elements = new Map();
const element = (id) => {
  if (!elements.has(id)) elements.set(id, { innerHTML: "", textContent: "", classList: { toggle() {} }, addEventListener() {}, querySelectorAll() { return []; }, querySelector() { return null; } });
  return elements.get(id);
};
const context = vm.createContext({
  URLSearchParams,
  document: { getElementById: element, querySelectorAll() { return []; } },
  window: { location: { search: "" }, addEventListener() {}, scrollTo() {} },
  requestAnimationFrame(callback) { callback(); },
  fetch() { throw new Error("rendering saved annual data must not request the network"); },
});
for (const file of ["historical-pitcher.js", "historical-batter.js"]) vm.runInContext(fs.readFileSync(path.join(root, "summary", file), "utf8"), context, { filename: file });
const source = fs.readFileSync(path.join(root, "summary/compare.js"), "utf8").replace(/\ninit\(\);\s*$/, "");
vm.runInContext(`${source}\nglobalThis.api = { state, TYPE_CONFIG, seasonDashboard, renderSeasonPanel, renderPitcherSeasonPanel, renderBatterSeasonPanel, renderSeasonInningSummary, renderPitcherDecisionInningTable, rowHits };`, context);
const api = context.api;
const read = (file) => JSON.parse(fs.readFileSync(path.join(root, "summary", file), "utf8"));
const annualRow = (profile) => ({ year: "2025", player: profile.player, team: profile.team, teams: [profile.team], ...profile.annual });
const text = (html) => html.replace(/<[^>]*>/g, "").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").trim();

function table(markup, className, transposed = false) {
  const selector = transposed ? `data-stat-help-scope="${className}"` : `class="[^\"]*${className}[^\"]*"`;
  const match = markup.match(new RegExp(`<table[^>]*${selector}[^>]*>([\\s\\S]*?)<\\/table>`));
  assert.ok(match, `missing shared table: ${className}`);
  const headers = [...match[1].match(/<thead>([\s\S]*?)<\/thead>/)[1].matchAll(/<th\b[^>]*>([\s\S]*?)<\/th>/g)].map((cell) => text(cell[1]));
  const rows = [...match[1].match(/<tbody>([\s\S]*?)<\/tbody>/)[1].matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/g)]
    .map((row) => [...row[1].matchAll(/<t[hd]\b[^>]*>([\s\S]*?)<\/t[hd]>/g)].map((cell) => text(cell[1])));
  return { headers, rows };
}
function cell(data, rowLabel, header) {
  const row = data.rows.find((row) => row[0] === rowLabel);
  assert.ok(row, `missing table row: ${rowLabel}`);
  const index = data.headers.indexOf(header);
  assert.ok(index >= 0, `missing table column: ${header}`);
  return row[index];
}
function assertTransposedTable(markup, className, mobileFirstHeader) {
  const desktop = table(markup, className);
  const mobile = table(markup, className, true);
  assert.deepEqual(mobile.headers, [mobileFirstHeader, ...desktop.rows.map((row) => row[0])]);
  assert.deepEqual(mobile.rows.map((row) => row[0]), desktop.headers.slice(1));
  for (const row of desktop.rows) {
    for (const header of desktop.headers.slice(1)) {
      assert.equal(cell(mobile, header, row[0]), cell(desktop, row[0], header), `${className}: ${row[0]} / ${header} survives transposition`);
    }
  }
  return { desktop, mobile };
}
function assertTruthfulMarkup(markup, label) {
  assert.doesNotMatch(markup, /NaN|undefined|\bInfinity\b/, `${label}: no invalid numeric output`);
  assert.doesNotMatch(markup, /historicalTableSelect|historical-stat-grid/, `${label}: no legacy picker or duplicate stat cards`);
  assert.doesNotMatch(text(markup), /nf3/i, `${label}: no visible source branding`);
  assert.doesNotMatch(markup, /href=["'][^"']*nf3\.sakura\.ne\.jp/i, `${label}: no source branding links`);
  assert.match(markup, /season-detail-grid/, `${label}: shared dashboard layout`);
}

const archives = { pitcher: read("nf3_2025_pitchers.json"), batter: read("nf3_2025_batters.json") };
const totals = { pitcher: read("player_totals.json"), batter: read("batter_totals.json") };
let renderedProfiles = 0;
for (const [type, archive] of Object.entries(archives)) {
  api.state.config = api.TYPE_CONFIG[type];
  api.state.historical.loaded = true;
  api.state.historical.loading = false;
  api.state.historical.error = "";
  api.state.historical.payload = archive;
  for (const profile of archive.players) {
    api.state.currentRow = annualRow(profile);
    api.renderSeasonPanel();
    const markup = element("seasonDetailWrap").innerHTML;
    assertTruthfulMarkup(markup, `${type} ${profile.nf3Id}`);
    assert.doesNotMatch(markup, /<h3>最近6試合の成績<\/h3>/, "unavailable game logs are not rendered as an empty historical card");
    renderedProfiles += 1;
  }
  // Existing 2026 dashboards pass straight through the same renderer, even
  // while the historical archive is unavailable or has a prior loading error.
  const current = totals[type].players.find((row) => row.year === "2026" && row.seasonDashboard && (type === "pitcher" ? row.pitches > 0 : row.plateAppearances > 0));
  assert.ok(current);
  const before = JSON.stringify(current);
  api.state.currentRow = current;
  api.state.historical.loaded = false;
  api.state.historical.error = "unavailable archive";
  assert.equal(api.seasonDashboard(), current.seasonDashboard, "2026 uses its native dashboard object");
  api.renderSeasonPanel();
  const native = type === "pitcher" ? api.renderPitcherSeasonPanel(current.seasonDashboard) : api.renderBatterSeasonPanel(current.seasonDashboard);
  assert.equal(element("seasonDetailWrap").innerHTML, native, "2026 remains on the existing shared rendering route");
  assert.equal(JSON.stringify(current), before, "rendering must not mutate 2026 data");
  assert.doesNotMatch(native, /2025年は|2025年の年度集計|season-additional-tables/);
}
assert.equal(renderedProfiles, 361 + 725);

// Verify values against specific source records, including their absent fields.
const miyagi = archives.pitcher.players.find((profile) => profile.nf3Id === "B:18");
api.state.config = api.TYPE_CONFIG.pitcher;
api.state.currentRow = annualRow(miyagi);
api.state.historical = { loaded: true, loading: false, error: "", payload: archives.pitcher };
api.renderSeasonPanel();
const pitcherMarkup = element("seasonDetailWrap").innerHTML;
const pitch = table(pitcherMarkup, "season-pitch-summary-table");
assert.equal(cell(pitch, "ストレート", "球数"), "1094");
assert.equal(cell(pitch, "ストレート", "被安打"), "61");
assert.equal(cell(pitch, "ストレート", "被本"), "2");
assert.equal(cell(pitch, "ストレート", "空振率"), "4.8%");
for (const header of ["最速", "ゴロ", "フライ"]) assert.equal(cell(pitch, "ストレート", header), "-");
const discipline = table(pitcherMarkup, "season-pitch-metric-summary-table");
assert.equal(cell(discipline, "ストレート", "whiff%"), "11.0%");
assert.equal(cell(discipline, "ストレート", "csw%"), "33.0%");
for (const header of ["zone%", "z-swing%", "o-contact%", "chase%", "chase+"]) assert.equal(cell(discipline, "ストレート", header), "-");
const hand = table(pitcherMarkup, "season-pitch-hand-summary-table");
assert.equal(cell(hand, "対右打者", "被安打"), "87");
assert.equal(cell(hand, "対右打者", "被打数"), "358");
for (const header of ["空振", "空振率", "ゴロ", "フライ"]) assert.equal(cell(hand, "対右打者", header), "-");
assert.match(pitcherMarkup, /先発時のイニング別失点数/);
assert.doesNotMatch(pitcherMarkup, /降板後の失点を含む/);
assertTransposedTable(pitcherMarkup, "pitcher-decision-inning-table", "イニング");
assert.doesNotMatch(pitcherMarkup, /<h3>イニング別四死球数/);
assert.equal(api.rowHits({ hits: 0, homeRuns: 0 }), 0);
assert.equal(api.rowHits({ homeRuns: 2 }), null, "unknown non-HR hits must not be silently counted as zero");
assert.equal(api.rowHits({ singles: 3, doubles: 2, triples: 1, homeRuns: 0 }), 6);

const ota = archives.batter.players.find((profile) => profile.player === "太田椋" && profile.team === "オリックス");
assert.ok(ota);
api.state.config = api.TYPE_CONFIG.batter;
api.state.currentRow = annualRow(ota);
api.state.historical.payload = archives.batter;
api.renderSeasonPanel();
const batterMarkup = element("seasonDetailWrap").innerHTML;
const battingPitch = table(batterMarkup, "batter-season-table--pitch-type");
assert.equal(cell(battingPitch, "ストレート", "打席"), "-");
assert.equal(cell(battingPitch, "ストレート", "打数"), "192");
assert.equal(cell(battingPitch, "ストレート", "安打"), "67");
assert.equal(cell(battingPitch, "ストレート", "本塁打"), "6");
for (const header of ["二塁打", "三塁打", "犠打", "犠飛", "長打率", "OPS"]) assert.equal(cell(battingPitch, "ストレート", header), "-");
assert.equal(cell(battingPitch, "ストレート", "球数"), "835");
const battingAppearance = table(batterMarkup, "batter-season-table--plate-appearance");
assert.equal(cell(battingAppearance, "1打席目", "打数"), "103");
assert.equal(cell(battingAppearance, "1打席目", "四死球"), "6");
assert.equal(cell(battingAppearance, "1打席目", "四球"), "-");
assert.equal(cell(battingAppearance, "1打席目", "死球"), "-");
assert.match(batterMarkup, /打順別打撃成績（先発時）/);
assert.match(batterMarkup, /打席別打撃成績（先発時）/);

// Known zeroes must be visible; an unavailable section or unknown inning must
// never acquire invented zeroes through Number(null) coercion.
const zeros = Array.from({ length: 12 }, (_, index) => ({ inning: index + 1, total: 0, win: 0, loss: 0, noDecision: 0 }));
for (const title of ["イニング別失点数", "イニング別四死球数"]) {
  const verified = api.renderPitcherDecisionInningTable(title, zeros, true);
  assert.match(verified, /pitcher-decision-inning-table/);
  assert.doesNotMatch(verified, /データなし|未収録/);
  const { desktop, mobile } = assertTransposedTable(verified, "pitcher-decision-inning-table", "イニング");
  assert.equal(desktop.rows.length, 4);
  assert.equal(mobile.rows.length, 13);
  assert.equal((verified.match(/<td\b[^>]*>0<\/td>/g) || []).length, 104, "desktop and mobile each retain twelve innings and total for four verified conditions");
  const unavailable = api.renderPitcherDecisionInningTable(title, zeros, false);
  assert.match(unavailable, /未収録/);
  assert.doesNotMatch(unavailable, /pitcher-decision-inning-table/);
  const partial = zeros.map((row) => ({ ...row }));
  partial[3].total = null;
  const unknown = api.renderPitcherDecisionInningTable(title, partial, true);
  const unknownTables = assertTransposedTable(unknown, "pitcher-decision-inning-table", "イニング");
  assert.equal(cell(unknownTables.desktop, "合計", "4回"), "-");
  assert.equal(cell(unknownTables.mobile, "4回", "合計"), "-");
  assert.equal(cell(unknownTables.desktop, "合計", "合計"), "-", "an unknown inning also makes the condition total unknown");
  assert.equal(cell(unknownTables.mobile, "合計", "合計"), "-");
}

// Exercise populated native records as well as 2025 starter-only coverage.
// Every inning and decision subtotal must occupy the same logical cell on
// desktop and mobile, and their final total must match the annual record.
for (const [key, title, annualTotal] of [
  ["inningRunRows", "イニング別失点数", (row) => row.runs],
  ["inningWalkRows", "イニング別四死球数", (row) => row.walks + row.hitByPitch],
]) {
  const player = totals.pitcher.players.find((row) => row.year === "2026" && row.seasonDashboard?.[key]?.some((inning) => inning.win > 0 && inning.loss > 0 && inning.noDecision > 0));
  assert.ok(player, `${key}: saved native record with all three decisions`);
  const rows = player.seasonDashboard[key];
  const markup = api.renderPitcherDecisionInningTable(title, rows, true);
  const { desktop, mobile } = assertTransposedTable(markup, "pitcher-decision-inning-table", "イニング");
  assert.deepEqual(desktop.headers, ["条件", ...Array.from({ length: 12 }, (_, index) => `${index + 1}回`), "合計"]);
  assert.deepEqual(mobile.headers, ["イニング", "合計", "勝利", "敗戦", "勝敗無"]);
  for (const [condition, label] of [["total", "合計"], ["win", "勝利"], ["loss", "敗戦"], ["noDecision", "勝敗無"]]) {
    const expectedTotal = rows.reduce((sum, row) => sum + row[condition], 0);
    for (const row of rows) assert.equal(cell(mobile, `${row.inning}回`, label), `${row[condition]}`);
    assert.equal(cell(mobile, "合計", label), `${expectedTotal}`);
  }
  assert.equal(cell(mobile, "合計", "合計"), `${annualTotal(player)}`);
}
const nativeInnings = totals.pitcher.players.find((row) => row.year === "2026" && row.seasonDashboard?.inningRows?.length > 1).seasonDashboard;
assertTransposedTable(api.renderSeasonInningSummary(nativeInnings), "season-inning-table", "項目");

console.log(`Historical season UI: all ${renderedProfiles} profiles, native 2026 routing, shared tables, transposed inning/decision values, known/missing counts and verified zero innings passed.`);
