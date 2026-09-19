# Control Session — V1 Audit Supplement & Combined Findings
**Date:** Sep 9 2026
**Author:** Buffy (Codebuff AI) — independent second-pass audit
**Status:** READ-ONLY audit. No code changed, no documentation updated (this report is new).
**Addendum (Sep 9 evening):** Section 7 added — cross-bot W7 drill (cab / cab_multi_pair / cab_super) cab_super-specific recommendations.

---

## Purpose

This document consolidates everything from the independent second-pass audit of Super V1
for the control session. It contains:

1. A **verification verdict** on the original `GHOST_SNIPER_RESEARCH_CONTROL_AUDIT.md`
2. **New findings the original audit missed** (code-verified, data-consistent, or flagged for verification)
3. **Corrections to the original audit** (where its claims are wrong or overstated)
4. **Assessment of the external LLM review** shared during the session
5. **Consolidated action items** requiring control-session decisions

Method: direct source reading of ghost_sniper.py (1,005 lines), sniper_watcher.py (1,310),
ghost_cache.py (400), supertrend_bot.py (2,021), cab_watcher.py, cab_entry.py,
shared_intelligence.py, knowledge_register.py, plus MDP v1.4, roadmap.md, todo_tracker.md,
UNIFIED_BOT_CONTEXT.md, GHOST_GRID_ANALYSIS_AUG31.md, log_extract_full data, and all four
research branches (RB001–RB004, REGISTRY.md).

---

## 1. Executive Verdict on the Original Audit

**The original audit is high quality and largely trustworthy.** Its source reconstruction
(Section 2) is accurate on every claim independently re-verified:

- SL multiplier 0.35×ATR (`SCALP_REV_SL_ATR_MULT = 0.35`, ghost_sniper.py:145)
- SPREAD_MAX 1.5, COOLDOWN 45s, MAX_LEGS 1, ATR step ×1.0
- BE_LOCK_R = 1.0, raised from 0.5 ("Change 9", sniper_watcher.py:151)
- HARD_FAILSAFE_TP_R = 2.0 (OOB = broker failsafe, not "TP hit")
- Conviction = ADX×1.0 + M1-body-ratio×0.5, capped 100 (sniper_watcher.py:268–270)
- `_get_h4_direction()` = close(rates[-2]) vs close(rates[-4]) — 12-hour slope proxy,
  explicitly "not a regime classifier"
- Magic 201 fires `is_shadow=True` → VIRTUAL_FILL → **no audit CSV row by construction**
  (is_shadow path returns before `log_event()`). The 828/0 finding is structurally guaranteed.
- RAW_LOGGING_MODE = True bypasses KR Layer 2/3 (knowledge_register.py:12)
- N_LAYERS lowered 3→2 (ghost_cache.py:111)
- LEG_TP_BY_MAGIC: 201=1.0R, 202=1.5R, 204=2.0R
- Grid: TP 1.0R / STOP −3.0R / PROT 0.35R / 72h age cap
- Regime gate blocks TRENDING_UP/DOWN/UNKNOWN at arming; F6 and F15 wiring confirmed
- 30-day session distribution (ASIAN 459 / LONDON 86 / NY_OVERLAP 104 / NY_CLOSE 135)
  matches `log_extract_full/summary.json` exactly
- BE_LOCK fires: 117, all magic 202 — matches summary.json
- W4 confounded (0.2×ATR SL, dead MPE, N_LAYERS=3) vs W6/W7 clean — confirmed by project history

**The central thesis is correct:** H4 direction as implemented is a displacement proxy,
not a structural trend classifier, which is why it inverts week-to-week. The W7 inversion
is predictable from the implementation, not a market anomaly.

**But the audit missed six findings and contains two factual errors.** Sections 2–4 below.

---

## 2. New Findings — NOT in the Original Audit

### F-A1. The "adaptive" ADX gate is likely INERT — the deployed gate is the static 40

**Evidence (data-consistent, needs one verification):**
- The audit (Ambiguity D) and the external LLM review both warn about the self-loosening
  P70-adaptive `rev_adx_block`. **But the 30-day data contradicts the mechanism being active.**
- `log_extract_full/summary.json`: adx_at_fill for magic 202 = avg 19.26, **max 39.43**;
  conviction max **59.75**. Both sit *just under* the static blocks (40 / 60).
