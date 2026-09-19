---

# Project Roadmap & Master Plan

**Last Updated:** Sep 19 2026
**Current Phase:** Phase 2 Demo Testing — Week 10 (NY_OVERLAP Gate + USTECm Disable)

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
| Week 6 | Aug 25–29 | $6,867.54 | -$109.96 | Ghost 202 240 fills at 40.0% WR. F15 gate pre-approved from H4 direction analysis. H9 refuted. |
| Week 7 | Sep 1–5 | $6,803.71 | +$35.95 | CAB outlier week +$85.50 (27.1% WR). ST streak ended -$29.56 (XAGUSDm drag). Ghost -$24.68. H4 direction signal INVERTED → B1b DEFERRED. Session dimension registered as H22. |
| Week 8 | Sep 8–12 | $6,504.41 | -$166.05 | Data collection week. H21 M5 logging active. Audit supplements filed Sep 9. Two-month retrospective completed. |
| Week 9 | Sep 15–19 | $6,563.54 | +$13.58 | ST best week (+$95.36). Ghost silent Sep 16–19 (F6 gate). H22 trigger confirmed. USTECm disabled. |

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
| F1 | ATR is the strongest single predictor. Q4 high-ATR: win%=57.5%, +$1.11/trade. Q2 low-ATR: win%=27.4%, -$1.18/trade. Gate candidate: arm only when M1 ATR > 1.8. | n=293 matched trades, quartile analysis | DEFERRED Sep 5 2026. W7 update: all-time H4=UP quartiles (n=267) — best bucket Q2 (1.33–1.74) reaches only +$0.01/tr. ATR alone cannot create positive expectancy in H4=UP population. W7 H4 inversion must be understood before secondary gating. Trigger: W8+W9 H4=UP WR > 42% and avg > $0.00/tr before threshold derivation. |
| F2 | NY_OVERLAP + H4_DOWN is the only strongly positive-expectancy subset. n=31, win%=64.5%, +$1.55/trade. | n=31, session×H4 cross-tab | RETIRED — REGIME ARTIFACT. W6 ranging week: NY_OVERLAP+H4_DOWN = 21.7% WR (was 64.5% in W4). Completely inverted. Do not implement. |
| F3 | Conviction > 50 predicts wins. Monotonic relationship confirmed. Gate candidate: conviction > 40. | n=293, conviction bucket analysis | PARTIALLY VALID — non-monotonic in W6. Conv>50 = 52.1% WR valid signal. Conv 40-50 = worst bucket (-$1.24/trade). Gate threshold revised to >50. Deferred to Phase C pending n≥80 in Conv>50 bucket. |
| F4 | ADX 20-25 is the dead zone. n=109, 32.1% win rate, -$0.69/trade. Gate candidate: block ADX 20-25. | n=109 in dead zone bucket | RETIRED — REGIME ARTIFACT. ADX 20-25 was WORST in W4 (32.1% WR), BEST in W6 (41.9% WR). Inverted. ADX is regime-sensitive. Gate permanently retired. |
| F5 | LONDON session is structurally negative. Both H4 directions lose. | n=59 LONDON trades | IMPLEMENTED — CAB Sep 1 2026. Ghost sequenced Week 9. Cross-system confirmation from 3 independent CAB systems cleared threshold. |
| F6 | ST LONG on XAUUSDm at Ghost 202 fire time: 32.4% win rate vs 40.3% baseline, 3× worse avg P&L. | n=34 overlap events | IMPLEMENTED Aug 16. Gate wired. Logs GHOST_ARM_BLOCKED_ST_LONG. |
| F7 | NY_CLOSE + H4_UP second-worst combo. n=54, 27.8% win rate, -$0.68/trade. 80% of NY_CLOSE fills fire into H4_UP. | n=54 | RETIRED — REGIME ARTIFACT. NY_CLOSE+H4_UP was 27.8% WR in W4, 41.2% WR in W6. Inverted. Retired. |
| F8 | Low ATR (Q1) produces 66.2% SL hit rate, avg hold 6 min. | n=74 Q1 trades | CONFIRMED BOTH WEEKS (mechanically grounded). Q1 ATR = 66.2% loss rate W4, 58.6% W6. Held directionally. Not regime-dependent — SL geometry is tight when ATR is low regardless of regime. Theoretical basis for ATR floor gate (F1 implementation). |

F15 | Ghost DOWN_PROBE+H4=DOWN gate. Implemented Sep 1. W7 outcome: 0 fires — DOWN_PROBE armed once in 832 all-time events. Gate is structurally correct but effectively inactive under current bullish market conditions. Not a current loss-reduction gate. | IMPLEMENTED Sep 1; ZERO FIRES W7; monitoring | Logs GHOST_ARM_BLOCKED_H4_DOWN.

