import MetaTrader5 as mt5
from datetime import timedelta
import logging
import pandas as pd
import config
import time
import json
import os
import csv

harvested_tickets = set()
active_excursions = {}  
trade_context = {}      
flip_ledger = {}        
h1_breach_tracker = {}  

CONTEXT_FILE = "trade_context.json"
# fix-excursion-series: standalone CAB had no persistent MFE/MAE series (it only
# printed them inside a log line), which is why the Sep-12 cross-bot audit could
# not include it in the MFE/MAE comparison against cab_super and cab_multi_pair.
EXCURSION_FILE = "trade_excursions.csv"
last_harvest_time = 0

def load_trade_context():
    """Loads trade risk context from disk to survive script restarts."""
    global trade_context
    if os.path.exists(CONTEXT_FILE):
        try:
            with open(CONTEXT_FILE, "r") as f:
                data = json.load(f)
                trade_context = {int(k): v for k, v in data.items()}
        except Exception as e:
            logging.error(f"Failed to load trade_context: {e}")

def save_trade_context():
    """
    Saves trade risk context to disk, atomically.

    fix-atomic-context: a plain open("w") + json.dump left a torn file whenever
    the process was killed mid-write — crash.log line "Failed to load
    trade_context: Expecting value: line 1 column 124 (char 123)" is exactly
    that. Every subsequent write then truncated the corrupt file again, silently
    losing the risk_amount for every open ticket (which is what produced the
    0.00R rows). Write to a sibling temp file, fsync, then os.replace() so a
    reader can only ever observe a complete document.
    """
    try:
        tmp = f"{CONTEXT_FILE}.tmp"
        with open(tmp, "w") as f:
            json.dump({str(k): v for k, v in trade_context.items()}, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, CONTEXT_FILE)
    except Exception as e:
        logging.error(f"Failed to save trade_context: {e}")

def _append_excursion_row(row: dict):
    """
    Appends one closed-trade excursion record to the standalone excursion series.

    Never raises: a failed analytics append must not break the harvest loop.
    """
    try:
        new_file = not os.path.exists(EXCURSION_FILE)
        with open(EXCURSION_FILE, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(row.keys()))
            if new_file:
                w.writeheader()
            w.writerow(row)
    except Exception as e:
        logging.error(f"Failed to append excursion row: {e}")

# Load context memory on startup
load_trade_context()

def register_trade_context(ticket, risk_amount, spread, slippage, exhaustion_state, volume, smc_confluence,
                            adx=0.0, plus_di=0.0, minus_di=0.0, ema50=0.0,
                            session="OTHER", subtype="UNKNOWN",
                            h4_atr=0.0, m5_atr=0.0, atr_ratio=0.0, m5_dist_to_swing_atr=0.0,
                            m5_structure="UNKNOWN"):
    """Stores entry diagnostics persistently (enhanced with directional context + LTF snapshot)."""
    trade_context[ticket] = {
        'risk_amount': risk_amount,
        'spread': spread,
        'slippage': slippage,
        'exhaustion_state': exhaustion_state,
        'volume': int(volume),
        'smc_confluence': smc_confluence,
        'adx': round(adx, 2),
        'plus_di': round(plus_di, 2),
        'minus_di': round(minus_di, 2),
        'ema50': round(ema50, 5),
        'session': session,
        'subtype': subtype,
        'h4_atr': round(h4_atr, 6),
        'm5_atr': round(m5_atr, 6),
        'atr_ratio': round(atr_ratio, 4),
        'm5_dist_to_swing_atr': round(m5_dist_to_swing_atr, 2),
        'm5_structure': m5_structure,
    }
    save_trade_context()

def log_structural_flip(ticket, reason="STRUCTURAL_FLIP"):
    """Flags a ticket as being closed by an early structural invalidation."""
    flip_ledger[ticket] = reason

def track_h1_structure(magic_number):
    """Passive H1 background monitoring for decay hypothesis."""
    positions = mt5.positions_get()
    if not positions: return
    
    for pos in positions:
        if pos.magic == magic_number and pos.ticket not in h1_breach_tracker:
            rates = mt5.copy_rates_from_pos(pos.symbol, mt5.TIMEFRAME_H1, 1, 4)
            if rates is None or len(rates) < 4: continue
            
            df = pd.DataFrame(rates)
            tick = mt5.symbol_info_tick(pos.symbol)
            if tick is None: continue
            
            is_buy = pos.type == mt5.ORDER_TYPE_BUY
            breached = tick.bid < df['low'].min() if is_buy else tick.ask > df['high'].max()
            
            if breached:
                h1_breach_tracker[pos.ticket] = tick.time 

def track_active_excursions(magic_number):
    """
    Monitors live floating MFE/MAE excursions.

    fix-excursion-origin: mfe/mae used to be seeded with the profit observed on
    the FIRST cycle a position was seen. Any trade already in the red when first
    observed (restart mid-trade, or simply the second cycle after entry) therefore
    seeded MFE with a negative number, so MFE could never record a favourable
    excursion — production logs show "MFE: $-56.24 (0.0%)" on losing trades and
    "MFE: $207.05" equal to profit on winners. Excursions are defined from entry,
    so they now seed at max(0, profit) / min(0, profit).
    """
    positions = mt5.positions_get()
    if positions is None: return

    for pos in positions:
        if pos.magic != magic_number:
            continue
        ticket = pos.ticket
        current_profit = pos.profit
        current_time = pos.time_update

        if ticket not in active_excursions:
            active_excursions[ticket] = {
                'mfe': max(0.0, current_profit),
                'mae': min(0.0, current_profit),
                'mfe_time': current_time,
                'mae_time': current_time,
                'samples': 1,
            }
        else:
            exc = active_excursions[ticket]
            if current_profit > exc['mfe']:
                exc['mfe'] = current_profit
                exc['mfe_time'] = current_time
            if current_profit < exc['mae']:
                exc['mae'] = current_profit
                exc['mae_time'] = current_time
            exc['samples'] = exc.get('samples', 0) + 1

