/* Brake-pad finder: page-specific wording only. The flow lives in ../assets/finder.js. */
window.FINDER = {
  part: function (p) { return (p.position || "") + "來令片"; },
  brandTag: "NISSIN",
  titleOne: 'NISSIN 煞車來令片　<span>點選前往購買</span>',
  titleMany: function () {
    return '前後輪使用不同來令片　<span>請依要更換的位置選購</span>';
  },
  // Quantity is never guessed: one set serves one caliper, and how many calipers a bike
  // has (single/dual disc, 4-pad calipers) is for the owner to check — same rule as the
  // plug finder's cylinder count.
  cardNote: function () { return "1 組 2 片，供單一卡鉗使用；雙碟或多片式卡鉗需要幾組，請依實車確認"; },
  footNote: '資料來自 NISSIN 商品頁的適用車款表。購買前請確認車型、年份與卡鉗規格是否相符，' +
    '不確定的話請洽客服。價格與庫存每日同步，實際成交以商品頁面為準。'
};
