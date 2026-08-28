---

# Algo Trading — Development Tracker

**Status:** Phase 2 Demo Testing — Week 6 (Statistical Gate Implementation)
**Version:** v17
**Last Updated:** Aug 22 2026

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

## Week 6 Active Tasks

### One code change (already applied before Week 6 start)
- [x] **N_LAYERS_DEFAULT = 2**: Applied in ghost_super/ghost_cache.py.
  10/10 unit tests confirmed passing. Only code change this week.

### Monitoring (daily, 5 minutes)
- [ ] **204 fires**: Check `grep -c "GHOST_CACHE_FIRE" logs/sniper_hunter.log`
  daily. Target: first fires in Week 6 now that n=2. If zero after Day 5
  of Week 6, this is a deeper problem — escalate before changing anything.
- [ ] **F6 gate**: Check `grep -c "GHOST_ARM_BLOCKED_ST_LONG" logs/unified_runner.log`
  after any ST XAUUSDm entry. If ST has open XAUUSDm positions and zero
  F6 logs appear, re-audit the KR thesis read in ghost_hunter_thread.
- [ ] **CAB BUY/SELL ratio**: At mid-week, tally CAB fills by direction
  from MT5 terminal or cab_watcher.log. If SELL fills are >60% of total
  and Gold is ranging (not trending), the directional split is structural,
  not regime-driven — early flag for H9.
- [ ] **Thread health**: grep "Heartbeat OK" logs/unified_runner.log | tail -3
  Expected: 5 threads alive.
- [ ] **H8 equity**: Record Week 6 close equity.

### End-of-Week 6 evaluations (data-dependent)
- [ ] **Ghost 202 session gate confirmation** (primary):
  If combined W4+W5+W6 reaches n≥170 LONDON fills and LONDON WR <35%
  → implement LONDON suppression on probe arming.
  If combined NY_CLOSE+H4_UP reaches n≥140 and WR <32%
  → implement direction gate on NY_CLOSE arming.
  If combined ATR Q2 reaches n≥195 and WR <30%
  → implement ATR floor gate (arm only when M1 ATR > 1.8).
  Run full audit CSV join with Week 6 MT5 export at session end.

- [ ] **H9 CAB direction gate** (secondary):
  Compute SELL vs BUY win rate from Week 6 MT5 export for CAB trades.
  Confirmation threshold: SELL WR < 35% AND BUY WR > 40% with n≥50
  in a week where Gold is not strongly trending.
  Refutation threshold: SELL WR within 5pp of BUY WR → gap was
  regime-specific → H9 not confirmed → no gate.

- [ ] **Gate 2 — 204 vs 202**: If 204 accumulates 10+ fills in Week 6,
  begin tracking avg_R per magic. Gate 2 requires 30+ fills each —
  still a longer-horizon target.

- [ ] **SuperTrend Gate 5 accumulation**: Pull per-symbol closed-trade
  data from MT5 export. Update bot-instrument fit matrix. Target for
  Gate 5 lock: 20+ trades per active symbol.

- [ ] **F6 effectiveness**: If 202 fires at normal volume and F6 gate
  also fires, compute win rate for 202 trades where F6 did NOT block
  vs baseline W4 win rate. First effectiveness data point.

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
