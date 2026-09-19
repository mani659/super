# RB001 — Volatility-Regime Adaptive Entry Gate
**Research Branch:** RB001  
**Stream:** APEX_BOT_INTEGRATION  
**Date:** August 31, 2026  
**Author:** Salman + Buffy (Codebuff AI)  
**Status:** DESIGNED — Awaiting Control Authorization  
**Parent APEX Artifacts:** A001 (HIGH_VOL primitive), A007 (duration predictability), A008 (persistence→RV), A010 (extremum boundary), A009 (directional rejection)  
**Parent Bot Findings:** F1 (ATR strongest predictor), F4 (ADX dead zone), F15 (H4 direction gate)  

---

## 1. Research Question

**Can the validated HIGH_VOL distributional primitive (A001) and its predicted persistence (A007) be translated into an M3 economic candidate that adaptively gates entry quality across volatility regimes?**

## 2. Scientific Foundation (What APEX Already Validated)

### M1/M2 Primitives Inherited

| Artifact | Primitive | Status | Reuse Role |
|----------|-----------|--------|------------|
| A001 | HIGH_VOL distributional characterization (onset, persistence, tail behavior) | VALIDATED | Defines volatility regime boundaries |
| A007 | HIGH_VOL episode duration predictable out-of-sample via survival/C-index | VALIDATED | Provides conditional duration forecast |
| A008 | Predicted persistence translates to forward realized volatility | VALIDATED | Provides forward vol input for position sizing |
| A010 | Predicted persistence translates to extremum boundary behavior | VALIDATED | Defines expected price excursion limits |
| A009 | Predicted persistence does NOT translate to directional drift | FAILED | **Direction is excluded — non-directional info only** |

### Bot Operational Evidence Inherited

| Finding | Source | Evidence | Status |
|---------|--------|----------|--------|
| F1 | Ghost Grid W4/W6 | ATR is strongest predictor of trade outcome. Q4 high-ATR 57.5% WR vs Q2 low-ATR 27.4% WR | CONFIRMED |
| F4 | Ghost Grid W4 | ADX 20-25 dead zone: n=109, 32.1% WR, -$0.69/trade | CONFIRMED |
| F15 | Ghost Grid W6 | DOWN_PROBE+H4_DOWN 33.9% WR vs UP_PROBE+H4_UP 58.3% WR (24.4pp gap) | IMPLEMENTED |

## 3. Hypothesis

The APEX programme validated that HIGH_VOL episodes have predictable duration (A007) and that persistence translates to forward RV (A008) but NOT to direction (A009). Meanwhile, the live Ghost Grid system confirms ATR is the single strongest predictor (F1) and that ADX 20-25 is a dead zone (F4).

**The gap:** APEX proved the science exists but never connected it to an entry gate. The live bots have ATR/ADX gates that are heuristic (fixed thresholds from operational observation) rather than derived from the validated distributional primitives.

**Hypothesis:** A volatility-regime adaptive entry gate that uses HIGH_VOL distributional boundaries (from A001) rather than fixed percentile thresholds will produce a statistically superior entry quality filter than the current heuristic gates.

## 4. Methodology

### Phase 1: Volatility Regime Classification (M1 Validation)

Using XAUUSD M1 historical data (minimum 90 days):

1. **Define volatility regimes from A001 primitives:**
   - LOW_VOL: Below 25th percentile of rolling realized vol (10-bar, annualized)
   - NORMAL_VOL: 25th–75th percentile
   - HIGH_VOL: Above 75th percentile (the A001 validated primitive)
   - EXTREME_VOL: Above 95th percentile (tail behavior from A001)

2. **Validate regime transitions:**
   - Compute transition probabilities between regimes (P(LOW→HIGH), P(HIGH→EXTREME), etc.)
   - Compute conditional expected duration in each regime (using A007 survival model)
   - Compute conditional expected forward RV from each regime (using A008 translation)

3. **Statistical validation:**
   - Bootstrap test that regime transitions are non-random (vs. i.i.d. null)
   - Test that conditional durations differ across regimes (log-rank test)
   - Test that forward RV differs across regimes (Kruskal-Wallis)

### Phase 2: Entry Quality by Volatility Regime (M2 Characterization)

Using Ghost Grid 202 historical fills (342 trades, 30-day window) and SuperTrend closed trades:

1. **Map each trade entry to its volatility regime at entry time**
2. **Compute per-regime metrics:**
   - Win rate by regime
   - Average R-multiple by regime
   - Expected R (win_rate × avg_win_R - loss_rate × |avg_loss_R|) by regime
   - MFE/MAE distribution by regime
3. **Identify the "sweet spot" regime** where entry quality is maximally positive
4. **Identify regimes where entries should be blocked or size-reduced**

