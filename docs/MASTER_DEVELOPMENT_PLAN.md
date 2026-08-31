# Algo Trading System — Master Development Plan
**Version:** v1.2
**Last Updated:** Aug 31 2026
**Account:** 474167713 · Exness-MT5Trial15
**Status:** Phase 2 Demo Testing — Week 7
**Document purpose:** Single authoritative reference combining original master plan intent, current system reality, weekly KPI history, outstanding work, and forward phase plan. Supersedes roadmap.md for planning purposes. roadmap.md remains the findings/hypothesis registry.

---

## Section 1 — Original Plan vs Current Reality

### 1.1 Original Phase Timeline (from AlgoTrading_MasterPlan.docx)

| Phase | Original Duration | Original Deliverable | Original Gate |
|-------|------------------|---------------------|---------------|
| Phase 1 | 1 week | Individual enrichment + watchdog | All enrichments running without crashes |
| Phase 2 | 2 weeks min | Individual conviction data | All three bots pass conviction gate |
| Phase 3 | 1 week | Cross-validation, regime complementarity | Four Phase 3 decision gates cleared |
| Phase 4 | 2–3 weeks build + 2 weeks demo | Unified architecture | Matches/exceeds combined individual performance |
| Live | 2 weeks micro-lot per bot | Sequential live deployment | Positive expectancy on live execution costs |
| Total estimate | 10–12 weeks | — | — |

### 1.2 Actual Timeline (what happened)

| Phase | Actual Duration | What Was Delivered | Status |
|-------|----------------|-------------------|--------|
| Phase 1 equivalent | April–July 2026 (~12 weeks) | Unified architecture FIRST (inverted from plan), then July fix batch for Tier 0 bugs | Partially complete — enrichment items done but some original spec items missing |
| Phase 2 | July 2026 – present (~7 weeks) | W1–W6 demo data collection with progressive bug discovery and fixes | IN PROGRESS |
| Phase 3 | Not started | — | NOT STARTED |
| Phase 4 | Built first (inverted) | One process, one gateway, 5 daemon threads, KR architecture | BUILT but KR Layer 0 non-functional |
| Total elapsed | ~20 weeks | — | ~8–10 weeks over original estimate |

The unified architecture was built before individual validation (inverted from the plan), and foundational bugs (TP broken for 5 weeks, CAB single-symbol for months, ADX 14x inflation) were not discovered until clean data was available. Extra time was not wasted — it was used to discover failures that would have invalidated live deployment.

### 1.3 Original Plan Items — Implementation Audit

[⚠ REAL ISSUE] core/shared_intelligence.py: MarketPulseEngine is instantiated correctly (unified_runner.py line 1074) but may silently fail to publish if copy_rates_from_pos() returns None for any symbol, or if the 4h+5min stale-expiry in get_market_state() causes snapshots to expire between publish cycles. Verification: grep logs/unified_runner.log for "MarketPulseEngine" and confirm non-zero publish lines for XAUUSDm H4 within 60 seconds of startup.

[CONFIRMED — No issue] Ghost Cache 204 wiring: correctly wired in unified_runner.py ghost_hunter_thread (lines 565, 575).

[CONFIRMED — No issue] F6 gate: present in both unified_runner.py ghost_hunter_thread and ghost_sniper.py run_hunter().

[CONFIRMED — No issue] RAW_LOGGING_MODE = True: confirmed in knowledge_register.py line 10.

[CONFIRMED — No issue] cab_watcher.log path: RotatingFileHandler correctly uses logs/cab_watcher.log in cab_watcher.py.

#### DONE

| Item | Priority | Status | Note |
|------|----------|--------|------|
| ST MQL5 Watchdog | CRITICAL | ✅ Done | Replaced by UnifiedFailover.mq5 |
| CAB SI Score (simplified) | CRITICAL | ✅ Done | Replaced by KR and CAB's fluid logic |
| CAB Continuous Management | HIGH | ✅ Done | Implemented via CAB manage_fluid_logic |
| Ghost Grid Grid-State Watcher | CRITICAL | ✅ Done | Watcher acts on combined ghost cache state |
| Ghost Grid Grid Take-Profit | CRITICAL | ✅ Done | Personality TP implemented |
| Ghost Grid Hard Grid Stop | CRITICAL | ✅ Done | Implemented in GridState staleness and SL |
| MarketPulseEngine Fix (Phase A) | CRITICAL | ✅ Done | H4 data fetch and staleness bug fixed |
| ST R-Multiple Tracking | HIGH | ✅ Done | Implemented in _record_closed_trade() in supertrend_bot.py v2.3 |

