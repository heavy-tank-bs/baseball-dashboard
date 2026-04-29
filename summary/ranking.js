const TEAM_ORDER = [
  "巨人",
  "阪神",
  "DeNA",
  "広島",
  "ヤクルト",
  "中日",
  "ソフトバンク",
  "日本ハム",
  "ロッテ",
  "オリックス",
  "西武",
  "東北楽天",
];

const FULL_TEAM_NAMES = {
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
  "東北楽天ゴールデンイーグルス": "東北楽天",
};

const PAGE_TYPE = document.body.dataset.rankingType === "batter" ? "batter" : "pitcher";

const TYPE_CONFIG = {
  pitcher: {
    datasetUrl: "./player_totals.json?v=20260427-10",
    thresholdKind: "innings",
    fixedQualification: 143 * 3,
    thresholdLabel: "投球回条件",
    qualifiedLabel: "規定投球回",
    customLabel: "投球回数を指定",
    denominatorLabel: "投球回",
    metrics: [
      { key: "era", label: "防御率", field: "era", kind: "decimal", digits: 2, lowerIsBetter: true, qualifier: true },
      { key: "fip", label: "FIP", field: "fip", kind: "decimal", digits: 2, lowerIsBetter: true, qualifier: true },
      { key: "whiffRate", label: "whiff%", field: "whiffRate", kind: "percent", source: "pitch" },
      { key: "csw", label: "csw%", field: "csw", kind: "percent", source: "pitch" },
      { key: "zoneRate", label: "zone%", field: "zoneRate", kind: "percent", source: "pitch" },
      { key: "chase", label: "chase%", field: "chase", kind: "percent", source: "pitch" },
      { key: "chasePlus", label: "chase+", field: "chasePlus", kind: "plus", source: "pitch" },
    ],
  },
  batter: {
    datasetUrl: "./batter_totals.json?v=20260427-10",
    thresholdKind: "plateAppearances",
    fixedQualification: 443,
    thresholdLabel: "打席数条件",
    qualifiedLabel: "規定打席",
    customLabel: "打席数を指定",
    denominatorLabel: "打席",
    metrics: [
      { key: "battingAverage", label: "打率", field: "battingAverage", kind: "average", qualifier: true },
      { key: "onBasePercentage", label: "出塁率", field: "onBasePercentage", kind: "average", qualifier: true },
      { key: "sluggingPercentage", label: "長打率", field: "sluggingPercentage", kind: "average", qualifier: true },
      { key: "ops", label: "OPS", field: "ops", kind: "average", qualifier: true },
      { key: "isoDiscipline", label: "IsoD", field: "isoDiscipline", kind: "average", qualifier: true },
      { key: "isoPower", label: "IsoP", field: "isoPower", kind: "average", qualifier: true },
    ],
  },
};

const config = TYPE_CONFIG[PAGE_TYPE];

const state = {
  rows: [],
  teamGamesByYear: new Map(),
  year: "",
  league: "all",
  team: "all",
  metricKey: config.metrics[0].key,
  limit: 10,
  thresholdMode: "qualified",
  customThreshold: null,
  error: "",
};

const els = {
  yearSelect: document.getElementById("yearSelect"),
  leagueSelect: document.getElementById("leagueSelect"),
  teamSelect: document.getElementById("teamSelect"),
  metricSelect: document.getElementById("metricSelect"),
  limitSelect: document.getElementById("limitSelect"),
  thresholdField: document.getElementById("thresholdField"),
  thresholdLabel: document.getElementById("thresholdLabel"),
  thresholdMode: document.getElementById("thresholdMode"),
  thresholdInput: document.getElementById("thresholdInput"),
  thresholdRange: document.getElementById("thresholdRange"),
  thresholdMaxLabel: document.getElementById("thresholdMaxLabel"),
  rankingResultCount: document.getElementById("rankingResultCount"),
  rankingNote: document.getElementById("rankingNote"),
  rankingBody: document.getElementById("rankingBody"),
};

