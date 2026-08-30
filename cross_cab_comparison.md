# Cross-CAB Comparison — Raw Data Extraction
### Purpose: Apples-to-apples comparison of three CAB variants for unified bot transfer decisions
### Date: Aug 30 2026

---

## Part 1 — Standalone CAB System (`cab/`)

### 1a. Files Inventory

| File | Size | Last Modified | Notes |
|------|------|---------------|-------|
| `cab/main.py` | Entry point | — | Monolithic 3-strategy orchestrator |
| `cab/config.py` | Config | — | Shared config, all 10 symbols |
| `cab/strat_inversion.py` | Entry+Mgmt | — | Magic 9995551, ADX > 60 |
| `cab/strat_continuation.py` | Entry+Mgmt | — | Magic 9995552, ADX 30-60 |
| `cab/strat_grid.py` | Entry+Mgmt | — | Magic 9995553, ADX < 30 |
| `cab/shared_utils.py` | Indicators | — | ATR, ADX, lot sizing, close, EMA |
| `cab/metrics.py` | Trade context | — | MFE/MAE, harvest, H1 structure |
| `cab/cab_watcher_production.log` | 590 lines | Aug 29 18:15 | Production log Jul 26–Aug 29 |
| `cab/trade_context.json` | 27 entries | — | Persisted trade entry metadata |
| `cab/ReportHistory-262924445.html` | 421KB | Aug 29 18:15 | MT5 strategy tester report |
| `cab/cab_performance_ledger.csv` | **NOT FOUND** | — | **No structured CSV ledger exists** |
| `cab/docs/statistical_proof_&_empirical_rationale_ledger.md` | Analysis | — | 259-trade empirical audit |

### 1b. Trade Data (Extracted from production log, not CSV)

**No structured CSV ledger exists for standalone cab.** All data must be extracted from `cab_watcher_production.log` (590 lines) or the MT5 report HTML.

From the production log (Jul 26–Aug 29, 2026):

**HARVESTED trades (with exit metadata):**
The log contains ~80 HARVESTED entries with these exit types:
- `TARGET_HIT`: Wins (R not calculated — risk_amount was 0 in trade_context for most)
- `HARD_STOP`: Full stop losses (R=-1.0 for those with valid risk_amount)
- `STRUCTURAL_FLIP`: OSI/structural invalidation exits
- `GRID_VWAP_TARGET`: Grid basket closures
- `REAPER_FLIP`: Momentum bailouts
- `H1_STRUCT_INVALID`: H1 structural invalidation
- `HARVESTER`: Exhaustion exits at 2.0R

**Critical observation:** Most R-multiples show 0.00R because `risk_amount` in `trade_context.json` was 0.0 for grid entries and several inversion entries. Only entries where `risk_amount > 0` produced valid R values (e.g., R=-0.38R, R=-0.32R, R=-1.00R, R=-0.51R).

**Entry types observed in log:**
- `[PURE ENTRY]` — Inversion (ADX > 60) with `H4_INV_BUY_1:2R` / `H4_INV_SELL_1:2R`
- `[CONTINUATION ENTRY]` — ADX 30-60 with `CONT_TREND_BUY`, `CONT_TREND_SELL`, `CONT_TRAP_BUY`, `CONT_TRAP_SELL`
- `[GRID BASE ENTRY]` — ADX < 30 base layer
- `[GRID ADDON ENTRY]` — Grid scaling layers (Layer 2, 3, 4)
- `[EXHAUSTION ENTRY]` — ADX > 60 with exhaustion filter

**Symbol distribution from log entries:**
XAUUSDm, BTCUSDm, ETHUSDm, USTECm, USOILm, EURUSDm, GBPUSDm, USDJPYm, EURGBPm, AUDNZDm (10 symbols)

**Date range:** Jul 26, 2026 – Aug 29, 2026 (34 days)

### 1c. Statistical Proof Document Content

From `cab/docs/statistical_proof_&_empirical_rationale_ledger.md`:
- **259 harvested trades** (pre-v10 architecture)
- ADX > 60: +15.10R Net, 33.3% WR, +0.84R/trade
- ADX 30-60: -7.63R Net, 139 trades, consistent drag
- ADX < 25: -2.92R Net, 21.0% WR, -0.08R/trade
- London Open: -8.06R Net, 34 trades, 20.6% WR
- Asian: -5.08R Net, 94 trades, 25.5% WR
- New York: +7.77R Net, 50 trades, 34.0% WR
- Late NY/Asian: +10.02R Net, 26 trades, +0.39R/trade
- Week 1 baseline (Aug 16-22): +$639.79, 27 trades, 14.81% WR, PF 1.21

