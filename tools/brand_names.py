"""Taiwanese brand names for the motorcycle finders in this repo (brands[].tw).

Jerry 2026-11-16: every finder shows brands the same way, English + the name Taiwan uses
("YAMAHA 山葉"), and for motorcycles the plug finder (liquimolytaiwan/carmall-ngk-finder)
is the reference. So the names are read from that finder's published data.json on every
build: when it changes a name, these finders follow the next day without a code change.

Display only. brands[].name stays the English name — it is the cross-project key (the
blog automation and the share links match on it), so nothing here may rename it.
"""
from __future__ import annotations

import json
import re

import carmall

NGK_DATA = "https://liquimolytaiwan.github.io/carmall-ngk-finder/data.json"

# Brands the plug finder's data.json does not list. When both have a brand, the plug
# finder wins. "" = Taiwan just says the English name, so no Chinese is added (same rule
# as the plug finder's KTM / HUSQVARNA).
EXTRA = {
    # The plug finder's own names (BRAND_TW in carmall-ngk-finder/tools/build_data.py;
    # BMW = 寶馬 is Jerry's 2026-08-14 call). Its data.json only lists brands that have
    # bikes in it, and it has none of these three, so they are copied here.
    "BMW": "寶馬", "DUCATI": "杜卡迪", "HARLEY-DAVIDSON": "哈雷",
    # Not in the plug finder at all. Jerry 2026-11-16 chose: AEON 宏佳騰, GOGORO and
    # BUELL stay English.
    "AEON": "宏佳騰", "GOGORO": "", "BUELL": "",
}


def key(name: str) -> str:
    """Spelling-insensitive brand key: the pad tables write HARLEY DAVIDSON, the plug
    finder HARLEY-DAVIDSON."""
    return re.sub(r"[\s\-_]+", "", name or "").upper()


_EXTRA = {key(k): v for k, v in EXTRA.items()}


def ngk_names(fetch=carmall.get) -> dict[str, str] | None:
    """Brand key -> Taiwanese name from the plug finder, or None if it can't be read."""
    try:
        data = json.loads(fetch(NGK_DATA))
        return {key(b["en"]): (b.get("tw") or "") for b in data["brands"]}
    except Exception:          # network, bad JSON, layout change: all mean "not today"
        return None


def resolve(names: list[str], ngk: dict[str, str] | None, previous: dict | None):
    """English name -> Taiwanese name for each brand, plus report lines.

    Plug finder first, then EXTRA. If the plug finder can't be read, yesterday's names
    are kept rather than dropping every Chinese name off the menus for a day."""
    prev = {b["name"]: b.get("tw", "") for b in (previous or {}).get("brands", [])}
    out, report = {}, []
    if ngk is None:
        report.append("NOTICE  讀不到火星塞查詢器的廠牌中文名，沿用上一版")
    for n in names:
        k = key(n)
        if ngk is not None and k in ngk:
            out[n] = ngk[k]
        elif k in _EXTRA:
            out[n] = _EXTRA[k]
        elif ngk is None and n in prev:
            out[n] = prev[n]
        else:
            out[n] = ""
            report.append(f"NOTICE  廠牌「{n}」火星塞查詢器沒有、tools/brand_names.py 的 EXTRA 也沒有，"
                          "選單先只顯示英文；台灣有慣用中文名的話加進 EXTRA")
    return out, report


def apply(data: dict, previous: dict | None, fetch=carmall.get) -> list[str]:
    """Add brands[].tw to a freshly built data.json, keeping "name" as the first key."""
    names, report = resolve([b["name"] for b in data["brands"]], ngk_names(fetch), previous)
    data["brands"] = [dict({"name": b["name"], "tw": names[b["name"]]},
                           **{k: v for k, v in b.items() if k not in ("name", "tw")})
                      for b in data["brands"]]
    return report
