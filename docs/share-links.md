# 分享查詢結果的連結（2026-11-16）

Jerry 的需求：查詢器嵌在 CarMall（Cyberbiz）頁面的 iframe 裡，選好車款後網址列不會變，
結果沒辦法分享。現在選到哪台車，店面網址就跟著變；結果下方有「分享這個查詢結果」按鈕
（手機叫出系統分享選單，可直接選 LINE；電腦複製連結）。

## 連結長這樣

```
https://www.carmall.com.tw/pages/partsfinder#f=wiper&b=TOYOTA&m=COROLLA+ALTIS&y=第二代+(08-13)
https://www.carmall.com.tw/pages/wiperguide#f=wiper&b=HONDA&m=CIVIC&y=第九代+(12-17)
https://www.carmall.com.tw/pages/plugsfinder#f=plugs&b=KAWASAKI&m=ZX-6R+636cc
```

| 參數 | 意思 |
|---|---|
| `f` | 哪一個查詢器：`wiper`、`plugs`，其他就是本 repo 的資料夾名稱（`filters`、`pads`、`tires`） |
| `b` `m` `y` | 廠牌、車款、年份 —— 用**名稱**，不用選單的序號 |

**🔴 這個格式已經發出去了**（客人分享的連結、日後部落格文章的連結），改格式等於讓舊連結失效。
要改的話新舊格式都要能讀。

### 為什麼放在 `#` 後面，不放 `?` 後面

2026-11-16 在正式的 /pages/partsfinder 實測：用 `history.replaceState` 改 `?` 後面，
GA4 每改一次就多送一筆 page_view（店面有好幾個 GA 追蹤碼，一次就是好幾筆）；只改 `#` 後面一筆都沒有。
`#` 也不會送到伺服器，Cyberbiz 快取、canonical 網址都不受影響。

### 為什麼用名稱不用序號

data.json 每天重建兩次，順序會變。序號連結過幾天就指到別台車 —— 那就是賣錯零件。
名稱對不到（車款改名、下架）或對到不只一個時，**停在那一層不猜**，客人自己選剩下的。
火星塞的車款名會重複（ZX-6R、MT-03 各有兩個排氣量），所以 `m` 帶排氣量：`ZX-6R 636cc`。

## 誰負責什麼

```
查詢器 ──carmallFinderState {finder, state}──▶ 店面頁的嵌入碼（改自己的 #hash）
查詢器 ◀──carmallHost {url}──────────────────  店面頁的嵌入碼（告訴查詢器分享連結該指向哪頁）
```

- **`assets/link.js`**（本 repo）：五個查詢器共用。讀自己網址的 `#b=…&m=…&y=…` 把選單選回去、
  每次選擇後回報狀態、管分享鈕。雨刷與火星塞查詢器從本 repo 的 GitHub Pages 用 `async` 載入它 ——
  **它是選配的**：載不到時查詢器照常運作，只是沒有分享鈕。各查詢器只負責給「每一層選單的名稱怎麼算」。
- **`embed-snippet.html`**（三個 repo 各一份，內容相同，只差最上面三行設定）：貼在 Cyberbiz 自訂頁面。
  依店面網址的 `#f=…` 決定框裡開哪個查詢器、帶哪台車；收到查詢器的狀態就改店面網址；
  `f` 只能是小寫英文字母、而且只會變成 `https://liquimolytaiwan.github.io` 底下的路徑。
  本 repo 新增查詢器類別（新資料夾）**不用重貼嵌入碼**。
- **`hub.js`**：入口頁載入時通知店面清掉 `#f=…`，不然重新整理會直接跳回剛剛那個查詢器。

## 分享鈕什麼時候出現

只在「有結果」而且「知道店面網址」時出現。舊版嵌入碼不會送店面網址、iframe 也沒有分享／剪貼簿權限，
所以在舊嵌入碼底下按鈕不出現（而不是按了沒反應）。直接開 github.io 的頁面時，分享的是 github.io 自己的連結。
分享 → 失敗就複製 → 再失敗就顯示一個選好的連結框讓客人自己複製。

## 測過什麼（2026-11-16）

用 Playwright 把 `www.carmall.com.tw` 與 `liquimolytaiwan.github.io` 兩個真網域導到本機檔案，跨網域行為與正式環境相同：
- 每一台車都跑一次：手動選出結果 → 用連結重開 → 結果 HTML 完全相同（五個查詢器全部）
- 入口頁 → 查詢器 → 選車 → 店面網址 → 分享鈕複製出店面連結 → 新分頁開啟結果相同 → 回入口網址清掉
- 惡意連結（`f=//evil.com`、`../`、大寫、`javascript:`、HTML 標籤、超長值）與別的 iframe 假冒訊息都擋下
- 舊嵌入碼 + 新查詢器：高度照常、分享鈕不出現、店面網址不動

- 正式站（Jerry 貼上新嵌入碼後）：三頁 6 種連結、手機分享／取消／被擋改複製／複製被擋顯示連結框；
  選車、切換、回入口時 GA 0 筆 page_view

測試腳本在 `tests/e2e/`（怎麼跑見那裡的 README），改到 link.js 或嵌入碼就重跑 flow.js 與 roundtrip.js。

**沒測到**：iPhone Safari／LINE 內建瀏覽器的分享選單（Chromium 模擬不了），要用手機實按一次；
Meta 像素抓不到它的送出紀錄，沒有量到。
