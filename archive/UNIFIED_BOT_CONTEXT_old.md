# Unified Algo Trading Bot — Full Project Context & Architecture

**Status:** Phase 2 Demo Testing  
**Last Updated:** 21 May 2026  
**Environment:** Exness MT5 Demo — XAUUSD.x · XAUUSDm · EURUSDm · GBPUSDm · XAGUSDm  
**Lot Size:** 0.01 (demo phase)

---

## 1. Project Philosophy

Three regime-complementary bots unified into one Python process sharing one MT5 connection. Each bot operates in a different market regime — they don't compete, they take turns.

**Core principle (agreed May 2026):** Every exit decision must be driven by market intelligence, not rigid R-thresholds. R-multiples are outcome measurements, not decision triggers. The roadmap leads toward a Market Exit Score (MES) that governs exit aggression continuously based on live market state.

**The finish line (Gate ⑥):** One unified process, micro-lot sizing, avg R > 0.3 over 50 live trades on validated bot-instrument pairs.

---

## 2. Regime Complementarity Map

| Regime | ADX Signal | SuperTrend | Ghost Grid | CAB Watcher |
|---|---|---|---|---|
| **RANGING** | ADX ≤ 35 | SLEEPING | **ACTIVE 201/202** | Watching |
| **STABLE** | ADX 35–55 | Watching | 201 only (caution) | Watching |
| **TRENDING** | ADX 55+ | **ACTIVE entries** | 202 BLOCKED, 203 fires | REAPER alert |
| **EXHAUSTION** | ATR spike, weak body | Exits via DEAD state | 202 fading | **HARVESTER fires** |

---

## 3. File Structure

```
Super/                          ← project root (run everything from here)
│
├── unified_runner.py           ← MASTER ENTRY POINT — 5 daemon threads
├── mt5_gateway.py              ← Thread-safe MT5 wrapper (single Lock)
├── run_bot.py                  ← Standalone SuperTrend runner (legacy)
├── config/
│   └── config.json             ← All credentials, symbols, caps, thresholds
├── logs/                       ← All rotating log files written here
│
├── core/
│   ├── __init__.py
│   └── supertrend_bot.py       ← SuperTrend v2.3 — M30 trend following
│
├── ghost_super/
│   ├── __init__.py
│   ├── ghost_sniper.py         ← Ghost Hunter v5.1 — probe detection + entry
│   ├── sniper_watcher.py       ← Ghost Brain v3.1 — market pulse + grid mgmt
│   └── ghost_cache.py          ← GhostCache — virtual grid layer tracker (204)
│
├── cab_super/
│   ├── __init__.py
│   ├── cab_entry.py            ← CAB Entry Engine — H4 inversion detector
│   └── cab_watcher.py          ← CAB Watcher v16.3 — fluid position manager
│
├── UnifiedFailover.mq5         ← MQL5 EA — 9 magic numbers, 60s/120s failover
├── verify_structure.py         ← Structure + import health check
├── test_cab_entry.py           ← 15 tests for CAB entry engine
├── test_cab_gateway_port.py    ← 10 tests for CAB gateway port
├── test_ghost_gateway_port.py  ← 13 tests for Ghost gateway port
└── test_supertrend_gateway_port.py  ← 12 tests for ST gateway port
```

---

## 4. Magic Number Registry

| Bot | Magic Number | Symbol | Purpose |
|---|---|---|---|
| SuperTrend | 101234 | EURUSDm | M30 trend entry |
| SuperTrend | 201567 | GBPUSDm | M30 trend entry |
| SuperTrend | 301890 | XAUUSDm | M30 trend entry |
| SuperTrend | 401213 | XAGUSDm | M30 trend entry |
| Ghost Grid | 201 | XAUUSDm | SCALP leg |
| Ghost Grid | 202 | XAUUSDm | REVERSAL leg |
| Ghost Grid | 203 | XAUUSDm | TREND-FOLLOW leg |
| Ghost Grid | 204 | XAUUSDm | GHOST CACHE (nth layer) |
| CAB Watcher | 999555 | All pairs | H4 inversion positions |

