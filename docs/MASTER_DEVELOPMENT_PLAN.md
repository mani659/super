# Algo Trading System — Master Development Plan
**Version:** v1.7
**Last Updated:** Sep 19 2026
**Account:** 474167713 · Exness-MT5Trial15
**Status:** Phase 2 Demo Testing — Week 9 (Entry Quality Data Collection)
**Document purpose:** Single authoritative reference combining original master plan intent, current system reality, weekly KPI history, outstanding work, and forward phase plan. Supersedes roadmap.md for planning purposes. roadmap.md remains the findings/hypothesis registry.

---

## Section 0 — System Vision and Architecture Philosophy

### 0.1 Core Vision

This system is not a fixed three-bot ensemble. It is a regime-conditional strategy portfolio where each module activates under statistically validated market conditions and stands down when those conditions are absent.

No single module is expected to be all-weather profitable. Each module is designed for a specific regime window. The system's edge comes from portfolio coverage across multiple regime states, with each component active only when its validated conditions are present. A module that has no valid conditions this week is not failing — it is behaving correctly.

Modules are not permanent fixtures. They are locked to their validated operating windows, retired if their conditions become structurally unfavorable across multiple market regimes, or supplemented by new modules when the data identifies an uncovered regime opportunity.

**The meta-system's job is regime detection and module activation, not making any individual strategy work in conditions it was never designed for.**

### 0.2 Module Portfolio Framework

Each module must satisfy all of the following before activation in the live system:

1. **Statistical evidence threshold:** Positive avg P&L confirmed across 100+ fills in the module's specific activation window, tested across at least two distinct market regimes (not just one regime where conditions happened to align).

2. **Activation condition definition:** Explicit, measurable conditions under which the module arms. Logged at every entry as structured fields in the audit CSV. Conditions must be verifiable from logged data alone — no qualitative judgment at runtime.

3. **Isolation validation:** Shadow mode for minimum 2 weeks before any live capital. One new module at a time. No two modules in shadow validation simultaneously.

4. **Architectural compatibility:** New modules wire to the existing MT5Gateway, KnowledgeRegister, and MarketPulseEngine without modifying those shared components. Each module gets its own magic number. Exit management handled by its own watcher or an extended existing watcher — never sharing exit logic with another module.

5. **Concurrent activation rule:** When two or more modules have valid activation conditions simultaneously on the same symbol and same direction, the combined position is subject to the KR Layer 3 correlation bucket ceiling. During Phase B (RAW_LOGGING_MODE=True), concurrent activations are logged but not blocked. When RAW_LOGGING_MODE is set to False in Phase C, the hard block activates automatically — no code change required. Until then, the daily circuit breaker and per-symbol position caps (max_positions=1 per symbol per bot) are the primary concurrent activation controls.

6. **Opposing direction rule:** Two modules firing in opposite directions on the same symbol at the same time is legitimate regime-complementarity behavior (SuperTrend LONG + Ghost 202 SELL on XAUUSDm is the designed use case). This is not a conflict — it is the system working as intended. The F6 gate (block Ghost UP_PROBE when ST holds confirmed LONG) is the one exception where cross-bot coordination overrides this rule, and it is backed by data (n=34, 8pp WR drop).

### 0.3 Current Module Registry

| Module | Magic(s) | Activation Window | Regime | TF | Status |
|--------|----------|-------------------|--------|----|--------|
| SuperTrend | 101234, 201567, 301890, 401213, 402213-408213 | ADX>55 trending, K-Means factor active | TRENDING | M30 | ✅ Active — 4 positive weeks, Gate 3 ST passed |
| Ghost 202 SELL | 202 | H4=UP, ATR>floor, UP_PROBE retrace | RANGING / TRENDING_DOWN | M1 | ⚠️ Active — Phase B gating in progress |
| Ghost 204 | 204 | nth virtual layer exhaustion, same conditions as 202 | RANGING | M1 virtual | ⚠️ Active — Gate 2: 3 all-time fires (27-week project at ~1/week). Reconsider criteria after Gate 5 lock. |
| CAB Watcher | 999555 | H4 two-bar inversion, EMA50 aligned (H14 pending), not London Open | H4 exhaustion / reversal | H4 | ⚠️ Active — H14 logging pending |
| Ghost BUY (DOWN_PROBE) | 202 or new magic TBD | H4=DOWN, ATR>floor, DOWN_PROBE retrace | TRENDING_UP exhaustion | M1 | 🔵 Research — monitoring F15 block count |

**Active Building Pipeline (Sep 12 2026)**

The following are concrete builds in progress, not hypotheses:

| Build | Bot | What it produces | Data target | Status |
|---|---|---|---|---|
| Win/loss classifier | SuperTrend | Entry quality gate from K-Means features | n≥80/symbol on XAUUSDm+BTCUSDm | Logging active W9 |
| Entry quality logging | CAB | h4_bar_position, m15_aligned, nearest_swing | n≥50 entries | Logging active W9 |
| M1 retrace quality | Ghost | committed_reversal_bars, body_ratio | n≥100 triggers | Logging active W9 |
| NY_OVERLAP session gate | Ghost | Remove worst session (-$0.685/tr) | W9 confirmation | ✅ IMPLEMENTED W10 |
| IMMEDIATE_EXIT rule | CAB | Kill thesis-not-confirmed trades at -0.2R | Live W9 | Deployed |
| Simplified REAPER | CAB | H4-structure-based loss exit | Live W9 | Deployed |

### 0.4 Candidate Module Pipeline

Modules in this section are under active research. They are NOT in shadow validation and NOT approved for build. A module moves from this section to shadow validation only when it satisfies the evidence threshold in Section 0.2. n=6 observations do not constitute a candidate — they constitute a registered hypothesis.

**Observed Pattern M4 — Trend Exhaustion Reversal (H4 timeframe)**
Observation: TRENDING_DOWN+H4_UP produces 66.7% WR at +$2.27/trade in Ghost data (n=6, theoretically grounded but statistically meaningless — minimum n=50 per regime combination required before any module build decision). Ghost 202 captures this incidentally but is not optimized for it — M1 probe detection and 0.35×ATR SL is wrong architecture for a structural H4 reversal setup.
Status: OBSERVATION ONLY. Not a candidate module. Not in shadow validation. The n=6 sample must not be used to justify build decisions or weight allocations in any scoring system.
Research required before upgrade to candidate: 50+ CAB entry events with M4 conditions logged alongside outcomes. If n≥50 shows consistent positive expectancy across two different regimes, upgrade to Candidate Module status at that time.
Register as: H19

**Observed Pattern M5 — London Open Range-Break Fade**
Observation: London Open is structurally negative across all three parallel CAB systems and Ghost data. All current modules gate it (or will gate it). No module has validated positive expectancy specifically during London Open.
Important caveat: the observation that London Open is negative for all existing modules does NOT confirm that a fade strategy would work there. It confirms that existing strategies (trend-following, mean-reversion from M1 probes, H4 inversions) perform poorly in that window. A dedicated fade module would need to be validated independently from first principles — the negative performance of other modules is necessary context but not sufficient evidence.
Hypothesis: London Open produces a predictable stop-hunt pattern above/below the Asian session range before reversing back into the range. A fade entry on the London Open spike with a structural SL above the spike high (for SELL) or below spike low (for BUY) and a target of Asian range midpoint could produce positive expectancy in the window where all other modules are silent.
Activation window: 07:00-10:00 UTC, price breaks above Asian session high or below Asian session low by 1×H1 ATR, fade the break with structural SL.
Research required: log Asian session range (high/low) and London Open price action for 4+ weeks. Identify break-and-reverse events. No code changes — pure data observation first.
Register as: H20

### 0.5 Multi-Timeframe Coverage and the M5 Research Agenda

**Current timeframe coverage:**

| Timeframe | Role | Module Using It |
|-----------|------|------------------|
| M1 | Ghost probe detection, conviction momentum | Ghost Grid |
| M15 | SuperTrend regime engine, ATR buffer | SuperTrend, MarketPulseEngine |
| M30 | SuperTrend entry signal, K-Means factor | SuperTrend |
| H1 | Structural breach reference (cab_multi_pair) | Research only |
| H4 | CAB entry signal, regime classification (MPE) | CAB, MarketPulseEngine |

**M5 gap and research proposal:**

M5 sits between M1 (noise-level, Ghost probe) and M15 (regime context). It covers the 5-35 minute window — the exact timeframe where the initial price reaction to a CAB H4 inversion entry would be visible before it completes or fails on M15.

When CAB fires an H4 inversion entry, the following M5 data exists but is not currently logged:
  - M5 close direction at entry bar (confirming or opposing)
  - M5 ATR at entry (local volatility context)
  - M5 body/range ratio at entry (momentum quality)
  - M5 trend direction (3-bar slope) at entry
  - Whether M5 shows a completed micro-pattern aligning with H4 inversion

