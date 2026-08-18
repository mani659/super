# V2 Migration Roadmap

This is the strict master tracking document for the V2 Architecture port. 
**RULE:** No phase can be started until the previous phase is fully validated by market data.

## Phase 1: Foundation (Complete)
- [x] Create Modular Doc Base
- [x] Step 2.1: Implement Market Oracle (v2/core/market_oracle.py)

## Phase 2: Core Routing & Intelligence (Complete)
- [x] Step 2.2: Implement Order Router (Layer 3 Correlation Buckets & Signal Vetoing)
- [x] Step 2.3: Expand Knowledge Register to track active Trade Theses

## Phase 3: Execution & Risk Management (In Progress)
- [x] Step 3.1: Build standard Trade Manager (Centralized BE+ and Trailing Stop logic)
- [x] Step 3.2: Port MT5 Gateway and Failover Heartbeat into v2/execution/

## Phase 4: Strategy Porting
- [x] Step 4.1: Port SuperTrend Logic (Strictly mathematical 1:1)
- [x] Step 4.2: Port Ghost Grid Logic (Strictly mathematical 1:1)
- [x] Step 4.3: Port CAB Super Logic (Strictly mathematical 1:1)

## Phase 5: Unified Orchestration
- [x] Step 5.1: Build v2_unified_runner.py
- [ ] Step 5.2: Shadow Testing (Run V2 in parallel with V1 to verify identical ticket generation)
