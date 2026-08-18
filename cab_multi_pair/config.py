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

# --- PAIR-SPECIFIC CONFIGURATIONS ---
PAIRS = {
    "XAUUSDm": {
        "RISK_PERCENT": 1.0,
        "ATR_MULT_SL": 2.5,
        "MAX_SPREAD": 500,
        "BE_GATE_R": 0.8,
        "LOCK_GATE_R": 1.0,
        "PARTIAL_R": 1.5
    },
    "BTCUSDm": {
        "RISK_PERCENT": 0.5,
        "ATR_MULT_SL": 3.0,
        "MAX_SPREAD": 2000,
        "BE_GATE_R": 1.0,
        "LOCK_GATE_R": 1.5,
        "PARTIAL_R": 2.0
    },
    "ETHUSDm": {
        "RISK_PERCENT": 0.5,
        "ATR_MULT_SL": 3.0,
        "MAX_SPREAD": 1500,
        "BE_GATE_R": 1.0,
        "LOCK_GATE_R": 1.5,
        "PARTIAL_R": 2.0
    },
    "USTECm": {
        "RISK_PERCENT": 1.0,
        "ATR_MULT_SL": 2.5,
        "MAX_SPREAD": 300,
        "BE_GATE_R": 0.8,
        "LOCK_GATE_R": 1.0,
        "PARTIAL_R": 1.5
    },
    "USOILm": {
        "RISK_PERCENT": 1.0,
        "ATR_MULT_SL": 2.5,
        "MAX_SPREAD": 100,
        "BE_GATE_R": 0.8,
        "LOCK_GATE_R": 1.0,
        "PARTIAL_R": 1.5
    },
    "EURUSDm": {
        "RISK_PERCENT": 1.0,
        "ATR_MULT_SL": 2.5,
        "MAX_SPREAD": 50,
        "BE_GATE_R": 0.8,
        "LOCK_GATE_R": 1.0,
        "PARTIAL_R": 1.5
    },
    "GBPUSDm": {
        "RISK_PERCENT": 1.0,
        "ATR_MULT_SL": 2.5,
        "MAX_SPREAD": 80,
        "BE_GATE_R": 0.8,
        "LOCK_GATE_R": 1.0,
        "PARTIAL_R": 1.5
    },
    "USDJPYm": {
        "RISK_PERCENT": 1.0,
        "ATR_MULT_SL": 2.5,
        "MAX_SPREAD": 80,
        "BE_GATE_R": 0.8,
        "LOCK_GATE_R": 1.0,
        "PARTIAL_R": 1.5
    },
    "EURGBPm": {
        "RISK_PERCENT": 1.0,
        "ATR_MULT_SL": 2.5,
        "MAX_SPREAD": 80,
        "BE_GATE_R": 0.8,
        "LOCK_GATE_R": 1.0,
        "PARTIAL_R": 1.5
    },
    "AUDNZDm": {
        "RISK_PERCENT": 1.0,
        "ATR_MULT_SL": 2.5,
        "MAX_SPREAD": 100,
        "BE_GATE_R": 0.8,
        "LOCK_GATE_R": 1.0,
        "PARTIAL_R": 1.5
    },
    "XAGUSDm": {
        "RISK_PERCENT": 1.0,
        "ATR_MULT_SL": 3.0,
        "MAX_SPREAD": 200,
        "BE_GATE_R": 1.0,
        "LOCK_GATE_R": 1.2,
        "PARTIAL_R": 2.0
    }
}

# Derived list for legacy backward-compatibility
SYMBOLS = list(PAIRS.keys())