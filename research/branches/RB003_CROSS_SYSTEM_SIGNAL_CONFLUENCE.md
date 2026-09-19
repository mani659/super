# RB003 — Cross-System Signal Confluence Quality
**Research Branch:** RB003  
**Stream:** APEX_BOT_INTEGRATION  
**Date:** August 31, 2026  
**Author:** Salman + Buffy (Codebuff AI)  
**Status:** DESIGNED — Awaiting Control Authorization  
**Parent APEX Artifacts:** A023 (SMC integration), A028 (M50 bot observations), S005 (BOS+OB gross +1.01 bps), S006 (BOS+OB M4 failed), S010 (CHOCH M3 failed), A005 (cross-asset rejected)  
**Parent Bot Findings:** H6 (ST LONG + Ghost 202 SELL = 32.4% WR), H9/F9/F10 (direction bias refuted in ranging), F13 (ST positive expectancy), F15 (H4 direction gate)  

---

## 1. Research Question

**When multiple independent bot systems generate conflicting or converging signals on the same instrument at the same time, does signal confluence (or divergence) predict trade outcome quality — and can this be exploited as an entry quality gate?**

## 2. Scientific Foundation (What APEX Already Validated)

### M1/M2 Primitives Inherited

| Artifact | Primitive | Status | Reuse Role |
|----------|-----------|--------|------------|
| A023 | SMC research workstream integrated into APEX | INTEGRATED | SMC event detection machinery available |
| A028 | Bot observations classified A/B/C/D, none promoted to VALIDATED | OBSERVED | Bot-level observations need statistical validation |
| S005 | BOS+OB gross effect: +1.01 bps/event (descriptive, not economic) | VALIDATED (M2) | Gross signal exists but needs economic framing |
| S006 | BOS+OB M4 qualification FAILED: mean daily Tier-2 payoff -1347.31 bps | FAILED | Standalone BOS+OB is uneconomic — need different expression |
| S010 | CHOCH M3 FAILED: net -17.03 bps | FAILED | Standalone CHOCH is uneconomic |

### Bot Operational Evidence Inherited

| Finding | Source | Evidence | Status |
|---------|--------|----------|--------|
| H6 | Ghost Grid W4 | When SuperTrend has active LONG on XAUUSD AND Ghost 202 fires SELL: 32.4% WR, 3× worse per-trade P&L (n=34) | CONFIRMED |
| F6 | Ghost Grid | GHOST_ARM_BLOCKED_ST_LONG gate implemented | IMPLEMENTED |
| F15 | Ghost Grid W6 | DOWN_PROBE+H4_DOWN vs UP_PROBE+H4_UP: 24.4pp WR gap | IMPLEMENTED |
| F13 | SuperTrend W3-W6 | 4 consecutive positive weeks | CONFIRMED (Gate 3 ST PASSED) |
| APEX M50 | Bot observation scoring | Best candidate "Execution-State" scored 34/50 — no candidate cleared M3 gate | All M50 candidates were overlays of nonexistent M4 base |

### The APEX M50 Problem (Why RB003 Exists)

A028/M50 scored 6 candidates (/60) and found that "all leading candidates are overlays of nonexistent M4 base." The programme was paused because M4=0. **RB003 attacks this from a different angle:** instead of searching for new M4 modules, it tests whether the **existing** M3/M4 systems (SuperTrend, CAB, Ghost 202) produce better outcomes when their signals are combined or when they conflict.

The insight from H6 is critical: **cross-bot signal conflict (ST LONG + Ghost 202 SELL) predicts poor outcomes.** This is a negative confluence finding. RB003 systematically tests both positive and negative confluence.

## 3. Hypothesis

Three independent trading systems (SuperTrend, CAB, Ghost 202) fire on the same instrument with different timeframes and logics. When they agree (confluence), trade quality should be higher. When they disagree (divergence), trade quality should be lower.

**Hypothesis A (Confluence):** Trades entered when ≥2 systems agree on direction have higher expectancy R than single-system trades.

**Hypothesis B (Divergence):** Trades entered when an active position in the OPPOSITE direction exists on the same instrument (cross-bot divergence) have lower expectancy R — and blocking these entries would improve portfolio performance.

**Hypothesis C (Sequential):** The *order* in which signals arrive matters. A trend-following signal (ST) that arrives *after* a mean-reversion signal (Ghost 202) may indicate regime transition — the second signal is more informative than the first.

## 4. Methodology

### Phase 1: Signal Timing Overlap Analysis (M2 Characterization)

Using all bot trade histories (Ghost, SuperTrend, CAB):

1. **For each XAUUSD trade across all bots:**
   - Record exact entry timestamp (to the second)
   - Record active positions in other bots at that moment
   - Record direction of each active position
2. **Define confluence categories:**
   - **SOLE:** Only one bot has an active position on XAUUSD at entry time
   - **CONFLUENT:** At least one other bot has an active position in the SAME direction
   - **DIVERGENT:** At least one other bot has an active position in the OPPOSITE direction
   - **H6-DIVERGENT:** Specifically ST LONG + Ghost 202 SELL (the H6 pattern)
3. **Compute per-category metrics:**
   - Win rate
   - Average R-multiple
   - Expectancy R
   - MFE (max favorable excursion)
   - MAE (max adverse excursion)
   - Hold time distribution

### Phase 2: Confluence Quality Test (M3 Candidate)

