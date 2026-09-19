# GHOST_SNIPER_RESEARCH_CONTROL_AUDIT.md

**Date:** Sep 9 2026  
**Method:** Direct source reading of ghost_sniper.py (1,006 lines), sniper_watcher.py (1,299 lines), ghost_cache.py (400 lines), supertrend_bot.py (2,022 lines), cab_watcher.py (989 lines), shared_intelligence.py, knowledge_register.py, MASTER_DEVELOPMENT_PLAN.md v1.4  
**Audit type:** Read-only evidence control. No code changed, no parameters tuned, no strategies modified.

---

## 1. Executive Conclusion

The Ghost Sniper system has a real but unstable edge. The edge is not a single condition — it is a combination of session, structural displacement, and liquidity context that the current feature set cannot cleanly capture because every feature used to detect it is computed from completed bars on a single timeframe. The result is that features keep inverting across weeks as the macro regime shifts, not because the underlying edge disappears, but because the proxy used to detect it was never measuring the right thing.

Three findings survive multi-week verification: ASIAN session outperforms NY sessions, Q1 ATR produces elevated SL hit rates mechanically, and F6 (ST LONG on XAUUSDm suppresses UP_PROBE) reduces drag. Everything else in the findings registry has inverted at least once across the observation window.

The primary open question is not whether the edge exists. It is whether the state that predicts the edge can be described with features that are stable across macro regime changes. That question cannot be answered from the current data alone.

---

## 2. Actual Architecture Reconstructed from Source

### 2.1 The Real Event Flow (VERIFIED FROM CODE)

```
M1 tick received
→ copy_rates_from_pos(SYMBOL, TIMEFRAME_M1, 0, 50)
→ ATR(14) computed on M1 bars [ghost_sniper.py:328-333]
→ dynamic_step = max(ATR × 1.0, 0.5) [line 715]
→ current_price = (tick.bid + tick.ask) / 2 [line 716]

IF armed is None:
  → read_brain_state() [line 721]
    → calls get_market_state() in sniper_watcher.py
    → gets KR M15 snapshot (adx_raw, atr_raw, regime.value)
    → computes M1 momentum_score = (current_body / avg_body) × 50
    → conviction = min(adx_val × 1.0 + momentum_score × 0.5, 100)
  → regime gate: if TRENDING_UP/DOWN/UNKNOWN → continue [line 724]
  → F6 gate: if ST LONG thesis in KR and price > recent_high → continue [line 756]
  → F15 gate: if price < recent_low AND h4_dir == "DOWN" → continue [line 772]
  → if price > 5-bar high → ARM UP_PROBE [line 781]
  → if price < 5-bar low → ARM DOWN_PROBE [line 806]

IF armed is not None (probe tracking):
  → update probe_extreme and break_level each tick
  → update GhostCache each tick [line 848]
  → if trigger condition met:
    → spread guard [line 873]
    → read_brain_state() AGAIN [line 894]
    → apply_gates(bs) [line 895]
    → send_order(is_shadow=True) for magic 201 [line 966]  ← VIRTUAL FILL
    → send_order() for magic 202 if gates[202] [line 934]  ← REAL ORDER
    → armed = None, cooldown 45s [lines 982-987]
```

### 2.2 Critical architectural facts confirmed from code

**VIRTUAL_FILL (magic 201) is created at line 422-447 of ghost_sniper.py.**
When `is_shadow=True`, `send_order()` logs `VIRTUAL_FILL magic=201`, writes a dummy KR thesis with `ticket=999999+magic`, and returns `True` immediately. No MT5 order is sent. No broker interaction occurs. The price logged is the live tick price at that moment, not a fill price. This event is entirely in-memory.

**Magic 202 (REVERSAL) is the only real order at trigger time** (when `gates[202]` is True). Magic 201 fires as shadow on every trigger regardless of gate state, but produces zero actual positions.

**Gate evaluation happens TWICE per probe cycle:**
1. At arming (lines 721-736): regime gate blocks arming during TRENDING_UP/DOWN/UNKNOWN
2. At trigger (lines 893-895): `read_brain_state()` and `apply_gates()` re-evaluated at the moment of firing

The brain state used to gate 202 is a fresh read at trigger time, not the state at arming time. These can differ if market state changed during the probe window.

**ORDER_SKIP code=10044** (line 522-527): occurs when the broker rejects the Phase 1 market order with "no margin or volume limit." This is treated as an expected low-equity event and does not log as an error. The order is not retried.

**`[OOB]` in FILL_SECURE log lines** (line 623): "OOB" stands for Out-Of-Band TP. Defined at line 147-150: `HARD_FAILSAFE_TP_R = 2.0`. When the caller passes `tp=0.0` (fluid TP — all 202 and 201 entries), the code computes a broker-side TP at `entry ± 2R` as a failsafe. This fires only if Python dies and the watcher cannot manage the exit. The `[OOB]` label in the log confirms this failsafe TP was successfully set on the broker. It does NOT mean the trade hit its TP — it means the broker-side protection was anchored.

**Latency measurement** (`lat=` in log, `latency_ms` in CSV): measured from `t0 = time.time()` at the start of `send_order()` (line 390) to `latency = (time.time() - t0) * 1000` immediately after `order_send()` returns (line 518). This measures **signal-to-Phase-1-fill**, including the KR block checks (lines 396-416), SL/TP guard computation, and the MT5 API round-trip. It does NOT include Phase 2 (SLTP anchor modification). The latency in the log covers everything from function entry to broker fill confirmation.

---

## 3. Version/Configuration Lineage

### 3.1 Current deployed version (VERIFIED FROM CODE)

| Component | Version | Source |
|---|---|---|
| Ghost Sniper | v5.2 | Startup banner line 687: "HUNTER v5.2 ONLINE" |
| Sniper Watcher | v3.1 | Changelog lines 42-54 |
| Ghost Cache | Not version-stamped | N_LAYERS_DEFAULT = 2 (line 43 ghost_cache.py) |
| Magic numbers active | 201 (shadow), 202 (real), 204 (ghost cache) | Lines 119-120, ghost_cache.py MAGIC_GHOST_CACHE=204 |
| SL multiplier | 0.35×ATR | SCALP_REV_SL_ATR_MULT = 0.35, line 145 |
| TP for 202 | Fluid (0.0 → OOB at 2R) | Lines 484-497 |
| TP for 201 | 1.0R set broker-side | sniper_watcher.py LEG_TP_BY_MAGIC {201:1.0} |
| MAX_LEGS_PER_PROBE | 1 | Line 134 |
| COOLDOWN_SECONDS | 45 | Line 135 |
| SPREAD_MAX | 1.5 | Line 122 |
| ATR_STEP_MULTIPLIER | 1.0 | Line 136 |
| GhostCache N_LAYERS | 2 | ghost_cache.py line 43 |

### 3.2 Historical version provenance assessment

**VERSION PROVENANCE INCOMPLETE** for W4 and earlier.

