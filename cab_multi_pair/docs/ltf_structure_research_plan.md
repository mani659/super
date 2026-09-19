# LTF Structure Research Plan — cab_multi_pair

**Date:** 13 Sep 2026  
**Status:** Phase 1–2 instrument only (no live filters)

---

## Hypothesis

At H4 inversion entry time, LTF (M15) liquidity/structure state may condition expectancy vs unfiltered H4 inversion.

## Phase 0: Live Risk Unchanged

Loss caps, half-risk, XAG 0.5%, management rules stay as-is. **No new entry filters.**

## Phase 1 — Three Flags Only

Frozen definitions; implement in later prompts.

1. **liq_swept_prior** (0/1): nearest opposite-side swing high/low (last 20 M15 bars) was traded through before signal time.
2. **fvg_with_signal** (0/1): unfilled 3-candle FVG on M15 in the signal direction within last 30 M15 bars.
3. **dist_next_pool_atr** (float): distance in M15-ATR units to the next same-direction swing pool (0 if none).

## Phase 2

Log flags on every new entry into intelligencia/ledger. **Zero impact on order send, SL, management.**

## Phase 3

After ≥80 closed new trades OR 4 weeks, compare E[R] and E[$] baseline vs flag splits. Holdout: first half explore, second half confirm (or time split). Kill rules that do not improve after costs.

## Phase 4

Only if a rule clears the bar → single filter in a **NEW plan**. Not this deploy.

## Explicit Non-Goals

- No Zone Recovery
- No signal flip
- No live OB discretionary logic
- No stacking extra SMC concepts
- No changes to BE/LOCK/H1/stagnation rules in this research deploy
