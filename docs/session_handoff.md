# Session Handoff Document: Super Bot (V1 / V2)

**Date of Handoff:** August 28, 2026
**Target Audience:** Incoming AI Models / Developers
**Current Phase:** Phase 2 Demo Testing — Week 6/7 Transition

---

## 1. Project Overview
The `Super` root directory houses the unified trading system, running the SuperTrend, Ghost Sniper, and CAB Super bots. 

We currently operate two distinct execution environments that run in parallel:
- **V1 (Live/Hardened):** The primary, monolithic execution environment (`unified_runner.py`). This version contains the proven, mathematical execution edge with all statistical gates hardcoded.
- **V2 (Validation/Shadow):** The newly developed, modularized Data-Bus architecture (`v2_unified_runner.py`, `v2/`). V2 uses a decoupled `KnowledgeRegister`, `MarketOracle`, and `OrderRouter` strictly designed to output deep telemetry for quantitative offline analysis (`v2_trade_ledger.jsonl`).

## 2. Current State & Recent Accomplishments
During this session, we conducted a rigorous quantitative audit and alignment phase between V1 and V2 to ensure they produce identical trade footprints during Week 7. 

**Recent Patches Applied to V2:**
1. **Execution Filters Re-enabled:** `RAW_LOGGING_MODE = False` is hardcoded in V2. V2 now enforces max global positions (15), daily drawdown circuit breakers, and layer 3 correlation buckets identically to V1.
2. **Synchronous Oracle Pulse:** Background threading was removed from the V2 `MarketOracle`. It now calculates H4/M30/M15 regimes synchronously on-tick within `v2_unified_runner.py` (Phase A) to eliminate timing disparities.
3. **Ghost Cache 204:** Tuned `N_LAYERS_DEFAULT = 2` (down from 3) in `ghost_cache.py` to match the W6 tightening.
4. **Nomenclature Parity:** V2 bots were renamed precisely to match V1 (`GhostSniperBot`, `CABSuperBot`).
5. **Cross-Bot F6 Gate:** We mathematically confirmed that both V1 and V2 correctly block Ghost `UP_PROBE` (a SHORT trade) when SuperTrend holds a LONG position, preventing internal conflict.
6. **Week 5 Data Commit (Aug 28):** All W5 log extractions, V2 architecture updates, and W6 Trading Plans were successfully committed to `main` (commit `bad7954`).

## 3. Active Directives (Do Not Violate)
- **Trading System Philosophy (Permanent Rule):** The `KnowledgeRegister` (in both V1 and V2) exists **strictly** to gather and serialize raw logging data for analysis. It must NEVER be used to arbitrarily block or restrict trades based on human liking. Any filters must be statistically informed.
- **Bot Boundaries:** Do NOT mix architectures or configurations between `Super` (V1/V2), `cab/`, and `cab_multi_pair/`. They are strictly independent bots running on different terminals and accounts.

## 4. Immediate Next Steps for Incoming Model
- Monitor the Week 7 parallel run between V1 and V2.
- Verify that V2 generates an identical trade footprint to V1 under live demo slippage conditions.
- Analyze `v2_trade_ledger.jsonl` post-run for edge validation.
- Do NOT apply code changes to V1; V2 is authorized to strictly mirror V1 logic.