1. **Statistical comparison:**
   - Kruskal-Wallis test across confluence categories for R-multiple distribution
   - Pairwise Mann-Whitney U tests (SOLE vs CONFLUENT, SOLE vs DIVERGENT)
   - Effect size (Cohen's d) for each comparison
2. **Sample size adequacy:**
   - Current total trades: Ghost 342 + ST ~218 + CAB ~211 = ~771
   - With 4 confluence categories, need ~30 per category minimum
   - If insufficient, pool across instruments (add XAGUSD, BTCUSD)
3. **Regime interaction:**
   - Test if confluence quality differs by regime (RANGING vs TRENDING vs EXHAUSTION)
   - Prior H6 finding was regime-specific (refuted in ranging by H9) — validate systematically

### Phase 3: Divergence Blocking Gate (M3 Candidate)

1. **Define the gate:** Before any new entry on instrument X:
   - Check if any other bot has an active position on X in the OPPOSITE direction
   - If yes: **block the entry** (divergence gate)
2. **Backtest the gate:**
   - Apply to all historical trades
   - Compare portfolio performance with and without the gate
   - Key metrics: total R saved by blocked trades vs R lost from missed winners
3. **Sensitivity analysis:**
   - Vary the definition of "active position" (same direction? same regime? same timeframe?)
   - Vary the blocking window (block only if divergence < 1 hour old? < 4 hours? < 24 hours?)

### Phase 4: Economic Qualification (M4 Test)

1. **Gate criteria:** Divergence blocking must:
   - Improve expectancy R by ≥ 0.05 (absolute)
   - Block trades with < 40% win rate (high false-negative tolerance)
   - Not reduce total trade count by > 30% (maintain statistical power)
2. **Cost sensitivity:**
   - Each blocked trade saves spread + slippage costs
   - Quantify the cost savings from avoided trades

## 5. Expected Outcomes

| Outcome | Decision |
|---------|----------|
| DIVERGENT trades significantly worse than SOLE (p<0.05) | **M3 CANDIDATE** — implement cross-bot divergence gate |
| CONFLUENT trades significantly better than SOLE (p<0.05) | **M3 CANDIDATE** — implement confluence sizing bonus |
| No significant difference across categories | **NO EDGE** — cross-bot signals are independent, no confluence value |
| DIVERGENT trades better than SOLE | **REVERSAL** — divergence is contrarian signal (unlikely but possible) |

## 6. Special Considerations

### Architecture Constraint (Non-Negotiable)

Per Master Plan Section 6: "Bots inform each other; they do not command each other's exits. Cross-bot signals gate entry arming only."

RB003's divergence gate is an **entry gate only** — it blocks new entries when divergence is detected. It NEVER closes or modifies existing positions based on cross-bot signals. This complies with the non-negotiable principle.

### Temporal Challenge

The three bots operate on different timeframes:
- Ghost 202: M1 (fires every ~minutes)
- SuperTrend: M30 (fires every ~30 minutes)
- CAB: H4 (fires every ~4 hours)

Confluence measurement must account for timeframe mismatch. A "concurrent" signal might mean within the same H4 bar (CAB's resolution), not the same second.

### Current Data Limitation

With ~771 total trades, per-category sample sizes may be small. The research must report exact n per category and flag any comparison with n < 20 as underpowered.

## 7. Data Requirements

| Data | Source | Minimum | Ideal |
|------|--------|---------|-------|
| All bot trade entries with timestamps | trade_ledger.csv | Current (~771) | 1500+ |
| Active position snapshots per bot | trade_ledger.csv (entry/exit times) | Derived from above | Real-time position state |
| Regime labels at entry time | trade_ledger.csv regime column | Partial | Full |
| Symbol and direction per trade | trade_ledger.csv | Yes | Yes |

## 8. Relationship to Closed APEX Paths

| Closed Path | Why RB003 Differs |
|-------------|-------------------|
| A005 (cross-asset transmission) | A005 tested volatility transmission across different assets. RB003 tests signal confluence on the **same** asset across different systems. |
| S006 (BOS+OB M4 failed) | S006 tried BOS+OB as standalone economic module. RB003 uses SMC events as **inputs to a confluence filter**, not as standalone signals. |
| S010 (CHOCH M3 failed) | S010 tried CHOCH standalone. RB003 doesn't use CHOCH — it uses the **existing bot systems** as confluence sources. |
| A028 (M50 candidates overlay) | A028 found candidates were "overlays of nonexistent M4 base." RB003 tests whether combining **existing M4-qualifying systems** (ST passed Gate 3) produces value. |

## 9. Deliverables

1. `RB003_Phase1_SignalOverlap.csv` — Per-trade confluence classification
2. `RB003_Phase2_ConfluenceQuality.csv` — Per-category R, WR, MFE/MAE
3. `RB003_Phase3_DivergenceGateBacktest.md` — Gate performance, sensitivity analysis
4. `RB003_Phase4_EconomicQualification.md` — Final economic test
5. `RB003_RESULT.md` — Final adjudication document

## 10. Evidence Ledger Entry

| Field | Value |
|-------|-------|
| record_id | RB003 |
| research_stream | APEX_BOT_INTEGRATION |
| milestone | RB003 |
| artifact_type | experiment_report |
| research_question | Does cross-bot signal confluence/divergence predict trade outcome quality? |
| information_type | Cross-system confluence gate |
| economic_status | NO_ECONOMIC_TEST (at design stage) |
| evidence_class | HYPOTHESIS |
| status | DESIGNED |
| scope | XAUUSD cross-bot signal quality |
| reuse_allowed | PRESERVED AS BACKGROUND ONLY |
| reuse_condition | REQUIRES NEW ECONOMIC HYPOTHESIS (until M3 gate passed) |
| related_artifacts | A023; A028; S005; S006; S010; H6; F6; F13 |
| auditability | AUDITED |
