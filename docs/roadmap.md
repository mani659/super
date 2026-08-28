---

# Project Roadmap & Master Plan

**Last Updated:** Aug 22 2026
**Current Phase:** Phase 2 Demo Testing — Week 6 (Statistical Gate Implementation)

---

## 1. What We Have Built and Stabilized

The unified three-bot system is fully operational on Exness MT5 demo
account 474167713. All Tier 0 mechanical bugs identified through the
July audit have been resolved. The system runs as a single Python
process with five daemon threads sharing one MT5Gateway instance.

### Tier 0 Bugs Resolved (complete)
- Ghost Grid LEG_TP_SET fires unconditionally on every leg. GridState
  resets on 72h staleness timeout.
- CAB Watcher manages PROTECTOR, HARVESTER, and REAPER across all
  symbols, not just XAUUSDm.
- Ghost Cache (magic 204) wired into live unified_runner.py thread and
  confirmed firing.
- KnowledgeRegister thread concurrency race condition eliminated.
- Ghost Hunter send_order() return value captured — FIRE_FAILED logged,
  leg quota not consumed on rejection.
- CAB manage_fluid_logic() ticket loop bug fixed — closed tickets removed
  from iteration after R-budget stop.
- UnifiedFailover.mq5 MAGIC_NUMBERS expanded to cover all 11 dynamic
  symbols.
- Circuit breaker blindspot closed — global position count checked before
  every entry.
- Ghost Grid 10016 SL rejection eliminated — Phase 2 SLTP anchor now
  computed from actual fill price (result.price), not pre-order tick price.
- CAB premature entry on restart fixed — state file persistence in
  logs/cab_state_{symbol}.json, startup grace period blocks cold-start
  re-fires.
- Ghost 204 decouple fix — ghost_cache = None removed from the 202
  trigger block. GhostCache now persists after a 202 fire, allowing 204
  to accumulate deeper virtual layers on the same probe. Cache only resets
  when armed = None (full probe cycle end).
- CAB watcher log path fixed — RotatingFileHandler now writes to
  logs/cab_watcher.log (was cab_production_v16.3.log in root).
  extract_bot_logs.py aligned to same path. H5 evaluation now unblocked.

### Architecture and Parameter Changes Applied
- Ghost Grid SL widened from 0.20×ATR to 0.35×ATR.
- Probe arming blocked during TRENDING_UP, TRENDING_DOWN, UNKNOWN regime.
- Magic 201 detached from MAX_LEGS and running as pure shadow
  (is_shadow=True, virtual fills only).
- SuperTrend si_confirmed calibrated to 0.55. Regime engine shifted from
  M1 to M15.
- Global config switches enable live bot/leg toggling without process
  restart.
- Leg 203 (Trend-Follow) removed from Ghost Grid. SuperTrend owns all
  trend entries.
- CAB demo lot cap at 0.01. Retry storm bounded to 3 attempts per H4 bar.
- MQL5 UnifiedFailover EA ATR handle caching implemented.
- H4 context logging added: h4_direction_at_arm and kr_regime_at_arm
  columns in sniper_v51_live_audit.csv.
- F6 cross-bot gate implemented (Aug 16 2026): Ghost UP_PROBE arming
  suppressed when KR contains active SuperTrend LONG thesis on XAUUSDm.
  Wired in both unified_runner.py ghost_hunter_thread and
  ghost_sniper.py run_hunter(). Logs GHOST_ARM_BLOCKED_ST_LONG.
- Ghost Cache N_LAYERS_DEFAULT lowered from 3 to 2 (Aug 22 2026):
  Zero fires in Week 5 met the pre-agreed trigger condition. n=2 fires
  at 2nd virtual layer, enabling Gate 2 data collection to begin.

---

## 2. Weekly Performance Summary

