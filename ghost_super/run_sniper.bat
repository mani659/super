@echo off
title GHOST_SNIPER_SUITE_V5.1_MASTER
:: Navigate to your project directory
cd /d "C:\Users\ABRAR\Desktop\MT5Bot\ghost_grid"

echo [%date% %time%] Launching Ghost Sniper Suite v5.1...
echo --------------------------------------------------
echo 🚀 Target: Same MT5 Terminal Instance
echo 🎯 Magic 201: Scalp (Always Active)
echo 🎯 Magic 202: Reversal (Gated by ADX/Conv)
echo 🎯 Magic 203: Trend-Follow (Gated by ADX/Conv)
echo --------------------------------------------------

:: 1. Launch the Hunter (Layer 2 - The Filter)
:: Auto-restarts if the script exits or crashes
start "SNIPER_HUNTER_V5.1" cmd /k "title SNIPER_HUNTER_V5.1 && FOR /L %%i IN (1,0,2) DO (echo [%date% %time%] Starting Hunter v5.1... & python ghost_sniper_v5_1.py & echo ⚠️ Hunter exited. Restarting in 5s... & timeout /t 5)"

:: 2. Launch the Brain (Layer 1 & 3 - The Watcher/Manager)
:: Auto-restarts if MT5 hiccups occur
start "SNIPER_BRAIN_V3.1" cmd /k "title SNIPER_BRAIN_V3.1 && FOR /L %%i IN (1,0,2) DO (echo [%date% %time%] Starting Brain v3.1... & python sniper_watcher_v3_1.py & echo ⚠️ Brain exited. Restarting in 5s... & timeout /t 5)"

echo.
echo ✅ Done! Sniper Suite is now running in two separate windows.
echo ✅ Hunter is scanning probes with Gated Logic (Fluid TP - Brain owns all exits).
echo ✅ Brain is writing live state and managing exits.
echo.
pause