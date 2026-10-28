"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const root = path.resolve(__dirname, "..");
const context = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(root, "summary/historical-batter.js"), "utf8"), context);
const adapt = context.window.HistoricalSeasonAdapters.batter;
const source = JSON.parse(fs.readFileSync(path.join(root, "summary/nf3_2025_batters.json"), "utf8"));
const countFields = ["plateAppearances", "atBats", "hits", "singles", "doubles", "triples", "homeRuns", "walks", "hitByPitch", "sacBunts", "sacFlies", "strikeouts"];
const rates = ["battingAverage", "onBasePercentage", "sluggingPercentage", "ops"];
const sections = ["byOpponent", "byStadium", "byPitchType", "byVelocity", "byPitcherHand", "byBattingOrder", "byPlateAppearance", "byStrikeCount"];
const sourceCountColumns = { 打席: "plateAppearances", 打数: "atBats", 安打: "hits", "2塁": "doubles", "3塁": "triples", 本塁: "homeRuns", 三振: "strikeouts", 四球: "walks", 死球: "hitByPitch", 犠打: "sacBunts", 犠飛: "sacFlies" };
const available = Object.fromEntries(sections.map((key) => [key, 0]));
let partitions = 0;
let countProfiles = 0;
let rispProfiles = 0;

function assertPartition(rows, annual, label) {
  for (const field of countFields) {
    if (!rows.length || !rows.every((row) => Number.isFinite(row[field])) || !Number.isFinite(annual[field])) continue;
    assert.equal(rows.reduce((sum, row) => sum + row[field], 0), annual[field], `${label}: ${field}`);
    partitions += 1;
  }
}

for (const profile of source.players) {
  const before = JSON.stringify(profile);
  const dashboard = adapt(profile, profile.annual);
  assert.equal(JSON.stringify(profile), before, `${profile.nf3Id}: pure adapter`);
  assert.equal(dashboard.totalPlateAppearances, profile.annual.plateAppearances);
  assert.equal(dashboard.historicalSource, true);
  for (const key of sections) {
    assert.ok(Array.isArray(dashboard[key]));
    assert.equal(dashboard.sectionMeta[key].available, dashboard[key].length > 0);
    if (dashboard[key].length) available[key] += 1;
    for (const row of dashboard[key]) {
      assert.equal(typeof row.label, "string");
      for (const field of [...countFields, ...rates]) {
        assert.ok(Object.hasOwn(row, field), `${profile.nf3Id} ${key} missing ${field}`);
        assert.ok(row[field] === null || Number.isFinite(row[field]), `${profile.nf3Id} ${key} invalid ${field}`);
      }
      if (row.atBats === 0) for (const field of ["battingAverage", "sluggingPercentage", "ops"]) assert.equal(row[field], null);
    }
  }
  for (const key of ["byOpponent", "byStadium", "byPitcherHand", "byStrikeCount"]) assertPartition(dashboard[key], profile.annual, `${profile.nf3Id} ${key}`);

  // Source tables have a rectangular schema, and the adapter retains each
  // reported count (including explicit zero) rather than manufacturing counts.
  for (const table of profile.tables) for (const row of table.rows) assert.equal(row.length, table.headers.length, `${profile.nf3Id} ${table.title} schema`);
  for (const key of ["byPitchType", "byPlateAppearance"]) for (const row of dashboard[key]) assert.equal(row.plateAppearances, null, `${profile.nf3Id} ${key} unknown PA`);
  for (const row of dashboard.byPitchType) {
    for (const field of ["doubles", "triples", "sacBunts", "sacFlies", "onBasePercentage", "sluggingPercentage", "ops"]) assert.equal(row[field], null, `${profile.nf3Id} pitch ${field}`);
    assert.ok(Number.isFinite(row.pitchCount));
  }
  for (const row of dashboard.byPlateAppearance) {
    for (const field of ["walks", "hitByPitch", "doubles", "triples", "sluggingPercentage", "ops"]) assert.equal(row[field], null, `${profile.nf3Id} plate ${field}`);
    assert.ok(Number.isFinite(row.walksAndHitByPitch));
  }
  if (dashboard.byBattingOrder.length) assert.equal(dashboard.sectionMeta.byBattingOrder.scope, "starts");
  if (dashboard.byPlateAppearance.length) assert.equal(dashboard.sectionMeta.byPlateAppearance.scope, "starts");
  assert.equal(dashboard.byVelocity.length, 0);
  assert.equal(dashboard.recentGames.length, 0);

  const countTable = profile.tables.find((table) => table.title === "カウント別成績");
  if (countTable) {
    countProfiles += 1;
    const strikeoutColumn = countTable.headers.indexOf("三振");
    assert.equal(dashboard.byCount.length, countTable.rows.length);
    for (const row of countTable.rows) {
      const match = row[0].match(/^([0-3])-([0-2])より$/);
      assert.ok(match, `${profile.nf3Id}: ball-strike count`);
      if (Number(row[strikeoutColumn]) > 0) assert.equal(match[2], "2", `${profile.nf3Id}: strikeouts use second count digit`);
    }
    for (const [header, field] of Object.entries(sourceCountColumns)) {
      const index = countTable.headers.indexOf(header);
      assert.ok(index >= 0);
      assert.equal(countTable.rows.reduce((sum, row) => sum + Number(row[index]), 0), profile.annual[field], `${profile.nf3Id} source count partition ${field}`);
      assert.equal(dashboard.byCount.reduce((sum, row) => sum + row[field], 0), profile.annual[field], `${profile.nf3Id} retained full count ${field}`);
    }
  }
  if (dashboard.scoringPosition) {
    rispProfiles += 1;
    assert.equal(dashboard.scoringPosition.atBats, profile.annual.scoringPositionAtBats, `${profile.nf3Id}: RISP AB`);
    assert.equal(dashboard.scoringPosition.hits, profile.annual.scoringPositionHits, `${profile.nf3Id}: RISP H`);
    if (dashboard.scoringPosition.atBats > 0) assert.equal(dashboard.scoringPosition.battingAverage, profile.annual.scoringPositionBattingAverage, `${profile.nf3Id}: RISP AVG`);
    assertPartition(dashboard.byRunner.filter((row) => !/得点圏/.test(row.label)), profile.annual, `${profile.nf3Id} runner disjoint rows`);
  }
}

