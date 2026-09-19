# Session Handoff Document: Super Bot (V1 / V2)

**Date of Handoff:** Sep 12, 2026
**Target Audience:** Incoming AI Models / Developers
**Current Phase:** Week 9 — Entry Quality Data Collection + Research Logging

---

## 1. Project Overview
The `Super` root directory houses the unified trading system, running the SuperTrend, Ghost Sniper, and CAB Super bots.

Two execution environments run in parallel:
- **V1 (Live/Hardened):** Monolithic execution (`unified_runner.py`). All statistical gates hardcoded. Account 474167713.
- **V2 (Validation/Shadow):** Modular Data-Bus architecture (`v2_unified_runner.py`, `v2/`). Outputs deep telemetry to `v2_trade_ledger.jsonl`.

## 2. Current State (Sep 12 2026)

**Week 8 Actuals:**
- Equity $6,504.41, week P&L −$166.05, max DD −35.0%
- Ghost: 132 fills, SuperTrend: 67 at 37.3% WR, CAB: 58 at 18.1% WR (BUY collapse to 10.0%)

**P1 Resolved (Sep 12):** SL geometry mismatch — CLOSED.
The 0.35×ATR SL is computed from M1 ATR but broker trade_stops_level (~100+ points) is wider. The SL guard widens automatically to broker minimum. Observed 1.50×atr_at_fill is correct behavior. The audit CSV `sl` column is the correct `risk_dist` denominator for all R-multiple and BE-lock calculations. BE-lock cohort analysis now unblocked.

**Three Building Opportunities (Deployed Sep 12):**

1. **SuperTrend: Win/Loss Classifier (LOGGING PHASE)**
   ENTRY_QUALITY logging deployed W9. cluster_spread, cluster_consensus, er_at_entry captured at every ST entry. After n≥80/symbol on XAUUSDm and BTCUSDm, train classifier. If >60% accuracy, wire as entry quality gate in W11+.

2. **CAB: Immediate Exit + Simplified REAPER (DEPLOYED)**
   IMMEDIATE_EXIT exits losing trades within first 2 hours when R ≤ −0.20 and no prior actions. Simplified REAPER: R ≤ −0.50 AND last closed H4 bar against position. Removed 7-condition triple gate that never fired. Post-W9: analyze fire rate and adjust thresholds.

3. **Ghost: Replace the Entry, Not the Gate (LOGGING PHASE)**
   GHOST_FIRE_QUALITY logs committed_reversal_bars and trigger_bar_body_ratio at every fire. After W9–W10 with n≥100 triggers, analyze whether committed_reversal_bars ≥ 2 separates winners. If yes, wire as replacement signal in W11.

**W8 Audit Findings (F-A1–F-A6):**
- F-A1: Adaptive ADX likely inert
- F-A2: h4_direction_at_arm is fill-time not arm-time
- F-A3: 3 session definitions coexist
- F-A4: BE-lock threshold unvalidated at 1.0R
- F-A5: Magic 204 doc error
- F-A6: F6 drag estimate overstated

**B1b Permanently Closed:** Three-regime H4 inversion n=834, Obs_WinRate 48.9%. Not worth reopening.

## 3. Active Directives (Do Not Violate)
- **Bot Boundaries:** Never mix architectures between `Super` (V1/V2), `cab/`, and `cab_multi_pair/`. Strictly independent.
- **Trading System Philosophy (Permanent):** The KnowledgeRegister exists strictly to gather raw logging data. Never block trades based on human liking. Filters must be statistically informed.
- **No V1 code changes** without explicit user request.

## 4. Immediate Next Steps for Incoming Model
- Run W9 data collection (Entry Quality logging, GHOST_FIRE_QUALITY).
- Monitor for n≥80 ST entries and n≥100 Ghost triggers.
- Post-W9: analyze P1 resolution impact on BE-lock cohort stats.
- Do NOT apply code changes to V1 unless explicitly requested.

## 5. Key References
- `docs/MASTER_DEVELOPMENT_PLAN.md` — v1.6, Week 9 task board
- `docs/roadmap.md` — v20, W8 row, F-A findings
- `docs/todo_tracker.md` — v21, Week 9 active tasks
- `docs/CLAUDE_ROLE.md` — v1.1, building opportunities, P1 resolved
- `docs/strategy_knowledge_base.md` — H21 ACTIVE, retrospective
- `docs/system_changelog.md` — Sep 9 entry
- `docs/GHOST_SNIPER_RESEARCH_CONTROL_AUDIT.md` — 717-line control audit
