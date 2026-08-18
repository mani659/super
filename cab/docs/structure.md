CAB_SUPER_BOT/
│
├── config.py                 # Magic numbers, SYMBOLS, risk parameters
├── logger_config.py          # Handles console/file logging
├── metrics.py                # JSON state persistence, harvest, excursions
├── shared_utils.py           # NEW: Central hub for all math & broker executions
│
├── strat_inversion.py        # Magic: 9995551 | ADX > 60 | Mean Reversion
├── strat_continuation.py     # Magic: 9995552 | ADX 30-60 | Trend Pullbacks
├── strat_grid.py             # Magic: 9995553 | ADX < 30 | Range Baskets
│
└── main.py                   # The Orchestrator (imports all strats and runs them)