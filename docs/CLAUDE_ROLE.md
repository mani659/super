# CLAUDE_ROLE.md — Agent Operating Context

**Version:** v1.1
**Updated:** Sep 12 2026 after first full session

---

## The Three Real Building Opportunities

**1. SuperTrend: Win/Loss Classifier (LOGGING PHASE)**
ENTRY_QUALITY logging deployed W9. cluster_spread, cluster_consensus,
er_at_entry captured at every ST entry. After n≥80/symbol on XAUUSDm
and BTCUSDm, train classifier to separate winning trades from losers
at entry time. If classifier achieves >60% accuracy, wire as entry
quality gate in W11+.

**2. CAB: Immediate Exit + Simplified REAPER (DEPLOYED Sep 12 2026)**
DEPLOYED: IMMEDIATE_EXIT rule exits losing trades within first 2 hours
when R ≤ −0.20 and no prior actions taken.
DEPLOYED: Simplified REAPER — R ≤ −0.50 AND last closed H4 bar against
position direction. Removed 7-condition triple gate that never fired.
NEXT: after W9, analyze IMMEDIATE_EXIT fire rate and average R at exit
vs projected full loss. If −0.20R threshold is too shallow (fires on
normal noise), raise to −0.30R. If too deep (missing fast losses),
lower to −0.15R.

**3. Ghost: Replace the Entry, Not the Gate (LOGGING PHASE)**
DEPLOYED: GHOST_FIRE_QUALITY logs committed_reversal_bars and
trigger_bar_body_ratio at every fire. After W9 and W10 with n≥100
triggers, analyze whether committed_reversal_bars ≥ 2 separates
winners from losers. If yes, wire as the replacement signal in W11.

---

## Open Blocking Items

**P1 [RESOLVED Sep 12 2026]:** SL geometry mismatch — CLOSED.
The 0.35×ATR SL is computed from M1 ATR but the Exness demo
trade_stops_level on XAUUSDm (~100+ points) is wider than 0.35×M1_ATR.
The SL guard in send_order() widens automatically to the broker minimum.
The binding constraint is the broker minimum distance, not the 0.35
multiplier. The observed 1.50×atr_at_fill is correct behavior.
Implication: the audit CSV sl column is the correct risk_dist denominator
for all future R-multiple and BE-lock calculations. The 0.35 multiplier
is effectively inactive on this instrument at this broker. No code change
required. BE-lock cohort analysis is now unblocked — risk_dist from the
sl column, not 0.35×atr_at_fill.
