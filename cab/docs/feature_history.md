# Feature History & Validation Register

| Feature / Logic | Status | Rationale & Historical Notes |
| :--- | :--- | :--- |
| **Tri-Vector ADX Regime Gating** | Active | Routes execution logic based on momentum. Prevents mean-reversion strategies from fighting strong trends (ADX 30-60) and grid strategies from blowing up in breakouts (ADX > 30). |
| **Intraday Session Filter** | Active | KPI data proved Asian/Early London entries suffered severe negative expectancy. H4 entries are now gated to the London/NY Overlap and NY Sessions. |
| **JSON State Persistence** | Active | Replaced RAM-only dictionaries in `metrics.py`. Solved the critical MT5 `uint64` serialization bug that was wiping trade risk context and defaulting harvested logs to `0.00R` after script restarts. |
| **The "Protector" & Elastic Trailing** | Active | Locks Break-Even + Buffer at 1.0R floating profit, then trails dynamically. Greatly improved MFE capture rates during high-momentum events like NFP. |
| **The "Reaper" (Active H1 Kills)** | Active | Transitioned from passive tracking to active execution. Cuts losing trades early (avg -0.5R) if H1 structure breaks heavily against the H4 entry, mathematically saving massive capital over time. |
| **Dynamic Risk Equalization** | Active | Replaced fixed `LOT_SIZE = 1.0`. Calculates volume dynamically to risk exactly 1% per setup, normalizing the severe nominal drawdowns previously caused by USOILm. |
| **Strict 1-Position Limit** | Conditional | Maintained for the Inversion and Continuation vectors for statistical purity. Lifted exclusively for the Grid vector to allow dynamic scaling and averaging. |
| **Fixed 1:2R Target Exits** | Scrapped | Replaced by the "Harvester" (closing >2.0R on M15 wick exhaustion) and Elastic Trailing mechanisms. |

## [v2.1.0] - 2026-08-22 (Week 2 Regime & Risk Hardening)

### Added
- **H4 Macro Trend Bias Filter (`cab/strat_inversion.py` & `cab/shared_utils.py`):**
  - Added vectorized `get_ema()` helper in `shared_utils.py`.
  - Injected an H4 50-period EMA filter into `execute_inversion_entries()`.
  - Restricts Inversion entries (ADX > 60) from taking counter-trend positions during macro trends (rejects Shorts when `Price > EMA50`; rejects Longs when `Price < EMA50`).
- **Behavioral Pacing & Geometric Spacing (`cab/strat_grid.py`):**
  - **Adverse Velocity Pacing Gate:** Enforced a 30-minute minimum cooldown (`MIN_ADDON_COOLDOWN_SECONDS = 1800`) between grid layers to prevent rapid stacking during intrabar vertical expansions.
  - **Geometric Step Expansion:** Add-on grid spacing dynamically widens per layer based on H4 ATR ($Step_n = \text{H4\_ATR} \times (1.0 + (n - 1) \times 0.5)$).
  - **Hard Layer Cap:** Enforced a maximum 5-position basket cap (`MAX_GRID_LAYERS = 5`).

### Preserved
- **Continuation Vector (`cab/strat_continuation.py`):** Maintained active dual-execution (Market Trend Entries + 24-Hour Pending Trap Stop Orders `CONT_TRAP_BUY / SELL`) without modification to continue multi-week data collection.

## [v2.1.1] - 2026-08-30 (Enhanced Telemetry — Observation-Layer Only)

### Added
- **Enriched Trade Context (`cab/metrics.py`):**
  - `register_trade_context()` now accepts and persists 6 additional fields: `adx`, `plus_di`, `minus_di`, `ema50`, `session`, `subtype`.
  - All fields are optional with safe defaults (0.0 / "OTHER" / "UNKNOWN") so existing call sites do not break during transition.
  - Stored to `trade_context.json` alongside existing risk/spread/slippage data.
- **Grid Notional Risk (`cab/strat_grid.py`):**
  - Grid base and addon entries now calculate a notional `risk_amount` using `H4_ATR × ATR_MULT_SL` as the theoretical SL distance.
  - Previously hardcoded to `0.0`, making R-multiples for grid trades meaningless. Now computable for future analysis.
- **Enriched Harvest Log (`cab/metrics.py`):**
  - `harvest_closed_trades()` now includes `ADX`, `Sub` (subtype), and `Session` in the log line.
  - Enables post-trade analysis by regime and entry type without manual correlation.
- **Strategy Call Sites Updated:**
  - `strat_inversion.py`: Passes `adx`, `plus_di`, `minus_di`, `ema50` (H4 EMA), `session` (hour-derived), `subtype` (INV_EXH_BUY / INV_EXH_SELL).
  - `strat_continuation.py`: Passes `adx`, `plus_di`, `minus_di`, `session`, `subtype` (CONT_TREND_BUY / CONT_TREND_SELL / CONT_TRAP_BUY / CONT_TRAP_SELL).
  - `strat_grid.py`: Passes `adx`, `session`, `subtype` (GRID_BASE / GRID_ADDON) with notional risk.

