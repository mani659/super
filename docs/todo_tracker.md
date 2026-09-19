---

# Algo Trading — Development Tracker

**Status:** Phase 2 Demo Testing — Week 10 (NY_OVERLAP Gate + USTECm Disable)
**Version:** v22
**Last Updated:** Sep 19 2026

## Completed Tasks

### Tier 0 (Mechanical Bugs) — All Resolved
- [x] Ghost Grid LEG_TP_SET fires unconditionally. GridState resets on 
  72h staleness timeout.
- [x] CAB Multi-symbol Fix — PROTECTOR, HARVESTER, REAPER across all 
  symbols.
- [x] Ghost Cache (magic 204) wired into unified_runner.py.
- [x] KnowledgeRegister thread concurrency race condition eliminated.
- [x] Ghost Hunter send_order() return value captured.
- [x] CAB ticket loop bug fixed.
- [x] UnifiedFailover.mq5 expanded to all 11 symbols.
- [x] Circuit breaker blindspot closed.
- [x] Ghost Grid 10016 SL rejection eliminated (Option 2 SLTP anchor 
  from result.price).
- [x] CAB premature entry on restart fixed — state file persistence 
  + startup grace period. Test suite 18/18.
- [x] **Ghost 204 decouple (Aug 16 2026)**: ghost_cache = None removed 
  from the `if trigger:` block in ghost_sniper.py run_hunter(). 
  GhostCache now survives a 202 fire and continues tracking deeper 
  virtual layers on the same probe. Resets only when armed = None 
  (full probe cycle end). Root cause was: 202 fires at first retraction, 
  immediately resets cache, 204 never accumulates nth layer. Fix allows 
  both legs to coexist on the same probe. New test T18 added to 
  test_ghost_gateway_port.py verifying ghost_cache is non-None after 
  trigger fires.
- [x] **CAB watcher log path fix (Aug 16 2026)**: RotatingFileHandler 
  in cab_watcher.py updated from cab_production_v16.3.log (root) to 
  logs/cab_watcher.log. extract_bot_logs.py aligned to same path. 
  os.makedirs("logs", exist_ok=True) guard added. H5 SL tightness 
  analysis now unblocked — Week 5 will produce first extractable CAB 
  log data.
- [x] **MarketPulseEngine Fix (Phase A, Aug 26 2026)**: H4 staleness bug and NaN output fixed in `shared_intelligence.py`. Engine now fetches 150 bars and evaluates intra-bar continuously, feeding fresh valid data to the Knowledge Register.
- [x] Monitor 204 fires (outcome: zero fires, action taken: N_LAYERS lowered)
- [x] Confirm CAB log active (outcome: confirmed active)
- [x] H8 equity tracking (outcome: $6,977 close, +$386 week)
- [x] F6 implementation (outcome: implemented Aug 16, zero fires in W5)

### Tier 1 (Parameter Changes)
- [x] 201/202 SL widened from 0.20×ATR to 0.35×ATR.

### Tier 3 (Architecture)
- [x] Regime gate on probe arming (TRENDING_UP/DOWN/UNKNOWN blocked).
- [x] Global config switch — live bot/leg toggling without restart.
- [x] H4 context logging — h4_direction_at_arm and kr_regime_at_arm 
  in sniper_v51_live_audit.csv.
- [x] Leg 203 removed. SuperTrend owns all trend entries.

### Code Audit & Core Refinements
- [x] ST test suite 12/12 passing.
- [x] CAB retry storm bounded to 3 attempts per H4 bar.
- [x] CAB demo lot cap at 0.01.
- [x] ST regime engine upgraded from M1 to M15.
- [x] Magic isolation breach detail logging.
- [x] MQL5 EA ATR handle caching.
- [x] SuperTrend si_partial_close_min lowered to 0.55.

- [x] **Full V1 codebase audit completed (Aug 28 2026)**: Independent
  audit by Buffy (Codebuff AI) covering unified_runner.py, all three
  bot subsystems, shared infrastructure, and MQL5 failover EA.
  Findings reviewed and filtered by Claude. V1-scope action items
  applied this session. cab/, cab_multi_pair/, and V2 audit findings
  deferred to post-Week 6 performance review session.

- [x] **Dead code deleted (Aug 28 2026)**: core/risk_manager.py,
  core/news_filter.py, and core/performance_monitor.py permanently
  removed. All three were unreachable from any live bot thread and
  superseded by existing architecture (circuit breaker, KR Layer 3,
  extract_bot_logs.py workflow respectively).

- [x] **CAB Watcher version string corrected (Aug 28 2026)**:
  Log banner in cab_watcher.py run_brain() updated from "v16.3" to
  "v16.4-1" to match the actual deployed version including OSI.

### Week 3 Performance Findings (Aug 1–8 2026)
- [x] SuperTrend confirmed positive-expectancy: +$119.26, 73 trades, 
  41.1% win rate.
- [x] Ghost Grid 202 direction bias identified — all 316 fills SELL 
  into 130-point Gold uptrend. Root cause: M15 RANGING label during 
  H4 uptrend. Logging enhancement deployed.
- [x] CAB REAPER non-firing confirmed. H5 registered.