**Research objective:** Determine whether M5 structure at the moment of CAB H4 inversion entry predicts trade outcome. If M5 is already moving in the inversion direction at entry, does the trade perform better than when M5 is still moving against the entry direction?

**Potential applications if M5 pattern is predictive:**
  1. CAB entry quality gate: only fire H4 inversion when M5 structure is already showing micro-alignment. This filters premature entries where H4 has inverted but M5 has not confirmed.
  2. Ghost Grid pre-arming: if M5 shows a developing exhaustion pattern ahead of a CAB H4 inversion, Ghost can arm a probe in the same direction before the H4 signal completes. This is earlier entry with smaller SL on the same thesis.
  3. New magic number: if M5 pre-arming proves distinct enough from both Ghost 202 and CAB entries, it warrants its own magic number and dedicated watcher personality — not a modification of either existing module.

**Implementation of M5 logging (data collection only, no gate):**

Add the following fields to cab_watcher.log at every ENTRY event (logged by cab_watcher.py manage_fluid_logic when a new position is detected with no prior context):

  m5_close_direction:  "UP" / "DOWN" — last closed M5 bar
  m5_atr:              M5 ATR(14) at entry time
  m5_body_ratio:       last M5 bar body / range ratio (0-1)
  m5_bars_in_direction: count of consecutive M5 bars in same direction as H4 inversion entry

These four fields require one M5 data fetch at the moment cab_watcher.py first detects a new cab_managed position. The data fetch adds approximately 50ms per detected entry and has zero impact on exit management, position sizing, or any other running logic.

Data collection target: 50+ CAB entries with M5 fields logged across at least two different market regimes before any pattern analysis. Do not analyze until n≥50.
Register as: H21

**The M5 data is the missing link between H4 structure and M1 execution. If predictive patterns exist at this timeframe during H4 inversion events, they unlock three capabilities: better CAB entry timing, Ghost pre-arming for inversion events, and potentially a new module operating in the M5-H4 cross-timeframe window that no current module covers.**

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

[CONFIRMED OPERATIONAL — Aug 31 2026] core/shared_intelligence.py: MarketPulseEngine confirmed publishing live data. W6 audit CSV shows 140 distinct ADX values ranging 7.09–38.95 and live regime labels (RANGING/TRENDING_DOWN/TRENDING_UP) — proving per-tick computation is running correctly. MPE logs at INFO level which routes to file only (not grep-visible in WARNING-threshold console output). No code change required.

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
| Ghost Grid Session Gate | MEDIUM | ⚠️ Partially Done | F5 London gate IMPLEMENTED Aug 31 in cab_entry.py (CAB). Ghost-side London gate pending ATR floor gate deployment first (Phase B1 sequencing — Ghost gates apply after H4 direction gate is stable). |
| Ghost Grid Bar-Aware Cache | MEDIUM | ❌ Not done | Not cached per bar properly yet |
| Ghost Grid ATR Position Sizing | HIGH | ❌ Not done | fixed lot 0.01, risk-based sizing not yet implemented |
| Ghost Gates (Phase B1) | NEW | ⚠️ Partial | F15 H4 Direction Gate IMPLEMENTED Aug 31. ATR floor gate is next in sequence (Week 8 target, data-dependent). |
| CAB H4 Direction Gate (Phase B2) | NEW | ❌ Not done — H9 REFUTED | H9 refuted Aug 30 2026. Gap narrowed to 7.5pp in ranging conditions. Effect regime-specific, not structural. No gate. H4 EMA50 bias filter (H14) registered as replacement hypothesis for Phase B2 consideration. |
| Intelligence-Driven Exits (Phase C) | NEW | ❌ Not done | Market Exit Score v1, Ghost ATR sizing |
| Live Deployment Sequencing (Phase D)| NEW | ❌ Not done | ST first, CAB second, Ghost third |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Section 2 — Weekly KPI Ledger

### 2.1 KPI Table — All Weeks

| KPI | W1 Baseline | W2 | W3 | W4 | W5 | W6 Actual | W7 Actual | W8 Actual | W9 Actual |
|-----|------------|----|----|----|----|-----------|-----------|-----------|-----------|
| Account equity | $7,739.28 | n/a | ~$7,128.00 | ~$6,723.00 | $6,977.50 | $6,867.54 | $6,803.71 | $6,504.41 | $6,563.54 |
| Week P&L | -$2,260.72 | n/a | ~-$872.00 | ~-$1,067.00 | +$385.78 | -$109.96 | +$35.95 | -$166.05 | +$13.58 |
| Cumulative drawdown | -22.6% | n/a | n/a | -32.8% | -30.2% | -31.3% | -31.9% | -35.0% | -34.4% |
| Circuit breaker trips | n/a | n/a | n/a | n/a | 0 | 0 | 0 | 0 | 0 |
| Magic 202 fills | 1,085 | n/a | 316 | 81 | 6 | 240 | 178 (168 closed) | 132 | 64 (Sep 15 only) |
| Magic 202 win rate | 55.7% | n/a | n/a | n/a | 33.3% | 40.0% | 45.2% | 41.7% | 50.0% |
| Magic 202 avg P&L | -$0.125 | n/a | n/a | n/a | -$1.37 | -$0.43 | -$0.15 | -$0.231 | -$0.26 |
| Magic 204 fires | 0 | n/a | n/a | n/a | 0 | 1 | 1 (3 all-time) | 1 (3 all-time) | 0 |
| Magic 201 shadow fills | n/a | n/a | n/a | n/a | n/a | n/a | 828 log events, 0 audit rows (pipeline broken) | pipeline broken (0 audit rows) | pipeline broken |
* Magic 201 shadow fills: six consecutive weeks of n/a. Root cause not yet identified — either (a) virtual fills are not being logged by the current extract_bot_logs.py script, (b) the is_shadow=True path in send_order() is not writing to sniper_v51_live_audit.csv, or (c) 201 arming conditions are never met independently of 202. Investigate at next code review session: grep "VIRTUAL_FILL" in sniper_hunter.log and confirm whether virtual fill events are being logged. W7 CONFIRMED: 828 VIRTUAL_FILL events in sniper_hunter.log, zero corresponding audit CSV rows. Virtual-fill path (is_shadow=True branch in send_order()) does not write to sniper_v51_live_audit.csv. This must be fixed before any 201-based shadow research can be conducted. The fix is a code task, not a documentation task — register in todo_tracker.md under 'Deferred / Parked Items'.
| LEG_TP_SET fires | 8 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| GRID_TP fires | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| GRID_STOP fires | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| Depth cap refused | 47,672 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| ST total closed trades| 2 | n/a | 73 | n/a | 84 | 59 | 66 | 67 | 72 |
| ST win rate | 100% | n/a | 41.1% | n/a | 52.4% | 35.6% | 42.4% | 37.3% | 45.8% |
| ST total P&L | +$4.47 | n/a | +$119.26 | +$55.00 | +$277.31 | +$10.92 | -$29.56 | -$92.85 | +$95.36 |
| ST avg P&L per trade| +$2.23 | n/a | +$1.63 | n/a | +$3.30 | n/a | n/a | n/a | +$1.32 |
| ST positive weeks | 0 | 0 | 1 | 2 | 3 | 4 | 4 (streak ended W7) | 4 (streak ended) | 5 (streak resumed) |
| CAB total closed trades| 18 | n/a | n/a | n/a | 92 | 101 | 48 | 58 | 65 |
| CAB win rate | 0.0% | n/a | n/a | n/a | 35.9% | 35.6% | 27.1% | 18.1% | 20.0% |
| CAB total P&L | -$1,846.79 | n/a | n/a | n/a | +$44.68 | +$229.78 | +$85.50 | -$39.41 | -$65.11 |
| CAB BUY win rate | n/a | n/a | n/a | 45.2% (W4+W5) | n/a | 39.6% | 29.2% | 10.0% (collapse) | 25.8% |
| CAB SELL win rate | n/a | n/a | n/a | 27.9% (W4+W5) | n/a | 32.1% | 25.0% | 25.0% | 14.7% |
| CAB BUY/SELL gap | n/a | n/a | n/a | 17.2pp | n/a | 7.5pp | 4.2pp | 15.0pp (persistent) | 11.1pp |
| CAB OSI fires % | n/a | n/a | n/a | n/a | 59.0% | n/a | n/a | n/a | n/a |
| Gate 1 | PASSED | PASSED | PASSED | PASSED | PASSED | PASSED | PASSED | PASSED | PASSED |
| Gate 2 | n/a | n/a | n/a | n/a | n/a | 1 fire | 3 all-time, avg P&L marginal | 3 all-time, 27-week project | 3 all-time, 28-week project |
| Gate 3 ST | n/a | n/a | n/a | n/a | PASSED | PASSED | streak ended — still passed | monitoring (streak ended) | monitoring (streak resumed) |
| Gate 3 CAB | n/a | n/a | n/a | n/a | pending H9 | H9 REFUTED | no gate | no gate | no gate |
| Gate 3 Ghost | n/a | n/a | n/a | n/a | pending — see criterion | pending — see criterion | pending — see updated criterion | pending | pending |
| Gate 4 | n/a | n/a | n/a | n/a | working | working | working | working | working |
| Gate 5 | n/a | n/a | n/a | n/a | accumulating | accumulating | accumulating | LOCK_CANDIDATEs: XAUUSDm + BTCUSDm | LOCK_CANDIDATEs confirmed: XAUUSDm + BTCUSDm |

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

