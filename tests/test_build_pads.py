"""Run: python3 tests/test_build_pads.py  (stdlib only, no network)."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import build_pads  # noqa: E402
import carmall  # noqa: E402

TD = '<td style="padding:11px 10px;">'
MAIN = ("<table><thead><tr><th>車廠品牌</th><th>適用車款</th></tr></thead><tbody>"
        f"<tr>{TD}YAMAHA</td>{TD}TZR250(89'-90')、YZF-R6(99'-01')、YZF-R6(03'-10')、XJ6N(09'-11'*)</td></tr>"
        f"<tr>{TD}HONDA Rear</td>{TD}CB1300SF(98'-00')</td></tr>"
        "</tbody></table>")
NOTES = ("<h3>● 備註與說明</h3><p>年份後標示 * 的車款，以下車架號碼起改適用 A0400：</p>"
         "<p>▪️XJ6N：JYARJ19G000002620</p>")
REF = ("<table><thead><tr><th>車廠品牌</th><th>參考適用車款</th></tr></thead><tbody>"
       f"<tr>{TD}YAMAHA</td>{TD}CYGNUS X 125 勁戰七代(26'-)、BW'S R 125(15'-20')</td></tr></tbody></table>")


def product(pid, title, body, sku):
    return {"id": pid, "handle": f"h{pid}", "url": f"/products/h{pid}", "title": title, "body_html": body,
            "available": True, "variants": [{"id": pid, "sku": sku, "price": 1380.0, "available": True,
                                              "inventory_quantity": 3}]}


def fetcher(products):
    by_url = {carmall.SITE + p["url"] + ".json": p for p in products}

    def fetch(url):
        if "/categories/brandlist/nissin.json" in url:
            return json.dumps([{"id": p["id"], "url": p["url"]} for p in products] if url.endswith("page=1") else [])
        return json.dumps(by_url[url])
    return fetch


def models(data):
    return {(b["name"], m["name"]): m["fits"] for b in data["brands"] for m in b["models"]}


class PadsTest(unittest.TestCase):
    def test_years_star_side_and_reference(self):
        ps = [product(1, "NISSIN A0041 Premium 半金屬煞車來令片(後) Brake Pad", MAIN + NOTES + REF, "HA-A0041")]
        data, code, report = build_pads.build(fetch=fetcher(ps))
        self.assertEqual(code, 0, report)
        m = models(data)
        self.assertEqual(m[("YAMAHA", "TZR250")][0]["years"], ["1989-1990"])
        self.assertEqual(m[("YAMAHA", "YZF-R6")][0]["years"], ["1999-2001", "2003-2010"])
        self.assertIn("JYARJ19G000002620", m[("YAMAHA", "XJ6N")][0]["notes"][0])
        self.assertIn("A0400", m[("YAMAHA", "XJ6N")][0]["notes"][0])
        self.assertIn(("HONDA", "CB1300SF"), m)                       # "HONDA Rear" -> HONDA
        ref = m[("YAMAHA", "CYGNUS X 125 勁戰七代")][0]
        self.assertEqual(ref["years"], ["2026-"])
        self.assertTrue(any("原廠未標示" in n for n in ref["notes"]))
        self.assertIn(("YAMAHA", "BW'S R 125"), m)
        self.assertEqual(data["products"][0]["position"], "後輪")
        self.assertTrue(any("HONDA Rear" in l for l in report))

    def test_star_without_frame_note_still_warns_customer(self):
        ps = [product(1, "NISSIN A0041 來令片(後)", MAIN, "HA-A0041")]
        data, code, report = build_pads.build(fetch=fetcher(ps))
        self.assertIn("車架號碼", models(data)[("YAMAHA", "XJ6N")][0]["notes"][0])
        self.assertTrue(any("沒寫從哪個車架號碼" in l for l in report))

    def test_unreadable_item_is_a_problem(self):
        bad = MAIN.replace("TZR250(89'-90')", "TZR250 89-90")
        ps = [product(1, "NISSIN A0041 來令片(後)", bad, "HA-A0041")]
        data, code, report = build_pads.build(fetch=fetcher(ps))
        self.assertEqual(code, 3)
        self.assertTrue(any(l.startswith("PROBLEM") and "TZR250 89-90" in l for l in report))

    def test_title_without_side_drops_product(self):
        ps = [product(1, "NISSIN A0041 來令片", MAIN, "HA-A0041")]
        data, code, report = build_pads.build(fetch=fetcher(ps))
        self.assertEqual(data["stats"]["products"], 0)
        self.assertEqual(code, 3)


if __name__ == "__main__":
    unittest.main(verbosity=1)
