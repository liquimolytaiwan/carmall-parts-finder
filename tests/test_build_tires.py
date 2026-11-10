"""Run: python3 tests/test_build_tires.py  (stdlib only, no network).

Fixtures copy the real ARISUN page shapes (2026-11-10): the stray space in 「輪胎尺寸 ／輪位」,
rowspan size cells, 參考車款 vs 適用車款, 「120/70-13 RS01・前輪」, the 「—｜依實車規格確認」
rows, and the set's one-model-per-row table.
"""
import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import build_tires  # noqa: E402
import carmall  # noqa: E402

SK1_TABLE = """<table><thead><tr><th>輪胎尺寸<br>／輪位</th><th>車廠品牌</th><th>適用車款</th></tr></thead><tbody>
<tr><td rowspan="2"><strong>110/70-12</strong><br><span>前輪</span></td><td>KYMCO</td><td>RTS125/135/165、RCS moto</td></tr>
<tr><td>SYM</td><td>Fiddle DX</td></tr>
<tr><td rowspan="1"><strong>120/70-12</strong><br><span>前輪</span></td><td>YAMAHA</td><td>BWS</td></tr>
<tr><td rowspan="2"><strong>120/70-12</strong><br><span>後輪</span></td><td>KYMCO</td><td>RTS125/135/165、RCS moto</td></tr>
<tr><td>SYM</td><td>Fiddle DX</td></tr>
<tr><td><strong>130/70-12</strong><br><span>後輪</span></td><td>YAMAHA</td><td>BWS</td></tr>
<tr><td rowspan="2"><strong>110/70-13</strong><br><span>前輪</span></td><td>KYMCO</td><td>RomaGT</td></tr>
<tr><td>YAMAHA</td><td>NMAX</td></tr>
<tr><td><strong>120/70-13</strong><br><span>前輪</span></td><td>YAMAHA</td><td>FORCE、AUGUR</td></tr>
<tr><td rowspan="2"><strong>130/70-13</strong><br><span>後輪</span></td><td>KYMCO</td><td>RomaGT</td></tr>
<tr><td>YAMAHA</td><td>FORCE、AUGUR、NMAX</td></tr>
</tbody></table><p>輪位依表列車款標示，本商品以單條販售。</p>"""

SK1_SIZES = ["110/70-12", "120/70-12", "後輪 130/70-12", "110/70-13", "120/70-13", "後輪 130/70-13"]

RS_BODY = """<table><thead><tr><th>型號</th><th>輪胎尺寸</th><th>輪位</th><th>胎款類型</th></tr></thead><tbody>
<tr><td>RS01</td><td>100/90-12</td><td>前輪</td><td>全熱熔</td></tr>
<tr><td>RS01</td><td>120/70-13</td><td>前輪</td><td>半熱熔</td></tr>
<tr><td>RS02</td><td>120/80-12</td><td>後輪</td><td>全熱熔</td></tr>
<tr><td>RS02</td><td>130/70-13</td><td>後輪</td><td>半熱熔</td></tr></tbody></table>
<table><thead><tr><th>輪胎尺寸／輪位</th><th>車廠品牌</th><th>參考車款</th></tr></thead><tbody>
<tr><td>100/90-12<br>RS01・前輪</td><td>—</td><td>依實車規格確認</td></tr>
<tr><td>120/70-13<br>RS01・前輪</td><td>YAMAHA</td><td>FORCE、AUGUR</td></tr>
<tr><td>120/80-12<br>RS02・後輪</td><td>—</td><td>依實車規格確認</td></tr>
<tr><td rowspan="2">130/70-13<br>RS02・後輪</td><td>KYMCO</td><td>RomaGT</td></tr>
<tr><td>YAMAHA</td><td>FORCE、AUGUR、NMAX</td></tr></tbody></table>
<p>本系列以賽道競技與賽道日使用為定位，購買前請確認使用需求及道路使用法規。</p>"""
RS_VARIANTS = [("RS01前輪", "100/90-12"), ("RS01前輪", "120/70-13"), ("RS02後輪", "120/80-12"), ("RS02後輪", "130/70-13")]

