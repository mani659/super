import MetaTrader5 as mt5
import pandas as pd
import logging
import math
import config
from metrics import register_trade_context, log_structural_flip
from shared_utils import (
    _get_filling_mode,
    get_atr,
    get_adx_directional,
    calculate_dynamic_lot,
    is_valid_session,
    check_h4_inversion,
    check_exhaustion_filter,
    check_smc_confluence,
    _close_position
)

# Magic Number hardcoded for the Continuation Vector (ADX 30 to 60)
MAGIC_CONTINUATION = 9995552
RISK_PERCENT = 0.01  # 1% Account Risk per trade

last_h4_bar = {sym: None for sym in config.SYMBOLS}
logger = logging.getLogger("STRAT_CONTINUATION")

def manage_continuation_positions():
    """
    Trade management for Trend Continuation positions (Magic: 9995552).
    - Reaper (-0.5R H1 momentum bailout)
    - Protector (Lock BE + buffer at 1.0R)
    - NO HARVESTER (Do not cap at 2.0R — let trend run)
    - Elastic Trailing (1.0R trail between 1R-2R, 0.5R trail > 2R)
    - H1 Structural Invalidation for losing trades
    """
    positions = mt5.positions_get()
    if not positions:
        return
    
    for pos in positions:
        if pos.magic != MAGIC_CONTINUATION:
            continue
        sym_info = mt5.symbol_info(pos.symbol)
        if not sym_info:
            continue
        
        orders = mt5.history_orders_get(position=pos.ticket)
        if not orders:
            continue
        entry_order = next((o for o in orders if o.type in (mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL)), None)
        if not entry_order or entry_order.sl == 0:
            continue
        
        initial_risk_price = abs(pos.price_open - entry_order.sl)
        if initial_risk_price <= 0:
            continue
        
        is_buy = pos.type == mt5.ORDER_TYPE_BUY
        profit_price_dist = (pos.price_current - pos.price_open) if is_buy else (pos.price_open - pos.price_current)
        current_r = profit_price_dist / initial_risk_price if initial_risk_price > 0 else 0.0
        
        five_dollars_target = 5.0
        tick_val = sym_info.trade_tick_value
        tick_sz = sym_info.trade_tick_size
        if tick_val > 0 and pos.volume > 0 and tick_sz > 0:
            price_for_five = (five_dollars_target / (tick_val * pos.volume)) * tick_sz
        else:
            price_for_five = sym_info.point * 50
            
        m15_atr_raw = get_atr(pos.symbol, mt5.TIMEFRAME_M15, 14)
        m15_atr = (price_for_five * 2) if m15_atr_raw <= 0 or math.isnan(m15_atr_raw) else m15_atr_raw
        
        buffer_price = max(price_for_five, m15_atr * 0.1)
        be_plus_buffer = pos.price_open + buffer_price if is_buy else pos.price_open - buffer_price
        
        # 1. REAPER (-0.5R Bailout on H1 Momentum)
        if current_r <= -0.5:
            rates_h1 = mt5.copy_rates_from_pos(pos.symbol, mt5.TIMEFRAME_H1, 0, 2)
            if rates_h1 is not None and len(rates_h1) > 1:
                cur_h1 = rates_h1[-2]
                h1_body = abs(cur_h1['close'] - cur_h1['open'])
                if is_buy and cur_h1['close'] < cur_h1['open'] and h1_body > m15_atr:
                    if _close_position(pos, "REAPER_FLIP", MAGIC_CONTINUATION):
                        log_structural_flip(pos.ticket, reason="REAPER_FLIP")
                        logger.warning(f"[MANAGEMENT] #{pos.ticket} [{pos.symbol}] REAPER killed trade early (-0.5R).")
                    continue
                elif not is_buy and cur_h1['close'] > cur_h1['open'] and h1_body > m15_atr:
                    if _close_position(pos, "REAPER_FLIP", MAGIC_CONTINUATION):
                        log_structural_flip(pos.ticket, reason="REAPER_FLIP")
                        logger.warning(f"[MANAGEMENT] #{pos.ticket} [{pos.symbol}] REAPER killed trade early (-0.5R).")
                    continue
        
        # 2. PROTECTOR (Break Even + Buffer Gate triggered at 1.0R)
        if current_r >= 1.0:
            sl_needs_be = (pos.sl < be_plus_buffer) if is_buy else (pos.sl == 0 or pos.sl > be_plus_buffer)
            if sl_needs_be:
                req = {
                    "action": mt5.TRADE_ACTION_SLTP, 
                    "position": pos.ticket, 
                    "symbol": pos.symbol,
                    "sl": round(be_plus_buffer, sym_info.digits), 
                    "tp": 0.0
                }
                res = mt5.order_send(req)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info(f"[MANAGEMENT] #{pos.ticket} [{pos.symbol}] hits 1R. PROTECTOR locked BE + buffer.")
                continue

        # 3. ELASTIC TRAILING (1.0R gap between 1.0R and 2.0R | 0.5R gap > 2.0R) - UNLIMITED RUNNING
        is_at_be = (pos.sl >= be_plus_buffer) if is_buy else (pos.sl > 0 and pos.sl <= be_plus_buffer)
        if is_at_be:
            min_step = sym_info.point * 10
            trail_gap = (initial_risk_price * 0.5) if current_r >= 2.0 else (initial_risk_price * 1.0)
            trail_level = pos.price_current - trail_gap if is_buy else pos.price_current + trail_gap
            needs_trail = (trail_level > pos.sl + min_step) if is_buy else (trail_level < pos.sl - min_step)
            
            if needs_trail:
                req = {
                    "action": mt5.TRADE_ACTION_SLTP, 
                    "position": pos.ticket, 
                    "symbol": pos.symbol,
                    "sl": round(trail_level, sym_info.digits), 
                    "tp": 0.0
                }
                res = mt5.order_send(req)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info(f"[MANAGEMENT] #{pos.ticket} [{pos.symbol}] ELASTIC TRAIL updated to {trail_level:.5f}")
        
        # 4. Active H1 Structural Invalidation (Losing Trades ONLY)
        if pos.profit < 0:
            rates = mt5.copy_rates_from_pos(pos.symbol, mt5.TIMEFRAME_H1, 1, 4)
            if rates is not None and len(rates) >= 4:
                df = pd.DataFrame(rates)
                tick = mt5.symbol_info_tick(pos.symbol)
                if tick is None:
                    continue
                
                breached = False
                if is_buy and tick.bid < df['low'].min():
                    breached = True
                elif not is_buy and tick.ask > df['high'].max():
                    breached = True
                    
                if breached:
                    if _close_position(pos, "H1_STRUCT_INVALID", MAGIC_CONTINUATION):
                        log_structural_flip(pos.ticket, reason="H1_STRUCT_INVALID")
                        logger.warning(f"[MANAGEMENT] #{pos.ticket} [{pos.symbol}] Killed early due to H1 Structural Invalidation.")

