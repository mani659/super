# Week 1 Demo Run — Daily Monitoring Guide (Historical) & Next Week Plan

**Period:** ~Jul 21–28 2026 (Reflecting Week 1 / Week 2 fixes)
**Goal:** Confirm the July fix batch landed correctly. Collect first clean
Gate 2 and Gate 3 data. Do NOT apply any new changes this week.

---

## Day 1 — First-hour checks (do these before stepping away)

### 1. All threads alive
Open `logs/unified_runner.log` and confirm the first heartbeat line looks like:
```
Heartbeat OK | 5 threads alive | Equity=10000.xx
```
If any thread is missing, check for `FATAL` or `Exception` lines above it.

### 2. LEG_TP_SET firing
Open `sniper_brain.log` and search for `LEG_TP SET`.
- **Pass:** You see it within the first few fills (should appear many times per hour)
- **Fail:** Still zero after 2 hours of trading activity → the sniper_watcher.py
  fix did not deploy correctly. Stop and re-check the file on the VPS.

### 3. CAB lot sizes
Open MT5 terminal, go to open positions. Any CAB entry (comment `cab_managed`)
on EURUSDm, GBPUSDm, or XAGUSDm should show volume = 0.01.
- **Pass:** 0.01 lot
- **Fail:** 0.14–0.32 lot → cab_entry.py with the lot cap fix is not deployed

### 4. Switch test
While the bot is running, open `config/config.json`, change `"203": true` to
`"203": false`, save. Wait 30–60 seconds. Check `sniper_hunter.log` — leg 203
should stop firing. Change it back to `true` and save. This confirms the live
switch works without a restart.

### 5. CAB multi-symbol working
Watch `logs/cab_watcher.log` (or `cab_production_v16.3.log` if the former is
empty). Within the first CAB management cycle after a non-XAUUSDm position
opens, you should see:
```
-- REGIME[EURUSDm]: STABLE | ...
-- REGIME[GBPUSDm]: STABLE | ...
```
- **Pass:** Multiple symbols in regime log
- **Fail:** Only `REGIME[XAUUSDm]` ever appears → cab_watcher.py fix not deployed

---

## Day 2–3 — Ghost Cache check

Search `sniper_brain.log` or `logs/sniper_hunter.log` for:
```
GHOST_CACHE_FIRE magic=204
```
- **Pass:** At least 1 fire by day 3
- **Action if zero after 5 trading days:** Open `ghost_super/ghost_cache.py`,
  change `N_LAYERS_DEFAULT = 3` to `N_LAYERS_DEFAULT = 2`, redeploy.
  Do NOT change anything else at the same time.

Also check `sniper_brain.log` for this line appearing — it confirms arming:
```
ARMED UP | price=...
ARMED DN | price=...
```
If you see hundreds of ARMED lines but zero GHOST_CACHE_FIRE, n=3 is too deep
for current conditions → lower to 2.

---

## Daily log check (5 minutes, every day)

Open `logs/unified_runner.log` and scan for any of these — they all need
immediate attention if they appear:

| Pattern | What it means | Action |
|---|---|---|
| `DEAD THREADS` | One of the 5 bot threads crashed | Check for Exception above it; restart if it does not self-recover |
| `CIRCUIT BREAKER TRIPPED` | Account hit 10% daily drawdown | No new entries until next session start — check open positions |
| `MAGIC_ISOLATION_BREACH_DETAIL` | Unknown magic number trading | Open `unified_session_log.csv`, filter on this action, read the `magic` and `symbol` columns — this is how you identify the mystery trader |
| `reconnect FAILED` | MT5 terminal connection lost | Check if terminal is still running on the VPS |
| `Heartbeat write failed` | UnifiedFailover.mq5 can't read heartbeat | Check file path in config.json matches the EA's `HeartbeatFile` setting |

---

## End-of-week data collection (run before reviewing results)

