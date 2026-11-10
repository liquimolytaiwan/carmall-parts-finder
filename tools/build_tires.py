#!/usr/bin/env python3
"""Build tires/data.json — the ARISUN motorcycle-tyre finder — from CarMall product pages.

Tyres are sold by size, not by bike, so this finder has a different shape from the
air-filter and brake-pad ones and does not use finder_build.build (which joins on SKU and
reads one offer per product — ARISUN's size variants have no SKU at all):

    bike  ->  its stock front / rear size        (from the tables in the descriptions)
    size  ->  every tyre CarMall sells in it     (from the products' size variants)

Product kinds, told apart by title:
    single   SK1, RS01/RS02 — one variant per size (and, for RS, per 款式)
    install  【合作車行安裝】SK1 — same sizes, shipped to a partner shop that fits it
    set      【前後輪套組】RS01+RS02 — one variant, fixed front and rear size

Tables (hand-edited in Cyberbiz; the layout is the contract with Jerry):
    輪胎尺寸／輪位 | 車廠品牌 | 適用車款 (or 參考車款)
        first cell "110/70-12 前輪" or "120/70-13 RS01・前輪", usually a rowspan;
        models separated by 「、」; a "—｜依實車規格確認" row lists no bikes.
    a set's  型號 | 輪位 | 輪胎尺寸   -> the set's front and rear size
    a set's  車廠品牌 | 適用車款       -> bikes that take exactly those two sizes

A set is recommended only when the bike's front AND rear size both match it.

Publish rules are finder_build's (same thresholds, same exit codes), applied per product:
a product still in the category whose table breaks keeps its previous rows (CARRIED); a
product that has left the category — or is listed but 404s, i.e. was taken down — is
dropped, and the bikes that only it listed drop with it (logged by name).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import carmall       # noqa: E402
import finder_build  # noqa: E402
import tables        # noqa: E402

BRAND = "arisun"
OUT = "tires/data.json"
SOURCE = "CarMall ARISUN 輪胎商品頁之常見車款尺寸對照表"
POSITIONS = ("前輪", "後輪")

SIZE = re.compile(r"(?<![\d/])(\d{2,3}/\d{2,3}-\d{2})(?!\d)")
# SK1, RS01, RS02 … a code not glued to other letters/digits ("RS01前輪" still matches).
LINE = re.compile(r"(?<![A-Za-z0-9])([A-Z]{2,3}\d{1,2})(?![A-Za-z0-9])")
NO_BIKES = re.compile(r"依實車")
DASH = {"", "—", "–", "-", "－", "─"}
RACE_CAVEAT = re.compile(r"本系列以賽道[^。]*。")


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _space(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def kind_of(title: str) -> str:
    if "合作車行安裝" in title:
        return "install"
    if "套組" in title:
        return "set"
    return "single"


def position_in(text: str) -> str | None:
    found = [p for p in POSITIONS if p in (text or "")]
    return found[0] if len(found) == 1 else None


def variant_label(v: dict) -> list[str]:
    """The option values a customer clicks on the product page, in order."""
    opts = [_space(v.get(k) or "") for k in ("option1", "option2", "option3")]
    opts = [o for o in opts if o]
    if not opts and _space(v.get("title") or ""):
        opts = [_space(x) for x in (v.get("title") or "").split(" / ") if _space(x)]
    return opts


# ---------------------------------------------------------------- one product

def read_product(detail: dict, previous_offers: dict[int, dict]):
    """-> (offers, rows, problems, notices).

    rows are (brand, model, position, size) as written in this product's tables."""
    title = carmall.clean_title(detail.get("title") or "")
    kind = kind_of(title)
    body = detail.get("body_html") or ""
    text = tables.plain_text(body)
    problems: list[str] = []
    notices: list[str] = []
    title_lines = sorted(set(LINE.findall(title.replace("ARISUN", " "))))
    caveat = RACE_CAVEAT.search(text)
    caveat = caveat.group(0) if caveat else None
    grids = tables.tables(body)

    offers: list[dict] = []
    if kind == "set":
        variants = detail.get("variants") or []
        if len(variants) != 1:
            problems.append(f"套組商品應只有 1 個規格，實際 {len(variants)} 個")
        if variants:
            o = base_offer(detail, variants[0], kind, title)
            sizes = set_sizes(grids)
            if sizes is None:
                prev = previous_offers.get(o["variant_id"]) or {}
                if prev.get("front") and prev.get("rear"):
                    sizes = (prev["front"], prev["rear"])
                    notices.append("套組前後尺寸沿用上一版")
                problems.append("找不到套組的「型號｜輪位｜輪胎尺寸」表格（要有前輪、後輪各一列）")
            if sizes:
                o["front"], o["rear"] = sizes
            o["line"] = "+".join(title_lines) if title_lines else None
            o["type"] = title_type(title)
            if caveat:
                o["caveat"] = caveat
            offers.append(o)
    else:
        for v in detail.get("variants") or []:
            label = variant_label(v)
            joined = " ".join(label)
            m = SIZE.search(joined)
            lines = LINE.findall(joined) or title_lines
            why = (f"規格「{joined or '（空白）'}」看不出輪胎尺寸" if not m else
                   f"規格「{joined}」看不出是哪一款胎（{'／'.join(lines) or '沒有型號'}）" if len(lines) != 1 else None)
            if why:
                # Same rule as a broken table: keep what this variant was last time (fresh
                # price/stock), so its bikes don't end up with no tyre to buy.
                prev = previous_offers.get(v.get("id"))
                if prev and prev.get("kind") == kind and prev.get("size"):
                    # Fresh offer + only what was parsed from the label last time. Spreading
                    # all of prev would keep a stale compare_at/sku/install the store dropped.
                    o = base_offer(detail, v, kind, title)
                    o.update({k: prev[k] for k in ("line", "size", "position", "choose", "type") if k in prev})
                    if caveat:
                        o["caveat"] = caveat
                    offers.append(o)
                    problems.append(why + "；這個規格沿用上一版的尺寸")
                else:
                    problems.append(why + "；這個規格先不收錄")
                continue
            o = base_offer(detail, v, kind, title)
            o.update({"line": lines[0], "size": m.group(1), "position": position_in(joined),
                      "choose": label})
            o["type"] = spec_type(grids, lines[0], m.group(1)) or title_type(title)
            if caveat:
                o["caveat"] = caveat
            offers.append(o)
        seen: dict[tuple, str] = {}
        for o in offers:
            k = (o["line"], o["size"], o["position"])
            if k in seen:
                problems.append(f"同一款同一尺寸有兩個規格：{seen[k]}、{' '.join(o['choose'])}")
            seen[k] = " ".join(o["choose"])

    rows = vehicle_rows(grids, kind, offers, title_lines, problems, notices)
    if not rows and not problems:
        problems.append("找不到「輪胎尺寸／輪位｜車廠品牌｜適用車款」表格，或表格沒有任何車款")
    if re.search(r"copy", title, re.I):
        notices.append("商品標題含「copy」，可能是複製商品時沒改到")
    return offers, rows, problems, notices


