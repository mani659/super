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