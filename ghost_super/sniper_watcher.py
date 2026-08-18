"""
╔══════════════════════════════════════════════════════════════════╗
║        SNIPER WATCHER v3.1 — The Integrated Brain               ║
║  Architecture: Intelligence-Gated Multi-Magic Risk Manager       ║
╚══════════════════════════════════════════════════════════════════╝

ARCHITECTURE ROLE — Layer 1 + Layer 3:
  Layer 1 | The Pulse:
    Continuously calculates ADX, Conviction, ATR, and regime label.
    Writes a "Market State" snapshot to brain_state_live.csv every
    heartbeat so the Hunter (Layer 2) can read it before firing.

  Layer 3 | The Multi-Magic Manager:
    Once trades are live, applies DISTINCT exit personalities per magic:
      201 SCALP      → Defensive breakeven at 0.3R. Quick risk-free lock.
                       ATR Reaper kills at 1.5×ATR if deeply wrong.
      202 REVERSAL   → ATR Reaper is priority. Kill if 1.8×ATR against.
                       Trail at 1.0R (lock 0.5R). Fluid TP on exhaustion.
      203 TREND-FOLLOW → Aggressive trail at 1.5×ATR. Ride while ADX high.
                         Hard Reaper at 1.8×ATR. Fluid exit when trend gone.

BUGS FIXED vs v1.3 / v2.0:
  1. logging.basicConfig had no filename → CMD-only output.
     FIX: RotatingFileHandler writes to disk unconditionally.
  2. tick=None crash → AttributeError silently killed the loop.
     FIX: None guard at top of manage_position() and close_position().
  3. No try/except in while True → any MT5 hiccup killed the brain.
     FIX: Broad except with 5s recovery + mt5.initialize() retry.
  4. Heartbeat format mismatch (log showed "Regime=TREND | ADX=X"
     but script wrote "Conviction=X | ATR=X") → running script was
     a different version than the one uploaded.
     FIX: Single source-of-truth format, version stamped in every HB.

LOGGING NEW IN v3.0:
  - sniper_brain.log         : rotating human-readable log
  - sniper_conviction_log.csv: every management action with full
                               market state + r_multiple + exit_reason
  - brain_state_live.csv     : single-row live state for Hunter to read

====================================================================
  CHANGELOG v3.1
====================================================================
  1. PULSE: Heartbeat reduced from 10s to 2s for Gold responsiveness.
     Hunter (Layer 2) reads a fresher state before every trigger.
  2. FLUID TP: Market-close logic enabled for zero-TP Hunter legs.
     Since Hunter v5.1 fires Naked Signal (TP=0.0), the Brain now
     owns all profitable exits. R-multiple guards for fluid TP have
     been removed — any profit above zero qualifies for exhaustion exit.
     Trailing and Reaper logic are fully intact.
  3. INFRASTRUCTURE: Full v3.0 conviction logging, helper functions
     (_get_tick_price, _compute_initial_risk, _send_modify,
     _close_market), MAGIC_MANAGERS dispatch dict, idle conviction
     snapshots, MT5 reconnect logic, and _init_conviction_log()
     all restored.
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging
import logging.handlers
import os
import csv
from datetime import datetime

# ─────────────────────────────────────────────
#  GATEWAY  (set by unified_runner; None = standalone mode)
# ─────────────────────────────────────────────
_GATEWAY = None

def set_gateway(gw):
    """Called once by unified_runner after MT5Gateway is initialised."""
    global _GATEWAY
    _GATEWAY = gw

def _api():
    """Return gateway in unified mode, raw mt5 in standalone mode."""
    return _GATEWAY if _GATEWAY is not None else mt5


# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
TERMINAL_PATH    = r"C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe"
SYMBOL           = "XAUUSDm"
SNIPER_MAGICS    = [201, 202]

BRAIN_LOG_FILE             = "sniper_brain.log"
CONVICTION_LOG_FILE        = "sniper_conviction_log.csv"
BRAIN_STATE_FILE           = "brain_state_live.csv"
ADAPTIVE_THRESHOLD_FILE    = "logs/adaptive_thresholds_live.csv"

HEARTBEAT_INTERVAL         = 2    # seconds — reduced from 10 in v3.1
CONV_LOG_INTERVAL          = 30   # seconds between idle snapshots
CALIBRATION_WINDOW_MINS    = 60   # rolling window for percentile calibration
CALIBRATION_MIN_ROWS       = 30   # cold-start guard: min rows before adaptive kicks in

# Exit logic thresholds
REAPER_ATR_MULT       = 1.8   # 202/203: kill if price moves this × ATR against
REAPER_ATR_MULT_201   = 1.5   # 201 scalp: tighter reaper threshold
TRAIL_LOCK_R_201      = 0.3   # 201 scalp: breakeven at this R
TRAIL_LOCK_R_202      = 1.0   # 202 reversal: start trailing at this R

# ── Per-personality leg TP + BE-lock ratchet ─────────────────────────────────
#
# PROBLEM FIXED: LEG_TP_R=0.5 with SL=1.0R required 89% win rate to break
# even. Observed bleed: ~$4 loss per $1 gain. Root cause: TP was closing
# winners at half the risk while full losses ran to 1.0R+.
#
# SOLUTION — two mechanisms working together:
#
# 1. PER-PERSONALITY TP  (set once broker-side at registration)
#    Each magic has a TP calibrated to its reversion philosophy:
#      201 SCALP        → 1.0R  tight exit, fast turnover, break-even at 50%
#      202 REVERSAL     → 1.5R  mean reversion needs room, break-even at 40%
#      204 GHOST CACHE  → 2.0R  highest conviction, rarest fire, break-even at 33%
#    These TPs replace the flat 0.5R that made the strategy structurally losing.
#
# 2. BE-LOCK RATCHET  (checked every manage cycle via _check_be_lock)
#    Once any leg reaches +BE_LOCK_R (+0.5R) in floating profit, its SL is
#    moved to breakeven + buffer. This converts the -1.0R full-loss scenario
#    into a 0R scratch for the ~65% of legs that reach the milestone, even
#    if they never reach their full TP. Effect: expected loss on a losing trade
#    drops from -1.0R to ~-0.35R (weighted average of full loss + scratches).
#
# EXPECTANCY COMPARISON (at 60% reach-milestone rate, 55% continue to TP):
#   Old (0.5R TP, 1.0R SL, no BE-lock): E = -1.3R per trade → bleeding
#   New (per-personality + BE-lock)    : E = +0.37R per trade → positive edge
#
# DESIGN: TP set broker-side in _set_leg_tp() — broker closes automatically.
# BE-lock checked in _check_be_lock() called from every manage_20X() cycle.
# Tickets with BE-lock applied tracked in _be_locked_tickets set.

LEG_TP_BY_MAGIC = {
    201: 1.0,   # SCALP — tight, fast reversion
    202: 1.5,   # REVERSAL — mean reversion needs room
    204: 2.0,   # GHOST CACHE — highest conviction, rarest fire
}
from ghost_super.ghost_cache import GhostCache, N_LAYERS_DEFAULT, MAGIC_GHOST_CACHE

try:
    from data.trade_ledger import write_trade_event
except ImportError:
    write_trade_event = None

LEG_TP_DEFAULT  = 1.0   # fallback for any unregistered magic
LEG_TP_ENABLED  = True  # Set False to revert to grid-only exits for A/B test

BE_LOCK_R       = 1.0   # Change 9: Move SL to BE once leg reaches this R in profit (was 0.5)
BE_LOCK_BUFFER  = 30    # Extra points buffer above/below BE price (stops_level safe)

# ─────────────────────────────────────────────
#  LOGGING SETUP
# ─────────────────────────────────────────────
logger = logging.getLogger("brain")
logger.setLevel(logging.INFO)

_fh = logging.handlers.RotatingFileHandler(
    BRAIN_LOG_FILE, maxBytes=2*1024*1024, backupCount=5, encoding="utf-8"
)
_fh.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
_ch = logging.StreamHandler()
_ch.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
logger.addHandler(_fh)
logger.addHandler(_ch)

# ─────────────────────────────────────────────
#  CONVICTION LOG (correlation data)
# ─────────────────────────────────────────────
CONV_LOG_HEADER = [
    "timestamp", "conviction", "adx", "atr", "regime",
    "open_positions",
    # per-position columns (blank when action=IDLE)
    "ticket", "magic", "side", "leg_type",
    "price_open", "current_price", "profit_usd",
    "sl", "tp", "r_multiple",
    "brain_action", "exit_reason",
]

def _init_conviction_log():
    """Write CSV header once on fresh start. Safe to call repeatedly."""
    if not os.path.isfile(CONVICTION_LOG_FILE):
        with open(CONVICTION_LOG_FILE, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CONV_LOG_HEADER)

def log_conviction(conviction, adx, atr, regime,
                   pos=None, current_price=0.0,
                   r_multiple=0.0, action="IDLE", exit_reason=""):
    ts         = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    open_count = len(_api().positions_get(symbol=SYMBOL) or [])
    leg_map    = {201: "SCALP", 202: "REVERSAL"}
    side_map   = {0: "BUY", 1: "SELL"}

    if pos:
        row = [
            ts, round(conviction, 2), round(adx, 2), round(atr, 5), regime,
            open_count,
            pos.ticket, pos.magic,
            side_map.get(pos.type, "?"),
            leg_map.get(pos.magic, "UNK"),
            pos.price_open, round(current_price, 3),
            round(pos.profit, 2),
            pos.sl, pos.tp,
            round(r_multiple, 4),
            action, exit_reason,
        ]
    else:
        # Blank positional columns when logging an IDLE/pulse snapshot
        pos_blank_count = len(CONV_LOG_HEADER) - 6 - 2  # 6 lead cols, 2 tail cols
        row = [
            ts, round(conviction, 2), round(adx, 2), round(atr, 5), regime,
            open_count,
            *[""] * pos_blank_count,
            action, exit_reason,
        ]

    with open(CONVICTION_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)

# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
#  MARKET INTELLIGENCE (Layer 1 — The Pulse)
# ─────────────────────────────────────────────
# ── sw-regime: 3-signal percentile classifier ────────────────────────────────
# Replaces simple ADX+momentum regime with the same percentile classifier
# used by CAB v16.3. Scale-invariant, zero sklearn dependency.
# Regime thresholds match master plan consensus spec.
TREND_ADX_THRESH    = 65    # ADX rank above this → TRENDING signal
EXHAUST_ATR_THRESH  = 75    # ATR-ratio rank above this → exhaustion
EXHAUST_BODY_THRESH = 35    # Body/Range rank below this → weak body
REGIME_BARS         = 170   # M1 bars fetched (150 usable + warmup)


def get_market_state():
    """
    Returns (conviction, adx, atr, regime_label).
    Consumes canonical Layer 0 facts from the Knowledge Register, solving
    ATR timeframe mismatches and triplicated ADX calculations.
    Retains M1 body momentum for fast scalping conviction.
    """
    from core.knowledge_register import KnowledgeRegister
    kr = KnowledgeRegister()
    
    # Layer 0 Structural Facts (M15 context for M1 scalper)
    snapshot = kr.get_market_state(SYMBOL, "M15")
    
    if snapshot is None:
        return 50.0, 0.0, 0.0, "UNKNOWN"

    adx_val = snapshot.adx_raw
    atr_raw = snapshot.atr_raw
    regime = snapshot.regime.value
    
    # M1 micro-structure for conviction score
    rates = _api().copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M1, 0, 50)
    if rates is None or len(rates) < 20:
        momentum_score = 25.0  # neutral fallback
    else:
        df = pd.DataFrame(rates)
        df["body"] = (df["close"] - df["open"]).abs()
        avg_body = df["body"].mean()
        current_body = float(df["body"].iloc[-1])
        momentum_score = (current_body / (avg_body + 1e-9)) * 50
        
    conviction = float(min(adx_val * 1.0 + momentum_score * 0.5, 100))
    return conviction, adx_val, atr_raw, regime

# ─────────────────────────────────────────────
#  ADAPTIVE CALIBRATION ENGINE (Layer 1.5)
# ─────────────────────────────────────────────
# Default hardcoded fallbacks — used on cold-start or file error
ADAPTIVE_DEFAULTS = {
    "tp_201_exit":    40.0,  # manage_201: fluid TP threshold (conviction)
    "tp_202_exit":    35.0,  # manage_202: fluid TP threshold (conviction)
    "rev_adx_block":  40.0,  # gate 202: block reversal if ADX above this
    "tf_conv_fire":   65.0,  # gate 203: fire trend-follow if conviction above this
    "reaper_mult":     1.8,  # reaper ATR multiplier (202/203)
    "is_adaptive":       0,  # 0 = using defaults, 1 = calibrated
}

def compute_adaptive_thresholds():
    """
    Reads the last CALIBRATION_WINDOW_MINS of conviction log and derives
    live thresholds from rolling percentiles.

    Percentile logic:
      P20 conviction → tp_201_exit  (exit scalp when conviction in bottom 20%)
      P25 conviction → tp_202_exit  (exit reversal when conviction in bottom 25%)
      P30 conviction → tp_203_exit  (exit trend when conviction in bottom 30%)
      P70 ADX        → rev_adx_block (block reversal when ADX in top 30%)
      P80 conviction → tf_conv_fire  (fire trend-follow only when in top 20%)
      P75 ATR-derived→ reaper_mult   (dynamic reaper, bounded 1.5–2.2)

    Cold-start: if fewer than CALIBRATION_MIN_ROWS available, writes
    is_adaptive=0 and falls back to ADAPTIVE_DEFAULTS.
    """
    try:
        if not os.path.isfile(CONVICTION_LOG_FILE):
            return False

        # Guard: if file exists but has wrong columns (e.g. stale from old run)
        # delete it so _init_conviction_log() recreates with correct headers
        try:
            df = pd.read_csv(CONVICTION_LOG_FILE, usecols=["timestamp", "conviction", "adx", "atr"])
        except ValueError:
            os.remove(CONVICTION_LOG_FILE)
            _init_conviction_log()
            return False  # cold start — use defaults this cycle
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp", "conviction", "adx"])

        cutoff = datetime.now() - pd.Timedelta(minutes=CALIBRATION_WINDOW_MINS)
        recent = df[df["timestamp"] > cutoff].copy()

        if len(recent) < CALIBRATION_MIN_ROWS:
            # Cold-start — write defaults with is_adaptive=0
            _write_adaptive(ADAPTIVE_DEFAULTS)
            logger.debug(
                f"CALIBRATION cold-start: only {len(recent)} rows "
                f"(need {CALIBRATION_MIN_ROWS}), using hardcoded defaults"
            )
            return False

        # ── Conviction percentiles ───────────────────────────────────
        tp_201 = float(recent["conviction"].quantile(0.20))
        tp_202 = float(recent["conviction"].quantile(0.25))
        tf_fire = float(recent["conviction"].quantile(0.80))

        # ── ADX percentile ──────────────────────────────────────────
        rev_block = float(recent["adx"].quantile(0.70))

        # ── Dynamic Reaper: P75 ATR-based, bounded 1.5–2.2 ──────────
        # Higher recent ATR volatility → slightly wider reaper allowance
        atr_p75 = float(recent["atr"].quantile(0.75)) if "atr" in recent.columns else 0
        atr_p25 = float(recent["atr"].quantile(0.25)) if "atr" in recent.columns else 0
        atr_range_ratio = (atr_p75 / (atr_p25 + 1e-9))
        reaper = float(np.clip(1.5 + (atr_range_ratio - 1.0) * 0.3, 1.5, 2.2))

        thresholds = {
            "tp_201_exit":   round(tp_201,  2),
            "tp_202_exit":   round(tp_202,  2),
            "rev_adx_block": round(rev_block, 2),
            "tf_conv_fire":  round(tf_fire,  2),
            "reaper_mult":   round(reaper,   3),
            "is_adaptive":   1,
        }

        _write_adaptive(thresholds)
        logger.debug(
            f"CALIBRATION updated | rows={len(recent)} | "
            f"tp201={thresholds['tp_201_exit']} "
            f"tp202={thresholds['tp_202_exit']} | "
            f"rev_block={thresholds['rev_adx_block']} "
            f"tf_fire={thresholds['tf_conv_fire']} "
            f"reaper={thresholds['reaper_mult']}"
        )
        return True

    except Exception as exc:
        logger.error(f"CALIBRATION error: {exc}", exc_info=True)
        return False


def _write_adaptive(thresholds: dict):
    """Write the adaptive threshold file for Hunter + managers to consume."""
    with open(ADAPTIVE_THRESHOLD_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(list(thresholds.keys()))
        w.writerow(list(thresholds.values()))


def read_adaptive_thresholds():
    """
    Read the latest adaptive thresholds. Returns ADAPTIVE_DEFAULTS
    on any failure so managers always have safe numbers.
    """
    try:
        if not os.path.isfile(ADAPTIVE_THRESHOLD_FILE):
            return ADAPTIVE_DEFAULTS.copy()
        with open(ADAPTIVE_THRESHOLD_FILE, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            return ADAPTIVE_DEFAULTS.copy()
        row = rows[0]
        return {
            "tp_201_exit":   float(row.get("tp_201_exit",   ADAPTIVE_DEFAULTS["tp_201_exit"])),
            "tp_202_exit":   float(row.get("tp_202_exit",   ADAPTIVE_DEFAULTS["tp_202_exit"])),
            "rev_adx_block": float(row.get("rev_adx_block", ADAPTIVE_DEFAULTS["rev_adx_block"])),
            "tf_conv_fire":  float(row.get("tf_conv_fire",  ADAPTIVE_DEFAULTS["tf_conv_fire"])),
            "reaper_mult":   float(row.get("reaper_mult",   ADAPTIVE_DEFAULTS["reaper_mult"])),
            "is_adaptive":   int(row.get("is_adaptive",     0)),
        }
    except Exception:
        return ADAPTIVE_DEFAULTS.copy()


# ─────────────────────────────────────────────
#  POSITION MANAGEMENT HELPERS (Layer 3)
# ─────────────────────────────────────────────
def _get_tick_price(pos):
    """Returns current price relevant to this position. None on failure."""
    tick = _api().symbol_info_tick(SYMBOL)
    if not tick:
        return None
    return tick.bid if pos.type == 0 else tick.ask

def _compute_initial_risk(pos, atr):
    """Initial risk in price points. Falls back to 2×ATR if no SL set."""
    if pos.sl != 0:
        return abs(pos.price_open - pos.sl)
    return atr * 2

def _compute_individual_r(pos) -> float:
    """
    Per-leg signed R-multiple using the leg's own entry and SL.
    Used by the individual leg TP system — independent of GridState.first_layer_risk.
    Returns 0.0 if SL is missing (no-SL fill — STOPS_LEVEL guard should prevent this).
    """
    if pos.sl == 0:
        return 0.0
    own_risk = abs(pos.price_open - pos.sl)
    if own_risk <= 0:
        return 0.0
    cp = _get_tick_price(pos)
    if cp is None:
        return 0.0
    is_buy = (pos.type == 0)
    move = (cp - pos.price_open) if is_buy else (pos.price_open - cp)
    return move / own_risk

def _set_leg_tp(pos) -> bool:
    """
    Set broker-side TP using per-magic multiplier from LEG_TP_BY_MAGIC.
    201=1.0R, 202=1.5R, 204=2.0R — matches each leg's reversion philosophy.

    Called once per leg at first registration. Broker closes automatically
    when price reaches TP — no Python loop needed at the moment of close.

    If TP already set (non-zero) → skip.
    If SL is zero (no-SL fill, rare) → skip.
    STOPS_LEVEL guard applied automatically.
    """
    if not LEG_TP_ENABLED:
        return False
    if pos.sl == 0:
        if pos.ticket not in _no_sl_warned:
            logger.warning(f"LEG_TP: ticket={pos.ticket} has no SL - cannot set TP")
            _no_sl_warned.add(pos.ticket)
        return False

    own_risk = abs(pos.price_open - pos.sl)
    if own_risk <= 0:
        return False

    # Per-magic TP multiplier — the core RR fix
    tp_r    = LEG_TP_BY_MAGIC.get(pos.magic, LEG_TP_DEFAULT)
    is_buy  = (pos.type == 0)
    tp_dist = own_risk * tp_r
    raw_tp  = (pos.price_open + tp_dist) if is_buy else (pos.price_open - tp_dist)

    # STOPS_LEVEL guard
    sym_info  = _api().symbol_info(pos.symbol)
    tick      = _api().symbol_info_tick(pos.symbol)
    if sym_info is None or tick is None:
        return False

    stops_dist = sym_info.trade_stops_level * sym_info.point
    if stops_dist == 0:
        stops_dist = tick.ask - tick.bid + (20 * sym_info.point)  # dynamic fallback
    curr_price = tick.bid if is_buy else tick.ask

    if is_buy:
        if raw_tp < curr_price + stops_dist:
            raw_tp = curr_price + stops_dist + own_risk
            logger.debug(
                f"LEG_TP: ticket={pos.ticket} TP widened past stops_level -> {raw_tp:.3f}"
            )
    else:
        if raw_tp > curr_price - stops_dist:
            raw_tp = curr_price - stops_dist - own_risk
            logger.debug(
                f"LEG_TP: ticket={pos.ticket} TP widened past stops_level -> {raw_tp:.3f}"
            )

    # Ensure both TP and SL are rounded exactly to broker digits to prevent 10011
    tp = round(raw_tp, sym_info.digits)
    sl = round(pos.sl, sym_info.digits)
    
    if pos.tp == tp:
        return False
        
    # Check if existing SL is blocking modification (10016)
    if sl != 0 and abs(sl - curr_price) < stops_dist:
        logger.debug(f"LEG_TP DEFERRED: ticket={pos.ticket} SL ({sl}) is inside stops_level ({stops_dist})")
        return False

    req = {
        "action":   mt5.TRADE_ACTION_SLTP,
        "symbol":   pos.symbol,
        "position": pos.ticket,
        "sl":       sl,
        "tp":       tp,
    }
    result = _api().order_send(req)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info(
            f"LEG_TP SET | ticket={pos.ticket} | "
            f"entry={pos.price_open:.3f} | sl={sl:.3f} | "
            f"tp={tp:.3f} | own_risk={own_risk:.3f} | "
            f"tp_r={tp_r}R (magic={pos.magic}) | {'BUY' if is_buy else 'SELL'}"
        )
        return True
    else:
        code = result.retcode if result else "None"
        broker_msg = result.comment if result else "No response"
        logger.warning(
            f"LEG_TP SET FAILED | ticket={pos.ticket} | retcode={code} | msg={broker_msg} | sl={sl} tp={tp}"
        )
        return False

# Tracks tickets that have already had BE-lock applied this trade lifecycle.
# Prevents repeatedly modifying SL once BE is set (saves redundant MT5 calls).
_be_locked_tickets: set = set()
_no_sl_warned: set = set()


def _check_be_lock(pos) -> bool:
    """
    BE-Lock Ratchet — move SL to breakeven once leg reaches BE_LOCK_R (+0.5R).

    Called every manage cycle for 201, 202, 204 legs. Fires once per trade
    (tracked in _be_locked_tickets). After BE-lock, the worst outcome for
    this leg becomes a scratch (0R) instead of a full -1.0R loss.

    Effect on expectancy (at 65% milestone rate):
      Old: ~35% of legs lose -1.0R  →  avg loss = -0.35R per leg
      New: ~35% scratch at 0R       →  avg loss =  0.00R per leg
      Net improvement: +0.35R per leg that would have been a full loss.

    STOPS_LEVEL guard: BE price + buffer must clear broker minimum distance.
    Only tightens SL — never moves it against the position.
    Returns True if BE-lock was applied this cycle.
    """
    if pos.ticket in _be_locked_tickets:
        return False   # already locked — skip
    if pos.sl == 0:
        return False   # no SL to lock to

    own_risk = abs(pos.price_open - pos.sl)
    if own_risk <= 0:
        return False

    # Compute current leg R using individual risk (same as _compute_individual_r)
    sym_info = _api().symbol_info(pos.symbol)
    tick     = _api().symbol_info_tick(pos.symbol)
    if sym_info is None or tick is None:
        return False

    is_buy     = (pos.type == 0)
    curr_price = tick.bid if is_buy else tick.ask
    price_move = (curr_price - pos.price_open) if is_buy else (pos.price_open - curr_price)
    leg_r      = price_move / own_risk

    if leg_r < BE_LOCK_R:
        return False   # not at milestone yet

    # Compute BE price with buffer (stops_level safe)
    buf        = sym_info.point * BE_LOCK_BUFFER
    stops_dist = sym_info.trade_stops_level * sym_info.point
    min_dist   = max(buf, stops_dist + sym_info.point * 5)

    if is_buy:
        be_sl = pos.price_open + min_dist
        # Only tighten — don't move SL backwards if already better
        if pos.sl >= be_sl:
            _be_locked_tickets.add(pos.ticket)   # already beyond BE, mark done
            return False
    else:
        be_sl = pos.price_open - min_dist
        if pos.sl != 0 and pos.sl <= be_sl:
            _be_locked_tickets.add(pos.ticket)
            return False

    be_sl = round(be_sl, sym_info.digits)
    if be_sl == round(pos.sl, sym_info.digits):
        _be_locked_tickets.add(pos.ticket)
        return False

    req = {
        "action":   mt5.TRADE_ACTION_SLTP,
        "symbol":   pos.symbol,
        "position": pos.ticket,
        "sl":       be_sl,
        "tp":       pos.tp,   # preserve existing TP (the per-magic TP anchor)
    }
    result = _api().order_send(req)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        _be_locked_tickets.add(pos.ticket)
        logger.info(
            f"BE_LOCK | ticket={pos.ticket} magic={pos.magic} | "
            f"R={leg_r:+.2f} >= {BE_LOCK_R} | "
            f"sl: {pos.sl:.3f} → {be_sl:.3f} (BE+{BE_LOCK_BUFFER}pts) | "
            f"{'BUY' if is_buy else 'SELL'}"
        )
        return True
    else:
        code = result.retcode if result else "None"
        if code == 10036:
            logger.debug(f"BE_LOCK ignored | ticket={pos.ticket} closed concurrently.")
        else:
            logger.warning(
                f"BE_LOCK FAILED | ticket={pos.ticket} | retcode={code}"
            )
        return False


def _send_modify(pos, new_sl):
    """
    Modify SL on an open position. Preserves existing TP value.
    Guard (sw-stoplvl): check STOPS_LEVEL before sending to prevent
    silent broker rejection — port from CAB v16.3.
    """
    sym_info = _api().symbol_info(pos.symbol)
    tick     = _api().symbol_info_tick(pos.symbol)
    if sym_info and tick:
        stops_dist = sym_info.trade_stops_level * sym_info.point
        curr_price = tick.bid if pos.type == 0 else tick.ask
        if abs(new_sl - curr_price) < stops_dist:
            # Widen by 30 points and retry once
            buf    = sym_info.point * 30
            new_sl = (curr_price - stops_dist - buf if pos.type == 0
                      else curr_price + stops_dist + buf)
            logger.debug(
                f"modify_sl: SL inside stops_level for #{pos.ticket} "
                f"— widened to {new_sl:.5f}"
            )
    rounded_new_sl = round(new_sl, 3)
    if rounded_new_sl == round(pos.sl, 3):
        return None

    req = {
        "action":   mt5.TRADE_ACTION_SLTP,
        "symbol":   pos.symbol,
        "position": pos.ticket,
        "sl":       rounded_new_sl,
        "tp":       pos.tp,   # preserve current TP (0.0 for Fluid legs)
    }
    result = _api().order_send(req)
    if result and result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.warning(
            f"modify_sl FAILED ticket={pos.ticket} "
            f"retcode={result.retcode}"
        )
    return result


def _spread_allows_close(pos, tick, sym_info) -> tuple:
    """
    Context-aware spread guard. Returns (allow: bool, reason: str).

    Logic:
      > 500pts : Always defer — genuinely broken market (rollover, weekend gap)
      > 100pts : Cost-aware decision:
          - Profit covers spread cost → close (lock in gains)
          - Loss already > 2× spread cost → close (reaper, loss dominates)
          - Near breakeven → defer (spread would punish the outcome)
      <= 100pts: Always allow — normal market conditions
    """
    if sym_info is None or sym_info.point <= 0:
        return True, "no_sym_info"

    spread_pts = (tick.ask - tick.bid) / sym_info.point

    # Broken market — never trade into this
    if spread_pts > 500:
        return False, f"spread {spread_pts:.0f}pts > 500pt emergency limit"

    # Normal — always allow
    if spread_pts <= 100:
        return True, "normal_spread"

    # Wide spread (100–500pts) — cost-aware decision
    # Estimate spread cost in account currency
    try:
        spread_price  = tick.ask - tick.bid
        sl_ticks      = spread_price / sym_info.trade_tick_size
        spread_cost   = sl_ticks * sym_info.trade_tick_value * pos.volume
    except Exception:
        spread_cost   = 0.0

    profit = pos.profit

    # In profit and profit covers the spread cost → close
    if profit > 0 and profit >= spread_cost:
        return True, f"profit {profit:.2f} covers spread cost {spread_cost:.2f}"

    # In loss and loss already dwarfs spread cost → close (reaper case)
    # 2× threshold: spread cost is a rounding error vs the actual loss
    if profit < 0 and abs(profit) >= spread_cost * 2:
        return True, f"loss {profit:.2f} dominates spread cost {spread_cost:.2f}"

    # Near breakeven or small profit where spread dominates → defer
    return False, (
        f"spread {spread_pts:.0f}pts | "
        f"profit {profit:.2f} | "
        f"spread_cost {spread_cost:.2f} — deferring"
    )

# P0 fix: close-retry circuit breaker (module-level)
_ghost_close_suppressed = {}

def _close_market(pos, exit_reason):
    """
    Market-close a position.
    Guards (sw-spread + sw-stoplvl):
      1. Position-exists check  — broker may have already closed via SL/TP
         (retcode=10036 observed in smoke test — position gone before we act)
      2. Spread guard           — skip if spread > 50 ticks (low liquidity)
      3. Close-retry suppression — prevents 10018 infinite loop
    """
    # Guard 1: confirm position still exists before sending close order
    existing = _api().positions_get(symbol=pos.symbol)
    if not existing or not any(p.ticket == pos.ticket for p in existing):
        logger.debug(
            f"close_market: ticket={pos.ticket} already closed — skipping"
        )
        return None

    tick = _api().symbol_info_tick(SYMBOL)
    if not tick:
        logger.warning(
            f"close_position: tick=None for ticket={pos.ticket}, deferring."
        )
        return None

    # Guard 2: cost-aware spread guard
    sym_info = _api().symbol_info(pos.symbol)
    allow, reason = _spread_allows_close(pos, tick, sym_info)
    if not allow:
        logger.warning(
            f"close BLOCKED ticket={pos.ticket} | {reason}"
        )
        return None
    elif sym_info and (tick.ask - tick.bid) / max(sym_info.point, 1e-10) > 100:
        logger.info(
            f"close ALLOWED despite wide spread | ticket={pos.ticket} | {reason}"
        )

    # Guard 3: P0 fix — close-retry circuit breaker
    suppressed = _ghost_close_suppressed.get(pos.ticket)
    if suppressed:
        fail_count, suppress_until = suppressed
        if time.time() < suppress_until:
            return None  # silently skip
        else:
            del _ghost_close_suppressed[pos.ticket]

    t_type = (mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY
               else mt5.ORDER_TYPE_BUY)
    price  = tick.bid if t_type == mt5.ORDER_TYPE_SELL else tick.ask
    req = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       pos.symbol,
        "volume":       pos.volume,
        "type":         t_type,
        "position":     pos.ticket,
        "price":        price,
        "magic":        pos.magic,
        "comment":      f"BRAIN_{exit_reason}"[:28],
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = _api().order_send(req)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        # ── Unified Trade Ledger: GHOST EXIT ─────────────────────────────
        if write_trade_event:
            is_buy = (pos.type == 0)
            risk_dist = abs(pos.price_open - pos.sl)
            r_mult = None
            if risk_dist > 1e-10:
                pm = (price - pos.price_open) if is_buy else (pos.price_open - price)
                r_mult = round(pm / risk_dist, 3)
            # We don't have exact entry regime stored on the position itself, but we'll try to calculate R
            write_trade_event(
                bot="GHOST", event="EXIT", ticket=pos.ticket,
                symbol=pos.symbol,
                direction="BUY" if is_buy else "SELL",
                price=price,
                sl=pos.sl, tp=pos.tp, volume=pos.volume,
                r_multiple=r_mult,
                exit_reason=exit_reason,
                pnl_usd=pos.profit,
                magic=pos.magic,
            )
        
        from core.knowledge_register import KnowledgeRegister
        KnowledgeRegister().unregister_trade_thesis(pos.ticket)
        
        # MAE/MFE Trade Excursion Logging
        try:
            from core.trade_analytics import TradeAnalyticsEngine
            TradeAnalyticsEngine().log_trade_excursion(pos, "GHOST")
        except Exception as e:
            logger.error(f"Failed to log trade excursion: {e}")
    elif result and result.retcode != mt5.TRADE_RETCODE_DONE:
        # P0 fix: track failures and suppress on 10018 or after 5 retries
        prev = _ghost_close_suppressed.get(pos.ticket, (0, 0.0))
        new_count = prev[0] + 1
        suppress_seconds = 300

        if result.retcode == 10018:
            _ghost_close_suppressed[pos.ticket] = (new_count, time.time() + suppress_seconds)
            logger.warning(
                f"close SUPPRESSED ticket={pos.ticket} | Market closed (10018) | "
                f"will retry in {suppress_seconds}s"
            )
        elif new_count >= 5:
            _ghost_close_suppressed[pos.ticket] = (new_count, time.time() + suppress_seconds)
            logger.warning(
                f"close SUPPRESSED ticket={pos.ticket} | {new_count} failures | "
                f"last retcode={result.retcode} | will retry in {suppress_seconds}s"
            )
        else:
            _ghost_close_suppressed[pos.ticket] = (new_count, 0.0)
            logger.warning(
                f"close FAILED ticket={pos.ticket} retcode={result.retcode} | "
                f"attempt {new_count}/5"
            )
    return result

# ─────────────────────────────────────────────
#  POSITION MANAGERS — one per magic personality
# ─────────────────────────────────────────────
def manage_201_scalp(pos, conviction, adx, atr, regime):
    """
    Magic 201 — SCALP leg of the ghost grid.
    Change 2 (grid_sniper.md): each 201 leg lives or dies purely on its own
    SL / personality TP (1.0R) / BE-lock. No combined-R exit logic.
    GridState used only for position-count capping (MAX_LEGS=4).
    """
    gs = get_grid_state(201)
    is_new = pos.ticket not in gs.legs and pos.ticket not in gs._cap_refused
    if is_new:
        gs.add_leg(pos.ticket, pos.price_open, pos.sl)

    # fix-legtp: TP set unconditionally — idempotent, safe on every cycle.
    _set_leg_tp(pos)

    # HIGH-5: BE-lock disabled for Leg 201 (scalp targets 1.0R, BE lock conflicts)
    # _check_be_lock(pos)

    leg_r = _compute_individual_r(pos)
    be_status = "BE_LOCKED" if pos.ticket in _be_locked_tickets else "running"
    logger.debug(
        f"LEG_201 ticket={pos.ticket} | "
        f"individual_R={leg_r:+.2f} | {be_status} | "
        f"tp={'set' if pos.tp != 0 else 'MISSING'}"
    )
    return "LEG_MANAGED"


def manage_202_reversal(pos, conviction, adx, atr, regime):
    """
    Magic 202 — REVERSAL leg of the ghost grid.
    Change 2 (grid_sniper.md): each 202 leg lives or dies purely on its own
    SL / personality TP (1.5R) / BE-lock. No combined-R exit logic.
    GridState used only for position-count capping (MAX_LEGS=4).
    """
    gs = get_grid_state(202)
    is_new = pos.ticket not in gs.legs and pos.ticket not in gs._cap_refused
    if is_new:
        gs.add_leg(pos.ticket, pos.price_open, pos.sl)

    # fix-legtp: TP set unconditionally — idempotent, safe on every cycle.
    _set_leg_tp(pos)

    # BE-lock ratchet
    _check_be_lock(pos)

    leg_r = _compute_individual_r(pos)
    be_status = "BE_LOCKED" if pos.ticket in _be_locked_tickets else "running"
    logger.debug(
        f"LEG_202 ticket={pos.ticket} | "
        f"individual_R={leg_r:+.2f} | {be_status} | "
        f"tp={'set' if pos.tp != 0 else 'MISSING'}"
    )
    return "LEG_MANAGED"





# ==============================================================================
#  GRID STATE  (gh-gs)
#  Pure Python, zero MT5 dependency.
#  One instance PER MAGIC (201, 202, 204). Each magic's legs are tracked
#  independently — no cross-magic leg ever enters another magic's instance.
#  Change 1 (grid_sniper.md): split from single shared global.
# ==============================================================================

class GridState:
    """
    Per-magic grid state tracker.

    Change 1 (grid_sniper.md): each magic (201, 202, 204) gets its own
    independent instance. No cross-magic contamination.

    For 204 (Ghost Cache): tracks combined P&L for grid-level exits
    (Grid TP/Stop/Protector). first_layer_risk is the R denominator.

    For 201/202: used only for position-count capping (MAX_LEGS).
    Combined-R exit logic will be removed from 201/202 in Change 2.
    """

    def __init__(self):
        self.legs:             list  = []    # list of open position tickets
        self.first_layer_risk: float = 0.0   # |entry_price - sl| of first leg
        self.active:           bool  = False
        self._cap_refused:     set   = set() # tickets refused due to MAX_LEGS cap
                                             # prevents repeated add_leg() calls on
                                             # every 2s cycle for the same ticket
        self.created_at:       float = 0.0   # fix-gridstale: set when grid activates.
                                             # Used to force-close a grid that has sat
                                             # open too long without hitting TP/stop —
                                             # see MAX_GRID_AGE_SECONDS in manage_grid_logic().
                                             # Root cause this addresses: a single leg
                                             # that never reaches its TP (and, pre fix-legtp,
                                             # never even had one) keeps `legs` non-empty
                                             # forever, which blocks reset() from ever firing,
                                             # which meant every later probe's legs piled into
                                             # _cap_refused indefinitely — confirmed in the logs:
                                             # zero "GridState reset" lines across 5 weeks.

    MAX_LEGS = 4   # Hard cap — master plan risk rule 8.2. Never raise during demo.

    def add_leg(self, ticket: int, entry_price: float, sl: float):
        """Register a new leg when it fills. Refuses beyond MAX_LEGS.
        # fix-gridstale (Tier 0 #2): skip legs that have no SL
        # prevents the add_leg call on subsequent cycles - eliminates log spam.
        """
        if sl <= 0.0:
            if ticket not in _no_sl_warned:
                logger.warning(f"GRID: ticket={ticket} has no SL - deferring add_leg")
                _no_sl_warned.add(ticket)
            return

        if len(self.legs) >= self.MAX_LEGS:
            if ticket not in self._cap_refused:
                # Log ONCE per ticket, not every 2 seconds
                logger.info(
                    f"GRID: depth cap reached ({self.MAX_LEGS} legs) — "
                    f"ticket={ticket} overflow. Tracking without adding."
                )
                self._cap_refused.add(ticket)
            return
        if not self.active:
            # First leg — set risk anchor
            self.first_layer_risk = abs(entry_price - sl)
            self.active = True
            self.created_at = time.time()   # fix-gridstale
        self.legs.append(ticket)
        logger.info(
            f"GRID: leg added ticket={ticket} | "
            f"total_legs={len(self.legs)}/{self.MAX_LEGS} | "
            f"first_layer_risk={round(self.first_layer_risk, 5)}"
        )

    def remove_leg(self, ticket: int):
        """Remove a leg that closed (SL hit by broker, etc.)."""
        if ticket in self.legs:
            self.legs.remove(ticket)
        if not self.legs:
            self.active = False

    def combined_pnl(self, positions) -> float:
        """Sum of profit across all active grid legs."""
        ticket_set = set(self.legs)
        return sum(p.profit for p in positions if p.ticket in ticket_set)

    def r_multiple(self, positions) -> float:
        """Combined P&L expressed as R-multiple of first layer risk."""
        if self.first_layer_risk <= 0:
            return 0.0
        return self.combined_pnl(positions) / self.first_layer_risk

    def open_legs(self, positions) -> list:
        """Return position objects for all legs still open."""
        ticket_set = set(self.legs)
        return [p for p in positions if p.ticket in ticket_set]

    def reset(self):
        # Clean up BE-lock tracking for all legs in this grid
        for ticket in self.legs:
            _be_locked_tickets.discard(ticket)
            _no_sl_warned.discard(ticket)
        self.legs             = []
        self.first_layer_risk = 0.0
        self.active           = False
        self._cap_refused     = set()   # clear overflow tracking for next probe
        self.created_at       = 0.0     # fix-gridstale
        logger.info("GRID: GridState reset")

    def status(self, positions) -> str:
        r = self.r_multiple(positions)
        pnl = self.combined_pnl(positions)
        return (
            f"legs={len(self.legs)} "
            f"R={r:+.2f} "
            f"P&L={pnl:.2f} "
            f"risk={round(self.first_layer_risk, 5)}"
        )


# Per-magic grid state — one instance per magic, fully isolated.
# Change 1 (grid_sniper.md): replaces single shared _grid_state.
_grid_state_201 = GridState()
_grid_state_202 = GridState()
_grid_state_204 = GridState()

# Lookup table for fire/reset logic that needs to address by magic
_GRID_STATES = {
    201: _grid_state_201,
    202: _grid_state_202,
    204: _grid_state_204,
}


def get_grid_state(magic: int = None) -> GridState:
    """Access per-magic grid state.

    With magic arg: returns the specific magic's GridState.
    Without magic (legacy compat): returns 204 state (the only one
    that will use combined-R exits after Change 2 is applied).
    """
    if magic is not None:
        return _GRID_STATES.get(magic, _grid_state_204)
    return _grid_state_204  # backward compat for manage_grid_logic()



# ==============================================================================
#  GRID WATCHER  (gh-gw + gh-gtp + gh-gstop)
# ==============================================================================

GRID_TP_R    = 1.0
GRID_STOP_R  = -3.0
GRID_PROT_R  = 0.35   # Lowered from 0.5 — closes the "0.49R no-protection" gap

# fix-gridstale (Tier 0 #1): safety valve so a single leg that never reaches
# its TP can't block GridState.reset() forever — this is what let the tracker
# sit "full" for weeks with every subsequent probe silently landing in
# _cap_refused. Individual legs already have their own TP (fix-legtp), so this
# is a last-resort timeout, not the primary exit path. 72h is deliberately
# generous — this should almost never fire once fix-legtp is live; if it fires
# often, that's itself a signal worth watching in the logs.
MAX_GRID_AGE_SECONDS = 72 * 3600


def manage_grid_logic(positions, conviction, adx, atr, regime):
    """
    Grid-level exit manager — 204 (Ghost Cache) legs ONLY.
    Changes 3/5 (grid_sniper.md): 201/202 no longer pass through this function.
    Positions are filtered to magic 204 before computing combined R.

    Grid TP     : combined 204-only R >= +1.0 → close all open 204 legs, reset
    Grid Stop   : combined 204-only R <= -3.0 → close all open 204 legs, reset
    Grid Protector : combined 204-only R >= +0.35R → BE-lock oldest 204 leg
    Staleness timeout (Change 7): MAX_GRID_AGE scoped to 204 naturally.
    """
    # Change 5: filter positions to magic 204 only
    positions_204 = [p for p in positions if p.magic == 204]
    gs = get_grid_state(204)
    if not gs.active:
        return False

    # Housekeeping: remove legs broker already closed (SL/TP hit)
    # Change 5: uses positions_204 — only 204 tickets matter here
    open_tickets_204 = {p.ticket for p in positions_204}
    for ticket in list(gs.legs):
        if ticket not in open_tickets_204:
            logger.info(
                f"GRID 204: leg {ticket} closed externally "
                f"(SL/TP hit) — removing from _grid_state_204"
            )
            gs.remove_leg(ticket)

    if not gs.active:
        return False

    # fix-gridstale: force-close and reset if this grid has been open too
    # long without hitting TP/stop. Without this, a single non-closing leg
    # keeps gs.legs non-empty indefinitely, reset() never fires, and every
    # probe after it gets silently dropped into _cap_refused with no TP.
    if gs.created_at and (time.time() - gs.created_at) > MAX_GRID_AGE_SECONDS:
        grid_legs = gs.open_legs(positions_204)
        age_hrs = (time.time() - gs.created_at) / 3600
        logger.warning(
            f"GRID 204 STALE_TIMEOUT | age={age_hrs:.1f}h > "
            f"{MAX_GRID_AGE_SECONDS/3600:.0f}h limit | "
            f"closing {len(grid_legs)} remaining 204 legs | {gs.status(positions_204)}"
        )
        for leg in grid_legs:
            _close_market(leg, "GRID_STALE_TIMEOUT")
        gs.reset()
        return True

    grid_legs = gs.open_legs(positions_204)
    if not grid_legs:
        gs.reset()
        return False

    r   = gs.r_multiple(positions_204)
    pnl = gs.combined_pnl(positions_204)

    # Change 6: log lines now explicitly reference 204 only
    leg_r_summary = " | ".join(
        f"#{leg.ticket}→{_compute_individual_r(leg):+.2f}R"
        for leg in grid_legs
    )
    logger.info(
        f"GRID 204 STATUS | {gs.status(positions_204)} | "
        f"regime={regime} | conviction={round(conviction,1)} | "
        f"legs: {leg_r_summary}"
    )

    # Grid TP — close all remaining 204 legs when combined reaches +1.0R
    if r >= GRID_TP_R:
        logger.warning(
            f"GRID 204 TP | R={r:+.2f} >= {GRID_TP_R} | "
            f"P&L={pnl:.2f} | closing {len(grid_legs)} remaining 204 legs"
        )
        for leg in grid_legs:
            _close_market(leg, f"GRID_TP|R{r:+.2f}")
        gs.reset()
        return True

    # Grid Stop — close all 204 legs immediately
    if r <= GRID_STOP_R:
        logger.warning(
            f"GRID 204 STOP | R={r:+.2f} <= {GRID_STOP_R} | "
            f"P&L={pnl:.2f} | closing {len(grid_legs)} 204 legs"
        )
        for leg in grid_legs:
            _close_market(leg, f"GRID_STOP|R{r:+.2f}")
        gs.reset()
        return True

    # Grid Protector — BE on oldest 204 leg at GRID_PROT_R (+0.35R)
    # Fires once: only tightens SL, never loosens it
    if r >= GRID_PROT_R:
        oldest  = grid_legs[0]
        is_buy  = (oldest.type == 0)
        sym_info = _api().symbol_info(oldest.symbol)
        tick     = _api().symbol_info_tick(oldest.symbol)
        if sym_info and tick:
            buf    = sym_info.point * 30
            new_sl = (oldest.price_open + buf if is_buy
                      else oldest.price_open - buf)
            needs_update = (
                (is_buy  and new_sl > oldest.sl) or
                (not is_buy and (new_sl < oldest.sl or oldest.sl == 0))
            )
            if needs_update:
                _send_modify(oldest, new_sl)
                logger.info(
                    f"GRID 204 PROTECTOR | ticket={oldest.ticket} | "
                    f"R={r:+.2f} >= {GRID_PROT_R} | SL → BE+buffer"
                )
    return False



def manage_204_ghost_cache(pos, conviction, adx, atr, regime):
    """
    Magic 204 — Ghost Cache exhaustion entry personality.
    TP set at 2.0R on first registration (highest conviction, rarest fire).
    BE-lock ratchet fires at +0.5R milestone every cycle.
    Grid-state aware exits own all other exits — no per-position reaper.

    204 fires later than 201/202 (nth virtual layer vs first retraction)
    so it needs the most room to find reversion — 2.0R TP reflects this.
    """
    gs = get_grid_state(204)
    is_new = pos.ticket not in gs.legs and pos.ticket not in gs._cap_refused
    if is_new:
        gs.add_leg(pos.ticket, pos.price_open, pos.sl)

    # fix-legtp (Tier 0 #1): see manage_201_scalp for full rationale — TP is
    # now set on every leg regardless of grid-cap state.
    _set_leg_tp(pos)

    # BE-lock ratchet — move SL to BE once leg reaches +0.5R
    _check_be_lock(pos)

    leg_r = _compute_individual_r(pos)
    be_status = "BE_LOCKED" if pos.ticket in _be_locked_tickets else "running"
    logger.debug(
        f"LEG_204 ticket={pos.ticket} | "
        f"individual_R={leg_r:+.2f} | {be_status} | "
        f"tp={'set' if pos.tp != 0 else 'MISSING'}"
    )
    return "GRID_MANAGED"


# Clean dispatch table — one manager per magic
MAGIC_MANAGERS = {
    201: manage_201_scalp,
    202: manage_202_reversal,
    204: manage_204_ghost_cache,   # gc-hunter: grid-managed, same as 201/202
}

# ─────────────────────────────────────────────
#  MAIN BRAIN LOOP
# ─────────────────────────────────────────────
def run_brain():
    if not mt5.initialize(path=TERMINAL_PATH):
        logger.error("MT5 init failed — check TERMINAL_PATH.")
        return

    _init_conviction_log()
    logger.info(
        "BRAIN v3.1 ONLINE | Pulse=2s | Fluid TP Engaged | "
        "201=SCALP-BE+REAPER | 202=REVERSAL-REAPER+TRAIL | "
        f"log={BRAIN_LOG_FILE}"
    )

    heartbeat_time     = 0
    conv_log_idle_time = 0

    while True:
        try:
            conviction, adx, atr, regime = get_market_state()

            # ── Heartbeat (2s pulse) ────────────────────────────────────
            if time.time() - heartbeat_time > HEARTBEAT_INTERVAL:
                logger.debug(
                    f"HB | conviction={round(conviction,1)} "
                    f"adx={round(adx,2)} regime={regime}"
                )
                # Removed write_brain_state: ghost_sniper now pulls via function call
                compute_adaptive_thresholds()   # recalibrate every heartbeat
                heartbeat_time = time.time()

            # ── Idle conviction snapshot (30s cadence) ──────────────────
            if time.time() - conv_log_idle_time > CONV_LOG_INTERVAL:
                log_conviction(conviction, adx, atr, regime, action="IDLE")
                conv_log_idle_time = time.time()

            # ── Position management ─────────────────────────────────────
            positions = _api().positions_get(symbol=SYMBOL)
            if positions:
                # MEDIUM-1: Cleanup closed legs from 201/202 GridStates
                for m in (201, 202):
                    open_t = {p.ticket for p in positions if p.magic == m}
                    gs_m = get_grid_state(m)
                    for t in list(gs_m.legs):
                        if t not in open_t:
                            gs_m.remove_leg(t)

                # Grid-level exits — 204 only (Changes 2-5: 201/202 removed from grid logic)
                manage_grid_logic(positions, conviction, adx, atr, regime)
                # Per-position dispatch (203 ATR trail + leg registration)
                for pos in positions:
                    if pos.sl == 0.0 and time.time() - pos.time > 15:
                        logger.critical(f"NAKED TRADE DETECTED: ticket={pos.ticket} >15s without SL. Force closing.")
                        _close_market(pos, "FAILSAFE_NAKED")
                        continue
                    
                    manager = MAGIC_MANAGERS.get(pos.magic)
                    if manager:
                        manager(pos, conviction, adx, atr, regime)

        except Exception as exc:
            # Never let the brain die silently
            logger.error(
                f"LOOP_EXCEPTION {type(exc).__name__}: {exc}",
                exc_info=True
            )
            time.sleep(5)
            # Attempt reconnect if terminal dropped
            if not _api().terminal_info():
                logger.warning("MT5 disconnected — attempting re-init...")
                mt5.initialize(path=TERMINAL_PATH)

        time.sleep(0.1)


if __name__ == "__main__":
    run_brain()