**Isolation rule:** Each bot manages only its own magic numbers. `unified_runner.py` runs a magic isolation check every 5 minutes — any breach is logged as `MAGIC_ISOLATION_BREACH`.

---

## 5. Thread Architecture

```
Main thread (60s)    — equity heartbeat, circuit breaker, magic isolation, MT5 health
Thread 1: GhostWatcher (2s)  — market pulse (ADX/ATR/conviction) → SharedState
Thread 2: GhostHunter (1s)   — M1 probe detection → fires 201/202/203/204
Thread 3: CABWatcher  (15s)  — manages open CAB positions (fluid matrix)
Thread 4: CABEntry    (30s)  — H4 inversion detection → fires 999555
Thread 5: SuperTrend  (30s)  — M30 trend following → fires 101234-401213
```

All threads share **one MT5Gateway instance**. The gateway's `threading.Lock` serialises every MT5 API call.

---

## 6. Bot Summaries

### 6.1 SuperTrend v2.3 — `core/supertrend_bot.py`

**Strategy:** M30 trend following with K-Means optimal factor selection.

**State machine per position:**
- `INCUBATING` → waits `incubation_bars_trending=2` bars before active SL management
- `CONFIRMED` → SI score high, trail SL to ST line + R-lock ratchet
- `DECAYING` → SI dropping, tighten trail, close after `decaying_tolerance_bars`
- `DEAD` → close immediately (ST line flip, SI collapse, ER churn)

**Key parameters:**
```python
max_positions = 4          # per symbol (raised from 1 — directional confirmation)
risk_percent = 1.0
sl_multiplier = 2.0
tp_safety_multiplier = 5.0 # was 10.0 — reduced so ceiling is reachable
si_partial_close_min = 0.65 # was 0.85 — reduced so partial close actually fires
partial_close_profit_atr_mult = 1.5  # was 3.0
incubation_bars_trending = 2
```

**R-lock ratchet (CONFIRMED state):**
- +1R → BE lock (SL to entry + buffer)
- +2R → lock 1R (SL to entry + 1×risk)
- +3R → lock 2R (SL to entry + 2×risk)

**Session gate:** Suppresses FX entries 00:00–07:00 UTC (Asian session).

**SI Score weights:** cluster=0.40, regime=0.25, adx=0.20, vol=0.15

---

### 6.2 Ghost Grid Reversion — `ghost_super/`

**Strategy:** Virtual (ghost) grid accumulates in memory against a probe move. Fires real entry at exhaustion point.

**Entry legs (ghost_sniper.py):**

| Magic | Leg type | Gate condition | TP | SL |
|---|---|---|---|---|
| 201 | SCALP | Always | 1.0R | 0.2×ATR |
| 202 | REVERSAL | ADX ≤ 40 AND conviction ≤ 60 | 1.5R | 0.2×ATR |
| 203 | TREND-FOLLOW | ADX > 45 AND conviction > 65 | OOB (3×ATR failsafe) | 0.5×ATR |
| 204 | GHOST CACHE | nth virtual layer reached | 2.0R | nth_layer ± 0.5×ATR |

**Grid management (sniper_watcher.py):**
- `GridState.MAX_LEGS = 4` — hard cap, never raised
- Grid TP: combined P&L ≥ +1.0R → close all legs
- Grid Stop: combined P&L ≤ -3.0R → close all immediately
- Grid Protector: combined R ≥ +0.35R → oldest leg SL to BE + 30pts
- BE-lock ratchet: per-leg, fires at +0.5R individual R

**ADX fix (critical):** All three files use corrected Wilder ADX with mean-init for the ADX smoothing step (was sum-init — caused steady-state ADX 14× too large, breaking all regime classifiers).

