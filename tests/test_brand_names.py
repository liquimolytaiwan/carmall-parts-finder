"""Run: python3 tests/test_brand_names.py  (stdlib only, no network)."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import brand_names  # noqa: E402

NGK = {"brands": [
    {"en": "YAMAHA", "tw": "山葉"}, {"en": "KYMCO", "tw": "光陽"}, {"en": "KTM", "tw": ""},
    {"en": "HARLEY-DAVIDSON", "tw": "哈雷"}, {"en": "AEON", "tw": "宏佳騰動力"},
]}


def fetch_ok(url):
    assert url == brand_names.NGK_DATA
    return json.dumps(NGK)


def fetch_down(url):
    raise brand_names.carmall.FetchError("timed out")


def data(*names):
    return {"generated": "x", "brands": [{"name": n, "models": [{"name": "M"}]} for n in names]}


class BrandNames(unittest.TestCase):
    def test_plug_finder_names_and_name_kept_first(self):
        d = data("YAMAHA", "KYMCO")
        report = brand_names.apply(d, None, fetch=fetch_ok)
        self.assertEqual([(b["name"], b["tw"]) for b in d["brands"]], [("YAMAHA", "山葉"), ("KYMCO", "光陽")])
        self.assertEqual(list(d["brands"][0].keys()), ["name", "tw", "models"])
        self.assertEqual(report, [])

    def test_english_only_brand_stays_english(self):
        d = data("KTM")
        brand_names.apply(d, None, fetch=fetch_ok)
        self.assertEqual(d["brands"][0]["tw"], "")

    def test_spelling_differences_still_match(self):
        d = data("HARLEY DAVIDSON")
        brand_names.apply(d, None, fetch=fetch_ok)
        self.assertEqual(d["brands"][0]["tw"], "哈雷")

    def test_plug_finder_wins_over_extra(self):
        d = data("AEON")
        brand_names.apply(d, None, fetch=fetch_ok)
        self.assertEqual(d["brands"][0]["tw"], "宏佳騰動力")

    def test_extra_covers_brands_the_plug_finder_lacks(self):
        d = data("GOGORO", "BUELL")
        report = brand_names.apply(d, None, fetch=fetch_ok)
        self.assertEqual([b["tw"] for b in d["brands"]], ["", ""])
        self.assertEqual(report, [])
        self.assertEqual(brand_names.EXTRA["AEON"], "宏佳騰")

    def test_plug_finder_names_it_does_not_publish(self):
        d = data("BMW", "DUCATI", "HARLEY DAVIDSON")
        NGK_NO_HD = {"brands": [b for b in NGK["brands"] if b["en"] != "HARLEY-DAVIDSON"]}
        brand_names.apply(d, None, fetch=lambda u: json.dumps(NGK_NO_HD))
        self.assertEqual([b["tw"] for b in d["brands"]], ["寶馬", "杜卡迪", "哈雷"])

    def test_unknown_brand_is_reported_not_guessed(self):
        d = data("ZONTES")
        report = brand_names.apply(d, None, fetch=fetch_ok)
        self.assertEqual(d["brands"][0]["tw"], "")
        self.assertTrue(any("ZONTES" in l and l.startswith("NOTICE") for l in report))

    def test_plug_finder_down_keeps_yesterdays_names(self):
        previous = {"brands": [{"name": "YAMAHA", "tw": "山葉", "models": []}]}
        d = data("YAMAHA", "AEON")
        report = brand_names.apply(d, previous, fetch=fetch_down)
        self.assertEqual([b["tw"] for b in d["brands"]], ["山葉", "宏佳騰"])
        self.assertTrue(any(l.startswith("NOTICE") for l in report))

    def test_bad_json_counts_as_down(self):
        d = data("YAMAHA")
        brand_names.apply(d, {"brands": [{"name": "YAMAHA", "tw": "山葉"}]}, fetch=lambda u: "<html>")
        self.assertEqual(d["brands"][0]["tw"], "山葉")


if __name__ == "__main__":
    unittest.main(verbosity=1)
