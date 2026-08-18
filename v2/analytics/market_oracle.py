import pandas as pd
import numpy as np
import time
from typing import Optional
from mt5_gateway import MT5Gateway
import MetaTrader5 as mt5
from v2.core.data_models import MarketStateSnapshot

class MarketOracle:
    """Centralized math engine to compute ATR, MACD, ADX, and Regime."""
    
    def __init__(self, gateway: MT5Gateway):
        self.gateway = gateway
        
    def evaluate_symbol(self, symbol: str) -> Optional[MarketStateSnapshot]:
        """Calculates and returns the canonical market state for a symbol."""
        # 1. Fetch Rates (H4 and M15)
        m15_rates = self.gateway.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 100)
        h4_rates = self.gateway.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 100)
        tick = self.gateway.symbol_info_tick(symbol)
        sym_info = self.gateway.symbol_info(symbol)
        
        if m15_rates is None or h4_rates is None or tick is None or sym_info is None:
            return None
            
        m15_df = pd.DataFrame(m15_rates)
        
        # 2. Compute ATR (M15)
        m15_df["tr"] = np.maximum(
            m15_df["high"] - m15_df["low"],
            np.maximum(
                (m15_df["high"] - m15_df["close"].shift(1)).abs(),
                (m15_df["low"]  - m15_df["close"].shift(1)).abs()
            )
        )
        atr_14 = m15_df["tr"].rolling(14).mean().iloc[-1]
        atr_14 = float(atr_14) if not pd.isna(atr_14) else 1.0
        
        # Calculate current spread in points
        spread_pts = (tick.ask - tick.bid) / max(sym_info.point, 1e-6)
        
        # Note: Actual Regime, ADX, and MACD calculations are stubs in v2 
        # until ported completely from the individual bots.
        # For this foundation, we populate the dataclass.
        
        return MarketStateSnapshot(
            symbol=symbol,
            timeframe="M15",
            timestamp=time.time(),
            source_bar_time=int(m15_df.iloc[-1]["time"]),
            adx_raw=0.0,
            adx_percentile=0.0,
            atr_raw=atr_14,
            atr_percentile=50.0,
            body_range_ratio=0.5,
            regime="UNKNOWN",
            session="LONDON",
            current_spread=spread_pts,
            normal_spread=20.0
        )
