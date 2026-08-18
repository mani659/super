# Development Roadmap & Future Integration

**Phase 1: Tri-Vector Walk-Forward Deployment (Current)**
* Deprecate the single monolithic strategy script and deploy the isolated `strat_inversion`, `strat_continuation`, and `strat_grid` modules.
* Validate that the Magic Number routing correctly segregates P/L, metrics, and active management rules for each vector.
* Monitor the Intraday Session Gate to confirm entries are strictly adhering to the London/NY overlapping liquidity windows.

**Phase 2: Grid & Basket Optimization**
* Fine-tune the scaling multipliers and fixed ATR step-distances within the `strat_grid.py` module.
* Stress-test the ADX > 30 "Kill Switch" to ensure range-bound grid baskets are ruthlessly liquidated the moment a macro trend breakout occurs, preventing catastrophic drawdowns.

**Phase 3: Portfolio Heat & Capital Velocity**
* Implement global account heat limitations (e.g., pausing the Grid vector if the Continuation vector is already utilizing 5% of total account margin).
* Evaluate the aggregate MFE capture rates of the Elastic Trailing stop mechanism to optimize the dynamic trail gap between 1.0R and 2.0R floating profits.