(function (global, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (!global || !global.document) return;
  global.StatHelp = api;
  const start = () => api.install(global.document, global.StatHelpConfig || {});
  if (global.document.readyState === "loading") global.document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";

  // Formulas follow this site's annual totals and pitch-discipline aggregation.
  // In particular, 空振率 and whiff% intentionally have different denominators.
  const entries = [
    ["防御率", "9イニング当たりに換算した自責点。小さいほど失点を抑えています。", "自責点 × 9 ÷ 投球回"],
    ["FIP", "本塁打・四死球・三振から投球内容を評価する指標。守備の影響を受けにくく、低いほど良好です。", "{13 × 被本塁打 ＋ 3 ×（故意四球を除く四球 ＋ 死球）− 2 × 奪三振} ÷ 投球回 ＋ 年度・リーグ定数"],
    ["WHIP", "1イニング当たりに四球と安打で出した走者数。死球は含みません。", "（被安打 ＋ 与四球）÷ 投球回"],
    ["投球回", "奪ったアウト数をイニングで表したもの。「.1」は1アウト、「.2」は2アウトです。", "3アウト ＝ 1イニング"],
    ["被打率", "相手打者に安打を許した割合。四死球・犠打・犠飛などは被打数に含めません。", "被安打 ÷ 被打数"],
    ["被BABIP", "本塁打を除き、打球が安打になった割合。三振は打球に含みません。", "（被安打 − 被本塁打）÷（被打数 − 奪三振 − 被本塁打 ＋ 犠飛）"],
    ["K/9", "9イニング当たりに換算した奪三振数。", "奪三振 × 9 ÷ 投球回"],
    ["BB/9", "9イニング当たりに換算した与四球数。", "与四球 × 9 ÷ 投球回"],
    ["HR/9", "9イニング当たりに換算した被本塁打数。", "被本塁打 × 9 ÷ 投球回"],
    ["K/BB", "四球1つに対して奪った三振の数。四球が0のときは算出できません。", "奪三振 ÷ 与四球"],
    ["ゴロアウト率", "記録されたアウトの打席結果のうち、ゴロが占める割合。", "ゴロによるアウトの打席結果 ÷ 記録されたアウトの打席結果 × 100"],
    ["フライアウト率", "記録されたアウトの打席結果のうち、フライが占める割合。ライナー・犠飛を含みます。", "フライによるアウトの打席結果 ÷ 記録されたアウトの打席結果 × 100"],
    ["whiff%", "振った球のうち、空振りした割合。全投球を分母にする「空振率」とは異なります。", "空振り数 ÷ スイング数 × 100"],
    ["空振率", "全投球のうち、空振りを取った割合。スイングを分母にする「whiff%」とは異なります。", "空振り数 ÷ 投球数 × 100"],
    ["csw%", "全投球のうち、空振りか見逃しでストライクを取った割合。", "（空振り数 ＋ 見逃しストライク数）÷ 全投球数 × 100"],
    ["zone%", "投球位置が分かる球のうち、ストライクゾーン内へ投げた割合。", "ゾーン内投球数 ÷ 投球位置を取得できた投球数 × 100"],
    ["z-swing%", "ゾーン内の球を打者が振った割合。", "ゾーン内スイング数 ÷ ゾーン内投球数 × 100"],
    ["o-contact%", "ゾーン外を振ったとき、バットに当たった割合。", "ゾーン外コンタクト数 ÷ ゾーン外スイング数 × 100"],
    ["chase%", "ゾーン外の球を打者が振った割合。ボール球を振らせた程度を表します。", "ゾーン外スイング数 ÷ ゾーン外投球数 × 100"],
    ["chase+", "同じリーグの平均を100として、ゾーン外を振らせる割合を比較した指数。", "球種別 chase% ÷ 同リーグ平均 chase% × 100"],
    ["ボールゾーンスイング率", "投球位置が分かるゾーン外の球を、打者が振った割合。", "ゾーン外スイング数 ÷ ゾーン外投球数 × 100"],
    ["打率", "打数のうち、安打を打った割合。四死球・犠打・犠飛などは打数に含めません。", "安打 ÷ 打数"],
    ["出塁率", "安打・四球・死球で出塁した割合。失策による出塁は含みません。", "（安打 ＋ 四球 ＋ 死球）÷（打数 ＋ 四球 ＋ 死球 ＋ 犠飛）"],
    ["長打率", "1打数当たりに安打で得た塁数。二塁打は2、三塁打は3、本塁打は4として数えます。", "塁打 ÷ 打数"],
    ["OPS", "出塁率と長打率を足した、打撃力の目安。", "出塁率 ＋ 長打率"],
    ["IsoD", "打率に対し、四死球によってどれだけ出塁率を上げたかを表す目安。", "出塁率 − 打率"],
    ["IsoP", "単打を除いた長打による塁打の多さを表す目安。", "長打率 − 打率"],
    ["BABIP", "本塁打を除き、打球が安打になった割合。三振は打球に含みません。", "（安打 − 本塁打）÷（打数 − 三振 − 本塁打 ＋ 犠飛）"],
    ["wOBA", "安打・四死球などを得点への貢献度で重み付けした出塁指標。年度・リーグの係数を使います。"],
    ["wRC", "安打・四死球などの打撃結果から推定した得点創出量。年度・リーグの係数を使います。"],
    ["wRC+", "球場とリーグの得点環境を補正した打撃指標。平均が100で、120なら平均より20%高い得点創出力が目安です。"],
    ["得点圏打率", "打席結果の直前に走者が二塁か三塁にいたときの打率。", "得点圏での安打 ÷ 得点圏での打数"],
    ["打席", "打者として打席に立った回数。四死球・犠打・犠飛なども含みます。"],
    ["打数", "打席数から四死球・犠打・犠飛・打撃妨害などを除いた数。"],
    ["被打数", "対戦した打者の打数。四死球・犠打・犠飛などは含みません。"],
    ["打者", "投手が対戦した打者の数。四死球・犠打・犠飛なども含みます。"],
    ["試合", "その選手が出場・登板した試合数。条件別の表では、その条件での試合数です。"],
    ["登板", "投手として試合で投球した回数。"],
    ["先発", "試合開始時から投げた登板数。"],
    ["救援", "試合途中から投げた登板数。"],
    ["勝利", "公式記録で勝利投手となった回数。"],
    ["敗戦", "公式記録で敗戦投手となった回数。"],
    ["勝利登板", "勝利投手となった登板での失点・四死球を集計した行です。"],
    ["敗戦登板", "敗戦投手となった登板での失点・四死球を集計した行です。"],
    ["勝敗なし登板", "勝利投手・敗戦投手のどちらにもならなかった登板での失点・四死球を集計した行です。"],
    ["セーブ", "リードを守って試合を終え、公式記録のセーブ条件を満たした回数。"],
    ["ホールド", "救援登板でリードや同点を守り、公式記録のホールド条件を満たした回数。"],
    ["球数", "投げた球の合計。球種別の表では、その球種を投げた数です。"],
    ["割合", "各区分が集計対象の全体に占める比率。", "各区分の件数 ÷ 集計対象の総数 × 100"],
    ["平均球速", "球速を取得できた投球の平均速度。単位は km/h です。", "記録された球速の合計 ÷ 球速を取得できた投球数"],
    ["最速", "球速を取得できた投球のうち、最も速かった球の速度。単位は km/h です。"],
    ["空振", "バットを振ってボールに当たらなかった投球の数。"],
    ["見逃し", "バットを振らずにストライクと判定された投球の数。"],
    ["安打", "単打・二塁打・三塁打・本塁打の合計。失策による出塁は含みません。"],
    ["単打", "安打のうち、一塁まで進んだもの。二塁打・三塁打・本塁打は含みません。"],
    ["塁打", "安打で得た塁数の合計。単打は1、二塁打は2、三塁打は3、本塁打は4として数えます。"],
    ["被安打", "相手に許した安打の合計。本塁打も含みます。"],
    ["二塁打", "打球が安打となり、打者が二塁まで進んだ回数。"],
    ["三塁打", "打球が安打となり、打者が三塁まで進んだ回数。"],
    ["本塁打", "打球が安打となり、打者が本塁まで生還した回数。"],
    ["被本塁打", "相手打者に本塁打を打たれた回数。"],
    ["三振", "打者が三振した回数。投手の表では奪った三振の数です。"],
    ["奪三振", "相手打者から三振を奪った回数。見逃し三振と空振り三振の合計です。"],
    ["空振り三振", "最後のストライクが空振りだった三振の回数。"],
    ["見逃し三振", "最後のストライクを打者が見逃した三振の回数。"],
    ["四球", "ボール4つで一塁へ進んだ回数。故意四球も含みます。"],
    ["与四球", "相手に与えた四球の数。故意四球も含みます。"],
    ["四死球", "四球と死球を合わせた数。四球には故意四球も含みます。", "四球 ＋ 死球"],
    ["死球", "投球が打者の体などに当たり、一塁への進塁が認められた回数。"],
    ["与死球", "相手打者に与えた死球の数。"],
    ["敬遠", "故意四球として記録された回数。四球の内数です。"],
    ["uBB", "故意四球を除いた四球の数。このサイトではFIPの計算にも使います。", "四球 − 故意四球"],
    ["犠打", "犠牲バントとして記録された回数。打数には含みません。"],
    ["犠飛", "犠牲フライとして記録された回数。打数には含みませんが、出塁率の分母には含みます。"],
    ["打点", "その打者の打撃結果によって入った得点として記録された数。併殺や失策などでは付かない場合があります。"],
    ["得点", "走者として本塁へ生還して記録された点数。"],
    ["失点", "その投手の責任として記録された得点。自責点以外の失点も含みます。"],
    ["自責点", "失策などの影響を除き、その投手の責任で入ったと公式記録で判定された得点。"],
    ["盗塁", "盗塁成功として記録された回数。盗塁死は含みません。"],
    ["ゴロ", "ゴロによるアウトの打席結果。併殺なども含みます。"],
    ["フライ", "フライによるアウトの打席結果。ライナーと犠飛も含みます。"],
    ["前年差", "今年の数値から前年の数値を引いた差。＋は増加、−は減少を表します。", "今年 − 前年（割合の指標はパーセントポイント差）"],
    ["球種比率", "記録された投球を球種ごとに分けた割合。", "各球種の球数 ÷ 全球数 × 100"],
    ["決め球サマリ", "三振の最後に投げた球を球種別に集計。三振数と、見逃し・空振りの内訳を示します。"],
    ["アウト内容", "打席結果のアウトを、ゴロ・フライ・三振などの種類に分けた内訳。"],
  ];
  const aliases = {
    "ERA": "防御率", "IP": "投球回", "HLD": "ホールド", "H": "安打", "HR": "本塁打",
    "BB": "四球", "HBP": "死球", "K": "奪三振", "AB": "打数", "PA": "打席", "AVG": "打率",
    "OBP": "出塁率", "SLG": "長打率", "被本": "被本塁打", "被安": "被安打", "本塁": "本塁打",
    "自責": "自責点", "対戦打者": "打者", "平均": "平均球速", "平均球速 (km/h)": "平均球速", "平均球速（km/h）": "平均球速",
    "空振り": "空振", "空振り率": "空振率", "Whiff%": "whiff%", "CSW%": "csw%", "Zone%": "zone%",
    "Z-Swing%": "z-swing%", "O-Contact%": "o-contact%", "Chase%": "chase%", "Chase+": "chase+",
    "２Ｂ": "二塁打", "2B": "二塁打", "３Ｂ": "三塁打", "3B": "三塁打",
    "故意四球": "敬遠", "故意四": "敬遠", "四死": "四死球", "空三振": "空振り三振", "見三振": "見逃し三振",
  };
  const normalizeLabel = (label) => String(label || "").normalize("NFKC").replace(/[\s\u200b]+/g, "").replace(/[↕▲▼]+$/g, "").toLowerCase();
  const dictionary = new Map(entries.map(([label, meaning, formula = ""]) => [normalizeLabel(label), Object.freeze({ label, meaning, formula })]));
  Object.entries(aliases).forEach(([alias, key]) => {
    if (key) dictionary.set(normalizeLabel(alias), dictionary.get(normalizeLabel(key)));
  });
  const getHelp = (label) => dictionary.get(normalizeLabel(label)) || null;

  const DEFAULT_SELECTOR = "th, dt, .metric-label, .stat-label, .metric-name, .legend-label, .stat-pill > span, .result-stat > span, .compare-season-item > span, .card-head > h3, .comparison-bar-head > h3, .legend-list li > span:last-child, .outcome-item-head > strong, [data-stat-help]";
  const installations = new WeakMap();

  function tooltipPosition(anchor, box, viewport) {
    const margin = 12;
    const gap = 10;
    const leftEdge = (viewport.left || 0) + margin;
    const topEdge = (viewport.top || 0) + margin;
    const maxWidth = Math.max(0, viewport.width - 2 * margin);
    const maxHeight = Math.max(0, viewport.height - 2 * margin);
    const width = Math.min(box.width, maxWidth);
    const height = Math.min(box.height, maxHeight);
    const rightEdge = leftEdge + maxWidth;
    const bottomEdge = topEdge + maxHeight;
    const below = bottomEdge - anchor.bottom - gap;
    const above = anchor.top - topEdge - gap;
    const placement = below >= height || below >= above ? "below" : "above";
    const preferredTop = placement === "below" ? anchor.bottom + gap : anchor.top - height - gap;
    return {
      left: Math.max(leftEdge, Math.min(anchor.left + (anchor.width - width) / 2, rightEdge - width)),
      top: Math.max(topEdge, Math.min(preferredTop, bottomEdge - height)),
      maxWidth, maxHeight, placement,
    };
  }

  function install(doc, options = {}) {
    if (!doc || !doc.body) return null;
    if (installations.has(doc)) return installations.get(doc);
    const win = doc.defaultView;
    const selector = options.selector || DEFAULT_SELECTOR;
    const records = new WeakMap();
    const tooltip = doc.createElement("div");
    tooltip.id = "stat-help-tooltip";
    tooltip.className = "stat-help-tooltip";
    tooltip.setAttribute("role", "tooltip");
    tooltip.hidden = true;
    const title = doc.createElement("strong");
    title.className = "stat-help-tooltip-title";
    const meaning = doc.createElement("p");
    const formula = doc.createElement("p");
    formula.className = "stat-help-tooltip-formula";
    tooltip.append(title, meaning, formula);
    doc.body.appendChild(tooltip);
    let active = null;
    let closeTimer = null;
    let pendingScan = false;
    let lastPointerWasTouch = false;

    function describedBy(node, add) {
      if (!node) return;
      const ids = new Set((node.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean));
      if (add) ids.add(tooltip.id); else ids.delete(tooltip.id);
      if (ids.size) node.setAttribute("aria-describedby", [...ids].join(" ")); else node.removeAttribute("aria-describedby");
    }
    function cancelClose() {
      if (closeTimer !== null) win.clearTimeout(closeTimer);
      closeTimer = null;
    }
    function hide() {
      cancelClose();
      if (active) {
        active.record.trigger.setAttribute("aria-expanded", "false");
        describedBy(active.record.trigger, false);
        describedBy(active.focusOwner, false);
        active.host.classList.remove("stat-help-open");
      }
      tooltip.hidden = true;
      active = null;
    }
    function viewport() {
      const visual = win.visualViewport;
      let left = visual?.offsetLeft || 0;
      let top = visual?.offsetTop || 0;
      let right = left + (visual?.width || win.innerWidth);
      let bottom = top + (visual?.height || win.innerHeight);
      // The individual-player page expands this iframe to its content height.
      // Its visible viewport is still limited by the outer browser window.
      let current = win;
      let offsetX = 0;
      let offsetY = 0;
      try {
        while (current.parent && current.parent !== current && current.frameElement) {
          const frame = current.frameElement;
          const rect = frame.getBoundingClientRect();
          offsetX += rect.left + (frame.clientLeft || 0);
          offsetY += rect.top + (frame.clientTop || 0);
          current = current.parent;
          const outer = current.visualViewport;
          const outerLeft = (outer?.offsetLeft || 0) - offsetX;
          const outerTop = (outer?.offsetTop || 0) - offsetY;
          left = Math.max(left, outerLeft);
          top = Math.max(top, outerTop);
          right = Math.min(right, outerLeft + (outer?.width || current.innerWidth));
          bottom = Math.min(bottom, outerTop + (outer?.height || current.innerHeight));
        }
      } catch (_) { /* A cross-origin frame can use its own viewport safely. */ }
      return { left, top, width: Math.max(0, right - left), height: Math.max(0, bottom - top) };
    }
    function show(host, pinned = false, focusOwner = null) {
      const record = records.get(host);
      if (!record) return;
      cancelClose();
      if (active?.host !== host) hide();
      else if (active.focusOwner !== focusOwner) describedBy(active.focusOwner, false);
      active = { host, record, pinned, focusOwner };
      title.textContent = record.help.label;
      meaning.textContent = record.help.meaning;
      formula.textContent = record.help.formula ? `計算：${record.help.formula}` : "";
      formula.hidden = !record.help.formula;
      tooltip.hidden = false;
      tooltip.style.visibility = "hidden";
      const bounds = viewport();
      tooltip.style.maxWidth = `${Math.min(350, Math.max(0, bounds.width - 24))}px`;
      tooltip.style.maxHeight = `${Math.max(0, bounds.height - 24)}px`;
      const position = tooltipPosition(host.getBoundingClientRect(), tooltip.getBoundingClientRect(), bounds);
      tooltip.style.left = `${position.left}px`;
      tooltip.style.top = `${position.top}px`;
      tooltip.dataset.placement = position.placement;
      tooltip.style.visibility = "";
      record.trigger.setAttribute("aria-expanded", "true");
      describedBy(record.trigger, true);
      describedBy(focusOwner, true);
      host.classList.add("stat-help-open");
    }
    function findHost(node) {
      const element = node?.nodeType === 1 ? node : node?.parentElement;
      const host = element?.closest?.(".stat-help-target");
      return host && records.has(host) ? host : null;
    }
    function labelText(node) {
      if (node.nodeType === 3) return node.textContent;
      if (node.nodeType !== 1 || node.classList.contains("stat-help-trigger") || node.classList.contains("sort-indicator") || node.getAttribute("aria-hidden") === "true") return "";
      return [...node.childNodes].map(labelText).join("");
    }
    function enhance(host) {
      if (host.closest(".stat-help-tooltip, svg, nav, select, option, [data-stat-help-ignore]")) return;
      // A help button must never be nested in a link, sort button, or other control.
      if (host.closest("button, a, input, textarea, [role=button]")) return;
      const ancestor = host.parentElement?.closest(".stat-help-target");
      if (ancestor && records.has(ancestor)) return;
      const label = host.getAttribute("data-stat-help") || labelText(host);
      const help = getHelp(label);
      let previous = records.get(host);
      if (previous && !host.contains(previous.trigger)) {
        if (active?.host === host) hide();
        records.delete(host);
        previous = null;
      }
      if (!help) {
        if (previous) {
          if (active?.host === host) hide();
          previous.trigger.remove();
          host.classList.remove("stat-help-target");
          records.delete(host);
        }
        return;
      }
      if (previous) {
        if (active?.host === host && previous.help !== help) hide();
        previous.help = help;
        previous.trigger.setAttribute("aria-label", `${help.label}の意味`);
        return;
      }
      const trigger = doc.createElement("button");
      trigger.type = "button";
      trigger.className = "stat-help-trigger";
      trigger.setAttribute("aria-label", `${help.label}の意味`);
      trigger.setAttribute("aria-expanded", "false");
      trigger.setAttribute("aria-controls", tooltip.id);
      trigger.setAttribute("data-stat-help-trigger", "");
      trigger.textContent = "?";
      host.appendChild(trigger);
      host.classList.add("stat-help-target");
      records.set(host, { help, trigger });
    }
    function refresh(root = doc) {
      if (active && !active.host.isConnected) hide();
      if (root.matches?.(selector)) enhance(root);
      root.querySelectorAll(selector).forEach(enhance);
    }
    function scheduleRefresh() {
      if (pendingScan) return;
      pendingScan = true;
      const schedule = win.requestAnimationFrame || ((callback) => win.setTimeout(callback, 0));
      schedule.call(win, () => { pendingScan = false; refresh(); });
    }
    function scheduleClose() {
      cancelClose();
      closeTimer = win.setTimeout(hide, 140);
    }
    const handlers = {
      pointerover(event) {
        if (event.pointerType === "touch") return;
        if (tooltip.contains(event.target)) { cancelClose(); return; }
        const host = findHost(event.target);
        if (!host || host.contains(event.relatedTarget) || (active?.pinned && active.host !== host)) return;
        show(host, active?.host === host && active.pinned);
      },
      pointerout(event) {
        if (!active || active.pinned || event.pointerType === "touch") return;
        if (active.host.contains(event.relatedTarget) || tooltip.contains(event.relatedTarget)) return;
        if (active.host.contains(event.target) || tooltip.contains(event.target)) scheduleClose();
      },
      pointerdown(event) {
        lastPointerWasTouch = event.pointerType === "touch";
        if (active && !active.host.contains(event.target) && !tooltip.contains(event.target)) hide();
      },
      click(event) {
        const host = findHost(event.target);
        if (!host) { if (active && !tooltip.contains(event.target)) hide(); return; }
        const element = event.target.nodeType === 1 ? event.target : event.target.parentElement;
        const isTrigger = Boolean(element.closest(".stat-help-trigger"));
        const coarse = lastPointerWasTouch || Boolean(win.matchMedia?.("(hover: none), (pointer: coarse)").matches);
        if (!isTrigger && (!coarse || element.closest("button, a, input, select, textarea, [role=button]"))) return;
        event.preventDefault();
        // Keep help clicks separate from delegated sorting/filtering actions.
        if (isTrigger) event.stopPropagation();
        if (active?.host === host && active.pinned) hide();
        else show(host, true, doc.activeElement === records.get(host).trigger ? doc.activeElement : null);
      },
      focusin(event) {
        if (lastPointerWasTouch) return;
        const host = findHost(event.target);
        if (host) show(host, false, event.target);
      },
      focusout(event) {
        if (active && !active.host.contains(event.relatedTarget) && !tooltip.contains(event.relatedTarget)) hide();
      },
      keydown(event) {
        lastPointerWasTouch = false;
        if (event.key === "Escape" && active) { hide(); event.preventDefault(); }
      },
    };
    Object.entries(handlers).forEach(([name, handler]) => doc.addEventListener(name, handler, name === "pointerdown" || name === "click"));
    doc.addEventListener("scroll", hide, true);
    win.addEventListener("resize", hide);
    win.addEventListener("blur", hide);
    win.visualViewport?.addEventListener("resize", hide);
    win.visualViewport?.addEventListener("scroll", hide);
    const ancestorWindows = [];
    try {
      let outer = win.parent;
      while (outer && outer !== win && !ancestorWindows.includes(outer)) {
        outer.document.addEventListener("scroll", hide, true);
        outer.document.addEventListener("pointerdown", hide, true);
        outer.addEventListener("resize", hide);
        outer.visualViewport?.addEventListener("resize", hide);
        outer.visualViewport?.addEventListener("scroll", hide);
        ancestorWindows.push(outer);
        if (outer.parent === outer) break;
        outer = outer.parent;
      }
    } catch (_) { /* Cross-origin ancestors do not expose their event targets. */ }
    refresh();
    const observer = typeof win.MutationObserver === "function" ? new win.MutationObserver(scheduleRefresh) : null;
    observer?.observe(doc.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["data-stat-help"] });
    const api = { refresh, close: hide, destroy() {
      hide();
      observer?.disconnect();
      Object.entries(handlers).forEach(([name, handler]) => doc.removeEventListener(name, handler, name === "pointerdown" || name === "click"));
      doc.removeEventListener("scroll", hide, true);
      win.removeEventListener("resize", hide);
      win.removeEventListener("blur", hide);
      win.visualViewport?.removeEventListener("resize", hide);
      win.visualViewport?.removeEventListener("scroll", hide);
      ancestorWindows.forEach((outer) => {
        outer.document.removeEventListener("scroll", hide, true);
        outer.document.removeEventListener("pointerdown", hide, true);
        outer.removeEventListener("resize", hide);
        outer.visualViewport?.removeEventListener("resize", hide);
        outer.visualViewport?.removeEventListener("scroll", hide);
      });
      doc.querySelectorAll(".stat-help-target").forEach((host) => {
        records.get(host)?.trigger.remove();
        host.classList.remove("stat-help-target");
      });
      tooltip.remove();
      installations.delete(doc);
    } };
    installations.set(doc, api);
    return api;
  }

  return Object.freeze({ getHelp, normalizeLabel, tooltipPosition, install, DEFAULT_SELECTOR });
});
