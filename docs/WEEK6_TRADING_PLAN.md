---

# Week 6 Trading Plan
**Period:** Aug 25–29 2026
**Account:** 474167713 · Exness-MT5Trial15
**Phase:** Phase 2 Demo Testing — Statistical Gate Implementation
**Last Updated:** Aug 22 2026

---

## 1. Objective

Week 6 has two objectives in priority order.

**Primary:** Collect Ghost 202 session-labelled data in a week where Gold
is not strongly trending, enabling the combined W4+W5+W6 dataset to reach
the n thresholds required for statistical gate confirmation. The five gates
(LONDON, NY_CLOSE+H4_UP, ATR Q2, conviction, ADX dead zone) cannot be
confirmed from 87 total fills — 81 of which are from a single trending week.

**Secondary:** Determine whether the CAB BUY/SELL win rate gap (F9/F10,
17.2pp across W4+W5) holds in different market conditions. This is the
H9 confirmation window.

No new feature changes are planned mid-week. The only change entering Week 6
was N_LAYERS_DEFAULT = 2 in ghost_super/ghost_cache.py, applied before
the week started. (Exception: The critical Phase A MarketPulseEngine data staleness bug was hotfixed mid-week on Aug 26).

---

## 2. What Is Running This Week

### Ghost Grid (XAUUSDm)
- Magic 202: live SELL reversals. No session filters yet — gates are still
  being confirmed. All sessions remain open.
- Magic 201: shadow mode, virtual fills only. No change.
- Magic 204: N_LAYERS=2 entering this week (lowered from 3). First fires
  expected. Monitor daily. If zero fires after Day 5, escalate before
  changing anything — at n=2 a persistent zero is a deeper signal problem.
- Probe arming: TRENDING_UP / TRENDING_DOWN / UNKNOWN still blocked.
- F6 gate: ST LONG thesis on XAUUSDm suppresses UP_PROBE arming. Wired.

### SuperTrend (11 symbols)
- All 11 symbols running unchanged.
- Focus pair: XAUUSDm (magic 301890) — reversed to strongly positive in
  W5 (+$167, 85.7% WR, n=7). Three-week disable trigger not met.
  Continue running.
- No parameter changes. No scaling. Account remains in drawdown.

### CAB Watcher (all symbols)
- Running unchanged on all symbols.
- Monitoring focus: BUY vs SELL win rate split across Week 6 fills.
  A ranging Gold week will reveal whether F9/F10 is structural (direction
  misalignment always present) or regime-specific (appeared only because
  Gold trended strongly in W4+W5).

---

## 3. Pre-Approved / Excepted Changes This Week

With the exception of the Phase A MarketPulseEngine architecture hotfix deployed mid-week (Aug 26), the only pre-approved mid-week action is the same one that has existed
since Week 1:

**If 204 fires zero times after Day 5 of Week 6:** This is not actionable
with a parameter change at n=2. N_LAYERS cannot go below 2 (n=1 means
fire immediately on first virtual layer, which is equivalent to 202).
Escalate to analysis session before any further action.

Everything else — session filters, ATR gates, conviction gates, CAB
direction gate, any SuperTrend symbol disables — waits for end-of-week
data analysis.

---

## 4. Daily Monitoring Checklist

```bash
# Check 1 — threads alive
grep "Heartbeat OK" logs/unified_runner.log | tail -3

# Check 2 — 204 firing
grep -c "GHOST_CACHE_FIRE" logs/sniper_hunter.log

# Check 3 — F6 gate
grep -c "GHOST_ARM_BLOCKED_ST_LONG" logs/unified_runner.log

# Check 4 — no naked trades
grep -c "FILL_NO_SL" logs/sniper_hunter.log
# Expected: 0

# Check 5 — circuit breaker
grep "CIRCUIT BREAKER" logs/unified_runner.log | tail -3
```

---

## 5. End-of-Week Data Collection

