/* Convert archived batting tables to the annual dashboard's shared row schema.
 * This adapter is deliberately pure: absent columns stay null, and no pitch or
 * game records are reconstructed from season totals. */
(function (global) {
  "use strict";

  const COUNTS = ["plateAppearances", "atBats", "hits", "singles", "doubles", "triples", "homeRuns", "walks", "hitByPitch", "sacBunts", "sacFlies", "strikeouts"];
  const RATES = ["battingAverage", "onBasePercentage", "sluggingPercentage", "ops"];
  const FIELDS = [...COUNTS, ...RATES];
  const EXTRA_COUNTS = ["games", "runs", "runsBattedIn", "intentionalWalks", "totalBases", "steals", "caughtStealing", "errors", "walksAndHitByPitch", "pitchCount", "whiffs", "calledStrikes", "fouls", "balls"];
  const HEADER_FIELDS = {
    打席: "plateAppearances", 打数: "atBats", 安打: "hits", "2B": "doubles", "2塁": "doubles", "3B": "triples", "3塁": "triples", 本塁: "homeRuns", HR: "homeRuns",
    四球: "walks", 死球: "hitByPitch", 犠打: "sacBunts", 犠飛: "sacFlies", 三振: "strikeouts", 打率: "battingAverage", 出塁率: "onBasePercentage", 長打率: "sluggingPercentage", OPS: "ops",
    試合: "games", 得点: "runs", 打点: "runsBattedIn", 敬遠: "intentionalWalks", 塁打: "totalBases", 盗塁: "steals", 盗塁死: "caughtStealing", 失策: "errors", 四死: "walksAndHitByPitch",
    球数: "pitchCount", 割合: "pitchPercentage", "平均球速(km/h)": "averageVelocity", 空振り: "whiffs", 見逃し: "calledStrikes", ファウル: "fouls", ボール: "balls", ストライク割合: "strikeRate", "Whiff%": "whiffRate",
  };
  const SECTION_KEYS = ["byOpponent", "byStadium", "byPitchType", "byVelocity", "byPitcherHand", "byBattingOrder", "byPlateAppearance", "byStrikeCount", "recentGames"];
  const normalize = (value) => String(value == null ? "" : value).normalize("NFKC").replace(/\s+/g, "");
  const numeric = (value) => {
    if (value == null || typeof value === "boolean") return null;
    if (typeof value === "number") return Number.isFinite(value) ? value : null;
    const text = String(value).trim().replace(/,/g, "");
    if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)%?$/.test(text)) return null;
    const result = Number(text.replace(/%$/, ""));
    return Number.isFinite(result) ? result : null;
  };
  const known = (...values) => values.every((value) => typeof value === "number" && Number.isFinite(value));
  const rounded = (value) => Math.round((value + Number.EPSILON) * 1000) / 1000;
  const ratio = (numerator, denominator) => known(numerator, denominator) && denominator > 0 ? rounded(numerator / denominator) : null;

  function finalize(row) {
    if (row.singles == null && known(row.hits, row.doubles, row.triples, row.homeRuns)) row.singles = row.hits - row.doubles - row.triples - row.homeRuns;
    if (row.totalBases == null && known(row.hits, row.doubles, row.triples, row.homeRuns)) row.totalBases = row.hits + row.doubles + (2 * row.triples) + (3 * row.homeRuns);
    if (row.battingAverage == null) row.battingAverage = ratio(row.hits, row.atBats);
    // Both BB and HBP must be known, or their explicitly reported combined count.
    const freeBases = known(row.walks, row.hitByPitch) ? row.walks + row.hitByPitch : row.walksAndHitByPitch;
    if (row.onBasePercentage == null && known(row.hits, row.atBats, freeBases, row.sacFlies)) row.onBasePercentage = ratio(row.hits + freeBases, row.atBats + freeBases + row.sacFlies);
    if (row.sluggingPercentage == null) row.sluggingPercentage = ratio(row.totalBases, row.atBats);
    if (row.ops == null && known(row.onBasePercentage, row.sluggingPercentage)) {
      const obpDenominator = known(row.atBats, freeBases, row.sacFlies) ? row.atBats + freeBases + row.sacFlies : null;
      const exactObp = known(row.hits, freeBases, obpDenominator) && obpDenominator > 0 ? (row.hits + freeBases) / obpDenominator : row.onBasePercentage;
      const exactSlg = known(row.totalBases, row.atBats) && row.atBats > 0 ? row.totalBases / row.atBats : row.sluggingPercentage;
      row.ops = rounded(exactObp + exactSlg);
    }
    // Some archived empty rows contain a literal .000 OPS; no AB means AVG,
    // SLG and OPS have no denominator. Keep that literal only in sourceRates.
    if (row.atBats === 0) row.battingAverage = row.sluggingPercentage = row.ops = null;
    return row;
  }

  function tableRows(table) {
    if (!table || !Array.isArray(table.headers) || !Array.isArray(table.rows)) return [];
    return table.rows.filter(Array.isArray).map((cells) => {
      const row = { label: String(cells[0] == null ? "" : cells[0]).trim(), sourceRates: {} };
      for (const field of [...FIELDS, ...EXTRA_COUNTS, "pitchPercentage", "averageVelocity", "strikeRate", "whiffRate"]) row[field] = null;
      table.headers.forEach((header, index) => {
        const field = HEADER_FIELDS[normalize(header)];
        if (!field) return;
        row[field] = numeric(cells[index]);
        if (RATES.includes(field)) row.sourceRates[field] = row[field];
      });
      return finalize(row);
    }).filter((row) => row.label && !/^(?:合計|計|総計|通算)$/.test(normalize(row.label)));
  }

  function sumRows(rows, label) {
    const result = { label, sourceRates: {} };
    for (const field of [...COUNTS, ...EXTRA_COUNTS]) result[field] = rows.length && rows.every((row) => known(row[field])) ? rows.reduce((sum, row) => sum + row[field], 0) : null;
    for (const field of RATES) result[field] = null;
    return finalize(result);
  }

  function buildBatterDashboard(profile, annualRow) {
    const tables = Array.isArray(profile && profile.tables) ? profile.tables : [];
    const findTable = (title) => tables.find((table) => normalize(table.title) === normalize(title));
    const annual = annualRow || profile && profile.annual || {};
    const dashboard = {
      historicalSource: true,
      sourceKind: "historicalTables",
      schemaVersion: 1,
      totalPlateAppearances: numeric(annual.plateAppearances),
      sectionMeta: {},
    };
    for (const key of SECTION_KEYS) dashboard[key] = [];

    function addSection(key, rows, details) {
      dashboard[key] = rows;
      dashboard.sectionMeta[key] = {
        available: rows.length > 0,
        columns: FIELDS.filter((field) => rows.some((row) => known(row[field]))),
        missingFields: FIELDS.filter((field) => !rows.some((row) => known(row[field]))),
        scope: "season",
        note: "",
        reason: rows.length ? "" : "この条件の年度集計は未収録です。",
        ...details,
      };
    }

    const opponentTables = [findTable("対チーム別成績(リーグ)"), findTable("対チーム別成績(交流戦)")].filter(Boolean);
    const opponents = opponentTables.flatMap(tableRows);
    const opponentLabels = [...new Set(opponents.map((row) => row.label))];
    addSection("byOpponent", opponentLabels.map((label) => {
      const rows = opponents.filter((row) => row.label === label);
      return rows.length === 1 ? rows[0] : sumRows(rows, label);
    }), { sourceTitle: "対チーム別成績", partition: true });
    addSection("byStadium", tableRows(findTable("球場別成績")), { sourceTitle: "球場別成績", partition: true });

    const pitchTable = tables.find((table) => normalize(table.title).startsWith("球種一覧"));
    addSection("byPitchType", tableRows(pitchTable), {
      sourceTitle: "球種別成績", scope: "reportedPitchResults", partition: false,
      note: "球種を確認できた投球・打席結果の集計です。四球には故意四球を含みません。打席・二塁打・三塁打・犠打・犠飛は未収録です。",
      extraColumns: ["pitchCount", "pitchPercentage", "averageVelocity", "whiffs", "calledStrikes", "fouls", "balls", "strikeRate", "whiffRate"],
    });
    addSection("byVelocity", [], { reason: "球速帯別の打撃成績は未収録です。" });

    const hands = tableRows(findTable("対左右別成績"));
    for (const row of hands) {
      if (normalize(row.label) === "対右投手") row.label = "右";
      if (normalize(row.label) === "対左投手") row.label = "左";
    }
    addSection("byPitcherHand", hands, { sourceTitle: "対左右別成績", partition: true });
    addSection("byBattingOrder", tableRows(findTable("打順別成績(先発時)")), {
      sourceTitle: "打順別成績(先発時)", title: "打順別打撃成績（先発時）", scope: "starts", partition: false,
      note: "先発出場時の成績です。途中出場時の打席は含みません。",
    });
    addSection("byPlateAppearance", tableRows(findTable("打席別成績(先発時)")), {
      sourceTitle: "打席別成績(先発時)", title: "打席別打撃成績（先発時）", scope: "starts", partition: false,
      note: "先発出場時の成績です。四球と死球は合計のみ収録しています。打席・二塁打・三塁打・長打率・OPSは未収録です。",
      extraColumns: ["walksAndHitByPitch"],
    });

    const counts = tableRows(findTable("カウント別成績"));
    dashboard.byCount = counts;
    const grouped = new Map();
    // Archived labels use balls-strikes (3-0, 3-1 and 3-2 are present).
    for (const row of counts) {
      const match = normalize(row.label).match(/^([0-3])-([0-2])(?:より|から)?$/);
      if (!match) continue;
      const strikes = Number(match[2]);
      if (!grouped.has(strikes)) grouped.set(strikes, []);
      grouped.get(strikes).push(row);
    }
    addSection("byStrikeCount", [...grouped.entries()].sort((a, b) => a[0] - b[0]).map(([strikes, rows]) => sumRows(rows, `${strikes}ストライク`)), {
      sourceTitle: "カウント別成績", partition: true,
      note: "打席結果直前のストライク数で集計しています。各ボールカウントの実数を合算し、率を再計算しています。",
    });

    // Retain the runner/RISP split without treating its overlapping summary as
    // a disjoint partition of plate appearances.
    const runnerTable = tables.find((table) => /^ランナ[ー−－-]別成績$/.test(normalize(table.title)));
    dashboard.byRunner = tableRows(runnerTable);
    dashboard.scoringPosition = dashboard.byRunner.find((row) => /得点圏/.test(row.label)) || null;
    addSection("recentGames", [], { reason: "試合別の直近成績は未収録です。" });
    dashboard.sectionMeta.byCount = { available: counts.length > 0, scope: "season", partition: true };
    dashboard.sectionMeta.byRunner = { available: dashboard.byRunner.length > 0, scope: "season", partition: false, note: "得点圏の行は他の走者状況と重複する集計です。" };
    return dashboard;
  }

  global.HistoricalSeasonAdapters = global.HistoricalSeasonAdapters || {};
  global.HistoricalSeasonAdapters.batter = buildBatterDashboard;
})(typeof window !== "undefined" ? window : globalThis);
