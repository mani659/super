# Ghost Grid — Comprehensive Analysis & Decision Document
**Date:** August 31, 2026
**Author:** Buffy (Codebuff AI) + Salman
**Status:** Pre-Week 7 — Decision Required
**Purpose:** Single reference document for control session to finalize Ghost Grid strategy

---

## Executive Summary

The Ghost Grid system was designed as a three-leg mean-reversion architecture (201 SCALP, 202 REVERSAL, 204 CACHE) firing on M1 Gold. After 6 weeks of demo testing:

- **201 SCALP** has been in virtual/shadow mode since Week 1 — **zero live fills**. The comparison experiment (201 virtual vs 202 live) has run its course and cannot answer the question it was designed for.
- **202 REVERSAL** is the only live-filling leg — 342 fills in 30 days, 40% WR, -$0.43/trade in Week 6. Primary structural problem: SELL direction bias into H4 UP trends.
- **204 CACHE** has fired exactly **1 time** in 30 days. The 5-minute cache expiry window makes the fire condition nearly impossible to meet on Gold M1.
- **Week 4 findings all held** — H4 RANGING classifier blindspot, LONDON negativity, ATR as strongest predictor, ADX dead zone, conviction thresholds. Two new gates (F15, F5) implemented for Week 7.

**Bottom line:** Ghost Grid is currently a single-leg (202) mean-reversion bot with accumulating gates. The multi-leg architecture is not producing data. A binary decision on 201 (enable live or kill) and 204 (fix fire rate or kill) is overdue.

---

## Section 1 — Magic Number Architecture

| Magic | Leg | Mode | Purpose | Live Fills (30d) | Virtual Fills |
|-------|-----|------|---------|-------------------|---------------|
| **201** | SCALP | **Virtual/Shadow** | Always-active fast reversion, 1.0R target, 0.35×ATR SL | **0** | 1,373 (Week 1 only) |
| **202** | REVERSAL | **Live** | First retraction from probe extreme, regime-gated | **342** | 0 |
| **204** | CACHE | **Live** | Exhaustion entry at nth virtual layer | **1** | 0 |
| 203 | TREND | **Removed** | Handed off to SuperTrend (Aug 16 2026) | N/A | N/A |

### 201 SCALP — Virtual Only Since Inception
- Placed in shadow mode during Week 1 because TP was broken and SL was too tight (0.2×ATR)
- After July fix batch (SL widened to 0.35×ATR, TP working), **nobody took 201 out of shadow mode**
- Every "fill" is logged via `is_shadow=True` in `send_order()` — no real order is placed
- Week 1 virtual data: 1,373 fills, 55.3% WR, -$0.135/trade — but **no spread, no slippage, no latency captured**
- **Cannot meaningfully compare 201 vs 202** because 201 has zero live data

### 202 REVERSAL — The Only Live Leg
- Fires at first retraction from probe extreme after price makes new high/low
- Regime-gated: blocked during TRENDING_UP, TRENDING_DOWN, UNKNOWN
- F6 gate: blocked when ST LONG active on XAUUSDm
- F15 gate (NEW Week 7): blocked DOWN_PROBE when H4 structural direction is DOWN

### 204 CACHE — Nearly Non-Functional
- Fires only AFTER 202 fires on the same probe, when price extends to nth virtual layer then retraces
- See Section 4 for detailed analysis

---

## Section 2 — Week 4 Observations: Did They Hold?

### Confirmed (Still Valid in 30-Day Data)

