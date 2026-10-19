# 呱呱 Discord Bot

> 由 [melvin0kuo](https://github.com/melvin0kuo) 開發的多功能 Discord 機器人
> **discord.py 2.7** · **Lavalink 4.2** · **Gemini 2.0 Flash**

---

## 功能一覽

| 模組 | 功能 |
|------|------|
| 🤖 **AI 對話** | Gemini 2.0 Flash 驅動，DM / 提及 / 回覆皆可觸發，含 prompt injection 防護 |
| 🎵 **音樂播放** | YouTube · SoundCloud · Bandcamp；循環、隨機、歷史；本機 Lavalink |
| 🧠 **對話記憶** | SQLite 持久化每位用戶的對話歷史、摘要與主題洞察 |
| 👤 **用戶管理** | 個人資料、標籤系統、互動記錄 |
| 🔄 **熱重載** | `DEV_MODE=True` 時，`.py` 儲存後 1.5 秒內自動重載 |

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

LM Studio 可使用未啟用驗證的本機伺服器；設定 `DEFAULT_LLM_TYPE=local`、
`LMSTUDIO_API_URL=http://localhost:1234` 及 `LMSTUDIO_MODEL` 即可。
啟用驗證時另設定 `LMSTUDIO_API_KEY`。動態載入模型使用 LM Studio 原生 v1 管理 API。

### 3. 建立 `.env`

在專案根目錄建立 `.env`，至少填入：

```env
DISCORD_TOKEN=your_discord_bot_token
GEMINI_API_KEY=your_gemini_api_key
```

其餘選填項目參考 [`config.py`](config.py)。

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

設定檔位於 [`Lavalink/application.yml`](Lavalink/application.yml)，預設值：

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

若本機 Lavalink 無法使用，Bot 會自動從 [lavalink.darrennathanael.com](https://lavalink.darrennathanael.com) 抓取公開伺服器，並依延遲排序自動切換。

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

[MIT](LICENSE)