SET_BODY = """<table><thead><tr><th>型號</th><th>輪位</th><th>輪胎尺寸</th></tr></thead><tbody>
<tr><td>RS01</td><td>前輪</td><td>120/70-13</td></tr><tr><td>RS02</td><td>後輪</td><td>130/70-13</td></tr></tbody></table>
<table><thead><tr><th>車廠品牌</th><th>適用車款</th></tr></thead><tbody>
<tr><td rowspan="2"><strong>YAMAHA</strong></td><td>FORCE</td></tr><tr><td>AUGUR</td></tr>
<tr><td rowspan="2"><strong>AEON</strong></td><td>STR 250</td></tr><tr><td>STR 300</td></tr></tbody></table>"""

SK1, INSTALL, RS, SET = 72972502, 73490813, 72973329, 73109778


def variants(pid, labels, base_price=1900.0):
    out = []
    for i, lab in enumerate(labels):
        opts = list(lab) if isinstance(lab, tuple) else [lab]
        v = {"id": pid * 100 + i, "title": " / ".join(opts), "sku": None, "price": base_price + 100 * i,
             "compare_at_price": base_price + 100 * i, "available": True, "inventory_quantity": 5,
             "option1": opts[0], "option2": opts[1] if len(opts) > 1 else None, "option3": None}
        out.append(v)
    return out


def product(pid, title, body, vs):
    return {"id": pid, "handle": f"h{pid}", "url": f"/products/h{pid}", "title": title,
            "body_html": body, "available": True, "variants": vs}


def shop():
    return [
        product(SK1, "ARISUN SK1｜全天候半熱熔胎", SK1_TABLE, variants(SK1, SK1_SIZES)),
        product(INSTALL, "【合作車行安裝】ARISUN SK1 全天候半熱熔胎", "<div id='x'>車行清單</div>" + SK1_TABLE,
                variants(INSTALL, SK1_SIZES)),
        product(RS, "ARISUN RS01／RS02｜競賽級熱熔胎", RS_BODY, variants(RS, RS_VARIANTS, 2100.0)),
        product(SET, "【前後輪套組】ARISUN RS01／RS02 競賽級半熱熔胎｜13吋", SET_BODY,
                [{"id": SET * 100, "title": "", "sku": "ARISUN RS01+RS02", "price": 3980.0,
                  "compare_at_price": 4300.0, "available": True, "inventory_quantity": 5,
                  "option1": None, "option2": None, "option3": None}]),
    ]


def fetcher(products, listed=None, missing=()):
    """listed: ids the category shows (default: all). missing: listed but their page 404s."""
    by_url = {carmall.SITE + p["url"] + ".json": p for p in products}
    ids = listed if listed is not None else [p["id"] for p in products]

    def fetch(url):
        if "/categories/brandlist/arisun.json" in url:
            return json.dumps([{"id": i, "url": f"/products/h{i}", "title": f"p{i}"} for i in ids]
                              if url.endswith("page=1") else [])
        p = by_url.get(url)
        if p is None or p["id"] in missing:
            raise carmall.NotFound("404 " + url)
        return json.dumps(p)
    return fetch


def models(data):
    return {(b["name"], m["name"]): m for b in data["brands"] for m in b["models"]}


def offers(data):
    return {o["variant_id"]: o for o in data["offers"]}


def lines_at(data, bike, wheel):
    o = offers(data)
    return [(o[v]["line"], s["size"]) for s in models(data)[bike][wheel] for v in s["tyres"]]


