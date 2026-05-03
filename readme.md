# 呱呱 Discord Bot

> 由 [melvin0kuo](https://github.com/melvin0kuo) 開發的多功能 Discord 機器人
> **discord.py 2.7** · **Lavalink 4.2** · **Gemini 2.0 Flash**

---

## 功能一覽

| 模組 | 功能 |
|------|------|
| 🤖 **AI 對話** | Gemini 2.0 Flash 驅動，DM / 提及 / 回覆皆可觸發，含 prompt injection 防護 |
| 🎵 **音樂播放** | YouTube · SoundCloud · Bandcamp；循環、隨機、歷史；Lavalink 伺服器自動切換 |
| 🧠 **對話記憶** | SQLite 持久化每位用戶的對話歷史、摘要與主題洞察 |
| 👤 **用戶管理** | 個人資料、標籤系統、互動記錄 |
| 🔄 **熱重載** | `DEV_MODE=True` 時，`.py` 儲存後 1.5 秒內自動重載 |

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

### 3. 建立 `.env`

在專案根目錄建立 `.env`，至少填入：

```env
DISCORD_TOKEN=your_discord_bot_token
GEMINI_API_KEY=your_gemini_api_key
```

其餘選填項目參考 [`config.py`](config.py)。

### 4. 安裝 Java 17+

| 系統 | 安裝方式 |
|------|---------|
| Windows | 至 [Adoptium](https://adoptium.net/) 下載 Temurin 21 LTS |
| Ubuntu / Debian | `sudo apt install openjdk-21-jre` |
| macOS | `brew install openjdk@21` |

### 5. 啟動

#### 方式 A — 一鍵啟動（推薦）

```bash
# Windows
start_with_lavalink.bat
```

腳本會先在新視窗中啟動 Lavalink，等待 8 秒後再啟動 Bot。

#### 方式 B — 分別啟動

```bash
# 終端 1：啟動 Lavalink
cd lavalink
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
│   ├── lavalink_manager.py              # Lavalink 伺服器自動探索 & 切換
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
| `/switch_lavalink` | 手動切換伺服器 |
| `/reconnect_lavalink` | 重新連接 |
| `/update_servers` | 從網路更新伺服器清單 |

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

設定檔位於 [`lavalink/application.yml`](lavalink/application.yml)，預設值：

```yaml
server:
  port: 2333

lavalink:
  server:
    password: "youshallnotpass"
```

若修改密碼，需同步更新 `.env` 中的 `LAVALINK_PASSWORD`。

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
