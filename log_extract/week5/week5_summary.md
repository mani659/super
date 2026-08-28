# Week 5 End-of-Week Analysis Summary
**Generated:** 2026-08-22
**Account:** 474167713 · Exness-MT5Trial15
**Period:** Aug 18–22 2026

---

## Equity

| Metric | Week 4 (W4) | Week 5 (W5) |
|---|---|---|
| Start equity | ~$6,723 | $6,590.72 |
| End equity | ~$6,723 | $6,976.50 |
| Week P&L | ~-$1,067 | +$385.78 |
| Inception drawdown | -32.8% | -30.2% |

---

## Ghost 202 Fill Counts

| Metric | Week 4 | Week 5 | Combined |
|---|---|---|---|
| Total 202 fills | 347 | 17 | 85 (since archive reset) |
| SELL fills | 347 (100%) | 17 (100%) | - |
| BUY fills | 0 | 0 | 0 |
| FILL_NO_SL | [W4 baseline] | 0 | 0 |

---

## Five Gate Metrics — Confirmation Check

Target: same directional signal as Week 4. "CONFIRMED" = W5 within 3pp of W4.

| Gate | W4 Signal | W5 Result | Status |
|---|---|---|---|
| LONDON win rate | ~28.6% (must stay <35%) | DATA MISSING | PENDING_MT5_JOIN |
| NY_CLOSE+H4_UP win rate | ~27.8% (must stay <32%) | DATA MISSING | PENDING_MT5_JOIN |
| ATR Q2 win rate | ~27.4% (must stay <30%) | DATA MISSING | PENDING_MT5_JOIN |
| Conviction 20-40 win rate | ~33% (must stay <35%) | DATA MISSING | PENDING_MT5_JOIN |
| ADX 20-25 win rate | ~32.1% (must stay <33%) | DATA MISSING | PENDING_MT5_JOIN |

Note: win/loss outcomes require joining audit CSV to MT5 trade history.
Fill counts and condition distributions are available from audit CSV alone
(see session_h4_crosstab_w5.txt for those numbers).

---

## 204 Ghost Cache

| Metric | Expected | Actual |
|---|---|---|
| Total fires | >0 (first week after decouple fix) | 0 |
| N_LAYERS action needed? | Only if zero after Day 5 | yes |

---

## F6 Cross-Bot Gate

| Metric | Result |
|---|---|
| GHOST_ARM_BLOCKED_ST_LONG fires | 0 |
| Gate confirmed wired? | no (Zero F6 fires) |

---

## CAB Fluid Matrix (first week with logs)

| Milestone | Fires |
|---|---|
| REAPER | 0 |
| PROTECTOR | 0 |
| HARVESTER | 0 |
| OSI | 0 |

---

## SuperTrend (From MT5 HTML)

| Metric | Week 4 | Week 5 |
|---|---|---|
| Total entries | 110 | 252 (84 closed round-trips) |
| Avg P&L | +$2.92 | +$3.30 (52.4% Win Rate) |
| XAUUSDm avg P&L | negative | +$23.90 (85.7% Win Rate) |
| XAUUSDm disable action? | No (week 2 of 3) | no |

---

## Files Required for Full Win/Loss Gate Analysis

The session × H4 gate confirmation (the primary Week 5 objective)
requires joining the audit CSV to MT5 trade outcomes. This needs:

1. `sniper_v51_live_audit.csv` — ✅ available
2. MT5 ReportHistory HTML for Week 5 (Aug 18–22) — missing
3. MT5 ReportHistory HTML for Week 4 (Aug 11–15, already in root) — ReportHistory-474167713.html

Next step for session: upload both exports and run the join to get
win/loss per session × H4 direction bucket for the combined W4+W5 dataset.
