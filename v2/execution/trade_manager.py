import csv
import logging
import os
import time
from datetime import datetime

# fix-parity-cleanup: 'import pandas as pd' was removed here — its only consumer
# was the deleted _manage_trend_bots() (the H1 structural-invalidation read).
import MetaTrader5 as mt5
from v2.core.knowledge_register import KnowledgeRegister
from v2.execution.grid_state import GridState
from v2.execution.cab_legacy_manager import CABLegacyManager

logger = logging.getLogger("TradeManager")

# ── V2 EXIT LEDGER (fix-v2-exit-ledger) ───────────────────────────────────────
# V2 had no exit-side record of any kind. v2_trade_ledger.jsonl is written by
# knowledge_register.unregister_trade_thesis() at thesis closure and carries entry
# fields only: no exit price, no P&L, no exit reason, no event type. The Sep-12 audit
# could not compute a single V2 outcome without joining out to an MT5 HTML export,
# and could not attribute stops vs targets vs logic exits at all — while cab_super,
# cab_multi_pair and the standalone bot all publish an outcome series.
# This appends one row per closed V2 position, including broker-closed ones, so V2
# trade outcomes stop depending on an external export.
V2_LEDGER_FILE = "v2_exit_ledger.csv"

# fix-v2-exit-class: broker-closed rows used to be labelled from the SIGN of the closed
# P&L alone, so every break-even scratch produced by the V1 BE-lock (SL parked 30 points
# from entry ⇒ a 3-cent retest on XAUUSDm closes the leg at +$0.03) was written as
# "BROKER_TP". 368 of the 1,266 V2 Ghost-202 trades in the Sep-12 audit are exactly
# that: +$0.03 each, 56% of every recorded "winner". Read naively they describe a 52%
# win-rate strategy with an inverted 0.73 payoff, when the resolved cohort is actually
# 284 TP at +$4.72 against 531 SL at -$2.99 — a 1.66 payoff. Exits are now classified
# from realised R, and BE_SCRATCH gets its own class so the scratch cohort can be
# counted or excluded without anybody touching the trade path.
BE_SCRATCH_R_BAND = 0.10   # |realised R| within this band == a break-even scratch

V2_LEDGER_COLUMNS = [
    "Ticket", "Symbol", "BotSystem", "SetupType", "Direction", "Volume",
    "OpenTime", "CloseTime", "DurationHours",
    "EntryPrice", "ExitPrice", "InitialSL",
    "RiskDistancePrice", "EntryRiskMoney", "Realized_R", "Realized_USD",
    "ExitReason", "ExitClass", "BrokerClosed", "LayerDepth",
    "RegimeAtEntry", "EntryATR", "EntryConviction",
    "ArmingH4Direction", "ArmingM15Regime",
]

_LEDGER_WRITTEN = set()


def _prepare_v2_ledger_file() -> None:
    """
    Ensures v2_exit_ledger.csv carries the canonical header, archiving a drifted file first.

    Corrective, not hypothetical: the cab_multi_pair ledger on this same estate drifted
    from a 20-column header to a 34-key row dict, and every append after that point landed
    under the wrong column names — Intel_Session holding floats, Intel_ATR_State holding
    booleans. A drifted header cannot be relabelled because the misaligned rows are
    unrecoverable, so the old file is preserved and a correctly-aligned one started.
    """
    try:
        if not os.path.isfile(V2_LEDGER_FILE):
            return
        with open(V2_LEDGER_FILE, "r", newline="") as f:
            first = f.readline().strip()
        header = next(csv.reader([first])) if first else []
        if header == V2_LEDGER_COLUMNS:
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive = f"{V2_LEDGER_FILE}.legacy-{stamp}.csv"
        os.replace(V2_LEDGER_FILE, archive)
        logger.warning(
            f"V2 EXIT LEDGER SCHEMA DRIFT: existing header had {len(header)} columns, "
            f"current schema has {len(V2_LEDGER_COLUMNS)}. Archived to {archive} and "
            f"starting a correctly-aligned ledger."
        )
    except Exception as e:
        logger.error(f"Could not prepare V2 exit ledger: {e}")


