# Trading System Changelog (V1 & V2)

This timeline maintains a strict historical record of all code modifications, bug fixes, and architectural changes since the start of the current raw logging phase.

---

## August 26, 2026 - Phase A Architecture Fix

### V1 System
- **MarketPulseEngine Data Publication Fix**
  - **Change:** Modified `core/shared_intelligence.py` to remove the 4-hour staleness block (`current_bar_time <= self._last_bar_times`) and increased the MT5 bar fetch count from 50 to 150. Added live publication logging.
  - **Impact:** Solved the critical bug where KR Layer 0 returned 98.5% `RANGING` due to NaN outputs from `atr14.rolling(50).mean()` on truncated 50-bar datasets. The pulse engine now correctly evaluates the current market state intra-bar (every 10s) instead of freezing for 4 hours after the H4 bar opens. Unblocks downstream KR consumers (CAB REAPER, ST SI score, Ghost regime gates).

---

## August 22, 2026 - Phase 2 Demo Testing (Week 6)

### V1 System
- **Ghost Cache N_LAYERS_DEFAULT Trigger**
  - **Change:** Lowered `N_LAYERS_DEFAULT` from 3 to 2 in `ghost_super/ghost_cache.py`.
  - **Impact:** Zero fires were recorded in Week 5. n=2 fires at the 2nd virtual layer (more frequent, lower conviction than n=3). This allows Gate 2 decision tracking (204 vs 202 avg_R) to accumulate the necessary 30+ fills.

- **Ghost 204 Decouple Fix**
  - **Change:** Removed `ghost_cache = None` from the 202 trigger block in `ghost_sniper.py`.
  - **Impact:** GhostCache now persists after a 202 fire, allowing 204 to accumulate deeper virtual layers on the same probe. Cache only resets when `armed = None` (full probe cycle end).

- **F6 Cross-Bot Gate Implementation**
  - **Change:** Ghost `UP_PROBE` arming is now suppressed when Knowledge Register contains an active SuperTrend `LONG` thesis on XAUUSDm.
  - **Impact:** Implemented in both `unified_runner.py` and `ghost_sniper.py`. Logs `GHOST_ARM_BLOCKED_ST_LONG`. This prevents Ghost 202 from firing structural short reversals into confirmed SuperTrend uptrends.

- **CAB Watcher Log Path Fix**
  - **Change:** `RotatingFileHandler` updated to write to `logs/cab_watcher.log` (was `cab_production_v16.3.log` in root). `extract_bot_logs.py` aligned to same path.
  - **Impact:** H5 evaluation now unblocked, allowing accurate SL distance analysis to be performed from extracted CAB logs.

- **CAB Premature Entry on Restart Fix**
  - **Change:** State file persistence added in `logs/cab_state_{symbol}.json` with a startup grace period.
  - **Impact:** Blocks cold-start re-fires and ensures clean tracking of fluid logic on restart.

- **Ghost Grid 10016 SL Rejection Eliminated**
  - **Change:** Phase 2 SL/TP anchor now computed from actual fill price (`result.price`), not pre-order tick price.
  - **Impact:** Eliminates geometric mismatches that caused 10016 rejections and downstream naked trade kill-switch terminations.

## August 16, 2026 - Terminal Hijacking Prevention

### V1 & V2 Systems
- **MT5 Reconnect Terminal Hijack Fix**
  - **Change:** Removed rogue `mt5.initialize(timeout=30000)` calls from exception handlers in `core/supertrend_bot.py`. Removed fallback pathless `mt5.initialize()` in `cab_multi_pair/connection.py`.
  - **Failure Mode:** When `mt5.initialize()` is called without specifying the explicit `path` argument, the MT5 library connects to the first available terminal on the system (e.g., `Copy` or `Copy (2)`). During a brief connection drop, the `SuperTrend` bot running under `unified_runner` used this pathless init to reconnect. It instantly connected to the standalone `CAB` terminals instead of the root terminal, executed a login with V1 credentials (474167713), forcefully added the V1 account to the CAB terminals, and began executing `SuperTrend` trades on the wrong terminals, knocking out the standalone bots.
  - **Impact:** Gateway architecture strictly enforced. The V1/V2 systems now universally rely exclusively on `MT5Gateway` for all initialization and reconnect logic, locking the bot purely to its configured `TERMINAL_PATH`.

---

### V2 System
- **Order Router Bypass (Edge Validation)**
  - **Change:** Implemented a `raw_logging_mode` flag inside `v2/execution/order_router.py`.
  - **Impact:** Entirely bypasses Global Circuit Breakers (Daily Drawdown caps) and Layer 3 Correlation Bucket limits (e.g., `GOLD_SILVER` 3.0% limit). 
  - **Reasoning:** Allows the bots to fire every generated signal unobstructed into the live market to gather pure statistical data on the mathematical edge without premature filtering.

