# Phase 3: Week 2 Implementation Plan

## Objective
The goal for Week 2 is to collect live market data on the Top 5 Stabilized Fixes while simultaneously porting the bot execution logic into the new strictly-typed, modular `v2/` architecture.

## 1. Live Data Collection (Legacy `unified_runner.py`)
While we build `v2/`, the legacy script continues to run 24/5 on the MT5 Demo.
- **Goal:** Collect 30+ trades for SuperTrend, CAB, and Ghost Grid.
- **Validation Gates:**
    - Verify `MAX_GLOBAL_POSITIONS = 30` circuit breaker behavior.
    - Validate MQL5 Failover EA successfully triggering on Magic number crashes.
    - Ensure CAB accurately recovers tickets that fail to close via MT5 broker spread spikes.

## 2. V2 Architecture Porting (Parallel Build)
We will incrementally build the new components in the `v2/` package.

### Step 2.1: The Market Oracle
- Complete the `market_oracle.py` calculations for ADX, MACD, and Regime definitions.
- Ensure the Oracle pushes data identically to the `KnowledgeRegister`.

### Step 2.2: Order Router
- Expand `order_router.py` to ingest the new KR Layer 3 Correlation Bucket rules.
- Test signal vetoing natively in the router logic.

### Step 2.3: Port Bot Logic
- **Ghost Sniper**: Strip out internal ATR math and replace with Oracle queries.
- **SuperTrend Bot**: Strip out internal regime definition and rely on KR layer.
- **CAB**: Adopt `TradeSignal` outputs in place of `gh.send_order()`.

## 3. Correlation Bucket Risk Implementation (Layer 3)
- Define `XAUUSDm` + `XAGUSDm` as the `GOLD_SILVER` risk silo.
- Define `EURUSDm` + `GBPUSDm` + `USDJPYm` as the `FX_MAJORS` risk silo.
- Inject hard cap logic into the KR to ensure that an individual silo cannot consume more than X% of account margin, regardless of how many bots are generating signals for that silo.

## 4. The Final V2 Cutover
Once the Dry-Run `v2_runner.py` produces the exact same execution decisions as the active legacy script, we will formally deprecate `unified_runner.py` and promote `v2_runner.py` to production.
