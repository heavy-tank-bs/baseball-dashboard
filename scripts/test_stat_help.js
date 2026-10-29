"use strict";

const assert = require("node:assert/strict");
const { getHelp, normalizeLabel, tooltipPosition, install, DEFAULT_SELECTOR } = require("../summary/stat-help.js");

// These assertions protect the distinct definitions used by the site's datasets.
assert.match(getHelp("FIP").formula, /故意四球を除く四球/);
assert.match(getHelp("WHIFF% ↕").formula, /÷ スイング数/);
assert.match(getHelp("空振率").formula, /÷ 投球数/);
assert.notEqual(getHelp("whiff%").formula, getHelp("空振率").formula);
assert.match(getHelp("zone%").formula, /投球位置を取得できた投球数/);
assert.match(getHelp("CSW%").formula, /空振り数 ＋ 見逃しストライク数/);
assert.match(getHelp("chase+").formula, /同リーグ平均/);
assert.equal(getHelp("四死").formula, "四球 ＋ 死球");
assert.match(getHelp("勝利登板").meaning, /失点・四死球を集計/);
assert.match(getHelp("敗戦登板").meaning, /失点・四死球を集計/);
assert.match(getHelp("勝敗なし登板").meaning, /どちらにもならなかった登板/);
assert.equal(getHelp("被本"), getHelp("被本塁打"));
assert.equal(getHelp("ＩｓｏＰ"), getHelp("IsoP"));
assert.equal(getHelp("2025"), null);
assert.equal(getHelp("宮城大弥"), null);
assert.equal(getHelp("2塁"), null, "a runner-position label must not be interpreted as a double");
assert.equal(normalizeLabel(" z-swing% ▲ "), "z-swing%");
assert.doesNotMatch(DEFAULT_SELECTOR, /(^|,)\s*(span|td|button)\s*(,|$)/, "do not scan arbitrary value/control text");

// Position against the visible viewport, including narrow phones and iframe offsets.
for (const viewport of [
  { width: 390, height: 844 }, { width: 320, height: 480 },
  { left: 20, top: 1200, width: 360, height: 640 },
]) {
  for (const anchor of [
    { left: -20, top: (viewport.top || 0) + 20, bottom: (viewport.top || 0) + 42, width: 70 },
    { left: viewport.width - 30, top: (viewport.top || 0) + viewport.height - 35, bottom: (viewport.top || 0) + viewport.height - 10, width: 70 },
  ]) {
    const position = tooltipPosition(anchor, { width: 350, height: 190 }, viewport);
    const width = Math.min(350, position.maxWidth);
    assert.ok(position.left >= (viewport.left || 0) + 12);
    assert.ok(position.left + width <= (viewport.left || 0) + viewport.width - 12);
    assert.ok(position.top >= (viewport.top || 0) + 12);
    assert.ok(position.top + 190 <= (viewport.top || 0) + viewport.height - 12);
  }
}
assert.equal(tooltipPosition({ left: 80, top: 430, bottom: 450, width: 60 }, { width: 280, height: 120 }, { width: 390, height: 480 }).placement, "above");
assert.equal(tooltipPosition({ left: 80, top: 10, bottom: 30, width: 60 }, { width: 280, height: 120 }, { width: 390, height: 480 }).placement, "below");

