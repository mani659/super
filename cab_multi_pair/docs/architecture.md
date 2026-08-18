# CAB MASTER: Modular Architecture & Development Journey

## 🚀 The Journey
The project began as a monolithic script (`cab_master.py`) handling all connections, logic, execution, and tracking inside a single file. As complexity grew, the monolith was entirely refactored into a highly decoupled, fail-safe 9-module architecture. 

**Milestone Reached:** The refactor passed 100% of structural health diagnostics, confirming safe math fallbacks, circular import elimination, and proper data pipeline integration.

## 🏛️ The System Blueprint

### 1. The Core Orchestrator
* **`main.py`**: The central nervous system. It initializes the terminal, writes the heartbeat, and houses the immortal runtime loop controlling execution and trade management.
* **`run.bat`**: The watchdog process that activates the Python virtual environment and auto-restarts the bot if an unhandled crash occurs.

### 2. The configuration & Utilities
* **`config.py`**: The sole source of truth. Contains file paths, terminal definitions, and dynamic, pair-specific parameters (e.g., Risk %, ATR Multipliers, Max Spread).
* **`utils.py`**: The math engine. Handles zero-division safety, ATR calculations, lot sizing, and broker fill-mode detection.
* **`connection.py`**: Manages the MT5 terminal handshake and writes the constant `cab_heartbeat.txt` timestamp to pacify the MQL5 failover sentinel.

### 3. The Quantitative Pipeline
* **`signals.py`**: The logic gate. Exclusively queries *completed* candles for H4 Inversions and monitors H1 extreme structural breaches.
* **`analytics/intelligencia.py`**: The environmental observer. Captures Volatility Regimes, Macro Trends (ADX), Liquidity Sessions, and Risk Sentiment at the exact second a trade opens.
* **`ledger.py`**: The state memory bank. Tracks MFE/MAE, orchestrates missing broker deals, and writes the highly detailed CSV performance database combining execution metrics with Intelligencia snapshots.

### 4. The Execution & Management Arm
* **`execution.py`**: Generates orders and dispatches risk-managed entries to the broker.
* **`trade_manager.py`**: The active watchdog. Trailing stops, protective logic closures (stagnation decay, opposite macro signals), and Intelligencia snapshot triggers.