### Week 4 Statistical Analysis Complete (Aug 11–15 2026)
- [x] **293 Ghost 202 trades matched** (audit CSV joined to MT5 
  outcomes). Full session × H4 × ADX × ATR × conviction analysis run.
- [x] **H4 CONFIRMED**: 98.5% RANGING label regardless of H4 direction. 
  KR M15 classifier blind to H4 structure. MarketPulseEngine not 
  instantiated — all Layer 0 data returns None.
- [x] **H6 CONFIRMED**: ST LONG on XAUUSDm at Ghost 202 fire time 
  produces 32.4% win rate vs 40.3% baseline. n=34, 3× worse per-trade 
  P&L. Actionable via KR thesis read without additional data collection.
- [x] **H2 REVISED**: Original DOWN_PROBE-into-uptrend framing not 
  confirmed. Real pattern: NY_CLOSE 80% fills into H4_UP at 27.8% win 
  rate. Confirmed as finding F7.
- [x] **H3 REVISED**: ADX level in RANGING near-random-walk at 20-25 
  range confirmed. Conviction score IS predictive (monotonic across 
  five buckets). Superseded by F3 and F4.
- [x] **F1 registered**: ATR strongest predictor. Q4 high-ATR 57.5% 
  win, Q2 low-ATR 27.4% win. Gate candidate: M1 ATR > 1.8.
- [x] **F2 registered**: NY_OVERLAP + H4_DOWN only strongly positive 
  subset. n=31, 64.5% win, +$1.55/trade.
- [x] **F3 registered**: Conviction > 50 predicts wins. Monotonic 
  relationship confirmed. Gate candidate: conviction > 40.
- [x] **F4 registered**: ADX 20-25 dead zone. n=109, 32.1% win, 
  -$0.69/trade. Gate candidate: avoid ADX 20-25.
- [x] **F5 registered**: LONDON session structurally negative. Both 
  H4 directions lose. -$50.15 on 59 LONDON trades.
- [x] **F7 registered**: NY_CLOSE + H4_UP second-worst combo. n=54, 
  27.8% win, -$0.68/trade.
- [x] **F8 registered**: Low ATR (Q1) produces 66.2% SL hit rate, 
  avg hold 6 min. Spread consumes meaningful fraction of SL.

### Week 5 Performance & Analysis (Aug 18–22 2026)
- [x] **Week 5 equity close**: $6,977.50 (+$385.78 for the week,
  -30.2% inception drawdown). First positive week.
- [x] **SuperTrend**: 84 trades, 52.4% WR, +$277.31. Third consecutive
  positive week. Gate 3 ST criterion passed.
- [x] **CAB**: 92 trades, 35.9% WR, +$44.68. Net positive driven by
  outlier wins (XAGUSDm +$165, BTCUSDm +$38). Underlying pattern
  unchanged.
- [x] **Ghost 202**: 6 fills, 33.3% WR, -$8.24. Near-silence from
  regime gate correctly suppressing probe arming in trending Gold week.
  Correct system behavior confirmed.
- [x] **Ghost 204**: Zero fires. N_LAYERS_DEFAULT pre-agreed trigger met
  (zero fires after Day 5). Lowered to 2 entering Week 6.
- [x] **F6 gate**: Zero GHOST_ARM_BLOCKED_ST_LONG fires. Probable cause:
  regime gate blocked arming before F6 evaluation. Gate wiring confirmed
  in code review — not a broken wire.
- [x] **F9 registered**: CAB BUY 45.2% WR vs SELL 27.9% WR across
  130 trades. 17.2pp gap. Direction misalignment in trending conditions.
- [x] **F10 registered**: SELL underperformance concentrated on trending
  assets: XAUUSDm SELL 25% WR, USOILm SELL 0% WR, GBPUSDm SELL 0% WR.
- [x] **F11 confirmed**: CAB losses exit at median 4h (1 H4 bar). 59% via
  OSI. 97.6% before full SL. Exit mechanism working correctly.
- [x] **H5 revised**: SL tightness hypothesis superseded. OSI is the
  primary loss exit, not SL hits. Primary CAB problem is direction
  misalignment (F9/F10), not SL width.
- [x] **H9 registered**: CAB H4 directional gate hypothesis. If SELL WR
  stays below 35% and BUY WR above 40% in Week 6 (n≥50, non-trending
  Gold) → implement H4 direction gate in cab_entry.py for Week 7.
- [x] **CAB architecture spec reviewed**: External enhancement spec
  (cab_super_enhancement_spec.md, Aug 22) reviewed and parked.
  H1_STRUCT_BREACH claim found non-existent in code. Tri-vector framework
  rejected as unvalidated strategy expansion. H4 direction gate (H9) is
  the only actionable item, pending Week 6 confirmation.
- [x] **Ghost 202 session gate**: F1–F5, F7–F8 still PENDING —
  Week 5 had only 6 fills. Confirmation window extended to Week 6.
- [x] **SuperTrend bot-instrument fit matrix (F14)**: BTCUSDm, XAUUSDm,
  XAGUSDm positive. EURGBPm, USDJPYm, USOILm marginal negative.
  Insufficient n per symbol for Gate 5 lock — accumulate.
