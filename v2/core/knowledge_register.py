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
RAW_LOGGING_MODE = False

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
