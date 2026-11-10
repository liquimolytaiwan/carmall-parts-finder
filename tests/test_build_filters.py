"""Run: python3 tests/test_build_filters.py  (stdlib only, no network)."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import build_filters  # noqa: E402
import carmall  # noqa: E402
import tables  # noqa: E402

# The real shape of a Champion table: one brand cell spanning several model rows.
SPAN_TABLE = """
<p>● 適用車種對照｜ CP-CAF0707</p>
<table><tbody>
<tr><td>品牌</td><td>車款</td><td>年份</td></tr>
<tr><td colspan="1" rowspan="3">YAMAHA</td><td>XTZ 700 TENERE ABS</td><td>2019-2023</td></tr>
<tr><td>XTZ 700 TENERE EXPLORE ABS</td><td>2023-</td></tr>
<tr><td>YZF-R7</td><td>2021–2024</td></tr>
</tbody></table>
<p>對應原廠 OE 料號： 1WS-14451-00 ※ 購買前請確認車型</p>
"""


def product(pid, title, body, sku, available=True, qty=5):
    return {
        "id": pid, "handle": f"h{pid}", "url": f"/products/h{pid}", "title": title,
        "body_html": body, "available": available,
        "variants": [{"id": pid * 10, "sku": sku, "price": 1300.0, "available": available,
                      "inventory_quantity": qty}],
    }


def fake_fetch(products):
    by_url = {carmall.SITE + p["url"] + ".json": p for p in products}
    summaries = [{"id": p["id"], "url": p["url"], "title": p["title"]} for p in products]

    def fetch(url):
        if "/categories/brandlist/champion.json" in url:
            page = int(url.rsplit("page=", 1)[1])
            return json.dumps(summaries if page == 1 else [])
        if url in by_url:
            return json.dumps(by_url[url])
        raise carmall.FetchError("404 " + url)
    return fetch


class TablesTest(unittest.TestCase):
    def test_rowspan_keeps_columns_aligned(self):
        t = tables.tables(SPAN_TABLE)[0]
        self.assertEqual(t[0], ["品牌", "車款", "年份"])
        self.assertEqual(t[2], ["YAMAHA", "XTZ 700 TENERE EXPLORE ABS", "2023-"])
        self.assertEqual(t[3], ["YAMAHA", "YZF-R7", "2021–2024"])

    def test_colspan_repeats_cell(self):
        t = tables.tables("<table><tr><td colspan='2'>A</td><td>B</td></tr></table>")[0]
        self.assertEqual(t[0], ["A", "A", "B"])


class BuildTest(unittest.TestCase):
    def test_builds_brands_positions_and_oe(self):
        ps = [
            product(1, "【Champion台灣代理】Yamaha MT-07 14-空氣芯 Air Filter", SPAN_TABLE, "CP-CAF0707"),
            product(2, "【Champion台灣代理】Yamaha TMAX530 12-16左傳動空氣芯 Air Filter",
                    "<table><tr><td>品牌</td><td>車款</td><td>年份</td></tr>"
                    "<tr><td>YAMAHA</td><td>YZF-R7</td><td>2021-2024</td></tr></table>", "CP-CAF3509"),
        ]
        data, code, report = build_filters.build(fetch=fake_fetch(ps))
        self.assertEqual(code, 0, report)
        yamaha = data["brands"][0]
        self.assertEqual(yamaha["name"], "YAMAHA")
        r7 = [m for m in yamaha["models"] if m["name"] == "YZF-R7"][0]
        # Both parts listed for the bike, main filter first, years normalised.
        self.assertEqual([f["sku"] for f in r7["fits"]], ["CP-CAF0707", "CP-CAF3509"])
        self.assertEqual(r7["fits"][0]["years"], ["2021-2024"])
        prods = {p["sku"]: p for p in data["products"]}
        self.assertEqual(prods["CP-CAF0707"]["oe"], "1WS-14451-00")
        self.assertEqual(prods["CP-CAF3509"]["position"], "左傳動空氣芯")
        self.assertEqual(prods["CP-CAF0707"]["position"], "空氣芯")

    def test_one_broken_table_publishes_rest_and_flags(self):
        ps = [product(1, "A 空氣芯", SPAN_TABLE, "CP-1"),
              product(2, "B 空氣芯", "<table><tr><td>車種</td><td>年式</td></tr></table>", "CP-2")]
        data, code, report = build_filters.build(fetch=fake_fetch(ps))
        self.assertEqual(code, 3)
        self.assertEqual(data["stats"]["products"], 1)
        self.assertTrue(any(l.startswith("PROBLEM") and "B 空氣芯" in l for l in report))

    def test_broken_table_keeps_previous_vehicles_and_fresh_price(self):
        good = [product(1, "A 空氣芯", SPAN_TABLE, "CP-1"), product(2, "B 主空氣芯", SPAN_TABLE, "CP-2")]
        previous, _, _ = build_filters.build(fetch=fake_fetch(good))
        broken = product(2, "B 主空氣芯", "<table><tr><td>車種</td><td>年式</td></tr></table>", "CP-2",
                         available=False, qty=0)
        data, code, report = build_filters.build(fetch=fake_fetch([good[0], broken]), previous=previous)
        self.assertEqual(code, 3)
        self.assertEqual(data["stats"]["carried"], 1)
        r7 = [m for b in data["brands"] for m in b["models"] if m["name"] == "YZF-R7"][0]
        self.assertEqual(sorted(f["sku"] for f in r7["fits"]), ["CP-1", "CP-2"])
        cp2 = [p for p in data["products"] if p["sku"] == "CP-2"][0]
        self.assertFalse(cp2["available"])          # price/stock still refreshed
        self.assertEqual(cp2["position"], "主空氣芯")
        self.assertTrue(any(l.startswith("CARRIED") for l in report))

    def test_one_bad_row_keeps_whole_previous_table(self):
        good = [product(1, "A 空氣芯", SPAN_TABLE, "CP-1")]
        previous, _, _ = build_filters.build(fetch=fake_fetch(good))
        half = SPAN_TABLE.replace("<td>YZF-R7</td>", "<td></td>")      # model cell emptied
        data, code, report = build_filters.build(fetch=fake_fetch([product(1, "A 空氣芯", half, "CP-1")]),
                                                 previous=previous)
        self.assertEqual(code, 3)
        self.assertEqual(data["stats"]["rows"], previous["stats"]["rows"])
        self.assertIn("YZF-R7", [m["name"] for b in data["brands"] for m in b["models"]])

    def test_template_change_across_many_products_refuses(self):
        broken = "<table><tr><td>車種</td><td>年式</td></tr></table>"
        ps = [product(1, "ok 空氣芯", SPAN_TABLE, "CP-1")] + \
             [product(i, f"x{i} 空氣芯", broken, f"CP-{i}") for i in range(2, 7)]
        data, code, report = build_filters.build(fetch=fake_fetch(ps))
        self.assertIsNone(data)
        self.assertEqual(code, 1)

    def test_big_shrink_against_previous_refuses(self):
        ps = [product(1, "ok 空氣芯", SPAN_TABLE, "CP-1")]
        data, code, _ = build_filters.build(fetch=fake_fetch(ps), previous={"stats": {"rows": 200}})
        self.assertIsNone(data)
        self.assertEqual(code, 1)

    def test_fetch_failure_raises_so_nothing_is_written(self):
        ps = [product(1, "ok 空氣芯", SPAN_TABLE, "CP-1")]
        fetch = fake_fetch(ps)

        def flaky(url):
            if "/products/" in url:
                raise carmall.FetchError("timeout")
            return fetch(url)
        with self.assertRaises(carmall.FetchError):
            build_filters.build(fetch=flaky)

    def test_out_of_stock_and_copy_title_are_kept_and_noted(self):
        ps = [product(1, "Kawasaki ZX-10R 空氣芯 Air Filter-copy", SPAN_TABLE, "CP-1", available=False, qty=0)]
        data, code, report = build_filters.build(fetch=fake_fetch(ps))
        self.assertEqual(code, 0)
        self.assertFalse(data["products"][0]["available"])
        self.assertTrue(any("copy" in l for l in report))


if __name__ == "__main__":
    unittest.main(verbosity=1)
