# SuperTrend Bot — Operator Guide
**Bot version: v2.2** | File: `supertrend_bot.py` / `run_bot.py`

---

## File layout (what goes where)

```
project/
├── supertrend_bot.py        ← brain (never run directly)
├── run_bot.py               ← entry point (always use this)
├── backtest_engine.py       ← only needed for --backtest
├── performance_monitor.py   ← only needed for --monitor
├── config/
│   └── config.json          ← credentials + per-symbol settings
└── logs/
    ├── bot_YYYYMMDD.log     ← master runner log (created automatically)
    ├── supertrend_EURUSDm.log   ← per-symbol watcher log
    ├── supertrend_GBPUSDm.log
    └── supertrend_runner.log    ← multi-pair runner log (multi-pair mode only)
```

---

## Section 1 — Commands (exactly what to type)

### 1A. The command you already know — single symbol, demo account
```bash
python run_bot.py --symbol EURUSDm --account demo
```
This is the baseline. Everything else is just flags added on top of this.

---

### 1B. Add dry-run (no real orders, everything else works)
```bash
python run_bot.py --symbol EURUSDm --account demo --dry-run
```
**Always start here.** Dry-run runs the full brain — data fetch, K-Means clustering,
regime detection, state machine, watcher decisions — but replaces `order_send()` with
a log line. Fake tickets start at 100001 and increment. You can verify every decision
the bot would make without risking a cent.

---

### 1C. Run live (real orders)
```bash
python run_bot.py --symbol EURUSDm --account demo
python run_bot.py --symbol EURUSDm --account live
```
The only difference between `demo` and `live` is which credential block is read from
`config.json`. The bot logic is identical.

---

### 1D. Change the update interval
```bash
python run_bot.py --symbol EURUSDm --account demo --interval 60
```
Default is 30 seconds. On M30 you have 1800 seconds per bar, so anything between
10–120 seconds is fine. Lower = more watcher cycles per bar = faster SL trailing
response. Higher = less CPU, fewer MT5 API calls.

---

### 1E. Multi-pair (new in v2.1/v2.2)
```bash
python run_bot.py --symbols EURUSDm,GBPUSDm --account demo
python run_bot.py --symbols EURUSDm,GBPUSDm,XAUUSDm --account demo --max-total-positions 5
```
Note: `--symbols` (plural) not `--symbol`. Each symbol gets its own isolated bot
instance with its own log file. The `--max-total-positions` cap applies across ALL
symbols combined.

---

### 1F. Enable equity curve filter (pauses new entries during drawdown)
```bash
python run_bot.py --symbols EURUSDm,GBPUSDm --account demo --equity-filter
```
Disabled by default. When active: if account equity drops below 97% of its rolling
20-cycle average, new entries are paused. Existing positions keep being managed
normally. Auto-recovers when equity improves. Fine-tune the threshold:
```bash
python run_bot.py --symbols EURUSDm,GBPUSDm --account demo \
    --equity-filter --equity-filter-ratio 0.95 --equity-filter-period 30
```

---

### 1G. Enable partial close (locks 50% profit at peak signal strength)
```bash
python run_bot.py --symbol EURUSDm --account demo --partial-close
```
Disabled by default. Fires once per trade when ALL of these are true:
- State machine is CONFIRMED (not DECAYING — that's the watcher's job)
- SI >= 0.85 (signal is extremely healthy)
- Trade is >= 3.0 ATRs in profit

Fine-tune:
```bash
python run_bot.py --symbol EURUSDm --account demo \
    --partial-close --partial-close-si 0.88 --partial-close-atr 2.5 --partial-close-frac 0.40
```

---

### 1H. Show session statistics on shutdown
```bash
python run_bot.py --symbol EURUSDm --account demo --monitor
```
When you press Ctrl+C, prints per-symbol trade count, win rate, P&L, and cache stats
before closing.

---

