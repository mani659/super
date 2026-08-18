# Knowledge Register (V2)
**Path:** 2/core/knowledge_register.py

## Purpose
The Knowledge Register acts as the central data bus and state manager for the entire V2 architecture. It is completely decoupled from MT5 execution logic and only stores the canonical state of the system in memory.

## Architectural Layers

### Layer 0: Oracle Data
Stores the most recent MarketStateSnapshot (ADX, ATR, MACD, Regime) pushed by the Market Oracle.
- **publish_market_state(snapshot)**: Ingests new Oracle data.
- **get_market_state(symbol, timeframe)**: Retrieves the latest state (with a 1-hour expiration safety check).

### Layer 1: Trade Thesis Tracking
When a bot opens a trade, it registers a TradeThesis here. This is an immutable snapshot of exactly *why* the trade was entered (the regime, the ATR, the setup type). This ensures that exit logic (e.g., structural invalidation) can perfectly reference the conditions that existed at entry, rather than shifting current conditions.
- **egister_trade_thesis(thesis)**: Locks and stores the thesis by MT5 ticket ID.
- **get_entry_snapshot(ticket)**: Retrieves the entry conditions for active management.
- **unregister_trade_thesis(ticket)**: Purges the thesis when the trade is closed to prevent memory leaks.
- **get_active_theses()**: Returns a list of all active trades for dashboarding and global risk checks.

### Layer 3: Correlation Buckets
Defines the hardcoded risk buckets (e.g. GOLD_SILVER, FX_USD_MAJORS) and their maximum portfolio exposure limits. The Order Router queries these lookup functions to enforce its vetoes.
- **get_bucket_for_symbol(symbol)**: Maps a symbol to its predefined bucket.
- **get_max_risk_for_bucket(bucket)**: Returns the maximum allowed risk percentage.
