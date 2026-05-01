const TEAM_ORDER = [
  "広島",
  "阪神",
  "DeNA",
  "巨人",
  "ヤクルト",
  "中日",
  "ソフトバンク",
  "日本ハム",
  "ロッテ",
  "オリックス",
  "西武",
  "東北楽天",
];

const FULL_SEASON_GAMES = 143;
const QUALIFIED_PLATE_APPEARANCES_PER_GAME = 3.1;

const state = {
  data: null,
  teamGamesByYear: new Map(),
  year: "",
  league: "all",
  team: "all",
  player: "all",
  plateAppearancesMin: 0,
  thresholdCustomized: false,
  sortKey: "",
  sortDirection: "",
};

const els = {
  yearSelect: document.getElementById("yearSelect"),
  leagueSelect: document.getElementById("leagueSelect"),
  teamSelect: document.getElementById("teamSelect"),
  playerSelect: document.getElementById("playerSelect"),
  plateAppearancesRange: document.getElementById("plateAppearancesRange"),
  plateAppearancesInput: document.getElementById("plateAppearancesInput"),
  plateAppearancesMaxLabel: document.getElementById("plateAppearancesMaxLabel"),
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

function formatAverage(value) {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(3) : `${value}`;
}

function formatDecimal(value, digits = 1) {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : `${value}`;
}

function formatPercent(value, digits = 1) {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(digits)}%` : `${value}`;
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

function hasScore(value) {
  return value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
}

function isCompletedGame(game) {
  return hasScore(game?.homeScore) && hasScore(game?.awayScore);
}

function rebuildTeamGames(context) {
  const gamesByYear = new Map();
  const games = Array.isArray(context?.games) ? context.games : [];
  for (const game of games) {
    if (!isCompletedGame(game)) continue;
    const year = `${game.date || context?.season || ""}`.slice(0, 4);
    if (!year) continue;
    if (!gamesByYear.has(year)) {
      gamesByYear.set(year, new Map());
    }
    const counts = gamesByYear.get(year);
    for (const team of [game.homeTeam, game.awayTeam]) {
      if (!team) continue;
      counts.set(team, (counts.get(team) || 0) + 1);
    }
  }
  state.teamGamesByYear = gamesByYear;
}

function minimumTeamGamesForYear(year) {
  if (year === "2025") return FULL_SEASON_GAMES;
  const counts = state.teamGamesByYear.get(year);
  if (!counts) return 0;
  const games = [...counts.values()].filter((value) => Number.isFinite(value) && value > 0);
  return games.length ? Math.min(...games) : 0;
}

function qualifiedPlateAppearances() {
  const games = minimumTeamGamesForYear(state.year);
  return games > 0 ? Math.floor(games * QUALIFIED_PLATE_APPEARANCES_PER_GAME) : 0;
}

const SORT_COLUMNS = [
  { key: "team", label: "球団", type: "team", value: (row) => row.team },
  { key: "player", label: "選手", type: "string", value: (row) => row.player },
  { key: "games", label: "試合", type: "number", value: (row) => row.games },
  { key: "battingAverage", label: "打率", type: "number", value: (row) => row.battingAverage },
  { key: "scoringPositionBattingAverage", label: "得点圏打率", type: "number", value: (row) => row.scoringPositionBattingAverage },
  { key: "ballZoneSwingRate", label: "ボールゾーンスイング率", type: "number", value: (row) => row.ballZoneSwingRate },
  { key: "plateAppearances", label: "打席", type: "number", value: (row) => row.plateAppearances },
  { key: "atBats", label: "打数", type: "number", value: (row) => row.atBats },
  { key: "runs", label: "得点", type: "number", value: (row) => row.runs },
  { key: "hits", label: "安打", type: "number", value: (row) => row.hits },
  { key: "doubles", label: "二塁打", type: "number", value: (row) => row.doubles },
  { key: "triples", label: "三塁打", type: "number", value: (row) => row.triples },
  { key: "homeRuns", label: "本塁打", type: "number", value: (row) => row.homeRuns },
  { key: "runsBattedIn", label: "打点", type: "number", value: (row) => row.runsBattedIn },
  { key: "walks", label: "四球", type: "number", value: (row) => row.walks },
  { key: "hitByPitch", label: "死球", type: "number", value: (row) => row.hitByPitch },
  { key: "sacBunts", label: "犠打", type: "number", value: (row) => row.sacBunts },
  { key: "steals", label: "盗塁", type: "number", value: (row) => row.steals },
  { key: "strikeouts", label: "三振", type: "number", value: (row) => row.strikeouts },
  { key: "onBasePercentage", label: "出塁率", type: "number", value: (row) => row.onBasePercentage },
  { key: "isoDiscipline", label: "IsoD", type: "number", value: (row) => row.isoDiscipline },
  { key: "sluggingPercentage", label: "長打率", type: "number", value: (row) => row.sluggingPercentage },
  { key: "isoPower", label: "IsoP", type: "number", value: (row) => row.isoPower },
  { key: "ops", label: "OPS", type: "number", value: (row) => row.ops },
  { key: "wrcPlus", label: "wRC+", type: "number", value: (row) => row.wrcPlus },
  { key: "babip", label: "BABIP", type: "number", value: (row) => row.babip },
];

const playerColumnIndex = SORT_COLUMNS.findIndex((column) => column.key === "player");
if (playerColumnIndex > 0) {
  const [playerColumn] = SORT_COLUMNS.splice(playerColumnIndex, 1);
  SORT_COLUMNS.unshift(playerColumn);
}

const SORT_COLUMN_MAP = Object.fromEntries(SORT_COLUMNS.map((column) => [column.key, column]));

function playerValue(row) {
  return row.batterId || `${row.team}::${row.player}`;
}

function playerCompareHref(row) {
  const params = new URLSearchParams({
    type: "batter",
    year: row.year || "",
    player: row.player || "",
    team: row.team || "",
  });
  if (row.batterId) {
    params.set("playerId", row.batterId);
  }
  return `./compare.html?${params.toString()}`;
}

function compareDefault(a, b) {
  if ((b.atBats || 0) !== (a.atBats || 0)) return (b.atBats || 0) - (a.atBats || 0);
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
  return state.sortDirection === "asc" ? "↑" : "↓";
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

function parsePlateAppearances(value) {
  const normalized = `${value ?? ""}`.trim().normalize("NFKC");
  if (!normalized) return 0;
  const number = Number.parseInt(normalized, 10);
  return Number.isFinite(number) ? Math.max(number, 0) : 0;
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
    .filter((row) => (row.plateAppearances || 0) >= state.plateAppearancesMin)
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
    .map((option) => `<option value="${option.value}" ${option.value === state.league ? "selected" : ""}>${option.label}</option>`)
    .join("");
}

function renderTeamOptions() {
  const teams = availableTeams();
  if (state.team !== "all" && !teams.includes(state.team)) {
    state.team = "all";
  }
  const options = [
    '<option value="all">すべての球団</option>',
    ...teams.map((team) => `<option value="${escapeHtml(team)}" ${team === state.team ? "selected" : ""}>${escapeHtml(team)}</option>`),
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
    ...players.map((row) => `<option value="${escapeHtml(row.value)}" ${row.value === state.player ? "selected" : ""}>${escapeHtml(row.label)}</option>`),
  ];
  els.playerSelect.innerHTML = options.join("");
}

function renderNote() {
  els.annualNote.textContent = "";
}

function renderPlateAppearancesFilter() {
  const qualifiedPlateAppearancesMin = qualifiedPlateAppearances();
  const rowMaxPlateAppearances = filteredPlayersBase().reduce(
    (max, row) => Math.max(max, row.plateAppearances || 0),
    0
  );
  const maxPlateAppearances = Math.max(rowMaxPlateAppearances, qualifiedPlateAppearancesMin);
  if (!state.thresholdCustomized) {
    state.plateAppearancesMin = qualifiedPlateAppearancesMin;
  }
  if (state.plateAppearancesMin > maxPlateAppearances) {
    state.plateAppearancesMin = maxPlateAppearances;
  }
  els.plateAppearancesRange.max = `${maxPlateAppearances}`;
  els.plateAppearancesRange.value = `${state.plateAppearancesMin}`;
  els.plateAppearancesInput.value = `${state.plateAppearancesMin}`;
  els.plateAppearancesMaxLabel.textContent = `${maxPlateAppearances}`;
}

function applyPlateAppearancesInput(rawValue) {
  const maxPlateAppearances = Number(els.plateAppearancesRange.max) || 0;
  state.thresholdCustomized = true;
  state.plateAppearancesMin = Math.min(parsePlateAppearances(rawValue), maxPlateAppearances);
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
    els.annualTableWrap.innerHTML = '<div class="section-empty">条件に合う年度別打者成績がありません。</div>';
    requestAnimationFrame(() => restoreTableScroll(scrollState));
    return;
  }

  const body = rows
    .map(
      (row) => `
        <tr>
          <td><a class="annual-player-link" href="${playerCompareHref(row)}">${escapeHtml(row.player)}</a></td>
          <td>${escapeHtml(row.team)}</td>
          <td>${row.games}</td>
          <td>${formatAverage(row.battingAverage)}</td>
          <td>${formatAverage(row.scoringPositionBattingAverage)}</td>
          <td>${formatPercent(row.ballZoneSwingRate, 1)}</td>
          <td>${row.plateAppearances}</td>
          <td>${row.atBats}</td>
          <td>${row.runs}</td>
          <td>${row.hits}</td>
          <td>${row.doubles}</td>
          <td>${row.triples}</td>
          <td>${row.homeRuns}</td>
          <td>${row.runsBattedIn}</td>
          <td>${row.walks}</td>
          <td>${row.hitByPitch}</td>
          <td>${row.sacBunts}</td>
          <td>${row.steals}</td>
          <td>${row.strikeouts}</td>
          <td>${formatAverage(row.onBasePercentage)}</td>
          <td>${formatAverage(row.isoDiscipline)}</td>
          <td>${formatAverage(row.sluggingPercentage)}</td>
          <td>${formatAverage(row.isoPower)}</td>
          <td>${formatAverage(row.ops)}</td>
          <td>${formatDecimal(row.wrcPlus, 1)}</td>
          <td>${formatAverage(row.babip)}</td>
        </tr>
      `
    )
    .join("");

  els.annualTableWrap.innerHTML = `
    <div class="table-scroll annual-table-scroll">
      <table class="data-table annual-batter-table">
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
  renderPlateAppearancesFilter();
  renderNote();
  renderTable();
}

