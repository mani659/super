# Trade Manager (V2)
**Path:** 2/execution/trade_manager.py

## Purpose
The unified Trade Manager is responsible for handling all active trades across every bot in the V2 architecture. Rather than relying on MT5 history to reverse-engineer a trade's starting risk, it queries the KnowledgeRegister for the immutable TradeThesis to calculate dynamic trailing stops accurately.

## Dynamic Management Gates

### Gate 1: Break Even + $5
When a trade reaches 1R in profit (price distance equals the initial risk defined in the TradeThesis), the Trade Manager automatically moves the Stop Loss to the open price plus an equivalent of $5 risk buffer (to cover spread/commissions). 

### Gate 2: 1R Dynamic Trailing
Once Break Even is locked in, the Trade Manager begins a strict 1R trail. The Stop Loss will dynamically move up to stay exactly 1R behind the Maximum Favorable Excursion (current price), capturing profits as the trend runs while still giving the trade 1R of breathing room.

### Gate 3: H1 Structural Invalidation
For trades that are currently losing (in drawdown), the Trade Manager scans the last 4 hours of H1 candles. 
- If it's a BUY and the current price drops below the absolute low of the last 4 H1 candles, the trade is killed early.
- If it's a SELL and the current price spikes above the absolute high of the last 4 H1 candles, the trade is killed early.
This stops us from holding onto doomed setups until they hit the hard stop loss.