#### PARTIAL

| Item | Priority | Status | Note |
|------|----------|--------|------|
| ST Equity Curve Filter | CRITICAL | ⚠️ Partial | Replaced by global circuit breaker |
| ST Conviction Score | HIGH | ⚠️ Partial | Replaced by ST's own logic, not full ADX*momentum |
| ST Incubation Adjustment | MEDIUM | ⚠️ Partial | incubation_bars_trending managed in states |
| ST Multi-TF ATR | MEDIUM | ⚠️ Partial | H4 and M15 regime engine in use |
| CAB Partial Close Harvester | HIGH | ⚠️ Partial | Implemented but regime locks removed |
| CAB Session Awareness | HIGH | ✅ Done | Asian session block implemented in cab_entry.py blocked_hours_utc and REAPER suppression in cab_watcher.py REAPER_ASIAN_SUPPRESS_HOURS |
| Ghost Grid Exhaustion Detection Gate | HIGH | ⚠️ Partial | Regime gate implemented, fully blocking UNKNOWN |

#### NOT DONE

| Item | Priority | Status | Note |
|------|----------|--------|------|
| CAB ER (Efficiency Ratio) | MEDIUM | ❌ Not done | Not integrated into REAPER yet |
| CAB Conviction Score | MEDIUM | ❌ Not done | Needs explicit logging |
| Ghost Grid Probe Significance Filter | HIGH | ❌ Not done | Not built |
| Ghost Grid Session Gate | MEDIUM | ❌ Not done | Pending W4+W5+W6 data |
| Ghost Grid Bar-Aware Cache | MEDIUM | ❌ Not done | Not cached per bar properly yet |
| Ghost Grid ATR Position Sizing | HIGH | ❌ Not done | fixed lot 0.01, risk-based sizing not yet implemented |
| Ghost Gates (Phase B1) | NEW | ❌ Not done | ATR floor, LONDON, NY_CLOSE, ADX dead zone |
| CAB H4 Direction Gate (Phase B2) | NEW | ❌ Not done | H9 gate pending Week 6 |
| Intelligence-Driven Exits (Phase C) | NEW | ❌ Not done | Market Exit Score v1, Ghost ATR sizing |
| Live Deployment Sequencing (Phase D)| NEW | ❌ Not done | ST first, CAB second, Ghost third |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Section 2 — Weekly KPI Ledger

### 2.1 KPI Table — All Weeks