- [x] **N_LAYERS_DEFAULT lowered to 2** (Aug 22 2026) in
  ghost_super/ghost_cache.py. Only code change entering Week 6.

### Week 6 Performance & Analysis (Aug 25–29 2026)
- [x] **Week 6 equity close**: $6,867.54 (-$109.96 for the week, -31.3%
      inception drawdown). Ghost 202 primary loss driver (-$103.00).
- [x] **Ghost 202**: 240 fills, 40.0% WR, -$103.00. All fills are UP_PROBE
      (SELL reversals). Zero matched DOWN_PROBE fills in observation window.
      H4=DOWN fills = 180 of 240 raw (134 of 229 matched outcomes) at
      36.6% WR (matched), -$0.79/trade.
      H4=UP fills = 60 of 240 raw (95 of 229 matched outcomes) at
      48.4% WR (matched), +$0.27/trade. Note: 58.3% WR figure cited
      elsewhere is from raw unmatched audit CSV. 48.4% from confirmed
      closed fills is the authoritative number for gate design.
      11 fills unmatched — positions open at MT5 export time.
      10.1pp WR gap confirmed (48.4% vs 38.3% on matched fills) —
      F15 gate pre-approved and implemented.
- [x] **Ghost 204**: 1 fire (first ever). SELL, UP_PROBE, H4=DOWN, RANGING,
      conviction=70.2. Won $1.15. Gate 2 data collection started.
- [x] **SuperTrend**: 59 trades, 35.6% WR, +$10.92. Fourth consecutive
      positive week. Gate 3 ST confirmed.
- [x] **CAB**: 101 trades, 35.6% WR, +$229.78. BUY 39.6% WR vs SELL 32.1%
      WR — gap narrowed to 7.5pp in ranging week. H9 REFUTED.
- [x] **H9 REFUTED Aug 30 2026**: CAB SELL/BUY gap narrowed from 17.2pp
      (W4+W5 trending) to 7.5pp (W6 ranging). Effect is regime-specific.
      No direction gate implemented. Spec archived.
- [x] **W4 findings scorecard completed**: F2 and F7 fully inverted W4→W6
      (NY_OVERLAP+H4_DOWN: 64.5%→21.7% WR; NY_CLOSE+H4_UP: 27.8%→41.2%).
      F4 inverted (ADX 20-25 worst→best bucket). All three permanently retired.
      F1/F5/F8 held directionally. F15 confirmed as dominant predictor.
- [x] **Cross-CAB comparison completed**: 3 parallel CAB systems analyzed.
      H13 (H1_STRUCT_BREACH) invalidated — trailing SL label, not active signal.
      H14 (EMA50 bias filter) registered from standalone cab code.
      H15/H16 registered as computable hypotheses. London finding cross-confirmed.
- [x] **F15 IMPLEMENTED Sep 1 2026**: Ghost DOWN_PROBE blocked when H4=DOWN.
      unified_runner.py ghost_hunter_thread + ghost_sniper.py run_hunter().
      Logs GHOST_ARM_BLOCKED_H4_DOWN. Test T20 added, 20/20 passing.
- [x] **F5 IMPLEMENTED Sep 1 2026 (CAB)**: blocked_hours_utc extended to
      07-11 UTC in cab_entry.py. Cross-system evidence from 3 CAB systems
      cleared single-system n=170 threshold. Test T19 added, 19/19 passing.
- [x] **MPE confirmed operational**: ADX 140 distinct values, live regime labels
      in W6 audit CSV. Zero publish count was log-level routing, not a data failure.

---

## Week 7 Performance & Analysis (Sep 1–5 2026)
- [x] **Week 7 equity close**: $6,803.71 (+$35.95 for the week, -31.9%
      inception drawdown). Weekend gap on open: -$99.78 (CAB positions).
- [x] **Ghost 202**: 168 closed fills, 45.2% WR, -$24.68. 178 raw fills
      (165 matched to MT5 outcomes). Zero fills Sep 4–5 — F6 suppressed
      all arming (2,354 GHOST_ARM_BLOCKED_ST_LONG events) while ST held
      LONG on XAUUSDm. H4 direction signal INVERTED vs W6: H4=DOWN
      +$0.27/tr (was -$0.82), H4=UP -$0.72/tr (was +$0.18).
- [x] **H4 inversion → B1b DEFERRED**: B1b counterfactual would have
      hurt W7 by ~$27. New readiness criterion: H4=DOWN avg < -$0.50/tr
      AND H4=UP avg > +$0.10/tr in BOTH W8 AND W9. F15 block-count
      criterion retired — DOWN_PROBE armed once in 832 events; F15
      fired 0 times in W7 (dead code in practice).
- [x] **Session dimension registered (H22)**: ASIAN +$0.36/tr (n=85),
      LONDON +$0.09/tr (n=38), NY_CLOSE -$0.98/tr (n=24), NY_OVERLAP
      -$2.32/tr (n=18). NY sessions = -$65.28 of W7 Ghost loss;
      ASIAN+LONDON = +$33.50 profit. Analysis only — W8+W9 data
      required before any gate evaluation.
