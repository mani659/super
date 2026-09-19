import MetaTrader5 as mt5

# ── Per-symbol risk multipliers (fix-symbol-risk) ─────────────────────────────
# Applied to V2 sizing only. Deliberately NOT placed in config/config.json, because
# that file is shared with V1 (cab_super), which is frozen.
# XAGUSDm is the worst-performing symbol in every CAB variant that trades it:
#   cab_super CAB      -$4.03/trade  (worst of 11 symbols)
#   V2 CAB inversion   -$6.10/trade  (worst; -$347.85 total = 127% of CAB's net loss)
#   cab_multi_pair     -0.169R avg
#   V2 SuperTrend      -$10.86/trade (worst; -$65.15 over 6 trades)
# Halved pending a symbol-level review; restore to 1.0 only when an edge is shown.
SYMBOL_RISK_MULTIPLIERS = {
    "XAGUSDm": 0.5,
}

def symbol_risk_multiplier(symbol: str) -> float:
    """Risk multiplier for a symbol. 1.0 when unlisted."""
    return SYMBOL_RISK_MULTIPLIERS.get(symbol, 1.0)

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

    # fix-symbol-risk: per-symbol risk scaling (see SYMBOL_RISK_MULTIPLIERS).
    risk_money = acc.equity * (risk_percent * symbol_risk_multiplier(symbol) / 100.0)
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
