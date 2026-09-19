# Bot log extract — trailing 30 days
Generated: 2026-08-31 10:35:26
Cutoff: 2026-08-01 10:34:52

## Files not found
- sniper_conviction_log.csv not found

## Ghost Grid — brain log (grid-level events)
- Lines in window: 2,424 / 2,424 total
- **LEG_TP_SET: 801** (should track ~1:1 with fills)
- **GRID TP fired: 0** | GRID STOP: 0
- GridState reset: 125 | Stale timeout: 0
- GRID_PROTECTOR: 0 | Depth cap refused: 325
- BE_LOCK fires: 117 by magic: {'202': 117}
- GHOST_CACHE_FIRE (204): 0 | layer depths: []
- ARMED UP: 0 | ARMED DN: 0
- Grid TP R stats: {'n': 0}
- Grid Stop R stats: {'n': 0}

## Ghost Hunter fills
- Fills by magic: {'202': 342, '204': 1}
- No-SL fill rate: 0.0% (0 / 340 fills)
- Gate blocks by magic: {}
- Session distribution: {'ASIAN': 459, 'LONDON': 86, 'NY_OVERLAP': 104, 'NY_CLOSE': 135}
- Conviction@fill by magic: {'202': {'n': 342, 'avg': 38.8037, 'min': 10.8292, 'max': 59.7461, 'win_pct': 100.0}, '204': {'n': 1, 'avg': 70.1574, 'min': 70.1574, 'max': 70.1574, 'win_pct': 100.0}}

## Ghost Watcher management actions

## CAB Watcher
- Lines in window: 131,154 / 131,154
- PROTECTOR fired: 1 | R stats: {'n': 1, 'avg': 0.83, 'min': 0.83, 'max': 0.83, 'win_pct': 100.0}
- HARVESTER (partial+full): 0 | R stats: {'n': 0}
- REAPER fired: 0 | blocked: 0 | R stats: {'n': 0}
- ORDER_FAILED: 3 | retry gave up: 1
- Close deferred: 0 | Close failed: 0
- Regime by symbol: {}

## SuperTrend (per symbol)
- **AUDNZDm**: lines=66,878 | entries=23 | R_stats={'n': 12, 'avg': -0.0133, 'min': -0.64, 'max': 0.77, 'win_pct': 41.7} | events={'ENTRY': 23, 'CLOSE_DECAYING': 9, 'R1_BE_LOCK': 4, 'R2_LOCK_1R': 2, 'R3_LOCK_2R': 1, 'CLOSE_DEAD': 3}
- **BTCUSDm**: lines=70,343 | entries=22 | R_stats={'n': 12, 'avg': 0.2533, 'min': -0.39, 'max': 1.28, 'win_pct': 66.7} | events={'ENTRY': 22, 'CLOSE_DECAYING': 10, 'R1_BE_LOCK': 7, 'R2_LOCK_1R': 6, 'R3_LOCK_2R': 1, 'CLOSE_DEAD': 2}
- **ETHUSDm**: lines=69,948 | entries=32 | R_stats={'n': 20, 'avg': 0.0715, 'min': -0.5, 'max': 1.69, 'win_pct': 35.0} | events={'ENTRY': 32, 'CLOSE_DECAYING': 18, 'R1_BE_LOCK': 2, 'CLOSE_DEAD': 2, 'R2_LOCK_1R': 1}
- **EURGBPm**: lines=66,461 | entries=19 | R_stats={'n': 8, 'avg': 0.23, 'min': -0.62, 'max': 1.68, 'win_pct': 62.5} | events={'ENTRY': 19, 'R1_BE_LOCK': 1, 'CLOSE_DECAYING': 8}
- **EURUSDm**: lines=60,417 | entries=10 | R_stats={'n': 5, 'avg': 0.53, 'min': 0.0, 'max': 1.29, 'win_pct': 80.0} | events={'SESSION_BLOCK': 113, 'ENTRY': 10, 'R1_BE_LOCK': 4, 'CLOSE_DECAYING': 5}
- **GBPUSDm**: lines=56,799 | entries=5 | R_stats={'n': 5, 'avg': 0.58, 'min': -0.22, 'max': 2.34, 'win_pct': 60.0} | events={'SESSION_BLOCK': 72, 'ENTRY': 5, 'CLOSE_DECAYING': 4, 'CLOSE_DEAD': 1, 'R1_BE_LOCK': 1}
- **USDJPYm**: lines=62,788 | entries=16 | R_stats={'n': 12, 'avg': 0.2792, 'min': -0.3, 'max': 2.04, 'win_pct': 58.3} | events={'ENTRY': 16, 'CLOSE_DECAYING': 10, 'CLOSE_DEAD': 2, 'R1_BE_LOCK': 2, 'R2_LOCK_1R': 1}
- **USOILm**: lines=66,518 | entries=20 | R_stats={'n': 13, 'avg': 0.1154, 'min': -0.92, 'max': 0.94, 'win_pct': 61.5} | events={'ENTRY': 20, 'R1_BE_LOCK': 2, 'CLOSE_DECAYING': 12, 'R2_LOCK_1R': 1, 'CLOSE_DEAD': 1}
- **USTECm**: lines=56,220 | entries=7 | R_stats={'n': 2, 'avg': -0.095, 'min': -0.19, 'max': 0.0, 'win_pct': 0.0} | events={'ENTRY': 7, 'CLOSE_DECAYING': 2}
- **XAGUSDm**: lines=64,912 | entries=18 | R_stats={'n': 11, 'avg': -0.0109, 'min': -0.73, 'max': 0.94, 'win_pct': 45.5} | events={'ENTRY': 18, 'CLOSE_DECAYING': 10, 'R1_BE_LOCK': 2, 'R2_LOCK_1R': 2, 'R3_LOCK_2R': 2, 'CLOSE_DEAD': 1}
- **XAUUSDm**: lines=63,403 | entries=13 | R_stats={'n': 9, 'avg': 0.5578, 'min': -0.38, 'max': 1.71, 'win_pct': 66.7} | events={'ENTRY': 13, 'R1_BE_LOCK': 5, 'CLOSE_DECAYING': 7, 'CLOSE_DEAD': 2, 'R2_LOCK_1R': 2, 'R3_LOCK_2R': 1}

## Unified session log
- Rows in window: 655,231 / 655,231
- Circuit breaker trips: 0 | times: []
- Magic isolation breaches: 0
- Regime distribution: {'RANGING': 293123, 'UNKNOWN': 104892, 'STABLE': 7899, 'TRENDING_UP': 106099, 'TRENDING_DOWN': 96485, 'TRENDING': 28486}

## Runner health
- HEARTBEAT_OK: 919
- THREAD_STARTED: 20
- SWITCH_LOADED: 603