**SuperTrend W6 performance alert:** Week 6 P&L was +$10.92 (59 trades, 35.6% WR) — substantially below W5 (+$277.31, 84 trades, 52.4% WR). Causes are unclear: W6 was a thinner week (59 vs 84 trades) and the XAGUSDm outlier that carried W5 did not repeat. USTECm continues to drag (W6: 16.7% WR, 1/6 trades). If Week 7 SuperTrend P&L is below +$50 on 50+ trades, a regime-shift analysis is warranted before Week 8. The four-consecutive-positive-weeks streak is intact but the magnitude is declining. Do not interpret positive-week count as confirmation of sustained edge without examining per-trade expectancy trend.

**CAB evolution**: Moving from a 0% WR in W1 (caused by a multi-symbol tracking bug) to a mixed performance in W4/W5 where outlier wins generated net positive returns despite structural direction bias (17.2pp BUY/SELL gap).

**SuperTrend W8 collapse — XAGUSDm:** W8 produced -$92.85 from 67 trades. Single driver: XAGUSDm -$79.65 in W8 alone. All-time XAGUSDm is now -$80.85 / -$2.38/tr across 34 trades. The prior F14 "positive" label for XAGUSDm is overturned. XAGUSDm is ESCALATED_WATCH. If W9 produces ≥5 closed XAGUSDm trades with net P&L < -$20, disable via config switch before W10.

**CAB BUY-side collapse W8:** BUY WR fell to 10.0% (n=30, avg -$2.75/tr). SELL was 25.0% (avg +$1.54/tr) — third consecutive week where SELL avg P&L exceeds BUY avg P&L in dollar terms. Gap magnitude is PERSISTENT but direction-unstable across weeks. H14 EMA50 logging will provide structural context. Monitor W9.

**W9 — Ghost silence explained, ST best week, H22 gate confirmed:**
Ghost produced 64 fills on Sep 15 only; F6 gate suppressed all UP_PROBE
arming Sep 16–19 while SuperTrend held a LONG thesis on XAUUSDm. This is
correct system behavior. SuperTrend delivered its best week (+$95.36, 72
trades, 45.8% WR) with XAGUSDm reversing sharply from W8 drag to +$40.60
(+$6.77/tr, n=6) — ESCALATED_WATCH status removed. USTECm confirmed as
third consecutive negative week (28.6% WR, n=7) — disabled entering W10.
CAB BUY-side collapsed to 25.8% WR — both directions losing. H22 NY_OVERLAP
trigger confirmed (third consecutive week avg < −$0.30/tr, n≥10) — gate
implemented entering W10. W9 probe investigation confirmed all Sep 12 code
is deployed and running correctly; M5_CONTEXT absence explained by no new
CAB entries during W9; IMMEDIATE_EXIT/REAPER conditions were simply never met.

**Ghost Grid W6 deep analysis findings (Aug 31 2026):**
Full statistical analysis of 229 matched fills (W5+W6 audit CSV joined to MT5 outcomes) produced the following validated results. All 229 matched fills are UP_PROBE (SELL reversals). The audit CSV contains 240 raw fills; 11 were unmatched to MT5 outcomes because positions were still open at the time of the HTML export. All WR and P&L figures in this analysis use the 229 matched (confirmed closed) fills. The 48.4% WR for H4=UP is derived from matched outcomes and is the authoritative figure for gate design. Zero matched DOWN_PROBE fills exist in the dataset — the BUY side has not been active in the observation window.

H4 direction is the single strongest predictor: H4=UP fills produce 48.4% WR at +$0.27/trade vs H4=DOWN at 38.3% WR at -$0.79/trade (gap: 10.1pp WR, $1.06/trade P&L). This gap is structural — the Ghost 202 SELL reversal is mean reversion when H4 is UP (fading an overbought push) and directional alignment when H4 is DOWN (shorting with the trend), which is the wrong application of a mean-reversion strategy. F15 gate addresses this directly.

W4 findings scorecard vs W6 data:
- F1 ATR floor: direction held, effect size collapsed from 30pp to 1.2pp. ATR is a secondary filter after H4 direction, not primary.
- F2 NY_OVERLAP+H4_DOWN: FULLY INVERTED. Was best combo in W4 (64.5% WR), became worst in W6 (21.7% WR). Regime artifact. Retired.
- F3 Conviction monotonic: BROKEN. Non-monotonic in W6. Conv>50 still predictive (52.1% WR) but 40-50 bucket is worst (-$1.24/trade). Gate threshold revised to >50 when implemented; deferred.
- F4 ADX dead zone: INVERTED. ADX 20-25 was worst in W4, best in W6. ADX is regime-sensitive. Gate permanently retired.
- F5 London negative: HELD IN DIRECTION. Gate implemented for CAB. Ghost London gate pending Phase B1 sequencing.
- F7 NY_CLOSE+H4_UP: INVERTED. Was worst in W4, above-average in W6. Regime artifact. Gate permanently retired.
- F8 Q1 ATR high SL rate: HELD. 58.6% loss rate in Q1 ATR (vs 66.2% W4). Mechanically grounded — not regime-dependent. Basis for ATR gate.
- F15 H4 direction: NEW FINDING. Strongest predictor in dataset. Gate implemented Week 7.

Filter stack projection (theoretical — based on H4 direction filtering of the full UP_PROBE dataset; actual F15 implementation only gates DOWN_PROBE which has zero observed fills):
- F15 alone: 41% of fills remain, WR 48.4%, avg +$0.27/trade
- F15 + ATR>1.8: 21% of fills remain, WR 45.8%, avg +$0.56/trade
- F15 + ATR + Conv>50: 5% of fills remain, WR 72.7%, avg +$3.23/trade (n=11 — too thin for reliable estimation, not actionable yet)
Optimal near-term target: F15+ATR at 60 trades/week, +$0.56/trade.

NOTE: The Phase B recovery projection must distinguish between F15 (DOWN_PROBE gate, $0 current impact) and Phase B1b (UP_PROBE+H4=DOWN gate, ~$105/week impact). F15 is the correct first step as a data collection gate. Phase B1b is the actual loss reduction gate and should follow in Week 8 after F15 wiring is confirmed. The "60 trades/week at +$0.56/trade" estimate applies to the post-Phase-B1b population (UP_PROBE+H4=UP only), not to the post-F15 population which is unchanged from W6.

TRENDING_DOWN+H4_UP is the highest-value regime combination observed: 66.7% WR at +$2.27/trade (n=6). This sample is too small for statistical reliability — it is noted as theoretically grounded and consistent with the mean-reversion thesis, but must not be used to calibrate Phase C component weights. Minimum n=50 per regime combination required before weight assignment. Ghost 202 performs best when macro regime is trending down but H4 has pushed up (fading a counter-trend push back into the dominant direction). This is the strategy's theoretical sweet spot.

**Ghost Grid W7 deep analysis findings (Sep 5 2026):**
W7 produced 168 Ghost 202 fills across 3 trading days (Sep 4–5 had zero fills — F6 (ST LONG on XAUUSDm) suppressed all arming for 2 days). 165 fills were matched to MT5 closed outcomes; 13 unmatched (open at extraction time).

**Critical: H4 direction signal inverted in W7.** The W6 dominant predictor — H4=DOWN worse, H4=UP better — completely reversed:
  W6: H4=DOWN avg=-$0.82/tr | H4=UP avg=+$0.18/tr
  W7: H4=DOWN avg=+$0.27/tr | H4=UP avg=-$0.72/tr
Combined W6+W7 (n=422): H4=DOWN avg=-$0.37/tr | H4=UP avg=-$0.19/tr.
All-time (595 matched, W4–W7): H4=DOWN n=328 avg=-$0.50 | H4=UP n=267
avg=-$0.29. Neither cohort is positive expectancy all-time.
This is the same class of single-week inversion that retired F2, F4, F7.
B1b (UP_PROBE gate when H4=DOWN) is deferred — the W6 evidence basis
that justified its pre-approval has been contradicted. B1b would have
worsened W7 Ghost P&L by approximately $27.