// A reported rounded rate remains authoritative; rates with absent denominator
// fields remain null, including OBP when sacrifice flies are unreported.
const partial = adapt({ tables: [{ title: "球場別成績", headers: ["球場", "打数", "安打", "打率", "四球", "死球"], rows: [["テスト", "10", "3", ".299", "2", "0"]] }] });
assert.equal(partial.byStadium[0].battingAverage, 0.299);
assert.equal(partial.byStadium[0].onBasePercentage, null);
assert.equal(partial.byStadium[0].sacFlies, null);
assert.equal(partial.byStadium[0].plateAppearances, null);
assert.equal(partial.byStadium[0].doubles, null);
const complete = adapt({ tables: [{ title: "対左右別成績", headers: ["条件", "打席", "打数", "安打", "2塁", "3塁", "本塁", "四球", "死球", "犠打", "犠飛", "三振"], rows: [["対右投手", "15", "10", "3", "1", "0", "1", "2", "1", "1", "1", "2"]] }] });
assert.equal(complete.byPitcherHand[0].onBasePercentage, 0.429);
assert.equal(complete.byPitcherHand[0].sluggingPercentage, 0.7);
assert.equal(complete.byPitcherHand[0].ops, 1.129);
assert.equal(complete.byPitcherHand[0].label, "右");
const sourceZero = adapt({ tables: [{ title: "球場別成績", headers: ["球場", "打数", "安打", "打率", "長打率", "OPS"], rows: [["空", "0", "0", ".000", ".000", ".000"]] }] });
for (const field of ["battingAverage", "sluggingPercentage", "ops"]) {
  assert.equal(sourceZero.byStadium[0][field], null);
  assert.equal(sourceZero.byStadium[0].sourceRates[field], 0);
}
assert.equal(adapt(null).totalPlateAppearances, null);
assert.equal(source.players.length, 725);
assert.equal(countProfiles, 366);
assert.equal(rispProfiles, 366);
console.log(JSON.stringify({ profiles: source.players.length, partitionAssertions: partitions, countProfiles, rispProfiles, available }));
