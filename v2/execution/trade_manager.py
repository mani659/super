import logging
import pandas as pd
import MetaTrader5 as mt5
from v2.core.knowledge_register import KnowledgeRegister
from v2.execution.grid_state import GridState
from v2.execution.cab_legacy_manager import CABLegacyManager

logger = logging.getLogger("TradeManager")

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
                self.kr.unregister_trade_thesis(ticket)
        except Exception as e:
            logger.debug(f"KR broker-close cleanup error: {e}")

        # DISPATCH LOGIC
        if magic_number in {201, 202, 204}:
            self._manage_ghost_grid(magic_number, bot_positions, positions)
        elif magic_number in self.st_magics:
            self._manage_trend_bots(magic_number, bot_positions)
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
            
            # Individual leg Break Even lock at 0.5R
            initial_risk = abs(thesis.fill_price - thesis.initial_sl)
            if initial_risk > 0:
                is_buy = (pos.type == mt5.ORDER_TYPE_BUY)
                profit_dist = (pos.price_current - pos.price_open) if is_buy else (pos.price_open - pos.price_current)
                if profit_dist >= initial_risk * 0.5:
                    sym_info = self.gateway.symbol_info(pos.symbol)
                    buf = sym_info.point * 30 if sym_info else 0.0
                    be_price = pos.price_open + buf if is_buy else pos.price_open - buf
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

    def _manage_trend_bots(self, magic_number: int, bot_positions: list):
        for pos in bot_positions:
            sym_info = self.gateway.symbol_info(pos.symbol)
            if not sym_info:
                continue
                
            thesis = self.kr.get_entry_snapshot(pos.ticket)
            if not thesis:
                continue
                
            pip_size = sym_info.point * (10 if sym_info.digits in (3, 5) else 1)
            initial_risk_price = abs(thesis.fill_price - thesis.initial_sl)
            if initial_risk_price <= 0:
                continue
                
            is_buy = (pos.type == mt5.ORDER_TYPE_BUY)
            profit_price_dist = (pos.price_current - pos.price_open) if is_buy else (pos.price_open - pos.price_current)
            
            five_dollars_risk = 5.0
            try:
                tick_value = sym_info.trade_tick_value
                pips_for_five = five_dollars_risk / (tick_value * pos.volume)
                price_for_five = pips_for_five * pip_size
            except Exception:
                price_for_five = initial_risk_price * 0.1
                
            be_plus_five = pos.price_open + price_for_five if is_buy else pos.price_open - price_for_five
            
            # GATE 1: Break Even + $5 Lock
            if profit_price_dist >= initial_risk_price:
                sl_needs_be = (pos.sl < be_plus_five) if is_buy else (pos.sl == 0 or pos.sl > be_plus_five)
                if sl_needs_be:
                    self._modify_sl(pos, be_plus_five, sym_info.digits, "hits 1R. SL locked at BE + ")
                    continue
                    
            # GATE 2: Dynamic Trailing (1R behind current price)
            is_at_be = (pos.sl >= be_plus_five) if is_buy else (pos.sl > 0 and pos.sl <= be_plus_five)
            if is_at_be:
                trail_level = pos.price_current - initial_risk_price if is_buy else pos.price_current + initial_risk_price
                needs_trail = (trail_level > pos.sl) if is_buy else (trail_level < pos.sl)
                
                if needs_trail:
                    self._modify_sl(pos, trail_level, sym_info.digits, "Trailing SL updated")
                    
            # GATE 3: H1 Structural Invalidation (Losing Trades Only)
            if pos.profit < 0:
                rates = self.gateway.copy_rates_from_pos(pos.symbol, mt5.TIMEFRAME_H1, 1, 4)
                if rates is not None and len(rates) >= 4:
                    df = pd.DataFrame(rates)
                    tick = self.gateway.symbol_info_tick(pos.symbol)
                    
                    breached = False
                    if is_buy and tick.bid < df['low'].min():
                        breached = True
                    elif not is_buy and tick.ask > df['high'].max():
                        breached = True
                        
                    if breached:
                        if self._close_position(pos, "H1_STRUCT_INVALID"):
                            self.kr.unregister_trade_thesis(pos.ticket)
                            logger.warning(f"[MANAGEMENT] #{pos.ticket} [{pos.symbol}] Killed early due to H1 Structural Invalidation.")

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
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            return True
        elif res and res.retcode == 10013:
            verify = self.gateway.positions_get(ticket=pos.ticket)
            if not verify:
                return True
        return False
