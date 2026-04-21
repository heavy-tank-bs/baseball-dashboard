const manifest = window.BATTER_GAME_MANIFEST || {
  teams: [],
  dates: [],
  players: [],
  entries: [],
  entryCount: 0,
  teamCount: 0,
  dateCount: 0,
};

const TEAM_META = [
  { name: "広島", league: "セ" },
  { name: "阪神", league: "セ" },
  { name: "DeNA", league: "セ" },
  { name: "巨人", league: "セ" },
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
  { id: "table", label: "打席別成績" },
  { id: "heat", label: "打席別ヒートマップ" },
];

const state = {
  team: "all",
  date: "all",
  player: "all",
  query: "",
  selectedId: null,
  section: "table",
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
  width: 288,
  height: 344,
  stageX: 30,
  stageY: 24,
  stageWidth: 228,
  stageHeight: 258,
};

function escapeHtml(value) {
  return `${value ?? ""}`
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatSpeed(value) {
  if (value === null || value === undefined || value === "" || value === "-") return "-";
  if (`${value}`.includes("km/h")) return `${value}`;
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(1)} km/h` : `${value}`;
}

function batterViewLabels(hand) {
  return hand === "右" ? ["外角", "内角"] : ["内角", "外角"];
}

function byTeam(name) {
  const summary = manifest.teams.find((team) => team.name === name);
  return summary || { name, count: 0, hasData: false };
}

function teamSortKey(team) {
  const index = TEAM_META.findIndex((row) => row.name === team);
  return [index === -1 ? TEAM_META.length : index, team];
}

function compareTeam(a, b) {
  const [aIndex, aName] = teamSortKey(a);
  const [bIndex, bName] = teamSortKey(b);
  if (aIndex !== bIndex) return aIndex - bIndex;
  return `${aName}`.localeCompare(`${bName}`, "ja");
}

function hasScopedSelection() {
  return state.team !== "all";
}

function entryOrder(entry) {
  const order = Number(entry?.order);
  return Number.isFinite(order) ? order : Number.MAX_SAFE_INTEGER;
}

function compareEntries(a, b) {
  if (a.date !== b.date) return b.date.localeCompare(a.date, "ja");
  const teamCompare = compareTeam(a.team, b.team);
  if (teamCompare !== 0) return teamCompare;
  const gameCompare = `${a.gameId || ""}`.localeCompare(`${b.gameId || ""}`, "ja");
  if (gameCompare !== 0) return gameCompare;
  const orderCompare = entryOrder(a) - entryOrder(b);
  if (orderCompare !== 0) return orderCompare;
  return a.player.localeCompare(b.player, "ja");
}

function availableDates() {
  const enabledDates = new Set(
    manifest.entries
      .filter((entry) => state.team === "all" || entry.team === state.team)
      .map((entry) => entry.date)
  );
  return manifest.dates.map(({ date }) => ({
    date,
    disabled: state.team !== "all" && !enabledDates.has(date),
  }));
}

function filteredEntries() {
  if (!hasScopedSelection()) return [];
  const query = state.query.trim().toLowerCase();
  return manifest.entries
    .filter((entry) => {
      if (state.team !== "all" && entry.team !== state.team) return false;
      if (state.date !== "all" && entry.date !== state.date) return false;
      if (state.player !== "all" && entry.player !== state.player) return false;
      if (!query) return true;
      const haystack = [entry.title, entry.player, entry.team, entry.matchup, entry.prefix, entry.date]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    })
    .sort(compareEntries);
}

function entriesForPlayerOptions() {
  if (!hasScopedSelection()) return [];
  return manifest.entries
    .filter((entry) => {
      if (state.team !== "all" && entry.team !== state.team) return false;
      if (state.date !== "all" && entry.date !== state.date) return false;
      return true;
    })
    .sort(compareEntries);
}

function selectedEntry(entries) {
  if (!entries.length) {
    state.selectedId = null;
    return null;
  }
  const found = state.selectedId ? entries.find((entry) => entry.id === state.selectedId) : null;
  if (found) return found;
  if (state.player !== "all") {
    const playerEntry = entries.find((entry) => entry.player === state.player);
    if (playerEntry) {
      state.selectedId = playerEntry.id;
      return playerEntry;
    }
  }
  return null;
}

function scrollToViewer() {
  requestAnimationFrame(() => {
    els.viewerPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

function statCell(label, value) {
  return `
    <div class="result-stat">
      <span>${label}</span>
      <strong>${value ?? "-"}</strong>
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
    button.innerHTML = `<span>${team.name}</span>`;
    button.disabled = !summary.hasData;
    button.addEventListener("click", () => {
      state.team = team.name;
      state.player = "all";
      state.selectedId = null;
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
      <h2>条件に合う打者ダッシュボードがありません</h2>
      <p>球団・日付・選手の条件を調整してください。</p>
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
          ${statCell("打数", entry.statline.ab)}
          ${statCell("安打", entry.statline.hits)}
          ${statCell("本塁打", entry.statline.homeRuns)}
          ${statCell("打点", entry.statline.rbi)}
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

function renderDateOptions() {
  const dates = availableDates();
  const enabledDates = new Set(dates.filter((row) => !row.disabled).map((row) => row.date));
  if (state.date !== "all" && !enabledDates.has(state.date)) {
    state.date = "all";
    state.player = "all";
    state.selectedId = null;
  }

  els.dateSelect.innerHTML = '<option value="all">日付を選択</option>';
  dates.forEach(({ date, disabled }) => {
    const option = document.createElement("option");
    option.value = date;
    option.textContent = date;
    option.disabled = disabled;
    if (date === state.date) option.selected = true;
    els.dateSelect.appendChild(option);
  });
}

function renderPlayerOptions() {
  const names = [];
  const seen = new Set();
  entriesForPlayerOptions().forEach((entry) => {
    if (seen.has(entry.player)) return;
    seen.add(entry.player);
    names.push(entry.player);
  });

  if (state.player !== "all" && !seen.has(state.player)) {
    state.player = "all";
    state.selectedId = null;
  }

  els.playerSelect.disabled = state.team === "all" || !names.length;
  els.playerSelect.innerHTML = '<option value="all">選手を選択</option>';
  names.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    if (name === state.player) option.selected = true;
    els.playerSelect.appendChild(option);
  });
}

function renderResultList(entries) {
  if (!hasScopedSelection()) {
    els.resultCount.textContent = "0件";
    els.resultList.innerHTML = `
      <div class="empty-state slim">
        <p class="empty-kicker">Select Filters</p>
        <h2>球団と日付を選択すると選手カードを表示します</h2>
        <p>先に球団を選び、そのチームが試合をした日付を選択してください。</p>
      </div>
    `;
    return;
  }

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
          ${statCell("打数", entry.statline.ab)}
          ${statCell("安打", entry.statline.hits)}
          ${statCell("本塁打", entry.statline.homeRuns)}
          ${statCell("打点", entry.statline.rbi)}
        </div>
        ${pitchPreview(entry.dashboard?.pitchMix)}
      </div>
    `;
    button.addEventListener("click", () => {
      state.selectedId = entry.id;
      state.player = entry.player;
      rerender();
      scrollToViewer();
    });
    els.resultList.appendChild(button);
  });
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

function renderMetaGrid(entry) {
  return `
    <div class="meta-grid">
      <article class="meta-card">
        <span>逅・屮</span>
        <strong>${entry.team}</strong>
      </article>
      <article class="meta-card">
        <span>譌･莉・/span>
        <strong>${entry.dateLabel || entry.date}</strong>
      </article>
      <article class="meta-card meta-card--wide">
        <span>蟇ｾ謌ｦ繧ｫ繝ｼ繝・/span>
        <strong>${entry.matchup || "-"}</strong>
      </article>
    </div>
  `;
}

function renderStatStrip(statline = {}) {
  const items = [
    ["打数", statline.ab],
    ["安打", statline.hits],
    ["本塁打", statline.homeRuns],
    ["打点", statline.rbi],
    ["四球", statline.walks],
    ["三振", statline.strikeouts],
  ];
  return `
    <div class="stat-strip stat-strip--compact">
      ${items
        .map(
          ([label, value]) => `
            <article class="stat-pill">
              <span>${label}</span>
              <strong>${value ?? "-"}</strong>
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

function renderPitchLegend(pitchMix = []) {
  if (!pitchMix.length) return "";
  return `
    <ul class="legend-list">
      ${pitchMix
        .map(
          (row) => `
            <li>
              <span class="legend-swatch" style="background:${row.color}"></span>
              <span>${row.pitchType} ${row.count}球</span>
            </li>
          `
        )
        .join("")}
    </ul>
  `;
}

function renderPlateTable(plateAppearances = []) {
  if (!plateAppearances.length) {
    return '<div class="section-empty">打席データがありません。</div>';
  }

  const body = plateAppearances
    .map(
      (row) => `
        <tr>
          <td>${row.label}</td>
          <td>${row.result || "-"}</td>
          <td>${row.pitchType || "-"}</td>
          <td>${row.speed || "-"}</td>
        </tr>
      `
    )
    .join("");

  return `
    <section class="dashboard-card">
      <div class="card-head">
        <h3>打席別成績</h3>
      </div>
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>打席</th>
              <th>結果</th>
              <th>球種</th>
              <th>球速</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    </section>
  `;
}

function renderPlateHeatCard(pa, bounds = {}) {
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
  const points = pa.points || [];
  const [leftLabel, rightLabel] = batterViewLabels(pa.batterHand);

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
      const radius = point.isFinalPitch ? 7 : 5.2;
      const lines = [
        point.pitchType,
        point.speedLabel || formatSpeed(point.speed),
        point.result || "-",
        point.pitcher ? `投手: ${point.pitcher}` : "",
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
    <article class="heatmap-card plate-heat-card">
      <div class="heatmap-head plate-heat-head">
        <strong>${pa.label}</strong>
        <p class="plate-heat-result">${pa.result || "-"}</p>
        <p class="plate-heat-summary">${pa.pitchType || "-"} / ${pa.speed || "-"} / ${pa.pitcher || "-"}</p>
      </div>
      <div class="heatmap-sides">
        <span>${leftLabel}</span>
        <span>${rightLabel}</span>
      </div>
      <div class="pitch-chart-wrap">
        <svg
          class="pitch-chart"
          viewBox="0 0 ${chartWidth} ${chartHeight}"
          role="img"
          aria-label="${escapeHtml(`${pa.label} の打席別ヒートマップ`)}"
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

function renderHeatSection(dashboard = {}) {
  const plateAppearances = dashboard.plateAppearances || [];
  if (!plateAppearances.length) {
    return '<div class="section-empty">打席別ヒートマップのデータがありません。</div>';
  }

  return `
    <section class="dashboard-card">
      <div class="card-head">
        <h3>打席別ヒートマップ</h3>
      </div>
      ${renderPitchLegend(dashboard.pitchMix)}
      <div class="heatmap-grid plate-heat-grid">
        ${plateAppearances.map((pa) => renderPlateHeatCard(pa, dashboard.bounds || {})).join("")}
      </div>
    </section>
  `;
}

function renderSection(entry) {
  const dashboard = entry.dashboard || {};
  switch (state.section) {
    case "heat":
      return renderHeatSection(dashboard);
    case "table":
    default:
      return renderPlateTable(dashboard.plateAppearances || []);
  }
}

function renderViewer(entry) {
  if (!entry) {
    els.viewerPanel.classList.add("empty");
    els.viewerPanel.innerHTML = `
      <div class="empty-state">
        <p class="empty-kicker">Select Dashboard</p>
        <h2>左の一覧から打者を選択してください</h2>
      </div>
    `;
    return;
  }

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
    state.date = "all";
    state.player = "all";
    state.selectedId = null;
    rerender();
  });

  els.dateSelect.addEventListener("change", (event) => {
    state.date = event.target.value;
    state.player = "all";
    state.selectedId = null;
    rerender();
  });

  els.playerSelect.addEventListener("change", (event) => {
    state.player = event.target.value;
    state.selectedId = null;
    rerender();
    if (state.player !== "all") scrollToViewer();
  });
}

bindEvents();
rerender();