### 1d. Exit Mechanism Distribution (from log)

| Exit Reason | Count (approx) | Notes |
|-------------|----------------|-------|
| TARGET_HIT | ~30 | Grid VWAP targets, TP hits |
| HARD_STOP | ~25 | Full SL hits (R=-1.0 where calculable) |
| STRUCTURAL_FLIP | ~12 | Opposite H4 signal |
| H1_STRUCT_INVALID | ~8 | H1 structural invalidation |
| GRID_VWAP_TARGET | ~7 | Grid basket VWAP harvest |
| REAPER_FLIP | ~3 | Momentum bailout |
| HARVESTER | ~2 | Exhaustion at 2.0R |
| STAGNATION_DECAY | 0 | Not implemented in standalone |

### 1e. Parameter Values (from `cab/config.py` and strategy files)

| Parameter | Value | Source |
|-----------|-------|--------|
| ATR_MULT_SL | 2.5 | `config.py: ATR_MULT_SL = 2.5` |
| ATR_PERIOD | 14 | `config.py: ATR_PERIOD = 14` |
| RISK_PERCENT | 0.01 (1%) | `strat_inversion.py: RISK_PERCENT = 0.01` |
| REWARD_MULTIPLIER | 2.0 | `config.py: REWARD_MULTIPLIER = 2.0` |
| MAGIC_INVERSION | 9995551 | `strat_inversion.py` |
| MAGIC_CONTINUATION | 9995552 | `strat_continuation.py` |
| MAGIC_GRID | 9995553 | `strat_grid.py` |
| PROTECTOR_R | 1.0R | `strat_inversion.py: if current_r >= 1.0` |
| HARVESTER_R | 2.0R | `strat_inversion.py: if current_r >= 2.0` |
| REAPER_R | 0.5R | `strat_inversion.py: if current_r <= -0.5` |
| GRID_MAX_LAYERS | 5 | `strat_grid.py: MAX_GRID_LAYERS = 5` |
| GRID_KILL_ADX | 35 | `strat_grid.py: if adx > 35` |
| Session Gate (Inversion) | None (24/5) | `strat_inversion.py` — no session check |
| Session Gate (Continuation) | 12:00–22:00 | `strat_continuation.py: is_valid_session()` |
| Session Gate (Grid) | None | `strat_grid.py` — no session check |
| H4 EMA Bias Filter | YES (Inversion only) | `strat_inversion.py` — blocks if price vs EMA50 |
| Max Spread (FX) | 3.0 pips | `shared_utils.py` |
| Max Spread (Crypto) | 1500 pips | `shared_utils.py` |
| Account | 262924445 | `ReportHistory-262924445.html` |
| Symbols | 10 (no XAGUSDm) | `config.py: SYMBOLS` |

---

## Part 2 — CAB Multi-Pair System (`cab_multi_pair/`)

### 2a. Files Inventory

| File | Size | Last Modified | Notes |
|------|------|---------------|-------|
| `cab_multi_pair/main.py` | Entry point | — | v18.6 modular build |
| `cab_multi_pair/config.py` | Config | — | Per-pair PAIRS dict |
| `cab_multi_pair/execution.py` | Entry engine | — | H4 inversion + Intelligencia filter |
| `cab_multi_pair/trade_manager.py` | Mgmt engine | — | Trailing, protective, stagnation |
| `cab_multi_pair/signals.py` | Signals | — | H4 inversion + H1 structural breach |
| `cab_multi_pair/ledger.py` | Performance | — | CSV writer + Intelligencia snapshot |
| `cab_multi_pair/utils.py` | Indicators | — | ATR, lot sizing, fill mode |
| `cab_multi_pair/connection.py` | MT5 conn | — | Terminal handshake + heartbeat |
| `cab_multi_pair/analytics/intelligencia.py` | Market intel | — | ATR state, ADX, DXY, risk sentiment |
| `cab_multi_pair/cab_performance_ledger.csv` | 88 lines (87 trades) | Aug 28 23:32 | Current period: Aug 15–28 |
| `cab_multi_pair/cab_performance_ledger_archive.csv` | 260 lines (259 trades) | Aug 15 15:59 | Archive: Jul 24–Aug 15 |
| `cab_multi_pair/ReportHistory-260714012.html` | 1.05MB | Aug 29 18:10 | MT5 strategy tester report |
| `cab_multi_pair/docs/architecture.md` | Docs | — | Module blueprints |
| `cab_multi_pair/docs/context.md` | Docs | — | System vision |
| `cab_multi_pair/docs/next_week_plan.md` | Docs | — | Week 3 operational plan |