### Zero Trading Logic Changes
- No entry conditions, exit conditions, risk sizing, position management, or strategy behaviour was modified.
- All changes are observation-layer only (logging, telemetry, context storage).
- Consistent with ADR-003 (Incubation Mandate) and ADR-004 (Enhanced Logging permitted during incubation).

## [observation] - 2026-09-19 (Post-Gate Segment 1: Sep 13–19)

### Runtime Behaviour — No Code Changes
- **ENABLE_CONTINUATION=False** active since 13 Sep 2026. Zero CONTINUATION ENTRY lines on/after 13 Sep.
- Inversion (9995551) and Grid (9995553) live and managing normally.
- manage_continuation still runs (existing positions managed, no new entries).

### Segment 1 Results (MT5 account 262924445)
- 22 closed trades, net ≈ +$1,415 (16 winners / 6 losers).
- Grid vector (BASE+ADDON): n=16, net ≈ +$1,549. ADDON legs (n=4, +$1,432) dominated BASE legs (n=12, +$118).
- Inversion: n=3 (EURUSDm), net ≈ –$134. All exits H1_STRUCT_INVALID.
- Continuation: 0 entries (disabled by design).
- Single USDJPY ADX-kill: –$1,007 (–1.20R), confirming grid path risk remains structural.
- No loss caps breached. All management operational.

### Key Observation
Grid ADDON legs drove nearly all profit this segment. BASE legs were near-flat. This is segment-1-only — not a locked pattern. Formal sample (2 weeks or 30 closes) still incomplete.

## [v2.1.2] - 2026-09-05 (M5 LTF Snapshot Telemetry — Diagnostic Only)

### Added
- **LTF Context Snapshot (`cab/shared_utils.py`):**
  - New function `snapshot_ltf_context(symbol, signal_direction)` captures M5 microstructure at the moment an H4 inversion signal fires.
  - Returns a dict with: `m5_atr`, `h4_atr`, `atr_ratio` (m5/h4), `m5_dist_to_swing_atr`, `m5_structure`.
  - Structure labels: `AT_OR_ABOVE_HIGH`, `NEAR_HIGH`, `MID_RANGE`, `NEAR_LOW`, `AT_OR_BELOW_LOW`.
  - Direction-aware distance: BULLISH signals measure distance from swing low; BEARISH signals measure distance from swing high.
  - Reuses existing `get_atr()` for both timeframes — no duplicate TR calculation.
  - Robust fallbacks: returns safe defaults (0.0 / "UNKNOWN") on missing rates, zero ATR, or None signal.
- **Extended Trade Context (`cab/metrics.py`):**
  - `register_trade_context()` now accepts 4 additional optional kwargs: `m5_atr`, `atr_ratio`, `m5_dist_to_swing_atr`, `m5_structure`.
  - All default to safe values (0.0 / "UNKNOWN") — fully backward compatible.
  - Stored in `trade_context.json` alongside existing fields.
- **Enriched Harvest Log (`cab/metrics.py`):**
  - Harvest log line now appends `ATR_Ratio` and `M5_Struct` for post-trade analysis.
- **Strategy Call Sites (`strat_inversion.py`, `strat_continuation.py`, `strat_grid.py`):**
  - Each strategy calls `snapshot_ltf_context()` after a successful entry and before `register_trade_context()`.
  - Fields passed via `**ltf` unpacking — no manual field duplication.
  - Grid addon entries use basket direction (`"BULLISH"` / `"BEARISH"`) for the snapshot call.

### Management Robustness Fix (Non-Strategy)
- `strat_inversion.py` and `strat_continuation.py`: Added `ENTRY_TYPES` tuple to `manage_*` functions so pending order types (BUY_STOP, SELL_STOP, BUY_LIMIT, SELL_LIMIT) are not silently skipped when resolving initial R from history.
- Added `pos.sl` fallback when history orders are missing or have SL=0 (common for filled pending orders).
- Reduces `[SKIP]` spam in logs without changing any exit logic or management behaviour.

### Purpose
- Enables post-trade analysis of the question: "Was price already extended on M5 when the H4 inversion signal fired?"
- `atr_ratio` captures the intraday volatility regime relative to the macro timeframe.
- `m5_structure` captures whether the entry was chasing an extended move or entering from a balanced position.

### Zero Trading Logic Changes
- No entry conditions, exit conditions, risk sizing, position management, or strategy behaviour was modified.
- All changes are observation-layer only (logging, telemetry, context storage).
- Consistent with ADR-003 (Incubation Mandate) and ADR-004 (Enhanced Logging permitted during incubation).