def execute_continuation_entries():
    """
    Execution routine for Trend Continuation Vector (ADX 30 to 60).
    Requires valid trading session (12:00 to 22:00 broker hours).
    Aligns H4 Inversion signal with directional +DI / -DI momentum.
    """
    global last_h4_bar
    
    positions = mt5.positions_get()
    open_positions = {}
    if positions:
        for p in positions:
            if p.magic == MAGIC_CONTINUATION:
                open_positions.setdefault(p.symbol, []).append(p)

    orders = mt5.orders_get()
    pending_orders = {}
    if orders:
        for o in orders:
            if o.magic == MAGIC_CONTINUATION:
                pending_orders.setdefault(o.symbol, []).append(o)

    for sym in config.SYMBOLS:
        sym_info = mt5.symbol_info(sym)
        if sym_info is None or not sym_info.visible: 
            continue
        
        rates_h4 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H4, 0, 1)
        if rates_h4 is None or len(rates_h4) == 0: 
            continue
        
        current_h4_time = rates_h4[0]['time']
        if current_h4_time == last_h4_bar[sym]: 
            continue

        # 1. Session Filter (12:00 to 22:00 server hours required)
        if not is_valid_session(sym):
            continue

        signal = check_h4_inversion(sym)
        skip_symbol = False
        
        # Close opposing positions on structural flip
        pos_list = open_positions.get(sym, [])
        for pos in pos_list:
            is_buy = (pos.type == mt5.ORDER_TYPE_BUY)
            if signal and ((is_buy and signal == "BEARISH") or (not is_buy and signal == "BULLISH")):
                if _close_position(pos, "STRUCTURAL_FLIP", MAGIC_CONTINUATION):
                    log_structural_flip(pos.ticket, reason="STRUCTURAL_FLIP") 
                else:
                    skip_symbol = True
            else:
                skip_symbol = True
                
        if skip_symbol:
            continue

        # 2. Base Signal Gate
        if not signal: 
            continue

        # 3. ADX Impulsive Trend Gate (30 <= ADX <= 60) & Directional Alignment
        adx, plus_di, minus_di = get_adx_directional(sym, mt5.TIMEFRAME_H4, 14)
        if not (30.0 <= adx <= 60.0):
            continue

        # Check directional alignment (+DI vs -DI) & Trap detection
        is_trap = False
        if signal == "BULLISH" and plus_di > minus_di:
            order_type, comment = mt5.ORDER_TYPE_BUY, "CONT_TREND_BUY"
        elif signal == "BEARISH" and minus_di > plus_di:
            order_type, comment = mt5.ORDER_TYPE_SELL, "CONT_TREND_SELL"
        elif signal == "BEARISH" and plus_di > minus_di:
            # Trap! Bearish Inversion but Bullish Trend
            order_type, comment = mt5.ORDER_TYPE_BUY_STOP, "CONT_TRAP_BUY"
            is_trap = True
        elif signal == "BULLISH" and minus_di > plus_di:
            # Trap! Bullish Inversion but Bearish Trend
            order_type, comment = mt5.ORDER_TYPE_SELL_STOP, "CONT_TRAP_SELL"
            is_trap = True
        else:
            continue
            
        # If it's a trap, check if we already have a pending order
        if is_trap and sym in pending_orders:
            continue

        pip_size = sym_info.point * (10 if sym_info.digits in (3, 5) else 1)
        current_spread_pips = sym_info.spread * sym_info.point / pip_size
        max_allowed_pips = 1500.0 if "BTC" in sym or "ETH" in sym else 3.0
        
        if current_spread_pips > max_allowed_pips: 
            continue

        atr_h4 = get_atr(sym, mt5.TIMEFRAME_H4, config.ATR_PERIOD)
        if not atr_h4 or atr_h4 <= 0: 
            continue

        exhaustion_state = check_exhaustion_filter(sym, is_buy=(signal == "BULLISH"))
        smc_confluence = check_smc_confluence(sym, rates_h4)
        tick_volume = rates_h4[0]['tick_volume']

        sl_dist = atr_h4 * config.ATR_MULT_SL
        tick = mt5.symbol_info_tick(sym)
        if not tick:
            continue
        
        # 4. Dynamic 1% Lot Sizing
        calc_volume = calculate_dynamic_lot(sym, sl_dist, RISK_PERCENT)

        if order_type == mt5.ORDER_TYPE_BUY:
            entry_price = tick.ask
            sl = entry_price - sl_dist
            req = {
                "action": mt5.TRADE_ACTION_DEAL, 
                "symbol": sym, 
                "volume": float(calc_volume),
                "type": order_type, 
                "price": entry_price, 
                "sl": round(sl, sym_info.digits),
                "tp": 0.0,
                "deviation": 20, 
                "magic": MAGIC_CONTINUATION,
                "comment": comment, 
                "type_time": mt5.ORDER_TIME_GTC, 
                "type_filling": _get_filling_mode(sym),
            }
        elif order_type == mt5.ORDER_TYPE_SELL:
            entry_price = tick.bid
            sl = entry_price + sl_dist
            req = {
                "action": mt5.TRADE_ACTION_DEAL, 
                "symbol": sym, 
                "volume": float(calc_volume),
                "type": order_type, 
                "price": entry_price, 
                "sl": round(sl, sym_info.digits),
                "tp": 0.0,
                "deviation": 20, 
                "magic": MAGIC_CONTINUATION,
                "comment": comment, 
                "type_time": mt5.ORDER_TIME_GTC, 
                "type_filling": _get_filling_mode(sym),
            }
        else:
            # Pending Orders (Breakout Trap)
            rates_trap = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H4, 1, 1)
            if rates_trap is None or len(rates_trap) == 0:
                continue
                
            trap_high = rates_trap[0]['high']
            trap_low = rates_trap[0]['low']
            
            if order_type == mt5.ORDER_TYPE_BUY_STOP:
                entry_price = trap_high + (sym_info.spread * sym_info.point)
                sl = entry_price - sl_dist
            else: # SELL_STOP
                entry_price = trap_low - (sym_info.spread * sym_info.point)
                sl = entry_price + sl_dist
                
            req = {
                "action": mt5.TRADE_ACTION_PENDING, 
                "symbol": sym, 
                "volume": float(calc_volume),
                "type": order_type, 
                "price": round(entry_price, sym_info.digits), 
                "sl": round(sl, sym_info.digits),
                "tp": 0.0,
                "deviation": 20, 
                "magic": MAGIC_CONTINUATION,
                "comment": comment, 
                "type_time": mt5.ORDER_TIME_SPECIFIED, 
                "expiration": int(current_h4_time) + 86400, # 24h expiration
                "type_filling": mt5.ORDER_FILLING_RETURN, # Typical for pending orders
            }
        
        # Mark as attempted to prevent spamming broker on failure
        last_h4_bar[sym] = current_h4_time
        res = mt5.order_send(req)
        
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            actual_price = res.price
            requested_price = req['price']
            slippage_pips = round((abs(actual_price - requested_price) / sym_info.point) / (10 if sym_info.digits in (3, 5) else 1), 2)
            
            try:
                point_value = sym_info.trade_tick_value / (sym_info.trade_tick_size / sym_info.point)
                sl_points = sl_dist / sym_info.point
                risk_amount = sl_points * point_value * float(calc_volume)
            except Exception:
                risk_amount = 0.0

            # Session label from hour
            try:
                from datetime import datetime
                h = datetime.utcfromtimestamp(tick.time).hour
            except Exception:
                h = 0
            if 0 <= h < 7:
                sess = "ASIAN"
            elif 7 <= h < 12:
                sess = "LONDON"
            elif 12 <= h < 17:
                sess = "LONDON_NY"
            elif 17 <= h < 22:
                sess = "NY"
            else:
                sess = "LATE_NY"

            register_trade_context(
                ticket=res.order,
                risk_amount=risk_amount,
                spread=round(current_spread_pips, 2),
                slippage=slippage_pips,
                exhaustion_state=exhaustion_state,
                volume=tick_volume,
                smc_confluence=smc_confluence,
                adx=adx,
                plus_di=plus_di,
                minus_di=minus_di,
                ema50=0.0,
                session=sess,
                subtype=comment
            )
            
            logger.info(f"[CONTINUATION ENTRY] Executed {sym} | ADX: {adx:.1f} (+DI={plus_di:.1f}, -DI={minus_di:.1f}) | Lot: {calc_volume} | Trigger: {comment}")
        else:
            logger.error(f"[{sym}] Continuation Entry Failed. Retcode: {res.retcode if res else 'None'}")