- [x] **SuperTrend**: 66 trades, 42.4% WR, -$29.56. Four-week positive
      streak ended. Primary drag: XAGUSDm -$48.75 (25% WR, n=8).
      USTECm recovered (80% WR, +$7.19, n=5) — disable trigger NOT met.
- [x] **CAB**: 48 trades, 27.1% WR, +$85.50. Outlier-driven: XAUUSDm
      +$79.39 (n=3), XAGUSDm +$34.10 (n=5). BUY 29.2% WR -$44.93 vs
      SELL 25.0% WR +$130.43 (outlier-dominated). F5 London gate held:
      0 CAB entries 07:00-11:59 UTC.
- [x] **Ghost 204**: 1 fire in W7 (-$2.72). 3 all-time fires
      (W3 +$1.35, W6 +$1.15, W7 -$2.72), WR=66.7%, cumulative -$0.22.
      Gate 2 requires 30 fires — accumulating at ~1/week, earliest
      completion W11-12.
- [x] **H15 CLOSED**: 1 of 115 W6+W7 CAB losses (0.9%) open 24h+ at
      R<0.5. Far below 30% threshold. No stagnation pattern.
- [x] **H16 CLOSED**: 0 CAB entries at 22:00-23:59 UTC across W6+W7.
      Rollover gate not needed.
- [x] **ATR gate DEFERRED**: All-time H4=UP quartiles (n=267) — best
      bucket Q2 (1.33–1.74) reaches only +$0.01/tr. ATR alone cannot
      create positive expectancy. Trigger: W8+W9 H4=UP WR > 42% and
      avg > $0.00/tr before threshold derivation.
- [x] **Magic 201 shadow pipeline CONFIRMED BROKEN**: 828 VIRTUAL_FILL
      events logged, zero audit CSV rows. is_shadow=True path in
      send_order() does not write to sniper_v51_live_audit.csv.
      Registered as code task under Deferred / Parked Items.
- [x] **Audit CSV unified-mode write path**: NOT yet confirmed. Sep 4–5
      produced zero Ghost fills (F6-blocked), so no rows would have been
      written regardless. MUST verify before W8 Ghost fires.

---

## Week 7 Active Tasks (Sep 1–5 2026)

### Code changes (applied before Week 7 start)
- [x] **F15 H4 direction gate**: IMPLEMENTED Aug 31 2026 in
  unified_runner.py ghost_hunter_thread and ghost_sniper.py
  run_hunter(). Blocks DOWN_PROBE arming when H4 structural direction
  is DOWN. Logs GHOST_ARM_BLOCKED_H4_DOWN. Test T20 added, 20/20 passing.
  Evidence: n=240, DOWN_PROBE+H4_DOWN 33.9% WR vs UP_PROBE+H4_UP 58.3% WR.
- [x] **F5 London Open gate**: IMPLEMENTED Aug 31 2026 in
  cab_super/cab_entry.py. blocked_hours_utc extended to (0..11) covering
  Asian (00-06) + London Open (07-11) UTC. Test T19 added, 19/19 passing.
  Cross-system evidence from 3 CAB variants cleared n=170 threshold.

### Daily monitoring
- [x] **F15 gate**: 0 fires in W7 (DOWN_PROBE dormant — 1 arm in 832 all-time).
      Gate is wired but dead code in practice. Falsified as B1b readiness signal.
- [x] **202 volume check**: 178 fills Sep 1–3 (~59/day, unchanged vs W6),
      0 fills Sep 4–5 (F6 suppressed all arming).
- [x] **F5 London gate**: 0 CAB entries 07:00-11:59 UTC. Gate held.
- [x] **204 fires**: 1 fire in W7 (Sep 2, -$2.72). 3 all-time.
- [x] **Thread health**: 5 threads alive, 1,632 heartbeats, 0 circuit breaker
      trips, 0 dead threads.
- [x] **USTECm ST trades**: 80% WR, +$7.19 (n=5) — disable trigger NOT met.

### End-of-week evaluations
- [x] **F15 effect**: 168 closed fills, 45.2% WR, -$24.68. H4=DOWN
      +$0.27/tr / H4=UP -$0.72/tr — signal INVERTED vs W6.
- [x] **ATR threshold derivation**: all-time H4=UP quartiles (n=267) — best
      bucket Q2 (1.33–1.74) = +$0.01/tr. No positive cohort. Gate DEFERRED.
- [x] **F5 London effectiveness**: 0 CAB fills 07-11 UTC in W7 MT5 export.
- [x] **H15**: CLOSED — 0.9% (1 of 115) W6+W7 losses open 24h+ at R<0.5.
- [x] **H16**: CLOSED — 0 CAB entries at 22:00-23:59 UTC across W6+W7.
- [x] **204 Gate 2**: 1 fire in W7 (-$2.72). 3 all-time, WR 66.7%, cum -$0.22.
- [x] **ST Gate 5**: fit matrix updated. XAGUSDm -$6.09/tr (n=8) strong
      drag; USTECm recovered (+$1.44/tr). Accumulating.
- [x] **GHOST_ARM_BLOCKED_H4_DOWN total count**: 0 — DOWN_PROBE dormant.
      Criterion retired; rely on H4 direction data instead.