**Why F1–F5, F7–F8 were pending:** Week 5 produced only 6 Ghost 202
fills due to regime suppression during a trending Gold week. Week 6
(240 fills) provided the ranging confirmation window. All findings
have now been evaluated against W6 data — see status updates above.

### CAB Findings (from Week 4+5 analysis, n=130)

| ID | Finding | Evidence | Status |
|----|---------|----------|--------|
| F9 | CAB SELL trades systematically underperform BUY trades in trending conditions. BUY: 45.2% win rate, avg_R +0.104. SELL: 27.9% win rate, avg_R -0.087. 17.2pp gap. | n=130, direction split across all symbols | REFUTED — regime-specific. Gap narrowed from 17.2pp to 7.5pp in ranging W6. H9 archived. |
| F10 | SELL underperformance concentrated in trending assets. XAUUSDm SELL: 25% WR. USOILm SELL: 0% WR. GBPUSDm SELL: 0% WR. All trended bullish in W4+W5. | n=130, direction×symbol cross-tab | REFUTED — same root cause as F9. |
| F11 | CAB losses exit at median exactly 1 H4 bar (4h) hold time. 59% of losses close at the next H4 bar via OSI. 97.6% of losses close before full 2.5×ATR SL. | n=83 losses, hold time distribution | CONFIRMED. OSI is the primary exit mechanism for CAB losers. Broker SL is not the problem. |
| F12 | CAB positive symbol cluster (BTCUSDm, ETHUSDm, USTECm): 59.4% win rate, +$91.18 combined. Negative cluster (GBPUSDm, XAGUSDm, EURGBPm, USOILm): 22.2% win rate, -$74.75 combined. | n=32 positive, n=54 negative | REGISTERED. Gate 5 data. Cluster difference is large but directional market conditions confound the sample. |

### SuperTrend Findings (emerging from W4+W5)

| ID | Finding | Evidence | Status |
|----|---------|----------|--------|
| F13 | SuperTrend has confirmed positive expectancy across four consecutive weeks. W3: +$119, W4: +$55, W5: +$277, W6: +$11. Win rate stable at 35–53%. | n=162 W3-W6 closed trades | CONFIRMED. Four-week consistency qualifies for Gate 3 ST criterion. |
| F14 | Bot-instrument fit matrix (early, n=9–20 per symbol): BTCUSDm (+$5.87/tr, 84.6% WR), XAUUSDm (+$22.20/tr, 88.9% WR), XAGUSDm (+$4.46/tr, 45.5% WR) are positive. EURGBPm (-$0.20/tr, 18.2% WR), USDJPYm (-$0.33/tr, 33.3% WR), USOILm (-$0.47/tr, 46.2% WR) are marginal negative. | n=103 W4+W5 by symbol | REGISTERED. Insufficient n per symbol for Gate 5 lock. Continue accumulating. |
| F16 | USTECm SuperTrend three consecutive negative weeks (W6 16.7% WR, W8 mixed negative, W9 28.6% WR n=7). Disable trigger met. | W6/W8/W9 data | IMPLEMENTED W10 — removed from config.json symbols. |

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
| H9 | CAB H4 directional bias gate improves win rate | REFUTED Aug 30 2026. W6 ranging week gap = 7.5pp (was 17.2pp). Effect is regime-specific. No gate. Archived. |
| H13 | H1 structural breach as faster CAB exit | INVALIDATED Aug 31 2026. cab_multi_pair H1_STRUCT_BREACH is a trailing SL label, not an active exit signal. Architecturally incomparable to cab_super's OSI. Archived. |
| H14 | H4 EMA50 bias filter for CAB entries — block bearish inversions when price > H4 EMA50, block bullish inversions when price < H4 EMA50. Source: standalone cab strat_inversion.py (confirmed in code). Would have suppressed W4+W5 SELL trades in Gold uptrend. | REGISTERED | Log EMA50 at entry for 2 weeks before any gate evaluation. |
| H15 | Stagnation decay: if CAB trade open 24h+ with R<0.5, close regardless of regime. Source: cab_multi_pair (n=4, 4.6% of exits). | CLOSED Sep 5 2026 | 0.9% of W6+W7 CAB losses open 24h+ at R<0.5 (1 of 115). Far below 30% threshold. No pattern. |
| H16 | Rollover gate 22:00-23:59 UTC for CAB entries. Source: session quality degradation consistent across 3 systems at session close. | CLOSED Sep 5 2026 | 0 CAB entries at 22:00-23:59 UTC across W6+W7. Gate not needed. |
| **H22** | Ghost NY session drag hypothesis. W7 Ghost P&L by session: ASIAN +$0.36/tr, LONDON +$0.09/tr, NY_CLOSE -$0.98/tr, NY_OVERLAP -$2.32/tr. Directionally consistent with retired F2/F7 (NY problematic in W4). Session tags are not regime-conditional — potentially more stable than H4 direction as a predictor. | ✅ IMPLEMENTED W10 — gate blocks probe arming 12:00–15:59 UTC. Logs GHOST_ARM_BLOCKED_SESSION. Test T21 added, 21/21 passing. |
| H17 | Intra-ASIAN time-of-day effect: 02:00-04:00 UTC better than 00:00-01:00 UTC within Ghost ASIAN session. | REGISTERED — thin sample | Accumulate across multiple weeks before evaluation. |
| H18 | Early R-velocity as Ghost loss predictor: positions going negative within 30 minutes have elevated loss rate. KR already computes r_velocity for registered theses. | REGISTERED — not yet logged per fill | Add 30-minute outcome checkpoint to sniper audit log before evaluation. |

