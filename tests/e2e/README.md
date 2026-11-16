# 分享連結的端對端測試（docs/share-links.md）

用 Playwright 把 `https://www.carmall.com.tw/pages/*` 與 `https://liquimolytaiwan.github.io/*`
兩個真網域導到本機檔案（三個 repo 要放在 `~/projects/` 底下並排），跨網域行為與正式環境相同。

```bash
export PW_EXE="<Chromium 執行檔路徑>"     # 例：~/Library/Caches/ms-playwright/chromium-*/chrome-mac-arm64/…/Google Chrome for Testing
node tests/e2e/flow.js        # 流程、惡意連結、假冒訊息、舊嵌入碼相容（約 1 分鐘）
node tests/e2e/roundtrip.js   # 五個查詢器每一台車：手動選 vs 連結重開，結果 HTML 要相同（約 5 分鐘）
node tests/e2e/phone.js       # 正式站：手機分享／取消／被擋改複製／複製被擋顯示連結框
```

`require()` 的 playwright-core 路徑寫的是 Mac mini 上 npx 快取的位置，換機器要改。
不進 CI：要真瀏覽器，而且 phone.js 打的是正式站。
