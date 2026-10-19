@echo off
chcp 65001 > nul
cd /d "%~dp0"
set "BOT_PYTHON=%DISCORD_BOT_PYTHON%"
if not defined BOT_PYTHON if exist "%USERPROFILE%\anaconda3\envs\discord\python.exe" set "BOT_PYTHON=%USERPROFILE%\anaconda3\envs\discord\python.exe"
if not defined BOT_PYTHON if exist "%USERPROFILE%\miniconda3\envs\discord\python.exe" set "BOT_PYTHON=%USERPROFILE%\miniconda3\envs\discord\python.exe"
if not defined BOT_PYTHON if exist "%~dp0.venv\Scripts\python.exe" set "BOT_PYTHON=%~dp0.venv\Scripts\python.exe"
if not defined BOT_PYTHON if exist "%~dp0venv\Scripts\python.exe" set "BOT_PYTHON=%~dp0venv\Scripts\python.exe"
if not defined BOT_PYTHON set "BOT_PYTHON=python"

"%BOT_PYTHON%" setup_local_lavalink.py
if errorlevel 1 goto failed
if /I "%~1"=="--setup-only" (
    set "BOT_EXIT=0"
    goto done
)
"%BOT_PYTHON%" main.py
set "BOT_EXIT=%ERRORLEVEL%"
goto done

:failed
echo Local Lavalink setup failed. See the error above.
set "BOT_EXIT=1"

:done
if /I not "%~1"=="--no-pause" if /I not "%~1"=="--setup-only" pause
exit /b %BOT_EXIT%
