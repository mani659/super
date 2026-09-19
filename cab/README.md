# CAB Standalone Bot

Standalone tri-vector trading engine for XAUUSDm and 9 other symbols on MT5 account 262924445.

**Current Phase:** Post-Gate — Continuation entries disabled (Sep 13 2026). Inversion (9995551) and Grid (9995553) live. Continuation management still runs for residual open legs. See `docs/post_gate_plan.md` for the formal plan and `docs/session_handoff.md` for operational state.

**Architecture:** 3-tier ADX regime engine — Inversion (ADX>60), Continuation (ADX 30–60, entries disabled), Grid (ADX<30). Active management: Protector, Elastic Trailing, Reaper, Harvester. Loss caps: 2% per symbol, 5% portfolio.

**Quick start:** `python main.py` — reads config.py, connects to MT5, starts all threads.
