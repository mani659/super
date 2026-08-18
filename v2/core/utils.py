import MetaTrader5 as mt5

def calculate_dynamic_lot(
    gateway,
    symbol: str,
    risk_percent: float,
    sl_dist_price: float,
    max_lot_demo_cap: float = None
) -> float:
    """
    Calculates dynamic lot size based on equity risk percentage.
    Incorporates max_lot_demo_cap safety guard.
    """
    if sl_dist_price <= 0:
        sym = gateway.symbol_info(symbol)
        return sym.volume_min if sym else 0.01

    acc = gateway.account_info()
    sym = gateway.symbol_info(symbol)
    
    if acc is None or sym is None:
        return 0.01

    risk_money = acc.equity * (risk_percent / 100.0)
    sl_ticks = sl_dist_price / sym.trade_tick_size
    
    # Protect against divide-by-zero if tick size is anomalous
    if sl_ticks <= 0:
        return sym.volume_min
        
    dollar_per_lot = sl_ticks * sym.trade_tick_value

    if dollar_per_lot <= 0:
        return sym.volume_min

    lot = risk_money / dollar_per_lot
    lot = max(sym.volume_min, min(lot, sym.volume_max))

    if max_lot_demo_cap is not None:
        lot = min(lot, max_lot_demo_cap)
        
    # Ensure capping didn't push us below volume_min again
    lot = max(sym.volume_min, lot)

    # Precise rounding to volume step
    result = round(lot / sym.volume_step) * sym.volume_step
    step_str = f"{sym.volume_step:.10f}".rstrip("0")
    decimals = len(step_str.split(".")[1]) if "." in step_str else 0
    return round(result, decimals)

from datetime import datetime

def is_session_active(session_gate_enabled: bool, blocked_hours_utc: tuple = ()) -> bool:
    if not session_gate_enabled:
        return True
    if not blocked_hours_utc:
        return True
    hour = datetime.utcnow().hour
    return hour not in blocked_hours_utc