class TiresTest(unittest.TestCase):
    def setUp(self):
        self.data, self.code, self.report = build_tires.build(fetch=fetcher(shop()))

    def test_builds_clean(self):
        self.assertEqual(self.code, 0, self.report)
        self.assertEqual(self.data["stats"]["products"], 4)

    def test_rowspan_and_models_split(self):
        m = models(self.data)
        self.assertIn(("KYMCO", "RTS125/135/165"), m)       # "/" inside a model is not a separator
        self.assertIn(("SYM", "Fiddle DX"), m)              # the rowspan size reached the 2nd brand row
        self.assertEqual([s["size"] for s in m[("SYM", "Fiddle DX")]["front"]], ["110/70-12"])
        self.assertEqual([s["size"] for s in m[("SYM", "Fiddle DX")]["rear"]], ["120/70-12"])

    def test_wheel_labelled_variant_only_on_that_wheel(self):
        # 120/70-12 is unlabelled: front on YAMAHA BWS, rear on KYMCO — both get the tyre.
        self.assertEqual(lines_at(self.data, ("YAMAHA", "BWS"), "front"), [("SK1", "120/70-12")])
        self.assertEqual(lines_at(self.data, ("KYMCO", "RCS moto"), "rear"), [("SK1", "120/70-12")])
        # RS01 is front-only and RS02 rear-only even when a size would fit the other wheel.
        o = offers(self.data)
        rs02 = [v for v in o.values() if v.get("line") == "RS02" and v["size"] == "130/70-13"][0]
        self.assertEqual(rs02["position"], "後輪")
        for bike in models(self.data).values():
            for s in bike["front"]:
                self.assertNotIn(rs02["variant_id"], s["tyres"])

    def test_tyres_by_size_road_first(self):
        self.assertEqual(lines_at(self.data, ("YAMAHA", "NMAX"), "rear"),
                         [("SK1", "130/70-13"), ("RS02", "130/70-13")])
        self.assertEqual(lines_at(self.data, ("YAMAHA", "FORCE"), "front"),
                         [("SK1", "120/70-13"), ("RS01", "120/70-13")])

    def test_set_only_when_both_sizes_match(self):
        m = models(self.data)
        for bike in [("YAMAHA", "FORCE"), ("YAMAHA", "AUGUR"), ("AEON", "STR 250"), ("AEON", "STR 300")]:
            self.assertEqual(len(m[bike]["sets"]), 1, bike)
        for bike in [("YAMAHA", "NMAX"), ("KYMCO", "RomaGT")]:      # rear matches, front is 110/70-13
            self.assertEqual(m[bike]["sets"], [], bike)

    def test_set_only_bike_gets_set_sizes(self):
        aeon = models(self.data)[("AEON", "STR 250")]
        self.assertEqual([s["size"] for s in aeon["front"]], ["120/70-13"])
        self.assertEqual([s["size"] for s in aeon["rear"]], ["130/70-13"])
        self.assertEqual(aeon["front"][0]["listed_by"], [SET])

    def test_install_twin_and_offer_fields(self):
        o = offers(self.data)
        sk1 = [v for v in o.values() if v["kind"] == "single" and v["line"] == "SK1"]
        self.assertTrue(sk1 and all(o[v["install"]]["kind"] == "install" for v in sk1))
        twin = o[sk1[0]["install"]]
        self.assertEqual((twin["size"], twin["position"]), (sk1[0]["size"], sk1[0]["position"]))
        rs01 = [v for v in o.values() if v.get("line") == "RS01" and v["size"] == "120/70-13"][0]
        self.assertEqual(rs01["type"], "半熱熔胎")
        self.assertIn("賽道", rs01["caveat"])
        self.assertEqual(rs01["choose"], ["RS01前輪", "120/70-13"])
        self.assertNotIn("install", rs01)
        self.assertNotIn("sku", rs01)                          # no empty 料號 in the data
        self.assertEqual(sk1[0]["type"], "全天候半熱熔胎")
        self.assertIn("?variant=", sk1[0]["url"])
        st = [v for v in o.values() if v["kind"] == "set"][0]
        self.assertEqual((st["front"], st["rear"], st["compare_at"]), ("120/70-13", "130/70-13", 4300.0))

    def test_table_size_without_variant_is_a_problem(self):
        ps = shop()
        ps[0]["variants"] = [v for v in ps[0]["variants"] if v["option1"] != "110/70-13"]
        data, code, report = build_tires.build(fetch=fetcher(ps))
        self.assertEqual(code, 3)
        self.assertTrue(any(l.startswith("PROBLEM") and "110/70-13 前輪" in l for l in report))

    def test_broken_table_carries_previous_rows(self):
        ps = shop()
        ps[0]["body_html"] = ps[0]["body_html"].replace("<strong>110/70-13</strong>", "110-70-13")
        data, code, report = build_tires.build(fetch=fetcher(ps), previous=self.data)
        self.assertEqual(code, 3)
        self.assertTrue(any(l.startswith("CARRIED") for l in report))
        self.assertIn(SK1, models(data)[("YAMAHA", "NMAX")]["front"][0]["listed_by"])

    def test_set_taken_down_drops_set_and_its_only_bikes(self):
        for kw in ({"listed": [SK1, INSTALL, RS]}, {"missing": (SET,)}):
            data, code, report = build_tires.build(fetch=fetcher(shop(), **kw), previous=self.data)
            self.assertEqual(code, 0, (kw, report))
            self.assertFalse([o for o in data["offers"] if o["kind"] == "set"], kw)
            m = models(data)
            self.assertNotIn(("AEON", "STR 250"), m)
            self.assertEqual(m[("YAMAHA", "FORCE")]["sets"], [])
            self.assertIn(("YAMAHA", "FORCE"), m)                 # still listed by SK1 / RS
            self.assertTrue(any("AEON STR 250" in l and "少了" in l for l in report), report)

    def test_empty_or_mostly_missing_category_refuses(self):
        for listed in ([], [SK1]):                  # empty response; 3 of 4 products gone
            data, code, report = build_tires.build(fetch=fetcher(shop(), listed=listed), previous=self.data)
            self.assertIsNone(data, listed)
            self.assertEqual(code, 1, listed)
            self.assertTrue(any(l.startswith("REFUSE") for l in report), report)
        # two gone (set + install) is still a legitimate takedown
        data, code, report = build_tires.build(fetch=fetcher(shop(), listed=[SK1, RS]), previous=self.data)
        self.assertEqual(code, 0, report)

    def test_unreadable_variant_keeps_previous_size(self):
        ps = shop()
        v = [x for x in ps[0]["variants"] if x["option1"] == "110/70-13"][0]
        prev = copy.deepcopy(self.data)
        offers(prev)[v["id"]]["compare_at"] = 9999.0          # a discount the store has since dropped
        v["option1"] = v["title"] = "110/70R13"
        v["price"] = 2500.0
        data, code, report = build_tires.build(fetch=fetcher(ps), previous=prev)
        self.assertEqual(code, 3)
        kept = offers(data)[v["id"]]
        self.assertEqual((kept["size"], kept["price"]), ("110/70-13", 2500.0))   # old size, fresh price
        self.assertNotIn("compare_at", kept)                                    # stale fields not carried
        self.assertEqual(lines_at(data, ("YAMAHA", "NMAX"), "front"), [("SK1", "110/70-13")])

    def test_unknown_bike_table_header_is_a_problem(self):
        ps = shop()
        ps[0]["body_html"] += SK1_TABLE.replace("適用車款", "車款").replace("NMAX", "XMAX")
        data, code, report = build_tires.build(fetch=fetcher(ps), previous=self.data)
        self.assertEqual(code, 3)
        self.assertTrue(any(l.startswith("PROBLEM") and "欄位看不懂" in l for l in report), report)

    def test_case_variants_join_and_rows_stay_consistent(self):
        ps = shop()
        ps[2]["body_html"] = ps[2]["body_html"].replace("FORCE、AUGUR、NMAX", "FORCE、AUGUR、Nmax")
        data, code, report = build_tires.build(fetch=fetcher(ps))
        self.assertNotIn(("YAMAHA", "Nmax"), models(data))
        self.assertIn(RS, models(data)[("YAMAHA", "NMAX")]["rear"][0]["listed_by"])
        listed = sum(len(s["listed_by"]) for m in models(data).values() for w in ("front", "rear") for s in m[w])
        self.assertEqual(listed, data["stats"]["rows"])

    def test_shrink_guard_still_refuses_for_listed_products(self):
        big = copy.deepcopy(self.data)
        big["stats"]["rows"] = self.data["stats"]["rows"] * 3
        data, code, report = build_tires.build(fetch=fetcher(shop()), previous=big)
        self.assertIsNone(data)
        self.assertEqual(code, 1)

    def test_category_fetch_failure_raises(self):
        def fetch(url):
            raise carmall.FetchError("timeout")
        with self.assertRaises(carmall.FetchError):
            build_tires.build(fetch=fetch)


if __name__ == "__main__":
    unittest.main()
