#!/usr/bin/env python3
"""Build filters/data.json — the Champion air-filter finder — from CarMall product pages.

Source of truth: each Champion product's description carries a table
    品牌 | 車款 | 年份
(brand cells often rowspan several models). One product = one SKU.

One bike usually maps to several SKUs, and they are NOT alternatives: a TMAX 530 takes a
主空氣芯 plus a 左傳動 and a 右傳動 filter, and its 左傳動 part changed in 2017. So a model
lists every (SKU, years) it appears with, and each product carries its `position`, read
from the product title — the title wording is part of the contract with Jerry.

Exit codes — the scheduled workflow reads these:
    0  published, nothing to look at
    1  refused to publish: a fetch failed, or the result shrank too much to trust.
       The previous data.json is left untouched.
    3  published, but some products/rows had problems (listed in the log). A product whose
       table can't be read keeps its vehicles from the previous build ("CARRIED"); only a
       brand-new product with no previous data is left out. The workflow commits the data
       (everyone's price/stock still updates) and then goes red so the email reaches a human.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import carmall  # noqa: E402
import tables   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "filters", "data.json")
BRAND_HANDLE = "champion"
HEADER = ["品牌", "車款", "年份"]
YEARS = re.compile(r"^(\d{4})?\s*-\s*(\d{4})?$|^\d{4}$")
OE = re.compile(r"OE\s*料號\s*[:：]\s*(.+?)\s*(?:※|$)")
MARKET_PREFIX = re.compile(r"^(UK|EU|US|USA|JP|TW|AU)\s", re.I)
# Longest first: 左傳動空氣芯 must not be read as 傳動空氣芯.
POSITIONS = ["左傳動空氣芯", "右傳動空氣芯", "傳動空氣芯", "主空氣芯", "空氣芯"]


def position_of(title: str) -> str | None:
    for p in POSITIONS:
        if p in title:
            return p
    return None

# Refuse to publish when this many products lose their table at once: that is the shape
# of a template change, not of one product being mid-edit.
MAX_SKIPPED_PRODUCTS = 3
# ...or when the number of vehicle rows drops below this share of the last good build.
MIN_ROWS_KEPT = 0.8


def norm_years(raw: str) -> str:
    return re.sub(r"\s*[-–~～]\s*", "-", raw.strip())


def year_sort_key(years: str) -> tuple:
    m = re.match(r"(\d{4})?-?(\d{4})?", years)
    a = int(m.group(1)) if m and m.group(1) else 0
    b = int(m.group(2)) if m and m.group(2) else 9999
    return (a, b, years)


def parse_product(detail: dict) -> tuple[list[tuple[str, str, str]], list[str], list[str]]:
    """-> (rows as (brand, model, years), problems that drop data, notices for a human)."""
    problems: list[str] = []
    notices: list[str] = []
    found = None
    for t in tables.tables(detail.get("body_html") or ""):
        if t and [c.strip() for c in t[0]] == HEADER:
            found = t
            break
    if found is None:
        return [], ["找不到「品牌／車款／年份」表格"], notices
    rows = []
    for i, r in enumerate(found[1:], start=2):
        if len(r) != 3:
            problems.append(f"表格第 {i} 列有 {len(r)} 格（應為 3 格）：{' | '.join(r)}")
            continue
        brand, model, years = (c.strip() for c in r)
        if not brand or not model:
            problems.append(f"表格第 {i} 列缺廠牌或車款：{' | '.join(r)}")
            continue
        years = norm_years(years)
        if years and not YEARS.match(years):
            notices.append(f"年份格式看不懂，照原文顯示：{model}「{years}」")
        if MARKET_PREFIX.match(model):
            notices.append(f"車款名稱帶市場代碼：{brand} {model}")
        rows.append((re.sub(r"\s+", " ", brand).upper(), re.sub(r"\s+", " ", model), years))
    if not rows:
        problems.append("表格沒有任何車款")
    return rows, problems, notices


def build(fetch=carmall.get, previous: dict | None = None):
    """-> (data or None, exit code, report lines)."""
    report: list[str] = []
    summaries = carmall.category_products(BRAND_HANDLE, fetch=fetch)
    products, fits, skipped, carried = [], {}, [], []
    rows_total = 0
    # A product whose table can't be read keeps its vehicles from the last good build, so
    # a half-finished edit on one product page doesn't make its bikes vanish from the
    # finder while everything else's price/stock still updates. Keyed by product id: the
    # SKU itself may be what broke.
    prev = previous or {}
    prev_products = {p.get("product_id"): p for p in prev.get("products", [])}
    prev_rows: dict[str, list[tuple[str, str, str]]] = {}
    for b in prev.get("brands", []):
        for m in b["models"]:
            for f in m["fits"]:
                for y in f["years"]:
                    prev_rows.setdefault(f["sku"], []).append((b["name"], m["name"], y))
    for s in sorted(summaries, key=lambda x: x["id"]):
        detail = carmall.product_detail(s, fetch=fetch)
        title = carmall.clean_title(detail.get("title") or "")
        rows, problems, notices = parse_product(detail)
        if re.search(r"copy", title, re.I):
            notices.append("商品標題含「copy」，可能是複製商品時沒改到")
        offer = carmall.offer(detail)
        if not offer["sku"]:
            problems.append("商品沒有料號（SKU）")
            rows = []
        for n in notices:
            report.append(f"NOTICE  {title}: {n}")
        for p in problems:
            report.append(f"PROBLEM {title}: {p}")
        old = prev_products.get(detail.get("id"))
        # Any row-level problem means this table is mid-edit or broken: keep the whole
        # previous table rather than publishing the rows that happened to parse.
        if problems and old and prev_rows.get(old["sku"]):
            rows = prev_rows[old["sku"]]
            offer["sku"] = offer["sku"] or old["sku"]
            offer["oe"], offer["position"] = old.get("oe"), old.get("position")
            carried.append(title)
            report.append(f"CARRIED {title}: 沿用上一版的 {len(rows)} 列車款（價格庫存照常更新），請修正商品頁表格")
        elif not rows:
            skipped.append(title)
            continue
        else:
            offer["oe"] = (OE.search(tables.plain_text(detail.get("body_html"))) or [None, None])[1]
            offer["position"] = position_of(title)
            if offer["position"] is None:
                report.append(f"NOTICE  {title}: 標題沒有「空氣芯」字樣，看不出是哪個位置的濾芯，先當一般空氣芯")
                offer["position"] = "空氣芯"
        products.append(offer)
        for brand, model, years in rows:
            rows_total += 1
            years_list = fits.setdefault((brand, model), {}).setdefault(offer["sku"], [])
            if years not in years_list:
                years_list.append(years)

    prev_total = prev.get("stats", {}).get("rows") or 0
    broken = len(skipped) + len(carried)
    if broken > MAX_SKIPPED_PRODUCTS:
        report.append(f"REFUSE  {broken} 個商品讀不到適應表（上限 {MAX_SKIPPED_PRODUCTS}），像是版型整批變了；保留上一版資料")
        return None, 1, report
    if prev_total and rows_total < prev_total * MIN_ROWS_KEPT:
        report.append(f"REFUSE  車款列數從 {prev_total} 掉到 {rows_total}（低於 {int(MIN_ROWS_KEPT*100)}%）；保留上一版資料")
        return None, 1, report

    # Main filter first, then the transmission ones — the order a mechanic would list them.
    shown = ["主空氣芯", "空氣芯", "傳動空氣芯", "左傳動空氣芯", "右傳動空氣芯"]
    order = {p["sku"]: (shown.index(p["position"]) if p["position"] in shown else 99)
             for p in products}
    brands: dict[str, dict[str, list]] = {}
    for (brand, model), by_sku in fits.items():
        brands.setdefault(brand, {})[model] = sorted(
            ({"sku": sku, "years": sorted(ys, key=year_sort_key)} for sku, ys in by_sku.items()),
            key=lambda f: (order.get(f["sku"], 99), year_sort_key(f["years"][0]), f["sku"]))
    data = {
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "CarMall Champion 空氣芯商品頁之車種對照表",
        "category_url": f"{carmall.SITE}/categories/brandlist/{BRAND_HANDLE}",
        "stats": {"products": len(products), "rows": rows_total, "skipped": len(skipped),
                  "carried": len(carried)},
        "products": sorted(products, key=lambda p: p["sku"]),
        "brands": [
            {"name": b, "models": [
                {"name": m, "fits": fl}
                for m, fl in sorted(ms.items(), key=lambda kv: kv[0].casefold())
            ]}
            for b, ms in sorted(brands.items(), key=lambda kv: kv[0].casefold())
        ],
    }
    report.append(f"OK      {len(summaries)} 個商品 → 收錄 {len(products)} 個（沿用舊表 {len(carried)} 個）、跳過 {len(skipped)} 個；"
                  f"{rows_total} 列車款、{sum(len(ms) for ms in brands.values())} 個車款、{len(brands)} 個廠牌")
    return data, (3 if skipped or carried or any(l.startswith("PROBLEM") for l in report) else 0), report


def main() -> int:
    previous = None
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            previous = json.load(f)
    try:
        data, code, report = build(previous=previous)
    except carmall.FetchError as e:
        print(f"REFUSE  抓取失敗，保留上一版資料：{e}", file=sys.stderr)
        return 1
    for line in report:
        print(line)
    if data is not None:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        tmp = OUT + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, OUT)
        print(f"wrote {os.path.relpath(OUT, ROOT)}")
    return code


if __name__ == "__main__":
    sys.exit(main())