- [x] **Phase B1b readiness (critical):** RESOLVED — B1b DEFERRED Sep 5.
      F15 fired 0 times in W7 (DOWN_PROBE dormant — 1 arm in 832 all-time).
      H4 direction signal inverted W6→W7 (DOWN +$0.27/tr vs UP -$0.72/tr).
      B1b would have hurt W7 by ~$27. New readiness criterion: H4=DOWN
      avg < -$0.50/tr AND H4=UP avg > +$0.10/tr in BOTH W8 AND W9.

---

## Sep 9 Completed Tasks — Audit Supplements Filed

### Level 2 Microstructure Assessment (Sep 9 2026)
- [x] **Cross-bot lagging indicator audit completed**: Independent second-pass
      audit (Buffy/Codebuff) assessed all four bots (CAB, SuperTrend, Ghost 202/204)
      against OBI/CVD microstructure architecture. Key finding: all bots use
      lagging indicators (RSI, ATR, ADX) for entries without order flow confirmation.
      Segregated into immediate fixes (F-A1 through F-A6) and longer-term micro
      architecture items.
- [x] **F-A1 registered**: Adaptive ADX gate likely INERT — max adx_at_fill=39.43
      and max conviction=59.75 across 30 days sit just under static thresholds
      (40/60). read_adaptive_thresholds_hunter() returns hardcoded defaults.
      is_adaptive flag and adaptive_thresholds_live.csv must be checked at next
      log extraction. Status: VERIFICATION REQUIRED.
- [x] **F-A2 registered (CRITICAL)**: h4_direction_at_arm column in ORDER_FILL_V51
      contains FILL-TIME H4 direction, not ARM-TIME. _get_h4_direction() is called
      inside send_order() at trigger time. True arm-time H4 exists only on ARMED
      rows (not joined to fills). B1b trigger thresholds were measured on fill-time
      H4 cohorts but B1b fires at arm time. W6/W7 H4 cohorts must be recomputed
      from ARMED rows joined to fills by time proximity before B1b can be wired.
- [x] **F-A3 registered**: Three session definitions coexist — ghost_sniper.get_session()
      (ASIAN 21-8, LONDON 8-12, NY_OVERLAP 12-16, NY_CLOSE 16-21), MPE KR field
      (ASIAN 0-6, LONDON 7-12, NY_OVERLAP 13-16, NY_CLOSE 17-20), RB002 research
      (ASIAN 0-7, LONDON 7-12, NY_OVERLAP 12-17, NY_CLOSE 17-0). H22 evidence uses
      get_session(); A016/A018 permutation tests used RB002 hours. MUST standardise
      to get_session() as single definition and re-run A016/A018 under those hours
      before H22 gate is designed.
- [x] **F-A4 registered**: BE-lock threshold raised from 0.5R to 1.0R
      (sniper_watcher.py BE_LOCK_R=1.0) without re-measuring against clean data.
      W1 n=2,458 measurement was at BE_LOCK_R=0.5 with SL=0.2×ATR; both parameters
      changed. No equivalent measurement exists at 1.0R with SL=0.35×ATR. Highest-value
      unvalidated parameter change in the system.
- [x] **F-A5 registered (doc fix only)**: Magic 204 does NOT share 202's trigger-time
      gates (spread guard, fresh brain state, 204 fires from GhostCache update loop
      before trigger check using arm-time context). MDP statement "204 fires under the
      same conditions as 202" is incorrect. Must correct all documentation references.
- [x] **F-A6 language reduced**: F6 "$85 drag avoided in W7" is single-week estimate
      on Ghost's worst days. V2 (without F6) earned +$63.68 on same days. Replace
      "sole effective Ghost drag-reducer" language with: "mechanistically validated
      (n=34, 8pp WR drop) but single-week drag estimates are unreliable. Multi-week
      series required before quantifying drag reduction."
- [x] **Audit findings filed in roadmap.md**: F-A1 through F-A6 added to Section 3
      hypotheses table with full status, evidence, and action required. H22 entry
      updated with F-A3 precondition. Cross-referenced from todo_tracker.md.

---
### Knowledge Register Wiring (High Priority)
- [x] **Fix 7: Lifecycle Cleanup**: Call `unregister_trade_thesis()` whenever a position is closed across ALL bots (CAB, ST, Ghost) to prevent unbounded memory growth and corrupted risk calculations.
- [x] **Fix 5: Wire Hard-Block Layers (2 & 3)**: Enforce invalidation and portfolio exposure limits. Inject `is_entry_invalidated()` and `check_portfolio_entry_allowed()` into the pre-entry logic for CAB, Ghost, and ST. Additionally, ensure all bots call `publish_invalidation()` when they locally identify a structural break (ST DEAD-state, CAB OSI, Ghost regime-arm-gate).
- [x] **Fix 4: Universal Thesis Registration**: Ensure Ghost Sniper and SuperTrend call `register_trade_thesis()` upon filling an order. (Currently CAB-only).
- [x] **Fix 6: Deduplicate Micro Degradation**: Decide between CAB's `TradeDegradationEngine.is_degrading()` and KR's `get_micro_degradation()`. Standardize on a single implementation and remove the dead code.
- [x] **Fix 1-3: Tech Debt & Tuning**: Fix cosmetic ATR comment in `ghost_sniper.py`, remove legacy kwargs from `run_bot.py`, and prepare for per-symbol weight tuning in `config.json`.

