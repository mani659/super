import logging
import numpy as np
import pandas as pd
from typing import Tuple, Optional, Dict, List
from sklearn.cluster import KMeans
from dataclasses import dataclass, field
from datetime import datetime

from v2.core.knowledge_register import KnowledgeRegister
from v2.core.data_models import TradeSignal, TradeThesis
from v2.execution.mt5_gateway import MT5Gateway
from v2.execution.order_router import OrderRouter
from v2.core.utils import calculate_dynamic_lot
import MetaTrader5 as mt5
import time
import talib

logger = logging.getLogger("SuperTrendBotV2")

# ==============================================================================
# V1 PARITY NOTE (core/supertrend_bot.py Config)
# Every default below mirrors V1's production-calibrated Config exactly.
# V2 previously used a different factor universe (2.0-4.0 step 0.1), different
# indicator periods, no session gate, no KR Layer 2/3, and a different exit
# manager — all of which made V2 drift from the V1 shadow.
# ==============================================================================


@dataclass
class SuperTrendConfig:
    symbol: str
    magic_number: int
    # K-Means SuperTrend (V1 values)
    atr_period: int = 10
    min_factor: float = 1.0
    max_factor: float = 5.0
    factor_step: float = 0.5
    perf_alpha: int = 10
    cluster_choice: str = "Best"  # "Worst", "Average", "Best"
    # Volume gate (V1 values)
    volume_ma_period: int = 20
    volume_multiplier: float = 1.2
    # Risk (V1 values)
    risk_percent: float = 1.0
    max_positions: int = 1
    max_lot_demo_cap: Optional[float] = 0.01
    # Hard SL / Safety TP (V1 values)
    sl_multiplier: float = 2.0
    tp_safety_multiplier: float = 5.0
    # Dynamic incubation (V1 values)
    incubation_bars: int = 2
    incubation_bars_trending: int = 2
    incubation_bars_stable: int = 2
    incubation_bars_exhaustion: int = 3
    # State machine thresholds (V1 values)
    si_confirmed: float = 0.55
    si_decaying: float = 0.50
    si_dead: float = 0.35
    er_confirmed: float = 0.35
    er_dead: float = 0.20
    er_bars_for_dead: int = 3
    decaying_tolerance_bars: int = 1
    # Regime urgency modifiers (V1 values)
    regime_exhaustion_si_penalty: float = 0.10
    regime_trending_with_si_bonus: float = 0.05
    # SI component weights (V1 values)
    si_weight_cluster: float = 0.40
    si_weight_regime: float = 0.25
    si_weight_adx: float = 0.20
    si_weight_volume: float = 0.15
    # Partial close (V1 values)
    enable_partial_close: bool = True
    si_partial_close_min: float = 0.55
    partial_close_profit_atr_mult: float = 1.5
    partial_close_fraction: float = 0.50
    # Session gate (V1 values: ASIAN blocks FX pairs; metals exempt)
    session_gate_enabled: bool = True
    session_gate_pairs: tuple = ("EURUSDm", "GBPUSDm")
    # Conviction gate (disabled in V1 unified runner — observation only)
    conviction_gate_enabled: bool = False
    conviction_min_threshold: float = 45.0
    # M15 ATR for SL buffer (V1 enabled)
    use_m15_atr_for_sl_buffer: bool = True


@dataclass
class TradeContext:
    """V1 parity — per-ticket context for the SI/ER state machine."""
    ticket: int
    direction: int
    entry_price: float
    entry_sl: float
    entry_tp: float
    entry_time: datetime
    entry_bar_time: object
    entry_st_factor: float
    entry_st_line: float
    entry_regime: str
    entry_adx_rank: float
    entry_atr_rank: float
    entry_cluster_agreement: int
    entry_total_factors: int
    entry_volume_ratio: float
    entry_atr: float
    state: str = ""
    bars_in_decaying: int = 0
    bars_in_incubating: int = 0