function escapeHtml(value) {
  return `${value ?? ""}`
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function parseNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function teamSortKey(team) {
  const primary = `${team || ""}`.split(" / ")[0];
  const index = TEAM_ORDER.indexOf(primary);
  return [index === -1 ? TEAM_ORDER.length : index, primary];
}

function compareTeam(a, b) {
  const [aIndex, aName] = teamSortKey(a);
  const [bIndex, bName] = teamSortKey(b);
  if (aIndex !== bIndex) return aIndex - bIndex;
  return aName.localeCompare(bName, "ja");
}

function normalizeTeam(team) {
  return FULL_TEAM_NAMES[team] || team;
}

function rowTeams(row) {
  return `${row?.team || ""}`
    .split(" / ")
    .map((team) => team.trim())
    .filter(Boolean);
}

function formatInningsFromOuts(outs) {
  const safeOuts = Math.max(0, Number(outs) || 0);
  const whole = Math.floor(safeOuts / 3);
  const remainder = safeOuts % 3;
  return remainder ? `${whole}.${remainder}` : `${whole}`;
}

function parseInningsToOuts(value) {
  const normalized = `${value ?? ""}`.trim().normalize("NFKC");
  if (!normalized) return 0;
  const [wholePart, decimalPart = ""] = normalized.split(".");
  const whole = Math.max(0, Number.parseInt(wholePart, 10) || 0);
  const remainder = Math.min(Math.max(Number.parseInt(decimalPart.slice(0, 1), 10) || 0, 0), 2);
  return whole * 3 + remainder;
}

function formatMetricValue(metric, value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "-";
  const number = Number(value);
  if (metric.kind === "average") {
    return number.toFixed(3).replace(/^0/, "");
  }
  if (metric.kind === "percent") {
    return `${number.toFixed(1)}%`;
  }
  if (metric.kind === "plus") {
    return Math.round(number).toString();
  }
  return number.toFixed(metric.digits ?? 1);
}

function formatDenominator(row) {
  if (row.source === "pitch") return `${row.denominator}球`;
  if (config.thresholdKind === "innings") return formatInningsFromOuts(row.denominator);
  return `${row.denominator}`;
}

function currentMetric() {
  return config.metrics.find((metric) => metric.key === state.metricKey) || config.metrics[0];
}

function baseRows() {
  return state.rows.filter((row) => {
    if (state.year && row.year !== state.year) return false;
    if (state.league !== "all" && row.league !== state.league) return false;
    if (state.team !== "all" && row.team !== state.team) return false;
    return true;
  });
}

function availableYears() {
  return [...new Set(state.rows.map((row) => row.year).filter(Boolean))].sort((a, b) => b.localeCompare(a));
}

function availableTeams() {
  const rows = state.rows.filter((row) => {
    if (state.year && row.year !== state.year) return false;
    if (state.league !== "all" && row.league !== state.league) return false;
    return true;
  });
  return [...new Set(rows.map((row) => row.team).filter(Boolean))].sort(compareTeam);
}

function teamGamesForRow(row) {
  if (row.year === "2025") return 143;
  const gamesForYear = state.teamGamesByYear.get(row.year);
  if (!gamesForYear) return null;
  const counts = rowTeams(row).map((team) => gamesForYear.get(team)).filter((value) => Number.isFinite(value));
  if (!counts.length) return null;
  return Math.max(...counts);
}

function qualificationThreshold(row) {
  if (row.year === "2025") return config.fixedQualification;
  if (row.year === "2026") {
    const games = teamGamesForRow(row);
    if (!games) return 0;
    if (config.thresholdKind === "plateAppearances") return Math.floor(games * 3.1);
    return games * 3;
  }
  return 0;
}

function rowDenominator(row) {
  if (config.thresholdKind === "innings") return Number(row.inningsOuts) || 0;
  return Number(row.plateAppearances) || 0;
}

function passesThreshold(row) {
  const denominator = rowDenominator(row);
  if (state.thresholdMode === "qualified") {
    return denominator >= qualificationThreshold(row);
  }
  return denominator >= state.customThreshold;
}

function metricRows() {
  const metric = currentMetric();
  const rows = baseRows().filter((row) => passesThreshold(row));
  if (metric.source === "pitch") {
    return rows
      .flatMap((playerRow) =>
        (playerRow.seasonDashboard?.pitchMix || []).map((pitchRow) => {
          const value = parseNumber(pitchRow[metric.field]);
          return {
            source: "pitch",
            year: playerRow.year,
            league: playerRow.league,
            team: playerRow.team,
            player: playerRow.player,
            pitchType: pitchRow.pitchType,
            value,
            denominator: Number(pitchRow.count) || 0,
            playerDenominator: rowDenominator(playerRow),
          };
        })
      )
      .filter((row) => row.value !== null && row.denominator > 0);
  }
  return rows
    .map((row) => {
      const value = parseNumber(row[metric.field]);
      return {
        source: "player",
        year: row.year,
        league: row.league,
        team: row.team,
        player: row.player,
        value,
        denominator: rowDenominator(row),
        raw: row,
      };
    })
    .filter((row) => row.value !== null);
}

function sortedRows() {
  const metric = currentMetric();
  return metricRows().sort((a, b) => {
    if (a.value !== b.value) {
      return metric.lowerIsBetter ? a.value - b.value : b.value - a.value;
    }
    if (b.denominator !== a.denominator) return b.denominator - a.denominator;
    const teamCompare = compareTeam(a.team, b.team);
    if (teamCompare !== 0) return teamCompare;
    return a.player.localeCompare(b.player, "ja");
  });
}

function displayedRows() {
  return sortedRows().slice(0, state.limit);
}

function defaultCustomThreshold() {
  const rows = baseRows();
  if (!rows.length) return 0;
  if (state.year === "2025") return config.fixedQualification;
  const thresholds = rows.map(qualificationThreshold).filter((value) => Number.isFinite(value));
  if (!thresholds.length) return 0;
  return Math.min(...thresholds);
}

function maxThreshold() {
  return baseRows().reduce((max, row) => Math.max(max, rowDenominator(row)), 0);
}

function thresholdDisplay(value) {
  return config.thresholdKind === "innings" ? formatInningsFromOuts(value) : `${value}`;
}

function renderYearOptions() {
  const years = availableYears();
  if (!state.year || !years.includes(state.year)) {
    state.year = years[0] || "";
  }
  els.yearSelect.innerHTML = years
    .map((year) => `<option value="${escapeHtml(year)}" ${year === state.year ? "selected" : ""}>${escapeHtml(year)}年度</option>`)
    .join("");
}

function renderLeagueOptions() {
  const options = [
    { value: "all", label: "すべてのリーグ" },
    { value: "セ", label: "セ・リーグ" },
    { value: "パ", label: "パ・リーグ" },
  ];
  els.leagueSelect.innerHTML = options
    .map((option) => `<option value="${option.value}" ${option.value === state.league ? "selected" : ""}>${option.label}</option>`)
    .join("");
}

function renderTeamOptions() {
  const teams = availableTeams();
  if (state.team !== "all" && !teams.includes(state.team)) {
    state.team = "all";
  }
  els.teamSelect.innerHTML = [
    '<option value="all">すべての球団</option>',
    ...teams.map((team) => `<option value="${escapeHtml(team)}" ${team === state.team ? "selected" : ""}>${escapeHtml(team)}</option>`),
  ].join("");
}

function renderMetricOptions() {
  els.metricSelect.innerHTML = config.metrics
    .map((metric) => `<option value="${metric.key}" ${metric.key === state.metricKey ? "selected" : ""}>${escapeHtml(metric.label)}</option>`)
    .join("");
}

function renderThresholdControls() {
  els.thresholdField.classList.remove("is-hidden");
  const maxValue = maxThreshold();
  if (state.customThreshold === null || state.customThreshold === undefined) {
    state.customThreshold = defaultCustomThreshold();
  }
  state.customThreshold = Math.min(Number(state.customThreshold) || 0, maxValue);
  const customMode = state.thresholdMode === "custom";
  els.thresholdLabel.textContent = config.thresholdLabel;
  els.thresholdMode.innerHTML = [
    `<option value="qualified" ${state.thresholdMode === "qualified" ? "selected" : ""}>${config.qualifiedLabel}</option>`,
    `<option value="custom" ${customMode ? "selected" : ""}>${config.customLabel}</option>`,
  ].join("");
  els.thresholdRange.max = `${maxValue}`;
  els.thresholdRange.value = `${state.customThreshold}`;
  els.thresholdRange.disabled = !customMode;
  els.thresholdInput.disabled = !customMode;
  els.thresholdInput.value = thresholdDisplay(customMode ? state.customThreshold : defaultCustomThreshold());
  els.thresholdMaxLabel.textContent = thresholdDisplay(maxValue);
}

function truncateLabel(value, maxLength = 9) {
  const text = `${value || ""}`;
  return text.length > maxLength ? `${text.slice(0, maxLength)}…` : text;
}

function chartAxisMax(metric, maxValue) {
  if (!Number.isFinite(maxValue) || maxValue <= 0) return 1;
  if (metric.kind === "percent") return Math.min(100, Math.ceil(maxValue / 10) * 10);
  if (metric.kind === "plus") return Math.ceil(maxValue / 10) * 10;
  if (metric.kind === "average") return Math.ceil(maxValue * 20) / 20;
  return Math.ceil(maxValue * 2) / 2;
}

function renderTable(rows) {
  const metric = currentMetric();
  const pitchMetric = metric.source === "pitch";
  if (!rows.length) {
    return '<div class="section-empty">条件に合うランキングデータがありません。</div>';
  }
  const rowsHtml = rows
    .map(
      (row, index) => `
        <tr>
          <td>${index + 1}</td>
          <td>${escapeHtml(row.player)}</td>
          ${pitchMetric ? `<td>${escapeHtml(row.pitchType || "-")}</td>` : ""}
          <td>${escapeHtml(row.team || "-")}</td>
          <td>${formatDenominator(row)}</td>
          <td>${escapeHtml(formatMetricValue(metric, row.value))}</td>
        </tr>
      `
    )
    .join("");
  return `
    <div class="table-scroll ranking-table-scroll">
      <table class="data-table ranking-table">
        <thead>
          <tr>
            <th>順位</th>
            <th>選手</th>
            ${pitchMetric ? "<th>球種</th>" : ""}
            <th>球団</th>
            <th>${pitchMetric ? "球数" : config.denominatorLabel}</th>
            <th>${escapeHtml(metric.label)}</th>
          </tr>
        </thead>
        <tbody>${rowsHtml}</tbody>
      </table>
    </div>
  `;
}

function renderChart(rows) {
  const metric = currentMetric();
  if (!rows.length) {
    return '<div class="section-empty">グラフデータがありません。</div>';
  }
  const values = rows.map((row) => Number(row.value)).filter((value) => Number.isFinite(value));
  const maxValue = Math.max(...values, 0);
  const yMax = chartAxisMax(metric, maxValue);
  const plotLeft = 56;
  const plotTop = 22;
  const plotHeight = 230;
  const labelHeight = 96;
  const gap = rows.length > 10 ? 52 : 66;
  const plotWidth = Math.max(460, rows.length * gap);
  const width = plotLeft + plotWidth + 24;
  const height = plotTop + plotHeight + labelHeight;
  const barWidthValue = Math.min(30, gap * 0.48);
  const ticks = [1, 0.75, 0.5, 0.25, 0];
  const tickLines = ticks
    .map((ratio) => {
      const value = yMax * ratio;
      const y = plotTop + plotHeight - ratio * plotHeight;
      return `
        <g>
          <line x1="${plotLeft}" y1="${y.toFixed(1)}" x2="${(plotLeft + plotWidth).toFixed(1)}" y2="${y.toFixed(1)}" class="ranking-chart-grid-line"></line>
          <text x="${plotLeft - 8}" y="${(y + 4).toFixed(1)}" class="ranking-chart-y-label">${escapeHtml(formatMetricValue(metric, value))}</text>
        </g>
      `;
    })
    .join("");
  const bars = rows
    .map((row, index) => {
      const x = plotLeft + index * gap + (gap - barWidthValue) / 2;
      const barHeight = yMax ? (Number(row.value) / yMax) * plotHeight : 0;
      const y = plotTop + plotHeight - barHeight;
      const label = row.pitchType ? `${row.player} / ${row.pitchType}` : row.player;
      const xCenter = x + barWidthValue / 2;
      return `
        <g>
          <title>${escapeHtml(`${label}\n${metric.label}: ${formatMetricValue(metric, row.value)}`)}</title>
          <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barWidthValue.toFixed(1)}" height="${Math.max(barHeight, 2).toFixed(1)}" class="ranking-chart-bar"></rect>
          <text x="${xCenter.toFixed(1)}" y="${(y - 7).toFixed(1)}" class="ranking-chart-value">${escapeHtml(formatMetricValue(metric, row.value))}</text>
          <text x="${xCenter.toFixed(1)}" y="${(plotTop + plotHeight + 18).toFixed(1)}" class="ranking-chart-x-label" transform="rotate(-45 ${xCenter.toFixed(1)} ${(plotTop + plotHeight + 18).toFixed(1)})">${escapeHtml(truncateLabel(row.player))}</text>
        </g>
      `;
    })
    .join("");
  return `
    <div class="ranking-chart-scroll">
      <svg class="ranking-axis-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(metric.label)}ランキング">
        ${tickLines}
        <line x1="${plotLeft}" y1="${plotTop}" x2="${plotLeft}" y2="${plotTop + plotHeight}" class="ranking-chart-axis-line"></line>
        <line x1="${plotLeft}" y1="${plotTop + plotHeight}" x2="${plotLeft + plotWidth}" y2="${plotTop + plotHeight}" class="ranking-chart-axis-line"></line>
        ${bars}
      </svg>
    </div>
  `;
}

function renderRanking() {
  const metric = currentMetric();
  const allRows = sortedRows();
  const rows = allRows.slice(0, state.limit);
  els.rankingResultCount.textContent = `${allRows.length}件`;
  els.rankingNote.textContent = "";
  els.rankingBody.innerHTML = `
    <div class="ranking-content-grid">
      <article class="ranking-table-card">
        <div class="card-head ranking-card-head">
          <h3>${escapeHtml(metric.label)} ランキング</h3>
          <span class="result-count">上位${state.limit}件</span>
        </div>
        ${renderTable(rows)}
      </article>
      <article class="ranking-chart-card">
        <div class="card-head ranking-card-head">
          <h3>${escapeHtml(metric.label)}</h3>
          <span class="result-count">上位${state.limit}件</span>
        </div>
        ${renderChart(rows)}
      </article>
    </div>
  `;
}

function render() {
  renderYearOptions();
  renderLeagueOptions();
  renderTeamOptions();
  renderMetricOptions();
  renderThresholdControls();
  if (state.error) {
    els.rankingBody.innerHTML = `<div class="section-empty">${escapeHtml(state.error)}</div>`;
    return;
  }
  renderRanking();
}

function rebuildTeamGames(context) {
  const gamesByTeam = new Map();
  for (const game of context?.games || []) {
    if (game.status && game.status !== "試合終了") continue;
    const year = `${game.date || ""}`.slice(0, 4);
    if (!year) continue;
    if (!gamesByTeam.has(year)) gamesByTeam.set(year, new Map());
    const bucket = gamesByTeam.get(year);
    for (const team of [game.homeTeam, game.awayTeam]) {
      const normalized = normalizeTeam(team || "");
      if (!normalized) continue;
      bucket.set(normalized, (bucket.get(normalized) || 0) + 1);
    }
  }
  state.teamGamesByYear = gamesByTeam;
}

function bindEvents() {
  els.yearSelect.addEventListener("change", (event) => {
    state.year = event.target.value;
    state.team = "all";
    state.customThreshold = defaultCustomThreshold();
    render();
  });
  els.leagueSelect.addEventListener("change", (event) => {
    state.league = event.target.value;
    state.team = "all";
    state.customThreshold = defaultCustomThreshold();
    render();
  });
  els.teamSelect.addEventListener("change", (event) => {
    state.team = event.target.value;
    state.customThreshold = defaultCustomThreshold();
    render();
  });
  els.metricSelect.addEventListener("change", (event) => {
    state.metricKey = event.target.value;
    state.thresholdMode = "qualified";
    state.customThreshold = defaultCustomThreshold();
    render();
  });
  els.limitSelect.addEventListener("change", (event) => {
    state.limit = Number(event.target.value) || 10;
    render();
  });
  els.thresholdMode.addEventListener("change", (event) => {
    state.thresholdMode = event.target.value;
    state.customThreshold = defaultCustomThreshold();
    render();
  });
  els.thresholdRange.addEventListener("input", (event) => {
    state.customThreshold = Number(event.target.value) || 0;
    render();
  });
  els.thresholdInput.addEventListener("change", (event) => {
    state.customThreshold =
      config.thresholdKind === "innings"
        ? parseInningsToOuts(event.target.value)
        : Math.max(0, Number.parseInt(event.target.value, 10) || 0);
    render();
  });
  els.thresholdInput.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    els.thresholdInput.dispatchEvent(new Event("change"));
  });
}

async function init() {
  bindEvents();
  try {
    const [rankingResponse, contextResponse] = await Promise.all([
      fetch(config.datasetUrl, { cache: "no-store" }),
      fetch("./sportsnavi_game_context_2026.json?v=20260429-1", { cache: "no-store" }).catch(() => null),
    ]);
    if (!rankingResponse.ok) throw new Error(`HTTP ${rankingResponse.status}`);
    const payload = await rankingResponse.json();
    state.rows = payload.players || [];
    if (contextResponse?.ok) {
      rebuildTeamGames(await contextResponse.json());
    }
  } catch (error) {
    state.error = error.message || "ランキングデータを読み込めませんでした。";
  }
  state.year = availableYears()[0] || "";
  state.customThreshold = defaultCustomThreshold();
  render();
}

init();
