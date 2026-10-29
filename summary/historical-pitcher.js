/* Adapt historical aggregate tables to the annual dashboard's shared data shape. */
(function (root) {
  "use strict";

  const COLORS = ["#0F2340", "#355C8C", "#6A89B4", "#C8A55A", "#D6C192", "#9D8B75", "#7D97B5"];
  const OUTCOMES = [
    ["grounders", "ゴロ", "ゴロ"],
    ["flyballs", "フライ", "フライ"],
    ["swingingStrikeouts", "空三振", "空三振"],
    ["lookingStrikeouts", "見三振", "見三振"],
    ["sacrificeBunts", "犠打", "犠打"],
    ["interference", "守備妨害", "守備妨"],
  ];

  function number(value) {
    if (value === null || value === undefined) return null;
    const text = String(value).trim().replace(/,/g, "").replace(/%$/, "");
    if (!text || text === "-" || text === "--" || text === "∞") return null;
    const parsed = Number(text);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function roundedRatio(numerator, denominator, digits = 1) {
    if (numerator === null || denominator === null || denominator <= 0) return null;
    return Number((numerator / denominator * 100).toFixed(digits));
  }

  function sum(rows, key) {
    return rows.reduce((total, row) => total + (number(row[key]) || 0), 0);
  }

  function cell(table, row, header) {
    const index = table.headers.indexOf(header);
    return index < 0 ? null : row[index];
  }

  function numericCell(table, row, header) {
    return number(cell(table, row, header));
  }

  function unknownPitchMetrics() {
    return {
      maxSpeed: null,
      speedTotal: null,
      speedCount: null,
      swingCount: null,
      locatedCount: null,
      zoneCount: null,
      outZoneCount: null,
      zoneSwingCount: null,
      outZoneSwingCount: null,
      outZoneContactCount: null,
      zoneRate: null,
      zSwing: null,
      oContact: null,
      chase: null,
      chasePlus: null,
      grounders: null,
      flyBalls: null,
      babipAllowed: null,
    };
  }

  function pitchRows(table) {
    if (!table) return [];
    return table.rows.map((row, index) => {
      const count = numericCell(table, row, "球数");
      const whiffCount = numericCell(table, row, "空振り");
      const calledStrikeCount = numericCell(table, row, "見逃し");
      return {
        ...unknownPitchMetrics(),
        pitchType: String(cell(table, row, "球種") || "不明"),
        color: COLORS[index % COLORS.length],
        count,
        ratio: numericCell(table, row, "割合"),
        avgSpeed: numericCell(table, row, "平均球速 (km/h)"),
        whiffCount,
        // The first table uses all pitches; whiff% uses swings in the second.
        whiff: roundedRatio(whiffCount, count),
        whiffRate: numericCell(table, row, "Whiff%"),
        calledStrikeCount,
        foulCount: numericCell(table, row, "ファウル"),
        ballCount: numericCell(table, row, "ボール"),
        csw: roundedRatio(whiffCount === null || calledStrikeCount === null ? null : whiffCount + calledStrikeCount, count),
        atBats: numericCell(table, row, "被打数"),
        hits: numericCell(table, row, "被安"),
        // A hit total is available; its single/double/triple breakdown is not.
        singles: null,
        doubles: null,
        triples: null,
        homeRuns: numericCell(table, row, "被本"),
        strikeouts: numericCell(table, row, "奪三振"),
        unintentionalWalks: numericCell(table, row, "与四球"),
        walks: null,
        intentionalWalks: null,
        hitByPitch: numericCell(table, row, "与死球"),
        sacrificeFlies: null,
        hitRate: numericCell(table, row, "被打率"),
      };
    });
  }

  function handRows(table) {
    if (!table) return [];
    return table.rows.map((row) => {
      const countPA = numericCell(table, row, "打席");
      const hits = numericCell(table, row, "安打");
      const doubles = numericCell(table, row, "2塁");
      const triples = numericCell(table, row, "3塁");
      const homeRuns = numericCell(table, row, "本塁");
      return {
        ...unknownPitchMetrics(),
        label: String(cell(table, row, "条件") || "不明"),
        // Only used as a nonempty-row guard. This is PA, never a pitch count.
        count: countPA,
        countPA,
        countBasis: "plateAppearances",
        pitchCount: null,
        ratio: null,
        avgSpeed: null,
        whiffCount: null,
        whiff: null,
        whiffRate: null,
        calledStrikeCount: null,
        csw: null,
        batters: countPA,
        atBats: numericCell(table, row, "打数"),
        hits,
        singles: [hits, doubles, triples, homeRuns].every((value) => value !== null) ? hits - doubles - triples - homeRuns : null,
        doubles,
        triples,
        homeRuns,
        strikeouts: numericCell(table, row, "三振"),
        walks: numericCell(table, row, "四球"),
        hitByPitch: numericCell(table, row, "死球"),
        sacrificeBunts: numericCell(table, row, "犠打"),
        sacrificeFlies: numericCell(table, row, "犠飛"),
        hitRate: numericCell(table, row, "打率"),
      };
    });
  }

  function inningsOuts(value) {
    const match = String(value || "").match(/^(\d+)(?:\.([012]))?$/);
    return match ? Number(match[1]) * 3 + Number(match[2] || 0) : null;
  }

  function gameSplitRows(tables, labelHeader) {
    return tables.flatMap((table) => table.rows.map((row) => {
      const innings = cell(table, row, "回数");
      return {
        label: String(cell(table, row, labelHeader) || "不明"),
        games: numericCell(table, row, "試合"),
        starts: numericCell(table, row, "先発"),
        reliefAppearances: numericCell(table, row, "救援"),
        wins: numericCell(table, row, "勝利"),
        losses: numericCell(table, row, "敗戦"),
        holds: numericCell(table, row, "HLD"),
        saves: numericCell(table, row, "Ｓ"),
        era: numericCell(table, row, "防御率"),
        innings: innings === null ? null : String(innings),
        inningsOuts: inningsOuts(innings),
        // Neither batters faced nor AB can be reconstructed from rounded AVG.
        batters: null,
        atBats: null,
        hits: numericCell(table, row, "被安"),
        homeRuns: numericCell(table, row, "被本"),
        strikeouts: numericCell(table, row, "三振"),
        walks: numericCell(table, row, "四球"),
        hitByPitch: numericCell(table, row, "死球"),
        runs: numericCell(table, row, "失点"),
        earnedRuns: numericCell(table, row, "自責"),
        whip: numericCell(table, row, "WHIP"),
        battingAverageAllowed: numericCell(table, row, "被打率"),
      };
    }));
  }

  function outcomeSummary(table) {
    if (!table) return { total: 0, rows: [] };
    const sourceCounts = new Map(table.rows.map((row) => [String(row[0]), number(row[1])]));
    const rows = OUTCOMES.map(([id, label, sourceLabel], index) => ({
      id, label, count: sourceCounts.get(sourceLabel) ?? null, color: COLORS[index % COLORS.length],
    }));
    const total = sum(rows, "count");
    return { total, rows: rows.map((row) => ({ ...row, ratio: roundedRatio(row.count, total) })) };
  }

  function starterInningRows(table) {
    if (!table) return [];
    const sourceRows = new Map(table.rows.map((row) => [String(row[0]), row]));
    return Array.from({ length: 12 }, (_unused, index) => {
      const inning = index + 1;
      const header = `${inning}回`;
      const get = (label) => sourceRows.has(label) ? numericCell(table, sourceRows.get(label), header) : null;
      return { inning, total: get("合計"), win: get("勝利"), loss: get("敗戦"), noDecision: get("勝敗無") };
    });
  }

  function pitcher(profile, annualRow) {
    if (!profile || !Array.isArray(profile.tables)) return null;
    const annual = { ...(annualRow || {}), ...(profile.annual || {}) };
    const tables = profile.tables;
    const pitchTable = tables.find((table) => table.headers.includes("球種") && table.headers.includes("球数"));
    const pitchMix = pitchRows(pitchTable);
    const batterHandRows = handRows(tables.find((table) => table.title === "左右別成績"));
    const opponentRows = gameSplitRows(tables.filter((table) => table.title.startsWith("対チーム別成績")), "チーム");
    const stadiumRows = gameSplitRows(tables.filter((table) => table.title === "球場別成績"), "球場");
    const outcomes = outcomeSummary(tables.find((table) => table.title.startsWith("対打者結果一覧")));
    const starterInningRunRows = starterInningRows(tables.find((table) => table.title.startsWith("先発時のイニング毎失点数")));
    const totalPitches = number(annual.pitches) ?? sum(pitchMix, "count");
    const finishTotal = sum(pitchMix, "strikeouts");
    const discrepancies = [];
    for (const [sourceKey, annualKey] of [["count", "pitches"], ["atBats", "atBats"], ["hits", "hits"], ["homeRuns", "homeRuns"], ["strikeouts", "strikeouts"]]) {
      const expected = number(annual[annualKey]);
      const recorded = sum(pitchMix, sourceKey);
      if (pitchTable && expected !== null && recorded !== expected) {
        discrepancies.push({ scope: "pitchMix", metric: annualKey, recorded, annual: expected });
      }
    }
    for (const [scope, rows] of [["opponentRows", opponentRows], ["stadiumRows", stadiumRows]]) {
      for (const metric of ["games", "inningsOuts", "hits", "homeRuns", "strikeouts", "walks", "hitByPitch", "runs", "earnedRuns"]) {
        const expected = number(annual[metric]);
        const recorded = sum(rows, metric);
        if (rows.length && expected !== null && recorded !== expected) {
          discrepancies.push({ scope, metric, recorded, annual: expected });
        }
      }
    }
    const note = "2025年は年度集計を表示しています。イニング別失点は先発時のみで、救援時の失点・イニング別四死球は未収録です。最速球速・投球位置に基づく指標・イニング別投球・最近の試合も未収録です。";
    return {
      historical: true,
      totalPitches,
      sourceCoverage: { games: number(annual.games), recordedPitches: sum(pitchMix, "count"), officialPitches: number(annual.pitches) },
      sourceCoverageInfo: {
        kind: "historical_aggregate",
        year: "2025",
        note,
        availableSections: ["pitchMix", "batterHandRows", "opponentRows", "stadiumRows", "outcomes", "finish"],
        unavailableSections: ["inningRows", "inningWalkRows", "recentGames"],
        unavailableMetrics: ["maxSpeed", "zoneRate", "zSwing", "oContact", "chase", "chasePlus", "pitchTypeGrounders", "pitchTypeFlyBalls", "handWhiffs", "pitchTypeStrikeoutLookingSwinging"],
        discrepancies,
        discrepancyNote: discrepancies.length ? "条件別の集計と年度合計に差がある項目は、確認できた件数を表示しています。" : "",
        pitchTypeWalksScope: "unintentional_walks",
        batterHandCountBasis: "plateAppearances",
        outcomeScope: "outcome_counts_including_line_drives_and_sacrifice_flies_in_flyballs",
      },
      pitchMix,
      metricBaselines: { chase: null, chaseScope: null },
      inningRows: [],
      batterHandRows,
      opponentRows,
      stadiumRows,
      inningRunRows: [],
      inningRunRowsAvailable: false,
      inningRunRowsMethod: "unavailable_full_season",
      inningWalkRows: [],
      inningWalkRowsAvailable: false,
      inningWalkRowsScope: "unavailable",
      // This table must never be labelled as the pitcher's full-season runs.
      starterInningRunRows,
      starterInningRunRowsTitle: "先発時のイニング別失点数",
      starterInningRunRowsScope: "starts_including_runs_after_exit",
      outcomes,
      finish: {
        total: finishTotal,
        annualTotal: number(annual.strikeouts),
        rows: pitchMix.filter((row) => row.strikeouts > 0).map((row) => ({
          pitchType: row.pitchType,
          color: row.color,
          count: row.strikeouts,
          ratio: roundedRatio(row.strikeouts, finishTotal),
          looking: null,
          swinging: null,
        })),
      },
      recentGames: [],
    };
  }

  root.HistoricalSeasonAdapters = root.HistoricalSeasonAdapters || {};
  root.HistoricalSeasonAdapters.pitcher = pitcher;
})(typeof window === "undefined" ? globalThis : window);
