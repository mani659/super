from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class MarketStateSnapshot:
    """Canonical record of a symbol's state at a point in time."""
    symbol: str
    timeframe: str
    timestamp: float
    source_bar_time: int
    adx_raw: float
    adx_percentile: float
    atr_raw: float
    atr_percentile: float
    body_range_ratio: float
    regime: str           # "TRENDING_UP", "RANGING", etc.
    session: str          # "ASIAN", "LONDON", "NY"
    current_spread: float
    normal_spread: float
    
    # New MACD properties (Week 2 Plan)
    macd_raw: float = 0.0
    macd_signal: float = 0.0
    
    # Pre-calculated scoring weights
    scores: Dict[str, float] = field(default_factory=dict)
    
@dataclass
class TradeSignal:
    """A standardized instruction emitted by any bot logic module."""
    symbol: str
    bot_name: str
    magic_number: int
    order_type: str       # "BUY" or "SELL"
    sl_price: float
    tp_price: float = 0.0
    layer_depth: int = 1
    context: str = ""     # e.g., "SNIPER_201"
    
@dataclass
class TradeThesis:
    """Registration record of why a trade was opened (Immutable Snapshot)."""
    ticket: int
    symbol: str
    direction: int        # +1 for BUY, -1 for SELL
    bot_system: str
    setup_type: str       # e.g., "H4_INV_BUY", "SNIPER_201"
    fill_price: float
    initial_sl: float
    initial_tp: float
    entry_atr: float
    regime_at_entry: str
    entry_conviction: float
    layer_depth: int
    timestamp: float
    arming_h4_direction: str = ""
    arming_m15_regime: str = ""
    market_snapshot: Optional[MarketStateSnapshot] = None
    is_virtual: bool = False