The Watcher changelog explicitly documents a prior heartbeat-format mismatch and a case where "running script was a different version than the one uploaded" (sniper_watcher.py lines 28-32). This is direct source-level evidence that historical observations may have been collected under code that differs from what is currently inspectable.

Known code changes that materially affect fill population and gate behaviour:
- SL widened from 0.20 to 0.35×ATR (Tier 1 fix, July 2026) — changes which fills survive vs hit SL
- Ghost Cache N_LAYERS lowered from 3 to 2 (Aug 22 2026) — affects 204 fire rate
- Ghost 204 decouple fix (Aug 16 2026) — 204 now persists after 202 fire
- CAB watcher log path fix (Aug 16 2026) — changes what is logged
- MarketPulseEngine fix (Aug 26 2026) — all pre-fix KR reads returned None/UNKNOWN
- F6 gate wired (Aug 16 2026) — suppresses UP_PROBE when ST holds LONG
- F15 gate wired (Sep 1 2026) — suppresses DOWN_PROBE when H4=DOWN

**Implication for W4 data:** W4 fills were collected under 0.20×ATR SL (not 0.35), with N_LAYERS=3 (not 2), without F6 gate, and with a MarketPulseEngine that may have been returning None/UNKNOWN for all KR reads. The W4 session×H4 cross-tabs are comparing fills from a different mechanical environment to W6/W7 fills from the current one. Direct comparison is confounded.

---

## 4. H4 Direction Audit

### 4.1 Exact implementation (VERIFIED FROM CODE, lines 351-370)

```python
def _get_h4_direction() -> str:
    rates = _api().copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_H4, 0, 4)
    # rates[-1] = current open bar (excluded)
    # rates[-2] = last closed H4 bar
    # rates[-3] = two bars ago
    # rates[-4] = three bars ago (reference)
    last_close = float(rates[-2]["close"])   # last closed bar
    ref_close  = float(rates[-4]["close"])   # 3 bars before that
    if last_close > ref_close: return "UP"
    elif last_close < ref_close: return "DOWN"
    return "UNKNOWN"
```

**This is not a regime classifier.** It is a 12-hour slope proxy: the close of the last completed H4 bar compared to the close three H4 bars earlier (12 hours prior). The three intermediate bars are ignored. There is no UNKNOWN for near-zero differences — UNKNOWN only returns on data failure or exact equality (which is essentially never on Gold).

**How it is used (VERIFIED FROM CODE):**
- At arming: logged as `h4_direction_at_arm` in the ARMED event and in the audit CSV
- As gate F15: if `current_price < recent_low AND h4_dir == "DOWN"` → block DOWN_PROBE arming
- F15 is a hard gate (continue statement, no entry) only for DOWN_PROBE

**What it does NOT do:**
- It does not gate UP_PROBE arming on any H4 direction value
- It is not used in gate_202 evaluation
- It is not fed into the conviction score
- It is not recalculated on H4 bar close only — it is computed fresh on every tick where arming is evaluated

**Critical ambiguity (see Section 14, Ambiguity A):** The 12-hour slope between two closes ignores everything in between. A Gold move that went UP 200 points and then DOWN 150 points over 12 hours produces the same `_get_h4_direction()` result as a smooth 50-point UP move. The function is a price-displacement proxy, not a structural trend classification.

---

## 5. M15/ADX/Conviction Audit

### 5.1 Exact construction (VERIFIED FROM CODE)

**Source of ADX and regime:** `sniper_watcher.py:get_market_state()` (lines 236-268):
1. Calls `KnowledgeRegister().get_market_state(SYMBOL, "M15")`
2. Reads `snapshot.adx_raw` — this is the Wilder ADX(14) computed by `MarketPulseEngine._wilder_adx()` on M15 bars
3. Reads `snapshot.atr_raw` — ATR(14) on M15 bars
4. Reads `snapshot.regime.value` — categorical label from percentile-ranked ADX, ATR-ratio, and body/range ratio on M15 completed bars

**Regime label computation (shared_intelligence.py):**
- EXHAUSTION: ATR-ratio percentile ≥ 75 AND body/range percentile ≤ 35
- TRENDING_UP/DOWN: ADX percentile ≥ 65 AND body/range percentile > 35 AND close direction
- RANGING: everything else (default)

This is a completed-bar categorical classifier. It changes only when a new M15 bar closes and MarketPulseEngine next polls (every 10 seconds, but publishes only on new bar time).

**Conviction formula (VERIFIED FROM CODE, line 267):**
```python
momentum_score = (current_body / (avg_body + 1e-9)) * 50
conviction = min(adx_val * 1.0 + momentum_score * 0.5, 100)
```

Where:
- `adx_val` is M15 ADX(14) raw value from KR snapshot
- `current_body` is the last M1 bar's `|close - open|`
- `avg_body` is the mean of the last 50 M1 bars' bodies

**ADX → conviction overlap (VERIFIED):**
ADX directly feeds into conviction with weight 1.0. When the gate_202 check evaluates `adx > adx_block_202` AND conviction independently, both are using the same M15 ADX raw value. ADX and conviction are NOT independent information. The 202 gate effectively has ADX in it twice:
- Directly: `adx > adx_block_202` (which is P70 of recent ADX)
- Indirectly: through `conv > GATE_202_CONV_BLOCK (60)`, since conviction = ADX + momentum_score

The only genuinely independent component in conviction is the M1 momentum_score (last bar body relative to 50-bar mean). Gate_202 has no direct access to this component — it sees it only through the conviction scalar.

**Calibration of the ADX gate threshold:**
`adx_block_202` is the P70 of the last 60 minutes of logged ADX values from `sniper_conviction_log.csv`. This is an adaptive threshold: as the recent ADX distribution shifts, the gate threshold shifts. In a high-ADX week, the P70 rises, making the gate looser. In a low-ADX week, P70 falls, making the gate tighter. The gate does not measure the same market condition across different weeks — it measures whether current ADX is above the 70th percentile of recent ADX. See Ambiguity D.

---

## 6. Adaptive Threshold Audit

### 6.1 Full specification (VERIFIED FROM CODE)

**Rolling window:** `CALIBRATION_WINDOW_MINS = 60` — last 60 minutes of `sniper_conviction_log.csv`

**Minimum rows:** `CALIBRATION_MIN_ROWS = 30` — if fewer than 30 rows in the window, use hardcoded defaults

**Cadence:** Recomputed every 2-second heartbeat by `compute_adaptive_thresholds()`, called from `run_brain()`. Updates are written to `logs/adaptive_thresholds_live.csv`.

**Thresholds produced:**

| Threshold | Derivation | Downstream use |
|---|---|---|
| `rev_adx_block` | P70 of last-hour ADX values | Gate 202: block if current ADX > this |
| `tp_201_exit` | P20 of last-hour conviction | Fluid exit for 201 (currently unused — manage_201 only calls _set_leg_tp and BE-lock, not this threshold) |
| `tp_202_exit` | P25 of last-hour conviction | Fluid exit for 202 (currently unused — same reason) |
| `tf_conv_fire` | P80 of last-hour conviction | Was gate 203 (trend-follow). Leg 203 removed. This threshold is still computed but has no active consumer |
| `reaper_mult` | Function of P75/P25 ATR ratio, bounded 1.5–2.2 | Dynamic reaper ATR multiplier (read by sniper_watcher.py manage_202_reversal, if referenced) |

