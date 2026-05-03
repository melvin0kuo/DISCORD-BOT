@echo off
chcp 65001 > nul
echo Starting Discord Bot...

:: Set Conda path (your actual Anaconda installation)
set CONDA_PATH=C:\Users\harekaze\anaconda3

:: Check if Conda path exists
if not exist "%CONDA_PATH%" (
    echo Error: Conda path not found at %CONDA_PATH%
    echo Please edit this batch file with the correct path.
    pause
    exit /b 1
)

:: Set working directory to the script location
cd /d %~dp0

:: Activate Conda environment
call "%CONDA_PATH%\Scripts\activate.bat" discord

:: Check if environment activation was successful
if %ERRORLEVEL% neq 0 (
    echo Error: Could not activate 'discord' environment
    echo Please check if the environment exists or create it with 'conda create -n discord python=3.10'
    pause
    exit /b 1
)

:: Run the bot
echo Running Discord Bot...
python main.py

:: Keep window open if script exits unexpectedly
pause