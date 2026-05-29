(() => {
  try {
    if (window.self !== window.top || new URLSearchParams(location.search).get("embed") === "1") return;
  } catch {
    return;
  }

  const STORAGE_KEY = "npb-dashboard-chat-history";
  const OPEN_KEY = "npb-dashboard-chat-open";
  const MAX_HISTORY = 10;
  const MAX_CONTEXT_LENGTH = 6500;
  const MAX_MESSAGE_LENGTH = 600;
  const AWS_CHAT_ENDPOINT = "https://2igxpnxlbz74ipsd46zkdo6dre0qykyq.lambda-url.ap-northeast-1.on.aws/";
  const localHosts = new Set(["localhost", "127.0.0.1", "::1", ""]);
  const endpoint =
    window.DASHBOARD_CHAT_ENDPOINT ||
    document.querySelector('meta[name="dashboard-chat-endpoint"]')?.content ||
    (localHosts.has(window.location.hostname) ? "/api/chat" : AWS_CHAT_ENDPOINT);
  const SELECTOR_SOURCES = [
    {
      kind: "投手",
      src: "./manifest.js?v=20260529-kind-auto",
      globalName: "PITCH_DASHBOARD_MANIFEST",
    },
    {
      kind: "野手",
      src: "./batter_manifest.js?v=20260529-kind-auto",
      globalName: "BATTER_GAME_MANIFEST",
    },
  ];
  const KIND_OPTIONS = ["投手", "野手"];
  const QUESTION_TYPES = [
    {
      type: "game",
      label: "試合詳細",
      note: "日付・チームを選んで試合内容を質問します。選手は未選択でも使えます。",
    },
    {
      type: "personal",
      label: "個人成績",
      note: "チーム・選手を選んで年度成績や指標を質問します。",
    },
    {
      type: "traits",
      label: "選手の特徴",
      note: "チーム・選手を選んで球種傾向、打撃傾向、強みを質問します。",
    },
    {
      type: "free",
      label: "その他",
      note: "下の入力欄に自由に質問を書いてください。",
    },
  ];

  const initialMessage = {
    role: "assistant",
    content: "全データ検索と表示中の画面内容を使って回答します。\n\nまず質問ジャンルを選んでください。投手 / 野手、チーム、選手など必要な項目を選ぶと自動で質問します。",
  };

  const state = {
    open: localStorage.getItem(OPEN_KEY) === "1",
    busy: false,
    messages: loadHistory(),
    selector: {
      activeType: "",
      activeKind: "",
      completed: false,
      loaded: false,
      loading: false,
      entries: [],
      dates: [],
    },
  };

  if (!state.messages.length) {
    state.messages = [initialMessage];
    saveHistory();
  } else if (isOldInitialMessage(state.messages[0])) {
    state.messages = [initialMessage, ...state.messages.slice(1)].slice(-MAX_HISTORY);
    saveHistory();
  } else if (state.messages[0]?.role !== "assistant") {
    state.messages = [initialMessage, ...state.messages.slice(-MAX_HISTORY + 1)];
    saveHistory();
  }

  function isOldInitialMessage(message) {
    if (message?.role !== "assistant" || typeof message.content !== "string") return false;
    return /[\u7e1d\u7e5d\u9666]/.test(message.content) || (
      message.content.includes("全データ検索と表示中の画面内容") && !message.content.includes("質問ジャンル")
    );
  }

  function loadHistory() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      if (!Array.isArray(parsed)) return [];
      return parsed
        .filter((message) => ["assistant", "user"].includes(message?.role) && typeof message.content === "string")
        .slice(-MAX_HISTORY);
    } catch {
      return [];
    }
  }

  function saveHistory() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state.messages.slice(-MAX_HISTORY)));
    } catch {
      // Ignore storage quota and private-mode failures.
    }
  }

  function normalizeText(value, limit = 1000) {
    return `${value || ""}`.replace(/\s+/g, " ").trim().slice(0, limit);
  }

  function normalizeReply(value, limit = 8000) {
    return `${value || ""}`
      .replace(/\r\n/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim()
      .slice(0, limit);
  }

  function visibleText(selector, limit = 1000) {
    const node = document.querySelector(selector);
    return node ? normalizeText(node.innerText || node.textContent, limit) : "";
  }

  function fieldLabel(field) {
    const label = field.closest("label");
    if (label) {
      const clone = label.cloneNode(true);
      clone.querySelectorAll("input, select, textarea, button").forEach((node) => node.remove());
      const text = normalizeText(clone.textContent, 80);
      if (text) return text;
    }

    if (field.id) {
      const explicit = document.querySelector(`label[for="${CSS.escape(field.id)}"]`);
      const text = normalizeText(explicit?.textContent, 80);
      if (text) return text;
    }

    return field.getAttribute("aria-label") || field.name || field.id || "";
  }

  function fieldValue(field) {
    if (field.tagName === "SELECT") {
      return Array.from(field.selectedOptions)
        .map((option) => normalizeText(option.textContent, 80))
        .filter(Boolean)
        .join(", ");
    }
    if (field.type === "checkbox" || field.type === "radio") {
      return field.checked ? "on" : "";
    }
    return normalizeText(field.value, 120);
  }

  function collectFilters() {
    return Array.from(document.querySelectorAll("input, select, textarea"))
      .filter((field) => !field.closest(".ai-chatbot"))
      .filter((field) => !["hidden", "button", "submit", "reset", "file"].includes(field.type))
      .map((field) => {
        const label = normalizeText(fieldLabel(field), 80);
        const value = fieldValue(field);
        if (!value || value === "all") return "";
        return `${label || field.id || field.name}: ${value}`;
      })
      .filter(Boolean)
      .slice(0, 16);
  }

  function collectIframeText() {
    const frame = document.querySelector("#playerStatsFrame");
    if (!frame || frame.classList.contains("is-hidden")) return "";
    try {
      return normalizeText(frame.contentDocument?.body?.innerText, 1600);
    } catch {
      return "";
    }
  }

  function collectMainContext() {
    const selectedResult = visibleText(".result-card.active", 1000);
    const selectedTabs = Array.from(
      document.querySelectorAll(".page-tab.active, .type-switch-link.active, .hero-nav-link.active, .hero-nav-sublink.active")
    )
      .map((node) => normalizeText(node.textContent, 80))
      .filter(Boolean);
    const filters = collectFilters();
    const regions = [
      "#viewerPanel:not(.empty)",
      "#annualTableWrap",
      "#rankingBody",
      "#comparePanel:not(.is-hidden)",
      "#monthlyPanel:not(.is-hidden)",
      "#seasonPanel:not(.is-hidden)",
      ".player-output-card",
      "main",
    ];
    const pageBody = regions.map((selector) => visibleText(selector, 4200)).find((text) => text.length > 80) || "";
    const iframeText = collectIframeText();
    const context = [
      `ページ: ${normalizeText(document.title, 120)}`,
      `URL: ${location.pathname}`,
      selectedTabs.length ? `選択中の表示: ${selectedTabs.join(" / ")}` : "",
      filters.length ? `フィルター: ${filters.join(" | ")}` : "",
      selectedResult ? `選択中カード: ${selectedResult}` : "",
      iframeText ? `埋め込み個人成績: ${iframeText}` : "",
      pageBody ? `画面本文: ${pageBody}` : "",
    ]
      .filter(Boolean)
      .join("\n");

    return context.slice(0, MAX_CONTEXT_LENGTH);
  }

  function createNode(tag, className, attrs = {}) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    Object.entries(attrs).forEach(([key, value]) => {
      if (value === undefined || value === null) return;
      if (key === "text") {
        node.textContent = value;
      } else {
        node.setAttribute(key, value);
      }
    });
    return node;
  }

  function uniqueSorted(values, sorter = (a, b) => `${a}`.localeCompare(`${b}`, "ja")) {
    return [...new Set(values.filter(Boolean))].sort(sorter);
  }

  function loadScriptOnce(source) {
    if (window[source.globalName]) return Promise.resolve(window[source.globalName]);
    const existing = document.querySelector(`script[data-chat-manifest="${source.globalName}"]`);
    if (existing) {
      return new Promise((resolve, reject) => {
        existing.addEventListener("load", () => resolve(window[source.globalName]), { once: true });
        existing.addEventListener("error", reject, { once: true });
      });
    }
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = source.src;
      script.dataset.chatManifest = source.globalName;
      script.onload = () => resolve(window[source.globalName]);
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  async function loadSelectorData() {
    if (state.selector.loaded || state.selector.loading) return;
    state.selector.loading = true;
    const manifests = await Promise.all(
      SELECTOR_SOURCES.map(async (source) => ({
        source,
        manifest: await loadScriptOnce(source),
      }))
    );
    const entries = manifests.flatMap(({ source, manifest }) => {
      const rows = Array.isArray(manifest?.entries) ? manifest.entries : [];
      return rows
        .map((entry) => ({
          kind: source.kind,
          date: normalizeText(entry.date, 20),
          team: normalizeText(entry.team || entry.teams?.[0], 80),
          player: normalizeText(entry.player, 120),
        }))
        .filter((entry) => entry.date && entry.team && entry.player);
    });
    state.selector.entries = entries;
    state.selector.dates = uniqueSorted(entries.map((entry) => entry.date), (a, b) => b.localeCompare(a));
    state.selector.loaded = true;
    state.selector.loading = false;
  }

  function selectorMatches(entry, filters) {
    if (filters.date && entry.date !== filters.date) return false;
    if (filters.kind && entry.kind !== filters.kind) return false;
    if (filters.team && entry.team !== filters.team) return false;
    return true;
  }

  function activeQuestionType() {
    return QUESTION_TYPES.find((item) => item.type === state.selector.activeType) || null;
  }

  function usesDateFilter() {
    return state.selector.activeType === "game";
  }

  function usesTeamPlayerFilters() {
    return ["game", "personal", "traits"].includes(state.selector.activeType);
  }

  function usesKindFilter() {
    return usesTeamPlayerFilters();
  }

  function selectorRequiresPlayer() {
    return ["personal", "traits"].includes(state.selector.activeType);
  }

  function optionNode(value, label, attrs = {}) {
    return createNode("option", "", { value, text: label, ...attrs });
  }

  function selectedFilters(dateInput, teamSelect) {
    return {
      date: usesDateFilter() ? dateInput.value || "" : "",
      kind: usesKindFilter() ? state.selector.activeKind || "" : "",
      team: usesTeamPlayerFilters() ? teamSelect.value || "" : "",
    };
  }

  function renderTeamOptions(dateInput, teamSelect) {
    const current = teamSelect.value;
    const date = usesDateFilter() ? dateInput.value || "" : "";
    const kind = usesKindFilter() ? state.selector.activeKind || "" : "";
    const teams = uniqueSorted(
      state.selector.entries
        .filter((entry) => !date || entry.date === date)
        .filter((entry) => !kind || entry.kind === kind)
        .map((entry) => entry.team)
    );
    teamSelect.replaceChildren(optionNode("", "チームを選択"), ...teams.map((team) => optionNode(team, team)));
    if (teams.includes(current)) teamSelect.value = current;
  }

  function renderPlayerOptions(dateInput, teamSelect, playerSelect) {
    const current = playerSelect.value;
    const filters = selectedFilters(dateInput, teamSelect);
    const players = state.selector.entries
      .filter((entry) => selectorMatches(entry, filters))
      .sort((a, b) => a.team.localeCompare(b.team, "ja") || a.player.localeCompare(b.player, "ja") || a.kind.localeCompare(b.kind, "ja"));
    const seen = new Set();
    const options = players
      .map((entry) => {
        const value = `${entry.kind}::${entry.player}`;
        const key = `${entry.team}::${value}`;
        if (seen.has(key)) return null;
        seen.add(key);
        const label = filters.team ? `${entry.player}（${entry.kind}）` : `${entry.team} ${entry.player}（${entry.kind}）`;
        return optionNode(value, label, {
          "data-player": entry.player,
          "data-kind": entry.kind,
        });
      })
      .filter(Boolean);
    const firstOptionLabel = activeQuestionType()?.type === "game" ? "選手を選択 / 指定しない" : "選手を選択";
    const baseOptions = [optionNode("", firstOptionLabel)];
    if (activeQuestionType()?.type === "game") {
      baseOptions.push(optionNode("__none__", "選手を指定しない", { "data-kind": filters.kind }));
    }
    playerSelect.replaceChildren(...baseOptions, ...options);
    if ([...playerSelect.options].some((option) => option.value === current)) playerSelect.value = current;
  }

  function syncSelectorVisibility(elements) {
    const type = activeQuestionType();
    elements.typeButtons.forEach((button) => {
      button.classList.toggle("active", button.dataset.chatQuestionType === state.selector.activeType);
    });
    elements.kindButtons.forEach((button) => {
      button.classList.toggle("active", button.dataset.chatKind === state.selector.activeKind);
    });
    const showDate = usesDateFilter();
    const showKind = usesKindFilter();
    const showTeam = showKind && Boolean(state.selector.activeKind);
    const showPlayer = showTeam && Boolean(elements.teamSelect.value);
    elements.dateLabel.hidden = !showDate;
    elements.dateInput.hidden = !showDate;
    elements.kindLabel.hidden = !showKind;
    elements.kindGroup.hidden = !showKind;
    elements.teamLabel.hidden = !showTeam;
    elements.teamSelect.hidden = !showTeam;
    elements.playerLabel.hidden = !showPlayer;
    elements.playerSelect.hidden = !showPlayer;
    elements.startButton.hidden = true;
    elements.textarea.placeholder = type?.type === "free" ? "自由に質問を入力" : "このダッシュボードについて質問";
  }

  function renderSelectorOptions(elements) {
    syncSelectorVisibility(elements);
    const type = activeQuestionType();
    if (!type) {
      elements.note.textContent = "最初に質問ジャンルを選択してください。";
      return;
    }
    if (type.type === "free") {
      elements.note.textContent = type.note;
      return;
    }
    if (usesKindFilter() && !state.selector.activeKind) {
      elements.note.textContent = "投手 / 野手を選択してください。";
      return;
    }
    if (!state.selector.loaded) {
      elements.note.textContent = "条件データを読み込み中...";
      return;
    }
    const dates = state.selector.dates;
    if (usesDateFilter() && dates.length) {
      elements.dateInput.min = dates[dates.length - 1];
      elements.dateInput.max = dates[0];
      if (!elements.dateInput.value) elements.dateInput.value = dates[0];
    }
    renderTeamOptions(elements.dateInput, elements.teamSelect);
    renderPlayerOptions(elements.dateInput, elements.teamSelect, elements.playerSelect);
    const dateText = dates.length ? `${dates[dates.length - 1]} - ${dates[0]}` : "データなし";
    elements.note.textContent = usesDateFilter() ? `${type.note} 対象日: ${dateText}` : type.note;
  }

  function selectorValidationMessage(dateInput, teamSelect, playerSelect) {
    const type = activeQuestionType();
    if (!type) return "質問ジャンルを選択してください。";
    if (type.type === "free") return "";
    if (type.type === "game" && !dateInput.value) return "日付を選択してください。";
    if (usesKindFilter() && !state.selector.activeKind) return "投手 / 野手を選択してください。";
    if (usesTeamPlayerFilters() && !teamSelect.value) return "チームを選択してください。";
    if (type.type === "game" && !playerSelect.value) return "選手を選択するか、「選手を指定しない」を選んでください。";
    if (selectorRequiresPlayer() && !playerSelect.value) return "選手を選択してください。";
    return "";
  }

  function buildSelectorQuestion(dateInput, teamSelect, playerSelect) {
    const type = activeQuestionType();
    if (!type || type.type === "free") return "";
    const date = dateInput.value || "";
    const team = teamSelect.value || "";
    const option = playerSelect.selectedOptions[0];
    const selectedNoPlayer = option?.value === "__none__";
    const player = option?.dataset.player || "";
    const kind = option?.dataset.kind || state.selector.activeKind || "";
    if (type.type === "game" && player && !selectedNoPlayer) {
      return `${date ? `${date}の` : ""}${team ? `${team}の` : ""}${player}（${kind}）について、試合内容と注目ポイントを教えて`;
    }
    if (type.type === "game" && team) {
      return `${date ? `${date}の` : ""}${team}の${kind}について、試合内容と注目ポイントを教えて`;
    }
    if (type.type === "game" && date) {
      return `${date}の注目選手と試合内容を教えて`;
    }
    if (type.type === "personal" && player) {
      return `${team ? `${team}の` : ""}${player}（${kind}）の個人成績を教えて`;
    }
    if (type.type === "personal" && team) {
      return `${team}の個人成績で注目すべき選手を教えて`;
    }
    if (type.type === "traits" && player) {
      return `${team ? `${team}の` : ""}${player}（${kind}）の選手としての特徴を教えて`;
    }
    if (type.type === "traits" && team) {
      return `${team}の選手の特徴と注目選手を教えて`;
    }
    return "";
  }

  function setChatStep(elements, step) {
    state.selector.completed = step === "chat";
    elements.root.dataset.step = step;
    elements.backButton.hidden = step !== "chat";
    const focusTarget = step === "chat" ? elements.textarea : elements.typeButtons[0];
    setTimeout(() => focusTarget?.focus(), 80);
  }

  function completeSelector(elements, question = "", autoSend = false) {
    elements.textarea.value = autoSend ? "" : question.slice(0, MAX_MESSAGE_LENGTH);
    if (!autoSend) {
      elements.textarea.setSelectionRange(elements.textarea.value.length, elements.textarea.value.length);
    }
    setChatStep(elements, "chat");
    if (autoSend && question && !state.busy) {
      ask(question, {
        messages: elements.messages,
        textarea: elements.textarea,
        sendButton: elements.sendButton,
      });
    }
  }

  function maybeAutoSend(elements) {
    const type = activeQuestionType();
    if (!type || type.type === "free") return;
    const validationMessage = selectorValidationMessage(elements.dateInput, elements.teamSelect, elements.playerSelect);
    if (validationMessage) {
      elements.note.textContent = validationMessage;
      return;
    }
    completeSelector(elements, buildSelectorQuestion(elements.dateInput, elements.teamSelect, elements.playerSelect), true);
  }

  function resetSelectorFlow(elements) {
    state.selector.activeType = "";
    state.selector.activeKind = "";
    elements.dateInput.value = "";
    elements.teamSelect.value = "";
    elements.playerSelect.value = "";
    elements.textarea.value = "";
    renderSelectorOptions(elements);
    setChatStep(elements, "select");
  }

  function bindSelectorControls(elements) {
    const refresh = () => renderSelectorOptions(elements);
    elements.typeButtons.forEach((button) => {
      button.addEventListener("click", () => {
        state.selector.activeType = button.dataset.chatQuestionType || "";
        state.selector.activeKind = "";
        elements.teamSelect.value = "";
        elements.playerSelect.value = "";
        refresh();
        if (state.selector.activeType === "free") completeSelector(elements);
      });
    });
    elements.kindButtons.forEach((button) => {
      button.addEventListener("click", () => {
        state.selector.activeKind = button.dataset.chatKind || "";
        elements.teamSelect.value = "";
        elements.playerSelect.value = "";
        refresh();
      });
    });
    elements.dateInput.addEventListener("change", () => {
      refresh();
      maybeAutoSend(elements);
    });
    elements.teamSelect.addEventListener("change", () => {
      renderPlayerOptions(elements.dateInput, elements.teamSelect, elements.playerSelect);
      refresh();
    });
    elements.playerSelect.addEventListener("change", () => {
      maybeAutoSend(elements);
    });
    elements.startButton.addEventListener("click", () => {
      const validationMessage = selectorValidationMessage(elements.dateInput, elements.teamSelect, elements.playerSelect);
      if (validationMessage) {
        elements.note.textContent = validationMessage;
        return;
      }
      const question = buildSelectorQuestion(elements.dateInput, elements.teamSelect, elements.playerSelect);
      completeSelector(elements, question);
    });
    elements.backButton.addEventListener("click", () => setChatStep(elements, "select"));
    refresh();
    loadSelectorData()
      .then(refresh)
      .catch(() => {
        elements.note.textContent = "条件データを読み込めませんでした。直接入力してください。";
      });
    return { reset: () => resetSelectorFlow(elements) };
  }

  function buildWidget() {
    const root = createNode("div", "ai-chatbot");
    const launcher = createNode("button", "ai-chatbot-launch", {
      type: "button",
      "aria-label": "AIチャットを開く",
      "aria-expanded": "false",
      text: "AI",
    });
    const panel = createNode("section", "ai-chatbot-panel", {
      role: "dialog",
      "aria-label": "AIチャット",
    });
    const header = createNode("div", "ai-chatbot-header");
    const titleWrap = createNode("div", "ai-chatbot-title-wrap");
    titleWrap.append(
      createNode("p", "ai-chatbot-kicker", { text: "Dashboard AI" }),
      createNode("h2", "ai-chatbot-title", { text: "AIチャット" })
    );
    const clearButton = createNode("button", "ai-chatbot-icon-button", {
      type: "button",
      "aria-label": "履歴を削除",
      title: "履歴を削除",
      text: "削除",
    });
    const backButton = createNode("button", "ai-chatbot-icon-button", {
      type: "button",
      "aria-label": "質問ジャンルを変更",
      title: "質問ジャンルを変更",
      text: "変更",
    });
    backButton.hidden = true;
    const closeButton = createNode("button", "ai-chatbot-icon-button", {
      type: "button",
      "aria-label": "閉じる",
      title: "閉じる",
      text: "閉じる",
    });
    const actions = createNode("div", "ai-chatbot-header-actions");
    actions.append(backButton, clearButton, closeButton);
    header.append(titleWrap, actions);

    const messages = createNode("div", "ai-chatbot-messages", {
      "aria-live": "polite",
    });
    const selectorPanel = createNode("div", "ai-chatbot-selector");
    const typeGroup = createNode("div", "ai-chatbot-type-group", {
      "aria-label": "質問ジャンル",
      role: "group",
    });
    const typeButtons = QUESTION_TYPES.map((item) =>
      createNode("button", "ai-chatbot-type-button", {
        type: "button",
        "data-chat-question-type": item.type,
        text: item.label,
      })
    );
    typeGroup.append(...typeButtons);
    selectorPanel.append(createNode("p", "ai-chatbot-selector-title", { text: "質問ジャンル" }), typeGroup);
    const kindGroup = createNode("div", "ai-chatbot-kind-group", {
      "aria-label": "投手または野手",
      role: "group",
    });
    const kindButtons = KIND_OPTIONS.map((kind) =>
      createNode("button", "ai-chatbot-kind-button", {
        type: "button",
        "data-chat-kind": kind,
        text: kind,
      })
    );
    kindGroup.append(...kindButtons);
    const dateInput = createNode("input", "ai-chatbot-filter-control", {
      type: "date",
      "aria-label": "日付",
    });
    const teamSelect = createNode("select", "ai-chatbot-filter-control", {
      "aria-label": "チーム",
    });
    const playerSelect = createNode("select", "ai-chatbot-filter-control", {
      "aria-label": "選手",
    });
    teamSelect.append(optionNode("", "読み込み中..."));
    playerSelect.append(optionNode("", "選手を選択"));
    const startButton = createNode("button", "ai-chatbot-selector-button", {
      type: "button",
      text: "チャットへ進む",
    });
    const selectorNote = createNode("p", "ai-chatbot-selector-note", { text: "条件データを読み込み中..." });
    const kindLabel = createNode("label", "ai-chatbot-filter-field", { text: "対象" });
    const dateLabel = createNode("label", "ai-chatbot-filter-field", { text: "日付" });
    const teamLabel = createNode("label", "ai-chatbot-filter-field", { text: "チーム" });
    const playerLabel = createNode("label", "ai-chatbot-filter-field", { text: "選手" });
    selectorPanel.append(
      kindLabel,
      kindGroup,
      dateLabel,
      dateInput,
      teamLabel,
      teamSelect,
      playerLabel,
      playerSelect,
      startButton,
      selectorNote
    );
    const form = createNode("form", "ai-chatbot-form");
    const textarea = createNode("textarea", "ai-chatbot-input", {
      rows: "2",
      maxlength: `${MAX_MESSAGE_LENGTH}`,
      placeholder: "このダッシュボードについて質問",
      "aria-label": "質問",
    });
    const sendButton = createNode("button", "ai-chatbot-send", {
      type: "submit",
      text: "送信",
    });
    form.append(textarea, sendButton);
    panel.append(header, messages, selectorPanel, form);
    root.append(launcher, panel);
    state.selector.completed = state.messages.some((message) => message.role === "user");
    root.dataset.step = state.selector.completed ? "chat" : "select";
    backButton.hidden = !state.selector.completed;
    document.body.appendChild(root);
    const selectorControls = bindSelectorControls({
      root,
      typeButtons,
      kindButtons,
      kindLabel,
      kindGroup,
      dateLabel,
      dateInput,
      teamLabel,
      teamSelect,
      playerLabel,
      playerSelect,
      startButton,
      note: selectorNote,
      messages,
      textarea,
      sendButton,
      backButton,
    });
    launcher.addEventListener("click", () => setOpen(!state.open));
    closeButton.addEventListener("click", () => setOpen(false));
    clearButton.addEventListener("click", () => {
      state.messages = [initialMessage];
      saveHistory();
      renderMessages(messages);
      selectorControls.reset();
    });
    textarea.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
      }
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const question = normalizeText(textarea.value, MAX_MESSAGE_LENGTH);
      if (!question || state.busy) return;
      textarea.value = "";
      await ask(question, { messages, textarea, sendButton });
    });

    renderMessages(messages);
    setOpen(state.open, false);
  }

  function setOpen(open, persist = true) {
    state.open = open;
    const root = document.querySelector(".ai-chatbot");
    const launcher = document.querySelector(".ai-chatbot-launch");
    if (!root || !launcher) return;
    root.dataset.open = open ? "true" : "false";
    launcher.setAttribute("aria-expanded", open ? "true" : "false");
    launcher.setAttribute("aria-label", open ? "AIチャットを閉じる" : "AIチャットを開く");
    if (persist) localStorage.setItem(OPEN_KEY, open ? "1" : "0");
    if (open) {
      const focusSelector = root.dataset.step === "chat" ? ".ai-chatbot-input" : ".ai-chatbot-type-button";
      setTimeout(() => document.querySelector(focusSelector)?.focus(), 80);
    }
  }

  function renderMessages(container) {
    container.innerHTML = "";
    state.messages.forEach((message) => {
      const item = createNode("div", `ai-chatbot-message ${message.role}`);
      item.textContent = message.content;
      container.appendChild(item);
    });
    container.scrollTop = container.scrollHeight;
  }

  function setBusy(busy, refs) {
    state.busy = busy;
    refs.sendButton.disabled = busy;
    refs.textarea.disabled = busy;
    const existing = refs.messages.querySelector("[data-loading]");
    if (existing) existing.remove();
    if (busy) {
      const loading = createNode("div", "ai-chatbot-message assistant loading", {
        "data-loading": "true",
        text: "回答を作成中...",
      });
      refs.messages.appendChild(loading);
      refs.messages.scrollTop = refs.messages.scrollHeight;
    }
  }

  async function ask(question, refs) {
    state.messages.push({ role: "user", content: question });
    renderMessages(refs.messages);
    setBusy(true, refs);

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: question,
          history: state.messages.slice(-8),
          context: collectMainContext(),
          page: {
            title: document.title,
            path: location.pathname,
          },
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || `チャットAPIでエラーが発生しました (${response.status})`);
      }
      state.messages.push({
        role: "assistant",
        content: normalizeReply(data.reply || "回答を取得できませんでした。"),
      });
    } catch (error) {
      const message = `${error?.message || ""}`;
      const missingApi = message.includes("404") || message.includes("Failed to fetch");
      state.messages.push({
        role: "assistant",
        content: missingApi
          ? "チャットAPIに接続できません。ローカルでは scripts/dashboard_chat_server.py からサイトを開いてください。"
          : message || "チャットAPIでエラーが発生しました。",
      });
    } finally {
      saveHistory();
      setBusy(false, refs);
      renderMessages(refs.messages);
      refs.textarea.focus();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", buildWidget);
  } else {
    buildWidget();
  }
})();