// A small DOM/event fixture tests interaction contracts without a browser dependency.
// Layout itself remains covered by the real-page browser checks.
class Element {
  constructor(tagName, text = "") {
    this.nodeType = 1;
    this.tagName = tagName.toUpperCase();
    this.childNodes = [];
    this.parentElement = null;
    this.attributes = new Map();
    this.classes = new Set();
    this.dataset = {};
    this.style = {};
    this.hidden = false;
    this.classList = { contains: (key) => this.classes.has(key), add: (key) => this.classes.add(key), remove: (key) => this.classes.delete(key) };
    if (text) this.textContent = text;
  }
  set className(value) { this.classes = new Set(value.split(/\s+/).filter(Boolean)); }
  get className() { return [...this.classes].join(" "); }
  set textContent(value) {
    this.childNodes.forEach((node) => { node.parentElement = null; });
    this.childNodes = [{ nodeType: 3, textContent: String(value), parentElement: this }];
  }
  get textContent() { return this.childNodes.map((node) => node.textContent).join(""); }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  removeAttribute(key) { this.attributes.delete(key); }
  append(...nodes) { nodes.forEach((node) => this.appendChild(node)); }
  appendChild(node) { node.parentElement = this; this.childNodes.push(node); return node; }
  remove() {
    if (this.parentElement) this.parentElement.childNodes = this.parentElement.childNodes.filter((node) => node !== this);
    this.parentElement = null;
  }
  contains(node) { return node === this || this.childNodes.some((child) => child === node || child.contains?.(node)); }
  get isConnected() { return this.tagName === "BODY" || Boolean(this.parentElement?.isConnected); }
  matches(selector) {
    return selector.split(",").some((part) => {
      part = part.trim();
      if (/[ >:]/.test(part)) return false;
      if (part.startsWith(".")) return this.classList.contains(part.slice(1));
      if (part.startsWith("[")) {
        if (part.includes("~=")) {
          const [key, value] = part.slice(1, -1).split("~=");
          return (this.getAttribute(key) || "").split(/\s+/).includes(value);
        }
        const [key, value] = part.slice(1, -1).split("=");
        return value ? this.getAttribute(key) === value : this.attributes.has(key);
      }
      return this.tagName.toLowerCase() === part;
    });
  }
  closest(selector) { return this.matches(selector) ? this : this.parentElement?.closest(selector) || null; }
  querySelectorAll(selector) {
    return this.childNodes.flatMap((node) => node.nodeType === 1 ? [...(node.matches(selector) ? [node] : []), ...node.querySelectorAll(selector)] : []);
  }
  getBoundingClientRect() { return { left: 80, top: 90, bottom: 120, width: this.classList.contains("stat-help-tooltip") ? 320 : 80, height: 140 }; }
}

function fixture() {
  const listeners = new Map();
  const observers = [];
  const mediaListeners = new Set();
  const media = {
    matches: false,
    addEventListener(name, listener) { if (name === "change") mediaListeners.add(listener); },
    removeEventListener(name, listener) { if (name === "change") mediaListeners.delete(listener); },
  };
  const body = new Element("body");
  const doc = {
    body, activeElement: null,
    createElement: (tag) => new Element(tag),
    querySelectorAll: (selector) => body.querySelectorAll(selector),
    addEventListener(name, handler) { if (!listeners.has(name)) listeners.set(name, new Set()); listeners.get(name).add(handler); },
    removeEventListener(name, handler) { listeners.get(name)?.delete(handler); },
  };
  doc.defaultView = {
    innerWidth: 390, innerHeight: 844,
    setTimeout, clearTimeout,
    addEventListener() {}, removeEventListener() {},
    requestAnimationFrame(callback) { callback(); },
    matchMedia() { return media; },
    MutationObserver: class {
      constructor(callback) { this.callback = callback; observers.push(this); }
      observe() {} disconnect() { this.disconnected = true; }
    },
  };
  doc.defaultView.parent = doc.defaultView;
  function event(name, target, properties = {}) {
    const value = { target, pointerType: "mouse", relatedTarget: null, prevented: false, stopped: false,
      preventDefault() { this.prevented = true; }, stopPropagation() { this.stopped = true; }, ...properties };
    listeners.get(name)?.forEach((handler) => handler(value));
    return value;
  }
  return { doc, body, event, observers, setMobile(value) {
    media.matches = value;
    mediaListeners.forEach((listener) => listener({ matches: value }));
  }, mediaListeners };
}