### 1I. Backtest (last 30 days)
```bash
python run_bot.py --symbol EURUSDm --account demo --backtest
```
Runs `backtest_engine.py` against 30 days of historical data, prints report, exits.
Requires `backtest_engine.py` to be present.

---

### 1J. Verbose debug logging
```bash
python run_bot.py --symbol EURUSDm --account demo --log-level DEBUG
```
Shows every cache hit/miss, every SL modification attempt (including blocked ones),
every tick fetch. Useful for diagnosing MT5 connectivity or spread guard issues.
Switch back to INFO for normal operation — DEBUG generates large log files.

---

### 1K. Full recommended dry-run before going live
```bash
python run_bot.py \
    --symbols EURUSDm,GBPUSDm \
    --account demo \
    --dry-run \
    --equity-filter \
    --partial-close \
    --interval 30 \
    --monitor \
    --log-level INFO
```
Run this for at least 2–4 hours (4–8 M30 bars). This validates the full stack before
any real money touches it.

---

## Section 2 — Log files (where they are and what to look at)

### Log file locations

| File | Created when | What's in it |
|---|---|---|
| `logs/bot_YYYYMMDD.log` | Every run | Runner startup, MT5 connection, account info, shutdown stats |
| `supertrend_EURUSDm.log` | Every run (per symbol) | Every cycle: price, ATR, factor, regime, watcher decisions, SL modifications, entries, closes |
| `supertrend_GBPUSDm.log` | Multi-pair run | Same as above for GBPUSDm |
| `supertrend_runner.log` | Multi-pair run only | Cross-symbol cycle timing, global position count, equity filter status |

All log files are in the **same folder as `run_bot.py`** — not in a subfolder, except
`logs/bot_YYYYMMDD.log` which is inside the `logs/` subfolder.

---

### What to look for in the logs

#### On startup — confirm connection is clean
```
Connected | Account: 262464396 | Balance: 10000.00 USD | Leverage: 1:2000
[EURUSDm] Config: TF=... | Risk=1.0% | MaxPos=1 | SL=2.0×ATR
```
If you don't see "Connected" the bot exited — check config.json credentials.

---

#### Each cycle — confirm data and regime are healthy
```
[EURUSDm] CYCLE | price=1.08542 | ATR=0.00087 | factor=2.50 | Regime=STABLE | Cache hits=5 misses=1
```
- `Cache hits` should be 5 or more after the first bar. If misses keep climbing every
  cycle it means MT5 is returning different bar timestamps each time — check your
  connection stability.
- `Regime=EXHAUSTION` means volatility is spiking — the SI thresholds are automatically
  raised by 0.10 this cycle. Expect fewer entries.

---

#### Watcher cycle — one line per open position
```
[EURUSDm] ── WATCHER CYCLE | Regime=STABLE | ADX 42nd | ST=1.08210 (↑) | Incubation=2bar(s)
[EURUSDm]   #12345678 BUY | State=CONFIRMED | SI=0.712 | ER=0.441 | Bars=3 | P&L=12.40
[EURUSDm] SL updated #12345678 → 1.08210 | CONFIRMED|ST_TRAIL
```
This is the most important section to watch. For each open position you want to see:
- **State=CONFIRMED** with SI > 0.65 and ER > 0.35 — trade is healthy
- **SL updated** — watcher is trailing the stop as intended
- **State=DECAYING** is normal for 1–2 bars — watch `DECAYING 1/1` → if it hits
  `DECAYING 2/1` the position will be closed next line
- **State=DEAD** + **CLOSED** — watcher exited the trade, check the reason tag:
  - `ST_LINE_FLIPPED` — SuperTrend reversed, clean exit
  - `SI_COLLAPSED_0.28x` — signal integrity fell apart, good exit
  - `ER_CHURN_0.12_b4` — price churning for 4 bars, good exit
  - `DECAYING_TIMEOUT` — signal weakened past tolerance, exit

---