**New signal: session dimension.** Independent verification identified
Ghost W7 session breakdown as a stronger and potentially more stable
signal than H4 direction:
  ASIAN:      n=85, avg=+$0.36/tr, P&L=+$30.26  (profitable)
  LONDON:     n=38, avg=+$0.09/tr, P&L=+$3.24   (near-flat)
  NY_CLOSE:   n=24, avg=-$0.98/tr, P&L=-$23.57  (loss)
  NY_OVERLAP: n=18, avg=-$2.32/tr, P&L=-$41.71  (worst)
NY sessions account for -$65.28 of W7 Ghost loss; ASIAN+LONDON
account for +$33.50 profit. Worst cohort: NY_OVERLAP×H4=UP×RANGING,
n=11, avg=-$2.98/tr. This is directionally consistent with the retired
F2/F7 observations (NY sessions were the problem zone in W4 too), and
session tags are not regime-conditional — making this potentially more
stable than H4 direction as a predictor. Registered as H22. Data
collection for W8+W9 before any gate evaluation.

**ATR floor update (all-time H4=UP, n=267):**
Q1 (ATR<1.33): WR=28.8%, avg=-$0.74 — mechanically grounded (F8).
Q2 (1.33–1.74): WR=49.3%, avg=+$0.01 — near-zero ceiling.
Q3 (1.74–2.47): WR=46.3%, avg=+$0.00 — flat.
Q4 (>2.47): WR=40.3%, avg=-$0.44 — negative again.
ATR gate alone cannot create positive expectancy in H4=UP fills. ATR
floor gate deferred pending W8 regime clarity.

**F6 quantified as W7's sole effective Ghost drag-reducer.** Sep 4–5
Ghost produced zero fills because F6 suppressed UP_PROBE arming while
ST held a LONG thesis on XAUUSDm (2,354 GHOST_ARM_BLOCKED_ST_LONG
events). At W7's H4=UP average (-$0.72/tr), the ~118 blocked fills
avoided approximately $85 of Ghost drag. F6 is currently the only
operational mechanism reducing Ghost loss.

**F15 confirmed as effective dead code.** In 832 all-time ARMED events,
DOWN_PROBE has armed once. The GHOST_ARM_BLOCKED_H4_DOWN counter cannot
serve as a B1b readiness signal — it will never accumulate meaningfully
while market conditions remain bullish. The original monitoring rule
('count > 10 events in W7') is falsified. B1b readiness rests
exclusively on multi-week H4 direction data consistency, which W7 does
not provide.

**Sep 9 2026 — Audit supplement findings affecting trend interpretation:**

Two findings from the independent audit supplement materially affect how prior
weekly data should be read:

1. **h4_direction_at_arm in fill rows is fill-time, not arm-time (F-A2):** Every
   H4 direction cohort analysis in W6 and W7 (the basis for F15, B1b pre-approval,
   and the B1b deferral) was measured at the moment the order was sent, not the
   moment the probe was armed. A probe can track across an H4 bar close. The H4
   direction at arming and at fill can differ. The W6/W7 cohort numbers should be
   treated as fill-time approximations until the arm-time cohort is computed from
   ARMED rows. This does not invalidate the session signal (H22) because session
   boundaries are hour-scale, not minute-scale.

2. **The adaptive ADX gate may not be running (F-A1):** The 30-day distribution
   of adx_at_fill (avg 19.26, max 39.43) and conviction at fill (max 59.75) is
   consistent with static thresholds (ADX<40, conviction<60), not with an adaptive
   P70 gate that would have blocked fills with ADX 33–39. If confirmed, the
   adaptive mechanism described in the architecture has been dormant throughout the
   observation period. All fill data was collected under a static gate, which is
   actually preferable for consistent analysis — but the documented mechanism and
   the running mechanism may differ.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Section 3 — Revised Forward Phase Plan

### 3.1 Phase A — Stabilize Foundation (Week 6, current)

**Status: ✅ COMPLETED AND CONFIRMED (Aug 31 2026)**
MPE confirmed publishing live data. See Section 2.3 for details.
- **MarketPulseEngine Fix:** Add startup verification logging in _update_symbol_timeframe() that logs first successful publish per symbol/timeframe. Add watchdog in main thread heartbeat checking KR snapshot age for XAUUSDm H4 — log WARNING if snapshot is older than 15 minutes or None. This makes the failure visible without changing the core logic.

### 3.2 Phase B — Statistical Gate Implementation (Weeks 7–10)

ONE GATE PER WEEK. Minimum one week of isolated measurement between each implementation. No stacking. One variable changes at a time.

#### GATE SEQUENCING RATIONALE
H4 direction (F15) must be implemented first because it is the dominant predictor — all other findings (ATR, conviction, session) were measured without controlling for H4 direction, which inflated their apparent effect sizes. Once F15 filters H4=DOWN fills, the remaining H4=UP population must be re-analyzed to derive correct thresholds for secondary gates. The sequence below reflects this.

#### Track B1: Ghost Grid Gates (in sequence)

1. **F15 — H4 Direction Gate** ✅ IMPLEMENTED Week 7 (Sep 1 2026)
   - Blocks DOWN_PROBE arming when H4 structural direction is DOWN
   - Logs: GHOST_ARM_BLOCKED_H4_DOWN
   - Evidence: n=229, H4=UP 48.4% WR vs H4=DOWN 38.3% WR, 10.1pp gap
   - Test: T20 added, 20/20 passing
   - Measurement: one full week of isolated data required before next gate
   - W7 outcome: GHOST_ARM_BLOCKED_H4_DOWN count = 0. Gate wiring confirmed
     in code but condition never reached (DOWN_PROBE armed once in 832
     all-time events). Zero fires is expected, not a wiring failure.
   - IMPORTANT — F15 SCOPE: F15 gates DOWN_PROBE (BUY side) when H4=DOWN. The entire current dataset is UP_PROBE (SELL reversals) — zero DOWN_PROBE fills exist. F15 reduces current Ghost drag by $0.00. It is a PREVENTIVE gate for the future BUY side, not a current loss reduction gate. F15 is also a data collection gate: GHOST_ARM_BLOCKED_H4_DOWN events count how often DOWN_PROBE wants to arm. When DOWN_PROBE is activated at Week 11+, H4=DOWN becomes the ACTIVATION trigger (the gate inverts from blocking to enabling). This dual nature must be understood before any parameter tuning based on W7 fill counts.

1b. **Phase B1b — PERMANENTLY CLOSED Sep 12 2026**
    H4 direction signal inverted in W6, W7, and W8 under three distinct
    macro Gold regimes. All-time arm-time cohort (n=834, F-A2 resolved):
    H4=DOWN avg -$0.372/tr, H4=UP avg -$0.389/tr. Neither cohort is
    positive-expectancy. The W8 arm-time data actively contradicts the
    hypothesis (DOWN +$0.877/tr, UP -$0.156/tr in W8).
    Do not re-evaluate at any future week without a structural explanation
    for the three-regime inversion.

2. **F1 — ATR Floor Gate** ⚠️ DEFERRED — NOT Week 9, data-dependent
   - Status: W7 H4 inversion must be understood before secondary gating.
   - All-time H4=UP data (n=267): best ATR bucket (Q2, 1.33–1.74)
     reaches only avg=+$0.01/tr. ATR alone cannot create positive
     expectancy within the H4=UP population. ATR Q1 gate (<1.33)
     remains mechanically grounded (F8) but is a noise-reduction tool,
     not a profit-generation gate.
   - Implementation trigger: two consecutive weeks of W8+W9 Ghost data
     showing H4=UP fills with WR > 42% and avg > $0.00/tr (confirming
     the H4=UP population can produce positive expectancy). Only then
     derive the ATR threshold from the combined post-inversion dataset.
   - Previous threshold of 1.8 is retired — derived from W6 pooled
     data before the W7 inversion. New threshold must come from
     post-inversion data.

3. **H22-revised — NY_OVERLAP Session Gate ✅ IMPLEMENTED Week 10 (Sep 22 2026)**
   Evidence: three consecutive weeks avg P&L < −$0.30/tr, n≥10.
   Gate blocks probe arming 12:00–15:59 UTC in ghost_hunter_thread
   (unified_runner.py) and run_hunter() (ghost_sniper.py).
   Logs GHOST_ARM_BLOCKED_SESSION. Verify: check count in
   logs/unified_runner.log during 12-16 UTC window.

4. **Conviction Gate** DEFERRED to Phase C
   - F3 is non-monotonic in W6. Conv>50 is directionally valid (52.1% WR) but conv 40-50 is WORSE than <40. Gate threshold of >40 is unreliable. Conviction metric needs regime-conditional interpretation before it becomes a reliable gate.
   - Action: collect Conv>50 fills across W7-W8. Requires n≥80 in the Conv>50 bucket before evaluating as a gate.

