@echo off
chcp 65001 >nul
cd /d "%USERPROFILE%\Desktop\MT5Bot\Super"

echo [System] Activating virtual environment...
call venv\Scripts\activate

:: Tell Python to use UTF-8 for all console output (fixes Unicode arrow/dash errors)
set PYTHONIOENCODING=utf-8

:: ==============================================================================
:: BOT EXECUTION ? Unified Ecosystem
:: ==============================================================================
echo [System] Starting Unified Runner...
python unified_runner.py

echo.
echo [!] Bot process terminated or stopped by user.
pause