**Persistence across restarts:** NO. The adaptive thresholds file is overwritten every 2 seconds. On cold start, if fewer than 30 rows exist in the log, hardcoded defaults are used (`rev_adx_block = 40.0`).

**Self-referential calibration concern (VERIFIED):**
The `rev_adx_block` gate is derived from the P70 of recent ADX values. When ADX is elevated across an entire period (e.g., a trending Gold week), P70 rises, raising the block threshold, which allows more 202 fires during high-ADX periods. This means the gate loosens precisely when the market is in the condition it was designed to block. The adaptive mechanism can work against its own intent depending on how ADX distributes across the calibration window.

**`tf_conv_fire` is a dead threshold:** Leg 203 was removed in v5.2. The threshold is still computed and written to file but nothing reads it for gating decisions. This is confirmed in code — `apply_gates()` in ghost_sniper.py only returns `{201: bool, 202: bool}`.

---

## 7. Gate Audit

### 7.1 Complete gate table (VERIFIED FROM CODE)

| Gate | Input | Exact condition | Affects magic | Hard/soft | When evaluated | Version introduced |
|---|---|---|---|---|---|---|
| Regime gate | KR M15 regime label | regime in {TRENDING_UP, TRENDING_DOWN, UNKNOWN} | 201+202+204 | Hard (continue) | At arming | July 2026 |
| F6 ST LONG | KR thesis registry | ST thesis exists on XAUUSDm with direction=+1 | 201+202 UP_PROBE only | Hard (continue) | At arming | Aug 16 2026 |
| F15 H4 DOWN | _get_h4_direction() | price < 5-bar low AND h4_dir=="DOWN" | 201+202 DOWN_PROBE only | Hard (continue) | At arming | Sep 1 2026 |
| Spread gate | live tick | tick.ask - tick.bid > 1.5 | 201+202 | Hard (reset armed) | At trigger | Pre-W4 |
| Daily pairs cap | counter | daily_pairs >= 999 | 201+202 | Hard (reset armed) | At trigger | Pre-W4 |
| Circuit breaker | shared.entries_allowed | False | 201+202 | Hard (unified_runner) | At trigger (unified mode) | July 2026 |
| Gate 202 ADX | KR M15 ADX raw | adx > rev_adx_block (P70, default 40) | 202 only | Soft (201 still fires as shadow) | At trigger | Pre-W4 |
| Gate 202 conviction | conviction scalar | conviction > 60 | 202 only | Soft (201 still fires as shadow) | At trigger | Pre-W4 |
| KR Layer 2 invalidation | is_entry_invalidated() | RAW_LOGGING_MODE=True → always False | All | Bypassed | Inside send_order | Aug 2026 |
| KR Layer 3 portfolio | check_portfolio_entry_allowed() | RAW_LOGGING_MODE=True → always True | All | Bypassed | Inside send_order | Aug 2026 |

**RAW_LOGGING_MODE = True is confirmed in knowledge_register.py.** KR Layer 2 and Layer 3 hard blocks are entirely bypassed in the current deployed configuration. Any thesis invalidation or portfolio exposure ceiling computed by the KR has no effect on entry decisions during this phase.

**Important asymmetry (VERIFIED):**
F6 and F15 gates are evaluated BEFORE `read_brain_state()` in the arming block. The regime gate also precedes brain state read. This means there can be cases where the regime gate blocks arming but a fresh brain state read was never performed — the gates fire against the previous cycle's brain state still in local variables from the last arming attempt.

**201 as shadow — full confirmation (VERIFIED FROM CODE):**
Magic 201 always fires `is_shadow=True`. It generates a VIRTUAL_FILL log line, registers a KR thesis with dummy ticket 999999+201=1000200, and returns `True` without sending any order. It does NOT go through the SL/TP guard, the broker, or Phase 2. The 828 VIRTUAL_FILL events in W7 logs are entirely internal. Zero audit CSV rows from 201 is confirmed by the code path: `is_shadow=True` causes an early return before `log_event()` is called.

---

## 8. Ghost Cache Audit

### 8.1 Architecture (VERIFIED FROM CODE, ghost_cache.py)

**Probe direction:** Same direction as the armed probe (UP_PROBE or DOWN_PROBE).

**Entry condition:** Price reaches nth virtual layer (defined by n_layers=2 steps of ATR beyond probe_extreme), then retraces through the (n-1)th layer. This is a REVERSAL signal relative to the probe extension — Ghost Cache fires a SELL when UP_PROBE price extended upward to layer 2 then retraced through layer 1. Same mean-reversion thesis as 202, but triggered only after deeper price extension.

**Concept classification:** This is an exhaustion/inventory-reversion entry. The developer comments describe it as firing at an "exhaustion point" — that is a developer hypothesis, not an independently verified market mechanism. The entry direction is always opposite to the probe extension direction.

**Layer geometry (VERIFIED):**
- UP_PROBE: nth layer = probe_extreme + (n × atr_step). ATR step locked at arming time.
- SL placed at nth_layer + 0.5×atr_step (above the exhaustion level for SELL entries)
- Invalidation: if price reaches (n+2)th layer → cache is dead (trend, not exhaustion)

**N_LAYERS = 2 currently.** This means Ghost Cache fires after price extends 2 ATR steps beyond the probe extreme and then retraces 1 step. At N_LAYERS=3 (previous setting), zero fires occurred across 5 weeks. At N_LAYERS=2, 3 all-time fires have occurred through W7.

**Cache lifecycle:** Created at arming, persists after 202 fire (204 decouple fix Aug 16), reset only when `armed = None` at top of next detection cycle or when invalidated by price extension. Cache age limit: 300 seconds (5 minutes) — after which it is marked invalidated.

---

## 9. Exit/Management Audit

### 9.1 Per-magic exit architecture (VERIFIED FROM CODE, sniper_watcher.py)

**Magic 201 (SCALP — shadow only, no real positions):**
- TP: 1.0R set broker-side via `_set_leg_tp()` at registration
- BE-lock: DISABLED (HIGH-5 comment, line note: "BE-lock at 1.0R TP and BE-lock at 1.0R are in direct conflict")
- Grid logic: tracked in `_grid_state_201` for position count only, not for combined-R exits

**Magic 202 (REVERSAL — real orders):**
- TP: 1.5R set broker-side via `_set_leg_tp()` at registration
- BE-lock: enabled at BE_LOCK_R = 1.0 (moved to 1.0R from 0.5R previously, per code comment)
- No per-position reaper in current code — manage_202_reversal() only calls `_set_leg_tp()` and `_check_be_lock()`
- Grid Stop: combined 202-magic positions tracked in `_grid_state_202` for count cap only (not combined-R exits — grid_logic is 204-only as of Change 5)