- [ ] **Gate 5 (Bot-Instrument Fit Matrix)**: Lock `avg_R` cross-tab by bot × instrument to finalize live pair deployment.
- [ ] **Gate 6 (Live Deployment)**: One unified process, micro-lot, avg R > 0.3 over 50 live trades.
- [ ] **Dynamic Lot Sizing (CAB)**: Implement dynamic lot sizing for the CAB bot. This will be made dynamic globally under the unified bot, with the only exception being the Ghost Grid (until logic validation is complete). Will apply in the next coding run.
- [ ] **Market Intelligence - Confluence Identification**: Add market environment intelligence logic to identify and leverage situations where both CAB and SuperTrend bots open trades in the same direction (e.g., both buy). This complementing direction indicates high market confluence and will be highly valuable in the long run.
- [ ] **Research/Discussion: Ghost Grid Risk Concentration**: Re-evaluate Legs 201 and 202 firing as a stacked block. Redesign to ensure true regime complementarity instead of doubling exposure on identical triggers.
- [ ] **Research/Discussion: Ghost BE-Lock Expectancy**: Review micro-lot scalping math; fixed spread costs currently consume profit targets before BE-lock mathematically engages.
- [ ] **Research/Discussion: Regime Disconnect (H2/H4 pending confirmation)**: Ghost Grid M15 probe arming and SuperTrend H4 regime reads disagreed during Week 3 — Gold classified as RANGING on M15 while making a 130-point H4 uptrend. Proposed fix: block DOWN_PROBE arming when H4 structural direction is UP, and UP_PROBE when H4 is DOWN. NOT implementable until H2 is confirmed from Week 4 h4_direction_at_arm data and H4 regime label accuracy is verified. Minimum evidence requirement: H2 confirmed at >30% DOWN_PROBE-into-H4-UP rate across Week 4 fills.
- [ ] **Research/Discussion: SuperTrend Continuation Signals**: Evaluate the risk of bypassing the `INCUBATING -> CONFIRMED` state machine for mid-trend entries, which strips SI protections.
- [ ] **Research/Discussion: Model Divergence vs. Exposure Limits**: Evaluate the workflow impact, pros, and cons of adding a statistical meta-model tie-breaker for conflicting positions (e.g., CAB sells on H4, SuperTrend buys on M15). Must reconcile with the current Knowledge Register design (Layers 2/3), which treats ST-vs-Ghost disagreement as legitimate and manages it via correlation-bucket exposure ceilings rather than a hard directional veto. Keep as an idea for detailed statistical discussion before considering any implementation.
- [ ] **Ghost probe logic unification (Phase C refactor)**: The probe
  arming/tracking/firing logic is duplicated between
  ghost_super/ghost_sniper.py run_hunter() (standalone) and
  unified_runner.py ghost_hunter_thread() (live). Any fix to one
  must be manually replicated to the other — the 204 decouple fix
  and ghost_cache = None divergence confirmed this is a real
  maintenance hazard. Refactor target: extract shared probe class.
  NOT touching during active data collection. Schedule for Phase C
  or between Phase B and C when no gates are mid-implementation.

- [ ] **MarketPulseEngine silent fallback monitoring (ongoing)**:
  If MarketPulseEngine errors on any symbol, get_market_state()
  returns None and all three bots silently fall back to hardcoded
  regime/ADX/ATR defaults with no loud alert. Add a watchdog check
  to the main thread heartbeat loop: if KR snapshot for XAUUSDm H4
  is None or older than 15 minutes, log WARNING at ERROR level so
  it surfaces in the heartbeat line. Low implementation cost, high
  diagnostic value. Schedule alongside next agent coding session.

- [ ] **204 fire bs/gates staleness (audit finding Aug 28 2026)**:
  When GhostCache fires magic 204 during the probe tracking phase,
  the brain state (bs) and gate evaluation (gates) passed to
  send_order() are from the arming tick — potentially minutes stale.
  Gate evaluation at the moment of 204 fire would be more accurate.
  Deliberately skipped during active data collection (Week 6+) to
  avoid altering 204 gate behavior mid-dataset. Address during Phase
  C probe logic unification refactor.

- [ ] **ghost_hunter_thread switches scope fragility (audit finding
  Aug 28 2026)**: In unified_runner.py ghost_hunter_thread(), the
  switches variable is assigned inside the `if armed is None:` block.
  In the `else:` (tracking) branch, switches references the value
  from the previous arming iteration. Practically harmless because
  armed always initialises as None, but fragile by design. Fix by
  moving load_switches() call to the top of the while loop so it
  is re-read every tick regardless of armed state. Deliberately
  skipped during active data collection. Address during Phase C
  probe logic unification refactor alongside the bs/gates staleness
  fix above.

