"""
==================================================================
                 CAB MASTER - TRADE MANAGER
==================================================================
Monitors active positions, updates MFE/MAE state memory,
handles trailing stops, executes protective trade closures,
and records the Market Intelligencia snapshot upon entry.
Enhanced with R-velocity timestamps and gate-hit tracking.
==================================================================
"""

import MetaTrader5 as mt5
import time
import logging
import config
from utils import _get_filling_mode
import ledger
from signals import check_h4_inversion, check_h1_structural_breach
from analytics.intelligencia import get_entry_intelligence

def _close_position(pos, reason: str) -> bool:
    """Closes an active position and triggers ledger audit."""
    tick = mt5.symbol_info_tick(pos.symbol)
    if tick is None: 
        return False
        
    exit_price = tick.bid if pos.type == 0 else tick.ask
    
    req = {
        "action": mt5.TRADE_ACTION_DEAL, 
        "position": pos.ticket, 
        "symbol": pos.symbol,
        "volume": pos.volume, 
        "type": mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
        "price": exit_price, 
        "deviation": 20, 
        "magic": config.MAGIC_NUMBER,
        "comment": reason[:31], 
        "type_time": mt5.ORDER_TIME_GTC, 
        "type_filling": _get_filling_mode(pos.symbol)
    }
    
    res = mt5.order_send(req)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        logging.info(f"KILLED #{pos.identifier} [{pos.symbol}] | Reason: {reason}")
        ledger.write_to_performance_ledger(pos, reason, exit_price)
        if pos.identifier in ledger.tracked_ids:
            ledger.tracked_ids.discard(pos.identifier)
        return True
    return False

# ── Hard loss caps (fix-loss-cap) ─────────────────────────────────────────────
# Nothing bounded floating loss in this bot. The Sep-12 audit found up to 16 concurrent
# positions with 198 of 206 trades overlapping at least two others, and a -$2,208
# BROKER_SL cohort; the sibling standalone bot let a single leg reach -$5,741.
# Measured on FLOATING loss at the top of the cycle: the failure mode is one leg
# running to a catastrophic stop while every other guard stays silent.
SYMBOL_LOSS_CAP_PCT    = getattr(config, "SYMBOL_LOSS_CAP_PCT", 0.02)
PORTFOLIO_LOSS_CAP_PCT = getattr(config, "PORTFOLIO_LOSS_CAP_PCT", 0.05)

_CAP_START_EQUITY = None

def enforce_loss_caps(positions) -> int:
    """
    Flattens CAB MASTER positions when floating loss breaches the per-symbol or
    portfolio cap. Returns the number of positions closed. Never raises.

    Portfolio cap first (largest blast radius), weakest legs first; the per-symbol cap
    then covers a single leg bleeding to a full stop.
    """
    global _CAP_START_EQUITY
    try:
        acct = mt5.account_info()
        if acct is None or acct.equity <= 0:
            return 0
        if _CAP_START_EQUITY is None:
            _CAP_START_EQUITY = acct.equity
            logging.info(
                f"[LOSS CAP] Armed | base equity=${_CAP_START_EQUITY:.2f} | "
                f"symbol cap={SYMBOL_LOSS_CAP_PCT:.0%} "
                f"(${_CAP_START_EQUITY * SYMBOL_LOSS_CAP_PCT:.2f}) | "
                f"portfolio cap={PORTFOLIO_LOSS_CAP_PCT:.0%} "
                f"(${_CAP_START_EQUITY * PORTFOLIO_LOSS_CAP_PCT:.2f})"
            )

        if not positions:
            return 0
        ours = [p for p in positions if p.magic == config.MAGIC_NUMBER]
        if not ours:
            return 0

        def floating(p):
            return p.profit + (getattr(p, "swap", 0.0) or 0.0)

        closed = 0
        port_cap = _CAP_START_EQUITY * PORTFOLIO_LOSS_CAP_PCT
        total = sum(floating(p) for p in ours)
        if total <= -port_cap:
            logging.warning(
                f"[LOSS CAP] PORTFOLIO floating ${total:.2f} <= -${port_cap:.2f} — "
                f"flattening all {len(ours)} CAB MASTER leg(s), weakest first"
            )
            for p in sorted(ours, key=floating):
                if _close_position(p, "LOSS_CAP_PORTFOLIO"):
                    closed += 1
            return closed

        sym_cap = _CAP_START_EQUITY * SYMBOL_LOSS_CAP_PCT
        by_sym = {}
        for p in ours:
            by_sym.setdefault(p.symbol, []).append(p)
        for sym, legs in by_sym.items():
            sym_floating = sum(floating(p) for p in legs)
            if sym_floating <= -sym_cap:
                logging.warning(
                    f"[LOSS CAP] {sym} floating ${sym_floating:.2f} <= -${sym_cap:.2f} — "
                    f"flattening {len(legs)} leg(s)"
                )
                for p in sorted(legs, key=floating):
                    if _close_position(p, "LOSS_CAP_SYMBOL"):
                        closed += 1
        return closed
    except Exception as e:
        logging.error(f"[LOSS CAP] check failed: {e}")
        return 0

