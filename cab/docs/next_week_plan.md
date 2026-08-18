# Walk-Forward Testing: Tri-Vector Architecture Roadmap
**Execution Period:** August 17 – August 21, 2026
**System Baseline:** GOLD SMC v10.0 (Multi-Regime Modular Environment)
**Objective:** Deploy three isolated strategic modules assigned to specific MT5 Magic Numbers to map profitability across different ADX volatility regimes while enforcing strict intraday session filters.

## 1. Architectural Decoupling & Magic Numbers
To maintain pristine data telemetry and isolate systemic risk, the single `strategy.py` file is being deprecated. It will be replaced by three distinct execution modules, each tracking its own P/L, scaling rules, and risk limits via unique Magic Numbers.

| Module | Regime Focus | Magic Number | Position Limit | Risk Model |
| :--- | :--- | :--- | :--- | :--- |
| `strat_inversion.py` | ADX > 60 | 9995551 | 1 Per Symbol | 1.0R Fixed Hard Stop |
| `strat_continuation.py` | ADX 30 - 60 | 9995552 | 1 Per Symbol | 1.0R Fixed Hard Stop |
| `strat_grid.py` | ADX < 30 | 9995553 | Uncapped (Basket) | Aggregate +1.0R Target |

## 2. The Three Strategic Vectors

*   **Vector 1: Momentum Exhaustion (The Snapback)**
    *   **Trigger:** H4 Structural Inversion.
    *   **Condition:** ADX must be `> 60`.
    *   **Logic:** Captures violent mean-reversion when a parabolic trend mathematically breaks. Utilizes the existing "Close & Flip" and M15 Exhaustion filters.
*   **Vector 2: Trend Continuation (The Pullback)**
    *   **Trigger:** H4 Structural Inversion (treated as a retracement).
    *   **Condition:** ADX must be between `30` and `60`.
    *   **Logic:** Enters *with* the dominant trend. The H4 inversion is validated by an M15/H1 SMC FVG mitigation before firing. 
*   **Vector 3: Range Extraction (The Grid Basket)**
    *   **Trigger:** H4 structural bounds.
    *   **Condition:** ADX must be `< 30`.
    *   **Logic:** Fires a minimum-lot entry. Scales in dynamically at fixed ATR intervals if price moves adversely. 
    *   **Kill Switch:** If the ADX pushes above `30` (indicating a range breakout), the entire basket is liquidated instantly at market price.

## 3. Global Defenses & Capital Efficiency

*   **The Session Gate:** All H4 entry signals are completely blocked during the Asian session and the initial London Open. Entries are only armed during the London/New York overlap and the core New York session.
*   **Dynamic Risk Equalization:** Fixed `1.0` lot sizes are deprecated. All modules will calculate dynamic lot sizes representing exactly 1% account risk per entry (or the equivalent fractional base for the Grid module) to normalize drag from highly volatile assets like USOILm.
*   **H1 Structural Decay:** The passive tracking continues, but the Reaper module remains active to ruthlessly cut solitary trades at -0.5R if the H1 structure breaks.