PERMANENTLY RETIRED (do not re-evaluate):
- F2 (NY_OVERLAP+H4_DOWN): Inverted completely W4→W6. Regime artifact.
- F4 (ADX 20-25 dead zone): Inverted completely W4→W6. Regime artifact.
- F7 (NY_CLOSE+H4_UP): Inverted completely W4→W6. Regime artifact.

#### Track B2: CAB Gates

1. **F5 — London Open Gate (CAB)** ✅ IMPLEMENTED Week 7 (Sep 1 2026)
   - Blocks CAB entries 07:00-11:59 UTC
   - Evidence: LONDON negative across all 3 parallel CAB systems (standalone cab n=259, cab_multi_pair negative, cab_super F5). Cross-system confirmation cleared single-system n=170 threshold.
   - Implementation: blocked_hours_utc extended to (0,1,2,3,4,5,6,7,8,9,10,11)
   - Test: T19 added, 19/19 passing
   - Entry gate only — open positions managed normally during London

2. **H14 — H4 EMA50 Bias Filter** PLANNED Phase B2 (Week 9+)
   - Description: Block bearish CAB inversions when price > H4 EMA50; block bullish inversions when price < H4 EMA50
   - Source: standalone cab strat_inversion.py (confirmed in code)
   - Evidence: would have suppressed SELL trades in W4+W5 trending Gold period that drove the 27.9% SELL WR
   - Action required first: add EMA50 at entry as a logged field in cab_watcher.log for 2 weeks. No gate until data confirmed.
   - H9 CAB H4 direction gate: REFUTED Aug 30. Gap narrowed to 7.5pp in ranging week. Effect regime-specific. No gate. Archived.

#### Track B3: Ghost DOWN_PROBE (BUY side) Research

The entire matched dataset (229 fills) is UP_PROBE. Zero matched DOWN_PROBE fills exist. F15 will log GHOST_ARM_BLOCKED_H4_DOWN events showing how often DOWN_PROBE wanted to arm. After 4 weeks of F15 data:
- If GHOST_ARM_BLOCKED_H4_DOWN count > 100: BUY side has abundant opportunity. Evaluate DOWN_PROBE activation when H4=DOWN (BUY reversals fading counter-trend pushes in a downtrend — symmetric thesis to SELL side).
- If count < 30: Market has not produced DOWN_PROBE conditions. Continue monitoring. Do not activate.
BUY side evaluation: earliest Week 11, contingent on F15 block count.

### 3.3 Phase C — Adaptive Intelligence (Weeks 10–14)

Adaptive intelligence replaces binary threshold gates with continuous regime-aware scoring. The hard filter path (Phase B) has a known ceiling: F15+ATR at 60 trades/week, approximately +$0.56/trade. Phase C extends this by making the system responsive to changing market conditions rather than calibrated to a specific regime.

**C1 — Entry Quality Score (Ghost)**
Replace binary arm/don't-arm with a continuous composite score:
  - H4 direction alignment weight (primary, ~40%)
  - ATR percentile weight (secondary, ~25%)
  - Regime alignment weight (TRENDING_DOWN+H4_UP = peak, ~20%)
  - Session quality weight (~15%)
Arm only when composite score exceeds threshold.
Implementation: shadow mode first (log score at every arm event, do not gate). Calibrate weights from 200+ post-F15 filtered fills. This is the same architecture as Market Exit Score, applied to entry.

**C2 — Market Exit Score v1 (all bots)**
Five-component continuous exit signal: regime alignment 30%, conviction trend 25%, ATR trajectory 20%, directional momentum 15%, opposite signal quality 10%.
MES < 0.30 for two consecutive cycles = exit regardless of R level.
Wire to CAB first (H4 timeframe = fewer spurious triggers). Validate two weeks before adding to SuperTrend.
Ghost exits: watcher already has BE-lock and personality TP. MES for Ghost targets the REAPER decision specifically.

**C3 — KR Layer 2/3 Shadow Activation**
RAW_LOGGING_MODE = True has been correct during edge validation.
Phase C begins shadow mode: log what Layer 2/3 would have blocked without actually blocking. One week shadow before activation.
Activation requires confirmed positive expectancy in at least two of three bots with gates in place.

**C4 — Gate 5 Lock (Bot-Instrument Fit Matrix)**
LOCK_CANDIDATEs confirmed Sep 12 2026: XAUUSDm and BTCUSDm. Formal lock pending W9 regression check. DISABLE_CANDIDATEs: EURUSDm, AUDNZDm, EURGBPm, USOILm. XAGUSDm: ESCALATED_WATCH — W9 outcome determines disable decision.

**C5 — Ghost ATR Position Sizing**
Replace fixed LOT_SIZE = 0.01 with risk-based sizing using the existing CAB _calculate_lot() pattern. max_lot_demo_cap = 0.01 remains. Prerequisite: Gate 3 Ghost must pass first.

**C6 — DOWN_PROBE Activation (BUY side)**
Contingent on F15 block count analysis at Week 11.
Apply symmetric H4 filter: arm DOWN_PROBE only when H4=DOWN.
Same entry quality score as SELL side, symmetric thesis.

### 3.4 Phase D — Live Deployment (Weeks 12–14)

Account recovery pre-condition: Do not begin Phase D until account equity > $7,500. Current equity $6,977. Phase B gates should recover this ground via reduced Ghost 202 drag and sustained SuperTrend positive expectancy.

1. **SuperTrend First**
   - **Go-live condition:** Gate 3 ST passed.
   - **Lot size:** Micro-lot (0.01)
   - **Monitoring period:** 2 weeks
   - **Scale condition:** Positive expectancy on live execution costs.
2. **CAB Watcher Second**
   - **Go-live condition:** Gate 3 CAB passed. CAB direction bias addressed — either H14 (EMA50 bias filter) validated from 2 weeks of logged data and confirmed positive, or BUY/SELL WR gap sustained below 5pp across two different market regimes.
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

## Section 4 — Confirmed Findings Registry

**CONFIRMED FINDINGS (implemented or statistically validated)**

| ID | Description | Evidence | Status | Gate |
|----|-------------|----------|--------|------|
| F6 | ST LONG on XAUUSDm at Ghost 202 fire = 32.4% WR vs 40.3% baseline | n=34, W4 | IMPLEMENTED Aug 16 | GHOST_ARM_BLOCKED_ST_LONG |
| F8 | Q1 ATR produces elevated SL hit rate (66.2% W4, 58.6% W6) | n=229 combined | CONFIRMED both weeks | Theoretical basis for ATR floor gate |
| F11 | OSI is primary CAB exit (59% of losses via OSI, 97.6% close before full SL) | n=83 losses W5 | CONFIRMED | No action — architecture working |
| F13 | SuperTrend positive expectancy 4 consecutive weeks | W3-W6 data | CONFIRMED | Gate 3 ST PASSED |
| F15 | Ghost DOWN_PROBE+H4=DOWN gate. Implemented Sep 1. F15 is a preventive gate for the future BUY side — DOWN_PROBE armed once in 832 total events; the gate fires 0 times under current market conditions. Not a current loss-reduction gate. | n=229 W5+W6 (basis); W7 confirmed gate as effective dead code — 0 fires in 178 fills | IMPLEMENTED Sep 1; ZERO FIRES W7; monitoring NOTE (Sep 9 audit): h4_direction_at_arm in fill rows is fill-time, not arm-time (F-A2). The evidence basis for F15 used fill-time H4. F15 gates DOWN_PROBE at arm time — these can differ if H4 bar closes during probe tracking. F15 has zero fires regardless, so this does not affect its current operational status, but the measurement methodology is noted. | GHOST_ARM_BLOCKED_H4_DOWN |
| F5 | LONDON session structurally negative across 3 independent CAB systems | cab n=259, cab_super n=82, cab_multi_pair negative | IMPLEMENTED Sep 1 (CAB) | blocked_hours_utc 07-11 UTC |

**FINDINGS WITH DIRECTIONAL SUPPORT (not yet gate-ready)**

