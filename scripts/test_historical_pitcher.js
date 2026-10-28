/* Verify the historical adapter against every saved pitcher profile; no network. */
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const sandbox = { window: {} };
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(root, "summary/historical-pitcher.js"), "utf8"), sandbox);
const adapt = sandbox.window.HistoricalSeasonAdapters.pitcher;
const archive = JSON.parse(fs.readFileSync(path.join(root, "summary/nf3_2025_pitchers.json"), "utf8"));

function deepFreeze(value) {
  if (!value || typeof value !== "object") return value;
  Object.freeze(value);
  Object.values(value).forEach(deepFreeze);
  return value;
}

function sum(rows, key) {
  return rows.reduce((total, row) => total + (row[key] || 0), 0);
}

function sourceNumber(table, row, header) {
  const value = row[table.headers.indexOf(header)];
  if (value === undefined || value === "-" || value === "") return null;
  const result = Number(String(value).replace(/%$/, ""));
  return Number.isFinite(result) ? result : null;
}

function assertTotal(rows, key, annual, label) {
  assert.equal(sum(rows, key), annual[key], `${label}: ${key}`);
}

assert.equal(adapt(null), null);
assert.equal(adapt({}), null);
assert.equal(archive.players.length, 361);
let pitchTypeRows = 0;
const discrepancies = [];
for (const profile of archive.players) {
  const before = JSON.stringify(profile);
  deepFreeze(profile);
  const dashboard = adapt(profile, deepFreeze({ pitches: -999, strikeouts: -999 }));
  const annual = profile.annual;
  const label = `${profile.nf3Id} ${profile.player}`;
  assert.equal(JSON.stringify(profile), before, `${label}: input is immutable`);
  assert.equal(dashboard.totalPitches, annual.pitches, `${label}: annual pitches`);
  assertTotal(dashboard.pitchMix.map((row) => ({ pitches: row.count })), "pitches", annual, label);
  ["atBats", "hits", "homeRuns"].forEach((key) => assertTotal(dashboard.pitchMix, key, annual, label));
  assert.equal(sum(dashboard.pitchMix, "whiffCount"), annual.swingMisses, `${label}: whiffs`);

  const source = profile.tables.find((table) => table.headers.includes("球種") && table.headers.includes("球数"));
  assert.equal(dashboard.pitchMix.length, source.rows.length, `${label}: source pitch types retained`);
  for (let index = 0; index < source.rows.length; index += 1) {
    const raw = source.rows[index];
    const row = dashboard.pitchMix[index];
    pitchTypeRows += 1;
    assert.equal(row.pitchType, raw[source.headers.indexOf("球種")], label);
    for (const [key, header] of [["count", "球数"], ["ratio", "割合"], ["avgSpeed", "平均球速 (km/h)"], ["whiffCount", "空振り"], ["whiffRate", "Whiff%"], ["calledStrikeCount", "見逃し"], ["atBats", "被打数"], ["hits", "被安"], ["homeRuns", "被本"], ["strikeouts", "奪三振"], ["unintentionalWalks", "与四球"], ["hitByPitch", "与死球"], ["hitRate", "被打率"]]) {
      assert.equal(row[key], sourceNumber(source, raw, header), `${label} ${row.pitchType}: ${key}`);
    }
    assert.equal(row.whiff, Number((row.whiffCount / row.count * 100).toFixed(1)), `${label}: whiff per pitch`);
    assert.equal(row.csw, Number(((row.whiffCount + row.calledStrikeCount) / row.count * 100).toFixed(1)), `${label}: CSW`);
    ["maxSpeed", "singles", "doubles", "triples", "grounders", "flyBalls", "zoneRate", "zSwing", "oContact", "chase", "chasePlus", "walks", "swingCount"].forEach((key) => {
      assert.equal(row[key], null, `${label}: unavailable ${key} must not become zero`);
    });
  }

  ["atBats", "hits", "homeRuns", "strikeouts", "walks", "hitByPitch", "singles", "doubles", "triples", "sacrificeBunts", "sacrificeFlies"].forEach((key) => {
    assertTotal(dashboard.batterHandRows, key, annual, `${label} by hand`);
  });
  assert.equal(sum(dashboard.batterHandRows, "countPA"), annual.batters, `${label}: hand PA total`);
  for (const row of dashboard.batterHandRows) {
    assert.equal(row.count, row.countPA, label);
    assert.equal(row.countBasis, "plateAppearances", label);
    assert.equal(row.pitchCount, null, label);
    assert.equal(row.whiffCount, null, label);
    assert.equal(row.whiff, null, label);
    assert.equal(row.hits, row.singles + row.doubles + row.triples + row.homeRuns, label);
  }
  for (const section of ["opponentRows", "stadiumRows"]) {
    for (const key of ["games", "inningsOuts", "hits", "homeRuns", "strikeouts", "walks", "hitByPitch", "runs", "earnedRuns"]) {
      const recorded = sum(dashboard[section], key);
      if (recorded !== annual[key]) {
        assert.ok(dashboard.sourceCoverageInfo.discrepancies.some((difference) => difference.scope === section && difference.metric === key && difference.recorded === recorded && difference.annual === annual[key]), `${label}: reported ${section} discrepancy`);
      } else {
        assertTotal(dashboard[section], key, annual, `${label} ${section}`);
      }
    }
    for (const row of dashboard[section]) {
      assert.equal(row.batters, null, `${label}: unrecorded split batters`);
      assert.equal(row.atBats, null, `${label}: unrecorded split AB`);
    }
  }

  const outcomeTable = profile.tables.find((table) => table.title.startsWith("対打者結果一覧"));
  assert.equal(dashboard.outcomes.total, outcomeTable.rows.reduce((total, row) => total + Number(row[1]), 0), `${label}: outcome counts`);
  for (const [id, key] of [["grounders", "grounders"], ["flyballs", "flyBalls"], ["swingingStrikeouts", "swingingStrikeouts"], ["lookingStrikeouts", "lookingStrikeouts"], ["sacrificeBunts", "sacrificeBunts"], ["interference", "interference"]]) {
    assert.equal(dashboard.outcomes.rows.find((row) => row.id === id).count, annual[key], `${label}: outcome ${id}`);
  }
  assert.equal(sum(dashboard.finish.rows, "count"), sum(dashboard.pitchMix, "strikeouts"), label);
  assert.equal(dashboard.finish.total, sum(dashboard.finish.rows, "count"), label);
  assert.equal(dashboard.finish.annualTotal, annual.strikeouts, label);
  for (const row of dashboard.finish.rows) {
    assert.equal(row.looking, null, label);
    assert.equal(row.swinging, null, label);
  }
  dashboard.sourceCoverageInfo.discrepancies.forEach((difference) => discrepancies.push({ player: profile.nf3Id, ...difference }));
  assert.equal(dashboard.inningRows.length, 0, label);
  assert.equal(dashboard.inningRunRowsAvailable, false, label);
  assert.equal(dashboard.inningWalkRowsAvailable, false, label);
  assert.equal(dashboard.recentGames.length, 0, label);
  assert.equal(dashboard.starterInningRunRowsScope, "starts_including_runs_after_exit", label);
  assert.equal(dashboard.starterInningRunRows.length, 12, label);
  assert.ok(dashboard.sourceCoverageInfo.unavailableSections.includes("recentGames"), label);
}

