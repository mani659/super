# APEX Research Branch Registry
**Date:** August 31, 2026  
**Status:** All branches DESIGNED — Awaiting Control Authorization  
**Purpose:** Master index of new research branches extending the APEX programme  

---

## Overview

The APEX research programme paused at M43-M50 because M4=0 (no validated economic module). This registry documents four new research branches that bridge from validated M1/M2 scientific primitives to M3/M4 economic candidates, using operational evidence from the live bot system.

### Key Insight

The original APEX programme searched for **new** economic hypotheses from scientific primitives. The new branches search for **modular** economic expressions — using validated primitives as inputs to existing bot systems rather than as standalone strategies.

| APEX Pattern | New Pattern |
|-------------|-------------|
| Primitive → standalone strategy → M4 | Primitive → entry/exit gate → improve existing M4 |
| A002: HIGH_VOL → trade vol directly (FAILED) | RB001: HIGH_VOL → gate entry quality (TO TEST) |
| A004: session → raw breakout (FAILED) | RB002: session scale → adaptive sizing (TO TEST) |
| S006: BOS+OB → standalone M4 (FAILED) | RB003: cross-bot signals → confluence filter (TO TEST) |
| A031: dispersion → standalone exit (FAILED) | RB004: MFE/MAE → regime-conditional exit (TO TEST) |

---

## Branch Summary

| Branch | Question | APEX Source | Bot Source | Gate Type | Status |
|--------|----------|-------------|------------|-----------|--------|
| **RB001** | Can HIGH_VOL regime boundaries improve entry quality? | A001, A007, A008, A010 | F1, F4, F15 | Entry gate | DESIGNED |
| **RB002** | Can session-transition scale improve risk-adjusted returns? | A003, A016, A018, A019 | F5, F7 | Sizing modifier | DESIGNED |
| **RB003** | Does cross-bot signal confluence predict trade quality? | A023, A028, S005-S010 | H6, F6, F13 | Entry gate | DESIGNED |
| **RB004** | Can MFE/MAE regime decomposition inform exit timing? | A010, A008, A001, A007 | BE-lock cohort, B001, F1 | Exit modifier | DESIGNED |

---

## Branch Dependencies and Ordering

```
RB001 (Entry Quality)  ──┐
RB002 (Session Sizing) ──┼──→ RB003 (Cross-Bot Confluence) ──→ RB004 (Exit Intelligence)
                         │         │                                    │
                         │         │                                    │
                         └─────────┴──→ Combined M4 Qualification ────┘
```

**Recommended execution order:**
1. **RB001** first — standalone entry gate, no dependency on other branches
2. **RB002** second — sizing modifier, can run in parallel with RB001
3. **RB003** third — requires trade data from RB001/RB002 execution periods
4. **RB004** last — requires MFE/MAE data from all prior branches' trade history

---

## APEX Primitive Coverage

### Validated Primitives (M1/M2) — All Covered

| Primitive | APEX ID | RB001 | RB002 | RB003 | RB004 |
|-----------|---------|-------|-------|-------|-------|
| HIGH_VOL distributional | A001 | ✅ Primary | — | — | ✅ Regime label |
| Session-transition asymmetry | A003 | — | ✅ Primary | — | — |
| Session-transition LNO 1.65× | A018 | — | ✅ Primary | — | — |
| HIGH_VOL duration predictable | A007 | ✅ Duration overlay | — | — | ✅ Hold time |
| Persistence → forward RV | A008 | ✅ Vol input | — | — | ✅ MFE boundary |
| Extremum boundary | A010 | ✅ Exhaustion gate | — | — | ✅ MFE/MAE |
| SMC BOS+OB gross effect | S005 | — | — | ✅ Confluence input | — |
| Day-block permutation (LNO) | A016 | — | ✅ Validation | — | — |

### Failed Paths — Explicitly Avoided

| Failed Path | APEX ID | Why Avoided | RB001 | RB002 | RB003 | RB004 |
|-------------|---------|-------------|-------|-------|-------|-------|
| HIGH_VOL spot monetization | A002 | Standalone vol trading | ✅ Filter only | — | — | — |
| Session raw breakout | A004 | Direction-based breakout | — | ✅ Sizing only | — | — |
| Cross-asset transmission | A005 | No exploitable effect | — | — | — | — |
| CME listed options | A006 | Method infeasible | — | — | — | — |
| Directional translation | A009 | No directional edge | ✅ Non-directional | ✅ Non-directional | ✅ Non-directional | ✅ Non-directional |
| BOS+OB standalone M4 | S006 | -1347 bps/day | — | — | ✅ Modular only | — |
| CHOCH standalone M3 | S010 | -17 bps net | — | — | ✅ Not used | — |
| Perp funding/carry | A027 | Costs exceed funding | — | — | — | — |
| Dispersion boundary economics | A031 | No standalone edge | — | — | ✅ Modular only | ✅ Modular only |

---

## Resource Requirements

| Branch | Data Required | MT5 Export Needed? | Estimated Analysis Time |
|--------|--------------|--------------------|-----------------------|
| RB001 | 90d M1 OHLCV + all trade fills | Yes (M1 bars) | 2-3 sessions |
| RB002 | 90d M1 OHLCV + all trade fills | Yes (M1 bars) | 1-2 sessions |
| RB003 | All trade fills with timestamps | No (trade_ledger.csv sufficient) | 1-2 sessions |
| RB004 | All trade fills + M1 bars during open trades | Yes (M1 bars for MFE/MAE) | 3-4 sessions |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Insufficient sample size per regime | Medium | High | Pool adjacent regimes; flag n<20 as preliminary |
| Regime classification mismatch with bot's own regime engine | Medium | Medium | Use bot's own regime labels where available; supplement with computed regimes |
| MFE/MAE computation requires M1 data during open trades | Low | High | Cross-reference trade timestamps with M1 export; skip trades with missing M1 data |
| Cost scaling cancels session sizing edge | Medium | Medium | Pre-register cost-scaling concern; measure spread-at-entry by session |
| Cross-bot confluence sample too small | High | Medium | Pool across instruments; flag as preliminary |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | Aug 31 2026 | Initial creation — 4 branches designed |