| ID | Description | Evidence | Status | Next action |
|----|-------------|----------|--------|-------------|
| F1 | ATR Q1 (<1.33) mechanically grounded negative: WR=28.8%, avg=-$0.74/tr (all-time H4=UP, n=267). Best ATR bucket (Q2, 1.33–1.74) reaches only avg=+$0.01/tr. ATR alone cannot create positive expectancy in H4=UP fills. | n=267 all-time H4=UP (W4–W7) | DEFERRED — W7 H4 inversion means B1b population undefined. Re-derive threshold after 2 stable weeks. | Accumulate W8+W9 H4=UP data before threshold derivation. |
| F3 | Conviction>50 produces 52.1% WR. Non-monotonic — 40-50 bucket is worst in W6 | n=229 | PARTIALLY VALID. >50 threshold only. Not monotonic. | Collect n≥80 in Conv>50 bucket before gate |
| F5 | London Open negative for Ghost (direction held W6, not worst session) | n=23 W6 London fills | DIRECTIONALLY VALID. Ghost London gate sequenced after ATR floor. | Ghost London gate Week 9 |
| F14 | ST bot-instrument fit: BTCUSDm+XAUUSDm confirmed positive. XAGUSDm ESCALATED_WATCH (all-time -$80.85, -$2.38/tr; prior positive label overturned by W8 data). EURGBPm+USDJPYm+USOILm negative. DISABLE_CANDIDATEs: EURUSDm, AUDNZDm, EURGBPm, USOILm (3–5 consecutive negative weeks each). | n sufficient per symbol | EMERGING PATTERN → LOCK_CANDIDATEs confirmed | Gate 5 LOCK: XAUUSDm + BTCUSDm. XAGUSDm: W9 disable decision. |
| F16 | USTECm SuperTrend three consecutive negative weeks (W6 16.7% WR, W8 mixed negative, W9 28.6% WR n=7). Disable trigger met. | W6/W8/W9 data | IMPLEMENTED W10 — removed from config.json symbols | No restart required once positions close; config hot-reloads only entry decisions. |

**FINDINGS PERMANENTLY RETIRED (inverted between regimes)**

| ID | Description | Reason for retirement |
|----|-------------|----------------------|
| F2 | NY_OVERLAP+H4_DOWN best combo (W4: 64.5% WR) | INVERTED in W6: 21.7% WR. Regime artifact from W4 Gold uptrend. |
| F4 | ADX 20-25 dead zone (W4: 32.1% WR worst) | INVERTED in W6: 41.9% WR best bucket. ADX is regime-sensitive. |
| F7 | NY_CLOSE+H4_UP worst combo (W4: 27.8% WR) | INVERTED in W6: 41.2% WR above average. Regime artifact. |
| F9 | CAB SELL underperforms BUY by 17.2pp | REFUTED in ranging week: gap narrowed to 7.5pp. Regime-specific. |
| F10 | SELL losses on trending symbols | REFUTED — consequence of F9, same regime-specific root cause. |

**HYPOTHESIS REGISTRY (registered observations, not yet actionable)**

| ID | Hypothesis | Source | Required before action |
|----|-----------|--------|------------------------|
| H14 | H4 EMA50 bias filter for CAB entries | standalone cab strat_inversion.py | Log EMA50 at every CAB entry for 2 weeks. Requires n≥60 with EMA50 logged before gate evaluation. |

| H17 | Intra-ASIAN time-of-day effect (02:00-04:00 better than 00:00-01:00) | Ghost audit CSV sub-bucket | Too thin to evaluate — register for future multi-week accumulation |
| H18 | Early R-velocity (negative within 30 min) as Ghost loss predictor | Theoretical, KR computes it | Add 30-minute outcome checkpoint to audit log. Not implementable until logged. |
| H22-revised | NY_OVERLAP is worst Ghost session (avg -$0.685/tr, negative 3/3 measured weeks). Gate candidate: block 12:00–15:59 UTC. W8 = confirmation week 1. W9 confirmation required. | W9 data collection | Gate evaluation end of W9. |
| H19 | Trend Exhaustion Reversal Module (M4 candidate): H4 counter-trend push entry during TRENDING_DOWN+H4_UP window, structural SL, H4-close target. Differentiated from CAB by entering during the push rather than after inversion completes. | Ghost data TRENDING_DOWN+H4_UP 66.7% WR (n=6) | REGISTERED Aug 31 | Log M4 conditions alongside 50+ CAB entries. Compare hypothetical entry price vs CAB entry price. |
| H20 | London Open Range-Break Fade (M5 candidate): fade the London Open spike above/below Asian session range with structural SL and range midpoint target. All current modules gate London Open — this module would be active only during that window. | London Open universally negative for all current modules across 3 independent systems — uncovered regime opportunity | REGISTERED Aug 31 | Log Asian session range high/low and London Open price action for 4+ weeks. Pure observation, no code. |
| H21 | M5 structure at CAB H4 inversion entry as outcome predictor. Fields: m5_close_direction, m5_atr, m5_body_ratio, m5_bars_in_direction. If M5 micro-alignment predicts trade outcome, enables: (1) CAB entry quality gate, (2) Ghost pre-arm ahead of H4 inversion, (3) new dedicated module in M5-H4 cross-timeframe window. | REGISTERED Aug 31 | Add 4 M5 fields to cab_watcher.log at every new entry detection. Collect n≥50 before analysis. |

**AUDIT SUPPLEMENT FINDINGS — Sep 9 2026**

Findings from independent second-pass audit. All code-verified or data-consistent.
Status column uses the standard registry vocabulary.

| ID | Description | Evidence | Status | Action |
|----|-------------|----------|--------|--------|
| F-A1 | Adaptive ADX gate likely inert — static thresholds (ADX<40, conv<60) appear to be the operational gates based on 30-day fill distribution. `is_adaptive` flag in adaptive_thresholds_live.csv likely reads 0. If confirmed, Ambiguity D (self-loosening paradox) is theoretical, not operational. | 30-day log_extract: adx_at_fill max=39.43, conviction max=59.75 — both just under static thresholds. Adaptive gate would have blocked ADX 33–39 if operational. | VERIFICATION REQUIRED | Check is_adaptive at W8 extraction. If 0 → record as CONFIRMED STATIC. If 1 → design review item for W9. |
| F-A2 | h4_direction_at_arm fill rows contain fill-time H4, not arm-time. _get_h4_direction() called inside send_order() at trigger time. True arm-time H4 on ARMED rows only, not joined to outcomes. W6/W7 H4 cohort numbers that justified B1b are fill-time measurements. Gate fires at arm-time. These are different points in time. | Code-verified: send_order() calls _get_h4_direction() at lines ~539 and ~615 (inside ORDER_ERROR and ORDER_FILL_V51 paths). | VERIFIED — affects B1b trigger | Recompute W6/W7 H4 cohorts from ARMED rows before wiring B1b. Prerequisite for W9 B1b decision. |
| F-A3 | Three session definitions coexist with different UTC hour boundaries. H22 evidence uses get_session() hours. Any permutation-test backbone (A016/A018) used different hours. Gate implementation and evidence base must use the same definition. | Code-verified: three independent session definitions in ghost_sniper.py (get_session), shared_intelligence.py (MPE SessionTag), and research documentation. | VERIFIED | Standardise to get_session() for all future analysis. Re-run permutation under those hours before H22 gate is designed. |
| F-A4 | BE-lock threshold raised 0.5R→1.0R (sniper_watcher.py BE_LOCK_R=1.0) without re-measuring against clean data at new parameters. W1 cohort (n=2,458, 41.5% died before +0.5R) is the only historical measurement and was collected at BE_LOCK_R=0.5, SL=0.2×ATR — both now changed. No equivalent measurement at 1.0R/0.35×ATR exists. Highest-value unvalidated parameter in the system. | Code-verified: BE_LOCK_R=1.0 in sniper_watcher.py:151. W1 dataset documented in UNIFIED_BOT_CONTEXT.md used different parameters. | OPEN — unvalidated parameter change | Two-month retrospective: extract BE-lock cohort at current parameters. Compare fraction dying before +1.0R to W1's 41.5% dying before +0.5R. If substantially higher, parameter review needed. |
| F-A5 | MDP incorrectly states "204 fires under the same conditions as 202." Ghost Cache fires from GhostCache.update() loop before trigger check, without spread guard, without fresh brain state, using arming-time context. Architecturally different from 202. | Code-verified: GhostCache.update() in ghost_hunter_thread runs before the trigger block. No spread gate, no apply_gates() call at 204 fire time. | DOCUMENTATION ERROR — no code defect | Correct all MDP and roadmap references. 204's architecture is correct by design; only the description was wrong. |
| F-A6 | F6 single-week drag estimate ("$85 avoided in W7") is overstated. F6 suppressed arming Sep 4–5 — Ghost's worst days — but V2 without F6 earned +$63.68 on the same days. F6 is mechanistically valid (n=34, 8pp WR drop) but quantified drag reduction requires multi-week series. | Single-week measurement. V2 counterfactual partially contradicts the estimate. n=34 causal evidence remains valid. | OVERSTATED — reduce confidence on magnitude | Replace drag-estimate language across docs. Keep mechanistic validation language. |
| F-A1 | Adaptive ADX gate CONFIRMED STATIC. adaptive_thresholds_live.csv absent from deployed system. All W4–W8 fills (n=834) collected under static ADX<40, conv<60. Ambiguity D (self-loosening paradox) is theoretical, not operational. | n=834 | CLOSED Sep 12 2026 | No action |
| F-A2 | Arm-time vs fill-time H4 discrepancy harmless. 99.7% agreement across 712 matched ARMED→FILL pairs. B1b closure is not a measurement error. | n=712 | CLOSED Sep 12 2026 | No corrective action |