---

### Audit Supplement Findings — Sep 9 2026 (CONTROL_SESSION_AUDIT_SUPPLEMENT_SEP9.md)

These findings emerged from the independent second-pass audit (Buffy/Codebuff). They
are verified from code and data and must be resolved before any Phase B gate is wired.

| ID | Finding | Status | Evidence | Action Required |
|----|---------|--------|----------|-----------------|
| F-A1 | Adaptive ADX gate is likely INERT — max ADX at fill=39.43, max conviction=59.75 across 30 days. Both sit just under the static thresholds (40/60), indicating read_adaptive_thresholds_hunter() is returning hardcoded defaults (rev_adx_block=40.0, is_adaptive=0), not the calibrated P70 values. The self-loosening paradox (Ambiguity D) is theoretical until verified. | VERIFICATION REQUIRED | 30-day log_extract: adx_at_fill avg=19.26, max=39.43; conviction max=59.75. Structurally consistent with static gates. | Check is_adaptive + rev_adx_block in adaptive_thresholds_live.csv at next log extraction. If is_adaptive=0, Ambiguity D is non-operational. |
| F-A2 | h4_direction_at_arm column in ORDER_FILL_V51 rows contains FILL-TIME H4 direction, not arm-time. _get_h4_direction() is called inside send_order() at trigger time and stored in a column named h4_direction_at_arm. True arm-time H4 exists only on ARMED rows, which are not joined to outcomes. The W6/W7 H4 cohort numbers (basis for B1b trigger) were measured at fill time. The B1b gate fires at arm time. These are different points in time — an H4 bar can close mid-probe. | CRITICAL — affects B1b trigger | Code-verified: send_order() calls _get_h4_direction() at lines ~539 and ~615. | Recompute W6/W7 H4 cohorts from ARMED rows joined to fills by time proximity. Do not wire B1b at W9 until arm-time cohort is computed and compared to fill-time numbers. |
| F-A3 | Three session definitions coexist with different hour boundaries. ghost_sniper.get_session() (used in audit CSV): ASIAN 21-8, LONDON 8-12, NY_OVERLAP 12-16, NY_CLOSE 16-21. MPE KR field: ASIAN 0-6, LONDON 7-12, NY_OVERLAP 13-16, NY_CLOSE 17-20, OFF_HOURS 21-23. RB002 research (A016/A018 permutation tests): ASIAN 0-7, LONDON 7-12, NY_OVERLAP 12-17, NY_CLOSE 17-0. H22's evidence uses get_session() boundaries. The permutation tests that provide H22's backbone used RB002 boundaries. A gate wired with one set cannot claim validation from tests run on another. | MUST RESOLVE BEFORE H22 GATE | Code-verified: three independent definitions in three files. | Standardise to get_session() as the single definition. Document it in H22. Re-run A016/A018-style permutation under get_session() hours before H22 gate is designed. |
| F-A4 | BE-lock threshold was raised from 0.5R to 1.0R (sniper_watcher.py BE_LOCK_R=1.0) without re-measuring against clean data. The n=2,458 W1 cohort (94.4% WR after +0.5R, 41.5% died before it) was measured at BE_LOCK_R=0.5 with SL=0.2×ATR. Both parameters changed. No equivalent measurement exists at 1.0R with SL=0.35×ATR. This is the largest unvalidated parameter change in the system. | OPEN QUESTION — highest-value parameter | Code-verified: BE_LOCK_R = 1.0 in sniper_watcher.py line 151. W1 dataset is the only relevant historical measurement and it used different parameters. | Consider a 2–3 week V2 split test: 0.5R vs 1.0R BE-lock on parallel accounts. If V2 is not available, at minimum tag this as a priority re-analysis item when the 2-month retrospective is run end of W8. |
| F-A5 | Magic 204 does not share 202's trigger-time gates. The MDP states "204 fires under the same conditions as 202." This is incorrect. 204 fires from the GhostCache update loop before the trigger check, without spread guard, without fresh brain state read, and using context from arming time. It is architecturally different from 202. | DOCUMENTATION ERROR — no code defect | Code-verified: GhostCache.update() in ghost_hunter_thread runs before the trigger block. No spread gate, no gate_202 check at 204 fire time. | Correct all documentation references that describe 204 as sharing 202's conditions. Note: this is a doc fix only — 204's behavior is by design. |
| F-A6 | F6 "$85 drag avoided in W7" is a single-week estimate taken on Ghost's worst days (Sep 4-5). On those same days, V2 (without F6) earned +$63.68. Calling F6 "the sole effective Ghost drag-reducer" is overstated. F6 is mechanistically correct (n=34, 8pp WR drop) but the W7 counterfactual partially contradicts the drag estimate. | OVERSTATED — reduce confidence | Single-week measurement. V2 counterfactual runs opposite sign. | Replace "F6 is the sole effective drag-reducer" language in all docs with: "F6 is mechanistically validated (n=34, 8pp WR drop) but single-week drag estimates are unreliable. Multi-week series required before quantifying drag reduction." |

