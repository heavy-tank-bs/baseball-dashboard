"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.resolve(__dirname, "../summary/compare.js"), "utf8");
const start = source.indexOf("function postEmbedHeight() {");
const end = source.indexOf("\nfunction renderHeader()", start);
assert.ok(start >= 0 && end > start, "extract the production iframe height notifier");
const notifierSource = source.slice(start, end);

function harness({ embedded = true, topLevel = false, shell = true, height = 1200, bodyHeight = 1200 } = {}) {
  const frames = [];
  const messages = [];
  const content = { height, bodyHeight };
  const hostWindow = {
    location: { origin: "https://example.test" },
    requestAnimationFrame(callback) { frames.push(callback); },
  };
  hostWindow.parent = topLevel ? hostWindow : {
    postMessage(message, origin) { messages.push({ ...message, origin }); },
  };
  const scope = {
    state: { embedded },
    window: hostWindow,
    document: {
      // A tall iframe viewport must not prevent shorter content from shrinking it.
      documentElement: { scrollHeight: 9000 },
      body: { scrollHeight: 9000, get offsetHeight() { return content.bodyHeight; } },
      querySelector(selector) {
        assert.equal(selector, ".site-shell");
        return shell ? { getBoundingClientRect: () => ({ height: content.height }) } : null;
      },
    },
  };
  vm.createContext(scope);
  vm.runInContext(notifierSource, scope);
  return {
    content, frames, messages,
    notify: () => scope.postEmbedHeight(),
    flush() { while (frames.length) frames.shift()(); },
  };
}

const embedded = harness();
embedded.notify();
assert.equal(embedded.messages.length, 0, "measure after the next animation frame");
embedded.flush();
assert.deepEqual(embedded.messages.pop(), {
  type: "playerStatsHeight", height: 1200, origin: "https://example.test",
}, "shorter content shrinks a previously 9000px iframe");

embedded.content.height = 6000;
embedded.notify();
embedded.flush();
assert.equal(embedded.messages.pop().height, 6000, "a larger annual view can grow again");

embedded.content.height = 700.25;
embedded.notify();
embedded.content.height = 701.1;
embedded.flush();
assert.equal(embedded.messages.pop().height, 702, "use the latest rendered size and round up fractional pixels");

const fallback = harness({ shell: false, bodyHeight: 850 });
fallback.notify();
fallback.flush();
assert.equal(fallback.messages[0].height, 850, "body layout height is the fallback before the shell exists");

const empty = harness({ height: 0, bodyHeight: 0 });
empty.notify();
empty.flush();
assert.equal(empty.messages[0].height, 1, "send a positive height for an empty layout");

for (const options of [{ embedded: false }, { topLevel: true }]) {
  const standalone = harness(options);
  standalone.notify();
  standalone.flush();
  assert.equal(standalone.frames.length, 0);
  assert.equal(standalone.messages.length, 0, "standalone views never resize another window");
}

console.log("PASS: iframe height grows, shrinks, rounds rendered content, falls back safely, and skips standalone views");
