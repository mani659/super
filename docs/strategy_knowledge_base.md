---

# Strategy Knowledge Base

**Last Updated:** Sep 9 2026

---

## Module Vision and Research Agenda (Aug 31 2026)

### Architecture Decision: Regime-Conditional Module Portfolio

Established Aug 31 2026 after 6 weeks of live statistical analysis.

The system architecture is a regime-conditional strategy portfolio.
Each module is designed for a specific market condition window.
No module is all-weather. The system's collective edge comes from
regime coverage, not from any single strategy's performance.

This decision was reached after observing that:
- F2 (NY_OVERLAP+H4_DOWN best combo) completely inverted W4→W6
- F4 (ADX dead zone) completely inverted W4→W6
- F7 (NY_CLOSE+H4_UP worst combo) completely inverted W4→W6
- Ghost 202 shows 66.7% WR in TRENDING_DOWN+H4_UP but near-breakeven
  in RANGING — the same entry pattern has radically different
  expectancy depending on regime context

No strategy is locked in. Modules that lose their statistical
edge across regime shifts are retired. New modules are added when
the data identifies uncovered opportunity.

### M5 Research Agenda (H21)

**Motivation:** When CAB fires an H4 inversion entry, the
subsequent M5 price action in the first 5-25 minutes is the
earliest observable confirmation or rejection of the trade thesis.
M5 is not currently logged or analyzed for any module.

**The hypothesis:** M5 structure at the moment of H4 inversion
entry predicts whether the trade will succeed. Specifically:
- If M5 is already moving in the direction of the H4 inversion
  when CAB fires, the trade has micro-structure alignment
  (H4 and M5 in agreement) → higher probability of success
- If M5 is still moving against the H4 inversion direction
  when CAB fires, the entry is premature — H4 has inverted but
  M5 has not confirmed → lower probability of success

**Four fields to log at every CAB entry:**

  m5_close_direction (str): "UP" or "DOWN"
    Last completed M5 bar close direction.
    UP = close > open. DOWN = close < open.
    Fetch: copy_rates_from_pos(symbol, TIMEFRAME_M5, 1, 1)
    Use bar[0] (index 1 = last closed M5 bar)

  m5_atr (float): M5 ATR(14) at entry time
    Local M5 volatility context.
    Fetch: copy_rates_from_pos(symbol, TIMEFRAME_M5, 0, 20)
    Compute: Wilder ATR(14) on that data
    Purpose: normalize M5 body size by local volatility

  m5_body_ratio (float): last M5 bar body/range ratio, 0.0-1.0
    body = abs(close - open)
    range = high - low (replace 0 with 0.0001 to avoid div/0)
    ratio = body / range
    High ratio (>0.6) = strong directional bar
    Low ratio (<0.3) = indecision / noise bar

  m5_bars_in_direction (int): consecutive M5 bars in same
    direction as the H4 inversion entry direction
    CAB BUY entry → count consecutive bullish M5 bars (close>open)
    going backward from last closed bar
    CAB SELL entry → count consecutive bearish M5 bars
    Stop counting when direction breaks
    Range: 0 (last bar against entry), 1, 2, 3...
    Higher count = more M5 momentum confirmation

**Where to log:**
cab_watcher.py manage_fluid_logic(), in the section where a
new position is first detected (ticket not in processed_actions).
At that moment, fetch M5 data and write a log line:

  logger.info(
    f"M5_CONTEXT #{pos.ticket} | "
    f"symbol={pos.symbol} | "
    f"m5_dir={m5_close_direction} | "
    f"m5_atr={m5_atr:.5f} | "
    f"m5_body={m5_body_ratio:.3f} | "
    f"m5_bars_in_dir={m5_bars_in_direction}"
  )

**What we are looking for after n≥50:**
  - Does m5_close_direction matching entry direction predict
    better WR? (e.g. BUY entry + last M5 bar bullish → higher WR)
  - Does m5_body_ratio > 0.5 at entry predict better WR?
  - Does m5_bars_in_direction ≥ 2 predict better WR?
  - Is there an interaction: H4=UP + M5 bullish + m5_body>0.5
    that produces a notably high WR subset?

**If patterns confirmed:**
  Application 1 — CAB entry gate: only fire H4 inversion when
  M5 structure aligns (m5_close_direction matches entry direction
  AND m5_body_ratio > threshold).

  Application 2 — Ghost pre-arming: when M5 shows developing
  exhaustion pattern (m5_bars_in_direction ≥ 3 opposing the H4
  trend), Ghost arms a probe in the reversal direction before the
  CAB H4 inversion signal fires. Earlier entry, smaller SL,
  captures more of the move.

  Application 3 — New magic number: if M5 pre-arming produces
  meaningfully different outcomes from both Ghost 202 (different
  timeframe and SL) and CAB (different entry timing), it warrants
  its own magic number (205 is the natural next), its own audit
  log column set, and its own watcher personality. It is not a
  modification of 202 or CAB — it is a new module in the M5-H4
  cross-timeframe window.

