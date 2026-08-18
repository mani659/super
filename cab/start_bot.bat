@echo off
title CAB WATCHER - MODULAR MAIN (MT5 Hybrid Brain)

echo ==================================================
echo   RUNNING: CAB WATCHER - MODULAR MAIN
echo ==================================================

:: 1. Navigate to the bot folder
echo Navigating to bot directory...
cd /d "%USERPROFILE%\Desktop\MT5Bot\super\cab"

:: 2. Activate the Virtual Environment
echo Activating Environment...
call "%USERPROFILE%\Desktop\MT5Bot\super\venv\Scripts\activate"

:: 3. The Immortal Loop
:loop
echo [%DATE% %TIME%] Starting main.py (CAB WATCHER MODULAR)...
python main.py 2>> crash.log

echo.
echo ==================================================
echo [CRASH DETECTED] Script closed unexpectedly at %TIME%
echo Restarting in 5 seconds...
echo ==================================================
timeout /t 5
goto loop