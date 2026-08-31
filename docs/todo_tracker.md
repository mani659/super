---

# Algo Trading — Development Tracker

**Status:** Phase 2 Demo Testing — Week 7 (Phase B Gates Active)
**Version:** v18
**Last Updated:** Aug 31 2026

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

---

## Week 7 Active Tasks

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

### Monitoring (daily, 5 minutes)
- [ ] **F15 gate**: `grep -c "GHOST_ARM_BLOCKED_H4_DOWN" logs/unified_runner.log`
  Expected: nonzero by Day 1 end. Zero after Day 3 = wiring broken.
- [ ] **F5 London gate**: Confirm 07-11 UTC cab fills drop to zero in MT5 export.
  Check `grep -c "session_gate\|LONDON" logs/cab_watcher.log`.
- [ ] **204 fires**: `grep -c "GHOST_CACHE_FIRE" logs/sniper_hunter.log`.
  Target: nonzero. If zero after Day 5 at N_LAYERS=2, escalate.
- [ ] **F6 gate**: `grep -c "GHOST_ARM_BLOCKED_ST_LONG" logs/unified_runner.log`.
- [ ] **Thread health**: `grep "Heartbeat OK" logs/unified_runner.log | tail -3`.

### End-of-Week 7 evaluations
- [ ] **F15 effectiveness**: W7 202 WR > 44% (from W6 40.0%) OR avg/trade improves from -$0.43.
  If not: gate may be helping on count but not per-trade quality.
- [ ] **F5 effectiveness**: Zero cab_managed fills opening 07-11 UTC in W7.
  If fills still appear: blocked_hours_utc change did not deploy.
- [ ] **H15 stagnation decay**: Compute from W6+W7 CAB MT5 export.
  Check % of CAB losses held 24h+ at R<0.5. If >30%: register for Phase C.
- [ ] **H16 rollover gate**: Compute W6 CAB entry WR at 22-23 UTC.
  If WR<30%: extend blocked_hours_utc to include 22,23 entering Week 8.
- [ ] **F7 NY_CLOSE+H4_UP**: Evaluate combined n vs 140 threshold.
- [ ] **USTECm disable**: If 3rd consecutive negative week with 5+ closed trades.
- [ ] **Gate 2 — 204 vs 202**: If 204 accumulates 5+ fires, begin avg_R tracking.

---
## Week 6 COMPLETED (Aug 25–29)
- [x] **N_LAYERS_DEFAULT = 2**: Applied in ghost_super/ghost_cache.py.
  10/10 unit tests confirmed passing.
- [x] **204 fires monitoring**: 1 fire Week 6. Gate 2 data started.
- [x] **F6 gate effectiveness**: 0 fires W6 (regime gate blocked arming before F6 — confirmed not a dead wire).
- [x] **H8 equity**: W6 close $6,867.54, week P&L -$109.96.
- [x] **H9 CAB direction gate**: REFUTED — gap narrowed to 7.5pp in ranging conditions. No gate.
- [x] **Cross-CAB comparison**: Completed. H13 invalidated, H14-H16 registered.
- [x] **W6 data extraction and analysis**: Complete.
- [x] **F5 London Open gate**: IMPLEMENTED Aug 31 2026. Cross-system evidence from 3 CAB variants.
- [x] **F15 H4 direction gate**: IMPLEMENTED Aug 31 2026. Test T20 added, 20/20 passing.

### Hypothesis tracking (Week 7 evaluation queue)
- [ ] **H14 EMA50 bias filter**: Log EMA50 at every cab_super entry starting Week 7.
  Two weeks of data before any gate decision. No gate until Week 9.
- [ ] **H15 stagnation decay**: Compute from W6+W7 CAB MT5 export.
  If >30% of losses held 24h+ at R<0.5: register for Phase C.
- [ ] **H16 rollover gate**: Compute from W6 CAB audit entries at 22-23 UTC.
  If WR<30%: extend blocked_hours_utc to include 22,23.

### End-of-Week 6 evaluations (completed)
- [x] **Ghost 202 session gate confirmation**: LONDON confirmed negative across 3 systems.
  n=341 cross-system, n=82 in-system. F5 London gate implemented.
  NY_CLOSE+H4_UP: n=89 of 140 needed. ATR floor: n=134 of 195 needed.
  ADX dead zone: insufficient n. Conviction: 37% WR in 20-40 bucket (above 35% threshold).
- [x] **H9 CAB direction gate**: REFUTED. Gap narrowed to 7.5pp in ranging conditions.
  Gate not implemented. H9 archived.
- [x] **Gate 2 — 204 vs 202**: 204 had 1 fire in W6. 30+ fills each still needed.
- [x] **SuperTrend Gate 5 accumulation**: Continue accumulating.
- [x] **F6 effectiveness**: 0 fires W6 — regime gate blocked arming before F6.
  Wiring confirmed in code review.
- [x] **MPE publishing**: Confirmed operational. Audit CSV shows 140 distinct ADX values.

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

## Deferred / Parked Items
- [ ] **H4 Directional Bias Gate on Probe Arming**: Block DOWN_PROBE arming when h4_direction=UP and UP_PROBE arming when h4_direction=DOWN. Deferred pending H2 confirmation from Week 4 data. If H2 confirmed, this becomes the first post-data-window mechanical change. Implementation target: `ghost_hunter_thread` in `unified_runner.py` and `run_hunter()` in `ghost_super/ghost_sniper.py` — add `_get_h4_direction()` check before any probe arming.
- [ ] **BE-lock step ratchet**: Replace one-shot BE-lock with progressive step. Parked until SL changes are cleanly measured.
- [ ] **Session filtering**: NY_CLOSE vs ASIAN. Parked until clean baseline is collected from the fully working system.
- [ ] **Controlled grid-sizing / martingale**: Parked until grid tracking is confirmed perfectly functional.
- [ ] **Market Exit Score (Phase 3)**: Replace static R-threshold exits with continuous 0-1 score (regime, conviction, ATR, momentum, OSI).
- [ ] **H9 CAB H4 direction gate**: Implementation in cab_entry.py blocked
  pending Week 6 confirmation. If confirmed: add _get_h4_direction(symbol)
  to CABEntryEngine, gate bearish inversion entries when H4=UP.
  Log CAB_SELL_BLOCKED_H4_UP. Does not touch exit logic or BUY entries.
- [ ] **CAB MFE/MAE logging (Enhancement 4)**: Safe to add anytime.
  TradeAnalyticsEngine already exists. Low priority — collect direction
  gate data first.
- [ ] **CAB enhancement spec**: Parked at Review Stage (Aug 22 2026).
  Tri-vector ADX framework deferred indefinitely. Vol_Expansion_Ratio
  gate deferred until ratio cross-referenced against trade outcomes.
  H4 Macro Trend Filter concept absorbed into H9 with simpler
  implementation path.