def base_offer(detail: dict, v: dict | None, kind: str, title: str) -> dict:
    o = carmall.offer(detail, v)
    o["variant_id"] = (v or {}).get("id")
    o["kind"] = kind
    if not o["sku"]:
        del o["sku"]
    cap = (v or {}).get("compare_at_price")
    if cap is not None and o["price"] is not None and cap > o["price"]:
        o["compare_at"] = cap
    return o


def set_sizes(grids) -> tuple[str, str] | None:
    for t in grids:
        head = [_norm(c) for c in t[0]] if t else []
        if "輪位" in head and "輪胎尺寸" in head:
            ip, isz = head.index("輪位"), head.index("輪胎尺寸")
            got = {}
            for r in t[1:]:
                if len(r) == len(head):
                    pos, m = position_in(r[ip]), SIZE.search(r[isz])
                    if pos and m:
                        got.setdefault(pos, set()).add(m.group(1))
            if len(got.get("前輪", ())) == 1 and len(got.get("後輪", ())) == 1:
                return next(iter(got["前輪"])), next(iter(got["後輪"]))
    return None


def title_type(title: str) -> str | None:
    """「ARISUN SK1｜全天候半熱熔胎」-> 全天候半熱熔胎 (the last word ending in 胎)."""
    words = re.findall(r"[^\s｜|】【／/]+胎", title)
    return words[-1] if words else None


