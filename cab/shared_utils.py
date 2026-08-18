import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import logging
import math
from datetime import datetime
import config

logger = logging.getLogger("CAB_SHARED")

def _get_filling_mode(symbol: str) -> int:
    """Standard MT5 FOK/IOC/RETURN filling mode detection."""
    sym_info = mt5.symbol_info(symbol)
    if sym_info is None: 
        return mt5.ORDER_FILLING_IOC
    
    if sym_info.filling_mode & 1: 
        return mt5.ORDER_FILLING_FOK
    elif sym_info.filling_mode & 2: 
        return mt5.ORDER_FILLING_IOC
    else:
        return mt5.ORDER_FILLING_RETURN

def get_atr(symbol: str, timeframe: int, period: int = 14) -> float:
    """
    ATR calculation returning a float.
    Guards against None and NaN values.
    """
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period + 1)
    if rates is None or len(rates) < period + 1: 
        return 0.0
    
    df = pd.DataFrame(rates)
    df['prev_close'] = df['close'].shift(1)
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            (df['high'] - df['prev_close']).abs(),
            (df['low'] - df['prev_close']).abs()
        )
    )
    atr_val = df['tr'].rolling(window=period).mean().iloc[-1]
    if atr_val is None or (isinstance(atr_val, float) and math.isnan(atr_val)):
        return 0.0
    return float(atr_val)

def get_adx_directional(symbol: str, timeframe: int, period: int = 14) -> tuple:
    """
    Calculate ADX, +DI, and -DI over the requested timeframe.
    Returns tuple: (adx_val, plus_di, minus_di).
    Guards against missing data with clean (0.0, 0.0, 0.0) fallback.
    """
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period * 3)
    if rates is None or len(rates) < period * 2:
        return (0.0, 0.0, 0.0)
    
    df = pd.DataFrame(rates)
    df['up_move'] = df['high'] - df['high'].shift(1)
    df['down_move'] = df['low'].shift(1) - df['low']
    
    df['+dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0.0)
    df['-dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0.0)
    
    df['prev_close'] = df['close'].shift(1)
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            (df['high'] - df['prev_close']).abs(),
            (df['low'] - df['prev_close']).abs()
        )
    )
    
    tr_smooth = df['tr'].rolling(window=period).sum()
    plus_dm_smooth = df['+dm'].rolling(window=period).sum()
    minus_dm_smooth = df['-dm'].rolling(window=period).sum()
    
    # Avoid zero division
    safe_tr = tr_smooth.replace(0, np.nan)
    plus_di_series = 100 * (plus_dm_smooth / safe_tr)
    minus_di_series = 100 * (minus_dm_smooth / safe_tr)
    
    di_sum = plus_di_series + minus_di_series
    safe_di_sum = di_sum.replace(0, np.nan)
    dx_series = 100 * ((plus_di_series - minus_di_series).abs() / safe_di_sum)
    adx_series = dx_series.rolling(window=period).mean()
    
    adx_val = adx_series.iloc[-1]
    plus_di = plus_di_series.iloc[-1]
    minus_di = minus_di_series.iloc[-1]
    
    adx_clean = 0.0 if (pd.isna(adx_val) or math.isnan(adx_val)) else float(adx_val)
    plus_di_clean = 0.0 if (pd.isna(plus_di) or math.isnan(plus_di)) else float(plus_di)
    minus_di_clean = 0.0 if (pd.isna(minus_di) or math.isnan(minus_di)) else float(minus_di)
    
    return (adx_clean, plus_di_clean, minus_di_clean)