**Strategic context — two paths forward:**
Phase B (current): hard filters. Ceiling is approximately F15+ATR at 60
trades/week, +$0.56/trade. Reaches this in 2-3 weeks if W7 ATR data confirms.
Phase C (next): adaptive intelligence. Entry quality score replaces binary
gates with continuous regime-aware scoring. Entry quality score and Market
Exit Score use the same KR infrastructure already built. Phase C is the path
past the hard filter ceiling and the mechanism for building the BUY side
(DOWN_PROBE) with symmetric logic.
The two paths are sequential, not competing. |

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
| Gate 2 | 204 vs 202 avg_R — 30+ fills each | In progress. 204: 3 all-time fires (W3 +$1.35, W6 +$1.15, W7 -$2.72), WR 66.7%, cumulative -$0.22. ~1 fire/week pace → Gate 2 earliest W11-12. 202: W7 produced 168 closed fills — accumulating. |
| Gate 3 | Individual conviction: ST avg R>0, CAB false-cut <30%, Ghost stop rate <20% | **SuperTrend: PASSED, monitoring** (streak of 4 ended W7 with -$29.56; one negative week is not a signal). CAB: neutral — H9 refuted, H14 EMA50 logging pending. Ghost: pending. Pass criterion (Sep 1 2026): 100+ post-Phase-B1b fills (UP_PROBE+H4=UP only) with avg P&L > $0.00/trade. NOTE: B1b deferral (W7 H4 inversion) delays the post-B1b population — criterion re-baselines on W8+W9 H4 direction data; H22 session filter may redefine the filtered population before this gate is evaluated. |
| Gate 4 | Regime complementarity confirmed — overlap <15%, combined drawdown lower than individual | Week 5 demonstrates this working as designed: trending week → ST profitable, Ghost suppressed, system net positive. Formal evaluation requires a ranging week comparison. |
| Gate 5 | Bot-instrument fit matrix — avg_R by bot × instrument locked | SuperTrend emerging pattern: BTCUSDm and XAUUSDm clearly positive (n=9–13 each). Marginal pairs need more data. Not yet locked. CAB cluster pattern emerging but confounded by directional market. |
| Gate 6 | Live deployment — one process, micro-lot, avg R >0.3 over 50 live trades | **Finish line.** |

---

## 7. What Comes Next — Week 8 Agenda (Sep 8–12 2026)

One code change enters Week 8 before session start: H21 M5 logging in
cab_watcher.py. No gate logic. Pure data collection.

Phase B gates are paused:
- B1b (UP_PROBE gate when H4=DOWN): deferred Sep 5. H4 direction
  inverted W6→W7. New trigger requires two consecutive weeks showing
  consistent directionality.
- ATR floor gate: deferred. Depends on stable H4 population definition
  before threshold derivation.