**Ghost Cache (magic 204):**
- Instantiated on `ARMED`, reset to `None` on probe reset
- `n_layers = 3` (start, do not change until 30+ fills)
- Fire condition: price reaches nth layer AND retraces through (n-1)th
- Invalidation: price reaches (n+2)th layer (trend, not exhaustion)
- Cache age limit: 300s (5 minutes)

**Emergency OOB TP (audit-oob-tp):** When `tp=0.0` (Fluid TP), `send_order()` sets a broker-side TP at entry ± 3×ATR. This is a Python-crash failsafe only — watcher closes dynamically before this level.

---

### 6.3 CAB Watcher — `cab_super/`

**Strategy:** H4 two-bar inversion entry + fluid position management.

**Entry (cab_entry.py):**
- Pattern: bar[-3] bearish + bar[-2] bullish = BUY; vice versa = SELL
- Bar-aware cache: fires once per H4 bar close, not every 30s cycle
- Lot sizing: ATR-based (tick formula, same as ST fix)
- `max_positions = 4` per symbol (raised from 1)
- Session gate: blocks 00:00–07:00 UTC
- Spread guard: blocks if spread > 50 points

**Management (cab_watcher.py):**

| Milestone | Condition | Action |
|---|---|---|
| PROTECTOR | R ≥ 1.2R | Move SL to BE + M15 ATR buffer |
| CONT_TIGHTEN | R > 0, post-protector | Light SL tighten every cycle (0.10×M15 ATR) |
| HARVESTER | R ≥ 2.0R, any regime | Partial close 50%, trail remainder 1.5×M15 ATR |
| REAPER | R ≤ -0.5R, TRENDING | Triple gate: SI < 0.45 AND ER < 0.25 for 2+ cycles |
| REAPER suppressed | Asian session | 00:00–07:00 UTC on XAUUSD |

**Critical bug fixes applied:**
1. `_close_position()` None guard — tick=None no longer crashes silently
2. `processed_actions` — no longer reset on transient empty-positions result
3. Regime TF: M1 (170 bars) → H4 (50 bars ≈ 8 days context)
4. HARVESTER: removed EXHAUSTION regime lock — now fires in any regime

---

## 7. MT5 Gateway — `mt5_gateway.py`

Single point of MT5 access for all bots. One `threading.Lock`.

**Methods:** `initialize()`, `login()`, `shutdown()`, `copy_rates_from_pos()`, `symbol_info()`, `symbol_info_tick()`, `account_info()`, `terminal_info()`, `positions_get()`, `positions_total()`, `order_send()`, `last_error()`, `reconnect_if_needed()`

**IPC failure tracking:** `_ipc_fail_count` increments on `symbol_info_tick()` failures. After 5 consecutive failures, `is_healthy` returns `False` and main thread forces reconnect.

**Gateway pattern (all bots):**
```python
_GATEWAY = None
def set_gateway(gw): global _GATEWAY; _GATEWAY = gw
def _api(): return _GATEWAY if _GATEWAY is not None else mt5
```
Standalone mode (no gateway) falls back to raw `mt5` calls — backward compatible.

---

## 8. SharedState — `unified_runner.py`

In-memory store replacing CSV IPC between threads. One `RLock`.

```python
shared.conviction        # float 0-100
shared.adx               # float 0-100
shared.atr               # float (price units)
shared.regime            # str: RANGING / TRENDING_UP / TRENDING_DOWN / EXHAUSTION
shared.adaptive          # dict of calibrated thresholds from sniper_watcher
shared.entries_allowed   # bool — circuit breaker state
shared.daily_start_equity # float — sampled once at session start
```

**Circuit breaker flow:**
1. Main thread samples `daily_start_equity` at startup
2. Every 60s: calculates `drawdown_pct = (start - current) / start × 100`
3. If `drawdown_pct >= max_daily_loss_percent` → `shared.trip_circuit_breaker(reason)`
4. All bot entry threads check `shared.check_entries_allowed()` before opening positions
5. Watchers continue running — existing positions still managed

