# Next Week Plan — CAB Multi-Pair

**From:** 19 Sep 2026
**Phase:** Continue LTF structure research logging (Phase 2)

---

## Rules

- **ZERO entry-logic changes**
- **ZERO new live filters from LTF flags**
- No ZR, no signal flip, no ATR-breakout live
- Audit 20 Sep: no code this week; C1 restart R-quality and C3/C4 clocks noted as deferred risks.

## Keep

- Loss caps
- Half-risk
- XAG 0.5%
- Vol-group management (BE_GATE_R, LOCK_GATE_R, H1_MIN_HOURS split)

## Research

- Keep logging LiqSweptPrior, FvgWithSignal, DistNextPoolAtr on every new entry
- Treat LiqSweptPrior as broken/uninformative until diagnostic fix (telemetry-only)

## End Window

- ≥80 closed trades with valid LTF fields **OR** 4 weeks from 13 Sep
- Whichever comes later

## Analysis at End Window

| Analysis | What to compute |
|----------|-----------------|
| E[R] and E[$] by FvgWithSignal | Fvg=1 vs Fvg=0 expectancy |
| E[R] and E[$] by DistNextPoolAtr bins | <0.1 ATR vs 0.1–0.3 vs >0.3 |
| BE_Hit split | Trades that reach BE vs those that don't |
| Session analysis | Which sessions produce best/worst expectancy |
| Symbol analysis | Per-pair breakdown |

## Optional (only if operator explicitly enabled)

- Pause EURGBP new entries as risk throttle
- Document if used — do not apply silently

## Non-Goals (explicitly excluded)

- No ZR
- No signal flip
- No ATR-breakout live
- No copying standalone Grid
- No Cont-style regime stack on this bot

## Success Criteria

- Clean ledger rows with LTF columns populated
- Enough n for holdout comparison (≥80 closes)
- No mid-window strategy edits
