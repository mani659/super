# Session Handoff Document: CAB Multi-Pair Master

**Date of Handoff:** 19 Sep 2026
**Target Audience:** Incoming AI Models / Developers
**Current Phase:** LTF research logging ongoing; week Sep 13–19 net ≈ –$324; LiqSweptPrior all-zero; no live filters

---

## 1. Project Overview
The `cab_multi_pair` repository operates an independent, standalone MetaTrader 5 bot designed to run across 11 different currency/commodity pairs simultaneously. It shares its architectural roots with the CAB strategy but functions entirely separately from both the `Super` monolith and the single-pair `cab` bot.

**Core Philosophy:** 
This engine is built as a data-collection and management-experiment engine. It is currently running a controlled demo experiment: splitting management thresholds by volatility group to test whether LOW-vol FX pairs improve without harming HIGH-vol outlier capture.

## 2. Current State & Recent Accomplishments
Week Sep 13–19 produced n=45 closes, net ≈ –$324 (improved from –$929 prior week but still negative). LTF structure research logging deployed and working — all three flags (liq_swept_prior, fvg_with_signal, dist_next_pool_atr) populate on new entries. LiqSweptPrior is all-zero (telemetry issue to diagnose). No live filters promoted from LTF data — Phase 3 threshold not met.

Key findings: BROKER_SL cohort (n=12, –$584, avgR –0.75R) is the primary loss driver. BE_Hit trades net +$504 vs non-BE trades net –$791. Management split dominates outcomes.

See `docs/week_Sep13_19_summary.md` for full week analysis.

## 3. Active Directives (Do Not Violate)
- **Bot Boundaries Mandate:** Never mix patches from `Super` (V1/V2) or the standalone single-pair `cab` bot into this repository. This system operates its own execution lifecycle and has its own risk constraints.
- **Demo Experiment Lock:** No entry signal changes, no ADX/session hard filters, no PARTIAL_R execution, no pair removals during the experiment week. Observation-layer logging only.
- **Data over Speculation:** Do not attempt to tweak logic, SL distances, or logic filters based on short-term winning or losing streaks. Any future trade filters must be translated directly from data science reviews, not speculative hypotheses.
- **LTF Research Lock:** No entry filters from LTF flags until Phase 3 threshold met (≥80 closes or 4 weeks from 13 Sep). LiqSweptPrior treated as broken until diagnostic fix.
- **Independent audit 20 Sep 2026 reviewed.** No code this week. See `docs/audit_response_Sep20.md`.

## 4. Current Configuration Summary

| Parameter | HIGH (BTC, ETH, XAU, XAG, USTEC, USOIL) | LOW (EURUSD, GBPUSD, USDJPY, EURGBP, AUDNZD) |
|-----------|------------------------------------------|-----------------------------------------------|
| BE_GATE_R | 0.5 | 0.5 |
| LOCK_GATE_R | 1.0–1.5 (per-pair) | 0.8 |
| H1_MIN_HOURS | 6.0 | 12.0 |
| RISK_PERCENT | 0.5–1.0 (per-pair, unchanged) | 1.0 |
| ATR_MULT_SL | 2.5–3.0 (per-pair, unchanged) | 2.5 |

All 11 pairs active. MAGIC_NUMBER = 999555. STAGNATION_HOURS = 24.

## 5. Immediate Next Steps for Incoming Model
- Verify LTF columns (liq_swept_prior, fvg_with_signal, dist_next_pool_atr) appear on new ledger rows.
- Do NOT introduce entry filters from LTF flags — research logging only.
- Confirm loss caps, BE/LOCK management, vol-group thresholds all operational.
- Track n toward Phase 3 threshold (≥80 closes with valid LTF fields or 4 weeks from 13 Sep).
- Reference `docs/week_Sep13_19_summary.md` for week findings.
- Reference `docs/next_week_plan_multipair.md` for week ahead plan.

## 6. Key References
- `docs/week_Sep13_19_summary.md` — Sep 13–19 week analysis
- `docs/next_week_plan_multipair.md` — week ahead plan and success criteria
- `docs/ltf_structure_research_plan.md` — LTF flag research plan
- `docs/decision_log_2026-09-05.md` — vol-group experiment rationale
- `docs/feature_history.md` — v18.7 section for parameter table
- `docs/architecture.md` — 9-module system design
- `docs/week_analysis_history.md` — prior weekly reviews