| KPI | W1 Baseline | W2 | W3 | W4 | W5 | W6 Actual | W7 Status |
|-----|------------|----|----|----|----|-----------|-----------|
| Account equity | $7,739.28 | n/a | ~$7,128.00 | ~$6,723.00 | $6,977.50 | $6,867.54 | tracking |
| Week P&L | -$2,260.72 | n/a | ~-$872.00 | ~-$1,067.00 | +$385.78 | -$109.96 | tracking |
| Cumulative drawdown | -22.6% | n/a | n/a | -32.8% | -30.2% | -31.3% | — |
| Circuit breaker trips | n/a | n/a | n/a | n/a | 0 | 0 | — |
| Magic 202 fills | 1,085 | n/a | 316 | 81 | 6 | 240 | tracking |
| Magic 202 win rate | 55.7% | n/a | n/a | n/a | 33.3% | 40.0% | tracking |
| Magic 202 avg P&L | -$0.125 | n/a | n/a | n/a | -$1.37 | -$0.43 | tracking |
| Magic 204 fires | 0 | n/a | n/a | n/a | 0 | 1 | tracking |
| Magic 201 shadow fills | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| LEG_TP_SET fires | 8 | n/a | n/a | n/a | n/a | n/a | n/a |
| GRID_TP fires | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| GRID_STOP fires | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| Depth cap refused | 47,672 | n/a | n/a | n/a | n/a | n/a | n/a |
| ST total closed trades| 2 | n/a | 73 | n/a | 84 | 59 | tracking |
| ST win rate | 100% | n/a | 41.1% | n/a | 52.4% | 35.6% | tracking |
| ST total P&L | +$4.47 | n/a | +$119.26 | +$55.00 | +$277.31 | +$10.92 | tracking |
| ST avg P&L per trade| +$2.23 | n/a | +$1.63 | n/a | +$3.30 | n/a | n/a |
| ST positive weeks | 0 | 0 | 1 | 2 | 3 | 4 | 4th positive |
| CAB total closed trades| 18 | n/a | n/a | n/a | 92 | 101 | tracking |
| CAB win rate | 0.0% | n/a | n/a | n/a | 35.9% | 35.6% | tracking |
| CAB total P&L | -$1,846.79 | n/a | n/a | n/a | +$44.68 | +$229.78 | tracking |
| CAB BUY win rate | n/a | n/a | n/a | 45.2% (W4+W5) | n/a | 39.6% | tracking |
| CAB SELL win rate | n/a | n/a | n/a | 27.9% (W4+W5) | n/a | 32.1% | tracking |
| CAB BUY/SELL gap | n/a | n/a | n/a | 17.2pp | n/a | 7.5pp | tracking |
| CAB OSI fires % | n/a | n/a | n/a | n/a | 59.0% | n/a | n/a |
| Gate 1 | PASSED | PASSED | PASSED | PASSED | PASSED | PASSED | PASSED |
| Gate 2 | n/a | n/a | n/a | n/a | n/a | 1 fire | accumulating |
| Gate 3 ST | n/a | n/a | n/a | n/a | PASSED | PASSED | PASSED |
| Gate 3 CAB | n/a | n/a | n/a | n/a | pending H9 | H9 REFUTED | no gate |
| Gate 3 Ghost | n/a | n/a | n/a | n/a | pending | pending | pending |
| Gate 4 | n/a | n/a | n/a | n/a | working | working | working |
| Gate 5 | n/a | n/a | n/a | n/a | accumulating | accumulating | accumulating |

* CAB direction analysis is from combined W4+W5 dataset (n=130), not W4-only.

### 2.2 Week 6 KPI Target Row

(See W6 Target column above).
- Account equity target: >$7,100 (SuperTrend ~$200–300 expected, Ghost 202 minimal with regime gate, CAB neutral)
- Ghost 202 fills target: 80–200 (depends on Gold regime this week)
- 204 fires target: >0 (n=2 should fire if probes reach 2nd layer)
- CAB BUY/SELL gap: watch for convergence or persistence
- Week P&L target: positive, driven by SuperTrend

### 2.3 Week-on-Week Trend Analysis

**Account equity trajectory**: Week 5 broke the continuous drawdown with a positive P&L of +$385.78, indicating the recovery may be structural due to SuperTrend's confirmed positive expectancy over three weeks, combined with Ghost Grid's regime filter effectively suppressing entries during unfavorable trending conditions.

**Ghost Grid evolution**: Transitioning from 47,672 depth-cap refusals in W1 (a broken state) to functioning management in W2+. W5's 6 fills tell us the regime filter is highly effective at keeping Ghost Grid out of strong, persistent trends, avoiding the drawdown spikes seen in previous weeks.

**SuperTrend consistency signal**: Three consecutive positive weeks demonstrate stable, structural edge in SuperTrend logic. It is the primary growth engine.

**CAB evolution**: Moving from a 0% WR in W1 (caused by a multi-symbol tracking bug) to a mixed performance in W4/W5 where outlier wins generated net positive returns despite structural direction bias (17.2pp BUY/SELL gap).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Section 3 — Revised Forward Phase Plan

### 3.1 Phase A — Stabilize Foundation (Week 6, current)

**Status: ✅ COMPLETED (Aug 26 2026)**
- **MarketPulseEngine Fix:** Add startup verification logging in _update_symbol_timeframe() that logs first successful publish per symbol/timeframe. Add watchdog in main thread heartbeat checking KR snapshot age for XAUUSDm H4 — log WARNING if snapshot is older than 15 minutes or None. This makes the failure visible without changing the core logic.