**Magic number 205 reserved for M5-H4 cross-timeframe module.**
Not assigned until shadow validation confirms the module warrants
independent tracking. The number is reserved to prevent future
conflicts with expanding SuperTrend or CAB magic assignments.

### Research Priority Tiers

**Tier 1 — Active data collection (Week 8 implementation)**

| ID | Research Item | Code Required | Target n | Status |
|----|--------------|---------------|----------|--------|
| H21 | M5 structure at CAB H4 inversion entry | 4 fields added to cab_watcher.py manage_fluid_logic() new position detection | 50 CAB entries | ACTIVE Week 8 — logging live. Verify M5_CONTEXT lines in cab_watcher.log by Day 1. |
| F-A3 | Session boundary standardisation — get_session() as canonical definition | Analysis task only. Document get_session() hours as single source of truth: LONDON 8-12 UTC, NY_OVERLAP 12-16 UTC, NY_CLOSE 16-21 UTC, ASIAN 21-8 UTC. Re-run A016/A018 permutation under these hours before H22 gate is designed. | Pre-W9 | REQUIRED before H22 gate wiring — Sep 9 2026 |
| F-A2 | Arm-time H4 direction cohort — recompute from ARMED rows | Extract ARMED event rows from logs/sniper_hunter.log. Join to ORDER_FILL_V51 rows within 45s. Compute H4=DOWN vs H4=UP WR and avg P&L at arm-time. Compare to fill-time numbers. | Pre-W9 | REQUIRED before B1b trigger decision — Sep 9 2026 |

Tier 1 reasoning: H21 requires one data fetch per new CAB position, produces four logged fields, and is the prerequisite for H19 analysis. It is implemented alongside Phase B1b in Week 8 — two code tasks, both small.

**Tier 2 — Dependent on Tier 1 data (earliest Week 10)**

| ID | Research Item | Dependency | Target n | Status |
|----|--------------|------------|----------|--------|
| H19 | Trend Exhaustion Reversal M4 — compare hypothetical H4 entry price to CAB entry price | H21 logging must be active for 50+ entries | 50 CAB entries with M4 conditions logged | MONITORING — zero code until H21 produces n≥50 |

Tier 2 reasoning: H19 analysis requires M5 data from H21 to be meaningful. Cannot evaluate M4 entry timing without knowing the M5 structure at each CAB entry. Start analysis earliest Week 10, more likely Week 11.

**Tier 3 — Pure observation, no code, longest timeline**

| ID | Research Item | Code Required | Observation Period | Status |
|----|--------------|---------------|--------------------|--------|
| H20 | London Open Range-Break Fade — observe Asian range high/low vs London Open price action | None — manual or log review only | 4+ weeks of pattern observation | MONITORING — lowest priority. Note: London Open being negative for existing modules does NOT confirm a fade pattern works. This must be observed independently. |

Tier 3 reasoning: H20 is the most speculative. It requires no code and no weekly action beyond noting London Open behavior during end-of-week reviews. If a clear pattern emerges after 4 weeks of observation, it gets upgraded to Tier 2 with a data collection plan. If no pattern is visible, it stays here indefinitely with no resource cost.

**Pipeline upgrade rules:**
- Tier 3 → Tier 2: pattern visually consistent across 4+ weeks of manual observation AND theoretically grounded mechanism identified
- Tier 2 → Tier 1: n≥50 logged events showing directional signal worth investigating with dedicated code
- Tier 1 → Candidate Module: 100+ shadow fills with positive avg P&L across two distinct market regimes (Section 0.2 requirements)
- Candidate Module → Active: all 6 Module Addition Protocol requirements satisfied (Section 9.6 in roadmap.md)

---

## Two-Month Retrospective Analysis — Scheduled Sep 12 2026

**Context:** Week 8 marks two calendar months since the first clean data
collection began (post-MPE-fix, post-SL-fix, W3 onward). The prior analysis
methodology has been weekly subsets — comparing W6 to W7, W4 to W6, etc.
This approach is vulnerable to regime-contamination of individual weeks.
The two-month retrospective is the first analysis that spans the full clean
period and looks at structural patterns rather than weekly variance.

**Why now:** Three conditions are met simultaneously for the first time:
1. MarketPulseEngine confirmed operational since Aug 26 — all KR Layer 0
   data reliable from that date onward.
2. Ghost SL at 0.35×ATR stable since July — consistent mechanical environment.
3. F5 (CAB London gate) and F15 (Ghost DOWN_PROBE gate) both live — the
   system is in its most gated state to date, and the unfiltered baseline
   from W3–W6 can be contrasted with the gated period W7–W8.