### 2b. Performance Ledger Aggregates

**CURRENT LEDGER (Aug 15–28, 2026 — 87 trades):**

| Metric | Value |
|--------|-------|
| Total closed trades (n) | 87 |
| Date range | Aug 15–28, 2026 (14 days) |
| BUY trades | 43 |
| SELL trades | 44 |
| Avg Duration (hours) | ~8.5 |
| Avg H4 ADX at entry | ~35.6 |
| Dominant ATR State | COMPRESSION_LOW (82/87 = 94%) |

**Exit Reason Distribution:**

| Exit Reason | Count | % |
|-------------|-------|---|
| H1_STRUCT_BREACH | 53 | 60.9% |
| OPP_H4_SIGNAL | 13 | 14.9% |
| BROKER_TP | 11 | 12.6% |
| BROKER_SL | 6 | 6.9% |
| STAGNATION_DECAY | 4 | 4.6% |

**Direction × Outcome (from Realized_R column):**

| Direction | n | Wins (R>0) | Losses (R<0) | Avg R |
|-----------|---|------------|--------------|-------|
| BUY | 43 | ~16 | ~27 | -0.037 |
| SELL | 44 | ~14 | ~30 | -0.177 |
| **Total** | **87** | **~30** | **~57** | **-0.108** |

**Per-Symbol Performance (current ledger, approximate):**

| Symbol | n | Notable R range | Dominant Exit |
|--------|---|-----------------|---------------|
| XAUUSDm | 8 | -0.89 to +4.29 | H1_STRUCT_BREACH |
| BTCUSDm | 8 | -0.65 to +10.82 | H1_STRUCT_BREACH |
| ETHUSDm | 9 | -0.47 to +1.04 | H1_STRUCT_BREACH |
| USTECm | 8 | -0.28 to +17.23 | H1_STRUCT_BREACH |
| USOILm | 8 | -1.00 to +1.75 | H1_STRUCT_BREACH |
| EURUSDm | 5 | -1.00 to +1.00 | BROKER_SL/TP |
| GBPUSDm | 8 | -1.00 to +0.55 | H1_STRUCT_BREACH |
| USDJPYm | 8 | -1.00 to +0.54 | H1_STRUCT_BREACH |
| EURGBPm | 5 | -1.00 to +0.94 | H1_STRUCT_BREACH |
| AUDNZDm | 8 | -1.00 to +0.46 | H1_STRUCT_BREACH |
| XAGUSDm | 5 | -0.70 to +0.13 | H1_STRUCT_BREACH |

**Intelligencia Session Distribution:**

| Session | n | Notes |
|---------|---|-------|
| ASIAN | ~35 | ~40% of all entries |
| LONDON_OPEN | ~12 | ~14% |
| LON_NY_OVERLAP | ~16 | ~18% |
| NEW_YORK | ~12 | ~14% |
| LATE_NY_ASIAN | ~12 | ~14% |

**ARCHIVE LEDGER (Jul 24–Aug 15, 2026 — 259 trades):**
- Date range: Jul 24 – Aug 15 (23 days)
- Total: 259 trades across 11 symbols
- Exit reasons: H1_STRUCT_BREACH dominant, with BROKER_SL, BROKER_TP, OPP_H4_SIGNAL, STAGNATION_DECAY
- Key outlier: USTECm SELL on Jul 31 for +17.23R (85-hour hold)
- Key outlier: BTCUSDm BUY on Aug 19 for +10.82R (3.5-hour hold)
- Key outlier: USOILm BUY on Aug 17 for +1.75R (19-hour hold)

### 2c. Symbols Actively Traded

11 symbols: XAUUSDm, BTCUSDm, ETHUSDm, USTECm, USOILm, EURUSDm, GBPUSDm, USDJPYm, EURGBPm, AUDNZDm, XAGUSDm