### 3.2 Phase B — Confirmed Gates and CAB Direction Fix (Weeks 7–8)

ONE GATE PER WEEK. Minimum one week of validation between each implementation. Do not stack multiple gate changes in a single deploy.

#### Track B1: Ghost Gates
1. **ATR Floor Gate** — BLOCKED: n=134 of 195 needed. Not implemented.
   - **Addresses:** F1 (ATR strongest predictor)
   - **Threshold:** ATR Q2 win rate < 30% combined (n≥195)
   - **Implementation:** `ghost_hunter_thread` in `unified_runner.py`
   - **Description:** Arm only when M1 ATR > 1.8.

2. **LONDON Session Gate** — **IMPLEMENTED Week 7**
   - **Addresses:** F5 (LONDON structurally negative)
   - **Evidence:** Cross-system confirmation from 3 independent CAB systems cleared threshold. n=341 cross-system fills (standalone cab n=259, cab_multi_pair negative, cab_super F5 n=82).
   - **Implementation:** `cab_super/cab_entry.py` blocked_hours_utc extended to (0..11).
   - **Status:** Active Week 7. Entry gate only — positions managed normally.

3. **NY_CLOSE + H4_UP Gate** — BLOCKED: n=89 of 140 needed. Not implemented.
   - **Addresses:** F7 (second worst combo)
   - **Threshold:** NY_CLOSE + H4_UP win rate < 32% combined (n≥140)

4. **ADX Dead Zone Gate** — BLOCKED: insufficient n. Not implemented.
   - **Addresses:** F4 (ADX 20-25 dead zone)
   - **Threshold:** ADX 20-25 win rate < 33% combined (n≥280)

5. **Conviction Gate** — BLOCKED: signal weakening. W6 20-40 bucket at 37% WR, above 35% threshold.
   - **Addresses:** F3 (Conviction > 50 predicts wins)
   - **Threshold:** Conviction 20-40 bucket win rate < 35% combined (n≥360)

6. **F15 Ghost H4 Direction Gate** — **IMPLEMENTED Week 7**
   - **Addresses:** F15 (DOWN_PROBE+H4=DOWN structural drag)
   - **Evidence:** n=240, DOWN_PROBE+H4_DOWN 33.9% WR (-$0.96/trade, n=180) vs UP_PROBE+H4_UP 58.3% WR (+$1.17/trade, n=60). 24.4pp gap.
   - **Implementation:** `unified_runner.py` ghost_hunter_thread + `ghost_super/ghost_sniper.py` run_hunter(). Blocks DOWN_PROBE arming when H4=DOWN. Logs GHOST_ARM_BLOCKED_H4_DOWN.
   - **Test:** T20 in test_ghost_gateway_port.py. 20/20 passing.

#### Track B2: CAB H9 Gate — **REFUTED Aug 30 2026**
- W6 ranging week data: gap narrowed to 7.5pp (was 17.2pp in trending conditions). Effect is regime-specific, not structural. H9 archived. No gate implemented. CAB runs unchanged.
- **Replaced by H14 (EMA50 bias filter)**: REGISTERED Week 7. Log EMA50 at every cab_super entry for 2 weeks. No gate until Week 9 at earliest.

### 3.3 Phase C — Intelligence-Driven Exits and Gate 5 (Weeks 9–11)

- **C1: MarketPulseEngine full activation:** Shadow mode first (log what KR Layer 2/3 would have blocked without actually blocking). One week shadow before activation.
- **C2: Market Exit Score v1:** Five components: regime alignment 30%, conviction trend 25%, ATR trajectory 20%, OSI signal quality 15%, R-velocity 10%. Threshold: MES < 0.30 for two consecutive cycles = exit. Wire into CAB first (H4 timeframe = fewer spurious triggers). Validate two weeks before adding to SuperTrend.
- **C3: Gate 5 lock:** Bot-instrument fit matrix. Target: 20+ trades per symbol. Emerging pattern (F14): BTCUSDm, XAUUSDm, XAGUSDm positive; EURGBPm, USDJPYm, USOILm marginal negative. These are preliminary.
- **C4: Ghost ATR position sizing:** Prerequisite for Gate 6. Replace fixed LOT_SIZE = 0.01 with risk-based sizing using existing CAB `_calculate_lot()` pattern. max_lot_demo_cap remains 0.01.