From the `Super/` folder on the VPS:
```bash
python extract_bot_logs.py --days 7
```
This produces `log_extract.zip`. Upload it alongside the MT5 trade history
export (Account History → export as HTML from the terminal).

The updated `extract_bot_logs.py` (v2) now correctly parses `sniper_brain.log`
and captures GRID TP/STOP/LEG_TP_SET/GHOST_CACHE_FIRE events that were
missing from the v1 script used for Week 1 analysis.

---

## End-of-week review — what numbers matter

### Ghost Grid fix confirmation
Run `extract_bot_logs.py` and look at `log_extract/brain_log_summary.csv`:

| Metric | Week 1 baseline | Week 2 target (fix confirmed) |
|---|---|---|
| `LEG_TP_SET` | 8 total in 5 weeks | Should roughly match fill count (~100s/day) |
| `GRID_TP` | 0 | Any nonzero value |
| `GRID_STOP` | 0 | Any nonzero value |
| `GRIDSTATE_RESET` | 0 | Nonzero (grids are now closing and resetting) |
| `GHOST_CACHE_FIRE` | 0 | At least a handful |
| `DEPTH_CAP` | 47,672 | Should fall dramatically as grids now reset properly |

### SL width impact (the main parameter change)
From the MT5 trade history export, split 201/202 trades into two cohorts:
- Reached BE-lock milestone (check `sniper_brain.log` for `BE_LOCK` events)
- Never reached BE-lock (closed at initial SL loss)

Week 1 baseline: 1,020 trades (41.5%) never reached BE-lock, -$2,560 total.
If the 0.35×ATR SL is working, this cohort should be meaningfully smaller
as a percentage of total 201/202 trades.

### CAB fix confirmation
From the MT5 trade history or `log_extract/cab_summary.csv`:
- PROTECTOR or HARVESTER lines for EURUSDm/GBPUSDm/XAGUSDm → fix confirmed
- CAB overall win rate nonzero → fix confirmed
- All FX CAB entries at 0.01 lot → lot cap confirmed

### SuperTrend activity
Week 1: 2 trades in 12 days. If Week 2 is still under 10 trades in 7 days,
investigate the entry filter stack before Gate 3 can be evaluated.

---

## What NOT to do this week

- Do not change `N_LAYERS_DEFAULT` unless 204 is still at zero fires after 5 days
- Do not apply session filtering (all sessions stay open)
- Do not disable leg 203 yet (let clean data decide)
- Do not change any other parameters — only one parameter changed (SL width)
  and isolating its effect requires a clean week
- Do not run `run_bot.py` alongside `unified_runner.py` on the same terminal

---

## Next session agenda & Next Week Plan (Week 3)

Bring these files:
1. `log_extract.zip` (from `python extract_bot_logs.py --days 7`)
2. MT5 trade history HTML export (full clean Week 2/3 period)
3. `sniper_brain.log` + rotations (.1, .2) if the zip is too large

**Our Next Week Plan (Data Collection & Evaluation):**
1. **Fix confirmation** — did LEG_TP_SET, GRID TP/STOP, and 204 Ghost Cache fires all become nonzero and correctly log?
2. **SL width impact** — did the never-reached-BE-lock cohort shrink significantly now that SL is 0.35xATR?
3. **CAB multi-symbol** — did PROTECTOR/HARVESTER fire effectively for non-Gold pairs (EURUSDm, GBPUSDm, XAGUSDm)?
4. **Gate 2 Data** — Compare 204 vs 202 avg_R (if 30+ fills accumulated) to decide on Phase 4 integration.
5. **Gate 3 Data** — Individual bot conviction criteria (SuperTrend fires, Ghost Grid stop rate, CAB false-cut rate).
6. **Decisions on Parked Items** — Once the data is clean, we will decide on the BE-lock step ratchet (Tier 2), session filtering (NY_CLOSE vs ASIAN), and the ultimate fate of leg 203 (which is currently removed).