**Magic 204 (Ghost Cache):**
- TP: 2.0R set broker-side
- BE-lock: enabled at BE_LOCK_R = 1.0
- Grid-level exits: managed by `manage_grid_logic()` with GRID_TP=1.0R, GRID_STOP=-3.0R, GRID_PROT=0.35R on combined 204-only P&L
- `MAX_GRID_AGE_SECONDS = 72 × 3600` — force close and reset after 72 hours

**R definition (VERIFIED):** Individual leg R computed as `(current_price - entry_price) / abs(entry_price - sl)` for BUY, inverted for SELL. Uses the leg's own SL, not a grid risk. This is the definition used for BE-lock decisions.

**`_send_modify` rounding pre-existing issue:** Uses `round(new_sl, 3)` hardcoded instead of `sym_info.digits`. For XAUUSDm (digits=3), this is harmless. For FX pairs, it truncates and can cause 10016 on modification.

---

## 10. Execution-Quality Audit

### 10.1 Latency semantics (VERIFIED FROM CODE)

`latency_ms` in the audit CSV measures the elapsed time from the start of `send_order()` to the return of `_api().order_send()` (Phase 1 only). It includes:
- KR Layer 2 `is_entry_invalidated()` check
- KR Layer 3 `check_portfolio_entry_allowed()` check  
- SL/TP guard computations
- Phase 1 market order send and broker fill response

It does NOT include:
- Phase 2 SLTP anchor modification
- Any time spent in `read_brain_state()` before `send_order()` is called
- The 150ms sleep between dual sends (line 545)

Latency values therefore represent signal-to-Phase-1-fill inclusive of KR overhead, which (with RAW_LOGGING_MODE=True) is minimal since both Layer 2/3 checks return immediately.

### 10.2 Virtual-to-secured price difference

For magic 202: the virtual price (from 201 shadow) is logged at `tick.ask` or `tick.bid` at the moment `send_order(is_shadow=True)` is called for 201. The real fill for 202 is the Phase 1 market order price from `result.price`. These can differ because:
1. 201 and 202 share the same firing block but 202 fires first (line 934 before 964)
2. The 150ms sleep between sends means 202 and 201 are evaluated at slightly different tick moments

No systematic price difference can be computed from the current data because 201 audit CSV rows do not exist (the is_shadow path does not write to audit CSV). The price recorded in 201's VIRTUAL_FILL log line is a logger.info call, not a CSV row.

---

## 11. Virtual vs Secured Event Analysis

| Event type | Log source | CSV source | Outcome linkable? |
|---|---|---|---|
| VIRTUAL_FILL magic=201 | sniper_hunter.log (logger.info) | NO — is_shadow path skips log_event() | NO |
| ARMED UP/DN | sniper_v51_live_audit.csv (event_type=ARMED) | YES | NO — outcome not in this row |
| ORDER_FILL_V51 magic=202 | sniper_v51_live_audit.csv | YES | YES — match to MT5 by price/time |
| ORDER_FILL_V51_NO_SL | sniper_v51_live_audit.csv | YES | YES — but position has no SL |
| GHOST_CACHE_FIRE magic=204 | sniper_hunter.log | sniper_v51_live_audit.csv | YES if FILL follows |
| ORDER_SKIP code=10044 | sniper_hunter.log | sniper_v51_live_audit.csv (ORDER_ERROR) | N/A — no position opened |
| GATE_BLOCK magic=202 | sniper_v51_live_audit.csv | YES | N/A — no position opened |

**Confirmed from W7 data:** 828 VIRTUAL_FILL events in sniper_hunter.log, 0 audit CSV rows from magic 201. This is expected given the is_shadow code path. The 201 shadow data cannot be recovered from logs already written — it requires a future code fix to the is_shadow path to write to the audit CSV.

---

## 12. Week-to-Week Confounding Analysis

### 12.1 Can the W4/W6/W7 inversion be explained by implementation changes?

**For W4 vs W6 (F2, F4, F7 inversions):**

| Variable | W4 state | W6 state | Confounding risk |
|---|---|---|---|
| SL width | 0.20×ATR | 0.35×ATR | HIGH — changes which fills survive to outcome |
| MarketPulseEngine | Likely non-functional (Layer 0 returning None/UNKNOWN) | Confirmed operational Aug 26 | HIGH — regime labels during W4 may all have been UNKNOWN |
| N_LAYERS | 3 (0 fires) | 2 (first fires) | LOW — 204 not part of 201/202 dataset |
| F6 gate | Not wired | Wired | MEDIUM — removes some UP_PROBE fills |
| Audit CSV | Filled | Filled | — |

**Classification: MIXED/CONFOUNDED**

The W4→W6 inversions (F2, F4, F7) cannot be attributed purely to market state change because the SL width change and the MarketPulseEngine fix both alter which fills reach the outcome data. A fill that would have hit SL at 0.20×ATR but not at 0.35×ATR changes the session and ADX distribution of survivors. The MPE fix means W4 regime labels may all have been fallback values (RANGING or UNKNOWN) rather than computed labels — cross-tabs of regime against session in W4 may be labelling artefacts.

**For W6 vs W7 (H4 direction inversion):**

| Variable | W6 state | W7 state | Confounding risk |
|---|---|---|---|
| SL width | 0.35×ATR | 0.35×ATR | None — identical |
| F6 gate | Wired | Wired | None — identical |
| F15 gate | Not wired | Wired (Sep 1) | LOW — F15 targets DOWN_PROBE which has never fired |
| F5 gate (CAB) | Not wired | Wired | None — does not affect Ghost |
| N_LAYERS | 2 | 2 | None — identical |
| MPE | Operational | Operational | None — confirmed both weeks |

**Classification: LIKELY MARKET-STATE EFFECT (for W6 vs W7)**

The architecture was essentially identical between W6 and W7. The H4 direction signal inverting is most likely a genuine market-state effect. Gold's macro direction changed between the two weeks, which changes what `_get_h4_direction()` returns and which fills fall into each cohort. The inversion is structurally predictable from the implementation: a 12-hour close-to-close slope in Gold will reflect short-term pullbacks and extensions within the dominant macro direction rather than the macro direction itself.

---

## 13. Ambiguity Register

**Ambiguity A — "H4 direction" versus actual implementation**  
VERIFIED: `_get_h4_direction()` is a 12-hour slope proxy (last closed H4 close vs close 3 bars prior). It is called "H4 direction" throughout documentation. The implementation ignores 12 hours of intermediate price action. A 12-hour gold move from 2,400→2,550→2,480 and a smooth move from 2,400→2,440 produce different UP/DOWN labels despite very different structural implications.

**Ambiguity B — Static M15 regime versus evolving intraday state**  
VERIFIED FROM CODE: The regime label updates only when MarketPulseEngine publishes a new M15 bar snapshot (every 10 seconds poll, but only if bar time changed). Between M15 bar closes (15 minutes), the same RANGING/TRENDING label is returned to every brain-state read. Multiple probe fires within a single M15 bar use identical regime context. PLAUSIBLE HYPOTHESIS that this matters for entry quality; NOT PROVEN from outcome data.