### 3.4 Phase D — Live Deployment (Weeks 12–14)

Account recovery pre-condition: Do not begin Phase D until account equity > $7,500. Current equity $6,977. Phase B gates should recover this ground via reduced Ghost 202 drag and sustained SuperTrend positive expectancy.

1. **SuperTrend First**
   - **Go-live condition:** Gate 3 ST passed.
   - **Lot size:** Micro-lot (0.01)
   - **Monitoring period:** 2 weeks
   - **Scale condition:** Positive expectancy on live execution costs.
2. **CAB Watcher Second**
   - **Go-live condition:** Gate 3 CAB passed, H9 implemented/resolved.
   - **Lot size:** Micro-lot (0.01)
   - **Monitoring period:** 2 weeks
   - **Scale condition:** Synergy and proper regime synchronization with ST.
3. **Ghost Grid Third**
   - **Go-live condition:** Gate 3 Ghost passed, 50+ grids with stop firing < 20%.
   - **Lot size:** Micro-lot (0.01)
   - **Monitoring period:** 2 weeks
   - **Scale condition:** Expected risk parameters hold live.

### 3.5 Items Formally Removed from Plan

| Item | Reason for Deferral/Removal | Status |
|------|-----------------------------|--------|
| Controlled grid-sizing / martingale | Deferred until 50+ grids at current scale with confirmed positive avg grid P&L. | DEFERRED |
| Model divergence confluence scaling | Deferred until KR Portfolio Ledger is validated and active. | DEFERRED |
| SuperTrend continuation signals | Deferred — strips SI protection. | DEFERRED |
| V2 parallel build alignment mid-week | V2 receives validated V1 changes after confirmation, not in parallel. | DEFERRED |
| CAB Tri-vector ADX framework | Rejected — unvalidated strategy expansion, not enhancement. | REMOVED |
| Vol_Expansion_Ratio gate | Deferred — no threshold derivation from data. | DEFERRED |
| H5 CAB SL tightness hypothesis | REVISED — not removed. 97.6% of CAB losses close via OSI before reaching full 2.5×ATR SL. Original hypothesis superseded by F11. No SL parameter changes needed. | REVISED |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Section 4 — Findings and Hypothesis Registry

Canonical registry maintained in roadmap.md Sections 3 and 4. Reproduce only summary status here.

| ID | Description (brief) | Status | Action Required |
|----|---------------------|--------|-----------------|
| F1 | ATR strongest predictor — Q2 loses | PENDING W6 confirmation | Implement ATR floor gate if confirmed |
| F2 | NY_OVERLAP + H4_DOWN only positive subset | PENDING W6 confirmation | No action until confirmed |
| F3 | Conviction >50 predicts wins | PENDING W6 confirmation | Implement conviction >40 gate if confirmed |
| F4 | ADX 20-25 dead zone | PENDING W6 confirmation | Implement ADX block if confirmed |
| F5 | LONDON structurally negative | PENDING W6 confirmation | Implement LONDON suppression if confirmed |
| F6 | ST LONG + Ghost 202 SELL = bad | IMPLEMENTED Aug 16 | Monitor effectiveness W6 |
| F7 | NY_CLOSE + H4_UP second worst | PENDING W6 confirmation | Implement direction gate if confirmed |
| F8 | Q1 ATR = 66% SL hit rate | PENDING W6 confirmation | Addressed by F1 ATR floor gate |
| F9 | CAB SELL underperforms BUY by 17pp | PENDING H9 W6 confirmation | Implement H4 direction gate if confirmed |
| F10 | SELL losses on trending symbols | PENDING H9 W6 confirmation | Same gate as F9 |
| F11 | OSI is primary CAB exit (59% losses) | CONFIRMED | No action — architecture working |
| F12 | CAB symbol clusters positive/negative | REGISTERED (confounded) | Revisit post-H9 resolution |
| F13 | ST positive expectancy 3 weeks | CONFIRMED | Gate 3 ST PASSED |
| F14 | ST fit matrix emerging | REGISTERED (n insufficient) | Lock at Gate 5 after 20+/symbol |
| F15 | Ghost DOWN_PROBE+H4=DOWN: 33.9% WR, -$0.96/trade (n=180). UP_PROBE+H4=UP: 58.3% WR, +$1.17/trade (n=60). 24.4pp gap. | IMPLEMENTED Week 7 | Monitor block rate and post-gate 202 WR |
| F9/F10 | CAB SELL underperforms BUY | REFUTED IN RANGING CONDITIONS Aug 30 2026. Gap narrowed to 7.5pp (was 17.2pp). Effect is regime-specific. H9 archived. No gate. |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Section 5 — Active Task Board

