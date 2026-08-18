---

# Project Roadmap & Master Plan

**Last Updated:** Aug 16 2026
**Current Phase:** Phase 2 Demo Testing — Week 5 (Statistical Gate Evaluation)

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

---

## 2. Where We Are Now — Week 5 Status

**Account:** $10,000 start → ~$6,723 close of Week 4 (-32.8% overall 
drawdown)
**System health:** 5 threads alive, no crashes, no mechanical bugs.
**Data collected:** 293 matched Ghost 202 trades (entry conditions joined 
to MT5 outcomes). Full statistical analysis complete.

**Performance by component (Week 4, Aug 11–15):**
- Ghost Grid 202: 347 fills (all UP_PROBE SELL on XAUUSDm), net 
  approximately -$124. Primary drawdown driver.
- SuperTrend: 110 entries across 11 symbols, 58 closed, weighted avg R 
  +0.088. Second consecutive week of positive expectancy.
- CAB: 31 entries, 2 PROTECTOR fires (first PROTECTOR data in system 
  history). Zero HARVESTER, zero REAPER.
- Ghost Cache 204: 0 fires (architectural conflict with 202 reset — fix 
  applied Aug 16, first data expected Week 5).
- Ghost 201 shadow: 479 virtual fire events. Threshold of 80 exceeded but 
  ADX/conviction per-fire data not yet extractable from current logging.

**Two mechanical changes applied going into Week 5:**
1. Ghost 204 decouple — ghost_cache survives 202 fire, enabling 204 to 
   accumulate layers on deep probes.
2. CAB watcher log path fix — logs/cab_watcher.log now populated, 
   unblocking H5 SL tightness analysis.
Nothing else changed. Session filter and statistical gate decisions 
deferred pending Week 5 data.

---

## 3. Confirmed Findings Registry (Week 4 Statistical Analysis)

Eight findings confirmed from 293 matched trades (Ghost 202 entry 
conditions joined to MT5 outcomes). These are confirmed findings, not 
hypotheses. Implementation of each is deferred pending one additional 
week of data per the agreed data collection discipline.

| ID | Finding | Evidence | Deferred Until |
|----|---------|----------|----------------|
| F1 | ATR is the strongest single predictor. Q4 high-ATR (avg 2.87): win%=57.5%, +$1.11/trade. Q2 low-ATR (avg 1.55): win%=27.4%, -$1.18/trade. Gate candidate: only arm when M1 ATR > 1.8. | n=293 matched trades, quartile analysis | Week 5 data confirms |
| F2 | NY_OVERLAP + H4_DOWN is the only strongly positive-expectancy subset. n=31, win%=64.5%, +$1.55/trade, SL hit rate 32.3%. 20pp above breakeven threshold. | n=31, session×H4 cross-tab | Week 5 data confirms |
| F3 | Conviction > 50 predicts wins. Monotonic: <20 wins 42.9%, 20-30 wins 33.3%, 30-40 wins 31.6%, 40-50 wins 42.2%, 50-60 wins 50.0%. Gate candidate: conviction > 40. | n=293, conviction bucket analysis | Week 5 data confirms |
| F4 | ADX 20-25 is the dead zone. 109 trades at 32.1% win rate, -$0.69/trade — worst per-trade loss of any ADX bucket. ADX 30-35 profitable at 53.1%. Gate candidate: block ADX 20-25. | n=109 in dead zone bucket | Week 5 data confirms |
| F5 | LONDON session is structurally negative. LONDON+H4_DOWN: n=42, win%=28.6%, -$1.04/trade (worst combo). LONDON+H4_UP: n=17, win%=41.2%, -$0.39/trade. Both negative. | n=59 LONDON trades | Week 5 data confirms |
| F6 | H6 Cross-bot confirmed. ST LONG on XAUUSDm at Ghost 202 fire time: win%=32.4% vs 40.3% baseline, avg loss 3× worse. n=34. ST LONG = trend thesis active = mean-reversion counter-trade fights confirmed momentum. | n=34 overlap events | Actionable now via KR thesis read — implementation in Week 5 session |
| F7 | NY_CLOSE + H4_UP is second-worst combo. n=54, win%=27.8%, -$0.68/trade, 68.5% SL hit rate. 80% of NY_CLOSE fills fire into H4_UP. Original H2 hypothesis confirmed in correct form. | n=54 | Week 5 data confirms |
| F8 | Low ATR suppresses reversion amplitude. Q1 ATR quartile: 31.1% win rate, 66.2% SL hit rate, avg hold 6 min. Spread consumes meaningful fraction of SL at ATR < 1.2. | n=74 Q1 trades | Week 5 data confirms |

---

## 4. Hypothesis Registry — Final Statuses