def _classify_exit(reason, realized_r) -> str:
    """
    Exit class from realised R — never from the sign of P&L alone (see BE_SCRATCH_R_BAND).

    Returns one of TP / SL / BE_SCRATCH / LOGIC / BROKER / UNKNOWN.
    """
    broker = "BROKER" in str(reason)
    if realized_r is None:
        return "BROKER" if broker else ("LOGIC" if reason else "UNKNOWN")
    if abs(realized_r) <= BE_SCRATCH_R_BAND:
        return "BE_SCRATCH"
    if broker:
        return "TP" if realized_r > 0 else "SL"
    return "LOGIC"

def _v2_risk_money(gateway, symbol, volume, risk_dist_price) -> float:
    """Money risked by `volume` lots across `risk_dist_price`. 0.0 when uncomputable."""
    try:
        if volume <= 0 or risk_dist_price <= 0:
            return 0.0
        si = gateway.symbol_info(symbol)
        if si is None or si.point <= 0 or si.trade_tick_size <= 0:
            return 0.0
        point_value = si.trade_tick_value / (si.trade_tick_size / si.point)
        return (risk_dist_price / si.point) * point_value * float(volume)
    except Exception:
        return 0.0

def write_v2_exit_record(gateway, *, ticket, symbol, direction, volume, entry_price,
                         exit_price, initial_sl, reason, open_time, close_ts,
                         thesis=None, broker_closed=False, profit=None) -> None:
    """
    Appends one closed-trade record to the V2 exit ledger. Never raises, and never
    writes the same ticket twice within a process — analytics must not be able to
    break the trade path, and a duplicate row would double-count an outcome.
    """
    try:
        if ticket in _LEDGER_WRITTEN:
            return

        is_buy = (direction == 1)
        risk_dist = 0.0
        if initial_sl and entry_price:
            risk_dist = abs(float(entry_price) - float(initial_sl))

        realized_r = None
        if risk_dist > 0:
            move = (float(exit_price) - float(entry_price)) if is_buy \
                else (float(entry_price) - float(exit_price))
            realized_r = round(move / risk_dist, 4)

        def _ts(value):
            try:
                return datetime.fromtimestamp(float(value)).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                return ""

        duration_hours = None
        if open_time:
            try:
                duration_hours = round((float(close_ts) - float(open_time)) / 3600.0, 3)
            except Exception:
                duration_hours = None

        # A broker close carries no bot-supplied reason, so derive it from realised R.
        # This is the whole point of the change: "profit > 0 ⇒ TP" wrote the BE-lock
        # scratch cohort into the ledger as winners.
        if broker_closed and realized_r is not None:
            if abs(realized_r) <= BE_SCRATCH_R_BAND:
                reason = "BROKER_BE_SCRATCH"
            elif realized_r > 0:
                reason = "BROKER_TP"
            else:
                reason = "BROKER_SL"
        elif reason is None:
            reason = "BROKER_CLOSE" if broker_closed else "LOGIC_EXIT"

        exit_class = _classify_exit(reason, realized_r)

        row = {
            "Ticket": ticket,
            "Symbol": symbol,
            "BotSystem": getattr(thesis, "bot_system", "") if thesis else "",
            "SetupType": getattr(thesis, "setup_type", "") if thesis else "",
            "Direction": "BUY" if is_buy else "SELL",
            "Volume": volume,
            "OpenTime": _ts(open_time),
            "CloseTime": _ts(close_ts),
            "DurationHours": duration_hours,
            "EntryPrice": entry_price,
            "ExitPrice": exit_price,
            "InitialSL": initial_sl,
            "RiskDistancePrice": round(risk_dist, 5),
            "EntryRiskMoney": round(_v2_risk_money(gateway, symbol, volume, risk_dist), 2),
            "Realized_R": realized_r,
            "Realized_USD": round(profit, 2) if profit is not None else "",
            "ExitReason": reason,
            "ExitClass": exit_class,
            "BrokerClosed": broker_closed,
            "LayerDepth": getattr(thesis, "layer_depth", 0) if thesis else 0,
            "RegimeAtEntry": getattr(thesis, "regime_at_entry", "") if thesis else "",
            "EntryATR": getattr(thesis, "entry_atr", 0.0) if thesis else 0.0,
            "EntryConviction": getattr(thesis, "entry_conviction", 0.0) if thesis else 0.0,
            "ArmingH4Direction": getattr(thesis, "arming_h4_direction", "") if thesis else "",
            "ArmingM15Regime": getattr(thesis, "arming_m15_regime", "") if thesis else "",
        }

        _prepare_v2_ledger_file()
        file_exists = os.path.isfile(V2_LEDGER_FILE)
        with open(V2_LEDGER_FILE, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=V2_LEDGER_COLUMNS)
            if not file_exists:
                w.writeheader()
            w.writerow({k: row.get(k, "") for k in V2_LEDGER_COLUMNS})

        _LEDGER_WRITTEN.add(ticket)
        logger.info(
            f"[V2 LEDGER] exit recorded #{ticket} {symbol} {reason} "
            f"R={realized_r} USD={row['Realized_USD']} broker_closed={broker_closed}"
        )
    except Exception as e:
        logger.error(f"[V2 LEDGER] write failed for #{ticket}: {e}")

