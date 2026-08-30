# CAB MASTER: Week 4 Operational Plan & Performance Benchmark

> **Execution Period:** Week 4 Trading Week (approx. 1–5 / 8 Sep 2026)  
> **Phase:** Incubation Phase (Data Accumulation) – **Enhanced Logging Active**  
> **Status:** Codebase Locked 🔒 (except pure observation-layer logging)

---

## 🎯 Primary Objective
Continue unbroken data collection under the new enhanced logging regime.  
Goal: accumulate another full week of high-quality, multi-dimensional trade records so that the next statistical review can properly test:

- R-velocity (TimeToMFE / TimeToMAE)
- True cost of spread
- BE_Hit / Lock_Hit effectiveness
- Same-direction and correlated cluster risk
- Whether the short-side bleed and GBP toxicity persist after costs

We are still in pure data-gathering mode. No strategy changes.

## 🔒 Baseline Configurations (Locked)
* **Execution Core:** Python Decoupled Architecture (`main.py` + `run.bat` Watchdog).
* **Filters:** 6-Hour H1 Suppression, Hostile Environment Gate (Risk Off + Low Compression), and Max Spread Gate remain ACTIVE.
* **Symbol List:** ALL 11 pairs remain active (No pairs sidelined yet).
* **New Logging Fields (read-only observation):**  
  `TimeToMFE_Hours`, `TimeToMAE_Hours`, `BE_Hit`, `Lock_Hit`,  
  `EntrySpreadPoints`, `EntryATR`, `EntryATR_Pct`,  
  `ActiveSameDirection`, `ActiveCorrelated`.

## 🧪 Key Hypotheses Under Observation (What to look for at end of Week 4)

1. **Short-Side Bleed:** Does `H4_MACRO_SELL` continue to underperform after accounting for spread and R-velocity?
2. **GBP Toxicity Check:** Do GBPUSDm and EURGBPm remain net negative once EntrySpreadPoints are included?
3. **ADX Edge Validation:**  
   - Does ADX < 20 remain a reliable trap?  
   - Is the 30–50 band still the most productive?
4. **R-Velocity:** How quickly do winning trades reach their MFE? Is there a useful early-exit threshold?
5. **Gate Effectiveness:** What percentage of trades that hit BE_Gate or Lock_Gate actually finish profitable?
6. **Cluster Risk:** Do high `ActiveSameDirection` or `ActiveCorrelated` counts correlate with worse outcomes?
7. **Overall System Expectancy:** Does Profit Factor remain > 1.50 over a non-outlier week?

## 🚫 Non-Negotiable Operational Rules
1. **Zero Mid-Week Tweaks:** No manual intervention, no code tweaks to trading logic, no asset quarantines.
2. **End-of-Week Review:** Run full Jupyter / Pandas analysis on the new ledger (including the new columns) immediately after Friday market close.
3. **Logging only:** Any future changes must first be proven by the data collected this week.

## 📋 Success Criteria for Moving Toward Phase 2
- At least 40–50 additional closed trades under the enhanced logging.
- Clear statistical answers (even if negative) on the seven hypotheses above.
- Confirmation that the new columns are being written correctly and contain usable values.