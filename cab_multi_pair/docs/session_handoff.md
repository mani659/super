# Session Handoff Document: CAB Multi-Pair Master

**Date of Handoff:** August 23, 2026
**Target Audience:** Incoming AI Models / Developers
**Current Phase:** Phase 1 (The Incubation Run)

---

## 1. Project Overview
The `cab_multi_pair` repository operates an independent, standalone MetaTrader 5 bot designed to run across 11 different currency/commodity pairs simultaneously. It shares its architectural roots with the CAB strategy but functions entirely separately from both the `Super` monolith and the single-pair `cab` bot.

**Core Philosophy:** 
This engine is built strictly as a data-collection engine (Incubation Run) designed to generate a 50-100 trade statistical dataset across all 11 pairs.

## 2. Current State & Recent Accomplishments
The architecture is fully decoupled into 9 distinct core modules (`main`, `config`, `connection`, `utils`, `signals`, `execution`, `trade_manager`, `ledger`, and `analytics/intelligencia`).

**Active & Proven Mechanisms (Do Not Remove):**
1. **COMPRESSION_LOW Optimizations:** Implemented a 6-hour age filter on `H1_STRUCT_BREACH` exits to prevent whipsaw kills. The intelligencia engine correctly drops entries when `Macro_Risk_Sentiment == "RISK_OFF"` and `H1_ATR_State == "COMPRESSION_LOW"`.
2. **Completed Candle Sampling:** Entry signals (`signals.py`) query only completed H4/H1 bars (index 1 and 2) to eliminate repainting.
3. **Immortal Python Watchdog:** Execution operates inside a `run.bat` loop that instantly restarts Python on a crash. MQL5 `CAB_Engine_Dashboard.mq5` acts purely as a visual health sentinel and NEVER modifies trades (to avoid MT5/Python race conditions).
4. **Config-Tethered Execution:** A hard `MAX_SPREAD` liquidity filter prevents toxic spread entries. `BE_GATE_R` and `LOCK_GATE_R` targets dynamically secure break-even earlier on highly volatile pairs (Gold/Crypto).

## 3. Active Directives (Do Not Violate)
- **Bot Boundaries Mandate:** Never mix patches from `Super` (V1/V2) or the standalone single-pair `cab` bot into this repository. This system operates its own execution lifecycle and has its own risk constraints.
- **Data over Speculation:** Do not attempt to tweak logic, SL distances, or logic filters based on short-term winning or losing streaks. This Phase 1 system must run uninterrupted to generate raw statistical data. Any future trade filters must be translated directly from data science reviews (Phase 2), not speculative hypotheses.

## 4. Immediate Next Steps for Incoming Model
- Run the system through `start_bot.bat` and monitor the `cab_performance_ledger.csv`.
- Wait for the 50-100 trade milestone across the 11 pairs to be reached before moving to Phase 2 (Data Science Review).
- If evaluating the ledger, analyze macro alignment (DXY proxy vs major pairs), Session Edge (London/NY overlap), and stagnation metrics.
