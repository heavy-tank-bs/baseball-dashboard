const TYPE_CONFIG = {
  pitcher: {
    label: "投手",
    datasetUrl: "./player_totals.json?v=20260426-02",
    annualHref: "./annual.html",
    annualLabel: "年度別投手成績へ戻る",
    idKey: "pitcherId",
    metrics: [
      { key: "games", label: "試合", kind: "number", digits: 0, default: true },
      { key: "wins", label: "勝利", kind: "number", digits: 0 },
      { key: "losses", label: "敗戦", kind: "number", digits: 0, lowerIsBetter: true },
      { key: "saves", label: "セーブ", kind: "number", digits: 0 },
      { key: "holds", label: "ホールド", kind: "number", digits: 0 },
      { key: "inningsOuts", label: "投球回", kind: "innings", default: true },
      { key: "era", label: "防御率", kind: "decimal", digits: 2, lowerIsBetter: true, default: true },
      { key: "fip", label: "FIP", kind: "decimal", digits: 2, lowerIsBetter: true, default: true },
      { key: "whip", label: "WHIP", kind: "decimal", digits: 2, lowerIsBetter: true, default: true },
      { key: "battingAverageAllowed", label: "被打率", kind: "average", digits: 3, lowerIsBetter: true },
      { key: "strikeouts", label: "奪三振", kind: "number", digits: 0, default: true },
      { key: "kPer9", label: "K/9", kind: "decimal", digits: 2 },
      { key: "walks", label: "四球", kind: "number", digits: 0 },
      { key: "bbPer9", label: "BB/9", kind: "decimal", digits: 2, lowerIsBetter: true },
      { key: "kBb", label: "K/BB", kind: "decimal", digits: 2 },
      { key: "homeRuns", label: "被本塁打", kind: "number", digits: 0 },
      { key: "hrPer9", label: "HR/9", kind: "decimal", digits: 2, lowerIsBetter: true },
      { key: "groundOutRate", label: "ゴロアウト率", kind: "percent", digits: 1 },
      { key: "flyOutRate", label: "フライアウト率", kind: "percent", digits: 1 },
      { key: "pitches", label: "球数", kind: "number", digits: 0 },
    ],
  },
  batter: {
    label: "打者",
    datasetUrl: "./batter_totals.json?v=20260426-02",
    annualHref: "./annual-batter.html",
    annualLabel: "年度別打者成績へ戻る",
    idKey: "batterId",
    metrics: [
      { key: "games", label: "試合", kind: "number", digits: 0 },
      { key: "plateAppearances", label: "打席", kind: "number", digits: 0, default: true },
      { key: "atBats", label: "打数", kind: "number", digits: 0 },
      { key: "battingAverage", label: "打率", kind: "average", digits: 3, default: true },
      { key: "onBasePercentage", label: "出塁率", kind: "average", digits: 3, default: true },
      { key: "sluggingPercentage", label: "長打率", kind: "average", digits: 3 },
      { key: "ops", label: "OPS", kind: "average", digits: 3, default: true },
      { key: "wrcPlus", label: "wRC+", kind: "decimal", digits: 1, default: true },
      { key: "babip", label: "BABIP", kind: "average", digits: 3 },
      { key: "hits", label: "安打", kind: "number", digits: 0, default: true },
      { key: "doubles", label: "二塁打", kind: "number", digits: 0 },
      { key: "triples", label: "三塁打", kind: "number", digits: 0 },
      { key: "homeRuns", label: "本塁打", kind: "number", digits: 0, default: true },
      { key: "runsBattedIn", label: "打点", kind: "number", digits: 0, default: true },
      { key: "walks", label: "四球", kind: "number", digits: 0 },
      { key: "strikeouts", label: "三振", kind: "number", digits: 0, lowerIsBetter: true },
      { key: "steals", label: "盗塁", kind: "number", digits: 0 },
      { key: "isoDiscipline", label: "IsoD", kind: "average", digits: 3 },
      { key: "isoPower", label: "IsoP", kind: "average", digits: 3 },
    ],
  },
};

const MODE_CONFIG = {
  season: { label: "年度成績" },
  compare: { label: "前年比較" },
  monthly: { label: "月別成績" },
};

const MATCHUP_TEAM_NAMES = {
  "読売ジャイアンツ": "巨人",
  "阪神タイガース": "阪神",
  "横浜DeNAベイスターズ": "DeNA",
  "広島東洋カープ": "広島",
  "東京ヤクルトスワローズ": "ヤクルト",
  "中日ドラゴンズ": "中日",
  "福岡ソフトバンクホークス": "ソフトバンク",
  "北海道日本ハムファイターズ": "日本ハム",
  "千葉ロッテマリーンズ": "ロッテ",
  "オリックス・バファローズ": "オリックス",
  "埼玉西武ライオンズ": "西武",
  "東北楽天ゴールデンイーグルス": "楽天",
};

const MONTH_BUCKETS = [
  { key: "03-04", label: "3・4月", months: ["03", "04"] },
  { key: "05", label: "5月", months: ["05"] },
  { key: "06", label: "6月", months: ["06"] },
  { key: "07", label: "7月", months: ["07"] },
  { key: "08", label: "8月", months: ["08"] },
  { key: "09-10", label: "9・10月", months: ["09", "10"] },
];

const MONTH_BUCKET_INDEX = new Map(
  MONTH_BUCKETS.flatMap((bucket) => bucket.months.map((month) => [month, bucket]))
);

const state = {
  config: null,
  rows: [],
  currentRow: null,
  previousRow: null,
  activeMetricKeys: [],
  activeMode: "compare",
  error: "",
};

const els = {
  compareEyebrow: document.getElementById("compareEyebrow"),
  compareTitle: document.getElementById("compareTitle"),
  compareSubtitle: document.getElementById("compareSubtitle"),
  comparePlayerName: document.getElementById("comparePlayerName"),
  compareDescription: document.getElementById("compareDescription"),
  compareBackLink: document.getElementById("compareBackLink"),
  modeToggleGroup: document.getElementById("modeToggleGroup"),
  metricToggleGroup: document.getElementById("metricToggleGroup"),
  seasonPanel: document.getElementById("seasonPanel"),
  seasonMetricCount: document.getElementById("seasonMetricCount"),
  seasonDetailWrap: document.getElementById("seasonDetailWrap"),
  comparePanel: document.getElementById("comparePanel"),
  compareMetricCount: document.getElementById("compareMetricCount"),
  compareSeasonGrid: document.getElementById("compareSeasonGrid"),
  compareCardGrid: document.getElementById("compareCardGrid"),
  monthlyPanel: document.getElementById("monthlyPanel"),
  monthlyMetricCount: document.getElementById("monthlyMetricCount"),
  monthlySeasonGrid: document.getElementById("monthlySeasonGrid"),
  monthlyTableWrap: document.getElementById("monthlyTableWrap"),
  monthlyChartGrid: document.getElementById("monthlyChartGrid"),
};

