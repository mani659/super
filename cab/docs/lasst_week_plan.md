# Walk-Forward Testing: Week 2 Roadmap & Macro Strategy
**Execution Period:** August 3 – August 7, 2026
**System Baseline:** GOLD SMC v9.3 (Strict H4, Raw Baseline)
**Objective:** Log raw H4 structural inversions against high-impact liquidity events and evaluate the newly activated passive H1 decay tracker.

## 1. Weekly Performance Ledger Summary (Week 1)
*   **The Top Performers (Trend Consistency):** USDJPYm & GBPUSDm. Both demonstrated strong directional stability, securing multiple large +2.02R full-target wins.
*   **The Wildcard (Extreme Volatility):** USOILm. Generated massive nominal swings (e.g., +$7,163 full target hit alongside severe -$4,973 and -$2,905 hard stops). ATR-based risk is drastically inflating nominal dollar exposure.
*   **The Bleeder (Ranging / Chop):** EURUSDm. Caught in a low-momentum environment, suffering a continuous string of early structural flips and -1.0R hard stops with no full target hits in the latter half of the week.

## 2. Macroeconomic Injection Points
We are entering a heavy liquidity week driven by U.S. labor and services data. The system will run raw to absorb and log exactly how these events impact the H4 baseline structure.

*   **Monday, August 3 (10:00 AM ET): ISM Manufacturing PMI**.
    *   *Expectation:* A PMI reading below 49 indicates ongoing contraction. Watch for early week localized volatility on USD pairs. Expect rapid structural flips on EURUSDm and GBPUSDm if the manufacturing sector shows unexpected contraction.
*   **Wednesday, August 5 (8:15 AM ET & 9:45 AM ET): ADP Employment & Services PMI**.
    *   *Expectation:* Mid-week momentum shifts. Watch for potential H4 candle exhaustion triggers around these windows. 
*   **Friday, August 7 (8:30 AM ET): US Non-Farm Payrolls (NFP)**.
    *   *Context:* The June report came in severely below expectations at just 57,000 jobs (forecasted at 110k-114k). The July forecast sits at around 85,000 to 114,000 jobs. A gain below 100,000 would increase concerns of an employment slowdown, likely boosting equities. Conversely, a gain above 150,000 could push Treasury yields higher.
    *   *Expectation:* Maximum volatility. A severe miss or beat will cause massive spread widening and immediate H4 structural invalidations across the board.

## 3. Telemetry Focus for Week 2
1.  **H1 Decay vs. NFP:** Friday will be the ultimate stress test for the H1 passive decay tracker. We will determine if the H1 structure breaks (logging the timestamp via `track_h1_structure`) *before* the H4 structure formally flips or hits the SL. If the H1 reliably predicts the H4 break by a margin of 1-2 hours during macro events, we have mathematically proven the need for an H1 early-exit filter.
2.  **USOILm Spread & Slippage:** Given the violent swings last week, we must monitor the `trade_context` logs for USOILm. Track if broker slippage is compounding the large nominal losses and evaluate if the asset requires a different fixed-dollar risk constraint compared to forex pairs.
3.  **The NFP Spread-Widening Test:** Observe the `slippage` and `spread` data points printed in the `trade_context` log during the 8:30 AM ET H4 candle on Friday. Verify if the broker respects the 3.0 pip maximum allowed spread logic in `strategy.py` during peak volatility.