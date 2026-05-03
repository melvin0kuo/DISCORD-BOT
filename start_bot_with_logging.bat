@echo off
chcp 65001 > nul
echo Starting Discord Bot... > bot_log.txt
echo Start time: %date% %time% >> bot_log.txt

:: Set Conda path (your actual Anaconda installation)
set CONDA_PATH=C:\Users\harekaze\anaconda3

:: Check if Conda path exists
if not exist "%CONDA_PATH%" (
    echo Error: Conda path not found at %CONDA_PATH% >> bot_log.txt
    exit /b 1
)

:: Set working directory to the script location
cd /d %~dp0

:: Activate Conda environment
call "%CONDA_PATH%\Scripts\activate.bat" discord

:: Check if environment activation was successful
if %ERRORLEVEL% neq 0 (
    echo Error: Could not activate 'discord' environment >> bot_log.txt
    exit /b 1
)

:: Run the bot and redirect output to log file
echo Running Discord Bot... >> bot_log.txt
python main.py >> bot_log.txt 2>&1