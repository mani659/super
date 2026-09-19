# Post-Gate Plan — CAB Standalone

**Date:** September 13, 2026  
**Phase:** Post-Gate — Continuation Entries Disabled  
**Status:** Active

---

## 1. Decision Summary

The observation gate (Aug 30 – Sep 12) **FAILED**.

- Continuation (magic 9995552) did not produce large winners during the window.
- Tagged Continuation trades: ~0 wins / 8 losses across the observation period.
- Window net P&L: deeply negative. The Continuation vector is a net drag on the system.

**Action taken:** DISABLE Continuation ENTRIES only.

- `strat_continuation.py` is **NOT deleted**. It remains in the codebase for reference.
- `manage_continuation_positions()` continues to run for any residual open Continuation legs. These must be managed to completion (Protector, Reaper, Harvester, loss caps).
- No new entries will be opened under magic 9995552.

## 2. What Remains Live

| Component | Magic | Status |
|-----------|-------|--------|
| Inversion entries | 9995551 | LIVE — unchanged |
| Grid entries | 9995553 | LIVE — unchanged |
| All position management (Protector, Elastic Trailing, Reaper, Harvester) | all | LIVE — unchanged |
| Loss caps (symbol + portfolio) | all | LIVE — unchanged |
| Telemetry (v2.1.1 + v2.1.2) | all | LIVE — unchanged |

## 3. Explicit Non-Goals

The following are **explicitly NOT part of this plan:**

- Zone Recovery
- Signal flip (e.g., Grid becomes trend-following)
- New timeframe confirmation filters
- Continuation parameter tweaks (the vector is disabled, not tuned)
- Risk% increase on Inversion or Grid

## 4. Next Measurement Window

**Duration:** 2 calendar weeks from deploy **OR** 30 closed Inversion + Grid trades, whichever comes later.

**Metrics to track:**

| Metric | Source | Target |
|--------|--------|--------|
| Net P&L (9995551 + 9995553) | harvest log | ≥ $0 |
| Max drawdown | trade_context.json | ≤ 10% of account |
| Inversion exit mix | harvest log | OSI + Reaper + Harvester distribution |
| Grid VWAP vs ADX-kill vs loss-cap counts | harvest log | Understand which exit mechanism dominates |

## 5. End-Window Decision Table

| Outcome | Action |
|---------|--------|
| Net P&L ≥ $0 | Continue Inversion + Grid as-is. No changes. |
| Net P&L < $0 but controlled (DD ≤ 10%, no single vector dominating losses) | Consider Inversion throttle in a **NEW plan**. Do not improvised adjustments. |
| Drawdown breach (> 10%) | PAUSE all entries. Full review before resuming. |

---

**Reference:** See `docs/session_handoff.md` for current operational state.