| ID | Finding | W4 Evidence | 30-Day Status | Gate Status |
|----|---------|-------------|---------------|-------------|
| **H4** | KR M15 classifier labels 98.5% RANGING regardless of H4 direction | 814/826 = RANGING, H4 UP=377, DOWN=437 | **Confirmed** — structural blindspot | No fix planned (Layer 0) |
| **F5** | LONDON session structurally negative | n=472, 55.9% WR, negative P&L | **Confirmed** — n=341 cross-system | **IMPLEMENTED Week 7** — blocked_hours_utc 0-11 UTC |
| **F1** | ATR is strongest predictor | Q4 high-ATR 57.5% WR vs Q2 low-ATR 27.4% WR | **Confirmed** | ATR floor gate — BLOCKED (n=134 of 195) |
| **F3** | Conviction >50 predicts wins | Monotonic across 5 buckets | **Confirmed** | Conviction gate — BLOCKED (37% WR in 20-40 bucket, above 35% threshold) |
| **F4** | ADX 20-25 dead zone | n=109, 32.1% WR, -$0.69/trade | **Confirmed** | ADX dead zone gate — BLOCKED (insufficient n) |
| **F7** | NY_CLOSE + H4_UP second worst combo | n=54, 27.8% WR, -$0.68/trade | **Confirmed** | BLOCKED (n=89 of 140 needed) |
| **F9/F10** | SELL underperforms BUY by 17pp | W4+W5: BUY 45.2% vs SELL 27.9% | **Revised** — gap narrowed to 7.5pp in ranging conditions (H9 refuted) | No gate — regime-specific effect |
| **H6** | ST LONG at Ghost fire time = 32.4% WR | n=34, 3× worse per-trade P&L | **Confirmed** | Read via KR thesis — no gate needed |

### Refuted / Revised

| ID | Original Hypothesis | Result | Action |
|----|---------------------|--------|--------|
| **H2** | DOWN_PROBE-into-H4-UP is the direction problem | **REFUTED** — DOWN_PROBE total = 0 in W4. Real issue is UP_PROBE firing SELL into H4_UP. Revised to F15. | F15 implemented |
| **H9** | CAB SELL underperforms BUY structurally | **REFUTED** — gap narrowed to 7.5pp in ranging week (was 17.2pp trending). Effect is regime-specific. | H9 archived, no gate |
| **H13** | H1 structural breach exit | **INVALIDATED** — cab_multi_pair H1_STRUCT_BREACH is a trailing SL label, not active exit | Removed |

### Key Structural Finding: 202 SELL Bias

The raw audit CSV from Aug 6-7 shows **nearly every 202 fill was a SELL order**. Gold was trending UP during this period, and the bot was repeatedly shorting into the uptrend. This is the primary loss driver — not SL width, not session timing, but **directional mismatch between the mean-reversion strategy and the prevailing H4 trend**.

This finding directly led to the F15 gate (blocking DOWN_PROBE when H4=DOWN), but the complementary problem (UP_PROBE firing SELL into H4_UP) remains unaddressed.

---

## Section 3 — 202 Performance Trajectory

| Period | Fills | WR | Avg P&L/Trade | Notes |
|--------|-------|----|---------------|-------|
| Week 1 (Jul 5-17) | 1,085 | 55.7% | -$0.125 | TP broken for 5 weeks, SL too tight |
| Week 3 (Aug 1-8) | 316 | ~40% | — | Post-fix, clean data first week |
| Week 4 (Aug 8-14) | 81 | — | — | Regime gate suppressing in trending Gold |
| Week 5 (Aug 15-22) | 6 | 33.3% | -$1.37 | Trending Gold week — gate correctly blocking |
| Week 6 (Aug 25-29) | 240 | 40.0% | -$0.43 | Ranging conditions, most fills |
| **30-day (Aug 1-31)** | **342** | — | — | BE-lock fires: 117 (all on 202) |

### Brain Log Events (30-day)
- **LEG_TP_SET: 801** (was 8 in Week 1 — TP fix working)
- **GRID TP fired: 0** | GRID STOP: 0 (grid mechanism still non-functional)
- **GridState reset: 125** (staleness timeout working)
- **Depth cap refused: 325** (vs 47,672 in Week 1 — massive improvement)
- **BE_LOCK fires: 117** (all on magic 202)
- **GHOST_CACHE_FIRE (204): 0** in brain log (1 in audit CSV)

### Session Distribution (30-day)
- ASIAN: 459 entries (was only profitable session in Week 1)
- LONDON: 86 entries (structurally negative — F5 gate now active)
- NY_OVERLAP: 104 entries
- NY_CLOSE: 135 entries (worst session historically — F7 pending)

### Conviction at Fill (30-day)
- Magic 202: avg 38.8, min 10.8, max 59.7
- **Average conviction is BELOW the F3 threshold of 50** — 202 is firing into statistically unfavorable conviction levels

---

## Section 4 — Magic 204 (CACHE): Why Only 1 Fire?

### Architecture Recap

