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
    matchMedia() { return { matches: false }; },
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
  return { doc, body, event, observers };
}

const { doc, body, event, observers } = fixture();
const header = body.appendChild(new Element("th"));
const sort = header.appendChild(new Element("button"));
sort.className = "sort-header";
sort.setAttribute("data-sort-key", "fip");
const label = sort.appendChild(new Element("span", "FIP"));
const indicator = sort.appendChild(new Element("span", "▼"));
indicator.className = "sort-indicator";
const plain = body.appendChild(new Element("th", "WHIP"));
const value = body.appendChild(new Element("td", "FIP"));
const unknown = body.appendChild(new Element("th", "宮城大弥"));
const nav = body.appendChild(new Element("nav"));
const navigation = nav.appendChild(new Element("th", "OPS"));
const explicitHeader = body.appendChild(new Element("th"));
const explicitLabel = explicitHeader.appendChild(new Element("span", "四球（敬遠除く）"));
explicitLabel.setAttribute("data-stat-help", "uBB");
const nestedHeader = body.appendChild(new Element("th"));
const nestedLabel = nestedHeader.appendChild(new Element("span", "OPS"));
nestedLabel.className = "metric-label";

const api = install(doc);
assert.equal(install(doc), api, "install is idempotent");
const tooltip = body.childNodes.find((node) => node.classList?.contains("stat-help-tooltip"));
const button = header.childNodes.find((node) => node.classList?.contains("stat-help-trigger"));
const plainButton = plain.childNodes.find((node) => node.classList?.contains("stat-help-trigger"));
assert.ok(button && plainButton);
assert.equal(button.parentElement, header, "help button is a sibling of the sort button");
assert.equal(sort.childNodes.length, 2, "original sort contents are preserved");
assert.equal(button.getAttribute("aria-label"), "FIPの意味");
assert.equal(value.querySelectorAll("button").length, 0);
assert.equal(unknown.querySelectorAll("button").length, 0);
assert.equal(navigation.querySelectorAll("button").length, 0);
assert.equal(explicitHeader.querySelectorAll("button").length, 1);
assert.equal(explicitHeader.querySelectorAll("button")[0].getAttribute("aria-label"), "uBBの意味", "explicit scope overrides generic BB meaning");
assert.equal(nestedHeader.querySelectorAll("button").length, 1, "nested metric selectors cannot create duplicate help controls");

event("pointerover", label);
assert.equal(tooltip.hidden, false, "the entire metric label supports hover");
assert.match(tooltip.textContent, /故意四球を除く四球/);
assert.equal(button.getAttribute("aria-expanded"), "true");
event("keydown", button, { key: "Escape" });
assert.equal(tooltip.hidden, true);
assert.equal(button.getAttribute("aria-expanded"), "false");

sort.setAttribute("aria-describedby", "sorting-note");
doc.activeElement = sort;
event("focusin", sort);
assert.equal(sort.getAttribute("aria-describedby"), "sorting-note stat-help-tooltip");
event("keydown", sort, { key: "Escape" });
assert.equal(sort.getAttribute("aria-describedby"), "sorting-note", "preserve existing accessibility descriptions");
const sortClick = event("click", label);
assert.equal(sortClick.prevented, false, "sorting stays on the original label/button");
assert.equal(sortClick.stopped, false);

event("pointerdown", button, { pointerType: "touch" });
doc.activeElement = button;
event("focusin", button);
assert.equal(tooltip.hidden, true, "touch focus must not consume the first tap");
const helpClick = event("click", button);
assert.equal(tooltip.hidden, false, "first touch tap opens the help");
assert.equal(helpClick.stopped, true, "help clicks do not bubble to sort/filter handlers");
event("click", button);
assert.equal(tooltip.hidden, true, "second tap closes help");

event("pointerdown", plain, { pointerType: "touch" });
event("click", plain);
assert.equal(tooltip.hidden, false, "plain metric labels also support tapping");
event("pointerdown", value, { pointerType: "touch" });
assert.equal(tooltip.hidden, true, "outside taps close help");
event("click", plainButton);
event("scroll", body);
assert.equal(tooltip.hidden, true, "table and document scrolling close help");

const dynamic = body.appendChild(new Element("th", "chase%"));
observers[0].callback([]);
assert.equal(dynamic.querySelectorAll("button").length, 1, "dynamic renderers receive help through the observer");
api.refresh();
assert.equal(dynamic.querySelectorAll("button").length, 1, "repeated scans never duplicate help controls");
dynamic.textContent = "OPS";
api.refresh();
assert.equal(dynamic.querySelectorAll("button").length, 1, "replacement header text gets a fresh help control");
assert.equal(dynamic.querySelectorAll("button")[0].getAttribute("aria-label"), "OPSの意味");
event("pointerover", dynamic);
dynamic.remove();
observers[0].callback([]);
assert.equal(tooltip.hidden, true, "re-rendering the active row does not leave an orphan tooltip");

api.destroy();
assert.equal(body.querySelectorAll(".stat-help-trigger").length, 0);
assert.equal(body.querySelectorAll(".stat-help-tooltip").length, 0);
assert.equal(observers[0].disconnected, true);
console.log("Stat help: formula, viewport, scoped enhancement, sorting, keyboard, touch, dismissal and dynamic-render checks passed.");
