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
        # V1 parity: unified_runner MAX_GLOBAL_POSITIONS = 30. V2 used 15,
        # which blocked entries earlier than V1 and drifted trade counts.
        self.max_global_positions = 30
        self.assumed_risk_per_trade_pct = 1.0 
        
        # Raw Logging Mode: Bypasses all risk filters to allow edge validation
        self.raw_logging_mode = False

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
            # fix-router-realrisk: exposure is measured from each position's own SL
            # distance, not from a constant assumption (see _calculate_bucket_exposure).
            _acct = self.gateway.account_info()
            _equity = _acct.equity if _acct is not None else 0.0
            current_bucket_exposure = self._calculate_bucket_exposure(
                bucket, open_positions, _equity
            )
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

    def _position_risk_pct(self, pos, equity: float) -> float:
        """
        Real risk of one open position, as a percentage of equity, from its own SL.

        fix-router-realrisk: the bucket check used to add a hardcoded 1.0% per open
        trade no matter what that trade actually risked, so the Layer-3 veto was
        measuring a constant rather than the book. With risk per 1R observed across
        $4.44-$114.81 in the Sep-12 audit, the constant could under- or overstate a
        bucket by roughly an order of magnitude — the veto either never fired or fired
        on fiction. Falls back to the assumed constant only when risk is uncomputable.
        """
        try:
            if equity <= 0 or pos.volume <= 0:
                return self.assumed_risk_per_trade_pct
            risk_distance = abs(pos.price_open - pos.sl)
            if risk_distance <= 0:
                return self.assumed_risk_per_trade_pct
            si = self.gateway.symbol_info(pos.symbol)
            if si is None or si.point <= 0 or si.trade_tick_size <= 0:
                return self.assumed_risk_per_trade_pct
            point_value = si.trade_tick_value / (si.trade_tick_size / si.point)
            risk_money = (risk_distance / si.point) * point_value * float(pos.volume)
            return (risk_money / equity) * 100.0
        except Exception:
            return self.assumed_risk_per_trade_pct

    def _calculate_bucket_exposure(self, bucket: str, open_positions: tuple,
                                   equity: float = 0.0) -> float:
        """Active risk deployed in one correlation bucket, in % of equity."""
        exposure = 0.0
        for pos in open_positions:
            if self.kr.get_bucket_for_symbol(pos.symbol) == bucket:
                exposure += self._position_risk_pct(pos, equity)
        return exposure
