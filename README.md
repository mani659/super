# MT5 Algorithmic Trading Suite
An enterprise-grade, multi-bot algorithmic trading matrix built for MetaTrader 5. This suite utilizes advanced Machine Learning (K-Means clustering), centralized cross-bot state management, and strict risk controls to navigate the Forex and CFD markets autonomously.

> ⚠️ **DISCLAIMER**: This project is for **EDUCATIONAL PURPOSES ONLY**. Trading forex/CFDs involves substantial risk of loss and is not suitable for all investors. Past performance is not indicative of future results.

---

## 🌟 System Architecture

The project has evolved into a sophisticated two-tier architecture:

### 1. V1: The Unified Runner (Legacy/Stable)
The original execution engine (`unified_runner.py`) running the legacy SuperTrend and Ghost Bot implementations. Features robust logging, crash recovery, and multithreading.

### 2. V2: The Modular Execution Matrix (Next-Gen)
A complete ground-up rewrite located in the `v2/` directory, built for strict institutional-grade execution.
- **Strict Data Contracts:** Powered by Python `dataclasses` (`TradeSignal`, `TradeThesis`, `MarketSnapshot`) ensuring zero ambiguity in state transfers.
- **Centralized Trade Management:** Execution and lifecycle management are entirely decoupled from signal generation.
- **Global Knowledge Register:** A thread-safe, cross-bot memory bank that tracks macro market regimes, ADX convictions, and trade theses across all active symbols.

---

## 🧠 Core Systems (V2)

### 📚 Knowledge Register (`v2.core.knowledge_register`)
The "brain" of the operation. It maintains state synchronization across the entire matrix:
- **Market State:** Tracks ATR, ADX, and mathematical Market Regimes (Trending vs Ranging) for multiple symbols simultaneously.
- **Thesis Tracking:** Every trade submitted to the market must register a `TradeThesis`. This prevents rogue executions and allows the system to recover state instantly on reboot (`v2_knowledge_state.json`).

### 🛡️ Centralized Trade Manager (`v2.execution.trade_manager`)
Manages the lifecycle of all open positions across all bots.
- **R-Based BE Ratchet:** Automatically locks trades at Breakeven + $5 once they reach 1.0R in floating profit.
- **Dynamic Trailing:** Trails profitable positions exactly 1.0R behind the Maximum Favorable Excursion (MFE).
- **H1 Structural Invalidation:** A critical bailout mechanism that instantly kills losing trades if the H1 market structure breaks against the position, overriding the hard Stop Loss.
- **Grid State Management:** Seamlessly manages complex multi-leg Grid states (Magic 204).

### 🔌 MT5 Gateway (`v2.execution.mt5_gateway`)
A resilient, error-handling wrapper around the raw MetaTrader 5 API.
- Implements the **Unified Failover** system (`UnifiedFailover.mq5`).
- Handles terminal connection drops, context errors, and slippage protections.

---

## 🤖 Active Trading Bots

### 1. SuperTrend Bot V2 (M30)
A pure mathematical trend-following engine.
- Computes K-Means clustered SuperTrend bands on M30 data to dynamically select the optimal ATR factor based on recent volatility-adjusted performance.
- Automatically adjusts position sizing dynamically using strict account risk percentages.

### 2. Ghost Bot (M15)
An advanced mean-reversion grid system.
- Operates on distinct Magic Numbers (201, 202, 204) for isolated logic flows.
- Features localized leg-level Breakeven locking alongside global, aggregated Grid Take-Profit and Stop-Loss management.

*(Note: CAB and CAB Multi-Pair bots have been intentionally excluded from this context scope).*

---

## 🚀 Setup & Execution

### Prerequisites
- Python 3.11+
- MetaTrader 5 Terminal (Windows OS required)
- Active MT5 account (Demo or Live)
- `TA-Lib` C-library and Python wrapper installed.

### Installation
1. Clone the repository to your local Windows environment.
2. Create and activate a virtual environment.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Systems
The system can be launched via the provided batch scripts which handle environment activation and infinite loop crash-recovery.

**To run the V1 Unified Runner:**
```bash
./start_bot.bat
```

**To run the V2 Matrix (Shadow/Live):**
```bash
./run_v2_shadow.bat
```

You can also run the Python entry points directly:
```bash
python unified_runner.py
python v2_unified_runner.py
```

## 🛠️ Performance & Analytics
The suite generates comprehensive metrics, tracking everything from MFE/MAE (Maximum Favorable/Adverse Excursion) to R-Multiples. Check the `reports/` and `logs/` directories for detailed audit trails, CSV session logs, and system crash reports.

---
*Built for precision. Managed for risk.*
"# super" 