class SuperTrendBot:
    """
    V2 SuperTrend Bot — V1 shadow (core/supertrend_bot.py parity).
    K-Means clustered SuperTrend bands on M30, signal generation, and the
    full V1 SI/ER state machine for position management. The bot manages its
    own positions (V1 architecture) — TradeManager must NOT double-manage
    ST magics.
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
        self.trade_contexts: Dict[int, TradeContext] = {}
        self._partial_closed_tickets: set = set()

    # ==========================================================================
    # DATA / INDICATORS  (V1 get_data() parity — periods from config)
    # ==========================================================================
    def _prepare_df(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        if "time" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["time"]):
            df["time"] = pd.to_datetime(df["time"], unit="s")
            df.set_index("time", inplace=True)
        if "hl2" not in df.columns:
            df["hl2"] = (df["high"] + df["low"]) / 2
            df["atr"] = talib.ATR(df["high"], df["low"], df["close"], timeperiod=self.config.atr_period)
            df["volume_ma"] = df["tick_volume"].rolling(window=self.config.volume_ma_period).mean()
            df["volatility"] = df["close"].rolling(window=self.config.atr_period).std()
            df["norm_volatility"] = df["volatility"] / df["volatility"].rolling(window=50).mean()
            df.dropna(inplace=True)
        return df

    # ==========================================================================
    # K-MEANS SUPERTREND  (unchanged — matches V1 core logic)
    # ==========================================================================
    def calculate_supertrends(self, df: pd.DataFrame) -> dict:
        factors = np.arange(
            self.config.min_factor,
            self.config.max_factor + self.config.factor_step,
            self.config.factor_step
        )
        supertrends = {}
        for factor in factors:
            st = pd.DataFrame(index=df.index)
            st["upper"] = df["hl2"] + (df["atr"] * factor)
            st["lower"] = df["hl2"] - (df["atr"] * factor)
            st["trend"] = 0
            st["output"] = 0.0
            st["perf"] = 0.0
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
                    st.at[st.index[i], "lower"] = new_lower
                    st.at[st.index[i], "output"] = new_lower
                else:
                    new_upper = st["upper"].iloc[i]
                    if prev_trend == 0:
                        new_upper = min(new_upper, st["upper"].iloc[i - 1])
                    st.at[st.index[i], "upper"] = new_upper
                    st.at[st.index[i], "output"] = new_upper

                price_change = df["close"].iloc[i] - df["close"].iloc[i - 1]
                direction = np.sign(df["close"].iloc[i - 1] - st["output"].iloc[i - 1])
                raw_perf = price_change * direction
                alpha = 2 / (self.config.perf_alpha + 1)
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
        sorted_idx = np.argsort(kmeans.cluster_centers_.flatten())
        cluster_map = {"Worst": 0, "Average": 1, "Best": 2}
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

    # ==========================================================================
    # VOLUME / SIGNAL  (V1 generate_signal() parity)
    # ==========================================================================
    def check_volume_condition(self, df: pd.DataFrame) -> bool:
        return (
            float(df["tick_volume"].iloc[-1]) >
            float(df["volume_ma"].iloc[-1]) * self.config.volume_multiplier
        )

    def generate_signal(self, df: pd.DataFrame, supertrends: dict = None,
                        optimal_factor: float = None) -> Optional[int]:
        """Returns 1 for BUY, -1 for SELL, None for no signal. V1 parity."""
        if df is None or len(df) < 200:
            return None

        if supertrends is None or optimal_factor is None:
            supertrends, optimal_factor = self._get_supertrends_cached(df)

        current_st = supertrends[min(supertrends.keys(), key=lambda x: abs(x - optimal_factor))]
        cur_trend = int(current_st["trend"].iloc[-1])
        prev_trend = int(current_st["trend"].iloc[-2])

        if not self.check_volume_condition(df):
            return None

        # 1. Trend Flip Signal
        if cur_trend > prev_trend:
            return 1
        if cur_trend < prev_trend:
            return -1

        # 2. Trend Continuation Signal (V1 parity — including V1's quirk that
        #    trend values are 0/1, so the SELL-continuation branch is dead in
        #    V1 too. Kept identical so the shadow behaves exactly like V1.)
        N = 3
        if len(df) > N + 1:
            last_close = float(df["close"].iloc[-1])
            expected_trend = 1 if cur_trend == 1 else 0
            agreeing_count = sum(
                1 for st in supertrends.values()
                if int(st["trend"].iloc[-1]) == expected_trend
            )
            # V1 parity: floor at 3 (V2 previously used max(1, ...))
            min_agree = max(3, len(supertrends) // 3)

            if agreeing_count >= min_agree:
                if cur_trend == 1:
                    recent_high = float(df["high"].iloc[-(N + 1):-1].max())
                    if last_close > recent_high:
                        return 1
                elif cur_trend == -1:
                    recent_low = float(df["low"].iloc[-(N + 1):-1].min())
                    if last_close < recent_low:
                        return -1
        return None

    # ==========================================================================
    # SESSION GATE  (V1 parity: ASIAN blocks gated FX pairs only)
    # ==========================================================================
    def _get_session(self) -> str:
        hour = datetime.utcnow().hour
        if hour < 7:
            return "ASIAN"
        if hour < 12:
            return "LONDON"
        if hour < 17:
            return "NY_OVERLAP"
        return "OTHER"

    def _is_session_allowed(self) -> bool:
        if not self.config.session_gate_enabled:
            return True
        if self._get_session() != "ASIAN":
            return True
        sym = self.config.symbol
        for gated in self.config.session_gate_pairs:
            if gated.upper() in sym.upper():
                logger.info(
                    f"SESSION GATE ACTIVE | session=ASIAN | {sym} entry suppressed"
                )
                return False
        return True

    # ==========================================================================
    # CONVICTION  (V1 parity — computed always, gate disabled by default)
    # ==========================================================================
    def _compute_conviction_score(self, regime_data: dict, df: pd.DataFrame) -> float:
        adx_raw = regime_data.get("adx_raw", 20.0)
        try:
            last_open = float(df["open"].iloc[-1])
            last_close = float(df["close"].iloc[-1])
            last_high = float(df["high"].iloc[-1])
            last_low = float(df["low"].iloc[-1])
            bar_range = last_high - last_low
            body = abs(last_close - last_open)
            body_ratio = (body / bar_range * 100) if bar_range > 0 else 0.0
        except Exception:
            body_ratio = 50.0
        conviction = adx_raw * 1.0 + body_ratio * 0.5
        return round(float(conviction), 2)

    # ==========================================================================
    # M15 ATR FOR SL BUFFER  (V1 parity)
    # ==========================================================================
    def _get_m15_atr(self) -> Optional[float]:
        try:
            rates = self.gateway.copy_rates_from_pos(
                self.config.symbol, mt5.TIMEFRAME_M15, 0, 60
            )
            if rates is None or len(rates) < 15:
                return None
            df_m15 = pd.DataFrame(rates)
            atr_series = talib.ATR(
                df_m15["high"], df_m15["low"], df_m15["close"],
                timeperiod=self.config.atr_period
            )
            val = float(atr_series.iloc[-1])
            return val if not np.isnan(val) else None
        except Exception as exc:
            logger.debug(f"_get_m15_atr failed: {exc}")
            return None

    # ==========================================================================
    # REGIME DATA  (V1 _get_market_regime() parity — H4 snapshot from KR)
    # ==========================================================================
    def _get_market_regime(self) -> dict:
        snapshot = self.kr.get_market_state(self.config.symbol, "H4")
        if not snapshot:
            return {
                "regime": "STABLE",
                "reason": "No Layer 0 state available",
                "scores": {},
                "atr_raw": 1.0,
                "adx_raw": 20.0
            }
        scores = {
            "adx_rank": snapshot.adx_percentile,
            "atr_rank": snapshot.atr_percentile,
            "br_rank": snapshot.body_range_ratio * 100.0,
        }
        regime_str = snapshot.regime
        if regime_str.startswith("TRENDING"):
            regime_str = "TRENDING"
        return {
            "regime": regime_str,
            "reason": f"Layer 0 | ADX {scores['adx_rank']:.0f}th | ATR {scores['atr_rank']:.0f}th",
            "scores": scores,
            "atr_raw": snapshot.atr_raw,
            "adx_raw": snapshot.adx_raw
        }

    # ==========================================================================
    # POSITION SIZING  (V1 risk-based with demo cap)
    # ==========================================================================
    def calculate_position_size(self, stop_loss_points: float) -> float:
        sym_info = self.gateway.symbol_info(self.config.symbol)
        if not sym_info:
            return 0.01
        sl_price_dist = stop_loss_points * sym_info.point
        return calculate_dynamic_lot(
            gateway=self.gateway,
            symbol=self.config.symbol,
            risk_percent=self.config.risk_percent,
            sl_dist_price=sl_price_dist,
            max_lot_demo_cap=self.config.max_lot_demo_cap
        )

    # ==========================================================================
    # EXECUTION HELPERS
    # ==========================================================================
    def _modify_sl(self, pos, new_sl: float, label: str = "") -> bool:
        sym_info = self.gateway.symbol_info(pos.symbol)
        tick = self.gateway.symbol_info_tick(pos.symbol)
        if not sym_info or not tick:
            return False
        stops_dist = sym_info.trade_stops_level * sym_info.point
        curr_price = tick.bid if pos.type == 0 else tick.ask
        if stops_dist > 0 and abs(new_sl - curr_price) < stops_dist:
            buf = sym_info.point * 30
            new_sl = (
                curr_price - stops_dist - buf if pos.type == 0
                else curr_price + stops_dist + buf
            )
        rounded = round(new_sl, sym_info.digits)
        if rounded == round(pos.sl, sym_info.digits):
            return True
        req = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": pos.symbol,
            "position": pos.ticket,
            "sl": rounded,
            "tp": pos.tp,
        }
        res = self.gateway.order_send(req)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"[MANAGEMENT] #{pos.ticket} [{pos.symbol}] {label} -> SL {rounded:.5f}")
            return True
        logger.debug(f"_modify_sl FAILED #{pos.ticket} retcode={res.retcode if res else 'None'}")
        return False

    def _close_position(self, pos, reason: str) -> bool:
        tick = self.gateway.symbol_info_tick(pos.symbol)
        if not tick:
            return False
        is_buy = (pos.type == 0)
        order_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
        price = tick.bid if is_buy else tick.ask
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": pos.magic,
            "comment": str(reason)[:28],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = self.gateway.order_send(req)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            return True
        elif res and res.retcode == 10013:
            verify = self.gateway.positions_get(ticket=pos.ticket)
            if not verify:
                return True
        return False

    # ==========================================================================
    # STATE MACHINE  (V1 manage_open_positions() + helpers — full port)
    # ==========================================================================
    def _compute_signal_integrity(self, ctx: TradeContext, supertrends: dict,
                                  regime_data: dict, df: pd.DataFrame) -> float:
        cfg = self.config
        expected_trend = 1 if ctx.direction == 1 else 0
        agreeing = sum(
            1 for st in supertrends.values()
            if int(st["trend"].iloc[-1]) == expected_trend
        )
        cluster_ratio = agreeing / max(len(supertrends), 1)
        regime_match = 1.0 if regime_data["regime"] == ctx.entry_regime else 0.0
        cur_adx_rank = regime_data["scores"].get("adx_rank", 50)
        adx_ratio = min(cur_adx_rank / max(ctx.entry_adx_rank, 1), 1.0)
        vol_ma = float(df["volume_ma"].iloc[-1])
        cur_vol_ratio = (
            float(df["tick_volume"].iloc[-1]) / vol_ma if vol_ma > 0 else 1.0
        )
        vol_ratio = min(cur_vol_ratio / max(ctx.entry_volume_ratio, 0.01), 1.0)
        si = (
            cfg.si_weight_cluster * cluster_ratio +
            cfg.si_weight_regime * regime_match +
            cfg.si_weight_adx * adx_ratio +
            cfg.si_weight_volume * vol_ratio
        )
        return round(float(np.clip(si, 0.0, 1.0)), 4)

    def _compute_efficiency_ratio(self, df: pd.DataFrame, bars: int) -> float:
        bars = max(2, min(bars, 8))
        if len(df) < bars + 1:
            return 0.5
        closes = df["close"].iloc[-(bars + 1):].values
        net_move = abs(closes[-1] - closes[0])
        total_path = float(np.sum(np.abs(np.diff(closes))))
        if total_path == 0:
            return 0.0
        return round(float(np.clip(net_move / total_path, 0.0, 1.0)), 4)

    def _get_dynamic_incubation(self, regime: str) -> int:
        return {
            "TRENDING": self.config.incubation_bars_trending,
            "STABLE": self.config.incubation_bars_stable,
            "EXHAUSTION": self.config.incubation_bars_exhaustion,
        }.get(regime, self.config.incubation_bars)

    def _evaluate_state(self, ctx: TradeContext, si: float, er: float,
                        bars_held: int, st_trend_current: int, regime: str) -> str:
        cfg = self.config
        expected_trend = 1 if ctx.direction == 1 else 0

        si_confirmed = cfg.si_confirmed
        si_decaying = cfg.si_decaying
        si_dead = cfg.si_dead

        if regime == "EXHAUSTION":
            si_confirmed += cfg.regime_exhaustion_si_penalty
            si_decaying += cfg.regime_exhaustion_si_penalty
            si_dead += cfg.regime_exhaustion_si_penalty
        elif regime == "TRENDING" and si >= cfg.si_confirmed:
            si_confirmed -= cfg.regime_trending_with_si_bonus
            si_decaying -= cfg.regime_trending_with_si_bonus

        if st_trend_current != expected_trend:
            return "DEAD"
        if si < si_dead:
            return "DEAD"
        if bars_held >= cfg.er_bars_for_dead and er < cfg.er_dead:
            return "DEAD"

        incubation_bars = self._get_dynamic_incubation(regime)
        if bars_held < incubation_bars:
            return "INCUBATING"

        if si < si_decaying:
            return "DECAYING"
        if si < si_confirmed and er < cfg.er_confirmed:
            return "DECAYING"
        if si >= si_confirmed and er >= cfg.er_confirmed:
            return "CONFIRMED"
        return "DECAYING"

    def _try_partial_close(self, pos, si: float, current_atr: float) -> bool:
        cfg = self.config
        if not cfg.enable_partial_close:
            return False
        if pos.ticket in self._partial_closed_tickets:
            return False
        ctx = self.trade_contexts.get(pos.ticket)
        if ctx is None:
            return False
        if si < cfg.si_partial_close_min:
            return False

        profit_in_atr = abs(pos.price_current - ctx.entry_price) / max(current_atr, 1e-10)
        if profit_in_atr < cfg.partial_close_profit_atr_mult:
            return False

        sym_info = self.gateway.symbol_info(self.config.symbol)
        if sym_info is None:
            return False

        raw_partial = pos.volume * cfg.partial_close_fraction
        partial_vol = round(raw_partial / sym_info.volume_step) * sym_info.volume_step
        partial_vol = max(sym_info.volume_min, partial_vol)
        remainder = round(pos.volume - partial_vol, 8)

        if remainder < sym_info.volume_min:
            # V1 behavior: remainder too small — skip partial (position stays whole)
            return False

        is_buy = (pos.type == 0)
        tick = self.gateway.symbol_info_tick(self.config.symbol)
        if tick is None:
            return False
        order_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
        price = tick.bid if is_buy else tick.ask
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "volume": partial_vol,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": pos.magic,
            "comment": "PARTIAL_CLOSE",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = self.gateway.order_send(req)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            self._partial_closed_tickets.add(pos.ticket)
            logger.info(f"  * PARTIAL CLOSE #{pos.ticket} | closed {partial_vol} lots | SI={si:.3f}")
            return True
        return False

    def _resolve_proposed_sl(self, pos, ctx: TradeContext, is_buy: bool, r_now: float,
                             st_line_now: float, st_trend_now: int):
        candidates = []

        if ctx.entry_sl != 0:
            entry_risk = abs(ctx.entry_price - ctx.entry_sl)
            if entry_risk > 0:
                if r_now is None:
                    price_move = (
                        (pos.price_current - ctx.entry_price) if is_buy
                        else (ctx.entry_price - pos.price_current)
                    )
                    r_now = price_move / entry_risk
                sym_info_r = self.gateway.symbol_info(self.config.symbol)
                buf = (sym_info_r.point * 30) if sym_info_r else 0

                if r_now >= 3.0:
                    lock_sl = (ctx.entry_price + entry_risk * 2.0 + buf) if is_buy \
                        else (ctx.entry_price - entry_risk * 2.0 - buf)
                    candidates.append((lock_sl, "R3_LOCK_2R"))
                elif r_now >= 2.0:
                    lock_sl = (ctx.entry_price + entry_risk * 1.0 + buf) if is_buy \
                        else (ctx.entry_price - entry_risk * 1.0 - buf)
                    candidates.append((lock_sl, "R2_LOCK_1R"))
                elif r_now >= 1.0:
                    lock_sl = (ctx.entry_price + buf) if is_buy else (ctx.entry_price - buf)
                    candidates.append((lock_sl, "R1_BE_LOCK"))

        if is_buy and st_trend_now == 1:
            candidates.append((st_line_now, "CONFIRMED|ST_TRAIL"))
        elif not is_buy and st_trend_now == 0:
            candidates.append((st_line_now, "CONFIRMED|ST_TRAIL"))

        if not candidates:
            return None, ""

        if is_buy:
            tightest = max(candidates, key=lambda x: x[0])
        else:
            tightest = min(candidates, key=lambda x: x[0])
        return tightest

    def _build_dead_reason(self, si, er, bars_held, st_trend_current, ctx) -> str:
        expected = 1 if ctx.direction == 1 else 0
        if st_trend_current != expected:
            return "ST_LINE_FLIPPED"
        if si < self.config.si_dead:
            return f"SI_COLLAPSED_{si:.3f}"
        if bars_held >= self.config.er_bars_for_dead and er < self.config.er_dead:
            return f"ER_CHURN_{er:.3f}_b{bars_held}"
        return f"SI_{si:.3f}_ER_{er:.3f}"

    def _timeframe_seconds(self) -> int:
        return {
            mt5.TIMEFRAME_M1: 60,
            mt5.TIMEFRAME_M5: 300,
            mt5.TIMEFRAME_M15: 900,
            mt5.TIMEFRAME_M30: 1800,
            mt5.TIMEFRAME_H1: 3600,
            mt5.TIMEFRAME_H4: 14400,
            mt5.TIMEFRAME_D1: 86400,
        }.get(mt5.TIMEFRAME_M30, 1800)

    def manage_open_positions(self, df: pd.DataFrame, supertrends: dict,
                              optimal_factor: float, regime_data: dict):
        """V1 manage_open_positions() full port — SI/ER state machine."""
        positions = self.gateway.positions_get(symbol=self.config.symbol)
        if not positions:
            self.trade_contexts.clear()
            return

        regime = regime_data["regime"]
        regime_reason = regime_data["reason"]

        closest_factor = min(supertrends.keys(), key=lambda x: abs(x - optimal_factor))
        current_st = supertrends[closest_factor]
        st_line_now = float(current_st["output"].iloc[-1])
        st_trend_now = int(current_st["trend"].iloc[-1])
        current_atr = float(df["atr"].iloc[-1])

        dyn_incubation = self._get_dynamic_incubation(regime)

        for pos in positions:
            if pos.magic != self.config.magic_number:
                continue

            is_buy = (pos.type == 0)
            ctx = self.trade_contexts.get(pos.ticket)

            # Context recovery (V1 parity)
            if ctx is None:
                vm = float(df["volume_ma"].iloc[-1])
                ctx = TradeContext(
                    ticket=pos.ticket,
                    direction=1 if is_buy else -1,
                    entry_price=pos.price_open,
                    entry_sl=pos.sl,
                    entry_tp=pos.tp,
                    entry_time=datetime.fromtimestamp(pos.time),
                    entry_bar_time=datetime.fromtimestamp(pos.time),
                    entry_st_factor=optimal_factor,
                    entry_st_line=st_line_now,
                    entry_regime=regime,
                    entry_adx_rank=regime_data["scores"].get("adx_rank", 50),
                    entry_atr_rank=regime_data["scores"].get("atr_rank", 50),
                    entry_cluster_agreement=sum(
                        1 for st in supertrends.values()
                        if int(st["trend"].iloc[-1]) == (1 if is_buy else 0)
                    ),
                    entry_total_factors=len(supertrends),
                    entry_volume_ratio=(
                        float(df["tick_volume"].iloc[-1]) / vm if vm > 0 else 1.0
                    ),
                    entry_atr=current_atr,
                )
                self.trade_contexts[pos.ticket] = ctx

            tf_secs = self._timeframe_seconds()
            bars_held = max(
                0,
                int((datetime.now() - ctx.entry_time).total_seconds() / tf_secs)
            )

            si = self._compute_signal_integrity(ctx, supertrends, regime_data, df)
            er = self._compute_efficiency_ratio(df, bars=max(2, min(bars_held, 8)))
            state = self._evaluate_state(ctx, si, er, bars_held, st_trend_now, regime)
            ctx.state = state

            if state == "DEAD":
                reason = self._build_dead_reason(si, er, bars_held, st_trend_now, ctx)
                self.kr.publish_invalidation(
                    symbol=self.config.symbol,
                    direction=ctx.direction,
                    source_bot="SuperTrend",
                    reason=f"ST DEAD-state: {reason}",
                    ttl_seconds=3600.0
                )
                if self._close_position(pos, f"DEAD|{reason}"):
                    self.trade_contexts.pop(pos.ticket, None)
                continue

            elif state == "INCUBATING":
                remaining = dyn_incubation - bars_held
                logger.info(f"  #{pos.ticket} INCUBATING | {remaining} bar(s) remaining (regime={regime})")
                if is_buy and st_line_now > pos.sl and st_trend_now == 1:
                    self._modify_sl(pos, st_line_now, label="INCUBATING_FLOOR")
                elif not is_buy and (pos.sl == 0 or st_line_now < pos.sl) and st_trend_now == 0:
                    self._modify_sl(pos, st_line_now, label="INCUBATING_FLOOR")

            elif state == "CONFIRMED":
                ctx.bars_in_decaying = 0
                self._try_partial_close(pos, si=si, current_atr=current_atr)

                tightest_sl, sl_label = self._resolve_proposed_sl(
                    pos, ctx, is_buy, r_now=None,
                    st_line_now=st_line_now, st_trend_now=st_trend_now
                )
                if tightest_sl is not None:
                    self._modify_sl(pos, tightest_sl, label=sl_label)

            elif state == "DECAYING":
                if is_buy and st_trend_now == 1:
                    self._modify_sl(pos, st_line_now, label="DECAYING|TIGHTEN")
                elif not is_buy and st_trend_now == 0:
                    self._modify_sl(pos, st_line_now, label="DECAYING|TIGHTEN")

                ctx.bars_in_decaying += 1
                logger.info(
                    f"  #{pos.ticket} DECAYING {ctx.bars_in_decaying}/{self.config.decaying_tolerance_bars} | "
                    f"SI={si:.3f} | ER={er:.3f}"
                )
                if ctx.bars_in_decaying > self.config.decaying_tolerance_bars:
                    if self._close_position(pos, f"DECAYING_TIMEOUT|SI={si:.3f}|ER={er:.3f}"):
                        self.trade_contexts.pop(pos.ticket, None)

    # ==========================================================================
    # MAIN CYCLE  (V1 run_cycle() parity: manage FIRST, then entry)
    # ==========================================================================
    def execute_cycle(self, df: pd.DataFrame, current_dd: float, max_dd: float,
                      allow_new_entry: bool = True):
        """allow_new_entry mirrors V1 SuperTrendBot.run_cycle(allow_new_entry=...)
        (core/supertrend_bot.py:1532). When False the position-management pass
        still runs -- it is called first, below -- and only NEW entries are
        blocked. That ordering is deliberate and matches V1 exactly: the
        switches doc in config.json states that a switch set to false blocks
        new entries only, and that open positions are always still managed.
        """
        df = self._prepare_df(df)
        if df is None or len(df) < 200:
            return False

        # Bar-aware cache — recomputes only on new bar close (V1 parity)
        supertrends, optimal_factor = self._get_supertrends_cached(df)
        regime_data = self._get_market_regime()

        logger.info(
            f"CYCLE | price={float(df['close'].iloc[-1]):.5f} | "
            f"ATR={float(df['atr'].iloc[-1]):.5f} | "
            f"factor={optimal_factor:.2f} | Regime={regime_data['regime']}"
        )

        # Watcher brain FIRST (V1 run_cycle ordering)
        self.manage_open_positions(df, supertrends, optimal_factor, regime_data)

        # fix-switches (V1 parity, core/supertrend_bot.py:1562): switch off =
        # no NEW entries. Management above has already run this cycle.
        if not allow_new_entry:
            logger.info(
                f"ENTRY BLOCKED | {self.config.symbol} | supertrend_enabled=false"
            )
            return False

        # ---- Entry check (V1 parity sequence) --------------------------------
        if not self._is_session_allowed():
            return False

        positions = self.gateway.positions_get(symbol=self.config.symbol)
        open_count = (
            len([p for p in positions if p.magic == self.config.magic_number])
            if positions else 0
        )

        signal = self.generate_signal(df, supertrends, optimal_factor)
        if signal not in (1, -1):
            return False

        # Auto-Reversal & Max Positions (V1 parity)
        my_positions = [p for p in (positions or []) if p.magic == self.config.magic_number]
        if my_positions:
            pos = my_positions[0]
            is_buy_signal = (signal == 1)
            is_buy_pos = (pos.type == 0)
            if is_buy_signal == is_buy_pos:
                logger.info(f"Signal matches open position #{pos.ticket} direction. Holding trade.")
                return False
            else:
                logger.warning(f"Reversal signal detected! Closing opposite position #{pos.ticket}.")
                if self._close_position(pos, "REVERSAL"):
                    time.sleep(0.5)
                    open_count -= 1
                    my_positions.clear()
                    self.trade_contexts.pop(pos.ticket, None)
                else:
                    return False

        if open_count >= self.config.max_positions:
            return False

        # Group risk view (V1 parity: continuation blocked at agg R <= -1.0)
        if open_count > 0:
            agg_r = 0.0
            for p in my_positions:
                risk_dist = abs(p.price_open - p.sl)
                if risk_dist > 0:
                    price_move = (p.price_current - p.price_open) if p.type == 0 else (p.price_open - p.price_current)
                    agg_r += price_move / risk_dist
            if agg_r <= -1.0:
                logger.info(
                    f"Continuation BLOCKED | symbol={self.config.symbol} "
                    f"aggregate R={agg_r:.2f} <= -1.0R"
                )
                return False

        # KR Layer 2 & 3: Hard Blocks (V1 parity)
        is_buy = (signal == 1)
        kr_dir = 1 if is_buy else -1
        invalidated, inv_reason = self.kr.is_entry_invalidated(self.config.symbol, kr_dir)
        if invalidated:
            logger.info(f"Entry BLOCKED by KR Layer 2: {inv_reason}")
            return False
        acc = self.gateway.account_info()
        equity = acc.equity if acc else 10000.0
        allowed, p_reason = self.kr.check_portfolio_entry_allowed(
            symbol=self.config.symbol,
            direction=kr_dir,
            proposed_risk_pct=0.5,
            account_equity=equity
        )
        if not allowed:
            logger.info(f"Entry BLOCKED by KR Layer 3: {p_reason}")
            return False

        # Conviction gate (V1 parity: disabled by default — compute only)
        conviction = self._compute_conviction_score(regime_data, df)
        if self.config.conviction_gate_enabled:
            if conviction < self.config.conviction_min_threshold:
                logger.info(
                    f"Entry BLOCKED by conviction gate | "
                    f"conviction={conviction:.1f} < {self.config.conviction_min_threshold}"
                )
                return False

        # SL/TP sizing (V1 parity: M15 ATR buffer x 2.0 SL, M30 ATR x 5.0 TP)
        current_atr = float(df["atr"].iloc[-1])
        m15_atr = None
        if self.config.use_m15_atr_for_sl_buffer:
            m15_atr = self._get_m15_atr()
        sl_atr = m15_atr if m15_atr is not None else current_atr

        tick_now = self.gateway.symbol_info_tick(self.config.symbol)
        if tick_now is None:
            return False
        ref_price = tick_now.ask if is_buy else tick_now.bid

        sl = (
            ref_price - sl_atr * self.config.sl_multiplier if is_buy
            else ref_price + sl_atr * self.config.sl_multiplier
        )
        tp = (
            ref_price + current_atr * self.config.tp_safety_multiplier if is_buy
            else ref_price - current_atr * self.config.tp_safety_multiplier
        )

        sym_info = self.gateway.symbol_info(self.config.symbol)
        if not sym_info:
            return False
        sl_points = abs(ref_price - sl) / sym_info.point
        volume = self.calculate_position_size(sl_points)

        # -- Entry quality context (LOGGING ONLY — never gates the entry) --------
        # V1 parity (core/supertrend_bot.run_cycle). Features available at entry time
        # for the offline win/loss classifier, pre-seeded to 0.0 and computed inside
        # try/except so a failure here can never block or alter the trade.
        cluster_spread = 0.0
        cluster_consensus = 0.0
        er_at_entry = 0.0
        try:
            perf_list = [st["vol_adj_perf"].iloc[-100:].mean()
                         for st in supertrends.values()]
            cluster_spread = float(max(perf_list) - min(perf_list)) if perf_list else 0.0
            er_at_entry = self._compute_efficiency_ratio(df, bars=8)
            expected_trend_val = 1 if is_buy else 0
            agreeing = sum(
                1 for st in supertrends.values()
                if int(st["trend"].iloc[-1]) == expected_trend_val
            )
            cluster_consensus = agreeing / max(len(supertrends), 1)
            logger.info(
                f"ENTRY_QUALITY | {self.config.symbol} | "
                f"cluster_spread={cluster_spread:.4f} | "
                f"cluster_consensus={cluster_consensus:.3f} | "
                f"er_at_entry={er_at_entry:.3f} | "
                f"direction={'BUY' if is_buy else 'SELL'}"
            )
        except Exception as _eq:
            logger.debug(f"Entry quality log error: {_eq}")

        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL

        ts = TradeSignal(
            symbol=self.config.symbol,
            bot_name="SuperTrendBotV2",
            magic_number=self.config.magic_number,
            order_type=order_type,
            sl_price=sl
        )
        if not self.router.route_signal(ts, current_dd, max_dd):
            return False

        # V1 parity: SL and TP are placed directly in the market order request
        # (V1 place_order). If stops are invalid (10016), the order is REJECTED
        # and no trade happens — exactly like V1. No two-phase widening.
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.config.symbol,
            "volume": volume,
            "type": order_type,
            "price": ref_price,
            "sl": round(sl, sym_info.digits),
            "tp": round(tp, sym_info.digits),
            "deviation": 20,
            "magic": self.config.magic_number,
            "comment": "ST_V2",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = self.gateway.order_send(req)
        if not (res and res.retcode == mt5.TRADE_RETCODE_DONE):
            if res:
                logger.info(f"ST order FAILED | code={res.retcode} | {getattr(res, 'comment', '')}")
            return False

        actual_fill_price = res.price
        logger.info(f"Executed ST_V2 {self.config.symbol} | Ticket {res.order}")

        # Build context snapshot (V1 parity)
        closest_factor = min(supertrends.keys(), key=lambda x: abs(x - optimal_factor))
        st_entry = supertrends[closest_factor]
        st_line_entry = float(st_entry["output"].iloc[-1])
        entry_agree = sum(
            1 for st in supertrends.values()
            if int(st["trend"].iloc[-1]) == (1 if is_buy else 0)
        )
        vm = float(df["volume_ma"].iloc[-1])
        vol_ratio = float(df["tick_volume"].iloc[-1]) / vm if vm > 0 else 1.0

        ctx = TradeContext(
            ticket=res.order,
            direction=1 if is_buy else -1,
            entry_price=ref_price,
            entry_sl=sl,
            entry_tp=tp,
            entry_time=datetime.now(),
            entry_bar_time=df.index[-1],
            entry_st_factor=optimal_factor,
            entry_st_line=st_line_entry,
            entry_regime=regime_data["regime"],
            entry_adx_rank=regime_data["scores"].get("adx_rank", 50),
            entry_atr_rank=regime_data["scores"].get("atr_rank", 50),
            entry_cluster_agreement=entry_agree,
            entry_total_factors=len(supertrends),
            entry_volume_ratio=vol_ratio,
            entry_atr=current_atr,
        )
        self.trade_contexts[res.order] = ctx

        # Register thesis (V1 parity: bot_id="SuperTrend" equivalent)
        snapshot = self.kr.get_market_state(self.config.symbol, "M15")
        if snapshot:
            thesis = TradeThesis(
                ticket=res.order,
                symbol=self.config.symbol,
                direction=1 if is_buy else -1,
                bot_system="SuperTrendBotV2",
                setup_type="ST_CLUSTER",
                fill_price=ref_price,
                initial_sl=sl,
                initial_tp=tp,
                entry_atr=current_atr,
                regime_at_entry=snapshot.regime,
                entry_conviction=conviction,
                layer_depth=0,
                timestamp=time.time(),
                market_snapshot=snapshot
            )
            self.kr.register_trade_thesis(thesis)
        return True