204 fires when:
1. A probe is armed (UP_PROBE or DOWN_PROBE)
2. Price extends to the **nth virtual layer** beyond probe extreme (exhaustion)
3. Price then **retraces** through the (n-1)th layer (confirmation)
4. All within **300 seconds (5 minutes)** of cache creation
5. Price must NOT reach invalidation level (n+2 layers)

### The Math Problem on Gold

| Parameter | Value | Gold Equivalent |
|-----------|-------|-----------------|
| `N_LAYERS_DEFAULT` | 2 | — |
| `atr_step` | 1.0 × ATR | ~$2.50 |
| Distance to 2nd layer | 2 × ATR | **$5.00 beyond probe extreme** |
| Retrace needed | 1 × ATR | **$2.50 pullback** |
| `MAX_CACHE_AGE_SECONDS` | **300 (5 min)** | 5 one-minute candles |
| `CACHE_INVALIDATION_N` | 2 | 4th layer = $10 beyond extreme = dead |

**204 requires Gold to move $5 beyond the probe extreme AND retrace $2.50 — all within 5 minutes.** This is a very specific price pattern (strong extension + immediate rejection) that is rare on Gold M1.

### Why Each Constraint Kills Fires

1. **5-minute expiry** is the primary killer. The exhaustion pattern needs time to develop.
2. **n=2 layers** means $5 move needed — significant on M1 Gold.
3. **Regime gate** blocks arming during trending conditions — when exhaustion patterns are most likely.
4. **Single pair** (XAUUSDm only) limits opportunity count.
5. **Sequential dependency** — 204 can only fire after a probe is armed AND price extends significantly beyond the probe extreme.

### Decision Matrix (from ghost_cache.py docstring)

| Outcome | Decision |
|---------|----------|
| 204 avg_R > 202 avg_R by >20% | Replace 202 with 204 in Phase 4 |
| 204 ≈ 202 (within 20%) | Keep both, tune by regime |
| 204 avg_R < 202 avg_R | Kill 204, keep 202 |
| **204 fires <10 times in 2 weeks** | **n too high → lower to n=2** ← WE ARE HERE |
| 204 fires >6 times per day | n too low → raise to n=4 |

**Status:** n was lowered to 2 entering Week 6. Got 1 fire. Still below the <10 threshold. The docstring's prescribed action has been exhausted — no further guidance exists.

### Recommendations for 204

#### Option A: Fix Fire Rate (Recommended)
1. **Extend `MAX_CACHE_AGE_SECONDS` from 300 to 600 (10 minutes)** — The ATR staleness concern is valid but 5 minutes is too tight. 10 minutes gives the exhaustion pattern room to develop without making the ATR step dangerously stale. This is the single biggest lever.

2. **Apply 204 to additional pairs** — XAGUSDm and USOILm have smaller ATRs, making the layer distance more achievable:
   - XAGUSDm: ATR ~$0.05-0.10 → 2nd layer = $0.10-0.20 (very achievable)
   - USOILm: ATR ~$0.10-0.20 → 2nd layer = $0.20-0.40 (achievable)
   - BTCUSDm: ATR ~$15-30 → 2nd layer = $30-60 (possible on volatile moves)

3. **Add 204-specific logging** — layer depth, cache age, probe origin distance at fire time. Currently not captured in the extract script.

#### Option B: Kill 204
- Remove GhostCache instantiation from `unified_runner.py` and `ghost_sniper.py`
- Remove `manage_204_ghost_cache()` from `sniper_watcher.py`
- Simplify Ghost Grid to single-leg 202 system
- Focus all resources on 202 gate optimization

**Recommendation:** Option A. The exhaustion concept is sound — waiting for deeper pullback before entering should produce higher-conviction entries. The problem is parameter tuning, not architecture. But set a hard deadline: if 204 doesn't reach 10 fires across all pairs within 2 weeks of the fix, switch to Option B.

---

## Section 5 — The 201 Decision

### The Virtual Comparison Experiment

| What Was Planned | What Happened |
|------------------|---------------|
| Run 201 virtual vs 202 live for 2-3 weeks | Ran for 6 weeks (Aug 1 - Aug 31) |
| Compare WR and avg P&L to decide which leg is better | Cannot compare — virtual data doesn't capture spread/slippage/latency |
| Establish basis for which leg is more profitable going forward | Question unanswered after 6 weeks |

### Why Virtual Data Is Unreliable for This Decision

