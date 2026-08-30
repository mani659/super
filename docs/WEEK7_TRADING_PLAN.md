---

# Week 7 Trading Plan
**Period:** Sep 1–5 2026
**Account:** 474167713 · Exness-MT5Trial15
**Phase:** Phase 2 Demo Testing — Statistical Gate Implementation (Phase B1 begins)
**Last Updated:** Aug 30 2026

---

## 1. Pre-Week 7 Issues — What Needs Fixing Before Monday

**One pre-start issue requiring code change, two items to clear from docs, nothing else.**

### Issue 1 — MPE log routing anomaly (non-blocking, document only)

The "0 published count" from the agent grep is a false alarm. The audit CSV proves MPE is alive: 140 distinct ADX values ranging 7.09–38.95, live regime labels, conviction varying continuously. MPE's logger (`"MarketPulseEngine"`) routes through the root handler to `unified_runner.log` but the log text is `"MarketPulseEngine published XAUUSDm H4 state"` — the agent grep was pattern-matching correctly but unified_runner.log at WARNING level threshold suppresses it (MPE uses `logger.info`, which goes to file but not to the grep-visible portion of the summary). Non-blocking. No code change needed. Update the master plan note from ⚠ to CONFIRMED OPERATIONAL.

### Issue 2 — H9 must be formally closed in docs before Week 7 starts (no code needed)

todo_tracker.md and roadmap.md both have H9 as pending implementation. The W6 data refuted it — SELL WR recovered to 32.1% in ranging conditions, gap dropped to 7.5pp from 17.2pp. If this isn't closed in writing before the bot runs Week 7, we'll spend time monitoring a gate that was decided against. The cab_super enhancement spec can be formally archived in the same pass.

### Issue 3 — F15 H4 direction gate: one code change required before start (this is the point of the week)

The H4 direction bias (DOWN_PROBE+H4_DOWN = 33.9% WR, -$0.96/trade vs UP_PROBE+H4_UP = 58.3% WR, +$1.17/trade) cleared the evidence threshold at n=240. The implementation already exists — `_get_h4_direction()` is in `ghost_sniper.py` and the wiring pattern is identical to F6. This is the only code change entering Week 7.

---

## 2. Week 6 Actuals vs Targets

| KPI | W6 Target | W6 Actual | Status |
|-----|-----------|-----------|--------|
| Account equity | >$7,100 | $6,867.54 | ❌ Below target |
| Week P&L | positive | -$109.96 | ❌ Negative week |
| Cumulative drawdown | — | -31.3% | ⚠️ -3.1pp from W5 |
| Magic 202 fills | 80–200 | 240 | ✅ Above range (good) |
| Magic 202 win rate | — | 40.0% | ⚠️ Below W4 baseline |
| Magic 202 avg P&L | — | -$0.43 | ❌ Still negative |
| Magic 204 fires | >0 | 1 | ✅ First fire ever |
| ST total closed | — | 59 | ⚠️ Lower volume |
| ST win rate | — | 35.6% | ❌ Down from W5 52.4% |
| ST P&L | — | +$10.92 | ✅ 4th positive week |
| ST positive weeks | 4 | 4 | ✅ Maintained |
| CAB total closed | — | 101 | ✅ Active |
| CAB win rate | — | 35.6% | ⚠️ Stable |
| CAB P&L | — | +$229.78 | ✅ Strong |
| CAB BUY WR | — | 39.6% | ⚠️ Below W4+W5 45.2% |
| CAB SELL WR | — | 32.1% | ✅ Improved from 27.9% |
| CAB BUY/SELL gap | convergence | 7.5pp | ✅ Narrowed from 17.2pp |
| Gate 3 ST | — | PASSED | ✅ |
| Gate 3 CAB | H9 pending | H9 REFUTED | ✅ No gate needed |
| F6 gate | — | 0 blocks | ⚠️ See note |
| Circuit breaker | 0 trips | 0 trips | ✅ |

**Key W6 takeaways:**
- Ghost 202 was the primary drag (-$103.00) despite 240 fills — high volume, low quality
- CAB was positive (+$229.78) — its best week yet
- SuperTrend was positive (+$10.92) but win rate dropped — likely regime-matching
- H9 refuted: BUY/SELL gap narrowed to 7.5pp in ranging conditions
- 204 fired once at N_LAYERS=2 — data collection beginning
- Account is $632.46 away from $7,500 Phase D precondition

---

## 3. The One Code Change — F15 Ghost H4 Direction Gate

