"""
==================================================================
                     CAB MASTER - UTILITIES
==================================================================
Math engine, technical indicators, lot sizing, and broker metadata.
==================================================================
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import config

def get_atr(symbol: str, timeframe, period: int = 14) -> float | None:
    """Calculates True Range and returns rolling ATR value."""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period + 1)
    if rates is None or len(rates) < period + 1:
        return None
    df = pd.DataFrame(rates)
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )
    return df['tr'].rolling(window=period).mean().iloc[-1]

def calculate_lot(symbol: str, sl_dist_price: float, risk_percent: float) -> float:
    """Calculates risk-adjusted position lot size matching broker constraints."""
    account = mt5.account_info()
    sym_info = mt5.symbol_info(symbol)
    if account is None or sym_info is None or sl_dist_price <= 0:
        return 0.01
        
    risk_money = account.equity * (risk_percent / 100.0)
    tick_val = sym_info.trade_tick_value
    tick_size = sym_info.trade_tick_size
    
    if tick_val <= 0:
        return 0.01
        
    raw_lot = risk_money / ((sl_dist_price / tick_size) * tick_val)
    step = sym_info.volume_step
    lot = round(raw_lot / step) * step
    return max(sym_info.volume_min, min(sym_info.volume_max, lot))

def _get_filling_mode(symbol: str) -> int:
    """Detects supported broker order filling execution mode."""
    info = mt5.symbol_info(symbol)
    if info is None:
        return mt5.ORDER_FILLING_RETURN
    fill = info.filling_mode
    if fill & 1:
        return mt5.ORDER_FILLING_FOK
    if fill & 2:
        return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN