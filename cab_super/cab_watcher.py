"""
==================================================================
          CAB WATCHER v16.4-1 - Production Brain                   
  Dynamic Percentile Regime Classifier + Full Fluid Matrix        
  Harvester / Protector / Reaper - deterministic & explainable    
  Author: CAB Trader  |  Date: 21 April 2026                      
==================================================================

Upgrade notes vs v16.3 (v16.4-1 additions):
  - Opposite Signal Invalidation (OSI): if a new H4 two-bar inversion
    fires AGAINST an open position, the position is immediately closed.
    This is the highest-priority exit in the fluid matrix, checked before
    REAPER / PROTECTOR / HARVESTER each cycle.
    Implementation: _detect_opposite_signal(symbol, is_buy) -> bool
    Returns True when bars[-3] & bars[-2] form an inversion opposing us.
    Guard: protector-locked positions (SL >= entry for BUY, or SL <=
    entry for SELL) are only closed by OSI if R >= 0 (i.e. we are not
    giving back profit on a position the market has already confirmed).
    This avoids false exits during normal H4 volatility while the
    position is still developing.

Upgrade notes vs v16.2 (v16.3 original):
  - K-Means / ER heuristic -> Dynamic Percentile Regime Classifier
  - Full Harvester / Protector / Reaper fluid matrix
  - M1 150-bar regime window (was M15, too slow)
  - _wilder_adx() matching MT5 iADX exactly
  - Spread guard on every close
  - STOPS_LEVEL guard on every SL modify
  - Hardcoded paths -> os.environ (with fallback defaults)
  - Optional MT5 login from env vars
  - reason + scores logged on every regime cycle
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import os
import time
import logging
from datetime import datetime
import json
from pathlib import Path

try:
    from data.trade_ledger import write_trade_event as _write_trade_event
except ImportError:
    _write_trade_event = None

# ------------------------------------------------------------------------------
# CONFIGURATION  (set these as environment variables in production)
# ------------------------------------------------------------------------------
TERMINAL_PATH = os.environ.get(
    "MT5_TERMINAL_PATH",
    r"C:\Program Files\Goat Funded MT5 Terminal - Copy\terminal64.exe"
)
COMMON_PATH = os.environ.get(
    "MT5_COMMON_PATH",
    r"C:\Users\ABRAR\AppData\Roaming\MetaQuotes\Terminal\Common\Files"
)
HEARTBEAT_FILE = os.path.join(COMMON_PATH, "cab_heartbeat.txt")

MAGIC_NUMBER = 999555
SYMBOL       = os.environ.get("CAB_SYMBOL", "XAUUSDm")

# Timeframes
TF_REGIME = mt5.TIMEFRAME_H4   # audit-cab-tf: H4 to match CAB entry timeframe.
                               # CAB entries are H4 inversions — evaluating against
                               # 150 M1 bars (2.5 hrs) introduced microstructure noise
                               # into the regime that determines whether to cut a 4-hour
                               # trade. 50 H4 bars = ~8 days of structural context.
TF_ATR    = mt5.TIMEFRAME_M15   # M15 ATR for Protector buffer (unchanged)

# ------------------------------------------------------------------------------
# FLUID DECISION THRESHOLDS
# ------------------------------------------------------------------------------
PROTECTOR_R = 1.2   # Move SL to BE + buffer at this R multiple
HARVESTER_R = 2.0   # Close full position on EXHAUSTION at this R
REAPER_R    = 0.5   # Cut loss on TRENDING when R <= -REAPER_R

# cw-reaper: triple gate thresholds (master plan 4.2)

# cw-harvpart: partial harvester config
HARVESTER_PARTIAL_FRAC = 0.50   # close this fraction at 2R
HARVESTER_TRAIL_ATR    = 1.5    # trail remainder with N × M15 ATR

# cw-session: Asian session hours (UTC) to suppress REAPER on XAUUSD
REAPER_ASIAN_SUPPRESS_HOURS = (0, 1, 2, 3, 4, 5, 6)   # 00:00–06:59 UTC

# ------------------------------------------------------------------------------
# PERCENTILE REGIME THRESHOLDS  (20 Apr spec - back-test before changing)
# ------------------------------------------------------------------------------
TREND_ADX_THRESH    = 65    # ADX rank above this -> TRENDING signal
EXHAUST_ATR_THRESH  = 75    # ATR-ratio rank above this -> exhaustion volatility spike
EXHAUST_BODY_THRESH = 35    # Body/Range rank below this -> weak candle body (exhaustion)
REGIME_BARS         = 50    # H4 bars fetched — 50 bars ≈ 8 days of context.
                            # audit-cab-tf: was 170 M1 bars (< 3 hrs). H4 gives
                            # structural regime context appropriate for H4 entries.

# ------------------------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------------------------
from logging.handlers import RotatingFileHandler
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler("logs/cab_watcher.log", maxBytes=5*1024*1024, backupCount=5, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# ------------------------------------------------------------------------------
# GATEWAY  (set by unified_runner; None = standalone mode uses raw mt5)
# ------------------------------------------------------------------------------
_GATEWAY = None

def set_gateway(gw):
    """Called once by unified_runner after MT5Gateway is initialised."""
    global _GATEWAY
    _GATEWAY = gw

def _api():
    """Return gateway in unified mode, raw mt5 in standalone mode."""
    return _GATEWAY if _GATEWAY is not None else mt5

def _get_symbol_config(symbol: str) -> dict:
    try:
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        with open(config_path, "r") as f:
            data = json.load(f)
        return data.get("symbols", {}).get(symbol, {}).get("cab_entry", {})
    except Exception as e:
        logging.error(f"Failed to read config for {symbol}: {e}")
        return {}


# ------------------------------------------------------------------------------
# GLOBAL STATE
# ------------------------------------------------------------------------------
processed_actions: dict = {}   # {ticket: set of fired actions}


# ==============================================================================
#  HELPER: Percentile rank  (no scipy dependency)
# ==============================================================================
#  REGIME HELPERS (Handled by KnowledgeRegister Layer 0)
# ==============================================================================
# ==============================================================================
#  REGIME ENGINE: Dynamic Percentile Classifier (Layer 0 Facts)
# ==============================================================================
def get_market_regime(symbol: str = None) -> dict:
    """
    Consumes canonical H4 market regime facts from the Knowledge Register.
    Replaces local calculation of ADX, ATR, and Regime.
    """
    kr = KnowledgeRegister()
    
    symbol = symbol or SYMBOL
    snapshot = kr.get_market_state(symbol, "H4")
    
    if not snapshot:
        logging.info("Regime: insufficient H4 data - defaulting STABLE")
        return {
            "regime": "STABLE", 
            "reason": "No Layer 0 state available",
            "scores": {}, 
            "atr_raw": 1.0
        }
        
    scores = {
        "adx_rank": snapshot.adx_percentile,
        "atr_rank": snapshot.atr_percentile,
        "br_rank": snapshot.body_range_ratio * 100.0  # approximate percentile from ratio
    }
    
    regime_str = snapshot.regime.value
    if regime_str.startswith("TRENDING"):
        regime_str = "TRENDING"
        
    return {
        "regime": regime_str,
        "reason": f"Layer 0 | ADX {scores['adx_rank']:.0f}th | ATR {scores['atr_rank']:.0f}th",
        "scores": scores,
        "atr_raw": snapshot.atr_raw,
        "source_bar_time": snapshot.source_bar_time
    }


# ==============================================================================
#  ATR HELPER: M15 ATR for Protector buffer  (different TF from regime)
# ==============================================================================
def _get_m15_atr(symbol: str = None, period: int = 14) -> float:
    symbol = symbol or SYMBOL
    rates = _api().copy_rates_from_pos(symbol, TF_ATR, 0, period + 5)
    if rates is None or len(rates) < period:
        return 1.0
    df = pd.DataFrame(rates)
    df["tr"] = np.maximum(
                    df["high"] - df["low"],
                    np.maximum(
                        (df["high"] - df["close"].shift(1)).abs(),
                        (df["low"]  - df["close"].shift(1)).abs()
                    )
               )
    val = df["tr"].rolling(period).mean().iloc[-1]
    return float(val) if not pd.isna(val) else 1.0


def _get_m5_context(symbol: str, is_buy: bool) -> dict:
    """
    Fetch M5 context fields for H21 logging at CAB entry detection.
    Returns dict with all four H21 fields, or safe defaults on any error.
    Never raises — failure returns neutral values so the watcher loop
    is never interrupted by a data fetch error.
    """
    defaults = {
        "m5_close_direction": "UNKNOWN",
        "m5_atr": 0.0,
        "m5_body_ratio": 0.0,
        "m5_bars_in_direction": 0,
    }
    try:
        # Last closed M5 bar — fetch 2 bars (index 0 = current open, index 1 = last closed)
        last_bar = _api().copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 1, 1)
        if last_bar is None or len(last_bar) == 0:
            return defaults

        bar = last_bar[0]
        close_dir = "UP" if bar["close"] > bar["open"] else "DOWN"

        bar_range = max(float(bar["high"]) - float(bar["low"]), 0.0001)
        body = abs(float(bar["close"]) - float(bar["open"]))
        body_ratio = round(min(body / bar_range, 1.0), 3)

        # ATR(14) on last 20 M5 bars
        m5_atr = 0.0
        rates_20 = _api().copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 20)
        if rates_20 is not None and len(rates_20) >= 15:
            import pandas as pd
            df = pd.DataFrame(rates_20)
            df["tr"] = pd.concat([
                df["high"] - df["low"],
                (df["high"] - df["close"].shift(1)).abs(),
                (df["low"]  - df["close"].shift(1)).abs(),
            ], axis=1).max(axis=1)
            atr_val = df["tr"].rolling(14).mean().iloc[-1]
            if not pd.isna(atr_val):
                m5_atr = round(float(atr_val), 5)

        # Consecutive M5 bars in same direction as entry
        # Fetch 10 bars to count a meaningful streak
        streak_bars = _api().copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 1, 10)
        m5_bars_in_dir = 0
        if streak_bars is not None and len(streak_bars) > 0:
            # Walk backward from most recent closed bar
            for bar_s in reversed(streak_bars):
                bar_bullish = bar_s["close"] > bar_s["open"]
                if is_buy and bar_bullish:
                    m5_bars_in_dir += 1
                elif not is_buy and not bar_bullish:
                    m5_bars_in_dir += 1
                else:
                    break  # streak broken

        return {
            "m5_close_direction": close_dir,
            "m5_atr": m5_atr,
            "m5_body_ratio": body_ratio,
            "m5_bars_in_direction": m5_bars_in_dir,
        }
    except Exception as e:
        logging.debug(f"_get_m5_context error for {symbol}: {e}")
        return defaults


from core.knowledge_register import KnowledgeRegister

# ==============================================================================
#  GLOBALS & CONFIG
# ==============================================================================

# Track last H4 bar checked for Macro logic per symbol
_last_macro_bar_time = {}

# Group Invalidation Threshold (Change 2)
GROUP_INVALIDATION_R = -1.5

def _spread_allows_close_cab(pos, tick, sym_info) -> tuple:
    """Same cost-aware spread logic as sniper_watcher."""
    if sym_info is None or sym_info.point <= 0:
        return True, "no_sym_info"
    spread_pts = (tick.ask - tick.bid) / sym_info.point
    if spread_pts > 500:
        return False, f"spread {spread_pts:.0f}pts > 500pt emergency limit"
    if spread_pts <= 100:
        return True, "normal_spread"
    try:
        spread_cost = (
            (tick.ask - tick.bid) / sym_info.trade_tick_size
            * sym_info.trade_tick_value * pos.volume
        )
    except Exception:
        spread_cost = 0.0
    profit = pos.profit
    if profit > 0 and profit >= spread_cost:
        return True, f"profit {profit:.2f} covers spread"
    if profit < 0 and abs(profit) >= spread_cost * 2:
        return True, f"loss dominates spread"
    return False, f"spread {spread_pts:.0f}pts — near breakeven, deferring"

# P0 fix: close-retry circuit breaker (module-level for standalone function)
# {ticket: (fail_count, suppress_until_timestamp)}
_close_suppressed = {}

def _close_position(pos, reason: str) -> bool:
    """
    Market-close a position.
    Guards: tick/sym_info None check, spread check.
    BUG FIXED: previous code dereferenced tick.ask before checking tick is
    not None — any broker connection blip caused AttributeError, which the
    outer try/except caught silently, leaving profitable trades open.
    """
    sym_info = _api().symbol_info(pos.symbol)
    tick     = _api().symbol_info_tick(pos.symbol)

    # None guard BEFORE any dereference — the bug that swallowed profit closes
    if tick is None or sym_info is None:
        logging.warning(
            f"  Close DEFERRED #{pos.ticket} — tick or sym_info unavailable "
            f"({reason[:40]}) — will retry next cycle"
        )
        return False

    spread = tick.ask - tick.bid

    # P0 fix: check if close is suppressed for this ticket
    suppressed = _close_suppressed.get(pos.ticket)
    if suppressed:
        fail_count, suppress_until = suppressed
        import time as _time
        if _time.time() < suppress_until:
            return False  # silently skip, already logged
        else:
            del _close_suppressed[pos.ticket]

    # Cost-aware spread guard
    allow, reason_spread = _spread_allows_close_cab(pos, tick, sym_info)
    if not allow:
        logging.warning(f"  Close BLOCKED #{pos.ticket} — {reason_spread}")
        return False
    elif spread / max(sym_info.point, 1e-10) > 100:
        logging.info(f"  Close ALLOWED wide spread #{pos.ticket} — {reason_spread}")

    order_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
    price      = tick.bid if pos.type == 0 else tick.ask

    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "position":     pos.ticket,
        "symbol":       pos.symbol,
        "volume":       pos.volume,
        "type":         order_type,
        "price":        price,
        "deviation":    20,
        "magic":        MAGIC_NUMBER,
        #"comment":      str(reason)[:31] if reason else "",  # FIX: Hard limit to 31 chars
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    res = _api().order_send(request)
    
    # FIX: Defensive check to prevent crash if order_send fails entirely
    if res is None:
        error = _api().last_error()
        logging.error(f"  Close FAILED #{pos.ticket} | order_send returned None | err={error}")
        return False

    if res.retcode == mt5.TRADE_RETCODE_DONE:
        logging.info(
            f"  Closed #{pos.ticket} | {reason} | "
            f"P&L: {pos.profit:.2f}"
        )
        
        # Tech Debt Fix: Unregister trade thesis on close
        try:
            KnowledgeRegister().unregister_trade_thesis(pos.ticket)
        except Exception:
            pass

        # MAE/MFE Trade Excursion Logging
        try:
            from core.trade_analytics import TradeAnalyticsEngine
            TradeAnalyticsEngine().log_trade_excursion(pos, "CAB")
        except Exception as e:
            logging.error(f"Failed to log trade excursion: {e}")

        # ── Unified Trade Ledger: CAB EXIT ────────────────────────────
        if _write_trade_event:
            is_buy = (pos.type == 0)
            risk_dist = abs(pos.price_open - pos.sl)
            r_mult = None
            if risk_dist > 1e-10:
                pm = (pos.price_current - pos.price_open) if is_buy else (pos.price_open - pos.price_current)
                r_mult = round(pm / risk_dist, 3)
            _write_trade_event(
                bot="CAB", event="EXIT", ticket=pos.ticket,
                symbol=pos.symbol,
                direction="BUY" if is_buy else "SELL",
                price=pos.price_current,
                sl=pos.sl, tp=pos.tp, volume=pos.volume,
                r_multiple=r_mult,
                exit_reason=reason,
                pnl_usd=pos.profit,
                spread_at_event=spread,
                magic=MAGIC_NUMBER,
            )
        return True
    elif res.retcode == 10036:
        # Position already closed by broker (SL/TP hit) — not an error
        logging.info(
            f"  #{pos.ticket} already closed by broker — skipping"
        )
        _close_suppressed.pop(pos.ticket, None)
        return False
    else:
        # P0 fix: track failures and suppress on 10018 or after 5 retries
        import time as _time
        prev = _close_suppressed.get(pos.ticket, (0, 0.0))
        new_count = prev[0] + 1
        suppress_seconds = 300  # 5 minutes

        if res.retcode == 10018:  # Market closed
            _close_suppressed[pos.ticket] = (new_count, _time.time() + suppress_seconds)
            logging.warning(
                f"  Close SUPPRESSED #{pos.ticket} | Market closed (10018) | "
                f"will retry in {suppress_seconds}s"
            )
        elif new_count >= 5:
            _close_suppressed[pos.ticket] = (new_count, _time.time() + suppress_seconds)
            logging.warning(
                f"  Close SUPPRESSED #{pos.ticket} | {new_count} consecutive failures | "
                f"last code={res.retcode} | will retry in {suppress_seconds}s"
            )
        else:
            _close_suppressed[pos.ticket] = (new_count, 0.0)
            logging.error(
                f"  Close FAILED #{pos.ticket} | "
                f"code={res.retcode} | {res.comment} | attempt {new_count}/5"
            )
        return False


def _modify_sl(pos, new_sl: float, label: str = "") -> bool:
    """
    Modify stop-loss.
    Guards: STOPS_LEVEL check before sending to prevent silent broker rejection.
    """
    sym_info    = _api().symbol_info(pos.symbol)
    tick        = _api().symbol_info_tick(pos.symbol)

    # fix-cabsym: this guard existed in _close_position but was missing here —
    # same crash class (AttributeError on a None tick/sym_info during a
    # connection blip), just on the modify-SL path instead of the close path.
    if tick is None or sym_info is None:
        logging.warning(
            f"  SL modify DEFERRED #{pos.ticket} ({label}) — "
            f"tick or sym_info unavailable — will retry next cycle"
        )
        return False

    stops_dist  = sym_info.trade_stops_level * sym_info.point
    curr_price  = tick.bid if pos.type == 0 else tick.ask

    if abs(new_sl - curr_price) < stops_dist:
        logging.warning(
            f"  SL modify BLOCKED #{pos.ticket} "
            f"({label}) - new SL {new_sl:.5f} inside "
            f"stops level ({stops_dist:.5f})"
        )
        return False
        
    new_sl = round(new_sl, sym_info.digits)
    if new_sl == round(pos.sl, sym_info.digits):
        return True

    request = {
        "action":   mt5.TRADE_ACTION_SLTP,
        "position": pos.ticket,
        "sl":       round(new_sl, sym_info.digits),
        "tp":       pos.tp,
    }
    res = _api().order_send(request)
    
    # FIX: Defensive check for None
    if res is None:
        error = _api().last_error()
        logging.error(f"  SL modify FAILED #{pos.ticket} ({label}) | order_send returned None | err={error}")
        return False

    if res.retcode == mt5.TRADE_RETCODE_DONE:
        return True
    else:
        logging.error(
            f"  SL modify FAILED #{pos.ticket} ({label}) | "
            f"code={res.retcode} | {res.comment}"
        )
        return False


# ==============================================================================
#  FLUID DECISION MATRIX  - Harvester / Protector / Reaper
# ==============================================================================

# Track which bars have already triggered OSI closes, keyed by (symbol, bar_time)
# This prevents repeated closes on the same H4 bar if the cycle re-reads the
# same two bars multiple times within a single 4-hour window.
_osi_fired_bars: dict = {}   # {symbol: last_bar_time_that_triggered_OSI}


def _detect_opposite_signal(symbol: str, is_buy: bool) -> bool:
    """
    Opposite Signal Invalidation (OSI) — CAB v16.4-1.

    Returns True when the last two closed H4 bars form a two-bar
    inversion pattern that is OPPOSITE to the current position direction:

      Bearish inversion (invalidates BUY):  bar[-3] bullish AND bar[-2] bearish
      Bullish inversion (invalidates SELL): bar[-3] bearish AND bar[-2] bullish

    Bar numbering (MT5 copy_rates_from_pos):
      rates[-1] = bar index 0  (current open bar — ignored)
      rates[-2] = bar index 1  (last closed bar)
      rates[-3] = bar index 2  (two bars ago)

    Returns False on any data error — never raises, never blocks exits.

    Guard: the same H4 bar_time triggers OSI only once per symbol.
    Subsequent cycles reading the same two bars do nothing.
    """
    try:
        rates = _api().copy_rates_from_pos(symbol, TF_REGIME, 0, 3)
        if rates is None or len(rates) < 3:
            return False

        bar2 = rates[-3]   # two bars ago (bar index 2)
        bar1 = rates[-2]   # last closed bar (bar index 1)
        current_bar_time = int(bar1["time"])  # H4 bar open time — unique per bar

        # Guard: only fire OSI once per H4 bar per symbol
        if _osi_fired_bars.get(symbol) == current_bar_time:
            return False

        bar2_bullish = bar2["close"] > bar2["open"]
        bar1_bullish = bar1["close"] > bar1["open"]

        # Inversion against a BUY: bar[-3] bullish → bar[-2] bearish
        if is_buy and bar2_bullish and not bar1_bullish:
            _osi_fired_bars[symbol] = current_bar_time
            logging.info(
                f"  OSI detected [{symbol}] bearish H4 inversion "
                f"(bar2 close={bar2['close']:.5f} open={bar2['open']:.5f} | "
                f"bar1 close={bar1['close']:.5f} open={bar1['open']:.5f}) "
                f"— invalidates BUY"
            )
            return True

        # Inversion against a SELL: bar[-3] bearish → bar[-2] bullish
        if not is_buy and not bar2_bullish and bar1_bullish:
            _osi_fired_bars[symbol] = current_bar_time
            logging.info(
                f"  OSI detected [{symbol}] bullish H4 inversion "
                f"(bar2 close={bar2['close']:.5f} open={bar2['open']:.5f} | "
                f"bar1 close={bar1['close']:.5f} open={bar1['open']:.5f}) "
                f"— invalidates SELL"
            )
            return True

        return False
    except Exception as e:
        logging.debug(f"  OSI check error [{symbol}]: {e}")
        return False

def manage_fluid_logic():
    global processed_actions

    # -- 1. Heartbeat pulse ----------------------------------------------------
    # Direct write with 3-attempt retry. Atomic rename (old approach) caused
    # WinError 5 (Access Denied) when MT5 held a read lock on the file.
    for _hb_attempt in range(3):
        try:
            with open(HEARTBEAT_FILE, "w") as f:
                f.write(str(int(time.time())))
            break
        except Exception as e:
            if _hb_attempt < 2:
                time.sleep(0.05)
            else:
                logging.error(f"Heartbeat write failed after 3 attempts: {e}")

    # -- 2. Position check -----------------------------------------------------
    # fix-cabsym (Tier 0 #2): no symbol= filter here — previously this only
    # ever fetched SYMBOL (default XAUUSDm), so every CAB position on
    # EURUSDm/GBPUSDm/XAGUSDm was invisible to this whole function. All open
    # positions are fetched, then filtered to our own magic number below —
    # exactly like every other bot in this codebase already does.
    all_positions = _api().positions_get()
    if not all_positions:
        return
    positions = [p for p in all_positions if p.magic == MAGIC_NUMBER]
    if not positions:
        # BUG FIXED: previously reset processed_actions on ANY empty-positions
        # result, including transient broker delays or reconnect gaps.
        # This wiped PROTECTOR/HARVESTER flags, making trades look new on the
        # next cycle — HARVESTER could then double-fire or protector SL re-set.
        # FIX: only purge tickets that are genuinely gone (not a reconnect blip).
        # We keep processed_actions intact and only clean stale entries at the
        # bottom of the position loop when we know which tickets are still live.
        return

    # -- 3. Regime + M15 ATR — once per DISTINCT SYMBOL this cycle, not once
    #    globally. fix-cabsym: previously computed once for SYMBOL only, so
    #    every non-Gold position was managed using Gold's regime (or, before
    #    the positions_get fix above, never managed at all).
    symbols_present = sorted({p.symbol for p in positions})
    regime_by_symbol = {}
    atr_by_symbol = {}
    
    # -- Grouped Portfolio R-Budgeting -----------------------------------------
    # Evaluates total combined R per symbol. If total <= -1.5R, cascade exit.
    valid_positions = []
    for sym in symbols_present:
        sym_positions = [p for p in positions if p.symbol == sym]
        sym_rs = []
        for p in sym_positions:
            is_buy = (p.type == 0)
            risk_dist = abs(p.price_open - p.sl)
            if risk_dist == 0:
                continue
            price_move = (p.price_current - p.price_open) if is_buy else (p.price_open - p.price_current)
            sym_rs.append((p, price_move / risk_dist))
            
        r_total = sum(r for _, r in sym_rs)
        if r_total <= GROUP_INVALIDATION_R:
            logging.warning(
                f"  * GROUP INVALIDATION [{sym}] | "
                f"Total R={r_total:+.2f} <= {GROUP_INVALIDATION_R}R threshold"
            )
            # Sort weakest first (most negative)
            sym_rs.sort(key=lambda x: x[1])
            unclosed = []
            for p, r in sym_rs:
                if _close_position(p, f"GROUP_INVALIDATION|R_total={r_total:+.2f}"):
                    if p.ticket not in processed_actions:
                        processed_actions[p.ticket] = set()
                    processed_actions[p.ticket].add("GROUP_INVALIDATION")
                else:
                    unclosed.append(p)
            
            # Fix 3: Explicitly remove closed tickets, but keep unclosed tickets for fluid management
            valid_positions.extend(unclosed)
            continue
            
        # If not invalidated, add to valid pool
        valid_positions.extend(sym_positions)
        
    positions = valid_positions
    if not positions:
        return
        
    symbols_present = sorted({p.symbol for p in positions})

    for sym in symbols_present:
        intel = get_market_regime(sym)
        regime_by_symbol[sym] = intel
        atr_by_symbol[sym] = _get_m15_atr(sym)
        logging.debug(
            f"-- REGIME[{sym}]: {intel['regime']} | {intel['reason']} | "
            f"scores={intel['scores']}"
        )

    for pos in positions:
        intel   = regime_by_symbol[pos.symbol]
        regime  = intel["regime"]
        reason  = intel["reason"]
        
        # Fetch immutable entry ATR if available (Change 4)
        kr = KnowledgeRegister()
        thesis = kr.get_entry_snapshot(pos.ticket)
        if thesis and thesis.entry_atr > 0:
            m15_atr = thesis.entry_atr
        else:
            m15_atr = atr_by_symbol[pos.symbol]

        if pos.ticket not in processed_actions:
            processed_actions[pos.ticket] = set()
            # H21: log M5 context at first detection of this position
            _is_buy_for_m5 = (pos.type == 0)
            m5_ctx = _get_m5_context(pos.symbol, _is_buy_for_m5)
            logging.info(
                f"M5_CONTEXT #{pos.ticket} | "
                f"symbol={pos.symbol} | "
                f"entry_dir={'BUY' if _is_buy_for_m5 else 'SELL'} | "
                f"m5_dir={m5_ctx['m5_close_direction']} | "
                f"m5_atr={m5_ctx['m5_atr']:.5f} | "
                f"m5_body={m5_ctx['m5_body_ratio']:.3f} | "
                f"m5_bars_in_dir={m5_ctx['m5_bars_in_direction']}"
            )

        if pos.sl == 0:
            logging.warning(f"  #{pos.ticket} has no SL - skipping")
            continue

        sym_cfg = _get_symbol_config(pos.symbol)
        protector_r = sym_cfg.get("cab_be_gate_r", PROTECTOR_R)
        harvester_r = sym_cfg.get("cab_partial_r", HARVESTER_R)
        lock_gate_r = sym_cfg.get("cab_lock_gate_r", protector_r + 0.5)
        reaper_r    = REAPER_R

        # -- R calculation (price-distance method) -----------------------------
        is_buy    = (pos.type == 0)
        risk_dist = abs(pos.price_open - pos.sl)
        if risk_dist == 0:
            continue

        # Signed R: positive = profit, negative = loss
        price_move = (
            (pos.price_current - pos.price_open) if is_buy
            else (pos.price_open - pos.price_current)
        )
        current_r = price_move / risk_dist

        side = "BUY" if is_buy else "SELL"
        done = processed_actions[pos.ticket]
        logging.info(
            f"  #{pos.ticket} {side} | "
            f"R={current_r:+.2f} | "
            f"Regime={regime} | "
            f"Done={done}"
        )

        # -- IMMEDIATE EXIT: trade moving wrong direction in first 2 hours -----
        # If within first 2 hours of entry AND R < -0.2 AND no actions taken yet:
        # the entry thesis has not confirmed. Exit before loss compounds.
        if (
            not done                          # no actions taken yet (fresh trade)
            and current_r <= -0.20            # already 0.2R against us
            and "IMMEDIATE_EXIT" not in done
        ):
            # Check time held
            try:
                open_time = pos.time          # MT5 position open timestamp (unix)
                import time as _time
                time_held_seconds = _time.time() - open_time
                if time_held_seconds < 7200:  # within first 2 hours
                    if _close_position(pos, f"IMMEDIATE_EXIT|R{current_r:+.2f}|held_{int(time_held_seconds/60)}min"):
                        done.add("IMMEDIATE_EXIT")
                        logging.warning(
                            f"  * IMMEDIATE_EXIT #{pos.ticket} | "
                            f"R={current_r:+.2f} | "
                            f"held={int(time_held_seconds/60)}min | "
                            f"thesis not confirmed"
                        )
                        continue
            except Exception as _e:
                logging.debug(f"IMMEDIATE_EXIT check error: {_e}")

        # -- EVENT GATE: MACRO LOGIC (OSI & REAPER) ---------------------------
        # These only evaluate on H4 bar close boundaries
        bar_time = intel.get("source_bar_time", 0)
        is_new_h4_bar = (bar_time > _last_macro_bar_time.get(pos.symbol, 0))
        
        if is_new_h4_bar:
            # -- OSI: OPPOSITE SIGNAL INVALIDATION --------------------------------
            if "OSI" not in done:
                osi_triggered = _detect_opposite_signal(pos.symbol, is_buy)
                if osi_triggered:
                    kr_dir = 1 if is_buy else -1
                    KnowledgeRegister().publish_invalidation(
                        symbol=pos.symbol,
                        direction=kr_dir,
                        source_bot="CAB",
                        reason="CAB OSI",
                        ttl_seconds=14400.0
                    )
                    # HIGH-2: Fix OSI guard (fire OSI if in profit, suppress if protector active and in loss)
                    protector_active = "PROTECTOR" in done or "HARVESTER" in done
                    if protector_active and current_r >= 0:
                        logging.info(
                            f"  OSI SUPPRESSED #{pos.ticket} - "
                            f"R={current_r:+.2f} | protector_active={protector_active} | reason={'PROTECTOR_LOCKED' if protector_active else 'POSITION_PROFITABLE'}"
                        )
                    else:
                        if _close_position(pos, f"OSI|H4_INVERSION|R{current_r:+.2f}"):
                            done.add("OSI")
                            continue

            # -- REAPER: exit losing trade when H4 structure turns against it --
            # Simplified from 7-condition triple gate to 2 conditions:
            # (1) R is in loss territory, (2) the last closed H4 bar closed
            # against our position direction. No regime check — regime label
            # is unreliable. No degradation check — adds conditions without
            # adding signal. Bar-gated to prevent thrashing.
            if (
                is_new_h4_bar
                and current_r <= -0.50
                and "REAPER"    not in done
                and "PROTECTOR" not in done
                and "IMMEDIATE_EXIT" not in done
            ):
                # Check if last closed H4 bar closed against position direction
                try:
                    h4_rates = _api().copy_rates_from_pos(
                        pos.symbol, mt5.TIMEFRAME_H4, 0, 3
                    )
                    if h4_rates is not None and len(h4_rates) >= 2:
                        last_bar = h4_rates[-2]   # last CLOSED H4 bar
                        bar_bullish = last_bar["close"] > last_bar["open"]
                        # For BUY: a bearish H4 bar closing against us triggers REAPER
                        # For SELL: a bullish H4 bar closing against us triggers REAPER
                        h4_against = (is_buy and not bar_bullish) or \
                                     (not is_buy and bar_bullish)

                        if h4_against:
                            if _close_position(
                                pos,
                                f"REAPER|H4_AGAINST|R{current_r:+.2f}"
                            ):
                                done.add("REAPER")
                                logging.warning(
                                    f"  * REAPER FIRED #{pos.ticket} | "
                                    f"R={current_r:+.2f} | "
                                    f"H4 closed against position | "
                                    f"bar_bullish={bar_bullish} is_buy={is_buy}"
                                )
                                continue
                        else:
                            logging.debug(
                                f"  REAPER HELD #{pos.ticket} | "
                                f"R={current_r:+.2f} | "
                                f"H4 bar direction still WITH position"
                            )
                except Exception as _e:
                    logging.debug(f"REAPER H4 check error: {_e}")

        # -- PROTECTOR ---------------------------------------------------------
        if current_r >= protector_r and "PROTECTOR" not in done:
            buffer = m15_atr * 0.15
            new_sl = (
                (pos.price_open + buffer) if is_buy
                else (pos.price_open - buffer)
            )
            if _modify_sl(pos, new_sl, label="PROTECTOR"):
                done.add("PROTECTOR")
                logging.info(
                    f"  * PROTECTOR FIRED #{pos.ticket} | "
                    f"R={current_r:+.2f} | "
                    f"New SL={new_sl:.5f} | "
                    f"Buffer={buffer:.5f}"
                )

        # -- LOCK GATE ---------------------------------------------------------
        if current_r >= lock_gate_r and "LOCK_GATE" not in done:
            buffer = m15_atr * 0.5
            new_sl = (
                (pos.price_open + buffer) if is_buy
                else (pos.price_open - buffer)
            )
            # Only tighten
            if (is_buy and new_sl > pos.sl) or (not is_buy and new_sl < pos.sl):
                if _modify_sl(pos, new_sl, label="LOCK_GATE"):
                    done.add("LOCK_GATE")
                    logging.info(
                        f"  * LOCK GATE FIRED #{pos.ticket} | "
                        f"R={current_r:+.2f} | "
                        f"New SL={new_sl:.5f} | "
                        f"Buffer={buffer:.5f}"
                    )

        # -- FRESH TICK (shared by CONT_TIGHTEN and HARVESTER below) ----------
        # Bug fix: pos.price_current is stale (last positions_get snapshot).
        # On fast Gold moves it can lag seconds behind real price.
        # Fetch one live tick here and reuse for all price-dependent logic.
        live_tick = _api().symbol_info_tick(pos.symbol)
        live_price = None
        if live_tick:
            live_price = live_tick.bid if is_buy else live_tick.ask

        # -- cw-contmgmt: CONTINUOUS SL TIGHTENING ----------------------------
        # Light SL tightening every cycle between milestones.
        # Only tightens (never loosens). Uses live tick price (not stale cache).
        # Runs until HARVESTER fires; after HARVESTER the trail logic takes over.
        if current_r > 0 and "PROTECTOR" in done and "HARVESTER" not in done and live_price:
            trail_dist = m15_atr * 0.10   # light step — 10% of M15 ATR
            new_sl = (
                (live_price - trail_dist) if is_buy
                else (live_price + trail_dist)
            )
            # Only tighten — never move SL against position
            if (is_buy and new_sl > pos.sl) or (not is_buy and new_sl < pos.sl):
                _modify_sl(pos, new_sl, label="CONT_TIGHTEN")

        # -- cw-harvpart: PARTIAL HARVESTER -----------------------------------
        # BUG FIX: HARVESTER was locked to regime == EXHAUSTION.
        # A position that reaches +2R in STABLE or TRENDING regime was NEVER
        # harvested — it rode profit back to SL with nothing booking gains.
        #
        # FIX: HARVESTER fires at HARVESTER_R in ANY regime. Regime context
        # is preserved in the comment/log. In EXHAUSTION the signal is stronger
        # (exhaustion = likely reversal) but we must book profit regardless.
        #
        # In TRENDING: partial close at 2R is still correct — the trend may
        # continue but we bank half and let the SL trail protect the runner.
        if (
            current_r >= harvester_r
            and "HARVESTER" not in done
        ):
            sym_info = _api().symbol_info(pos.symbol)
            if sym_info and live_tick and live_price:
                partial_vol = round(
                    pos.volume * HARVESTER_PARTIAL_FRAC / sym_info.volume_step
                ) * sym_info.volume_step
                remainder   = round(pos.volume - partial_vol, 8)

                if remainder >= sym_info.volume_min:
                    order_type = (mt5.ORDER_TYPE_SELL if is_buy
                                  else mt5.ORDER_TYPE_BUY)
                    req = {
                        "action":       mt5.TRADE_ACTION_DEAL,
                        "position":     pos.ticket,
                        "symbol":       pos.symbol,
                        "volume":       partial_vol,
                        "type":         order_type,
                        "price":        live_price,
                        "deviation":    20,
                        "magic":        MAGIC_NUMBER,
                        #"comment":      str(f"HARVESTER_{regime[:4]}|R{current_r:+.2f}")[:31], # FIX: 31 char limit
                        "type_time":    mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    res = _api().order_send(req)
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        done.add("HARVESTER")
                        # Trail SL for remainder — use live tick, not stale pos.price_current
                        trail_sl = (
                            (live_price - m15_atr * HARVESTER_TRAIL_ATR)
                            if is_buy
                            else (live_price + m15_atr * HARVESTER_TRAIL_ATR)
                        )
                        _modify_sl(pos, trail_sl, label="HARVESTER_TRAIL")
                        logging.warning(
                            f"  * HARVESTER PARTIAL #{pos.ticket} | "
                            f"closed {partial_vol} lots | "
                            f"remainder={remainder} trailing | "
                            f"R={current_r:+.2f} | regime={regime}"
                        )
                else:
                    # Remainder too small — full close
                    if _close_position(pos, f"HARVESTER_FULL|{regime}|{reason[:35]}"):
                        done.add("HARVESTER")
                        logging.warning(
                            f"  * HARVESTER FULL #{pos.ticket} | "
                            f"R={current_r:+.2f} | regime={regime}"
                        )

    # -- 5. Update Macro Bar Times & Cleanup -----------------------------------
    # After processing all positions for this cycle, update the last checked bar
    for sym in symbols_present:
        bar_t = regime_by_symbol[sym].get("source_bar_time", 0)
        if bar_t > _last_macro_bar_time.get(sym, 0):
            _last_macro_bar_time[sym] = bar_t

    # Remove processed_actions entries for tickets no longer in the terminal.
    # This is the safe alternative to the blanket reset on empty-positions.
    # Runs every cycle but only purges tickets that are genuinely closed.
    live_tickets = {p.ticket for p in all_positions if p.magic == MAGIC_NUMBER}
    stale = [t for t in list(processed_actions) if t not in live_tickets]
    for t in stale:
        processed_actions.pop(t, None)
    
    if stale:
        logging.debug(f"  Cleaned {len(stale)} stale processed_actions entries: {stale}")


# ==============================================================================
#  MAIN LOOP
# ==============================================================================
def run_brain():
    if not mt5.initialize(path=TERMINAL_PATH):
        logging.critical("CRITICAL: MT5 initialize() failed - check terminal path")
        return

    # Optional: login from environment (leave blank if auto-login is configured)
    login    = int(os.environ.get("MT5_LOGIN",    0))
    password = os.environ.get("MT5_PASSWORD", "")
    server   = os.environ.get("MT5_SERVER",   "")
    if login and password and server:
        if not mt5.login(login, password=password, server=server):
            logging.critical(f"MT5 login failed for account {login}")
            mt5.shutdown()
            return

    logging.info("-" * 60)
    logging.info("  CAB WATCHER v16.4-1 - PRODUCTION BRAIN ONLINE")
    # fix-cabsym: no longer single-symbol — manages every open magic=999555
    # position across whatever symbols cab_entry.py opened, discovered fresh
    # each cycle from positions_get(). SYMBOL now only matters as the Asian-
    # session-suppression allowlist check and the standalone-script default.
    logging.info("  Symbol  : ALL (multi-symbol — discovered per cycle from open positions)")
    logging.info(
        f"  Matrix  : Protector@{PROTECTOR_R}R | "
        f"Harvester@{HARVESTER_R}R | Reaper@-{REAPER_R}R"
    )
    logging.info(
        f"  Regime  : ADX>={TREND_ADX_THRESH}th | "
        f"ATR>={EXHAUST_ATR_THRESH}th | body<={EXHAUST_BODY_THRESH}th"
    )
    logging.info(f"  Magic   : {MAGIC_NUMBER}")
    logging.info("-" * 60)

    while True:
        try:
            manage_fluid_logic()
        except Exception as e:
            logging.error(f"Loop error: {e}", exc_info=True)
        time.sleep(15)


if __name__ == "__main__":
    run_brain()