The 201 SCALP targets 1.0R with 0.35×ATR SL — a scalp-scale setup where **execution quality IS the edge**. Virtual fills cannot capture:

- **Spread impact**: Gold spreads $0.10-$0.50. At 1.0R target, spread consumes 25-60% of profit
- **Latency**: FILL_SECURE logs show 30-840ms latency. On M1 scalps, 500ms slippage is meaningful
- **Broker rejections**: Virtual fills always succeed. Real fills get 10016, 10044, spread widening
- **BE-lock math**: *"fixed spread costs currently consume profit targets before BE-lock mathematically engages"* — project_audit_report.md

Virtual 201 at 55.3% WR and -$0.135/trade is **optimistic**. Real execution would be worse.

### Week 1 Live Data (When Both Were Briefly Live)

```
201 SCALP    1,373 trades  Win% 55.3%  Avg/trade -$0.135
202 REVERSAL 1,085 trades  Win% 55.7%  Avg/trade -$0.125
```

Both were negative. The BE-lock cohort was the real story:
- Reached +0.5R: n=1,438, P&L +$2,239, WR 94.4%
- Never reached BE-lock: n=1,020, P&L -$2,560, WR 0.5%
- 41.5% of trades died before BE-lock at 0.2×ATR SL

### Binary Decision Required

| Option | Action | Code Change | Risk |
|--------|--------|-------------|------|
| **Enable 201 Live** | Remove `is_shadow=True` from unified_runner.py line 784 | 1 line | Unknown spread impact on scalp targets. Could add negative expectancy. |
| **Kill 201** | Remove virtual fire path (unified_runner.py lines 771-792) | ~20 lines | Lose the option to ever compare. Simplifies codebase. |

**Recommendation:** If Ghost Grid is to survive as a multi-leg system, 201 needs real data. Enable at 0.01 lot (micro-lot, same as everything else). Give it 2 weeks. If avg P&L is worse than 202, kill it permanently. The virtual experiment has had more than enough time.

If the decision is to simplify Ghost Grid to a single-leg 202 system (see Section 7), then kill 201 and remove the virtual fire path.

---

## Section 6 — Week 7 Gates: What's Active

### Implemented (Aug 31 2026)

| Gate | System | Evidence | Implementation | Test |
|------|--------|----------|----------------|------|
| **F15** H4 direction | Ghost | n=240, 24.4pp WR gap (33.9% vs 58.3%) | `unified_runner.py` + `ghost_sniper.py` — blocks DOWN_PROBE when H4=DOWN | T20, 20/20 pass |
| **F5** London Open | CAB | n=341 cross-system | `cab_entry.py` — blocked_hours_utc (0..11) | T19, 19/19 pass |

### Monitoring Targets (Week 7)

| Check | Command | Expected | Failure Signal |
|-------|---------|----------|----------------|
| F15 gate activity | `grep -c "GHOST_ARM_BLOCKED_H4_DOWN" logs/unified_runner.log` | Nonzero by Day 1 | Zero after Day 3 = wiring broken |
| F5 gate activity | `grep -c "session_gate\|LONDON" logs/cab_watcher.log` | 07-11 UTC fills = zero | Fills still appearing = deploy failed |
| 204 fires | `grep -c "GHOST_CACHE_FIRE" logs/sniper_hunter.log` | Nonzero | Zero after Day 5 at N_LAYERS=2 |
| F6 gate | `grep -c "GHOST_ARM_BLOCKED_ST_LONG" logs/unified_runner.log` | Fires when ST LONG active | Zero = wiring issue |
| Thread health | `grep "Heartbeat OK" logs/unified_runner.log \| tail -3` | 5 threads alive | Dead threads |

### End-of-Week 7 Evaluations

| Evaluation | Threshold | Action if met |
|------------|-----------|---------------|
| F15 effectiveness | 202 WR > 44% (from 40%) OR avg/trade improves from -$0.43 | Gate is working |
| F5 effectiveness | Zero cab_managed fills 07-11 UTC | Gate deployed correctly |
| H15 stagnation decay | >30% of CAB losses held 24h+ at R<0.5 | Register for Phase C |
| H16 rollover gate | CAB entry WR at 22-23 UTC < 30% | Extend blocked_hours_utc to include 22,23 |
| F7 NY_CLOSE+H4_UP | Combined n vs 140 threshold | Approaching implementability |
| USTECm disable | 3rd consecutive negative week with 5+ closed trades | Disable symbol |
| Gate 2 (204 vs 202) | 204 accumulates 5+ fires | Begin avg_R tracking |

