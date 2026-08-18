# CAB MASTER: Week 2 Operational Plan & Performance Benchmark

> **Execution Period:** Next Trading Week  
> **Phase:** Incubation Phase (Data Accumulation)  
> **Status:** Empirically Optimized & Forward Testing 🔒

---

## 🎯 Primary Objective

Accumulate an additional **70–100 completed trades** under live market conditions to actively validate our two newly deployed data-informed fixes:
- **Time-Gated H1 Suppression:** Measuring whether suppressing premature structural breach exits under 6 hours successfully stops the bleed in short-duration low-compression trades.
- **Hostile Environment Filter:** Tracking capital preservation by blocking new entries during combined `RISK_OFF` + `COMPRESSION_LOW` conditions.
- **Toxic Liquidity Immunity:** Confirming the new `MAX_SPREAD` execution gate successfully blocks trades during Friday rollover, Sunday open, and major news spikes.
- **Asset-Specific Trailing (BE/LOCK Gates):** Observing the impact of the newly tethered `BE_GATE_R` on high-volatility pairs (Gold, Crypto) to see if early break-even locking reduces full `-1.0 R` drawdowns.

---

## 🔒 Baseline Configurations (Locked)

* **Execution Core:** Python Decoupled Architecture (`main.py` + `run.bat` Watchdog).
* **Sampling Window:** H4 / H1 strictly completed candle index `1` and `2`.
* **Symbol List:** Active on all designated symbols (No pairs removed yet).
* **Risk Management:** Dynamic ATR risk distances + R-slider trailing stop.
* **Intelligencia Logging:** Active (Logging Session, ATR state, DXY proxy, and Risk Sentiment).

---

## 📊 Week 1 Baseline Benchmarks (To Compare Against)

We will evaluate Week 2 data directly against these established Week 1 metrics during our end-of-week review session:

| Metric Category | Week 1 Baseline | Week 2 Goal / Focus |
| :--- | :--- | :--- |
| **Total Sample Size** | 98 Trades | Reach **170–200 Cumulative Trades** |
| **Overall Realized R** | -8.67 R | Monitor equity curve variance |
| **Win Rate** | 25.51% | Monitor stability across market regimes |
| **Average MFE (Peak)** | +0.60 R | Verify peak profit behavior |
| **Median MFE** | +0.30 R | Verify median profit threshold stability |
| **Top Session (LON_NY)** | +1.96 R (37.9% WR) | Test if London/NY Overlap remains profitable |
| **Worst Session (NY)** | -4.31 R (9.09% WR) | Test if standalone NY remains toxic |
| **Top Symbol (ETHUSDm)**| +2.08 R | Track stability |
| **Worst Symbol (USOILm)**| -6.30 R | Observe if Oil continues bleeding or mean-reverts |

---

## 🧪 Key Hypotheses Under Observation

During Week 2, we are actively observing the following hypotheses under forward-testing conditions:

1. **6-Hour Survival Edge:** Does the new 6-hour age filter on `H1_STRUCT_BREACH` allow low-compression trades to absorb initial noise and mature into the historically profitable 6–24 hour window?
2. **Capital Preservation:** Does the `RISK_OFF` + `COMPRESSION_LOW` filter mathematically improve overall system expectancy by dropping hostile, low-liquidity signals?
3. **London/NY Overlap Superiority:** Does trading exclusively during liquidity overlaps maintain a positive expectancy after the above filters are applied?
4. **MFE Retraction Behavior:** Does average peak profit stay near +0.60 R while median stays near +0.30 R?

---

## 🚫 Non-Negotiable Operational Rules

1. **Zero Mid-Week Tweaks:** No manual intervention, stop adjustments, or parameter tuning based on daily drawdown or winning streaks.
2. **Watchdog Enforcement:** If Python drops, `run.bat` must handle automatic reboot without manual trade modification.
3. **End-of-Week Review:** Run full statistical analysis on `cab_performance_ledger.csv` immediately after Friday market close.