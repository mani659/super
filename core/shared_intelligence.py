import time
import logging
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import threading
from typing import List, Dict

from core.knowledge_register import (
    KnowledgeRegister,
    RegimeType,
    SessionTag
)
from mt5_gateway import MT5Gateway

logger = logging.getLogger("MarketPulseEngine")

class MarketPulseEngine:
    """
    Centralized calculation engine for Layer 0 facts.
    Eliminates duplicated indicator computations across bots.
    """
    def __init__(self, gateway: MT5Gateway, kr: KnowledgeRegister, symbols: List[str]):
        self.gateway = gateway
        self.kr = kr
        self.symbols = symbols
        self.running = False
        self._thread = None
        
        # We track the last bar times to only recalculate on a new bar close
        self._last_bar_times = {sym: {mt5.TIMEFRAME_H4: 0, mt5.TIMEFRAME_M15: 0} for sym in symbols}
        
    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._pulse_loop, daemon=True, name="MarketPulseEngine")
        self._thread.start()
        logger.info("MarketPulseEngine started.")
        
    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            logger.info("MarketPulseEngine stopped.")

    def _pulse_loop(self):
        while self.running:
            try:
                for symbol in self.symbols:
                    self._update_symbol_timeframe(symbol, mt5.TIMEFRAME_H4, 150)
                    self._update_symbol_timeframe(symbol, mt5.TIMEFRAME_M15, 150)
            except Exception as e:
                logger.error(f"Error in pulse loop: {e}", exc_info=True)
            
            # Poll every 10 seconds. New calculation only happens if source_bar_time changes.
            time.sleep(10)

    def _update_symbol_timeframe(self, symbol: str, timeframe: int, count: int):
        rates = self.gateway.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None or len(rates) < 20:
            return
        
        current_bar_time = int(rates[-1]['time'])
        df = pd.DataFrame(rates)
        
        # Calculate Facts
        adx_series = self._wilder_adx(df, 14)
        adx_val = float(adx_series.iloc[-1])
        adx_percentile = float(self._percentile_rank(adx_series, adx_val))
        
        # TR & ATR
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
        
        # Body/Range
        df["body"] = (df["close"] - df["open"]).abs()
        df["range_"] = (df["high"] - df["low"]).replace(0, np.nan)
        br_series = df["body"] / df["range_"]
        br_val = float(br_series.iloc[-1]) if not pd.isna(br_series.iloc[-1]) else 0.5
        br_percentile = float(self._percentile_rank(br_series.dropna(), br_val)) if not pd.isna(br_val) else 50.0
        
        # Regime Classification (using H4 logic)
        regime = RegimeType.UNKNOWN
        if atr_percentile >= 75 and br_percentile <= 35:
            regime = RegimeType.EXHAUSTION
        elif adx_percentile >= 65 and br_percentile > 35:
            if float(df["close"].iloc[-1]) > float(df["close"].iloc[-14]):
                regime = RegimeType.TRENDING_UP
            else:
                regime = RegimeType.TRENDING_DOWN
        else:
            regime = RegimeType.RANGING
            
        # Session Tag & Execution Quality
        tick = self.gateway.symbol_info_tick(symbol)
        current_spread = float(tick.ask - tick.bid) if tick else 0.0
        normal_spread = 2.0  # Placeholder, should ideally track rolling spread
        
        # Session hours aligned to ghost_sniper.get_session() (canonical).
        # F-A3 fix: standardised Sep 2026 — single taxonomy across all bots.
        current_hour = pd.Timestamp.now(tz='UTC').hour
        if 8 <= current_hour < 12:
            session = SessionTag.LONDON
        elif 12 <= current_hour < 16:
            session = SessionTag.NY_OVERLAP
        elif 16 <= current_hour < 21:
            session = SessionTag.NY_CLOSE
        else:
            session = SessionTag.ASIAN
            
        tf_str = "H4" if timeframe == mt5.TIMEFRAME_H4 else "M15"
            
        self.kr.publish_market_state(
            symbol=symbol,
            timeframe=tf_str,
            source_bar_time=current_bar_time,
            adx_raw=adx_val,
            adx_percentile=adx_percentile,
            atr_raw=atr_raw,
            atr_percentile=atr_percentile,
            body_range_ratio=br_val,
            regime=regime,
            session=session,
            current_spread=current_spread,
            normal_spread=normal_spread
        )
        logger.info(f"MarketPulseEngine published {symbol} {tf_str} state")

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


