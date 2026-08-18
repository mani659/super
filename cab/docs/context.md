# System Context & Execution Philosophy

**Core Identity**
The system is an automated, multi-asset quantitative trading engine built on Python and MT5. The current operational baseline aligns with the "GOLD SMC v10.0" framework, functioning as a multi-regime state machine. It dynamically adapts its trading logic based on prevailing market momentum (ADX) and intraday liquidity cycles.

**Execution Methodology**
* **Timeframe & Session Gating:** Core execution is bound to the H4 macroeconomic timeframe, but explicitly restricted by Intraday Session Gates. Entries are blocked during the Asian session and the initial London open to avoid false liquidity sweeps, arming only during the London/NY overlap and the core New York session.
* **Risk Profile:** Dynamic risk equalization (e.g., 1% account risk per entry) replaces fixed lot sizing. This normalizes nominal dollar risk across highly disparate asset classes (e.g., USOILm vs. EURUSDm).
* **Tri-Vector Deployment:** The engine operates three isolated logic vectors simultaneously:
    1. **Inversion (ADX > 60):** Mean-reversion for extreme momentum exhaustion.
    2. **Continuation (ADX 30-60):** Pullback trading in the direction of strong trends.
    3. **Grid Basket (ADX < 30):** Range-extraction scaling.
* **Active Lifecycle Management:** Replaces the hardcoded 1:2R target/stop mechanism. The system utilizes real-time active management protocols including the **Protector** (Break-Even + Buffer lock), **Elastic Trailing**, the **Reaper** (early H1 structural invalidation kills), and the **Harvester** (M15 exhaustion peak exits).
* **Intelligence Logging:** The engine operates on an Event-Driven logging philosophy, utilizing JSON state persistence to maintain accurate post-trade metrics (MFE, MAE, R-Multiple) across terminal restarts and server crashes.