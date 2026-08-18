# MT5 Hybrid Brain - Modular Architecture

## 📂 Core Python Modules
* **`main.py`**: The central entry point and execution loop. It initializes the MT5 terminal, manages the heartbeat, evaluates the Intraday Session Gates, and orchestrates the strategic sub-modules.
* **`strat_inversion.py` (Magic: 9995551):** Execution module for **Mean Reversion**. Activates only when ADX > 60. Limits exposure to 1-position-per-pair.
* **`strat_continuation.py` (Magic: 9995552):** Execution module for **Trend Continuation**. Activates when ADX is 30–60. Requires lower-timeframe SMC FVG mitigation to enter pullbacks.
* **`strat_grid.py` (Magic: 9995553):** Execution module for **Range Extraction**. Activates when ADX < 30. Manages a multi-position basket, scaling in at ATR intervals and liquidating the aggregate basket at +1.0R. Includes a hard kill-switch if ADX exceeds 30.
* **`config.py`**: The centralized configuration hub. Stores terminal paths, dynamic risk percentages (e.g., 1%), grid step parameters, and the routing logic for the tri-vector Magic Numbers.
* **`metrics.py`**: Handles event-driven market intelligence telemetry. Uses `trade_context.json` for crash-proof state memory. Scans dynamic broker history to log exact R-multiples, MFE/MAE excursions, and active lifecycle management triggers (Reaper/Harvester).
* **`logger_config.py`**: Configures the logging infrastructure, actively wiping implicit/duplicate handlers to prevent console spam, and routing output to `cab_watcher_production.log`.

## ⚙️ Execution & Management
* **`start_bot.bat`**: The immortal watchdog script. Activates the virtual environment, executes `main.py`, pipes standard errors to `crash.log`, and immediately restarts the engine if a fatal connection or API error occurs.