| Week | Period | Account Close | Week P&L | Primary Driver |
|------|--------|--------------|----------|----------------|
| Week 3 | Aug 1–8 | ~$7,128 | ~-$872 | Ghost 202 structural short bias into uptrend |
| Week 4 | Aug 11–15 | ~$6,723 | ~-$1,067 | Ghost 202 all-SELL into 130pt Gold rally; CAB drag |
| Week 5 | Aug 18–22 | $6,977 | +$386 | SuperTrend trending week; Ghost 202 correctly suppressed |

**Week 5 performance by component (Aug 18–22, MT5 export verified):**
- SuperTrend: 84 closed trades, 52.4% win rate, +$277.31. Third
  consecutive positive-expectancy week. Dominant driver of account
  recovery.
- CAB: 92 closed trades, 35.9% win rate, +$44.68. Net positive driven
  by two large outlier wins (XAGUSDm +$165, BTCUSDm +$38). Underlying
  pattern unchanged — see H9 CAB direction bias below.
- Ghost 202: 6 fills (vs 81 in Week 4), 33.3% win rate, -$8.24.
  Near-silence caused by regime gate correctly suppressing probe arming
  during trending Gold week. This is correct system behavior.
- Ghost 204: 0 fires. N_LAYERS_DEFAULT lowered to 2 entering Week 6.
- Ghost 201 shadow: data not yet extractable from current logging.
- F6 gate: 0 GHOST_ARM_BLOCKED_ST_LONG events. Probable cause: regime
  gate blocked arming before F6 check evaluated. Gate wiring confirmed
  in code review — not a dead wire.

**Account:** $10,000 start → $6,977 close of Week 5 (-30.2% overall
drawdown, recovered 2.6pp from Week 4 close).

---

## 3. Confirmed Findings Registry

### Ghost Grid Findings (from Week 4 statistical analysis, n=293)

| ID | Finding | Evidence | Status |
|----|---------|----------|--------|
| F1 | ATR is the strongest single predictor. Q4 high-ATR: win%=57.5%, +$1.11/trade. Q2 low-ATR: win%=27.4%, -$1.18/trade. Gate candidate: arm only when M1 ATR > 1.8. | n=293 matched trades, quartile analysis | PENDING Week 6 confirmation (W5 had only 6 fills — insufficient) |
| F2 | NY_OVERLAP + H4_DOWN is the only strongly positive-expectancy subset. n=31, win%=64.5%, +$1.55/trade. | n=31, session×H4 cross-tab | PENDING Week 6 confirmation |
| F3 | Conviction > 50 predicts wins. Monotonic relationship confirmed. Gate candidate: conviction > 40. | n=293, conviction bucket analysis | PENDING Week 6 confirmation |
| F4 | ADX 20-25 is the dead zone. n=109, 32.1% win rate, -$0.69/trade. Gate candidate: block ADX 20-25. | n=109 in dead zone bucket | PENDING Week 6 confirmation |
| F5 | LONDON session is structurally negative. Both H4 directions lose. | n=59 LONDON trades | PENDING Week 6 confirmation |
| F6 | ST LONG on XAUUSDm at Ghost 202 fire time: 32.4% win rate vs 40.3% baseline, 3× worse avg P&L. | n=34 overlap events | IMPLEMENTED (Aug 16). Gate wired. Effectiveness evaluable after Week 6 data. |
| F7 | NY_CLOSE + H4_UP second-worst combo. n=54, 27.8% win rate, -$0.68/trade. 80% of NY_CLOSE fills fire into H4_UP. | n=54 | PENDING Week 6 confirmation |
| F8 | Low ATR (Q1) produces 66.2% SL hit rate, avg hold 6 min. | n=74 Q1 trades | PENDING Week 6 confirmation |

**Why F1–F5, F7–F8 remain pending:** Week 5 produced only 6 Ghost 202
fills due to regime suppression during a trending Gold week. The combined
dataset is n=87 — still dominated by Week 4 data. Confirmation requires
a ranging Gold week where 202 runs at normal volume (80–350 fills). All
gate implementation decisions are deferred until that data arrives.

