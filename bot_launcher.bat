@echo off
chcp 65001 > nul
title Discord Bot Launcher

echo Discord Bot Launcher
echo ===================
echo.
echo 1. Start bot with visible console
echo 2. Start bot hidden (background)
echo 3. View running bot processes
echo 4. Exit
echo.

:menu
set /p choice="Select an option (1-4): "

if "%choice%"=="1" goto start_visible
if "%choice%"=="2" goto start_hidden
if "%choice%"=="3" goto view_processes
if "%choice%"=="4" goto end

echo Invalid option. Please try again.
goto menu

:start_visible
echo Starting bot with visible console...
start cmd /k "start_discord_bot.bat"
goto end

:start_hidden
echo Starting bot in background...
start /b wscript.exe "run_bot_hidden.vbs"
echo Bot started in background.
goto end

:view_processes
echo.
echo Current Python processes:
tasklist /fi "imagename eq python.exe"
echo.
echo Current CMD processes:
tasklist /fi "imagename eq cmd.exe"
echo.
pause
goto menu

:end
echo Exiting launcher...