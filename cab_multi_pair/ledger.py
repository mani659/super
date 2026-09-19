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
import csv
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

# --- PATH CLOCK TRACKERS (observation-layer, no strategy impact) ---
time_to_0_3r = {}         # pos_id -> hours from open when peak_r first reached 0.3
time_to_0_5r = {}         # pos_id -> hours from open when peak_r first reached 0.5
time_to_mae_0_5 = {}      # pos_id -> hours from open when MAE first reached -0.5R

# --- CANONICAL LEDGER SCHEMA (fix-ledger-schema) -----------------------------
# Rows used to be appended via pandas' default dict-order write. That is only safe
# while the column set never changes, and it did: the file on disk carries a
# 20-column header while the current row dict has 34 keys, so every append after
# that point landed under the wrong column names. The Sep-12 audit found the symptom
# directly — "Intel_Session" holding floats (0.016, 4.493, 11.823) and
# "Intel_ATR_State" holding True/False. Those are TimeToMFE_Hours and BE_Hit in
# Intel_Session's and Intel_ATR_State's slots. Every session and ATR-state statistic
# read off this file has been wrong since the drift.
# The schema is now explicit and a drifted file is archived rather than appended to.
LEDGER_COLUMNS = [
    "Ticket", "Symbol", "Direction", "Volume", "OpenTime", "CloseTime",
    "DurationHours", "OpenPrice", "ExitPrice",
    # --- risk & outcome (fix-r-money-unit) ---
    "RiskDistancePrice", "RiskSource", "EntryRiskMoney", "Realized_R", "Realized_USD",
    "MFE_Peak_R", "MAE_Trough_R", "ExitReason",
    # --- R-velocity & gates ---
    "TimeToMFE_Hours", "TimeToMAE_Hours", "BE_Hit", "Lock_Hit",
    # --- path clocks ---
    "TimeTo0_3R_Hours", "TimeTo0_5R_Hours", "TimeToMAE_0_5_Hours",
    "VolGroup", "H1_MinHours_Config",
    # --- intelligencia ---
    "Intel_Session", "Intel_ActiveTrades", "Intel_ATR_State", "Intel_H4_ADX",
    "Intel_DXY_Trend", "Intel_Risk_Sentiment",
    "EntrySpreadPoints", "EntryATR", "EntryATR_Pct",
    "ActiveSameDirection", "ActiveCorrelated",
    # --- LTF structure research (M15) ---
    "LiqSweptPrior", "FvgWithSignal", "DistNextPoolAtr",
]

def _existing_header():
    """First line of the ledger as a list of names, or None when the file is absent."""
    try:
        if not os.path.isfile(config.LEDGER_FILE):
            return None
        with open(config.LEDGER_FILE, "r", newline="") as f:
            first = f.readline().strip()
        return next(csv.reader([first])) if first else []
    except Exception:
        return None

def _prepare_ledger_file() -> None:
    """
    Ensures the ledger carries the canonical header, archiving a drifted file first.

    A drifted header cannot be repaired by relabelling — the misaligned rows are
    unrecoverable — so the old file is preserved under a .legacy-<stamp> name instead
    of being mixed with correctly-aligned rows.
    """
    header = _existing_header()
    if header is None or header == LEDGER_COLUMNS:
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = f"{config.LEDGER_FILE}.legacy-{stamp}.csv"
    try:
        os.replace(config.LEDGER_FILE, archive)
        logging.warning(
            f"LEDGER SCHEMA DRIFT: existing header had {len(header)} columns, current "
            f"schema has {len(LEDGER_COLUMNS)}. Archived to {archive} and starting a "
            f"correctly-aligned ledger. Rows in the archived file are mislabelled."
        )
    except Exception as e:
        logging.error(f"Could not archive drifted ledger: {e}")

def _risk_money(symbol: str, volume: float, risk_dist_price: float) -> float:
    """Money risked by `volume` lots across `risk_dist_price`. 0.0 when uncomputable."""
    try:
        si = mt5.symbol_info(symbol)
        if si is None or si.point <= 0 or volume <= 0 or risk_dist_price <= 0:
            return 0.0
        point_value = si.trade_tick_value / (si.trade_tick_size / si.point)
        return (risk_dist_price / si.point) * point_value * float(volume)
    except Exception:
        return 0.0


