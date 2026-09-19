# RB004 — Exit Intelligence via MFE/MAE Regime Decomposition
**Research Branch:** RB004  
**Stream:** APEX_BOT_INTEGRATION  
**Date:** August 31, 2026  
**Author:** Salman + Buffy (Codebuff AI)  
**Status:** DESIGNED — Awaiting Control Authorization  
**Parent APEX Artifacts:** A010 (extremum boundary), A008 (persistence→RV), A001 (HIGH_VOL), A007 (duration predictability), A031 (dispersion boundary economics — failed)  
**Parent Bot Findings:** BE-lock cohort (94.4% WR if reached +0.5R), B001 (R-Velocity observation), Phase C plan (Market Exit Score v1), Ghost 204 CACHE concept  

---

## 1. Research Question

**Does the distribution of MFE (Maximum Favorable Excursion) and MAE (Maximum Adverse Excursion) differ systematically across volatility regimes and session contexts — and can this decomposition inform optimal exit timing to replace or augment the current R-threshold exit system?**

## 2. Scientific Foundation (What APEX Already Validated)

### M1/M2 Primitives Inherited

| Artifact | Primitive | Status | Reuse Role |
|----------|-----------|--------|------------|
| A010 | Predicted persistence translates to extremum boundary behavior | VALIDATED | Defines expected MFE/MAE boundaries per regime |
| A008 | Predicted persistence translates to forward RV | VALIDATED | Forward vol informs expected price excursion |
| A001 | HIGH_VOL distributional characterization | VALIDATED | Regime classification for MFE/MAE decomposition |
| A007 | HIGH_VOL episode duration predictable | VALIDATED | Timing exit based on predicted regime duration |
| A031 (M31) | Dispersion boundary economics NOT monetizable as standalone | FAILED | **Standalone dispersion exit doesn't work — must be modular** |

### Bot Operational Evidence Inherited

| Finding | Source | Evidence | Status |
|---------|--------|----------|--------|
| BE-lock cohort | Week 1 Ghost Grid (n=2,458) | Reached +0.5R: n=1,438, WR 94.4%, P&L +$2,239. Never reached: n=1,020, WR 0.5%, P&L -$2,560. 41.5% die before BE-lock. | **CRITICAL STRUCTURAL FINDING** |
| B001 (R-Velocity) | Week 6 ops observation | Trades that go negative within 30 min of entry have 75% chance of being losers. Current SL loses ~0.18R. Early exit at -0.05R saves ~0.13R. | OBSERVED (not validated) |
| Phase C plan | Master Plan v1.2 | Market Exit Score v1: regime alignment 30%, conviction trend 25%, ATR trajectory 20%, OSI 15%, R-velocity 10%. MES < 0.30 = exit. | PLANNED |
| Ghost 204 concept | Ghost Cache architecture | Exhaustion entry at nth virtual layer: requires $5 move + $2.50 retrace in 5 min. 1 fire in 30 days. | FAILED to fire (parameter issue) |
| F1 | Ghost Grid W4/W6 | ATR is strongest predictor. Q4 high-ATR 57.5% WR vs Q2 low-ATR 27.4% WR. | CONFIRMED |

### The Core Problem RB004 Addresses

The current exit system across all bots is primarily R-threshold based:
- Ghost 202: TP at 1.5R, SL at 0.35×ATR, BE-lock at 1.0R
- SuperTrend: R-lock ratchet (+1R→BE, +2R→lock 1R, +3R→lock 2R)
- CAB: PROTECTOR at 1.2R, HARVESTER at 2.0R

The BE-lock cohort finding shows this is deeply suboptimal: **94.4% of trades that reach +0.5R are winners, but 73% of all trades are capped at scratch by the one-shot BE-lock.** The exit system is destroying the upside of winning trades while the downside of losing trades is fully realized.

The Master Plan already plans a "Market Exit Score" for Phase C. RB004 provides the **empirical foundation** for that score by decomposing MFE/MAE by regime and session, rather than building MES from first principles.

## 3. Hypothesis

**Hypothesis A (Regime-Dependent MFE):** The maximum favorable excursion achievable by a trade depends on the volatility regime at entry. HIGH_VOL regimes produce higher MFE but also higher MAE. Optimal exit should be regime-conditional, not fixed.

**Hypothesis B (Session-Dependent MFE):** MFE distributions differ by session due to the validated scale component (A018: LNO 1.65× more dispersed). Trades entered during LNO should have wider MFE distributions — and tighter trailing stops may prematurely exit profitable trades.

**Hypothesis C (Duration-Dependent MFE):** The predicted remaining HIGH_VOL duration (A007) correlates with how long a trade should be held. Trades entered early in a HIGH_VOL episode should be held longer than trades entered late.