function escapeHtml(value) {
  return `${value ?? ""}`
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatInningsFromOuts(outs) {
  const safeOuts = Math.max(0, Number(outs) || 0);
  const whole = Math.floor(safeOuts / 3);
  const remainder = safeOuts % 3;
  return remainder === 0 ? `${whole}` : `${whole}.${remainder}`;
}

function formatSignedInnings(outs) {
  const safeOuts = Number(outs);
  if (!Number.isFinite(safeOuts)) return "-";
  const sign = safeOuts > 0 ? "+" : safeOuts < 0 ? "-" : "";
  return `${sign}${formatInningsFromOuts(Math.abs(safeOuts))}`;
}

function metricMap(config) {
  return Object.fromEntries(config.metrics.map((metric) => [metric.key, metric]));
}

function metricValue(metric, row) {
  if (!row) return null;
  const value = row[metric.key];
  if (value === null || value === undefined || value === "") return null;
  return value;
}

function numericMetricValue(metric, row) {
  const value = metricValue(metric, row);
  if (value === null) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function formatMetricValue(metric, row) {
  const value = metricValue(metric, row);
  if (value === null) return "-";
  const number = Number(value);
  switch (metric.kind) {
    case "innings":
      return formatInningsFromOuts(number);
    case "average":
      return Number.isFinite(number) ? number.toFixed(metric.digits ?? 3) : `${value}`;
    case "percent":
      return Number.isFinite(number) ? `${number.toFixed(metric.digits ?? 1)}%` : `${value}`;
    case "decimal":
      return Number.isFinite(number) ? number.toFixed(metric.digits ?? 2) : `${value}`;
    case "number":
    default:
      return Number.isFinite(number) ? number.toFixed(metric.digits ?? 0) : `${value}`;
  }
}

function formatNumber(value, digits = 0) {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : `${value}`;
}

function formatPercentValue(value, digits = 1) {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(digits)}%` : `${value}`;
}

function formatAverageValue(value) {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(3) : `${value}`;
}

function formatSpeedValue(value) {
  if (value === null || value === undefined || value === "" || value === "-") return "-";
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(1)}km/h` : `${value}`;
}

function formatMetricDelta(metric, delta) {
  if (delta === null || delta === undefined) return "差分なし";
  if (metric.kind === "innings") return formatSignedInnings(delta);
  const sign = delta > 0 ? "+" : "";
  if (metric.kind === "number") return `${sign}${delta.toFixed(0)}`;
  if (metric.kind === "average") return `${sign}${delta.toFixed(metric.digits ?? 3)}`;
  if (metric.kind === "percent") return `${sign}${delta.toFixed(metric.digits ?? 1)}%`;
  return `${sign}${delta.toFixed(metric.digits ?? 2)}`;
}

function comparisonDirection(metric, delta) {
  if (delta === null || delta === undefined) return "flat";
  if (delta === 0) return "flat";
  const improved = metric.lowerIsBetter ? delta < 0 : delta > 0;
  return improved ? "up" : "down";
}

function currentParams() {
  return new URLSearchParams(window.location.search);
}

function seasonLabel(row, fallback = "データなし") {
  if (!row?.year) return fallback;
  return `${row.year}年度`;
}

function normalizePlayerName(value) {
  return `${value ?? ""}`
    .normalize("NFKC")
    .replaceAll(/[\s\u3000]+/g, "");
}

function rowMatchesPlayerName(row, player) {
  if (!player) return true;
  const rowPlayer = row?.player ?? "";
  return rowPlayer === player || normalizePlayerName(rowPlayer) === normalizePlayerName(player);
}

function findCurrentRow(rows, params, config) {
  const year = params.get("year") || "";
  const player = params.get("player") || "";
  const team = params.get("team") || "";
  const playerId = params.get("playerId") || "";
  const scopedRows = rows.filter((row) => {
    if (year && row.year !== year) return false;
    if (!rowMatchesPlayerName(row, player)) return false;
    return true;
  });
  if (playerId) {
    const byId = scopedRows.find((row) => (row[config.idKey] || "") === playerId);
    if (byId) return byId;
  }
  if (team) {
    const byTeam = scopedRows.find((row) => row.team === team);
    if (byTeam) return byTeam;
  }
  return scopedRows[0] || null;
}

function findPreviousRow(rows, currentRow, params, config) {
  if (!currentRow) return null;
  const previousYear = `${Math.max(Number.parseInt(currentRow.year || "0", 10) - 1, 0)}`;
  if (!previousYear || previousYear === "0") return null;
  const playerId = currentRow[config.idKey] || params.get("playerId") || "";
  const candidates = rows.filter((row) => row.year === previousYear && rowMatchesPlayerName(row, currentRow.player));
  if (!candidates.length) return null;
  if (playerId) {
    const byId = candidates.find((row) => (row[config.idKey] || "") === playerId);
    if (byId) return byId;
  }
  const requestedTeam = params.get("team") || currentRow.team || "";
  if (requestedTeam) {
    const byTeam = candidates.find((row) => row.team === requestedTeam);
    if (byTeam) return byTeam;
  }
  return candidates[0];
}

function summaryItems(config, row) {
  if (!row) return [];
  if (config === TYPE_CONFIG.pitcher) {
    return [
      ["チーム", row.team],
      ["リーグ", row.league || "-"],
      ["試合", `${row.games ?? "-"}試合`],
      ["投球回", row.innings || formatInningsFromOuts(row.inningsOuts)],
      ["防御率", formatMetricValue(metricMap(config).era, row)],
      ["WHIP", formatMetricValue(metricMap(config).whip, row)],
    ];
  }
  return [
    ["チーム", row.team],
    ["リーグ", row.league || "-"],
    ["試合", `${row.games ?? "-"}試合`],
    ["打席", `${row.plateAppearances ?? "-"}打席`],
    ["打率", formatMetricValue(metricMap(config).battingAverage, row)],
    ["OPS", formatMetricValue(metricMap(config).ops, row)],
  ];
}

function renderSeasonCard(row, config, heading, emptyMessage = "データがありません。") {
  if (!row) {
    return `
      <article class="season-meta-card compare-season-card empty">
        <span>${escapeHtml(heading)}</span>
        <strong>データなし</strong>
        <small>${escapeHtml(emptyMessage)}</small>
      </article>
    `;
  }
  const items = summaryItems(config, row)
    .map(
      ([label, value]) => `
        <div class="compare-season-item">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>
      `
    )
    .join("");
  return `
    <article class="season-meta-card compare-season-card">
      <span>${escapeHtml(heading)}</span>
      <strong>${escapeHtml(row.team)}</strong>
      <small>${escapeHtml(row.year)}年度 ${escapeHtml(config.label)}</small>
      <div class="compare-season-list">${items}</div>
    </article>
  `;
}

function safeDivide(numerator, denominator, multiplier = 1) {
  const safeNumerator = Number(numerator);
  const safeDenominator = Number(denominator);
  if (!Number.isFinite(safeNumerator) || !Number.isFinite(safeDenominator) || safeDenominator === 0) {
    return null;
  }
  return (safeNumerator / safeDenominator) * multiplier;
}

function monthNumberFromSplit(split) {
  const rawMonth = `${split?.month ?? ""}`;
  const isoMatch = rawMonth.match(/-(\d{2})$/);
  if (isoMatch) return isoMatch[1];
  const labelMatch = `${split?.monthLabel ?? ""}`.match(/(\d{1,2})月/);
  if (labelMatch) return labelMatch[1].padStart(2, "0");
  return "";
}

function sumMetric(rows, key) {
  return rows.reduce((total, row) => total + (Number(row?.[key]) || 0), 0);
}

function weightedAverage(rows, key, weightKey) {
  const weighted = rows.reduce((total, row) => {
    const value = Number(row?.[key]);
    const weight = Number(row?.[weightKey]);
    if (!Number.isFinite(value) || !Number.isFinite(weight) || weight <= 0) return total;
    return total + (value * weight);
  }, 0);
  const totalWeight = rows.reduce((total, row) => {
    const weight = Number(row?.[weightKey]);
    return Number.isFinite(weight) && weight > 0 ? total + weight : total;
  }, 0);
  return totalWeight > 0 ? weighted / totalWeight : null;
}

function aggregatePitcherBucket(rows, bucket) {
  const latestRow = rows[rows.length - 1] || rows[0] || null;
  if (!latestRow) return null;
  const inningsOuts = sumMetric(rows, "inningsOuts");
  const outEventTotal = sumMetric(rows, "grounders") + sumMetric(rows, "flyBalls");
  const fipConstant = rows.find((row) => Number.isFinite(Number(row?.fipConstant)))?.fipConstant ?? latestRow.fipConstant ?? null;
  const atBats = sumMetric(rows, "atBats");
  const hits = sumMetric(rows, "hits");
  const walks = sumMetric(rows, "walks");
  const unintentionalWalks = sumMetric(rows, "unintentionalWalks");
  const strikeouts = sumMetric(rows, "strikeouts");
  const homeRuns = sumMetric(rows, "homeRuns");
  const hitByPitch = sumMetric(rows, "hitByPitch");
  const pitches = sumMetric(rows, "pitches");
  const hasPitchCount = rows.some((row) => Boolean(row?.hasPitchCount));
  const flyBalls = sumMetric(rows, "flyBalls");
  const grounders = sumMetric(rows, "grounders");
  const teams = [...new Set(rows.flatMap((row) => (Array.isArray(row?.teams) ? row.teams : [row?.team]).filter(Boolean)))];
  const era = safeDivide(sumMetric(rows, "earnedRuns"), inningsOuts, 27);
  const whip = safeDivide(hits + walks, inningsOuts, 3);
  const kPer9 = safeDivide(strikeouts, inningsOuts, 27);
  const bbPer9 = safeDivide(walks, inningsOuts, 27);
  const hPer9 = safeDivide(hits, inningsOuts, 27);
  const hrPer9 = safeDivide(homeRuns, inningsOuts, 27);
  const kBb = safeDivide(strikeouts, walks);
  const battingAverageAllowed = safeDivide(hits, atBats);
  const goFo = safeDivide(grounders, flyBalls);
  const groundOutRate = safeDivide(grounders, outEventTotal, 100);
  const flyOutRate = safeDivide(flyBalls, outEventTotal, 100);
  const whiffRate = hasPitchCount ? safeDivide(sumMetric(rows, "swingMisses"), pitches, 100) : null;
  const fip =
    inningsOuts && Number.isFinite(Number(fipConstant))
      ? (((13 * homeRuns) + (3 * (unintentionalWalks + hitByPitch)) - (2 * strikeouts)) / (inningsOuts / 3)) + Number(fipConstant)
      : null;

  return {
    ...latestRow,
    month: bucket.key,
    monthLabel: bucket.label,
    team: latestRow.team,
    teams,
    games: sumMetric(rows, "games"),
    wins: sumMetric(rows, "wins"),
    losses: sumMetric(rows, "losses"),
    saves: sumMetric(rows, "saves"),
    holds: sumMetric(rows, "holds"),
    innings: formatInningsFromOuts(inningsOuts),
    inningsOuts,
    batters: sumMetric(rows, "batters"),
    pitches,
    hasPitchCount,
    hits,
    homeRuns,
    strikeouts,
    walks,
    unintentionalWalks,
    intentionalWalks: sumMetric(rows, "intentionalWalks"),
    hitByPitch,
    balks: sumMetric(rows, "balks"),
    runs: sumMetric(rows, "runs"),
    earnedRuns: sumMetric(rows, "earnedRuns"),
    atBats,
    singles: sumMetric(rows, "singles"),
    doubles: sumMetric(rows, "doubles"),
    triples: sumMetric(rows, "triples"),
    grounders,
    flyBalls,
    swingMisses: sumMetric(rows, "swingMisses"),
    lookingStrikeouts: sumMetric(rows, "lookingStrikeouts"),
    swingingStrikeouts: sumMetric(rows, "swingingStrikeouts"),
    sacrificeBunts: sumMetric(rows, "sacrificeBunts"),
    interference: sumMetric(rows, "interference"),
    era,
    whip,
    kPer9,
    bbPer9,
    hPer9,
    hrPer9,
    kBb,
    fip,
    fipConstant: Number.isFinite(Number(fipConstant)) ? Number(fipConstant) : null,
    battingAverageAllowed,
    goFo,
    groundOutRate,
    flyOutRate,
    whiffRate,
  };
}

function aggregateBatterBucket(rows, bucket) {
  const latestRow = rows[rows.length - 1] || rows[0] || null;
  if (!latestRow) return null;
  const atBats = sumMetric(rows, "atBats");
  const hits = sumMetric(rows, "hits");
  const walks = sumMetric(rows, "walks");
  const hitByPitch = sumMetric(rows, "hitByPitch");
  const sacFlies = sumMetric(rows, "sacFlies");
  const strikeouts = sumMetric(rows, "strikeouts");
  const homeRuns = sumMetric(rows, "homeRuns");
  const singles = sumMetric(rows, "singles");
  const doubles = sumMetric(rows, "doubles");
  const triples = sumMetric(rows, "triples");
  const totalBases = singles + (2 * doubles) + (3 * triples) + (4 * homeRuns);
  const battingAverage = safeDivide(hits, atBats);
  const onBasePercentage = safeDivide(hits + walks + hitByPitch, atBats + walks + hitByPitch + sacFlies);
  const sluggingPercentage = safeDivide(totalBases, atBats);
  const isoDiscipline =
    battingAverage !== null && onBasePercentage !== null ? onBasePercentage - battingAverage : null;
  const isoPower =
    battingAverage !== null && sluggingPercentage !== null ? sluggingPercentage - battingAverage : null;
  const babip = safeDivide(hits - homeRuns, atBats - strikeouts - homeRuns + sacFlies);
  const ops = onBasePercentage !== null && sluggingPercentage !== null ? onBasePercentage + sluggingPercentage : null;
  const teams = [...new Set(rows.flatMap((row) => (Array.isArray(row?.teams) ? row.teams : [row?.team]).filter(Boolean)))];

  return {
    ...latestRow,
    month: bucket.key,
    monthLabel: bucket.label,
    team: latestRow.team,
    teams,
    games: sumMetric(rows, "games"),
    plateAppearances: sumMetric(rows, "plateAppearances"),
    atBats,
    runs: sumMetric(rows, "runs"),
    hits,
    singles,
    doubles,
    triples,
    homeRuns,
    runsBattedIn: sumMetric(rows, "runsBattedIn"),
    walks,
    unintentionalWalks: sumMetric(rows, "unintentionalWalks"),
    intentionalWalks: sumMetric(rows, "intentionalWalks"),
    hitByPitch,
    sacBunts: sumMetric(rows, "sacBunts"),
    sacFlies,
    steals: sumMetric(rows, "steals"),
    strikeouts,
    battingAverage,
    onBasePercentage,
    isoDiscipline,
    sluggingPercentage,
    isoPower,
    babip,
    ops,
    wrc: sumMetric(rows, "wrc"),
    wrcPlus: weightedAverage(rows, "wrcPlus", "plateAppearances"),
    parkFactor: weightedAverage(rows, "parkFactor", "plateAppearances"),
    effectiveParkFactor: weightedAverage(rows, "effectiveParkFactor", "plateAppearances"),
  };
}

function monthlySplits() {
  const splits = Array.isArray(state.currentRow?.monthlySplits) ? state.currentRow.monthlySplits : [];
  if (!splits.length) return [];
  const bucketRows = new Map();
  const fallbackRows = [];

  for (const split of splits) {
    const month = monthNumberFromSplit(split);
    const bucket = MONTH_BUCKET_INDEX.get(month);
    if (!bucket) {
      fallbackRows.push({
        key: split.month || month || `${fallbackRows.length}`,
        label: split.monthLabel || `${Number.parseInt(month || "0", 10) || month}月`,
        rows: [split],
        order: MONTH_BUCKETS.length + fallbackRows.length,
      });
      continue;
    }
    const entry = bucketRows.get(bucket.key) || { ...bucket, rows: [], order: MONTH_BUCKETS.findIndex((item) => item.key === bucket.key) };
    entry.rows.push(split);
    bucketRows.set(bucket.key, entry);
  }

  const grouped = [...bucketRows.values(), ...fallbackRows]
    .sort((a, b) => a.order - b.order)
    .map((bucket) =>
      state.config === TYPE_CONFIG.pitcher
        ? aggregatePitcherBucket(bucket.rows, bucket)
        : aggregateBatterBucket(bucket.rows, bucket)
    )
    .filter(Boolean);

  return grouped;
}

function seasonDashboard() {
  return state.currentRow?.seasonDashboard || null;
}

function rowHits(row) {
  return (
    (Number(row?.singles) || 0)
    + (Number(row?.doubles) || 0)
    + (Number(row?.triples) || 0)
    + (Number(row?.homeRuns) || 0)
  );
}

function normalizeMatchupTeam(value) {
  const trimmed = `${value || ""}`.trim();
  return MATCHUP_TEAM_NAMES[trimmed] || trimmed;
}

function opponentLabel(row) {
  const matchup = `${row?.matchup || ""}`.replace("vs.", "vs");
  const teams = matchup.split("vs").map(normalizeMatchupTeam).filter(Boolean);
  const ownTeams = new Set(
    [
      row?.team,
      state.currentRow?.team,
      ...(Array.isArray(state.currentRow?.teams) ? state.currentRow.teams : []),
    ]
      .flatMap((team) => `${team || ""}`.split(" / "))
      .map(normalizeMatchupTeam)
      .filter(Boolean)
  );
  const opponent = teams.find((team) => !ownTeams.has(team));
  return opponent ? `vs${opponent}` : matchup || "-";
}

function seasonStackBar(rows, labelKey = "pitchType") {
  const visibleRows = (rows || []).filter((row) => (Number(row?.count) || 0) > 0);
  if (!visibleRows.length) return '<div class="section-empty compare-empty">データなし</div>';
  return `
    <div class="stack-bar season-stack-bar">
      ${visibleRows
        .map((row) => {
          const ratio = Math.max(Number(row.ratio) || 0, 0);
          const label = ratio >= 30 ? `${row[labelKey] || row.label || ""} ${ratio.toFixed(1)}%` : "";
          return `
            <span
              class="stack-segment"
              style="width:${ratio}%; background:${escapeHtml(row.color || "#0F2340")};"
              title="${escapeHtml(row[labelKey] || row.label || "")} ${ratio.toFixed(1)}%"
            >
              ${escapeHtml(label)}
            </span>
          `;
        })
        .join("")}
    </div>
  `;
}

function polarToCartesian(cx, cy, radius, angle) {
  const radians = ((angle - 90) * Math.PI) / 180;
  return {
    x: cx + (radius * Math.cos(radians)),
    y: cy + (radius * Math.sin(radians)),
  };
}

function pieSlicePath(cx, cy, radius, startAngle, endAngle) {
  const start = polarToCartesian(cx, cy, radius, endAngle);
  const end = polarToCartesian(cx, cy, radius, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
  return [
    `M ${cx} ${cy}`,
    `L ${start.x.toFixed(2)} ${start.y.toFixed(2)}`,
    `A ${radius} ${radius} 0 ${largeArcFlag} 0 ${end.x.toFixed(2)} ${end.y.toFixed(2)}`,
    "Z",
  ].join(" ");
}

function seasonPieChart(rows, labelKey = "label") {
  const visibleRows = (rows || []).filter((row) => (Number(row?.count) || 0) > 0);
  const total = visibleRows.reduce((sum, row) => sum + (Number(row.count) || 0), 0);
  if (!visibleRows.length || !total) return '<div class="section-empty compare-empty">データなし</div>';

  const cx = 150;
  const cy = 150;
  const radius = 122;
  let cursor = 0;
  const slices = visibleRows
    .map((row) => {
      const count = Number(row.count) || 0;
      const ratio = (count / total) * 100;
      const angle = (count / total) * 360;
      const startAngle = cursor;
      const endAngle = cursor + angle;
      cursor = endAngle;
      const labelPoint = polarToCartesian(cx, cy, radius * 0.62, startAngle + (angle / 2));
      if (visibleRows.length === 1) {
        return `
          <circle cx="${cx}" cy="${cy}" r="${radius}" fill="${escapeHtml(row.color || "#0F2340")}" />
          <text x="${cx}" y="${cy}" class="season-pie-label">${formatPercentValue(100, 1)}</text>
        `;
      }
      return `
        <path
          d="${pieSlicePath(cx, cy, radius, startAngle, endAngle)}"
          fill="${escapeHtml(row.color || "#0F2340")}"
        >
          <title>${escapeHtml(row[labelKey] || row.pitchType || row.label || "")} ${formatPercentValue(ratio, 1)}</title>
        </path>
        ${
          ratio >= 6
            ? `<text x="${labelPoint.x.toFixed(2)}" y="${labelPoint.y.toFixed(2)}" class="season-pie-label">${formatPercentValue(ratio, 1)}</text>`
            : ""
        }
      `;
    })
    .join("");

  return `
    <div class="season-pie-shell">
      <svg class="season-pie-chart" viewBox="0 0 300 300" role="img" aria-label="割合グラフ">
        ${slices}
      </svg>
    </div>
  `;
}

function seasonPitchCards(rows) {
  const visibleRows = (rows || []).filter((row) => (Number(row?.count) || 0) > 0).slice(0, 8);
  if (!visibleRows.length) return "";
  return `
    <div class="pitch-card-grid season-pitch-grid">
      ${visibleRows
        .map(
          (row) => `
            <article class="pitch-card">
              <div class="pitch-card-head">
                <span class="legend-swatch" style="background:${escapeHtml(row.color || "#0F2340")}"></span>
                <strong>${escapeHtml(row.pitchType)}</strong>
              </div>
              <div class="pitch-card-metrics">
                <span>${formatNumber(row.count)}球</span>
                <span>${formatPercentValue(row.ratio)}</span>
                <span>平均 ${formatSpeedValue(row.avgSpeed)}</span>
                <span>空振率 ${formatPercentValue(row.whiff)}</span>
              </div>
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

function renderSeasonPitchMix(dashboard) {
  const rows = dashboard?.pitchMix || [];
  return `
    <article class="dashboard-card season-card-wide">
      <div class="card-head">
        <h3>球種比率</h3>
        <span class="result-count">${formatNumber(dashboard?.totalPitches)}球</span>
      </div>
      ${seasonStackBar(rows)}
      ${seasonPitchCards(rows)}
    </article>
  `;
}

function renderSeasonPitchSummary(dashboard) {
  const rows = (dashboard?.pitchMix || []).filter((row) => (Number(row?.count) || 0) > 0);
  if (!rows.length) {
    return `
      <article class="dashboard-card">
        <div class="card-head"><h3>球種サマリ</h3></div>
        <div class="section-empty compare-empty">データなし</div>
      </article>
    `;
  }
  const body = rows
    .map(
      (row) => `
        <tr>
          <td><span class="pitch-name-cell"><span class="legend-swatch" style="background:${escapeHtml(row.color || "#0F2340")}"></span>${escapeHtml(row.pitchType)}</span></td>
          <td>${formatNumber(row.count)}</td>
          <td>${formatPercentValue(row.ratio)}</td>
          <td>${formatSpeedValue(row.avgSpeed)}</td>
          <td>${formatSpeedValue(row.maxSpeed)}</td>
          <td>${formatNumber(row.whiffCount)}</td>
          <td>${formatPercentValue(row.whiff)}</td>
          <td>${formatNumber(row.atBats)}</td>
          <td>${formatNumber(rowHits(row))}</td>
          <td>${formatNumber(row.homeRuns)}</td>
          <td>${formatNumber(row.grounders)}</td>
          <td>${formatNumber(row.flyBalls)}</td>
          <td>${formatNumber(row.strikeouts)}</td>
          <td>${formatAverageValue(row.hitRate)}</td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="dashboard-card season-card-wide">
      <div class="card-head"><h3>球種サマリ</h3></div>
      <div class="table-scroll">
        <table class="data-table season-table season-pitch-summary-table">
          <thead>
            <tr>
              <th>球種</th><th>球数</th><th>割合</th><th>平均</th><th>最速</th><th>空振</th><th>空振率</th>
              <th>被打数</th><th>被安打</th><th>被本</th><th>ゴロ</th><th>フライ</th><th>三振</th><th>被打率</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    </article>
  `;
}

function renderSeasonInningSummary(dashboard) {
  const rows = dashboard?.inningRows || [];
  if (!rows.some((row) => (Number(row?.count) || 0) > 0)) {
    return `
      <article class="dashboard-card">
        <div class="card-head"><h3>イニング別サマリ</h3></div>
        <div class="section-empty compare-empty">データなし</div>
      </article>
    `;
  }
  const body = rows
    .map(
      (row) => `
        <tr>
          <td>${escapeHtml(row.inning)}</td>
          <td>${formatNumber(row.count)}</td>
          <td>${formatSpeedValue(row.avgSpeed)}</td>
          <td>${formatSpeedValue(row.maxSpeed)}</td>
          <td>${formatNumber(row.whiffCount)}</td>
          <td>${formatPercentValue(row.whiff)}</td>
          <td>${formatNumber(row.atBats)}</td>
          <td>${formatNumber(rowHits(row))}</td>
          <td>${formatNumber(row.homeRuns)}</td>
          <td>${formatNumber(row.grounders)}</td>
          <td>${formatNumber(row.flyBalls)}</td>
          <td>${formatNumber(row.strikeouts)}</td>
          <td>${formatAverageValue(row.hitRate)}</td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="dashboard-card season-card-wide">
      <div class="card-head"><h3>イニング別サマリ</h3></div>
      <div class="table-scroll">
        <table class="data-table season-table season-inning-table">
          <thead>
            <tr>
              <th>回</th><th>球数</th><th>平均</th><th>最速</th><th>空振</th><th>空振率</th>
              <th>被打数</th><th>被安打</th><th>被本</th><th>ゴロ</th><th>フライ</th><th>三振</th><th>被打率</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    </article>
  `;
}

function renderSeasonOutcomes(dashboard) {
  const outcomes = dashboard?.outcomes || {};
  const rows = outcomes.rows || [];
  if (!rows.some((row) => (Number(row?.count) || 0) > 0)) {
    return `
      <article class="dashboard-card">
        <div class="card-head"><h3>アウト内容</h3></div>
        <div class="section-empty compare-empty">データなし</div>
      </article>
    `;
  }
  return `
    <article class="dashboard-card">
      <div class="card-head">
        <h3>アウト内容</h3>
        <span class="result-count">${formatNumber(outcomes.total)}件</span>
      </div>
      ${seasonPieChart(rows, "label")}
      <div class="season-outcome-grid">
        ${rows
          .map(
            (row) => `
              <div class="outcome-item">
                <div class="outcome-item-head">
                  <span class="legend-swatch" style="background:${escapeHtml(row.color || "#0F2340")}"></span>
                  <strong>${escapeHtml(row.label)}</strong>
                </div>
                <div class="outcome-item-values">
                  <span>${formatNumber(row.count)}件</span>
                  <span>${formatPercentValue(row.ratio)}</span>
                </div>
              </div>
            `
          )
          .join("")}
      </div>
    </article>
  `;
}

function renderSeasonFinish(dashboard) {
  const finish = dashboard?.finish || {};
  const rows = (finish.rows || []).filter((row) => (Number(row?.count) || 0) > 0);
  if (!rows.length) {
    return `
      <article class="dashboard-card">
        <div class="card-head"><h3>決め球サマリ</h3></div>
        <div class="section-empty compare-empty">データなし</div>
      </article>
    `;
  }
  const body = rows
    .map(
      (row) => `
        <tr>
          <td><span class="pitch-name-cell"><span class="legend-swatch" style="background:${escapeHtml(row.color || "#0F2340")}"></span>${escapeHtml(row.pitchType)}</span></td>
          <td>${formatNumber(row.count)}</td>
          <td>${formatPercentValue(row.ratio)}</td>
          <td>${formatNumber(row.looking)}</td>
          <td>${formatNumber(row.swinging)}</td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="dashboard-card">
      <div class="card-head">
        <h3>決め球サマリ</h3>
        <span class="result-count">${formatNumber(finish.total)}件</span>
      </div>
      ${seasonPieChart(rows, "pitchType")}
      <div class="table-scroll">
        <table class="data-table season-table">
          <thead><tr><th>球種</th><th>三振</th><th>割合</th><th>見逃し</th><th>空振り</th></tr></thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    </article>
  `;
}

function renderRecentGames(dashboard) {
  const rows = dashboard?.recentGames || [];
  if (!rows.length) {
    return `
      <article class="dashboard-card season-card-wide">
        <div class="card-head"><h3>最近6試合の成績</h3></div>
        <div class="section-empty compare-empty">データなし</div>
      </article>
    `;
  }
  const body = rows
    .map(
      (row) => `
        <tr>
          <td>${escapeHtml(row.date)}</td>
          <td class="season-matchup-cell">${escapeHtml(opponentLabel(row))}</td>
          <td>${escapeHtml(row.innings)}</td>
          <td>${formatNumber(row.pitches)}</td>
          <td>${formatNumber(row.batters)}</td>
          <td>${formatNumber(row.hits)}</td>
          <td>${formatNumber(row.homeRuns)}</td>
          <td>${formatNumber(row.strikeouts)}</td>
          <td>${formatNumber(row.walks)}</td>
          <td>${formatNumber(row.runs)}</td>
          <td>${formatNumber(row.earnedRuns)}</td>
          <td>${formatNumber(row.gameEra, 2)}</td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="dashboard-card season-card-wide">
      <div class="card-head"><h3>最近6試合の成績</h3></div>
      <div class="table-scroll">
        <table class="data-table season-table recent-game-table">
          <thead>
            <tr>
              <th>日付</th><th>カード</th><th>投球回</th><th>球数</th><th>打者</th><th>被安打</th>
              <th>被本</th><th>奪三振</th><th>与四球</th><th>失点</th><th>自責</th><th>防御率</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    </article>
  `;
}

const BATTER_SEASON_SECTIONS = [
  ["byOpponent", "対チーム別打撃成績"],
  ["byStadium", "球場別打撃成績"],
  ["byPitchType", "球種別打撃成績"],
  ["byVelocity", "球速別打撃成績"],
  ["byPitcherHand", "対左右別打撃成績"],
  ["byBattingOrder", "打順別打撃成績"],
  ["byPlateAppearance", "打席別打撃成績"],
  ["byStrikeCount", "カウント別打撃成績"],
];

function batterSplitLabel(sectionKey, row) {
  const label = row?.label || "-";
  if (sectionKey === "byPitcherHand") {
    if (label === "右") return "右投手";
    if (label === "左") return "左投手";
  }
  if (sectionKey === "byOpponent" && label !== "-") {
    return `vs${label}`;
  }
  return label;
}

function renderBatterSplitTable(sectionKey, title, rows = []) {
  const visibleRows = rows.filter((row) => (Number(row?.plateAppearances) || 0) > 0);
  if (!visibleRows.length) {
    return `
      <article class="dashboard-card season-card-wide">
        <div class="card-head"><h3>${escapeHtml(title)}</h3></div>
        <div class="section-empty compare-empty">データなし</div>
      </article>
    `;
  }
  const body = visibleRows
    .map(
      (row) => `
        <tr>
          <td>${escapeHtml(batterSplitLabel(sectionKey, row))}</td>
          <td>${formatNumber(row.plateAppearances)}</td>
          <td>${formatNumber(row.atBats)}</td>
          <td>${formatNumber(row.hits)}</td>
          <td>${formatNumber(row.doubles)}</td>
          <td>${formatNumber(row.triples)}</td>
          <td>${formatNumber(row.homeRuns)}</td>
          <td>${formatNumber(row.walks)}</td>
          <td>${formatNumber(row.hitByPitch)}</td>
          <td>${formatNumber(row.sacBunts)}</td>
          <td>${formatNumber(row.sacFlies)}</td>
          <td>${formatNumber(row.strikeouts)}</td>
          <td>${formatAverageValue(row.battingAverage)}</td>
          <td>${formatAverageValue(row.onBasePercentage)}</td>
          <td>${formatAverageValue(row.sluggingPercentage)}</td>
          <td>${formatAverageValue(row.ops)}</td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="dashboard-card season-card-wide">
      <div class="card-head"><h3>${escapeHtml(title)}</h3></div>
      <div class="table-scroll">
        <table class="data-table season-table batter-season-table">
          <thead>
            <tr>
              <th>区分</th><th>打席</th><th>打数</th><th>安打</th><th>二塁打</th><th>三塁打</th><th>本塁打</th>
              <th>四球</th><th>死球</th><th>犠打</th><th>犠飛</th><th>三振</th><th>打率</th><th>出塁率</th><th>長打率</th><th>OPS</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    </article>
  `;
}

function renderBatterSeasonPanel(dashboard) {
  return `
    <div class="season-detail-grid">
      ${BATTER_SEASON_SECTIONS
        .map(([key, title]) => renderBatterSplitTable(key, title, dashboard?.[key] || []))
        .join("")}
    </div>
  `;
}

function renderPitcherSeasonPanel(dashboard) {
  return `
    <div class="season-detail-grid">
      ${renderSeasonPitchMix(dashboard)}
      ${renderSeasonPitchSummary(dashboard)}
      ${renderSeasonInningSummary(dashboard)}
      ${renderSeasonOutcomes(dashboard)}
      ${renderSeasonFinish(dashboard)}
      ${renderRecentGames(dashboard)}
    </div>
  `;
}

function renderSeasonPanel() {
  const dashboard = seasonDashboard();
  els.seasonMetricCount.textContent = dashboard
    ? state.config === TYPE_CONFIG.pitcher
      ? `${formatNumber(dashboard.totalPitches)}球`
      : `${formatNumber(dashboard.totalPlateAppearances)}打席`
    : state.config === TYPE_CONFIG.pitcher
      ? "0球"
      : "0打席";
  if (!state.currentRow) {
    els.seasonDetailWrap.innerHTML = `<div class="section-empty compare-empty">${escapeHtml(state.error || "選手データを読み込めませんでした。")}</div>`;
    return;
  }
  if (!dashboard) {
    els.seasonDetailWrap.innerHTML = '<div class="section-empty compare-empty">この年度の一球データ集計はありません。</div>';
    return;
  }
  els.seasonDetailWrap.innerHTML =
    state.config === TYPE_CONFIG.pitcher
      ? renderPitcherSeasonPanel(dashboard)
      : renderBatterSeasonPanel(dashboard);
}

function renderModeToggles() {
  const modes = Object.entries(MODE_CONFIG);
  if (!modes.some(([mode]) => mode === state.activeMode)) {
    state.activeMode = modes[0]?.[0] || "compare";
  }
  els.modeToggleGroup.innerHTML = modes
    .map(
      ([mode, config]) => `
        <button
          type="button"
          class="compare-mode-button${state.activeMode === mode ? " active" : ""}"
          data-mode="${mode}"
        >
          ${escapeHtml(config.label)}
        </button>
      `
    )
    .join("");
  els.modeToggleGroup.querySelectorAll("[data-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      const mode = button.dataset.mode || "compare";
      state.activeMode = mode;
      renderModeToggles();
      renderPanels();
    });
  });
}

function renderMetricToggles() {
  els.metricToggleGroup.innerHTML = state.config.metrics
    .map((metric) => {
      const active = state.activeMetricKeys.includes(metric.key);
      return `
        <button
          type="button"
          class="compare-toggle${active ? " active" : ""}"
          data-metric-key="${metric.key}"
        >
          ${escapeHtml(metric.label)}
        </button>
      `;
    })
    .join("");
  els.metricToggleGroup.querySelectorAll("[data-metric-key]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.metricKey || "";
      if (!key) return;
      if (state.activeMetricKeys.includes(key)) {
        state.activeMetricKeys = state.activeMetricKeys.filter((item) => item !== key);
      } else {
        state.activeMetricKeys = [...state.activeMetricKeys, key];
      }
      renderMetricToggles();
      renderPanels();
    });
  });
}

function compareCardsMarkup() {
  if (!state.currentRow) {
    return `<div class="section-empty compare-empty">${escapeHtml(state.error || "選手データを読み込めませんでした。")}</div>`;
  }
  if (!state.activeMetricKeys.length) {
    return '<div class="section-empty compare-empty">比較したい指標を選択してください。</div>';
  }
  const metricsByKey = metricMap(state.config);
  return state.activeMetricKeys
    .map((key) => metricsByKey[key])
    .filter(Boolean)
    .map((metric) => {
      const leftValue = numericMetricValue(metric, state.previousRow);
      const rightValue = numericMetricValue(metric, state.currentRow);
      const delta = leftValue === null || rightValue === null ? null : rightValue - leftValue;
      const direction = comparisonDirection(metric, delta);
      const deltaLabel = formatMetricDelta(metric, delta);
      const leftLabel = seasonLabel(state.previousRow, "前年データなし");
      const rightLabel = seasonLabel(state.currentRow);
      return `
        <article class="compare-card">
          <span>${escapeHtml(metric.label)}</span>
          <div class="compare-values">
            <div class="compare-value-block">
              <small class="compare-year-label">${escapeHtml(leftLabel)}</small>
              <strong>${escapeHtml(formatMetricValue(metric, state.previousRow))}</strong>
            </div>
            <span class="compare-arrow compare-arrow--${direction}">${direction === "up" ? "↗" : direction === "down" ? "↘" : "→"}</span>
            <div class="compare-value-block">
              <small class="compare-year-label">${escapeHtml(rightLabel)}</small>
              <strong>${escapeHtml(formatMetricValue(metric, state.currentRow))}</strong>
            </div>
          </div>
          <p class="compare-delta compare-delta--${direction}">${escapeHtml(deltaLabel)}</p>
        </article>
      `;
    })
    .join("");
}

function chartSvg(metric, splits) {
  const width = 360;
  const height = 180;
  const padding = { top: 18, right: 16, bottom: 34, left: 42 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const points = splits
    .map((row, index) => ({
      index,
      label: row.monthLabel || row.month || `${index + 1}`,
      value: numericMetricValue(metric, row),
    }))
    .filter((point) => point.value !== null);

  if (!points.length) {
    return '<div class="section-empty compare-empty monthly-chart-empty">データなし</div>';
  }

  let min = Math.min(...points.map((point) => point.value));
  let max = Math.max(...points.map((point) => point.value));
  if (min === max) {
    const margin = metric.kind === "number" ? 1 : 0.1;
    min -= margin;
    max += margin;
  }

  const xStep = points.length > 1 ? plotWidth / (points.length - 1) : 0;
  const yScale = (value) => padding.top + ((max - value) / (max - min || 1)) * plotHeight;
  const xScale = (index) => padding.left + (xStep * index);
  const pathData = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${xScale(index).toFixed(2)} ${yScale(point.value).toFixed(2)}`)
    .join(" ");

  const xLabels = points
    .map(
      (point, index) => `
        <text x="${xScale(index).toFixed(2)}" y="${height - 10}" text-anchor="middle" class="monthly-chart-axis-label">
          ${escapeHtml(point.label)}
        </text>
      `
    )
    .join("");
  const circles = points
    .map(
      (point, index) => `
        <g>
          <circle cx="${xScale(index).toFixed(2)}" cy="${yScale(point.value).toFixed(2)}" r="4.5" class="monthly-chart-point" />
          <text x="${xScale(index).toFixed(2)}" y="${(yScale(point.value) - 10).toFixed(2)}" text-anchor="middle" class="monthly-chart-point-label">
            ${escapeHtml(formatMetricValue(metric, { [metric.key]: point.value, inningsOuts: point.value }))}
          </text>
        </g>
      `
    )
    .join("");

  return `
    <svg class="monthly-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(metric.label)}の月別推移">
      <line x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${height - padding.bottom}" class="monthly-chart-axis" />
      <line x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}" class="monthly-chart-axis" />
      <text x="${padding.left - 8}" y="${padding.top + 4}" text-anchor="end" class="monthly-chart-range-label">${escapeHtml(formatMetricValue(metric, { [metric.key]: max, inningsOuts: max }))}</text>
      <text x="${padding.left - 8}" y="${height - padding.bottom + 4}" text-anchor="end" class="monthly-chart-range-label">${escapeHtml(formatMetricValue(metric, { [metric.key]: min, inningsOuts: min }))}</text>
      <path d="${pathData}" class="monthly-chart-line" />
      ${circles}
      ${xLabels}
    </svg>
  `;
}

function renderMonthlyTable(splits) {
  if (!state.currentRow) {
    els.monthlyTableWrap.innerHTML = `<div class="section-empty compare-empty">${escapeHtml(state.error || "選手データを読み込めませんでした。")}</div>`;
    return;
  }
  if (!splits.length) {
    els.monthlyTableWrap.innerHTML = '<div class="section-empty compare-empty">この年度の月別データはありません。</div>';
    return;
  }
  const visibleMetrics = state.config.metrics.filter((metric) => {
    if (state.config === TYPE_CONFIG.pitcher && metric.key === "pitches") {
      return splits.some((split) => split.hasPitchCount);
    }
    return true;
  });
  const headers = visibleMetrics
    .map((metric) => `<th>${escapeHtml(metric.label)}</th>`)
    .join("");
  const rows = splits
    .map((split) => {
      const values = visibleMetrics
        .map((metric) => `<td>${escapeHtml(formatMetricValue(metric, split))}</td>`)
        .join("");
      return `<tr><th>${escapeHtml(split.monthLabel || split.month || "-")}</th>${values}</tr>`;
    })
    .join("");

  els.monthlyTableWrap.innerHTML = `
    <div class="table-scroll monthly-table-shell">
      <table class="data-table monthly-table">
        <thead>
          <tr>
            <th>月</th>
            ${headers}
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function renderMonthlyCharts(splits) {
  if (!state.currentRow) {
    els.monthlyChartGrid.innerHTML = `<div class="section-empty compare-empty">${escapeHtml(state.error || "選手データを読み込めませんでした。")}</div>`;
    return;
  }
  if (!splits.length) {
    els.monthlyChartGrid.innerHTML = '<div class="section-empty compare-empty">この年度の月別データはありません。</div>';
    return;
  }
  if (!state.activeMetricKeys.length) {
    els.monthlyChartGrid.innerHTML = '<div class="section-empty compare-empty">表示したい指標を選択してください。</div>';
    return;
  }

  const metricsByKey = metricMap(state.config);
  els.monthlyChartGrid.innerHTML = state.activeMetricKeys
    .map((key) => metricsByKey[key])
    .filter(Boolean)
    .map((metric) => {
      const latestRow = splits[splits.length - 1] || null;
      return `
        <article class="compare-card monthly-chart-card">
          <div class="monthly-chart-head">
            <span>${escapeHtml(metric.label)}</span>
            <strong>${escapeHtml(formatMetricValue(metric, latestRow))}</strong>
          </div>
          ${chartSvg(metric, splits)}
        </article>
      `;
    })
    .join("");
}

function renderComparePanel() {
  els.compareMetricCount.textContent = `${state.activeMetricKeys.length}項目`;
  els.compareSeasonGrid.innerHTML = [
    renderSeasonCard(state.previousRow, state.config, state.previousRow ? seasonLabel(state.previousRow) : "前年データなし", "前年データがありません。"),
    renderSeasonCard(state.currentRow, state.config, seasonLabel(state.currentRow, "対象年度")),
  ].join("");
  els.compareCardGrid.innerHTML = compareCardsMarkup();
}

function renderMonthlyPanel() {
  const splits = monthlySplits();
  els.monthlyMetricCount.textContent = `表 ${state.config.metrics.length}項目 / グラフ ${state.activeMetricKeys.length}項目`;
  els.monthlySeasonGrid.innerHTML = [
    renderSeasonCard(state.currentRow, state.config, seasonLabel(state.currentRow, "対象年度"), "対象年度データがありません。"),
  ].join("");
  renderMonthlyTable(splits);
  renderMonthlyCharts(splits);
}

function renderPanels() {
  const showSeason = state.activeMode === "season";
  const showCompare = state.activeMode === "compare";
  const showMonthly = state.activeMode === "monthly";
  els.metricToggleGroup.classList.toggle("is-hidden", showSeason);
  els.seasonPanel.classList.toggle("is-hidden", !showSeason);
  els.comparePanel.classList.toggle("is-hidden", !showCompare);
  els.monthlyPanel.classList.toggle("is-hidden", !showMonthly);
  renderSeasonPanel();
  renderComparePanel();
  renderMonthlyPanel();
}

function renderHeader() {
  const currentRow = state.currentRow;
  const previousRow = state.previousRow;
  els.compareEyebrow.textContent = state.config.label;
  els.compareBackLink.href = state.config.annualHref;
  els.compareBackLink.textContent = state.config.annualLabel;

  if (!currentRow) {
    els.compareTitle.textContent = "選手成績ビュー";
    els.compareSubtitle.textContent = "";
    els.comparePlayerName.textContent = "選手が見つかりません";
    els.compareDescription.textContent = state.error || "リンク条件に合う成績がありません。";
    document.title = "選手成績ビュー";
    return;
  }

  const monthlyAvailable = monthlySplits().length > 0;
  const seasonAvailable = Boolean(seasonDashboard());
  els.compareTitle.textContent = `${currentRow.player} 成績ビュー`;
  els.compareSubtitle.textContent = `${currentRow.year}年度 ${state.config.label}`;
  els.comparePlayerName.textContent = currentRow.player;
  els.compareDescription.textContent = previousRow
    ? `${seasonLabel(previousRow)}との比較、${seasonAvailable ? "年度成績" : "年度成績データなし"}、${monthlyAvailable ? `${seasonLabel(currentRow)}の月別推移` : `${seasonLabel(currentRow)}の月別データなし`}を切り替えて表示できます。`
    : `${seasonLabel(currentRow)}の成績を表示しています。${seasonAvailable ? "年度成績を表示できます。" : "この年度の一球データ集計はありません。"}${monthlyAvailable ? "月別推移も表示できます。" : "この年度の月別データはありません。"}`;
  document.title = `${currentRow.player} | 成績ビュー`;
}

async function init() {
  const params = currentParams();
  state.config = TYPE_CONFIG[params.get("type")] || TYPE_CONFIG.pitcher;
  state.activeMode = "season";
  state.activeMetricKeys = [];

  try {
    const response = await fetch(state.config.datasetUrl, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    state.rows = payload.players || [];
    state.currentRow = findCurrentRow(state.rows, params, state.config);
    state.previousRow = findPreviousRow(state.rows, state.currentRow, params, state.config);
    if (!state.currentRow) {
      state.error = "リンク先の選手データが見つかりませんでした。";
    }
  } catch (error) {
    state.error = error.message || "成績データの取得に失敗しました。";
  }

  renderHeader();
  renderModeToggles();
  renderMetricToggles();
  renderPanels();
}

init();
