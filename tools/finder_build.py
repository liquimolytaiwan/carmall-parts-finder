"""The build engine every finder in this repo shares.

A finder supplies a `Spec`: which CarMall brand category to read, and how to turn one
product's description into vehicle rows. This module does the rest the same way for all
of them — fetching, the publish/refuse rules, carrying a broken product's previous rows,
assembling data.json — so the rules a finder publishes under can't drift between finders.

Exit codes (the scheduled workflow reads these):
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
from dataclasses import dataclass, field
from typing import Callable

import carmall

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Refuse to publish when this many products lose their table at once: that is the shape
# of a template change, not of one product being mid-edit.
MAX_SKIPPED_PRODUCTS = 3
# ...or when the number of vehicle rows drops below this share of the last good build.
MIN_ROWS_KEPT = 0.8

# Offer fields that are always re-read from the live product; everything else a parser
# adds (position, oe, …) is carried over from the previous build when the table breaks.
FRESH_FIELDS = {"product_id", "title", "url", "sku", "price", "qty", "available"}


@dataclass
class Parsed:
    # (brand, model, years, notes): notes are short strings shown with that fit.
    rows: list[tuple[str, str, str, tuple[str, ...]]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)   # data was dropped
    notices: list[str] = field(default_factory=list)    # worth a human look, nothing dropped
    fields: dict = field(default_factory=dict)          # extra product fields (position, oe…)


@dataclass
class Spec:
    brand_handle: str
    out: str                         # path relative to the repo root
    source: str
    parse: Callable[[dict, str], Parsed]
    position_order: list[str] = field(default_factory=list)


def year_sort_key(years: str) -> tuple:
    m = re.match(r"(\d{4})?-?(\d{4})?", years or "")
    a = int(m.group(1)) if m and m.group(1) else 0
    b = int(m.group(2)) if m and m.group(2) else 9999
    return (a, b, years or "")


def build(spec: Spec, fetch=carmall.get, previous: dict | None = None):
    """-> (data or None, exit code, report lines). Raises carmall.FetchError on fetch failure."""
    report: list[str] = []
    summaries = carmall.category_products(spec.brand_handle, fetch=fetch)
    products, skipped, carried = [], [], []
    fits: dict[tuple[str, str], dict[str, dict[str, list]]] = {}
    rows_total = 0
    # A product whose table can't be read keeps its vehicles from the last good build, so
    # a half-finished edit on one product page doesn't make its bikes vanish while every
    # other product's price/stock still updates. Keyed by product id: the SKU itself may
    # be what broke.
    prev = previous or {}
    prev_products = {p.get("product_id"): p for p in prev.get("products", [])}
    prev_rows: dict[str, list[tuple[str, str, str, tuple[str, ...]]]] = {}
    for b in prev.get("brands", []):
        for m in b["models"]:
            for f in m["fits"]:
                for y in f["years"]:
                    prev_rows.setdefault(f["sku"], []).append(
                        (b["name"], m["name"], y, tuple(f.get("notes", []))))

    for s in sorted(summaries, key=lambda x: x["id"]):
        detail = carmall.product_detail(s, fetch=fetch)
        title = carmall.clean_title(detail.get("title") or "")
        parsed = spec.parse(detail, title)
        problems, notices, rows = list(parsed.problems), list(parsed.notices), list(parsed.rows)
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
            offer.update({k: v for k, v in old.items() if k not in FRESH_FIELDS})
            carried.append(title)
            report.append(f"CARRIED {title}: 沿用上一版的 {len(rows)} 列車款（價格庫存照常更新），請修正商品頁表格")
        elif not rows:
            skipped.append(title)
            continue
        else:
            offer.update(parsed.fields)
        products.append(offer)
        for brand, model, years, notes in rows:
            rows_total += 1
            slot = fits.setdefault((brand, model), {}).setdefault(offer["sku"], {"years": [], "notes": []})
            if years not in slot["years"]:
                slot["years"].append(years)
            for n in notes:
                if n not in slot["notes"]:
                    slot["notes"].append(n)

    prev_total = prev.get("stats", {}).get("rows") or 0
    broken = len(skipped) + len(carried)
    if broken > MAX_SKIPPED_PRODUCTS:
        report.append(f"REFUSE  {broken} 個商品讀不到適應表（上限 {MAX_SKIPPED_PRODUCTS}），像是版型整批變了；保留上一版資料")
        return None, 1, report
    if prev_total and rows_total < prev_total * MIN_ROWS_KEPT:
        report.append(f"REFUSE  車款列數從 {prev_total} 掉到 {rows_total}（低於 {int(MIN_ROWS_KEPT*100)}%）；保留上一版資料")
        return None, 1, report

    order = {p["sku"]: (spec.position_order.index(p.get("position"))
                        if p.get("position") in spec.position_order else 99) for p in products}

    def fit_out(sku: str, slot: dict) -> dict:
        f = {"sku": sku, "years": sorted(slot["years"], key=year_sort_key)}
        if slot["notes"]:
            f["notes"] = slot["notes"]
        return f

    brands: dict[str, dict[str, list]] = {}
    for (brand, model), by_sku in fits.items():
        brands.setdefault(brand, {})[model] = sorted(
            (fit_out(sku, slot) for sku, slot in by_sku.items()),
            key=lambda f: (order.get(f["sku"], 99), year_sort_key(f["years"][0]), f["sku"]))
    data = {
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": spec.source,
        "category_url": f"{carmall.SITE}/categories/brandlist/{spec.brand_handle}",
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


def main(spec: Spec) -> int:
    out = os.path.join(ROOT, spec.out)
    previous = None
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            previous = json.load(f)
    try:
        data, code, report = build(spec, previous=previous)
    except carmall.FetchError as e:
        print(f"REFUSE  抓取失敗，保留上一版資料：{e}", file=sys.stderr)
        return 1
    for line in report:
        print(line)
    if data is not None:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        tmp = out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, out)
        print(f"wrote {spec.out}")
    return code
