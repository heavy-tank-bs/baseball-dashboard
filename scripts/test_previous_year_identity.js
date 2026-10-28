"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(root, "summary/compare.js"), "utf8");
const scope = { URLSearchParams };
vm.createContext(scope);
vm.runInContext(source.slice(source.indexOf("function normalizePlayerName("), source.indexOf("function summaryItems(")), scope);

for (const idKey of ["pitcherId", "batterId"]) {
  const config = { idKey };
  const previous = { year: "2025", team: "西武", player: "旧登録名", [idKey]: "renamed" };
  const current = { year: "2026", team: "西武", player: "新登録名", [idKey]: "renamed" };
  const params = new URLSearchParams({ year: "2026", team: current.team, player: previous.player, playerId: "renamed" });
  assert.equal(scope.findCurrentRow([previous, current], params, config), current, "ID links survive display-name changes");
  assert.equal(scope.findPreviousRow([previous, current], current, params, config), previous, "year matching considers IDs before names");

  const historical = { year: "2025", team: "東北楽天", player: "選手 太郎", npbUrl: "https://npb.jp/bis/players/12345678.html" };
  const transferred = { year: "2026", team: "巨人", player: "選手　太郎", [idKey]: "transfer" };
  const rows = [historical, transferred];
  assert.equal(scope.findPlayerSeasonRow(rows, historical, "2026", config), transferred, "unique names link forward from an ID-less historical row");
  assert.equal(scope.findPlayerSeasonRow(rows, transferred, "2025", config), historical, "unique transfers link back across clubs");
  assert.equal(scope.findPlayerSeasonRow(rows, { year: "2026", team: "楽天", player: "選手太郎" }, "2025", config), historical, "Rakuten team labels and whitespace normalize");

  const otherPerson = { year: "2025", team: "西武", player: "選手 太郎", [idKey]: "someone-else" };
  assert.equal(scope.findPlayerSeasonRow([otherPerson, transferred], transferred, "2025", config), null, "same names never override conflicting IDs");

  const swallows = { year: "2026", team: "ヤクルト", player: "オスナ", [idKey]: "batter-osuna" };
  const hawks = { year: "2026", team: "ソフトバンク", player: "オスナ", [idKey]: "pitcher-osuna" };
  const hawksPrevious = { year: "2025", team: "ソフトバンク", player: "オスナ", npbUrl: "https://npb.jp/bis/players/13415155.html" };
  const osunas = [swallows, hawks, hawksPrevious];
  assert.equal(scope.findPlayerSeasonRow(osunas, swallows, "2025", config), null, "position-player pitching must not borrow another Osuna's season");
  assert.equal(scope.findPlayerSeasonRow(osunas, hawks, "2025", config), hawksPrevious);
  assert.equal(scope.findPlayerSeasonRow(osunas, hawksPrevious, "2026", config), hawks, "historical views choose the same-club namesake");

  const hernandezGiants = { year: "2025", team: "巨人", player: "ヘルナンデス", npbUrl: "https://npb.jp/bis/players/11111111.html" };
  const hernandezHawks = { year: "2025", team: "ソフトバンク", player: "ヘルナンデス", npbUrl: "https://npb.jp/bis/players/22222222.html" };
  const hernandez2026 = { year: "2026", team: "ソフトバンク", player: "ヘルナンデス", [idKey]: "hawks" };
  assert.equal(scope.findPlayerSeasonRow([hernandezGiants, hernandezHawks, hernandez2026], hernandezGiants, "2026", config), null, "NPB profiles expose namesakes even when only one 2026 ID exists");

  const richardHawks = { year: "2025", team: "ソフトバンク", player: "リチャード", npbUrl: "https://npb.jp/bis/players/11015136.html" };
  const richardGiants = { ...richardHawks, team: "巨人" };
  const richard2026 = { year: "2026", team: "巨人", player: "リチャード", [idKey]: "richard" };
  assert.equal(scope.findPlayerSeasonRow([richardHawks, richardGiants, richard2026], richardHawks, "2026", config), richard2026, "one NPB identity across transfer rows is not a namesake collision");
  assert.equal(scope.findPlayerSeasonRow([richardHawks, richardGiants], richardGiants, "2025", config), richardGiants, "proven identity keeps requested team splits");
  assert.equal(scope.findPlayerSeasonRow([previous, current], { year: "2026", team: "西武", player: "新人" }, "2025", config), null);
}

for (const [kind, filename, idKey] of [
  ["pitcher", "player_totals.json", "pitcherId"],
  ["batter", "batter_totals.json", "batterId"],
]) {
  const rows = JSON.parse(fs.readFileSync(path.join(root, "summary", filename), "utf8")).players;
  const currentRows = rows.filter((row) => row.year === "2026");
  let matched = 0;
  for (const row of currentRows) {
    const previous = scope.findPlayerSeasonRow(rows, row, "2025", { idKey });
    if (!previous) continue;
    matched += 1;
    assert.equal(previous.year, "2025");
    if (previous[idKey]) assert.equal(previous[idKey], row[idKey]);
  }
  const exampleName = kind === "pitcher" ? "宮城大弥" : "若月健矢";
  const historicalExample = rows.find((row) => row.year === "2025" && scope.normalizePlayerName(row.player) === exampleName);
  if (historicalExample) {
    const next = scope.findPlayerSeasonRow(rows, historicalExample, "2026", { idKey });
    assert.ok(next, `2025 ${exampleName} view can compare with 2026`);
    assert.equal(next.team, "オリックス");
    assert.equal(scope.findPlayerSeasonRow(rows, next, "2025", { idKey }), historicalExample);
  }
  if (kind === "pitcher") {
    const swallowsOsuna = currentRows.find((row) => row.player === "オスナ" && row.team === "ヤクルト");
    assert.ok(swallowsOsuna, "real dataset includes the position-player pitching regression");
    assert.equal(scope.findPlayerSeasonRow(rows, swallowsOsuna, "2025", { idKey }), null);
  }
  console.log(`PASS: ${kind} season identities; ${matched}/${currentRows.length} 2026 rows safely match 2025`);
}

console.log("PASS: forward/backward seasons, renamed IDs, transfer splits, namesake rejection and historical ID gaps");