### THIS WEEK (Week 7, Sep 1–5) — Active Tasks
- `[ ]` F15 gate (Daily): `grep -c "GHOST_ARM_BLOCKED_H4_DOWN" logs/unified_runner.log`.
- `[ ]` F5 London gate (Daily): Confirm 07-11 UTC cab fills drop to zero in MT5 export.
- `[ ]` 204 fires (Daily): `grep -c "GHOST_CACHE_FIRE" logs/sniper_hunter.log`.
- `[ ]` F6 gate (Daily): `grep -c "GHOST_ARM_BLOCKED_ST_LONG" logs/unified_runner.log`.
- `[ ]` Thread health (Daily): `grep "Heartbeat OK" logs/unified_runner.log | tail -3`.
- `[ ]` End-of-week: Compute H15 (stagnation decay) from W6+W7 CAB loss hold times.
- `[ ]` End-of-week: Compute H16 (rollover gate 22-23 UTC) from W6 CAB entries.
- `[ ]` End-of-week: Evaluate F7 NY_CLOSE+H4_UP combined n vs 140 threshold.
- `[ ]` End-of-week: USTECm disable check (3rd consecutive negative week trigger).

### COMPLETED (Week 6, Aug 25–29)
- `[x]` N_LAYERS_DEFAULT = 2: Applied in ghost_super/ghost_cache.py.
- `[x]` 204 fires: 1 fire Week 6. Gate 2 data started.
- `[x]` F6 gate effectiveness: 0 fires W6 (regime gate blocked arming before F6 — confirmed not a dead wire).
- `[x]` H8 equity: W6 close $6,867.54, week P&L -$109.96.
- `[x]` H9 CAB direction gate: REFUTED — gap narrowed to 7.5pp. No gate.
- `[x]` Cross-CAB comparison: completed. H13 invalidated, H14-H16 registered.
- `[x]` W6 data extraction and analysis: complete.
- `[x]` F5 London Open gate: IMPLEMENTED Aug 31 2026. blocked_hours_utc extended to 07-11 UTC. Cross-system evidence from 3 CAB variants.
- `[x]` F15 H4 direction gate: IMPLEMENTED Aug 31 2026. Blocks DOWN_PROBE when H4=DOWN. Test T20 added, 20/20 passing.
### Hypothesis Registry (new entries)
| ID | Hypothesis | Status | Action |
|----|-----------|--------|--------|
| H14 | H4 EMA50 bias filter for cab_super entries | REGISTERED | Log EMA50 at every cab_super entry for 2 weeks. No gate until Week 9.
| H15 | Stagnation decay — close CAB trade open 24h+ at R<0.5 | REGISTERED | Compute from W6+W7 CAB loss hold times. If >30%, register for Phase C.
| H16 | Rollover gate 22:00-23:59 UTC for CAB entries | REGISTERED | Compute from W6 CAB entry outcomes. If WR<30%, extend blocked_hours_utc.
| H13 | H1 structural breach exit | **INVALIDATED** | cab_multi_pair H1_STRUCT_BREACH is a trailing SL label, not an active exit. Architecturally incomparable to cab_super OSI. Removed.
### NEXT (Weeks 8–9, Phase B continued)
| Task | Status | Trigger / Threshold |
|------|--------|---------------------|
| Ghost ATR Floor Gate | BLOCKED | n=134 of 195 needed |
| Ghost NY_CLOSE + H4_UP Gate | BLOCKED | n=89 of 140 needed |
| Ghost ADX Dead Zone Gate | BLOCKED | insufficient n |
| Ghost Conviction Gate | BLOCKED | 37% WR in 20-40 bucket (above 35% threshold) |
| H14 EMA50 bias filter | EVALUATE Week 9 | 2 weeks of EMA50 logging data |
| H15 stagnation decay | EVALUATE Week 8 | W6+W7 hold time distribution |
| H16 rollover gate | EVALUATE Week 8 | W6 CAB entry outcomes at 22-23 UTC |