- If `rev_adx_block` were truly P70 of the last 60 minutes of ADX (typically ~28–32 on a
  7–39 distribution), fills with ADX 33–39 would have been blocked. They were not.
- `conviction max 59.75 < 60` is the same signature.

**Conclusion:** `read_adaptive_thresholds_hunter()` is almost certainly returning the
hardcoded default (`rev_adx_block=40.0, is_adaptive=0`) — either the watcher's
`compute_adaptive_thresholds()` never writes `adaptive_thresholds_live.csv` where the
hunter reads it, or the file's `is_adaptive` flag is 0.

**Why this matters:**
- The self-loosening paradox is currently **theoretical, not operational**.
- The gate that actually ran was a **fixed ADX<40 + conv<60 filter**.
- Ambiguity D is a verification task first, a design concern second.

**Verification (no code change):** check `is_adaptive` + `rev_adx_block` in
`adaptive_thresholds_live.csv` at the next log extraction.

---

### F-A2. `h4_direction_at_arm` is a misnomer on fill rows — it's computed at FILL time

**Evidence (code-verified):**
- In `send_order()`, the ORDER_ERROR path (line ~539) and ORDER_FILL_V51 path (line ~615)
  both call `_get_h4_direction()` **inside send_order — i.e., at trigger/fill time** —
  and store it in a column named `h4_direction_at_arm`.
- Only the ARMED rows (lines ~798, ~823) contain true arm-time values.

**Consequences:**
1. The W6/W7 H4=UP/DOWN cohort analyses — the basis for F15 and the B1b trigger — were
   computed on **fill-time H4 direction**, not arm-time H4.
2. The original audit's Ambiguity L says "the audit CSV only logs H4 direction at arming,
   not at trigger." **It is the opposite:** fills carry trigger-time H4 (mislabeled), and
   arm-time H4 exists only on ARMED rows, which are not joined to outcomes.
3. Since probes can track for minutes and an H4 bar can close mid-probe, fill-time ≠
   arm-time. **B1b gates at arming; the evidence that justified it was measured at fill.**
   The gate's input variable and the analysis variable are different points in time.

**Action:** recompute W6/W7 H4 cohorts using ARMED rows (true arm-time H4) joined to
fills, or at minimum label existing cohort numbers as fill-time. **Prerequisite for
trusting the B1b trigger at W9.**

---

### F-A3. Three different session definitions coexist — H22's evidence and gate use different hours than RB002's validated primitives

| Source | ASIAN | LONDON | NY_OVERLAP | NY_CLOSE | Other |
|---|---|---|---|---|---|
| `ghost_sniper.get_session()` (audit CSV tags) | 21–8 | 8–12 | 12–16 | 16–21 | — |
| `shared_intelligence` MPE (KR session field) | 0–6 | 7–12 | 13–16 | 17–20 | OFF_HOURS 21–23 |
| RB002 research (validated A003/A016/A018) | 0–7 | 7–12 | 12–17 | 17–0 | — |

**Why this matters:**
- The H22 analysis (W7 sessions) used `get_session()` boundaries (8–12 LONDON,
  12–16/16–21 NY).
- RB002 — the branch whose validated primitives (A016 day-block permutation p=0.0001,
  A018 LNO 1.65× dispersion) give H22 its theoretical backbone — uses **different
  boundaries** (7–12 LONDON, 12–17/17–0 NY).
- A day-block permutation test run on one session grid does not transfer to another grid.
- If the H22 gate is implemented with `get_session()` hours (correct for the CSV data),
  it is testing a different session construct than the APEX evidence claims to support.

**Action:** standardize ONE session definition (recommend `get_session()`, since that is
what the CSV uses) and re-run the A016/A018-style permutation under it before using A018
to justify H22 sizing or gating.

---

### F-A4. BE-lock threshold moved 0.5R→1.0R WITHOUT re-measuring the largest dataset in the project

**Evidence:**
- The n=2,458 W1 cohort (94.4% WR once +0.5R reached; 41.5% died before it) is **the
  biggest sample in the project** — yet it lives only in UNIFIED_BOT_CONTEXT.md and RB004,
  **not in the findings registry**.
- It was measured at **BE_LOCK_R=0.5, SL=0.2×ATR**. Both parameters have since changed
  (SL→0.35, BE→1.0R, Change 9). The cohort numbers describe a system that no longer
  exists, and **no re-measurement at the new thresholds exists**.