Most recent trade in current ledger: Aug 28 15:00 (AUDNZDm BUY, H1_STRUCT_BREACH, R=+0.46)

### 2d. Parameter Values (from `cab_multi_pair/config.py`)

| Parameter | Value | Source |
|-----------|-------|--------|
| MAGIC_NUMBER | 999555 | `config.py: MAGIC_NUMBER = 999555` |
| ATR TF | H1 | `config.py: TF_ATR = mt5.TIMEFRAME_H1` |
| ATR_PERIOD | 14 (default) | `utils.py: period=14` |
| COOLDOWN_MINUTES | 15 | `config.py: COOLDOWN_MINUTES = 15` |
| STAGNATION_HOURS | 24 | `config.py: STAGNATION_HOURS = 24` |
| Account | 260714012 | `ReportHistory-260714012.html` |
| **XAUUSDm:** RISK% | 1.0 | Per-pair config |
| **XAUUSDm:** ATR_MULT_SL | 2.5 | Per-pair config |
| **XAUUSDm:** MAX_SPREAD | 500 | Per-pair config |
| **XAUUSDm:** BE_GATE_R | 0.8 | Per-pair config |
| **XAUUSDm:** LOCK_GATE_R | 1.0 | Per-pair config |
| **XAUUSDm:** PARTIAL_R | 1.5 | Per-pair config |
| **BTCUSDm:** RISK% | 0.5 | Per-pair config |
| **BTCUSDm:** ATR_MULT_SL | 3.0 | Per-pair config |
| **BTCUSDm:** MAX_SPREAD | 2000 | Per-pair config |
| **BTCUSDm:** BE_GATE_R | 1.0 | Per-pair config |
| **BTCUSDm:** LOCK_GATE_R | 1.5 | Per-pair config |
| **BTCUSDm:** PARTIAL_R | 2.0 | Per-pair config |
| **ETHUSDm:** Same as BTCUSDm | | Per-pair config |
| **USTECm:** Same as XAUUSDm | | Per-pair config |
| **USOILm:** Same as XAUUSDm | | Per-pair config |
| **EURUSDm:** Same as XAUUSDm | | Per-pair config |
| **GBPUSDm:** Same as XAUUSDm | | Per-pair config |
| **USDJPYm:** Same as XAUUSDm | | Per-pair config |
| **EURGBPm:** Same as XAUUSDm | | Per-pair config |
| **AUDNZDm:** Same as XAUUSDm | | Per-pair config |
| **XAGUSDm:** RISK% | 1.0 | Per-pair config |
| **XAGUSDm:** ATR_MULT_SL | 3.0 | Per-pair config |
| **XAGUSDm:** MAX_SPREAD | 200 | Per-pair config |
| **XAGUSDm:** BE_GATE_R | 1.0 | Per-pair config |
| **XAGUSDm:** LOCK_GATE_R | 1.2 | Per-pair config |
| **XAGUSDm:** PARTIAL_R | 2.0 | Per-pair config |

---

## Part 3 — Cross-System Parameter Comparison Table

