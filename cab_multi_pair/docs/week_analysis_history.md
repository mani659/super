# CAB MASTER – Week-by-Week Analysis History

## Purpose
Permanent record of statistical reviews so future comparisons are easy and nothing is lost.

---

## Week 2 / W33 (17–21 Aug 2026) – “The Outlier Week”

| Metric              | Value          | Notes |
|---------------------|----------------|-------|
| Trades              | 39             | — |
| Win Rate            | 61.5%          | — |
| Total Realized R    | +35.82 R       | Dominated by two large winners |
| Avg R               | +0.92          | — |
| Profit Factor       | 4.83           | — |
| Long WR / R         | 66.7% / +20.2  | Strong |
| Short WR / R        | 50.0% / +15.6  | Temporary (driven by one USTECm short) |
| Largest Winner      | +17.23 R (USTECm SELL) | Extreme outlier |
| Second Largest      | +10.82 R (BTCUSDm BUY) | — |
| GBP pairs           | Net negative   | Still a drag |

**Key Observation:** The strong headline numbers were not a new baseline. Removing the two largest winners collapses most of the positive expectancy.

---

## Week 3 / W34 (25–28 Aug 2026) – “Reversion Week”

| Metric              | Value          | Notes |
|---------------------|----------------|-------|
| Trades              | 42             | — |
| Win Rate            | 38.1%          | Sharp drop |
| Total Realized R    | –2.54 R        | — |
| Avg R               | –0.06          | — |
| Profit Factor       | 0.71           | Below 1.0 |
| Long WR / R         | 42.9% / –0.3   | Deteriorated |
| Short WR / R        | 33.3% / –2.3   | Bleed returned |
| Dominant Exit       | H1_STRUCT_BREACH (30 of 42) | Protective exits working hard |

**Key Observation:** System reverted toward its longer-term behaviour (mid-30s to low-40s win rate). Confirms that W33 was variance, not a structural upgrade.

---

## Full Recent Ledger Snapshot (14–28 Aug 2026)

- Total trades in ledger: 87
- Overall Realized R: +32.47 R (still positive only because of the W33 outliers)
- Overall Win Rate: 48.3%
- Best pairs: USTECm, BTCUSDm, USOILm, XAUUSDm
- Worst pairs: EURGBPm, GBPUSDm, AUDNZDm

---

## Logging Upgrade Deployed – 30 Aug 2026

From this point forward every new closed trade records:

- TimeToMFE_Hours / TimeToMAE_Hours
- BE_Hit / Lock_Hit
- EntrySpreadPoints
- EntryATR / EntryATR_Pct
- ActiveSameDirection / ActiveCorrelated

These fields are observation-only and do not affect trading decisions.

---

## Next Review Checkpoint
End of Week 4 (after ~40–50 new trades under enhanced logging).  
Focus: R-velocity, spread cost, gate effectiveness, persistence of short-side and GBP weakness.