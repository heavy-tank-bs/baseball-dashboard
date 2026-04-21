const TYPE_CONFIG = {
  pitcher: {
    label: "投手",
    datasetUrl: "./player_totals.json?v=20260421-04",
    annualHref: "./annual.html",
    annualLabel: "年度別投手成績へ戻る",
    idKey: "pitcherId",
    metrics: [
      { key: "games", label: "登板", kind: "number", digits: 0, default: true },
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
      { key: "walks", label: "与四球", kind: "number", digits: 0 },
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
    datasetUrl: "./batter_totals.json?v=20260421-04",
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

const state = {
  config: null,
  rows: [],
  currentRow: null,
  previousRow: null,
  activeMetricKeys: [],
  error: "",
};

const els = {
  compareEyebrow: document.getElementById("compareEyebrow"),
  compareTitle: document.getElementById("compareTitle"),
  compareSubtitle: document.getElementById("compareSubtitle"),
  comparePlayerName: document.getElementById("comparePlayerName"),
  compareDescription: document.getElementById("compareDescription"),
  compareBackLink: document.getElementById("compareBackLink"),
  compareSeasonGrid: document.getElementById("compareSeasonGrid"),
  compareMetricCount: document.getElementById("compareMetricCount"),
  metricToggleGroup: document.getElementById("metricToggleGroup"),
  compareCardGrid: document.getElementById("compareCardGrid"),
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

function formatMetricDelta(metric, delta) {
  if (delta === null || delta === undefined) return "比較不可";
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

function metricMap(config) {
  return Object.fromEntries(config.metrics.map((metric) => [metric.key, metric]));
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
      ["登板", `${row.games ?? "-"}試合`],
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

function renderSeasonCard(row, config, heading) {
  if (!row) {
    return `
      <article class="season-meta-card compare-season-card empty">
        <span>${escapeHtml(heading)}</span>
        <strong>データなし</strong>
        <small>前年データがまだありません。</small>
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

function renderMetricToggles() {
  const buttons = state.config.metrics
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
  els.metricToggleGroup.innerHTML = buttons;
  els.metricToggleGroup.querySelectorAll("[data-metric-key]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.metricKey || "";
      if (!key) return;
      if (state.activeMetricKeys.includes(key)) {
        state.activeMetricKeys = state.activeMetricKeys.filter((item) => item !== key);
      } else {
        state.activeMetricKeys = [...state.activeMetricKeys, key];
      }
      renderComparisonCards();
      renderMetricToggles();
    });
  });
}

function renderComparisonCards() {
  els.compareMetricCount.textContent = `${state.activeMetricKeys.length}項目`;
  if (!state.currentRow) {
    els.compareCardGrid.innerHTML = `<div class="section-empty compare-empty">${escapeHtml(state.error || "選手データを読み込めませんでした。")}</div>`;
    return;
  }
  if (!state.activeMetricKeys.length) {
    els.compareCardGrid.innerHTML = '<div class="section-empty compare-empty">比較したい指標を選択してください。</div>';
    return;
  }
  const metricsByKey = metricMap(state.config);
  const cards = state.activeMetricKeys
    .map((key) => metricsByKey[key])
    .filter(Boolean)
    .map((metric) => {
      const leftValue = numericMetricValue(metric, state.previousRow);
      const rightValue = numericMetricValue(metric, state.currentRow);
      const delta = leftValue === null || rightValue === null ? null : rightValue - leftValue;
      const direction = comparisonDirection(metric, delta);
      const deltaLabel = formatMetricDelta(metric, delta);
      return `
        <article class="compare-card">
          <span>${escapeHtml(metric.label)}</span>
          <div class="compare-values">
            <strong>${escapeHtml(formatMetricValue(metric, state.previousRow))}</strong>
            <span class="compare-arrow compare-arrow--${direction}">${direction === "up" ? "↑" : direction === "down" ? "↓" : "→"}</span>
            <strong>${escapeHtml(formatMetricValue(metric, state.currentRow))}</strong>
          </div>
          <p class="compare-delta compare-delta--${direction}">${escapeHtml(deltaLabel)}</p>
        </article>
      `;
    })
    .join("");
  els.compareCardGrid.innerHTML = cards;
}

function renderSummary() {
  const currentRow = state.currentRow;
  const previousRow = state.previousRow;
  els.compareEyebrow.textContent = state.config.label;
  els.compareBackLink.href = state.config.annualHref;
  els.compareBackLink.textContent = state.config.annualLabel;
  if (!currentRow) {
    els.compareTitle.textContent = "前年比較ダッシュボード";
    els.compareSubtitle.textContent = "";
    els.comparePlayerName.textContent = "選手が見つかりません";
    els.compareDescription.textContent = state.error || "リンク元の条件に合う成績がありません。";
    els.compareSeasonGrid.innerHTML = "";
    return;
  }
  const previousLabel = previousRow ? `${previousRow.year}年度` : "前年データなし";
  els.compareTitle.textContent = `${currentRow.player} 前年比較`;
  els.compareSubtitle.textContent = `${currentRow.year}年度 ${state.config.label}`;
  els.comparePlayerName.textContent = currentRow.player;
  els.compareDescription.textContent = previousRow
    ? `${previousLabel} と ${currentRow.year}年度の成績差分`
    : `${currentRow.year}年度の前年データはまだありません`;
  document.title = `${currentRow.player} | 前年比較`;
  els.compareSeasonGrid.innerHTML = [
    renderSeasonCard(previousRow, state.config, previousLabel),
    renderSeasonCard(currentRow, state.config, `${currentRow.year}年度`),
  ].join("");
}

async function init() {
  const params = currentParams();
  state.config = TYPE_CONFIG[params.get("type")] || TYPE_CONFIG.pitcher;
  state.activeMetricKeys = state.config.metrics.filter((metric) => metric.default).map((metric) => metric.key);
  try {
    const response = await fetch(state.config.datasetUrl, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    state.rows = payload.players || [];
    state.currentRow = findCurrentRow(state.rows, params, state.config);
    state.previousRow = findPreviousRow(state.rows, state.currentRow, params, state.config);
    if (!state.currentRow) {
      state.error = "リンク元の選手データが見つかりませんでした。";
    }
  } catch (error) {
    state.error = error.message || "前年比較データの取得に失敗しました。";
  }
  renderSummary();
  renderMetricToggles();
  renderComparisonCards();
}

init();