---

## 9. MQL5 Failover — `UnifiedFailover.mq5`

Single EA covering all 9 magic numbers.

- **Heartbeat file:** `cab_heartbeat.txt` (Unix timestamp written every 30s by CABEntryRunner)
- **Warn threshold:** 60s since last heartbeat → chart comment warning
- **Failover threshold:** 120s → activates airbag trailing stop
- **Airbag:** ATR-based trail at 5×H1 ATR on ALL open positions across all magics
- **Trail direction:** Only tightens, never widens existing SL

---

## 10. Critical Fixes History

### Session 1 (May 2026)
- MT5Gateway thread-safe wrapper
- All bots ported to gateway pattern (`_api()` / `set_gateway()`)
- Unified runner: 5 daemon threads, SharedState IPC, magic isolation check
- CAB entry engine built from scratch (was MQL5 only)
- UnifiedFailover.mq5: single EA replacing 3 separate watchdogs

### Session 2
- Wilder ADX fix: mean-init for ADX smoothing step (all 3 bots) — **critical**, was 14× wrong
- Sniper watcher: 3-signal percentile regime classifier ported from CAB
- CAB: triple-gated reaper (SI + ER + consecutive bars), partial harvester, continuous tightening
- Ghost: STOPS_LEVEL guard on SL placement, spread guard on closes
- GridState.MAX_LEGS=4 hard cap

### Session 3
- Ghost Cache (magic 204) integrated — nth virtual layer exhaustion entry
- Per-personality leg TPs: 201=1.0R, 202=1.5R, 204=2.0R (was 0.5R flat — required 89% win rate)
- BE-lock ratchet: `_check_be_lock()` at +0.5R per leg
- Emergency OOB TP: 3×ATR broker-side failsafe on Fluid TP legs
- CAB regime TF: M1 → H4 (50 bars ≈ 8 days context)

### Session 4 (latest)
- **CAB tick=None crash fixed** — silent profit swallowing eliminated
- **CAB processed_actions reset fixed** — PROTECTOR/HARVESTER flags no longer wiped on reconnect
- **CAB HARVESTER regime lock removed** — now fires at 2.0R in any regime
- ST partial close thresholds fixed: SI gate 0.85→0.65, ATR mult 3.0→1.5
- ST TP ceiling: 10×ATR→5×ATR (was never hit on M30 Gold)
- ST R-lock ratchet: BE at +1R, lock 1R at +2R, lock 2R at +3R
- **Position caps raised**: ST and CAB max_positions 1→4 per instrument
- **Global position cap removed**: replaced by daily equity circuit breaker
- **Daily equity circuit breaker wired**: 10% max daily loss, blocks new entries, watchers continue

---

## 11. Architecture Decisions (Finalised)

### Position Caps
- **Ghost Grid:** MAX_LEGS=4 per probe — non-negotiable (accumulation architecture)
- **SuperTrend:** max_positions=4 per symbol — directional confirmation hypothesis
- **CAB:** max_positions=4 per symbol — sequential same-direction inversions = thesis confirmation
- **Global cap:** Removed. Circuit breaker is the correct global safety mechanism.

### Signal Sync (Planned — next implementation)
CAB Neural Link: when H4 opposite signal fires, apply sliding-scale response based on combined R + conviction score `(body_ratio × 0.6) + (body_size_in_ATR × 0.4) > 0.65`:

| Combined R at opposite signal | Action |
|---|---|
| < 0R | Kill all legs immediately |
| 0R – 0.5R | Kill all legs immediately |
| 0.5R – 1.2R | Move all SLs to BE + buffer, one H4 bar grace |
| 1.2R – 2.0R | Partial harvest 30-50%, trail remainder 1×H4 ATR |
| > 2.0R | Larger harvest 50-70%, very tight trail |

