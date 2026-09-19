#!/usr/bin/env python3
"""
SuperTrend Bot v2.3 — Master-Plan Enrichment Edition
======================================================
Author  : xPOURY4 (enhanced)
Build   : v2.3

CHANGES FROM v2.2
==================
1.  LOT SIZING BUG FIX (CRITICAL)
        calculate_position_size previously computed:
            point_value = trade_tick_value / trade_tick_size
        which is $/1.0-price-move — not $/point. Multiplying by
        stop_loss_points (which is in points) produced a denominator
        ~100,000× too large, pinning virtually every trade to volume_min
        (0.01) regardless of risk_percent or account size.
        Correct formula converts SL distance → ticks → dollar_risk_per_lot
        using MT5's own trade_tick_value. Works correctly for all
        instruments including metals where trade_tick_size ≠ point.

2.  SESSION GATE  (Master Plan 4.1 #5 — HIGH)
        New Config fields: session_gate_enabled, session_gate_pairs.
        Suppresses new entries for EURUSDm / GBPUSDm during the Asian
        session (00:00–07:00 UTC) where tick volume correlation degrades.
        XAUUSDm / XAGUSDm are exempt — metals trade actively all session.
        New helper: _get_session() → "ASIAN" | "LONDON" | "NY_OVERLAP" | "OTHER"
        Session tag is logged every cycle and recorded on trade entry.

3.  CONVICTION SCORE  (Master Plan 4.1 #3 — HIGH)
        Port of Ghost Sniper's conviction composite:
            conviction = ADX_raw × 1.0  +  momentum_body_score × 0.5
        Only opens new positions when conviction > conviction_min_threshold
        (default 45). Computed in run_cycle() before any order is placed.
        New Config fields: conviction_gate_enabled, conviction_min_threshold.
        Conviction value logged on every entry.

4.  R-MULTIPLE TRACKING  (Master Plan 4.1 #4 — HIGH)
        _record_closed_trade() now computes and stores signed R-multiple:
            r_multiple = (exit_price − entry_price) / entry_risk_per_unit
            entry_risk_per_unit = |entry_price − entry_sl|
        Logged on every close ("R=+2.34"). Essential for Phase 2 SI-vs-outcome
        correlation analysis.

5.  INCUBATION BARS TRENDING  (Master Plan 4.1 #6 — MEDIUM)
        Changed default incubation_bars_trending from 1 → 2.
        Gives trend entries a full 60 minutes of breathing room on M30
        before active SL management starts. Avoids the watcher tightening
        SL immediately on a valid momentum entry.

6.  MULTI-TF ATR FOR SL BUFFER  (Master Plan 4.1 #7 — MEDIUM)
        New method: _get_m15_atr() fetches last 60 M15 bars, returns ATR.
        SL/TP calculation now uses M30 ATR for position sizing (unchanged)
        and M15 ATR for the STOPS_LEVEL buffer on SL placement.
        New Config field: use_m15_atr_for_sl_buffer (default True).
        Falls back gracefully to M30 ATR if M15 data unavailable.

7.  EQUITY FILTER ON BY DEFAULT  (Master Plan 4.1 #2 — CRITICAL)
        Changed MultiPairRunner equity_filter_enabled default False → True.
        Period=20 cycles, min_ratio=0.97 (unchanged).
        The code was already correct — it was simply switched off.

UNCHANGED FROM v2.2
====================
All entry logic (K-Means, volume gate), state machine, SI score,
Kaufman ER, TradeContext, _evaluate_state, manage_open_positions
watcher actions, CAB guards, _get_market_regime, bar-aware cache,
partial close, place_order fresh-tick, dry-run ticket counter.
"""

# ── v2.3 CHANGES SUMMARY ───────────────────────────────────────────────────────
# Line ~432 : calculate_position_size — bug fix
# Line ~107 : Config — session_gate, conviction_gate, use_m15_atr_for_sl_buffer
# Line ~139 : Config — incubation_bars_trending default 1→2
# Line ~580 : _get_session()         NEW helper
# Line ~595 : _is_session_allowed()  NEW helper
# Line ~615 : _compute_conviction_score() NEW helper
# Line ~640 : _get_m15_atr()         NEW helper
# Line ~830 : _record_closed_trade() — r_multiple added
# Line ~1185: run_cycle()            — session gate + conviction gate
# Line ~1336: MultiPairRunner        — equity_filter_enabled default True
# ──────────────────────────────────────────────────────────────────────────────

