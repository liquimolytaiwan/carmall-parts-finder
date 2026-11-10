/* Tyre finder: brand → model → the bike's stock front/rear size → every tyre sold in it.
 *
 * Tyres are sold by size, so this page does not use ../assets/finder.js (one product per
 * card, joined on SKU). Everything a card shows is decided at build time by
 * tools/build_tires.py — which tyres fit which wheel, whether the front+rear set fits,
 * which single tyre has a 合作車行安裝 twin — so the page only renders tires/data.json
 * (docs/data-contract.md).
 *
 * CarMall's product page ignores ?variant= (checked 2026-11-10: it always opens on the
 * first size and shows that size's price), so every card tells the customer which option
 * to pick on the page instead of implying it is already selected.
 */
(function () {
  "use strict";
  var DATA = null, OFFERS = {};
  var elBrand  = document.getElementById("sel-brand");
  var elModel  = document.getElementById("sel-model");
  var elResult = document.getElementById("result");

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
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n) {
    if (n == null) return "-";
    return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  // ---- load data ----
  fetch("data.json", { cache: "no-cache" })
    .then(function (r) { if (!r.ok) throw new Error("data load " + r.status); return r.json(); })
    .then(function (d) {
      DATA = d;
      d.offers.forEach(function (o) { OFFERS[o.variant_id] = o; });
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
    hideResult();
    clearSelect(elModel, "請選擇車款");
    var b = currentBrand();
    if (!b) { elModel.disabled = true; postHeight(); return; }
    b.models.forEach(function (m, i) { elModel.appendChild(opt(String(i), m.name)); });
    elModel.disabled = false;
    postHeight();
  });

  elModel.addEventListener("change", function () {
    var m = currentModel();
    if (!m) { hideResult(); postHeight(); return; }
    render(currentBrand(), m);
  });

  function hideResult() { elResult.hidden = true; elResult.innerHTML = ""; }
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
  function sizesText(list) {
    return list.length ? list.map(function (s) { return s.size; }).join(" 或 ") : "未標示";
  }

  function render(b, m) {
    var head = '<div class="rc-top"><div class="rc-veh">' + esc(b.name + " " + m.name) +
      '<small>原廠輪胎尺寸　前輪 ' + esc(sizesText(m.front)) + '｜後輪 ' + esc(sizesText(m.rear)) +
      '</small></div></div>';
    var body = '<div class="note note-warn">' + iconInfo() + '<span><b>請先核對輪胎側面的尺寸。</b>' +
      '這裡是常見車款的原廠尺寸，同一車款不同年份、版本，或輪圈改過，尺寸可能不同；' +
      '請以你車上輪胎側面印的尺寸（例如 ' + esc((m.front[0] || m.rear[0] || { size: "110/70-12" }).size) +
      '）為準。</span></div>';

    [["front", "前輪"], ["rear", "後輪"]].forEach(function (w) {
      var list = m[w[0]];
      if (list.length > 1) {
        body += '<div class="note note-warn">' + iconInfo() + '<span>這台車的' + w[1] +
          '在不同商品頁寫了不同尺寸（' + esc(sizesText(list)) + '），<b>請以輪胎側面的尺寸為準</b>選購。</span></div>';
      }
      list.forEach(function (s) {
        body += '<div class="opt-title tire-pos">' + w[1] + '　' + esc(s.size) +
          '　<span>單條販售</span></div>';
        var cards = s.tyres.map(function (v) { return tyreCard(OFFERS[v]); }).join("");
        body += cards || '<div class="note">' + iconInfo() + '<span>目前沒有單條販售這個尺寸，請洽客服。</span></div>';
      });
      if (!list.length) {
        body += '<div class="opt-title tire-pos">' + w[1] + '</div><div class="note">' + iconInfo() +
          '<span>商品頁沒有列出這台車的' + w[1] + '尺寸，請以輪胎側面的尺寸洽客服。</span></div>';
      }
    });

    if (m.sets.length) {
      body += '<div class="opt-title tire-pos">前後輪一起換　<span>這台車前後輪尺寸都符合</span></div>' +
        m.sets.map(function (v) { return setCard(OFFERS[v]); }).join("");
    }

    body += '<div class="note">' + iconInfo() + '<span>資料來自 ARISUN 商品頁的「常見車款尺寸對照」。' +
      '購買前請依實車確認輪胎尺寸、輪圈及載重／速度等級，不確定的話請洽客服。' +
      '價格與庫存每日同步，實際成交以商品頁面為準。</span></div>';
    elResult.innerHTML = '<div class="rc">' + head + '<div class="rc-body">' + body + '</div></div>';
    elResult.hidden = false;
    postHeight();
  }

  function stockTag(o) {
    if (!o.available) return '<span class="tag tag-low">暫時缺貨</span>';
    if (o.qty != null && o.qty > 0 && o.qty <= 3) return '<span class="tag tag-low">僅剩 ' + esc(o.qty) + ' 件</span>';
    return "";
  }
  function choose(o) {
    if (!o.choose || !o.choose.length) return "";
    return '<div class="opt-sub">到商品頁請選 ' +
      o.choose.map(function (c) { return "「" + esc(c) + "」"; }).join("") + '</div>';
  }
  function priceBlock(o) {
    return '<div class="opt-right"><div class="opt-price">' +
      (o.compare_at ? '<span class="unitp was">原價 $' + fmt(o.compare_at) + '</span>' : "") +
      '<span class="now">$' + fmt(o.price) + '</span></div>' + cart() + '</div>';
  }
  function caveat(o) {
    return o.caveat ? '<div class="opt-note">' + esc(o.caveat) + '</div>' : "";
  }

  function tyreCard(o) {
    if (!o) return "";
    var wheel = o.position ? o.position + "專用" : "";
    var main = '<a class="opt" href="' + esc(o.url) + '" target="_blank" rel="noopener">' +
      '<div class="opt-main"><div class="opt-name">ARISUN ' + esc(o.line) +
      (o.type ? '<span class="tag tag-brand">' + esc(o.type) + '</span>' : "") + stockTag(o) + '</div>' +
      '<div class="opt-sub">尺寸 ' + esc(o.size) + (wheel ? '　' + esc(wheel) : "") + '</div>' +
      choose(o) + caveat(o) + '</div>' + priceBlock(o) + '</a>';
    var twin = o.install != null ? OFFERS[o.install] : null;
    if (!twin) return '<div class="tc">' + main + '</div>';
    // A sibling link, not nested inside the card's <a>.
    var inst = '<a class="opt-install" href="' + esc(twin.url) + '" target="_blank" rel="noopener">' +
      '<span class="oi-main"><b>寄到合作車行安裝</b>' + stockTag(twin) +
      '<small>下單前請先在商品頁確認你所在的縣市有合作車行；下單後 CarMall 會與你聯繫，確認安裝日期與時段。' +
      (twin.choose && twin.choose.length ? '到商品頁請選 ' +
        twin.choose.map(function (c) { return "「" + esc(c) + "」"; }).join("") + '。' : "") +
      '</small></span><span class="oi-price">$' + fmt(twin.price) + '</span></a>';
    return '<div class="tc has-install">' + main + inst + '</div>';
  }

  function setCard(o) {
    if (!o) return "";
    return '<div class="tc"><a class="opt" href="' + esc(o.url) + '" target="_blank" rel="noopener">' +
      '<div class="opt-main"><div class="opt-name">ARISUN ' + esc((o.line || "").replace("+", "＋")) +
      ' 前後輪套組' + (o.type ? '<span class="tag tag-brand">' + esc(o.type) + '</span>' : "") + stockTag(o) + '</div>' +
      '<div class="opt-sub">前輪 ' + esc(o.front) + '＋後輪 ' + esc(o.rear) + '，共 2 條</div>' +
      caveat(o) + '</div>' + priceBlock(o) + '</a></div>';
  }

  // ---- icons ----
  function cart() { return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.7 13.4a2 2 0 0 0 2 1.6h9.7a2 2 0 0 0 2-1.6L23 6H6"/></svg>'; }
  function iconAlertBig() { return '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="#b9892b" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12" y2="17"/></svg>'; }
  function iconInfo() { return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="8"/></svg>'; }

  // ---- iframe auto-height (same contract as ../assets/finder.js) ----
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