const { doc, body, event, observers, setMobile, mediaListeners } = fixture();
const header = body.appendChild(new Element("th"));
const sort = header.appendChild(new Element("button"));
sort.className = "sort-header";
sort.setAttribute("data-sort-key", "fip");
const label = sort.appendChild(new Element("span", "FIP"));
const indicator = sort.appendChild(new Element("span", "▼"));
indicator.className = "sort-indicator";
const plain = body.appendChild(new Element("th", "WHIP"));
const value = body.appendChild(new Element("td", "whiff%"));
const unknown = body.appendChild(new Element("th", "宮城大弥"));
const nav = body.appendChild(new Element("nav"));
const navigation = nav.appendChild(new Element("th", "chase%"));
const explicitHeader = body.appendChild(new Element("th"));
const explicitLabel = explicitHeader.appendChild(new Element("span", "四球（敬遠除く）"));
explicitLabel.setAttribute("data-stat-help", "uBB");
const nestedHeader = body.appendChild(new Element("th"));
const nestedLabel = nestedHeader.appendChild(new Element("span", "OPS"));
nestedLabel.className = "metric-label";
const pitchTable = body.appendChild(new Element("table"));
pitchTable.className = "pitch-metric-summary-table";
const pitchWhiff = pitchTable.appendChild(new Element("th"));
const pitchSort = pitchWhiff.appendChild(new Element("button"));
pitchSort.className = "sort-header";
pitchSort.setAttribute("data-sort-key", "whiffRate");
const pitchLabel = pitchSort.appendChild(new Element("span", "WHIFF%"));
const pitchIndicator = pitchSort.appendChild(new Element("span", "▼"));
pitchIndicator.className = "sort-indicator";
const pitchBallCount = pitchTable.appendChild(new Element("th", "球数"));
const mobilePitchTable = body.appendChild(new Element("table"));
mobilePitchTable.className = "mobile-transpose-table";
mobilePitchTable.setAttribute("data-stat-help-scope", "season-pitch-metric-summary-table extra-presentation-class");
const mobileChase = mobilePitchTable.appendChild(new Element("th", "chase%"));
const remainingMetrics = ["csw%", "zone%", "z-swing%", "o-contact%", "chase+"].map((name) => mobilePitchTable.appendChild(new Element("th", name)));
const rankingWhiff = body.appendChild(new Element("th", "whiff%"));

const api = install(doc);
assert.equal(install(doc), api, "install is idempotent");
const tooltip = body.childNodes.find((node) => node.classList?.contains("stat-help-tooltip"));
const pitchButton = pitchWhiff.querySelectorAll(".stat-help-trigger")[0];
assert.ok(pitchButton);
assert.equal(pitchButton.parentElement, pitchWhiff, "help button is a sibling of the sort button");
assert.equal(pitchSort.childNodes.length, 2, "original sort contents are preserved");
assert.equal(pitchButton.getAttribute("aria-label"), "whiff%の意味");
for (const excluded of [header, plain, value, unknown, navigation, explicitHeader, nestedHeader, pitchBallCount, rankingWhiff]) {
  assert.equal(excluded.querySelectorAll(".stat-help-trigger").length, 0, `desktop adds no help for excluded label: ${excluded.textContent}`);
  assert.equal(excluded.classList.contains("stat-help-target"), false);
}
assert.equal(body.querySelectorAll(".stat-help-trigger").length, 7, "only the seven pitch-discipline metrics receive help controls");
assert.equal(mobileChase.querySelectorAll(".stat-help-trigger").length, 1, "transposed annual tables preserve pitch-metric scope on desktop too");
assert.ok(remainingMetrics.every((host) => host.querySelectorAll(".stat-help-trigger").length === 1));

for (const excluded of [label, plain, explicitLabel, nestedLabel, pitchBallCount, rankingWhiff]) {
  event("pointerover", excluded);
  event("focusin", excluded);
  event("click", excluded);
  assert.equal(tooltip.hidden, true, `desktop hover, focus and click cannot open help for: ${excluded.textContent}`);
}
const sortClick = event("click", label);
assert.equal(sortClick.prevented, false, "ordinary sorting stays on the original label/button");
assert.equal(sortClick.stopped, false);
assert.equal(sort.childNodes.length, 2, "excluded sort contents are untouched");

event("pointerover", pitchLabel);
assert.equal(tooltip.hidden, false, "the entire allowed metric label supports desktop hover");
assert.match(tooltip.textContent, /÷ スイング数/);
assert.equal(pitchButton.getAttribute("aria-expanded"), "true");
event("keydown", pitchButton, { key: "Escape" });
assert.equal(tooltip.hidden, true);
assert.equal(pitchButton.getAttribute("aria-expanded"), "false");

pitchSort.setAttribute("aria-describedby", "sorting-note");
doc.activeElement = pitchSort;
event("focusin", pitchSort);
assert.equal(tooltip.hidden, false, "allowed metric supports keyboard focus");
assert.equal(pitchSort.getAttribute("aria-describedby"), "sorting-note stat-help-tooltip");
event("keydown", pitchSort, { key: "Escape" });
assert.equal(pitchSort.getAttribute("aria-describedby"), "sorting-note", "preserve existing accessibility descriptions");
const pitchSortClick = event("click", pitchLabel);
assert.equal(pitchSortClick.prevented, false, "help on the header never intercepts the sort label");
assert.equal(pitchSortClick.stopped, false);

