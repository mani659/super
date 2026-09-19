"""
CAB MASTER - LTF STRUCTURE RESEARCH (M15)
Pure-flag logging module. No order sends, no risk changes.
Returns three diagnostic flags on each call for research intake.
"""

import MetaTrader5 as mt5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_m15(symbol: str, bars: int = 50) -> list[dict] | None:
    """Load M15 closed+forming bars via copy_rates_from_pos.
    Returns list of bar dicts sorted oldest-first, or None on failure."""
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, bars)
    if rates is None or len(rates) < 25:
        return None
    return list(rates)


def _closed(bars: list[dict]) -> list[dict]:
    """Return only closed bars (exclude the current forming bar at index 0)."""
    return bars[1:]


# ---------------------------------------------------------------------------
# 1. liq_swept_prior  (0/1)
# ---------------------------------------------------------------------------

def liq_swept_prior(symbol: str, direction: str) -> int:
    """Was the nearest opposite-side swing level swept before signal time?

    For BUY  the opposite-side pool is the highest-high of bars 1..20.
    For SELL the opposite-side pool is the lowest-low  of bars 1..20.
    Swept = any later closed bar traded through that level.
    Returns 0 on insufficient data.
    """
    rates = _load_m15(symbol)
    if rates is None:
        return 0

    closed = _closed(rates)
    if len(closed) < 21:
        return 0

    # closed[0] is most recent; higher indices are older.
    # swing_window = closed[:20] → index 0 most recent, index 19 oldest.
    swing_window = closed[:20]

    if direction == "BUY":
        # opposite-side pool = highest high in the swing window
        pool_level = max(b["high"] for b in swing_window)
        pool_idx = next(i for i, b in enumerate(swing_window) if b["high"] == pool_level)
        # swept = any MORE RECENT bar (index < pool_idx) with high >= pool_level
        if pool_idx == 0:
            return 0  # swing is the most recent bar — nothing newer to sweep it
        for b in closed[0:pool_idx]:
            if b["high"] >= pool_level:
                return 1
    elif direction == "SELL":
        # opposite-side pool = lowest low in the swing window
        pool_level = min(b["low"] for b in swing_window)
        pool_idx = next(i for i, b in enumerate(swing_window) if b["low"] == pool_level)
        # swept = any MORE RECENT bar (index < pool_idx) with low <= pool_level
        if pool_idx == 0:
            return 0
        for b in closed[0:pool_idx]:
            if b["low"] <= pool_level:
                return 1

    return 0


# ---------------------------------------------------------------------------
# 2. fvg_with_signal  (0/1)
# ---------------------------------------------------------------------------

def fvg_with_signal(symbol: str, direction: str) -> int:
    """Is there an unfilled FVG in the signal direction on M15?

    Bullish FVG (BUY): bar[i].high < bar[i+2].low  (gap up).
    Bearish FVG (SELL): bar[i].low  > bar[i+2].high (gap down).
    Scan last 30 closed bars. Unfilled = current price has not fully
    traded through the gap.
    Returns 0 on insufficient data.
    """
    rates = _load_m15(symbol)
    if rates is None:
        return 0

    closed = _closed(rates)
    if len(closed) < 31:
        return 0

    # current price (from the forming bar, index 0 of full list)
    current_price = rates[0]["close"]

    # scan last 30 closed bars for 3-candle FVG
    scan = closed[:30]
    for i in range(len(scan) - 2):
        if direction == "BUY":
            # bullish FVG: gap between bar[i].high and bar[i+2].low
            if scan[i]["high"] < scan[i + 2]["low"]:
                # unfilled if current price hasn't dropped back into the gap
                if current_price > scan[i]["high"]:
                    return 1
        elif direction == "SELL":
            # bearish FVG: gap between bar[i].low and bar[i+2].high
            if scan[i]["low"] > scan[i + 2]["high"]:
                # unfilled if current price hasn't risen back into the gap
                if current_price < scan[i]["low"]:
                    return 1

    return 0


# ---------------------------------------------------------------------------
# 3. dist_next_pool_atr  (float, 0.0 if none)
# ---------------------------------------------------------------------------

def dist_next_pool_atr(symbol: str, direction: str) -> float:
    """Distance in M15-ATR units to the next same-direction swing pool.

    BUY  → next swing high above current close (nearest structural high).
    SELL → next swing low  below current close (nearest structural low).
    Distance = abs(pool - close) / ATR(14). Returns 0.0 if ATR<=0 or no pool.
    """
    rates = _load_m15(symbol)
    if rates is None:
        return 0.0

    closed = _closed(rates)
    if len(closed) < 21:
        return 0.0

    # current close from forming bar
    current_close = rates[0]["close"]

    # M15 ATR(14) — manual computation on closed bars
    trs = []
    for i in range(1, min(15, len(closed))):
        bar = closed[i]
        prev_close = closed[i - 1]["close"]
        tr = max(
            bar["high"] - bar["low"],
            abs(bar["high"] - prev_close),
            abs(bar["low"] - prev_close),
        )
        trs.append(tr)
    atr = sum(trs) / len(trs) if trs else 0.0
    if atr <= 0:
        return 0.0

    swing_window = closed[:20]

    if direction == "BUY":
        # next swing high above current close
        highs_above = [b["high"] for b in swing_window if b["high"] > current_close]
        if not highs_above:
            return 0.0
        pool = min(highs_above)  # nearest (smallest above)
    elif direction == "SELL":
        # next swing low below current close
        lows_below = [b["low"] for b in swing_window if b["low"] < current_close]
        if not lows_below:
            return 0.0
        pool = max(lows_below)  # nearest (largest below)
    else:
        return 0.0

    return abs(pool - current_close) / atr


# ---------------------------------------------------------------------------
# Public entry point — returns all three flags as a dict
# ---------------------------------------------------------------------------

def get_ltf_flags(symbol: str, direction: str) -> dict:
    """Compute all three LTF structure flags for a given symbol and direction.

    Returns:
        dict with keys: liq_swept_prior, fvg_with_signal,
                        dist_next_pool_atr, ltf_tf
    """
    return {
        "liq_swept_prior": liq_swept_prior(symbol, direction),
        "fvg_with_signal": fvg_with_signal(symbol, direction),
        "dist_next_pool_atr": dist_next_pool_atr(symbol, direction),
        "ltf_tf": "M15",
    }
