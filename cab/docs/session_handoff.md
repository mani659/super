# Session Handoff Document: CAB Standalone (Single Pair)

**Date of Handoff:** August 30, 2026
**Target Audience:** Incoming AI Models / Developers
**Current Phase:** Observation Window (Week 3+) — Pure Data Collection, Enhanced Telemetry Active

---

## 1. Project Overview
The `cab` repository contains a standalone, fully decoupled Inversion and Grid execution engine. It operates on a **different MT5 terminal** and a **different account** than the main `Super` project.

**Current Architecture:**
The bot utilizes a 3-tier ADX dynamic risk system to navigate different market regimes:
- **ADX < 30:** Grid execution logic with strict Min Lot sizing (0.01).
- **ADX 30-60:** Continuation strategy (Dynamic Lot sizing, 1% risk).
- **ADX > 60:** Volatility strategy (Dynamic Lot sizing, 1% risk).

## 2. Current State & Recent Accomplishments
During Week 2, a significant statistical anomaly was uncovered: Long positions generated a massive edge (64.5% win rate), while Short positions severely underperformed (33.3% win rate) because they were executed during macro bullish trends on Gold and Oil without directional bias gates. 

To resolve this, the following architectural updates were applied:

1. **H4 Macro Trend Filter:** Added vectorized `get_h4_macro_trend()` in `cab/shared_utils.py` and implemented it in `cab/strat_inversion.py`. Inversion sequences (F9/F10) are now completely blocked from firing against the prevailing 50-EMA H4 trend.
2. **Behavioral Pacing (Grid Spacing):** Added geometric expansion to `cab/strat_grid.py`. Subsequent grid levels now dynamically expand their spacing based on an exponent of the level depth.
3. **The 30-60 ADX Bracket (Untouched):** `cab/strat_continuation.py` generated $2,037.86 net profit in Week 1. This file has been **strictly locked and left untouched** to continue validating its edge in W2/W3.

## 3. Active Directives (Do Not Violate)
- **Bot Boundaries Mandate:** Do **NOT** apply V1's `max_lot_demo_cap` or global multi-bot constraints to this bot. It runs a standalone mathematical strategy with its own dynamic balance rules.
- **The Incubation Mandate (ADR-003):** You are strictly prohibited from tweaking code parameters to fit short-term (1-week) variance. We require multiple weeks of uninterrupted telemetry before altering core math. 

## 4. Current Directives
- **Observation Window (active):** No code changes, no parameter changes, no new filters. See `docs/observation_window_plan.md` for the formal measurement plan.
- **Enhanced Telemetry (v2.1.1 deployed Aug 30):** Trade context now captures ADX, +DI, -DI, H4 EMA, session, and subtype at entry. Grid entries now have notional risk for R-multiple calculation. Harvest log enriched. Zero trading logic changes.
- **Decision Gate:** At end of observation window (~Sep 12), evaluate whether Continuation winners justify Inversion + Grid drag.

## 5. Immediate Next Steps for Incoming Model
- Verify the bot is running and heartbeat is active on the standalone terminal.
- Confirm `trade_context.json` is being written with the new v2.1.1 fields (adx, plus_di, minus_di, ema50, session, subtype) on the next closed trade.
- Do NOT introduce arbitrary filters, parameter changes, or strategy modifications.
- Log weekly observations in `docs/week2_performance_summary.md` (template) at end of each trading week.
