/* Shareable result links for every CarMall finder (wiper, NGK plug, and this repo's
 * filters / pads / tires). Spec: docs/share-links.md.
 *
 * The finders live in an iframe on carmall.com.tw, so they cannot touch the address bar
 * the customer sees. The embed snippet on the store page does that for them:
 *
 *   finder ──carmallFinderState {finder, state}──▶ store page  (rewrites its #hash)
 *   finder ◀──carmallHost {url}──────────────────  store page  (so the finder can build
 *                                                               a link to the STORE page)
 *
 * State lives in the #hash, never in ?query: on the store page GA4 sends a page_view for
 * every query-string change made with history.replaceState, but none for hash changes
 * (measured on /pages/partsfinder 2026-11-16). The same #b=…&m=…&y=… format is used in
 * the finder's own URL, which is how the snippet hands a shared link back in.
 *
 * Keys are names, never <option> indexes: data.json is rebuilt twice a day and the order
 * moves. A key that matches no option, or more than one, stops the restore at that level —
 * a guessed car is a wrong part in someone's cart.
 *
 * This file is OPTIONAL for every finder. The wiper and NGK finders load it from this repo
 * with `async`; if it never arrives they work exactly as before, minus the share button.
 * A finder hands over its config through a queue so the load order does not matter:
 *   (window.CarmallLinkQueue = window.CarmallLinkQueue || []).push(config)
 *   config = { finder: "wiper", title: "雨刷快速查詢", result: <#result element>,
 *              steps: [{ el: <select>, p: "b", key: function (optionValue) -> string }, …] }
 */
