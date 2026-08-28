# CAB MASTER: Week 3 Operational Plan & Performance Benchmark

> **Execution Period:** Week 3 Trading Week  
> **Phase:** Incubation Phase (Data Accumulation)  
> **Status:** Codebase Locked 🔒

---

## 🎯 Primary Objective
Accumulate another continuous week of unbroken data to validate if the massive jump in Week 2's win rate (55.8%) is the new baseline created by our protective filters, or simply a favorable market variance. We must push the total sample size closer to the 170–200 trade benchmark without altering the code.

## 🔒 Baseline Configurations (Locked)
*   **Execution Core:** Python Decoupled Architecture (`main.py` + `run.bat` Watchdog).
*   **Filters:** 6-Hour H1 Suppression, Hostile Environment Gate (Risk Off + Low Compression), and Max Spread Gate remain ACTIVE.
*   **Symbol List:** ALL 11 pairs remain active (No pairs sidelined yet, despite GBP weakness).

## 🧪 Key Hypotheses Under Observation (What to look for in Week 3)

During the Week 3 end-of-week review, the data science analysis must specifically answer the following:

1.  **The Short-Side Bleed:** Does the `H4_MACRO_SELL` win rate remain suppressed (sub-35%), or does it mean-revert to match the Long win rate?
2.  **GBP Toxicity Check:** Do GBPUSDm and EURGBPm continue to act as a localized drag on the portfolio? If they fail again in Week 3, they will be formally flagged for quarantine in Phase 3.
3.  **ADX Edge Validation:** 
    *   Did trades taken with an H4 ADX > 50 continue to capture outsized R-multiples?
    *   Did the ADX < 20 zone continue to trap the bot?
4.  **Overall System Expectancy:** Does the Profit Factor remain > 1.50, and does the max drawdown remain securely under 5%?

## 🚫 Non-Negotiable Operational Rules
1.  **Zero Mid-Week Tweaks:** No manual intervention, no code tweaks, no asset quarantines. Let the algorithm ingest the market data raw.
2.  **End-of-Week Review:** Run the Jupyter/Pandas ADX and Asset breakdown on `cab_performance_ledger.csv` immediately after Friday market close.