Multi-position evaluation uses **combined R**, not per-leg. Conviction threshold raised to 0.70 when 3-4 positions open.

### Exit Intelligence Roadmap (MES)
After 3-week Phase 2 data collection, R-threshold exits will be replaced/supplemented by a **Market Exit Score** (0–1) computed from: regime alignment (30%), conviction trend (25%), ATR trajectory (20%), directional momentum (15%), opposite signal quality (10%). MES < 0.30 exits regardless of R level.

---

## 12. Phase 2 Validation Criteria (3-Week Demo Run)

| Bot | Gate to pass |
|---|---|
| SuperTrend | avg R > 0 over ≥ 30 trades |
| CAB Watcher | REAPER false-cut rate < 30% |
| Ghost Grid | grid stop rate < 20% |
| Ghost Cache 204 | ≥ 10 fills in first week; 30+ fills for Gate ② comparison vs 202 |
| Unified | regime overlap ST/Ghost < 15%; combined drawdown < any individual bot |

**Bot-instrument fit matrix (Gate ⑤):** avg_R cross-tab by bot × instrument. Live deployment pairs decided from this data, not assumed.

---

## 13. Instrument Notes

| Instrument | Best fit (hypothesis) | Notes |
|---|---|---|
| XAUUSDm | All three bots | High ATR, strong session effects. Ghost Grid primary instrument. |
| XAGUSDm | SuperTrend, maybe Ghost | Higher vol than Gold, lower liquidity. Wider spread guard needed. |
| EURUSDm | SuperTrend | Lower ATR vs spread. M30 trend following most appropriate. |
| GBPUSDm | SuperTrend, CAB | Higher ATR for FX. H4 inversions worth testing. |

---

## 14. Pre-Flight Checklist Before Phase 2

- [ ] `core/supertrend_bot.py` placed in project (MISSING — upload required)
- [ ] All corrupted log files deleted before restart
- [ ] First run: ADX in sniper_brain.log between 10–60 (not 150–300)
- [ ] First run: conviction between 20–70 (not 100 every line)
- [ ] Within 48h: at least 1 magic 204 fire (lower N_LAYERS to 2 if zero after 5 days)
- [ ] Zero MAGIC_ISOLATION_BREACH in unified_runner.log after first 4 hours
- [ ] Zero "Heartbeat write failed" — UnifiedFailover.mq5 shows ONLINE
- [ ] CAB positions can open up to 4 per symbol simultaneously
- [ ] ST R-lock entries (R1_BE_LOCK, R2_LOCK_1R, R3_LOCK_2R) appear in logs after profitable trades
- [ ] CB check: drawdown calculation in code confirmed — do NOT trigger intentionally on demo

---

## 15. Remaining Development Tasks (before Phase 2 close)

**CRITICAL (code required):**
1. Signal Sync — CAB Neural Link (ss-register, ss-conviction, ss-table, ss-grid-level, ss-handoff)

**HIGH (config/data):**
2. Enable ST partial close in config.json for XAUUSDm and XAGUSDm
3. Ghost Grid 204 audit CSV columns (virtual_layer_depth, cache_age_seconds, etc.)
4. Ghost Grid session/condition filtering research (after Phase 2 data)

**MEDIUM:**
5. Adaptive calibration fully in-memory (sw-adaptive)
6. Async CSV write queue for unified_session_log.csv

---

## 16. Running the Bot

```bash
# Full unified run (recommended)
python unified_runner.py --account demo

# SuperTrend standalone (legacy)
python run_bot.py --account demo --symbols XAUUSDm,EURUSDm

# Structure verification
python verify_structure.py

# Unit tests
python test_cab_entry.py
python test_cab_gateway_port.py
python test_ghost_gateway_port.py
```

**Config location:** `config/config.json`  
**Key config values:**
```json
{
  "global_settings": {
    "max_daily_loss_percent": 10.0,
    "max_positions_per_symbol": 4,
    "cab_max_positions": 4
  }
}
```
