/* Shared brand → model → (year) → parts flow for the finders in this repo.
 *
 * A page sets window.FINDER before loading this file:
 *   {
 *     part(p)        -> card heading for a product, e.g. "左傳動空氣芯" / "前輪來令片"
 *     brandTag       -> small tag on every card, e.g. "Champion"
 *     titleOne       -> heading above the cards when the bike has one position
 *     titleMany(n)   -> heading when it has n positions (different parts, not alternatives)
 *     footNote       -> grey note at the end of every result (source + caveats)
 *     cardNote(p)    -> optional extra line on every card (e.g. how many per set)
 *   }
 * and the page's data.json follows docs/data-contract.md.
 */
(function () {
  "use strict";
  var C = window.FINDER;
  var DATA = null, PRODUCTS = {}, SEGMENTS = [];
  var elBrand  = document.getElementById("sel-brand");
  var elModel  = document.getElementById("sel-model");
  var elYear   = document.getElementById("sel-year");
  var fldYear  = document.getElementById("field-year");
  var elResult = document.getElementById("result");

  // The back link is only for visitors who came from the parts-finder hub (?from=hub).
  var elBack = document.getElementById("back-hub");
  if (elBack && /(?:^|[?&])from=hub(?:&|$)/.test(location.search)) elBack.hidden = false;

  function opt(value, label) {
    var o = document.createElement("option");
    o.value = value; o.textContent = label;
    return o;
  }
  function clearSelect(sel, placeholder) {
    sel.innerHTML = "";
    sel.appendChild(opt("", placeholder));
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[c];
    });
  }
  function fmt(n) {
    if (n == null) return "-";
    return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  // ---- years ----
  // Ranges come straight from the product tables: "2015-2018", "2018-" (open), "2019".
  function parseYears(y) {
    var m = /^(\d{4})?-(\d{4})?$/.exec(y || "");
    if (m && (m[1] || m[2])) return { a: m[1] ? +m[1] : null, b: m[2] ? +m[2] : null };
    if (/^\d{4}$/.test(y || "")) return { a: +y, b: +y };
    return null;
  }
  function yearsLabel(y) {
    var r = parseYears(y);
    if (!r) return y ? y : "未標示年份";
    if (r.a != null && r.b == null) return r.a + " 年起";
    if (r.a == null) return r.b + " 年以前";
    return r.a === r.b ? String(r.a) : r.a + "–" + r.b;
  }

  // Split a model's year span at every point where the set of fitting parts changes, so
  // the year question is only asked when the answer depends on it (TMAX 530: its 左傳動
  // filter changed in 2017). Returns [] when years can't be compared or when every year
  // gets the same parts — then each card shows its own year ranges instead.
  function segments(fits) {
    var ranges = [], open = false, hi = -Infinity, cuts = {};
    for (var i = 0; i < fits.length; i++) {
      for (var j = 0; j < fits[i].years.length; j++) {
        var r = parseYears(fits[i].years[j]);
        if (!r || r.a == null) return [];
        ranges.push({ fit: i, a: r.a, b: r.b });
        cuts[r.a] = 1;
        if (r.b == null) open = true; else { cuts[r.b + 1] = 1; hi = Math.max(hi, r.b); }
      }
    }
    var pts = Object.keys(cuts).map(Number).sort(function (x, y) { return x - y; });
    var segs = [];
    for (var k = 0; k < pts.length; k++) {
      var s = pts[k], e = k + 1 < pts.length ? pts[k + 1] - 1 : (open ? Infinity : hi);
      if (e < s) continue;
      var set = [];
      ranges.forEach(function (r) {
        if (r.a <= s && (r.b == null || r.b >= e) && set.indexOf(r.fit) < 0) set.push(r.fit);
      });
      if (!set.length) continue;
      set.sort(function (x, y) { return x - y; });
      var last = segs[segs.length - 1];
      if (last && last.e === s - 1 && last.set.join() === set.join()) last.e = e;
      else segs.push({ s: s, e: e, set: set });
    }
    // Same parts in every year range (YZF-R6 99-01, 03-10, 17-20 all take A0100): asking
    // the year would only change which gap years are hidden, not the answer.
    var distinct = {};
    segs.forEach(function (g) { distinct[g.set.join()] = 1; });
    return Object.keys(distinct).length > 1 ? segs : [];
  }
  function segLabel(g) {
    if (g.e === Infinity) return g.s + " 年起";
    return g.s === g.e ? String(g.s) : g.s + "–" + g.e;
  }

  // ---- load data ----
  fetch("data.json", { cache: "no-cache" })
    .then(function (r) { if (!r.ok) throw new Error("data load " + r.status); return r.json(); })
    .then(function (d) {
      DATA = d;
      d.products.forEach(function (p) { PRODUCTS[p.sku] = p; });
      clearSelect(elBrand, "請選擇廠牌");
      d.brands.forEach(function (b, i) { elBrand.appendChild(opt(String(i), b.name)); });
      postHeight();
    })
    .catch(function () {
      elResult.hidden = false;
      elResult.innerHTML = '<div class="rc"><div class="state">' + iconAlertBig() +
        '<h3>查詢系統載入失敗</h3><p>請稍後重新整理頁面，或直接洽詢客服</p></div></div>';
      postHeight();
    });

  // ---- cascade ----
  elBrand.addEventListener("change", function () {
    hideResult(); hideYear();
    clearSelect(elModel, "請選擇車款");
    var b = currentBrand();
    if (!b) { elModel.disabled = true; postHeight(); return; }
    b.models.forEach(function (m, i) { elModel.appendChild(opt(String(i), m.name)); });
    elModel.disabled = false;
    postHeight();
  });

  elModel.addEventListener("change", function () {
    hideResult(); hideYear();
    var m = currentModel();
    if (!m) { postHeight(); return; }
    SEGMENTS = segments(m.fits);
    if (!SEGMENTS.length) { render(m, m.fits, null); return; }
    SEGMENTS.forEach(function (g, i) { elYear.appendChild(opt(String(i), segLabel(g))); });
    fldYear.hidden = false;
    postHeight();
  });

  elYear.addEventListener("change", function () {
    var m = currentModel();
    if (!m || elYear.value === "") { hideResult(); postHeight(); return; }
    var g = SEGMENTS[parseInt(elYear.value, 10)];
    render(m, g.set.map(function (i) { return m.fits[i]; }), segLabel(g));
  });

  function hideResult() { elResult.hidden = true; elResult.innerHTML = ""; }
  function hideYear() { fldYear.hidden = true; clearSelect(elYear, "請選擇出廠年份"); SEGMENTS = []; }
  function currentBrand() {
    if (!DATA || elBrand.value === "") return null;
    return DATA.brands[parseInt(elBrand.value, 10)];
  }
  function currentModel() {
    var b = currentBrand();
    if (!b || elModel.value === "") return null;
    return b.models[parseInt(elModel.value, 10)];
  }

  // ---- render ----
  function render(m, fits, yearPicked) {
    var b = currentBrand();
    var head = '<div class="rc-top"><div class="rc-veh">' + esc(b.name + " " + m.name) +
      (yearPicked ? '<small>出廠年份 ' + esc(yearPicked) + '</small>' : "") + '</div></div>';
    var positions = [], perPos = {};
    fits.forEach(function (f) {
      var p = PRODUCTS[f.sku];
      if (!p) return;
      if (positions.indexOf(p.position) < 0) positions.push(p.position);
      perPos[p.position] = (perPos[p.position] || 0) + 1;
    });
    // Two different part numbers for the same position and years means the product
    // tables disagree. Don't pick one — show both with their years and say so.
    var clash = positions.some(function (k) { return perPos[k] > 1; });
    var title = positions.length > 1 ? C.titleMany(positions.length) : C.titleOne;
    var cards = fits.map(function (f) { return card(PRODUCTS[f.sku], f, !yearPicked || clash); }).join("");
    var warn = clash ? '<div class="note note-warn">' + iconInfo() +
      '<span>同一個位置對到不同料號，<b>請以車上零件的原廠料號核對</b>後再選購，' +
      '不確定的話請洽客服。</span></div>' : "";
    elResult.innerHTML = '<div class="rc">' + head + '<div class="rc-body">' +
      '<div class="opt-title">' + title + '</div>' + cards + warn +
      '<div class="note">' + iconInfo() + '<span>' + C.footNote + '</span></div></div></div>';
    elResult.hidden = false;
    postHeight();
  }

  function card(p, f, showYears) {
    if (!p) return "";
    var bits = ['料號 ' + esc(p.sku)];
    if (p.oe) bits.push('原廠料號 ' + esc(p.oe));
    if (showYears) bits.push('適用 ' + f.years.map(yearsLabel).map(esc).join("、"));
    var stock = !p.available
      ? '<span class="tag tag-low">暫時缺貨</span>'
      : (p.qty != null && p.qty > 0 && p.qty <= 3 ? '<span class="tag tag-low">僅剩 ' + p.qty + ' 件</span>' : "");
    var notes = (f.notes || []).map(function (n) { return '<div class="opt-note">' + esc(n) + '</div>'; }).join("");
    var extra = C.cardNote ? C.cardNote(p) : "";
    return '<a class="opt" href="' + esc(p.url) + '" target="_blank" rel="noopener">' +
      '<div class="opt-main"><div class="opt-name">' + esc(C.part(p)) +
      '<span class="tag tag-brand">' + esc(C.brandTag) + '</span>' + stock + '</div>' +
      '<div class="opt-sub">' + bits.join("　") + '</div>' +
      (extra ? '<div class="opt-sub">' + esc(extra) + '</div>' : "") + notes + '</div>' +
      '<div class="opt-right"><div class="opt-price"><span class="now">$' + fmt(p.price) +
      '</span></div>' + cart() + '</div></a>';
  }

  // ---- icons ----
  function cart() { return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.7 13.4a2 2 0 0 0 2 1.6h9.7a2 2 0 0 0 2-1.6L23 6H6"/></svg>'; }
  function iconAlertBig() { return '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="#b9892b" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12" y2="17"/></svg>'; }
  function iconInfo() { return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="8"/></svg>'; }

  // ---- iframe auto-height ----
  // Measure the content element, not documentElement.scrollHeight (clamped to the viewport
  // inside an iframe, so it only grows). carmallFinderHeight is the shared name the hub's
  // embed snippet listens for.
  var elRoot = document.getElementById("fd");
  function postHeight() {
    try {
      var h = Math.ceil(elRoot.getBoundingClientRect().height);
      if (h > 0) parent.postMessage({ type: "carmallFinderHeight", height: h }, "*");
    } catch (e) {}
  }
  window.addEventListener("load", postHeight);
  window.addEventListener("resize", postHeight);
  if (window.ResizeObserver) { new ResizeObserver(postHeight).observe(elRoot); }
})();