**Ambiguity C — ADX and conviction independence**  
VERIFIED: conviction = adx_val × 1.0 + momentum_score × 0.5. ADX is directly inside conviction with weight 1.0. The gate_202 check uses both `adx > threshold` AND `conv > 60`. ADX influences the outcome twice. The only independent component is the M1 body momentum (last bar body / 50-bar mean body). Whether this independence matters for the gate is UNRESOLVED — the audit CSV has both conviction and adx_at_fill logged, enabling analysis.

**Ambiguity D — Adaptive thresholds**  
VERIFIED: `rev_adx_block` is the P70 of the last 60 minutes of logged ADX. In a volatile week with high ADX, P70 rises, loosening the 202 block. The threshold is not a fixed market-state definition — it changes with the recent ADX distribution. A "high ADX" reading relative to one week's calibration may be "normal ADX" relative to another week's calibration. UNRESOLVED whether this amplifies or dampens the observed week-to-week behaviour.

**Ambiguity E — Version drift**  
CONFIRMED for W4. W4 was collected under 0.20×ATR SL and likely non-functional MPE. For W6/W7, version drift is low. Full provenance cannot be established for W4 without log examination of git history or startup banners from that period.

**Ambiguity F — Strategy versus state**  
UNRESOLVED: the observation "Ghost 202 works when H4 has made a push and M1 is retracing" describes a market condition, not a complete trading mechanism. The current system detects the 5-bar M1 break (which is the outcome of a push) but does not measure whether the push itself was orderly or chaotic, whether volume was one-sided or mixed, or whether the retrace is a genuine liquidity reversion or a continuation of the same move. PLAUSIBLE HYPOTHESIS that these distinctions matter.

**Ambiguity G — Directional asymmetry**  
VERIFIED: The entire observed dataset (595+ matched fills) is UP_PROBE (SELL reversals). Zero matched DOWN_PROBE fills exist. All session analysis, H4 direction analysis, ATR analysis, and conviction analysis is based on SELL reversal entries only. DOWN_PROBE performance is entirely unknown. F15 gates DOWN_PROBE based on W6 UP_PROBE findings — the assumption that DOWN_PROBE behaviour mirrors UP_PROBE is unverified.

**Ambiguity H — Session effect versus liquidity condition**  
OBSERVED: ASIAN session produces higher WR than NY sessions across W4 and W7. INFERENCE: this may be because Asian session has directional flow from Tokyo/Shanghai demand that resolves M1 reversals quickly, while NY sessions have competing institutional flow that fights the reversal. PLAUSIBLE HYPOTHESIS only. Session time is a proxy for liquidity condition — the causal mechanism is unconfirmed from trade data alone.

**Ambiguity I — Execution contamination**  
VERIFIED: the 150ms sleep between sends (line 545) and the separation between probe trigger detection and Phase 1 order send means the entry price differs from the "virtual price" at trigger detection. `current_price` at trigger (midpoint of bid/ask) is not the fill price. Fill price is `result.price` from the broker, which for a SELL market order is `tick.bid` at the moment of MT5 execution — which may differ from the detected trigger price by the price change during the 150ms sleep plus network roundtrip.

**Ambiguity J — Outcome-selection contamination**  
CONFIRMED FOR SOME FINDINGS: TRENDING_DOWN+H4_UP at 66.7% WR (n=6) was observed from outcome data and then used to describe "the best market state." This is outcome-conditioned and should not be used to define the entry condition for a new gate. It is correctly registered as H19 (observation only), not as a gate.

**Ambiguity K — Rollover/spread contamination**  
UNRESOLVED: Q1 ATR (low volatility) produces 28.8% WR and elevated SL hits. This is mechanically grounded — low ATR means the 0.35×ATR SL is tighter in absolute price terms, and Gold's minimum M1 noise may exceed this. But whether the pattern persists because of SL geometry or because low-ATR sessions coincide with low-liquidity periods (Asian overnight, pre-London) is UNRESOLVED from trade data. The ATR floor (F8) is mechanically grounded but the mechanism explanation is still an inference.

**Ambiguity L — Cached state staleness**  
VERIFIED FROM CODE: brain state is read at two points in the probe lifecycle — at arming and at trigger. Between these reads, the probe may track for multiple minutes (up to 300 seconds per GhostCache age limit). The regime label, ADX, and conviction used at trigger are a fresh read, but the H4 direction used at arming (logged as `h4_direction_at_arm`) is computed at arming time and may differ from H4 direction at trigger time if an H4 bar closed during the probe tracking phase. Currently the audit CSV only logs H4 direction at arming, not at trigger. Whether H4 direction changed during the probe window is unknown for existing fills.

---

## 14. Research Claim Ledger

| Claim / Observation | Source | Status | Evidence | Confidence | Outcome-Dependent? | Still Safe to Use? |
|---|---|---|---|---|---|---|
| ASIAN session produces higher WR than NY | MASTER_DEVELOPMENT_PLAN W4+W7 data | STRONGLY SUPPORTED | Positive W4 and W7 independently; different market regimes | Medium | YES — derived from outcome data | YES — as hypothesis for W8+W9 confirmation |
| NY_CLOSE and NY_OVERLAP are loss sessions | MASTER_DEVELOPMENT_PLAN W4+W7 | STRONGLY SUPPORTED | Two independent weeks, different H4 direction environments | Medium | YES | YES — as hypothesis |
| H4 direction is the strongest single predictor | MASTER_DEVELOPMENT_PLAN W6 analysis | CONFLICTED | W6: supported (10.1pp gap). W7: inverted | Low | YES | NO — do not use as gate basis alone |
| ADX and conviction are independent | INFERENCE | INVALID | Conviction = ADX + momentum. Not independent. | — | — | NO — treat as partially redundant |
| Adaptive rev_adx_block is a stable gate threshold | INFERENCE | INVALID | P70 of recent ADX shifts with recent market volatility | — | — | NO — threshold is relative, not absolute |
| TRENDING_DOWN+H4_UP is the favorable regime | MASTER_DEVELOPMENT_PLAN W6 | OBSERVED | n=6. Single-week. Outcome-conditioned. | Very low | YES | NO for gating; YES for monitoring |
| Q1 ATR produces elevated SL hit rate | MASTER_DEVELOPMENT_PLAN W4+W6+W7 | VERIFIED | Mechanically grounded. Three weeks. | High | Partially | YES — mechanically grounded |
| M15 RANGING label is stale during H4 trend | INFERENCE | PLAUSIBLE HYPOTHESIS | MPE publishes only on bar close. Logic confirmed in code. | Medium | NO | YES — as research question |
| F6 reduces Ghost drag | MASTER_DEVELOPMENT_PLAN W7 | VERIFIED | 2,354 blocks, estimated $85 drag avoided | High | Partially | YES |
| F15 reduces current Ghost drag | MASTER_DEVELOPMENT_PLAN W7 | INVALID | Zero DOWN_PROBE fires. $0 current impact. | — | — | NO — acknowledged in plan |
| 201 virtual fills track 202 real fills | INFERENCE | INVALID | 201 is_shadow=True fires on every trigger; 202 gated by ADX/conv. They are not 1:1. | — | — | NO |
| Post-displacement M1 retrace is favorable state | INFERENCE | PLAUSIBLE HYPOTHESIS | Theoretically grounded. Not independently verified from non-outcome data. | Low | YES | YES — as research question |