- RB004's own Phase 3 recommends "RANGING: BE-lock at 0.5R" — contradicting live 1.0R.

**The de-facto A/B test we already ran:**
- V2 (0.5R BE-lock) vs V1 (1.0R) — same week, same market (W7): V2 60.5% WR vs V1 45.2%.
- This is the only evidence at the new architecture — and it was **destroyed as an
  experiment** when V2 was forced to 1.0R for shadow parity.

**Action / decision for control session:** before locking V2 to 1.0R permanently, capture
2–3 weeks of both thresholds. This is a genuinely open, high-value parameter question.

---

### F-A5. Magic 204 has NO trigger-time gates at all — the MDP's "same conditions as 202" is wrong

**Evidence (code-verified):**
- The 204 block (ghost_sniper ~lines 832–857) fires `send_order(..., bs, gates)` where
  `bs` and `gates` are the **arming-time** values — the trigger block's fresh
  `read_brain_state()`/`apply_gates()` happens *after* the 204 block.
- There is **no spread check** on the 204 path (SPREAD_MAX is enforced only inside
  `if trigger:`).
- 204's only gates: regime gate at arming + cache-fire geometry.

**Impact:** with 3 all-time fires this is harmless today. It becomes relevant only if 204
ever scales. The original audit's gate table correctly limits spread to "201+202" but does
not call out that 204 bypasses *all* trigger-time gating and uses stale context.

---

### F-A6. Regime gate silently publishes cross-bot invalidations that will HARD-BLOCK in Phase C

**Evidence (code-verified, undocumented):**
- When the regime gate blocks arming (ghost_sniper ~lines 728–736), it calls
  `KnowledgeRegister().publish_invalidation(...)` with TTL 300s.
- Today this is inert because `is_entry_invalidated()` short-circuits under
  RAW_LOGGING_MODE.
- **When Phase C flips RAW_LOGGING_MODE=False, the Ghost regime gate will automatically
  start hard-blocking BUY/SELL entries for ALL bots on XAUUSDm every time it refuses to arm.**

**Why this matters:** that is a cross-bot kill switch wired in by accident of design.
The plan's C3 "shadow activation" discussion never mentions that the invalidation bus is
already being written by Ghost's arming logic. Must be audited and documented before
Layer 2/3 activation.

---

### F-A7. Naked-risk window: every real fill is unanchored for ~150–400ms

**Evidence (code-verified):**
- After Phase 1 fills, `time.sleep(0.15)` + modify round-trip means every 202/204 position
  has **no broker SL and no OOB TP for ~150–400ms**.
- If the process dies in that window (which is exactly what killed the cab bot on Sep 6),
  the position is naked.

**Note:** the LLM review's execution critique (150ms sleep *before* the real order) is
factually wrong — see Section 4. The real risk is this anchor gap, not shadow-delay
slippage. Small but real tail risk; should be monitored and considered in failover design.

---

## 3. Corrections to the Original Audit

### C-A1. `_send_modify` rounding — the audit's flagship "W9 fix" is ALREADY in the code

- The audit (Section 9.1 + "W9 code changes") claims `_send_modify` uses hardcoded
  `round(new_sl, 3)` and prescribes `sym_info.digits` at "lines 642-643."
- **Verified:** `sniper_watcher.py:645-646` already does
  `digits = sym_info.digits if sym_info else 3; round(new_sl, digits)`.
  Lines 491–492 and 592 also use `sym_info.digits`.
- **The proposed fix is a no-op.** Strike it from the W9 list so it does not consume a
  code session. This is the audit's only substantive factual error.

### C-A2. "Three intermediate bars ignored" — actually ONE

- `_get_h4_direction()` compares `rates[-2]` (last closed) to `rates[-4]` (3 bars back),
  with `rates[-3]` — **one** intermediate bar — between them.
- The audit's "12-hour slope that ignores everything in between" is directionally right
  but quantitatively overstated: it's an **8-hour close-to-close comparison** ignoring one
  bar plus the current open. Conclusion unchanged; description corrected.

### C-A3. MPE regime is computed on the FORMING bar every 10s — Ambiguity B is wrong

- The audit says regime "changes only when a new M15 bar closes... the same label is
  returned to every read between bar closes."