### CAB Findings (from Week 4+5 analysis, n=130)

| ID | Finding | Evidence | Status |
|----|---------|----------|--------|
| F9 | CAB SELL trades systematically underperform BUY trades in trending conditions. BUY: 45.2% win rate, avg_R +0.104. SELL: 27.9% win rate, avg_R -0.087. 17.2pp gap. | n=130, direction split across all symbols | REGISTERED. Requires Week 6 data to confirm gap holds in non-trending week. |
| F10 | SELL underperformance concentrated in trending assets. XAUUSDm SELL: 25% WR. USOILm SELL: 0% WR. GBPUSDm SELL: 0% WR. All trended bullish in W4+W5. | n=130, direction×symbol cross-tab | REGISTERED. Same data source as F9. One-variable observation. |
| F11 | CAB losses exit at median exactly 1 H4 bar (4h) hold time. 59% of losses close at the next H4 bar via OSI. 97.6% of losses close before full 2.5×ATR SL. | n=83 losses, hold time distribution | CONFIRMED. OSI is the primary exit mechanism for CAB losers. Broker SL is not the problem. |
| F12 | CAB positive symbol cluster (BTCUSDm, ETHUSDm, USTECm): 59.4% win rate, +$91.18 combined. Negative cluster (GBPUSDm, XAGUSDm, EURGBPm, USOILm): 22.2% win rate, -$74.75 combined. | n=32 positive, n=54 negative | REGISTERED. Gate 5 data. Cluster difference is large but directional market conditions confound the sample. |

### SuperTrend Findings (emerging from W4+W5)

| ID | Finding | Evidence | Status |
|----|---------|----------|--------|
| F13 | SuperTrend has confirmed positive expectancy across three consecutive weeks. W3: +$119, W4: +$55, W5: +$277. Win rate stable at 52–53%. | n=103 W4+W5 closed trades | CONFIRMED. Three-week consistency qualifies for Gate 3 ST criterion. |
| F14 | Bot-instrument fit matrix (early, n=9–20 per symbol): BTCUSDm (+$5.87/tr, 84.6% WR), XAUUSDm (+$22.20/tr, 88.9% WR), XAGUSDm (+$4.46/tr, 45.5% WR) are positive. EURGBPm (-$0.20/tr, 18.2% WR), USDJPYm (-$0.33/tr, 33.3% WR), USOILm (-$0.47/tr, 46.2% WR) are marginal negative. | n=103 W4+W5 by symbol | REGISTERED. Insufficient n per symbol for Gate 5 lock. Continue accumulating. |

---

## 4. Hypothesis Registry

| ID | Hypothesis | Status |
|----|-----------|--------|
| H1 | 201 ADX gate improves win rate | UNRESOLVABLE. Virtual fill ADX not captured per-fire. Superseded by F3 and F4. |
| H2 | DOWN_PROBE fires into H4 uptrends | REVISED → confirmed as F7. Direction + session is the correct framing. |
| H3 | 202 outcome in ADX<20 is random walk | REVISED → confirmed as F3+F4. Conviction IS predictive; ADX dead zone confirmed. |
| H4 | KR M15 regime mislabels H4 trends as RANGING | CONFIRMED. 98.5% RANGING label regardless of H4 direction. MarketPulseEngine not instantiated — all KR Layer 0 data returns None. Architectural fix deferred to post-gate-validation. |
| H5 | CAB 2.5×ATR SL inside H4 noise band | BLOCKED → REVISED. Data shows 97.6% of CAB losses close before full SL. Median loss exits at exactly 1 H4 bar via OSI. H5 as originally framed (SL too tight) is not the primary CAB problem. Primary problem is direction misalignment (F9, F10). |
| H6 | SuperTrend RANGING predicts 202 success | CONFIRMED → implemented as F6 gate. |
| H7 | Ghost Grid ADX predicts CAB hold duration | STILL BLOCKED. Insufficient PROTECTOR data (2 fires across W4+W5). |
| H8 | Equity trajectory | W5 close $6,977 (-30.2% from $10,000). First positive week. SuperTrend is the confirmed positive-expectancy component. Ghost 202 correctly suppressed by regime gate. |
| H9 | CAB H4 directional bias gate improves win rate | NEW — REGISTERED Week 5. Hypothesis: blocking CAB bearish inversion entries when H4 structural direction is bullish will close the 17.2pp BUY/SELL win rate gap (F9). Test: check whether gap persists in Week 6 when Gold market structure may differ. Minimum evidence: gap holds at >10pp in Week 6 non-trending conditions (n≥50). Implementation if confirmed: single H4 direction check in cab_entry.py before bearish inversion entry, using _get_h4_direction() logic already implemented in ghost_sniper.py. |

