---

# Algo Trading — Development Tracker

**Status:** Phase 2 Demo Testing — Week 5 (Statistical Gate Evaluation)
**Version:** v16
**Last Updated:** Aug 16 2026

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

---

## Week 5 Active Tasks

### Immediate (system running, no code changes)
- [ ] **Monitor 204 fires**: First fires expected in Week 5 following 
  decouple fix. Check logs/sniper_hunter.log for GHOST_CACHE_FIRE 
  lines daily. If zero fires after 5 trading days, lower 
  N_LAYERS_DEFAULT from 3 to 2 in ghost_cache.py (one change only).
- [ ] **Confirm CAB log active**: Within first hour of Week 5 session, 
  verify logs/cab_watcher.log exists and has content. If empty, 
  the path fix did not deploy correctly — stop and re-check 
  cab_watcher.py on the VPS before proceeding.
- [ ] **H5 evaluation**: At end of Week 5, run SL distance analysis 
  from logs/cab_watcher.log. For each CAB SL hit, compute 
  pip distance from entry to SL vs ATR at entry. If median < 1.5×ATR, 
  H5 confirmed and SL widening enters the agenda for Week 6.
- [ ] **H8 equity tracking**: Record Week 5 close equity. Target: 
  stabilize drawdown rate. Primary lever is Ghost 202 session exposure.

### F6 Implementation (only agreed Week 5 code change)
- [ ] **H6 Cross-bot gate on Ghost 202 arming**: In ghost_hunter_thread 
  (unified_runner.py), before arming a new probe on XAUUSDm, query KR 
  for active SuperTrend thesis on XAUUSDm. If thesis exists with 
  direction=+1 (BUY/LONG), block UP_PROBE arming and log 
  GHOST_ARM_BLOCKED_ST_LONG. Does not affect any fired or open 
  positions — arming only. Single KR read, no new data structures. 
  Evidence: n=34, 8pp win rate drop, 3× worse P&L when opposing ST 
  confirmed LONG. This is the only Week 5 implementation candidate 
  not requiring additional session data.

### Statistical gate evaluations (end of Week 5, data-dependent)
- [ ] **F1 ATR gate**: If Q2 win rate stays below 30% in Week 5 
  data (expected n=150+ combined) → implement ATR floor at 1.8 on 
  probe arming.
- [ ] **F2/F5 Session gate**: If LONDON win rate stays below 35% 
  combined Weeks 4+5 (expected n=118+) → implement LONDON suppression.
- [ ] **F7 Direction gate**: If NY_CLOSE + H4_UP win rate stays below 
  32% combined (expected n=108+) → implement direction gate on 
  NY_CLOSE arming.
- [ ] **F3 Conviction gate**: If conviction 20-40 stays below 35% 
  combined → implement conviction gate at 40+.
- [ ] **F4 ADX dead zone gate**: If ADX 20-25 stays below 33% 
  combined → implement ADX 20-25 suppression.

### H5 — CAB SL tightness (evaluate end of Week 5)
- [ ] Pull pip distance from entry to SL hit vs ATR at entry for all 
  CAB losses in Week 5 from logs/cab_watcher.log.
  Run: grep "Closed #" logs/cab_watcher.log | grep "sl"
  Cross-reference with KR thesis entry_atr for each ticket.
  Compute: sl_hit_distance / entry_atr for each loss.
  If median ratio < 1.5 → H5 confirmed → SL widening agenda for Week 6.

---
### Knowledge Register Wiring (High Priority)
- [ ] **Fix 7: Lifecycle Cleanup**: Call `unregister_trade_thesis()` whenever a position is closed across ALL bots (CAB, ST, Ghost) to prevent unbounded memory growth and corrupted risk calculations.
- [ ] **Fix 5: Wire Hard-Block Layers (2 & 3)**: Enforce invalidation and portfolio exposure limits. Inject `is_entry_invalidated()` and `check_portfolio_entry_allowed()` into the pre-entry logic for CAB, Ghost, and ST. Additionally, ensure all bots call `publish_invalidation()` when they locally identify a structural break (ST DEAD-state, CAB OSI, Ghost regime-arm-gate).
- [ ] **Fix 4: Universal Thesis Registration**: Ensure Ghost Sniper and SuperTrend call `register_trade_thesis()` upon filling an order. (Currently CAB-only).
- [ ] **Fix 6: Deduplicate Micro Degradation**: Decide between CAB's `TradeDegradationEngine.is_degrading()` and KR's `get_micro_degradation()`. Standardize on a single implementation and remove the dead code.
- [ ] **Fix 1-3: Tech Debt & Tuning**: Fix cosmetic ATR comment in `ghost_sniper.py`, remove legacy kwargs from `run_bot.py`, and prepare for per-symbol weight tuning in `config.json`.