**Null Hypothesis:** MFE/MAE distributions do NOT differ systematically across regimes, sessions, or durations. Current R-threshold exits are already optimal.

## 4. Methodology

### Phase 1: MFE/MAE Data Collection (M1 Baseline)

Using all bot trade histories:

1. **For every closed trade across all bots, compute:**
   - MFE in R-multiple units (max favorable price excursion / entry risk)
   - MAE in R-multiple units (max adverse price excursion / entry risk)
   - Time-to-MFE (how many bars from entry to peak favorable excursion)
   - Time-to-MAE (how many bars from entry to peak adverse excursion)
   - Regime at entry (RANGING/TRENDING/EXHAUSTION from regime engine)
   - Session at entry (ASIAN/LONDON/NY_OVERLAP/NY_CLOSE)
   - Bot identity (Ghost/SuperTrend/CAB)
   - Final R-multiple at exit
2. **Classify trades by their MFE/MAE profile:**
   - **Deep MAE, Recovered:** MAE > 1.0R, but final R > 0 (trade survived deep drawdown)
   - **Shallow MAE, Died:** MAE < 0.5R, final R < 0 (trade died without deep drawdown — SL was too tight or entry was wrong)
   - **MFE Captured:** MFE within 20% of final R (trade captured most of its potential)
   - **MFE Wasted:** MFE > 1.5× final R (trade gave back significant profit before exit)

### Phase 2: MFE/MAE Decomposition by Regime (M2 Characterization)

1. **Per-regime MFE/MAE distributions:**
   - Plot MFE distributions (box plots or violin plots) by regime
   - Compute per-regime MFE percentiles (25th, 50th, 75th, 90th)
   - Compute per-regime MAE percentiles
   - Compute per-regime "MFE capture ratio" = final_R / MFE (how much of potential was captured)
2. **Statistical tests:**
   - Kruskal-Wallis for MFE distribution differences across regimes
   - Kruskal-Wallis for MAE distribution differences across regimes
   - Dunn's post-hoc test for pairwise regime comparisons
3. **Session decomposition:**
   - Repeat above by session instead of regime
   - Test interaction: regime × session on MFE/MAE
4. **Duration analysis:**
   - For trades in HIGH_VOL regime: correlate time-to-MFE with predicted remaining episode duration (from A007)
   - Test if early-in-episode trades have longer MFE development time

### Phase 3: Optimal Exit Rule Derivation (M3 Candidate)

1. **Current exit analysis:**
   - For each trade, compute: at what R-multiple did the trade peak (MFE)?
   - What percentage of trades reached +0.5R, +1.0R, +1.5R, +2.0R before exiting?
   - What was the R-multiple at the time of the current exit rule (TP, BE-lock, etc.)?
2. **Regime-conditional optimal exit:**
   - **RANGING regime:** MFE distribution likely tighter → tighter TP appropriate
   - **TRENDING regime:** MFE distribution likely wider → wider TP or trailing stop appropriate
   - **HIGH_VOL regime:** MFE distribution widest → longest hold appropriate
3. **Proposed exit rules by regime:**
   - RANGING: TP at 1.0R (conservative — tight MFE distribution), BE-lock at 0.5R
   - TRENDING: TP at 2.0R (progressive — wide MFE distribution), trailing at 1.5R behind MFE
   - HIGH_VOL: TP at 3.0R (aggressive — A008 predicts forward RV supports wider excursion), trailing at 2.0R behind MFE
   - EXHAUSTION: TP at 0.75R (quick profit capture), tight BE-lock at 0.3R
4. **R-velocity integration (from B001):**
   - If R-velocity negative for 6+ consecutive cycles AND trade is in EXHAUSTION regime: exit immediately (regime supports deterioration)
   - If R-velocity negative for 6+ cycles AND trade is in TRENDING regime: hold (trend may resume)

### Phase 4: Economic Qualification (M4 Test)

