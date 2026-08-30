"""
==================================================================
                   CAB MASTER - PERFORMANCE LEDGER
==================================================================
Manages excursion state memory (MFE/MAE), risk distances,
environmental snapshot injection, and CSV performance output.
Enhanced with R-velocity, gate flags, and richer Intelligencia.
==================================================================
"""

import MetaTrader5 as mt5
import pandas as pd
import os
import time
import logging
from datetime import datetime
import config

# --- STATE MEMORY TRACKERS ---
mfe_tracker = {}          # pos_id -> peak price
mae_tracker = {}          # pos_id -> worst price
mfe_time = {}             # pos_id -> unix timestamp when MFE was last updated
mae_time = {}             # pos_id -> unix timestamp when MAE was last updated
entry_risk = {}           # pos_id -> risk distance in price
tracked_ids = set()
entry_intelligence = {}   # pos_id -> full intelligencia snapshot (expanded)
be_hit = {}               # pos_id -> True if BE gate was ever reached
lock_hit = {}             # pos_id -> True if Lock gate was ever reached


def write_to_performance_ledger(pos, reason: str, exit_price: float, historic_deal=None) -> None:
    """Calculates structured metrics, merges Intelligencia data, and appends to CSV."""
    global mfe_tracker, mae_tracker, mfe_time, mae_time, entry_risk, entry_intelligence, be_hit, lock_hit
    
    pos_id = pos.identifier if hasattr(pos, 'identifier') else pos.ticket
    ticket = pos.ticket
    symbol = pos.symbol
    pos_type = pos.type
    volume = pos.volume
    price_open = pos.price_open
    time_open = pos.time
    
    try:
        is_buy = (pos_type == 0)
        risk_dist = entry_risk.get(pos_id, 0)
        
        if risk_dist <= 0:
            hist_orders = mt5.history_orders_get(position=pos_id)
            if hist_orders:
                for o in hist_orders:
                    if o.sl > 0:
                        risk_dist = abs(o.price_open - o.sl)
                        break
            if risk_dist <= 0:
                risk_dist = max(0.00001, abs(price_open - exit_price))

        risk_dist = max(risk_dist, 0.00001)

        # 1. Realized Performance
        gross_profit_price = (exit_price - price_open) if is_buy else (price_open - exit_price)
        realized_r = round(gross_profit_price / risk_dist, 4)
        
        # 2. Historical Excursion Peaks (MFE / MAE)
        peak_price = mfe_tracker.get(pos_id, exit_price)
        worst_price = mae_tracker.get(pos_id, exit_price)
        
        mfe_move = (peak_price - price_open) if is_buy else (price_open - peak_price)
        mae_move = (worst_price - price_open) if is_buy else (price_open - worst_price)
        
        mfe_r = round(max(0.0, mfe_move / risk_dist), 4)
        mae_r = round(min(0.0, mae_move / risk_dist), 4)

        # Time-to-peak / time-to-trough (hours from open)
        time_to_mfe = None
        time_to_mae = None
        if pos_id in mfe_time:
            time_to_mfe = round((mfe_time[pos_id] - time_open) / 3600.0, 3)
        if pos_id in mae_time:
            time_to_mae = round((mae_time[pos_id] - time_open) / 3600.0, 3)
        
        # 3. Retrieve Intelligencia Snapshot (expanded defaults)
        intel = entry_intelligence.get(pos_id, {
            "Session": "UNKNOWN", "Active_Risk_Trades": 0, "H1_ATR_State": "UNKNOWN",
            "H4_Trend_ADX": 0.0, "Macro_DXY_Proxy": "UNKNOWN", "Macro_Risk_Sentiment": "UNKNOWN",
            "EntrySpreadPoints": None, "EntryATR": None, "EntryATR_Pct": None,
            "ActiveSameDirection": 0, "ActiveCorrelated": 0
        })

        # 4. Time Duration Tracking
        time_open_str = datetime.fromtimestamp(time_open).strftime('%Y-%m-%d %H:%M:%S')
        time_close_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        duration_hours = round((time.time() - time_open) / 3600.0, 2)

        # 5. Gate flags
        reached_be = be_hit.get(pos_id, False)
        reached_lock = lock_hit.get(pos_id, False)

        trade_data = {
            "Ticket": ticket, "Symbol": symbol, "Direction": "BUY" if is_buy else "SELL",
            "Volume": volume, "OpenTime": time_open_str, "CloseTime": time_close_str,
            "DurationHours": duration_hours, "OpenPrice": price_open, "ExitPrice": exit_price,
            "RiskDistancePrice": round(risk_dist, 5), "Realized_R": realized_r,
            "MFE_Peak_R": mfe_r, "MAE_Trough_R": mae_r, "ExitReason": reason,
            
            # --- NEW: R-VELOCITY & GATES ---
            "TimeToMFE_Hours": time_to_mfe,
            "TimeToMAE_Hours": time_to_mae,
            "BE_Hit": reached_be,
            "Lock_Hit": reached_lock,

            # --- INTELLIGENCIA COLUMNS (expanded) ---
            "Intel_Session": intel.get("Session", "UNKNOWN"),
            "Intel_ActiveTrades": intel.get("Active_Risk_Trades", 0),
            "Intel_ATR_State": intel.get("H1_ATR_State", "UNKNOWN"),
            "Intel_H4_ADX": intel.get("H4_Trend_ADX", 0.0),
            "Intel_DXY_Trend": intel.get("Macro_DXY_Proxy", "UNKNOWN"),
            "Intel_Risk_Sentiment": intel.get("Macro_Risk_Sentiment", "UNKNOWN"),
            "EntrySpreadPoints": intel.get("EntrySpreadPoints"),
            "EntryATR": intel.get("EntryATR"),
            "EntryATR_Pct": intel.get("EntryATR_Pct"),
            "ActiveSameDirection": intel.get("ActiveSameDirection", 0),
            "ActiveCorrelated": intel.get("ActiveCorrelated", 0)
        }
        
        df = pd.DataFrame([trade_data])
        file_exists = os.path.isfile(config.LEDGER_FILE)
        df.to_csv(config.LEDGER_FILE, mode='a', index=False, header=not file_exists)
        logging.info(f"✔️ LEDGER SECURED: Position #{pos_id} [{reason}] saved with enhanced Intelligencia.")
        
    except Exception as ledger_error:
        logging.error(f"Ledger Safe-Fail Warning: Could not write metrics. Reason: {ledger_error}")


