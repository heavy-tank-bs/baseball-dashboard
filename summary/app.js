const manifest = window.PITCH_DASHBOARD_MANIFEST || {
  teams: [],
  dates: [],
  players: [],
  entries: [],
  entryCount: 0,
  teamCount: 0,
  dateCount: 0,
};

const TEAM_META = [
  { name: "巨人", league: "セ" },
  { name: "阪神", league: "セ" },
  { name: "DeNA", league: "セ" },
  { name: "広島", league: "セ" },
  { name: "ヤクルト", league: "セ" },
  { name: "中日", league: "セ" },
  { name: "ソフトバンク", league: "パ" },
  { name: "日本ハム", league: "パ" },
  { name: "ロッテ", league: "パ" },
  { name: "オリックス", league: "パ" },
  { name: "西武", league: "パ" },
  { name: "東北楽天", league: "パ" },
];

const SECTION_META = [
  { id: "mix", label: "球種比率 / 球種別サマリ" },
  { id: "inning", label: "イニング別サマリ" },
  { id: "heat", label: "配球チャート" },
  { id: "outcomes", label: "アウト内容" },
  { id: "finish", label: "決め球 / 球速推移" },
  { id: "count", label: "カウント別球種割合" },
];

const state = {
  team: "all",
  date: "all",
  player: "all",
  query: "",
  selectedId: null,
  section: "mix",
  selectedInningPitch: "all",
  selectedHeatPitch: "all",
};

const els = {
  searchInput: document.getElementById("searchInput"),
  clearTeamButton: document.getElementById("clearTeamButton"),
  teamFilters: document.getElementById("teamFilters"),
  dateSelect: document.getElementById("dateSelect"),
  playerSelect: document.getElementById("playerSelect"),
  resultCount: document.getElementById("resultCount"),
  resultList: document.getElementById("resultList"),
  viewerPanel: document.getElementById("viewerPanel"),
};

const PITCH_CHART_FRAME = {
  width: 320,
  height: 392,
  stageX: 34,
  stageY: 28,
  stageWidth: 252,
  stageHeight: 308,
};

function formatPercent(value) {
  if (value === null || value === undefined || value === "") return "-";
  return `${Number(value).toFixed(1)}%`;
}

function formatAverage(value) {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  if (!Number.isFinite(number)) return `${value}`;
  const normalized = Math.abs(number) > 1 ? number / 100 : number;
  return normalized.toFixed(3);
}