- **MT5 Comment Truncation (Crash Prevention)**
  - **Change:** Modified `trade_manager.py` to aggressively truncate all dynamically generated trade comments (like `REAPER|Macro=TREND_AGAINST...`) to exactly `[:28]` characters.
  - **Impact:** Prevents the MT5 Python package from crashing with `(-2, 'Invalid "comment" argument')` when submitting long exit reason strings.

- **False-Positive Error Logging Cleaned**
  - **Change:** Removed the unconditional `logger.error("DEBUG_REQ: ...")` probe from `mt5_gateway.py`.
  - **Impact:** Cleans up the terminal console. Successful trades are no longer falsely flagged as errors in the terminal output.

### V1 System
- **Knowledge Register Bypass (Edge Validation)**
  - **Change:** Injected a `RAW_LOGGING_MODE = True` override directly into V1's `core/knowledge_register.py`.
  - **Impact:** Entirely disables Layer 4 (Hard Block Check) and Layer 3 (Portfolio Exposure) API restrictions (such as `CAB OSI`).
  - **Reasoning:** Parallels the V2 Order Router bypass. Ensures that V1 bots (like `ghost_sniper`) do not get blocked from taking trades due to opposite signals generated by CAB or other macro blocks, allowing for completely pure statistical data gathering.

- **Take Profit Modification Rejection (10011 Fix)**
  - **Change:** Updated `sniper_watcher.py` `_set_leg_tp()` logic. Added strict `round(x, sym_info.digits)` to both the SL and TP values before sending the modification payload.
  - **Impact:** Prevents MT5 from rejecting the order modification due to floating point inaccuracies (`bad stops`).

- **Dynamic Stops Level Fallback (Broker Compliance)**
  - **Change:** Injected a dynamic spread-based fallback (`Spread + 20 points`) inside `sniper_watcher.py`.
  - **Impact:** Protects the bot against modern brokers (like Exness) that report a `trade_stops_level` of `0`. The bot will now always construct a mathematically safe buffer from the current price, preventing illegal TP placement.

- **Watcher Console Spam Eradicated**
  - **Change:** Added a `_no_sl_warned` memory set to `sniper_watcher.py`.
  - **Impact:** The watcher will now only warn you *once* if it encounters an unmanaged/manual trade with no Stop Loss, completely eliminating the 2-second infinite console spam loop.

- **Multi-Symbol Compatibility Enabled**
  - **Change:** Stripped out the hardcoded `"XAUUSDm"` dependency inside `sniper_watcher.py`'s position tracking loops.
  - **Impact:** The watcher now dynamically inherits the symbol (`pos.symbol`) from the open trade, allowing it to correctly monitor grids across multiple different pairs simultaneously.

---

## August 3 - 5, 2026 - V2 Migration & State Management

### V2 System
- **Centralized MT5 Connection (Unified Runner)**
  - **Change:** Deprecated individual bot initialization logic and migrated the MT5 connection to a single `MT5Gateway` inside `v2_unified_runner.py`.
  - **Impact:** Fixed severe multi-threading crash loops where multiple bots attempted to invoke the MT5 terminal concurrently.

- **GhostBot V2 Translation**
  - **Change:** Successfully ported V1 `ghost_sniper` into the object-oriented `v2/bots/ghost_bot.py`.
  - **Impact:** Mapped `magic=201` as virtual shadow executions and successfully implemented the V2 architecture rules.

- **Knowledge Register (Python 3.12 Patch)**
  - **Change:** Replaced deprecated `datetime.utcnow()` and `timezone.utc` implementations with Python 3.12 compliant logic.
  - **Impact:** Unblocked the Knowledge Register state serialization across disk reloads.

- **TradeThesis Data Model Upgrade**
  - **Change:** Enforced `layer_depth` and sanitized `entry_regime` parameters across `v2.core.data_models`.
  - **Impact:** Prevented V2 Runner `Fatal error in main loop` crashes upon TradeThesis instantiation.

### V1 System
- **Grid Staleness Timeout (Grid Reset Fix)**
  - **Change:** Added a 72-hour `MAX_GRID_AGE_SECONDS` timeout and a `created_at` timestamp to Grid states in `sniper_watcher.py`.
  - **Impact:** Solved the "frozen grid" bug where a single trade failing to hit its TP would prevent the Grid tracker from ever resetting, which effectively clogged the execution queue for weeks.

---
> Document generated during Edge Validation Phase.