#### Entry — what a clean signal looks like
```
[EURUSDm] BUY ENTRY | ticket=12345678 | ref=1.08542 | SL=1.08368 | TP=1.09412 |
           cluster=7/9 | vol=1.43 | Regime=STABLE | Incubation=2bar(s)
```
- `cluster=7/9` means 7 of 9 factor variants agree on the direction. Anything ≥ 6/9
  is a strong consensus signal.
- `vol=1.43` means current volume is 1.43× the 20-bar average — volume gate passed.
- If you never see an ENTRY line the volume gate is probably blocking signals.
  Check `volume_multiplier` in config.json — try lowering from 1.2 to 1.1.

---

#### Partial close — what it looks like when it fires
```
[EURUSDm] PARTIAL CLOSE #12345678 | vol=0.01 (50%) | SI=0.871 | pnl=3.21ATR | remaining=0.01
```
After this line the position ticket stays open with half the volume. The watcher
continues managing the remaining half normally.

---

#### Equity filter — when it activates
```
[RUNNER] EQUITY FILTER ACTIVE | equity=9720.00 | avg=10010.00 | ratio=0.9710
         (threshold=0.97) | New entries PAUSED
```
When you see this, new entries stop but you will still see watcher cycle lines for
existing positions — that's correct behaviour. When equity recovers the line disappears
and entries resume automatically.

---

#### On shutdown (with --monitor)
```
[EURUSDm] Shutdown | Cache: 312 hits / 6 misses | Trades: 4 | P&L: 38.20
── Session Statistics ──
  [EURUSDm] Trades: 4 | Win%: 75.0 | P&L: 38.20 | Cache: 312 hits / 6 misses
```
`312 hits / 6 misses` on a 6-bar session = ~52 hits per bar. That matches the
expected ~60 cycles/bar on a 30-second interval. Confirms the cache is working.

---

## Section 3 — Reading the log in real time

On Windows:
```powershell
Get-Content supertrend_EURUSDm.log -Wait -Tail 30
```

On Linux/Mac:
```bash
tail -f supertrend_EURUSDm.log
tail -f supertrend_runner.log   # multi-pair
```

To watch two symbols at once (Linux/Mac):
```bash
tail -f supertrend_EURUSDm.log supertrend_GBPUSDm.log
```

---

## Section 4 — Red flags to watch for

| Log pattern | What it means | What to do |
|---|---|---|
| `Close BLOCKED` | Spread too wide at exit time | Normal in news events — bot retries next cycle |
| `SL BLOCKED` | New SL too close to current price | Normal — broker STOPS_LEVEL protection, not a bug |
| `No tick` | MT5 lost market data feed | Check internet/MT5 connection |
| `MT5 disconnected — re-initialising` | Terminal dropped | Bot auto-reconnects — watch if it recovers within 1–2 cycles |
| `Cache hits=0` every cycle | MT5 returning inconsistent timestamps | Investigate MT5 connection quality |
| `cluster=2/9` on entry | Weak signal consensus | Reduce `max_factor` or tighten `cluster_choice` to "Best" |
| ENTRY lines but no position in MT5 | `Order FAILED` line above it | Check lot size, margin, broker symbol name (EURUSDm vs EURUSD) |
| Never seeing any ENTRY | Volume gate blocking | Lower `volume_multiplier` from 1.2 → 1.1 in config.json |

---

## Section 5 — Stopping and restarting safely

**To stop:**
```
Ctrl+C
```
The bot closes cleanly — MT5 connection is shut down, `--monitor` stats print if
requested. Open positions are left open on the broker side (the bot does not
force-close on shutdown). When you restart, the watcher reconstructs context
from live position data automatically — you will see `No context — reconstructing`
in the log, which is expected and safe.

**To restart after a config change:**
```bash
Ctrl+C
# edit config/config.json
python run_bot.py --symbol EURUSDm --account demo
```
No special steps needed. The bot always reads config fresh on startup.
