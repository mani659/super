# Strategy Knowledge Base

This document serves as the central repository for maintaining knowledge data related to exploring trading strategies, rules, stop loss logic, and exit management (e.g. Trailing logic).

## 1. Trade Analytics Data Logging
To support statistical analysis, all trade events (Entries, Exits, Partial Closes) across the three bot subsystems (SuperTrend, CAB, Ghost Grid) are now logged in a unified ledger: `data/trade_ledger.csv`.
This unified log captures critical variables such as regime, session, conviction, ATR, R-multiple, and exit reasons for every trade. The ledger serves as the foundation for the following analytics:
- Win/loss analysis by trade type and direction
- Co-relation between pairs
- Performance profiling by time of day / holding period
- Optimal exit management (when trailing works vs grid)

## 2. Dynamic Lot Sizing & Exposure Logic
- **CAB Bot Dynamic Lot Sizing (TODO):** Dynamic lot sizing needs to be implemented for the CAB bot to match SuperTrend logic. It will be managed globally under `unified_runner.py` with an exception for Ghost Grid until logic validation is complete.
- **Model Divergence/Confluence (TODO):** Develop logic to identify high-conviction environments when both CAB and SuperTrend open trades in the same direction. We need to implement a mechanism to increase weight/conviction on such trades.
- **Opposing Positions (Discussion):** Reconcile opposing model decisions using the Knowledge Register's existing correlation-bucket exposure ceiling rather than a hard veto. 

## 3. Exit Strategies & Stop Loss Management
- **Trailing vs Grid Exits:** (To be analyzed post Week-1 data collection)
- **Spread Guards:** Currently strictly enforced on entries but disabled on exits to avoid trapping trades during volatile markets.

## 4. Market Environment & Pair Performance
- **Best / Worst Performing Pairs:** (Data to be compiled post Week-1 data collection)
- **Session Analysis:** (Data to be compiled post Week-1 data collection)

---
*Note: This knowledge base is a living document. It will be updated iteratively as new statistical analysis is drawn from `trade_ledger.csv` over the coming weeks.*