---

## 15. State vs Outcome Boundary

**State/decision-time data (available at entry):**
- Session tag (UTC hour at trigger)
- H4 slope proxy (rates[-2].close vs rates[-4].close)
- M15 ADX raw value (from KR snapshot)
- M15 regime categorical label (from KR snapshot)
- Conviction scalar (ADX + M1 body momentum)
- M1 ATR(14) at arming and at trigger
- Spread at trigger
- GhostCache virtual layer depth (if 204)
- Probe direction (UP/DOWN)
- KR snapshot timestamp (staleness indicator)
- Gates state (gate_201, gate_202)

**Outcome data (not available at entry):**
- MFE/MAE (highest/lowest price during trade)
- Final P&L
- Exit reason (SL hit, TP hit, BE-lock, OOB TP)
- R-multiple at close
- Time to exit
- Whether BE-lock was reached before SL

**Current contamination risk:** The TRENDING_DOWN+H4_UP finding (66.7% WR, n=6) was derived by looking at which fills were profitable and then labelling their context. This is outcome-conditioned. Using it to define a "good" entry condition would be circular. It is correctly registered as an observation, not a gate.

---

## 16. Tick-Data Interpretation Boundary

The Exness feed provides bid/ask ticks with timestamps. From this data the following can be reliably computed:
- Bid/ask spread at any moment
- Quote update frequency (how often bid/ask changes per second)
- Intrabar price path (sequence of quotes within an M1 bar)
- Quote-level volatility transitions (spread widening/narrowing)
- Temporal clustering of quote updates

The following CANNOT be reliably established from Exness tick data alone:
- Which side (buyer or seller) initiated each price change
- Traded volume at any specific price
- Order book depth at any price level
- Institutional positioning or order flow direction
- Whether a price move was driven by aggressive market orders or passive limit order posting

Any analysis of "buy pressure" or "sell pressure" from Exness tick data is an inference, not a direct measurement. CVD estimated from tick data assumes that upticks represent aggressive buying — this assumption is valid for exchange-traded instruments with disclosed trade tape but is an approximation for OTC/aggregated broker feeds.

---

## 17. Minimum Future Data Requirements

### Required (necessary to test the market-state hypothesis)

- Session tag at every fill (already logged: `get_session()` in audit CSV)
- H4 slope proxy at arm time (already logged: `h4_direction_at_arm`)
- M1 ATR at arm time and at trigger (already logged: `atr_at_fill`)
- Probe direction (already logged: `probe_direction`)
- Fill outcome matched to MT5 (already being done manually each week)
- Minimum n=50 fills per session bucket per week for 2 consecutive weeks before gate evaluation

### Valuable (improves diagnosis without being strictly required)

- H4 slope proxy at trigger time (not currently logged — only logged at arm)
- Whether H4 bar changed between arming and trigger (derivable if arm timestamp and trigger timestamp are both logged)
- M1 ATR at trigger time separately from at arm time (currently logged as `atr_at_fill` which is computed at trigger, not at arm)
- M15 ATR percentile rank at arm time (available from KR snapshot, not currently logged in audit CSV)
- Time elapsed from arming to trigger (derivable if arm event timestamp is stored)
- `context_bucket` computed field combining session × h4_direction × regime (not currently computed)

### Unavailable / currently unsupported

- Intrabar price path during probe tracking (would require tick-level logging during the probe window)
- Quote update frequency at trigger (not logged anywhere)
- True traded volume (not available from Exness broker feed)
- Order book depth (requires market_book_get() subscription, not currently implemented)
- Whether the 5-bar M1 high/low was new vs a retrace of a prior session's extreme (derivable but not currently computed)
- M1 body momentum at arm time vs at trigger time (currently only captured at trigger)

---

## 18. Known Unknowns

1. Whether W4 fills are comparable to W6/W7 fills given the SL width change and possible MPE non-functionality
2. Whether the ASIAN session advantage is caused by session time itself or by ATR distribution within that session (Asian fills may cluster in lower-ATR periods)
3. What the M1 momentum_score distribution looks like at ASIAN vs NY triggers — the only component of conviction that is independent of ADX and could be the actual signal
4. Whether the probe trigger price (midpoint) and the actual fill price (bid for SELL market order) diverge systematically by session — spread is wider in NY sessions, meaning the effective entry price differs by session in addition to outcome
5. Whether the W4 KR regime labels were all UNKNOWN/RANGING due to MPE non-functionality — if so, all W4 session×regime cross-tabs are meaningless for regime analysis

---

## Section A — What Do We KNOW?

**From code, verified:**
1. Magic 201 fires as pure shadow (VIRTUAL_FILL) on every probe trigger. It generates zero real positions and zero audit CSV rows.
2. Magic 202 is the only real entry. It is gated by ADX>P70 of recent ADX AND conviction>60, where conviction = ADX×1.0 + M1_body_ratio×0.5. ADX appears in both the direct gate and the conviction gate.
3. `_get_h4_direction()` is a 12-hour close-to-close slope proxy, not a regime classifier. Three intermediate bars are ignored.
4. The regime label (RANGING/TRENDING/EXHAUSTION) is computed from M15 completed bars and changes only on new M15 bar close. It is the same for all probes within a 15-minute window.
5. `rev_adx_block` (the adaptive 202 gate threshold) is P70 of the last 60 minutes of logged ADX values. It shifts as recent ADX distribution shifts.
6. KR Layer 2 and Layer 3 hard blocks are bypassed (RAW_LOGGING_MODE=True). No entry is blocked by portfolio exposure or invalidation in the current configuration.
7. `[OOB]` in log lines means the broker-side failsafe TP at 2R was successfully anchored. It does not mean the TP was hit.
8. `latency_ms` measures start-of-send_order() to Phase-1-fill. It does not include Phase 2 SLTP modification.

**From data, verified:**
1. ASIAN session: positive avg P&L in W4 and W7 (different macro regimes)
2. NY_CLOSE and NY_OVERLAP: negative in W4 and W7
3. Q1 ATR (<1.33): elevated SL hit rate in W4, W6, W7 — mechanically grounded
4. F6 (ST LONG suppresses UP_PROBE): prevented ~118 fills in W7, estimated $85 drag avoided
5. H4 direction signal: W6=DOWN was loss driver; W7=UP was loss driver. Inverted. All-time, neither cohort is positive-expectancy.
6. 828 VIRTUAL_FILL events logged, 0 audit CSV rows — is_shadow path confirmed broken for audit logging