---

## Section 7 — Ghost Grid Simplification: Single-Leg 202 System

### The Case For Simplification

After 6 weeks, the Ghost Grid is effectively already a single-leg system:

| Original Design | Current Reality |
|-----------------|-----------------|
| 201 SCALP + 202 REVERSAL + 204 CACHE | Only 202 fires live |
| Grid accumulation (MAX_LEGS=4) | Grid mechanism non-functional (GRID TP/STOP = 0) |
| Three complementary entry timings | One timing: first retraction |
| Cross-leg risk diversification | Single-point-of-failure on 202 |

### What "Single-Leg 202" Would Mean

- Remove 201 virtual fire path (~20 lines in unified_runner.py)
- Remove 204 GhostCache instantiation (~30 lines across files)
- Remove `manage_201_scalp()` and `manage_204_ghost_cache()` from sniper_watcher.py
- Simplify ghost_hunter_thread to only fire 202
- Focus all gate development on 202 performance

### What You'd Lose

- The exhaustion concept (204) — never properly tested
- The scalp concept (201) — never properly tested
- Future optionality if either concept proves viable on different parameters

### What You'd Gain

- Simpler codebase (less maintenance burden)
- Clearer performance attribution (all results = 202)
- Faster gate iteration (one system to optimize)
- Reduced cognitive load for analysis sessions

**Recommendation:** Don't simplify yet. Fix 204's fire rate first (Section 4, Option A). Give it 2 weeks with extended cache expiry and multi-pair deployment. If 204 still can't reach 10 fires, THEN simplify to single-leg 202. The exhaustion concept deserves a fair test before being killed.

---

## Section 8 — Open Items & Deferred Decisions

| Item | Status | Recommended Timeline |
|------|--------|---------------------|
| **201 binary decision** (live or kill) | OVERDUE — 6 weeks virtual | Decision this week |
| **204 fire rate fix** (cache expiry + multi-pair) | NEW — see Section 4 | Implement before Week 8 |
| **BE-lock step ratchet** | PARKED since Week 1 | Evaluate after 201/204 decisions |
| **Ghost probe logic unification** | DEFERRD to Phase C | Between Phase B and C |
| **204 bs/gates staleness** | DEFERRD to Phase C | Address during probe unification |
| **ghost_hunter_thread switches fragility** | DEFERRD to Phase C | Address during probe unification |
| **MarketPulseEngine watchdog** | NEW — in todo_tracker | Next coding session |
| **Dynamic lot sizing (Ghost)** | PLANNED Phase C | After Gate 5 lock |
| **Ghost Grid ATR position sizing** | PLANNED Phase C | Replace fixed 0.01 lot |

---

## Section 9 — Key Metrics to Track Going Forward

### Primary KPIs for Ghost Grid Health

| Metric | Current | Target | Why It Matters |
|--------|---------|--------|----------------|
| 202 avg P&L/trade | -$0.43 | > $0.00 | Break-even = foundation for gates to create edge |
| 202 WR | 40.0% | > 44% | F15 gate should eliminate worst entries |
| 204 fire count (per week) | 0-1 | > 5 | Need data for Gate 2 decision |
| F15 block rate | TBD (Week 7 first data) | 15-25% of DOWN_PROBE attempts | Too low = gate not catching enough; too high = gate too aggressive |
| F5 block rate | TBD (Week 7 first data) | 100% of 07-11 UTC entries | Binary — should be zero fills |
| BE-lock reach rate | 58.5% (Week 1) | > 65% | Higher = SL is wide enough for M1 noise |

### Gate Decision Timeline