function formatSpeed(value) {
  if (value === null || value === undefined || value === "" || value === "-") return "-";
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(1)} km/h` : `${value}`;
}

function escapeHtml(value) {
  return `${value ?? ""}`
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function pitcherViewLabels(hand) {
  return hand === "右" ? ["外角", "内角"] : ["内角", "外角"];
}

function byTeam(name) {
  const summary = manifest.teams.find((team) => team.name === name);
  return summary || { name, count: 0, hasData: false };
}

function filteredEntries() {
  const query = state.query.trim().toLowerCase();
  return manifest.entries.filter((entry) => {
    if (state.team !== "all" && entry.team !== state.team) return false;
    if (state.date !== "all" && entry.date !== state.date) return false;
    if (state.player !== "all" && entry.player !== state.player) return false;
    if (!query) return true;
    const haystack = [entry.title, entry.player, entry.team, entry.matchup, entry.prefix, entry.date]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
}

function entriesForPlayerOptions() {
  return manifest.entries.filter((entry) => {
    if (state.team !== "all" && entry.team !== state.team) return false;
    if (state.date !== "all" && entry.date !== state.date) return false;
    return true;
  });
}

function selectedEntry(entries) {
  if (!entries.length) return null;
  const found = entries.find((entry) => entry.id === state.selectedId);
  if (found) return found;
  state.selectedId = entries[0].id;
  return entries[0];
}

function statCell(label, value) {
  return `
    <div class="result-stat">
      <span>${label}</span>
      <strong>${value || "-"}</strong>
    </div>
  `;
}

function pitchPreview(pitchMix = []) {
  if (!pitchMix.length) return "";
  const segments = pitchMix
    .map((row) => `<span class="preview-segment" style="width:${row.ratio}%;background:${row.color}"></span>`)
    .join("");
  const labels = pitchMix
    .slice(0, 3)
    .map((row) => `<span>${row.pitchType} ${row.ratio.toFixed(1)}%</span>`)
    .join("");
  return `
    <div class="preview-bar">${segments}</div>
    <div class="preview-labels">${labels}</div>
  `;
}

function renderTeamFilters() {
  const teams = new Map(TEAM_META.map((team) => [team.name, team]));
  manifest.teams.forEach((team) => {
    if (!teams.has(team.name)) teams.set(team.name, { name: team.name, league: "-" });
  });

  els.teamFilters.innerHTML = "";

  [...teams.values()].forEach((team) => {
    const summary = byTeam(team.name);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "team-chip";
    if (!summary.hasData) button.classList.add("disabled");
    if (state.team === team.name) button.classList.add("active");
    button.innerHTML = `<span>${team.name}</span><span class="count">${summary.count}</span>`;
    button.disabled = !summary.hasData;
    button.addEventListener("click", () => {
      state.team = team.name;
      state.player = "all";
      rerender();
    });
    els.teamFilters.appendChild(button);
  });
}

function renderDateOptions() {
  const current = state.date;
  els.dateSelect.innerHTML = '<option value="all">すべての日付</option>';
  manifest.dates.forEach(({ date, count }) => {
    const option = document.createElement("option");
    option.value = date;
    option.textContent = `${date} (${count})`;
    if (date === current) option.selected = true;
    els.dateSelect.appendChild(option);
  });
}

function renderPlayerOptions() {
  const current = state.player;
  const counts = new Map();
  entriesForPlayerOptions().forEach((entry) => {
    counts.set(entry.player, (counts.get(entry.player) || 0) + 1);
  });

  const names = [...counts.keys()].sort((a, b) => a.localeCompare(b, "ja"));
  if (current !== "all" && !counts.has(current)) {
    state.player = "all";
  }

  els.playerSelect.innerHTML = '<option value="all">すべての選手</option>';
  names.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = `${name} (${counts.get(name)})`;
    if (name === state.player) option.selected = true;
    els.playerSelect.appendChild(option);
  });
}

function renderResultList(entries) {
  els.resultCount.textContent = `${entries.length}件`;
  els.resultList.innerHTML = "";

  if (!entries.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state slim";
    empty.innerHTML = `
      <p class="empty-kicker">No Results</p>
      <h2>条件に合うダッシュボードがありません</h2>
      <p>検索語かフィルタ条件を調整してください。</p>
    `;
    els.resultList.appendChild(empty);
    return;
  }

  entries.forEach((entry) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "result-card";
    if (entry.id === state.selectedId) button.classList.add("active");
    button.innerHTML = `
      <div class="result-meta">
        <p class="team-date">${entry.team} / ${entry.date}</p>
        <h3>${entry.player}</h3>
        <p>${entry.matchup || "-"}</p>
        <div class="result-stats">
          ${statCell("投球回", entry.statline.innings)}
          ${statCell("球数", entry.statline.pitches)}
          ${statCell("奪三振", entry.statline.k)}
          ${statCell("与四球", entry.statline.bb)}
        </div>
        ${pitchPreview(entry.dashboard?.pitchMix)}
      </div>
    `;
    button.addEventListener("click", () => {
      state.selectedId = entry.id;
      rerender();
    });
    els.resultList.appendChild(button);
  });
}

function legendItems(rows = []) {
  return rows
    .map(
      (row) => `
        <li>
          <span class="legend-swatch" style="background:${row.color}"></span>
          <span>${row.pitchType}</span>
        </li>
      `
    )
    .join("");
}

function normalizePitchSelection(entry, key) {
  const rows = entry?.dashboard?.pitchMix || [];
  if (state[key] === "all") return;
  if (!rows.some((row) => row.pitchType === state[key])) {
    state[key] = "all";
  }
}

function renderPitchMixSection(dashboard) {
  const rows = dashboard.pitchMix || [];
  if (!rows.length) {
    return '<div class="section-empty">球種データがありません。</div>';
  }

  const stacked = rows
    .map(
      (row) => `
        <div class="stack-segment" style="width:${row.ratio}%;background:${row.color}">
          <span>${row.ratio >= 12 ? `${row.ratio.toFixed(1)}%` : ""}</span>
        </div>
      `
    )
    .join("");

  const cards = rows
    .map(
      (row) => `
        <article class="pitch-card">
          <div class="pitch-card-head">
            <span class="legend-swatch" style="background:${row.color}"></span>
            <strong>${row.pitchType}</strong>
          </div>
          <div class="pitch-card-metrics">
            <span>${row.count}球</span>
            <span>${row.ratio.toFixed(1)}%</span>
            <span>${formatSpeed(row.avgSpeed)}</span>
          </div>
        </article>
      `
    )
    .join("");

  return `
    <div class="section-grid page-one" style="grid-template-columns:1fr">
      <section class="dashboard-card">
        <div class="card-head">
          <h3>球種比率</h3>
        </div>
        <div class="stack-bar">${stacked}</div>
        <div class="pitch-card-grid">${cards}</div>
      </section>
      <section class="dashboard-card">
        <div class="card-head">
          <h3>球種別サマリ</h3>
        </div>
        ${renderPitchSummaryTable(rows)}
      </section>
    </div>
  `;
}

function renderPitchSummaryTable(rows) {
  const body = rows
    .map(
      (row) => `
        <tr>
          <td class="pitch-name-cell">
            <span class="legend-swatch" style="background:${row.color}"></span>
            <span>${row.pitchType}</span>
          </td>
          <td>${formatSpeed(row.avgSpeed)}</td>
          <td>${row.count}</td>
          <td>${row.whiffCount ?? 0}</td>
          <td>${formatPercent(row.whiff)}</td>
          <td>${row.atBats ?? 0}</td>
          <td>${row.singles ?? 0}</td>
          <td>${row.doubles ?? 0}</td>
          <td>${row.triples ?? 0}</td>
          <td>${row.homeRuns ?? 0}</td>
          <td>${row.grounders ?? 0}</td>
          <td>${row.flyBalls ?? 0}</td>
          <td>${row.strikeouts ?? 0}</td>
          <td>${formatAverage(row.hitRate)}</td>
        </tr>
      `
    )
    .join("");

  return `
    <div class="table-scroll">
      <table class="data-table wide-table pitch-summary-table">
        <thead>
          <tr>
            <th>球種</th>
            <th>平均球速</th>
            <th>球数</th>
            <th>空振数</th>
            <th>空振率</th>
            <th>被打数</th>
            <th>単打</th>
            <th>二塁打</th>
            <th>三塁打</th>
            <th>本塁打</th>
            <th>ゴロ</th>
            <th>フライ</th>
            <th>三振</th>
            <th>被打率</th>
          </tr>
        </thead>
        <tbody>${body}</tbody>
      </table>
    </div>
  `;
}

function renderInningSection(dashboard) {
  const inningSummary = dashboard.inningSummary || {};
  const legendRows = dashboard.pitchMix || [];
  const selectedPitch = state.selectedInningPitch;
  const inningRows =
    selectedPitch === "all"
      ? inningSummary.all || dashboard.inningRows || []
      : inningSummary.byPitchType?.[selectedPitch] || [];
  return `
    <div class="section-grid page-two">
      <section class="dashboard-card">
        <div class="card-head">
          <h3>イニング別サマリ</h3>
        </div>
        ${renderPitchFilterLegend(legendRows, state.selectedInningPitch, "inning")}
        ${renderInningTable(inningRows)}
      </section>
    </div>
  `;
}

function renderPitchFilterLegend(rows, selectedPitch, scope) {
  const buttons = [
    `
      <button
        type="button"
        class="heat-legend-button ${selectedPitch === "all" ? "active" : ""}"
        data-${scope}-pitch="all"
      >
        <span>すべて</span>
      </button>
    `,
    ...rows.map(
      (row) => `
        <button
          type="button"
          class="heat-legend-button ${selectedPitch === row.pitchType ? "active" : ""}"
          data-${scope}-pitch="${escapeHtml(row.pitchType)}"
        >
          <span class="legend-swatch" style="background:${row.color}"></span>
          <span>${row.pitchType}</span>
        </button>
      `
    ),
  ].join("");

  return `<div class="heat-legend">${buttons}</div>`;
}

function renderInningTable(rows) {
  const body = rows
    .map(
      (row) => `
        <tr>
          <td>${row.inning}回</td>
          <td>${formatSpeed(row.avgSpeed)}</td>
          <td>${row.count}</td>
          <td>${row.whiffCount ?? 0}</td>
          <td>${formatPercent(row.whiff)}</td>
          <td>${row.atBats ?? 0}</td>
          <td>${row.singles ?? 0}</td>
          <td>${row.doubles ?? 0}</td>
          <td>${row.triples ?? 0}</td>
          <td>${row.homeRuns ?? 0}</td>
          <td>${row.grounders ?? 0}</td>
          <td>${row.flyBalls ?? 0}</td>
          <td>${row.strikeouts ?? 0}</td>
          <td>${formatAverage(row.hitRate)}</td>
        </tr>
      `
    )
    .join("");

  return `
    <div class="table-scroll">
      <table class="data-table wide-table inning-table">
      <thead>
        <tr>
          <th>回</th>
          <th>平均球速</th>
          <th>球数</th>
          <th>空振数</th>
          <th>空振率</th>
          <th>被打数</th>
          <th>単打</th>
          <th>二塁打</th>
          <th>三塁打</th>
          <th>本塁打</th>
          <th>ゴロ</th>
          <th>フライ</th>
          <th>三振</th>
          <th>被打率</th>
        </tr>
      </thead>
      <tbody>${body}</tbody>
      </table>
    </div>
  `;
}

function renderHeatSection(dashboard) {
  const legendRows = dashboard.pitchMix || [];
  const pitchChart = dashboard.pitchChart || {};
  const bounds = pitchChart.bounds || {};
  const selectedPitch = state.selectedHeatPitch;
  const filterPoints = (points) =>
    selectedPitch === "all" ? points : points.filter((point) => point.pitchType === selectedPitch);

  return `
    <div class="section-grid page-heat">
      <section class="dashboard-card">
        <div class="card-head">
          <h3>配球チャート</h3>
        </div>
        ${renderPitchFilterLegend(legendRows, state.selectedHeatPitch, "heat")}
        <div class="heatmap-grid">
          ${renderPitchChartCard("vs 右打者", filterPoints(pitchChart.right || []), "右", bounds)}
          ${renderPitchChartCard("vs 左打者", filterPoints(pitchChart.left || []), "左", bounds)}
        </div>
      </section>
    </div>
  `;
}

function renderOutcomeSection(dashboard) {
  return `
    <div class="section-grid page-two">
      <section class="dashboard-card">
        <div class="card-head">
          <h3>アウト内容</h3>
        </div>
        ${renderOutcomeChart(dashboard.outcomes)}
      </section>
    </div>
  `;
}

function renderOutcomeChart(outcomes = {}) {
  const rows = outcomes.rows || [];
  const total = Number(outcomes.total) || 0;
  if (!rows.length || total <= 0) {
    return '<div class="section-empty">アウト内容データがありません。</div>';
  }

  const size = 320;
  const center = size / 2;
  const radius = 98;
  const strokeWidth = 42;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  const segments = rows
    .filter((row) => Number(row.count) > 0)
    .map((row) => {
      const dash = (Number(row.count) / total) * circumference;
      const isFullCircle = dash >= circumference - 0.1;
      const segment = isFullCircle
        ? `
          <circle
            cx="${center}"
            cy="${center}"
            r="${radius}"
            class="outcome-segment"
            style="stroke:${row.color};stroke-width:${strokeWidth}"
          ></circle>
        `
        : `
          <circle
            cx="${center}"
            cy="${center}"
            r="${radius}"
            class="outcome-segment"
            style="stroke:${row.color};stroke-width:${strokeWidth}"
            stroke-dasharray="${dash.toFixed(2)} ${(circumference - dash).toFixed(2)}"
            stroke-dashoffset="${(-offset).toFixed(2)}"
          ></circle>
        `;
      offset += dash;
      return segment;
    })
    .join("");

  const cards = rows
    .map(
      (row) => `
        <article class="outcome-item">
          <div class="outcome-item-head">
            <span class="legend-swatch" style="background:${row.color}"></span>
            <strong>${escapeHtml(row.label)}</strong>
          </div>
          <div class="outcome-item-values">
            <span>${row.count}件</span>
            <span>${formatPercent(row.ratio)}</span>
          </div>
        </article>
      `
    )
    .join("");

  return `
    <div class="outcome-dashboard">
      <div class="outcome-chart-shell">
        <svg viewBox="0 0 ${size} ${size}" class="outcome-chart" role="img" aria-label="アウト内容の円グラフ">
          <circle
            cx="${center}"
            cy="${center}"
            r="${radius}"
            class="outcome-track"
            style="stroke-width:${strokeWidth}"
          ></circle>
          <g transform="rotate(-90 ${center} ${center})">${segments}</g>
          <text x="${center}" y="${center - 18}" class="outcome-center-label">対象アウト</text>
          <text x="${center}" y="${center + 26}" class="outcome-center-value">${total}</text>
        </svg>
      </div>
      <div class="outcome-grid">${cards}</div>
    </div>
  `;
}

function renderPitchChartCard(title, points, hand, bounds = {}) {
  const chartWidth = PITCH_CHART_FRAME.width;
  const chartHeight = PITCH_CHART_FRAME.height;
  const stageX = PITCH_CHART_FRAME.stageX;
  const stageY = PITCH_CHART_FRAME.stageY;
  const stageWidth = PITCH_CHART_FRAME.stageWidth;
  const stageHeight = PITCH_CHART_FRAME.stageHeight;
  const zoneX = stageX + stageWidth * 0.2;
  const zoneY = stageY + stageHeight * 0.2;
  const zoneWidth = stageWidth * 0.6;
  const zoneHeight = stageHeight * 0.6;
  const fullWidth = Number(bounds.width) || 54;
  const fullHeight = Number(bounds.height) || 63;
  const [leftLabel, rightLabel] = pitcherViewLabels(hand);

  const gridLines = [1, 2]
    .map(
      (index) => `
        <line
          x1="${zoneX + (zoneWidth / 3) * index}"
          y1="${zoneY}"
          x2="${zoneX + (zoneWidth / 3) * index}"
          y2="${zoneY + zoneHeight}"
          class="pitch-chart-grid"
        ></line>
        <line
          x1="${zoneX}"
          y1="${zoneY + (zoneHeight / 3) * index}"
          x2="${zoneX + zoneWidth}"
          y2="${zoneY + (zoneHeight / 3) * index}"
          class="pitch-chart-grid"
        ></line>
      `
    )
    .join("");

  const markers = points
    .map((point) => {
      const cx = stageX + (Number(point.left) / fullWidth) * stageWidth;
      const cy = stageY + (Number(point.top) / fullHeight) * stageHeight;
      const radius = point.isFinalPitch ? 7 : 5.4;
      const speedLabel = point.speedLabel || formatSpeed(point.speed);
      const lines = [
        point.pitchType,
        speedLabel,
        point.result || "-",
        point.batter ? `打者: ${point.batter}` : "",
        point.pitchNo ? `球順: ${point.pitchNo}` : "",
        point.isFinalPitch ? "打席最終球" : "",
      ].filter(Boolean);
      return `
        <g class="pitch-point${point.isFinalPitch ? " final" : ""}" transform="translate(${cx.toFixed(1)} ${cy.toFixed(1)})">
          <title>${escapeHtml(lines.join("\n"))}</title>
          ${point.isFinalPitch ? `<circle class="pitch-point-ring" r="${(radius + 3.2).toFixed(1)}"></circle>` : ""}
          <circle class="pitch-point-core" r="${radius.toFixed(1)}" style="fill:${point.color}"></circle>
        </g>
      `;
    })
    .join("");

  return `
    <article class="heatmap-card">
      <div class="heatmap-head">
        <strong>${title}</strong>
        <div class="heatmap-sides">
          <span>${leftLabel}</span>
          <span>${rightLabel}</span>
        </div>
      </div>
      <div class="pitch-chart-wrap">
        <svg
          class="pitch-chart"
          viewBox="0 0 ${chartWidth} ${chartHeight}"
          role="img"
          aria-label="${escapeHtml(`${title} の配球チャート`)}"
        >
          <rect x="${stageX}" y="${stageY}" width="${stageWidth}" height="${stageHeight}" rx="18" class="pitch-chart-stage"></rect>
          <rect x="${zoneX}" y="${zoneY}" width="${zoneWidth}" height="${zoneHeight}" class="pitch-chart-zone"></rect>
          ${gridLines}
          <polygon
            points="${zoneX + zoneWidth * 0.35},${stageY + stageHeight} ${zoneX + zoneWidth * 0.65},${stageY + stageHeight} ${zoneX + zoneWidth * 0.56},${stageY + stageHeight + 22} ${zoneX + zoneWidth * 0.44},${stageY + stageHeight + 22}"
            class="pitch-chart-plate"
          ></polygon>
          ${markers}
        </svg>
      </div>
      ${!points.length ? '<p class="pitch-chart-note">該当投球なし</p>' : ""}
    </article>
  `;
}

function renderFinishSection(dashboard) {
  return `
    <div class="section-grid page-three">
      <section class="dashboard-card">
        <div class="card-head">
          <h3>決め球サマリ</h3>
        </div>
        ${renderFinishTable(dashboard.finish)}
      </section>
      <section class="dashboard-card">
        <div class="card-head inline">
          <h3>球速推移</h3>
          <span class="inline-label"><span class="legend-swatch navy"></span>ストレート</span>
        </div>
        ${renderVelocityChart(dashboard.velocity)}
      </section>
    </div>
  `;
}

function renderFinishTable(finish = {}) {
  const rows = finish.rows || [];
  if (!rows.length) {
    return '<div class="section-empty">三振打席の決め球データがありません。</div>';
  }

  const body = rows
    .map(
      (row) => `
        <tr>
          <td class="pitch-name-cell">
            <span class="legend-swatch" style="background:${row.color}"></span>
            <span>${row.pitchType}</span>
          </td>
          <td>${row.count}</td>
          <td>${formatPercent(row.ratio)}</td>
          <td>${row.looking}</td>
          <td>${row.swinging}</td>
        </tr>
      `
    )
    .join("");

  return `
    <table class="data-table">
      <thead>
        <tr>
          <th>球種</th>
          <th>球数</th>
          <th>割合</th>
          <th>見逃し</th>
          <th>空振</th>
        </tr>
      </thead>
      <tbody>${body}</tbody>
    </table>
  `;
}

function renderVelocityChart(velocity = {}) {
  const rows = velocity.rows || [];
  if (!rows.length) {
    return '<div class="section-empty">ストレートの球速データがありません。</div>';
  }

  const width = 920;
  const height = 320;
  const margin = { top: 24, right: 32, bottom: 42, left: 54 };
  const speeds = rows.map((row) => row.speed);
  const minSpeed = Math.min(...speeds);
  const maxSpeed = Math.max(...speeds);
  const range = Math.max(maxSpeed - minSpeed, 1);
  const maxPitchNo = Math.max(...rows.map((row) => row.pitchNo), 1);
  const baseColor = rows[0].color || "#0F2340";

  const x = (pitchNo) => margin.left + ((pitchNo - 1) / Math.max(maxPitchNo - 1, 1)) * (width - margin.left - margin.right);
  const y = (speed) => height - margin.bottom - ((speed - minSpeed) / range) * (height - margin.top - margin.bottom);

  const points = rows.map((row) => `${x(row.pitchNo)},${y(row.speed)}`).join(" ");
  const circles = rows
    .map((row) => `<circle cx="${x(row.pitchNo)}" cy="${y(row.speed)}" r="4" fill="${baseColor}"></circle>`)
    .join("");

  const gridValues = Array.from({ length: 4 }, (_, idx) => minSpeed + (range * idx) / 3);
  const gridLines = gridValues
    .map((value) => {
      const py = y(value);
      return `
        <line x1="${margin.left}" y1="${py}" x2="${width - margin.right}" y2="${py}" class="chart-grid"></line>
        <text x="${margin.left - 10}" y="${py + 4}" class="chart-axis chart-axis-left">${value.toFixed(1)}</text>
      `;
    })
    .join("");

  const markers = (velocity.markers || [])
    .filter((marker) => marker.pitchNo >= 1 && marker.pitchNo <= maxPitchNo)
    .map(
      (marker) => `
        <line x1="${x(marker.pitchNo)}" y1="${margin.top}" x2="${x(marker.pitchNo)}" y2="${height - margin.bottom}" class="chart-marker"></line>
        <text x="${x(marker.pitchNo) + 4}" y="${margin.top + 14}" class="chart-axis">${marker.inning}回</text>
      `
    )
    .join("");

  return `
    <div class="velocity-chart-wrap">
      <div class="velocity-chart-scroll">
      <svg viewBox="0 0 ${width} ${height}" class="velocity-chart" role="img" aria-label="球速推移">
        ${gridLines}
        ${markers}
        <polyline points="${points}" fill="none" stroke="${baseColor}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></polyline>
        ${circles}
        <text x="${width / 2}" y="${height - 10}" class="chart-axis chart-axis-bottom">投球番号</text>
      </svg>
      </div>
    </div>
  `;
}

function renderCountSection(dashboard) {
  const rows = dashboard.countMix || [];
  if (!rows.length) {
    return '<div class="section-empty">カウント別球種割合データがありません。</div>';
  }

  const legend = dashboard.pitchMix || [];
  const bars = rows
    .map((row) => {
      const segments = row.segments
        .filter((segment) => segment.count > 0)
        .map(
          (segment) => `
            <div class="count-segment" style="width:${segment.ratio}%;background:${segment.color}">
              <span>${segment.ratio >= 14 ? `${segment.ratio.toFixed(0)}%` : ""}</span>
            </div>
          `
        )
        .join("");
      return `
        <div class="count-row">
          <span class="count-label">${row.bucket}</span>
          <div class="count-bar">${segments}</div>
          <span class="count-total">${row.total}球</span>
        </div>
      `;
    })
    .join("");

  return `
    <section class="dashboard-card count-card">
      <div class="card-head">
        <h3>カウント別球種割合</h3>
      </div>
      <ul class="legend-list centered">${legendItems(legend)}</ul>
      <div class="count-chart">${bars}</div>
      <div class="count-axis">
        <span>0</span>
        <span>20</span>
        <span>40</span>
        <span>60</span>
        <span>80</span>
        <span>100%</span>
      </div>
    </section>
  `;
}

function renderMetaGrid(entry) {
  return `
    <div class="meta-grid">
      <article class="meta-card">
        <span>球団</span>
        <strong>${entry.team}</strong>
      </article>
      <article class="meta-card">
        <span>日付</span>
        <strong>${entry.dateLabel || entry.date}</strong>
      </article>
      <article class="meta-card">
        <span>選手名</span>
        <strong>${entry.player}</strong>
      </article>
      <article class="meta-card">
        <span>対戦カード</span>
        <strong>${entry.matchup || "-"}</strong>
      </article>
    </div>
  `;
}

function renderStatStrip(statline = {}) {
  const items = [
    ["投球回", statline.innings],
    ["球数", statline.pitches],
    ["対戦打者", statline.batters],
    ["被安打", statline.hits],
    ["奪三振", statline.k],
    ["与四球", statline.bb],
    ["自責点", statline.er],
    ["失点", statline.runs],
  ];
  return `
    <div class="stat-strip">
      ${items
        .map(
          ([label, value]) => `
            <article class="stat-pill">
              <span>${label}</span>
              <strong>${value || "-"}</strong>
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

function renderSection(entry) {
  const dashboard = entry.dashboard || {};
  switch (state.section) {
    case "inning":
      return renderInningSection(dashboard);
    case "heat":
      return renderHeatSection(dashboard);
    case "outcomes":
      return renderOutcomeSection(dashboard);
    case "finish":
      return renderFinishSection(dashboard);
    case "count":
      return renderCountSection(dashboard);
    case "mix":
    default:
      return renderPitchMixSection(dashboard);
  }
}

function renderViewer(entry) {
  if (!entry) {
    els.viewerPanel.classList.add("empty");
    els.viewerPanel.innerHTML = `
      <div class="empty-state">
        <p class="empty-kicker">Select Dashboard</p>
        <h2>左の一覧から投手を選択してください</h2>
        <p>生成済み JSON データのある投手のみ表示できます。</p>
      </div>
    `;
    return;
  }

  normalizePitchSelection(entry, "selectedInningPitch");
  normalizePitchSelection(entry, "selectedHeatPitch");
  els.viewerPanel.classList.remove("empty");
  const tabs = SECTION_META.map(
    (section) => `
      <button type="button" class="page-tab ${section.id === state.section ? "active" : ""}" data-section="${section.id}">
        ${section.label}
      </button>
    `
  ).join("");

  els.viewerPanel.innerHTML = `
    <div class="viewer-head">
      <div>
        <p class="hero-kicker">${entry.team} / ${entry.date}</p>
        <h2>${entry.player}</h2>
      </div>
    </div>
    ${renderMetaGrid(entry)}
    ${renderStatStrip(entry.statline)}
    <div class="page-tabs">${tabs}</div>
    <div class="native-stage">${renderSection(entry)}</div>
  `;

  els.viewerPanel.querySelectorAll("[data-section]").forEach((button) => {
    button.addEventListener("click", () => {
      state.section = button.dataset.section;
      renderViewer(entry);
    });
  });

  els.viewerPanel.querySelectorAll("[data-heat-pitch]").forEach((button) => {
    button.addEventListener("click", () => {
      const pitchType = button.dataset.heatPitch || "all";
      state.selectedHeatPitch = state.selectedHeatPitch === pitchType ? "all" : pitchType;
      renderViewer(entry);
    });
  });

  els.viewerPanel.querySelectorAll("[data-inning-pitch]").forEach((button) => {
    button.addEventListener("click", () => {
      const pitchType = button.dataset.inningPitch || "all";
      state.selectedInningPitch = state.selectedInningPitch === pitchType ? "all" : pitchType;
      renderViewer(entry);
    });
  });
}

function rerender() {
  renderTeamFilters();
  renderDateOptions();
  renderPlayerOptions();
  const entries = filteredEntries();
  const entry = selectedEntry(entries);
  renderResultList(entries);
  renderViewer(entry);
}

function bindEvents() {
  els.searchInput.addEventListener("input", (event) => {
    state.query = event.target.value;
    rerender();
  });

  els.clearTeamButton.addEventListener("click", () => {
    state.team = "all";
    state.player = "all";
    rerender();
  });

  els.dateSelect.addEventListener("change", (event) => {
    state.date = event.target.value;
    state.player = "all";
    rerender();
  });

  els.playerSelect.addEventListener("change", (event) => {
    state.player = event.target.value;
    rerender();
  });
}

bindEvents();
rerender();
