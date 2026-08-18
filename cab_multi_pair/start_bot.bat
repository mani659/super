@echo off
title CAB Omni-Pair Master Engine (VENV ACTIVE)

:: 1. Navigate to the bot folder
echo Navigating to bot directory...
cd /d "%USERPROFILE%\Desktop\MT5Bot\Super\cab_multi_pair"

:: 2. Activate the Virtual Environment
echo Activating Environment...
call "%USERPROFILE%\Desktop\MT5Bot\super\venv\Scripts\activate"

:: 3. The Immortal Loop
:loop
echo [%DATE% %TIME%] Starting main.py...
python main.py

echo.
echo ==================================================
echo [CRASH DETECTED] Script closed unexpectedly at %TIME%
echo Restarting in 5 seconds...
echo ==================================================
timeout /t 5
goto loop