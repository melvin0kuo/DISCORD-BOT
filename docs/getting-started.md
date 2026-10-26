# 第一次部署

[← 回首頁](../readme.md)

## 1. 下載與開啟

Windows 10/11 x64 安裝 Python 3.11 或 3.12。從 GitHub Download ZIP 下載並**解壓縮**，或使用 Git clone。雙擊 `setup.bat`，本機精靈會在瀏覽器開啟。缺少 Python 時，啟動器可引導使用官方 WinGet 套件安裝；安裝後重新執行。不要在 ZIP 預覽視窗內直接執行。

精靈使用隨機本機連接埠，只監聽 `127.0.0.1`。網址內含暫時工作階段，請勿分享。金鑰不放入 URL，不載入第三方網頁資源；點選官方入口才開啟對應網站。

## 2. 安裝環境

第一步按「建立並安裝環境」。建立 `.bot-venv`，安裝 `requirements-bot.txt`。需要 PyPI 網路連線與可用磁碟空間；重試不會刪除資料庫或重建系統 Python。原本的 `requirements.txt` 保留供舊環境使用。

## 3. 建立 Discord Bot

1. 到 [Developer Portal](https://discord.com/developers/applications)，建立 Application。
2. 到 Bot 頁面取得 Token，並啟用 **Message Content Intent** 和 **Server Members Intent**。若應用需要驗證，請依 Discord 規則申請 Intent。
3. 把 **Bot Token** 填入精靈；不是 Client Secret，也不是個人 Discord Token。
4. 最後一步執行連線檢查，從紀錄複製邀請網址，選擇你可管理的伺服器。
5. 確認 Bot 能查看頻道、發訊息、讀取歷史、連線與說話；不需要 Administrator。

忘記 Token 時只能在官方平台重設；重設後舊 Token 失效，請重新填入。不要將 Token 貼到 Issue、Discord 公開頻道或 GitHub。

## 4. 選擇模型

### Gemini：較少硬體準備

到 [Google AI Studio](https://aistudio.google.com/apikey) 建立 API Key，貼入精靈。選可用的 Gemini 模型；預設 `gemini-2.5-flash`，可用性、地區、額度與計費依官方帳戶規則。精靈驗證 Key 能否查詢模型，不會代辦付費或保證對話生成額度。

### LM Studio：本機運算

1. 安裝 [LM Studio](https://lmstudio.ai/download)，開啟一次。
2. 依 RAM／VRAM 選擇支援工具呼叫的聊天模型，並在 LM Studio 自行下載。不要直接照抄他人的大型模型設定。
3. 將實際下載的模型 ID 填入精靈，提供 Bot 的別名可用 `discord-local`。預設模型 ID 只是範例；可依硬體與現有模型調整。
4. 下載並載入 `text-embedding-nomic-embed-text-v1.5`，供語義記憶使用。辨識圖片與掃描 PDF 另需聊天模型具備視覺能力。
5. 按「儲存並啟動已下載的本機模型」。既有啟動器使用 `lms` CLI，嘗試啟動本機 1234 port、以單一並行載入聊天模型。請保持 API 網址為預設值；自訂 port／API Token 時先在 LM Studio 手動啟動服務。

精靈不自動挑選、下載數 GB 模型，也不會代替你接受模型授權。模型與 context 都會消耗記憶體；載入失敗時降低模型大小／context，再重試。

## 5. 搜尋與音樂

搜尋可以不填 Key，使用 DuckDuckGo。若希望 Google 結果優先，至 [SerpApi](https://serpapi.com/users/sign_up) 申請並填入 Key；額度／方案依[官方價格頁](https://serpapi.com/pricing)。精靈不會啟用自動續費。

音樂步驟沿用現有安裝器，準備 Java、Lavalink 與音源工具。第一次較久；下載失敗時檢查網路／代理與下方紀錄再重試。串流平台可能改版、限制地區或要求登入；安裝成功不代表所有 YouTube 影片都能播放。

## 6. 檢查並啟動

先「儲存並檢查連線」，再邀請 Bot；確認沒有其他啟動腳本正在運行，最後按「啟動機器人」。查看 Discord 上線狀態並試用：

```text
@呱呱 你好
@呱呱 幫我找台北車站附近的午餐，預算 300 元
```

加入語音頻道後輸入 `/play` 測試音樂。Bot 程序紀錄位於 `data/wizard-bot.log`；精靈上顯示「已啟動程序」僅代表程序已建立，登入仍可能失敗。點「停止」只處理本精靈啟動的程序，關閉瀏覽器不會自動停止機器人。

日後再次雙擊 `setup.bat`，重新檢查／啟動即可，不需每次重裝。不要同時用精靈和舊啟動腳本啟動同一個 Bot。

## 常見問題

| 問題 | 檢查方式 |
|---|---|
| 雙擊後沒有開啟 | 在終端執行 `python setup_wizard.py`；確認 Python 3.11／3.12 與瀏覽器可用 |
| 套件安裝失敗 | 查看精靈紀錄；確認 PyPI 連線與使用 64 位元 Python；不要把錯誤中含個資或金鑰的完整紀錄公開 |
| Discord 401 | Bot Token 不正確或已被重設 |
| Privileged intents 錯誤 | 在 Discord Bot 設定啟用兩項 Intent，確認應用資格 |
| AI 429／無法回應 | 檢查模型可用性與供應商額度；本機模型檢查 LM Studio 是否載入及 API 是否開啟 |
| 聽不到音樂 | 先加入語音、檢查連線／說話權限，再看 `Lavalink/local-runtime.log` |
| 金鑰欄位是空白 | 已儲存的 Key 不回傳網頁，只顯示「已設定」。留白保留；停用時手動清空 `.env` 對應項目 |
| 檢查工具不能關閉外部 Bot | 這是刻意限制，請在原本啟動視窗自行停止 |

## 設定與資料

`.env`、`.bot-venv/`、`.runtime/`、資料庫及執行紀錄屬於本機資料。既有被 Git 追蹤的檔案不會因 `.gitignore` 自動停止追蹤，提交前務必檢查差異。更改金鑰前後不會刪除資料庫；備份請自行妥善保管。精靈不會建立對外公開的部署網站或自動開放防火牆連接埠。

## 手動安裝與其他系統

目前一鍵流程主要支援 Windows x64。Linux／macOS 可手動建立 Python 3.11／3.12 虛擬環境、安裝 `requirements-bot.txt`、準備 Java 17 以上，再依[完整功能文件](features.md)設定與執行。YouTube 工具及 LM Studio 啟動的跨平台自動化未經完整驗證。
