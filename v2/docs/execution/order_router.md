# Order Router (V2)
**Path:** 2/execution/order_router.py

## Purpose
The Order Router is the ultimate gatekeeper for trade execution in the V2 architecture. It sits between the logic bots (e.g., SuperTrend, Ghost) and the MT5 Gateway. 

Its primary responsibility is to enforce **Layer 3 Risk Constraints** (Correlation Buckets) and global circuit breakers, acting as a passive filter. It does NOT modify the mathematical parameters of the proposed trade; it only approves or vetoes it.

## Validation Pipeline
When a bot proposes a TradeSignal, it is passed to oute_signal(). The signal must survive the following checks:

### 1. Global Circuit Breakers
- **Daily Drawdown Limit:** Rejects signals if the account equity has fallen past the configured max daily loss percentage.
- **Max Global Positions:** Rejects signals if the total number of open positions in MT5 exceeds the configured maximum (e.g., 15).

### 2. Layer 3 Correlation Buckets
To prevent over-exposure to highly correlated assets, the Knowledge Register defines "Buckets" (e.g., GOLD_SILVER containing XAUUSDm and XAGUSDm).
- The router checks which bucket the proposed symbol belongs to.
- It queries MT5 for all open positions and filters them by the same bucket.
- It assumes a standard 1.0% risk per active trade for performance speed.
- If the current bucket exposure + 1.0% exceeds the max_bucket_risk_pct defined in the Knowledge Register (e.g., 3.0%), the trade is **Vetoed**.

## Output
Returns True if the trade is approved for execution, or False if it is vetoed by any of the checks above.