def _modify_sl(pos, new_sl: float) -> bool:
    """Modifies the stop loss for an active position."""
    sym_info = mt5.symbol_info(pos.symbol)
    if sym_info is None: 
        return False
        
    req = {
        "action": mt5.TRADE_ACTION_SLTP, 
        "position": pos.ticket, 
        "sl": round(new_sl, sym_info.digits), 
        "tp": 0.0
    }
    res = mt5.order_send(req)
    return res is not None and res.retcode == mt5.TRADE_RETCODE_DONE

def manage_open_trades() -> None:
    """Main loop for updating trade states, trailing stops, and protective checks."""
    positions = mt5.positions_get()
    active_ids = [p.identifier for p in positions if p.magic == config.MAGIC_NUMBER] if positions else []

    # fix-loss-cap: hard caps run before any management or trailing logic, so a blown
    # book is flattened before trailing decisions are made on it.
    closed_by_cap = enforce_loss_caps(positions)
    if closed_by_cap:
        logging.warning(f"[LOSS CAP] flattened {closed_by_cap} position(s) this cycle")
        positions = mt5.positions_get()
        active_ids = [p.identifier for p in positions if p.magic == config.MAGIC_NUMBER] if positions else []

    # Sync any trades that were closed by the broker (SL/TP) before processing active ones
    ledger.sync_broker_closed_positions(active_ids)

    if not positions: 
        return

    for pos in positions:
        if pos.magic != config.MAGIC_NUMBER or pos.symbol not in config.SYMBOLS: 
            continue
        
        pos_id = pos.identifier
        ledger.tracked_ids.add(pos_id) 
        is_buy = (pos.type == 0)
        
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None: 
            continue
            
        current_price = tick.bid if is_buy else tick.ask
        now_ts = time.time()

        # 1. Establish Risk Distance & Capture Entry Intelligencia Snapshot
        if pos_id not in ledger.entry_risk:
            dist = abs(pos.price_open - pos.sl)
            if dist > 0: 
                ledger.entry_risk[pos_id] = dist
                
                # --- TRIGGER ENHANCED INTELLIGENCIA SNAPSHOT ---
                if pos_id not in ledger.entry_intelligence:
                    ledger.entry_intelligence[pos_id] = get_entry_intelligence(pos.symbol, direction="BUY" if is_buy else "SELL")
            else: 
                continue
            
        risk_dist = max(ledger.entry_risk[pos_id], 0.00001)
        price_move = (current_price - pos.price_open) if is_buy else (pos.price_open - current_price)
        current_r = price_move / risk_dist

        # 2. Update MFE and MAE State Memory + timestamps
        if pos_id not in ledger.mfe_tracker:
            ledger.mfe_tracker[pos_id] = current_price
            ledger.mfe_time[pos_id] = now_ts
        if pos_id not in ledger.mae_tracker:
            ledger.mae_tracker[pos_id] = current_price
            ledger.mae_time[pos_id] = now_ts
        
        if is_buy:
            if current_price > ledger.mfe_tracker[pos_id]:
                ledger.mfe_tracker[pos_id] = current_price
                ledger.mfe_time[pos_id] = now_ts
            if current_price < ledger.mae_tracker[pos_id]:
                ledger.mae_tracker[pos_id] = current_price
                ledger.mae_time[pos_id] = now_ts
        else:
            if current_price < ledger.mfe_tracker[pos_id]:
                ledger.mfe_tracker[pos_id] = current_price
                ledger.mfe_time[pos_id] = now_ts
            if current_price > ledger.mae_tracker[pos_id]:
                ledger.mae_tracker[pos_id] = current_price
                ledger.mae_time[pos_id] = now_ts

        # --- PATH CLOCKS (observation-layer, no strategy impact) ---
        hours_open = (now_ts - pos.time) / 3600.0

        # Compute peak_r from existing MFE state (same math as section 4)
        peak_move = ((ledger.mfe_tracker[pos_id] - pos.price_open)
                     if is_buy else
                     (pos.price_open - ledger.mfe_tracker[pos_id]))
        peak_r = peak_move / risk_dist

        if pos_id not in ledger.time_to_0_3r and peak_r >= 0.3:
            ledger.time_to_0_3r[pos_id] = round(hours_open, 3)
        if pos_id not in ledger.time_to_0_5r and peak_r >= 0.5:
            ledger.time_to_0_5r[pos_id] = round(hours_open, 3)

        # MAE trough R from worst-price tracker (direction-aware)
        worst_p = ledger.mae_tracker.get(pos_id, pos.price_open)
        mae_move = ((pos.price_open - worst_p) if is_buy
                    else (worst_p - pos.price_open))
        mae_r_clock = mae_move / risk_dist  # negative when adverse

        if pos_id not in ledger.time_to_mae_0_5 and mae_r_clock <= -0.5:
            ledger.time_to_mae_0_5[pos_id] = round(hours_open, 3)

        # 3. Protective Sentinel Checks

        h4_signal = check_h4_inversion(pos.symbol)
        if (is_buy and h4_signal == "BEARISH") or (not is_buy and h4_signal == "BULLISH"):
            _close_position(pos, "OPP_H4_SIGNAL")
            continue

        # Data-backed H1 structural breach suppression (age threshold per volatility group)
        h1_min = config.PAIRS.get(pos.symbol, {}).get("H1_MIN_HOURS", 6.0)
        if hours_open >= h1_min:
            if check_h1_structural_breach(pos.symbol, is_buy):
                _close_position(pos, "H1_STRUCT_BREACH")
                continue

        if hours_open >= config.STAGNATION_HOURS and current_r < 0.5:
            _close_position(pos, "STAGNATION_DECAY")
            continue

        # 4. Configured Trailing & Gate Execution + gate-hit flags
        updated_best = ledger.mfe_tracker[pos_id]
        pair_conf = config.PAIRS.get(pos.symbol, {})
        be_gate_r = pair_conf.get("BE_GATE_R", 1.0)
        lock_gate_r = pair_conf.get("LOCK_GATE_R", 1.5)
        
        peak_move = (updated_best - pos.price_open) if is_buy else (pos.price_open - updated_best)
        peak_r = peak_move / risk_dist
        
        # Record gate hits (for statistical analysis of trailing effectiveness)
        if peak_r >= be_gate_r:
            ledger.be_hit[pos_id] = True
        if peak_r >= lock_gate_r:
            ledger.lock_hit[pos_id] = True
        
        target_sl = pos.sl
        if peak_r >= lock_gate_r:
            # Trailing Phase: 1R behind peak
            target_sl = updated_best - risk_dist if is_buy else updated_best + risk_dist
        elif peak_r >= be_gate_r:
            # Break-Even Phase: Lock Open Price + 5% buffer
            buffer = risk_dist * 0.05
            target_sl = pos.price_open + buffer if is_buy else pos.price_open - buffer
            
        if is_buy and target_sl > pos.sl:
            _modify_sl(pos, target_sl)
        elif not is_buy and target_sl < pos.sl and pos.sl > 0:
            _modify_sl(pos, target_sl)

        # --- fix-stop-tail: half-risk tightening before the BE gate ever arms ------
        # 26 of 167 ledger rows are BROKER_SL exits realising a full -0.981R and they
        # cost -$2,208 — more than the whole segment's net loss (Sep-12 audit). The BE
        # gate only arms after a +0.5R peak, so a trade that never goes in favour has no
        # protection at all until the broker stop arrives. Once a trade is this old and
        # still has not armed the BE gate, its stop is pulled in to half the initial risk.
        # Mutually exclusive with the gate block above: peak_r >= BE_GATE_R sets be_hit
        # in the same cycle, so this only runs for trades that never armed a gate.
        half_risk_hours = getattr(config, "HALF_RISK_AFTER_HOURS", 0.0)
        if (half_risk_hours > 0
                and hours_open >= half_risk_hours
                and pos_id not in ledger.be_hit):
            half_risk_sl = (pos.price_open - risk_dist * 0.5) if is_buy \
                else (pos.price_open + risk_dist * 0.5)
            tighter = (is_buy and half_risk_sl > pos.sl) or \
                      (not is_buy and (pos.sl == 0 or half_risk_sl < pos.sl))
            if tighter and _modify_sl(pos, half_risk_sl):
                logging.info(
                    f"[MANAGEMENT] #{pos_id} [{pos.symbol}] half-risk stop armed | "
                    f"age={hours_open:.1f}h peak_r={peak_r:+.2f} "
                    f"(< BE gate {be_gate_r}R) | SL -> {half_risk_sl:.5f}"
                )