def spec_type(grids, line: str, size: str) -> str | None:
    """胎款類型 (全熱熔／半熱熔) from a 型號｜輪胎尺寸｜輪位｜胎款類型 table, when there is one."""
    for t in grids:
        head = [_norm(c) for c in t[0]] if t else []
        if {"型號", "輪胎尺寸", "胎款類型"} <= set(head):
            for r in t[1:]:
                if len(r) == len(head) and _norm(r[head.index("型號")]) == line \
                        and size in r[head.index("輪胎尺寸")]:
                    return _space(r[head.index("胎款類型")]) + "胎"
    return None


def vehicle_rows(grids, kind, offers, title_lines, problems, notices):
    rows: list[tuple[str, str, str, str]] = []
    for t in grids:
        head = [_norm(c) for c in t[0]] if t else []
        if len(head) == 3 and head[0].startswith("輪胎尺寸") and head[1] == "車廠品牌" \
                and head[2] in ("適用車款", "參考車款"):
            for i, r in enumerate(t[1:], start=2):
                if len(r) != 3:
                    problems.append(f"表格第 {i} 列格式不對：{' | '.join(r)}")
                    continue
                first, brand, models = r
                if _space(brand) in DASH and NO_BIKES.search(models):
                    continue                        # "—｜依實車規格確認": a size with no bikes listed
                m, pos = SIZE.search(first), position_in(first)
                if not m or not pos:
                    problems.append(f"表格第 {i} 列看不出尺寸或前後輪：「{first}」")
                    continue
                size = m.group(1)
                line = (LINE.findall(first) or [None])[0]
                if kind != "set" and not matching(offers, size, pos, line):
                    problems.append(f"表格寫「{size} {pos}」，但商品沒有可以裝在{pos}的這個尺寸規格")
                    continue
                rows.extend(split_models(brand, models, size, pos, i, problems))
        elif kind == "set" and head in (["車廠品牌", "適用車款"], ["車廠品牌", "參考車款"]):
            o = offers[0] if offers else {}
            if not (o.get("front") and o.get("rear")):
                continue                            # already a PROBLEM: no sizes to give them
            for i, r in enumerate(t[1:], start=2):
                if len(r) != 2:
                    problems.append(f"套組車款表第 {i} 列格式不對：{' | '.join(r)}")
                    continue
                for pos, size in (("前輪", o["front"]), ("後輪", o["rear"])):
                    rows.extend(split_models(r[0], r[1], size, pos, i, problems))
        elif "車廠品牌" in head:
            # A bike table whose header was edited into a shape we don't read: say so, even
            # when another table on the page still parses — otherwise its bikes vanish quietly.
            problems.append("有一張表的欄位看不懂：" + "｜".join(t[0]) +
                            "（應為「輪胎尺寸／輪位｜車廠品牌｜適用車款」"
                            + ("，或套組的「車廠品牌｜適用車款」" if kind == "set" else "") + "）")
    return rows


def matching(offers, size, pos, line=None):
    return [o for o in offers if o["size"] == size and o["position"] in (None, pos)
            and (line is None or o["line"] == line)]


def split_models(brand, models, size, pos, i, problems):
    brand = _space(brand).upper()
    names = [_space(x) for x in re.split(r"[、，,]", models) if _space(x)]
    if not brand or brand in DASH or not names:
        problems.append(f"表格第 {i} 列缺廠牌或車款：{brand} | {models}")
        return []
    return [(brand, n, pos, size) for n in names]


# ---------------------------------------------------------------- whole brand

