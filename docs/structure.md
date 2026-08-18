# Project Structure

```text
Super/
├── .pytest_cache
│   ├── .gitignore
│   ├── CACHEDIR.TAG
│   ├── README.md
│   └── v
│       └── cache
│           ├── lastfailed
│           ├── nodeids
│           └── stepwise
├── LICENSE
├── MANIFEST.in
├── UnifiedFailover.mq5
├── archive
│   ├── Assessment Report.docx
│   ├── UNIFIED_BOT_CONTEXT_old.md
│   ├── core_old
│   │   ├── supertrend_bot.py
│   │   ├── supertrend_bot_before_improvements_from_gemini.py
│   │   └── supertrend_bot_old.py
│   ├── master plan.docx
│   ├── run_bot.py
│   ├── start_bot.bat
│   └── supertrend_bot_v2_3.py
├── backtest_engine.py
├── cab_multi_pair
│   ├── 25-07-2026
│   │   ├── CAB_Global_Sentinel.mq5
│   │   ├── cab_master.py
│   │   ├── cab_performance_ledger - Copy.csv
│   │   ├── cab_performance_ledger.csv
│   │   ├── config.py
│   │   ├── old
│   │   │   ├── CAB_Global_Sentinel.mq5
│   │   │   ├── cab_master.py
│   │   │   ├── config.py
│   │   │   └── start_bot.bat
│   │   └── start_bot.bat
│   ├── Structure.txt
│   ├── analytics
│   │   ├── __init__.py
│   │   └── intelligencia.py
│   ├── cab_engine_dashboard.mq5
│   ├── cab_performance_ledger.csv
│   ├── config.py
│   ├── connection.py
│   ├── docs
│   │   ├── architecture.md
│   │   ├── context.md
│   │   ├── feature_history.md
│   │   └── roadmap.md
│   ├── execution.py
│   ├── ledger.py
│   ├── main.py
│   ├── signals.py
│   ├── start_bot.bat
│   ├── test_health.py
│   ├── trade_manager.py
│   └── utils.py
├── cab_production_v16.3.log
├── cab_super
│   ├── CAB_Unified.mq5
│   ├── __init__.py
│   ├── cab_entry.py
│   └── cab_watcher.py
├── config
│   ├── config.example.json
│   └── config.json
├── core
│   ├── __init__.py
│   ├── knowledge_register.py
│   ├── news_filter.py
│   ├── performance_monitor.py
│   ├── risk_manager.py
│   ├── shared_intelligence.py
│   ├── supertrend_bot.py
│   └── verify_structure.py
├── docs
│   ├── CONTRIBUTING.md
│   ├── FAQ.md
│   ├── QUICKSTART.md
│   ├── README.md
│   ├── UNIFIED_BOT_CONTEXT.md
│   ├── WEEK2_MONITORING_GUIDE.md
│   ├── knowledge_register.md
│   ├── knowledge_register_gemini.md
│   ├── operator_guide.md
│   ├── requirements.txt
│   ├── structure.md
│   └── todo_tracker.md
├── examples.py
├── extract_bot_logs.py
├── generate_structure.py
├── ghost_super
│   ├── __init__.py
│   ├── ghost_cache.py
│   ├── ghost_sniper.py
│   ├── run_sniper.bat
│   └── sniper_watcher.py
├── log_extract
│   ├── cab_summary.csv
│   ├── ghost_audit_summary.csv
│   ├── ghost_conviction_summary.csv
│   ├── runner_health.md
│   ├── summary.md
│   ├── supertrend_summary.csv
│   └── unified_session_summary.csv
├── logs
│   ├── adaptive_thresholds_live.csv
│   ├── cab_watcher.log
│   ├── old logs
│   │   ├── adaptive_thresholds_live.csv
│   │   ├── bot_20260430.log
│   │   ├── cab_production_v16.3.log
│   │   ├── sniper_brain.log.1
│   │   ├── sniper_brain.log.2
│   │   ├── sniper_brain.log.3
│   │   ├── sniper_brain.log.4
│   │   ├── sniper_brain.log.5
│   │   ├── sniper_v51_live_audit.csv
│   │   ├── supertrend_EURUSDm.log
│   │   ├── supertrend_GBPUSDm.log
│   │   ├── supertrend_XAGUSDm.log
│   │   ├── supertrend_XAUUSDm.log
│   │   ├── supertrend_runner.log
│   │   ├── unified_runner - Copy.txt
│   │   ├── unified_runner.log
│   │   ├── unified_runner.log.1
│   │   ├── unified_runner.log.2
│   │   ├── unified_runner.log.3
│   │   ├── unified_runner.log.4
│   │   ├── unified_runner.log.5
│   │   └── unified_session_log.csv
│   ├── sniper_hunter.log
│   ├── supertrend_EURUSDm.log
│   ├── supertrend_GBPUSDm.log
│   ├── supertrend_XAGUSDm.log
│   ├── supertrend_XAUUSDm.log
│   ├── supertrend_runner.log
│   └── unified_runner.log
├── mt5_gateway.py
├── reports
│   ├── audit_report.py
│   ├── daily_performance_report.txt
│   ├── framework_analyzer.py
│   ├── log_aggregator.py
│   └── unified_performance_report.txt
├── setup.py
├── sniper_brain.log
├── sniper_conviction_log.csv
├── test_cab_entry.py
├── test_cab_gateway_port.py
├── test_ghost_gateway_port.py
├── test_supertrend_gateway_port.py
├── unified_runner.py
├── unified_session_log.csv
└── verify_structure.py
```