Run on Friday Aug 29 before the analysis session:

```bash
python extract_bot_logs.py --days 7
```

Collect and upload:
1. logs/sniper_v51_live_audit.csv
2. logs/sniper_hunter.log (check for GHOST_CACHE_FIRE and
   GHOST_ARM_BLOCKED_ST_LONG)
3. logs/unified_runner.log
4. logs/cab_watcher.log
5. logs/kpi_ledger.csv
6. MT5 ReportHistory HTML export — full account, all magic numbers,
   Aug 25–29 2026

---

## 6. End-of-Week Decision Triggers

| Trigger | Condition | Action if Met | Action if Not Met |
|---------|-----------|---------------|-------------------|
| LONDON gate | LONDON WR <35% combined W4+W5+W6 (n≥170) | Implement LONDON suppression on probe arming | Extend collection one more week |
| NY_CLOSE+H4_UP gate | WR <32% combined (n≥140) | Implement direction gate on NY_CLOSE arming | Extend |
| ATR floor gate | Q2 WR <30% combined (n≥195) | Implement ATR floor (arm only ATR > 1.8) | Extend |
| Conviction gate | 20-40 bucket WR <35% combined (n≥360) | Implement conviction > 40 gate | Extend |
| ADX dead zone gate | ADX 20-25 WR <33% combined (n≥280) | Implement ADX 20-25 suppression | Extend |
| H9 CAB direction | SELL WR <35% AND BUY WR >40%, n≥50, non-trending week | Implement H4 direction gate in cab_entry.py (Week 7) | Refute H9 — no gate needed |
| 204 first fires | >0 fires in Week 6 | Record avg_R per fire. Continue accumulating. | If still zero: analysis session required |
| Gate 3 CAB | Await H9 resolution | — | — |

---

## 7. What Is Explicitly Off the Table

- No session filters implemented mid-week
- No ATR gate mid-week
- No conviction gate mid-week
- No ADX dead zone gate mid-week
- No CAB direction gate mid-week (H9 must be confirmed first)
- No SuperTrend symbol disables (no pair met the 3-week trigger)
- No CAB architectural changes (spec parked at Review Stage)
- No KR Layer 2/3 hard blocks activated (RAW_LOGGING_MODE stays True)
- No scaling of any position size on any bot

---

## 8. Account Risk Context

Week 5 close: $6,977 (-30.2% from $10,000 inception).
Week 5 was the first recovery week (+$386). SuperTrend is confirmed
positive-expectancy. Ghost 202 regime suppression prevented further drag
during a trending week. The system is behaving as designed.

The data collection discipline holds. The gates will be implemented when
the data confirms them. Acting on 87 fills (of which 81 came from one
trending week) would be implementing gates calibrated to a regime, not
to a strategy edge.

---

## 9. CAB Architecture — Parked Status

The external enhancement spec (cab_super_enhancement_spec.md, Aug 22 2026)
was reviewed. Decision: run Week 6 with cab_super unchanged.

The one testable hypothesis from the spec (H4 directional bias gate, H9)
requires Week 6 data from a non-trending week before it can be confirmed
or refuted. All other proposed enhancements are deferred:
- Tri-vector ADX framework: unvalidated strategy expansion, not an
  enhancement to the current edge.
- Vol_Expansion_Ratio gate: no threshold derivation from trade data.
- H1_STRUCT_BREACH feature referenced in spec: does not exist in
  current codebase.

If H9 is confirmed at end of Week 6, the implementation plan is:
add `_get_h4_direction(symbol)` inside `CABEntryEngine.run_cycle()` in
`cab_super/cab_entry.py`, gate bearish inversion entries when H4=UP,
log `CAB_SELL_BLOCKED_H4_UP`. Single function, single gate, one week
of validation before wiring.

If H9 is not confirmed (SELL gap reverses in ranging week), the CAB
architecture spec is archived and no direction filter is implemented.