function bindEvents() {
  els.yearSelect.addEventListener("change", (event) => {
    state.year = event.target.value;
    state.team = "all";
    state.player = "all";
    state.thresholdCustomized = false;
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

  els.plateAppearancesRange.addEventListener("input", (event) => {
    state.thresholdCustomized = true;
    state.plateAppearancesMin = Number(event.target.value) || 0;
    render();
  });

  els.plateAppearancesInput.addEventListener("change", (event) => {
    applyPlateAppearancesInput(event.target.value);
  });

  els.plateAppearancesInput.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    applyPlateAppearancesInput(event.target.value);
  });

  els.annualTableWrap.addEventListener("click", (event) => {
    const button = event.target.closest(".sort-header");
    if (!button) return;
    toggleSort(button.dataset.sortKey || "");
  });
}

async function init() {
  try {
    const [response, contextResponse] = await Promise.all([
      fetch("./batter_totals.json?v=20260501-2", { cache: "no-store" }),
      fetch("./sportsnavi_game_context_2026.json?v=20260429-1", { cache: "no-store" }).catch(() => null),
    ]);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    if (contextResponse?.ok) {
      rebuildTeamGames(await contextResponse.json());
    }
    bindEvents();
    render();
  } catch (error) {
    els.annualTableWrap.innerHTML = `<div class="section-empty">年度別打者成績データを読み込めませんでした。${escapeHtml(error.message)}</div>`;
  }
}

init();