- [ ] **Architectural Fix for 10016 SL Rejections (RESOLVED — Aug 8 2026)**: Option 2 (Phase 2 Dynamic SL) implemented in `ghost_super/ghost_sniper.py` `send_order()`. SL/TP anchor in Phase 2 now computed from `result.price` (actual fill price) rather than pre-order tick price. Eliminates geometric mismatch that caused 10016 rejections and downstream naked trade kill-switch terminations. Single-Phase entry (Option 1) was rejected because it would cause missed entries on 10016 rejection of the bundled order — worse outcome on a strategy that fires at precise probe retraction moments.

## Week 8 Active Tasks (Sep 8–12 2026) — COMPLETED

### W8 Completed (Sep 8–12 2026)
- [x] H21 M5 logging confirmed active (29 lines, all fields present)
- [x] Audit CSV unified-mode write path confirmed (141 W8 rows)
- [x] F-A1 closed: adaptive gate static throughout W4–W8
- [x] F-A2 closed: arm-time H4 discrepancy harmless (99.7% agreement)
- [x] B1b permanently closed: three-regime inversion confirmed
- [x] H22 redefined: NY_OVERLAP worst session, ASIAN not profitable
- [x] Gate 5 LOCK_CANDIDATEs confirmed: XAUUSDm + BTCUSDm
- [x] F14 XAGUSDm overturned: -$80.85 all-time
- [x] Two-month retrospective completed: 7 targets, all produced
- [x] CAB IMMEDIATE_EXIT deployed (cab_watcher.py)
- [x] CAB REAPER simplified (cab_watcher.py)
- [x] SuperTrend ENTRY_QUALITY logging deployed (supertrend_bot.py)
- [x] CAB_ENTRY_QUALITY logging deployed (cab_entry.py)
- [x] GHOST_FIRE_QUALITY logging deployed (ghost_sniper.py, unified_runner.py)

## Week 9 Active Tasks (Sep 15–19 2026)

### Code changes deployed entering W9
- [x] CAB IMMEDIATE_EXIT rule (cab_watcher.py): exits losing trades within first 2 hours when R ≤ −0.20 and no prior actions taken. Logs: IMMEDIATE_EXIT|R{x}|held_{n}min
- [x] CAB REAPER simplified (cab_watcher.py): removed 7-condition triple gate. New: R ≤ −0.50 AND last closed H4 bar against position direction. Bar-gated. Logs: REAPER|H4_AGAINST|R{x}
- [x] SuperTrend ENTRY_QUALITY logging (supertrend_bot.py): cluster_spread, cluster_consensus, er_at_entry logged at every entry.
- [x] CAB_ENTRY_QUALITY logging (cab_entry.py): h4_bar_position, m15_aligned_bars, nearest_swing_atr logged at every H4 inversion.
- [x] GHOST_FIRE_QUALITY logging (ghost_sniper.py, unified_runner.py): committed_reversal_bars, trigger_bar_body_ratio logged at every Ghost trigger.

### Daily monitoring W9
- [x] IMMEDIATE_EXIT fires: conditions not met in W9 (no position hit −0.20R threshold)
- [x] REAPER fires: conditions not met in W9 (no position hit −0.50R threshold)
- [x] ENTRY_QUALITY logging: confirmed deployed in code (no ST entries during W9 review window)
- [x] CAB_ENTRY_QUALITY: confirmed deployed in code (no new CAB entries during W9)
- [x] GHOST_FIRE_QUALITY: confirmed in unified_runner.log (not sniper_hunter.log — routing clarified)
- [x] Thread health: 71 heartbeats Sep 16–19, 0 circuit breaker trips
- [x] XAGUSDm ST P&L: +$40.60 in W9 (+$6.77/tr, n=6). ESCALATED_WATCH removed.

### End-of-week W9 evaluations
- [x] H22-revised: CONFIRMED — NY_OVERLAP avg −$1.00/tr, n=14. Gate implemented entering W10.
- [x] XAGUSDm disable decision: NOT DISABLED — W9 strongly positive (+$40.60)
- [x] Gate 5 formal lock: XAUUSDm + BTCUSDm confirmed, no W9 regression
- [x] IMMEDIATE_EXIT vs full-loss: conditions never met in W9 (code confirmed deployed)
- [x] REAPER fires: conditions never met in W9 (code confirmed deployed)
- [x] Entry quality data: GHOST_FIRE_QUALITY and CAB_ENTRY_QUALITY confirmed in correct log files; code deployed correctly
- [x] Probe investigation: all Sep 12 features confirmed deployed; all zero-count results explained
- [x] Audit CSV gap explained: Ghost blocked by F6 Sep 16–19; no events = no writes

---

## Week 10 Active Tasks (Sep 22–26 2026)

### Code changes deployed entering W10
- [x] H22 NY_OVERLAP gate: wired in unified_runner.py ghost_hunter_thread and ghost_sniper.py run_hunter(). Logs GHOST_ARM_BLOCKED_SESSION. Test T21 added, 21/21 passing.
- [x] USTECm disabled: removed from config/config.json symbols section. Requires restart to take effect.

### Daily monitoring W10
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

### End-of-week W10 evaluations
- [ ] Ghost 202: does avg P&L improve from −$0.26/tr (W9)? Target: positive
      or materially less negative. Key question: does blocking NY_OVERLAP
      move the remaining ASIAN+LONDON fills to net positive?