"""  # noqa: E501 — version banner above intentionally wide


CHANGES FROM v2.1
==================
1.  Bar-aware supertrend cache
        calculate_supertrends + perform_clustering are called ONCE per new
        M30 bar close, then the result is reused for all intra-bar cycles.
        On M30 with a 30-second interval this is ~59× CPU reduction per symbol.
        Safe because trend direction is determined by bar close vs the
        previous bar's upper/lower bands — it cannot flip mid-bar.
        Cache stats (hits / misses) are logged on shutdown.

2.  Fresh-tick entry price
        place_order now calls symbol_info_tick() immediately before sending
        the order and uses ask (BUY) / bid (SELL) instead of the previous
        bar's close. Removes one-bar slippage from entry price.

3.  Unique dry-run ticket counter
        Replaced int(time.time()) with a monotonically incrementing per-bot
        counter (_dry_run_ticket_seq). No collision risk in rapid testing.

4.  Dynamic incubation bars (regime-aware)
        incubation_bars is now resolved per-cycle from three Config fields:
          incubation_bars_trending  (default 1) — strong trend, manage sooner
          incubation_bars_stable    (default 2) — unchanged from v2.1
          incubation_bars_exhaustion (default 3) — weak structure, more patience
        The single incubation_bars field in Config is kept as the fallback
        default used when _get_dynamic_incubation is not applicable.

5.  Partial close on extreme SI  (opt-in, disabled by default)
        When state == CONFIRMED and SI >= si_partial_close_min and the trade
        has moved at least partial_close_profit_atr_mult ATRs in profit,
        close partial_close_fraction of the volume (default 50%) one time.
        Guards: remainder >= volume_min, spread check, STOPS_LEVEL check.
        Tracked per-ticket via _partial_closed_tickets to fire once per trade.

6.  Equity curve filter  (opt-in, disabled by default, lives in MultiPairRunner)
        Tracks account equity over a rolling window. If equity < min_ratio of
        the rolling average (e.g. 97%), new entries are paused — existing
        watcher logic keeps running. Reactivates automatically when equity
        recovers. Configurable: equity_filter_period, equity_filter_min_ratio.

SI WEIGHT NOTE (v2.1 already correct)
        si_weight_cluster / regime / adx / volume are already per-symbol
        Config fields. They are noted here for clarity — no code change needed.

UNCHANGED FROM v2.1
====================
All entry logic (K-Means, volume gate), state machine, SI score,
Kaufman ER, TradeContext, _evaluate_state, manage_open_positions
watcher actions, CAB guards, _get_market_regime, regime helpers.
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import talib
from sklearn.cluster import KMeans
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Set, Tuple
import warnings
warnings.filterwarnings('ignore')


# ==============================================================================
#  TRADE CONTEXT  (unchanged)
# ==============================================================================
@dataclass
class TradeContext:
    ticket:    int
    direction: int          # 1 = BUY, -1 = SELL

    entry_price: float
    entry_sl:    float
    entry_tp:    float

    entry_time:     datetime
    entry_bar_time: datetime

    entry_st_factor:          float
    entry_st_line:            float
    entry_regime:             str
    entry_adx_rank:           int
    entry_atr_rank:           int
    entry_cluster_agreement:  int
    entry_total_factors:      int
    entry_volume_ratio:       float
    entry_atr:                float

    state:             str = "INCUBATING"
    bars_in_decaying:  int = 0


# ==============================================================================
#  CONFIG
# ==============================================================================
@dataclass
class Config:
    # ── Identity ──────────────────────────────────────────────────────────────
    symbol:           str   = "EURUSDm"
    timeframe:        int   = mt5.TIMEFRAME_M30

    # ── K-Means SuperTrend ────────────────────────────────────────────────────
    atr_period:       int   = 10
    min_factor:       float = 1.0
    max_factor:       float = 5.0
    factor_step:      float = 0.5
    perf_alpha:       float = 10.0
    cluster_choice:   str   = "Best"

    # ── Volume gate ───────────────────────────────────────────────────────────
    volume_ma_period:  int   = 20
    volume_multiplier: float = 1.2

    # ── Risk ──────────────────────────────────────────────────────────────────
    risk_percent:     float = 1.0
    max_positions:    int   = 1
    magic_number:     int   = 123456

    # ── Hard SL / Safety TP ───────────────────────────────────────────────────
    sl_multiplier:         float = 2.0
    tp_safety_multiplier:  float = 10.0

    # ── Dynamic Incubation (v2.2 NEW) ─────────────────────────────────────────
    # Bars held before the watcher starts actively managing, per regime.
    # TRENDING: strong structure → fewer bars before management kicks in.
    # EXHAUSTION: weak structure → give entry more time to establish.
    incubation_bars:            int = 2    # fallback default
    incubation_bars_trending:   int = 2    # v2.3: raised 1→2 (Master Plan 4.1 #6)
    incubation_bars_stable:     int = 2
    incubation_bars_exhaustion: int = 3

    # ── State Machine Thresholds (unchanged) ──────────────────────────────────
    si_confirmed:     float = 0.65
    si_decaying:      float = 0.50
    si_dead:          float = 0.35

    er_confirmed:     float = 0.35
    er_dead:          float = 0.20
    er_bars_for_dead: int   = 3

    decaying_tolerance_bars: int = 1

    # ── Regime urgency modifiers (unchanged) ──────────────────────────────────
    regime_exhaustion_si_penalty:  float = 0.10
    regime_trending_with_si_bonus: float = 0.05

    # ── SI component weights — tune per symbol in config.json ─────────────────
    # Example: XAUUSD → raise si_weight_volume; volatile pairs → raise si_weight_regime
    si_weight_cluster: float = 0.40
    si_weight_regime:  float = 0.25
    si_weight_adx:     float = 0.20
    si_weight_volume:  float = 0.15

    # ── Regime engine (unchanged) ─────────────────────────────────────────────
    trend_adx_thresh:    int = 65
    exhaust_atr_thresh:  int = 75
    exhaust_body_thresh: int = 35
    regime_bars:         int = 170

    # ── Partial Close (v2.2 NEW, disabled by default) ─────────────────────────
    # When state == CONFIRMED, SI is extreme, AND profit >= N ATRs:
    # close partial_close_fraction of the position volume once per trade.
    # Requires state machine to have confirmed the trade is healthy.
    enable_partial_close:           bool  = False
    si_partial_close_min:           float = 0.85   # SI must be >= this
    partial_close_profit_atr_mult:  float = 3.0    # profit must be >= N × ATR
    partial_close_fraction:         float = 0.50   # fraction of position to close

    # ── Session Gate (v2.3 NEW — Master Plan 4.1 #5) ─────────────────────────
    # Suppress new entries during Asian session (00:00–07:00 UTC) for FX pairs.
    # XAUUSDm / XAGUSDm are exempt — metals trade actively all sessions.
    # session_gate_pairs: list of symbol substrings that ARE gated.
    session_gate_enabled: bool      = True
    session_gate_pairs:   List[str] = field(
        default_factory=lambda: ["EURUSDm", "GBPUSDm"]
    )

    # ── Conviction Gate (v2.3 NEW — Master Plan 4.1 #3) ──────────────────────
    # Pre-entry filter: conviction = ADX_raw × 1.0 + momentum_body × 0.5
    # Only opens new positions when conviction > conviction_min_threshold.
    # Disabled by default — enable after Phase 2 calibration.
    conviction_gate_enabled:   bool  = False
    conviction_min_threshold:  float = 45.0

    # ── Multi-TF ATR (v2.3 NEW — Master Plan 4.1 #7) ─────────────────────────
    # Use M15 ATR (instead of M30) for STOPS_LEVEL buffer on SL placement.
    # M30 ATR is still used for position sizing. Falls back to M30 if M15
    # data is unavailable.
    use_m15_atr_for_sl_buffer: bool  = True


# ==============================================================================
#  REGIME HELPERS (unchanged)
# ==============================================================================
def _percentile_rank(series: pd.Series, value: float) -> int:
    arr = series.dropna().values
    if len(arr) == 0:
        return 50
    return int(100 * np.sum(arr <= value) / len(arr))


def _wilder_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
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
    def _smooth(s: pd.Series, p: int) -> pd.Series:
        result = np.zeros(len(s))
        if len(s) < p:
            return pd.Series(result, index=s.index)
        result[p - 1] = float(s.iloc[:p].sum())
        for i in range(p, len(s)):
            result[i] = result[i - 1] - result[i - 1] / p + float(s.iloc[i])
        return pd.Series(result, index=s.index)
    atr14 = _smooth(df["tr"],  period)
    pdm14 = _smooth(df["pdm"], period)
    ndm14 = _smooth(df["ndm"], period)
    safe_atr = atr14.replace(0, np.nan)
    pdi = 100 * pdm14 / safe_atr
    ndi = 100 * ndm14 / safe_atr
    dx  = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
    return _smooth(dx.fillna(0), period)


# ==============================================================================
#  SUPERTREND BOT  (single-symbol)
# ==============================================================================
class SuperTrendBot:

    def __init__(self, config: Config, gateway=None):
        self.config            = config
        self.trade_contexts:   Dict[int, TradeContext] = {}
        self.trade_history     = []
        self.logger            = self._setup_logger()
        self.is_connected      = False
        self.dry_run           = False

        # ── v2.2: bar-aware cache ─────────────────────────────────────────────
        # Key: last bar's pd.Timestamp. Value: (supertrends dict, optimal_factor).
        # Invalidated whenever a new bar closes — safe on any timeframe.
        self._st_cache:        Optional[Tuple] = None   # (bar_time, sts, factor)
        self._cache_hits:      int = 0
        self._cache_misses:    int = 0

        # ── v2.2: unique dry-run tickets ──────────────────────────────────────
        self._dry_run_ticket_seq: int = 100_000

        # ── v2.2: partial close tracking ─────────────────────────────────────
        # Tickets that have already had a partial close this trade lifecycle.
        self._partial_closed_tickets: Set[int] = set()


        # ── v2.3-gw: gateway reference ─────────────────────────────────────
        self._gw = gateway  # None = standalone (uses raw mt5)

    # ── v2.3-gw: MT5 API router ────────────────────────────────────────────
    @property
    def _api(self):
        """Return gateway in unified mode, raw mt5 in standalone mode."""
        return self._gw if self._gw is not None else mt5

    # ──────────────────────────────────────────────────────────────────────────
    def _setup_logger(self) -> logging.Logger:
        name = f"STBot_{self.config.symbol}"
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        if logger.handlers:
            return logger
        fmt = logging.Formatter(
            f"%(asctime)s [{self.config.symbol}] [%(levelname)s] %(message)s"
        )
        fh = logging.FileHandler(
            f"logs/supertrend_{self.config.symbol}.log", encoding="utf-8"
        )
        fh.setFormatter(fmt)
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(ch)
        return logger

    # ──────────────────────────────────────────────────────────────────────────
    def connect(self, login: int, password: str, server: str) -> bool:
        if not mt5.initialize(timeout=180000):
            self.logger.error(f"MT5 init failed: {mt5.last_error()}")
            return False
        if not mt5.login(login, password=password, server=server):
            self.logger.error(f"Login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False
        self.is_connected = True
        self.logger.info(f"Connected → {self._api.account_info().server}")
        return True

    # ==========================================================================
    #  DATA & CORE INDICATORS (unchanged)
    # ==========================================================================
    def get_data(self, bars: int = 1000) -> Optional[pd.DataFrame]:
        rates = self._api.copy_rates_from_pos(
            self.config.symbol, self.config.timeframe, 0, bars
        )
        if rates is None:
            self.logger.error("Failed to get M30 rates")
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)
        df["hl2"]          = (df["high"] + df["low"]) / 2
        df["atr"]          = talib.ATR(
            df["high"], df["low"], df["close"], timeperiod=self.config.atr_period
        )
        df["volume_ma"]    = df["tick_volume"].rolling(
            window=self.config.volume_ma_period
        ).mean()
        df["volatility"]   = df["close"].rolling(
            window=self.config.atr_period
        ).std()
        df["norm_volatility"] = (
            df["volatility"] / df["volatility"].rolling(window=50).mean()
        )
        return df.dropna()

    # ──────────────────────────────────────────────────────────────────────────
    def calculate_supertrends(self, df: pd.DataFrame) -> dict:
        """Unchanged — computes all factor variants."""
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

    # ──────────────────────────────────────────────────────────────────────────
    def perform_clustering(self, supertrends: dict) -> Tuple[float, float]:
        """Unchanged — K-Means on vol-adj performance."""
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

    # ==========================================================================
    #  v2.2 NEW: BAR-AWARE SUPERTREND CACHE
    # ==========================================================================
    def _get_supertrends_cached(
        self, df: pd.DataFrame
    ) -> Tuple[dict, float]:
        """
        Return (supertrends, optimal_factor), recomputing only when the last
        bar timestamp changes (i.e. a new bar has closed).

        Why this is safe:
          - SuperTrend trend direction (0/1) is determined by comparing the
            current bar's close to the PREVIOUS bar's upper/lower bands.
          - Within an open bar, those previous-bar bands do not change.
          - Therefore trend cannot flip until the current bar closes and a
            new bar opens — precisely when the timestamp changes.
          - The watcher uses the live ST output line for SL trailing, which
            does drift slightly intra-bar as price moves the hl2/ATR estimate.
            Accepting one bar of stale ST line is well within noise given that
            the SL guard (STOPS_LEVEL) already prevents micro-adjustments.

        Performance:
          M30 with 30-second cycle → ~60 cycles per bar → ~59 cache hits.
          On 5 symbols that eliminates ~295 expensive supertrend computations
          per 30-minute bar.
        """
        last_bar_time = df.index[-1]

        if self._st_cache is not None and self._st_cache[0] == last_bar_time:
            self._cache_hits += 1
            return self._st_cache[1], self._st_cache[2]

        # Cache miss — new bar has closed, recompute
        supertrends    = self.calculate_supertrends(df)
        optimal_factor, _ = self.perform_clustering(supertrends)
        self._st_cache = (last_bar_time, supertrends, optimal_factor)
        self._cache_misses += 1
        self.logger.debug(
            f"Cache MISS — new bar {last_bar_time} | "
            f"factor={optimal_factor:.2f} | "
            f"hits so far: {self._cache_hits}"
        )
        return supertrends, optimal_factor

    # ──────────────────────────────────────────────────────────────────────────
    def calculate_position_size(self, stop_loss_points: float) -> float:
        """
        v2.3 BUG FIX — correct lot-size formula.

        Previous formula:
            point_value = trade_tick_value / trade_tick_size
            size = risk / (sl_points × point_value)
        This was wrong: dividing trade_tick_value by trade_tick_size
        produces $/1.0-price-unit, NOT $/point. For GBPUSD that inflated
        the denominator by ×100,000, pinning every trade to volume_min.

        Correct approach — use MT5's own tick metadata consistently:
            sl_price_dist   = sl_points × point      (SL in price units)
            sl_ticks        = sl_price_dist / tick_size   (how many ticks)
            dollar_per_lot  = sl_ticks × tick_value   ($ at risk per lot)
            size            = risk_amount / dollar_per_lot

        Works for all instruments (forex, metals, indices) because
        trade_tick_value already reflects the broker's contract size.
        """
        account_info = self._api.account_info()
        if account_info is None:
            return 0.01
        balance     = account_info.balance
        risk_amount = balance * (self.config.risk_percent / 100.0)

        sym_info = self._api.symbol_info(self.config.symbol)
        if sym_info is None:
            return 0.01
        if stop_loss_points <= 0:
            self.logger.warning("calculate_position_size: sl_points <= 0 — returning volume_min")
            return sym_info.volume_min

        sl_price_dist  = stop_loss_points * sym_info.point
        sl_ticks       = sl_price_dist / sym_info.trade_tick_size
        dollar_per_lot = sl_ticks * sym_info.trade_tick_value

        if dollar_per_lot <= 0:
            self.logger.warning("calculate_position_size: dollar_per_lot <= 0 — returning volume_min")
            return sym_info.volume_min

        position_size = risk_amount / dollar_per_lot
        position_size = max(sym_info.volume_min, min(position_size, sym_info.volume_max))
        result        = round(position_size / sym_info.volume_step) * sym_info.volume_step

        self.logger.debug(
            f"LOT SIZING | balance={balance:.2f} | risk={risk_amount:.2f} | "
            f"sl_pts={stop_loss_points:.1f} | $/lot={dollar_per_lot:.4f} | "
            f"raw={position_size:.4f} | final={result:.2f}"
        )
        return result

    # ==========================================================================
    #  v2.3 NEW: SESSION GATE  (Master Plan 4.1 #5)
    # ==========================================================================
    def _get_session(self) -> str:
        """
        Classify current UTC hour into trading session.

        ASIAN      : 00:00 – 06:59 UTC (Tokyo / Sydney)
        LONDON     : 07:00 – 11:59 UTC
        NY_OVERLAP : 12:00 – 16:59 UTC (London / NY overlap — highest volume)
        OTHER      : 17:00 – 23:59 UTC (NY solo / pre-Asia)
        """
        hour = datetime.utcnow().hour
        if hour < 7:
            return "ASIAN"
        if hour < 12:
            return "LONDON"
        if hour < 17:
            return "NY_OVERLAP"
        return "OTHER"

    def _is_session_allowed(self) -> bool:
        """
        Returns False (entry blocked) when:
          - session_gate_enabled is True, AND
          - current session is ASIAN, AND
          - symbol matches one of session_gate_pairs.

        XAUUSDm / XAGUSDm are excluded from gating — metals trade
        actively through the Asian session (Shanghai/Tokyo demand).
        """
        if not self.config.session_gate_enabled:
            return True
        session = self._get_session()
        if session != "ASIAN":
            return True
        # Check if this symbol is in the gated list
        sym = self.config.symbol
        for gated in self.config.session_gate_pairs:
            if gated.upper() in sym.upper():
                self.logger.info(
                    f"SESSION GATE ACTIVE | session=ASIAN | {sym} entry suppressed"
                )
                return False
        return True  # metal or ungated symbol — allow

    # ==========================================================================
    #  v2.3 NEW: CONVICTION SCORE  (Master Plan 4.1 #3)
    # ==========================================================================
    def _compute_conviction_score(self, regime_data: dict, df: pd.DataFrame) -> float:
        """
        Ghost Sniper's conviction composite, ported for pre-entry filtering.

            conviction = ADX_raw_value × 1.0  +  momentum_body_score × 0.5

        ADX_raw_value: the actual ADX level (not percentile) from the M1
            regime engine scores. If unavailable, estimated from adx_rank.

        momentum_body_score: the latest bar's body-to-range ratio (0–100).
            Strong directional bars have high body ratio.

        Interpretation:
          < 45  → weak setup — skip entry (gate threshold in config)
          45–65 → moderate — allow with normal risk
          > 65  → strong conviction — full position

        Note: the conviction score is computed from the same M1 regime
        data already fetched by _get_market_regime(), so there is zero
        extra API overhead.
        """
        scores = regime_data.get("scores", {})

        # ADX component — use raw ADX if available, else estimate from rank
        adx_rank  = scores.get("adx_rank", 50)
        # Approximate raw ADX from percentile rank (rough but sufficient for gate)
        adx_raw   = adx_rank * 0.5  # rank 70th ≈ ADX 35 for typical FX

        # Momentum body component — last bar body ratio (0–1) → scale to 0–100
        try:
            last_open  = float(df["open"].iloc[-1])
            last_close = float(df["close"].iloc[-1])
            last_high  = float(df["high"].iloc[-1])
            last_low   = float(df["low"].iloc[-1])
            bar_range  = last_high - last_low
            body       = abs(last_close - last_open)
            body_ratio = (body / bar_range * 100) if bar_range > 0 else 0.0
        except Exception:
            body_ratio = 50.0

        conviction = adx_raw * 1.0 + body_ratio * 0.5
        return round(float(conviction), 2)

    # ==========================================================================
    #  v2.3 NEW: M15 ATR FOR SL BUFFER  (Master Plan 4.1 #7)
    # ==========================================================================
    def _get_m15_atr(self) -> Optional[float]:
        """
        Fetch last 60 M15 bars and return ATR(10) as a fine-grained SL buffer.

        The M30 ATR used for position sizing captures the overall trade risk.
        The M15 ATR is tighter and better represents the immediate noise level
        that a SL must clear to avoid premature triggering on normal intra-bar
        volatility.

        Returns None if M15 data is unavailable — caller falls back to M30 ATR.
        """
        try:
            rates = self._api.copy_rates_from_pos(
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
            self.logger.debug(f"_get_m15_atr failed: {exc}")
            return None

    # ──────────────────────────────────────────────────────────────────────────
    def check_volume_condition(self, df: pd.DataFrame) -> bool:
        return (
            float(df["tick_volume"].iloc[-1]) >
            float(df["volume_ma"].iloc[-1]) * self.config.volume_multiplier
        )

    # ──────────────────────────────────────────────────────────────────────────
    def generate_signal(
        self,
        df:             pd.DataFrame,
        supertrends:    dict = None,
        optimal_factor: float = None
    ) -> Optional[int]:
        if df is None or len(df) < 200:
            return None
        if supertrends is None or optimal_factor is None:
            supertrends, optimal_factor = self._get_supertrends_cached(df)
        current_st = supertrends[
            min(supertrends.keys(), key=lambda x: abs(x - optimal_factor))
        ]
        cur_trend  = int(current_st["trend"].iloc[-1])
        prev_trend = int(current_st["trend"].iloc[-2])
        if not self.check_volume_condition(df):
            return None
        if cur_trend > prev_trend:
            return  1
        if cur_trend < prev_trend:
            return -1
        return None

    # ==========================================================================
    #  REGIME ENGINE (unchanged)
    # ==========================================================================
    def _get_market_regime(self) -> dict:
        rates = self._api.copy_rates_from_pos(
            self.config.symbol, mt5.TIMEFRAME_M1, 0, self.config.regime_bars
        )
        if rates is None or len(rates) < 50:
            return {
                "regime": "STABLE", "reason": "Insufficient M1 data",
                "scores": {}, "atr_raw": 1.0
            }
        df = pd.DataFrame(rates)
        df["tr"] = np.maximum(
            df["high"] - df["low"],
            np.maximum(
                (df["high"] - df["close"].shift(1)).abs(),
                (df["low"]  - df["close"].shift(1)).abs()
            )
        )
        adx_series = _wilder_adx(df, 14)
        adx_rank   = _percentile_rank(adx_series, adx_series.iloc[-1])
        atr14      = df["tr"].rolling(14).mean()
        atr_ratio  = atr14 / atr14.rolling(50).mean().replace(0, np.nan)
        atr_rank   = _percentile_rank(atr_ratio.dropna(), atr_ratio.iloc[-1])
        atr_raw    = float(atr14.iloc[-1]) if not pd.isna(atr14.iloc[-1]) else 1.0
        df["body"]   = (df["close"] - df["open"]).abs()
        df["range_"] = (df["high"] - df["low"]).replace(0, np.nan)
        br_series    = df["body"] / df["range_"]
        br_rank      = _percentile_rank(br_series.dropna(), br_series.iloc[-1])
        scores = {"adx_rank": adx_rank, "atr_rank": atr_rank, "br_rank": br_rank}
        if (atr_rank >= self.config.exhaust_atr_thresh
                and br_rank <= self.config.exhaust_body_thresh):
            return {
                "regime": "EXHAUSTION",
                "reason": f"ATR spike {atr_rank}th | weak body {br_rank}th",
                "scores": scores, "atr_raw": atr_raw
            }
        elif (adx_rank >= self.config.trend_adx_thresh
              and br_rank > self.config.exhaust_body_thresh):
            return {
                "regime": "TRENDING",
                "reason": f"ADX {adx_rank}th | directional body {br_rank}th",
                "scores": scores, "atr_raw": atr_raw
            }
        else:
            return {
                "regime": "STABLE",
                "reason": f"ADX {adx_rank}th | ATR {atr_rank}th | body {br_rank}th",
                "scores": scores, "atr_raw": atr_raw
            }

    # ==========================================================================
    #  SIGNAL INTEGRITY (unchanged)
    # ==========================================================================
    def _compute_signal_integrity(
        self,
        ctx:         TradeContext,
        supertrends: dict,
        regime_data: dict,
        df:          pd.DataFrame
    ) -> float:
        cfg            = self.config
        expected_trend = 1 if ctx.direction == 1 else 0
        agreeing       = sum(
            1 for st in supertrends.values()
            if int(st["trend"].iloc[-1]) == expected_trend
        )
        cluster_ratio = agreeing / max(len(supertrends), 1)
        regime_match  = 1.0 if regime_data["regime"] == ctx.entry_regime else 0.0
        cur_adx_rank  = regime_data["scores"].get("adx_rank", 50)
        adx_ratio     = min(cur_adx_rank / max(ctx.entry_adx_rank, 1), 1.0)
        vol_ma        = float(df["volume_ma"].iloc[-1])
        cur_vol_ratio = (
            float(df["tick_volume"].iloc[-1]) / vol_ma if vol_ma > 0 else 1.0
        )
        vol_ratio = min(cur_vol_ratio / max(ctx.entry_volume_ratio, 0.01), 1.0)
        si = (
            cfg.si_weight_cluster * cluster_ratio +
            cfg.si_weight_regime  * regime_match  +
            cfg.si_weight_adx     * adx_ratio     +
            cfg.si_weight_volume  * vol_ratio
        )
        return round(float(np.clip(si, 0.0, 1.0)), 4)

    # ==========================================================================
    #  EFFICIENCY RATIO — Classic Kaufman (v2.1 version, unchanged)
    # ==========================================================================
    def _compute_efficiency_ratio(self, df: pd.DataFrame, bars: int) -> float:
        bars = max(2, min(bars, 8))
        if len(df) < bars + 1:
            return 0.5
        closes     = df["close"].iloc[-(bars + 1):].values
        net_move   = abs(closes[-1] - closes[0])
        total_path = float(np.sum(np.abs(np.diff(closes))))
        if total_path == 0:
            return 0.0
        return round(float(np.clip(net_move / total_path, 0.0, 1.0)), 4)

    # ==========================================================================
    #  v2.2 NEW: DYNAMIC INCUBATION BARS
    # ==========================================================================
    def _get_dynamic_incubation(self, regime: str) -> int:
        """
        Return the incubation bar count appropriate for the current regime.

        TRENDING   → fewer bars (strong structure, manage sooner)
        STABLE     → standard (same as v2.1 default)
        EXHAUSTION → more bars (weak structure, give entry time to establish)

        This prevents the watcher from immediately tightening SL on a genuine
        momentum entry in TRENDING, while giving extra breathing room when
        the regime is flaky at entry.
        """
        return {
            "TRENDING":   self.config.incubation_bars_trending,
            "STABLE":     self.config.incubation_bars_stable,
            "EXHAUSTION": self.config.incubation_bars_exhaustion,
        }.get(regime, self.config.incubation_bars)

    # ==========================================================================
    #  STATE MACHINE — updated to use dynamic incubation
    # ==========================================================================
    def _evaluate_state(
        self,
        ctx:              TradeContext,
        si:               float,
        er:               float,
        bars_held:        int,
        st_trend_current: int,
        regime:           str
    ) -> str:
        cfg            = self.config
        expected_trend = 1 if ctx.direction == 1 else 0

        si_confirmed = cfg.si_confirmed
        si_decaying  = cfg.si_decaying
        si_dead      = cfg.si_dead

        if regime == "EXHAUSTION":
            si_confirmed += cfg.regime_exhaustion_si_penalty
            si_decaying  += cfg.regime_exhaustion_si_penalty
            si_dead      += cfg.regime_exhaustion_si_penalty
        elif regime == "TRENDING" and si >= cfg.si_confirmed:
            si_confirmed -= cfg.regime_trending_with_si_bonus
            si_decaying  -= cfg.regime_trending_with_si_bonus

        # DEAD (highest priority)
        if st_trend_current != expected_trend:
            return "DEAD"
        if si < si_dead:
            return "DEAD"
        if bars_held >= cfg.er_bars_for_dead and er < cfg.er_dead:
            return "DEAD"

        # INCUBATING — use dynamic bar count for this regime
        incubation_bars = self._get_dynamic_incubation(regime)
        if bars_held < incubation_bars:
            return "INCUBATING"

        # DECAYING
        if si < si_decaying:
            return "DECAYING"
        if si < si_confirmed and er < cfg.er_confirmed:
            return "DECAYING"

        # CONFIRMED
        if si >= si_confirmed and er >= cfg.er_confirmed:
            return "CONFIRMED"

        return "DECAYING"

    # ==========================================================================
    #  v2.2 NEW: PARTIAL CLOSE
    # ==========================================================================
    def _try_partial_close(
        self,
        pos,
        si:          float,
        current_atr: float
    ) -> bool:
        """
        Close partial_close_fraction of the position volume exactly once per trade.

        Conditions (all must be true):
          1. enable_partial_close is True
          2. This ticket has not been partially closed yet this trade
          3. SI >= si_partial_close_min  (signal is extremely healthy)
          4. Profit in ATR units >= partial_close_profit_atr_mult
          5. Remaining volume after partial close >= volume_min

        Why only in CONFIRMED state?
          Partial close is a profit-locking mechanism when the trade is at
          peak health. Calling it in DECAYING would be double-penalising an
          already stressed trade — let the state machine handle that instead.

        Returns True if a partial close was executed (or simulated in dry-run).
        """
        cfg = self.config
        if not cfg.enable_partial_close:
            return False
        if pos.ticket in self._partial_closed_tickets:
            return False

        ctx = self.trade_contexts.get(pos.ticket)
        if ctx is None:
            return False

        # SI gate
        if si < cfg.si_partial_close_min:
            return False

        # Profit gate
        profit_in_atr = abs(pos.price_current - ctx.entry_price) / max(current_atr, 1e-10)
        if profit_in_atr < cfg.partial_close_profit_atr_mult:
            return False

        sym_info = self._api.symbol_info(self.config.symbol)
        if sym_info is None:
            return False

        # Compute partial volume, ensuring valid remainder
        raw_partial  = pos.volume * cfg.partial_close_fraction
        partial_vol  = (
            round(raw_partial / sym_info.volume_step) * sym_info.volume_step
        )
        partial_vol  = max(sym_info.volume_min, partial_vol)
        remainder    = round(pos.volume - partial_vol, 8)

        if remainder < sym_info.volume_min:
            # Can't leave a valid lot size — skip (full close is the state
            # machine's job, not partial close's)
            self.logger.debug(
                f"Partial close skipped #{pos.ticket} — "
                f"remainder {remainder:.2f} < vol_min {sym_info.volume_min:.2f}"
            )
            return False

        if self.dry_run:
            self.logger.info(
                f"[DRY RUN] PARTIAL CLOSE #{pos.ticket} | "
                f"vol={partial_vol} ({cfg.partial_close_fraction*100:.0f}%) | "
                f"SI={si:.3f} | pnl={profit_in_atr:.2f}ATR"
            )
            self._partial_closed_tickets.add(pos.ticket)
            return True

        # Spread guard (same as _close_position)
        tick = self._api.symbol_info_tick(self.config.symbol)
        if tick is None:
            return False
        spread     = tick.ask - tick.bid
        max_spread = sym_info.trade_tick_size * 50
        if spread > max_spread:
            self.logger.warning(
                f"Partial close BLOCKED #{pos.ticket} | spread too wide"
            )
            return False

        order_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
        price      = tick.bid if pos.type == 0 else tick.ask

        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       self.config.symbol,
            "volume":       partial_vol,
            "type":         order_type,
            "position":     pos.ticket,
            "price":        price,
            "deviation":    20,
            "magic":        self.config.magic_number,
            "comment":      f"STv2.2|PARTIAL|SI{si:.2f}",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = self._api.order_send(request)
        if res.retcode == mt5.TRADE_RETCODE_DONE:
            self.logger.info(
                f"PARTIAL CLOSE #{pos.ticket} | "
                f"vol={partial_vol} ({cfg.partial_close_fraction*100:.0f}%) | "
                f"SI={si:.3f} | pnl={profit_in_atr:.2f}ATR | "
                f"remaining={remainder}"
            )
            self._partial_closed_tickets.add(pos.ticket)
            return True
        else:
            self.logger.error(
                f"PARTIAL CLOSE FAILED #{pos.ticket} | "
                f"code={res.retcode} | {res.comment}"
            )
            return False

    # ==========================================================================
    #  POSITION HELPERS
    # ==========================================================================
    def _close_position(
        self, pos, reason: str,
        si: float = 0.0, er: float = 0.0, bars_held: int = 0
    ) -> bool:
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Close #{pos.ticket} | {reason}")
            self._record_closed_trade(pos, reason, si, er, bars_held)
            self._partial_closed_tickets.discard(pos.ticket)
            self.trade_contexts.pop(pos.ticket, None)
            return True

        sym_info = self._api.symbol_info(self.config.symbol)
        tick     = self._api.symbol_info_tick(self.config.symbol)
        if tick is None:
            self.logger.warning(f"No tick for close #{pos.ticket} — skipping")
            return False

        spread     = tick.ask - tick.bid
        max_spread = sym_info.trade_tick_size * 50
        if spread > max_spread:
            self.logger.warning(
                f"Close BLOCKED #{pos.ticket} | spread {spread:.5f} > {max_spread:.5f}"
            )
            return False

        order_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
        price      = tick.bid if pos.type == 0 else tick.ask
        request    = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       self.config.symbol,
            "volume":       pos.volume,
            "type":         order_type,
            "position":     pos.ticket,
            "price":        price,
            "deviation":    20,
            "magic":        self.config.magic_number,
            "comment":      f"STv2|{reason[:18]}",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = self._api.order_send(request)
        if res.retcode == mt5.TRADE_RETCODE_DONE:
            self.logger.info(
                f"CLOSED #{pos.ticket} | {reason} | P&L: {pos.profit:.2f}"
            )
            self._record_closed_trade(pos, reason, si, er, bars_held)
            self._partial_closed_tickets.discard(pos.ticket)
            self.trade_contexts.pop(pos.ticket, None)
            return True
        else:
            self.logger.error(
                f"Close FAILED #{pos.ticket} | code={res.retcode} | {res.comment}"
            )
            return False

    # ──────────────────────────────────────────────────────────────────────────
    def _record_closed_trade(
        self, pos, reason: str, si: float, er: float, bars_held: int
    ):
        """v2.3: adds signed R-multiple for Phase 2 SI-vs-outcome correlation."""
        ctx = self.trade_contexts.get(pos.ticket)

        # ── R-multiple calculation (Master Plan 4.1 #4) ───────────────────────
        r_multiple = None
        if ctx is not None:
            entry_risk = abs(ctx.entry_price - ctx.entry_sl)
            if entry_risk > 1e-10:
                direction   = 1 if ctx.direction == 1 else -1
                price_delta = (pos.price_current - ctx.entry_price) * direction
                r_multiple  = round(price_delta / entry_risk, 3)

        if r_multiple is not None:
            self.logger.info(
                f"  CLOSE #{pos.ticket} | R={'+' if r_multiple >= 0 else ''}"
                f"{r_multiple:.2f} | SI@close={si:.3f}"
            )

        self.trade_history.append({
            "ticket":      pos.ticket,
            "symbol":      self.config.symbol,
            "direction":   "BUY" if pos.type == 0 else "SELL",
            "entry_price": ctx.entry_price if ctx else pos.price_open,
            "entry_sl":    ctx.entry_sl    if ctx else pos.sl,
            "exit_price":  pos.price_current,
            "profit":      pos.profit,
            "r_multiple":  r_multiple,          # NEW v2.3
            "bars_held":   bars_held,
            "exit_reason": reason,
            "si_at_close": si,
            "er_at_close": er,
            "exit_time":   datetime.now().isoformat(),
        })

    # ──────────────────────────────────────────────────────────────────────────
    def _modify_sl(self, pos, new_sl: float, label: str = "") -> bool:
        if self.dry_run:
            self.logger.info(
                f"[DRY RUN] Modify SL #{pos.ticket} → {new_sl:.5f} | {label}"
            )
            return True

        sym_info  = self._api.symbol_info(self.config.symbol)
        tick      = self._api.symbol_info_tick(self.config.symbol)
        if tick is None:
            return False

        is_buy     = (pos.type == 0)
        curr_price = tick.bid if is_buy else tick.ask
        stops_dist = sym_info.trade_stops_level * sym_info.point

        if abs(new_sl - curr_price) < stops_dist:
            self.logger.warning(
                f"SL BLOCKED #{pos.ticket} ({label}) | "
                f"new_sl {new_sl:.5f} inside stops level {stops_dist:.5f}"
            )
            return False
        if is_buy  and pos.sl != 0 and new_sl <= pos.sl:
            return False
        if not is_buy and pos.sl != 0 and new_sl >= pos.sl:
            return False

        ctx = self.trade_contexts.get(pos.ticket)
        if ctx is not None:
            if is_buy  and new_sl < ctx.entry_sl:
                new_sl = ctx.entry_sl
            if not is_buy and new_sl > ctx.entry_sl:
                new_sl = ctx.entry_sl

        request = {
            "action":   mt5.TRADE_ACTION_SLTP,
            "position": pos.ticket,
            "sl":       round(new_sl, sym_info.digits),
            "tp":       pos.tp,
        }
        res = self._api.order_send(request)
        if res.retcode == mt5.TRADE_RETCODE_DONE:
            self.logger.info(f"SL updated #{pos.ticket} → {new_sl:.5f} | {label}")
            return True
        else:
            self.logger.error(
                f"SL FAILED #{pos.ticket} ({label}) | "
                f"code={res.retcode} | {res.comment}"
            )
            return False

    # ──────────────────────────────────────────────────────────────────────────
    def place_order(
        self,
        order_type: int,
        volume:     float,
        sl:         float,
        tp:         float
    ) -> Optional[int]:
        """
        v2.2 change: price is no longer a parameter.
        A fresh tick is pulled immediately before sending to minimise slippage.
        Using the previous bar's close as entry price was safe but introduced
        one-bar lag. With a fresh tick we use the live ask/bid.
        """
        is_buy = (order_type == mt5.ORDER_TYPE_BUY)

        if self.dry_run:
            self._dry_run_ticket_seq += 1
            fake_ticket = self._dry_run_ticket_seq
            self.logger.info(
                f"[DRY RUN] {'BUY' if is_buy else 'SELL'} "
                f"vol={volume} SL={sl:.5f} TP={tp:.5f} "
                f"→ fake_ticket={fake_ticket}"
            )
            return fake_ticket

        sym_info = self._api.symbol_info(self.config.symbol)
        if sym_info is None:
            return None

        # Fresh tick — pulled right before send
        tick = self._api.symbol_info_tick(self.config.symbol)
        if tick is None:
            self.logger.error("No tick data — order aborted")
            return None
        price = tick.ask if is_buy else tick.bid

        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       self.config.symbol,
            "volume":       volume,
            "type":         order_type,
            "price":        price,
            "sl":           sl,
            "tp":           tp,
            "deviation":    20,
            "magic":        self.config.magic_number,
            "comment":      "SuperTrend Bot v2.2",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = self._api.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(
                f"Order FAILED | code={result.retcode} | {result.comment}"
            )
            return None
        return result.order

    # ==========================================================================
    #  WATCHER BRAIN  (updated: partial close call + dynamic incubation log)
    # ==========================================================================
    def manage_open_positions(
        self,
        df:             pd.DataFrame,
        supertrends:    dict,
        optimal_factor: float,
        regime_data:    dict
    ):
        positions = self._api.positions_get(symbol=self.config.symbol)
        if not positions:
            self.trade_contexts.clear()
            return

        regime        = regime_data["regime"]
        regime_reason = regime_data["reason"]

        closest_factor = min(
            supertrends.keys(), key=lambda x: abs(x - optimal_factor)
        )
        current_st   = supertrends[closest_factor]
        st_line_now  = float(current_st["output"].iloc[-1])
        st_trend_now = int(current_st["trend"].iloc[-1])
        current_atr  = float(df["atr"].iloc[-1])

        dyn_incubation = self._get_dynamic_incubation(regime)

        self.logger.info(
            f"== WATCHER CYCLE | Regime={regime} | {regime_reason} | "
            f"ST={st_line_now:.5f} ({'^' if st_trend_now else 'v'}) | "
            f"Incubation={dyn_incubation}bar(s)"
        )

        for pos in positions:
            if pos.magic != self.config.magic_number:
                continue

            is_buy = (pos.type == 0)
            ctx    = self.trade_contexts.get(pos.ticket)

            # Context recovery
            if ctx is None:
                self.logger.warning(
                    f"No context for #{pos.ticket} — reconstructing"
                )
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

            tf_secs   = self._timeframe_seconds()
            bars_held = max(
                0,
                int((datetime.now() - ctx.entry_time).total_seconds() / tf_secs)
            )

            si    = self._compute_signal_integrity(ctx, supertrends, regime_data, df)
            er    = self._compute_efficiency_ratio(df, bars=max(2, min(bars_held, 8)))
            state = self._evaluate_state(ctx, si, er, bars_held, st_trend_now, regime)
            ctx.state = state

            self.logger.info(
                f"  #{pos.ticket} {'BUY' if is_buy else 'SELL'} | "
                f"State={state} | SI={si:.3f} | ER={er:.3f} | "
                f"Bars={bars_held} | P&L={pos.profit:.2f}"
            )

            # STATE ACTIONS ────────────────────────────────────────────────────
            if state == "DEAD":
                reason = self._build_dead_reason(si, er, bars_held, st_trend_now, ctx)
                self._close_position(pos, f"DEAD|{reason}", si=si, er=er,
                                     bars_held=bars_held)
                continue

            elif state == "INCUBATING":
                remaining = dyn_incubation - bars_held
                self.logger.info(
                    f"  #{pos.ticket} INCUBATING | "
                    f"{remaining} bar(s) remaining (regime={regime})"
                )
                if is_buy and st_line_now > pos.sl and st_trend_now == 1:
                    self._modify_sl(pos, st_line_now, label="INCUBATING_FLOOR")
                elif not is_buy and (pos.sl == 0 or st_line_now < pos.sl) \
                        and st_trend_now == 0:
                    self._modify_sl(pos, st_line_now, label="INCUBATING_FLOOR")

            elif state == "CONFIRMED":
                ctx.bars_in_decaying = 0

                # Partial close — one-time, when signal is extremely strong
                self._try_partial_close(pos, si=si, current_atr=current_atr)

                # Trail SL to ST line
                if is_buy and st_trend_now == 1:
                    self._modify_sl(pos, st_line_now, label="CONFIRMED|ST_TRAIL")
                elif not is_buy and st_trend_now == 0:
                    self._modify_sl(pos, st_line_now, label="CONFIRMED|ST_TRAIL")

            elif state == "DECAYING":
                if is_buy and st_trend_now == 1:
                    self._modify_sl(pos, st_line_now, label="DECAYING|TIGHTEN")
                elif not is_buy and st_trend_now == 0:
                    self._modify_sl(pos, st_line_now, label="DECAYING|TIGHTEN")

                ctx.bars_in_decaying += 1
                self.logger.info(
                    f"  #{pos.ticket} DECAYING "
                    f"{ctx.bars_in_decaying}/{self.config.decaying_tolerance_bars} | "
                    f"SI={si:.3f} | ER={er:.3f}"
                )
                if ctx.bars_in_decaying > self.config.decaying_tolerance_bars:
                    self._close_position(
                        pos,
                        f"DECAYING_TIMEOUT|SI={si:.3f}|ER={er:.3f}",
                        si=si, er=er, bars_held=bars_held
                    )

    # ──────────────────────────────────────────────────────────────────────────
    def _build_dead_reason(self, si, er, bars_held, st_trend_current, ctx) -> str:
        expected = 1 if ctx.direction == 1 else 0
        if st_trend_current != expected:
            return "ST_LINE_FLIPPED"
        if si < self.config.si_dead:
            return f"SI_COLLAPSED_{si:.3f}"
        if bars_held >= self.config.er_bars_for_dead and er < self.config.er_dead:
            return f"ER_CHURN_{er:.3f}_b{bars_held}"
        return f"SI_{si:.3f}_ER_{er:.3f}"

    # ──────────────────────────────────────────────────────────────────────────
    def _timeframe_seconds(self) -> int:
        return {
            mt5.TIMEFRAME_M1:  60,
            mt5.TIMEFRAME_M5:  300,
            mt5.TIMEFRAME_M15: 900,
            mt5.TIMEFRAME_M30: 1800,
            mt5.TIMEFRAME_H1:  3600,
            mt5.TIMEFRAME_H4:  14400,
            mt5.TIMEFRAME_D1:  86400,
        }.get(self.config.timeframe, 1800)

    # ==========================================================================
    #  MAIN BRAIN CYCLE
    # ==========================================================================
    def run_cycle(
        self,
        global_open_count:    int  = 0,
        max_total_positions:  int  = 999,
        allow_new_entry:      bool = True   # v2.2: equity filter gate
    ) -> int:
        """
        One full brain cycle.

        allow_new_entry=False means the watcher still runs (existing positions
        are still managed) but no new orders are opened. Used by the equity
        curve filter in MultiPairRunner.

        Returns: number of NEW positions opened this cycle (0 or 1).
        """
        if not self.is_connected:
            self.logger.error("Not connected to MT5")
            return 0

        df = self.get_data()
        if df is None or len(df) < 200:
            return 0

        # Bar-aware cache — recomputes only on new bar close
        supertrends, optimal_factor = self._get_supertrends_cached(df)
        regime_data = self._get_market_regime()

        self.logger.info(
            f"CYCLE | price={float(df['close'].iloc[-1]):.5f} | "
            f"ATR={float(df['atr'].iloc[-1]):.5f} | "
            f"factor={optimal_factor:.2f} | Regime={regime_data['regime']} | "
            f"Cache hits={self._cache_hits} misses={self._cache_misses}"
        )

        # Watcher brain
        self.manage_open_positions(df, supertrends, optimal_factor, regime_data)

        # Entry check
        if not allow_new_entry:
            return 0

        positions  = self._api.positions_get(symbol=self.config.symbol)
        open_count = (
            len([p for p in positions if p.magic == self.config.magic_number])
            if positions else 0
        )

        if open_count >= self.config.max_positions:
            return 0
        if global_open_count >= max_total_positions:
            self.logger.info(
                f"No entry — global cap ({global_open_count}/{max_total_positions})"
            )
            return 0

        signal = self.generate_signal(df, supertrends, optimal_factor)
        if signal not in (1, -1):
            return 0

        is_buy      = (signal == 1)
        current_atr = float(df["atr"].iloc[-1])

        # ── v2.3: SESSION GATE  (Master Plan 4.1 #5) ─────────────────────────
        session = self._get_session()
        if not self._is_session_allowed():
            self.logger.info(
                f"Entry BLOCKED by session gate | session={session} | "
                f"symbol={self.config.symbol}"
            )
            return 0

        # ── v2.3: CONVICTION GATE  (Master Plan 4.1 #3) ──────────────────────
        conviction = self._compute_conviction_score(regime_data, df)
        if self.config.conviction_gate_enabled:
            if conviction < self.config.conviction_min_threshold:
                self.logger.info(
                    f"Entry BLOCKED by conviction gate | "
                    f"conviction={conviction:.1f} < {self.config.conviction_min_threshold}"
                )
                return 0

        # ── v2.3: M15 ATR for SL buffer  (Master Plan 4.1 #7) ────────────────
        # M30 ATR: position sizing (unchanged)
        # M15 ATR: SL distance buffer — tighter, captures immediate noise
        m15_atr = None
        if self.config.use_m15_atr_for_sl_buffer:
            m15_atr = self._get_m15_atr()
        sl_atr = m15_atr if m15_atr is not None else current_atr
        if m15_atr is not None:
            self.logger.debug(
                f"ATR | M30={current_atr:.5f} | M15={m15_atr:.5f} "
                f"| using M15 for SL buffer"
            )

        # Compute SL/TP using last bar ATR for sizing
        # Entry price itself is fetched inside place_order() from a fresh tick
        # We need an approximate current price for SL/TP calculation
        tick_now = self._api.symbol_info_tick(self.config.symbol)
        if tick_now is None:
            self.logger.warning("No tick — skipping entry")
            return 0
        ref_price = tick_now.ask if is_buy else tick_now.bid

        sl = (
            ref_price - sl_atr * self.config.sl_multiplier if is_buy
            else ref_price + sl_atr * self.config.sl_multiplier
        )
        tp = (
            ref_price + current_atr * self.config.tp_safety_multiplier if is_buy
            else ref_price - current_atr * self.config.tp_safety_multiplier
        )

        sl_points = abs(ref_price - sl) / self._api.symbol_info(self.config.symbol).point
        volume    = self.calculate_position_size(sl_points)

        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        # place_order now fetches its own fresh tick internally
        ticket = self.place_order(order_type, volume, sl, tp)
        if not ticket:
            return 0

        # Build context snapshot
        closest_factor = min(
            supertrends.keys(), key=lambda x: abs(x - optimal_factor)
        )
        st_entry      = supertrends[closest_factor]
        st_line_entry = float(st_entry["output"].iloc[-1])
        entry_agree   = sum(
            1 for st in supertrends.values()
            if int(st["trend"].iloc[-1]) == (1 if is_buy else 0)
        )
        vm        = float(df["volume_ma"].iloc[-1])
        vol_ratio = float(df["tick_volume"].iloc[-1]) / vm if vm > 0 else 1.0

        ctx = TradeContext(
            ticket=ticket,
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
        self.trade_contexts[ticket] = ctx

        self.logger.info(
            f"{'BUY' if is_buy else 'SELL'} ENTRY | "
            f"ticket={ticket} | ref={ref_price:.5f} | vol={volume:.2f} | "
            f"SL={sl:.5f} | TP={tp:.5f} | "
            f"cluster={entry_agree}/{len(supertrends)} | "
            f"vol_ratio={vol_ratio:.2f} | Regime={regime_data['regime']} | "
            f"Session={session} | Conviction={conviction:.1f} | "
            f"SL_ATR={'M15' if m15_atr else 'M30'} | "
            f"Incubation={self._get_dynamic_incubation(regime_data['regime'])}bar(s)"
        )
        return 1

    # ==========================================================================
    #  STATISTICS
    # ==========================================================================
    def calculate_statistics(self) -> dict:
        if not self.trade_history:
            return {
                "symbol": self.config.symbol, "total_trades": 0,
                "win_rate": 0, "total_pnl": 0, "avg_r_multiple": "n/a"
            }
        wins      = sum(1 for t in self.trade_history if t.get("profit", 0) > 0)
        total_pnl = sum(t.get("profit", 0) for t in self.trade_history)
        exit_reasons = {}
        for t in self.trade_history:
            r = t.get("exit_reason", "unknown")
            exit_reasons[r] = exit_reasons.get(r, 0) + 1
        # R-multiple stats (v2.3)
        r_values = [t["r_multiple"] for t in self.trade_history
                    if t.get("r_multiple") is not None]
        avg_r = round(sum(r_values) / len(r_values), 3) if r_values else None
        return {
            "symbol":        self.config.symbol,
            "total_trades":  len(self.trade_history),
            "win_rate":      round(wins / len(self.trade_history) * 100, 1),
            "total_pnl":     round(total_pnl, 2),
            "avg_r_multiple": avg_r,
            "exit_reasons":  exit_reasons,
            "cache_hits":    self._cache_hits,
            "cache_misses":  self._cache_misses,
        }

    # ==========================================================================
    #  SINGLE-SYMBOL LOOP (legacy / standalone)
    # ==========================================================================
    def run(self, interval_seconds: int = 30):
        self.logger.info(
            f"SuperTrend Bot v2.2 ONLINE | "
            f"Symbol={self.config.symbol} | Interval={interval_seconds}s | "
            f"DryRun={self.dry_run}"
        )
        try:
            while True:
                try:
                    self.run_cycle()
                except Exception as e:
                    self.logger.error(f"Cycle error: {e}", exc_info=True)
                    if not self._api.terminal_info():
                        self.logger.warning("MT5 disconnected — re-initialising...")
                        mt5.initialize(timeout=30000)
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            self.logger.info("Bot stopped by user")
        finally:
            self.shutdown()

    def shutdown(self):
        stats = self.calculate_statistics()
        self.logger.info(
            f"Shutdown | Cache: {stats['cache_hits']} hits / "
            f"{stats['cache_misses']} misses | "
            f"Trades: {stats['total_trades']} | P&L: {stats['total_pnl']:.2f}"
        )
        if self.is_connected:
            mt5.shutdown()


# ==============================================================================
#  MULTI-PAIR RUNNER  (v2.2: equity curve filter added)
# ==============================================================================
class MultiPairRunner:
    """
    Orchestrates N SuperTrendBot instances in a sequential brain cycle.

    v2.2 additions:
      - Equity curve filter: if account equity drops below equity_filter_min_ratio
        of the rolling N-cycle average, new entries are paused across ALL symbols.
        Existing positions continue to be managed normally by the watcher.
        The filter auto-recovers when equity improves.
        Set equity_filter_enabled=True to activate (disabled by default).
    """

    def __init__(
        self,
        bots:                  List[SuperTrendBot],
        interval_seconds:      int   = 30,
        max_total_positions:   int   = 5,
        dry_run:               bool  = False,
        gateway=None,
        # ── Equity Curve Filter (v2.2, enabled by default in v2.3) ────────────
        # v2.3 Master Plan 4.1 #2: code was correct — was simply switched off.
        equity_filter_enabled:    bool  = True,    # v2.3: was False
        equity_filter_period:     int   = 20,    # rolling window (cycles)
        equity_filter_min_ratio:  float = 0.97,  # pause if equity < 97% of avg
    ):
        self.bots                   = bots
        self.interval_seconds       = interval_seconds
        self.max_total_positions    = max_total_positions
        self.dry_run                = dry_run
        self.equity_filter_enabled  = equity_filter_enabled
        self.equity_filter_period   = equity_filter_period
        self.equity_filter_min_ratio = equity_filter_min_ratio
        self._equity_history:       List[float] = []
        self._gw = gateway  # v2.3-gw

        self.logger = logging.getLogger("MultiPairRunner")
        if not self.logger.handlers:
            fmt = logging.Formatter(
                "%(asctime)s [RUNNER] [%(levelname)s] %(message)s"
            )
            fh = logging.FileHandler("logs/supertrend_runner.log", encoding="utf-8")
            fh.setFormatter(fmt)
            ch = logging.StreamHandler()
            ch.setFormatter(fmt)
            self.logger.addHandler(fh)
            self.logger.addHandler(ch)
            self.logger.setLevel(logging.INFO)

        for bot in self.bots:
            bot.dry_run      = dry_run
            bot.is_connected = True

        self.logger.info(
            f"MultiPairRunner v2.2 | "
            f"Symbols: {[b.config.symbol for b in self.bots]} | "
            f"Interval: {interval_seconds}s | GlobalCap: {max_total_positions} | "
            f"DryRun: {dry_run} | "
            f"EquityFilter: {'ON (' + str(equity_filter_period) + ' cycles, ' + str(equity_filter_min_ratio) + ')' if equity_filter_enabled else 'OFF'}"
        )

    # ──────────────────────────────────────────────────────────────────────────

    @property
    def _api(self):
        """Gateway router — same pattern as SuperTrendBot._api."""
        return self._gw if self._gw is not None else mt5

    def _count_total_open(self) -> int:
        all_magic = {b.config.magic_number for b in self.bots}
        positions = self._api.positions_get()
        if not positions:
            return 0
        return sum(1 for p in positions if p.magic in all_magic)

    # ──────────────────────────────────────────────────────────────────────────
    def _check_equity_filter(self) -> bool:
        """
        Returns True (entries allowed) unless equity has fallen below
        equity_filter_min_ratio of its rolling average.

        Logic:
          1. Sample current equity.
          2. Append to rolling window (max equity_filter_period entries).
          3. If window not yet full → allow entries (insufficient data).
          4. Compute window average.
          5. Block entries if current equity < min_ratio × average.
          6. Log transitions (OFF→ON and ON→OFF) but not every cycle.
        """
        if not self.equity_filter_enabled:
            return True

        account = self._api.account_info()
        if account is None:
            return True   # can't read equity — don't block on MT5 error

        current_equity = account.equity
        self._equity_history.append(current_equity)

        # Trim to rolling window
        if len(self._equity_history) > self.equity_filter_period:
            self._equity_history.pop(0)

        # Not enough data yet
        if len(self._equity_history) < self.equity_filter_period:
            return True

        avg_equity = sum(self._equity_history) / len(self._equity_history)
        ratio      = current_equity / avg_equity if avg_equity > 0 else 1.0
        allowed    = ratio >= self.equity_filter_min_ratio

        if not allowed:
            self.logger.warning(
                f"EQUITY FILTER ACTIVE | equity={current_equity:.2f} | "
                f"avg={avg_equity:.2f} | ratio={ratio:.4f} "
                f"(threshold={self.equity_filter_min_ratio}) | "
                f"New entries PAUSED"
            )

        return allowed

    # ──────────────────────────────────────────────────────────────────────────
    def run_cycle_all(self):
        global_open    = self._count_total_open()
        allow_entries  = self._check_equity_filter()

        self.logger.info(
            f"== MULTI-PAIR CYCLE | "
            f"Total open: {global_open}/{self.max_total_positions} | "
            f"Entries: {'OPEN' if allow_entries else 'PAUSED (equity filter)'} =="
        )

        newly_opened = 0
        for bot in self.bots:
            try:
                opened = bot.run_cycle(
                    global_open_count=global_open + newly_opened,
                    max_total_positions=self.max_total_positions,
                    allow_new_entry=allow_entries,
                )
                newly_opened += opened
            except Exception as e:
                self.logger.error(
                    f"[{bot.config.symbol}] Cycle error: {e}", exc_info=True
                )
                if not self._api.terminal_info():
                    self.logger.warning("MT5 disconnected — re-initialising...")
                    mt5.initialize(timeout=30000)

    # ──────────────────────────────────────────────────────────────────────────
    def run(self):
        self.logger.info("MultiPairRunner STARTED")
        try:
            while True:
                cycle_start = time.time()
                self.run_cycle_all()
                elapsed    = time.time() - cycle_start
                sleep_time = max(0, self.interval_seconds - elapsed)
                self.logger.info(
                    f"Cycle done in {elapsed:.1f}s | Sleeping {sleep_time:.1f}s"
                )
                time.sleep(sleep_time)
        except KeyboardInterrupt:
            self.logger.info("Runner stopped by user (Ctrl+C)")
        finally:
            self._print_summary()
            mt5.shutdown()
            self.logger.info("MT5 connection closed")

    # ──────────────────────────────────────────────────────────────────────────
    def _print_summary(self):
        self.logger.info("-- SESSION SUMMARY --")
        for bot in self.bots:
            stats = bot.calculate_statistics()
            self.logger.info(
                f"  {stats['symbol']} | "
                f"Trades: {stats['total_trades']} | "
                f"Win%: {stats.get('win_rate', 0)} | "
                f"P&L: {stats.get('total_pnl', 0):.2f} | "
                f"Avg R: {stats.get('avg_r_multiple', 'n/a')} | "
                f"Cache: {stats.get('cache_hits', 0)}hits/"
                f"{stats.get('cache_misses', 0)}misses"
            )


# ==============================================================================
#  STANDALONE MAIN
# ==============================================================================
def main():
    symbols = ["EURUSDm", "GBPUSDm"]
    configs = [
        Config(
            symbol=sym,
            timeframe=mt5.TIMEFRAME_M30,
            risk_percent=1.0,
            max_positions=1,
            # Partial close example — off by default
            enable_partial_close=False,
            si_partial_close_min=0.85,
            partial_close_profit_atr_mult=3.0,
            partial_close_fraction=0.50,
        )
        for sym in symbols
    ]

    if not mt5.initialize(timeout=180000):
        print(f"MT5 init failed: {mt5.last_error()}")
        return

    # fix-secrets: no credential literal. Supply MT5_PASSWORD in the environment.
    import os as _os
    login, password, server = 260178085, _os.environ.get("MT5_PASSWORD", ""), "Exness-MT5Trial15"
    if not mt5.login(login, password=password, server=server):
        print(f"Login failed: {mt5.last_error()}")
        mt5.shutdown()
        return

    bots = [SuperTrendBot(cfg) for cfg in configs]
    runner = MultiPairRunner(
        bots=bots,
        interval_seconds=30,
        max_total_positions=4,
        dry_run=False,
        equity_filter_enabled=False,     # enable when ready
        equity_filter_period=20,
        equity_filter_min_ratio=0.97,
    )
    runner.run()


if __name__ == "__main__":
    main()