| Gate | Data Needed | Expected Timeline | Decision |
|------|-------------|-------------------|----------|
| F15 effectiveness | W7 202 WR and avg P&L | End of Week 7 (Sep 5) | Keep, adjust, or remove gate |
| F5 effectiveness | W7 07-11 UTC fill count | End of Week 7 (Sep 5) | Confirm deployment or investigate |
| Gate 2 (204 vs 202) | 30+ fills each with avg_R | Week 9-10 (if 204 fire rate fixed) | Kill 204, keep both, or replace 202 |
| ATR floor gate | n=195, WR < 30% in Q2 | Week 9-10 (accumulating) | Implement M1 ATR > 1.8 filter |
| NY_CLOSE+H4_UP gate | n=140, WR < 32% | Week 9-10 (accumulating) | Block arming during NY_CLOSE + H4_UP |
| ADX dead zone gate | n=280, WR < 33% | Week 10-12 (accumulating) | Block ADX 20-25 |
| Conviction gate | n=360, 20-40 bucket WR < 35% | Week 10-12 (accumulating) | Require conviction > 40 |

---

## Section 10 — Recommendations Summary

### Immediate (This Week — Before Week 8)

1. **Decide on 201**: Enable live at 0.01 lot OR remove virtual fire path. The 6-week virtual experiment is over.
2. **Fix 204 fire rate**: Extend `MAX_CACHE_AGE_SECONDS` from 300 to 600. Apply GhostCache to XAGUSDm and USOILm.
3. **Commit Week 7 gates**: F15 and F5 are implemented and tested — commit if not already done.

### Short Term (Weeks 8-9)

4. **Evaluate F15 effectiveness**: Is 202 WR improving? Is avg P&L improving?
5. **Target 10+ 204 fires** across all pairs to evaluate Gate 2 decision matrix.
6. **Begin BE-lock step ratchet evaluation**: The one-shot BE-lock at 0.5R caps 73% of trades at scratch. A progressive step (+0.5R→BE, +1.0R→lock 0.3R, +1.5R→lock 0.7R) could capture more upside.

### Medium Term (Phase C, Weeks 9-11)

7. **Ghost probe logic unification**: Extract shared probe class from duplicated code in unified_runner.py and ghost_sniper.py.
8. **204 bs/gates staleness fix**: Refresh brain state and gate evaluation at moment of 204 fire, not at arming tick.
9. **Ghost ATR position sizing**: Replace fixed LOT_SIZE = 0.01 with risk-based sizing.
10. **MarketPulseEngine watchdog**: Add heartbeat check for KR snapshot staleness.

### Decision Point (End of Week 9)

**If 204 reaches 10+ fires:** Evaluate Gate 2 decision matrix (204 avg_R vs 202 avg_R).
**If 204 doesn't reach 10 fires:** Kill 204. Simplify to single-leg 202 system.
**If 201 is live and performing worse than 202:** Kill 201. Focus on 202 gates.
**If 201 is live and performing better than 202:** Consider enabling 201 as primary, 202 as secondary.

---

## Appendix A — Files Modified in Week 7 Session

| File | Change | Lines |
|------|--------|-------|
| `cab_super/cab_entry.py` | F5 London Open gate — blocked_hours_utc extended | +4 |
| `ghost_super/ghost_sniper.py` | F15 H4 direction gate — blocks DOWN_PROBE when H4=DOWN | +15 |
| `unified_runner.py` | F15 H4 direction gate — same logic in live thread | +15 |
| `test_cab_entry.py` | T19 — London Open session gate test | +17 |
| `test_ghost_gateway_port.py` | T20 — F15 gate logic test | +12 |
| `docs/MASTER_DEVELOPMENT_PLAN.md` | v1.2 — W6 actuals, F15/F5 implemented, H9 refuted | Full update |
| `docs/todo_tracker.md` | v18 — Week 7 status, monitoring tasks, evaluations | Full update |

**Commit:** `3f261f0` — "Week 7 gates: F15 H4 direction gate + F5 London Open session gate"
**Test suites:** CAB 19/19, Ghost 20/20 — all green.

---

## Appendix B — Non-Negotiable Principles (from Master Plan)

- Position management gates can never block open trade management — only entry creation is gatable
- R-multiples measure outcomes. They must not mechanically trigger exits. Market state drives exit decisions
- One variable changes at a time. Evidence before action
- Ghost Grid MAX_LEGS=4 is non-negotiable during demo. Evaluate statistically after 50+ grids
- Statistical gates are implemented only after data confirms the pattern across sufficient combined sample
- Bots inform each other; they do not command each other's exits. Cross-bot signals gate entry arming only
- Cross-system confirmation from parallel standalone models accelerates gate evidence thresholds
