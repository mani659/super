# Observation Window Plan — CAB Standalone

**Effective:** August 30, 2026  
**Duration:** 1–2 weeks (through ~Sep 12, 2026)  
**Phase:** Pure Observation (Incubation Mandate / ADR-003)

---

## 1. Stance

**No parameter changes. No strategy changes. No new filters. No code modifications.**

The bot runs exactly as deployed in v2.1 (August 22) with the v2.1.1 telemetry overlay (August 30). We are collecting data to answer specific questions that require multi-week sample sizes.

---

## 2. What We Are Measuring

Only three metrics matter during this window. Everything else is noise.

### Metric 1: Continuation Winners

**Question:** Does the Continuation vector (ADX 30–60) produce large winners consistently, or was Week 1's +$2,037.86 a one-off outlier?

**What to count:**
- Trades closed by the Continuation vector with R-multiple > +1.5R
- Trades closed by the Continuation vector with P&L > +$800
- Frequency per week (target: at least 1 per week)

**Why it matters:** The entire system's positive expectancy in Week 1 came from a single BTCUSDm trade (+$2,991.96). If large Continuation winners are rare (0–1 per week across 10 pairs), the system relies on outlier capture — which is viable but requires larger drawdown tolerance. If they appear regularly (2+ per week), the edge is structural.

### Metric 2: Inversion + Grid Weekly Drag

**Question:** Is the combined drag from Inversion and Grid manageable, or does it consume all Continuation profits?

**What to count:**
- Net P&L from Inversion vector per week
- Net P&L from Grid vector per week
- Combined weekly drag (Inversion + Grid)

**Why it matters:** In Week 1, Inversion (-$878.84) + Grid (-$1,146.23) = -$2,025.07 drag against +$2,037.86 Continuation profit, leaving only +$639.79 net. If this ratio holds, the system is break-even after costs. The v2.1 H4 EMA filter should reduce Inversion drag; the geometric grid spacing should reduce Grid blowups. We need 2+ weeks to confirm.

### Metric 3: Management Layer Effectiveness

**Question:** Does the Reaper + Protector continue to keep individual losses small?

**What to count:**
- Average loss on Reaper exits (target: < -0.5R)
- Average loss on H1 structural invalidation exits (target: < -0.3R)
- Percentage of trades that hit Protector BE gate (target: > 20%)

**Why it matters:** This is the system's most reliable subsystem. If the management layer degrades (wider average losses, fewer BE gates hit), something structural has changed — regardless of what the entry signals are doing.

---

## 3. What We Are NOT Measuring

These are explicitly out of scope for this window:

- Win rate changes (too noisy at n < 50 per vector)
- Session-level performance (insufficient sample per session)
- Pair-level quality scores (needs n > 10 per pair per vector)
- Spread / slippage impact (telemetry is new, needs accumulation)
- R-velocity / time-to-MFE (telemetry just deployed, needs data)

---

## 4. Decision Gate

At the end of the observation window (~Sep 12), we answer one question:

> **Are large Continuation winners appearing at a rate that justifies the combined Inversion + Grid drag?**

**If YES** (1+ Continuation winner > +1.5R per week, combined drag < Continuation profit):
- Continue the current architecture.
- Begin evaluating v2.1.1 telemetry data for entry quality insights.
- No structural changes needed.

**If NO** (0 large Continuation winners in 2+ weeks, or drag consistently exceeds Continuation profit):
- Reassess the core tri-vector architecture.
- Specific options to evaluate (NOT implement immediately):
  - Reduce Inversion exposure (tighter ADX gate or session restriction)
  - Reduce Grid exposure (lower max layers or wider spacing)
  - Increase Continuation frequency (widen ADX band or add pairs)
- All options require fresh statistical proof before implementation.

---

## 5. Rules During This Window

1. **Zero code changes** to any strategy file (`strat_inversion.py`, `strat_continuation.py`, `strat_grid.py`).
2. **Zero parameter changes** to `config.py` risk percentages, ATR multipliers, or session hours.
3. **Zero new filters or gates** added to any entry or exit path.
4. **Telemetry-only changes** are permitted (v2.1.1 is already deployed).
5. **Weekly review** at end of each trading week — log observations, do not act on them.
6. **Decision gate is a single meeting** at end of window — all options evaluated together, not incrementally.

---

## 6. Data Sources for Weekly Review

| Source | What it provides |
|--------|-----------------|
| MT5 Terminal Report | P&L, trade count, win rate per magic number |
| `trade_context.json` | Entry diagnostics (now includes ADX, DI, session, subtype) |
| `cab_watcher_production.log` | Harvested trade log with enriched R-multiples and exit reasons |
| `docs/week2_performance_summary.md` | Baseline comparison template |

---

*This plan is a measurement protocol, not a strategy document. It defines what to watch, not what to change. All decisions deferred to the gate at end of window.*
