import time
import math
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from threading import RLock

logger = logging.getLogger("KnowledgeRegister")

# Raw Logging Mode: Bypasses all risk filters and invalidations to allow edge validation
RAW_LOGGING_MODE = True

# -------------------------------------------------------------------
# Enums and Data Models
# -------------------------------------------------------------------

class RegimeType(Enum):
    RANGING = "RANGING"
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    EXHAUSTION = "EXHAUSTION"
    UNKNOWN = "UNKNOWN"

class SessionTag(Enum):
    ASIAN = "ASIAN"
    LONDON = "LONDON"
    NY_OVERLAP = "NY_OVERLAP"
    NY_CLOSE = "NY_CLOSE"
    OFF_HOURS = "OFF_HOURS"

@dataclass(frozen=True)
class MarketStateSnapshot:
    symbol: str
    timeframe: str
    timestamp: float
    source_bar_time: int
    adx_raw: float
    adx_percentile: float
    atr_raw: float
    atr_percentile: float
    body_range_ratio: float
    regime: RegimeType
    session: SessionTag
    execution_quality_ok: bool
    current_spread: float
    normal_spread: float

@dataclass(frozen=True)
class TradeThesis:
    ticket: int
    magic: int
    symbol: str
    direction: int  # +1 for BUY, -1 for SELL
    bot_id: str
    setup_type: str
    fill_price: float
    fill_time: float
    entry_atr: float
    entry_regime: RegimeType
    entry_conviction: float
    initial_sl: float
    initial_tp: float
    market_snapshot: MarketStateSnapshot
    is_virtual: bool = False

@dataclass
class InvalidationEvent:
    symbol: str
    direction: int  # +1 (invalidates BUYs) or -1 (invalidates SELLs)
    source_bot: str
    reason: str
    timestamp: float
    expiry: float  # Time-to-live for transient flags

# -------------------------------------------------------------------
# Core Shared Knowledge Register
# -------------------------------------------------------------------

