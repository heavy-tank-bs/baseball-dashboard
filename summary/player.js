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

const TYPE_CONFIG = {
  pitcher: {
    label: "投手",
    datasetUrl: "./player_totals.json?v=20260430-3",
    idKey: "pitcherId",
  },
  batter: {
    label: "打者",
    datasetUrl: "./batter_totals.json?v=20260501-2",
    idKey: "batterId",
  },
};

const state = {
  type: "pitcher",
  datasets: {},
  year: "",
  league: "all",
  team: "all",
  player: "all",
};

const initialParams = new URLSearchParams(window.location.search);
const initialType = initialParams.get("type");
if (TYPE_CONFIG[initialType]) {
  state.type = initialType;
}
const initialSelection = {
  year: initialParams.get("year") || "",
  league: initialParams.get("league") || "all",
  team: initialParams.get("team") || "all",
  playerId: initialParams.get("playerId") || "",
  player: initialParams.get("player") || "",
};

const els = {
  typeButtons: [...document.querySelectorAll("[data-player-type]")],
  yearSelect: document.getElementById("yearSelect"),
  leagueSelect: document.getElementById("leagueSelect"),
  teamSelect: document.getElementById("teamSelect"),
  playerSelect: document.getElementById("playerSelect"),
  playerResultCount: document.getElementById("playerResultCount"),
  playerSelectionLabel: document.getElementById("playerSelectionLabel"),
  playerSelectionTitle: document.getElementById("playerSelectionTitle"),
  playerStatsEmpty: document.getElementById("playerStatsEmpty"),
  playerStatsFrame: document.getElementById("playerStatsFrame"),
};

function escapeHtml(value) {
  return `${value ?? ""}`
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
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

function config() {
  return TYPE_CONFIG[state.type] || TYPE_CONFIG.pitcher;
}

function rows() {
  return state.datasets[state.type]?.players || [];
}

function playerValue(row) {
  const id = row[config().idKey];
  return id || `${row.team}::${row.player}`;
}

function availableYears() {
  return [...new Set(rows().map((row) => row.year).filter(Boolean))].sort((a, b) => b.localeCompare(a));
}

function filteredRowsBase() {
  return rows().filter((row) => {
    if (state.year && row.year !== state.year) return false;
    if (state.league !== "all" && row.league !== state.league) return false;
    if (state.team !== "all" && row.team !== state.team) return false;
    return true;
  });
}

function availableTeams() {
  const teams = rows()
    .filter((row) => {
      if (state.year && row.year !== state.year) return false;
      if (state.league !== "all" && row.league !== state.league) return false;
      return true;
    })
    .map((row) => row.team)
    .filter(Boolean);
  return [...new Set(teams)].sort(compareTeam);
}

function availablePlayers() {
  const candidates = filteredRowsBase().sort((a, b) => {
    const teamCompare = compareTeam(a.team, b.team);
    if (teamCompare !== 0) return teamCompare;
    return `${a.player || ""}`.localeCompare(`${b.player || ""}`, "ja");
  });
  const nameCounts = candidates.reduce((map, row) => {
    map.set(row.player, (map.get(row.player) || 0) + 1);
    return map;
  }, new Map());
  return candidates.map((row) => ({
    row,
    value: playerValue(row),
    label: nameCounts.get(row.player) > 1 ? `${row.player} (${row.team})` : row.player,
  }));
}

function selectedPlayerRow() {
  if (state.player === "all") return null;
  return availablePlayers().find((item) => item.value === state.player)?.row || null;
}

function playerHref(row) {
  const params = new URLSearchParams({
    type: state.type,
    year: row.year || "",
    player: row.player || "",
    team: row.team || "",
  });
  const id = row[config().idKey];
  if (id) {
    params.set("playerId", id);
  }
  return `./compare.html?${params.toString()}`;
}

function embeddedPlayerHref(row) {
  return `${playerHref(row)}&embed=1`;
}

function renderTypeOptions() {
  els.typeButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.playerType === state.type);
  });
}

