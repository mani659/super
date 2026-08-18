import os

with open('v2/bots/cab_bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_content = """import time
import logging
import pandas as pd
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime
import MetaTrader5 as mt5

from v2.core.knowledge_register import KnowledgeRegister
from v2.core.data_models import TradeSignal, TradeThesis
from v2.execution.mt5_gateway import MT5Gateway
from v2.execution.order_router import OrderRouter
from v2.core.utils import calculate_dynamic_lot

logger = logging.getLogger("CABBotV2")

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
    \"\"\"
    V2 CAB Bot: H4 Inversion Pattern Engine.
    Generates signals on H4 close based on Bullish/Bearish inversion logic.
    \"\"\"
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
        
        self._last_h4_bar_time = None
        self._fire_attempt_bar_time = None
        self._fire_attempt_count = 0

    def _session_allowed(self) -> bool:
        if not self.config.session_gate_enabled:
            return True
        hour = datetime.utcnow().hour
        return hour not in self.config.blocked_hours_utc

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
            
"""

with open('v2/bots/cab_bot.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
    f.writelines(lines[3:])
