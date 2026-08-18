from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from v2.core.data_models import TradeSignal, MarketStateSnapshot

class IMarketOracle(ABC):
    """Computes all math, indicators, and regime definitions."""
    @abstractmethod
    def evaluate_symbol(self, symbol: str) -> MarketStateSnapshot:
        pass

class ITradingBot(ABC):
    """Pure logic bot that consumes Oracle data and emits TradeSignals."""
    @abstractmethod
    def run_cycle(self) -> List[TradeSignal]:
        pass

class IExecutionEngine(ABC):
    """Executes TradeSignals against the broker, enforcing Layer 2/3 limits."""
    @abstractmethod
    def execute_signals(self, signals: List[TradeSignal]) -> None:
        pass
