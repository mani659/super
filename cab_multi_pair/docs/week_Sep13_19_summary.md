# CAB Multi-Pair — Week Summary: Sep 13–19 2026

**Date:** 19 Sep 2026
**Account:** 260714012 (standalone MT5 terminal)
**Magic:** 999555
**Phase:** LTF structure research logging (Phase 1–2)

---

## Context

- LTF structure research logging deployed ~13 Sep 2026 (Phase 1–2). Entries/management unchanged.
- Three M15 structure flags (liq_swept_prior, fvg_with_signal, dist_next_pool_atr) wired into ledger.py and intelligencia.py.
- Account 260714012, magic 999555.

---

## Results (MT5 ground truth)

| Metric | Sep 6–12 (prior) | Sep 13–19 (this week) |
|--------|-------------------|------------------------|
| Closed trades | n=41 | n=45 |
| Net P&L | ≈ –$929 | ≈ **–$324** |
| W/L | — | 20W / 25L |

Improved vs prior week but still negative.

---

## Ledger (45 rows, closes Sep 13–19)

| Metric | Value |
|--------|-------|
| sumUSD | ≈ –$292 |
| sumR | ≈ –3.45 |
| win% | ≈ 44% |

### Exit Breakdown

| Exit Type | Count |
|-----------|-------|
| H1_STRUCT_BREACH | 13 |
| BROKER_TP | 12 |
| BROKER_SL | 12 |
| OPP_H4_SIGNAL | 6 |
| STAGNATION_DECAY | 2 |

### BROKER_SL Cohort

- n=12, sumUSD ≈ –$584, avgR ≈ –0.75R
- Many duration 2–4h, BE never armed
- This cohort is the primary loss driver

### Management Split (BE_Hit)

| BE_Hit | Net P&L |
|--------|---------|
| True | ≈ +$504 |
| False | ≈ –$791 |

Management split dominates — trades that reach BE are net positive; those that don't are net negative.

---

## LTF Flags (research logging)

| Flag | Status | Use as live filter? |
|------|--------|---------------------|
| LiqSweptPrior | 0 on ALL rows → no information | **NO** — diagnose later |
| FvgWithSignal | Fvg=1 worse in $ than Fvg=0 on this sample | **NO** — no live filter |
| DistNextPoolAtr | <0.1 ATR bucket least bad / slightly green; farther buckets weaker | **HINT ONLY** — n too small |

**Phase 3 threshold NOT met** (need ≥80 new closes with valid LTF fields or 4 weeks from 13 Sep).

---

## What Did NOT Change

- No entry filters from LTF flags
- No ZR, no flip, no ATR-breakout deploy
- No pair removals, no risk% changes

---

## Interpretation

- Book still negative expectancy in this segment
- Logging pipeline works — all three LTF columns populated on new entries
- No proof for promoting LTF flags to live gates
- LiqSweptPrior all-zero is a telemetry issue to diagnose, not a trading signal
- BROKER_SL cohort (n=12, –$584) is the actionable loss area — BE never armed on these trades