- [ ] **Gate 5 (Bot-Instrument Fit Matrix)**: Lock `avg_R` cross-tab by bot × instrument to finalize live pair deployment.
- [ ] **Gate 6 (Live Deployment)**: One unified process, micro-lot, avg R > 0.3 over 50 live trades.
- [ ] **Dynamic Lot Sizing (CAB)**: Implement dynamic lot sizing for the CAB bot. This will be made dynamic globally under the unified bot, with the only exception being the Ghost Grid (until logic validation is complete). Will apply in the next coding run.
- [ ] **Market Intelligence - Confluence Identification**: Add market environment intelligence logic to identify and leverage situations where both CAB and SuperTrend bots open trades in the same direction (e.g., both buy). This complementing direction indicates high market confluence and will be highly valuable in the long run.
- [ ] **Research/Discussion: Ghost Grid Risk Concentration**: Re-evaluate Legs 201 and 202 firing as a stacked block. Redesign to ensure true regime complementarity instead of doubling exposure on identical triggers.
- [ ] **Research/Discussion: Ghost BE-Lock Expectancy**: Review micro-lot scalping math; fixed spread costs currently consume profit targets before BE-lock mathematically engages.
- [ ] **Research/Discussion: Regime Disconnect (H2/H4 pending confirmation)**: Ghost Grid M15 probe arming and SuperTrend H4 regime reads disagreed during Week 3 — Gold classified as RANGING on M15 while making a 130-point H4 uptrend. Proposed fix: block DOWN_PROBE arming when H4 structural direction is UP, and UP_PROBE when H4 is DOWN. NOT implementable until H2 is confirmed from Week 4 h4_direction_at_arm data and H4 regime label accuracy is verified. Minimum evidence requirement: H2 confirmed at >30% DOWN_PROBE-into-H4-UP rate across Week 4 fills.
- [ ] **Research/Discussion: SuperTrend Continuation Signals**: Evaluate the risk of bypassing the `INCUBATING -> CONFIRMED` state machine for mid-trend entries, which strips SI protections.
- [ ] **Research/Discussion: Model Divergence vs. Exposure Limits**: Evaluate the workflow impact, pros, and cons of adding a statistical meta-model tie-breaker for conflicting positions (e.g., CAB sells on H4, SuperTrend buys on M15). Must reconcile with the current Knowledge Register design (Layers 2/3), which treats ST-vs-Ghost disagreement as legitimate and manages it via correlation-bucket exposure ceilings rather than a hard directional veto. Keep as an idea for detailed statistical discussion before considering any implementation.
- [ ] **Architectural Fix for 10016 SL Rejections (RESOLVED — Aug 8 2026)**: Option 2 (Phase 2 Dynamic SL) implemented in `ghost_super/ghost_sniper.py` `send_order()`. SL/TP anchor in Phase 2 now computed from `result.price` (actual fill price) rather than pre-order tick price. Eliminates geometric mismatch that caused 10016 rejections and downstream naked trade kill-switch terminations. Single-Phase entry (Option 1) was rejected because it would cause missed entries on 10016 rejection of the bundled order — worse outcome on a strategy that fires at precise probe retraction moments.

## Deferred / Parked Items
- [ ] **H4 Directional Bias Gate on Probe Arming**: Block DOWN_PROBE arming when h4_direction=UP and UP_PROBE arming when h4_direction=DOWN. Deferred pending H2 confirmation from Week 4 data. If H2 confirmed, this becomes the first post-data-window mechanical change. Implementation target: `ghost_hunter_thread` in `unified_runner.py` and `run_hunter()` in `ghost_super/ghost_sniper.py` — add `_get_h4_direction()` check before any probe arming.
- [ ] **BE-lock step ratchet**: Replace one-shot BE-lock with progressive step. Parked until SL changes are cleanly measured.
- [ ] **Session filtering**: NY_CLOSE vs ASIAN. Parked until clean baseline is collected from the fully working system.
- [ ] **Controlled grid-sizing / martingale**: Parked until grid tracking is confirmed perfectly functional.
- [ ] **Market Exit Score (Phase 3)**: Replace static R-threshold exits with continuous 0-1 score (regime, conviction, ATR, momentum, OSI).