(function () {
  "use strict";
  if (window.CarmallLink) return;

  var HOST_ORIGIN = /^https:\/\/(www\.)?carmall\.com\.tw$/;
  var MAX_LEN = 100;
  var embedded = window.parent !== window;
  var cfg = null, host = null, current = "", restoring = false;
  var bar = null, btn = null, msg = null, box = null;

  function readHash() {
    try { return new URLSearchParams(location.hash.replace(/^#/, "")); }
    catch (e) { return new URLSearchParams(); }
  }

  // Walk the steps in order, picking the one option whose key equals the link's value.
  // Each pick fires the select's own change handler, which fills the next select.
  function restore() {
    var q = readHash();
    if (!q.get(cfg.steps[0].p)) return;
    // The customer already started picking before this file arrived: theirs wins.
    if (cfg.steps[0].el.value !== "") return;
    restoring = true;
    try {
      for (var i = 0; i < cfg.steps.length; i++) {
        var s = cfg.steps[i], want = q.get(s.p);
        if (!want) break;
        var hits = [];
        for (var j = 0; j < s.el.options.length; j++) {
          var v = s.el.options[j].value;
          if (v !== "" && s.key(v) === want) hits.push(v);
        }
        if (hits.length !== 1) break;
        s.el.value = hits[0];
        s.el.dispatchEvent(new Event("change"));
      }
    } finally {
      restoring = false;
    }
  }

  function state() {
    var q = new URLSearchParams();
    for (var i = 0; i < cfg.steps.length; i++) {
      var s = cfg.steps[i];
      if (s.el.value === "") break;
      var k = s.key(s.el.value);
      if (!k || k.length > MAX_LEN) break;
      q.set(s.p, k);
    }
    return q.toString();
  }

  function sync() {
    if (restoring) return;
    var next = state();
    if (next !== current && box) { box.hidden = true; say(""); }   // old car's link / message
    current = next;
    // Own URL too, so the bare github.io page is shareable and a reload keeps the result.
    try {
      history.replaceState(history.state, "",
        location.pathname + location.search + (current ? "#" + current : ""));
    } catch (e) {}
    if (embedded) {
      try {
        parent.postMessage({ type: "carmallFinderState", finder: cfg.finder, state: current }, "*");
      } catch (e) {}
    }
    updateBar();
  }

  // Inside the store page the link must point at the STORE page, which only the new embed
  // snippet tells us. Under an older snippet there is no such URL and the iframe has no
  // clipboard/share permission, so the button stays hidden rather than failing on tap.
  function shareUrl() {
    if (!current) return null;
    if (embedded) return host ? host + "#f=" + cfg.finder + "&" + current : null;
    return location.origin + location.pathname + "#" + current;
  }

  function label() {
    var q = new URLSearchParams(current), parts = [];
    cfg.steps.forEach(function (s) { if (q.get(s.p)) parts.push(q.get(s.p)); });
    return parts.join(" ");
  }

  function say(text) { msg.textContent = text; }

  function manual(url) {
    box.value = url;
    box.hidden = false;
    try { box.focus(); box.select(); } catch (e) {}
    say("請複製上面的連結");
  }

  function copy(url) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(
        function () { box.hidden = true; say("已複製連結，可以貼給朋友了"); },
        function () { manual(url); });
    } else {
      manual(url);
    }
  }

  function onShare() {
    var url = shareUrl();
    if (!url) return;
    say("");
    // Phones get the system share sheet (LINE, Messenger…); desktops copy the link, which
    // is what the button promises there.
    var touch = window.matchMedia && window.matchMedia("(pointer: coarse)").matches;
    if (touch && navigator.share) {
      navigator.share({ title: cfg.title + "｜" + label(), url: url }).catch(function (e) {
        if (e && e.name === "AbortError") return;   // the customer closed the sheet
        copy(url);
      });
      return;
    }
    copy(url);
  }

  function buildBar() {
    var css = document.createElement("style");
    css.textContent =
      ".cl-share{margin:12px 0 0;display:flex;flex-direction:column;gap:6px}" +
      ".cl-btn{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;" +
      "padding:11px 14px;border:1px solid var(--line,#e6e7ec);border-radius:var(--radius,14px);" +
      "background:var(--bg,#fff);color:var(--navy,#2b2b6e);font:inherit;font-size:15px;" +
      "font-weight:700;cursor:pointer}" +
      ".cl-btn:hover{background:var(--soft,#f5f6f9)}" +
      ".cl-btn svg{width:18px;height:18px;flex:0 0 auto}" +
      ".cl-msg{font-size:13px;color:var(--muted,#6b6f76);text-align:center;min-height:1em}" +
      ".cl-url{width:100%;box-sizing:border-box;padding:8px 10px;font:inherit;font-size:13px;" +
      "border:1px solid var(--line,#e6e7ec);border-radius:8px;color:var(--ink,#1d1d24)}" +
      // display:flex above would otherwise beat the [hidden] attribute.
      ".cl-share[hidden],.cl-url[hidden]{display:none}";
    document.head.appendChild(css);

    bar = document.createElement("div");
    bar.className = "cl-share";
    bar.hidden = true;
    btn = document.createElement("button");
    btn.type = "button";
    btn.className = "cl-btn";
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
      'stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/>' +
      '<circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>' +
      '<line x1="8.6" y1="13.5" x2="15.4" y2="17.5"/><line x1="15.4" y1="6.5" x2="8.6" y2="10.5"/></svg>' +
      '<span>分享這個查詢結果</span>';
    btn.addEventListener("click", onShare);
    box = document.createElement("input");
    box.className = "cl-url";
    box.readOnly = true;
    box.hidden = true;
    box.setAttribute("aria-label", "查詢結果連結");
    msg = document.createElement("span");
    msg.className = "cl-msg";
    msg.setAttribute("aria-live", "polite");
    bar.appendChild(btn);
    bar.appendChild(box);
    bar.appendChild(msg);
    cfg.result.parentNode.insertBefore(bar, cfg.result.nextSibling);
  }

  function updateBar() {
    if (!bar) return;
    bar.hidden = !(shareUrl() && !cfg.result.hidden);
  }

  // Only the store page may tell us where we are embedded.
  window.addEventListener("message", function (e) {
    if (!embedded || e.source !== window.parent || !HOST_ORIGIN.test(e.origin)) return;
    var d = e.data;
    if (!d || d.type !== "carmallHost" || typeof d.url !== "string") return;
    try {
      var u = new URL(d.url);
      if (u.origin !== e.origin) return;
      host = u.origin + u.pathname;
    } catch (err) { return; }
    updateBar();
  });

  // A new link for the same finder (pasted into the store's address bar, or the bare
  // github.io page's) only changes this frame's #hash, so the page does not reload and
  // init() never runs again. Start over from the first select and restore the new car —
  // otherwise the address bar names one car while the cards still sell another.
  window.addEventListener("hashchange", function () {
    if (!cfg) return;
    try {
      restoring = true;
      var first = cfg.steps[0].el;
      if (first.value !== "") { first.value = ""; first.dispatchEvent(new Event("change")); }
    } finally {
      restoring = false;
    }
    restore();
    sync();
  });

  // Never let this file break a finder: init runs inside the finder's data-load promise,
  // and an exception there would show the finder's "載入失敗" screen.
  function init(c) {
    if (cfg || !c || !c.steps || !c.steps.length || !c.result) return;
    try {
      cfg = c;
      buildBar();
      cfg.steps.forEach(function (s) { s.el.addEventListener("change", sync); });
      restore();
      sync();
    } catch (e) {
      if (bar) bar.hidden = true;
    }
  }

  var queued = window.CarmallLinkQueue || [];
  window.CarmallLink = { init: init };
  window.CarmallLinkQueue = { push: init };
  for (var i = 0; i < queued.length; i++) init(queued[i]);
})();
