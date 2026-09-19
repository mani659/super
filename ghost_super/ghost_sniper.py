"""
╔══════════════════════════════════════════════════════════════════╗
║        GHOST SNIPER v5.1 — Intelligence-Gated Execution Engine   ║
║  Architecture: Layer 2 — The Filter                              ║
╚══════════════════════════════════════════════════════════════════╝

ARCHITECTURE ROLE — Layer 2: The Filter
  Before firing any probe, this script reads the Brain's market state
  (brain_state_live.csv written by Watcher v3.1 every 2 seconds)
  and applies regime-specific gates:

  GATE RULES (v5.2 — Leg 203 REMOVED; trend-following handed off to SuperTrend):
  ┌─────────────────┬────────┬──────────────────────────────────────┐
  │ Leg             │ Magic  │ Condition                            │
  ├─────────────────┼────────┼──────────────────────────────────────┤
  │ Scalp           │  201   │ Always active (if spread ≤ max)      │
  │ Reversal        │  202   │ BLOCKED if ADX > 40 OR conv > 60     │
  └─────────────────┴────────┴──────────────────────────────────────┘

  In a strong trend (ADX>40 or Conv>60): only 201 fires (202 blocked).
  In exhaustion/low-conviction: 201 + 202 fire.
  In ranging low-ADX: 201 + 202 fire (default open).

  NOTE: Leg 203 (Trend-Follow, Magic MAGIC_TREND_FOLLOW) has been
  fully removed. Trend entries are now exclusively managed by
  core/supertrend_bot.py (si_confirmed=0.55) across all four pairs.

KEY CHANGES vs v4.8.2 (v5.0 baseline):
  1. GRID_STEP is dynamic: 1.0 × ATR (floor 0.5).
     Replaces the fixed 0.5 that caused 76 trade-pairs on Apr 23.
  2. Gate logic blocks / allows legs based on live brain state.
  3. 150ms sleep between each order_send to eliminate Err 10027.
  4. Broker buffer raised from point×10 to point×20 for SL anchor.
  5. Enhanced audit CSV: sl, tp, atr, conviction, adx, regime,
     probe_direction, leg_type, grid_step_used at every fill.
  6. RotatingFileHandler on hunter log (no shell redirect needed).
  7. Daily pair counter (soft cap, 999 = unlimited for demo).
  8. Session-tagged fills (ASIAN / LONDON / NY_OVERLAP / NY_CLOSE).

====================================================================
  CHANGELOG v5.2 — Leg 203 Removal
====================================================================
  1. STRIPPED: Leg 203 (Trend-Follow) completely removed.
     SuperTrend bot (si_confirmed=0.55) absorbs trend-follow role.
  2. AUDIT CSV: gate_203 column removed — only gate_201/gate_202 remain.
  3. apply_gates() now returns {201: bool, 202: bool} only.
  4. SLAB C GRACE, FLUID TP, INFRASTRUCTURE from v5.1 unchanged.

  CHANGELOG v5.1 (unchanged from prior):
  1. STRIPPED: Abandoned 'Strict 1:3 RRR' per research reports.
  2. FLUID TP: Watcher (Layer 3) owns all exits via exhaustion logic.
  3. BUFFER: SL anchor buffer raised to point×25 (was point×20).
  4. TP GUARD: TP stops-level check is skipped when tp=0.0 (Fluid TP).
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import os
import csv
import json
import logging
import logging.handlers
from datetime import datetime, date
from pathlib import Path

# fix-204wire: run_hunter() below references GhostCache / N_LAYERS_DEFAULT /
# MAGIC_GHOST_CACHE but this file never imported them — a standalone
# `python ghost_sniper.py` run would NameError the moment a probe armed.
# Try both import forms since this module gets loaded two different ways in
# this codebase: as part of the ghost_super package (unified_runner.py) and
# via importlib.spec_from_file_location pointed straight at this file (tests).
try:
    from ghost_cache import GhostCache, N_LAYERS_DEFAULT, MAGIC_GHOST_CACHE
except ImportError:
    from ghost_super.ghost_cache import GhostCache, N_LAYERS_DEFAULT, MAGIC_GHOST_CACHE

try:
    from data.trade_ledger import write_trade_event
except ImportError:
    write_trade_event = None

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
SYMBOL             = "XAUUSDm"
LOT_SIZE           = 0.01

# Load MT5 credentials from local config file (gitignored).
# fix-secrets (Sep 19 2026): no credential literal lives in this file any more.
# Resolution order is the MT5_* env vars first, then ghost_super/config.json —
# env wins so credentials can be injected without editing a file, which is the
# precedence unified_runner.py already uses for MT5_PASSWORD.
# The literal that used to sit in the PASSWORD fallback is still recoverable from
# git history, so it must be rotated at the broker — scrubbing source does not
# un-publish it.
_GHOST_CFG = Path(__file__).parent / "config.json"
if _GHOST_CFG.exists():
    with open(_GHOST_CFG) as _f:
        _cfg = json.load(_f)
else:
    _cfg = {}

MT5_PATH           = _cfg.get("mt5_path", r"C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe")
ACCOUNT            = _cfg.get("login", 260714012)
PASSWORD           = os.environ.get("MT5_PASSWORD") or _cfg.get("password") or ""
SERVER             = os.environ.get("MT5_SERVER") or _cfg.get("server") or "Exness-MT5Trial15"

MAGIC_SCALP        = 201
MAGIC_REVERSAL     = 202

SPREAD_MAX         = 1.5
COOLDOWN_SECONDS   = 45
DATA_LOG_FILE      = "sniper_v51_live_audit.csv"
BRAIN_STATE_FILE   = "brain_state_live.csv"
HUNTER_LOG_FILE    = "logs/sniper_hunter.log"
ADAPTIVE_THRESHOLD_FILE = "adaptive_thresholds_live.csv"

# ── Gate thresholds ──────────────────────────────
# 202 is BLOCKED when EITHER condition is true
GATE_202_ADX_BLOCK    = 40     # block reversal if ADX above this
GATE_202_CONV_BLOCK   = 60     # block reversal if conviction above this

MAX_LEGS_PER_PROBE    = 1      # set to 2 to re-enable dual-leg firing
MAX_DAILY_PAIRS       = 999    # 999 = unlimited (demo). Set lower for live.
ATR_STEP_MULTIPLIER   = 1.0    # GRID_STEP = ATR × this
ATR_STEP_FLOOR        = 0.5    # minimum step in points

# fix-sltight (Tier 1 #4): 201/202 initial SL distance. Was 0.2×ATR — inside a
# single M1 bar's normal noise band on Gold, and confirmed from two weeks of
# live data as the single largest loss driver: 1,020 of 2,458 combined 201/202
# trades (41.5%) hit this SL before ever reaching the +0.5R BE-lock milestone,
# for -$2,559.67 — more than the entire net Ghost Grid loss for the period.
# Change 8: widened to 0.8 to give trades more room to breathe.
SCALP_REV_SL_ATR_MULT = 0.35    # HIGH-1: reverted back from 0.8 (and 0.2 before that)

# audit-oob-tp: Hard broker-side TP at +2R failsafe (Change 10).
# Replaces the 3xATR OOB TP with a tighter 2R profit-securing TP for all
# Fluid TP (tp=0.0) legs so gains aren't given back if the watcher dies.
HARD_FAILSAFE_TP_R    = 2.0   # OOB TP = entry ± 2R (broker failsafe)


# ─────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────
logger = logging.getLogger("hunter")
logger.setLevel(logging.INFO)
_fh = logging.handlers.RotatingFileHandler(
    HUNTER_LOG_FILE, maxBytes=2*1024*1024, backupCount=5, encoding="utf-8"
)
_fh.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
_ch = logging.StreamHandler()
_ch.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
logger.addHandler(_fh)
logger.addHandler(_ch)

# ─────────────────────────────────────────────
#  AUDIT CSV
# ─────────────────────────────────────────────
AUDIT_HEADER = [
    "timestamp", "session", "event_type",
    # execution
    "price", "spread", "latency_ms",
    # order details
    "magic", "leg_type", "side", "sl", "tp", "comment",
    # market at execution
    "atr_at_fill", "grid_step_used", "probe_direction",
    # brain state at execution
    "conviction_at_fill", "adx_at_fill", "regime_at_fill",
    # gate decisions (gate_203 removed — Leg 203 eliminated in v5.2)
    "gate_201", "gate_202",
    "h4_direction_at_arm",
    "kr_regime_at_arm",
]

def get_session():
    h = datetime.utcnow().hour
    if  8 <= h < 12: return "LONDON"
    if 12 <= h < 16: return "NY_OVERLAP"
    if 16 <= h < 21: return "NY_CLOSE"
    return "ASIAN"

def log_event(event_type, data):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    row = [
        ts,
        get_session(),
        event_type,
        data.get("price",              ""),
        data.get("spread",             ""),
        data.get("latency_ms",         ""),
        data.get("magic",              ""),
        data.get("leg_type",           ""),
        data.get("side",               ""),
        data.get("sl",                 ""),
        data.get("tp",                 ""),
        data.get("comment",            ""),
        data.get("atr_at_fill",        ""),
        data.get("grid_step_used",     ""),
        data.get("probe_direction",    ""),
        data.get("conviction_at_fill", ""),
        data.get("adx_at_fill",        ""),
        data.get("regime_at_fill",     ""),
        data.get("gate_201",           ""),
        data.get("gate_202",           ""),
        data.get("h4_direction_at_arm", ""),
        data.get("kr_regime_at_arm",    ""),
        # gate_203 removed in v5.2 — Leg 203 eliminated
    ]
    file_exists = os.path.isfile(DATA_LOG_FILE)
    with open(DATA_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not file_exists:
            w.writerow(AUDIT_HEADER)
        w.writerow(row)

# ─────────────────────────────────────────────
#  BRAIN STATE READER
# ─────────────────────────────────────────────
_EMPTY_STATE = {
    "conviction": 50.0, "adx": 0.0, "atr": 0.0,
    "regime": "UNKNOWN", "updated_utc": "",
}

def read_brain_state():
    """
    Read live brain state directly from sniper_watcher (which queries KnowledgeRegister).
    Eliminates CSV file I/O latency. Returns _EMPTY_STATE on any failure.
    """
    try:
        from ghost_super.sniper_watcher import get_market_state
        conviction, adx_val, atr_raw, regime = get_market_state()
        return {
            "conviction": float(conviction),
            "adx": float(adx_val),
            "atr": float(atr_raw),
            "regime": str(regime),
            "updated_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        logger.debug(f"read_brain_state failed: {e}")
        return _EMPTY_STATE.copy()

# ─────────────────────────────────────────────
#  ADAPTIVE THRESHOLD READER
# ─────────────────────────────────────────────
# Hardcoded fallback values — used on cold-start or file error
# v5.2: tf_conv_fire removed — gate 203 no longer exists
_ADAPTIVE_DEFAULTS_HUNTER = {
    "rev_adx_block": 40.0,   # gate 202: block reversal if ADX above this
    "is_adaptive":      0,
}

def read_adaptive_thresholds_hunter():
    """
    Read adaptive_thresholds_live.csv written by the Brain every heartbeat.
    Falls back to hardcoded defaults on any failure — gates never crash.
    v5.2: tf_conv_fire key removed (Leg 203 eliminated).
    """
    try:
        if not os.path.isfile(ADAPTIVE_THRESHOLD_FILE):
            return _ADAPTIVE_DEFAULTS_HUNTER.copy()
        with open(ADAPTIVE_THRESHOLD_FILE, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            return _ADAPTIVE_DEFAULTS_HUNTER.copy()
        row = rows[0]
        return {
            "rev_adx_block": float(row.get("rev_adx_block", _ADAPTIVE_DEFAULTS_HUNTER["rev_adx_block"])),
            "is_adaptive":   int(row.get("is_adaptive",     0)),
        }
    except Exception:
        return _ADAPTIVE_DEFAULTS_HUNTER.copy()


def apply_gates(bs):
    """
    Returns {201: fire, 202: fire} using adaptive thresholds
    derived from the last 60 minutes of real Gold conviction data.

    Falls back to hardcoded v5.2 defaults on cold-start or file error.

    Gate logic:
      201 — always fires (spread guard handled in main loop)
      202 — blocked when ADX > rev_adx_block (P70 of recent ADX)
             also blocked when conviction > GATE_202_CONV_BLOCK (static, unchanged)

    NOTE: gate_203 (Trend-Follow) removed in v5.2.
    Trend entries are now exclusively handled by SuperTrend bot.
    """
    try:
        adx  = float(bs.get("adx",        0))
        conv = float(bs.get("conviction",  0))
    except (TypeError, ValueError):
        adx, conv = 0.0, 50.0

    # Load adaptive thresholds from Brain's calibration
    adaptive      = read_adaptive_thresholds_hunter()
    adx_block_202 = adaptive["rev_adx_block"]   # P70 ADX  (default 40)
    is_adaptive   = adaptive["is_adaptive"]

    gate_201 = True

    # 202: blocked in strong trend — adaptive ADX block + static conviction block
    gate_202 = not (adx > adx_block_202 or conv > GATE_202_CONV_BLOCK)

    logger.debug(
        f"GATES | ADX={round(adx,2)} Conv={round(conv,1)} | "
        f"adx_block202={'[A]' if is_adaptive else '[D]'}{adx_block_202} | "
        f"201={gate_201} 202={gate_202}"
    )

    return {201: gate_201, 202: gate_202}

# ─────────────────────────────────────────────
#  ATR / ADX HELPERS
# ─────────────────────────────────────────────
def _get_atr(df, n=14):
    df = df.copy()
    df["tr"] = pd.concat(
        [df["high"] - df["low"],
         (df["high"] - df["close"].shift()).abs()], axis=1).max(axis=1)
    return float(df["tr"].rolling(n).mean().iloc[-1])

def _get_adx(df, n=14):
    """Returns (adx, +DI, -DI). Available as local fallback reference."""
    df = df.copy()
    df["up"]  = df["high"] - df["high"].shift(1)
    df["dn"]  = df["low"].shift(1) - df["low"]
    df["+dm"] = np.where((df["up"] > df["dn"]) & (df["up"] > 0), df["up"], 0)
    df["-dm"] = np.where((df["dn"] > df["up"]) & (df["dn"] > 0), df["dn"], 0)
    df["tr"]  = pd.concat(
        [df["high"] - df["low"],
         (df["high"] - df["close"].shift()).abs()], axis=1).max(axis=1)
    tr_s  = df["tr"].rolling(n).sum()
    p_di  = 100 * df["+dm"].rolling(n).sum() / tr_s
    m_di  = 100 * df["-dm"].rolling(n).sum() / tr_s
    dx    = 100 * (p_di - m_di).abs() / (p_di + m_di)
    return float(dx.rolling(n).mean().iloc[-1]), float(p_di.iloc[-1]), float(m_di.iloc[-1])

def _get_h4_direction() -> str:
    """
    Returns 'UP', 'DOWN', or 'UNKNOWN' based on whether the last closed
    H4 bar's close is above or below the close 3 bars prior.
    Uses 4 H4 bars: bar[0]=current open, bar[1..3]=last three closed.
    Simple structural bias — not a regime classifier.
    """
    try:
        rates = _api().copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_H4, 0, 4)
        if rates is None or len(rates) < 4:
            return "UNKNOWN"
        last_close = float(rates[-2]["close"])   # last closed bar
        ref_close  = float(rates[-4]["close"])   # 3 bars before that
        if last_close > ref_close:
            return "UP"
        elif last_close < ref_close:
            return "DOWN"
        return "UNKNOWN"
    except Exception:
        return "UNKNOWN"

# ─────────────────────────────────────────────
#  EXECUTION ENGINE
# ─────────────────────────────────────────────
def send_order(order_type, sl, tp, magic, comment,
               atr, probe_direction, leg_type, brain_state, gates, is_shadow=False):
    """
    Two-phase execution:
      Phase 1: Market fill
      Phase 2: SLTP anchor (with raised buffer + retry on 10016)

    v5.1 notes:
      - tp=0.0 signals Fluid TP (Naked Signal). TP stops-level guard is
        intentionally skipped when tp==0.0 to avoid accidental inflation.
      - On 10016 retry, only sl is updated (tp stays 0.0).
      - SL buffer raised to point×25 (was point×20 in v5.0).
      - Retry buffer raised to point×35 (was point×30 in v5.0).
      - Logs ORDER_FILL_V51 on SL success, ORDER_FILL_V51_NO_SL on fail.
    """
    t0          = time.time()
    sym_info    = _api().symbol_info(SYMBOL)
    tick        = _api().symbol_info_tick(SYMBOL)
    if not sym_info or not tick:
        return None
        
    # ── KR Layer 2 & 3: Hard Blocks ──────────────────────────────────────
    from core.knowledge_register import KnowledgeRegister
    kr = KnowledgeRegister()
    kr_dir = 1 if order_type == mt5.ORDER_TYPE_BUY else -1
    
    invalidated, inv_reason = kr.is_entry_invalidated(SYMBOL, kr_dir)
    if invalidated:
        logger.info(f"Entry BLOCKED by KR Layer 2: {inv_reason}")
        return None
        
    account_info = _api().account_info()
    equity = account_info.equity if account_info else 10000.0
    allowed, p_reason = kr.check_portfolio_entry_allowed(
        symbol=SYMBOL,
        direction=kr_dir,
        proposed_risk_pct=0.5,
        account_equity=equity
    )
    if not allowed:
        logger.info(f"Entry BLOCKED by KR Layer 3: {p_reason}")
        return None

    price  = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
    spread = round(tick.ask - tick.bid, 3)
    side   = "BUY" if order_type == mt5.ORDER_TYPE_BUY else "SELL"

    if is_shadow:
        logger.info(f"[GhostSniper] VIRTUAL_FILL magic={magic} ticket=VIRTUAL price={price}")
        from core.knowledge_register import KnowledgeRegister, TradeThesis
        kr = KnowledgeRegister()
        snapshot = kr.get_market_state(SYMBOL, "M15")
        if snapshot:
            thesis = TradeThesis(
                ticket=999999 + magic, # dummy ticket
                magic=magic,
                symbol=SYMBOL,
                direction=1 if order_type == mt5.ORDER_TYPE_BUY else -1,
                bot_id="Ghost",
                setup_type=leg_type,
                fill_price=price,
                fill_time=time.time(),
                entry_atr=atr,
                entry_regime=snapshot.regime,
                entry_conviction=float(brain_state.get("conviction", 0.0)),
                initial_sl=sl,
                initial_tp=tp,
                market_snapshot=snapshot,
                is_virtual=True
            )
            kr.unregister_trade_thesis(999999 + magic)
            kr.register_trade_thesis(thesis)
        return True


    # SL guard (gh-slguard) — dynamic buffer = stops_level + 20% headroom
    # Fixed point*25 buffer was too small for XAUUSD (stops_level 100+ pts)
    stops_level = sym_info.trade_stops_level * sym_info.point
    buf         = max(sym_info.point * 25, stops_level * 0.20)  # at least 20% headroom

    if order_type == mt5.ORDER_TYPE_BUY:
        min_sl = price - stops_level - buf
        if sl > price - stops_level:
            logger.debug(
                f"SL guard BUY: {sl:.3f} too close to {price:.3f} "
                f"(stops={stops_level:.3f}) — widened to {min_sl:.3f}"
            )
            sl = min_sl
    else:
        min_sl = price + stops_level + buf
        if sl < price + stops_level:
            logger.debug(
                f"SL guard SELL: {sl:.3f} too close to {price:.3f} "
                f"(stops={stops_level:.3f}) — widened to {min_sl:.3f}"
            )
            sl = min_sl

    # TP guard — SKIPPED when tp=0.0 (Fluid TP / Naked Signal)
    if tp != 0.0:
        if order_type == mt5.ORDER_TYPE_BUY:
            if tp < price + stops_level: tp = price + stops_level + buf
        else:
            if tp > price - stops_level: tp = price - stops_level - buf

    # audit-oob-tp: Hard broker-side TP failsafe (Change 10).
    # Replaces the 0.0 in the SLTP anchor with a real broker-side TP at 2R.
    # The watcher closes dynamically long before this level — this only fires
    # if Python is offline (crash, restart). Broker handles the exit cleanly.
    # This does NOT affect the Phase 1 market order (which has no TP field).
    oob_tp = tp   # default: use caller's tp (non-zero means caller set a target)
    if tp == 0.0:
        own_risk = abs(price - sl)
        if own_risk > 0:
            if order_type == mt5.ORDER_TYPE_BUY:
                oob_tp = price + own_risk * HARD_FAILSAFE_TP_R
                # Guard: must be at least stops_level above entry
                if oob_tp < price + stops_level + buf:
                    oob_tp = price + stops_level + buf
            else:
                oob_tp = price - own_risk * HARD_FAILSAFE_TP_R
                if oob_tp > price - stops_level - buf:
                    oob_tp = price - stops_level - buf
            oob_tp = round(oob_tp, 3)
            logger.debug(
                f"OOB_TP set | {side} | price={price:.3f} | "
                f"oob_tp={oob_tp:.3f} | {HARD_FAILSAFE_TP_R}R={round(own_risk*HARD_FAILSAFE_TP_R,3)}"
            )

    req = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       SYMBOL,
        "volume":       LOT_SIZE,
        "type":         order_type,
        "price":        price,
        "deviation":    20,
        "magic":        magic,
        "comment":      comment,
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    # ── Phase 1: Market execution ──────────────────────────────────
    result  = _api().order_send(req)
    latency = (time.time() - t0) * 1000

    if not (result and result.retcode == mt5.TRADE_RETCODE_DONE):
        code = result.retcode if result else "NONE"
        if code == 10044:
            logger.warning(
                f"ORDER_SKIP magic={magic} code=10044 — "
                f"no margin or volume limit reached, skipping entry"
            )
            return result   # don't log as error — expected during low-equity
        logger.warning(f"ORDER_ERROR magic={magic} code={code}")
        log_event("ORDER_ERROR", {
            "magic": magic, "leg_type": leg_type, "side": side,
            "comment": f"Err_{code}", "sl": round(sl, 3), "tp": round(oob_tp, 3),
            "latency_ms": round(latency, 1),
            "probe_direction": probe_direction,
            "atr_at_fill": round(atr, 5),
            "conviction_at_fill": brain_state.get("conviction", ""),
            "adx_at_fill":        brain_state.get("adx",        ""),
            "regime_at_fill":     brain_state.get("regime",     ""),
            "gate_201": gates[201], "gate_202": gates[202],
            "h4_direction_at_arm": _get_h4_direction(),
            "kr_regime_at_arm":    brain_state.get("regime", ""),
        })
        return result

    ticket = result.order
    time.sleep(0.15)   # FIX: prevent Err 10027 on rapid dual-send

    # ── Phase 2: SL/TP anchor (retry once on 10016) ────────────────

    # Option 2: recompute SL anchor from actual fill price to prevent 10016
    fill_price = result.price
    own_risk_fill = abs(fill_price - sl)  # preserve original risk distance
    if own_risk_fill > 0:
        if order_type == mt5.ORDER_TYPE_BUY:
            sl = fill_price - own_risk_fill
        else:
            sl = fill_price + own_risk_fill
    
    # Recompute OOB TP from fill price
    if oob_tp != 0.0:
        if order_type == mt5.ORDER_TYPE_BUY:
            oob_tp = fill_price + own_risk_fill * HARD_FAILSAFE_TP_R
            if oob_tp < fill_price + stops_level + buf:
                oob_tp = fill_price + stops_level + buf
        else:
            oob_tp = fill_price - own_risk_fill * HARD_FAILSAFE_TP_R
            if oob_tp > fill_price - stops_level - buf:
                oob_tp = fill_price - stops_level - buf
        oob_tp = round(oob_tp, 3)
    
    sl = round(sl, 3)

    mod_req = {
        "action":   mt5.TRADE_ACTION_SLTP,
        "symbol":   SYMBOL,
        "position": ticket,
        "sl":       sl,
        "tp":       oob_tp,    # audit-oob-tp: 3×ATR failsafe when caller sent tp=0.0
    }
    mod = _api().order_send(mod_req)

    # Retry up to 2 times on 10016 (broker stops-level rejection)
    # Each retry doubles the buffer — guarantees we clear stops_level
    retry_buf = sym_info.point * 50   # start wider than v5.1 (was 35)
    for _retry in range(2):
        if not (mod and mod.retcode == 10016):
            break
        time.sleep(0.2)
        if order_type == mt5.ORDER_TYPE_BUY:
            sl = fill_price - stops_level - retry_buf
        else:
            sl = fill_price + stops_level + retry_buf
        mod_req.update({"sl": round(sl, 3)})
        mod = _api().order_send(mod_req)
        retry_buf *= 2   # double buffer on second attempt

    sl_ok = mod and mod.retcode == mt5.TRADE_RETCODE_DONE

    common = {
        "price":              result.price,
        "spread":             spread,
        "latency_ms":         round(latency, 1),
        "magic":              magic,
        "leg_type":           leg_type,
        "side":               side,
        "sl":                 round(sl, 3),
        "tp":                 round(oob_tp, 3),   # actual broker TP anchored
        "atr_at_fill":        round(atr, 5),
        "grid_step_used":     round(atr * ATR_STEP_MULTIPLIER, 5),
        "probe_direction":    probe_direction,
        "conviction_at_fill": brain_state.get("conviction", ""),
        "adx_at_fill":        brain_state.get("adx",        ""),
        "regime_at_fill":     brain_state.get("regime",     ""),
        "gate_201":  gates[201],
        "gate_202":  gates[202],
        "h4_direction_at_arm": _get_h4_direction(),
        "kr_regime_at_arm":    brain_state.get("regime", ""),
    }

    if sl_ok:
        log_event("ORDER_FILL_V51", {**common, "comment": "SL_APPLIED"})
        logger.info(
            f"FILL_SECURE magic={magic} {side} "
            f"price={result.price} sl={round(sl,3)} tp={round(oob_tp,3)} [OOB] "
            f"lat={round(latency,1)}ms"
        )
        try:
            from data.trade_ledger import set_initial_risk
            set_initial_risk(result.order, abs(result.price - sl))
        except ImportError:
            pass
        # ── Unified Trade Ledger: GHOST ENTRY ────────────────────────────
        if write_trade_event:
            write_trade_event(
                bot="GHOST", event="ENTRY", ticket=result.order,
                symbol=SYMBOL,
                direction=side,
                price=result.price, sl=sl, tp=oob_tp, volume=LOT_SIZE,
                regime=brain_state.get("regime", ""),
                conviction=brain_state.get("conviction", None),
                atr=atr,
                spread_at_event=spread,
                magic=magic,
            )
    else:
        code = mod.retcode if mod else "UNK"
        log_event("ORDER_FILL_V51_NO_SL", {**common, "comment": f"SL_FAIL_{code}"})
        logger.warning(
            f"FILL_NO_SL magic={magic} ticket={ticket} code={code}"
        )

    # ── Register State to KnowledgeRegister ───────────────────────────
    from core.knowledge_register import KnowledgeRegister, TradeThesis
    kr = KnowledgeRegister()
    snapshot = kr.get_market_state(SYMBOL, "M15")
    if snapshot:
        thesis = TradeThesis(
            ticket=result.order,
            magic=magic,
            symbol=SYMBOL,
            direction=1 if order_type == mt5.ORDER_TYPE_BUY else -1,
            bot_id="Ghost",
            setup_type=leg_type,
            fill_price=result.price,
            fill_time=time.time(),
            entry_atr=atr,
            entry_regime=snapshot.regime,
            entry_conviction=float(brain_state.get("conviction", 0.0)),
            initial_sl=sl,
            initial_tp=oob_tp,
            market_snapshot=snapshot
        )
        kr.register_trade_thesis(thesis)

    return result

# ─────────────────────────────────────────────
#  MAIN HUNTER LOOP
# ─────────────────────────────────────────────
def run_hunter():
    # fix-secrets: fail loudly on a missing credential rather than attempting a
    # login with an empty password and reporting it as a generic connect failure.
    if not PASSWORD:
        logger.error(
            "No MT5 password available. Put it in ghost_super/config.json "
            "(gitignored) or export MT5_PASSWORD."
        )
        return

    if not mt5.initialize(
        path=MT5_PATH, login=ACCOUNT, password=PASSWORD, server=SERVER
    ):
        logger.error(f"MT5 connect failed. Path: {MT5_PATH}")
        return

    logger.info(
        "HUNTER v5.2 ONLINE | Leg 203 REMOVED (SuperTrend owns trend entries) | "
        "Gate: 202 blocks ADX>40|Conv>60 | "
        f"Step: {ATR_STEP_MULTIPLIER}×ATR | Fluid TP: Brain owns all exits"
    )

    armed, break_level, probe_extreme = None, 0.0, 0.0
    armed_at    = 0.0   # timestamp when probe armed (stale timeout)
    daily_pairs = 0
    today       = date.today()

    try:
        while True:
            try:
                # ── Daily reset ─────────────────────────────────────────
                if date.today() != today:
                    logger.info(f"Daily reset: pairs_yesterday={daily_pairs}")
                    daily_pairs = 0
                    today = date.today()

                # ── Market data ─────────────────────────────────────────
                tick  = _api().symbol_info_tick(SYMBOL)
                rates = _api().copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M1, 0, 50)
                if not tick or rates is None or len(rates) < 20:
                    time.sleep(1)
                    continue

                df            = pd.DataFrame(rates)
                atr           = _get_atr(df)
                dynamic_step  = max(atr * ATR_STEP_MULTIPLIER, ATR_STEP_FLOOR)
                current_price = (tick.bid + tick.ask) / 2
                spread        = tick.ask - tick.bid

                # ── Probe detection ─────────────────────────────────────
                if armed is None:
                    bs = read_brain_state()
                    bs_regime = bs.get("regime", "")
                    
                    if bs_regime in ("TRENDING_UP", "TRENDING_DOWN", "UNKNOWN"):
                        from core.knowledge_register import KnowledgeRegister
                        kr_dir = 1 if bs_regime == "TRENDING_DOWN" else (-1 if bs_regime == "TRENDING_UP" else 0)
                        if kr_dir != 0:
                            KnowledgeRegister().publish_invalidation(
                                symbol=SYMBOL,
                                direction=kr_dir,
                                source_bot="Ghost",
                                reason=f"Ghost regime-arm-gate blocked probe: {bs_regime}",
                                ttl_seconds=300.0
                            )
                        time.sleep(1)
                        continue
                        
                    recent_high = df["high"].iloc[-5:].max()
                    recent_low  = df["low"].iloc[-5:].min()


                    # F6 Cross-bot gate: block UP_PROBE when ST holds confirmed LONG
                    st_long_active = False
                    try:
                        from core.knowledge_register import KnowledgeRegister
                        kr = KnowledgeRegister()
                        for thesis in kr._theses.values():
                            if (thesis.symbol == "XAUUSDm" and 
                                thesis.bot_id in ("SuperTrend", "ST") and
                                thesis.direction == 1):
                                st_long_active = True
                                break
                    except Exception:
                        pass  # fail open — never block on KR read failure
                    
                    if SYMBOL == "XAUUSDm" and st_long_active and current_price > recent_high:
                        logger.info(
                            f"GHOST_ARM_BLOCKED_ST_LONG | "
                            f"price={round(current_price,3)} | "
                            f"ST LONG thesis active on XAUUSDm — suppressing UP_PROBE"
                        )
                        # Skip arming, continue loop
                        time.sleep(1)
                        continue

                    # F15: block DOWN_PROBE when H4 structural direction is DOWN
                    try:
                        h4_dir = _get_h4_direction()
                    except Exception:
                        h4_dir = "UNKNOWN"

                    if current_price < recent_low and h4_dir == "DOWN":
                        logger.info(
                            f"GHOST_ARM_BLOCKED_H4_DOWN | "
                            f"price={round(current_price,3)} | "
                            f"h4={h4_dir} — DOWN_PROBE suppressed"
                        )
                        time.sleep(1)
                        continue

                    # H22 NY_OVERLAP session gate: block all probe arming during NY_OVERLAP
                    # Evidence: three consecutive weeks avg P&L < -$0.68/tr, n>=10 each week
                    try:
                        _current_session = get_session()
                    except Exception:
                        _current_session = "UNKNOWN"
                    if _current_session == "NY_OVERLAP":
                        logger.info(
                            f"GHOST_ARM_BLOCKED_SESSION | "
                            f"session={_current_session} | "
                            f"price={round(current_price,3)} — probe arming suppressed"
                        )
                        time.sleep(1)
                        continue

                    if current_price > recent_high:
                        armed         = "UP_PROBE"
                        probe_extreme = current_price
                        break_level   = current_price - dynamic_step
                        ghost_cache   = GhostCache(
                            probe_direction="UP_PROBE",
                            probe_origin=break_level,
                            probe_extreme=current_price,
                            atr_step=dynamic_step,
                            n_layers=N_LAYERS_DEFAULT,
                        )
                        log_event("ARMED", {
                            "price":          round(current_price, 3),
                            "atr_at_fill":    round(atr, 5),
                            "spread":         round(spread, 3),
                            "comment":        "UP_PROBE",
                            "grid_step_used": round(dynamic_step, 5),
                            "h4_direction_at_arm": _get_h4_direction(),
                            "kr_regime_at_arm":    bs.get("regime", ""),
                        })
                        logger.warning(
                            f"ARMED UP | price={round(current_price,3)} "
                            f"step={round(dynamic_step,3)} "
                            f"atr={round(atr,5)}"
                        )
                    elif current_price < recent_low:
                        armed         = "DOWN_PROBE"
                        probe_extreme = current_price
                        break_level   = current_price + dynamic_step
                        ghost_cache   = GhostCache(
                            probe_direction="DOWN_PROBE",
                            probe_origin=break_level,
                            probe_extreme=current_price,
                            atr_step=dynamic_step,
                            n_layers=N_LAYERS_DEFAULT,
                        )
                        log_event("ARMED", {
                            "price":          round(current_price, 3),
                            "atr_at_fill":    round(atr, 5),
                            "spread":         round(spread, 3),
                            "comment":        "DOWN_PROBE",
                            "grid_step_used": round(dynamic_step, 5),
                            "h4_direction_at_arm": _get_h4_direction(),
                            "kr_regime_at_arm":    bs.get("regime", ""),
                        })
                        logger.warning(
                            f"ARMED DN | price={round(current_price,3)} "
                            f"step={round(dynamic_step,3)} "
                            f"atr={round(atr,5)}"
                        )

                else:
                    # ── Track probe extreme and update break level ────────
                    if armed == "UP_PROBE":
                        if current_price > probe_extreme:
                            probe_extreme = current_price
                            break_level   = current_price - dynamic_step
                        trigger = current_price < break_level
                    else:
                        if current_price < probe_extreme:
                            probe_extreme = current_price
                            break_level   = current_price + dynamic_step
                        trigger = current_price > break_level

                    # gc-hunter: update GhostCache every tick
                    # Runs independently — 204 fires at nth virtual layer
                    # Only update when not already triggering 201/202/203
                    if ghost_cache is not None and not trigger:
                        gc_signal = ghost_cache.update(current_price, atr)
                        if gc_signal is not None:
                            gc_type = (mt5.ORDER_TYPE_SELL
                                       if gc_signal["order_type"] == "SELL"
                                       else mt5.ORDER_TYPE_BUY)
                            send_order(
                                gc_type, gc_signal["sl"], 0.0,
                                MAGIC_GHOST_CACHE, "SNIPER_GC",
                                atr, armed, "GHOST_CACHE", bs, gates,
                            )
                            log_event("GHOST_CACHE_FIRE", {
                                **gc_signal,
                                "atr_at_fill":     round(atr, 5),
                                "regime_at_fill":  bs.get("regime", ""),
                                "probe_direction": armed,
                            })
                            logger.warning(
                                f"GHOST_CACHE_FIRE magic=204 | "
                                f"layer_depth={gc_signal['virtual_layer_depth']} | "
                                f"sl={gc_signal['sl']:.3f}"
                            )

                    if trigger:
                        # -- M1 retrace structure at fire (LOGGING ONLY) ------
                        # Placed BEFORE spread/cap guards so quality is captured
                        # even on blocked fires.
                        try:
                            _retrace_rates = _api().copy_rates_from_pos(
                                SYMBOL, mt5.TIMEFRAME_M1, 0, 5
                            )
                            committed_bars = 0
                            retrace_body_ratio = 0.0
                            if _retrace_rates is not None and len(_retrace_rates) >= 2:
                                for _bar in _retrace_rates[-3:]:
                                    _bar_bull = _bar["close"] > _bar["open"]
                                    _bar_range = max(_bar["high"] - _bar["low"], 0.0001)
                                    _bar_body = abs(_bar["close"] - _bar["open"])
                                    _body_ratio = _bar_body / _bar_range

                                    if armed == "UP_PROBE" and not _bar_bull and _body_ratio > 0.35:
                                        committed_bars += 1
                                    elif armed == "DOWN_PROBE" and _bar_bull and _body_ratio > 0.35:
                                        committed_bars += 1

                                _last = _retrace_rates[-2]
                                _last_range = max(_last["high"] - _last["low"], 0.0001)
                                retrace_body_ratio = abs(_last["close"] - _last["open"]) / _last_range

                            logger.info(
                                f"GHOST_FIRE_QUALITY | {armed} | "
                                f"committed_reversal_bars={committed_bars}/3 | "
                                f"trigger_bar_body_ratio={retrace_body_ratio:.3f} | "
                                f"atr={round(atr,5)}"
                            )
                        except Exception as _gq:
                            logger.debug(f"Ghost fire quality log error: {_gq}")

                        # ── Pre-fire checks ──────────────────────────────
                        if spread > SPREAD_MAX:
                            log_event("SKIP_SPREAD", {
                                "price":           round(current_price, 3),
                                "spread":          round(spread, 3),
                                "probe_direction": armed,
                            })
                            logger.info(f"SKIP_SPREAD spread={round(spread,3)}")
                            armed       = None
                            ghost_cache = None
                            continue

                        if daily_pairs >= MAX_DAILY_PAIRS:
                            log_event("SKIP_DAILY_CAP", {
                                "price":   round(current_price, 3),
                                "comment": f"pairs={daily_pairs}",
                            })
                            armed       = None
                            ghost_cache = None
                            continue

                        # ── Read brain state + apply gates (single read) ──
                        bs      = read_brain_state()
                        gates   = apply_gates(bs)
                        bs_adx  = float(bs.get("adx", 0))
                        bs_conv = float(bs.get("conviction", 50))

                        # ── SL geometry (v5.1 Slab C Grace) ─────────────
                        # fix-sltight: Scalp/Reversal legs widened from
                        # 0.2×ATR to SCALP_REV_SL_ATR_MULT (0.35×ATR) — see
                        # constant definition above for the data behind this.
                        # Trend-Follow leg:    0.5 × ATR (wider — liquidity room)
                        sl_dist_tight = SCALP_REV_SL_ATR_MULT * atr

                        # Direction for reversal vs trend-follow
                        dir_rev    = (mt5.ORDER_TYPE_SELL if armed == "UP_PROBE"
                                      else mt5.ORDER_TYPE_BUY)
                        dir_follow = (mt5.ORDER_TYPE_BUY if armed == "UP_PROBE"
                                      else mt5.ORDER_TYPE_SELL)

                        # SL for reversal legs (201, 202) — MUST be on loss side:
                        #   UP_PROBE  → we SELL the reversal → SL ABOVE probe_extreme
                        #               (protects if price keeps rising past the high)
                        #   DOWN_PROBE → we BUY the reversal → SL BELOW probe_extreme
                        #               (protects if price keeps falling past the low)
                        sl_rev  = (probe_extreme + sl_dist_tight if armed == "UP_PROBE"
                                   else probe_extreme - sl_dist_tight)

                        fired_any = False

                        logger.info(
                            f"FIRE {armed} | "
                            f"price={round(current_price,3)} "
                            f"adx={round(bs_adx,2)} conv={round(bs_conv,1)} "
                            f"regime={bs.get('regime','')} | "
                            f"gates 201={gates[201]} 202={gates[202]}"
                        )

                        # ── Legs 202 (Reversal) and 201 (Scalp) firing logic ──
                        legs_fired_this_probe = 0
                        
                        # We prioritize 202 (Reversal) over 201 (Scalp)
                        if gates[202] and legs_fired_this_probe < MAX_LEGS_PER_PROBE:
                            send_order(
                                dir_rev, sl_rev, 0.0,
                                MAGIC_REVERSAL, "SNIPER_R",
                                atr, armed, "REVERSAL", bs, gates,
                            )
                            fired_any = True
                            legs_fired_this_probe += 1
                            time.sleep(0.15)
                        elif not gates[202]:
                            logger.info(
                                f"GATE_BLOCK 202 | "
                                f"adx={round(bs_adx,2)} conv={round(bs_conv,1)}"
                            )
                            log_event("GATE_BLOCK", {
                                "magic":              202,
                                "leg_type":           "REVERSAL",
                                "probe_direction":    armed,
                                "conviction_at_fill": bs_conv,
                                "adx_at_fill":        bs_adx,
                                "regime_at_fill":     bs.get("regime", ""),
                                "gate_201":  gates[201],
                                "gate_202":  gates[202],
                                "comment": (
                                    f"BLOCKED_ADX>{GATE_202_ADX_BLOCK}"
                                    if bs_adx > GATE_202_ADX_BLOCK
                                    else f"BLOCKED_CONV>{GATE_202_CONV_BLOCK}"
                                ),
                            })

                        if gates[201]:
                            # Shadow leg fires 100% of the time independent of max legs limit
                            send_order(
                                dir_rev, sl_rev, 0.0,
                                MAGIC_SCALP, "SNIPER_S",
                                atr, armed, "SCALP", bs, gates,
                                is_shadow=True
                            )
                            fired_any = True
                            legs_fired_this_probe += 1
                            time.sleep(0.15)

                        # NOTE: Leg 203 (Trend-Follow) removed in v5.2.
                        # SuperTrend bot (si_confirmed=0.55) handles all trend entries.

                        if fired_any:
                            daily_pairs += 1

                        armed       = None
                        # 204 DECOUPLE: ghost_cache persists after 202 fire.
                        # Reset happens only when the outer probe cycle ends (armed=None
                        # at top of detection loop). GhostCache.invalidated handles the
                        # case where price extends too far (trend, not exhaustion).
                        time.sleep(COOLDOWN_SECONDS)

            except Exception as exc:
                logger.error(
                    f"HUNTER_EXCEPTION {type(exc).__name__}: {exc}",
                    exc_info=True
                )
                time.sleep(5)

            time.sleep(0.01)

    except KeyboardInterrupt:
        logger.info("Hunter stopped manually.")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    run_hunter()
