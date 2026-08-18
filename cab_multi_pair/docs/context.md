# CAB MASTER: System Context & Vision

## 🎯 The Core Objective
CAB (Context-Aware Bot) Master is an institutional-grade, multi-pair algorithmic trading framework built for MetaTrader 5 (specifically tailored for Exness execution). The system is designed to migrate away from rigid, speculative trading by implementing a quantitative, data-driven approach to market execution.

## 🧬 System DNA
The framework is built on three foundational pillars:
1. **Macro Context Validation:** Trades are strictly initiated upon H4 candle macro inversions and validated by localized H1 structural momentum.
2. **Dynamic Risk & State Memory:** Position sizing is equity-normalized, and every active trade maintains a localized "memory" of its journey—capturing Maximum Favorable Excursion (MFE) and Maximum Adverse Excursion (MAE) to govern trailing stops.
3. **Market Intelligencia:** The system does not just trade; it observes. Every execution is tagged with its surrounding environmental state (ADX momentum, ATR volatility regimes, liquidity sessions, and Macro DXY proxies) to fuel future statistical modeling.

## 🛡️ The Failover Philosophy
The Python execution engine is treated as a highly intelligent but potentially volatile node. It runs alongside a localized MQL5 Sentinel (`CAB_Global_Sentinel.mq5`) that monitors a localized heartbeat file. If Python crashes or disconnects, MQL5 instantly takes over risk management (trailing SL) to ensure capital preservation.