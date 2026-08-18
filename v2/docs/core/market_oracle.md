# Market Oracle (V2)
**Path:** 2/core/market_oracle.py

## Purpose
Centralized calculation engine for Layer 0 market facts. Eliminates duplicated indicator computation across bots and standardizes the market regime state.

## Calculations (Strict 1:1 V1 Port)
- **ADX:** 14-period Wilder's Smoothing.
- **ATR:** 14-period True Range vs 50-period average.
- **Body/Range Ratio:** Candle body size vs full wick range.
- **MACD (Silent addition):** 12, 26, 9 configuration appended to stream, but does NOT affect the regime classification.

## Regime Classification Matrix
- **EXHAUSTION:** ATR Percentile >= 75 AND Body/Range <= 35
- **TRENDING_UP:** ADX Percentile >= 65 AND Body/Range > 35 AND Close > Close[14]
- **TRENDING_DOWN:** ADX Percentile >= 65 AND Body/Range > 35 AND Close <= Close[14]
- **RANGING:** Anything else.

## Output
Pushes a MarketStateSnapshot directly to the KnowledgeRegister.
