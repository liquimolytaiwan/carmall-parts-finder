#!/usr/bin/env python3
"""Build pads/data.json — the NISSIN brake-pad finder — from CarMall product pages.

Source of truth: each NISSIN product's description carries a table
    車廠品牌 | 適用車款
where the second cell lists many bikes separated by 「、」, each as MODEL(YY'-YY'), e.g.
    TZR250(89'-90')、TMAX530 / SX / DX(13'-19')、XJ6N(09'-11'*)
A trailing * on the years means the part changes from a frame number partway through
that range; the frame numbers, when given, are in the same page's 備註 section.

Front/rear comes from the product title — (前) or (後). The model text is kept verbatim:
NISSIN writes bike variants into it ("ZX-14R (FRONT BREMBO CALIPER)" is the ZX-14R fitted
with Brembo front calipers, and A0570 is its rear pad), so it is not read as a position.

A second table headed 車廠品牌 | 參考適用車款 lists bikes NISSIN does not list but the shop
has matched itself; those fits carry a note saying exactly that.

Publish rules and exit codes: see finder_build.py.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import carmall       # noqa: E402,F401
import finder_build  # noqa: E402
import tables        # noqa: E402

HEADER = ["車廠品牌", "適用車款"]
REF_HEADER = ["車廠品牌", "參考適用車款"]
REF_NOTE = "NISSIN 原廠未標示此車款，為店家與競品比對後的參考適用，購買前請再確認"
# MODEL(YY') / (YY'-YY') / (YY'-) open-ended / optional * before the closing paren.
ITEM = re.compile(r"^(?P<name>.+?)\s*\(\s*(?P<a>\d{2})['’]\s*(?P<dash>[-–~]\s*(?:(?P<b>\d{2})['’]?)?)?\s*(?P<star>\*)?\s*\)$")
# A quote touching a digit is a mangled name (XV00'CU); BW'S is a real model name.
MANGLED = re.compile(r"\d['’]|['’]\d")
SIDE_IN_BRAND = re.compile(r"\s+(rear|front)$", re.I)
FRAME_NOTE = re.compile(r"[▪•・]\s*️?\s*(?P<model>[^：:▪•・]+?)\s*[:：]\s*(?P<frame>[A-HJ-NPR-Z0-9]{10,17})")
REPLACEMENT = re.compile(r"改適用\s*(?P<part>[A-Z]\d{3,5})")


def full_year(yy: str) -> int:
    n = int(yy)
    return 1900 + n if n >= 50 else 2000 + n


def side_of(title: str) -> str | None:
    if re.search(r"[(（]\s*前\s*[)）]", title):
        return "前輪"
    if re.search(r"[(（]\s*後\s*[)）]", title):
        return "後輪"
    return None


def parse(detail: dict, title: str) -> finder_build.Parsed:
    out = finder_build.Parsed()
    body = detail.get("body_html") or ""
    text = tables.plain_text(body)
    frames = {m.group("model").strip().upper(): m.group("frame") for m in FRAME_NOTE.finditer(text)}
    rep = REPLACEMENT.search(text)
    replacement = rep.group("part") if rep else None

    main, refs = None, []
    for t in tables.tables(body):
        head = [c.strip() for c in t[0]] if t else []
        if head == HEADER and main is None:
            main = t
        elif head == REF_HEADER:
            refs.append(t)
    if main is None:
        out.problems.append("找不到「車廠品牌／適用車款」表格")
        return out

    starred_without_frame = []
    for table, extra in [(main, ())] + [(t, (REF_NOTE,)) for t in refs]:
        for i, r in enumerate(table[1:], start=2):
            if len(r) != 2 or not r[0].strip() or not r[1].strip():
                out.problems.append(f"表格第 {i} 列格式不對：{' | '.join(r)}")
                continue
            brand = r[0].strip()
            if SIDE_IN_BRAND.search(brand):
                out.notices.append(f"廠牌欄寫「{brand}」，當成 {SIDE_IN_BRAND.sub('', brand).upper()}（前後以商品標題為準）")
                brand = SIDE_IN_BRAND.sub("", brand)
            brand = re.sub(r"\s+", " ", brand).upper()
            for item in [x.strip() for x in r[1].split("、") if x.strip()]:
                m = ITEM.match(item)
                if not m:
                    out.problems.append(f"看不懂這個車款寫法：「{item}」（應為 車款(年'-年')）")
                    continue
                name = re.sub(r"\s+", " ", m.group("name")).strip()
                a = full_year(m.group("a"))
                b = full_year(m.group("b")) if m.group("b") else (None if m.group("dash") else a)
                if b is not None and b < a:
                    out.notices.append(f"年份前後顛倒：{name}「{item}」")
                if MANGLED.search(name):
                    out.notices.append(f"車款名稱疑似打錯：「{name}」")
                notes = list(extra)
                if m.group("star"):
                    frame = frames.get(name.upper())
                    if frame and replacement:
                        notes.append(f"車架號碼 {frame} 起改用 {replacement}，購買前請核對車架號碼")
                    else:
                        starred_without_frame.append(name)
                        notes.append("此年份區間中途（依車架號碼）改用其他料號，購買前請洽客服核對車架號碼")
                years = f"{a}-" if b is None else (str(a) if a == b else f"{a}-{b}")
                out.rows.append((brand, name, years, tuple(notes)))
    if starred_without_frame:
        out.notices.append("有標 * 的車款，但這頁沒寫從哪個車架號碼改用哪個料號："
                           + "、".join(starred_without_frame))
    if not out.rows:
        out.problems.append("表格沒有任何車款")

    side = side_of(title)
    if side is None:
        out.problems.append("標題看不出是前輪還是後輪（應含「(前)」或「(後)」）")
        out.rows = []
    out.fields = {"position": side}
    return out


SPEC = finder_build.Spec(
    brand_handle="nissin",
    out="pads/data.json",
    source="CarMall NISSIN 來令片商品頁之適用車款表",
    parse=parse,
    position_order=["前輪", "後輪"],
)


def build(fetch=finder_build.carmall.get, previous=None):
    return finder_build.build(SPEC, fetch=fetch, previous=previous)


if __name__ == "__main__":
    sys.exit(finder_build.main(SPEC))
