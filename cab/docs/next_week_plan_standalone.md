# Next Week Plan — CAB Standalone

**From:** 19 Sep 2026
**Phase:** Continue post-gate measurement

---

## Rules

- **ZERO trading-logic changes**
- **Cont entries stay OFF** (`ENABLE_CONTINUATION=False`)

## Book

- Magic 9995551 (Inversion) + 9995553 (Grid) only
- No 9995552 (Continuation) entries

## End Window

- 2 calendar weeks from 13 Sep **OR** 30 closed Inv+Grid trades
- Whichever comes later

## Metrics to Track

| Metric | Target / Note |
|--------|---------------|
| Net P&L Inv+Grid | Must be ≥ 0 for "continue" decision |
| Max DD | Must stay within loss-cap thresholds |
| Grid VWAP vs ADX-kill counts and $ | Track whether ADX-kill pattern repeats |
| BASE vs ADDON P&L | Segment 1 showed ADDONs dominant — is this stable? |
| Inv n and $ | Inv was –$134 on 3 trades — does it contribute? |
| Loss-cap hits | Confirm none breached |

## Decision

- Per `docs/post_gate_plan.md` table only
- No discretionary overrides

## Non-Goals (explicitly excluded)

- No Cont re-enable
- No ZR / flip
- No new filters
- No risk% up
- No silent grid redesign mid-window

## Watch Items

- Repeat of USDJPY-class grid kills (single ADX-kill drove –$1,007 in segment 1)
- Whether Grid stays net green without Cont
- Whether Inv contributes positively or remains a drag
