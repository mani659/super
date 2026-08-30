import MetaTrader5 as mt5
from datetime import timedelta
import logging
import pandas as pd
import config
import time
import json
import os

harvested_tickets = set()
active_excursions = {}  
trade_context = {}      
flip_ledger = {}        
h1_breach_tracker = {}  

CONTEXT_FILE = "trade_context.json"
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
    """Saves trade risk context to disk."""
    try:
        with open(CONTEXT_FILE, "w") as f:
            json.dump({str(k): v for k, v in trade_context.items()}, f)
    except Exception as e:
        logging.error(f"Failed to save trade_context: {e}")

# Load context memory on startup
load_trade_context()

def register_trade_context(ticket, risk_amount, spread, slippage, exhaustion_state, volume, smc_confluence,
                            adx=0.0, plus_di=0.0, minus_di=0.0, ema50=0.0,
                            session="OTHER", subtype="UNKNOWN"):
    """Stores entry diagnostics persistently (enhanced with directional context)."""
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
        'subtype': subtype
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
    """Monitors live floating MFE/MAE excursions."""
    positions = mt5.positions_get()
    if positions is None: return

    for pos in positions:
        if pos.magic == magic_number:
            ticket = pos.ticket
            current_profit = pos.profit
            current_time = pos.time_update 
            
            if ticket not in active_excursions:
                active_excursions[ticket] = {'mfe': current_profit, 'mae': current_profit, 'mfe_time': current_time, 'mae_time': current_time}
            else:
                if current_profit > active_excursions[ticket]['mfe']:
                    active_excursions[ticket]['mfe'] = current_profit
                    active_excursions[ticket]['mfe_time'] = current_time
                if current_profit < active_excursions[ticket]['mae']:
                    active_excursions[ticket]['mae'] = current_profit
                    active_excursions[ticket]['mae_time'] = current_time

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
            
            entry_order = next((o for o in history_orders if o.type in (mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL)), None)
            if not entry_order: continue
            
            profit = deal.profit
            duration = deal.time - entry_order.time_setup
            dur_str = str(timedelta(seconds=duration))
            
            exit_reason = flip_ledger.pop(ticket, "HARD_STOP" if profit <= 0 else "TRAILING_STOP")
            
            excursion_data = active_excursions.pop(ticket, {'mfe': profit, 'mae': profit})
            mfe = max(excursion_data['mfe'], profit)
            mae = min(excursion_data['mae'], profit)
            
            ctx = trade_context.pop(ticket, {})
            risk_amount = ctx.get('risk_amount', None)
            
            mfe_capture = (profit / mfe * 100) if mfe > 0 and profit > 0 else 0.0
            r_multiple_val = profit / risk_amount if (risk_amount and risk_amount > 0) else 0.0
            
            r_saved = round(r_multiple_val - (-1.0), 2) if "FLIP" in exit_reason or "H1_STRUCT" in exit_reason else "N/A"
            
            decay_time = "N/A"
            h1_breach_time = h1_breach_tracker.pop(ticket, None)
            if h1_breach_time:
                decay_duration = deal.time - h1_breach_time
                if decay_duration > 0:
                    decay_time = str(timedelta(seconds=decay_duration))
            
            adx_val = ctx.get('adx', 0.0)
            subtype_val = ctx.get('subtype', 'UNKNOWN')
            session_val = ctx.get('session', 'OTHER')
            
            logger.info(
                f"[METRICS] HARVESTED | ID {ticket} | {deal.symbol} | Profit: ${profit:.2f} | R: {r_multiple_val:.2f}R | "
                f"Exit: {exit_reason} | R-Saved: {r_saved} | MFE: ${mfe:.2f} ({mfe_capture:.1f}%) | "
                f"MAE: ${mae:.2f} | H1-Decay: {decay_time} | Dur: {dur_str} | "
                f"ADX: {adx_val:.1f} | Sub: {subtype_val} | Session: {session_val}"
            )
            harvested_tickets.add(ticket)
            save_trade_context()
            
    last_harvest_time = tick_ref.time