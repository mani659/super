# CAB MASTER: Quantitative Roadmap

## 📌 Phase 1: The Incubation Run (CURRENT)
**Goal:** Generate a statistically significant, unbiased dataset (minimum 50-100 trades across all 11 pairs).
**Rules of Engagement:**
* Deploy the bot on an Exness Demo account via `start_bot.bat`.
* Do not interfere with trades manually.
* Do not attempt to tweak logic, SL distances, or logic filters based on short-term winning or losing streaks. Let the bot generate raw data.

## 📊 Phase 2: The Data Science Review (PENDING)
**Goal:** Ingest the `cab_performance_ledger.csv` into a Python Data Science environment (Jupyter Notebook / Pandas) to identify true statistical edges.
**Key Analytical Queries:**
1. *Session Edge:* Does execution during the London/NY overlap yield a higher R-multiple than the Asian session?
2. *Volatility Filters:* Are win rates inversely correlated to `EXPANSION_HIGH` ATR states?
3. *Macro Alignment:* Does a `USD_BULLISH` DXY proxy significantly improve short positions across major pairs?
4. *Stagnation:* What is the average duration of winning trades vs. losing trades? Should `STAGNATION_HOURS` be reduced?

## ⚙️ Phase 3: The Filter Translation (PENDING)
**Goal:** Hard-code proven statistical edges back into the trading logic.
* Use insights from Phase 2 to update `signals.py` and `trade_manager.py`.
* Example: "If Session == 'ASIAN' and Symbol == 'GBPUSDm', reject execution."
* This ensures the bot evolves from speculative logic into purely empirical execution.

## 🌍 Phase 4: Live Deployment & Scaling (PENDING)
**Goal:** Graduate to real capital.
* Migrate to a dedicated ultra-low latency VPS (close to Exness servers).
* Final validation of the MQL5 Sentinel failover under live slippage conditions.
* Scale capital incrementally based on the finalized Sharpe Ratio and Max Drawdown metrics.