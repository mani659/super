# Session Handoff Document: CAB Standalone (Single Pair)

**Date of Handoff:** September 19, 2026
**Target Audience:** Incoming AI Models / Developers
**Current Phase:** Post-gate measurement continuing; first segment Sep 13–19 net positive (~+$1.4k), Grid-led

---

## 1. Project Overview
The `cab` repository contains a standalone, fully decoupled Inversion and Grid execution engine. It operates on a **different MT5 terminal** and a **different account** than the main `Super` project.

**Current Architecture:**
The bot utilizes a 3-tier ADX dynamic risk system to navigate different market regimes:
- **ADX < 30:** Grid execution logic with strict Min Lot sizing (0.01).
- **ADX 30-60:** Continuation strategy (Dynamic Lot sizing, 1% risk) — **DISABLED** (post-gate plan 13 Sep 2026).
- **ADX > 60:** Volatility strategy (Dynamic Lot sizing, 1% risk).

## 2. Current State & Recent Accomplishments
Post-gate measurement segment 1 (Sep 13–19) produced a net positive week (~+$1,415) driven almost entirely by Grid ADDON legs. Inversion contributed –$134 on 3 EURUSDm trades (all H1_STRUCT_INVALID exits). Continuation entries remained OFF as designed.

Key findings from segment 1:
- Grid ADDON legs (n=4, +$1,432) dominated Grid BASE legs (n=12, +$118).
- Single USDJPY ADX-kill drove –$1,007, confirming grid path risk remains structural.
- No loss caps breached; all management operational.

See `docs/week_postgate_Sep13_19_summary.md` for full segment 1 analysis.

## 3. Active Directives (Do Not Violate)
- **Bot Boundaries Mandate:** Do **NOT** apply V1's `max_lot_demo_cap` or global multi-bot constraints to this bot. It runs a standalone mathematical strategy with its own dynamic balance rules.
- **The Incubation Mandate (ADR-003):** You are strictly prohibited from tweaking code parameters to fit short-term (1-week) variance. We require multiple weeks of uninterrupted telemetry before altering core math. 
- **Post-Gate (active):** Continuation entries DISABLED (magic 9995552). No new Cont entries. Inversion + Grid live and unchanged. See `docs/post_gate_plan.md` for the formal plan.

## 4. Current Directives
- **Post-Gate (active):** Continuation entries DISABLED (magic 9995552). No new Cont entries. Inversion + Grid live and unchanged. See `docs/post_gate_plan.md` for the formal plan.
- **Enhanced Telemetry (v2.1.1 deployed Aug 30):** Trade context now captures ADX, +DI, -DI, H4 EMA, session, and subtype at entry. Grid entries now have notional risk for R-multiple calculation. Harvest log enriched. Zero trading logic changes.
- **M5 LTF Snapshot Telemetry (v2.1.2 deployed Sep 5):** Diagnostic-only. `snapshot_ltf_context()` captures M5 ATR, ATR ratio, swing distance, and structure label at entry. Fields stored in `trade_context.json`. Harvest log includes ATR_Ratio and M5_Struct. Zero trading logic changes.
- **Next measurement window:** 2 calendar weeks from Sep 13 OR 30 closed Inv+Grid trades (whichever later). End-window decision: net≥0 continue; net<0 but controlled → new plan; DD breach → pause.
- **Segment 1 result:** Net +$1,415 (22 closes, 16W/6L). Grid-led. Formal sample still incomplete.

## 5. Immediate Next Steps for Incoming Model
- Verify `ENABLE_CONTINUATION=False` on startup log — confirm no new 9995552 entries are being opened.
- Confirm Inversion (9995551) and Grid (9995553) are still firing and managing normally.
- Confirm loss caps, Protector, Reaper, Harvester are all operational on existing positions.
- Do NOT introduce arbitrary filters, parameter changes, or strategy modifications.
- Track metrics per `docs/post_gate_plan.md` end-window decision table.
- Reference `docs/week_postgate_Sep13_19_summary.md` for segment 1 findings.
- Reference `docs/next_week_plan_standalone.md` for week ahead plan.