- [ ] Gate 5 lock: XAUUSDm and BTCUSDm — any W10 regression?
- [ ] CAB trajectory: is BUY WR recovering from 25.8%? Are IMMEDIATE_EXIT
      or REAPER firing now that more data has accumulated?
- [ ] H22 gate count: how many probes were blocked during 12-16 UTC?
      Express as % of total ARM events.
- [ ] Account equity direction: is the trajectory improving?

### Known items to watch
- [ ] Magic 201 shadow pipeline (broken): 828 log events, 0 audit rows.
      Add to next code session agenda. Do not attempt mid-week.

---

## Deferred / Parked Items
- [ ] **P1 [BLOCKER — ACTIVE]:** SL geometry mismatch. Code: SCALP_REV_SL_ATR_MULT=0.35. Observed: median broker SL = 1.50×atr_at_fill. Hypothesis: 0.35 is applied to H1 ATR (0.35×H1 ≈ 2.67 ≈ observed 2.673). Resolve by grepping ghost_sniper.py for which copy_rates_from_pos timeframe feeds the SL calculation. Blocks BE-lock and ATR gate work.
- [x] **H4 Directional Bias Gate on Probe Arming**: IMPLEMENTED as F15 Sep 1 2026.
      Logs GHOST_ARM_BLOCKED_H4_DOWN. Only DOWN_PROBE gated.
- [x] **Phase B1b (UP_PROBE gate when H4=DOWN)**: PERMANENTLY CLOSED Sep 12 2026.
      H4 direction inverted in W6, W7, W8. No stable directional advantage
      all-time. Do not re-evaluate.
- [x] **Session filtering NY_CLOSE vs ASIAN**: RETIRED. F7 inverted W4→W6.
      Session×H4 combinations are regime-specific, not structural.
- [x] **H9 CAB H4 direction gate**: REFUTED Aug 30 2026. Gap narrowed to 7.5pp.
      No gate implemented. H14 EMA50 bias filter registered as Phase B2
      replacement hypothesis — requires 2 weeks of EMA50 logging before evaluation.
- [ ] **H14 EMA50 bias filter (CAB)**: Log EMA50 at every CAB entry in
      cab_watcher.log starting Week 7. Gate evaluation: earliest Week 9
      after n≥60 logged fills with EMA50 field.
- [x] **H15 stagnation decay**: CLOSED Sep 5 2026 — 0.9% of W6+W7 CAB
      losses open 24h+ at R<0.5 (1 of 115). No pattern.
- [x] **H16 rollover gate**: CLOSED Sep 5 2026 — 0 CAB entries at
      22:00-23:59 UTC across W6+W7. Gate not needed.
- [ ] **DOWN_PROBE BUY side**: F15 counter cannot accumulate (1 DOWN_PROBE
      arm in 832 events — gate is dead code in practice). Rely on H4
      direction data consistency instead. Earliest activation: Week 11.
- [ ] **Magic 201 audit CSV write fix (code task, registered Sep 5 2026)**:
      828 VIRTUAL_FILL events logged, zero audit CSV rows. is_shadow=True
      path in send_order() does not write to sniper_v51_live_audit.csv.
      Must be fixed before any 201-based shadow research can be conducted
      (shadow validation in Section 0.2 depends on virtual-fill tracking).
- [ ] **H22-revised NY_OVERLAP gate [IMPLEMENTED W10]**: Gate wired in
      unified_runner.py and ghost_sniper.py. Logs GHOST_ARM_BLOCKED_SESSION.
      Test T21 added, 21/21 passing. Verify firing during 12-16 UTC window
      in W10. Session definition: get_session() in ghost_sniper.py (canonical).
- [ ] **USTECm removed from config.json**: Disable trigger met (3 consecutive
      negative weeks). Removed from symbols section. Requires restart.
      Monitor: confirm magic 404213 absent from startup symbol list.
- [ ] **Entry Quality Score (Ghost)**: Phase C, requires 200+ post-F15 fills.
- [ ] **Conviction gate**: Phase C. Requires n≥80 in Conv>50 bucket. Non-monotonic
      in W6 — do not implement as binary threshold at <40 gate.
- [ ] **BE-lock step ratchet**: Replace one-shot BE-lock with progressive step. Parked until SL changes are cleanly measured.
- [ ] **Controlled grid-sizing / martingale**: Parked until grid tracking is confirmed perfectly functional.
- [ ] **Market Exit Score (Phase 3)**: Replace static R-threshold exits with continuous 0-1 score (regime, conviction, ATR, momentum, OSI).
- [ ] **CAB MFE/MAE logging (Enhancement 4)**: Safe to add anytime.
      TradeAnalyticsEngine already exists. Low priority — collect direction
      gate data first.
- [ ] **CAB enhancement spec**: Parked at Review Stage (Aug 22 2026).
      Tri-vector ADX framework deferred indefinitely. Vol_Expansion_Ratio
      gate deferred until ratio cross-referenced against trade outcomes.
      H4 Macro Trend Filter concept absorbed into H9 with simpler
      implementation path.
