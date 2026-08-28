"""
==================================================================
                   CAB MASTER - EXECUTION ENGINE
==================================================================
Manages order generation, risk calculation integrations, 
and broker execution dispatching.
==================================================================
"""

import MetaTrader5 as mt5
import logging
import config
from utils import get_atr, calculate_lot, _get_filling_mode
from signals import check_h4_inversion
from analytics.intelligencia import get_entry_intelligence

# State tracker for locking active H4 macro bars per symbol
last_h4_bars = {sym: 0 for sym in config.SYMBOLS}

def execute_entries() -> None:
    """Scans all configured symbols for macro signals and executes risk-managed entries."""
    global last_h4_bars
    
    positions = mt5.positions_get()
    open_symbols = [p.symbol for p in positions if p.magic == config.MAGIC_NUMBER] if positions else []

    for sym in config.SYMBOLS:
        if sym in open_symbols:
            continue 

        sym_info = mt5.symbol_info(sym)
        if sym_info is None or not sym_info.visible:
            continue
            
        # Ensure bar-locking matches only newly closed H4 bars
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H4, 0, 1)
        if rates is None or len(rates) == 0:
            continue
            
        current_h4_time = rates[0]['time']
        if current_h4_time == last_h4_bars[sym]:
            continue
        last_h4_bars[sym] = current_h4_time

        signal = check_h4_inversion(sym)
        if not signal:
            continue

        # Data-backed filter: Block entries in RISK_OFF + COMPRESSION_LOW
        intel = get_entry_intelligence(sym)
        atr_state = intel.get("H1_ATR_State", "UNKNOWN")
        risk_sentiment = intel.get("Macro_Risk_Sentiment", "UNKNOWN")
        
        if risk_sentiment == "RISK_OFF" and atr_state == "COMPRESSION_LOW":
            logging.info(f"FILTERED: {sym} [{signal}] trade blocked due to RISK_OFF + COMPRESSION_LOW.")
            continue

        pair_conf = config.PAIRS.get(sym, {"RISK_PERCENT": 1.0, "ATR_MULT_SL": 2.5})
        atr = get_atr(sym, config.TF_ATR, 14) 
        if not atr:
            continue

        sl_dist = atr * pair_conf["ATR_MULT_SL"]
        lot = calculate_lot(sym, sl_dist, pair_conf["RISK_PERCENT"])
        tick = mt5.symbol_info_tick(sym)
        if tick is None:
            continue

        # Implement Configured Spread Filter
        max_spread = pair_conf.get("MAX_SPREAD", 9999)
        if sym_info.spread > max_spread:
            logging.warning(f"SPREAD REJECTION: {sym} spread {sym_info.spread} > Max {max_spread}")
            continue

        if signal == "BULLISH":
            sl = tick.bid - sl_dist
            req = {
                "action": mt5.TRADE_ACTION_DEAL, 
                "symbol": sym, 
                "volume": lot,
                "type": mt5.ORDER_TYPE_BUY, 
                "price": tick.ask, 
                "sl": sl, 
                "tp": 0.0,
                "deviation": 20, 
                "magic": config.MAGIC_NUMBER, 
                "comment": "H4_MACRO_BUY",
                "type_time": mt5.ORDER_TIME_GTC, 
                "type_filling": _get_filling_mode(sym),
            }
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE: 
                logging.info(f"ENTRY: Bought {sym} | Lot: {lot}")

        elif signal == "BEARISH":
            sl = tick.ask + sl_dist
            req = {
                "action": mt5.TRADE_ACTION_DEAL, 
                "symbol": sym, 
                "volume": lot,
                "type": mt5.ORDER_TYPE_SELL, 
                "price": tick.bid, 
                "sl": sl, 
                "tp": 0.0,
                "deviation": 20, 
                "magic": config.MAGIC_NUMBER, 
                "comment": "H4_MACRO_SELL",
                "type_time": mt5.ORDER_TIME_GTC, 
                "type_filling": _get_filling_mode(sym),
            }
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE: 
                logging.info(f"ENTRY: Sold {sym} | Lot: {lot}")