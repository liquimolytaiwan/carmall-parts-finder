"""Shared CarMall (Cyberbiz) storefront access for the finders in this repo.

Every finder here takes its fitment data from the product pages themselves: Jerry keeps
a vehicle table in each product's description, so the product page is the source of
truth and the table layout is the interface contract between him and this code.

Two public, keyless JSON endpoints are enough:
    /categories/brandlist/<brand>.json?page=N  -> product summaries, 25 per page
    /products/<handle>.json                   -> full product incl. body_html and variants

Neither sends a CORS header, so data is baked in at build time, not fetched by the browser.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

SITE = "https://www.carmall.com.tw"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")
PACE = 0.3          # seconds between requests; ~60 products per brand at most
MAX_PAGES = 40      # hard stop in case the category endpoint ever ignores ?page
_last = [0.0]


class FetchError(Exception):
    pass


def get(url: str, retries: int = 4) -> str:
    """GET with pacing and incremental backoff. A 404 is final — retrying it only makes a
    renamed product handle take minutes to report (seen on the wiper finder)."""
    last: Exception | None = None
    for attempt in range(retries):
        wait = PACE - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise FetchError(f"404 {url}") from e
            last = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
        if attempt < retries - 1:
            time.sleep(3 * (attempt + 1))
    raise FetchError(f"{url}: {last}")


def category_products(brand_handle: str, fetch=get) -> list[dict]:
    """All product summaries in a brand category, following ?page until an empty page."""
    seen: dict[int, dict] = {}
    for page in range(1, MAX_PAGES + 1):
        url = f"{SITE}/categories/brandlist/{urllib.parse.quote(brand_handle)}.json?page={page}"
        items = json.loads(fetch(url))
        new = [x for x in items if x["id"] not in seen]
        if not new:
            break
        for x in new:
            seen[x["id"]] = x
    else:
        raise FetchError(f"category {brand_handle}: still returning new items after {MAX_PAGES} pages")
    return list(seen.values())


def product_detail(summary: dict, fetch=get) -> dict:
    path = summary.get("url") or ("/products/" + summary["full_handle"])
    return json.loads(fetch(SITE + urllib.parse.quote(path, safe="/-_%.") + ".json"))


def offer(detail: dict, variant: dict | None = None) -> dict:
    """Price/stock/link fields shown on a buy card. One variant per product for most
    brands; tyres pass the variant for the size being sold."""
    v = variant or (detail.get("variants") or [{}])[0]
    url = SITE + (detail.get("url") or ("/products/" + detail.get("handle", "")))
    if variant and variant.get("id"):
        url += "?variant=" + str(variant["id"])
    return {
        "product_id": detail.get("id"),
        "title": clean_title(detail.get("title") or ""),
        "url": url,
        "sku": (v.get("sku") or "").strip(),
        "price": v.get("price") if v.get("price") is not None else detail.get("price"),
        "qty": v.get("inventory_quantity"),
        "available": bool(v.get("available", detail.get("available"))),
    }


def clean_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip()
