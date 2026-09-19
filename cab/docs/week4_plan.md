# Week 4 Plan — CAB Standalone

**Period:** September 6 – September 12, 2026  
**Phase:** Final week of Observation Window (Incubation Mandate / ADR-003)  
**System Version:** v2.1.2 (M5 LTF snapshot telemetry active)

---

## 1. Stance

**No parameter changes. No strategy changes. No new filters. No code modifications.**

This is the final week of the observation window. The decision gate is at ~Sep 12. Week 4 continues collecting data for the three core metrics and adds optional LTF structural analysis as a new data dimension.

---

## 2. Core Metrics (Unchanged from Observation Plan)

Only three metrics matter. Everything else is noise.

### Metric 1: Continuation Winners

**Question:** Does the Continuation vector (ADX 30–60) produce large winners consistently?

**What to count:**
- Trades closed by the Continuation vector with R-multiple > +1.5R
- Trades closed by the Continuation vector with P&L > +$800
- Frequency per week (target: at least 1 per week)

### Metric 2: Inversion + Grid Weekly Drag

**Question:** Is the combined drag from Inversion and Grid manageable?

**What to count:**
- Net P&L from Inversion vector per week
- Net P&L from Grid vector per week
- Combined weekly drag (Inversion + Grid)

### Metric 3: Management Layer Effectiveness

**Question:** Does the Reaper + Protector continue to keep individual losses small?

**What to count:**
- Average loss on Reaper exits (target: < -0.5R)
- Average loss on H1 structural invalidation exits (target: < -0.3R)
- Percentage of trades that hit Protector BE gate (target: > 20%)

---

## 3. New Data Dimension: M5 LTF Structure (Observation Only)

v2.1.2 deployed on Sep 5. New entries from Week 4 onward will carry M5 microstructure data in `trade_context.json`.

### New Fields

| Field | Description |
|-------|-------------|
| `m5_atr` | M5 ATR(14) at entry time |
| `atr_ratio` | m5_atr / h4_atr — captures intraday vs macro volatility ratio |
| `m5_dist_to_swing_atr` | Distance from nearest M5 swing in ATR units (direction-aware) |
| `m5_structure` | Position label: `AT_OR_ABOVE_HIGH`, `NEAR_HIGH`, `MID_RANGE`, `NEAR_LOW`, `AT_OR_BELOW_LOW` |

### What We Can Optionally Tabulate at End of Week

**Still observation only — no filters, no strategy changes.**

- Large Continuation winners (R > +1.5R) vs M5 structure at entry
  - Did winners tend to fire from `MID_RANGE` or `NEAR_LOW` (bullish) vs `NEAR_HIGH` (already extended)?
- Inversion winners vs M5 structure
  - Did mean-reversion entries that fired from `AT_OR_ABOVE_HIGH` (bearish) outperform those from `MID_RANGE`?
- ATR ratio distribution across vectors
  - Is there a clustering of `atr_ratio` values that correlates with win/loss?

**Decision gate still evaluates the three core metrics above. LTF structure is supplementary context only.**

---

## 4. Data Sources for Weekly Review

| Source | What it provides |
|--------|-----------------|
| MT5 Terminal Report | P&L, trade count, win rate per magic number |
| `trade_context.json` | Entry diagnostics (ADX, DI, session, subtype + new M5 fields) |
| `cab_watcher_production.log` | Harvested trade log with R-multiples, exit reasons, ATR_Ratio, M5_Struct |
| `docs/week2_performance_summary.md` | Baseline comparison template |

### Practical Checklist

- [ ] Confirm `trade_context.json` is writing `m5_structure` and `atr_ratio` on new entries
- [ ] At end of week: tabulate large winners vs M5 structure (observation only)
- [ ] At end of week: note any patterns in `atr_ratio` across win/loss groups
- [ ] Final decision gate at ~Sep 12: evaluate all three core metrics together

---

## 5. Decision Gate Reminder

At the end of the observation window (~Sep 12), we answer one question:

> **Are large Continuation winners appearing at a rate that justifies the combined Inversion + Grid drag?**

**If YES:** Continue current architecture. Begin evaluating v2.1.2 LTF data for entry quality insights.  
**If NO:** Reassess tri-vector architecture. All options require fresh statistical proof before implementation.

No strategy changes during Week 4. All decisions deferred to the gate.

---

*This plan is a measurement protocol, not a strategy document. It defines what to watch, not what to change.*
