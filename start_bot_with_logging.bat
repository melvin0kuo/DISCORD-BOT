@echo off
cd /d "%~dp0"
call "%~dp0start_with_lavalink.bat" --no-pause >> "%~dp0bot_log.txt" 2>&1
exit /b %ERRORLEVEL%
