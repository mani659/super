"""
Unified Trade Ledger — single CSV that ALL bots write to.

Every ENTRY, EXIT, and PARTIAL_CLOSE across SuperTrend, CAB, and Ghost Grid
is recorded here. This is the foundation for all statistical analysis.

Usage:
    from data.trade_ledger import write_trade_event
    write_trade_event(
        bot="ST", event="ENTRY", ticket=123456,
        symbol="XAUUSDm", direction="BUY", price=4050.0,
        sl=4040.0, tp=4080.0, volume=0.03,
        regime="TRENDING", session="LONDON", conviction=72.5,
        atr=8.5, magic=100,
    )
"""

import csv
import os
import threading
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
_LEDGER_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)))
_LEDGER_PATH = os.path.join(_LEDGER_DIR, "trade_ledger.csv")
_LOCK        = threading.Lock()

_COLUMNS = [
    "timestamp",
    "bot",              # ST / CAB / GHOST
    "event",            # ENTRY / EXIT / PARTIAL_CLOSE
    "ticket",
    "symbol",
    "direction",        # BUY / SELL
    "price",
    "sl",
    "tp",
    "volume",
    "regime",           # TRENDING / RANGING / EXHAUSTION / STABLE
    "session",          # ASIAN / LONDON / NY_OVERLAP / NY_CLOSE / OTHER
    "conviction",       # 0-100 (entry only, blank on exit if unavailable)
    "atr",              # ATR at event time
    "r_multiple",       # signed R at exit (blank on entry)
    "hold_bars",        # bars held (exit only)
    "hold_minutes",     # minutes held (exit only)
    "exit_reason",      # DECAYING_TIMEOUT / OSI / REAPER / HARVESTER / SL_HIT / TP_HIT / etc.
    "pnl_usd",          # dollar P&L (exit only)
    "spread_at_event",  # spread in price units at the moment of event
    "magic",            # magic number
]

_EQUITY_PATH = os.path.join(_LEDGER_DIR, "equity_curve.csv")
_EQUITY_COLUMNS = ["timestamp", "equity", "balance", "profit", "open_positions"]

def _ensure_headers():
    """Write the CSV headers if the files don't exist yet."""
    os.makedirs(_LEDGER_DIR, exist_ok=True)
    if not os.path.exists(_LEDGER_PATH):
        with open(_LEDGER_PATH, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(_COLUMNS)
    if not os.path.exists(_EQUITY_PATH):
        with open(_EQUITY_PATH, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(_EQUITY_COLUMNS)

def write_equity_snapshot(equity: float, balance: float, profit: float, open_positions: int):
    """Thread-safe append to the equity curve CSV."""
    try:
        with _LOCK:
            _ensure_headers()
            row = [
                datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                f"{equity:.2f}",
                f"{balance:.2f}",
                f"{profit:.2f}",
                str(open_positions)
            ]
            with open(_EQUITY_PATH, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(row)
    except Exception:
        pass


def write_trade_event(
    bot:        str,
    event:      str,
    ticket:     int,
    symbol:     str,
    direction:  str,
    price:      float,
    sl:         float = 0.0,
    tp:         float = 0.0,
    volume:     float = 0.0,
    regime:     str   = "",
    session:    str   = "",
    conviction: float = None,
    atr:        float = None,
    r_multiple: float = None,
    hold_bars:  int   = None,
    hold_minutes: float = None,
    exit_reason: str  = "",
    pnl_usd:   float = None,
    spread_at_event: float = None,
    magic:     int   = None,
):
    """
    Append one row to the unified trade ledger.

    Thread-safe via a module-level lock.
    Silently catches exceptions so it never crashes a trading bot.
    """
    try:
        with _LOCK:
            _ensure_headers()
            row = [
                datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                bot,
                event,
                ticket,
                symbol,
                direction,
                f"{price:.5f}" if price else "",
                f"{sl:.5f}"    if sl    else "",
                f"{tp:.5f}"    if tp    else "",
                f"{volume:.4f}" if volume else "",
                regime,
                session,
                f"{conviction:.1f}" if conviction is not None else "",
                f"{atr:.5f}"        if atr is not None else "",
                f"{r_multiple:.3f}" if r_multiple is not None else "",
                str(hold_bars)      if hold_bars is not None else "",
                f"{hold_minutes:.1f}" if hold_minutes is not None else "",
                exit_reason,
                f"{pnl_usd:.2f}"    if pnl_usd is not None else "",
                f"{spread_at_event:.5f}" if spread_at_event is not None else "",
                str(magic)          if magic is not None else "",
            ]
            with open(_LEDGER_PATH, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(row)
    except Exception:
        # Never crash a trading bot for a logging failure.
        pass