def calculate_dynamic_lot(symbol: str, sl_dist: float, risk_pct: float = 0.01) -> float:
    """
    Calculates lot size using (risk_amount / (sl_points * tick_value)).
    Clamps to volume_min, volume_max, and rounds to volume_step.
    """
    account_info = mt5.account_info()
    sym_info = mt5.symbol_info(symbol)
    if not account_info or not sym_info: 
        return 0.01

    risk_amount = account_info.balance * risk_pct
    try:
        sl_points = sl_dist / sym_info.point
        tick_value = sym_info.trade_tick_value
        tick_size = sym_info.trade_tick_size
        
        if tick_value <= 0 or sl_points <= 0 or tick_size <= 0: 
            return sym_info.volume_min
            
        point_value = tick_value / (tick_size / sym_info.point)
        
        raw_lot = risk_amount / (sl_points * point_value)
        step = sym_info.volume_step if sym_info.volume_step > 0 else 0.01
        lot_size = round(raw_lot / step) * step
        lot_size = max(sym_info.volume_min, min(lot_size, sym_info.volume_max))
        
        # Format decimals based on volume step
        if step == 0.01:
            return round(lot_size, 2)
        elif step == 0.1:
            return round(lot_size, 1)
        else:
            return round(lot_size, 2)
    except Exception as e:
        logger.error(f"Lot sizing error on {symbol}: {e}")
        return sym_info.volume_min if sym_info else 0.01

def is_valid_session(symbol: str = None) -> bool:
    """
    Returns True only if current broker server hour is between 12 and 22
    (London/NY overlap & NY session). Returns False otherwise.
    """
    hour = None
    if symbol:
        tick = mt5.symbol_info_tick(symbol)
        if tick:
            hour = datetime.utcfromtimestamp(tick.time).hour
    
    if hour is None:
        if config.SYMBOLS:
            tick = mt5.symbol_info_tick(config.SYMBOLS[0])
            if tick:
                hour = datetime.utcfromtimestamp(tick.time).hour
    
    if hour is None:
        hour = datetime.utcnow().hour
        
    return 12 <= hour < 22

def check_exhaustion_filter(symbol: str, is_buy: bool = True) -> bool:
    """
    Evaluates closed M15 candle wick rejection (>50% of bar size).
    """
    rates_m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 1, 1)
    if rates_m15 is None or len(rates_m15) == 0: 
        return False
    
    for r in rates_m15:
        bar_size = r['high'] - r['low']
        if bar_size <= 0: 
            continue
        if is_buy:
            upper_wick = r['high'] - max(r['open'], r['close'])
            if (upper_wick / bar_size) > 0.5: 
                return True
        else:
            lower_wick = min(r['open'], r['close']) - r['low']
            if (lower_wick / bar_size) > 0.5: 
                return True
    return False

def check_smc_confluence(symbol: str, rates = None) -> str:
    """SMC Confluence check returning FVG_ALIGNED."""
    return "FVG_ALIGNED"

def check_h4_inversion(symbol: str) -> str:
    """
    Detects 2-bar H4 Inversion setup.
    Returns 'BULLISH', 'BEARISH', or None.
    """
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 3)
    if rates is None or len(rates) < 3: 
        return None
    c1, c2 = rates[-2], rates[-3]
    if (c1['close'] > c1['open']) and (c2['close'] < c2['open']) and (c1['close'] > c2['high']): 
        return "BULLISH"
    if (c1['close'] < c1['open']) and (c2['close'] > c2['open']) and (c1['close'] < c2['low']): 
        return "BEARISH"
    return None

def _close_position(pos, reason: str, magic_number: int) -> bool:
    """
    Force-closes MT5 positions with error handling and logging.
    """
    tick = mt5.symbol_info_tick(pos.symbol)
    if tick is None: 
        return False
    
    exit_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
    order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    
    req = {
        "action": mt5.TRADE_ACTION_DEAL, 
        "position": pos.ticket, 
        "symbol": pos.symbol,
        "volume": pos.volume, 
        "type": order_type,
        "price": exit_price, 
        "deviation": 20, 
        "magic": magic_number,
        "comment": str(reason)[:31], 
        "type_time": mt5.ORDER_TIME_GTC, 
        "type_filling": _get_filling_mode(pos.symbol)
    }
    res = mt5.order_send(req)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        logging.getLogger().info(f"[{reason}] KILLED #{pos.ticket} [{pos.symbol}] at {exit_price}")
        return True
    else:
        ret = res.retcode if res else "NoResponse"
        logging.getLogger().error(f"Failed to close #{pos.ticket} [{pos.symbol}]: Retcode {ret}")
    return False