function applyInitialSelection() {
  if (initialSelection.year) state.year = initialSelection.year;
  if (initialSelection.league) state.league = initialSelection.league;
  if (initialSelection.team) state.team = initialSelection.team;
  if (initialSelection.playerId) {
    state.player = initialSelection.playerId;
  } else if (initialSelection.player && initialSelection.team && initialSelection.team !== "all") {
    state.player = `${initialSelection.team}::${initialSelection.player}`;
  } else if (initialSelection.player) {
    const match = rows().find((row) => row.player === initialSelection.player && (!initialSelection.year || row.year === initialSelection.year));
    if (match) state.player = playerValue(match);
  }
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
  const options = [
    '<option value="all">すべての球団</option>',
    ...teams.map((team) => `<option value="${escapeHtml(team)}" ${team === state.team ? "selected" : ""}>${escapeHtml(team)}</option>`),
  ];
  els.teamSelect.innerHTML = options.join("");
}

function renderPlayerOptions() {
  const players = availablePlayers();
  if (state.player !== "all" && !players.some((item) => item.value === state.player)) {
    state.player = "all";
  }
  const options = [
    '<option value="all">選手を選択</option>',
    ...players.map((item) => `<option value="${escapeHtml(item.value)}" ${item.value === state.player ? "selected" : ""}>${escapeHtml(item.label)}</option>`),
  ];
  els.playerSelect.innerHTML = options.join("");
  els.playerResultCount.textContent = `${players.length}件`;
}

function renderSelectedPlayer() {
  const row = selectedPlayerRow();
  if (!row) {
    els.playerSelectionLabel.textContent = `${config().label}を選択してください。`;
    els.playerSelectionTitle.textContent = "-";
    els.playerStatsFrame.removeAttribute("src");
    els.playerStatsFrame.classList.add("is-hidden");
    els.playerStatsFrame.style.height = "";
    els.playerStatsEmpty.classList.remove("is-hidden");
    return;
  }
  els.playerSelectionLabel.textContent = `${row.year}年度 ${row.team} ${config().label}`;
  els.playerSelectionTitle.textContent = row.player;
  const nextSrc = embeddedPlayerHref(row);
  if (els.playerStatsFrame.getAttribute("src") !== nextSrc) {
    els.playerStatsFrame.style.height = "640px";
    els.playerStatsFrame.src = nextSrc;
  }
  els.playerStatsEmpty.classList.add("is-hidden");
  els.playerStatsFrame.classList.remove("is-hidden");
}

function render() {
  renderTypeOptions();
  renderYearOptions();
  renderLeagueOptions();
  renderTeamOptions();
  renderPlayerOptions();
  renderSelectedPlayer();
}

function bindEvents() {
  els.typeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const nextType = button.dataset.playerType;
      if (!TYPE_CONFIG[nextType] || nextType === state.type) return;
      state.type = nextType;
      state.year = "";
      state.league = "all";
      state.team = "all";
      state.player = "all";
      const params = new URLSearchParams(window.location.search);
      params.set("type", state.type);
      window.history.replaceState(null, "", `?${params.toString()}`);
      render();
    });
  });

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
}

window.addEventListener("message", (event) => {
  if (event.origin !== window.location.origin) return;
  if (event.data?.type !== "playerStatsHeight") return;
  const height = Number(event.data.height);
  if (!Number.isFinite(height) || height <= 0) return;
  els.playerStatsFrame.style.height = `${Math.ceil(height)}px`;
});

async function init() {
  try {
    const entries = await Promise.all(
      Object.entries(TYPE_CONFIG).map(async ([type, typeConfig]) => {
        const response = await fetch(typeConfig.datasetUrl, { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return [type, await response.json()];
      })
    );
    state.datasets = Object.fromEntries(entries);
    applyInitialSelection();
    bindEvents();
    render();
  } catch (error) {
    els.playerSelectionLabel.textContent = "選手データを読み込めませんでした。";
    els.playerSelectionTitle.textContent = error.message;
    els.playerStatsFrame.classList.add("is-hidden");
    els.playerStatsEmpty.textContent = "選手データを読み込めませんでした。";
    els.playerStatsEmpty.classList.remove("is-hidden");
  }
}

init();
