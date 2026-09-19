# CAB Standalone — Post-Gate Measurement Segment 1: Sep 13–19 2026

**Date:** 19 Sep 2026
**Account:** 262924445 (standalone MT5 terminal)
**Phase:** Post-gate measurement (first segment)

---

## Context

- Post-gate plan effective 13 Sep 2026: `ENABLE_CONTINUATION=False`; manage_continuation still runs; Inv (9995551) + Grid (9995553) live.
- Startup log confirmed: `"CONTINUATION ENTRIES DISABLED (post-gate plan 13 Sep 2026) | manage_continuation still active"`
- No CONTINUATION ENTRY lines on/after 13 Sep.

---

## Results (MT5 account 262924445 — ground truth)

| Metric | Pre-gate (Aug 30–Sep 12) | Post-gate (Sep 13–19) |
|--------|--------------------------|------------------------|
| Closed trades | n≈47 | n=22 |
| Net P&L | ≈ –$1,965 | ≈ **+$1,415** |
| Winners / Losers | — | 16 / 6 |

Harvest log aligns (~+$1,415 on 19 tagged harvest rows).

---

## Vector Breakdown (trade_excursions / harvest subtypes)

### GRID (BASE + ADDON): n=16, net ≈ +$1,549

| Subtype | n | Sum | Avg R | Avg MAE | MFE Capture |
|---------|---|-----|-------|---------|-------------|
| GRID_BASE | 12 | ≈ +$118 | ≈ +0.02 | ≈ –$358 | ≈ 56% |
| GRID_ADDON | 4 | ≈ +$1,432 | ≈ +0.43 | — | 100% |

**Exits:**
- 15× GRID_VWAP_TARGET (sum ≈ +$2,556)
- 1× GRID_KILL_ADX35 (USDJPY ≈ –$1,007, ≈ –1.20R, MAE ≈ –$1,019, duration ≈ 12h)

### INV_EXH_SELL: n=3 (all EURUSDm), net ≈ –$134

- All exits: H1_STRUCT_INVALID
- Management cut small; entry not proven

### CONT: no new entries

---

## Path / Risk Observations

- **Grid path pain large:** sum MAE on grid legs ≈ –$4.9k vs realized ≈ +$1.5k
- **Grid economics dominated by ADDON legs**, not BASE
- **Risk_amount** generally ~$820–850 (~1% equity); one residual GBP base with tiny risk_amount
- **USDJPY GRID_BASE** never logged an addon; ADX path 27.7 → kill at 35.9; design dead-band 30≤ADX≤35 blocks addons but not open risk
- **No evidence loss caps failed this week** (USDJPY loss below 2% symbol cap on ~$83k equity)

---

## What Did NOT Change

- No Cont re-enable
- No Inv/Grid parameter changes
- No new filters
- No ZR/flip

---

## Interpretation (honest)

- Removing Cont coincides with a green week; Grid was the profit engine; Inv not the payday
- One week ≠ locked edge; single large ADX-kill shows grid path risk remains structural
- Formal sample (2 weeks or 30 closes from Sep 13) still incomplete

---

## Decision Window

- **End window:** 2 calendar weeks from Sep 13 OR 30 closed Inv+Grid trades, whichever later
- **Decision criteria:** per `docs/post_gate_plan.md` table only
- **Current status:** Segment 1 of 2 complete (or segment 1 of N if 30-close threshold not yet met)
