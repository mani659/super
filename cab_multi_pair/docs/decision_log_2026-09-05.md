# Decision Log — 5 Sep 2026 Vol-Group Management + Path Logging

**Date:** 5 Sep 2026
**System:** CAB Multi-Pair Master (cab_multi_pair)
**Author:** Abrar
**Classification:** Demo experiment — observation-layer + management threshold split

---

## A. Context

Multi-week ledger review shows the system is still net negative in MT5 dollar
terms. R-positive outcomes are driven by a small number of outlier wins
(principally BTCUSDm and USTECm single-trade +8R to +17R events). The
median trade across all 11 pairs is approximately flat to slightly negative.

Key observations from the cumulative ledger:

- HIGH-volatility pairs (crypto, metals, index, oil) produce the outlier wins
  that fund the book. Their mean R is positive but variance is extreme.
- LOW-volatility FX pairs (EURUSDm, GBPUSDm, USDJPYm, EURGBPm, AUDNZDm)
  cluster near zero mean R. They rarely reach the 1.0R–1.5R MFE thresholds
  that trigger the lock gate, so they die at or near BE with small losses.
- Losers across all pairs share a pattern: shallow MFE (often <0.3R), deeper
  MAE, shorter duration. Winners show larger MFE and longer hold times.

All 11 pairs are KEPT ACTIVE this week. The goal is to test whether adjusting
management thresholds by volatility group improves the LOW-vol cluster without
destroying HIGH-vol outlier capture.

---

## B. What We Rejected (and Why)

### Continuous R-slider from tick 1 (global rule)
**Rejected.** High-volatility runners (BTC, Gold, Oil) occasionally produce
+3R to +17R trades that single-handedly offset weeks of small losses. A
continuous trailing SL from entry would clip these outliers by tightening
too early. The early portion of a trade's life needs room to breathe.
Deferred until path clock data shows a clear optimal entry-to-trail transition
point.

### Global half-lot close at mean MFE
**Rejected.** Counterfactual simulation of closing 50% at the population
mean MFE (approximately 0.6R across all pairs) produces an estimated
–11R worse outcome versus holding to current gates. The mechanism hurts
HIGH-volatility pairs more than it helps LOW-volatility pairs, because
HIGH-vol trades that reach 2R–5R after mean MFE would be prematurely
halved. Not implemented.

### Hard pair retirement this week
**Deferred.** The LOW-vol cluster is underperforming but not yet
statistically distinguishable from zero in a regime-dependent system.
Retiring pairs before the management experiment runs would conflate
the effect of threshold changes with the effect of pair removal.
Pair-level disable decisions are deferred to end-of-week review if
the vol-group experiment does not improve outcomes.

---

## C. What We Accepted

### Volatility group split
All 11 pairs classified into two groups:

**HIGH volatility:** BTCUSDm, ETHUSDm, XAUUSDm, XAGUSDm, USTECm, USOILm
**LOW volatility:** EURUSDm, GBPUSDm, USDJPYm, EURGBPm, AUDNZDm

### Management thresholds by group

| Parameter | HIGH | LOW |
|-----------|------|-----|
| BE_GATE_R | 0.5 | 0.5 |
| LOCK_GATE_R | 1.0–1.5 (per-pair, unchanged) | 0.8 |
| H1_MIN_HOURS | 6.0 | 12.0 |

LOW-vol pairs get a tighter BE gate (0.5R vs old 0.8R) and a lower lock
gate (0.8R vs old 1.0R). This means they lock break-even earlier and trail
sooner, acknowledging that LOW-vol pairs rarely push beyond 1.0R. The H1
structural breach age threshold is extended to 12 hours for LOW-vol, giving
slower-moving FX pairs more time before the breach check fires.

HIGH-vol pairs keep their existing per-pair LOCK_GATE_R values. BTC/ETH
remain at 1.5R lock, XAG at 1.2R, XAU/USTEC/USOIL at 1.0R. Only the BE
gate is lowered to 0.5R across all HIGH-vol pairs.

### Path logging (observation-layer)
Five new CSV columns added to `cab_performance_ledger.csv`:

- `TimeTo0_3R_Hours` — hours from open when peak_r first reached 0.3
- `TimeTo0_5R_Hours` — hours from open when peak_r first reached 0.5
- `TimeToMAE_0_5_Hours` — hours from open when MAE first hit –0.5R
- `VolGroup` — HIGH or LOW
- `H1_MinHours_Config` — the pair's H1_MIN_HOURS value

These are pure clocks. They do not trigger any trade action. The objective
is to measure winner vs loser path characteristics after entry.

### What stays the same
- Entry logic: unchanged (H4 inversion, RISK_OFF + COMPRESSION_LOW filter)
- Trailing formula: BE gate → lock gate → 1R-behind-peak trail (not continuous)
- Risk percent per pair: unchanged
- Pair list: all 11 active
- MAGIC_NUMBER, STAGNATION_HOURS, spread filters, lot math: unchanged

---

## D. Evidence Pointers

- HIGH-vol mean R across the cumulative ledger is approximately +0.65R,
  driven by occasional large winners. LOW-vol mean R is approximately 0.
- LOW-vol pairs reach 1.0R MFE in fewer than 20% of trades. The old
  LOCK_GATE_R of 1.0 was effectively unreachable for most LOW-vol trades,
  meaning they never entered the trailing phase and often died at BE or
  slightly below.
- Loser path pattern: MFE typically <0.3R within the first 2 hours, MAE
  reaches –0.5R quickly, trade closes within 4–8 hours. Winners show MFE
  >0.5R within 4–6 hours and hold 12–24+ hours.
- Partial-close at mean MFE counterfactual: estimated –11R vs actual.
  Simulation result documented in pre-experiment analysis.

---

## E. Explicit Non-Goals This Week

- **No entry signal changes.** H4 inversion logic, RISK_OFF filter, and
  session gating remain exactly as deployed.
- **No ADX or session hard filters.** These remain under observation in
  the broader system (H22 session hypothesis, F15 direction gate).
- **No PARTIAL_R execution.** The partial-close mechanism remains config-
  defined only. It will not be activated until path clock data reveals
  optimal R-thresholds from the LOW-vol cluster.
- **No pair removals or additions.** All 11 pairs remain live.
