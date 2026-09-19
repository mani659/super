# Week 9 Extraction Summary (Sep 15�19 2026)

**Generated:** 2026-09-19 00:39:53


## Ghost 202

- **Audit CSV fills (magic 202):** 0 (CSV stopped updating Sep 15 — no W9 data)
- **Armed events:** 0 (CSV)
- **Gate blocks:** 0 (CSV)
- **Magic 204 fills:** 0 (CSV)
- **GHOST_FIRE_QUALITY lines:** 0 (sniper_hunter.log last updated Sep 15)
- **HTML Ghost fills (SNIPER_R):** 64 | WR: 32/64=50.0% | P&L: $-16.67
  - All 64 fills were XAUUSDm SELL, all closed on Sep 15 only

### Session Breakdown (from HTML)

| Session | n | Win Rate | Sum P&L | Avg P&L |
|---------|---|----------|---------|---------|
| ASIAN | 43 | 46.5% | $-6.38 | $-0.15 |
| LONDON | 7 | 57.1% | $+3.67 | $+0.52 |
| NY_OVERLAP | 14 | 57.1% | $-13.96 | $-1.00 |
| NY_CLOSE | 0 | — | $0.00 | — |

> Note: Audit CSV stopped updating Sep 15. Session breakdown uses HTML fills only (all 64 on Sep 15).

## SuperTrend

| Symbol | n | WR | Sum P&L | Avg P&L |
|--------|---|-----|---------|---------|
| AUDNZDm | 7 | 71.4% | $+1.95 | $+0.28 |
| BTCUSDm | 5 | 60.0% | $+17.61 | $+3.52 |
| ETHUSDm | 8 | 12.5% | $-1.80 | $-0.22 |
| EURGBPm | 8 | 62.5% | $+0.70 | $+0.09 |
| EURUSDm | 1 | 0.0% | $-0.19 | $-0.19 |
| GBPUSDm | 1 | 0.0% | $-0.55 | $-0.55 |
| USDJPYm | 13 | 38.5% | $+0.94 | $+0.07 |
| USOILm | 6 | 33.3% | $-2.81 | $-0.47 |
| USTECm | 7 | 28.6% | $-8.33 | $-1.19 |
| XAGUSDm | 6 | 66.7% | $+40.60 | $+6.77 |
| XAUUSDm | 10 | 60.0% | $+47.24 | $+4.72 |

- **ENTRY_QUALITY (XAUUSDm):** 10 lines

## CAB

- **Total closed:** 65
- **Win rate:** 20.0%
- **Sum P&L:** $-65.11

| Direction | n | WR | Avg P&L |
|-----------|---|-----|---------|
| BUY | 31 | 25.8% | $-1.03 |
| SELL | 34 | 14.7% | $-0.98 |
| GAP | | 11.1% | |

- **IMMEDIATE_EXIT fires:** 0
- **REAPER|H4_AGAINST fires:** 0
- **M5_CONTEXT:** 0
- **CAB_ENTRY_QUALITY:** 0

## Logging Verification

| Log Type | Count | Status |
|----------|-------|--------|
| ENTRY_QUALITY (XAUUSDm) | 10 | PASS |
| CAB_ENTRY_QUALITY | 0 | FAIL |
| GHOST_FIRE_QUALITY | 0 | FAIL |
| M5_CONTEXT | 0 | FAIL |

## Account

- **Equity:** $6563.54
- **Balance:** $6526.12
- **Daily DD%:** -0.9041%
- **KPI timestamp:** 2026-09-18 21:39:48

## Health

- **Heartbeat entries:** 47
- **Last heartbeat:** 2026-09-19 00:39:48,385 [UnifiedRunner] WARNING | Heartbeat OK | 5 threads alive | Equity=6563.54 P&L=37.42
- **CIRCUIT BREAKER fires:** 0
- **DEAD THREADS fires:** 0
