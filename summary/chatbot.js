(() => {
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

  const initialMessage = {
    role: "assistant",
    content: "全データ検索と表示中の画面内容を使って回答します。選手名、チーム、日付、指標を指定して聞いてください。",
  };

  const state = {
    open: localStorage.getItem(OPEN_KEY) === "1",
    busy: false,
    messages: loadHistory(),
  };

  if (!state.messages.length || isOldInitialMessage(state.messages[0])) {
    state.messages = [initialMessage, ...state.messages.filter((message) => message.role !== "assistant").slice(-MAX_HISTORY + 1)];
    saveHistory();
  }

  function isOldInitialMessage(message) {
    if (message?.role !== "assistant" || typeof message.content !== "string") return false;
    return /[\u7e1d\u7e5d\u9666]/.test(message.content);
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
    const closeButton = createNode("button", "ai-chatbot-icon-button", {
      type: "button",
      "aria-label": "閉じる",
      title: "閉じる",
      text: "閉じる",
    });
    const actions = createNode("div", "ai-chatbot-header-actions");
    actions.append(clearButton, closeButton);
    header.append(titleWrap, actions);

    const messages = createNode("div", "ai-chatbot-messages", {
      "aria-live": "polite",
    });
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
    panel.append(header, messages, form);
    root.append(launcher, panel);
    document.body.appendChild(root);

    launcher.addEventListener("click", () => setOpen(!state.open));
    closeButton.addEventListener("click", () => setOpen(false));
    clearButton.addEventListener("click", () => {
      state.messages = [initialMessage];
      saveHistory();
      renderMessages(messages);
      textarea.focus();
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
      setTimeout(() => document.querySelector(".ai-chatbot-input")?.focus(), 80);
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