---

## 5. CAB Architecture Discussion — Parked for Data Confirmation

An external enhancement specification (`cab_super_enhancement_spec.md`,
Aug 22 2026) proposed four enhancements to cab_super and a comparison
against two standalone CAB models.

**Decision: Run cab_super unchanged through Week 6. Revisit after data.**

**What the audit confirmed is real:**
- F9/F10 direction misalignment is confirmed in data (17.2pp BUY/SELL gap).
- F11 OSI is the primary exit mechanism — exit architecture is working.
- Enhancement 4 (MFE/MAE logging) is safe and addable anytime; infra
  exists via TradeAnalyticsEngine.

**What was rejected or deferred:**
- Enhancement 3 (Tri-Vector ADX framework): introduces two unvalidated
  strategies under the same model. Not an enhancement — a strategy change.
  Deferred indefinitely pending independent validation.
- Enhancement 2 (Vol_Expansion_Ratio gate at 1.5): threshold has no
  derivation from actual trade data. Not implementable until the ratio
  is cross-referenced against winning vs losing trades.
- Enhancement 1 (H4 Macro Trend Filter): the mechanism is correct in
  principle (H9 registered above). The implementation path is simpler
  than proposed — one if-statement in cab_entry.py using _get_h4_direction()
  rather than a new EMA alignment system.
- H1_STRUCT_BREACH claim in the external spec: this feature does not
  exist in cab_watcher.py. The spec attributes a non-existent feature
  to the current system. The actual exit mechanism is OSI at the next H4
  bar — confirmed from data (F11).

**Week 6 confirmation triggers for H9:**
- If SELL win rate stays below 35% and BUY win rate stays above 40% in
  Week 6 data (n≥50 with a non-trending Gold week) → H9 confirmed →
  implement H4 direction gate in cab_entry.py for Week 7.
- If gap reverses in a ranging week (SELL recovers to within 5pp of BUY)
  → the F9/F10 effect was regime-specific, not structural → H9 refuted
  → no gate needed → re-evaluate direction filter hypothesis.

**Next action if H9 confirmed:** Write single-function `_get_h4_direction(symbol)`
in cab_entry.py CABEntryEngine (the ghost_sniper.py version is standalone,
not importable by CABEntryEngine without import restructure). Gate: before
firing a bearish inversion on any symbol, check H4 direction. If H4 is UP
(last closed H4 bar close > close 3 bars prior), skip the SELL entry and
log CAB_SELL_BLOCKED_H4_UP. Does not affect BUY entries or any open
position management.

---

## 6. Decision Gates — Current Status