def build(fetch=carmall.get, previous: dict | None = None):
    """-> (data or None, exit code, report lines). Raises carmall.FetchError when the
    category or a still-listed product can't be fetched (other than a 404)."""
    report: list[str] = []
    prev = previous or {}
    prev_offers = {o.get("variant_id"): o for o in prev.get("offers", [])}
    prev_titles = {o.get("product_id"): o.get("title") for o in prev.get("offers", [])}
    prev_rows: dict[int, list[tuple[str, str, str, str]]] = {}
    for b in prev.get("brands", []):
        for m in b["models"]:
            for pos_key, pos in (("front", "前輪"), ("rear", "後輪")):
                for s in m.get(pos_key, []):
                    for pid in s.get("listed_by", []):
                        prev_rows.setdefault(pid, []).append((b["name"], m["name"], pos, s["size"]))

    summaries = carmall.category_products(BRAND, fetch=fetch)
    offers: list[dict] = []
    rows: list[tuple[str, str, str, str, int]] = []
    skipped, carried, gone = [], [], []
    gone_ids: set[int] = set()
    for s in sorted(summaries, key=lambda x: x["id"]):
        try:
            detail = carmall.product_detail(s, fetch=fetch)
        except carmall.NotFound:
            gone.append(s.get("title") or str(s["id"]))
            gone_ids.add(s["id"])
            report.append(f"NOTICE  {s.get('title') or s['id']}: 分類裡還列著，但商品頁 404，當作已下架、不收錄")
            continue
        title = carmall.clean_title(detail.get("title") or "")
        p_offers, p_rows, problems, notices = read_product(detail, prev_offers)
        for n in notices:
            report.append(f"NOTICE  {title}: {n}")
        for p in problems:
            report.append(f"PROBLEM {title}: {p}")
        pid = detail.get("id")
        # Any problem means the table is mid-edit or broken: keep this product's whole
        # previous table rather than the rows that happened to parse. Its size variants
        # are still sold either way — a tyre is matched by size, not by whose table
        # listed the bike — so its offers are kept even when its own rows are not.
        if problems and prev_rows.get(pid):
            p_rows = prev_rows[pid]
            carried.append(title)
            report.append(f"CARRIED {title}: 沿用上一版的 {len(p_rows)} 列車款（價格庫存照常更新），請修正商品頁表格")
        elif problems:
            p_rows = []
            skipped.append(title)
            report.append(f"SKIPPED {title}: 這頁表格沒有上一版可沿用，這頁列的車款先不收錄（尺寸照常販售）")
        offers.extend(p_offers)
        rows.extend((b, m, pos, size, pid) for b, m, pos, size in p_rows)
    # Join bikes case-insensitively (first spelling wins), then keep one row per
    # (bike, wheel, size, product) — exactly what listed_by is rebuilt from next time, so
    # stats.rows and the carried/gone row counts measure the same thing.
    names: dict[tuple[str, str], str] = {}
    canon = []
    for b, m, pos, size, pid in rows:
        first = names.setdefault((b, m.casefold()), m)
        if first != m:
            report.append(f"NOTICE  車款大小寫不一致：「{first}」與「{m}」當成同一台")
        canon.append((b, first, pos, size, pid))
    rows = list(dict.fromkeys(canon))

    # Gone from the category entirely (not just 404): say so, it takes its bikes with it.
    now_ids = {s["id"] for s in summaries}
    for pid, t in prev_titles.items():
        if pid not in now_ids:
            gone_ids.add(pid)
            report.append(f"NOTICE  {t}: 已不在 ARISUN 分類裡（下架或移出分類），不再收錄")

    # Taking one product down is normal (the RS01+RS02 set is a time-limited offer); most of
    # the brand vanishing at once is the shape of a broken or empty category response, and
    # trusting it would publish an empty finder.
    prev_ids = set(prev_titles)
    if prev_ids and (not summaries or len(gone_ids & prev_ids) > len(prev_ids) // 2):
        report.append(f"REFUSE  上一版 {len(prev_ids)} 個商品這次有 {len(gone_ids & prev_ids)} 個不見了"
                      "（超過一半），像是分類頁抓取異常；保留上一版資料")
        return None, 1, report

    broken = len(skipped) + len(carried)
    prev_total = prev.get("stats", {}).get("rows") or 0
    if broken > finder_build.MAX_SKIPPED_PRODUCTS:
        report.append(f"REFUSE  {broken} 個商品讀不到適應表（上限 {finder_build.MAX_SKIPPED_PRODUCTS}），像是版型整批變了；保留上一版資料")
        return None, 1, report
    # A product that left the store takes its rows with it legitimately; only the rows of
    # products still listed are held to the shrink guard.
    gone_rows = sum(len(v) for pid, v in prev_rows.items() if pid in gone_ids)
    if prev_total and len(rows) < (prev_total - gone_rows) * finder_build.MIN_ROWS_KEPT:
        report.append(f"REFUSE  車款列數從 {prev_total} 掉到 {len(rows)}（扣掉已下架商品後仍低於 "
                      f"{int(finder_build.MIN_ROWS_KEPT*100)}%）；保留上一版資料")
        return None, 1, report

    data = assemble(offers, rows, report)
    data["stats"].update({"skipped": len(skipped), "carried": len(carried), "gone": len(gone)})

    # Name every bike that dropped out since the last build: AGENTS.md — never lose bikes silently.
    before = {(b["name"], m["name"]) for b in prev.get("brands", []) for m in b["models"]}
    after = {(b["name"], m["name"]) for b in data["brands"] for m in b["models"]}
    if before - after:
        report.append("NOTICE  這次少了這些車款：" + "、".join(f"{b} {m}" for b, m in sorted(before - after)))

    report.append(f"OK      {len(summaries)} 個商品 → {len({o['product_id'] for o in offers})} 個收錄"
                  f"（沿用舊表 {len(carried)} 個、跳過 {len(skipped)} 個、下架 {len(gone)} 個）；"
                  f"{len(rows)} 列車款、{data['stats']['models']} 個車款、{len(data['brands'])} 個廠牌、"
                  f"{len(data['offers'])} 個規格")
    code = 3 if skipped or carried or any(l.startswith("PROBLEM") for l in report) else 0
    return data, code, report


def assemble(offers: list[dict], rows, report: list[str]) -> dict:
    singles = [o for o in offers if o["kind"] == "single"]
    installs = [o for o in offers if o["kind"] == "install"]
    sets = [o for o in offers if o["kind"] == "set" and o.get("front") and o.get("rear")]

    # The install twin of a single tyre: same line, size and wheel, shipped to a partner shop.
    twinned = set()
    for o in singles:
        twin = [i for i in installs if (i["line"], i["size"], i["position"]) == (o["line"], o["size"], o["position"])]
        if len(twin) == 1:
            o["install"] = twin[0]["variant_id"]
            twinned.add(twin[0]["variant_id"])
    for i in installs:
        if i["variant_id"] not in twinned:
            report.append(f"NOTICE  {i['title']}：規格「{' '.join(i['choose'])}」在一般版找不到同款同尺寸，查詢器不會顯示這個合作車行規格")

    # rows arrive with bike names already joined case-insensitively (see build).
    bikes: dict[tuple[str, str], dict[str, dict[str, set]]] = {}
    for brand, model, pos, size, pid in rows:
        bikes.setdefault((brand, model), {}).setdefault(pos, {}).setdefault(size, set()).add(pid)

    def tyres_for(size, pos):
        # Road tyres before the track-oriented ones (those carry the page's 賽道 caveat).
        hits = [o for o in singles if o["size"] == size and o["position"] in (None, pos)]
        return [o["variant_id"] for o in sorted(
            hits, key=lambda o: (bool(o.get("caveat")), o["line"], o["price"] or 0, o["variant_id"]))]

    brands: dict[str, list[dict]] = {}
    for (brand, name), by_pos in bikes.items():
        model = {"name": name}
        for pos_key, pos in (("front", "前輪"), ("rear", "後輪")):
            model[pos_key] = [{"size": size, "tyres": tyres_for(size, pos), "listed_by": sorted(pids)}
                              for size, pids in sorted(by_pos.get(pos, {}).items())]
            if len(model[pos_key]) > 1:
                report.append(f"NOTICE  {brand} {model['name']}：{pos}對到不止一個尺寸（"
                              + "、".join(s["size"] for s in model[pos_key]) + "），畫面會請客人核對")
            for s in model[pos_key]:
                if not s["tyres"]:
                    report.append(f"NOTICE  {brand} {model['name']}：{pos} {s['size']} 目前沒有單條販售的規格")
        fronts = {s["size"] for s in model["front"]}
        rears = {s["size"] for s in model["rear"]}
        model["sets"] = [o["variant_id"] for o in sets if fronts == {o["front"]} and rears == {o["rear"]}]
        brands.setdefault(brand, []).append(model)

    out_offers = sorted(singles + installs + sets, key=lambda o: (o["product_id"], o["variant_id"] or 0))
    return {
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": SOURCE,
        "category_url": f"{carmall.SITE}/categories/brandlist/{BRAND}",
        "stats": {"products": len({o["product_id"] for o in out_offers}), "rows": len(rows),
                  "models": sum(len(v) for v in brands.values())},
        "offers": out_offers,
        "brands": [
            {"name": b, "models": sorted(ms, key=lambda m: m["name"].casefold())}
            for b, ms in sorted(brands.items(), key=lambda kv: kv[0].casefold())
        ],
    }


def main() -> int:
    out = os.path.join(finder_build.ROOT, OUT)
    previous = None
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            previous = json.load(f)
    try:
        data, code, report = build(previous=previous)
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
        print(f"wrote {OUT}")
    return code


if __name__ == "__main__":
    sys.exit(main())
