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
    _close_position,
    snapshot_ltf_context,
    calculate_dynamic_lot
)

# Magic Number for Range Extraction Grid (ADX < 30)
MAGIC_GRID = 9995553
MAX_GRID_LAYERS = 5 # CAP AT 5 LAYERS
BASE_GRID_MULTIPLIER = 1.0 # Static base lot

# ── Grid sizing and exposure ceiling (fix-grid-sizing) ────────────────────────
# The grid's base leg used to be `max(0.01, sym_info.volume_min)` — the broker's
# minimum tradable lot, with no reference to account size or risk — while the
# inversion and continuation vectors both sized from RISK_PERCENT. The ladder was
# anchored the same way, internally re-deriving base_lot from volume_min rather
# than from the leg the basket actually held, and nothing capped the basket.
# Sep-12 audit of this bot: -$4,577 over 99 closed trades, of which USOILm -$3,196
# (two legs of 1.0 lot) and ETHUSDm -$1,305 (a ladder observed out to 1.68 lots,
# with a 46.63-lot ETH leg in the export). Both legs and the ladder are now
# risk-derived and the whole basket is bounded.
RISK_PERCENT = getattr(config, "RISK_PERCENT", 0.01)
MAX_BASKET_RISK_PCT = 0.03   # hard ceiling on total basket risk, fraction of equity

last_h4_bar = {sym: None for sym in config.SYMBOLS}
logger = logging.getLogger("STRAT_GRID")

def _grid_risk_per_lot(sym_info, sl_dist_price: float) -> float:
    """Money risked by 1.0 lot at the grid's notional stop distance. 0.0 if unknown."""
    try:
        if sl_dist_price <= 0 or sym_info.point <= 0:
            return 0.0
        point_value = sym_info.trade_tick_value / (sym_info.trade_tick_size / sym_info.point)
        return (sl_dist_price / sym_info.point) * point_value
    except Exception:
        return 0.0

def _projected_basket_risk(sym_info, sl_dist_price: float,
                           basket_volume: float, extra_volume: float):
    """Total money risk of (existing basket + proposed leg). None when unknowable."""
    per_lot = _grid_risk_per_lot(sym_info, sl_dist_price)
    if per_lot <= 0:
        return None
    return per_lot * (basket_volume + extra_volume)

def _risk_cap_amount():
    """Absolute money ceiling on total grid-basket risk. None when equity is unreadable."""
    acct = mt5.account_info()
    if acct is None or acct.equity <= 0:
        return None
    return acct.equity * MAX_BASKET_RISK_PCT

