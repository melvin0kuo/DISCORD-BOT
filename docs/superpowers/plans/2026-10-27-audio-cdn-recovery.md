# 同影片 CDN 備援恢復

證據：左右盲（1IlTeOMCNJU）在 11:59 原生播放失敗後，Lavalink 載入 loopback 備援得到 HTTP 502。當時上游狀態未記錄，不能斷言登入限制。現場重新擷取同影片已可回傳 audio/webm；舊 relay 遇單次上游錯誤即結束，沒有有限重試。

變更：連線錯誤與 429／500／502／503／504 在準備回覆前最多重試兩次。403／410 允許重取原影片音訊網址一次並更新 relay token 內的網址；所有新網址及 redirect 仍驗證 YouTube CDN 白名單。記錄狀態與次數，不記錄帶簽章的網址。已開始輸出的音訊不拼接重試，以免破壞音訊內容。

測試：模擬 503 恢復、持續失敗的三次上限、403 更新網址且沿用新網址、原 redirect／seek 測試。真實原影片透過 relay 測試首段與一 MB 位移各 4096 bytes，Lavalink 回傳 loadType=track；未進行 Discord 語音播出測試。