def write_to_performance_ledger(pos, reason: str, exit_price: float, historic_deal=None) -> None:
    """Calculates structured metrics, merges Intelligencia data, and appends to CSV."""
    global mfe_tracker, mae_tracker, mfe_time, mae_time, entry_risk, entry_intelligence, be_hit, lock_hit
    global time_to_0_3r, time_to_0_5r, time_to_mae_0_5
    
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
        risk_source = "ENTRY_TRACK" if risk_dist > 0 else None

        if risk_dist <= 0:
            hist_orders = mt5.history_orders_get(position=pos_id)
            if hist_orders:
                for o in hist_orders:
                    if o.sl > 0:
                        risk_dist = abs(o.price_open - o.sl)
                        risk_source = "BROKER_ORDER"
                        break
            if risk_dist <= 0:
                # fix-r-circular: this fallback derives the R denominator from the exit
                # itself, so Realized_R collapses to ~-1.0 on any stop and ~+1.0 on any
                # target regardless of risk actually taken — which is exactly what the
                # Sep-12 audit measured (BROKER_SL avg R -0.981, BROKER_TP avg +1.023,
                # while implied $/R ranged $4.44-$114.81). Kept only so the row is not
                # lost; RiskSource marks it so analyses can exclude it.
                risk_dist = max(0.00001, abs(price_open - exit_price))
                risk_source = "EXIT_FALLBACK"

        risk_dist = max(risk_dist, 0.00001)

        # 1. Realized Performance
        gross_profit_price = (exit_price - price_open) if is_buy else (price_open - exit_price)
        realized_r = round(gross_profit_price / risk_dist, 4)

        # fix-r-money-unit: 1R was not a money unit, so summing R did not reconcile with
        # the account — Sep-12 saw the ledger total +21.09R against an actual -$842.79 on
        # the same 167 tickets. Record the money at risk and the money realized so R and
        # dollars can be reconciled row by row instead of trusted in aggregate.
        realized_usd = None
        if historic_deal is not None:
            try:
                realized_usd = round(
                    historic_deal.profit
                    + (getattr(historic_deal, "swap", 0.0) or 0.0)
                    + (getattr(historic_deal, "commission", 0.0) or 0.0), 2
                )
            except Exception:
                realized_usd = None
        if realized_usd is None:
            try:
                realized_usd = round(pos.profit + (getattr(pos, "swap", 0.0) or 0.0), 2)
            except Exception:
                realized_usd = None
        entry_risk_money = round(_risk_money(symbol, volume, risk_dist), 2)
        
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
            "ActiveSameDirection": 0, "ActiveCorrelated": 0,
            "liq_swept_prior": 0, "fvg_with_signal": 0, "dist_next_pool_atr": 0.0
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
            "RiskDistancePrice": round(risk_dist, 5),
            "RiskSource": risk_source,
            "EntryRiskMoney": entry_risk_money,
            "Realized_R": realized_r,
            "Realized_USD": realized_usd,
            "MFE_Peak_R": mfe_r, "MAE_Trough_R": mae_r, "ExitReason": reason,
            
            # --- NEW: R-VELOCITY & GATES ---
            "TimeToMFE_Hours": time_to_mfe,
            "TimeToMAE_Hours": time_to_mae,
            "BE_Hit": reached_be,
            "Lock_Hit": reached_lock,

            # --- PATH CLOCKS (observation-layer) ---
            "TimeTo0_3R_Hours": time_to_0_3r.get(pos_id),
            "TimeTo0_5R_Hours": time_to_0_5r.get(pos_id),
            "TimeToMAE_0_5_Hours": time_to_mae_0_5.get(pos_id),
            "VolGroup": config.get_vol_group(symbol),
            "H1_MinHours_Config": config.PAIRS.get(symbol, {}).get("H1_MIN_HOURS", 6.0),

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
            "ActiveCorrelated": intel.get("ActiveCorrelated", 0),

            # --- LTF STRUCTURE RESEARCH (M15) ---
            "LiqSweptPrior": intel.get("liq_swept_prior", 0),
            "FvgWithSignal": intel.get("fvg_with_signal", 0),
            "DistNextPoolAtr": intel.get("dist_next_pool_atr", 0.0),
        }
        
        # fix-ledger-schema: write against the explicit canonical schema, never against
        # dict insertion order, and archive the file first if its header has drifted.
        _prepare_ledger_file()
        df = pd.DataFrame([trade_data]).reindex(columns=LEDGER_COLUMNS)
        file_exists = os.path.isfile(config.LEDGER_FILE)
        df.to_csv(config.LEDGER_FILE, mode='a', index=False, header=not file_exists)
        logging.info(f"✔️ LEDGER SECURED: Position #{pos_id} [{reason}] saved with enhanced Intelligencia.")
        
    except Exception as ledger_error:
        logging.error(f"Ledger Safe-Fail Warning: Could not write metrics. Reason: {ledger_error}")


def sync_broker_closed_positions(active_ids: list) -> None:
    """Detects missing trades that hit broker SL/TP and logs them."""
    global tracked_ids, mfe_tracker, mae_tracker, mfe_time, mae_time, entry_risk, entry_intelligence, be_hit, lock_hit
    global time_to_0_3r, time_to_0_5r, time_to_mae_0_5
    
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
            time_to_0_3r.pop(vanished_id, None)
            time_to_0_5r.pop(vanished_id, None)
            time_to_mae_0_5.pop(vanished_id, None)