// Preserve a known source discrepancy instead of inventing a pitch type or a K.
assert.deepEqual(discrepancies.sort((left, right) => left.player.localeCompare(right.player)), [
  { player: "E:31", scope: "stadiumRows", metric: "walks", recorded: 13, annual: 14 },
  { player: "E:41", scope: "stadiumRows", metric: "walks", recorded: 18, annual: 19 },
  { player: "E:45", scope: "stadiumRows", metric: "walks", recorded: 16, annual: 19 },
  { player: "E:57", scope: "stadiumRows", metric: "walks", recorded: 20, annual: 21 },
  { player: "F:18", scope: "pitchMix", metric: "strikeouts", recorded: 50, annual: 51 },
]);
const miyagi = adapt(archive.players.find((profile) => profile.nf3Id === "B:18"));
assert.equal(miyagi.totalPitches, 2403);
assert.equal(miyagi.pitchMix[0].hits, 61);
assert.equal(miyagi.pitchMix[0].whiff, 4.8);
assert.equal(miyagi.pitchMix[0].whiffRate, 11.0);
assert.equal(miyagi.pitchMix[0].csw, 33.0);
assert.equal(miyagi.finish.total, 165);
assert.equal(miyagi.outcomes.total, 440);
// 40 runs covers starts with runs after exit; full-season Miyagi has 41 runs.
assert.equal(sum(miyagi.starterInningRunRows, "total"), 40);
assert.equal(miyagi.inningRunRows.length, 0);

// Missing values must remain missing, including zero-denominator rates.
const synthetic = adapt({ annual: { pitches: 0 }, tables: [{
  title: "球種一覧",
  headers: ["球種", "球数", "割合", "空振り", "見逃し", "被安", "被本", "Whiff%"],
  rows: [["不明", "0", "-", "-", "-", "-", "-", "-"]],
}] });
assert.equal(synthetic.pitchMix[0].hits, null);
assert.equal(synthetic.pitchMix[0].whiff, null);
assert.equal(synthetic.pitchMix[0].csw, null);
assert.equal(synthetic.pitchMix[0].avgSpeed, null);
console.log(`PASS: ${archive.players.length} pitcher profiles, ${pitchTypeRows} pitch-type rows; ${discrepancies.length} preserved source discrepancies.`);
