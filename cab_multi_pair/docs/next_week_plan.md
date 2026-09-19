# CAB MASTER: Week 5 Operational Plan — Vol-Group Experiment

> **Execution Period:** Week 5 Trading Week (approx. 8–12 Sep 2026)
> **Phase:** Demo Experiment — Vol-Group Management + Path Logging
> **Status:** Task 1 (vol-group thresholds) + Task 2 (path clocks) locked; entries unchanged; all 11 pairs live

---

## Context

This is not a continuation of pure data accumulation. We are running a
controlled experiment: does splitting management thresholds by volatility
group improve the LOW-vol FX cluster without destroying HIGH-vol outlier
capture?

See `decision_log_2026-09-05.md` for the full rationale, rejected
alternatives, and evidence pointers.

---

## Objectives

1. **Measure LOW-vol improvement.** Compare mean R, SL hit rate, and
   BE_Hit rate for EURUSDm/GBPUSDm/USDJPYm/EURGBPm/AUDNZDm against
   the prior baseline (pre-vol-group thresholds).

2. **Confirm HIGH-vol still captures outliers.** Verify that BTCUSDm,
   ETHUSDm, XAUUSDm, XAGUSDm, USTECm, USOILm still produce occasional
   trades >=1.5R. The lower BE gate (0.5R) should not clip these because
   the lock gate values are unchanged for HIGH pairs.

3. **Fill path clocks.** Collect TimeTo0_3R, TimeTo0_5R, and
   TimeToMAE_0_5 data across both groups. At week end, compare winners
   vs losers on these path fields to identify early-differentiation
   signals.

4. **Re-score the pair table.** Standard columns: n (trade count),
   sum R, mean R, profit factor, percentage of loss mass. Same format
   as prior weekly reviews.

---

## Success Metrics (directional, not forced)

| Metric | LOW-vol target | HIGH-vol target |
|--------|---------------|-----------------|
| BE_Hit % | Higher than prior baseline | Not materially changed |
| 0-MFE deaths | Fewer pure-zero MFE exits | Not materially changed |
| Mean R | Not worse than baseline | Not collapsed (still >+0.3R) |
| Sum R | Improved or flat vs baseline | Still positive |
| >=1.5R trades | N/A | Still present if market provides |
| Path columns | Populated on new ledger file | Populated on new ledger file |

We are NOT forcing PF > 1.5. The goal is directional improvement in the
LOW-vol cluster and confirmation that HIGH-vol is not harmed.

---

## Locked Configurations

- **BE_GATE_R:** 0.5 all pairs
- **LOCK_GATE_R:** HIGH per-pair (1.0–1.5); LOW = 0.8
- **H1_MIN_HOURS:** HIGH 6.0h; LOW 12.0h
- **Path columns:** TimeTo0_3R_Hours, TimeTo0_5R_Hours, TimeToMAE_0_5_Hours, VolGroup, H1_MinHours_Config
- **Entry logic:** unchanged
- **Pair list:** all 11 active
- **RISK_PERCENT, MAGIC_NUMBER, STAGNATION_HOURS, spread filters:** unchanged

---

## Ops

1. **Archive old ledger.** Rename `cab_performance_ledger.csv` to
   `cab_performance_ledger_pre_volgroup.csv` (or similar) before the
   first trade of the week. Start a fresh file with the new schema
   so old rows with missing columns do not cause append issues.

2. **Zero mid-week strategy tweaks.** No code changes to entries,
   exits, gates, or thresholds during the experiment week. Observation-
   layer logging only if a critical bug is found.

3. **End-week review.** Analyze the new ledger file only. The path
   clock columns should have data for all new trades. Standard
   scorecard: pair table, vol-group comparison, path-field winner/
   loser analysis.

4. **Decision points at week end:**
   - If LOW-vol mean R improves by >=0.1R vs baseline: vol-group
     thresholds validated, keep as permanent.
   - If LOW-vol mean R is flat or worse: evaluate whether the
     LOCK_GATE_R of 0.8 is still too high, or whether the issue
     is entry quality rather than management.
   - If HIGH-vol sum R collapses (no trades >=1.5R, mean R <0):
     investigate whether the 0.5R BE gate is causing premature
     exits. Revert BE_GATE_R to per-group values if confirmed.
