# CAB MASTER: Feature History & Decision Ledger

> **Purpose:** This file acts as the official institutional memory for the CAB Master trading system. It logs every active mechanism, every failed/scrapped experiment (and why it failed), and key architectural decisions to prevent repeating past mistakes.

---

## 🟢 1. Active & Proven Mechanisms (What We Keep & Why)

### 1. Data-Informed Regime Filters & Time-Gated Structural Breaches (`COMPRESSION_LOW` Optimizations)
* **Mechanism:** Enforcing a 6-hour age filter on `H1_STRUCT_BREACH` exits to prevent whipsaw chop kills, and integrating an intelligencia check to drop entries when `Macro_Risk_Sentiment == "RISK_OFF"` and `H1_ATR_State == "COMPRESSION_LOW"`.
* **Why It Works:** Empirical post-analysis of 257 ledger trades revealed that 79.7% of low-compression losses stemmed from premature structural exits under 6 hours, and hostile `RISK_OFF` low-volatility entries drained -14.62 R. Aligning code with these findings replaces rigid incubation restrictions with data-backed survival rules.

### 2. Completed Candle Sampling
* **Mechanism:** Entry signals in `signals.py` query strictly completed H4/H1 bars (`index 1` and `index 2`).
* **Why It Works:** Completely eliminates indicator repainting and mid-bar signal shifting. 

### 3. Multi-Module Decoupled Architecture
* **Mechanism:** Split monolithic execution into 9 core modules (`main`, `config`, `connection`, `utils`, `signals`, `execution`, `trade_manager`, `ledger`, and `analytics/intelligencia`).
* **Why It Works:** Eliminates circular dependency risks, allows isolated module debugging, and enables smooth feature additions without breaking order execution.

### 4. Immortal Python Watchdog Loop (`run.bat`)
* **Mechanism:** An external batch script runs `main.py` inside an infinite loop that auto-restarts the script instantly if an unhandled crash or network drop occurs.
* **Why It Works:** Guarantees 24/5 uptime without risking execution race conditions between Python and MetaTrader.

### 5. Market Intelligencia Logging
* **Mechanism:** Captures ADX trend strength, H1 ATR volatility states, active session tags, and Macro DXY/Risk proxies at the exact second a trade is initiated.
* **Why It Works:** Builds a rich dataset to replace speculative guesswork with data-driven optimization in Phase 2.

### 6. Pure Visual Dashboard Sentinel (`CAB_Engine_Dashboard.mq5`)
* **Mechanism:** MQL5 script attached to a single chart that strictly reads `cab_heartbeat.txt` and displays a clean GUI (`✅ ONLINE` / `❌ OFFLINE`).
* **Why It Works:** Gives instant visual confirmation of Python's health without risking order modification conflicts.

### 7. Config-Tethered Execution & Management
* **Mechanism:** Integration of a hard `MAX_SPREAD` liquidity filter in `execution.py` and dynamic, pair-specific `BE_GATE_R` and `LOCK_GATE_R` management targets in `trade_manager.py`.
* **Why It Works:** Prevents massive negative slippage by outright rejecting entries during toxic liquidity events (rollover, news). Additionally, rather than a static 1.0R trail for every asset, the engine dynamically secures break-even earlier on high-volatility pairs (like Gold/Crypto), preventing unnecessary full `-1.0 R` drawdowns on fast-moving assets.

---

## 🔴 2. Scrapped Experiments & Lessons Learned (What We Discarded & Why)

### ❌ Experiment 1: MQL5 Active Failover Trailing (`CAB_Global_Sentinel.mq5`)
* **Concept:** MQL5 would automatically take over trailing stops if Python missed a heartbeat for 60 seconds.
* **Result:** **Scrapped.** Failed miserably in live trading.
* **Why It Failed:** Caused severe race conditions and double-modification errors with the broker. When Python rebooted via `run.bat` while MQL5 was actively modifying stops, both engines fought over the same position ticket.
* **Rule Moving Forward:** MQL5 must **NEVER** handle order execution or stop modifications while Python is active. Python handles 100% of the trading lifecycle, while `run.bat` handles crash recovery.

### ❌ Experiment 2: Monolithic Script Architecture (`cab_master.py`)
* **Concept:** Running connection, execution, state memory, and logging inside a single 1000+ line Python file.
* **Result:** **Scrapped.**
* **Why It Failed:** Highly fragile. Modifying a single utility function carried a high risk of breaking position modification or trade closing logic.

### ❌ Experiment 3: Fixed-Pips / Rigid Profit Targets
* **Concept:** Setting hard stop-loss and take-profit values in fixed pips across all pairs.
* **Result:** **Scrapped.**
* **Why It Failed:** Ignored pair-specific volatility (e.g., Gold vs. EURUSD) and market regime shifts. Replaced with ATR-normalized risk distances and dynamic MFE/MAE trailing stops.

---

## 🏛️ 3. Architectural Decision Records (ADRs)

* **ADR-001 (Zero-Division Shields):** Every math utility (`calculate_lot`, `realized_r`) must feature hardcoded fallbacks to prevent runtime `ZeroDivisionError` crashes during illiquid market gaps.
* **ADR-002 (Offline Health Diagnostics):** Any structural or analytics code change must pass `python test_health.py` with zero errors before being deployed to a live environment.
* **ADR-003 (The Incubation Mandate):** Code logic must remain locked during incubation phases (50–100 trades). Strategy tweaks based on short-term winning/losing streaks are strictly prohibited until statistically validated via `ledger.csv`.

---

## 🔬 Week 2 Empirical Observations (Pending Validation)
*Status: Observed in live forward-testing (Week 2). Code remains locked pending Week 3 validation.*

**1. The Directional Disparity:**
*   **Observation:** Long positions demonstrated a heavy statistical edge (64.5% win rate), while Short positions dragged system performance (33.3% win rate).
*   **Hypothesis:** The macro environment may be heavily skewed, or the `H4_MACRO_SELL` inversion logic requires a stricter structural confirmation than the buy side.

**2. Asset Friction on GBP Pairs:**
*   **Observation:** High-volatility pairs (BTCUSDm, XAUUSDm) thrived under the dynamic trailing lock, capturing bulk profits. However, traditional GBP pairs (GBPUSDm, EURGBPm) accounted for the heaviest systemic bleed (-$378 combined).
*   **Hypothesis:** The current `BE_GATE_R` or H4 entry parameters may be incompatible with the intraday chop characteristics of the British Pound in the current regime.

**3. The ADX Momentum Bands:**
*   **Observation:** Deep-dive into `cab_performance_ledger` revealed that ADX averages between winning (36.2) and losing (35.4) trades are identical. However, the extremes hold the edge:
    *   **ADX > 50:** Highly profitable (+17.75 R).
    *   **ADX < 20:** A low-volatility trap (18.1% win rate, -3.16 R).
    *   **ADX 30-50:** The deceptive "Chop Zone" (-10.27 R).
*   **Action Plan:** Do not implement filters yet. Monitor Week 3 to see if these exact bands persist.