- Ghost NY session gate (H22): newly registered. Two-week observation
  minimum before gate design.

All bots run unchanged from Week 7 end configuration. F5 and F15
remain in place. No new gates.

End-of-week W8 evaluation targets:
1. H4 direction re-check (primary B1b re-evaluation input)
2. H22 session pattern (second data point)
3. Audit CSV unified-mode write path verification
4. H21 M5 logging line count confirmation

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
- CAB architecture changes require multi-regime data confirmation.
  H9 was refuted (Aug 30 2026). CAB direction bias (H14 EMA50
  filter) requires 2 weeks of logged EMA50 data before evaluation.
  No CAB entry-filter changes until H14 data is available.

---

## 9. System Architecture Vision — Established Aug 31 2026

### Core Philosophy

The system is a regime-conditional strategy portfolio, not a fixed
multi-bot ensemble. Each module activates under statistically
validated conditions and is silent outside those conditions.
No module is expected to be profitable in all market states.
The system's edge is coverage across regime states with each
module active only in its validated window.

Modules are added when the data identifies an uncovered regime
opportunity. Modules are retired or locked when their conditions
become structurally unfavorable across multiple observed regimes.
New modules follow the same statistical validation pipeline as
the founding modules — shadow mode first, evidence threshold
before live capital, one at a time.

### Current Module Windows (as of Aug 31 2026)

SuperTrend: TRENDING markets, M30, ADX>55.
Ghost 202 SELL: RANGING/TRENDING_DOWN, M1 probe, H4=UP (F15 gate),
  ATR>floor (B1 gate deferred — W7 H4 inversion), UP_PROBE retrace
  only. Session dimension (H22) under observation — NY sessions
  were -$65.28 of W7 loss; ASIAN/LONDON +$33.50.
Ghost BUY (DOWN_PROBE): TRENDING_UP exhaustion, M1 probe, H4=DOWN.
  Monitoring only — Week 11+ evaluation.
CAB: H4 exhaustion/reversal, H4 inversion entry, EMA50 aligned
  (H14 pending), London Open blocked (F5 gate).

### Timeframe Architecture

M1: Ghost probe detection and execution.
M5: RESEARCH — logging at CAB H4 inversion entries from Week 8.
    Potential: CAB entry quality gate, Ghost pre-arming signal,
    new dedicated module in M5-H4 cross-timeframe window (H21).
M15: SuperTrend regime engine, ATR buffer, MarketPulseEngine.
M30: SuperTrend entry signal, K-Means optimal factor.
H1: Structural breach reference — research only.
H4: CAB entry signal, regime classification, MarketPulseEngine,
    H4 direction gate (F15; B1b deferred pending W8+W9 H4 data).

The M5 timeframe is the identified missing link between H4
structural signals and M1 execution. Data collection begins
Week 8 alongside existing bot operations.

### Candidate Modules in Research Pipeline

H19 — Trend Exhaustion Reversal (M4): H4-timeframe entry during
TRENDING_DOWN+H4_UP window. Earlier entry than CAB with structural
SL. Differentiated from Ghost by H4 timeframe not M1.
Data required: 50+ comparable events logged.

H20 — London Open Range-Break Fade (M5): Active only during
07:00-10:00 UTC when all current modules are silent. Fade the
Asian range break. No code — pure data observation for 4+ weeks.

H21 — M5 structure at H4 inversion: four M5 fields logged at
every CAB entry from Week 8. If predictive, enables three
applications: CAB quality gate, Ghost pre-arming, new module.

### Two-Month Retrospective (Target: Sep 12 2026)

Week 8 marks two months since live trading began (Aug 1 2026).
A retrospective analysis is scheduled for end-of-W8. Scope:
- Cumulative P&L across all four systems (Ghost 202, Ghost 204, SuperTrend, CAB)
- Gate performance scorecard: which gates improved expectancy, which were neutral
- Parameter sensitivity review: which Tier 1 changes had measurable impact
- Audit supplement resolution: F-A1 through F-A6 status at end of W8
- Phase B readiness: B1b arm-time H4 recompute, H22 session standardisation, ATR gate

The retrospective should produce a written summary for the next
session handoff. The V2 split (if running) should be included
in the comparison.

### The Module Addition Protocol

A new module is added to the live system only when:
1. 100+ shadow fills with positive avg P&L in its specific
   activation window
2. Tested across at least two distinct market regimes
3. Own magic number assigned
4. Own watcher or extended watcher confirmed functional
5. All existing modules stable (no active Phase B gating on
   any existing module simultaneously)
6. One new module in shadow validation at a time