- **Verified:** `shared_intelligence._update_symbol_timeframe()` computes ADX/ATR/regime
  from `rates[-1]` — the current forming bar — and publishes every 10-second poll
  unconditionally (the `_last_bar_times` gate declared at line 29 is never applied in the
  visible body).
- The KR snapshot is refreshed with a fresh timestamp every 10s, which **defeats the
  staleness check** in `get_market_state()` (max_age = timeframe + 5min grace, but the
  timestamp never ages).
- **Two consequences:** (a) regime labels jitter intra-bar — "regime at fill" is a noisier
  construct than completed-bar labels; (b) the Layer-0 staleness guard the plan relies on
  does not work as designed.

### C-A4. Gate-202 blocking logic is OR, not AND (audit Section 2 phrasing)

- The audit's summary says 202 is "gated by ADX>P70 AND conviction>60." The code blocks
  when **either** trips: `gate_202 = not (adx > adx_block_202 or conv > GATE_202_CONV_BLOCK)`.
- Its own gate table (Section 7) is correct, so the tables are fine — the summary phrasing
  is misleading.
- Practical impact: ADX and conviction are *more* redundant than Ambiguity C implies
  (whichever trips first does the blocking).

---

## 4. Assessment of the External LLM Review

### Where I AGREE
1. **Proxy-vs-reality framing is the correct mental model.** The system measures shadows
   of the edge (12-hour slope for trend, ATR geometry for exhaustion, clock for liquidity).
2. **Collinearity (ADX double-counted through conviction) is verified and important.**
3. **Exhaustion-fallback critique of 204 is fair in principle** — with n=3 fires it is
   untestable either way, so skepticism is warranted but certainty is not.