| Gate | Description | Status |
|------|-------------|--------|
| Gate 1 | Unified runner stable, magic isolation clean | **PASSED** |
| Gate 2 | 204 vs 202 avg_R — 30+ fills each | In progress. 204: 0 fills in W5 (N_LAYERS lowered to 2 entering W6 — first data expected W6). 202: 87 fills total but only 6 in W5. Not yet evaluable. |
| Gate 3 | Individual conviction: ST avg R>0, CAB false-cut <30%, Ghost stop rate <20% | **SuperTrend: PASSED** (three consecutive positive weeks, avg +$3.23/trade W4+W5). CAB: neutral pending H9 confirmation. Ghost: gate not evaluable until 202 runs at normal volume. |
| Gate 4 | Regime complementarity confirmed — overlap <15%, combined drawdown lower than individual | Week 5 demonstrates this working as designed: trending week → ST profitable, Ghost suppressed, system net positive. Formal evaluation requires a ranging week comparison. |
| Gate 5 | Bot-instrument fit matrix — avg_R by bot × instrument locked | SuperTrend emerging pattern: BTCUSDm and XAUUSDm clearly positive (n=9–13 each). Marginal pairs need more data. Not yet locked. CAB cluster pattern emerging but confounded by directional market. |
| Gate 6 | Live deployment — one process, micro-lot, avg R >0.3 over 50 live trades | **Finish line.** |

---

## 7. What Comes Next — Week 6 Agenda

### One code change entering Week 6 (already applied)
- N_LAYERS_DEFAULT lowered from 3 to 2 in ghost_super/ghost_cache.py.
  This is the only code change. Everything else runs unchanged.

### Primary objective: Ghost 202 session gate confirmation
Week 5 produced only 6 Ghost 202 fills — not a confirmation window for
F1–F5, F7–F8. Week 6 is the continuation of the confirmation window.
If Gold enters a ranging regime and 202 runs at normal volume, the
combined W4+W5+W6 dataset will have sufficient n to confirm or refute
all five session/ATR/ADX/conviction gates.

**Confirmation triggers (evaluate end of Week 6):**
- LONDON win rate < 35% combined W4+W5+W6 (n≥170+) → implement LONDON
  suppression on probe arming.
- NY_CLOSE + H4_UP win rate < 32% combined (n≥140+) → implement
  direction gate on NY_CLOSE arming.
- ATR Q2 win rate < 30% combined (n≥195+) → implement ATR floor gate
  (arm only when M1 ATR > 1.8).
- Conviction 20–40 bucket < 35% combined (n≥360+) → implement
  conviction gate at 40+.
- ADX 20–25 bucket < 33% combined (n≥280+) → implement ADX 20–25
  suppression.

### Secondary objective: H9 CAB direction gate confirmation
Week 6 will reveal whether the 17.2pp BUY/SELL win rate gap (F9/F10)
holds in a potentially different market regime. Collection target: 50+
CAB trades with approximately balanced BUY/SELL split.

### 204 Ghost Cache — first real data expected
With N_LAYERS=2, the 2nd virtual layer is half the distance of the 3rd.
Probes that would not have triggered n=3 should now trigger n=2. Monitor
daily for GHOST_CACHE_FIRE in logs/sniper_hunter.log.

### SuperTrend — accumulate Gate 5 data
No changes. Continue accumulating per-symbol data. Target: 20+ trades
per symbol before locking the bot-instrument fit matrix.

---

## 8. Non-Negotiable Principles (locked)

- Position management gates can never block open trade management — only
  entry creation is gatable.
- R-multiples measure outcomes. They must not mechanically trigger exits.
  Market state drives exit decisions.
- The Knowledge Register informs but does not command — except Layer 2
  invalidation and Layer 3 portfolio exposure hard blocks, which require
  multi-week data validation before activation.
- One variable changes at a time. Evidence before action.
- Ghost Grid MAX_LEGS=4 is non-negotiable during demo. Evaluate
  statistically after 50+ grids.
- The hypothesis registry exists so no observation is lost. Observations
  are stored and tested, not acted on immediately.
- Statistical gates are implemented only after data confirms the pattern
  across sufficient combined sample (see triggers above). Week 4 findings
  are registered. Week 6 is the extended confirmation window.
- Bots inform each other; they do not command each other's exits.
  Cross-bot signals gate entry arming only.
- CAB architecture changes require H9 confirmation from Week 6 data
  before any implementation. The spec is parked at Review Stage.