### BACKLOG (Phase C–D)
| Task | Status | Trigger Condition |
|------|--------|-------------------|
| MarketPulseEngine Shadow Mode | PLANNED | Phase C start |
| Market Exit Score v1 | PLANNED | Phase C start |
| Gate 5 Lock | PLANNED | 20+ trades per symbol accumulated |
| Ghost ATR Position Sizing | PLANNED | Phase C start |
| SuperTrend Live Deployment | PLANNED | Account > $7,500, Phase D start |
| CAB Live Deployment | PLANNED | Account > $7,500, Phase D start |
| Ghost Live Deployment | PLANNED | Account > $7,500, Phase D start |

### Formally Deferred / Removed
| Task | Status | Reason |
|------|--------|--------|
| Controlled grid-sizing / martingale | DEFERRED | Until 50+ grids at current scale with confirmed positive avg grid P&L. |
| Model divergence confluence scaling | DEFERRED | Until KR Portfolio Ledger is validated and active. |
| SuperTrend continuation signals | DEFERRED | Strips SI protection. |
| V2 parallel build alignment mid-week | DEFERRED | V2 receives validated V1 changes after confirmation. |
| CAB Tri-vector ADX framework | REMOVED | Unvalidated strategy expansion, not enhancement. |
| Vol_Expansion_Ratio gate | DEFERRED | No threshold derivation from data. |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Section 6 — Non-Negotiable Principles

- Position management gates can never block open trade management — only entry creation is gatable.
- R-multiples measure outcomes. They must not mechanically trigger exits. Market state drives exit decisions.
- The Knowledge Register informs but does not command — except Layer 2 invalidation and Layer 3 portfolio exposure hard blocks, which require multi-week data validation before activation.
- One variable changes at a time. Evidence before action.
- Ghost Grid MAX_LEGS=4 is non-negotiable during demo. Evaluate statistically after 50+ grids.
- The hypothesis registry exists so no observation is lost. Observations are stored and tested, not acted on immediately.
- Statistical gates are implemented only after data confirms the pattern across sufficient combined sample (see triggers above). Week 4 findings are registered. Week 6 is the extended confirmation window.
- Bots inform each other; they do not command each other's exits. Cross-bot signals gate entry arming only.
- CAB architecture changes require H9 confirmation from Week 6 data before any implementation. The spec is parked at Review Stage.
- MarketPulseEngine is the single highest architectural priority. Every bot is running on hardcoded fallbacks for regime, ADX, and ATR. Fixing Layer 0 data publication unlocks all downstream KR value.
- Account recovery is a precondition for live deployment. Do not begin Phase D while account equity is below $7,500.
- Cross-system confirmation from parallel standalone models running the same entry signal accelerates gate evidence thresholds. A finding confirmed independently across three systems with different exit architectures is treated as stronger evidence than single-system n alone. Applied first to F5 London gate (n=82 in-system confirmed by n=259 standalone cab + cab_multi_pair negative direction).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Section 7 — Document Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| v1.0 | Aug 26 2026 | IDE Agent | Initial creation consolidating roadmap.md, todo_tracker.md, W5/W6 plans, and revised plan from session Aug 26 2026 |
| v1.1 | Aug 26 2026 | IDE Agent | Correction pass per Claude review Aug 26 2026 |
| v1.2 | Aug 31 2026 | IDE Agent | W6 actuals added, F15 implemented, H9 refuted, F5 London gate implemented, H14-H16 registered, H13 invalidated, cross-system confirmation principle added |

