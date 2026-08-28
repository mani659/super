import time
import logging
import os
import json
import pandas as pd
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime
import MetaTrader5 as mt5

from v2.core.knowledge_register import KnowledgeRegister
from v2.core.data_models import TradeSignal, TradeThesis
from v2.execution.mt5_gateway import MT5Gateway
from v2.execution.order_router import OrderRouter
from v2.core.utils import calculate_dynamic_lot, is_session_active

logger = logging.getLogger("CABSuperBotV2")

@dataclass
class CABConfig:
    symbol: str
    magic_number: int = 999555
    risk_percent: float = 0.5
    atr_multiplier: float = 1.0
    max_positions: int = 1
    max_spread_points: int = 400
    session_gate_enabled: bool = True
    blocked_hours_utc: tuple = (0, 1, 2, 3, 4, 5, 6)
    max_lot_demo_cap: Optional[float] = None
    max_fire_attempts_per_bar: int = 3

class CABBot:
    """
    V2 CAB Bot: H4 Inversion Pattern Engine.
    Generates signals on H4 close based on Bullish/Bearish inversion logic.
    """
    def __init__(
        self,
        config: CABConfig,
        gateway: MT5Gateway,
        router: OrderRouter,
        kr: KnowledgeRegister
    ):
        self.config = config
        self.gateway = gateway
        self.router = router
        self.kr = kr
        
        self.state_file = f"logs/cab_state_{self.config.symbol}.json"
        os.makedirs("logs", exist_ok=True)
        self.startup_grace = time.time() + 10
        
        self._last_h4_bar_time = None
        self._load_state()
        self._fire_attempt_bar_time = None
        self._fire_attempt_count = 0

    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                    val = state.get("last_h4_bar_time")
                    if val is not None:
                        import pandas as pd
                        self._last_h4_bar_time = pd.to_datetime(val, unit='s')
            except Exception as e:
                logger.error(f"Failed to load CAB state for {self.config.symbol}: {e}")

    def _save_state(self):
        try:
            val = None
            if self._last_h4_bar_time is not None:
                val = int(self._last_h4_bar_time.timestamp()) if hasattr(self._last_h4_bar_time, 'timestamp') else int(self._last_h4_bar_time)
            with open(self.state_file, "w") as f:
                json.dump({"last_h4_bar_time": val}, f)
        except Exception as e:
            logger.error(f"Failed to save CAB state for {self.config.symbol}: {e}")

    def _session_allowed(self) -> bool:
        return is_session_active(
            session_gate_enabled=self.config.session_gate_enabled,
            blocked_hours_utc=self.config.blocked_hours_utc
        )

    def _calculate_lot(self, sl_dist_price: float) -> float:
        return calculate_dynamic_lot(
            gateway=self.gateway,
            symbol=self.config.symbol,
            risk_percent=self.config.risk_percent,
            sl_dist_price=sl_dist_price,
            max_lot_demo_cap=self.config.max_lot_demo_cap
        )

    def _close_position(self, pos) -> bool:
        tick = self.gateway.symbol_info_tick(self.config.symbol)
        if not tick:
            return False
            
        is_buy = (pos.type == 0)
        price = tick.bid if is_buy else tick.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.config.symbol,
            "volume": float(pos.volume),
            "type": mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
            "position": pos.ticket,
            "price": price,
            "deviation": 20,
            "magic": self.config.magic_number,
            "comment": "CAB_REV_CLOSE_V2",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = self.gateway.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Closed CAB position #{pos.ticket} for reversal.")
            self.kr.unregister_trade_thesis(pos.ticket)
            return True
        logger.warning(f"Failed to close position #{pos.ticket} for reversal. Code: {res.retcode if res else 'None'}")
        return False

    def execute_cycle(self, df: pd.DataFrame, current_dd: float, max_dd: float):
        """
        Main H4 cycle. df must contain H4 data.
        """
        if time.time() < self.startup_grace:
            return False
            
        if df is None or len(df) < 5:
            return False

        if not self._session_allowed():
            return False

        tick = self.gateway.symbol_info_tick(self.config.symbol)
        sym = self.gateway.symbol_info(self.config.symbol)
        if tick is None or sym is None:
            return False

        spread_points = int((tick.ask - tick.bid) / sym.point)
        if spread_points > self.config.max_spread_points:
            return False

        bar1_time = df["time"].iloc[-2]
        if bar1_time == self._last_h4_bar_time:
            return False

        bar1_open  = float(df["open"].iloc[-2])
        bar1_close = float(df["close"].iloc[-2])
        bar2_open  = float(df["open"].iloc[-3])
        bar2_close = float(df["close"].iloc[-3])

        bar1_bullish = bar1_close > bar1_open
        bar1_bearish = bar1_close < bar1_open
        bar2_bullish = bar2_close > bar2_open
        bar2_bearish = bar2_close < bar2_open

        is_bullish_inversion = bar2_bearish and bar1_bullish
        is_bearish_inversion = bar2_bullish and bar1_bearish

        if not (is_bullish_inversion or is_bearish_inversion):
            self._last_h4_bar_time = bar1_time; self._save_state()
            self._fire_attempt_bar_time = None
            self._fire_attempt_count = 0
            return False

        if self._fire_attempt_bar_time != bar1_time:
            self._fire_attempt_bar_time = bar1_time
            self._fire_attempt_count = 0

        if self._fire_attempt_count >= self.config.max_fire_attempts_per_bar:
            self._last_h4_bar_time = bar1_time; self._save_state()
            return False

        # Fetch KR State
        snapshot = self.kr.get_market_state(self.config.symbol, "H4")
        if not snapshot:
            return False
            
        atr = snapshot.atr_raw if snapshot.atr_raw > 0 else 1.0

        # Auto-Reversal Logic
        all_pos = self.gateway.positions_get(symbol=self.config.symbol)
        my_pos = [p for p in (all_pos or []) if p.magic == self.config.magic_number]
        
        if my_pos:
            pos = my_pos[0]
            is_buy_pos = (pos.type == 0)
            
            if (is_bullish_inversion and is_buy_pos) or (is_bearish_inversion and not is_buy_pos):
                self._last_h4_bar_time = bar1_time; self._save_state()
                return False
            else:
                if self._close_position(pos):
                    time.sleep(0.5)
                else:
                    return False
                    
        if len(my_pos) >= self.config.max_positions:
            return False

        sl_dist = atr * self.config.atr_multiplier
        lot = self._calculate_lot(sl_dist)
        
        order_type = mt5.ORDER_TYPE_BUY if is_bullish_inversion else mt5.ORDER_TYPE_SELL
        
        # Pre-calculate SL for Signal Routing
        if order_type == mt5.ORDER_TYPE_BUY:
            sl = tick.bid - sl_dist
            fill_price = tick.ask
        else:
            sl = tick.ask + sl_dist
            fill_price = tick.bid
            
        # SL guard (widen if too close)
        stops_dist = sym.trade_stops_level * sym.point
        buf = sym.point * 30
        if order_type == mt5.ORDER_TYPE_BUY and (fill_price - sl) < stops_dist:
            sl = fill_price - stops_dist - buf
        if order_type == mt5.ORDER_TYPE_SELL and (sl - fill_price) < stops_dist:
            sl = fill_price + stops_dist + buf
        sl = round(sl, sym.digits)

        self._fire_attempt_count += 1

        ts = TradeSignal(
            symbol=self.config.symbol,
            bot_name="CABSuperBotV2",
            magic_number=self.config.magic_number,
            order_type=order_type,
            sl_price=sl
        )
        
        if self.router.route_signal(ts, current_dd, max_dd):
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.config.symbol,
                "volume": lot,
                "type": order_type,
                "price": fill_price,
                "sl": sl,
                "tp": 0.0,
                "deviation": 20,
                "magic": self.config.magic_number,
                "comment": "CAB_INV_V2",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            res = self.gateway.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"CAB Executed INVERSION | Ticket {res.order}")
                self._last_h4_bar_time = bar1_time; self._save_state()
                
                # Register Thesis
                thesis = TradeThesis(
                    ticket=res.order,
                    symbol=self.config.symbol,
                    direction=1 if order_type == mt5.ORDER_TYPE_BUY else -1,
                    bot_system="CABSuperBotV2",
                    setup_type="H4_INVERSION",
                    fill_price=fill_price,
                    initial_sl=sl,
                    initial_tp=0.0,
                    entry_atr=atr,
                    regime_at_entry=snapshot.regime,
                    entry_conviction=50.0,  # CAB doesn't use conviction math in V1
                    layer_depth=1,
                    timestamp=time.time(),
                    market_snapshot=snapshot
                )
                self.kr.register_trade_thesis(thesis)
                return True

        return False


