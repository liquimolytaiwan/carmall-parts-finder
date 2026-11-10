# Finder data files — cross-project contract

Each finder's `data.json` is read by the browser page **and** by the blog automation
(liquimolytaiwan/carmall-blog-automation) as the fact source for "which part fits my
bike" articles — the same arrangement carmall-ngk-finder already has, where renaming
vehicles once broke the blog's nickname table and two published articles. Treat field
names and the brand/model strings as an API: add fields freely, do not rename or repurpose.

## `filters/data.json` — Champion air filters

```jsonc
{
  "generated": "2026-11-10T03:58:00Z",        // UTC build time
  "source": "CarMall Champion 空氣芯商品頁之車種對照表",
  "category_url": "https://www.carmall.com.tw/categories/brandlist/champion",
  "stats": { "products": 56, "rows": 202, "skipped": 0 },
  "products": [{
    "sku": "CP-CAF3510",                       // join key; the variant SKU on CarMall
    "product_id": 73491234,
    "title": "【Champion台灣代理】Yamaha TMAX530/560 12-24右傳動空氣芯 Air Filter",
    "url": "https://www.carmall.com.tw/products/…",
    "price": 600.0,
    "qty": 0,                                  // may be null
    "available": false,
    "oe": "59C-15408-00",                      // OEM part number from the description, may be null
    "position": "右傳動空氣芯"                  // 主空氣芯 | 空氣芯 | 傳動空氣芯 | 左傳動空氣芯 | 右傳動空氣芯
  }],
  "brands": [{
    "name": "YAMAHA",                          // upper-cased as written in the product tables
    "models": [{
      "name": "TMAX 530 ABS",                  // exactly as written in the product tables
      "fits": [                                // every part for this bike, main filter first
        { "sku": "CP-CAF3511", "years": ["2017-2019"] },
        { "sku": "CP-CAF3509", "years": ["2012-2016"] }
      ]
    }]
  }]
}
```

- **Several fits on one model are different parts, not alternatives** (a TMAX takes a main
  filter plus left and right transmission filters). Group or label by `position`.
- `years` entries are `YYYY-YYYY`, `YYYY-` (open-ended), `YYYY`, or the raw text when the
  table used a format the build could not read (the build log says so). Empty = no year given.
- `position` comes from the product **title**; the brand/model/year come from the table in
  the product **description**. Both are hand-maintained on CarMall.

## `tires/data.json` — ARISUN motorcycle tyres

Tyres are sold **by size**, so this file has a different shape from the two above: no
`products`/`fits`/`sku` join (ARISUN size variants have no SKU). Each bike carries its stock
front and rear size and, already worked out by `tools/build_tires.py`, which tyres to sell
for each — the page and the blog render these lists as they are, they don't re-derive them.

```jsonc
{
  "generated": "2026-11-10T05:13:40Z",
  "source": "CarMall ARISUN 輪胎商品頁之常見車款尺寸對照表",
  "category_url": "https://www.carmall.com.tw/categories/brandlist/arisun",
  "stats": { "products": 4, "rows": 108, "models": 23, "skipped": 0, "carried": 0, "gone": 0 },
  "offers": [{                                 // one per sellable variant, keyed by variant_id
    "variant_id": 89888914,
    "product_id": 72972502,
    "kind": "single",                          // single | install | set
    "title": "ARISUN SK1｜全天候半熱熔胎",
    "url": "https://www.carmall.com.tw/products/…?variant=89888914",
    "price": 1900.0, "qty": 5, "available": true,
    "line": "SK1",                             // tyre model; a set has "RS01+RS02" (null if its title has no code)
    "type": "全天候半熱熔胎",                   // 胎款, may be null
    "size": "110/70-12",                       // single/install only (sets have front/rear instead)
    "position": null,                          // single/install only: 前輪 | 後輪 | null = either wheel
    "choose": ["110/70-12"],                   // single/install only: option values to click on the page
    "install": 90612401,                       // single only: its 合作車行安裝 twin's variant_id
    "caveat": "本系列以賽道競技…",              // optional, quoted from the product page
    "compare_at": 4300.0,                      // optional, only when above price
    "front": "120/70-13", "rear": "130/70-13", // set only
    "sku": "ARISUN RS01+RS02"                  // only when the variant has one
  }],
  "brands": [{
    "name": "YAMAHA",                          // upper-cased as written in the product tables
    "models": [{
      "name": "NMAX",                          // exactly as written in the product tables
      "front": [{ "size": "110/70-13", "tyres": [89888917], "listed_by": [72972502, 73490813] }],
      "rear":  [{ "size": "130/70-13", "tyres": [89888919, 89891515], "listed_by": [72972502, 72973329, 73490813] }],
      "sets":  []                              // variant_ids of sets whose front AND rear both match
    }]
  }]
}
```

- `tyres` are `single` offers only, road tyres before track ones (those with a `caveat`).
  An `install` offer is never listed on its own — reach it through a single's `install`.
- More than one entry in `front` or `rear` means two product tables disagree on that bike's
  size; show both and tell the customer to read the tyre's sidewall.
- `listed_by` = the product ids whose table lists that bike at that size. A bike listed only
  by a product that leaves the store (AEON STR 250/300 are only on the set page) drops out.
- **`?variant=` in `url` does not preselect the size**: CarMall's product page ignores it
  (checked 2026-11-10). Say which option to pick (`choose`) instead of implying it is chosen.
- The tables carry no model years, and the product pages call them 常見車款尺寸對照 —
  never present a fit as guaranteed; tell the customer to check the size on the sidewall.
