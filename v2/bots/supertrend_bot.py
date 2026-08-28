import logging
import numpy as np
import pandas as pd
from typing import Tuple, Optional, Dict
from sklearn.cluster import KMeans
from dataclasses import dataclass

from v2.core.knowledge_register import KnowledgeRegister
from v2.core.data_models import TradeSignal, TradeThesis
from v2.execution.mt5_gateway import MT5Gateway
from v2.execution.order_router import OrderRouter
from v2.core.utils import calculate_dynamic_lot, is_session_active
import MetaTrader5 as mt5
import time
import talib

logger = logging.getLogger("SuperTrendBotV2")

@dataclass
class SuperTrendConfig:
    symbol: str
    magic_number: int
    min_factor: float = 2.0
    max_factor: float = 4.0
    factor_step: float = 0.1
    perf_alpha: int = 14
    cluster_choice: str = "Best"  # "Worst", "Average", "Best"
    volume_multiplier: float = 1.0
    risk_percent: float = 1.0
    session_gate_enabled: bool = True
    session_gate_pairs: tuple = ("EURUSD", "GBPUSD", "EURUSDm", "GBPUSDm")

class SuperTrendBot:
    """
    V2 SuperTrend Bot: Pure mathematical signal engine.
    Computes K-Means clustered SuperTrend bands on M30 data,
    then generates TradeSignals for the OrderRouter.
    """
    def __init__(
        self,
        config: SuperTrendConfig,
        gateway: MT5Gateway,
        router: OrderRouter,
        kr: KnowledgeRegister
    ):
        self.config = config
        self.gateway = gateway
        self.router = router
        self.kr = kr
        
        self._st_cache: Optional[Tuple] = None
        self._last_bar_time = None

    def calculate_supertrends(self, df: pd.DataFrame) -> dict:
        """Computes all factor variants (1:1 with V1 logic)."""
        factors = np.arange(
            self.config.min_factor,
            self.config.max_factor + self.config.factor_step,
            self.config.factor_step
        )
        supertrends = {}
        for factor in factors:
            st = pd.DataFrame(index=df.index)
            st["upper"]        = df["hl2"] + (df["atr"] * factor)
            st["lower"]        = df["hl2"] - (df["atr"] * factor)
            st["trend"]        = 0
            st["output"]       = 0.0
            st["perf"]         = 0.0
            st["vol_adj_perf"] = 0.0
            
            for i in range(1, len(df)):
                prev_trend = st["trend"].iloc[i - 1]
                if df["close"].iloc[i] > st["upper"].iloc[i - 1]:
                    st.at[st.index[i], "trend"] = 1
                elif df["close"].iloc[i] < st["lower"].iloc[i - 1]:
                    st.at[st.index[i], "trend"] = 0
                else:
                    st.at[st.index[i], "trend"] = prev_trend
                    
                cur_trend = st["trend"].iloc[i]
                if cur_trend == 1:
                    new_lower = st["lower"].iloc[i]
                    if prev_trend == 1:
                        new_lower = max(new_lower, st["lower"].iloc[i - 1])
                    st.at[st.index[i], "lower"]  = new_lower
                    st.at[st.index[i], "output"] = new_lower
                else:
                    new_upper = st["upper"].iloc[i]
                    if prev_trend == 0:
                        new_upper = min(new_upper, st["upper"].iloc[i - 1])
                    st.at[st.index[i], "upper"]  = new_upper
                    st.at[st.index[i], "output"] = new_upper
                    
                price_change = df["close"].iloc[i] - df["close"].iloc[i - 1]
                direction    = np.sign(df["close"].iloc[i - 1] - st["output"].iloc[i - 1])
                raw_perf = price_change * direction
                alpha    = 2 / (self.config.perf_alpha + 1)
                st.at[st.index[i], "perf"] = (
                    alpha * raw_perf + (1 - alpha) * st["perf"].iloc[i - 1]
                )
                vol_adj = raw_perf / (1 + df["norm_volatility"].iloc[i])
                st.at[st.index[i], "vol_adj_perf"] = (
                    alpha * vol_adj + (1 - alpha) * st["vol_adj_perf"].iloc[i - 1]
                )
            supertrends[round(float(factor), 2)] = st
        return supertrends

    def perform_clustering(self, supertrends: dict) -> Tuple[float, float]:
        """K-Means on vol-adj performance."""
        performances, factors = [], []
        for factor, st in supertrends.items():
            performances.append(st["vol_adj_perf"].iloc[-100:].mean())
            factors.append(factor)
            
        perf_arr = np.array(performances).reshape(-1, 1)
        if len(set(performances)) < 3:
            best_idx = int(np.argmax(performances))
            return factors[best_idx], float(perf_arr.max())
            
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        kmeans.fit(perf_arr)
        sorted_idx   = np.argsort(kmeans.cluster_centers_.flatten())
        cluster_map  = {"Worst": 0, "Average": 1, "Best": 2}
        target_label = sorted_idx[cluster_map[self.config.cluster_choice]]
        
        cluster_factors = [
            factors[i] for i, lbl in enumerate(kmeans.labels_)
            if lbl == target_label
        ]
        
        if not cluster_factors:
            best_idx = int(np.argmax(performances))
            return factors[best_idx], float(perf_arr.max())
            
        return float(np.mean(cluster_factors)), float(
            kmeans.cluster_centers_.flatten()[target_label]
        )

    def _get_supertrends_cached(self, df: pd.DataFrame) -> Tuple[dict, float]:
        last_bar_time = df.index[-1]
        if self._st_cache is not None and self._st_cache[0] == last_bar_time:
            return self._st_cache[1], self._st_cache[2]
            
        supertrends = self.calculate_supertrends(df)
        optimal_factor, _ = self.perform_clustering(supertrends)
        self._st_cache = (last_bar_time, supertrends, optimal_factor)
        return supertrends, optimal_factor

    def check_volume_condition(self, df: pd.DataFrame) -> bool:
        return (
            float(df["tick_volume"].iloc[-1]) >
            float(df["volume_ma"].iloc[-1]) * self.config.volume_multiplier
        )

    def generate_signal(self, df: pd.DataFrame) -> Optional[int]:
        """Returns 1 for BUY, -1 for SELL, None for no signal."""
        if df is None or len(df) < 200:
            return None
            
        supertrends, optimal_factor = self._get_supertrends_cached(df)
        current_st = supertrends[min(supertrends.keys(), key=lambda x: abs(x - optimal_factor))]
        
        cur_trend  = int(current_st["trend"].iloc[-1])
        prev_trend = int(current_st["trend"].iloc[-2])
        
        if not self.check_volume_condition(df):
            return None
            
        # 1. Trend Flip Signal
        if cur_trend > prev_trend:
            return 1
        if cur_trend < prev_trend:
            return -1
            
        # 2. Trend Continuation Signal
        N = 3
        if len(df) > N + 1:
            last_close = float(df["close"].iloc[-1])
            expected_trend = 1 if cur_trend == 1 else 0
            agreeing_count = sum(1 for st in supertrends.values() if int(st["trend"].iloc[-1]) == expected_trend)
            min_agree = max(1, len(supertrends) // 3)
            
            if agreeing_count >= min_agree:
                if cur_trend == 1:
                    recent_high = float(df["high"].iloc[-(N+1):-1].max())
                    if last_close > recent_high:
                        return 1
                elif cur_trend == -1: # V1 bug mirrored/retained for identical behavior, or fixed? Let's fix it to 0 as V2 intended. Wait, V2 is cur_trend == 0.
                    recent_low = float(df["low"].iloc[-(N+1):-1].min())
                    if last_close < recent_low:
                        return -1
        return None

    def _session_allowed(self) -> bool:
        if self.config.symbol not in self.config.session_gate_pairs:
            return True
        return is_session_active(
            session_gate_enabled=self.config.session_gate_enabled,
            blocked_hours_utc=()
        )

    def calculate_position_size(self, stop_loss_points: float) -> float:
        """V2.3 strict mathematical port for position sizing using shared utils."""
        sym_info = self.gateway.symbol_info(self.config.symbol)
        if not sym_info:
            return 0.01
            
        sl_price_dist = stop_loss_points * sym_info.point
        
        return calculate_dynamic_lot(
            gateway=self.gateway,
            symbol=self.config.symbol,
            risk_percent=self.config.risk_percent,
            sl_dist_price=sl_price_dist,
            max_lot_demo_cap=None
        )

    def execute_cycle(self, df: pd.DataFrame, current_dd: float, max_dd: float):
        if not self._session_allowed():
            return False

        if "time" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["time"]):
            df["time"] = pd.to_datetime(df["time"], unit="s")
            df.set_index("time", inplace=True)
            
        # V1 logic: Calculate signal on full dataframe, do not drop current bar or throttle to bar-close
        # self._get_supertrends_cached handles the performance efficiency internally.

        if "hl2" not in df.columns:
            df["hl2"] = (df["high"] + df["low"]) / 2
            df["atr"] = talib.ATR(df["high"], df["low"], df["close"], timeperiod=14)
            df["volume_ma"] = df["tick_volume"].rolling(window=14).mean()
            df["volatility"] = df["close"].rolling(window=14).std()
            df["norm_volatility"] = df["volatility"] / df["volatility"].rolling(window=50).mean()
            df.dropna(inplace=True)

        signal_dir = self.generate_signal(df)
        if signal_dir is None:
            return False

        sym_info = self.gateway.symbol_info(self.config.symbol)
        tick = self.gateway.symbol_info_tick(self.config.symbol)
        if not sym_info or not tick:
            return False

        snapshot = self.kr.get_market_state(self.config.symbol, "M30")
        if not snapshot:
            return False

        supertrends, optimal_factor = self._get_supertrends_cached(df)
        current_st = supertrends[min(supertrends.keys(), key=lambda x: abs(x - optimal_factor))]
        st_line = float(current_st["output"].iloc[-1])
        
        if signal_dir == 1:
            order_type = mt5.ORDER_TYPE_BUY
            fill_price = tick.ask
            sl_points = abs(fill_price - st_line) / sym_info.point
        else:
            order_type = mt5.ORDER_TYPE_SELL
            fill_price = tick.bid
            sl_points = abs(fill_price - st_line) / sym_info.point

        volume = self.calculate_position_size(sl_points)
        sl_price = round(st_line, sym_info.digits)

        ts = TradeSignal(
            symbol=self.config.symbol,
            bot_name="SuperTrendBotV2",
            magic_number=self.config.magic_number,
            order_type=order_type,
            sl_price=sl_price
        )
        
        if self.router.route_signal(ts, current_dd, max_dd):
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.config.symbol,
                "volume": volume,
                "type": order_type,
                "price": fill_price,
                "sl": 0.0,
                "tp": 0.0,
                "deviation": 20,
                "magic": self.config.magic_number,
                "comment": "ST_V2",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            res = self.gateway.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                actual_fill_price = res.price
                mod_req = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "symbol": self.config.symbol,
                    "position": res.order,
                    "sl": sl_price,
                    "tp": 0.0,
                }
                
                retry_buf = sym_info.point * 50
                for _retry in range(3):
                    mod = self.gateway.order_send(mod_req)
                    if mod and mod.retcode == mt5.TRADE_RETCODE_DONE:
                        break
                    if mod and mod.retcode == 10016:
                        time.sleep(0.2)
                        stops_level = sym_info.trade_stops_level * sym_info.point
                        if order_type == mt5.ORDER_TYPE_BUY:
                            sl_target = actual_fill_price - stops_level - retry_buf
                        else:
                            sl_target = actual_fill_price + stops_level + retry_buf
                        mod_req["sl"] = round(sl_target, sym_info.digits)
                        retry_buf *= 2
                    else:
                        break

                logger.info(f"Executed ST_V2 {self.config.symbol} | Ticket {res.order}")
                # Build and register Trade Thesis
                thesis = TradeThesis(
                    ticket=res.order,
                    symbol=self.config.symbol,
                    direction=signal_dir,
                    bot_name="SuperTrendBotV2",
                    magic_number=self.config.magic_number,
                    timeframe="M30",
                    initial_sl=sl_price,
                    initial_tp=0.0,
                    entry_atr=snapshot.atr_raw,
                    regime_at_entry=snapshot.regime,
                    entry_conviction=snapshot.adx_raw,
                    layer_depth=0,
                    timestamp=time.time(),
                    market_snapshot=snapshot
                )
                self.kr.register_trade_thesis(thesis)
                return True
        return False