def harvest_closed_trades(magic_number):
    global harvested_tickets, active_excursions, trade_context, flip_ledger, h1_breach_tracker, last_harvest_time
    logger = logging.getLogger()
    
    terminal_info = mt5.terminal_info()
    if not terminal_info: return
    
    tick_ref = mt5.symbol_info_tick(config.SYMBOLS[0])
    if tick_ref is None: return
    current_broker_time = tick_ref.time + 86400
    start_time = int(time.time() - 172800) if last_harvest_time == 0 else last_harvest_time
    
    history_deals = mt5.history_deals_get(start_time, current_broker_time) 
    if not history_deals: return
    
    for deal in history_deals:
        if deal.magic == magic_number and deal.entry == mt5.DEAL_ENTRY_OUT:
            ticket = deal.position_id
            if ticket in harvested_tickets: continue
            
            history_orders = mt5.history_orders_get(position=ticket)
            if not history_orders: continue
            
            ENTRY_TYPES = (
                mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL,
                mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_LIMIT,
                mt5.ORDER_TYPE_BUY_STOP, mt5.ORDER_TYPE_SELL_STOP,
            )
            entry_order = next((o for o in history_orders if o.type in ENTRY_TYPES), None)
            if not entry_order: continue
            
            profit = deal.profit
            duration = deal.time - entry_order.time_setup
            dur_str = str(timedelta(seconds=duration))
            
            exit_reason = flip_ledger.pop(ticket, "HARD_STOP" if profit <= 0 else "TRAILING_STOP")

            excursion_data = active_excursions.pop(ticket, None)
            if excursion_data:
                mfe = max(excursion_data['mfe'], profit)
                mae = min(excursion_data['mae'], profit)
                excursion_samples = excursion_data.get('samples', 0)
            else:
                # Never sampled before it closed (harvest raced the first cycle).
                # The realised value is a bound, not the true excursion, so record
                # it with samples=0 to keep it distinguishable downstream.
                mfe = max(0.0, profit)
                mae = min(0.0, profit)
                excursion_samples = 0

            ctx = trade_context.pop(ticket, {})
            risk_amount = ctx.get('risk_amount', None)

            mfe_capture = (profit / mfe * 100) if mfe > 0 and profit > 0 else 0.0

            # fix-r-multiple: a missing risk_amount used to fall through to a silent
            # 0.00R, which then averaged into downstream analysis as if it were a
            # real flat trade (104 such rows in the production log). Emit an explicit
            # 'N/A' sentinel instead so unknown risk is visibly unknown.
            if risk_amount and risk_amount > 0:
                r_multiple_val = profit / risk_amount
                r_display = f"{r_multiple_val:.2f}R"
            else:
                r_multiple_val = None
                r_display = "N/A"

            r_saved = (round(r_multiple_val - (-1.0), 2)
                       if (r_multiple_val is not None
                           and ("FLIP" in exit_reason or "H1_STRUCT" in exit_reason))
                       else "N/A")
            
            decay_time = "N/A"
            h1_breach_time = h1_breach_tracker.pop(ticket, None)
            if h1_breach_time:
                decay_duration = deal.time - h1_breach_time
                if decay_duration > 0:
                    decay_time = str(timedelta(seconds=decay_duration))
            
            adx_val = ctx.get('adx', 0.0)
            subtype_val = ctx.get('subtype', 'UNKNOWN')
            session_val = ctx.get('session', 'OTHER')
            atr_ratio_val = ctx.get('atr_ratio', 0.0)
            m5_struct_val = ctx.get('m5_structure', 'UNKNOWN')
            
            logger.info(
                f"[METRICS] HARVESTED | ID {ticket} | {deal.symbol} | Profit: ${profit:.2f} | R: {r_display} | "
                f"Exit: {exit_reason} | R-Saved: {r_saved} | MFE: ${mfe:.2f} ({mfe_capture:.1f}%) | "
                f"MAE: ${mae:.2f} | H1-Decay: {decay_time} | Dur: {dur_str} | "
                f"ADX: {adx_val:.1f} | Sub: {subtype_val} | Session: {session_val} | "
                f"ATR_Ratio: {atr_ratio_val:.3f} | M5_Struct: {m5_struct_val}"
            )

            # Persist the excursion record so the standalone bot has the same MFE/MAE
            # series the other CAB variants already publish.
            _append_excursion_row({
                'ticket': ticket,
                'symbol': deal.symbol,
                'magic': magic_number,
                'profit': round(profit, 2),
                'risk_amount': round(risk_amount, 2) if risk_amount else '',
                'realized_r': round(r_multiple_val, 4) if r_multiple_val is not None else '',
                'mfe_usd': round(mfe, 2),
                'mae_usd': round(mae, 2),
                'mfe_capture_pct': round(mfe_capture, 1),
                'excursion_samples': excursion_samples,
                'exit_reason': exit_reason,
                'duration_seconds': duration,
                'duration_str': dur_str,
                'adx': adx_val,
                'subtype': subtype_val,
                'session': session_val,
                'atr_ratio': atr_ratio_val,
                'm5_structure': m5_struct_val,
                'h4_atr': ctx.get('h4_atr', 0.0),
                'm5_atr': ctx.get('m5_atr', 0.0),
                'closed_at': deal.time,
            })

            harvested_tickets.add(ticket)
            save_trade_context()
            
    last_harvest_time = tick_ref.time