**HYPOTHESES REFUTED AND ARCHIVED**

| ID | Hypothesis | Refutation date | Reason |
|----|-----------|-----------------|--------|
| H9 | CAB H4 direction gate (block SELL when H4=UP) | Aug 30 2026 | Gap narrowed from 17.2pp to 7.5pp in ranging week. Regime-specific, not structural. |
| H13 | H1 structural breach as faster CAB exit than OSI | Aug 31 2026 | cab_multi_pair's H1_STRUCT_BREACH is a trailing SL label, not an active signal. Architecturally incomparable. |
| H15 | Stagnation decay: CAB trade open 24h+ at R<0.5 close on timeout | Sep 5 2026 | 0.9% of W6+W7 CAB losses qualify (1 of 115). Far below 30% threshold. No stagnation pattern exists. |
| H16 | Rollover gate for CAB entries 22:00-23:59 UTC | Sep 5 2026 | 0 CAB entries in that window across W6+W7. Gate not needed — pattern does not exist. |
| B1b | UP_PROBE gate when H4=DOWN | PERMANENTLY CLOSED Sep 12 2026 | H4 direction inverted in W6, W7, W8. No stable directional advantage all-time. |
| H22-original | "ASIAN is profitable" | REFUTED Sep 12 2026 | ASIAN avg -$0.314/tr, negative 4/5 weeks. Superseded by H22-revised (NY_OVERLAP is worst session). |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Section 5 — Active Task Board

### COMPLETED (Week 7, Sep 1–5 2026)

**Code changes deployed before W7:**
- [x] F15 Ghost H4 direction gate: wired in both unified_runner.py and
  ghost_sniper.py. Zero fires (DOWN_PROBE never armed). Gate is
  structurally correct — the arm condition was simply never met.
- [x] F5 CAB London Open gate: blocked_hours_utc (0..11). Zero CAB
  entries 07:00–11:59 UTC confirmed. Doc discrepancy noted: code blocks
  00:00–11:59, docs say 07:00–11:59 — correct docs, keep code as-is.

**End-of-week evaluations — outcomes:**
- [x] F15 effect: H4=DOWN avg +$0.27/tr, H4=UP avg -$0.72/tr. INVERTED
  vs W6. B1b deferred. 'Block count > 10' rule FALSIFIED and retired.
- [x] ATR threshold: all-time H4=UP Q2 ceiling only +$0.01/tr. ATR
  gate deferred — cannot produce positive expectancy without stable H4
  population.
- [x] F5 London gate (CAB): confirmed zero entries in window. ✅
- [x] H15 stagnation: 0.9% qualify. CLOSED — no pattern.
- [x] H16 rollover: 0 entries in window. CLOSED — no pattern.
- [x] 204 Gate 2: 3 all-time fires. Need 27 more.
- [x] ST Gate 5: XAUUSDm +$2.73/tr, ETHUSDm +$1.51/tr, USTECm +$1.44/tr
  positive. XAGUSDm -$6.09/tr, USOILm -$1.97/tr negative. Accumulating.
- [x] F15 block count: 0. Readiness rule retired (see B1b deferral).
- [x] B1b readiness: H4 inversion observed. B1b deferred. New criterion
  established (see Section 3.2).
- [x] H22 registered: Ghost NY session signal (see Hypothesis Registry).

### WEEK 8 (Sep 8–12 2026) — COMPLETED

**Code changes deployed entering W8:**
- [x] H21 M5 logging — cab_watcher.py manage_fluid_logic(). 29 lines
      confirmed, all fields present.
- [x] CAB IMMEDIATE_EXIT rule (cab_watcher.py): exits losing trades
      within first 2 hours when R ≤ −0.20 and no prior actions taken.
      Logs: IMMEDIATE_EXIT|R{x}|held_{n}min
- [x] CAB REAPER simplified (cab_watcher.py): removed 7-condition
      triple gate. New: R ≤ −0.50 AND last closed H4 bar against
      position direction. Bar-gated. Logs: REAPER|H4_AGAINST|R{x}
- [x] SuperTrend ENTRY_QUALITY logging (supertrend_bot.py):
      cluster_spread, cluster_consensus, er_at_entry logged at every
      entry. Stored in TradeContext and trade_history for classifier.
- [x] CAB_ENTRY_QUALITY logging (cab_entry.py): h4_bar_position,
      m15_aligned_bars, nearest_swing_atr logged at every H4 inversion.
- [x] GHOST_FIRE_QUALITY logging (ghost_sniper.py, unified_runner.py):
      committed_reversal_bars, trigger_bar_body_ratio logged at every
      Ghost trigger (before spread guard in unified_runner.py).

**W8 outcomes:**
- [x] H21 M5 logging confirmed active (29 lines, all fields present)
- [x] Audit CSV unified-mode write path confirmed (141 W8 rows)
- [x] F-A1 closed: adaptive gate static throughout W4–W8
- [x] F-A2 closed: arm-time H4 discrepancy harmless (99.7% agreement)
- [x] B1b permanently closed: three-regime inversion confirmed
- [x] H22 redefined: NY_OVERLAP worst session, ASIAN not profitable
- [x] Gate 5 LOCK_CANDIDATEs confirmed: XAUUSDm + BTCUSDm
- [x] F14 XAGUSDm overturned: -$80.85 all-time
- [x] Two-month retrospective completed: 7 targets, all produced

### WEEK 9 — Data Collection + W8 Implementation Verification

**Code changes deployed entering W9:**
- [x] CAB IMMEDIATE_EXIT rule (cab_watcher.py) — live W9
- [x] CAB REAPER simplified (cab_watcher.py) — live W9
- [x] SuperTrend ENTRY_QUALITY logging (supertrend_bot.py) — live W9
- [x] CAB_ENTRY_QUALITY logging (cab_entry.py) — live W9
- [x] GHOST_FIRE_QUALITY logging (ghost_sniper.py, unified_runner.py) — live W9

**Daily monitoring W9:**
- [ ] IMMEDIATE_EXIT fires: grep -c "IMMEDIATE_EXIT" logs/cab_watcher.log
      Expected: nonzero within first trading day.
- [ ] REAPER fires: grep -c "REAPER|H4_AGAINST" logs/cab_watcher.log
      Expected: nonzero within first week. If zero after 5 days,
      investigate — the H4 bar condition should trigger regularly.
- [ ] ENTRY_QUALITY logging: grep -c "ENTRY_QUALITY" logs/supertrend_XAUUSDm.log
      Expected: one line per ST entry on XAUUSDm.
- [ ] CAB_ENTRY_QUALITY: grep -c "CAB_ENTRY_QUALITY" logs/cab_watcher.log
      Expected: one line per CAB inversion fire.
- [ ] GHOST_FIRE_QUALITY: grep -c "GHOST_FIRE_QUALITY" logs/sniper_hunter.log
      Expected: one line per Ghost probe trigger (including blocked fires).
- [ ] Thread health: grep "Heartbeat OK" logs/unified_runner.log | tail -3
- [ ] XAGUSDm ST P&L: track daily. If ≥5 trades, net < −$20 → disable.

**End-of-week W9 evaluations:**
- [x] H22-revised: CONFIRMED — gate implemented entering W10
- [x] XAGUSDm disable decision: NOT DISABLED — W9 strongly positive (+$40.60)
- [x] Gate 5 formal lock: XAUUSDm + BTCUSDm confirmed, no regression
- [x] IMMEDIATE_EXIT vs full-loss comparison: conditions not met in W9, code confirmed deployed
- [x] REAPER fires: conditions not met in W9, code confirmed deployed
- [x] Entry quality data: GHOST_FIRE_QUALITY and CAB_ENTRY_QUALITY confirmed in correct log files; code deployed correctly
- [x] Probe investigation: all Sep 12 features confirmed deployed; all zero-count results explained

### WEEK 10 (Sep 22–26 2026)

**Code changes deployed entering W10:**
- [x] H22 NY_OVERLAP gate: wired in unified_runner.py ghost_hunter_thread
      and ghost_sniper.py run_hunter(). Logs GHOST_ARM_BLOCKED_SESSION.
      Test T21 added, 21/21 passing.
- [x] USTECm disabled: removed from config/config.json symbols section.
      Requires restart to take effect.

**Daily monitoring W10:**
- [ ] H22 gate firing: grep -c "GHOST_ARM_BLOCKED_SESSION" logs/unified_runner.log
      Expected: nonzero on first day with fills during 12-16 UTC.
      If zero after Day 3 with normal Ghost activity: wiring broken.
- [ ] Ghost 202 fills: reduced volume expected vs prior weeks (NY_OVERLAP
      was ~22% of fills). WR and avg P&L should improve.
- [ ] USTECm absent: confirm magic 404213 not in startup symbol list in
      logs/unified_runner.log after restart.
- [ ] M5_CONTEXT: if new CAB entries fire this week, confirm M5_CONTEXT
      appears in logs/cab_watcher.log.