_GRID_STATES = {
    201: GridState(max_legs=4),
    202: GridState(max_legs=4),
    204: GridState(max_legs=4),
}

class TradeManager:
    """
    V2 Trade Manager:
    Centralized module to handle active trade management across all V2 bots.
    Implements:
    - Break Even + $5 lock at 1R profit
    - Dynamic Trailing SL 1R behind MFE
    - H1 Structural Invalidation for losing trades
    """
    def __init__(self, gateway, kr: KnowledgeRegister, st_magics: set = None):
        self.gateway = gateway
        self.kr = kr
        self.cab_legacy = CABLegacyManager(gateway, kr, self)
        self.st_magics = st_magics or {101234, 201567, 301890, 401213}

    def manage_open_positions(self, magic_number: int):
        """Processes all open positions matching the bot's magic number."""
        positions = self.gateway.positions_get()
        if not positions:
            return
            
        bot_positions = [pos for pos in positions if pos.magic == magic_number]
        if not bot_positions:
            return
            
        # Broker-close thesis cleanup — runs every management cycle
        try:
            live_tickets = {pos.ticket for pos in positions}
            with self.kr._lock:
                registered = set(self.kr._theses.keys())
            broker_closed = registered - live_tickets
            for ticket in broker_closed:
                # fix-v2-exit-ledger: capture the outcome BEFORE the thesis is cleared —
                # after unregister_trade_thesis() the entry context is gone and the
                # trade's result can no longer be attributed.
                self._record_broker_close(ticket)
                self.kr.unregister_trade_thesis(ticket)
        except Exception as e:
            logger.debug(f"KR broker-close cleanup error: {e}")

        # DISPATCH LOGIC
        if magic_number in {201, 202, 204}:
            self._manage_ghost_grid(magic_number, bot_positions, positions)
        elif magic_number in self.st_magics:
            # V1 parity: SuperTrend manages its own positions inside its
            # execute_cycle() (V1 run_cycle ordering). The old V2-invented
            # BE+$5/trail/H1-invalidation manager (_manage_trend_bots) was
            # deleted (Sep 19 2026) to prevent double management.
            logger.debug(f"ST magic {magic_number} self-manages — TradeManager skipped")
        elif magic_number == 999555:
            self.cab_legacy.manage_fluid_logic(bot_positions)

    def _manage_ghost_grid(self, magic_number: int, bot_positions: list, all_positions: list):
        # 1. Update GridState
        grid = _GRID_STATES.get(magic_number)
        if not grid: return
        grid.sync(all_positions)
        
        for pos in bot_positions:
            thesis = self.kr.get_entry_snapshot(pos.ticket)
            if not thesis: continue
            
            grid.add_leg(pos.ticket, pos.price_open, pos.sl)
            
            # Individual leg Break Even lock at 1.0R — V1 parity
            # (V1 sniper_watcher.py BE_LOCK_R = 1.0, Change 9: was 0.5)
            # V1 computes leg R from the CURRENT SL (pos.sl), not the thesis
            # snapshot — same here so a 10016-widened SL behaves identically.
            initial_risk = abs(pos.price_open - pos.sl)
            if initial_risk > 0:
                is_buy = (pos.type == mt5.ORDER_TYPE_BUY)
                profit_dist = (pos.price_current - pos.price_open) if is_buy else (pos.price_open - pos.price_current)
                if profit_dist >= initial_risk * 1.0:
                    sym_info = self.gateway.symbol_info(pos.symbol)
                    # V1 parity (sniper_watcher._check_be_lock): the BE price must clear the
                    # broker's STOPS_LEVEL, not just the flat 30-point buffer. V1 computes
                    # min_dist = max(point*30, stops_level*point + point*5), and every V1
                    # modify helper widens-and-retries when a request lands inside
                    # stops_level. V2 applied the bare 30-point buffer and _modify_sl
                    # returned False silently on a rejection — so on any symbol whose
                    # stops_level exceeds 25 points the BE lock never applied at all and
                    # the leg rode to full SL. Fixed to V1's formula so the lock cannot be
                    # skipped for that reason.
                    if sym_info:
                        buf = sym_info.point * 30
                        stops_dist = sym_info.trade_stops_level * sym_info.point
                        min_dist = max(buf, stops_dist + sym_info.point * 5)
                    else:
                        min_dist = 0.0
                    be_price = pos.price_open + min_dist if is_buy else pos.price_open - min_dist
                    sl_needs_be = (pos.sl < be_price) if is_buy else (pos.sl == 0 or pos.sl > be_price)
                    if sl_needs_be:
                        self._modify_sl(pos, be_price, sym_info.digits if sym_info else 3, "Locked leg at BE")
        
        # 2. Grid-Level Exits (Magic 204 specifically targets combined R)
        if magic_number == 204 and grid.active:
            r = grid.r_multiple(all_positions)
            grid_legs = grid.open_legs(all_positions)
            
            # Grid TP
            if r >= 1.0:
                logger.warning(f"GRID 204 TP | R={r:+.2f} | closing {len(grid_legs)} legs")
                for leg in grid_legs:
                    self._close_position(leg, f"GRID_TP|R{r:+.2f}")
                grid.reset()
                return
                
            # Grid Stop
            if r <= -3.0:
                logger.warning(f"GRID 204 STOP | R={r:+.2f} | closing {len(grid_legs)} legs")
                for leg in grid_legs:
                    self._close_position(leg, f"GRID_STOP|R{r:+.2f}")
                grid.reset()
                return
                
            # Grid Protector
            if r >= 0.35 and grid_legs:
                oldest = grid_legs[0]
                is_buy = (oldest.type == mt5.ORDER_TYPE_BUY)
                sym_info = self.gateway.symbol_info(oldest.symbol)
                if sym_info:
                    buf = sym_info.point * 30
                    new_sl = oldest.price_open + buf if is_buy else oldest.price_open - buf
                    needs_update = ((is_buy and new_sl > oldest.sl) or (not is_buy and (new_sl < oldest.sl or oldest.sl == 0)))
                    if needs_update:
                        self._modify_sl(oldest, new_sl, sym_info.digits, "Grid Protector BE")

    # fix-parity-cleanup (Sep 19 2026): _manage_trend_bots() was deleted here.
    # It was a V2-invented exit engine (break-even + $5 lock, 1R-behind trailing
    # SL, H1 structural invalidation) with no V1 counterpart. The per-magic
    # dispatch above stopped calling it when V1 parity was restored, so it was
    # dead code — and a second, unused exit engine sitting in the manager is
    # exactly what gets re-wired by accident. V1's ghost exits live in
    # _manage_ghost_grid(); SuperTrend self-manages inside its own cycle.

    def _modify_sl(self, pos, new_sl: float, digits: int, reason: str) -> bool:
        rounded_sl = round(new_sl, digits)
        if rounded_sl == round(pos.sl, digits):
            return True

        tick = self.gateway.symbol_info_tick(pos.symbol)
        sym_info = self.gateway.symbol_info(pos.symbol)
        if not tick or not sym_info:
            return False
            
        stops_dist = sym_info.trade_stops_level * sym_info.point
        is_buy = (pos.type == mt5.ORDER_TYPE_BUY)
        curr_price = tick.bid if is_buy else tick.ask

        if is_buy:
            if rounded_sl > curr_price - stops_dist:
                return False
        else:
            if rounded_sl < curr_price + stops_dist:
                return False

        req = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "sl": rounded_sl,
            "tp": pos.tp
        }
        res = self.gateway.order_send(req)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"[MANAGEMENT] #{pos.ticket} [{pos.symbol}] {reason} to {rounded_sl:.5f}")
            return True
        return False

    def _close_position(self, pos, reason: str) -> bool:
        tick = self.gateway.symbol_info_tick(pos.symbol)
        if not tick: return False
        
        is_buy = (pos.type == mt5.ORDER_TYPE_BUY)
        price = tick.bid if is_buy else tick.ask
        order_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
        
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": pos.magic,
            "comment": str(reason)[:28] if reason else "",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC
        }
        res = self.gateway.order_send(req)
        closed = False
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            closed = True
        elif res and res.retcode == 10013:
            verify = self.gateway.positions_get(ticket=pos.ticket)
            if not verify:
                closed = True

        if closed:
            # Record the exit while the thesis still exists — the KR is cleared for this
            # ticket as soon as the position vanishes from positions_get().
            try:
                thesis = self.kr.get_entry_snapshot(pos.ticket)
            except Exception:
                thesis = None
            # initial_sl must come from the thesis: pos.sl may already have been trailed
            # to break-even or beyond, which would corrupt the R denominator.
            initial_sl = getattr(thesis, "initial_sl", 0.0) if thesis else 0.0
            if not initial_sl:
                initial_sl = pos.sl
            write_v2_exit_record(
                self.gateway,
                ticket=pos.ticket,
                symbol=pos.symbol,
                direction=1 if pos.type == mt5.ORDER_TYPE_BUY else -1,
                volume=pos.volume,
                entry_price=pos.price_open,
                exit_price=price,
                initial_sl=initial_sl,
                reason=reason,
                open_time=pos.time,
                close_ts=time.time(),
                thesis=thesis,
                broker_closed=False,
                profit=getattr(pos, "profit", None),
            )

        return closed

    def _record_broker_close(self, ticket: int) -> None:
        """
        Writes an exit-ledger row for a position the broker closed (stop or target)
        rather than a bot decision. Without this the largest cohort in any V2 book —
        stops — was entirely invisible, which is why V2 exit attribution was impossible.
        """
        try:
            thesis = None
            try:
                thesis = self.kr.get_entry_snapshot(ticket)
            except Exception:
                thesis = None

            hist = getattr(self.gateway, "history_deals_get", None) or mt5.history_deals_get
            deals = hist(position=ticket)
            if not deals:
                return

            entry_deal = next((d for d in deals if d.entry == mt5.DEAL_ENTRY_IN), None)
            exit_deal = next((d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT), None)
            if exit_deal is None:
                return

            if entry_deal is not None:
                direction = 1 if entry_deal.type == mt5.DEAL_TYPE_BUY else -1
                entry_price = entry_deal.price
                open_time = entry_deal.time
            else:
                direction = 1 if getattr(thesis, "direction", 1) == 1 else -1
                entry_price = getattr(thesis, "fill_price", 0.0) or 0.0
                open_time = getattr(thesis, "timestamp", 0.0) or 0.0

            profit = (exit_deal.profit
                      + (getattr(exit_deal, "swap", 0.0) or 0.0)
                      + (getattr(exit_deal, "commission", 0.0) or 0.0))

            write_v2_exit_record(
                self.gateway,
                ticket=ticket,
                symbol=exit_deal.symbol,
                direction=direction,
                volume=exit_deal.volume,
                entry_price=entry_price,
                exit_price=exit_deal.price,
                initial_sl=getattr(thesis, "initial_sl", 0.0) or 0.0,
                # Reason is derived from realised R inside write_v2_exit_record, so a
                # break-even scratch is not recorded as a take-profit (fix-v2-exit-class).
                reason=None,
                open_time=open_time,
                close_ts=exit_deal.time,
                thesis=thesis,
                broker_closed=True,
                profit=profit,
            )
        except Exception as e:
            logger.debug(f"[V2 LEDGER] broker-close record failed #{ticket}: {e}")
