# 呱呱 Discord Bot

> 由 [melvin0kuo](https://github.com/melvin0kuo) 開發的多功能 Discord 機器人
> **discord.py 2.7** · **Lavalink 4.2** · **LM Studio / Gemini**

---

## 功能一覽

| 模組 | 功能 |
|------|------|
| 🤖 **AI 對話** | LM Studio 本機模型或 Gemini，DM / 提及 / 回覆皆可觸發，含 prompt injection 防護 |
| 🎵 **音樂播放** | YouTube · SoundCloud · Bandcamp；循環、隨機、歷史；本機 Lavalink |
| 🧠 **對話記憶** | SQLite 持久化每位用戶的對話歷史、摘要與主題洞察 |
| 👤 **用戶管理** | 個人資料、標籤系統、互動記錄 |
| 🔄 **熱重載** | `DEV_MODE=True` 時，`.py` 儲存後 1.5 秒內自動重載 |

## 情境式網路搜尋

在文字頻道提及機器人，例如：

- `@呱呱 台北車站附近有什麼午餐？每人預算 300 元，幫我找兩家。`
- `@呱呱 查一下鼎泰豐信義本店的地址和營業時間，附來源。`
- `@呱呱 那附近有素食嗎？`（可沿用近期對話已提供的地點）

模型會視需求呼叫搜尋或網頁閱讀工具，再以繁體中文整理並引用來源。詢問「附近吃什麼」但未提供地點時，會先追問城市或區域；家常料理與一般閒聊不必搜尋。
餐廳、店家與營業時間問題優先使用 SerpApi Google Maps 結構化結果，核對分店地址與營業狀態；永久／暫停營業列為不可推薦，今日休息不代表永久停業。Maps 要求略過供應商舊快取，本機結果快取兩分鐘；一般 Google 網頁快取十分鐘並保留來源日期。未設定金鑰、額度不足或服務失敗時改用免費 DuckDuckGo，普通網頁的店家狀態標為未確認。本機模型每輪最多三次網頁工具，隨後依已有結果作答。搜尋失敗、價位不明或無法確認營業狀態時會說明限制；搜尋結果不能保證即時空位或現在營業。

## 閱讀頻道附件

本機模型回覆達單次輸出上限時，會自動接續最多兩次，並持續以 Discord 多則訊息顯示；仍達上限會明確提示回覆「繼續」。續寫不會執行工具操作。對話接近模型上下文上限時，會嘗試移除較早歷史後續寫，仍無法容納則提示另開對話。

回覆同一頻道中含附件的訊息，輸入 `@呱呱 請摘要這份文件`；也可以在提問時直接附上檔案。
支援 TXT、Markdown、CSV、JSON 等文字檔、圖片、PDF、DOCX 和 XLSX。
機器人需要有該頻道的讀取訊息與歷史訊息權限，且只讀取本次訊息及明確回覆的附件，不會自行搜尋整個頻道。

每次最多 4 個附件，每檔最多 10 MB；每份文件最多擷取 200,000 字元。長文件會以每段 4,000 字元逐段摘要，再合併，提供給回答模型的文件內容合計最多 12,000 字元。
PDF 最多擷取前 200 頁；XLSX 最多前 20 個工作表、每表前 5,000 列與 50 欄，公式使用檔案已儲存的計算結果。
掃描 PDF 及混合 PDF 中沒有文字層的頁面，會交由支援圖片的本機模型辨識，每份最多 30 個掃描頁。辨識結果可能有誤，關鍵數字請核對原件。超出範圍、加密、損壞或無法完整摘要時會明確說明；不會把未完成的讀取宣稱為全文總結。

## 正式運行與本地記憶

`DEV_MODE=False` 為預設值，正式運行不監控原始碼熱重載。開發時可自行設為 `True`。
音樂操作面板、音量、搜尋選單和播放清單載入會檢查操作者是否仍在同一語音頻道，以及播放器是否仍有效；舊面板不能操作新播放器。
本機聊天的語義記憶使用 LM Studio 的 `text-embedding-nomic-embed-text-v1.5`，須先下載該模型；索引獨立存於 `vector_db/local-nomic-v1/`，不混用舊 Gemini 向量。記憶寫入在背景進行，失敗有日誌且不阻止聊天。
本機長對話以模型回報的輸入 token 數檢查容量，預留輸出空間；超限時摘要較早的對話，不裁切本輪問題。token 計數使用一次最多 1 token 的本機預檢請求，不會執行工具。
店家搜尋回答會移除未出現在來源中的 Markdown 連結與未能由來源支持的完整台灣地址；此檢查不等於驗證所有價格、評價及營業狀態。

## 自然語言音樂操作

加入伺服器的語音頻道後，在文字頻道 **@機器人** 即可用一般對話點歌或控制播放：

- `@呱呱 幫我放周杰倫的晴天`
- `@呱呱 來點適合讀書的爵士樂`
- `@呱呱 暫停一下`、`@呱呱 繼續播放`、`@呱呱 下一首`
- `@呱呱 音量設成 30`、`@呱呱 小聲一點`
- `@呱呱 看一下播放佇列`、`@呱呱 開啟單曲循環`
- `@呱呱 停止播放並離開`

支援播放、加入語音、暫停、繼續、跳過、上一首、停止、佇列、正在播放、音量、循環、隨機與自動播放。
Gemini 與 LM Studio 共用同一套音樂工具；本機模型需要支援工具呼叫。
模型根據語意選擇操作，否定、假設與歌曲閒聊應保持一般對話；缺少歌名或語意不明時會先詢問。

每則訊息最多執行一項音樂操作。只有明確提及機器人且位於語音頻道的用戶才會取得操作工具；
執行時重新確認語音狀態，並拒絕操作機器人在其他語音頻道的播放器。
尚未加入語音頻道時，點歌會提示先加入；私訊、未直接提及機器人或音樂模組未載入時，也會說明對應限制。
所有操作沿用既有音樂指令的權限檢查與冷卻時間，實際播放結果以音樂指令的回覆為準。

所有擷取路徑都失敗或音軌卡住時會停止自動接播，同一輪失敗只通知一次；重新點歌可再次嘗試。
YouTube 先使用本機 yt-cipher 協助解析；若仍載入失敗，會用 yt-dlp + Deno 對**同一支影片**重試一次。
備援會驗證實際音訊資料後交給 Lavalink 播放，不會自動換成翻唱或其他歌曲。
兩條路徑都失敗時，會停止接播，並嘗試列出最多三個 SoundCloud 候選供使用者選擇。
停止、離開或開始另一首歌後，尚在處理中的舊備援不會自行恢復播放。
推薦歌曲不會在搜尋完成時提前宣告播放，播放通知會等待音軌開始事件並確認目前音軌仍有效。
語音連線會處理 Discord 事件先後順序，逾時僅清理該伺服器的播放器，不會關閉整個本機節點。
佇列播完且沒有接播歌曲時，閒置 30 秒會自動離開；可用 `MUSIC_IDLE_TIMEOUT` 調整秒數。
重新點歌會取消離開計時，並核對 Lavalink 的實際播放器狀態，必要時重新加入語音。
自動推薦預設關閉，可用 `/autoplay` 開啟；既有伺服器明確儲存的開關設定會保留。
本機模型未呼叫音樂工具卻宣稱已執行時，會重新要求執行一次；仍未執行則明確提示，不會假稱已播放。

---

## 技術棧

```
discord.py  2.7.1   —  Discord API 客戶端
wavelink    3.5.2   —  Lavalink Python 封裝（含 DAVE 語音加密）
Lavalink    4.2.2   —  Java 音頻串流後端（本機自托管）
Gemini API          —  google-generativeai（LLM）
SQLite              —  用戶資料 & 對話記憶
```

---

## 環境需求

Windows 的 `start_with_lavalink.bat` 會準備可攜式 Deno、yt-dlp、yt-cipher 與 EJS，
放在忽略提交的 `.runtime/` 中；首次安裝需要連線下載官方 release 與固定版本原始碼。
本機 cipher 只監聽 `127.0.0.1:8001`，由機器人啟動與關閉。
安裝輸出位於 `.runtime/youtube-setup.log`，cipher 執行記錄位於 `.runtime/youtube-cipher.log`。
可用 `YOUTUBE_CIPHER_ENABLED=false` 停用自動啟動 cipher、
`YOUTUBE_FALLBACK_ENABLED=false` 停用 yt-dlp 備援。
YouTube 行為仍可能改變，這些工具不保證所有影片都能播放。

| 需求 | 版本 |
|------|------|
| Python | 3.10 以上 |
| Java | 17 以上（用於 Lavalink） |
| 作業系統 | Windows / Linux / macOS |

---

## 快速開始

### 1. 複製專案

```bash
git clone https://github.com/melvin0kuo/DISCORD-BOT.git
cd DISCORD-BOT
```

### 2. 安裝 Python 依賴

```bash
# Conda（推薦）
conda create -n discord python=3.11
conda activate discord

# venv 也可以
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 開發驗證

```bash
pip install -r requirements-dev.txt
python -m pytest
python -m ruff check main.py config.py cogs utils tests --select F821,F823,E9
```

自動測試使用暫存資料庫與本機測試伺服器，不需要 Discord Token、Gemini API 或正在運行的 Lavalink。
根目錄與 `test/` 中的舊診斷腳本需要模型或外部服務，不屬於自動測試套件。

### 本機聊天與語義點歌（LM Studio）

安裝 [LM Studio](https://lmstudio.ai/download) 並開啟一次，再用 PowerShell 下載模型：

```powershell
& "$env:USERPROFILE\.lmstudio\bin\lms.exe" get qwen/qwen3.5-9b --gguf --yes
```

在 `.env` 設定：

```env
DEFAULT_LLM_TYPE=local
ENABLE_FALLBACK=false
LMSTUDIO_API_URL=http://127.0.0.1:1234
LMSTUDIO_MODEL=discord-local
LMSTUDIO_MODEL_KEY=qwen/qwen3.5-9b
LMSTUDIO_CONTEXT_LENGTH=32768
LMSTUDIO_ENABLE_THINKING=false
```

`LMSTUDIO_MODEL_KEY` 是已下載的模型名稱；`LMSTUDIO_MODEL` 是提供給機器人的固定 API 識別名稱。
可依硬體改用其他支援工具呼叫的模型。本機部署使用 Qwen3.6 27B Q6_K、32768 context、單一並行請求，使用 RTX 5090 32GB。啟動腳本會在現有模型上下文不足時重新載入；閱讀新附件時，優先提供該文件並省略舊對話歷史，避免重複內容塞滿輸入。
啟用 API 驗證時，另將 LM Studio 的 Token 填入 `LMSTUDIO_API_KEY`，不要提交 `.env`。

執行 `start_with_lavalink.bat` 會啟動本機 API、載入模型並啟動音樂服務與機器人；
若模型已載入會直接沿用。API 僅監聽 `127.0.0.1:1234`。
本機聊天與語義理解不消耗 Gemini 額度；網路搜尋及線上音樂來源仍需要網路。
預設停用模型思考以降低聊天延遲，使用 LM Studio 0.4.8 以上支援的 `reasoning_effort` 參數。

### 3. 建立 `.env`

在專案根目錄建立 `.env`，至少填入：

```env
DISCORD_TOKEN=your_discord_bot_token
GEMINI_API_KEY=your_gemini_api_key
```

其餘選填項目參考 [`config.py`](../config.py)。

### 4. 準備本機音樂服務

Windows 啟動腳本會自動下載並驗證可攜式 Java 21，以及 YouTube 插件。
Java 放在專案的 `.runtime/`，不修改系統 PATH；插件放在 `Lavalink/plugins-local/`。
這些執行檔不會提交到 GitHub。已有 Java 的其他系統可執行：

```bash
python setup_local_lavalink.py
```

| 系統 | 安裝方式 |
|------|---------|
| Windows | 啟動腳本自動準備可攜式 Temurin 21 JRE |
| Ubuntu / Debian | `sudo apt install openjdk-21-jre` |
| macOS | `brew install openjdk@21` |

### 5. 啟動

#### 方式 A — 一鍵啟動（推薦）

```bash
# Windows
start_with_lavalink.bat
```

腳本會先準備執行環境，再啟動 Bot。Bot 會在背景啟動本機 Lavalink，
等待 API 與 WebSocket 就緒後才啟用音樂功能；已有正常運行的本機服務時直接沿用。
可透過 `DISCORD_BOT_PYTHON` 指定 Python 路徑；預設優先使用 Conda 的 `discord` 環境。

#### 方式 B — 分別啟動

```bash
# 終端 1：已有 Java 時可手動啟動 Lavalink
cd Lavalink
java -jar Lavalink.jar

# 終端 2：確認 Lavalink 就緒後啟動 Bot
python main.py
```

---

## 目錄結構

```
DISCORD-BOT/
├── main.py                              # 入口點、EnhancedBot 定義
├── config.py                            # 環境變數統一讀取
├── requirements.txt
│
├── cogs/
│   ├── conversation.py                  # AI 對話觸發 & 串流回應
│   ├── music.py                         # 音樂播放（wavelink + MusicQueue）
│   ├── slash_commands.py                # 額外斜線指令 & Lavalink 管理
│   ├── user_management.py               # 用戶個人資料指令
│   └── conversation_memory_commands.py  # 記憶管理指令
│
├── utils/
│   ├── llm_handler.py                   # Gemini API 呼叫 & 對話歷史
│   ├── lavalink_manager.py              # 本機 Lavalink API 驗證與狀態
│   ├── local_lavalink.py                # 可攜式 Java、插件安裝與程序管理
│   ├── user_database.py                 # SQLite 用戶資料存取
│   ├── conversation_memory.py           # 對話持久化 & 摘要
│   └── reloader.py                      # watchdog 熱重載
│
└── lavalink/
    ├── Lavalink.jar                     # Lavalink 4.2.2 伺服器
    └── application.yml                  # Lavalink 設定（port 2333）
```

---

## Bot 指令

### 音樂

| 指令 | 說明 |
|------|------|
| `/join` | 加入語音頻道 |
| `/play <關鍵字或 URL>` | 搜尋並播放 |
| `/nowplaying` | 顯示目前播放資訊 |
| `/queue` | 查看播放清單 |
| `/skip` / `/back` | 下一首 / 上一首 |
| `/loop` | 切換循環模式 |
| `/shuffle` | 隨機播放 |
| `/volume <0–100>` | 調整音量 |
| `/stop` | 停止並離開頻道 |
| `/search <關鍵字>` | 搜尋並手動選擇歌曲 |
| `/lyrics` | 查看歌詞 |
| `/history` | 播放歷史 |

### Lavalink 管理

| 指令 | 說明 |
|------|------|
| `/lavalink_status` | 查看目前節點狀態 |
| `/switch_lavalink` | 重新連接本機節點（相容舊指令） |
| `/reconnect_lavalink` | 重新連接 |
| `/update_servers` | 重新檢查本機節點狀態 |

### 用戶系統

| 指令 | 說明 |
|------|------|
| `/設定個人資料` | 設定暱稱、簡介 |
| `/個人資料` | 查看個人資料 |
| `/添加標籤` | 新增自訂標籤 |
| `/查看記憶` | 查看機器人儲存的對話摘要 |
| `/導出對話記憶` | 匯出完整對話歷史 |

### 管理員前綴指令

| 指令 | 說明 |
|------|------|
| `!reload_config` | 重新載入 `.env` & `config.py` |
| `!reload_cogs` | 重新載入所有 Cog |
| `!full_reload` | 完整重載（Config + Cogs + Presence） |
| `!sync_commands` | 同步斜線指令至 Discord |

---

## Lavalink 設定

設定檔位於 [`Lavalink/application.yml`](../Lavalink/application.yml)，預設值：

```yaml
server:
  port: 2333
  address: 127.0.0.1

lavalink:
  server:
    password: "youshallnotpass"
```

Bot 僅連接本機節點，不抓取公共節點清單，也不沿用舊公共節點快取。
`.env` 可設定 `LAVALINK_URI=http://127.0.0.1:2333` 與 `LAVALINK_PASSWORD`；
Bot 自動啟動服務時會將連線位址、連接埠和密碼同步傳入 JVM。
手動啟動 Java 時，需確保設定檔的連接埠和密碼與 `.env` 相同。
啟動問題可查看 `Lavalink/local-runtime.log`；播放器需保持外網連線以取得歌曲。

### 公開伺服器自動備援

目前主要使用本機 Lavalink。若無法連線，請先檢查 Java、安裝紀錄與 `Lavalink/local-runtime.log`，不要依賴未驗證的公開節點。

---

## 開發模式

在 `.env` 中加入：

```env
DEV_MODE=True
```

任何 `.py` 檔案儲存後，Bot 會在 1.5 秒內自動重載，無需手動重啟。

---

## 常見問題

**Q：斜線指令沒有出現？**
執行 `!sync_commands`，等候 1–15 分鐘讓 Discord 全球同步完成。

**Q：機器人加入語音頻道後馬上離開？**
公開 Lavalink 伺服器可能無法連接至你的 Discord 語音區域。強烈建議使用本機 Lavalink（執行 `start_with_lavalink.bat`）。

**Q：YouTube 無法播放？**
確認 `lavalink/application.yml` 的 `plugins.youtube.enabled: true`，並確認 Lavalink 啟動時已成功下載 `youtube-plugin`（會顯示在啟動 log 中）。

---

## 版本紀錄

| 日期 | 更新內容 |
|------|---------|
| 2025-05 | 升級 wavelink 3.5.2、discord.py 2.7.1、Lavalink 4.2.2；加入 DAVE 語音加密；修正節點堆積 & 節點健康檢查 bug |
| 2025-05 | 重寫 Lavalink 伺服器管理器（自動爬取 darrennathanael.com + 智能切換）；新增對話記憶系統；新增用戶管理系統 |

---

## License

[MIT](../LICENSE)
# 對話安全與處理狀態

搜尋預設優先使用 SerpApi，在本機 `.env` 設定 `SERPAPI_API_KEY` 後重啟即可啟用。店家查詢使用 Google Maps，其他查詢使用 Google 網頁；未設定、查無結果、逾時或 API 失敗時自動切換 DuckDuckGo。HTTP 401／403／429 後暫停 SerpApi 一小時再試；這是錯誤冷卻，並非精確追蹤帳戶帳期。成功結果最多快取 256 組，店家兩分鐘、一般網頁十分鐘；每次最多五筆，Maps 可能包含評分與評論數，但不代表評論是近期發布。程式不會購買方案或啟用自動續費，實際用量請查看 SerpApi 後台。

Discord 應用擁有者由 `bot.is_owner` 驗證；顯示名稱、自稱管理員或引用他人的訊息都不能取得擁有者權限。受保護的實作資訊僅接受已驗證擁有者在私訊詢問，機器人不提供讀取原始碼或任意執行程式的工具。金鑰及密碼即使在擁有者私訊也會遮蔽，工具參數含已知機密時會阻止傳送。

所有回答在發送前先檢查，處理期間顯示記憶檢索、文件整理、搜尋、網頁讀取或音樂操作等實際階段。文字檢查與模型指示只能降低 prompt injection 風險，不能保證攔下所有改寫／編碼攻擊；不要把機密放入系統提示或用戶記憶。此功能無法隱藏公開 GitHub 儲存庫內的程式碼，需要保密時應另將儲存庫設為私人。
