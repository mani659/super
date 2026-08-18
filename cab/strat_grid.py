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
    check_h4_inversion,
    check_exhaustion_filter,
    check_smc_confluence,
    _close_position
)

# Magic Number for Range Extraction Grid (ADX < 30)
MAGIC_GRID = 9995553
MAX_GRID_LAYERS = 5         # Maximum number of layers per symbol basket

last_h4_bar = {sym: None for sym in config.SYMBOLS}
logger = logging.getLogger("STRAT_GRID")

def _calculate_grid_addon_lot(sym_info, previous_lot: float) -> float:
    """Calculates next layer lot size (1.5x previous lot, clamped and stepped)."""
    raw_lot = previous_lot * 1.5
    step = sym_info.volume_step if sym_info.volume_step > 0 else 0.01
    lot_size = round(raw_lot / step) * step
    lot_size = max(sym_info.volume_min, min(lot_size, sym_info.volume_max))
    if step == 0.01:
        return round(lot_size, 2)
    elif step == 0.1:
        return round(lot_size, 1)
    else:
        return round(lot_size, 2)

def manage_grid_positions():
    """
    Basket & Lifecycle management for Range Extraction Grid (Magic: 9995553).
    - Dynamic VWAP + ATR targeting based on H4 ADX Regime.
    """
    positions = mt5.positions_get()
    if not positions:
        return
    
    grid_positions = [p for p in positions if p.magic == MAGIC_GRID]
    if not grid_positions:
        return

    baskets_by_sym = {}
    for pos in grid_positions:
        baskets_by_sym.setdefault(pos.symbol, []).append(pos)
    
    for sym, basket in baskets_by_sym.items():
        if not basket:
            continue
            
        sym_info = mt5.symbol_info(sym)
        if not sym_info:
            continue
        
        is_buy = basket[0].type == mt5.ORDER_TYPE_BUY
        if any((p.type == mt5.ORDER_TYPE_BUY) != is_buy for p in basket):
            logger.error(f"[GRID ERROR] Mixed position directions detected in basket for {sym}.")
            continue
            
        total_volume = sum(p.volume for p in basket)
        vwap = sum(p.volume * p.price_open for p in basket) / total_volume
        
        adx, _, _ = get_adx_directional(sym, mt5.TIMEFRAME_H4, 14)
        h4_atr = get_atr(sym, mt5.TIMEFRAME_H4, config.ATR_PERIOD)
        if not h4_atr or h4_atr <= 0:
            continue
            
        # State 1: The Kill Switch (ADX > 35)
        if adx > 35:
            logger.warning(f"[GRID KILL-SWITCH] ADX breached 35 ({adx:.1f}). Liquidating grid basket for {sym} ({len(basket)} legs).")
            for pos in basket:
                if _close_position(pos, "GRID_KILL_ADX35", MAGIC_GRID):
                    log_structural_flip(pos.ticket, reason="GRID_KILL_ADX35")
            continue
            
        # State 2 & 3 Target calculation
        if 30 <= adx <= 35:
            # The Escape Hatch
            target_price = vwap + (sym_info.point * 10) if is_buy else vwap - (sym_info.point * 10)
        else:
            # Normal Extraction (ADX < 30)
            target_price = vwap + (0.5 * h4_atr) if is_buy else vwap - (0.5 * h4_atr)
            
        # Execution Trigger
        tick = mt5.symbol_info_tick(sym)
        if not tick:
            continue
            
        current_price = tick.bid if is_buy else tick.ask
        hit_target = (is_buy and current_price >= target_price) or (not is_buy and current_price <= target_price)
        
        if hit_target:
            logger.info(f"[GRID HARVEST] Basket closed for {sym} at VWAP Target. ADX: {adx:.1f}")
            for pos in basket:
                if _close_position(pos, "GRID_VWAP_TARGET", MAGIC_GRID):
                    log_structural_flip(pos.ticket, reason="GRID_VWAP_TARGET")