### Where I DISAGREE / overreach
1. **The L2 solutions are largely unimplementable on this feed.** Exness tick data cannot
   yield order-book depth, trade tape, or aggressor direction — OBI and CVD are
   approximations at best, and `market_book_get` on XAUUSDm demo is unverified. Prescribing
   "measure OBI/CVD" as the fix for a system whose feed can't produce them is aspirational,
   not actionable. (The original audit's Section 16 already establishes this.)
2. **The 150ms execution-bleed mechanism is wrong.** The real 202 order fires FIRST, then
   the 150ms sleep, then the 201 shadow. The real order is not delayed behind the shadow.
   The legitimate concern is F-A7 (the naked anchor window), not shadow-delay slippage.
3. **The adaptive-paradox concern is premature.** The mechanism appears inert in the
   deployed process (F-A1). Verify first, then decide if the paradox is even live.
4. The review treats the audit's ambiguities as confirmed defects; several are open data
   questions (e.g., whether momentum-in-isolation carries signal — never analyzed).

---

## 5. Consolidated Agreement/Disagreement Summary (for control session)

| Item | Original Audit | This Supplement | Status |
|---|---|---|---|
| Core architecture reconstruction | Accurate | Confirmed | AGREE |
| H4 direction = displacement proxy (inversion explained) | Correct | Confirmed + refined (8h close-to-close, one bar ignored) | AGREE (refined) |
| 201 shadow no-audit-row (828/0) | Correct | Confirmed — structurally guaranteed | AGREE |
| W4 data confounded vs W6/W7 | Correct | Confirmed | AGREE |
| Adaptive P70 self-loosening | Flagged as ambiguity | **Likely INERT in deployed process** | DISAGREE on priority — verify first |
| H4 at arm vs trigger | Claimed only arm-time logged | **Fill rows log trigger-time, mislabeled** | DISAGREE — audit got it backwards |
| Session signal (H22) stable > H4 | Agreed | Agreed, + session-grid mismatch with RB002 | AGREE + new caveat |
| BE-lock cohort (n=2,458, 94.4% @ +0.5R) | Mentioned only as RB004 parent | **Parameter changed 0.5→1.0 without re-measure; A/B destroyed** | NEW FINDING |
| `_send_modify` digits fix needed | Listed as W9 fix | **Already in code — no-op** | DISAGREE (strike item) |
| MPE regime static between M15 closes | Claimed static | **Computed on forming bar every 10s; staleness guard defeated** | DISAGREE |
| F6 "sole effective drag-reducer" / $85 | Accepted | **Single-week, blocked best days; V2 earned +$63.68 Sep 4 with no F6** | DISAGREE — needs multi-week series |
| 204 "same conditions as 202" (MDP) | Followed MDP | **204 has no trigger-time gates, no spread check, stale context** | DISAGREE |
| LLM review L2 solutions (OBI/CVD) | Not in scope | **Unimplementable on Exness feed; aspirational** | DISAGREE |
| LLM review 150ms bleed | Audit had it right | **Review reversed order — real order first** | DISAGREE with review |

---

## 6. Consolidated Action Items for Control Session

### Verify first (analysis only, no code, answerable from existing logs)
1. **F-A1:** `is_adaptive` + `rev_adx_block` in `adaptive_thresholds_live.csv` vs static 40.
   Determines whether the adaptive gate exists at all.
2. **F-A2:** recompute W6/W7 H4 cohorts from ARMED rows (true arm-time H4) joined to fills,
   or label existing numbers as fill-time. **Prerequisite for the W9 B1b trigger.**
3. **F-A3:** pick one session grid (recommend `get_session()`); re-run A016/A018-style
   permutation under it; record the boundary in the H22 hypothesis.

### Decisions to force
4. **F-A4:** re-open the BE-lock question — re-derive the cohort at 1.0R/0.35×ATR, or run
   a controlled 2–3 week 0.5R vs 1.0R split on V2 before it is permanently locked to 1.0R.
   Highest-value open parameter in the system.
5. **F-A6:** before Phase C Layer 2/3 activation, inventory every `publish_invalidation`
   caller (Ghost regime gate already writes). The bus becomes a hard cross-bot switch the
   moment RAW_LOGGING_MODE flips.
6. **F-A7:** add the Phase-1→Phase-2 naked window to monitored risks; factor into failover
   design (already proven necessary by the Sep 6 cab incident).

### What NOT to do
- Do NOT schedule the `_send_modify` digits fix (already in code).
- Do NOT gate on H22 before the session-grid standardization (F-A3).
- Do NOT treat F6's "$85 drag avoided" as a validated number — single-week measurement,
  it blocked the week's best days, and the V2 counterfactual contradicts it.
- Do NOT treat the adaptive-threshold paradox as a live defect until F-A1 verification.

### Standing research question (unchanged, from original audit Section D)
> Can the Ghost 202 fill population be separated into structurally distinct sub-populations
> using only decision-time features — session tag × intrabar M1 momentum × M15 ATR
> percentile — with ≥3 independent weeks, different H4 environments, controlling for the
> confirmed Q1-ATR SL geometry effect?

The four verification tasks above are cheaper and must come first: two of them (F-A1, F-A2)
determine whether the current B1b/H22 machinery is even measuring what its docs claim.

---

## 7. Addendum — Cross-Bot W7 Drill: cab_super-specific Findings & Recommendations

**Added:** Sep 9 2026. Source: W7 (Sep 1–5) cross-bot extraction of the three CAB
architectures — cab_super (acct 474167713, control-verified n=48, +$85.50), cab/ modular
(acct 262924445, n=19, −$261.80), cab_multi_pair (acct 260714012, n=38, −9.78R).
Methodology: two-sided t-test vs 0 per cohort (p<0.05 flagged); multi_pair ledger parsed
with corrected per-band schema (v2/v3 Intel columns verified 40/40 and 30/30 — earlier
"Intel_ATR_State=True/False" reads were misaligned `Lock_Hit` booleans and are void).
These are the cab_super-relevant findings the original audit and Sections 1–6 did not cover.

### X-A1. Symbol-level gating is NOT justified — only USOILm is cross-bot negative

The drill's convergence test shows the same symbols traded **opposite signs across
architectures in the same week**: XAUUSDm +$79.39 (cab_super) vs −1.45R (multi),
XAGUSDm +$34.10 vs −1.69R, ETHUSDm +$7.83 vs −1.62R, EURUSDm +$75.39 vs −0.71R,
GBPUSDm +$79.18 vs −0.38R. **USOILm is the only symbol negative in all three**
(cab_super −$21.45 n=6, cab/ −$497.43 n=2, multi −1.58R n=6).

**Recommendation (cab_super):**
- Do NOT treat XAU/XAG as structural winners — W7's outliers were management-stack
effects, not symbol edges. Retiring or promoting symbols on single-bot evidence is
unsupported.
- USOILm joins the cross-bot watchlist: W8 second-week confirmation (n≥5 closed per bot,
negative P&L) before any symbol-level action. cab_super's own W7 USOILm drag (−$21.45,
17% WR) is consistent with both other bots — the one place symbol gating may be defensible.