- [ ] IMMEDIATE_EXIT: any fires? Note R at fire and time held.
- [ ] Thread health: grep "Heartbeat OK" logs/unified_runner.log | tail -3
- [ ] XAGUSDm: track ST P&L daily. W9 reversal needs one more week to
      confirm stability before removing from watch list entirely.

**End-of-week W10 evaluations:**
- [ ] Ghost 202: does avg P&L improve from −$0.26/tr (W9)? Target: positive
      or materially less negative. Key question: does blocking NY_OVERLAP
      move the remaining ASIAN+LONDON fills to net positive?
- [ ] Gate 5 lock: XAUUSDm and BTCUSDm — any W10 regression?
- [ ] CAB trajectory: is BUY WR recovering from 25.8%? Are IMMEDIATE_EXIT
      or REAPER firing now that more data has accumulated?
- [ ] H22 gate count: how many probes were blocked during 12-16 UTC?
      Express as % of total ARM events.
- [ ] Account equity direction: is the trajectory improving?

**B1b trigger for W9 consideration (both required):**
  - W8 H4=DOWN avg P&L < -$0.50/tr AND H4=UP avg P&L > +$0.10/tr
  - W9 H4=DOWN avg P&L < -$0.50/tr AND H4=UP avg P&L > +$0.10/tr
  If both met: prepare B1b for W9. If not: extend observation to W10.

**NEXT (Week 9 — conditional):**
| Task | Status | Trigger |
|------|--------|---------|
| Phase B1b — UP_PROBE H4=DOWN Gate | DEFERRED — evaluate at W9 | Both W8+W9 H4 trigger conditions met (see above) |
| ATR Floor Gate (Ghost) | DEFERRED — data-dependent | W8+W9 H4=UP fills show avg > $0.00/tr before deriving threshold |
| Ghost NY Session Gate (H22) | RESEARCH | W8+W9 NY session data confirms pattern before any gate |
| H14 EMA50 logging (CAB) | PLANNED | Add EMA50 at every CAB entry — data collection only |

**BACKLOG (Phase C, Weeks 10–14):**
| Task | Status | Trigger |
|------|--------|---------|
| Entry Quality Score (Ghost) | PLANNED | 200+ post-gate filtered fills accumulated |
| Market Exit Score v1 | PLANNED | Phase C start, confirmed B-phase positive expectancy |
| KR Layer 2/3 Shadow Mode | PLANNED | Two bots confirmed positive expectancy with gates |
| Gate 5 Lock | PLANNED | 20+ trades per active ST symbol |
| Ghost ATR Position Sizing | PLANNED | Gate 3 Ghost passed |
| DOWN_PROBE Activation | PLANNED | F15 block count >100 over 4 weeks |
| Magic 201 shadow pipeline fix | PLANNED | Fix is_shadow send_order() to write audit CSV rows |
| SuperTrend Live Deployment | PLANNED | Account >$7,500, Phase D start |
| CAB Live Deployment | PLANNED | Account >$7,500, H14 evaluated |
| Ghost Live Deployment | PLANNED | Account >$7,500, Gate 3 Ghost passed |
| M5 data collection (H21) | ACTIVE Week 8 | Logging implemented — accumulate n≥50 before analysis |
| H19 Trend Exhaustion Module | MONITORING | 50+ comparable events logged |
| H20 London Open Fade | MONITORING | 4+ weeks of pattern observation |
| H22 Ghost NY Session | MONITORING | W8+W9 data before gate evaluation |

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
- CAB architecture changes require multi-regime data confirmation. H9 was refuted (Aug 30 2026). CAB direction bias (H14 EMA50 filter) requires 2 weeks of logged EMA50 data before evaluation. No CAB entry-filter changes until H14 data is available.
- MarketPulseEngine is the single highest architectural priority. Every bot is running on hardcoded fallbacks for regime, ADX, and ATR. Fixing Layer 0 data publication unlocks all downstream KR value.
- Account recovery is a precondition for live deployment. Do not begin Phase D while account equity is below $7,500.
- Cross-system confirmation from parallel standalone models running the same entry signal accelerates gate evidence thresholds. A finding confirmed independently across three systems with different exit architectures is treated as stronger evidence than single-system n alone. Applied first to F5 London gate (n=82 in-system confirmed by n=259 standalone cab + cab_multi_pair negative direction).
- W4 statistical findings must not be implemented based on W4 data alone. F2, F4, and F7 were confirmed findings that completely inverted in W6. Multi-regime confirmation (minimum two distinct market regimes) is required before any session×H4 combination gate is implemented.
- The hard filter path (Phase B gates) has a known ceiling at approximately +$0.56/trade at 60 trades/week (F15+ATR combination). Adaptive intelligence (Phase C entry quality score) is the path beyond that ceiling and must be built from filtered Phase B data, not from the unfiltered baseline.
- H4 direction is a regime-conditional predictor, not a structural one.
  W6 showed H4=DOWN as the loss driver; W7 showed H4=UP as the loss
  driver. All-time, neither cohort is positive-expectancy. Any H4-based
  gate (B1b) requires confirmation across a minimum of two consecutive
  weeks showing the same directional advantage before implementation.
  Single-week evidence that contradicts a prior week's finding is
  sufficient to defer the gate.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Section 7 — Document Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| v1.7 | Sep 19 2026 | Claude + IDE Agent | W9 analysis integration: W9 KPI actuals, ST best week (+$95.36), Ghost silence explained (F6 gate Sep 16–19), H22 NY_OVERLAP gate implemented (T21 added, 21/21 passing), USTECm disabled (F16), XAGUSDm ESCALATED_WATCH removed (+$40.60 W9), Gate 5 LOCK_CANDIDATEs confirmed (XAUUSDm + BTCUSDm), W10 task board with H22 monitoring and USTECm verification. |
| v1.6 | Sep 12 2026 | Claude + IDE Agent | W8 two-month retrospective integration. B1b permanently closed (three-regime H4 inversion confirmed). H22 redefined (NY_OVERLAP worst session, not ASIAN profitable). F14 XAGUSDm label overturned (-$80.85 all-time). Gate 5 LOCK_CANDIDATEs: XAUUSDm + BTCUSDm. DISABLE_CANDIDATEs: EURUSDm/AUDNZDm/EURGBPm/USOILm. F-A1 and F-A2 closed. CAB IMMEDIATE_EXIT and simplified REAPER deployed. Entry quality logging scaffold deployed across all three bots. |
| v1.5 | Sep 9 2026 | Claude + IDE Agent | Audit supplement integration: six F-A findings added to findings registry (F-A1 through F-A6); two doc corrections (F-A5 204 description, F-A6 F6 drag estimate); pre-W9 verification tasks added; two-month retrospective analysis scheduled for Sep 12; h4_direction_at_arm measurement methodology correction (F-A2) applied to B1b and H22 preconditions; session boundary standardisation requirement (F-A3) added to H22; BE-lock parameter question (F-A4) added to retrospective scope; L2 integration assessment recorded (Ghost Phase C, ST Phase D, CAB Phase C). |
| v1.4 | Sep 5 2026 | Claude + IDE Agent | W7 analysis integration: W7 KPI actuals, H4 direction inversion documented, B1b deferred with new trigger criteria, ATR floor deferred, H22 registered (Ghost NY session), H15/H16 refuted and archived, F6 quantified as sole Ghost drag-reducer, F15 confirmed as zero-fire dead code with readiness rule retired, 201 shadow pipeline broken confirmed, W8 task board, updated B1b and ATR gate sequencing. |
| v1.0 | Aug 26 2026 | IDE Agent | Initial creation consolidating roadmap.md, todo_tracker.md, W5/W6 plans, and revised plan from session Aug 26 2026 |
| v1.1 | Aug 26 2026 | IDE Agent | Correction pass per Claude review Aug 26 2026 |
| v1.2 | Aug 31 2026 | Claude + IDE Agent | Full W6 analysis integration: W6 KPI actuals, W7 KPI targets, W4 findings scorecard (F2/F4/F7 permanently retired), F15+F5 implementation records, Phase B gate sequence revised with B1b UP_PROBE gate added, Phase C adaptive intelligence roadmap, Section 4 findings registry rebuilt with confirmed/directional/retired/hypothesis tiers, permanently retired F2/F4/F7/H9/H13, added H14-H18, F15 scope clarified as DOWN_PROBE preventive gate (not current loss reduction). |
| v1.3 | Aug 31 2026 | Claude + IDE Agent | Added Section 0 (System Vision and Architecture Philosophy): core vision, module portfolio framework, current module registry, candidate pipeline (M4/M5), M5 research agenda (H21). Registered H19 (Trend Exhaustion Reversal), H20 (London Open Fade), H21 (M5 structure predictor). Added M5 logging, H19/H20 research items to backlog. |

