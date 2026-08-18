import logging
from typing import List, Optional
from v2.core.data_models import TradeSignal
from v2.core.knowledge_register import KnowledgeRegister
from v2.execution.mt5_gateway import MT5Gateway

logger = logging.getLogger("OrderRouter")

class OrderRouter:
    """
    V2 Order Router:
    Ingests proposed TradeSignals from bots, validates them against 
    global circuit breakers and Layer 3 Correlation Buckets.
    Acts as a strict passive filter (no math modification).
    """
    def __init__(self, gateway: MT5Gateway, kr: KnowledgeRegister):
        self.gateway = gateway
        self.kr = kr
        
        # Hardcoded constraints (to be moved to config later)
        self.max_global_positions = 15
        self.assumed_risk_per_trade_pct = 1.0 
        
        # Raw Logging Mode: Bypasses all risk filters to allow edge validation
        self.raw_logging_mode = True

    def route_signal(self, signal: TradeSignal, current_drawdown_pct: float, max_drawdown_pct: float) -> bool:
        """
        Validates a signal through all risk layers.
        Returns True if the signal is approved for execution, False if vetoed.
        """
        if self.raw_logging_mode:
            logger.info(f"[ROUTER APPROVED] {signal.symbol} via {signal.bot_name} (RAW LOGGING MODE)")
            return True
            
        # 1. Global Circuit Breakers
        if current_drawdown_pct >= max_drawdown_pct:
            logger.warning(f"[ROUTER VETO] {signal.symbol} | Daily Drawdown ({current_drawdown_pct:.2f}%) exceeds limit.")
            return False
            
        open_positions = self.gateway.positions_get()
        if open_positions is None:
            logger.error("[ROUTER ERROR] Failed to fetch MT5 positions. Vetoing signal for safety.")
            return False
            
        if len(open_positions) >= self.max_global_positions:
            logger.warning(f"[ROUTER VETO] {signal.symbol} | Max global positions ({self.max_global_positions}) reached.")
            return False

        # 2. Layer 3: Correlation Bucket Check
        bucket = self.kr.get_bucket_for_symbol(signal.symbol)
        if bucket:
            current_bucket_exposure = self._calculate_bucket_exposure(bucket, open_positions)
            max_allowed_risk = self.kr.get_max_risk_for_bucket(bucket)
            
            proposed_total_risk = current_bucket_exposure + self.assumed_risk_per_trade_pct
            
            if proposed_total_risk > max_allowed_risk:
                logger.warning(
                    f"[ROUTER VETO] {signal.symbol} | Bucket '{bucket}' risk limit breached. "
                    f"Current: {current_bucket_exposure}%, Proposed: {proposed_total_risk}%, Max: {max_allowed_risk}%"
                )
                return False
                
        logger.info(f"[ROUTER APPROVED] {signal.symbol} via {signal.bot_name}")
        return True

    def _calculate_bucket_exposure(self, bucket: str, open_positions: tuple) -> float:
        """
        Calculates the active risk deployed in a specific correlation bucket.
        For V2 performance, we assume a static 1.0% risk per open trade.
        """
        # We need the symbols that belong to this bucket
        # We can reach into the KR's private dict, or better, we can just iterate positions and check their bucket
        exposure = 0.0
        for pos in open_positions:
            pos_bucket = self.kr.get_bucket_for_symbol(pos.symbol)
            if pos_bucket == bucket:
                exposure += self.assumed_risk_per_trade_pct
                
        return exposure
