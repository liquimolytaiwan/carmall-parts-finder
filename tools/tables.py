"""Read the vehicle tables out of a product description (body_html).

The tables are hand-edited in Cyberbiz's editor and use rowspan for a brand that covers
several model rows (Champion MT-07: one YAMAHA cell spanning 12 rows). Reading cells by
position without expanding spans shifts every following row one column left, so the model
lands in the brand column — silently. Expand spans into a plain grid first.
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.tables: list[list[list[tuple[str, int, int]]]] = []
        self._stack: list[list[list[tuple[str, int, int]]]] = []
        self._row: list[tuple[str, int, int]] | None = None
        self._cell: list[str] | None = None
        self._span = (1, 1)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self._stack.append([])
        elif tag == "tr" and self._stack:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            self._span = (_int(a.get("rowspan")), _int(a.get("colspan")))
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append((_text("".join(self._cell)), *self._span))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._stack:
            self._stack[-1].append(self._row)
            self._row = None
        elif tag == "table" and self._stack:
            self.tables.append(self._stack.pop())

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_entityref(self, name):
        if self._cell is not None:
            self._cell.append(f"&{name};")

    def handle_charref(self, name):
        if self._cell is not None:
            self._cell.append(f"&#{name};")


def _int(v) -> int:
    try:
        return max(1, int(str(v).strip()))
    except (TypeError, ValueError):
        return 1


def _grid(rows: list[list[tuple[str, int, int]]]) -> list[list[str]]:
    """Expand rowspan/colspan so every row has its cells in their real columns."""
    out: list[list[str]] = []
    carry: dict[int, tuple[str, int]] = {}      # column -> (text, rows still to fill)
    for raw in rows:
        row: list[str] = []
        cells = list(raw)
        col = 0
        while cells or col in carry:
            if col in carry:
                text, left = carry[col]
                row.append(text)
                if left <= 1:
                    del carry[col]
                else:
                    carry[col] = (text, left - 1)
                col += 1
                continue
            text, rs, cs = cells.pop(0)
            for _ in range(cs):
                row.append(text)
                if rs > 1:
                    carry[col] = (text, rs - 1)
                col += 1
        out.append(row)
    return out


def tables(body_html: str) -> list[list[list[str]]]:
    """Every table in the description as a list of rows of cell text (spans expanded)."""
    p = _TableParser()
    p.feed(body_html or "")
    p.close()
    return [_grid(t) for t in p.tables]


def plain_text(body_html: str) -> str:
    return _text(re.sub(r"<[^>]+>", " ", body_html or ""))
