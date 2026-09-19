from threading import RLock
from typing import Dict, Tuple, List, Optional
from v2.core.data_models import MarketStateSnapshot, TradeThesis
import time
import json
import os
from dataclasses import asdict
import logging

logger = logging.getLogger("KnowledgeRegister")

# Raw Logging Mode: Bypasses all risk filters and invalidations to allow edge validation
#
# fix-parity-rawlogging (V1 -> V2 alignment, Sep 19 2026):
# This was False in V2 while V1 (core/knowledge_register.py:12) runs True. Because
# both books call the same two APIs -- is_entry_invalidated() and
# check_portfolio_entry_allowed() -- from identical call sites, the flag decided
# whether KR Layer 2 (entry invalidation bus) and Layer 3 (portfolio risk ceiling)
# existed at all. V1 ran with both layers short-circuited to always-allow; V2 ran
# with both armed. That made the two systems non-comparable as live books even
# though every strategy-level threshold matched. Flipped to True to match V1.
#
# Consequence, stated plainly: V2 no longer blocks any entry on invalidation-bus
# or portfolio-ceiling grounds. Entry counts may rise. Existing positions are
# unaffected -- these two APIs guard NEW entries only.
RAW_LOGGING_MODE = True

class KnowledgeRegister:
    """
    V2 Knowledge Register: The Central Data Bus.
    
    [PERMANENT MANDATE]
    The sole purpose of the Knowledge Register is to gather, serialize, and store 
    raw market state data. It exists to provide the necessary contextual information 
    required to perform offline statistical analysis and edge validation.
    
    It must NEVER be used to arbitrarily filter, block, or restrict trades based on 
    human preference. Any trade filters introduced in the future must be strictly 
    informed by the raw data analysis mapping why trades win vs. lose in specific regimes.
    """
    
    _instance = None
    _init_lock = RLock()
    _lock = RLock()

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
            
            # Layer 0: Oracle Data
            self._market_states: Dict[Tuple[str, str], MarketStateSnapshot] = {}
            
            # Layer 1: Thesis Tracking
            self._theses: Dict[int, TradeThesis] = {}
            
            # Layer 2: Invalidation Bus (Regime Blocks)
            self._invalidations: Dict[Tuple[str, int], dict] = {}
            
            # Layer 3: Correlation Buckets
            self._correlation_buckets: Dict[str, List[str]] = {
                "GOLD_SILVER": ["XAUUSDm", "XAGUSDm"],
                "FX_USD_MAJORS": ["EURUSDm", "GBPUSDm", "USDJPYm"]
            }
            self._max_bucket_risk_pct: Dict[str, float] = {
                "GOLD_SILVER": 3.0,
                "FX_USD_MAJORS": 4.0
            }
            
            self._state_file = "v2_knowledge_state.json"
            self._load_state()
            
            self._initialized = True

    def _load_state(self):
        """Loads theses from disk to survive script restarts."""
        if os.path.exists(self._state_file):
            try:
                with open(self._state_file, 'r') as f:
                    data = json.load(f)
                    for k, v in data.items():
                        if v.get('market_snapshot'):
                            v['market_snapshot'] = MarketStateSnapshot(**v['market_snapshot'])
                        self._theses[int(k)] = TradeThesis(**v)
                logger.info(f"Loaded {len(self._theses)} active theses from disk.")
            except Exception as e:
                logger.error(f"Failed to load KR state: {e}")

    def _save_state(self):
        """Serializes current theses to disk."""
        try:
            with open(self._state_file, 'w') as f:
                json.dump({str(k): asdict(v) for k, v in self._theses.items()}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save KR state: {e}")

    def publish_market_state(self, snapshot: MarketStateSnapshot) -> None:
        """Stores the latest Oracle snapshot."""
        with self._lock:
            self._market_states[(snapshot.symbol, snapshot.timeframe)] = snapshot


    def get_market_state(self, symbol: str, timeframe: str) -> Optional[MarketStateSnapshot]:
        """Retrieves the latest Oracle snapshot."""
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

    def get_bucket_for_symbol(self, symbol: str) -> Optional[str]:
        """Returns the bucket name the symbol belongs to, if any."""
        for bucket, symbols in self._correlation_buckets.items():
            if symbol in symbols:
                return bucket
        return None
        
    def get_max_risk_for_bucket(self, bucket: str) -> float:
        """Returns the maximum allowed risk percentage for the bucket."""
        return self._max_bucket_risk_pct.get(bucket, 100.0) # Default to 100% if not defined

    # -------------------------------------------------------------------
    # LAYER 1: Thesis Tracking
    # -------------------------------------------------------------------
    
    def register_trade_thesis(self, thesis: TradeThesis) -> None:
        """Registers an immutable snapshot of a position's entry context at fill time."""
        with self._lock:
            self._theses[thesis.ticket] = thesis
            self._save_state()
            
    def get_entry_snapshot(self, ticket: int) -> Optional[TradeThesis]:
        """Fetches the immutable fill-time context for a ticket."""
        with self._lock:
            return self._theses.get(ticket)
            
    def unregister_trade_thesis(self, ticket: int) -> None:
        """Removes thesis tracking upon trade closure and serializes to permanent ledger."""
        with self._lock:
            if ticket in self._theses:
                thesis = self._theses[ticket]
                try:
                    with open("v2_trade_ledger.jsonl", "a") as f:
                        f.write(json.dumps(asdict(thesis)) + "\n")
                except Exception as e:
                    logger.error(f"Failed to write thesis to permanent ledger: {e}")
                
                del self._theses[ticket]
                self._save_state()
                


    def get_active_theses(self) -> List[TradeThesis]:
        """Returns all currently active theses."""
        with self._lock:
            return list(self._theses.values())

    # -------------------------------------------------------------------
    # LAYER 2: Thesis Invalidation Bus  (V1 parity port — core/knowledge_register.py)
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
        Publishes a macro structure change invalidating new entries in a direction.
        direction: +1 invalidates BUY entries, -1 invalidates SELL entries.
        Mirrors V1 core/knowledge_register.py publish_invalidation exactly.
        """
        now = time.time()
        with self._lock:
            self._invalidations[(symbol, direction)] = {
                "symbol": symbol,
                "direction": direction,
                "source_bot": source_bot,
                "reason": reason,
                "timestamp": now,
                "expiry": now + ttl_seconds,
            }
            logger.warning(
                f"Invalidation published: [{symbol} dir={direction}] by {source_bot}. Reason: {reason}"
            )

    def is_entry_invalidated(self, symbol: str, direction: int):
        """
        Layer 2 HARD BLOCK check. Returns (True, reason) if new entries in
        this direction are blocked across all bots. Mirrors V1 exactly.
        """
        if RAW_LOGGING_MODE:
            return False, None
        now = time.time()
        with self._lock:
            event = self._invalidations.get((symbol, direction))
            if event:
                if now <= event["expiry"]:
                    return True, f"Blocked by {event['source_bot']}: {event['reason']}"
                else:
                    del self._invalidations[(symbol, direction)]
            return False, None

    # -------------------------------------------------------------------
    # LAYER 3: Portfolio Exposure Ledger  (V1 parity port)
    # -------------------------------------------------------------------

    def check_portfolio_entry_allowed(
        self,
        symbol: str,
        direction: int,
        proposed_risk_pct: float,
        account_equity: float
    ):
        """
        Layer 3 HARD BLOCK check. Enforces cross-bot aggregate risk ceilings
        and correlation bucket limits. Mirrors V1 exactly.
        """
        if RAW_LOGGING_MODE:
            return True, None

        invalidated, reason = self.is_entry_invalidated(symbol, direction)
        if invalidated:
            return False, f"Hard Block (Layer 2 Invalidation): {reason}"

        with self._lock:
            target_bucket = None
            for bucket_name, symbols in self._correlation_buckets.items():
                if symbol in symbols:
                    target_bucket = bucket_name
                    break

            if not target_bucket:
                return True, "Allowed (No correlation bucket restrictions applied)"

            current_bucket_risk_pct = 0.0
            for thesis in self._theses.values():
                if thesis.symbol in self._correlation_buckets[target_bucket]:
                    if thesis.fill_price > 0 and thesis.initial_sl > 0:
                        sl_dist = abs(thesis.fill_price - thesis.initial_sl)
                        estimated_risk_pct = (sl_dist / thesis.fill_price) * 100.0 * 0.1
                        current_bucket_risk_pct += estimated_risk_pct
                    else:
                        current_bucket_risk_pct += 0.5

            max_allowed = self._max_bucket_risk_pct.get(target_bucket, 5.0)
            if (current_bucket_risk_pct + proposed_risk_pct) > max_allowed:
                return False, (
                    f"Hard Block (Layer 3 Portfolio Risk): Bucket [{target_bucket}] risk "
                    f"would reach {current_bucket_risk_pct + proposed_risk_pct:.2f}%, "
                    f"exceeding ceiling of {max_allowed:.2f}%."
                )
            return True, "Allowed (bucket risk within ceiling)"
