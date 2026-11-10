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