| ID | Hypothesis | Final Status |
|----|-----------|--------------|
| H1 | 201 ADX gate improves win rate | UNRESOLVABLE from current logging. Virtual fill ADX not captured per-fire. FIRE_201_VIRTUAL logging fires on every loop tick (~40×/probe), not once per trigger. Superseded by F3 and F4 which show ADX and conviction predictiveness on live 202 trades. |
| H2 | DOWN_PROBE fires into H4 uptrends | REVISED. Original framing not confirmed — zero DOWN_PROBE events in Week 4 (Gold moved differently). Real finding: NY_CLOSE 80% fills into H4_UP, losing at 27.8%. Confirmed as F7. Direction + session is the correct gate. |
| H3 | 202 outcome in ADX<20 is random walk | PARTIALLY CONFIRMED, REVISED. ADX level alone in the 20-25 range is near-random-walk (32.1% win). But conviction score IS predictive (monotonic relationship confirmed). Both dimensions needed. Superseded by F3 and F4. |
| H4 | KR M15 regime mislabels H4 trends as RANGING | CONFIRMED. 98.5% RANGING label regardless of H4 direction. MarketPulseEngine not instantiated in unified_runner.py — all KR Layer 0 data returns None. Bots run on hardcoded fallbacks. Regime classifier is blind to H4 structure. |
| H5 | CAB 2.5×ATR SL inside H4 noise band | NOW EVALUABLE. CAB watcher log path fixed Aug 16. Week 5 will produce first clean cab_watcher.log data for SL distance analysis. |
| H6 | SuperTrend RANGING predicts 202 success | CONFIRMED IN STRONGER FORM. ST directional position (not regime label) predicts 202 outcome. ST LONG opposing Ghost SELL: 8pp win rate drop, 3× worse P&L/trade. n=34. Actionable via KR thesis registry read. |
| H7 | Ghost Grid ADX predicts CAB hold duration | STILL BLOCKED. Insufficient PROTECTOR data (2 fires vs 30 needed). |
| H8 | Equity trajectory | Week 4 close ~$6,723. Combined weekly loss ~$1,067 (V1 -$406 + estimated CAB drag). Ghost 202 London+NY_CLOSE primary driver. SuperTrend positive two consecutive weeks. |

---

## 5. Decision Gates — Current Status

| Gate | Description | Status |
|------|-------------|--------|
| Gate 1 | Unified runner stable, magic isolation clean | **PASSED** |
| Gate 2 | 204 vs 202 avg_R — 30+ fills each | In progress. 204: 1 fill total (decouple fix applied Aug 16 — first real data Week 5). 202: 663 fills. Not yet evaluable on R-multiple basis. |
| Gate 3 | Individual conviction: ST avg R>0, CAB false-cut <30%, Ghost stop rate <20% | In progress. ST passing (avg R +0.088, two consecutive positive weeks). Ghost failing but statistical cause identified (session/ATR/direction gates pending). CAB: insufficient REAPER data (2 PROTECTOR fires, 0 REAPER). |
| Gate 4 | Regime complementarity confirmed — overlap <15%, combined drawdown lower than individual | Not yet evaluable. |
| Gate 5 | Bot-instrument fit matrix — avg_R by bot × instrument locked | SuperTrend emerging pattern: XAUUSDm and XAGUSDm negative R two consecutive weeks. USOILm positive (n=9). Not yet locked — insufficient closed-trade sample. |
| Gate 6 | Live deployment — one process, micro-lot, avg R >0.3 over 50 live trades | **Finish line.** |

---

## 6. What Comes Next — Week 5 Agenda

### Mechanical changes already applied (no further action needed)
- Ghost 204 decouple: ghost_cache survives 202 trigger. Monitor for 
  first 204 fires in Week 5 logs.
- CAB watcher log: logs/cab_watcher.log now active. Run H5 analysis 
  at end of Week 5.

### Pending one more week of session data before implementation
All eight confirmed findings (F1–F8) require Week 5 confirmation before 
any gate is added to entry logic. The data collection discipline holds: 
one more week of session-labelled trades at the same conditions validates 
that Week 4 patterns are structural, not a single-week artifact.

**End of Week 5 decision triggers:**
- If LONDON win rate stays below 35% across both Week 4 and Week 5 
  combined (n=118+): implement LONDON session suppression on probe arming.
- If NY_CLOSE + H4_UP win rate stays below 32% (n=108+): implement 
  directional gate on NY_CLOSE arming (block when H4=UP).
- If ATR Q2 win rate stays below 30% (n=146+): implement ATR floor gate 
  (arm only when M1 ATR > 1.8).
- If conviction 20-40 bucket stays below 35% (n=272+): implement 
  conviction gate at 40+.

### F6 — H6 Cross-bot gate (actionable now, no session data needed)
When ST holds a confirmed LONG thesis on XAUUSDm in the KR, block 
Ghost 202 UP_PROBE arming. Implementation: single KR thesis read in 
ghost_hunter_thread before arming. Does not affect 202 entry logic, 
only arming condition. Does not require additional data collection — 
n=34 opposing events already sufficient with 8pp win rate drop confirmed.
This is the only Week 5 implementation candidate that does not require 
waiting for session data.

### H5 — CAB SL tightness (evaluate end of Week 5)
With cab_watcher.log now active, Week 5 will produce the first 
extractable SL distance data. Run pip-distance-vs-ATR analysis from 
MT5 history at end of Week 5. If median SL hit distance < 1.5×ATR 
across CAB losses, H5 confirmed and SL widening enters the agenda.

---

## 7. Non-Negotiable Principles (locked)

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
- Session filtering and statistical gates are implemented only after two 
  consecutive weeks of data confirm the same pattern. Week 4 findings 
  are registered. Week 5 is the confirmation window.
- Bots inform each other; they do not command each other's exits. 
  Cross-bot signals gate entry arming only.
