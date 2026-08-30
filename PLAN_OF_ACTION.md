# 📋 Plan of Action — Based on Deep Regime Intelligence Analysis
**Generated:** August 30, 2026
**Source:** DEEP_REGIME_INTELLIGENCE_ANALYSIS.md
**Scope:** Project-wide + per-bot recommendations
**Status:** Planning only — no code changes yet

---

## Table of Contents
1. [Priority Matrix](#1-priority-matrix)
2. [Project-Level Recommendations](#2-project-level-recommendations)
3. [SuperTrend/CAB Bot Recommendations](#3-supertrendcab-bot-recommendations)
4. [Ghost Sniper Bot Recommendations](#4-ghost-sniper-bot-recommendations)
5. [Unified Runner Recommendations](#5-unified-runner-recommendations)
6. [Knowledge Base Updates](#6-knowledge-base-updates)
7. [Implementation Timeline](#7-implementation-timeline)
8. [Success Metrics & Validation](#8-success-metrics--validation)

---

## 1. Priority Matrix

### Priority Classification
- 🔴 **P0 — Critical:** Directly prevents losses. Implement first.
- 🟡 **P1 — High:** Improves win rate or R-multiples. Implement within 1 week.
- 🟢 **P2 — Medium:** Optimization. Implement within 2 weeks.
- ⚪ **P3 — Low:** Nice to have. Backlog.

### Quick Reference

| # | Recommendation | Level | Priority | Est. Impact |
|---|----------------|-------|----------|-------------|
| 1 | R-Velocity Early Warning | Project | 🔴 P0 | Save ~0.13R per early exit |
| 2 | Volume Spike Block | Project | 🔴 P0 | Block rollover traps |
| 3 | Portfolio Cluster Ceiling | Project | 🔴 P0 | Prevent correlated blowup |
| 4 | ADX Exhaustion Gate | Project | 🟡 P1 | Block exhausted trend entries |
| 5 | Conviction Floor Gate | CAB | 🟡 P1 | Block low-conviction losers |
| 6 | ATR Expansion Entry Gate | CAB | 🟡 P1 | Enter during opportunity, not exhaustion |
| 7 | Ghost 202 Session Filter | Ghost | 🟡 P1 | Block rollover/London entries |
| 8 | Regime Drift Rate | Project | 🟢 P2 | Detect regime transitions |
| 9 | Cache Freshness Gate | Runner | 🟢 P2 | Act on current data only |
| 10 | Spread Ratio Ceiling | Project | ⚪ P3 | Avoid degraded execution |

---

## 2. Project-Level Recommendations

### 🔴 P0-1: R-Velocity Early Warning System

**Problem:** Trades that go negative within 30 minutes of entry have a 75% chance of being losers. Current system holds to full SL, losing ~0.18R average. Early exit at -0.05R would save ~0.13R per trade.

**Recommendation:**
- Implement R-Velocity measurement for every active position, computed every cycle
- R-Velocity = rate of change of R-multiple over time
- Define exit thresholds:
  - **Yellow flag:** R-Velocity negative for 3+ consecutive cycles (~30 min) → alert, prepare to exit
  - **Red flag:** R-Velocity negative for 6+ consecutive cycles (~60 min) → force exit
- Track and log every R-Velocity triggered exit separately from normal SL/TP exits
- Measure how much R was saved per early exit vs what would have been lost to full SL

**Expected Impact:**
- Save ~0.13R per structural loser caught early
- At 40+ trades/week with ~40% losers, that's ~16 trades × 0.13R = ~2.08R saved per week
- At current risk sizing, that's approximately +$10–15/week in avoided losses

**Validation Criteria:**
- After 1 week: Track how many early exits were triggered vs how many would have recovered to breakeven/positive
- After 2 weeks: Compare total R saved vs R lost from premature exits
- Key metric: Net R impact of the feature (must be positive)

---

### 🔴 P0-2: Volume Spike Block (Rollover Protection)

**Problem:** Entries during 21:00–23:00 UTC (rollover) have avg R = -0.18. Volume spikes 2–4x normal + spread widening 3–5x cause execution traps.

**Recommendation:**
- Define rollover window: 21:00–23:00 UTC daily
- Define volume spike threshold: Vol_Ratio > 2.5
- Block new entries when EITHER condition is met:
  - Current time is within rollover window, OR
  - Current Vol_Ratio > 2.5 (regardless of time)
- Allow existing positions to manage normally (don't force exits during rollover)
- Log every blocked entry with reason (TIME/Volume/Both)

**Expected Impact:**
- Block ~2–3 entries per week that would have avg R = -0.18
- Prevent ~0.36–0.54R in weekly losses
- At current sizing: ~$2–3/week saved

**Validation Criteria:**
- Count blocks per week (expect 3–5)
- Track if blocked entries would have actually lost (compare next-bar price action)
- Ensure no good entries are being blocked (false positive rate should be <20%)

---

### 🔴 P0-3: Portfolio Cluster Ceiling

**Problem:** Cluster Score ≥7 creates correlated portfolio concentration. Aug 28 drawdown (-$25) was actually one correlated event masked as multiple independent losses.

**Recommendation:**
- Hard cap: Cluster Score maximum = 7
- Before any new entry, calculate resulting Cluster Score
- If adding position would push Cluster Score > 7:
  - **Option A (Conservative):** Block the entry entirely
  - **Option B (Moderate):** Allow but reduce position size by 50%
  - **Option C (Aggressive):** Allow but require Cluster Score > 8 to exit first (reduce before adding)
- Track Cluster Score over time and log drawdown events alongside Cluster Score at entry

**Expected Impact:**
- Prevent portfolio-level correlated blowups
- Estimated drawdown reduction: 30–40% on worst days
- May reduce total trade count by 10–15% (acceptable tradeoff)

**Validation Criteria:**
- Monitor if blocked entries would have been winners (check next 4H price)
- Track peak Cluster Score vs drawdown correlation
- After 2 weeks: Compare max drawdown before/after implementation

---

### 🟡 P1-4: ADX Exhaustion Gate

**Problem:** ADX percentile > 95 is exhaustion, not strength. Current system treats high ADX as "strong trend" when it's actually "trend about to reverse." 35% win rate at ADX > 95.

**Recommendation:**
- Block new TREND entries when ADX_Pctl > 90
- Reduce position size by 50% when ADX_Pctl > 85
- Flag as potential reversal zone when ADX_Pctl > 95
- Log all blocked entries with ADX_Pctl value and subsequent price action

**Expected Impact:**
- Block ~1–2 entries per week in exhaustion zone
- Improve overall win rate by 3–5%
- Reduce avg losing R by avoiding worst entries

**Validation Criteria:**
- Compare blocked entries' next-4H price action (did they reverse?)
- Track if trend continuation entries above ADX 90 would have won or lost
- After 2 weeks: Measure win rate improvement

---

### 🟡 P1-5: Conviction Floor Gate

**Problem:** Conviction < 40 is almost universally negative. These trades are guaranteed losers.

**Recommendation:**
- Hard floor: Conviction ≥ 35 to enter any trade
- No ceiling: Indifferent between 60 and 90 conviction
- Log all blocked entries with conviction score and subsequent price action
- Track if any blocked entries would have been winners (false positive rate)

**Expected Impact:**
- Block ~3–5 low-conviction entries per week
- Prevent ~0.45–0.75R in weekly losses
- At current sizing: ~$2–3/week saved

**Validation Criteria:**
- Monitor false positive rate (blocked entries that would have won)
- Target: <10% false positive rate
- After 1 week: Verify win rate improvement on remaining trades

---

### 🟡 P1-6: ATR Expansion Entry Gate

**Problem:** Entry during expanding ATR (1.0→1.5) is the winning zone. Entry during already-expanded ATR (>2.0) catches the tail end of moves.

**Recommendation:**
- Track ATR Factor AND ATR Factor Delta (direction of change)
- Entry rules:
  - **Allowed:** ATR Factor 0.8–1.8 AND ATR Factor Delta positive (expanding)
  - **Caution:** ATR Factor 1.5–1.8 AND ATR Factor Delta negative (contracting) → reduce size
  - **Blocked:** ATR Factor > 2.5 (already expanded = exhausted)
  - **Blocked:** ATR Factor < 0.7 (too quiet = no opportunity)
- Log all ATR-gated entries with ATR Factor and Delta values

**Expected Impact:**
- Enter trades at better risk/reward moments
- Avoid chasing exhausted moves
- Improve avg R by 0.05–0.10

**Validation Criteria:**
- Compare ATR Factor at entry for winning vs losing trades
- Track if blocked entries would have been losers
- After 2 weeks: Measure avg R improvement

---

### 🟢 P2-7: Regime Drift Rate

**Problem:** M15 regime classifier is static — never changes within a session. Trades enter in "stable" regimes that are actually transitioning.

**Recommendation:**
- Implement rolling metric: ADX percentile change per H4 bar
- Define thresholds:
  - **Stable:** |ADX_Pctl_delta| < 10 per H4 bar → regime label reliable
  - **Transitional:** |ADX_Pctl_delta| 10–15 → regime label unreliable, proceed with caution
  - **Unstable:** |ADX_Pctl_delta| > 15 → regime label unreliable, reduce exposure
- Flag all trades entered during "Transitional" or "Unstable" drift
- Log drift rate at entry and compare to outcome

**Expected Impact:**
- Better regime awareness
- Fewer entries during regime transitions
- Estimated win rate improvement: 2–4%

**Validation Criteria:**
- Compare regime label vs drift rate over time
- Track win rate during stable vs transitional regimes
- After 2 weeks: Validate drift rate as regime quality indicator

---

### 🟢 P2-8: Spread Ratio Ceiling

**Problem:** Degraded execution during high-spread conditions (rollover, news) costs R.

**Recommendation:**
- Track normal spread per pair (20-period average)
- Block entries when current spread > 3x normal
- Log all spread-gated entries with spread values
- Track if blocked entries would have been losers

**Expected Impact:**
- Avoid execution quality degradation
- Small but consistent improvement in avg R
- Estimated: +0.02–0.05R per trade affected

**Validation Criteria:**
- Monitor spread levels during winning vs losing trades
- Verify blocked entries would have lost
- After 2 weeks: Measure execution quality improvement

---

## 3. SuperTrend/CAB Bot Recommendations

### 3.1 Conviction-Based Position Sizing

**Current:** Fixed position sizing regardless of conviction score.

**Recommendation:**
- Use conviction as a sizing modifier:
  - Conviction 35–50: Base size × 0.75
  - Conviction 50–70: Base size × 1.0 (standard)
  - Conviction 70–85: Base size × 1.25
  - Conviction 85+: Base size × 1.0 (cap at standard — high conviction doesn't mean more size)
- Rationale: The data shows conviction is a quality filter below 60, but not above 80. Size accordingly.

**Expected Impact:**
- Reduce exposure on lower-quality trades
- Increase exposure on high-quality trades
- Improve risk-adjusted returns

---

### 3.2 Regime-Specific Strategy Selection

**Current:** Same strategy logic regardless of regime.

**Recommendation:**
- **RANGING regime:** Prioritize grid/mean-reversion entries. Reduce trend-following confidence.
- **TRENDING regime:** Prioritize continuation entries. Block grid/mean-reversion. Require cluster ≥ 7.
- **VOLATILE regime:** Reduce all position sizes by 50%. Block new entries. Only manage existing positions.
- **MIXED regime:** Grid trades only with tight parameters. No directional bets.

**Expected Impact:**
- Better strategy-regime alignment
- Fewer mismatched entries
- Estimated win rate improvement: 5–8%

---

### 3.3 Pair-Specific Quality Scores

**Current:** All pairs treated equally.

**Recommendation:**
- Maintain rolling quality score per pair (20-trade window):
  - **Score > 0.10 R:** Premium pair → normal sizing
  - **Score 0.00–0.10 R:** Standard pair → normal sizing
  - **Score < 0.00 R:** Underperforming pair → reduce sizing by 50%
  - **Score < -0.05 R:** Problem pair → block new entries until score recovers

**Week 6 Baseline Scores:**
| Pair | Avg R | Quality Score | Recommendation |
|---|---|---|---|
| USDJPY | +0.15 | Premium | Normal sizing |
| AUDNZD | +0.10 | Premium | Normal sizing |
| BTCUSD | +0.08 | Standard | Normal sizing |
| EURUSD | +0.05 | Standard | Normal sizing |
| GBPUSD | -0.03 | Underperforming | Reduce size 50% |
| ETHUSD | -0.06 | Problem | Block until recovery |
| USOIL | -0.08 | Problem | Block until recovery |

**Expected Impact:**
- Reduce exposure to underperforming pairs
- Capitalize on high-performing pairs
- Overall portfolio quality improvement

---

### 3.4 R-Velocity Integration with Exit Logic

**Current:** SL/TP based on fixed levels.

**Recommendation:**
- Add R-Velocity as a dynamic exit modifier:
  - If R-Velocity negative for 6+ cycles AND trade is in profit: Tighten TP (take what you can)
  - If R-Velocity negative for 6+ cycles AND trade is in loss: Exit early (save R)
  - If R-Velocity positive: Let trade run, widen TP if conviction supports it
- Track every R-Velocity exit separately

**Expected Impact:**
- Early exits save ~0.13R per structural loser
- Profit-taking on fading winners captures gains before reversal
- Estimated weekly R saved: 1.5–2.5R

---

### 3.5 London Open Protection

**Current:** No special handling for London open.

**Recommendation:**
- **Block ALL trend entries during 08:00–10:00 UTC (London open)**
- Rationale: Ledger shows -8.06R from London open false breakouts
- Allow grid entries only (with tighter parameters)
- Log all London open blocks with subsequent price action

**Expected Impact:**
- Prevent false breakout losses
- Estimated R saved: 0.5–1.0R per week

---

## 4. Ghost Sniper Bot Recommendations

### 4.1 Ghost 202 Session Filter

**Current:** 202 pattern entries allowed at any time.

**Recommendation:**
- **Block 202 entries during:**
  - 20:00–23:00 UTC (rollover execution trap)
  - 08:00–10:00 UTC (London open false breakouts)
- **Allow 202 entries during:**
  - 10:00–20:00 UTC (best execution window)
- Track blocked vs allowed entries and compare outcomes

**Expected Impact:**
- Improve 202 win rate from 33% to estimated 50%+
- Avoid execution quality degradation
- Estimated R improvement: +0.10–0.15 per 202 entry

---

### 4.2 Ghost Entry Volume Confirmation

**Current:** No volume confirmation for ghost entries.

**Recommendation:**
- Require Vol_Ratio > 0.8 (above minimum liquidity) for any ghost entry
- Require Vol_Ratio < 2.0 (below spike threshold) for any ghost entry
- Block ghost entries when Vol_Ratio outside 0.8–2.0 range
- Log volume-gated ghost entries

**Expected Impact:**
- Avoid entering during low-liquidity dead zones
- Avoid entering during volume spike traps
- Improve ghost entry quality

---

### 4.3 Ghost R-Velocity Monitoring

**Current:** No R-Velocity tracking for ghost positions.

**Recommendation:**
- Apply same R-Velocity early warning to ghost positions
- Ghost entries are typically smaller/s shorter-term, so adjust thresholds:
  - **Yellow flag:** R-Velocity negative for 2+ cycles (~20 min)
  - **Red flag:** R-Velocity negative for 4+ cycles (~40 min)
- Ghost positions are more sensitive to momentum shifts

**Expected Impact:**
- Faster exit on failing ghost positions
- Better capital preservation for re-entry

---

### 4.4 Ghost ADX Exhaustion Protection

**Current:** No ADX-based filtering for ghost entries.

**Recommendation:**
- Block ghost entries when ADX_Pctl > 85 (ghost trades are momentum-based, exhaustion kills them)
- Ghost entries perform best in ADX_Pctl 40–75 range (genuine momentum, not exhaustion)
- Log ADX_Pctl at ghost entry and compare to outcome

**Expected Impact:**
- Avoid entering exhausted trends
- Improve ghost win rate by 5–10%

---

### 4.5 Ghost Pair Rotation

**Current:** Ghost trades same pairs regardless of recent performance.

**Recommendation:**
- Maintain ghost-specific pair quality scores (10-trade window)
- Rotate away from underperforming pairs for ghost entries
- Prioritize pairs with positive ghost R-multiples
- Log pair rotation decisions

**Expected Impact:**
- Avoid chasing dead pairs
- Capitalize on pairs with active momentum

---

## 5. Unified Runner Recommendations

### 5.1 Cache Freshness Gate

**Problem:** Stale cache reads (>30min) correlate with entries into dead zones. System acts on market data that no longer reflects current conditions.

**Recommendation:**
- Track cache age for every signal
- Define freshness thresholds:
  - **Fresh:** < 10 minutes → full confidence
  - **Acceptable:** 10–20 minutes → proceed with caution
  - **Stale:** 20–30 minutes → reduce position size by 50%
  - **Expired:** > 30 minutes → block entry entirely
- Log cache age at every entry decision
- Track win rate by cache age bucket

**Expected Impact:**
- Act on current market data only
- Avoid entries based on stale prices
- Estimated win rate improvement: 3–5%

---

### 5.2 Heartbeat-Driven Anomaly Detection

**Current:** Heartbeats log equity/P&L but don't trigger actions.

**Recommendation:**
- Add anomaly detection to heartbeat monitoring:
  - **Equity drop > $10 in single heartbeat:** Alert + pause new entries for 1 hour
  - **Equity drop > $20 in single heartbeat:** Alert + pause new entries for 2 hours + review all positions
  - **Drawdown > 3% of equity:** Alert + reduce position sizes by 50% until recovery
- Log all anomaly triggers with context (what positions were open, what regime, what time)

**Expected Impact:**
- Faster response to drawdown events
- Prevent cascade losses
- Better risk management during adverse conditions

---

### 5.3 Execution Quality Monitoring

**Current:** No execution quality tracking.

**Recommendation:**
- Log execution quality metrics for every trade:
  - Spread at entry vs normal spread
  - Slippage (requested price vs actual fill)
  - Vol_Ratio at entry
  - Time of day
- Calculate execution quality score per trade
- Track correlation between execution quality and outcome
- Alert when execution quality degrades (e.g., multiple bad fills in sequence)

**Expected Impact:**
- Identify execution quality issues
- Better understanding of slippage impact on R
- Data-driven execution optimization

---

### 5.4 Position Reconciliation

**Current:** Positions tracked internally but not reconciled against broker.

**Recommendation:**
- Add periodic position reconciliation (every heartbeat):
  - Compare internal position list vs broker position list
  - Flag any discrepancies (missing positions, extra positions, wrong sizes)
  - Log reconciliation results
- Critical for detecting execution failures, partial fills, and broker issues

**Expected Impact:**
- Catch execution failures early
- Prevent position drift
- Better accuracy in R-multiple calculations

---

## 6. Knowledge Base Updates

### 6.1 Add to `docs/knowledge_register.md`

**New Entries to Add:**

1. **R-Velocity as Leading Indicator**
   - Definition, calculation, thresholds
   - Observed patterns and validation data
   - Implementation guidance

2. **Regime-Truth Gap**
   - M15 classifier limitations
   - Regime Drift Rate as solution
   - When to trust vs distrust regime labels

3. **Conviction Paradox**
   - Conviction as floor filter, not quality filter
   - Optimal conviction ranges by strategy
   - Position sizing implications

4. **ATR Factor Sweet Spots**
   - Optimal entry range (0.8–1.8 expanding)
   - Danger zones (>2.5, <0.7)
   - ATR Factor Delta importance

5. **Volume & Liquidity Patterns**
   - Volume spike traps
   - Rollover execution window
   - Optimal Vol_Ratio ranges

6. **Cluster Score Risk**
   - Portfolio concentration
   - Correlated drawdown events
   - Recommended caps

7. **Ghost 202 Pattern**
   - Performance baseline
   - Session filters
   - Volume confirmation requirements

8. **ADX Exhaustion**
   - High ADX ≠ strength
   - Exhaustion zone identification
   - Entry blocking thresholds

9. **Execution Quality Metrics**
   - Spread ratio tracking
   - Cache freshness importance
   - Rollover protection

10. **Pair Quality Scores**
    - Rolling quality calculation
    - Pair rotation logic
    - Underperforming pair handling

### 6.2 Update `cab/docs/statistical_proof_&_empirical_rationale_ledger.md`

- Add Week 6 baseline data
- Add R-Velocity baseline measurements
- Add cluster score correlation data
- Add volume regime analysis

### 6.3 Update `docs/session_handoff.md`

- Add current bot configurations
- Add active KPIs and thresholds
- Add recent performance metrics
- Add known issues and workarounds

---

## 7. Implementation Timeline

### Week 1 (Aug 31 – Sep 6): Critical Fixes
**Focus:** P0 items that directly prevent losses

| Day | Task | Bot | Priority |
|---|---|---|---|
| Day 1–2 | R-Velocity measurement implementation | Project | 🔴 P0 |
| Day 2–3 | Volume Spike Block implementation | Project | 🔴 P0 |
| Day 3–4 | Portfolio Cluster Ceiling implementation | Project | 🔴 P0 |
| Day 4–5 | Testing and validation | All | 🔴 P0 |
| Day 5–7 | Monitor and collect data | All | — |

**Success Criteria:**
- R-Velocity tracking active on all positions
- Volume spike blocks logged (3–5 expected)
- Cluster score ceiling enforced
- No false positives > 20%

---

### Week 2 (Sep 7–13): High-Impact Optimizations
**Focus:** P1 items that improve win rate

| Day | Task | Bot | Priority |
|---|---|---|---|
| Day 1–2 | ADX Exhaustion Gate implementation | Project | 🟡 P1 |
| Day 2–3 | Conviction Floor Gate implementation | CAB | 🟡 P1 |
| Day 3–4 | ATR Expansion Entry Gate implementation | CAB | 🟡 P1 |
| Day 4–5 | Ghost 202 Session Filter implementation | Ghost | 🟡 P1 |
| Day 5–7 | Monitor and compare vs Week 1 | All | — |

**Success Criteria:**
- All P1 gates active and logging
- Win rate improvement measurable
- False positive rate < 15%
- R-multiples improving

---

### Week 3 (Sep 14–20): Bot-Specific Enhancements
**Focus:** P2 items + bot-specific recommendations

| Day | Task | Bot | Priority |
|---|---|---|---|
| Day 1–2 | Regime Drift Rate implementation | Project | 🟢 P2 |
| Day 2–3 | Cache Freshness Gate implementation | Runner | 🟢 P2 |
| Day 3–4 | CAB regime-specific strategy selection | CAB | 🟢 P2 |
| Day 4–5 | Ghost volume confirmation + ADX protection | Ghost | 🟢 P2 |
| Day 5–7 | Comprehensive performance review | All | — |

**Success Criteria:**
- All P2 items active
- Bot-specific logic validated
- Performance baseline established for comparison
- Knowledge base updated

---

### Week 4 (Sep 21–27): Monitoring & Refinement
**Focus:** Data collection, validation, and refinement

| Day | Task | Bot | Priority |
|---|---|---|---|
| Day 1–3 | Collect full week of data with all KPIs active | All | — |
| Day 3–4 | Analyze KPI effectiveness | All | — |
| Day 4–5 | Refine thresholds based on data | All | — |
| Day 5–7 | Document learnings and update knowledge base | All | — |

**Success Criteria:**
- All KPIs validated with 2+ weeks of data
- Thresholds refined based on actual performance
- Knowledge base comprehensive and current
- Performance improvement documented

---

## 8. Success Metrics & Validation

### Overall System Metrics (Track Weekly)

| Metric | Week 6 Baseline | Target (Week 4) | Measurement |
|---|---|---|---|
| Net P&L | +$29.40 | +$45+ | Weekly total |
| Win Rate | 52% | 60%+ | Winning trades / total trades |
| Avg Winning R | +0.22 | +0.25+ | Average of positive R-multiples |
| Avg Losing R | -0.14 | -0.10+ | Average of negative R-multiples |
| Profit Factor | 1.45 | 1.8+ | Gross profit / gross loss |
| Max Drawdown | $25 | <$15 | Largest equity drop |
| R-Velocity Saves | 0 | 1.5+ R/week | R saved by early exits |
| Blocks Preventing Losses | 0 | 2+ R/week | R avoided by gate blocks |

### Per-Bot Metrics

**SuperTrend/CAB:**
| Metric | Baseline | Target |
|---|---|---|
| Win Rate | 52% | 60%+ |
| Avg R | +0.08 | +0.12+ |
| Grid Win Rate | 62% | 70%+ |
| Continuation Win Rate | 55% | 62%+ |

**Ghost Sniper:**
| Metric | Baseline | Target |
|---|---|---|
| Win Rate | 33% | 50%+ |
| 202 Pattern Win Rate | 33% | 50%+ |
| Net R | -0.84/week | Positive |

**Unified Runner:**
| Metric | Baseline | Target |
|---|---|---|
| Execution Quality Score | Unknown | >80% |
| Cache Freshness | Unknown | >90% fresh |
| Reconciliation Accuracy | Unknown | 100% |

### Validation Checklist (Weekly)

- [ ] R-Velocity early exits triggered? How many? R saved?
- [ ] Volume spike blocks triggered? Would they have lost?
- [ ] Cluster ceiling blocks triggered? Would they have lost?
- [ ] ADX exhaustion blocks triggered? Would they have lost?
- [ ] Conviction floor blocks triggered? Would they have lost?
- [ ] ATR gate blocks triggered? Would they have lost?
- [ ] Ghost session filter blocks triggered? Would they have lost?
- [ ] Win rate improved vs baseline?
- [ ] Avg R improved vs baseline?
- [ ] Max drawdown reduced vs baseline?
- [ ] False positive rate acceptable (<20%)?
- [ ] Any KPI showing negative impact? (Remove or refine)

---

## Appendix: Risk Assessment

### Risks of Implementation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Over-filtering (too many blocks) | Medium | High | Monitor false positive rate, adjust thresholds |
| R-Velocity premature exits | Medium | Medium | Validate with 2+ weeks data, compare to full SL |
| Cluster ceiling too restrictive | Low | Medium | Allow Option B (reduce size) if Option A blocks too many |
| Regime Drift Rate noise | Medium | Low | Use H4 bar timeframe, not M15 |
| Cache freshness too aggressive | Low | Low | Start with 30min threshold, tighten gradually |

### Rollback Plan
- Each KPI can be disabled independently
- Log all KPI decisions (allow/block/reduce) for post-hoc analysis
- If any KPI shows negative impact for 1+ week, disable and investigate
- Maintain baseline comparison data for rollback decisions

---

## Appendix: Dependencies

### Data Requirements
- R-Velocity: Requires R-multiple calculation every cycle (already exists)
- Volume Spike: Requires Vol_Ratio calculation (already exists)
- Cluster Score: Requires portfolio correlation calculation (already exists)
- ADX Exhaustion: Requires ADX_Pctl calculation (already exists)
- Conviction: Requires conviction score from ML model (already exists)
- ATR Expansion: Requires ATR Factor + Delta calculation (need to add Delta)
- Regime Drift: Requires ADX_Pctl history over H4 bars (need to add tracking)
- Cache Freshness: Requires timestamp tracking (need to add)
- Spread Ratio: Requires spread data from broker (need to add)

### Infrastructure Requirements
- No new services required
- All KPIs can be implemented as additional checks in existing watcher threads
- Logging infrastructure already supports required data capture
- Knowledge base updates are documentation only

---

*This plan of action provides a structured approach to implementing the findings from the deep regime intelligence analysis. Each recommendation includes clear success criteria and validation methods. Start with P0 items in Week 1, then progress through P1 and P2 based on observed results.*