---

## Section B — What Do We SUSPECT?

1. The session signal (ASIAN positive, NY negative) is more stable than the H4 direction signal because it reflects a structural difference in who is trading XAUUSDm and why — not a computed technical feature
2. The 12-hour H4 slope proxy is capturing short-term Gold price excursions within a longer trend, not the longer trend itself — this is why it inverts weekly as Gold oscillates around its macro direction
3. The M1 body momentum component of conviction (the only part independent of M15 ADX) may contain more useful information than the ADX component for this strategy, but it has never been analyzed in isolation
4. The adaptive `rev_adx_block` threshold may be loosening precisely during the worst entry conditions because high-ADX weeks push P70 higher, allowing more 202 fires into trending conditions
5. H4 bar change during the probe tracking phase (H4 bar closes while probe is being tracked) may explain some of the arm-time vs trigger-time mismatch

---

## Section C — What Remains Structurally Ambiguous?

1. Whether W4 session×regime cross-tabs are meaningful given possible MPE non-functionality during that period
2. Whether ASIAN advantage is session time or ATR distribution within session (or spread level within session)
3. Whether M1 body momentum at trigger time is systematically different by session — never analyzed
4. Whether the probe trigger price and actual fill price diverge by session due to spread differences — never measured
5. Whether the 5-bar M1 high/low break is measuring a new price extreme or a re-test of a prior extreme — these are structurally different events
6. Whether the adaptive threshold mechanism amplifies or dampens the week-to-week variability by tracking recent ADX distribution

---

## Section D — What Question Is Worth Taking Forward?

> Can the Ghost 202 fill population be separated into structurally distinct sub-populations using only decision-time features — specifically the combination of session tag, intrabar M1 price momentum, and M15 ATR percentile rank — where at least one sub-population shows consistent positive expectancy across a minimum of three independent observation weeks with different H4 direction environments, after controlling for the confirmed SL-geometry effect of Q1 ATR?

This question is neutral. It does not assume which variable matters. It specifies the independence requirement (three weeks, different H4 environments) to prevent regime-conditional findings from being mistaken for structural ones. It names the one confirmed confounder (Q1 ATR SL geometry) that must be controlled. It is answerable from the existing audit CSV data enriched with the `context_bucket` computed field (session × H4 direction × regime).

---

## Now: Plan Update After W8 — SuperTrend and CAB L2 Assessment

---

## ST Assessment: Does SuperTrend Need L2 Data?

**Verdict: No — not in Phase B or C. Possibly in Phase D (live) for execution quality only.**

### What ST actually does at entry (VERIFIED FROM CODE)

Entry gates in order:
1. ST band flip between two completed M30 bars (or 3-bar high/low continuation breakout)
2. `tick_volume[-1] > volume_ma[-1] × 1.2` — tick count gate, not traded volume
3. Auto-reversal check against open positions
4. KR Layer 2/3 (bypassed — RAW_LOGGING_MODE=True)
5. Session gate (FX pairs blocked in Asian session)
6. Conviction gate (disabled by default)

Exit uses SI score computed from: cluster agreement (0.40), regime match (0.25), ADX ratio (0.20), tick volume ratio (0.15). State machine transitions: INCUBATING → CONFIRMED → DECAYING → DEAD.

### ST's actual gap

The volume gate uses tick_volume, not traded volume. In a fast Gold move, tick_volume rises because the bid/ask updates rapidly — not because buyers or sellers are executing size. CVD (which tracks trade aggressor direction) would be more meaningful here.

**But this gap does not meaningfully affect SuperTrend in Phase B.** Why: ST's positive-expectancy evidence spans four consecutive weeks (W3–W6) across different market regimes. The mechanism is K-Means adaptive factor selection, which finds the SuperTrend factor that best fit the last 100 bars of vol-adjusted performance. This is a lagging but regime-adaptive mechanism — it self-calibrates. The exit (ST line flip + SI collapse → DEAD) is also regime-adaptive.

The tick_volume gate blocks low-activity entries, which is its intent — it is not trying to measure directional conviction, it is trying to ensure there is sufficient market activity for the M30 breakout to be meaningful. For this purpose, tick count is a reasonable proxy.

**Where CVD would help for ST (Phase D only):** At the moment of entry, confirming that the ST flip is accompanied by net aggressive buying (CVD positive for BUY) rather than passive bid lifting would filter false breakouts. This matters more in live trading where execution costs are real. For the demo phase, the benefit does not exceed the implementation cost.

**Conclusion:** ST does not need L2 data for Phase B or C. The current positive-expectancy signal is stable enough without it. If ST moves to live (Phase D), adding CVD at entry as a soft filter (log-only first, then gate if correlation confirmed) is a valid Phase D item. Not before.

---

## CAB Assessment: Does CAB Need L2 Data?

**Verdict: No for Phase B. Possibly yes for Phase C exit timing only — specifically for the Harvester and OSI paths.**

### What CAB actually does (VERIFIED FROM CODE)

**Entry:** H4 two-bar candlestick inversion. Zero volume, zero flow, zero depth. Session gate blocks 00:00–11:59 UTC. SL = H4 ATR × 2.5.

**Exit mechanisms:**
- OSI: two completed H4 bars form counter-inversion → close immediately. Fires only on new H4 bar (bar-gated by `is_new_h4_bar` check)
- Reaper: regime=TRENDING AND R ≤ -0.5 AND KR micro-degradation factor > 0.25. Also bar-gated.
- Protector: R ≥ 1.2 → SL to BE. Continuous (not bar-gated).
- Harvester: R ≥ 2.0 → close 50%, trail remainder at 1.5×M15 ATR. Continuous.
- Group invalidation: combined position R ≤ -1.5 → cascade exit.

### Where CAB's actual gaps are

**Gap 1 — H4 inversion has zero sub-H4 confirmation.**
The entry fires on a completed 8-hour candlestick pattern. By the time the second bar of the inversion closes, the reversal may be 30–60% complete or may already be failing. The H21 M5 logging being implemented in W8 is the right first step — it adds four M5 fields (direction, ATR, body ratio, consecutive bars) at entry detection. This is pure data collection and should reveal whether M5 structure at entry predicts OSI on the next bar.

L2 data at H4 entry would face a fundamental timing problem: OBI is a sub-minute signal applied to an 8-hour pattern. A single OBI reading at the moment CAB fires is unlikely to be more predictive than the M5 structure over the preceding 15–30 minutes, which H21 will capture. M5 logging is the correct instrument here, not L2.

**Gap 2 — Harvester fires at fixed R with no book-thinning detection.**
The Harvester closes 50% at R ≥ 2.0 regardless of whether the market is accelerating or exhausting at that point. A position that reaches 2.0R during a strong continuation is harvested at the same threshold as one reaching 2.0R on a fading move. CVD at the Harvester decision point would distinguish these two cases.