class KnowledgeRegister:
    """
    Knowledge Register: The Central Data Bus.
    
    [PERMANENT MANDATE]
    The sole purpose of the Knowledge Register is to gather, serialize, and store 
    raw market state data. It exists to provide the necessary contextual information 
    required to perform offline statistical analysis and edge validation.
    
    It must NEVER be used to arbitrarily filter, block, or restrict trades based on 
    human preference. Any trade filters introduced in the future must be strictly 
    informed by the raw data analysis mapping why trades win vs. lose in specific regimes.
    """
    """
    Centralized, thread-safe Knowledge Register (v1).
    Serves as the single source of truth for market state, trade theses,
    cross-bot invalidations, and combined portfolio exposure.
    """
    _instance = None
    _lock = RLock()
    _init_lock = RLock()

    def __new__(cls):
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super(KnowledgeRegister, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        with self._init_lock:
            if getattr(self, '_initialized', False):
                return
            
            # Initialize internal Data Stores first
            self._market_states: Dict[Tuple[str, str], MarketStateSnapshot] = {}
            self._theses: Dict[int, TradeThesis] = {}
            self._invalidations: Dict[Tuple[str, int], InvalidationEvent] = {}
            self._correlation_buckets: Dict[str, List[str]] = {
                "GOLD_SILVER": ["XAUUSD", "XAUUSDm", "XAGUSD", "XAGUSDm"],
                "FX_USD_MAJORS": ["EURUSD", "EURUSDm", "GBPUSD", "GBPUSDm", "USDJPY", "USDJPYm"]
            }
            self._max_bucket_risk_pct: Dict[str, float] = {
                "GOLD_SILVER": 3.0,
                "FX_USD_MAJORS": 4.0
            }
            
            # Set initialized to True only AFTER dicts are loaded
            self._initialized = True
            logger.info("KnowledgeRegister initialized successfully.")

    # -------------------------------------------------------------------
    # LAYER 0 & 0b: Shared Market State & Execution Quality
    # -------------------------------------------------------------------
    
    def publish_market_state(
        self,
        symbol: str,
        timeframe: str,
        source_bar_time: int,
        adx_raw: float,
        adx_percentile: float,
        atr_raw: float,
        atr_percentile: float,
        body_range_ratio: float,
        regime: RegimeType,
        session: SessionTag,
        current_spread: float,
        normal_spread: float
    ) -> None:
        """Publishes updated Layer 0 and Layer 0b market facts from canonical calculators."""
        execution_quality_ok = current_spread <= (normal_spread * 2.0)
        
        snapshot = MarketStateSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=time.time(),
            source_bar_time=source_bar_time,
            adx_raw=adx_raw,
            adx_percentile=adx_percentile,
            atr_raw=atr_raw,
            atr_percentile=atr_percentile,
            body_range_ratio=body_range_ratio,
            regime=regime,
            session=session,
            execution_quality_ok=execution_quality_ok,
            current_spread=current_spread,
            normal_spread=normal_spread
        )
        
        with self._lock:
            self._market_states[(symbol, timeframe)] = snapshot

    def get_market_state(self, symbol: str, timeframe: str) -> Optional[MarketStateSnapshot]:
        """Layer 4 API Read: Fetches the latest market state facts."""
        with self._lock:
            snapshot = self._market_states.get((symbol, timeframe))
            if snapshot:
                tf_to_seconds = {
                    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
                    "H1": 3600, "H4": 14400, "D1": 86400
                }
                max_age = tf_to_seconds.get(timeframe, 3600) + 300  # timeframe duration + 5min grace
                if time.time() - snapshot.timestamp > max_age:
                    if not hasattr(self, '_stale_logged_ts'):
                        self._stale_logged_ts = {}
                    if self._stale_logged_ts.get((symbol, timeframe)) != snapshot.timestamp:
                        logger.warning(f"Stale market data blocked for {symbol}_{timeframe}")
                        self._stale_logged_ts[(symbol, timeframe)] = snapshot.timestamp
                    return None
            return snapshot

    # -------------------------------------------------------------------
    # LAYER 1: Thesis Registry
    # -------------------------------------------------------------------

    def register_trade_thesis(self, thesis: TradeThesis) -> None:
        """Registers an immutable snapshot of a position's entry context at fill time."""
        with self._lock:
            self._theses[thesis.ticket] = thesis
            logger.info(f"Registered Trade Thesis for ticket #{thesis.ticket} ({thesis.bot_id} {thesis.symbol})")

    def get_entry_snapshot(self, ticket: int) -> Optional[TradeThesis]:
        """Layer 4 API Read: Fetches the immutable fill-time context for a ticket."""
        with self._lock:
            return self._theses.get(ticket)

    def unregister_trade_thesis(self, ticket: int) -> None:
        """Removes thesis tracking upon trade closure."""
        with self._lock:
            if ticket in self._theses:
                del self._theses[ticket]

    # -------------------------------------------------------------------
    # LAYER 2: Thesis Invalidation Bus
    # -------------------------------------------------------------------

    def publish_invalidation(
        self,
        symbol: str,
        direction: int,
        source_bot: str,
        reason: str,
        ttl_seconds: float = 1800.0
    ) -> None:
        """
        Publishes a macro structure change invalidating new entries in a specific direction.
        direction: +1 invalidates BUY entries, -1 invalidates SELL entries.
        """
        now = time.time()
        event = InvalidationEvent(
            symbol=symbol,
            direction=direction,
            source_bot=source_bot,
            reason=reason,
            timestamp=now,
            expiry=now + ttl_seconds
        )
        with self._lock:
            self._invalidations[(symbol, direction)] = event
            logger.warning(f"Invalidation published: [{symbol} dir={direction}] by {source_bot}. Reason: {reason}")

    def is_entry_invalidated(self, symbol: str, direction: int) -> Tuple[bool, Optional[str]]:
        """
        Layer 4 API Read & HARD BLOCK Check.
        Returns (True, reason) if new entries in this direction are blocked across all bots.
        """
        if RAW_LOGGING_MODE:
            return False, None
            
        now = time.time()
        with self._lock:
            event = self._invalidations.get((symbol, direction))
            if event:
                if now <= event.expiry:
                    return True, f"Blocked by {event.source_bot}: {event.reason}"
                else:
                    # Clean up expired flag
                    del self._invalidations[(symbol, direction)]
            return False, None

    # -------------------------------------------------------------------
    # LAYER 3: Portfolio Exposure Ledger
    # -------------------------------------------------------------------

    def check_portfolio_entry_allowed(
        self,
        symbol: str,
        direction: int,
        proposed_risk_pct: float,
        account_equity: float
    ) -> Tuple[bool, str]:
        """
        Layer 4 API Read & HARD BLOCK Check.
        Enforces cross-bot aggregate risk ceilings and correlation bucket limits.
        """
        if RAW_LOGGING_MODE:
            return True, None

        # Check 1: Invalidation Bus Block
        invalidated, reason = self.is_entry_invalidated(symbol, direction)
        if invalidated:
            return False, f"Hard Block (Layer 2 Invalidation): {reason}"

        with self._lock:

            # Identify Correlation Bucket
            target_bucket = None
            for bucket_name, symbols in self._correlation_buckets.items():
                if symbol in symbols:
                    target_bucket = bucket_name
                    break

            if not target_bucket:
                return True, "Allowed (No correlation bucket restrictions applied)"

            # Calculate total current risk across all active trade theses in this bucket
            current_bucket_risk_pct = 0.0
            for thesis in self._theses.values():
                if thesis.symbol in self._correlation_buckets[target_bucket]:
                    # Estimate position risk % based on initial SL distance or allocated risk
                    if thesis.fill_price > 0 and thesis.initial_sl > 0:
                        sl_dist = abs(thesis.fill_price - thesis.initial_sl)
                        # Standardized risk proxy evaluation
                        estimated_risk_pct = (sl_dist / thesis.fill_price) * 100.0 * 0.1  # Scaled estimate
                        current_bucket_risk_pct += estimated_risk_pct
                    else:
                        current_bucket_risk_pct += 0.5  # Fallback standard risk unit

            max_allowed = self._max_bucket_risk_pct.get(target_bucket, 5.0)
            if (current_bucket_risk_pct + proposed_risk_pct) > max_allowed:
                return False, (
                    f"Hard Block (Layer 3 Portfolio Risk): Bucket [{target_bucket}] risk "
                    f"would reach {current_bucket_risk_pct + proposed_risk_pct:.2f}%, "
                    f"exceeding ceiling of {max_allowed:.2f}%."
                )

            return True, "Allowed"

    # -------------------------------------------------------------------
    # LAYER 4: Decision Advisory API — Micro Degradation Vector
    # -------------------------------------------------------------------

    def get_micro_degradation(
        self,
        ticket: int,
        current_price: float,
        current_atr: float
    ) -> Dict[str, float]:
        """
        Layer 4 API Read: Calculates shared trade decay / R-velocity metrics.
        Computes price progress normalized by time held and volatility.
        """
        with self._lock:
            thesis = self._theses.get(ticket)
            if not thesis:
                return {"r_velocity": 0.0, "decay_factor": 0.0, "r_multiple": 0.0}

            time_held_hours = max((time.time() - thesis.fill_time) / 3600.0, 0.01)
            
            # Directional Price Distance
            if thesis.direction == 1: # BUY
                price_diff = current_price - thesis.fill_price
            else: # SELL
                price_diff = thesis.fill_price - current_price

            initial_risk = abs(thesis.fill_price - thesis.initial_sl)
            if initial_risk <= 0:
                initial_risk = current_atr * 1.5

            r_multiple = price_diff / initial_risk
            r_velocity = r_multiple / time_held_hours
            
            # Time decay factor: increases as trade stalls over time without making R-progress
            decay_factor = max(0.0, (time_held_hours / 12.0) - max(0.0, r_multiple))

            return {
                "r_multiple": round(r_multiple, 4),
                "r_velocity": round(r_velocity, 4),
                "decay_factor": round(decay_factor, 4)
            }
