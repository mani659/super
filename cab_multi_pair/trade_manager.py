"""
==================================================================
                 CAB MASTER - TRADE MANAGER
==================================================================
Monitors active positions, updates MFE/MAE state memory,
handles trailing stops, executes protective trade closures,
and records the Market Intelligencia snapshot upon entry.
==================================================================
"""

import MetaTrader5 as mt5
import time
import logging
import config
from utils import _get_filling_mode
import ledger
from signals import check_h4_inversion, check_h1_structural_breach
from analytics.intelligencia import get_entry_intelligence

def _close_position(pos, reason: str) -> bool:
    """Closes an active position and triggers ledger audit."""
    tick = mt5.symbol_info_tick(pos.symbol)
    if tick is None: 
        return False
        
    exit_price = tick.bid if pos.type == 0 else tick.ask
    
    req = {
        "action": mt5.TRADE_ACTION_DEAL, 
        "position": pos.ticket, 
        "symbol": pos.symbol,
        "volume": pos.volume, 
        "type": mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
        "price": exit_price, 
        "deviation": 20, 
        "magic": config.MAGIC_NUMBER,
        "comment": reason[:31], 
        "type_time": mt5.ORDER_TIME_GTC, 
        "type_filling": _get_filling_mode(pos.symbol)
    }
    
    res = mt5.order_send(req)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        logging.info(f"KILLED #{pos.identifier} [{pos.symbol}] | Reason: {reason}")
        ledger.write_to_performance_ledger(pos, reason, exit_price)
        if pos.identifier in ledger.tracked_ids:
            ledger.tracked_ids.remove(pos.identifier)
        return True
    return False

def _modify_sl(pos, new_sl: float) -> bool:
    """Modifies the stop loss for an active position."""
    sym_info = mt5.symbol_info(pos.symbol)
    if sym_info is None: 
        return False
        
    req = {
        "action": mt5.TRADE_ACTION_SLTP, 
        "position": pos.ticket, 
        "sl": round(new_sl, sym_info.digits), 
        "tp": 0.0
    }
    res = mt5.order_send(req)
    return res is not None and res.retcode == mt5.TRADE_RETCODE_DONE

def manage_open_trades() -> None:
    """Main loop for updating trade states, trailing stops, and protective checks."""
    positions = mt5.positions_get()
    active_ids = [p.identifier for p in positions if p.magic == config.MAGIC_NUMBER] if positions else []

    # Sync any trades that were closed by the broker (SL/TP) before processing active ones
    ledger.sync_broker_closed_positions(active_ids)

    if not positions: 
        return

    for pos in positions:
        if pos.magic != config.MAGIC_NUMBER or pos.symbol not in config.SYMBOLS: 
            continue
        
        pos_id = pos.identifier
        ledger.tracked_ids.add(pos_id) 
        is_buy = (pos.type == 0)
        
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None: 
            continue
            
        current_price = tick.bid if is_buy else tick.ask

        # 1. Establish Risk Distance & Capture Entry Intelligencia Snapshot
        if pos_id not in ledger.entry_risk:
            dist = abs(pos.price_open - pos.sl)
            if dist > 0: 
                ledger.entry_risk[pos_id] = dist
                
                # --- NEW: TRIGGER INTELLIGENCIA SNAPSHOT ---
                if pos_id not in ledger.entry_intelligence:
                    ledger.entry_intelligence[pos_id] = get_entry_intelligence(pos.symbol)
            else: 
                continue
            
        risk_dist = max(ledger.entry_risk[pos_id], 0.00001)
        price_move = (current_price - pos.price_open) if is_buy else (pos.price_open - current_price)
        current_r = price_move / risk_dist

        # 2. Update MFE and MAE State Memory
        if pos_id not in ledger.mfe_tracker: ledger.mfe_tracker[pos_id] = current_price
        if pos_id not in ledger.mae_tracker: ledger.mae_tracker[pos_id] = current_price
        
        if is_buy:
            if current_price > ledger.mfe_tracker[pos_id]: ledger.mfe_tracker[pos_id] = current_price
            if current_price < ledger.mae_tracker[pos_id]: ledger.mae_tracker[pos_id] = current_price
        else:
            if current_price < ledger.mfe_tracker[pos_id]: ledger.mfe_tracker[pos_id] = current_price
            if current_price > ledger.mae_tracker[pos_id]: ledger.mae_tracker[pos_id] = current_price

        # 3. Protective Sentinel Checks
        hours_open = (time.time() - pos.time) / 3600.0

        h4_signal = check_h4_inversion(pos.symbol)
        if (is_buy and h4_signal == "BEARISH") or (not is_buy and h4_signal == "BULLISH"):
            _close_position(pos, "OPP_H4_SIGNAL")
            continue

        # Data-backed 6h suppression for chop noise
        if hours_open >= 6.0:
            if check_h1_structural_breach(pos.symbol, is_buy):
                _close_position(pos, "H1_STRUCT_BREACH")
                continue

        if hours_open >= config.STAGNATION_HOURS and current_r < 0.5:
            _close_position(pos, "STAGNATION_DECAY")
            continue

        # 4. Configured Trailing & Gate Execution
        updated_best = ledger.mfe_tracker[pos_id]
        pair_conf = config.PAIRS.get(pos.symbol, {})
        be_gate_r = pair_conf.get("BE_GATE_R", 1.0)
        lock_gate_r = pair_conf.get("LOCK_GATE_R", 1.5)
        
        peak_move = (updated_best - pos.price_open) if is_buy else (pos.price_open - updated_best)
        peak_r = peak_move / risk_dist
        
        target_sl = pos.sl
        if peak_r >= lock_gate_r:
            # Trailing Phase: 1R behind peak
            target_sl = updated_best - risk_dist if is_buy else updated_best + risk_dist
        elif peak_r >= be_gate_r:
            # Break-Even Phase: Lock Open Price + 5% buffer
            buffer = risk_dist * 0.05
            target_sl = pos.price_open + buffer if is_buy else pos.price_open - buffer
            
        if is_buy and target_sl > pos.sl:
            _modify_sl(pos, target_sl)
        elif not is_buy and target_sl < pos.sl and pos.sl > 0:
            _modify_sl(pos, target_sl)