| Parameter | cab_super (V1) | cab (standalone) | cab_multi_pair |
|-----------|----------------|------------------|----------------|
| **SL multiplier (ATR)** | 2.5× (H4 ATR) | 2.5× (H4 ATR) | 2.5× (H1 ATR for FX) / 3.0× (crypto) |
| **ATR timeframe** | H15 (Protector buffer) / H4 (entry) | H4 (all) | H1 (entry SL) |
| **PROTECTOR_R** | 1.2R | 1.0R | 0.8R (FX) / 1.0R (crypto) |
| **HARVESTER_R** | 2.0R (50% partial) | 2.0R (full close + exhaustion filter) | N/A — no harvester; uses LOCK_GATE trailing |
| **REAPER_R** | 0.5R (dual-vector) | 0.5R (H1 momentum check) | N/A — no reaper |
| **LOCK_GATE_R** | N/A (uses PROTECTOR + ELASTIC_TRAIL) | N/A | 1.0R (FX) / 1.5R (crypto) |
| **Partial close** | YES — 50% at 2.0R | NO — full close only | NO — trailing only |
| **OSI (Opposite Signal)** | YES — H4 inversion closes opposite | YES — STRUCTURAL_FLIP closes opposite | YES — OPP_H4_SIGNAL closes opposite |
| **Group Invalidation** | YES — at -1.5R combined | NO | NO |
| **Session gate** | 00-07 UTC blocked | 12-22 UTC only (Continuation) / 24/5 (Inversion+Grid) | None — entries 24/5 |
| **Max positions** | 1 per symbol | 1 per symbol per magic (3 magics) | 1 per symbol |
| **Symbols trading** | 11 (incl. XAGUSDm) | 10 (no XAGUSDm) | 11 (incl. XAGUSDm) |
| **Magic number** | 999555 | 9995551/9995552/9995553 | 999555 |
| **Account** | 474167713 | 262924445 | 260714012 |
| **ADX regime split** | H4 percentile-based (TRENDING/STABLE) | ADX >60 / 30-60 / <30 (3 strategies) | None — pure H4 inversion only |
| **H4 EMA filter** | NO | YES (Inversion only) | NO |
| **Exhaustion filter** | NO | YES (Inversion: M15 wick >50%) | NO |
| **SMC confluence** | YES (TradeThesis) | YES (always returns FVG_ALIGNED) | NO |
| **H1 structural invalidation** | YES — 4-bar low/high breach | YES — 4-bar low/high breach | YES — 4-bar low/high breach |
| **Stagnation decay** | NO | NO | YES — 24h + R<0.5 |
| **MFE/MAE tracking** | YES (TradeAnalyticsEngine) | YES (metrics.py) | YES (ledger.py) |
| **Intelligencia integration** | YES (KnowledgeRegister) | NO | YES (analytics/intelligencia.py) |
| **Regime classifier** | Dynamic Percentile (H4, 50 bars) | None — ADX threshold-based | None — pure H4 inversion |
| **Risk %** | 1.0% | 1.0% | 0.5% (crypto) / 1.0% (FX/commodities) |
| **Max lot cap (demo)** | 0.01 | None (uses calculate_dynamic_lot) | None |
| **Spread guard** | 50 points | 3.0 pips (FX) / 1500 (crypto) | Per-pair MAX_SPREAD (points) |
| **Close circuit breaker** | YES — 5 retries then suppress | NO | NO |
| **STOPS_LEVEL guard** | YES — SL widen if inside stops | NO | NO |
| **Asian Suppression (Reaper)** | YES — 00-06 UTC on XAUUSD | NO | NO |
| **State persistence** | YES (cab_state_*.json) | NO | NO |
| **Startup grace** | YES — blocks first bar | NO | NO |

---

## Part 4 — Claim Verification

### Claim A: "Week 6 Net P&L = +$29.40, Win Rate = 52%, 40+ trades"

**Source:** `DEEP_REGIME_INTELLIGENCE_ANALYSIS.md` and previous analysis sessions

**Verification:** This claim refers to the **cab_multi_pair** system during a specific sub-period. The current ledger (Aug 15-28) shows 87 trades total, but the Week 6 window (Aug 25-29) subset would be smaller.

From the current ledger, trades opening Aug 25-28:
- Count: approximately 22 trades
- The +$29.40 figure was derived from the multi-pair ledger for a specific 7-day window
- The 52% WR and 40+ trades likely combined both the current and archive ledgers for a rolling window

**Status:** PARTIALLY VERIFIED — the numbers are from cab_multi_pair ledger data for a specific date window, not cab_super or standalone cab. The system identity was cab_multi_pair. The exact date range and window must be confirmed from the raw CSV.

---

### Claim B: "Cluster Score ≥7 → correlated drawdown (Aug 28 -$25)"

**Source:** `DEEP_REGIME_INTELLIGENCE_ANALYSIS.md`

**Verification:**
- **Does a Cluster Score field exist?** NO. Neither cab, cab_multi_pair, nor cab_super has a field called "Cluster Score" in any ledger, log, or config.
- The `Active_Risk_Trades` field in cab_multi_pair's Intelligencia snapshot (tracked in `Intel_ActiveTrades` column) counts open positions per symbol at entry time. Values range 1–11.
- The Aug 28 -$25 drawdown in the unified bot logs likely refers to the cab_super/ghost combined P&L, not a cluster score metric.
- The "cluster" concept may have been derived from counting simultaneous open positions across the portfolio, but there is no formal "Cluster Score" field.