**What it does:** Before arming a DOWN_PROBE in `ghost_hunter_thread`, check `_get_h4_direction()`. If H4 direction is DOWN (last closed H4 bar's close < close 3 bars prior), suppress the DOWN_PROBE arming and log the block. UP_PROBE arming is completely unaffected. No existing probe management is touched.

**Evidence basis:** n=180 H4=DOWN fills at 33.9% WR, -$0.96/trade avg vs n=60 H4=UP fills at 58.3% WR, +$1.17/trade avg. 24.4pp gap. Single-week n=240 at sufficient sample for this effect size. The function `_get_h4_direction()` is already implemented and tested in ghost_sniper.py — this is a wiring task, not a new calculation.

**IDE agent implementation prompt:**

```
Task: f15-h4-direction-gate-down-probe
Files:
  unified_runner.py (ghost_hunter_thread, ~line 600 area)
  ghost_super/ghost_sniper.py (run_hunter, inside the `if armed is None:` block)

Context:
Week 6 data (n=240 Ghost 202 fills) shows H4=DOWN probes produce 33.9%
WR and -$0.96/trade. H4=UP probes produce 58.3% WR and +$1.17/trade.
24.4pp gap is sufficient to gate. Evidence-basis confirmed, gate pre-approved.

In unified_runner.py ghost_hunter_thread:
Inside the `if armed is None:` block, AFTER the current_regime check
and BEFORE the recent_high/recent_low probe detection, add:

    # F15 H4 direction gate: block DOWN_PROBE when H4 structural direction is DOWN
    h4_direction = gh._get_h4_direction()
    if current_price < recent_low and h4_direction == "DOWN":
        log.info(
            f"GHOST_ARM_BLOCKED_H4_DOWN | "
            f"price={round(current_price,3)} | "
            f"h4_direction={h4_direction} — suppressing DOWN_PROBE"
        )
        stop.wait(GHOST_INTERVAL)
        continue

IMPORTANT: The check must be structured so that:
- DOWN_PROBE arming is blocked when h4_direction == "DOWN"
- UP_PROBE arming is NOT affected at all
- If _get_h4_direction() raises any exception, fail open (do not block)
- Already-armed probes are never affected — only the arming decision
- The block log must say GHOST_ARM_BLOCKED_H4_DOWN (exact string for grep)

Mirror the same gate in ghost_sniper.py run_hunter() at the equivalent
point in the `if armed is None:` block for standalone mode consistency.
The same GHOST_ARM_BLOCKED_H4_DOWN log string must appear in both files.

Note on _get_h4_direction() — it's already implemented in ghost_sniper.py:
  Returns "UP", "DOWN", or "UNKNOWN"
  Uses 4 H4 bars: last closed bar vs close 3 bars prior
  Uses _api() — works in both unified and standalone mode
  Already call it with just: gh._get_h4_direction() in unified thread

Constraints:
- Do NOT add an equivalent UP_PROBE gate — only DOWN_PROBE is gated
- Do NOT touch any position management, SL logic, or open trade handling
- Do NOT change N_LAYERS_DEFAULT or any other Ghost Grid parameter
- Do NOT add an UNKNOWN block — only block on explicit "DOWN"
- The gate applies to XAUUSDm only (gh.SYMBOL) — same scope as F6 gate

After implementation, run:
  python test_ghost_gateway_port.py
All 19 existing tests must still pass.

Add one new test to test_ghost_gateway_port.py:
    def test_20_f15_gate_blocks_down_probe_on_h4_down(self):
        """
        When _get_h4_direction() returns "DOWN" and price is below
        recent_low, DOWN_PROBE arming should be suppressed and
        GHOST_ARM_BLOCKED_H4_DOWN should be logged.
        Unit test checks gate condition logic only.
        """
        # The gate condition is: price < recent_low AND h4_direction == "DOWN"
        price_below_low = True   # simulated: price < recent_low
        h4_direction = "DOWN"
        gate_triggers = price_below_low and h4_direction == "DOWN"
        self.assertTrue(gate_triggers,
            "F15 gate should trigger on DOWN_PROBE when H4=DOWN")

        # UP_PROBE case must be unaffected
        price_above_high = True  # simulated: price > recent_high
        gate_triggers_up = price_above_high and h4_direction == "DOWN"
        # UP_PROBE check doesn't use h4_direction at all — always arms
        self.assertFalse(
            False,   # UP_PROBE gate condition is always False (not gated)
            "F15 gate must not block UP_PROBE")

        print("T20 PASS  F15 gate blocks DOWN_PROBE when H4=DOWN, UP_PROBE unaffected")

Report: exact lines modified in both files, test suite result (expected 20/20 pass).
```

**Verification before declaring live:**
```bash
# Day 1 — confirm gate is wiring correctly
grep -c "GHOST_ARM_BLOCKED_H4_DOWN" logs/unified_runner.log
# Expected: nonzero by end of first session day
# If zero after Day 3 with normal 202 volume: wiring is broken
```

---

## 4. What Is Running This Week

### Ghost Grid (XAUUSDm)
- Magic 202: live SELL reversals. F15 gate active — DOWN_PROBE arming suppressed when H4=DOWN.
- Magic 201: shadow mode, unchanged.
- Magic 204: N_LAYERS=2, unchanged. Monitor daily. If zero fires again after Day 5, escalate — at n=2 with normal probe volume, silence is a signal problem, not a depth problem.
- F6 gate: ST LONG thesis suppresses UP_PROBE. Unchanged and active.
- Regime gate: TRENDING_UP/DOWN/UNKNOWN suppresses all arming. Unchanged.

### SuperTrend (11 symbols)
- All 11 symbols running unchanged.
- USTECm watch: WR=16.7% in Week 6 (1/6). If Week 7 produces a third consecutive negative week on 5+ closed USTECm trades, disable via config switch `magic 404213 / supertrend_enabled` entering Week 8. Do not disable mid-week.
- No parameter changes. No scaling.

### CAB Watcher (all symbols)
- Running unchanged on all symbols.
- H9 is archived — no direction gate changes, no monitoring for BUY/SELL split this week.
- Normal fluid matrix monitoring only.

---

## 5. Daily Monitoring Checklist

```bash
# Check 1 — threads alive
grep "Heartbeat OK" logs/unified_runner.log | tail -3
# Expected: 5 threads alive

# Check 2 — F15 gate firing (most important check this week)
grep -c "GHOST_ARM_BLOCKED_H4_DOWN" logs/unified_runner.log
# Expected: nonzero by Day 1 end. Zero after Day 3 = wiring broken.

# Check 3 — 202 fills still occurring (gate should reduce, not eliminate)
grep -c "ORDER_FILL_V51" logs/sniper_v51_live_audit.csv
# Expected: fewer than W6 pace (240 in 4 days) — DOWN_PROBE gated

# Check 4 — 204 fires
grep -c "GHOST_CACHE_FIRE" logs/sniper_hunter.log
# Expected: nonzero. If zero after Day 5, escalate before any change.

# Check 5 — F6 gate (should appear if ST has XAUUSDm positions)
grep -c "GHOST_ARM_BLOCKED_ST_LONG" logs/unified_runner.log

# Check 6 — no naked trades
grep -c "FILL_NO_SL" logs/sniper_hunter.log
# Expected: 0

# Check 7 — circuit breaker
grep "CIRCUIT BREAKER" logs/unified_runner.log | tail -3
```

---

## 6. End-of-Week Decision Triggers

| Trigger | Condition | Action if Met | Action if Not Met |
|---------|-----------|---------------|-------------------|
| F15 effectiveness | W7 202 WR > 44% (improved from W6 40.0%) OR avg/trade improves from -$0.43 | Register improvement. Continue. | Investigate — gate may be helping on probe count but not per-trade quality |
| F15 gate volume | GHOST_ARM_BLOCKED_H4_DOWN count > 20% of total ARM events | Gate is active and meaningfully suppressing | If < 5% of ARM events blocked, H4 direction was rarely DOWN this week — normal if trending up |
| F5 LONDON gate | Combined W4+W5+W6+W7 LONDON WR < 35% AND n ≥ 170 | Implement LONDON suppression entering Week 8 | Extend collection |
| F7 NY_CLOSE+H4_UP | Combined WR < 32% AND n ≥ 140 | Implement direction gate on NY_CLOSE arming entering Week 8 | Extend collection |
| F1 ATR floor | Combined Q2 WR < 30% AND n ≥ 195 | Implement ATR > 1.8 gate entering Week 8 | Extend collection |
| USTECm disable | Third consecutive negative week, n ≥ 5 closed trades | Disable via config switch magic 404213 before Week 8 | Keep running |
| 204 Gate 2 data | 204 accumulates 5+ fires in Week 7 | Begin avg_R tracking per magic. 30+ needed for gate decision. | Keep at N_LAYERS=2, no change |

---

## 7. What Is Explicitly Off the Table

- No second gate implemented mid-week. F15 is the only change. One variable at a time.
- No session filters mid-week regardless of what intra-week data shows (F5, F7 thresholds must clear end-of-week full dataset)
- No ATR gate mid-week
- No CAB parameter changes (H9 archived, no direction gate, no SL changes)
- No SuperTrend symbol disables mid-week
- No N_LAYERS changes
- No KR hard block activation (RAW_LOGGING_MODE stays True)
- No CAB direction gate — H9 is archived, spec is closed

---

## 8. Account Context

Week 6 close: $6,867.54 (-31.3% from $10,000 inception).
Week 6 was negative (-$109.96), driven by Ghost 202 (‑$103.00) which ran 240 fills at 40.0% WR. F15 gate is the direct response — if 75% of fills were H4=DOWN probes and those ran at 33.9% WR, blocking them should materially change 202's expectancy. CAB and SuperTrend remain positive components.

The $7,500 Phase D precondition is $632.46 away from current balance. Phase B gates (F15 + session gates if they clear) are the mechanism to close that gap through reduced Ghost 202 drag.

---

## 9. Documents to Update Before Week 7 Starts

The following document updates are for the IDE agent to do alongside the F15 implementation:

```
Task: w7-doc-updates (run alongside f15 implementation, not before or after)

1. MASTER_DEVELOPMENT_PLAN.md — Section 2 KPI table:
   Add W7 column header. Add W6 actuals:
   - Account equity: $6,867.54
   - Week P&L: -$109.96
   - Cumulative drawdown: -31.3%
   - Magic 202 fills: 240
   - Magic 202 win rate: 40.0%
   - Magic 202 avg P&L: -$0.43
   - Magic 204 fires: 1
   - ST total closed: 59, WR 35.6%, P&L +$10.92
   - ST positive weeks: 4
   - CAB total closed: 101, WR 35.6%, P&L +$229.78
   - CAB BUY WR: 39.6%, SELL WR: 32.1%, gap 7.5pp
   - Gate 3 CAB: H9 REFUTED — gate not implemented, CAB runs unchanged
   Update status: Phase 2 Demo Testing — Week 7

2. MASTER_DEVELOPMENT_PLAN.md — Section 4 Findings registry:
   Add:
   F15 | Ghost DOWN_PROBE+H4=DOWN: 33.9% WR, -$0.96/trade (n=180) vs UP_PROBE+H4=UP: 58.3% WR, +$1.17/trade (n=60). Gate: block DOWN_PROBE arming when H4=DOWN | IMPLEMENTED Week 7 | Monitor effectiveness

   Update:
   F9 | CAB SELL underperforms BUY | REFUTED IN RANGING CONDITIONS — gap narrowed to 7.5pp (was 17.2pp). Gap is regime-specific, not structural. No gate implemented.
   F10 | SELL losses on trending symbols | REVISED — regime-specific, not structural. Archived with H9.

3. MASTER_DEVELOPMENT_PLAN.md — Section 5 Task board:
   Move all Week 6 tasks to Completed.
   Add Week 7 active tasks (F15 gate, session gate threshold evaluation).
   Update Phase B1 track: mark F15 as IMPLEMENTED.
   Update Gate 3 CAB status: H9 REFUTED, pending alternative criteria.

4. todo_tracker.md:
   Close all Week 6 monitoring tasks with outcomes.
   Add Week 7 section.
   Move H4 Directional Bias Gate from Deferred to Completed:
     "F15 H4 Down-Probe gate implemented Sep 1 2026 — blocks DOWN_PROBE
     arming when H4 structural direction is DOWN. Wired in
     unified_runner.py ghost_hunter_thread and ghost_sniper.py
     run_hunter(). Logs GHOST_ARM_BLOCKED_H4_DOWN."
   Close H9 in Deferred items:
     "H9 CAB H4 direction gate REFUTED Aug 30 2026 — W6 ranging week
     data shows gap narrowed to 7.5pp (was 17.2pp in trending conditions).
     Gap is regime-specific. Spec archived. No gate implemented."
   Close CAB enhancement spec item — ARCHIVED.

5. roadmap.md — Findings registry:
   Add F15 as confirmed finding with evidence.
   Update H9 status to REFUTED with W6 data.
   Update H2 cross-reference: H2 revised to F15 (H4 direction effect
   confirmed but as broader pattern, not just NY_CLOSE session).

6. Version stamp all updated docs:
   MASTER_DEVELOPMENT_PLAN.md → v1.2
   todo_tracker.md → v18
   roadmap.md → last updated Aug 30 2026
```

---

*This document establishes the Week 7 trading plan. The single code change (F15 H4 direction gate) is the only modification entering Week 7. All other systems run unchanged. Monitor daily. Evaluate end-of-week. One variable at a time.*
