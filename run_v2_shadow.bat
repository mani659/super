@echo off
chcp 65001 >nul
cd /d "%USERPROFILE%\Desktop\MT5Bot\Super"

echo [System] Activating virtual environment...
call venv\Scripts\activate

:: Tell Python to use UTF-8 for all console output (fixes Unicode arrow/dash errors)
set PYTHONIOENCODING=utf-8

:: ==============================================================================
:: BOT EXECUTION ? V2 Shadow Mode
:: ==============================================================================
echo [System] Starting V2 Shadow Runner...
python v2_unified_runner.py --mt5-path "C:\Program Files\MetaTrader 5 EXNESS - Copy (3)\terminal64.exe"

echo.
echo [!] Bot process terminated or stopped by user.
pause
