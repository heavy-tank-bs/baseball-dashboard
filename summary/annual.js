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
  "楽天",
];

const state = {
  data: null,
  year: "",
  league: "all",
  team: "all",
  player: "all",
  inningsMinOuts: 0,
  sortKey: "",
  sortDirection: "",
};

const els = {
  yearSelect: document.getElementById("yearSelect"),
  leagueSelect: document.getElementById("leagueSelect"),
  teamSelect: document.getElementById("teamSelect"),
  playerSelect: document.getElementById("playerSelect"),
  inningsRange: document.getElementById("inningsRange"),
  inningsInput: document.getElementById("inningsInput"),
  inningsValue: document.getElementById("inningsValue"),
  inningsMaxLabel: document.getElementById("inningsMaxLabel"),
  annualResultCount: document.getElementById("annualResultCount"),
  annualNote: document.getElementById("annualNote"),
  annualTableWrap: document.getElementById("annualTableWrap"),
};

function escapeHtml(value) {
  return `${value ?? ""}`
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatDecimal(value, digits = 2) {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : `${value}`;
}

function formatAverage(value) {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(3) : `${value}`;
}

function formatPercent(value, digits = 1) {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(digits)}%` : `${value}`;
}

function formatInningsFromOuts(outs) {
  const safeOuts = Math.max(0, Number(outs) || 0);
  const whole = Math.floor(safeOuts / 3);
  const remainder = safeOuts % 3;
  return remainder === 0 ? `${whole}` : `${whole}.${remainder}`;
}

function parseInningsToOuts(value) {
  const normalized = `${value ?? ""}`.trim().normalize("NFKC");
  if (!normalized) return 0;
  const sign = normalized.startsWith("-") ? -1 : 1;
  const unsigned = sign < 0 ? normalized.slice(1) : normalized;
  const [wholePart, fractionPart = ""] = unsigned.split(".", 2);
  const whole = Number.parseInt(wholePart || "0", 10);
  if (!Number.isFinite(whole)) return 0;
  const digit = fractionPart.match(/\d/)?.[0];
  const remainder = digit ? Math.min(Number.parseInt(digit, 10), 2) : 0;
  return Math.max(0, sign * ((whole * 3) + remainder));
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

const SORT_COLUMNS = [
  { key: "team", label: "球団", type: "team", value: (row) => row.team },
  { key: "player", label: "投手", type: "string", value: (row) => row.player },
  { key: "games", label: "登板", type: "number", value: (row) => row.games },
  { key: "wins", label: "勝利", type: "number", value: (row) => row.wins },
  { key: "losses", label: "敗戦", type: "number", value: (row) => row.losses },
  { key: "saves", label: "セーブ", type: "number", value: (row) => row.saves },
  { key: "holds", label: "ホールド", type: "number", value: (row) => row.holds },
  { key: "inningsOuts", label: "投球回", type: "number", value: (row) => row.inningsOuts },
  { key: "era", label: "防御率", type: "number", value: (row) => row.era },
  { key: "fip", label: "FIP", type: "number", value: (row) => row.fip },
  { key: "hits", label: "被安打", type: "number", value: (row) => row.hits },
  { key: "whip", label: "WHIP", type: "number", value: (row) => row.whip },
  { key: "battingAverageAllowed", label: "被打率", type: "number", value: (row) => row.battingAverageAllowed },
  { key: "strikeouts", label: "奪三振", type: "number", value: (row) => row.strikeouts },
  { key: "kPer9", label: "K/9", type: "number", value: (row) => row.kPer9 },
  { key: "walks", label: "与四球", type: "number", value: (row) => row.walks },
  { key: "bbPer9", label: "BB/9", type: "number", value: (row) => row.bbPer9 },
  { key: "kBb", label: "K/BB", type: "number", value: (row) => row.kBb },
  { key: "homeRuns", label: "被本塁打", type: "number", value: (row) => row.homeRuns },
  { key: "hrPer9", label: "HR/9", type: "number", value: (row) => row.hrPer9 },
  { key: "groundOutRate", label: "ゴロアウト率", type: "number", value: (row) => row.groundOutRate },
  { key: "flyOutRate", label: "フライアウト率", type: "number", value: (row) => row.flyOutRate },
  { key: "pitches", label: "球数", type: "number", value: (row) => row.pitches },
];

const SORT_COLUMN_MAP = Object.fromEntries(SORT_COLUMNS.map((column) => [column.key, column]));

function playerValue(row) {
  return row.pitcherId || `${row.team}::${row.player}`;
}

function compareDefault(a, b) {
  if (b.inningsOuts !== a.inningsOuts) return b.inningsOuts - a.inningsOuts;
  if ((b.games || 0) !== (a.games || 0)) return (b.games || 0) - (a.games || 0);
  const teamCompare = compareTeam(a.team, b.team);
  if (teamCompare !== 0) return teamCompare;
  return a.player.localeCompare(b.player, "ja");
}

function isMissingSortValue(value) {
  return value === null || value === undefined || value === "";
}

function compareSorted(a, b) {
  const column = SORT_COLUMN_MAP[state.sortKey];
  if (!column || !state.sortDirection) {
    return compareDefault(a, b);
  }

  const aValue = column.value(a);
  const bValue = column.value(b);
  const aMissing = isMissingSortValue(aValue);
  const bMissing = isMissingSortValue(bValue);

  if (aMissing && bMissing) return compareDefault(a, b);
  if (aMissing) return 1;
  if (bMissing) return -1;

  let result = 0;
  if (column.type === "team") {
    result = compareTeam(aValue, bValue);
  } else if (column.type === "string") {
    result = `${aValue}`.localeCompare(`${bValue}`, "ja");
  } else {
    result = Number(aValue) - Number(bValue);
  }

  if (result === 0) return compareDefault(a, b);
  return state.sortDirection === "asc" ? result : -result;
}

function sortIndicator(key) {
  if (state.sortKey !== key || !state.sortDirection) return "↕";
  return state.sortDirection === "asc" ? "▲" : "▼";
}

function renderSortHeader(column) {
  const active = state.sortKey === column.key && state.sortDirection;
  return `
    <th>
      <button
        type="button"
        class="sort-header${active ? " active" : ""}"
        data-sort-key="${column.key}"
        aria-label="${column.label}で並び替え"
      >
        <span>${column.label}</span>
        <span class="sort-indicator" aria-hidden="true">${sortIndicator(column.key)}</span>
      </button>
    </th>
  `;
}

function toggleSort(sortKey) {
  if (state.sortKey !== sortKey) {
    state.sortKey = sortKey;
    state.sortDirection = "desc";
  } else if (state.sortDirection === "desc") {
    state.sortDirection = "asc";
  } else {
    state.sortKey = "";
    state.sortDirection = "";
  }
  render();
}

function availableTeams() {
  const rows = (state.data?.players || []).filter((row) => {
    if (state.year && row.year !== state.year) return false;
    if (state.league !== "all" && row.league !== state.league) return false;
    return true;
  });
  return [...new Set(rows.map((row) => row.team))].sort(compareTeam);
}

function availablePlayers() {
  const rows = (state.data?.players || [])
    .filter((row) => {
      if (state.year && row.year !== state.year) return false;
      if (state.league !== "all" && row.league !== state.league) return false;
      if (state.team !== "all" && row.team !== state.team) return false;
      return true;
    })
    .sort((a, b) => {
      const teamCompare = compareTeam(a.team, b.team);
      if (teamCompare !== 0) return teamCompare;
      return a.player.localeCompare(b.player, "ja");
    });

  const nameCounts = rows.reduce((map, row) => {
    map.set(row.player, (map.get(row.player) || 0) + 1);
    return map;
  }, new Map());

  return rows.map((row) => ({
    value: playerValue(row),
    label: nameCounts.get(row.player) > 1 ? `${row.player} (${row.team})` : row.player,
  }));
}

function filteredPlayersBase() {
  return (state.data?.players || []).filter((row) => {
    if (state.year && row.year !== state.year) return false;
    if (state.league !== "all" && row.league !== state.league) return false;
    if (state.team !== "all" && row.team !== state.team) return false;
    if (state.player !== "all" && playerValue(row) !== state.player) return false;
    return true;
  });
}

function filteredPlayers() {
  return filteredPlayersBase()
    .filter((row) => (row.inningsOuts || 0) >= state.inningsMinOuts)
    .sort(compareSorted);
}

function renderYearOptions() {
  const years = [...(state.data?.years || [])].sort().reverse();
  if (!state.year && years.length) {
    state.year = years[0];
  }
  els.yearSelect.innerHTML = years
    .map((year) => `<option value="${escapeHtml(year)}" ${year === state.year ? "selected" : ""}>${year}年度</option>`)
    .join("");
}

function renderLeagueOptions() {
  const options = [
    { value: "all", label: "すべてのリーグ" },
    { value: "セ", label: "セ・リーグ" },
    { value: "パ", label: "パ・リーグ" },
  ];
  els.leagueSelect.innerHTML = options
    .map(
      (option) =>
        `<option value="${option.value}" ${option.value === state.league ? "selected" : ""}>${option.label}</option>`
    )
    .join("");
}

function renderTeamOptions() {
  const teams = availableTeams();
  if (state.team !== "all" && !teams.includes(state.team)) {
    state.team = "all";
  }
  const options = [
    '<option value="all">すべての球団</option>',
    ...teams.map(
      (team) => `<option value="${escapeHtml(team)}" ${team === state.team ? "selected" : ""}>${escapeHtml(team)}</option>`
    ),
  ];
  els.teamSelect.innerHTML = options.join("");
}

function renderPlayerOptions() {
  const players = availablePlayers();
  if (state.player !== "all" && !players.some((row) => row.value === state.player)) {
    state.player = "all";
  }
  const options = [
    '<option value="all">すべての選手</option>',
    ...players.map(
      (row) => `<option value="${escapeHtml(row.value)}" ${row.value === state.player ? "selected" : ""}>${escapeHtml(row.label)}</option>`
    ),
  ];
  els.playerSelect.innerHTML = options.join("");
}

function renderNote() {
  const yearLabel = state.year ? `${state.year}年度` : "全年度";
  els.annualNote.textContent = `${yearLabel}の集計です。FIP は BB をそのまま使用し、ゴロアウト率・フライアウト率は全アウト系イベントに対する割合です。`;
}

function renderInningsFilter() {
  const maxOuts = filteredPlayersBase().reduce((max, row) => Math.max(max, row.inningsOuts || 0), 0);
  if (state.inningsMinOuts > maxOuts) {
    state.inningsMinOuts = maxOuts;
  }
  els.inningsRange.max = `${maxOuts}`;
  els.inningsRange.value = `${state.inningsMinOuts}`;
  els.inningsInput.value = formatInningsFromOuts(state.inningsMinOuts);
  els.inningsValue.textContent = `${formatInningsFromOuts(state.inningsMinOuts)} 以上`;
  els.inningsMaxLabel.textContent = formatInningsFromOuts(maxOuts);
}

function applyInningsInput(rawValue) {
  const maxOuts = Number(els.inningsRange.max) || 0;
  state.inningsMinOuts = Math.min(parseInningsToOuts(rawValue), maxOuts);
  render();
}

function captureTableScroll() {
  const scroller = els.annualTableWrap.querySelector(".table-scroll");
  return {
    left: scroller?.scrollLeft ?? 0,
    top: scroller?.scrollTop ?? 0,
    pageX: window.scrollX,
    pageY: window.scrollY,
  };
}

function restoreTableScroll(scrollState) {
  window.scrollTo(scrollState.pageX, scrollState.pageY);
  const scroller = els.annualTableWrap.querySelector(".table-scroll");
  if (!scroller) return;
  scroller.scrollLeft = scrollState.left;
  scroller.scrollTop = scrollState.top;
}

function renderTable() {
  const scrollState = captureTableScroll();
  const rows = filteredPlayers();
  els.annualResultCount.textContent = `${rows.length}件`;

  if (!rows.length) {
    els.annualTableWrap.innerHTML = '<div class="section-empty">条件に合う年度別成績がありません。</div>';
    requestAnimationFrame(() => restoreTableScroll(scrollState));
    return;
  }

  const body = rows
    .map(
      (row) => `
        <tr>
          <td>${escapeHtml(row.team)}</td>
          <td>${escapeHtml(row.player)}</td>
          <td>${row.games}</td>
          <td>${row.wins ?? 0}</td>
          <td>${row.losses ?? 0}</td>
          <td>${row.saves ?? 0}</td>
          <td>${row.holds ?? 0}</td>
          <td>${row.innings}</td>
          <td>${formatDecimal(row.era, 2)}</td>
          <td>${formatDecimal(row.fip, 2)}</td>
          <td>${row.hits}</td>
          <td>${formatDecimal(row.whip, 2)}</td>
          <td>${formatAverage(row.battingAverageAllowed)}</td>
          <td>${row.strikeouts}</td>
          <td>${formatDecimal(row.kPer9, 2)}</td>
          <td>${row.walks}</td>
          <td>${formatDecimal(row.bbPer9, 2)}</td>
          <td>${formatDecimal(row.kBb, 2)}</td>
          <td>${row.homeRuns}</td>
          <td>${formatDecimal(row.hrPer9, 2)}</td>
          <td>${formatPercent(row.groundOutRate, 1)}</td>
          <td>${formatPercent(row.flyOutRate, 1)}</td>
          <td>${row.pitches}</td>
        </tr>
      `
    )
    .join("");

  els.annualTableWrap.innerHTML = `
    <div class="table-scroll">
      <table class="data-table annual-table">
        <thead>
          <tr>${SORT_COLUMNS.map((column) => renderSortHeader(column)).join("")}</tr>
        </thead>
        <tbody>${body}</tbody>
      </table>
    </div>
  `;
  requestAnimationFrame(() => restoreTableScroll(scrollState));
}

function render() {
  renderYearOptions();
  renderLeagueOptions();
  renderTeamOptions();
  renderPlayerOptions();
  renderInningsFilter();
  renderNote();
  renderTable();
}

function bindEvents() {
  els.yearSelect.addEventListener("change", (event) => {
    state.year = event.target.value;
    state.team = "all";
    state.player = "all";
    render();
  });

  els.leagueSelect.addEventListener("change", (event) => {
    state.league = event.target.value;
    state.team = "all";
    state.player = "all";
    render();
  });

  els.teamSelect.addEventListener("change", (event) => {
    state.team = event.target.value;
    state.player = "all";
    render();
  });

  els.playerSelect.addEventListener("change", (event) => {
    state.player = event.target.value;
    render();
  });

  els.inningsRange.addEventListener("input", (event) => {
    state.inningsMinOuts = Number(event.target.value) || 0;
    render();
  });

  els.inningsInput.addEventListener("change", (event) => {
    applyInningsInput(event.target.value);
  });

  els.inningsInput.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    applyInningsInput(event.target.value);
  });

  els.annualTableWrap.addEventListener("click", (event) => {
    const button = event.target.closest(".sort-header");
    if (!button) return;
    toggleSort(button.dataset.sortKey || "");
  });
}

async function init() {
  try {
    const response = await fetch("./player_totals.json?v=20260413-25", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    bindEvents();
    render();
  } catch (error) {
    els.annualTableWrap.innerHTML = `<div class="section-empty">年度別成績データを読み込めませんでした。${escapeHtml(error.message)}</div>`;
  }
}

init();