def _calculate_grid_addon_lot(sym_info, layer_index: int, base_lot: float) -> float:
    """
    Behavioral Scaling: Layers 1-2 (Feeler) = 1.0x, Layers 3-5 (Commitment) = 1.5x, 2.0x, 2.5x

    fix-grid-sizing: `base_lot` is now passed in as the risk-derived unit for this
    symbol (see RISK_PERCENT above). It used to be re-derived internally as
    max(0.01, volume_min), so the ladder was anchored to the broker minimum rather
    than to the leg the basket actually holds.
    """
    unit = max(float(base_lot), sym_info.volume_min)
    if layer_index <= 2:
        raw_lot = unit * 1.0
    elif layer_index == 3:
        raw_lot = unit * 1.5
    elif layer_index == 4:
        raw_lot = unit * 2.0
    else:
        raw_lot = unit * 2.5
        
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

            # fix-grid-sizing: the base leg is risk-derived, and refused outright if
            # its projected risk alone would breach the basket ceiling.
            sl_dist_notional = h4_atr * config.ATR_MULT_SL
            base_lot = calculate_dynamic_lot(sym, sl_dist_notional, RISK_PERCENT)
            if base_lot is None or base_lot <= 0:
                logger.warning(f"[{sym}] Grid base skipped — lot sizing returned {base_lot}")
                continue

            _projected = _projected_basket_risk(sym_info, sl_dist_notional, 0.0, base_lot)
            _cap = _risk_cap_amount()
            if _projected is None or _cap is None or _projected > _cap:
                logger.warning(
                    f"[{sym}] Grid base BLOCKED — projected risk "
                    f"{'?' if _projected is None else f'${_projected:.2f}'} > cap "
                    f"{'?' if _cap is None else f'${_cap:.2f}'} "
                    f"({MAX_BASKET_RISK_PCT:.0%} of equity)"
                )
                last_h4_bar[sym] = current_h4_time
                continue

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
                # Calculate notional risk for R-multiple tracking
                try:
                    point_value = sym_info.trade_tick_value / (sym_info.trade_tick_size / sym_info.point)
                    sl_dist_notional = h4_atr * config.ATR_MULT_SL
                    sl_points = sl_dist_notional / sym_info.point
                    risk_amount = sl_points * point_value * float(base_lot)
                except Exception:
                    risk_amount = 0.0
                
                # Session label
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

                ltf = snapshot_ltf_context(sym, signal)
                register_trade_context(
                    ticket=res.order,
                    risk_amount=risk_amount,
                    spread=round(current_spread_pips, 2),
                    slippage=0.0,
                    exhaustion_state=False,
                    volume=rates_h4[0]['tick_volume'],
                    smc_confluence="GRID_INITIAL",
                    adx=adx,
                    plus_di=0.0,
                    minus_di=0.0,
                    ema50=0.0,
                    session=sess,
                    subtype=comment,
                    **ltf
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

            # Check Geometric Spacing & Max Depth
            # Layer 1 = 1 ATR, Layer 2 = 1.5 ATR, Layer 3 = 2.0 ATR...
            current_layer = len(basket)
            required_spacing = h4_atr * (1.0 + (current_layer - 1) * 0.5)
            
            if adverse_move >= required_spacing and current_layer < MAX_GRID_LAYERS:
                # fix-grid-sizing: ladder anchored to the risk-derived unit, and the
                # basket as a whole may not exceed MAX_BASKET_RISK_PCT of equity.
                # Before this, `next_lot` came from a ladder anchored to the broker
                # minimum with no ceiling on the basket at all.
                sl_dist_notional = h4_atr * config.ATR_MULT_SL
                base_unit_lot = calculate_dynamic_lot(sym, sl_dist_notional, RISK_PERCENT)
                next_lot = _calculate_grid_addon_lot(sym_info, current_layer + 1, base_unit_lot)

                _basket_vol = sum(p.volume for p in basket)
                _projected = _projected_basket_risk(sym_info, sl_dist_notional, _basket_vol, next_lot)
                _cap = _risk_cap_amount()
                if _projected is None or _cap is None or _projected > _cap:
                    logger.warning(
                        f"[{sym}] GRID ADDON BLOCKED at layer {current_layer + 1} — "
                        f"projected basket risk "
                        f"{'?' if _projected is None else f'${_projected:.2f}'} > cap "
                        f"{'?' if _cap is None else f'${_cap:.2f}'} "
                        f"({MAX_BASKET_RISK_PCT:.0%} of equity). "
                        f"Basket held at {_basket_vol:.2f} lots."
                    )
                    continue

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
                    # Calculate notional risk for R-multiple tracking
                    try:
                        point_value = sym_info.trade_tick_value / (sym_info.trade_tick_size / sym_info.point)
                        sl_dist_notional = h4_atr * config.ATR_MULT_SL
                        sl_points = sl_dist_notional / sym_info.point
                        risk_amount = sl_points * point_value * float(next_lot)
                    except Exception:
                        risk_amount = 0.0
                    
                    # Session label
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

                    ltf = snapshot_ltf_context(sym, "BULLISH" if is_buy else "BEARISH")
                    register_trade_context(
                        ticket=res.order,
                        risk_amount=risk_amount,
                        spread=round(current_spread_pips, 2),
                        slippage=0.0,
                        exhaustion_state=False,
                        volume=rates_h4[0]['tick_volume'],
                        smc_confluence="GRID_LAYER",
                        adx=adx,
                        plus_di=0.0,
                        minus_di=0.0,
                        ema50=0.0,
                        session=sess,
                        subtype=comment,
                        **ltf
                    )
                    logger.info(f"[GRID ADDON ENTRY] Layer {current_layer+1} on {sym} | Lot: {next_lot} | Step: {adverse_move:.5f} (>= {required_spacing:.5f} ATR)")
                else:
                    logger.error(f"[{sym}] Grid Addon Entry Failed. Retcode: {res.retcode if res else 'None'}")