**But the gap is manageable without L2 in Phase B.** The current Harvester trail at 1.5×M15 ATR after the partial close handles continuation cases — the remaining 50% stays in play. The cost of harvesting too early on a continuation is the foregone gain on the harvested portion, which is bounded by the position size (0.01 lot). The benefit of early harvest on a reversal is locking 2R on 50% before it gives back.

For Phase C (after CAB has confirmed multi-regime positive expectancy), adding CVD to the Harvester decision — if CVD is still positive at 1.5R, delay harvest to 2.5R — is a valid enhancement. Not before.

**Gap 3 — OSI is a candlestick pattern exit with an 8-hour lag.**
OSI fires when the next two H4 bars form a counter-inversion. This means a position that is losing from entry can hold for up to 8 hours before OSI fires. During that 8 hours, the position is accumulating loss.

**The Reaper exists to address this** — it fires at -0.5R when regime=TRENDING, independent of H4 bar close (it is Reaper that is bar-gated in current code, via `is_new_h4_bar`). The Reaper is the intended early-exit mechanism for the intra-bar loss case.

Whether OBI would improve on the Reaper as an early-exit signal is PLAUSIBLE but unverified. The Reaper triple gate (regime=TRENDING + R≤-0.5 + micro-degradation>0.25) is already a multi-condition exit. Adding OBI as a fourth condition would add complexity without established data support for CAB.

**Conclusion:** CAB does not need L2 for Phase B. For Phase C, log CVD at Harvester decision as shadow data (does CVD direction agree with the position at +2.0R?). If the correlation is confirmed, wire CVD as an optional Harvester accelerator. H21 M5 logging is a better near-term investment than L2 for CAB.

---

## Updated Plan After W8 Run

### What W8 must produce (non-negotiable)

**Ghost:**
1. H4 direction data for W8 (H4=DOWN avg P&L and H4=UP avg P&L from matched fills)
2. Session breakdown (ASIAN/LONDON/NY_CLOSE/NY_OVERLAP avg P&L from matched fills)
3. Audit CSV write path confirmed (unified mode producing rows — Sep 4–5 had zero fills due to F6, so unified path is unproven)
4. H22 data point: is W8 ASIAN positive and NY negative? This is the second data point toward a gate.

**CAB:**
5. H21 M5 logging confirmed (at least 1 M5_CONTEXT line per new CAB position in cab_watcher.log)
6. Gate 2 (204): fires count and avg P&L

**SuperTrend:**
7. Per-symbol W8 P&L for Gate 5 accumulation

### Decision tree entering W9 (all branches)

**Branch A — W8 H4 direction confirms W6 picture (DOWN worse, UP better):**
- H4=DOWN avg < -$0.50/tr AND H4=UP avg > +$0.10/tr
- Action: B1b is ONE week away from trigger. Collect W9 data. If W9 confirms, wire B1b before W10.
- ST and CAB: unchanged

**Branch B — W8 H4 direction continues W7 picture (DOWN better, UP worse):**
- Action: B1b deferred again. H4 direction confirmed unstable across 3 different regimes. Retire it as a gate candidate until a structural explanation is found. Focus shifts entirely to H22 session gate.
- ST and CAB: unchanged

**Branch C — W8 H22 session confirms (ASIAN positive, NY negative):**
- This is the most important W8 outcome.
- Action: H22 has two confirmations (W7+W8). Begin designing the NY session block gate for W9. Exact hours to block: NY_CLOSE (16:00–21:00 UTC) and NY_OVERLAP (12:00–16:00 UTC).
- Expected effect: removes ~40% of fills (the loss-generating sessions), leaves ASIAN+LONDON (~60% of fills at positive avg). First potential for Ghost to become net positive without any other gate.

**Branch D — W8 H22 session reversal (ASIAN negative, NY positive):**
- Action: H22 loses second-data-point support. Do not register W8 as a confirmation. Continue W9 data collection. Note the reversal in the findings registry. Revisit after W9.

**Branch E — Audit CSV write path still not confirmed in unified mode:**
- Action: This is a code investigation before W9 starts. Without confirmed unified-mode audit CSV rows, B1b and ATR gate analysis cannot be trusted. Must resolve before any gate implementation.
- Investigation: add a test write at the start of `ghost_hunter_thread` startup that writes one row with event_type=RUNNER_START to sniper_v51_live_audit.csv, then check it appears after next restart.

### W9 code changes (conditional on W8 outcomes)

| Change | Condition | Scope |
|---|---|---|
| H22 NY session block gate | Branch C confirmed | Block Ghost probe arming during NY_CLOSE (16-21 UTC) and NY_OVERLAP (12-16 UTC). One constant, one block in `ghost_hunter_thread`. Log GHOST_ARM_BLOCKED_SESSION. |
| B1b UP_PROBE gate when H4=DOWN | Branch A confirmed W8 AND W9 | Block UP_PROBE arming when H4=DOWN. ~4 lines. Only if W8 meets threshold. |
| EMA50 logging for CAB (H14) | No condition — data collection | Add EMA50 at H4 to every CAB entry in cab_watcher.log. Pure logging. 3 lines in _place_order(). |
| 201 audit CSV fix | No condition — infrastructure | In is_shadow path of send_order(), add log_event("VIRTUAL_FILL_V51", {...}) call to write audit CSV row. Enables shadow analysis. |
| _send_modify digits fix | No condition — correctness | Replace `round(new_sl, 3)` with `round(new_sl, sym_info.digits)` in sniper_watcher.py lines 642-643. |

### Phase B gate sequence (updated)

**Confirmed and delivered:**
- F5 CAB London: operational
- F15 Ghost H4_DOWN: operational (zero fires, correctly dormant)
- F6 Ghost ST_LONG: operational (quantified $85 drag reduction in W7)

**Next in sequence (W9, conditional):**
- H22 NY session block: most impactful available gate. Gated on W8+W9 session confirmation.
- B1b UP_PROBE gate: lower priority than H22. Gated on W8+W9 H4 direction consistency.

**Phase C prerequisites (unchanged):**
- Positive-expectancy filtered Ghost population (n≥200 post-gate fills, positive avg P&L)
- Gate 3 Ghost passed (defined as 100+ filtered fills with avg P&L > $0)
- ST Gate 5 locked (20+ trades per active symbol)
- Account equity > $7,500 before Phase D begins

### L2 integration — where it fits in the forward plan

| Bot | Phase | L2 value | When to add |
|---|---|---|---|
| Ghost 202 | Phase C | OBI at probe arming as entry quality signal | After H22 session gate is confirmed and filtered population exists. Log OBI at arm time as shadow field. Requires `market_book_get()` call at arming. |
| SuperTrend | Phase D only | CVD at entry to filter tick-count volume gate | Only if moving to live capital. Not a Phase B/C item. |
| CAB | Phase C | CVD at Harvester decision point | After CAB shows multi-regime positive expectancy. Log CVD direction at Harvester time as shadow. |
| Ghost 204 | Phase C | No specific L2 value identified | 204 fires too rarely (3 all-time) for L2 analysis to be meaningful |

