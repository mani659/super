import time
import logging
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import threading
from typing import List

from v2.core.knowledge_register import KnowledgeRegister
from v2.core.data_models import MarketStateSnapshot
from v2.execution.mt5_gateway import MT5Gateway

logger = logging.getLogger("MarketOracle")

class MarketOracle:
    """
    V2 Market Oracle:
    Centralized calculation engine for Layer 0 facts (ADX, ATR, Regime, MACD).
    """
    def __init__(self, gateway: MT5Gateway, kr: KnowledgeRegister, symbols: List[str]):
        self.gateway = gateway
        self.kr = kr
        self.symbols = symbols
        self.running = False
        self._thread = None
        
        self._last_bar_times = {sym: {mt5.TIMEFRAME_H4: 0, mt5.TIMEFRAME_M30: 0, mt5.TIMEFRAME_M15: 0} for sym in symbols}
        
    def tick(self):
        try:
            for symbol in self.symbols:
                self._update_symbol_timeframe(symbol, mt5.TIMEFRAME_H4, 50)
                self._update_symbol_timeframe(symbol, mt5.TIMEFRAME_M30, 50)
                self._update_symbol_timeframe(symbol, mt5.TIMEFRAME_M15, 50)
        except Exception as e:
            logger.error(f"Error in oracle tick: {e}", exc_info=True)

    def _update_symbol_timeframe(self, symbol: str, timeframe: int, count: int):
        rates = self.gateway.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None or len(rates) < 35: # Need 35 for MACD 26+9
            return
        
        current_bar_time = int(rates[-1]['time'])
        
        if current_bar_time <= self._last_bar_times[symbol][timeframe]:
            return
            
        self._last_bar_times[symbol][timeframe] = current_bar_time
        df = pd.DataFrame(rates)
        
        # 1. ADX Calculation
        adx_series = self._wilder_adx(df, 14)
        adx_val = float(adx_series.iloc[-1])
        adx_percentile = float(self._percentile_rank(adx_series, adx_val))
        
        # 2. TR & ATR
        df["tr"] = np.maximum(
            df["high"] - df["low"],
            np.maximum(
                (df["high"] - df["close"].shift(1)).abs(),
                (df["low"]  - df["close"].shift(1)).abs()
            )
        )
        atr14 = df["tr"].rolling(14).mean()
        atr_raw = float(atr14.iloc[-1]) if not pd.isna(atr14.iloc[-1]) else 1.0
        
        atr_ratio = atr14 / atr14.rolling(50).mean().replace(0, np.nan)
        atr_val = atr_ratio.iloc[-1]
        atr_percentile = float(self._percentile_rank(atr_ratio.dropna(), atr_val)) if not pd.isna(atr_val) else 50.0
        
        # 3. Body/Range
        df["body"] = (df["close"] - df["open"]).abs()
        df["range_"] = (df["high"] - df["low"]).replace(0, np.nan)
        br_series = df["body"] / df["range_"]
        br_val = float(br_series.iloc[-1]) if not pd.isna(br_series.iloc[-1]) else 0.5
        br_percentile = float(self._percentile_rank(br_series.dropna(), br_val)) if not pd.isna(br_val) else 50.0
        
        # 4. Regime Classification (1:1 Port)
        if atr_percentile >= 75 and br_percentile <= 35:
            regime = "EXHAUSTION"
        elif adx_percentile >= 65 and br_percentile > 35:
            if float(df["close"].iloc[-1]) > float(df["close"].iloc[-14]):
                regime = "TRENDING_UP"
            else:
                regime = "TRENDING_DOWN"
        else:
            regime = "RANGING"
            
        # 5. MACD Calculation (12, 26, 9)
        ema12 = df["close"].ewm(span=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        
        macd_raw = float(macd_line.iloc[-1])
        macd_signal_val = float(signal_line.iloc[-1])

        # 6. Session Tag
        tick = self.gateway.symbol_info_tick(symbol)
        current_spread = float(tick.ask - tick.bid) if tick else 0.0
        normal_spread = 2.0
        
        current_hour = pd.Timestamp.now(tz='UTC').hour
        if current_hour in (0, 1, 2, 3, 4, 5, 6):
            session = "ASIAN"
        elif current_hour in (7, 8, 9, 10, 11, 12):
            session = "LONDON"
        elif current_hour in (13, 14, 15, 16):
            session = "NY_OVERLAP"
        elif current_hour in (17, 18, 19, 20):
            session = "NY_CLOSE"
        else:
            session = "OFF_HOURS"
            
        if timeframe == mt5.TIMEFRAME_H4: tf_str = "H4"
        elif timeframe == mt5.TIMEFRAME_M30: tf_str = "M30"
        else: tf_str = "M15"
            
        snapshot = MarketStateSnapshot(
            symbol=symbol,
            timeframe=tf_str,
            timestamp=time.time(),
            source_bar_time=current_bar_time,
            adx_raw=adx_val,
            adx_percentile=adx_percentile,
            atr_raw=atr_raw,
            atr_percentile=atr_percentile,
            body_range_ratio=br_val,
            regime=regime,
            session=session,
            current_spread=current_spread,
            normal_spread=normal_spread,
            macd_raw=macd_raw,
            macd_signal=macd_signal_val
        )
        self.kr.publish_market_state(snapshot)

    def _percentile_rank(self, series: pd.Series, value: float) -> int:
        arr = series.dropna().values
        if len(arr) == 0:
            return 50
        return int(100 * np.sum(arr <= value) / len(arr))

    def _wilder_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        df = df.copy()
        hi_diff = df["high"] - df["high"].shift(1)
        lo_diff = df["low"].shift(1) - df["low"]

        df["pdm"] = np.where((hi_diff > lo_diff) & (hi_diff > 0), hi_diff, 0.0)
        df["ndm"] = np.where((lo_diff > hi_diff) & (lo_diff > 0), lo_diff, 0.0)
        df["tr"]  = np.maximum(
                        df["high"] - df["low"],
                        np.maximum(
                            (df["high"] - df["close"].shift(1)).abs(),
                            (df["low"]  - df["close"].shift(1)).abs()
                        )
                    )

        def _smooth_dm(s: pd.Series, p: int) -> pd.Series:
            result = np.zeros(len(s))
            if len(s) < p:
                return pd.Series(result, index=s.index)
            result[p - 1] = float(s.iloc[:p].sum())
            for i in range(p, len(s)):
                result[i] = result[i - 1] - result[i - 1] / p + float(s.iloc[i])
            return pd.Series(result, index=s.index)

        def _smooth_adx(s: pd.Series, p: int) -> pd.Series:
            arr = s.values
            result = np.zeros(len(arr))
            if len(arr) < p:
                return pd.Series(result, index=s.index)
            result[p - 1] = float(np.mean(arr[:p]))
            for i in range(p, len(arr)):
                result[i] = result[i - 1] * (p - 1) / p + arr[i] / p
            return pd.Series(result, index=s.index)

        atr14 = _smooth_dm(df["tr"],  period)
        pdm14 = _smooth_dm(df["pdm"], period)
        ndm14 = _smooth_dm(df["ndm"], period)

        safe_atr = atr14.replace(0, np.nan)
        pdi = 100 * pdm14 / safe_atr
        ndi = 100 * ndm14 / safe_atr
        dx  = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
        adx = _smooth_adx(dx.fillna(0), period)
        return adx
