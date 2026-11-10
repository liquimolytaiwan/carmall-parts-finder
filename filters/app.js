/* Air-filter finder: page-specific wording only. The flow lives in ../assets/finder.js. */
window.FINDER = {
  part: function (p) { return p.position; },
  brandTag: "Champion",
  titleOne: 'Champion 空氣芯　<span>點選前往購買</span>',
  // Several positions on one bike are different parts, not alternatives — say so, or a
  // TMAX owner reads three cards as "pick one".
  titleMany: function (n) {
    return '此車款有 ' + n + ' 個位置的空氣芯　<span>位置不同、各自更換，請依要更換的位置選購</span>';
  },
  footNote: '資料來自 Champion 商品頁的車種對照表。購買前請確認車型、年份及原廠料號是否相符，' +
    '實際適用性以車輛規格為準。價格與庫存每日同步，實際成交以商品頁面為準。'
};
