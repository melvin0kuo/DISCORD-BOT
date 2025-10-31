# DISCORD-BOT

這是一個由 [melvin0kuo](https://github.com/melvin0kuo) 開發的 Discord 機器人。

## 專案描述

本專案旨在提供一個具備多功能的 Discord 機器人，包含音樂播放、日誌記錄和設定檔管理等核心模組。

## 主要功能

* **音樂播放 (Music Playback):** 整合 [Lavamusic](https://github.com/itzappu/lavamusic) (作為 Lavalink 伺服器) 提供高品質的音樂播放功能。
* **日誌記錄 (Logging):** 詳細記錄機器人的運行狀態與事件，方便追蹤與除錯。
* **設定檔管理 (Configuration Management):** 允許使用者輕鬆配置機器人的各項參數。
* **可擴展性:** 專案結構設計良好，方便未來新增更多客製化功能。

## 技術棧

* **程式語言:** Python
* **主要函式庫:** Discord.py
* **子模組 (Submodules):**
    * [Lavamusic](https://github.com/itzappu/lavamusic) (Lavalink 伺服器)
    * [Triton](https://github.com/triton-lang/triton) (Python 函式庫)

## 安裝指南 (Installation)

本專案同時依賴 Python 函式庫和 Java 伺服器 (Lavamusic)。

1.  **複製專案 (Clone the repository):**

    由於專案包含子模組 (submodules)，clone 時請務必加上 `--recursive` 參數：
    ```bash
    git clone --recursive [https://github.com/melvin0kuo/DISCORD-BOT.git](https://github.com/melvin0kuo/DISCORD-BOT.git)
    cd DISCORD-BOT
    ```
    *(如果你 clone 時忘記加 `--recursive`，請在 `cd DISCORD-BOT` 後執行 `git submodule update --init --recursive` 來補下載子模組)*

2.  **安裝 Python 依賴 (Install Python dependencies):**

    ```bash
    # 安裝主專案的依賴 (例如 discord.py)
    pip install -r requirements.txt
    
    # 安裝 Triton 子模組 (它是一個 Python 函式庫)
    cd triton/python
    pip install .
    cd ../..
    ```

3.  **設定並運行 Lavamusic (Lavalink 伺服器):**

    `Lavamusic` 是一個 Java 專案 (Lavalink 伺服器)，它**必須被獨立運行**，你的 Python 機器人才能連線到它。

    *(請在此處根據 Lavamusic 的文件，填寫 build 和 run 的步驟)*

    一個可能的流程 (範例)：
    * 你需要安裝 Java (JDK)。
    * (你可能需要 build 它，或是下載 pre-built 的 `.jar` 檔)
    * 你需要一個 `application.yml` 設定檔來設定 Lavalink。
    * 使用 `java -jar Lavamusic.jar` 來啟動它。

4.  **設定環境變數 (Set up environment variables):**

    * 建立一個 `.env` 檔案。
    * 填入必要的設定。**特別注意：** 你必須填入 Lavalink 伺服器的連線資訊。

    ```
    # 你的 Discord 機器人 Token
    DISCORD_TOKEN=你的BOT_TOKEN
    
    # 根據步驟 3 設定的 Lavalink 伺服器資訊
    LAVALINK_HOST=localhost
    LAVALINK_PORT=2333
    LAVALINK_PASSWORD=youshallnotpass
    ```

## 使用方法 (Usage)

1.  **啟動 Lavalink 伺服器** (請參照安裝指南步驟 3)。
2.  **啟動 Python 機器人**:
    ```bash
    python main.py
    ```
之後，你就可以根據機器人的指令在 Discord 中與其互動。

## 如何貢獻 (Contributing)

歡迎任何形式的貢獻！如果你有任何建議或想修復錯誤，請隨時提出 Pull Request 或建立 Issue。

## 授權 (License)

MIT License
