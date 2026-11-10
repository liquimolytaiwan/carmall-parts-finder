#!/usr/bin/env python3
"""Build filters/data.json — the Champion air-filter finder — from CarMall product pages.

Source of truth: each Champion product's description carries a table
    品牌 | 車款 | 年份
(brand cells often rowspan several models). One product = one SKU.

One bike usually maps to several SKUs, and they are NOT alternatives: a TMAX 530 takes a
主空氣芯 plus a 左傳動 and a 右傳動 filter, and its 左傳動 part changed in 2017. So a model
lists every (SKU, years) it appears with, and each product carries its `position`, read
from the product title — the title wording is part of the contract with Jerry.

Publish rules and exit codes: see finder_build.py.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import carmall       # noqa: E402,F401  (kept importable as build_filters.carmall for tests)
import finder_build  # noqa: E402
import tables        # noqa: E402

HEADER = ["品牌", "車款", "年份"]
YEARS = re.compile(r"^(\d{4})?\s*-\s*(\d{4})?$|^\d{4}$")
OE = re.compile(r"OE\s*料號\s*[:：]\s*(.+?)\s*(?:※|$)")
MARKET_PREFIX = re.compile(r"^(UK|EU|US|USA|JP|TW|AU)\s", re.I)
# Longest first: 左傳動空氣芯 must not be read as 傳動空氣芯.
POSITIONS = ["左傳動空氣芯", "右傳動空氣芯", "傳動空氣芯", "主空氣芯", "空氣芯"]
# Main filter first, then the transmission ones — the order a mechanic would list them.
SHOWN_ORDER = ["主空氣芯", "空氣芯", "傳動空氣芯", "左傳動空氣芯", "右傳動空氣芯"]


def position_of(title: str) -> str | None:
    for p in POSITIONS:
        if p in title:
            return p
    return None


def norm_years(raw: str) -> str:
    return re.sub(r"\s*[-–~～]\s*", "-", raw.strip())


def parse(detail: dict, title: str) -> finder_build.Parsed:
    out = finder_build.Parsed()
    found = None
    for t in tables.tables(detail.get("body_html") or ""):
        if t and [c.strip() for c in t[0]] == HEADER:
            found = t
            break
    if found is None:
        out.problems.append("找不到「品牌／車款／年份」表格")
        return out
    for i, r in enumerate(found[1:], start=2):
        if len(r) != 3:
            out.problems.append(f"表格第 {i} 列有 {len(r)} 格（應為 3 格）：{' | '.join(r)}")
            continue
        brand, model, years = (c.strip() for c in r)
        if not brand or not model:
            out.problems.append(f"表格第 {i} 列缺廠牌或車款：{' | '.join(r)}")
            continue
        years = norm_years(years)
        if years and not YEARS.match(years):
            out.notices.append(f"年份格式看不懂，照原文顯示：{model}「{years}」")
        if MARKET_PREFIX.match(model):
            out.notices.append(f"車款名稱帶市場代碼：{brand} {model}")
        out.rows.append((re.sub(r"\s+", " ", brand).upper(), re.sub(r"\s+", " ", model), years, ()))
    if not out.rows:
        out.problems.append("表格沒有任何車款")
    position = position_of(title)
    if position is None:
        out.notices.append("標題沒有「空氣芯」字樣，看不出是哪個位置的濾芯，先當一般空氣芯")
        position = "空氣芯"
    out.fields = {"oe": (OE.search(tables.plain_text(detail.get("body_html"))) or [None, None])[1],
                  "position": position}
    return out


SPEC = finder_build.Spec(
    brand_handle="champion",
    out="filters/data.json",
    source="CarMall Champion 空氣芯商品頁之車種對照表",
    parse=parse,
    position_order=SHOWN_ORDER,
)


def build(fetch=finder_build.carmall.get, previous=None):
    return finder_build.build(SPEC, fetch=fetch, previous=previous)


if __name__ == "__main__":
    sys.exit(finder_build.main(SPEC))
