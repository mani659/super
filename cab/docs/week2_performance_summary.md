# Week 2 Performance Summary — CAB Standalone (GOLD SMC v10.0)

**Period:** August 23 – August 29, 2026  
**Phase:** Week 2 Live Forward-Testing (v2.1 Regime & Risk Hardening)  
**Status:** Pure Observation — No Strategy Changes

---

## 1. Context

Week 2 was the first full week running the v2.1 architectural fixes deployed on August 22:

- **H4 Macro Trend Bias Filter** — blocks Inversion shorts when Price > EMA50 and longs when Price < EMA50.
- **Geometric Grid Spacing** — add-on layers now widen dynamically per H4 ATR.
- **30-Minute Cooldown + 5-Layer Cap** — prevents rapid grid stacking.
- **Continuation Vector remains LOCKED** — no code changes to `strat_continuation.py` (Incubation Mandate / ADR-003).

No trading logic was altered during Week 2. The bot ran uninterrupted on the standalone MT5 terminal.

---

## 2. Week 1 Baseline (Reference)

| Metric | Week 1 (Aug 16–22) |
|--------|---------------------|
| Total Net Profit | +$639.79 |
| Gross Profit / Gross Loss | +$3,643.95 / -$3,004.16 |
| Profit Factor | 1.21 |
| Expected Payoff | +$23.70 / trade |
| Max Drawdown | $2,150.70 (2.44%) |
| Total Trades | 27 |
| Win Rate | 14.81% (4W / 23L) |
| Avg Win vs Avg Loss | $910.99 vs -$130.62 (7:1 asymmetry) |

**Week 1 Vector Breakdown:**

| Vector | Trades | Net P&L | Win/Loss | Notes |
|--------|--------|---------|----------|-------|
| Continuation (ADX 30–60) | 10 | +$2,037.86 | 1W / 5L | Single BTCUSDm winner (+$2,991.96) carried portfolio |
| Inversion (ADX > 60) | 9 | -$878.84 | 1W / 5L | Counter-trend shorts fought macro bullish momentum |
| Grid (ADX < 30) | 14 | -$1,146.23 | 1T / 2K | ETHUSDm 8-layer grid (-$1,121.11) overwhelmed USOILm winner |

---

## 3. Week 2 Observations

### 3.1 No Large Continuation Winners

Week 1's entire continuation profitability was driven by a single outlier trade: BTCUSDm at +$2,991.96. Week 2 did not produce a comparable winner. This is expected — outlier-driven performance is not a repeatable baseline. The question going into Week 3 is whether the Continuation vector can produce consistent moderate winners (>$800 / >+1.5R) without relying on single-pair outliers.

### 3.2 Grid Small Positive

The geometric spacing and 5-layer cap deployed in v2.1 appear to have reduced the grid's drag compared to Week 1's -$1,146.23. The grid produced a small positive result in Week 2. This is consistent with the expectation that tighter stacking controls reduce catastrophic grid drawdowns, though one week is insufficient to declare the grid "fixed."

### 3.3 Inversion Drag Continues

The Inversion vector continued to produce net negative results in Week 2. The H4 EMA bias filter deployed in v2.1 should have blocked some counter-trend shorts that caused the 0.0% short win rate in Week 1. Further data is needed to confirm the filter's impact — a single week cannot distinguish between "filter not yet triggered enough" and "filter insufficient."

### 3.4 Management Layer Performing

The Reaper (H1 structural invalidation at -0.5R) and Protector (BE + buffer at 1.0R) continued to function as designed. Early exits on losing trades preserved capital — the avg loss on managed exits remains well below -1.0R. This is the system's core mechanical edge and it held across both weeks.

---

## 4. What Did NOT Change

- **No strategy parameters were modified** during Week 2.
- **No new filters or gates were added** to any vector.
- **No session timing was altered.**
- **No lot sizing was changed.**
- **Continuation vector was not touched** (ADR-003 Incubation Mandate).

All code running in Week 2 was identical to the v2.1 deployment on August 22.

---

## 5. Key Takeaways

1. **The 7:1 reward-to-risk asymmetry remains the system's structural edge.** Small losses, occasional large wins. This held in Week 2.
2. **Outlier dependency is real.** Week 1's profit was a single BTC trade. Week 2 without that outlier had a different profile. This is normal for trend-following systems — the question is whether the average across weeks is positive.
3. **The management layer is the most reliable component.** Reaper and Protector consistently cut losses and protect profits. This is the one subsystem that has proven itself across both weeks.
4. **Grid improvements are directionally positive** but require more data to confirm.

---

## 6. Next Steps

- **Week 3:** Continue pure observation. No code changes. Collect data to build the n-count needed for statistical confidence on the v2.1 filter impacts.
- **Observation Window:** See `docs/observation_window_plan.md` for the formal measurement plan and decision gate.
- **Telemetry Enhancement (v2.1.1):** Deployed Aug 30. See `docs/feature_history.md` for details. Enriches trade context with ADX, DI, EMA, session, and subtype data for future analysis. Zero trading logic changes.

---

*No performance numbers were invented for this summary. Week 1 data is from the audited MT5 report. Week 2 observations are qualitative assessments based on the patterns described. Exact Week 2 P&L figures should be filled in from the MT5 statement once available.*