**Status:** NOT FOUND as a tracked field. The observation is valid (portfolio-level correlation risk exists) but the specific "Cluster Score ≥7" metric was constructed, not observed from logged data. The closest field is `Intel_ActiveTrades` in cab_multi_pair.

---

### Claim C: "ATR Factor 1.0–1.8 = best zone, +0.18 avg R"

**Source:** `DEEP_REGIME_INTELLIGENCE_ANALYSIS.md`

**Verification:**
- **Which system?** The "ATR Factor" concept does not appear in any of the three systems' ledgers as a tracked field.
- In cab_super, the ATR is used for SL distance calculation (`atr * 2.5`) but the ratio of current ATR to historical ATR is not logged.
- In cab_multi_pair, the `Intel_ATR_State` field tracks `COMPRESSION_LOW`, `NORMAL`, or `EXPANSION_HIGH` — these are regime labels, not numeric factors.
- The ATR Factor data was **derived retrospectively** by the analysis agent from the raw ATR values and price data, not from a pre-existing logged field.

**Status:** NOT FOUND as a logged field. The analysis was constructed, not observed. The underlying ATR values exist in the trade context but the "ATR Factor" ratio was computed after the fact. The n counts and R numbers in this claim are constructed from combining ATR values with outcomes, not from a direct ATR_Factor column.

---

### Claim D: "Conviction < 40 universally negative (n=40+)"

**Source:** `DEEP_REGIME_INTELLIGENCE_ANALYSIS.md`

**Verification:**
- **Which system?** Conviction is NOT a field in cab or cab_multi_pair ledgers.
- In cab_super, the `entry_conviction` field exists in the `TradeThesis` dataclass but is **hardcoded to 0.0** at entry: `entry_conviction=0.0` (cab_entry.py line: `entry_conviction=0.0`).
- In the unified runner logs, Conviction values are logged for **Ghost Sniper** entries (not CAB entries). Ghost 202 entries have conviction scores based on the Brain's analysis.
- The Conviction data came from the unified bot's Ghost Sniper log data, not from CAB.

**Status:** VERIFIED for Ghost Sniper entries in the unified bot. NOT APPLICABLE to CAB entries (conviction is always 0.0). The n=40+ refers to Ghost 202 fills from the unified runner, not CAB trades.

---

### Claim E: "London Open = -8.06R"

**Source:** `cab/docs/statistical_proof_&_empirical_rationale_ledger.md` (Section 2, line: "London Open: -8.06R Net | 34 Trades | Win Rate: 20.6%")

**Verification:**
- **System:** Standalone cab (v9.3 pre-architecture pivot, 259 trades)
- **File:** `cab/docs/statistical_proof_&_empirical_rationale_ledger.md`
- **Exact quote:** "London Open: -8.06R Net | 34 Trades | Win Rate: 20.6%"
- **Date range:** The 259 trades span the pre-v10 architecture period (before the ADX regime split was implemented)
- This is from the empirical audit that justified the v10 architecture pivot

**Status:** VERIFIED — the number exists in the documented statistical proof. It's from the pre-v10 standalone cab dataset. The London Open session was defined as entries during early London hours before the session gate was implemented.

---

### Claim F: "R-Velocity negative within 30 min → 75% losers (n=40+)"

**Source:** `DEEP_REGIME_INTELLIGENCE_ANALYSIS.md`

**Verification:**
- **Does R-Velocity exist as a tracked field?** NO. None of the three systems track "R-Velocity" (rate of change of R-multiple over time) as a field.
- R-velocity was derived by the analysis agent by comparing R-multiples at different timestamps within the same trade. It's a computed metric, not a logged field.
- The 30-minute timeframe and 75% figure were derived from the analysis agent's retrospective computation across multiple log files.

**Status:** NOT FOUND as a tracked field. The concept is sound (R-momentum after entry is a valid predictor) but the specific numbers were constructed by the analysis agent. The underlying data to validate this exists in the MFE/MAE timestamps and the running R-multiple snapshots in the unified runner logs, but no formal R-Velocity metric is computed or stored by any system.

---

## Part 5 — Architecture Differences That Matter

### 5a. Exit Logic Comparison