### X-A2. Directional asymmetry (SELL ≥ BUY) is convergent — measure weekly, never hard-code

cab_super: SELL +$130.43 vs BUY −$44.93. multi_pair: SELL −0.04R (53.8% WR) vs BUY
−9.97R, 16.7% WR (**p<0.001**). Two independent architectures, same week, same sign.
This is a regime-level effect — the same class of weekly signal that inverted Ghost's
H4 direction W6→W7.

**Recommendation (cab_super):**
- The W7 SELL-side outperformance does **not** license a SELL-only mode or a BUY gate.
Track the BUY/SELL split as a weekly statistic; act only on two consecutive weeks of
agreement. This ties into F-A2: any direction-based inference is additionally time-shifted
because fill rows log trigger-time H4.

### X-A3. Exit-stack external validation — preserve the OSI R-guard

The two most significant loss cohorts in the entire drill were **exit-mechanism defects,
not entry-signal failures**: multi_pair OPP_H4_SIGNAL exit without R-guard (0/7, −3.23R,
p<0.001; ×ASIAN 0/6, −3.07R, p<0.001) and cab/ modular H1_STRUCT_INVALID (n=5, −$1,155,
p=0.011) at 1.85–4.09 lots. cab_super's OSI-with-R-guard is the exact component that let
its locked winners survive.

**Recommendation (cab_super):**
- Preserve the OSI R-guard, protector (1.2R), and harvester (50% at 2R) unchanged. This
is the single component most supported by cross-bot data this week — it is the difference
between +$85.50 and −9.78R on the same symbols.

### X-A4. MFE→R conversion is the outcome predictor — confirm cab_super logs MFE/MAE

Winners in all three bots were trades with MFE > 1R held by management; losers were
killed before MFE 0.3R (multi BROKER_TP avg MFE 1.43R vs BROKER_SL 0.10R; XAGUSDm
MFE 0.09R, capture −11.5R). cab_super's 27.1% WR with +$1.78/trade is the same
architecture expressed as outlier capture.

**Recommendation (cab_super):**
- Confirm the unified audit trail records MFE/MAE per closed cab_super trade. If not,
add it (pure logging). MFE was the one outcome field that predicted every cohort in the
drill; without it cab_super cannot participate in the RB004-style exit analysis the
other bots support.

### X-A5. Entry-intelligence parity — cab_super has no per-entry context to join the regime-class matrix

Only cab_multi_pair logs entry-time context (Intel_Session, ATR_State, H4_ADX, DXY,
Risk). cab_super has no comparable per-entry fields, so the unified "each trade handled
by its own statistically proven regime class" objective cannot include it.

**Recommendation (cab_super):**
- Mirror the multi_pair Intel schema at cab_super entry (session, H1 ATR state, H4 ADX,
DXY proxy, risk sentiment — pure logging, no gating). This is the cross-bot complement
to H21 M5 logging and the prerequisite for regime-class analysis across all three bots.

### X-A6. Session toxicity: observation, not gate

multi_pair NEW_YORK entries were significantly negative (n=11, −2.56R, p=0.008;
H1_STRUCT_BREACH × NEW_YORK p=0.013). cab_super's session gate blocks 00–11 UTC
(ASIAN + London open) but not the NY window. Different bots and entry logic mean this
**does not license a NY gate for cab_super** — but it is a testable question.

**Recommendation (cab_super):**
- Segment cab_super's W8 closed trades by entry session (NY window 12–21 UTC vs rest)
and record it. If NY is negative for a second week, register as a candidate hypothesis
(mirror of the H22 two-week discipline). Note: multi's OPP_H4_SIGNAL × ASIAN deaths
(0/6, p<0.001) indirectly validate cab_super's existing ASIAN block — keep it.

### Summary of cab_super action items (from this addendum)
1. **W8 watch:** USOILm across all three bots (X-A1).
2. **W8 measurement:** cab_super BUY/SELL weekly split + NY-window segment (X-A2, X-A6).
3. **Confirm logging:** MFE/MAE per closed trade; entry-intelligence fields at entry
   (X-A4, X-A5) — pure data collection, no gates.
4. **Do NOT:** hard-code SELL bias, retire/promote symbols on W7 evidence, alter the
   OSI R-guard / protector / harvester.