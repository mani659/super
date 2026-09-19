"""
==================================================================
                  CAB MASTER - CONFIGURATION
==================================================================
Central source of truth for terminal paths, risk settings,
and symbol-specific parameters.
==================================================================
"""

import os
import MetaTrader5 as mt5

# --- SYSTEM & TERMINAL PATHS ---
TERMINAL_PATH = r"C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe"
COMMON_PATH   = r"C:\Users\ABRAR\AppData\Roaming\MetaQuotes\Terminal\Common\Files"
HEARTBEAT_FILE = os.path.join(COMMON_PATH, "cab_heartbeat.txt")
LEDGER_FILE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cab_performance_ledger.csv")

# --- GLOBAL ENGINE CONSTANTS ---
MAGIC_NUMBER     = 999555
COOLDOWN_MINUTES = 15
TF_ATR           = mt5.TIMEFRAME_H1
STAGNATION_HOURS = 24

# ── Stop-tail control (fix-stop-tail) ────────────────────────────────────────
# The BE gate only arms after a +peak of BE_GATE_R, so a trade that never moves in
# favour has no protection until the broker stop. Over the Sep-12 audit window 26 of
# 167 ledger rows were BROKER_SL exits realising a full -0.981R and they cost -$2,208,
# more than the segment's entire net loss. Once a trade is this many hours old and has
# still not armed its BE gate, the stop is pulled in to half the initial risk.
# 0 disables the rule.
HALF_RISK_AFTER_HOURS = 6.0

# ── Hard loss caps (fix-loss-cap) ────────────────────────────────────────────
# See trade_manager.enforce_loss_caps(). Fractions of starting equity, measured on
# FLOATING loss, checked once per cycle per symbol and across the whole book.
SYMBOL_LOSS_CAP_PCT    = 0.02
PORTFOLIO_LOSS_CAP_PCT = 0.05

# --- VOLATILITY GROUPS ---
# HIGH: crypto/metals/index/oil — wider swings, wider trailing gates
# LOW:  FX majors/crosses — tighter swings, tighter gates
VOL_GROUPS = {
    "HIGH": ["BTCUSDm", "ETHUSDm", "XAUUSDm", "XAGUSDm", "USTECm", "USOILm"],
    "LOW":  ["EURUSDm", "GBPUSDm", "USDJPYm", "EURGBPm", "AUDNZDm"],
}

def get_vol_group(symbol: str) -> str:
    """Returns 'HIGH' or 'LOW' for the given symbol."""
    for group, syms in VOL_GROUPS.items():
        if symbol in syms:
            return group
    return "HIGH"

# --- PAIR-SPECIFIC CONFIGURATIONS ---
# BE_GATE_R / LOCK_GATE_R split by volatility group
# H1_MIN_HOURS: minimum age before H1 structural breach check fires
#   HIGH = 6.0h (legacy default), LOW = 12.0h (slower FX cycles)
PAIRS = {
    # --- HIGH VOLATILITY ---
    "XAUUSDm": {
        "RISK_PERCENT": 1.0,
        "ATR_MULT_SL": 2.5,
        "MAX_SPREAD": 500,
        "BE_GATE_R": 0.5,
        "LOCK_GATE_R": 1.0,
        "PARTIAL_R": 1.5,
        "H1_MIN_HOURS": 6.0
    },
    "BTCUSDm": {
        "RISK_PERCENT": 0.5,
        "ATR_MULT_SL": 3.0,
        "MAX_SPREAD": 2000,
        "BE_GATE_R": 0.5,
        "LOCK_GATE_R": 1.5,
        "PARTIAL_R": 2.0,
        "H1_MIN_HOURS": 6.0
    },
    "ETHUSDm": {
        "RISK_PERCENT": 0.5,
        "ATR_MULT_SL": 3.0,
        "MAX_SPREAD": 1500,
        "BE_GATE_R": 0.5,
        "LOCK_GATE_R": 1.5,
        "PARTIAL_R": 2.0,
        "H1_MIN_HOURS": 6.0
    },
    "USTECm": {
        "RISK_PERCENT": 1.0,
        "ATR_MULT_SL": 2.5,
        "MAX_SPREAD": 300,
        "BE_GATE_R": 0.5,
        "LOCK_GATE_R": 1.0,
        "PARTIAL_R": 1.5,
        "H1_MIN_HOURS": 6.0
    },
    "USOILm": {
        "RISK_PERCENT": 1.0,
        "ATR_MULT_SL": 2.5,
        "MAX_SPREAD": 100,
        "BE_GATE_R": 0.5,
        "LOCK_GATE_R": 1.0,
        "PARTIAL_R": 1.5,
        "H1_MIN_HOURS": 6.0
    },
    # fix-symbol-risk: XAGUSDm is the worst symbol in every CAB variant that trades
    # it (cab_super CAB -$4.03/trade worst-of-11; V2 CAB -$6.10/trade, -$347.85 total
    # = 127% of CAB's net loss; this bot -0.169R average). Risk halved pending a
    # symbol-level review.
    "XAGUSDm": {
        "RISK_PERCENT": 0.5,
        "ATR_MULT_SL": 3.0,
        "MAX_SPREAD": 200,
        "BE_GATE_R": 0.5,
        "LOCK_GATE_R": 1.2,
        "PARTIAL_R": 2.0,
        "H1_MIN_HOURS": 6.0
    },
    # --- LOW VOLATILITY ---
    "EURUSDm": {
        "RISK_PERCENT": 1.0,
        "ATR_MULT_SL": 2.5,
        "MAX_SPREAD": 50,
        "BE_GATE_R": 0.5,
        "LOCK_GATE_R": 0.8,
        "PARTIAL_R": 1.5,
        "H1_MIN_HOURS": 12.0
    },
    "GBPUSDm": {
        "RISK_PERCENT": 1.0,
        "ATR_MULT_SL": 2.5,
        "MAX_SPREAD": 80,
        "BE_GATE_R": 0.5,
        "LOCK_GATE_R": 0.8,
        "PARTIAL_R": 1.5,
        "H1_MIN_HOURS": 12.0
    },
    "USDJPYm": {
        "RISK_PERCENT": 1.0,
        "ATR_MULT_SL": 2.5,
        "MAX_SPREAD": 80,
        "BE_GATE_R": 0.5,
        "LOCK_GATE_R": 0.8,
        "PARTIAL_R": 1.5,
        "H1_MIN_HOURS": 12.0
    },
    "EURGBPm": {
        "RISK_PERCENT": 1.0,
        "ATR_MULT_SL": 2.5,
        "MAX_SPREAD": 80,
        "BE_GATE_R": 0.5,
        "LOCK_GATE_R": 0.8,
        "PARTIAL_R": 1.5,
        "H1_MIN_HOURS": 12.0
    },
    "AUDNZDm": {
        "RISK_PERCENT": 1.0,
        "ATR_MULT_SL": 2.5,
        "MAX_SPREAD": 100,
        "BE_GATE_R": 0.5,
        "LOCK_GATE_R": 0.8,
        "PARTIAL_R": 1.5,
        "H1_MIN_HOURS": 12.0
    }
}

# Derived list for legacy backward-compatibility
SYMBOLS = list(PAIRS.keys())