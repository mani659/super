import os
from datetime import datetime

today_str = datetime.today().strftime('%b %d %Y')

content = f"""# Algo Trading System — Master Development Plan
**Version:** v1.0
**Last Updated:** {today_str}
**Account:** 474167713 · Exness-MT5Trial15
**Status:** Phase 2 Demo Testing — Week 6
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

[⚠ VERIFY] core/shared_intelligence.py MarketPulseEngine is instantiated in unified_runner.py, but H4 rates may fail to fetch or publish due to MT5 data gap.
[⚠ VERIFY] unified_runner.py ghost_hunter_thread Ghost Cache 204 decoupling wiring.
[⚠ VERIFY] unified_runner.py and ghost_super/ghost_sniper.py F6 gate presence.
[⚠ VERIFY] core/knowledge_register.py KR RAW_LOGGING_MODE is set to True.
[⚠ VERIFY] cab_super/cab_watcher.py RotatingFileHandler path uses logs/cab_watcher.log.

#### DONE

| Item | Priority | Status | Note |
|------|----------|--------|------|
| ST MQL5 Watchdog | CRITICAL | ✅ Done | Replaced by UnifiedFailover.mq5 |
| CAB SI Score (simplified) | CRITICAL | ✅ Done | Replaced by KR and CAB's fluid logic |
| CAB Continuous Management | HIGH | ✅ Done | Implemented via CAB manage_fluid_logic |
| Ghost Grid Grid-State Watcher | CRITICAL | ✅ Done | Watcher acts on combined ghost cache state |
| Ghost Grid Grid Take-Profit | CRITICAL | ✅ Done | Personality TP implemented |
| Ghost Grid Hard Grid Stop | CRITICAL | ✅ Done | Implemented in GridState staleness and SL |
| Ghost Grid ATR Position Sizing | HIGH | ✅ Done | SL shifted to ATR based sizing |

#### PARTIAL

| Item | Priority | Status | Note |
|------|----------|--------|------|
| ST Equity Curve Filter | CRITICAL | ⚠️ Partial | Replaced by global circuit breaker |
| ST Conviction Score | HIGH | ⚠️ Partial | Replaced by ST's own logic, not full ADX*momentum |
| ST Incubation Adjustment | MEDIUM | ⚠️ Partial | incubation_bars_trending managed in states |
| ST Multi-TF ATR | MEDIUM | ⚠️ Partial | H4 and M15 regime engine in use |
| CAB Partial Close Harvester | HIGH | ⚠️ Partial | Implemented but regime locks removed |
| CAB Session Awareness | HIGH | ⚠️ Partial | Session tracking exists, suppression pending data |
| Ghost Grid Exhaustion Detection Gate | HIGH | ⚠️ Partial | Regime gate implemented, fully blocking UNKNOWN |

#### NOT DONE

| Item | Priority | Status | Note |
|------|----------|--------|------|
| ST R-Multiple Tracking | HIGH | ❌ Not done | Waiting for Phase 2 data completion |
| ST Session Gate | HIGH | ❌ Not done | Pending Week 6 data confirmation |
| CAB ER (Efficiency Ratio) | MEDIUM | ❌ Not done | Not integrated into REAPER yet |
| CAB Conviction Score | MEDIUM | ❌ Not done | Needs explicit logging |
| Ghost Grid Probe Significance Filter | HIGH | ❌ Not done | Not built |
| Ghost Grid Session Gate | MEDIUM | ❌ Not done | Pending W4+W5+W6 data |
| Ghost Grid Bar-Aware Cache | MEDIUM | ❌ Not done | Not cached per bar properly yet |
| MarketPulseEngine Fix (Phase A) | NEW | ❌ Not done | High priority Phase A task |
| Ghost Gates (Phase B1) | NEW | ❌ Not done | ATR floor, LONDON, NY_CLOSE, ADX dead zone |
| CAB H4 Direction Gate (Phase B2) | NEW | ❌ Not done | H9 gate pending Week 6 |
| Intelligence-Driven Exits (Phase C) | NEW | ❌ Not done | Market Exit Score v1, Ghost ATR sizing |
| Live Deployment Sequencing (Phase D)| NEW | ❌ Not done | ST first, CAB second, Ghost third |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Section 2 — Weekly KPI Ledger

### 2.1 KPI Table — All Weeks

| KPI | W1 Baseline | W2 | W3 | W4 | W5 | W6 Target |
|-----|------------|----|----|----|----|-----------|
| Account equity | $7,739.28 | n/a — not captured | ~$7,128.00 | ~$6,723.00 | $6,977.50 | >$7,100 |
| Week P&L | -$2,260.72 | n/a — not captured | ~-$872.00 | ~-$1,067.00 | +$385.78 | positive |
| Cumulative drawdown | -22.6% | n/a — not captured | n/a — not captured | -32.8% | -30.2% | n/a — not captured |
| Circuit breaker trips | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured | 0 | 0 |
| Magic 202 fills | 1,085 | n/a — not captured | 316 | 81 | 6 | 80–200 |
| Magic 202 win rate | 55.7% | n/a — not captured | n/a — not captured | n/a — not captured | 33.3% | n/a — not captured |
| Magic 202 avg P&L | -$0.125 | n/a — not captured | n/a — not captured | n/a — not captured | -$1.37 | n/a — not captured |
| Magic 204 fires | 0 | n/a — not captured | n/a — not captured | n/a — not captured | 0 | >0 |
| Magic 201 shadow fills | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured |
| LEG_TP_SET fires | 8 | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured |
| GRID_TP fires | 0 | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured |
| GRID_STOP fires | 0 | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured |
| Depth cap refused | 47,672 | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured |
| ST total closed trades| 2 | n/a — not captured | 73 | n/a — not captured | 84 | n/a — not captured |
| ST win rate | 100% | n/a — not captured | 41.1% | n/a — not captured | 52.4% | n/a — not captured |
| ST total P&L | +$4.47 | n/a — not captured | +$119.26 | +$55.00 | +$277.31 | n/a — not captured |
| ST avg P&L per trade| +$2.23 | n/a — not captured | +$1.63 | n/a — not captured | +$3.30 | n/a — not captured |
| ST positive weeks | 0 | 0 | 1 | 2 | 3 | 4 |
| CAB total closed trades| 18 | n/a — not captured | n/a — not captured | n/a — not captured | 92 | n/a — not captured |
| CAB win rate | 0.0% | n/a — not captured | n/a — not captured | n/a — not captured | 35.9% | n/a — not captured |
| CAB total P&L | -$1,846.79 | n/a — not captured | n/a — not captured | n/a — not captured | +$44.68 | n/a — not captured |
| CAB BUY win rate | n/a — not captured | n/a — not captured | n/a — not captured | 45.2% | n/a — not captured | n/a — not captured |
| CAB SELL win rate | n/a — not captured | n/a — not captured | n/a — not captured | 27.9% | n/a — not captured | n/a — not captured |
| CAB BUY/SELL gap | n/a — not captured | n/a — not captured | n/a — not captured | 17.2pp | n/a — not captured | convergence |
| CAB OSI fires % | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured | 59.0% | n/a — not captured |
| Gate 1 | PASSED | PASSED | PASSED | PASSED | PASSED | PASSED |
| Gate 2 | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured |
| Gate 3 ST | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured | PASSED | PASSED |
| Gate 3 CAB | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured | pending H9 | pending H9 |
| Gate 3 Ghost | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured | pending | pending |
| Gate 4 | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured | working | working |
| Gate 5 | n/a — not captured | n/a — not captured | n/a — not captured | n/a — not captured | accumulating | accumulating |

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

**Highest priority technical action:**
**MarketPulseEngine Fix**
- **Gate name / Finding:** MarketPulseEngine Fix
- **Confirmation threshold:** N/A (Architecture fix)
- **Implementation location:** `core/shared_intelligence.py` and KR integration.
- **One-line description:** Repair H4 regime classification by fixing `MarketPulseEngine` execution context and MT5 data feeds.
- **Verification check:** Confirm H4 returns valid regime data instead of `None` or 98.5% `RANGING`.
- **Reminder:** Do not implement until threshold met. (Fix applies immediately as it's Tier 0).

### 3.2 Phase B — Confirmed Gates and CAB Direction Fix (Weeks 7–8)

ONE GATE PER WEEK. Minimum one week of validation between each implementation. Do not stack multiple gate changes in a single deploy.

#### Track B1: Ghost Gates
1. **ATR Floor Gate**
   - **Addresses:** F1 (ATR strongest predictor)
   - **Threshold:** ATR Q2 win rate < 30% combined (n≥195)
   - **Implementation:** `ghost_hunter_thread` in `unified_runner.py`
   - **Description:** Arm only when M1 ATR > 1.8.
   - **Verification:** `grep` for new logging of ATR block.
   - **Reminder:** Do not implement until threshold met.
2. **LONDON Session Gate**
   - **Addresses:** F5 (LONDON structurally negative)
   - **Threshold:** LONDON win rate < 35% combined (n≥170)
   - **Implementation:** `ghost_hunter_thread` in `unified_runner.py`
   - **Description:** Implement LONDON suppression on probe arming.
   - **Verification:** No LONDON fills in session logs.
   - **Reminder:** Do not implement until threshold met.
3. **NY_CLOSE + H4_UP Gate**
   - **Addresses:** F7 (second worst combo)
   - **Threshold:** NY_CLOSE + H4_UP win rate < 32% combined (n≥140)
   - **Implementation:** `ghost_hunter_thread` in `unified_runner.py`
   - **Description:** Block H4_UP during NY_CLOSE arming.
   - **Verification:** NY_CLOSE + H4_UP block logged.
   - **Reminder:** Do not implement until threshold met.
4. **ADX Dead Zone Gate**
   - **Addresses:** F4 (ADX 20-25 dead zone)
   - **Threshold:** ADX 20-25 win rate < 33% combined (n≥280)
   - **Implementation:** `ghost_hunter_thread` in `unified_runner.py`
   - **Description:** Implement ADX 20-25 suppression on arming.
   - **Verification:** Block logged for ADX 20-25.
   - **Reminder:** Do not implement until threshold met.
5. **Conviction Gate**
   - **Addresses:** F3 (Conviction > 50 predicts wins)
   - **Threshold:** Conviction 20-40 bucket win rate < 35% combined (n≥360)
   - **Implementation:** `ghost_hunter_thread` in `unified_runner.py`
   - **Description:** Require conviction > 40 for arming.
   - **Verification:** Block logged for conviction < 40.
   - **Reminder:** Do not implement until threshold met.

#### Track B2: CAB H9 Gate
1. **CAB H4 Direction Gate**
   - **Addresses:** F9, F10, H9
   - **Threshold:** SELL WR < 35% AND BUY WR > 40% (n≥50) in non-trending Gold week.
   - **Implementation:** `cab_entry.py` inside `CABEntryEngine.run_cycle()`
   - **Description:** Check `_get_h4_direction()`, block bearish inversion if H4 is UP. Log `CAB_SELL_BLOCKED_H4_UP`.
   - **Verification:** `grep "CAB_SELL_BLOCKED_H4_UP"`
   - **Fallback:** If refuted (SELL WR within 5pp of BUY), accept CAB as is and archive the spec.
   - **Reminder:** Do not implement until threshold met.

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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Section 5 — Active Task Board

### THIS WEEK (Week 6, Aug 25–29)
- `[x]` N_LAYERS_DEFAULT = 2: Applied in ghost_super/ghost_cache.py.
- `[ ]` 204 fires (Daily): Check `grep -c "GHOST_CACHE_FIRE" logs/sniper_hunter.log`.
- `[ ]` F6 gate (Daily): Check `grep -c "GHOST_ARM_BLOCKED_ST_LONG" logs/unified_runner.log`.
- `[ ]` CAB BUY/SELL ratio (Daily): Tally CAB fills by direction mid-week.
- `[ ]` Thread health (Daily): `grep "Heartbeat OK" logs/unified_runner.log | tail -3`.
- `[ ]` H8 equity (Daily): Record Week 6 close equity.
- `[ ]` End-of-week data collection command: `python extract_bot_logs.py --days 7`.
- `[ ]` Evaluate End-of-Week decision triggers (LONDON, NY_CLOSE, ATR, Conviction, ADX, H9, 204 layers).

### NEXT (Weeks 7–8, Phase B)
| Task | Status | Trigger / Threshold |
|------|--------|---------------------|
| Ghost ATR Floor Gate | BLOCKED UNTIL W6 DATA | Q2 WR < 30% combined (n≥195) |
| Ghost LONDON Gate | BLOCKED UNTIL W6 DATA | LONDON WR < 35% combined (n≥170) |
| Ghost NY_CLOSE + H4_UP Gate | BLOCKED UNTIL W6 DATA | WR < 32% combined (n≥140) |
| Ghost ADX Dead Zone Gate | BLOCKED UNTIL W6 DATA | ADX 20-25 WR < 33% combined (n≥280) |
| Ghost Conviction Gate | BLOCKED UNTIL W6 DATA | 20-40 bucket WR < 35% combined (n≥360) |
| CAB H9 Direction Gate | BLOCKED UNTIL W6 DATA | SELL WR < 35% AND BUY WR > 40% (n≥50) |

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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Section 7 — Document Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| v1.0 | {today_str} | IDE Agent | Initial creation consolidating roadmap.md, todo_tracker.md, W5/W6 plans, and revised plan from session Aug 26 2026 |

"""

with open("docs/MASTER_DEVELOPMENT_PLAN.md", "w", encoding="utf-8") as f:
    f.write(content)

print(f"File path confirmed: docs/MASTER_DEVELOPMENT_PLAN.md")
print(f"Word count: {len(content.split())}")
print(f"Line count: {len(content.splitlines())}")
