"""
==================================================================
                   CAB MASTER - SIGNALS ENGINE
==================================================================
Handles technical condition analysis, including H4 macro inversions
and H1 structural breakout/breach validations.
==================================================================
"""

import MetaTrader5 as mt5
import pandas as pd

def check_h4_inversion(symbol: str) -> str | None:
    """Queries completed candles exclusively to eliminate mid-bar data shifting."""
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 1, 2)
    if rates is None or len(rates) < 2:
        return None
        
    c1_o, c1_c = rates[1]['open'], rates[1]['close'] # Completed Bar -1
    c2_o, c2_c = rates[0]['open'], rates[0]['close'] # Completed Bar -2
    
    if c1_c > c1_o and c2_c < c2_o and c1_c > c2_o:
        return "BULLISH"
    if c1_c < c1_o and c2_c > c2_o and c1_c < c2_o:
        return "BEARISH"
        
    return None

def check_h1_structural_breach(symbol: str, is_buy: bool, lookback: int = 4) -> bool:
    """Detects if current price has breached the extreme structural range of past H1 bars."""
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 1, lookback)
    if rates is None or len(rates) < lookback:
        return False
        
    df = pd.DataFrame(rates)
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return False
        
    return tick.bid < df['low'].min() if is_buy else tick.ask > df['high'].max()