### Phase 3: Adaptive Gate Design (M3 Candidate)

1. **Gate A — Regime Block:** Block entries in EXTREME_VOL regime (A001 tail behavior = unpredictable)
2. **Gate B — Regime Size:** Scale position size by regime:
   - LOW_VOL: 0.5× (insufficient opportunity)
   - NORMAL_VOL: 1.0× (baseline)
   - HIGH_VOL: 1.25× (validated forward RV from A008 supports larger exposure)
3. **Gate C — Duration Overlay:** If predicted HIGH_VOL remaining duration (from A007 model) < X bars, reduce size (regime about to end)
4. **Gate D — Extremum Boundary:** If price is within extremum boundary range (from A010), block new entries (exhaustion zone)

### Phase 4: Economic Qualification (M4 Test)

Apply the adaptive gate to historical trade data and compare:
- **Baseline:** Current heuristic gates (fixed ATR percentile, fixed ADX thresholds)
- **Treatment:** Volatility-regime adaptive gates derived from APEX primitives
- **Metrics:** Expectancy R, Sharpe ratio, max drawdown, win rate
- **Gate criteria:** Treatment must exceed baseline on expectancy R with p < 0.05 (bootstrap 10,000 iterations)

## 5. Expected Outcomes

| Outcome | Decision |
|---------|----------|
| Adaptive gate > baseline on expectancy R (p<0.05) | **M3 CANDIDATE** — proceed to live gate implementation |
| Adaptive gate ≈ baseline (within noise) | **NO IMPROVEMENT** — keep current heuristic gates |
| Adaptive gate < baseline | **REGRESSION** — archive, the primitives don't add economic value at entry |

## 6. Data Requirements

| Data | Source | Minimum | Ideal |
|------|--------|---------|-------|
| XAUUSD M1 OHLCV | MT5 historical export | 90 days | 180 days |
| Ghost Grid 202 trade fills | trade_ledger.csv / brain log | 342 trades (current) | 500+ trades |
| SuperTrend closed trades | trade_ledger.csv | 218 trades (current) | 500+ trades |
| CAB closed trades | trade_ledger.csv | 211 trades (current) | 500+ trades |

## 7. Scope & Constraints

- **Primary instrument:** XAUUSDm (highest data density, most trade history)
- **Extension candidates:** XAGUSDm, BTCUSDm (if primary validates)
- **Direction:** NON-DIRECTIONAL only (A009 eliminated directional exploitation)
- **Regime gate principle:** Gate only blocks entries, never exits (non-negotiable per Master Plan)
- **One variable at a time:** Test regime gate in isolation before combining with F15 or other existing gates

## 8. Relationship to Closed APEX Paths

| Closed Path | Why RB001 Differs |
|-------------|-------------------|
| A002 (HIGH_VOL spot monetization) | A002 tried direct HIGH_VOL trading. RB001 uses HIGH_VOL as an **entry filter**, not a trading signal. |
| A004 (session raw breakout) | A004 tried raw session breakout. RB001 uses volatility regime as a **quality gate**, not a signal source. |
| A011 (dispersion boundary economics) | A011 tested standalone dispersion. RB001 combines dispersion with ATR regime for **composite entry quality**. |
| A009 (directional translation) | A009 proved no directional edge. RB001 explicitly **excludes direction** — non-directional filter only. |

## 9. Deliverables

1. `RB001_Phase1_RegimeClassification.csv` — Regime labels, transition probabilities, conditional durations
2. `RB001_Phase2_EntryQualityByRegime.csv` — Per-regime WR, avg R, MFE/MAE
3. `RB001_Phase3_GateDesign.md` — Final gate parameters and implementation spec
4. `RB001_Phase4_EconomicQualification.md` — Backtest results, statistical evidence, M3/M4 gate decision
5. `RB001_RESULT.md` — Final adjudication document

## 10. Evidence Ledger Entry

| Field | Value |
|-------|-------|
| record_id | RB001 |
| research_stream | APEX_BOT_INTEGRATION |
| milestone | RB001 |
| artifact_type | experiment_report |
| research_question | Can HIGH_VOL regime boundaries improve entry quality over heuristic ATR gates? |
| information_type | Volatility regime entry gate |
| economic_status | NO_ECONOMIC_TEST (at design stage) |
| evidence_class | HYPOTHESIS |
| status | DESIGNED |
| scope | XAUUSD entry quality filtering |
| reuse_allowed | PRESERVED AS BACKGROUND ONLY |
| reuse_condition | REQUIRES NEW ECONOMIC HYPOTHESIS (until M3 gate passed) |
| related_artifacts | A001; A007; A008; A010; A009; F1; F4; F15 |
| auditability | AUDITED |
