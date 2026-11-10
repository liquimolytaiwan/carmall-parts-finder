# carmall-parts-finder

CarMall「車型對照查詢」：一個整合入口頁（先選商品類別 → 再進該類查詢器），以及來令片、空氣芯、輪胎三個新查詢器。
既有的雨刷（liquimolytaiwan/carmall-wiper-finder）與火星塞（liquimolytaiwan/carmall-ngk-finder）查詢器留在各自的 repo，入口頁連過去。

- GitHub 帳號：liquimolytaiwan（`gh auth switch -u liquimolytaiwan`）；commit email `manhowtrading@gmail.com`
- 適應表的事實來源是 CarMall 商品頁內文的表格 —— 表格版型是 Jerry 手動維護的介面契約，解析失敗要大聲失敗、保留上一份資料，不要靜默少車

## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues (`gh` CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root, created lazily. See `docs/agents/domain.md`.