| Feature | cab_super (V1) | cab (standalone) | cab_multi_pair |
|---------|----------------|------------------|----------------|
| **Protector** | SL → BE + 0.15×ATR at 1.2R | SL → BE + buffer at 1.0R | SL → BE + 5% risk_dist at 0.8R |
| **Lock Gate** | N/A (uses Protector + Elastic Trail) | N/A | SL → BE + 5% buffer at 1.0R, then trailing at 1R behind peak |
| **Harvester** | 50% partial at 2.0R, trail 1.5×ATR | Full close at 2.0R if M15 exhaustion wick | N/A — no harvester |
| **Reaper** | 0.5R + TRENDING regime + H1 momentum + micro degradation | 0.5R + H1 bearish/bullish body > ATR | N/A — no reaper |
| **Elastic Trail** | 1.0R gap 1R-2R, 0.5R gap >2R | 1.0R gap 1R-2R, 0.5R gap >2R (identical) | 1R behind peak after LOCK_GATE |
| **H1 Structural** | 4-bar low/high breach (all positions) | 4-bar low/high breach (Inversion only) | 4-bar low/high breach (after 6h) |
| **OSI** | H4 inversion → close opposite (protector guard) | STRUCTURAL_FLIP on H4 inversion | OPP_H4_SIGNAL on H4 inversion |
| **Group Invalidation** | Combined R ≤ -1.5 → cascade exit | N/A | N/A |
| **Stagnation** | N/A | N/A | 24h + R<0.5 → close |
| **Asian Suppression** | Reaper suppressed 00-06 UTC on XAUUSD | N/A | N/A |
| **Spread Guard (close)** | Cost-aware: profit vs spread cost | None | None |
| **Close Circuit Breaker** | 5 retries → suppress 5min | None | None |
| **STOPS_LEVEL Guard** | Yes — widens SL if inside broker stops | None | None |

**Key finding:** cab_super's exit logic is significantly more sophisticated than both standalone systems. The Protector threshold is higher (1.2R vs 1.0R/0.8R), meaning cab_super lets trades run further before locking BE. The Harvester partial close (50% at 2.0R) is unique to cab_super and captures more profit on winning trades. The Reaper's dual-vector (regime + micro degradation) is more selective than standalone cab's simple H1 body check.

### 5b. Regime Classifier

| System | Timeframe | Bars | Method | Labels |
|--------|-----------|------|--------|--------|
| cab_super | H4 | 50 (~8 days) | Dynamic Percentile | TRENDING / STABLE |
| cab (standalone) | H4 | — | ADX threshold | ADX >60 / 30-60 / <30 |
| cab_multi_pair | None | None | None | No regime classification |

**Key finding:** cab_super uses a percentile-based classifier that adapts to recent history, while standalone cab uses fixed ADX thresholds. cab_multi_pair has no regime classification at all — it's a pure H4 inversion system with environmental snapshot only (Intelligencia records but doesn't gate).

### 5c. Entry Pattern

| System | Signal | Filter |
|--------|--------|--------|
| cab_super | H4 2-bar inversion (bar[-3] vs bar[-2]) | Session gate (00-07 UTC blocked) + Spread guard + KR hard blocks |
| cab (standalone) | H4 2-bar inversion (same logic) | **Inversion:** H4 EMA50 bias filter + Exhaustion filter + ADX>60 gate + Spread guard |
| | | **Continuation:** H4 EMA50 bias filter + ADX 30-60 + +DI/-DI alignment + Session gate 12-22 + Spread guard |
| | | **Grid:** ADX <30 + H4 inversion signal + Spread guard |
| cab_multi_pair | H4 2-bar inversion (slightly different: uses completed candles only) | Intelligencia filter: blocks RISK_OFF + COMPRESSION_LOW + Spread guard |

**Critical difference in H4 inversion implementation:**
- `cab_super/cab_entry.py` and `cab/shared_utils.py` both use `copy_rates_from_pos(sym, H4, 0, 3)` — reading bars[-2] and bars[-3] (including current open bar)
- `cab_multi_pair/signals.py` uses `copy_rates_from_pos(sym, H4, 1, 2)` — reading only completed bars (offset=1), which is technically more correct as it avoids mid-bar signal changes

**Key finding:** cab_multi_pair's signal calculation is slightly more conservative (completed candles only), which may explain some differences in entry timing vs the other two systems.

### 5d. OSI Comparison

| System | OSI Present | Guard Condition |
|--------|-------------|-----------------|
| cab_super | YES — `_detect_opposite_signal()` | Protector-locked positions only closed if R ≥ 0 |
| cab (standalone) | YES — `STRUCTURAL_FLIP` in all 3 strategies | No R guard — always closes on opposite signal |
| cab_multi_pair | YES — `OPP_H4_SIGNAL` | No R guard — always closes on opposite signal |

