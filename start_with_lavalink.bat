@echo off
chcp 65001 > nul
title Discord Bot + Local Lavalink

echo 正在啟動本機 Lavalink 伺服器...
start "Lavalink Server" cmd /k "cd /d %~dp0lavalink && java -jar Lavalink.jar"

echo 等待 Lavalink 啟動 (8 秒)...
timeout /t 8 /nobreak > nul

echo 正在啟動 Discord Bot...
cd /d %~dp0
call conda activate discord 2>nul || call venv\Scripts\activate 2>nul
python main.py

pause