1. **Apply regime-conditional exit rules to historical data**
2. **Compare vs current exit rules:**
   - Expectancy R
   - Sharpe ratio
   - MFE capture ratio (should improve — capturing more of each trade's potential)
   - Max drawdown
   - Win rate (may change — some TP exits replaced by trailing)
3. **Critical test:** The regime-conditional system must not increase max drawdown by > 20% (downside protection is non-negotiable)
4. **Statistical evidence:**
   - Paired bootstrap (10,000 iterations) comparing regime-conditional vs fixed exits
   - Permutation test for Sharpe ratio difference

## 5. Expected Outcomes

| Outcome | Decision |
|---------|----------|
| Regime-conditional exits > fixed exits on Sharpe (p<0.05) AND MFE capture improves | **M3 CANDIDATE** — proceed to live exit implementation |
| Regime-conditional exits ≈ fixed exits | **NO IMPROVEMENT** — current exits are approximately optimal |
| Regime-conditional exits increase max drawdown > 20% | **DOWNSIDE RISK** — exit intelligence hurts risk profile |
| MFE capture ratio is already > 80% across all regimes | **NO WASTE** — current exits capture most potential, limited room for improvement |

## 6. Special Considerations

### Connection to Master Plan Phase C

RB004 directly feeds into the planned "Market Exit Score v1" (Phase C, Weeks 9-11). The MES plan uses 5 components: regime alignment (30%), conviction trend (25%), ATR trajectory (20%), OSI (15%), R-velocity (10%). RB004 provides the empirical basis for:
- **Regime alignment weight (30%):** Derived from per-regime MFE distributions
- **ATR trajectory weight (20%):** Derived from HIGH_VOL persistence predictions (A007)
- **R-velocity weight (10%):** Derived from B001 operational observation

### Ghost 204 Insight

The Ghost 204 CACHE concept (exhaustion entry at nth virtual layer) was essentially trying to capture MFE at the peak of an exhaustion move. It failed to fire because the parameter window was too narrow (5 minutes, $5 move). RB004's MFE analysis may reveal that exhaustion MFEs are captured better by the existing 202 REVERSAL entry with a regime-conditional TP, rather than the complex 204 architecture.

### Data Quantity Concern

With ~771 total trades, regime-specific MFE/MAE analysis may be underpowered. RB004 must report exact n per regime per bot and flag comparisons with n < 20 as preliminary.

## 7. Data Requirements

| Data | Source | Minimum | Ideal |
|------|--------|---------|-------|
| All bot trades with entry/exit prices and times | trade_ledger.csv | Current (~771) | 1500+ |
| High-frequency price data during open trades | MT5 M1 export (same periods as trades) | Required for MFE/MAE computation | Yes |
| Regime labels at entry time | trade_ledger.csv + regime engine | Partial | Full |
| Session labels at entry time | trade_ledger.csv session column | Yes | Yes |

**Critical data requirement:** MFE/MAE computation requires access to M1 price data during the period each trade was open. This means cross-referencing trade open/close timestamps with M1 OHLCV data to find the high/low during the holding period.

## 8. Relationship to Closed APEX Paths

| Closed Path | Why RB004 Differs |
|-------------|-------------------|
| A010 (extremum boundary) | A010 characterized boundaries theoretically. RB004 measures **actual MFE/MAE in live bot trades** and tests regime-conditional exit rules. |
| A031 (dispersion boundary economics) | A031 tested standalone dispersion exit. RB004 tests **modular exit modification** within existing exit architecture. |
| A009 (directional rejected) | A009 confirmed no directional edge. RB004 is **direction-agnostic** — MFE/MAE is symmetric for BUY and SELL. |
| A002 (HIGH_VOL monetization) | A002 tried to trade HIGH_VOL directly. RB004 uses HIGH_VOL as a **regime label for exit optimization**, not a trading signal. |

## 9. Deliverables

1. `RB004_Phase1_MFE_MAE_Raw.csv` — Per-trade MFE, MAE, time-to-MFE, time-to-MAE
2. `RB004_Phase2_RegimeDecomposition.csv` — Per-regime MFE/MAE distributions, percentiles
3. `RB004_Phase3_OptimalExitRules.md` — Regime-conditional exit rule specification
4. `RB004_Phase4_EconomicQualification.md` — Backtest comparison, statistical evidence
5. `RB004_RESULT.md` — Final adjudication document

## 10. Evidence Ledger Entry

| Field | Value |
|-------|-------|
| record_id | RB004 |
| research_stream | APEX_BOT_INTEGRATION |
| milestone | RB004 |
| artifact_type | experiment_report |
| research_question | Can regime-decomposed MFE/MAE analysis inform optimal exit timing? |
| information_type | Exit intelligence regime decomposition |
| economic_status | NO_ECONOMIC_TEST (at design stage) |
| evidence_class | HYPOTHESIS |
| status | DESIGNED |
| scope | XAUUSD exit optimization across all bots |
| reuse_allowed | PRESERVED AS BACKGROUND ONLY |
| reuse_condition | REQUIRES NEW ECONOMIC HYPOTHESIS (until M3 gate passed) |
| related_artifacts | A010; A008; A001; A007; A031; BE-lock_cohort; B001; F1 |
| auditability | AUDITED |
