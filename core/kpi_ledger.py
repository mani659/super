"""
kpi_ledger.py — Append-only per-heartbeat KPI snapshot
=======================================================
Written by the main thread heartbeat loop in unified_runner.py.
One row per heartbeat (60s cadence). Never read by any mechanical
system component — analytical layer only.
"""
import csv
import os
import logging
from datetime import datetime
from pathlib import Path
from threading import Lock

_ledger_lock = Lock()
_LEDGER_PATH = Path("logs/kpi_ledger.csv")
_HEADER = [
    "timestamp_utc",
    "account_equity",
    "account_balance",
    "open_pnl",
    "daily_drawdown_pct",
    "entries_allowed",
    "open_positions_total",
    "open_ghost_201",
    "open_ghost_202",
    "open_ghost_204",
    "open_supertrend",
    "open_cab",
    "regime_xauusd",
    "conviction_xauusd",
]

def _ensure_header():
    _LEDGER_PATH.parent.mkdir(exist_ok=True)
    if not _LEDGER_PATH.is_file():
        with open(_LEDGER_PATH, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(_HEADER)

def write_kpi_snapshot(
    equity: float,
    balance: float,
    open_pnl: float,
    daily_drawdown_pct: float,
    entries_allowed: bool,
    positions,         # list/tuple of position objects from gateway.positions_get()
    regime_xauusd: str = "",
    conviction_xauusd: float = 0.0,
):
    """
    Append one KPI row. Called from unified_runner.py main heartbeat loop.
    positions: raw list from gateway.positions_get() — may be None or empty.
    """
    try:
        _ensure_header()
        pos_list = list(positions) if positions else []
        counts = {201: 0, 202: 0, 204: 0, "st": 0, "cab": 0}
        ST_MAGICS = {101234, 201567, 301890, 401213}
        for p in pos_list:
            if p.magic in (201, 202, 204):
                counts[p.magic] = counts.get(p.magic, 0) + 1
            elif p.magic in ST_MAGICS:
                counts["st"] += 1
            elif p.magic == 999555:
                counts["cab"] += 1
        row = [
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            round(equity, 2),
            round(balance, 2),
            round(open_pnl, 2),
            round(daily_drawdown_pct, 4),
            1 if entries_allowed else 0,
            len(pos_list),
            counts[201],
            counts[202],
            counts[204],
            counts["st"],
            counts["cab"],
            regime_xauusd,
            round(conviction_xauusd, 2),
        ]
        with _ledger_lock:
            with open(_LEDGER_PATH, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(row)
    except Exception as e:
        logging.getLogger("KPILedger").debug(f"write_kpi_snapshot failed: {e}")