event("pointerdown", pitchButton, { pointerType: "touch" });
doc.activeElement = pitchButton;
event("focusin", pitchButton);
assert.equal(tooltip.hidden, true, "touch focus must not consume the first tap");
const helpClick = event("click", pitchButton);
assert.equal(tooltip.hidden, false, "first touch tap opens the help");
assert.equal(helpClick.stopped, true, "help clicks do not bubble to sort/filter handlers");
event("click", pitchButton);
assert.equal(tooltip.hidden, true, "second tap closes help");

for (const excluded of [plain, pitchBallCount, rankingWhiff]) {
  event("pointerdown", excluded, { pointerType: "touch" });
  event("click", excluded);
  assert.equal(tooltip.hidden, true, `touch cannot open help for excluded label: ${excluded.textContent}`);
}
event("pointerdown", mobileChase, { pointerType: "touch" });
event("click", mobileChase);
assert.equal(tooltip.hidden, false, "the transposed metric label supports tapping");
event("pointerdown", value, { pointerType: "touch" });
assert.equal(tooltip.hidden, true, "outside taps close help");
event("click", pitchButton);
event("scroll", body);
assert.equal(tooltip.hidden, true, "table and document scrolling close help");

// The same scope applies on wide desktop, phone layouts and touch-capable PCs.
setMobile(true);
for (const excluded of [label, plain, explicitLabel, nestedLabel, pitchBallCount, rankingWhiff]) {
  event("pointerdown", excluded, { pointerType: "mouse" });
  event("pointerover", excluded);
  event("focusin", excluded);
  event("click", excluded);
  assert.equal(tooltip.hidden, true, `phone layouts exclude the same labels: ${excluded.textContent}`);
}
const mobileSortClick = event("click", label);
assert.equal(mobileSortClick.prevented, false, "scope restrictions do not interfere with sorting");
event("pointerdown", mobileChase, { pointerType: "touch" });
event("click", mobileChase);
assert.equal(tooltip.hidden, false);
setMobile(false);
api.close();
event("pointerdown", pitchLabel, { pointerType: "mouse" });
event("pointerover", pitchLabel);
assert.equal(tooltip.hidden, false, "allowed metric desktop hover works after resizing without a reload");
api.close();

const dynamic = pitchTable.appendChild(new Element("th", "chase%"));
observers[0].callback([]);
assert.equal(dynamic.querySelectorAll(".stat-help-trigger").length, 1, "dynamic in-scope renderers receive help through the observer");
api.refresh();
assert.equal(dynamic.querySelectorAll(".stat-help-trigger").length, 1, "repeated scans never duplicate help controls");
event("pointerover", dynamic);
assert.equal(tooltip.hidden, false);
dynamic.textContent = "球数";
api.refresh();
assert.equal(dynamic.querySelectorAll(".stat-help-trigger").length, 0, "replacing an allowed metric with a basic header removes stale help");
assert.equal(dynamic.classList.contains("stat-help-target"), false, "removed help leaves no stale interactive target");
assert.equal(tooltip.hidden, true, "replacing the active metric closes its tooltip");
event("pointerover", dynamic);
assert.equal(tooltip.hidden, true, "the replacement basic header cannot open stale help");

dynamic.textContent = "zone%";
api.refresh();
assert.equal(dynamic.querySelectorAll(".stat-help-trigger").length, 1, "an allowed replacement gets a fresh help control");
assert.equal(dynamic.querySelectorAll(".stat-help-trigger")[0].getAttribute("aria-label"), "zone%の意味");
event("pointerover", dynamic);
dynamic.remove();
observers[0].callback([]);
assert.equal(tooltip.hidden, true, "re-rendering the active row does not leave an orphan tooltip");

api.destroy();
assert.equal(body.querySelectorAll(".stat-help-trigger").length, 0);
assert.equal(body.querySelectorAll(".stat-help-tooltip").length, 0);
assert.equal(observers[0].disconnected, true);
assert.equal(mediaListeners.size, 0);
console.log("Stat help: formulas, viewport, seven-metric scope on desktop/phone/touch, sorting, keyboard, dismissal and dynamic-render checks passed.");
