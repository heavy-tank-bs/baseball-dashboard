const TYPE_CONFIG = {
  pitcher: {
    label: "投手",
    datasetUrl: "./player_totals.json?v=20260511-count",
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
      { key: "babipAllowed", label: "被BABIP", kind: "average", digits: 3, lowerIsBetter: true },
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
    datasetUrl: "./batter_totals.json?v=20260511-count",
    annualHref: "./annual-batter.html",
    annualLabel: "年度別打者成績へ戻る",
    idKey: "batterId",
    metrics: [
      { key: "games", label: "試合", kind: "number", digits: 0 },
      { key: "plateAppearances", label: "打席", kind: "number", digits: 0, default: true },
      { key: "atBats", label: "打数", kind: "number", digits: 0 },
      { key: "battingAverage", label: "打率", kind: "average", digits: 3, default: true },
      { key: "scoringPositionBattingAverage", label: "得点圏打率", kind: "average", digits: 3 },
      { key: "ballZoneSwingRate", label: "ボールゾーンスイング率", kind: "percent", digits: 1 },
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

const STADIUM_LABELS = {
  バンテリンドーム: "バンテリンD",
  バンテリンドームナゴヤ: "バンテリンD",
  マツダスタジアム: "マツダ",
  東京ドーム: "東京D",
  京セラドーム大阪: "京セラD",
  京セラD大阪: "京セラD",
};

const MONTH_BUCKETS = [
  { key: "03", label: "3月", months: ["03"] },
  { key: "04", label: "4月", months: ["04"] },
  { key: "05", label: "5月", months: ["05"] },
  { key: "06", label: "6月", months: ["06"] },
  { key: "07", label: "7月", months: ["07"] },
  { key: "08", label: "8月", months: ["08"] },
  { key: "09", label: "9月", months: ["09"] },
  { key: "10", label: "10月", months: ["10"] },
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
  comparisonMetricKeys: null,
  comparisonYear: "",
  comparisonPreset: "main",
  comparisonView: "table",
  activeMode: "compare",
  embedded: false,
  error: "",
  historical: { payload: null, loading: false, loaded: false, error: "", selectedTable: 0 },
};

const els = {
  compareEyebrow: document.getElementById("compareEyebrow"),
  compareTitle: document.getElementById("compareTitle"),
  compareSubtitle: document.getElementById("compareSubtitle"),
  comparePlayerName: document.getElementById("comparePlayerName"),
  compareDescription: document.getElementById("compareDescription"),
  compareBackLink: document.getElementById("compareBackLink"),
  comparePitcherTypeLink: document.getElementById("comparePitcherTypeLink"),
  compareBatterTypeLink: document.getElementById("compareBatterTypeLink"),
  modeToggleGroup: document.getElementById("modeToggleGroup"),
  metricToggleGroup: document.getElementById("metricToggleGroup"),
  metricControls: document.getElementById("metricControls"),
  comparisonYearSelect: document.getElementById("comparisonYearSelect"),
  seasonPanel: document.getElementById("seasonPanel"),
  seasonMetricCount: document.getElementById("seasonMetricCount"),
  seasonDetailWrap: document.getElementById("seasonDetailWrap"),
  comparePanel: document.getElementById("comparePanel"),
  compareMetricCount: document.getElementById("compareMetricCount"),
  compareSeasonGrid: document.getElementById("compareSeasonGrid"),
  compareCardGrid: document.getElementById("compareCardGrid"),
  historicalCompareNote: document.getElementById("historicalCompareNote"),
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

function renderResponsiveDataTable({ tableClass, headers, rows, mobileFirstHeader = "項目" }) {
  const desktopBody = rows
    .map((row) => `<tr><td>${row.heading}</td>${row.values.map((value) => `<td>${value}</td>`).join("")}</tr>`)
    .join("");
  const mobileHeader = rows.map((row) => `<th>${row.heading}</th>`).join("");
  const mobileBody = headers
    .slice(1)
    .map((header, index) => {
      const values = rows.map((row) => `<td>${row.values[index] ?? "-"}</td>`).join("");
      return `<tr><th scope="row">${header}</th>${values}</tr>`;
    })
    .join("");

  return `
    <div class="table-scroll responsive-table-desktop">
      <table class="data-table season-table ${tableClass}">
        <thead>
          <tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr>
        </thead>
        <tbody>${desktopBody}</tbody>
      </table>
    </div>
    <div class="table-scroll mobile-transpose-scroll">
      <table class="data-table mobile-transpose-table">
        <thead>
          <tr><th>${mobileFirstHeader}</th>${mobileHeader}</tr>
        </thead>
        <tbody>${mobileBody}</tbody>
      </table>
    </div>
  `;
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
  if (["ops", "isoDiscipline", "isoPower"].includes(metric.key) && row.atBats != null && Number(row.atBats) === 0) return null;
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

function formatPlusValue(value) {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(0) : `${value}`;
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
  if (delta === null || delta === undefined || !Number.isFinite(delta)) return "—";
  if (metric.kind === "innings") return formatSignedInnings(delta);
  const digits = metric.digits ?? (metric.kind === "number" ? 0 : 2);
  delta = Number(delta.toFixed(digits));
  const sign = delta > 0 ? "+" : "";
  if (metric.kind === "number") return `${sign}${delta.toFixed(0)}`;
  if (metric.kind === "average") return `${sign}${delta.toFixed(metric.digits ?? 3)}`;
  if (metric.kind === "percent") return `${sign}${delta.toFixed(metric.digits ?? 1)}pt`;
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

function normalizeHistoricalTeam(value) {
  const normalized = `${value ?? ""}`.normalize("NFKC").replaceAll(/[\s\u3000]+/g, "");
  return normalized === "東北楽天" ? "楽天" : normalized;
}

function findHistoricalPlayer(players, row) {
  if (!row || row.year !== "2025") return null;
  const teams = (Array.isArray(row.sourceTeams) ? row.sourceTeams : Array.isArray(row.teams) ? row.teams : [row.team])
    .map(normalizeHistoricalTeam);
  const matches = players.filter((player) => rowMatchesPlayerName(player, row.player)
    && teams.includes(normalizeHistoricalTeam(player.team)));
  const exactTeam = matches.find((player) => normalizeHistoricalTeam(player.team) === normalizeHistoricalTeam(row.team));
  return exactTeam || (matches.length === 1 ? matches[0] : null);
}

function historicalPlayerHref(row) {
  const params = new URLSearchParams({
    type: state.config === TYPE_CONFIG.pitcher ? "pitcher" : "batter",
    year: row.year,
    player: row.player,
    team: row.team,
  });
  return `./compare.html?${params.toString()}`;
}

function sourceLink(url, label) {
  if (!/^https?:\/\//i.test(`${url ?? ""}`)) return escapeHtml(label);
  return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
}

function historicalTableGroup(table) {
  const title = table.title || "";
  if (/通算|各種指標/.test(title)) return "年度成績・指標";
  if (/月別/.test(title)) return "月別";
  if (/球種|コース/.test(title)) return "球種・コース";
  if (/チーム|球場|左右/.test(title)) return "対戦相手・球場・左右";
  return "場面別・その他";
}

function historicalTables(player) {
  return (player?.tables || []).filter((table) => Array.isArray(table.headers)
    && table.headers.length && Array.isArray(table.rows) && table.rows.length);
}

function renderHistoricalTable(table) {
  if (!table) return '<p class="section-empty">この選手の条件別成績は収録されていません。</p>';
  const headerCount = table.headers.length;
  return `
    <div class="table-scroll historical-table-scroll" tabindex="0" aria-label="${escapeHtml(table.title)}。横にスクロールできます">
      <table class="data-table historical-source-table">
        <caption>${escapeHtml(table.title)}</caption>
        <thead><tr>${table.headers.map((header) => /^球種一覧/.test(table.title) && header === "四球"
          ? '<th scope="col" data-stat-help="uBB">四球（敬遠除く）</th>'
          : `<th scope="col">${escapeHtml(header)}</th>`).join("")}</tr></thead>
        <tbody>${table.rows.map((row) => `<tr>${Array.from({ length: headerCount }, (_, index) => index === 0
          ? `<th scope="row">${escapeHtml(row[index] ?? "-")}</th>`
          : `<td>${escapeHtml(row[index] ?? "-")}</td>`).join("")}</tr>`).join("")}</tbody>
      </table>
    </div>${(table.notes || []).map((note) => `<p class="historical-source-note">${escapeHtml(note)}</p>`).join("")}`;
}

function renderHistoricalAnnualSummary(row) {
  const extraMetrics = state.config === TYPE_CONFIG.pitcher
    ? [{ key: "hits", label: "被安打", kind: "number" }, { key: "runs", label: "失点", kind: "number" }, { key: "earnedRuns", label: "自責点", kind: "number" }]
    : [{ key: "runs", label: "得点", kind: "number" }, { key: "hitByPitch", label: "死球", kind: "number" }, { key: "sacBunts", label: "犠打", kind: "number" }, { key: "sacFlies", label: "犠飛", kind: "number" }];
  const metrics = [...state.config.metrics, ...extraMetrics];
  return `<article class="historical-summary-card">
    <div class="section-head"><h3>2025年度の基本成績</h3><span>${escapeHtml(row.team)}</span></div>
    <dl class="historical-stat-grid">${metrics.map((metric) => `<div><dt>${escapeHtml(metric.label)}</dt><dd>${escapeHtml(formatMetricValue(metric, row))}</dd></div>`).join("")}</dl>
  </article>`;
}

function renderHistoricalSourcePanel(row) {
  const historical = state.historical;
  if (historical.error) return '<article class="historical-source-card"><h3>2025年の条件別成績</h3><p class="section-empty">条件別成績を読み込めませんでした。ページを再読み込みしてください。</p></article>';
  if (!historical.loaded) return '<article class="historical-source-card" aria-busy="true"><h3>2025年の条件別成績</h3><p class="section-empty">条件別成績を読み込み中…</p></article>';
  const player = findHistoricalPlayer(historical.payload?.players || [], row);
  if (!player) return '<article class="historical-source-card"><h3>2025年の条件別成績</h3><p class="section-empty">この球団・選手に対応する追加データは収録されていません。</p></article>';
  const tables = historicalTables(player);
  const selectedIndex = Math.min(historical.selectedTable, Math.max(0, tables.length - 1));
  const groups = new Map();
  tables.forEach((table, index) => {
    const group = historicalTableGroup(table);
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push({ table, index });
  });
  return `<article class="historical-source-card">
    <div class="section-head"><h3>2025年の条件別成績</h3><span class="result-count">${tables.length}表</span></div>
    <p class="historical-source-note">球種別の Whiff% は、スイング数に対する空振りの割合です。</p>
    ${tables.length ? `<label class="historical-table-picker"><span>表示する成績</span><select id="historicalTableSelect" class="field-select">${[...groups].map(([group, items]) => `<optgroup label="${escapeHtml(group)}">${items.map(({ table, index }) => `<option value="${index}"${index === selectedIndex ? " selected" : ""}>${escapeHtml(table.title)}</option>`).join("")}</optgroup>`).join("")}</select></label>` : ""}
    <div id="historicalTableContent" aria-live="polite">${renderHistoricalTable(tables[selectedIndex])}</div>
  </article>`;
}

async function ensureHistoricalData() {
  const historical = state.historical;
  if (state.currentRow?.year !== "2025" || historical.loaded || historical.loading) return;
  historical.loading = true;
  try {
    const kind = state.config === TYPE_CONFIG.pitcher ? "pitchers" : "batters";
    const response = await fetch(`./nf3_2025_${kind}.json?v=20261028`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    historical.payload = await response.json();
  } catch (error) {
    historical.error = error.message || "追加データを取得できませんでした。";
  } finally {
    historical.loading = false;
    historical.loaded = true;
    renderSeasonPanel();
    postEmbedHeight();
  }
}

function seasonPlayerId(row, config) {
  return `${row?.[config.idKey] ?? ""}`.trim();
}

function officialPlayerId(row) {
  return `${row?.npbUrl ?? ""}`.match(/\/bis\/players\/(\d+)\.html(?:[?#].*)?$/)?.[1] || "";
}

function rowTeamNames(row) {
  return [...new Set([row?.team, ...(row?.teams || []), ...(row?.sourceTeams || [])]
    .filter(Boolean).map(normalizeHistoricalTeam))];
}

function preferSeasonRow(candidates, currentRow, requestedTeam = "") {
  const preferredTeams = [requestedTeam, currentRow?.team].filter(Boolean).map(normalizeHistoricalTeam);
  for (const team of preferredTeams) {
    const exact = candidates.find((row) => normalizeHistoricalTeam(row.team) === team);
    if (exact) return exact;
  }
  const currentTeams = rowTeamNames(currentRow);
  return candidates.find((row) => rowTeamNames(row).some((team) => currentTeams.includes(team)))
    || candidates.find((row) => currentRow?.league && row.league === currentRow.league)
    || candidates[0] || null;
}

function findPlayerSeasonRow(rows, currentRow, year, config, requestedTeam = "") {
  if (!currentRow) return null;
  const seasonRows = rows.filter((row) => !year || `${row.year}` === `${year}`);
  const playerId = seasonPlayerId(currentRow, config);
  const npbId = officialPlayerId(currentRow);

  // Positive identities take precedence over display names, including renamed players.
  if (playerId) {
    const exactIds = seasonRows.filter((row) => seasonPlayerId(row, config) === playerId);
    if (exactIds.length) return preferSeasonRow(exactIds, currentRow, requestedTeam);
  }
  if (npbId) {
    const exactProfiles = seasonRows.filter((row) => officialPlayerId(row) === npbId
      && (!playerId || !seasonPlayerId(row, config) || seasonPlayerId(row, config) === playerId));
    if (exactProfiles.length) return preferSeasonRow(exactProfiles, currentRow, requestedTeam);
  }
  if (!currentRow.player) return null;

  const namesakes = rows.filter((row) => rowMatchesPlayerName(row, currentRow.player));
  const candidates = seasonRows.filter((row) => rowMatchesPlayerName(row, currentRow.player)
    && (!playerId || !seasonPlayerId(row, config) || seasonPlayerId(row, config) === playerId)
    && (!npbId || !officialPlayerId(row) || officialPlayerId(row) === npbId));
  if (!candidates.length) return null;

  const currentTeams = [...new Set([requestedTeam, ...rowTeamNames(currentRow)]
    .filter(Boolean).map(normalizeHistoricalTeam))];
  const sameClub = candidates.filter((row) => rowTeamNames(row).some((team) => currentTeams.includes(team)));
  const distinctIds = (items, getId) => new Set(items.map(getId).filter(Boolean)).size;
  if (sameClub.length) {
    if (distinctIds(sameClub, (row) => seasonPlayerId(row, config)) > 1
      || distinctIds(sameClub, officialPlayerId) > 1) return null;
    return preferSeasonRow(sameClub, currentRow, requestedTeam);
  }

  // A shared surname can represent different players (e.g. the two オスナ players).
  // Without a club match or positive identity, never infer a transfer between them.
  if (distinctIds(namesakes, (row) => seasonPlayerId(row, config)) > 1
    || distinctIds(namesakes, officialPlayerId) > 1) return null;
  return preferSeasonRow(candidates, currentRow, requestedTeam);
}

function findCurrentRow(rows, params, config) {
  const year = params.get("year") || "";
  const player = params.get("player") || "";
  const team = params.get("team") || "";
  const playerId = params.get("playerId") || "";
  const scopedRows = rows.filter((row) => !year || `${row.year}` === year);
  if (player || playerId) {
    return findPlayerSeasonRow(rows, { player, team, [config.idKey]: playerId }, year, config, team);
  }
  return scopedRows.find((row) => team && normalizeHistoricalTeam(row.team) === normalizeHistoricalTeam(team))
    || scopedRows[0] || null;
}

function findPreviousRow(rows, currentRow, params, config) {
  if (!currentRow) return null;
  const previousYear = Number.parseInt(currentRow.year, 10) - 1;
  if (!Number.isFinite(previousYear) || previousYear <= 0) return null;
  return findPlayerSeasonRow(rows, currentRow, `${previousYear}`, config, params.get("team") || "");
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
  if (numerator == null || denominator == null) return null;
  const safeNumerator = Number(numerator);
  const safeDenominator = Number(denominator);
  if (!Number.isFinite(safeNumerator) || !Number.isFinite(safeDenominator) || safeDenominator === 0) {
    return null;
  }
  return (safeNumerator / safeDenominator) * multiplier;
}

function monthNumberFromSplit(split) {
  const rawMonth = `${split?.month ?? ""}`;
  const sourceLabel = `${split?.sourceGrouping || split?.label || split?.monthLabel || ""}`;
  if (rawMonth.includes("/") || /\d{1,2}\s*[・･/〜～–-]\s*\d{1,2}\s*月/.test(sourceLabel)) return "";
  const isoMatch = rawMonth.match(/-(\d{2})$/);
  if (isoMatch) return isoMatch[1];
  const labelMatch = `${split?.monthLabel ?? ""}`.match(/(\d{1,2})月/);
  if (labelMatch) return labelMatch[1].padStart(2, "0");
  return "";
}

function sumMetric(rows, key) {
  return rows.reduce((total, row) => total + (Number(row?.[key]) || 0), 0);
}

function hasKnownCount(rows, key) {
  return rows.every((row) => row?.[key] != null && row[key] !== ""
    && Number.isFinite(Number(row[key])) && Number(row[key]) >= 0);
}

function weightedAverage(rows, key, weightKey) {
  const available = rows.filter((row) => row?.[key] != null && row?.[weightKey] != null
    && Number.isFinite(Number(row[key])) && Number.isFinite(Number(row[weightKey])) && Number(row[weightKey]) > 0);
  const weighted = available.reduce((total, row) => {
    const value = Number(row?.[key]);
    const weight = Number(row?.[weightKey]);
    if (!Number.isFinite(value) || !Number.isFinite(weight) || weight <= 0) return total;
    return total + (value * weight);
  }, 0);
  const totalWeight = available.reduce((total, row) => {
    const weight = Number(row?.[weightKey]);
    return Number.isFinite(weight) && weight > 0 ? total + weight : total;
  }, 0);
  return totalWeight > 0 ? weighted / totalWeight : null;
}

function aggregatePitcherBucket(rows, bucket) {
  const latestRow = rows[rows.length - 1] || rows[0] || null;
  if (!latestRow) return null;
  const inningsOuts = sumMetric(rows, "inningsOuts");
  const outEventTotal =
    sumMetric(rows, "grounders") +
    sumMetric(rows, "flyBalls") +
    sumMetric(rows, "lookingStrikeouts") +
    sumMetric(rows, "swingingStrikeouts") +
    sumMetric(rows, "sacrificeBunts") +
    sumMetric(rows, "interference");
  const fipConstant = rows.find((row) => row?.fipConstant != null && Number.isFinite(Number(row.fipConstant)))?.fipConstant ?? null;
  const atBats = sumMetric(rows, "atBats");
  const hits = sumMetric(rows, "hits");
  const scoringPositionAtBats = sumMetric(rows, "scoringPositionAtBats");
  const scoringPositionHits = sumMetric(rows, "scoringPositionHits");
  const walks = sumMetric(rows, "walks");
  const unintentionalWalks = hasKnownCount(rows, "unintentionalWalks") ? sumMetric(rows, "unintentionalWalks") : null;
  const strikeouts = sumMetric(rows, "strikeouts");
  const homeRuns = sumMetric(rows, "homeRuns");
  const hitByPitch = sumMetric(rows, "hitByPitch");
  const sacrificeFlies = sumMetric(rows, "sacrificeFlies");
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
  const sourceCoverage = rows.some((row) => row.sourceCoverage) ? rows.reduce((total, row) => {
    for (const key of ["games", "incompleteGames", "unknownGames", "recordedPitches", "officialPitches", "unknownInningPitches"]) {
      total[key] = (total[key] || 0) + (Number(row.sourceCoverage?.[key]) || 0);
    }
    return total;
  }, {}) : null;
  const incompleteSource = sourceCoverage && (sourceCoverage.incompleteGames > 0 || sourceCoverage.unknownGames > 0);
  const battingAverageAllowed = incompleteSource || !hasKnownCount(rows, "atBats") ? null : safeDivide(hits, atBats);
  const knownBabipInputs = ["atBats", "hits", "homeRuns", "strikeouts", "sacrificeFlies"].every((key) => hasKnownCount(rows, key));
  const babipAllowed = incompleteSource || !knownBabipInputs ? null : safeDivide(hits - homeRuns, atBats - strikeouts - homeRuns + sacrificeFlies);
  const goFo = safeDivide(grounders, flyBalls);
  const groundOutRate = safeDivide(grounders, outEventTotal, 100);
  const flyOutRate = safeDivide(flyBalls, outEventTotal, 100);
  const whiffRate = hasPitchCount ? safeDivide(sumMetric(rows, "swingMisses"), pitches, 100) : null;
  const fip =
    inningsOuts && fipConstant != null && unintentionalWalks != null && Number.isFinite(Number(fipConstant))
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
    sacrificeFlies,
    interference: sumMetric(rows, "interference"),
    era,
    whip,
    kPer9,
    bbPer9,
    hPer9,
    hrPer9,
    kBb,
    fip,
    fipConstant: fipConstant != null && Number.isFinite(Number(fipConstant)) ? Number(fipConstant) : null,
    sourceCoverage,
    battingAverageAllowed,
    babipAllowed,
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
  const scoringPositionAtBats = sumMetric(rows, "scoringPositionAtBats");
  const scoringPositionHits = sumMetric(rows, "scoringPositionHits");
  const ballZonePitchCount = sumMetric(rows, "ballZonePitchCount");
  const ballZoneSwingCount = sumMetric(rows, "ballZoneSwingCount");
  const singles = sumMetric(rows, "singles");
  const doubles = sumMetric(rows, "doubles");
  const triples = sumMetric(rows, "triples");
  const totalBases = singles + (2 * doubles) + (3 * triples) + (4 * homeRuns);
  const battingAverage = safeDivide(hits, atBats);
  const scoringPositionBattingAverage = safeDivide(scoringPositionHits, scoringPositionAtBats);
  const onBasePercentage = safeDivide(hits + walks + hitByPitch, atBats + walks + hitByPitch + sacFlies);
  const sluggingPercentage = safeDivide(totalBases, atBats);
  const isoDiscipline =
    battingAverage !== null && onBasePercentage !== null ? onBasePercentage - battingAverage : null;
  const isoPower =
    battingAverage !== null && sluggingPercentage !== null ? sluggingPercentage - battingAverage : null;
  const babip = safeDivide(hits - homeRuns, atBats - strikeouts - homeRuns + sacFlies);
  const ops = onBasePercentage !== null && sluggingPercentage !== null ? onBasePercentage + sluggingPercentage : null;
  const ballZoneSwingRate = safeDivide(ballZoneSwingCount, ballZonePitchCount, 100);
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
    scoringPositionAtBats,
    scoringPositionHits,
    ballZonePitchCount,
    ballZoneSwingCount,
    battingAverage,
    scoringPositionBattingAverage,
    ballZoneSwingRate,
    onBasePercentage,
    isoDiscipline,
    sluggingPercentage,
    isoPower,
    babip,
    ops,
    wrc: rows.some((row) => row.wrc != null) ? sumMetric(rows, "wrc") : null,
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
      const sourceLabel = split.sourceGrouping || split.label || split.monthLabel || `${Number.parseInt(month || "0", 10) || month}月`;
      const groupedFirstMonth = `${sourceLabel}`.match(/(\d{1,2})\s*[・･/〜～–-]\s*\d{1,2}\s*月/)?.[1]?.padStart(2, "0");
      const groupedOrder = MONTH_BUCKETS.findIndex((item) => item.key === groupedFirstMonth);
      fallbackRows.push({
        key: split.month || month || `${fallbackRows.length}`,
        label: sourceLabel,
        rows: [split],
        order: groupedOrder >= 0 ? groupedOrder : MONTH_BUCKETS.length + fallbackRows.length,
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
  if (state.currentRow?.seasonDashboard) return state.currentRow.seasonDashboard;
  if (state.currentRow?.year !== "2025" || !state.historical.loaded) return null;
  const profile = findHistoricalPlayer(state.historical.payload?.players || [], state.currentRow);
  const type = state.config === TYPE_CONFIG.pitcher ? "pitcher" : "batter";
  return window.HistoricalSeasonAdapters?.[type]?.(profile, state.currentRow) || null;
}

function rowHits(row) {
  if (row?.hits != null && Number.isFinite(Number(row.hits))) return Number(row.hits);
  const counts = [row?.singles, row?.doubles, row?.triples, row?.homeRuns];
  return counts.every((value) => value != null && Number.isFinite(Number(value)))
    ? counts.reduce((sum, value) => sum + Number(value), 0) : null;
}

function normalizeMatchupTeam(value) {
  const trimmed = `${value || ""}`.trim();
  return MATCHUP_TEAM_NAMES[trimmed] || trimmed;
}

function stadiumLabel(value) {
  const trimmed = `${value || ""}`.trim();
  if (!trimmed || trimmed === "-") return trimmed || "-";
  return STADIUM_LABELS[trimmed] || trimmed;
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

function seasonPitchMixLegend(rows) {
  const visibleRows = (rows || []).filter((row) => (Number(row?.count) || 0) > 0);
  if (!visibleRows.length) return "";
  return `
    <div class="season-outcome-grid season-pitch-mix-legend">
      ${visibleRows
        .map(
          (row) => `
            <div class="outcome-item">
              <div class="outcome-item-head">
                <span class="legend-swatch" style="background:${escapeHtml(row.color || "#0F2340")}"></span>
                <strong>${escapeHtml(row.pitchType)}</strong>
              </div>
              <div class="outcome-item-values">
                <span>${formatNumber(row.count)}球</span>
                <span>${formatPercentValue(row.ratio)}</span>
              </div>
            </div>
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
      <div class="season-pitch-mix-layout">
        ${seasonPieChart(rows, "pitchType")}
        ${seasonPitchMixLegend(rows)}
      </div>
    </article>
  `;
}

function renderSeasonPitchSummary(dashboard) {
  const rows = (dashboard?.pitchMix || []).filter((row) => (Number(row?.count) || 0) > 0);
  if (!rows.length) {
    return `
      <article class="dashboard-card">
        <div class="card-head"><h3>球種別サマリ</h3></div>
        <div class="section-empty compare-empty">データなし</div>
      </article>
    `;
  }
  return `
    <article class="dashboard-card season-card-wide">
      <div class="card-head"><h3>球種別サマリ</h3></div>
      ${renderResponsiveDataTable({
        tableClass: "season-pitch-summary-table",
        headers: ["球種", "球数", "割合", "平均", "最速", "空振", "空振率", "被打数", "被安打", "被本", "ゴロ", "フライ", "三振", "被打率"],
        rows: rows.map((row) => ({
          heading: `<span class="pitch-name-cell"><span class="legend-swatch" style="background:${escapeHtml(row.color || "#0F2340")}"></span>${escapeHtml(row.pitchType)}</span>`,
          values: [
            formatNumber(row.count),
            formatPercentValue(row.ratio),
            formatSpeedValue(row.avgSpeed),
            formatSpeedValue(row.maxSpeed),
            formatNumber(row.whiffCount),
            formatPercentValue(row.whiff),
            formatNumber(row.atBats),
            formatNumber(rowHits(row)),
            formatNumber(row.homeRuns),
            formatNumber(row.grounders),
            formatNumber(row.flyBalls),
            formatNumber(row.strikeouts),
            formatAverageValue(row.hitRate),
          ],
        })),
      })}
    </article>
  `;
}

function renderSeasonPitchMetricSummary(dashboard) {
  const rows = (dashboard?.pitchMix || []).filter((row) => (Number(row?.count) || 0) > 0);
  if (!rows.length) {
    return `
      <article class="dashboard-card">
        <div class="card-head"><h3>球種別サマリ（各種指標）</h3></div>
        <div class="section-empty compare-empty">データなし</div>
      </article>
    `;
  }
  return `
    <article class="dashboard-card season-card-wide">
      <div class="card-head"><h3>球種別サマリ（各種指標）</h3></div>
      ${renderResponsiveDataTable({
        tableClass: "season-pitch-metric-summary-table",
        headers: ["球種", "whiff%", "csw%", "zone%", "z-swing%", "o-contact%", "chase%", "chase+"],
        rows: rows.map((row) => ({
          heading: `<span class="pitch-name-cell"><span class="legend-swatch" style="background:${escapeHtml(row.color || "#0F2340")}"></span>${escapeHtml(row.pitchType)}</span>`,
          values: [
            formatPercentValue(row.whiffRate),
            formatPercentValue(row.csw),
            formatPercentValue(row.zoneRate),
            formatPercentValue(row.zSwing),
            formatPercentValue(row.oContact),
            formatPercentValue(row.chase),
            formatPlusValue(row.chasePlus),
          ],
        })),
      })}
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
  return `
    <article class="dashboard-card season-card-wide">
      <div class="card-head"><h3>イニング別サマリ</h3></div>
      ${renderResponsiveDataTable({
        tableClass: "season-inning-table",
        headers: ["回", "球数", "平均", "最速", "空振", "空振率", "被打数", "被安打", "被本", "ゴロ", "フライ", "三振", "被打率"],
        rows: rows.map((row) => ({
          heading: `${escapeHtml(row.inning)}回`,
          values: [
            formatNumber(row.count),
            formatSpeedValue(row.avgSpeed),
            formatSpeedValue(row.maxSpeed),
            formatNumber(row.whiffCount),
            formatPercentValue(row.whiff),
            formatNumber(row.atBats),
            formatNumber(rowHits(row)),
            formatNumber(row.homeRuns),
            formatNumber(row.grounders),
            formatNumber(row.flyBalls),
            formatNumber(row.strikeouts),
            formatAverageValue(row.hitRate),
          ],
        })),
      })}
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

function pitcherHandLabel(row) {
  const label = row?.label || "-";
  if (label === "右") return "対右打者";
  if (label === "左") return "対左打者";
  return label;
}

function renderPitcherHandSummary(dashboard) {
  const rows = dashboard?.batterHandRows || [];
  const visibleRows = rows.filter((row) => [row.count, row.countPA, row.atBats].some((value) => Number(value) > 0));
  if (!visibleRows.length) {
    return `
      <article class="dashboard-card season-card-wide">
        <div class="card-head"><h3>対左右別成績</h3></div>
        <div class="section-empty compare-empty">データなし</div>
      </article>
    `;
  }
  return `
    <article class="dashboard-card season-card-wide">
      <div class="card-head"><h3>対左右別成績</h3></div>
      ${renderResponsiveDataTable({
        tableClass: "season-pitch-hand-summary-table",
        headers: ["区分", "被打率", "空振", "空振率", "被打数", "被安打", "被本", "ゴロ", "フライ", "三振"],
        rows: visibleRows.map((row) => ({
          heading: escapeHtml(pitcherHandLabel(row)),
          values: [
            formatAverageValue(row.hitRate),
            formatNumber(row.whiffCount),
            formatPercentValue(row.whiff),
            formatNumber(row.atBats),
            formatNumber(rowHits(row)),
            formatNumber(row.homeRuns),
            formatNumber(row.grounders),
            formatNumber(row.flyBalls),
            formatNumber(row.strikeouts),
          ],
        })),
      })}
    </article>
  `;
}

function pitcherGameSplitLabel(sectionKey, row) {
  const label = row?.label || "-";
  if (sectionKey === "opponentRows" && label !== "-") return `vs${label}`;
  if (sectionKey === "stadiumRows") return stadiumLabel(label);
  return label;
}

function renderPitcherGameSplitTable(sectionKey, title, rows = []) {
  const visibleRows = rows.filter((row) => (Number(row?.games) || 0) > 0);
  if (!visibleRows.length) {
    return `
      <article class="dashboard-card season-card-wide">
        <div class="card-head"><h3>${escapeHtml(title)}</h3></div>
        <div class="section-empty compare-empty">データなし</div>
      </article>
    `;
  }
  return `
    <article class="dashboard-card season-card-wide">
      <div class="card-head"><h3>${escapeHtml(title)}</h3></div>
      ${renderResponsiveDataTable({
        tableClass: "pitcher-game-split-table",
        headers: ["区分", "試合", "防御率", "投球回", "打者", "被安打", "被本", "奪三振", "与四球", "与死球", "失点", "自責", "WHIP", "被打率"],
        rows: visibleRows.map((row) => ({
          heading: escapeHtml(pitcherGameSplitLabel(sectionKey, row)),
          values: [
            formatNumber(row.games),
            formatNumber(row.era, 2),
            escapeHtml(row.innings || "-"),
            formatNumber(row.batters),
            formatNumber(row.hits),
            formatNumber(row.homeRuns),
            formatNumber(row.strikeouts),
            formatNumber(row.walks),
            formatNumber(row.hitByPitch),
            formatNumber(row.runs),
            formatNumber(row.earnedRuns),
            formatNumber(row.whip, 2),
            formatAverageValue(row.battingAverageAllowed),
          ],
        })),
      })}
    </article>
  `;
}

function renderPitcherDecisionInningTable(title, rows = [], available = true) {
  if (!available) {
    return `
      <article class="dashboard-card season-card-wide">
        <div class="card-head"><h3>${escapeHtml(title)}</h3></div>
        <div class="section-empty compare-empty">この年度のイニング別集計は未収録です。</div>
      </article>
    `;
  }
  if (!rows.length) {
    return `
      <article class="dashboard-card season-card-wide">
        <div class="card-head"><h3>${escapeHtml(title)}</h3></div>
        <div class="section-empty compare-empty">データなし</div>
      </article>
    `;
  }
  const innings = Array.from({ length: 12 }, (_item, index) => index + 1);
  const rowByInning = new Map(rows.map((row) => [Number(row?.inning), row]));
  const conditionRows = [
    ["total", "合計"],
    ["win", "勝利"],
    ["loss", "敗戦"],
    ["noDecision", "勝敗無"],
  ];
  const conditionHelp = { win: "勝利登板", loss: "敗戦登板", noDecision: "勝敗なし登板" };
  const cellClass = (key, value) => {
    const count = Number(value) || 0;
    if (key === "total" && count === 0) return " inning-cell-zero";
    if (count >= 3) return " inning-cell-high";
    if (count >= 2) return " inning-cell-mid";
    if (count >= 1) return " inning-cell-low";
    return "";
  };
  const body = conditionRows
    .map(([key, label]) => {
      const values = innings.map((inning) => {
        const value = rowByInning.get(inning)?.[key];
        return typeof value === "number" && Number.isFinite(value) ? value : null;
      });
      const total = values.every((value) => value != null) ? values.reduce((sum, value) => sum + value, 0) : null;
      return `
        <tr>
          <th scope="row"${conditionHelp[key] ? ` data-stat-help="${conditionHelp[key]}"` : ""}>${escapeHtml(label)}</th>
          ${values
            .map((value) => `<td class="${cellClass(key, value).trim()}">${formatNumber(value)}</td>`)
            .join("")}
          <td class="inning-cell-total">${formatNumber(total)}</td>
        </tr>
      `;
    })
    .join("");
  return `
    <article class="dashboard-card season-card-wide">
      <div class="card-head"><h3>${escapeHtml(title)}</h3></div>
      <div class="table-scroll">
        <table class="data-table season-table pitcher-decision-inning-table">
          <thead>
            <tr>
              <th>条件</th>
              ${innings.map((inning) => `<th>${inning}回</th>`).join("")}
              <th>合計</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    </article>
  `;
}

function renderBatterRecentGames(dashboard) {
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
          <td>${formatAverageValue(row.battingAverage)}</td>
          <td>${formatNumber(row.plateAppearances)}</td>
          <td>${formatNumber(row.atBats)}</td>
          <td>${formatNumber(row.hits)}</td>
          <td>${formatNumber(row.homeRuns)}</td>
          <td>${formatNumber(row.runsBattedIn)}</td>
          <td>${formatNumber(row.walks)}</td>
          <td>${formatNumber(row.strikeouts)}</td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="dashboard-card season-card-wide">
      <div class="card-head"><h3>最近6試合の成績</h3></div>
      <div class="table-scroll">
        <table class="data-table season-table batter-recent-game-table">
          <thead>
            <tr><th>日付</th><th>カード</th><th>打率</th><th>打席</th><th>打数</th><th>安打</th><th>本塁打</th><th>打点</th><th>四球</th><th>三振</th></tr>
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

const BATTER_SPLIT_HEADER_LABELS = {
  byOpponent: "対戦相手",
  byStadium: "球場名",
  byPitchType: "球種",
  byVelocity: "球速",
  byBattingOrder: "打順",
  byPlateAppearance: "打席",
  byStrikeCount: "カウント",
};

const BATTER_SPLIT_TABLE_CLASSES = {
  byOpponent: "batter-season-table--opponent",
  byStadium: "batter-season-table--stadium",
  byPitchType: "batter-season-table--pitch-type",
  byVelocity: "batter-season-table--velocity",
  byPitcherHand: "batter-season-table--pitcher-hand",
  byBattingOrder: "batter-season-table--batting-order",
  byPlateAppearance: "batter-season-table--plate-appearance",
  byStrikeCount: "batter-season-table--strike-count",
};

function batterSplitLabel(sectionKey, row) {
  const label = row?.label || "-";
  if (sectionKey === "byPitcherHand") {
    if (label === "右") return "右投手";
    if (label === "左") return "左投手";
  }
  if (sectionKey === "byOpponent" && label !== "-") {
    return `vs${label}`;
  }
  if (sectionKey === "byStadium") {
    return stadiumLabel(label);
  }
  return label;
}

function renderBatterSplitTable(sectionKey, title, rows = [], meta = {}) {
  title = meta.title || title;
  const splitHeader = BATTER_SPLIT_HEADER_LABELS[sectionKey] || "区分";
  const splitTableClass = BATTER_SPLIT_TABLE_CLASSES[sectionKey] || "";
  const visibleRows = rows.filter((row) => ["plateAppearances", "atBats", "hits", "walks", "hitByPitch", "sacBunts", "sacFlies", "walksAndHitByPitch"].some((key) => Number(row[key]) > 0));
  const extraColumns = [
    ["walksAndHitByPitch", "四死球", (value) => formatNumber(value)],
    ["pitchCount", "球数", (value) => formatNumber(value)],
    ["averageVelocity", "平均球速", (value) => formatNumber(value, 1)],
    ["whiffRate", "Whiff%", (value) => formatNumber(value, 1)],
  ].filter(([key]) => meta.extraColumns?.includes(key));
  if (!visibleRows.length) {
    return `
      <article class="dashboard-card season-card-wide">
        <div class="card-head"><h3>${escapeHtml(title)}</h3></div>
        <div class="section-empty compare-empty">データなし</div>
      </article>
    `;
  }
  return `
    <article class="dashboard-card season-card-wide">
      <div class="card-head"><h3>${escapeHtml(title)}</h3></div>
      ${meta.note ? `<p class="season-coverage-note">${escapeHtml(meta.note)}</p>` : ""}
      ${renderResponsiveDataTable({
        tableClass: `batter-season-table ${splitTableClass}`,
        headers: [escapeHtml(splitHeader), "打率", "打席", "打数", "安打", "二塁打", "三塁打", "本塁打", meta.scope === "reportedPitchResults" ? '<span data-stat-help="uBB">四球（敬遠除く）</span>' : "四球", "死球", "犠打", "犠飛", "三振", "出塁率", "長打率", "OPS", ...extraColumns.map(([, label]) => label)],
        rows: visibleRows.map((row) => ({
          heading: `<span class="batter-split-label-cell">${escapeHtml(batterSplitLabel(sectionKey, row))}</span>`,
          values: [
            formatAverageValue(row.battingAverage),
            formatNumber(row.plateAppearances),
            formatNumber(row.atBats),
            formatNumber(row.hits),
            formatNumber(row.doubles),
            formatNumber(row.triples),
            formatNumber(row.homeRuns),
            formatNumber(row.walks),
            formatNumber(row.hitByPitch),
            formatNumber(row.sacBunts),
            formatNumber(row.sacFlies),
            formatNumber(row.strikeouts),
            formatAverageValue(row.onBasePercentage),
            formatAverageValue(row.sluggingPercentage),
            formatAverageValue(row.ops),
            ...extraColumns.map(([key, , formatter]) => formatter(row[key])),
          ],
        })),
      })}
    </article>
  `;
}

function renderBatterSeasonPanel(dashboard) {
  const historical = Boolean(dashboard?.historicalSource);
  const sections = BATTER_SEASON_SECTIONS.filter(([key]) => !historical || dashboard?.sectionMeta?.[key]?.available);
  return `
    <p class="season-coverage-note">${historical ? "2025年の年度集計を共通の形式で表示しています。未収録の項目は「-」で表示します。" : "条件別成績は公式の完了打席で集計しています。球種・球速・投手左右・カウントを特定できない打席は「不明」に含めます。得点圏は打席結果直前の走者状況で判定しています。"}</p>
    <div class="season-detail-grid">
      ${sections
        .map(([key, title]) => renderBatterSplitTable(key, title, dashboard?.[key] || [], dashboard?.sectionMeta?.[key] || {}))
        .join("")}
      ${historical ? "" : renderBatterRecentGames(dashboard)}
    </div>
    ${historical ? '<p class="season-coverage-note">球速帯別・最近6試合の成績は未収録です。</p>' : ""}
  `;
}

function renderPitcherSeasonPanel(dashboard) {
  const historical = Boolean(dashboard?.historical);
  const coverage = dashboard?.sourceCoverage;
  const note = coverage?.incompleteGames || coverage?.unknownGames
    ? `<p class="section-empty">投球記録が不完全な登板が${formatNumber((coverage.incompleteGames || 0) + (coverage.unknownGames || 0))}試合あります。球種・左右・回別は収録された投球の集計です。完全な打数を確認できない被打率・被BABIPは「-」で表示します。</p>` : "";
  return `
    ${note}
    ${historical ? `<p class="season-coverage-note">${escapeHtml(dashboard.sourceCoverageInfo?.note || "未収録の項目は「-」で表示します。")}${escapeHtml(dashboard.sourceCoverageInfo?.discrepancyNote || "")}</p>` : ""}
    <div class="season-detail-grid">
      ${renderSeasonPitchMix(dashboard)}
      ${renderSeasonPitchSummary(dashboard)}
      ${renderSeasonPitchMetricSummary(dashboard)}
      ${historical ? "" : renderSeasonInningSummary(dashboard)}
      ${renderPitcherHandSummary(dashboard)}
      ${renderPitcherGameSplitTable("opponentRows", "対チーム別投手成績", dashboard?.opponentRows || [])}
      ${renderPitcherGameSplitTable("stadiumRows", "球場別投手成績", dashboard?.stadiumRows || [])}
      ${historical ? renderPitcherDecisionInningTable(dashboard.starterInningRunRowsTitle, dashboard.starterInningRunRows || []) : renderPitcherDecisionInningTable("イニング別失点数", dashboard?.inningRunRows || [], Boolean(dashboard?.inningRunRowsAvailable) && dashboard?.inningRunRowsMethod !== "proportional_estimate")}
      ${historical ? "" : renderPitcherDecisionInningTable("イニング別四死球数", dashboard?.inningWalkRows || [], Boolean(dashboard?.inningWalkRowsAvailable))}
      ${renderSeasonOutcomes(dashboard)}
      ${renderSeasonFinish(dashboard)}
      ${historical ? "" : renderRecentGames(dashboard)}
    </div>
  `;
}

function renderAdditionalSeasonTables() {
  if (state.currentRow?.year !== "2025") return "";
  const profile = findHistoricalPlayer(state.historical.payload?.players || [], state.currentRow);
  const represented = state.config === TYPE_CONFIG.pitcher
    ? /^(左右別成績|対チーム別成績|球場別成績|対打者結果一覧|先発時のイニング毎失点数)/
    : /^(対左右別成績|対チーム別成績|球場別成績|打順別成績|打席別成績)/;
  const tables = historicalTables(profile).filter((table) => !represented.test(table.title));
  if (!tables.length) return "";
  return `<details class="season-additional-tables"><summary>その他の年度集計 <span>${tables.length}項目</span></summary><div>${tables.map((table) => `<details class="season-extra-table"><summary>${escapeHtml(table.title)}</summary>${renderHistoricalTable(table)}</details>`).join("")}</div></details>`;
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
  if (!dashboard && state.currentRow.year === "2025") {
    els.seasonMetricCount.textContent = "2025年度集計";
    els.seasonDetailWrap.innerHTML = `<article class="dashboard-card season-card-wide"><div class="card-head"><h3>年度成績</h3></div><p class="section-empty">${state.historical.error ? "年度成績を読み込めませんでした。ページを再読み込みしてください。" : state.historical.loaded ? "この選手の年度詳細は未収録です。" : "年度成績を読み込み中…"}</p></article>`;
    void ensureHistoricalData();
    return;
  }
  if (!dashboard) {
    els.seasonDetailWrap.innerHTML = '<div class="section-empty compare-empty">この年度の一球データ集計はありません。</div>';
    return;
  }
  els.seasonDetailWrap.innerHTML =
    (state.config === TYPE_CONFIG.pitcher
      ? renderPitcherSeasonPanel(dashboard)
      : renderBatterSeasonPanel(dashboard)) + renderAdditionalSeasonTables();
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
          aria-pressed="${state.activeMode === mode}"
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
      renderMetricToggles();
      renderHeader();
      renderPanels();
    });
  });
}

function renderMetricToggles() {
  const keys = state.activeMode === "compare" ? comparisonMetricKeys() : state.activeMetricKeys;
  els.metricToggleGroup.innerHTML = state.config.metrics
    .map((metric) => {
      const active = keys.includes(metric.key);
      return `
        <button
          type="button"
          class="compare-toggle${active ? " active" : ""}"
          data-metric-key="${metric.key}"
          aria-pressed="${active}"
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
      const selected = state.activeMode === "compare" ? comparisonMetricKeys() : state.activeMetricKeys;
      const next = selected.includes(key) ? selected.filter((item) => item !== key) : [...selected, key];
      if (state.activeMode === "compare") {
        state.comparisonMetricKeys = next;
        state.comparisonPreset = "custom";
      } else state.activeMetricKeys = next;
      renderMetricToggles();
      renderPanels();
    });
  });
}

function comparisonMetricKeys() {
  return state.comparisonMetricKeys ?? state.config.metrics.filter((metric) => metric.default).map((metric) => metric.key);
}

function availableComparisonYears() {
  if (!state.currentRow) return [];
  return [...new Set([state.currentRow.year, ...state.rows.map((row) => row.year)])]
    .filter((year) => findPlayerSeasonRow(state.rows, state.currentRow, year, state.config) || year === state.currentRow.year)
    .sort((a, b) => Number(b) - Number(a));
}

function comparisonPair(year = state.comparisonYear) {
  const current = !year || year === state.currentRow?.year ? state.currentRow
    : findPlayerSeasonRow(state.rows, state.currentRow, year, state.config);
  const previous = current ? findPreviousRow(state.rows, current, new URLSearchParams(), state.config) : null;
  return { current, previous: previous || (current === state.currentRow ? state.previousRow : null) };
}

function comparisonSeasonMarkup(row, year) {
  const detail = !row ? "成績データなし" : state.config === TYPE_CONFIG.pitcher
    ? `${row.team} · ${row.games}試合 · ${formatInningsFromOuts(row.inningsOuts)}回`
    : `${row.team} · ${row.games}試合 · ${row.plateAppearances}打席`;
  return `<div class="comparison-season"><strong>${escapeHtml(year)}<small> 年</small></strong><span>${escapeHtml(detail)}</span></div>`;
}

function comparisonMetrics() {
  const selected = new Set(comparisonMetricKeys());
  return state.config.metrics.filter((metric) => selected.has(metric.key));
}

function comparisonValue(metric, row) {
  return numericMetricValue(metric, row) === null ? "—" : formatMetricValue(metric, row);
}

function differenceMarkup(metric, previous, current) {
  const before = numericMetricValue(metric, previous);
  const after = numericMetricValue(metric, current);
  const delta = before === null || after === null ? null : after - before;
  const rounded = delta === null ? null : Number(delta.toFixed(metric.digits ?? (metric.kind === "innings" || metric.kind === "number" ? 0 : 2)));
  const tone = rounded > 0 ? "positive" : rounded < 0 ? "negative" : "flat";
  return `<span class="comparison-difference comparison-difference--${tone}">${escapeHtml(formatMetricDelta(metric, delta))}</span>`;
}

function comparisonBarMarkup(metric, previous, current) {
  const values = [numericMetricValue(metric, previous), numericMetricValue(metric, current)];
  const known = values.filter((value) => value !== null);
  const min = Math.min(0, ...known);
  const max = Math.max(0, ...known);
  const range = max - min || 1;
  const line = (row, index) => {
    const value = values[index];
    const left = value === null ? 0 : 100 * (Math.min(0, value) - min) / range;
    const width = value === null ? 0 : 100 * Math.abs(value) / range;
    return `<div class="comparison-bar-line${index ? " comparison-bar-line--current" : ""}"><span>${escapeHtml(row?.year || Number(current.year) - 1)}</span><div class="comparison-bar-track" aria-hidden="true"><i class="comparison-bar-fill" style="left:${left.toFixed(3)}%;width:${width.toFixed(3)}%"></i><i class="comparison-bar-zero" style="left:${(100 * -min / range).toFixed(3)}%"></i></div><strong>${escapeHtml(comparisonValue(metric, row))}</strong></div>`;
  };
  return `<article class="comparison-bar-card"><div class="comparison-bar-head"><h3>${escapeHtml(metric.label)}</h3>${differenceMarkup(metric, previous, current)}</div>${line(previous, 0)}${line(current, 1)}</article>`;
}

function compareCardsMarkup() {
  if (!state.currentRow) {
    return `<div class="section-empty compare-empty">${escapeHtml(state.error || "選手データを読み込めませんでした。")}</div>`;
  }
  if (!comparisonMetricKeys().length) {
    return '<div class="section-empty compare-empty">比較したい指標を選択してください。</div>';
  }
  const { previous, current } = comparisonPair();
  if (!current) return '<p class="section-empty">この年度の成績はありません。</p>';
  const metrics = comparisonMetrics();
  const missingNote = previous ? "" : '<p class="comparison-help comparison-missing">前年の成績がないため、前年差は表示できません。</p>';
  if (state.comparisonView === "bars") return `${missingNote}<div class="comparison-bars">${metrics.map((metric) => comparisonBarMarkup(metric, previous, current)).join("")}</div>`;
  const previousYear = Number(current.year) - 1;
  return `${missingNote}<div class="comparison-table-scroll" tabindex="0" aria-label="前年比較の成績表。横にスクロールできます"><table class="comparison-table"><thead><tr><th scope="col">指標</th><th scope="col">${escapeHtml(previousYear)}年</th><th scope="col">${escapeHtml(current.year)}年</th><th scope="col">前年差</th></tr></thead><tbody>${metrics.map((metric) => `<tr><th scope="row">${escapeHtml(metric.label)}</th><td>${escapeHtml(comparisonValue(metric, previous))}</td><td>${escapeHtml(comparisonValue(metric, current))}</td><td>${differenceMarkup(metric, previous, current)}</td></tr>`).join("")}</tbody></table></div>`;
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
  const { previous, current } = comparisonPair();
  const year = current?.year || state.currentRow?.year || "";
  els.compareMetricCount.textContent = `${comparisonMetrics().length}項目`;
  const years = availableComparisonYears();
  const pairedYears = years.filter((value) => comparisonPair(value).previous);
  els.comparisonYearSelect.innerHTML = (pairedYears.length ? pairedYears : years).map((value) => `<option value="${escapeHtml(value)}"${value === year ? " selected" : ""}>${escapeHtml(Number(value) - 1)} → ${escapeHtml(value)}</option>`).join("");
  els.compareSeasonGrid.innerHTML = current
    ? `${comparisonSeasonMarkup(previous, Number(year) - 1)}<span class="comparison-season-arrow" aria-hidden="true">→</span>${comparisonSeasonMarkup(current, year)}` : "";
  els.compareCardGrid.innerHTML = compareCardsMarkup();
  document.querySelectorAll("[data-compare-preset]").forEach((button) => button.setAttribute("aria-pressed", `${button.dataset.comparePreset === state.comparisonPreset}`));
  document.querySelectorAll("[data-compare-view]").forEach((button) => button.setAttribute("aria-pressed", `${button.dataset.compareView === state.comparisonView}`));
  const historicalRow = [previous, current].find((row) => row?.year === "2025");
  els.historicalCompareNote.classList.toggle("is-hidden", !historicalRow);
  els.historicalCompareNote.innerHTML = historicalRow
    ? `<a href="${escapeHtml(historicalPlayerHref(historicalRow))}" target="${state.embedded ? "_top" : "_self"}">2025年の基本成績・条件別成績を見る</a>${state.config === TYPE_CONFIG.batter ? "。wRC・wRC+ は年度係数未収録のため比較対象外です。" : ""}`
    : "";
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
  els.metricControls.classList.toggle("is-hidden", showSeason);
  if (showMonthly) els.metricControls.open = true;
  els.seasonPanel.classList.toggle("is-hidden", !showSeason);
  els.comparePanel.classList.toggle("is-hidden", !showCompare);
  els.monthlyPanel.classList.toggle("is-hidden", !showMonthly);
  if (showSeason) renderSeasonPanel();
  if (showCompare) renderComparePanel();
  if (showMonthly) renderMonthlyPanel();
  postEmbedHeight();
}

function postEmbedHeight() {
  if (!state.embedded || window.parent === window) return;
  window.requestAnimationFrame(() => {
    const height = Math.max(
      document.documentElement.scrollHeight,
      document.body.scrollHeight,
      document.querySelector(".site-shell")?.scrollHeight || 0
    );
    window.parent.postMessage({ type: "playerStatsHeight", height }, window.location.origin);
  });
}

function renderHeader() {
  const currentRow = state.currentRow;
  const previousRow = state.previousRow;
  els.compareEyebrow.textContent = state.config.label;
  els.compareBackLink.href = state.config.annualHref;
  els.compareBackLink.textContent = state.config.annualLabel;
  els.comparePitcherTypeLink?.classList.toggle("active", state.config === TYPE_CONFIG.pitcher);
  els.compareBatterTypeLink?.classList.toggle("active", state.config === TYPE_CONFIG.batter);

  if (!currentRow) {
    els.compareTitle.textContent = "選手成績ビュー";
    els.compareSubtitle.textContent = "";
    els.comparePlayerName.textContent = "選手が見つかりません";
    els.compareDescription.textContent = state.error || "リンク条件に合う成績がありません。";
    document.title = "選手成績ビュー";
    return;
  }

  const monthlyAvailable = monthlySplits().length > 0;
  const seasonAvailable = Boolean(seasonDashboard()) || currentRow.year === "2025";
  els.compareTitle.textContent = `${currentRow.player} 成績ビュー`;
  els.compareSubtitle.textContent = `${currentRow.year}年度 ${state.config.label}`;
  els.comparePlayerName.textContent = currentRow.player;
  els.compareDescription.textContent = previousRow
    ? `${seasonLabel(previousRow)}との比較、${seasonAvailable ? "年度成績" : "年度成績データなし"}、${monthlyAvailable ? `${seasonLabel(currentRow)}の月別推移` : `${seasonLabel(currentRow)}の月別データなし`}を切り替えて表示できます。`
    : `${seasonLabel(currentRow)}の成績を表示しています。${seasonAvailable ? "年度成績を表示できます。" : "この年度の一球データ集計はありません。"}${monthlyAvailable ? "月別推移も表示できます。" : "この年度の月別データはありません。"}`;
  if (state.activeMode === "compare") {
    const pair = comparisonPair();
    if (pair.current) {
      els.compareSubtitle.textContent = `${Number(pair.current.year) - 1} → ${pair.current.year}年度 ${state.config.label}`;
      els.compareDescription.textContent = pair.previous
        ? `${Number(pair.current.year) - 1}年と${pair.current.year}年の数値・前年差を表示しています。`
        : `${pair.current.year}年の成績を表示しています。前年の成績はありません。`;
    }
  }
  document.title = `${currentRow.player} | 成績ビュー`;
}

async function init() {
  const params = currentParams();
  state.embedded = params.get("embed") === "1";
  document.body.classList.toggle("compare-embed", state.embedded);
  state.config = TYPE_CONFIG[params.get("type")] || TYPE_CONFIG.pitcher;
  state.activeMode = MODE_CONFIG[params.get("mode")] ? params.get("mode") : "season";
  state.activeMetricKeys = [];

  try {
    const response = await fetch(state.config.datasetUrl, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    state.rows = payload.players || [];
    state.currentRow = findCurrentRow(state.rows, params, state.config);
    state.previousRow = findPreviousRow(state.rows, state.currentRow, params, state.config);
    state.comparisonYear = state.currentRow?.year || "";
    if (state.currentRow && !state.previousRow) {
      state.comparisonYear = availableComparisonYears().find((year) => comparisonPair(year).previous) || state.currentRow.year;
    }
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
  els.comparisonYearSelect.addEventListener("change", (event) => {
    state.comparisonYear = event.target.value;
    renderHeader();
    renderComparePanel();
    postEmbedHeight();
  });
  document.querySelectorAll("[data-compare-preset]").forEach((button) => {
    button.addEventListener("click", () => {
      state.comparisonPreset = button.dataset.comparePreset;
      state.comparisonMetricKeys = state.config.metrics.filter((metric) => state.comparisonPreset === "all" || metric.default).map((metric) => metric.key);
      renderMetricToggles();
      renderComparePanel();
      postEmbedHeight();
    });
  });
  document.querySelectorAll("[data-compare-view]").forEach((button) => {
    button.addEventListener("click", () => {
      state.comparisonView = button.dataset.compareView;
      renderComparePanel();
      postEmbedHeight();
    });
  });
  els.seasonDetailWrap.addEventListener("change", (event) => {
    if (event.target.id !== "historicalTableSelect") return;
    state.historical.selectedTable = Number(event.target.value) || 0;
    const player = findHistoricalPlayer(state.historical.payload?.players || [], state.currentRow);
    document.getElementById("historicalTableContent").innerHTML = renderHistoricalTable(historicalTables(player)[state.historical.selectedTable]);
    postEmbedHeight();
  });
  if (state.embedded && "ResizeObserver" in window) {
    const resizeObserver = new ResizeObserver(() => postEmbedHeight());
    resizeObserver.observe(document.body);
  }
}

init();