**Seven analysis targets (in priority order):**

1. **Ghost session breakdown all-time (H22 definitive evaluation)**
   All-time Ghost 202 matched fills W3–W8 (target n≥700) broken down by
   get_session() session tag. This is the first multi-regime sample large
   enough to give H22 a reliable confidence interval. The question is not
   just direction (ASIAN positive, NY negative — already observed twice)
   but stability: is the gap consistent across sub-periods with different
   macro Gold direction?
   Output: session × sub-period cross-tab. If ASIAN consistently positive
   and NY consistently negative in each sub-period, H22 confirmation is
   structural not regime-conditional.

2. **Ghost H4 direction arm-time cohort (F-A2 resolution)**
   First-ever arm-time H4 measurement. Extracted from ARMED rows joined
   to fills within COOLDOWN_SECONDS (45s). Compare arm-time cohort WR to
   the fill-time cohort that produced the W6 B1b pre-approval.
   Output: arm-time H4=DOWN vs H4=UP WR and avg P&L, W3–W8 combined.
   This either validates or invalidates the B1b trigger criterion.

3. **SuperTrend symbol fit matrix — Gate 5 pre-lock**
   Per-symbol total closed trades, WR, avg P&L, and positive-week count
   across W3–W8. First time n per symbol is sufficient for preliminary
   Gate 5 assessment. Target: any symbol with n≥20 and two consecutive
   negative weeks is a config switch candidate. Any symbol with n≥20 and
   consistent positive avg P&L is a Gate 5 lock candidate.
   Output: bot-instrument fit table with full W3–W8 data.

4. **CAB trajectory — OSI, MFE/MAE, and BUY/SELL gap**
   CAB all-time closed trades W3–W8 segmented by: (a) exit mechanism
   (OSI vs SL vs Harvester vs Protector), (b) BUY/SELL direction per week,
   (c) MFE distribution (how far did winning trades run vs how far did
   losing trades go against before closing).
   Output: CAB structural profile. Does the BUY/SELL gap show a converging
   trend (regime-specific) or persistent gap (structural)?

5. **BE-lock cohort at current parameters (F-A4 measurement)**
   First measurement of BE-lock change impact. What fraction of W7–W8 fills
   never reached +1.0R (current threshold) vs W1's 41.5% that never reached
   +0.5R (old threshold)?
   Output: BE-lock cohort split (reached vs never reached +1.0R). If the
   fraction dying before +1.0R is materially higher than W1's 41.5%,
   the parameter needs review. If lower, the wider SL (0.35×ATR) is
   compensating for the higher BE-lock threshold.

6. **Cross-bot equity attribution**
   Weekly P&L contribution by bot (Ghost 202, SuperTrend, CAB) from W3–W8.
   Visualise as stacked bar per week. Is Ghost's drag trend improving,
   flat, or worsening? Has CAB stabilised as a positive contributor? Has
   SuperTrend's streak ended or is W7 a one-week anomaly?
   Output: 6-week attribution table. Basis for Phase D sequencing decision.

7. **Adaptive threshold verification (F-A1)**
   Read is_adaptive and rev_adx_block from adaptive_thresholds_live.csv
   at the time of W8 extraction. Record. Check if the log history contains
   any is_adaptive=1 records. If the adaptive mechanism has been dormant
   throughout W3–W8, all analysis should be re-labelled: "collected under
   static gates ADX<40, conviction<60" — which is actually cleaner for
   analysis purposes than an adaptive gate.

**Files required (collect Sep 12 before analysis session):**
```
sniper_v51_live_audit.csv          — full W3–W8, all rows
MT5 HTML export                     — Jul 1 – Sep 12 2026, all magic numbers
logs/sniper_hunter.log (+ rotations)— for ARMED rows (F-A2 arm-time H4)
logs/cab_watcher.log                — W8 M5_CONTEXT lines (H21 count)
logs/kpi_ledger.csv                 — full period equity curve
logs/adaptive_thresholds_live.csv   — is_adaptive + rev_adx_block current
logs/trade_excursions.csv           — MFE/MAE all bots
```

**Expected outputs from retrospective:**
- H22 confirmation or extended-observation verdict (3 weeks consistent = confirmed)
- B1b arm-time trigger criterion (replaces fill-time criterion)
- ST Gate 5 pre-lock list (symbols ready to lock vs symbols to continue collecting)
- CAB BUY/SELL gap verdict (converging = regime-conditional; persistent = structural)
- BE-lock parameter verdict (1.0R justified vs needs review)
- Ghost drag trajectory (improving vs flat vs worsening across W3–W8)
- Adaptive gate status (dormant vs active)
