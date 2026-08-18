# SuperTrend Bot (V2)
**Path:** 2/bots/supertrend_bot.py

## Overview
The V2 SuperTrend Bot has been stripped of all MT5 terminal management, trailing stop logic, and equity circuit breakers. It is now a pure, clean mathematical engine.

## Execution Pipeline
1. **Data Ingestion:** The bot pulls the pre-calculated MarketStateSnapshot (ADX, ATR, Regime) from the KnowledgeRegister.
2. **K-Means Clustering:** It computes SuperTrend bands across 20 factors (from 2.0 to 4.0 in 0.1 increments). It clusters the volatility-adjusted performance of these lines using K-Means and selects the optimal factor based on the configuration (Best, Average, Worst).
3. **Signal Generation:** If a trend flip occurs, or a trend continuation breakout occurs, it generates a TradeSignal.
4. **Order Routing:** It passes the signal to the OrderRouter (Layer 3 checks).
5. **Execution & Registration:** If the router approves, the bot sends the order to the MT5Gateway and permanently registers the TradeThesis in the Knowledge Register.

## Strict Parity (Lot Sizing)
To ensure 100% mathematical parity with V1 during the shadow testing phase, the lot sizing logic remains internal to the bot, utilizing MT5's 	rade_tick_value and 	rade_tick_size precisely as defined in the V2.3 patch.