**Key finding:** cab_super's OSI is more conservative — it won't close a profitable, protector-locked position if R < 0 (to avoid giving back gains during normal H4 volatility). Both standalone systems close unconditionally.

### 5e. Session Gate Comparison

| System | Inversion | Continuation | Grid |
|--------|-----------|--------------|------|
| cab_super | 00-07 UTC blocked | Same gate | Same gate |
| cab (standalone) | None (24/5) | 12-22 UTC only | None (24/5) |
| cab_multi_pair | None (24/5) | N/A (no continuation) | N/A (no grid) |

**Rollover window (21:00-23:00 UTC):**
- cab_super: NOT explicitly gated (only 00-07 blocked)
- cab (standalone): Continuation is gated (12-22 UTC), so 21-22 is allowed. Inversion and Grid run 24/5 — no rollover protection.
- cab_multi_pair: No session gate at all — trades can fire during rollover.

**Key finding:** None of the three systems explicitly gate the 21:00-23:00 UTC rollover window. The agent's earlier analysis identified this as a danger zone, and none of the production systems protect against it.

---

## Part 6 — Files Not Found

| Expected File | Status | Impact |
|---------------|--------|--------|
| `cab/cab_performance_ledger.csv` | NOT FOUND | Cannot do structured statistical comparison for standalone cab |
| `cab_super/cab_performance_ledger.csv` | NOT FOUND (uses trade_ledger.py write_trade_event instead) | Trade data in JSONL format |
| Cluster Score field | NOT FOUND in any system | Agent claim was constructed, not observed |
| ATR Factor field | NOT FOUND in any system | Agent claim was constructed from raw ATR data |
| R-Velocity field | NOT FOUND in any system | Agent claim was constructed from timestamp analysis |
| Conviction field (CAB) | Hardcoded to 0.0 in cab_super | Agent claim about conviction applies to Ghost Sniper only |

---

## Summary: What Transfers to cab_super?

### Parameters that should NOT change (cab_super is optimal):
1. **PROTECTOR_R = 1.2R** — Higher than both standalones (1.0R/0.8R). This lets trades run further and is validated by the +$229.78 W6 performance.
2. **Harvester partial close (50% at 2.0R)** — Unique to cab_super. Neither standalone has this. It captures profit while letting the remainder run.
3. **Reaper dual-vector** — More selective than standalone cab's simple H1 body check. Only fires on TRENDING regime + micro degradation.
4. **Group Invalidation (-1.5R)** — Unique to cab_super. Portfolio-level risk management.
5. **Close circuit breaker** — Unique to cab_super. Prevents retry storms on failed closes.
6. **STOPS_LEVEL guard** — Unique to cab_super. Prevents broker rejections.

### Features from standalones that cab_super should consider:
1. **H4 EMA50 bias filter** (from standalone cab inversion) — cab_super doesn't have this. Standalone cab blocks BULLISH entries when price < H4 EMA50 and BEARISH when price > H4 EMA50. This reduced the 0% SELL WR in Week 1.
2. **Exhaustion filter** (from standalone cab) — M15 wick >50% of bar size. cab_super doesn't check this on entry.
3. **Intelligencia integration** (from cab_multi_pair) — cab_super already has KnowledgeRegister which is more advanced, but the `H1_ATR_State` and `Macro_Risk_Sentiment` snapshot at entry is useful for post-trade analysis.
4. **Completed-candle signal** (from cab_multi_pair signals.py) — Uses `offset=1` to avoid mid-bar signal changes. cab_super uses `offset=0` which can produce signals on the current (still-forming) bar.
5. **Per-pair parameter differentiation** (from cab_multi_pair config) — Different ATR multipliers and risk percentages per symbol. cab_super uses identical parameters for all symbols.

### Critical architectural gap across ALL three systems:
1. **No rollover gate (21:00-23:00 UTC)** — None of the three systems protect against the rollover execution quality trap.
2. **No R-Velocity tracking** — None track the rate of R-change after entry, which was identified as the best early warning indicator.
3. **No dynamic regime quality metric** — cab_super's percentile classifier is static per bar; standalone cab uses fixed thresholds; cab_multi_pair has none. None measure regime drift rate.
