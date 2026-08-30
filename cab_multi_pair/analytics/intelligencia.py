"""
==================================================================
              CAB MASTER - MARKET INTELLIGENCIA
==================================================================
Captures deep environmental features at trade entry:
ADX, Normalized ATR, Sessions, Macro DXY & Risk Sentiment,
plus EntrySpread, absolute ATR, same-direction / correlated counts.
==================================================================
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
import config

def _calculate_adx(df: pd.DataFrame, period: int = 14) -> float:
    """Calculates Average Directional Index (ADX) without TA-Lib."""
    try:
        df = df.copy()
        df['H-L'] = df['high'] - df['low']
        df['H-C'] = np.abs(df['high'] - df['close'].shift(1))
        df['L-C'] = np.abs(df['low'] - df['close'].shift(1))
        df['TR'] = df[['H-L', 'H-C', 'L-C']].max(axis=1)

        df['UpM'] = df['high'] - df['high'].shift(1)
        df['DnM'] = df['low'].shift(1) - df['low']
        
        df['+DM'] = np.where((df['UpM'] > df['DnM']) & (df['UpM'] > 0), df['UpM'], 0)
        df['-DM'] = np.where((df['DnM'] > df['UpM']) & (df['DnM'] > 0), df['DnM'], 0)

        df['TR_s'] = df['TR'].rolling(window=period).sum()
        df['+DM_s'] = df['+DM'].rolling(window=period).sum()
        df['-DM_s'] = df['-DM'].rolling(window=period).sum()

        df['+DI'] = 100 * (df['+DM_s'] / df['TR_s'])
        df['-DI'] = 100 * (df['-DM_s'] / df['TR_s'])

        df['DX'] = 100 * (np.abs(df['+DI'] - df['-DI']) / (df['+DI'] + df['-DI']))
        adx = df['DX'].rolling(window=period).mean().iloc[-1]
        return round(float(adx), 2) if not np.isnan(adx) else 0.0
    except Exception:
        return 0.0

def _get_trading_session(hour: int) -> str:
    """Tags the active liquidity session based on server time (UTC+2/3)."""
    if 0 <= hour < 8: return "ASIAN"
    elif 8 <= hour < 13: return "LONDON_OPEN"
    elif 13 <= hour < 17: return "LON_NY_OVERLAP"
    elif 17 <= hour < 22: return "NEW_YORK"
    else: return "LATE_NY_ASIAN"

# Simple correlation groups for cluster risk (can be expanded later)
CORRELATED_GROUPS = {
    "XAUUSDm": ["XAGUSDm"],
    "XAGUSDm": ["XAUUSDm"],
    "BTCUSDm": ["ETHUSDm"],
    "ETHUSDm": ["BTCUSDm"],
    "EURUSDm": ["GBPUSDm", "EURGBPm"],
    "GBPUSDm": ["EURUSDm", "EURGBPm"],
    "EURGBPm": ["EURUSDm", "GBPUSDm"],
    "USDJPYm": [],
    "AUDNZDm": [],
    "USTECm": [],
    "USOILm": []
}

def get_entry_intelligence(symbol: str, direction: str = None) -> dict:
    """Generates the holistic environmental snapshot for the ledger.
    
    direction: optional "BUY" or "SELL" so we can count same-direction exposure.
    """
    snapshot = {
        "Session": _get_trading_session(datetime.now().hour),
        "Active_Risk_Trades": 0,
        "H1_ATR_State": "NORMAL",
        "H4_Trend_ADX": 0.0,
        "Macro_DXY_Proxy": "NEUTRAL",
        "Macro_Risk_Sentiment": "NEUTRAL",
        "EntrySpreadPoints": None,
        "EntryATR": None,
        "EntryATR_Pct": None,
        "ActiveSameDirection": 0,
        "ActiveCorrelated": 0
    }
    
    try:
        # 0. Spread at snapshot time
        sym_info = mt5.symbol_info(symbol)
        if sym_info is not None:
            snapshot["EntrySpreadPoints"] = int(sym_info.spread)

        # 1. Active Portfolio Exposure + same-direction + correlated
        positions = mt5.positions_get()
        if positions:
            cab_positions = [p for p in positions if p.magic == config.MAGIC_NUMBER]
            snapshot["Active_Risk_Trades"] = len(cab_positions)

            if direction:
                same_dir = 0
                for p in cab_positions:
                    p_dir = "BUY" if p.type == 0 else "SELL"
                    if p_dir == direction:
                        same_dir += 1
                snapshot["ActiveSameDirection"] = max(0, same_dir)

            # Correlated open count
            corr_symbols = CORRELATED_GROUPS.get(symbol, [])
            corr_count = sum(1 for p in cab_positions if p.symbol in corr_symbols)
            snapshot["ActiveCorrelated"] = corr_count

        # 2. Volatility State (Normalized ATR) + absolute values
        rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 30)
        if rates_h1 is not None and len(rates_h1) >= 30:
            df_h1 = pd.DataFrame(rates_h1)
            df_h1['tr'] = np.maximum(df_h1['high'] - df_h1['low'], 
                          np.maximum(abs(df_h1['high'] - df_h1['close'].shift(1)), 
                                     abs(df_h1['low'] - df_h1['close'].shift(1))))
            current_atr = float(df_h1['tr'].iloc[-1])
            mean_atr = float(df_h1['tr'].mean())
            
            snapshot["EntryATR"] = round(current_atr, 5)
            
            tick = mt5.symbol_info_tick(symbol)
            if tick is not None and tick.bid > 0:
                snapshot["EntryATR_Pct"] = round((current_atr / tick.bid) * 100.0, 4)
            
            if current_atr > (mean_atr * 1.5):
                snapshot["H1_ATR_State"] = "EXPANSION_HIGH"
            elif current_atr < (mean_atr * 0.7):
                snapshot["H1_ATR_State"] = "COMPRESSION_LOW"

        # 3. Trend Strength (H4 ADX)
        rates_h4 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 40)
        if rates_h4 is not None and len(rates_h4) >= 40:
            df_h4 = pd.DataFrame(rates_h4)
            snapshot["H4_Trend_ADX"] = _calculate_adx(df_h4, 14)

        # 4. Macro Environment (DXY Proxy via EURUSD & Risk Proxy via USTEC)
        eu_rates = mt5.copy_rates_from_pos("EURUSDm", mt5.TIMEFRAME_H4, 1, 3)
        if eu_rates is not None and len(eu_rates) >= 3:
            if eu_rates[-1]['close'] < eu_rates[0]['open']:
                snapshot["Macro_DXY_Proxy"] = "USD_BULLISH"
            else:
                snapshot["Macro_DXY_Proxy"] = "USD_BEARISH"

        nq_rates = mt5.copy_rates_from_pos("USTECm", mt5.TIMEFRAME_H4, 1, 3)
        if nq_rates is not None and len(nq_rates) >= 3:
            if nq_rates[-1]['close'] > nq_rates[0]['open']:
                snapshot["Macro_Risk_Sentiment"] = "RISK_ON"
            else:
                snapshot["Macro_Risk_Sentiment"] = "RISK_OFF"

    except Exception:
        pass  # Silently fail open to ensure execution is never blocked

    return snapshot