def sync_broker_closed_positions(active_ids: list) -> None:
    """Detects missing trades that hit broker SL/TP and logs them."""
    global tracked_ids, mfe_tracker, mae_tracker, mfe_time, mae_time, entry_risk, entry_intelligence, be_hit, lock_hit
    
    for vanished_id in list(tracked_ids):
        if vanished_id not in active_ids:
            logging.info(f"Detected missing trade #{vanished_id}. Fetching historical logs...")
            time.sleep(0.5) 
            
            history_deals = mt5.history_deals_get(position=vanished_id)
            
            if history_deals and len(history_deals) > 0:
                entry_deal = next((d for d in history_deals if d.entry == 0), None)
                exit_deal = next((d for d in history_deals if d.entry == 1), None)
                
                if entry_deal and exit_deal:
                    class MockPosition:
                        def __init__(self, en_d, ex_d, p_id):
                            self.ticket = ex_d.position_id
                            self.identifier = p_id
                            self.symbol = ex_d.symbol
                            self.type = en_d.type 
                            self.volume = ex_d.volume
                            self.price_open = en_d.price
                            self.time = en_d.time
                    
                    mock_pos = MockPosition(entry_deal, exit_deal, vanished_id)
                    reason_str = "BROKER_SL" if exit_deal.profit <= 0 else "BROKER_TP"
                    write_to_performance_ledger(mock_pos, reason_str, exit_deal.price, historic_deal=exit_deal)
            
            # Memory Cleanup Protocol
            tracked_ids.discard(vanished_id)
            mfe_tracker.pop(vanished_id, None)
            mae_tracker.pop(vanished_id, None)
            mfe_time.pop(vanished_id, None)
            mae_time.pop(vanished_id, None)
            entry_risk.pop(vanished_id, None)
            entry_intelligence.pop(vanished_id, None)
            be_hit.pop(vanished_id, None)
            lock_hit.pop(vanished_id, None)