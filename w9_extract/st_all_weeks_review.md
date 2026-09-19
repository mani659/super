# SuperTrend All-Week Performance Review

**Bot:** SuperTrend (Magic 101234-408213)
**Data:** MT5 ReportHistory (Aug 9 - Sep 18, 2026)
**Total:** 466 trades | WR: 39.3% | P&L: $-67.38

---

## Week-by-Week Summary

| Week | Dates | Trades | WR | P&L | Avg | Verdict |
|------|-------|--------|-----|-----|-----|---------|
| W1 | Aug 9-15 | 108 | 38.9% | $-88.92 | $-0.82 | BLEED |
| W2 | Aug 16-22 | 40 | 50.0% | $+136.36 | $+3.41 | KILLER |
| W3 | Aug 23-29 | 78 | 29.5% | $-81.96 | $-1.05 | BLEED |
| W4 | Aug 30-Sep 5 | 77 | 40.3% | $-39.32 | $-0.51 | WEAK |
| W5 | Sep 6-12 | 78 | 34.6% | $-96.46 | $-1.24 | BLEED |
| W6 | Sep 13-19 | 85 | 47.1% | $+102.92 | $+1.21 | KILLER |

**Pattern:** Alternating KILLER/BLEED weeks. W2 and W6 were the only profitable weeks. W1, W3, W5 were the worst.

---

## Per-Symbol Overall Rating

| Rank | Symbol | Trades | WR | Total P&L | Avg P&L | Rating |
|------|--------|--------|-----|-----------|---------|--------|
| 1 | **BTCUSDm** | 36 | 55.6% | **$+50.76** | $+1.41 | **KILLER** |
| 2 | **XAUUSDm** | 49 | 42.9% | **$+29.26** | $+0.60 | **SOLID** |
| 3 | USDJPYm | 42 | 45.2% | $+0.60 | $+0.01 | OK |
| 4 | AUDNZDm | 63 | 38.1% | $-1.01 | $-0.02 | WEAK |
| 5 | ETHUSDm | 55 | 30.9% | $-2.74 | $-0.05 | WEAK |
| 6 | EURUSDm | 22 | 31.8% | $-4.86 | $-0.22 | WEAK |
| 7 | GBPUSDm | 22 | 40.9% | $-4.94 | $-0.22 | WEAK |
| 8 | EURGBPm | 43 | 25.6% | $-6.46 | $-0.15 | WEAK |
| 9 | USTECm | 40 | 37.5% | $-8.22 | $-0.21 | WEAK |
| 10 | **USOILm** | 55 | 47.3% | **$-10.77** | $-0.20 | **BLEED** |
| 11 | **XAGUSDm** | 39 | 35.9% | **$-109.00** | $-2.79 | **BLEED** |

---

## Pair Deep Dive

### KILLER: BTCUSDm (+$50.76)
- Best overall pair. 55.6% WR with highest avg P&L.
- Consistent: profitable in 4/6 weeks.
- W2 standout: +$32.79 (80% WR, 5 trades).
- Only weak week: W3 (-$12.15).
- **Action: KEEP. Never disable.**

### SOLID: XAUUSDm (+$29.26)
- Second best. High variance but net positive.
- W2: +$91.54 (100% WR, 4 trades) — best single-week performance.
- W1: -$75.52 (25% WR) — worst single-week performance.
- W6: +$47.24 (60% WR) — strong recovery.
- **Action: KEEP. Lock confirmed.**

### OK: USDJPYm (+$0.60)
- Break-even. 45.2% WR across 42 trades.
- Never had a big win or big loss.
- **Action: KEEP but monitor.**

### WEAK: AUDNZDm, ETHUSDm, EURUSDm, GBPUSDm, EURGBPm, USTECm
- All negative but small losses (-$1 to -$8).
- AUDNZDm: Most trades (63) but only 38.1% WR. Volume without edge.
- ETHUSDm: 30.9% WR — worst WR of all pairs. Small losses add up.
- EURGBPm: 25.6% WR — lowest WR overall.
- **Action: Monitor. Consider disabling if trend continues.**

### BLEED: USOILm (-$10.77)
- 47.3% WR but net negative — avg loss exceeds avg win.
- Inconsistent: profitable in W1 (+$14.30) but bled in W4 (-$20.69).
- **Action: DISABLE or reduce size. Cross-bot negative (also negative in CAB).**

### BLEED: XAGUSDm (-$109.00) — WORST PAIR
- Massive losses. 35.9% WR with -$2.79 avg.
- W1: -$38.00, W4: -$48.75, W5: -$79.65 — three catastrophic weeks.
- W2 and W6 were positive but couldn't offset the damage.
- **Action: DISABLE IMMEDIATELY. This pair alone accounts for more loss than the entire bot's net deficit.**

---

## Key Insights

1. **XAGUSDm is the #1 problem.** Without XAGUSDm, the bot would be +$41.62 net positive. The pair bleeds massively and inconsistently.

2. **BTCUSDm and XAUUSDm carry the bot.** Together they're +$80.02. Everything else is negative.

3. **Win rate is misleading.** USOILm has 47.3% WR (decent) but loses money. XAGUSDm has 35.9% WR and loses catastrophically. WR alone doesn't determine profitability.

4. **Week alternation pattern.** KILLER weeks (W2, W6) alternate with BLEED weeks (W1, W3, W5). This suggests the bot profits in trending markets and loses in ranging/choppy markets.

5. **Volume without edge.** AUDNZDm has the most trades (63) but is slightly negative. More trades ≠ more profit.

---

## Recommended Actions

| Priority | Action | Impact |
|----------|--------|--------|
| **P0** | DISABLE XAGUSDm | Removes -$109 bleed → bot becomes +$41.62 net |
| **P1** | DISABLE USOILm | Removes -$10.77 bleed |
| **P2** | Monitor ETHUSDm, EURGBPm | If W7 negative, disable |
| **P3** | LOCK BTCUSDm, XAUUSDm | Never disable these two |
| **P4** | Investigate W1/W3/W5 pattern | What market condition causes BLEED weeks? |