def execute_grid_entries():
    """
    Entry & Scaling logic for Range Extraction Grid (ADX < 30).
    - If NO open positions: Triggers 0.01 lot base anchor on H4 inversion.
    - If open positions exist: Scales in 1.5x volume if price moves >= 1.0 * H4 ATR adversely.
    """
    global last_h4_bar
    
    positions = mt5.positions_get()
    all_grid_positions = [p for p in positions if p.magic == MAGIC_GRID] if positions else []
    baskets_by_sym = {}
    for pos in all_grid_positions:
        baskets_by_sym.setdefault(pos.symbol, []).append(pos)

    for sym in config.SYMBOLS:
        sym_info = mt5.symbol_info(sym)
        if sym_info is None or not sym_info.visible:
            continue
        
        rates_h4 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H4, 0, 1)
        if rates_h4 is None or len(rates_h4) == 0:
            continue
        
        current_h4_time = rates_h4[0]['time']
        # 1. Regime Gate: ADX < 30 ONLY (Ranging / Chop Market)
        adx, _, _ = get_adx_directional(sym, mt5.TIMEFRAME_H4, 14)
        if adx >= 30.0:
            continue

        pip_size = sym_info.point * (10 if sym_info.digits in (3, 5) else 1)
        current_spread_pips = sym_info.spread * sym_info.point / pip_size
        max_allowed_pips = 1500.0 if "BTC" in sym or "ETH" in sym else 3.0
        if current_spread_pips > max_allowed_pips:
            continue

        h4_atr = get_atr(sym, mt5.TIMEFRAME_H4, config.ATR_PERIOD)
        if not h4_atr or h4_atr <= 0:
            continue

        tick = mt5.symbol_info_tick(sym)
        if not tick:
            continue

        basket = baskets_by_sym.get(sym, [])

        # Case 1: Initial Entry (No open grid positions for this symbol)
        if len(basket) == 0:
            # Only apply H4 bar deduplication to initial entries
            if current_h4_time == last_h4_bar[sym]:
                continue
            signal = check_h4_inversion(sym)
            if not signal:
                continue

            base_lot = max(0.01, sym_info.volume_min)
            if signal == "BULLISH":
                entry_price = tick.ask
                order_type, comment = mt5.ORDER_TYPE_BUY, "GRID_BASE"
            elif signal == "BEARISH":
                entry_price = tick.bid
                order_type, comment = mt5.ORDER_TYPE_SELL, "GRID_BASE"
            else:
                continue

            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": sym,
                "volume": float(base_lot),
                "type": order_type,
                "price": entry_price,
                "sl": 0.0,
                "tp": 0.0,
                "deviation": 20,
                "magic": MAGIC_GRID,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": _get_filling_mode(sym),
            }

            # Enforce cooldown on failure
            last_h4_bar[sym] = current_h4_time
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                register_trade_context(
                    ticket=res.order,
                    risk_amount=0.0,
                    spread=round(current_spread_pips, 2),
                    slippage=0.0,
                    exhaustion_state=False,
                    volume=rates_h4[0]['tick_volume'],
                    smc_confluence="GRID_INITIAL"
                )
                logger.info(f"[GRID BASE ENTRY] Executed {sym} | Lot: {base_lot} | Type: {comment} | ADX: {adx:.1f}")
            else:
                logger.error(f"[{sym}] Grid Base Entry Failed. Retcode: {res.retcode if res else 'None'}")

        # Case 2: Scaling / Add-On Layer (Existing basket open)
        else:
            is_buy = (basket[0].type == mt5.ORDER_TYPE_BUY)
            
            # Find the worst-priced position in the active basket
            if is_buy:
                worst_pos = min(basket, key=lambda p: p.price_open)
                worst_price = worst_pos.price_open
                current_price = tick.ask
                adverse_move = worst_price - current_price  # Price dropped below worst BUY price
            else:
                worst_pos = max(basket, key=lambda p: p.price_open)
                worst_price = worst_pos.price_open
                current_price = tick.bid
                adverse_move = current_price - worst_price  # Price rose above worst SELL price

            # Check if adverse move is >= 1.0 * H4 ATR and basket not at max depth
            if adverse_move >= (1.0 * h4_atr) and len(basket) < MAX_GRID_LAYERS:
                previous_lot = worst_pos.volume
                next_lot = _calculate_grid_addon_lot(sym_info, previous_lot)
                order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
                comment = "GRID_ADDON"

                req = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": sym,
                    "volume": float(next_lot),
                    "type": order_type,
                    "price": current_price,
                    "sl": 0.0,
                    "tp": 0.0,
                    "deviation": 20,
                    "magic": MAGIC_GRID,
                    "comment": comment,
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": _get_filling_mode(sym),
                }

                res = mt5.order_send(req)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    last_h4_bar[sym] = current_h4_time
                    register_trade_context(
                        ticket=res.order,
                        risk_amount=0.0,
                        spread=round(current_spread_pips, 2),
                        slippage=0.0,
                        exhaustion_state=False,
                        volume=rates_h4[0]['tick_volume'],
                        smc_confluence="GRID_LAYER"
                    )
                    logger.info(f"[GRID ADDON ENTRY] Layer {len(basket)+1} on {sym} | Lot: {next_lot} (prev={previous_lot}) | Step: {adverse_move:.5f} (>= {h4_atr:.5f} ATR)")
                else:
                    logger.error(f"[{sym}] Grid Addon Entry Failed. Retcode: {res.retcode if res else 'None'}")
