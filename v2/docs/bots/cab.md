# CAB Bot (V2)
**Path:** 2/bots/cab_bot.py

## Overview
The V2 CAB Bot has been ported from cab_super/cab_entry.py. 
It detects structural inversions on the H4 timeframe and immediately executes entries, reversing any conflicting positions it currently holds.

## Execution Pipeline
1. **Guards:** Checks session times (blocks Asian session by default) and max spread limits.
2. **Inversion Detection:**
   - Evaluates the last two fully closed H4 bars.
   - **Bullish Inversion:** Previous bar closed bearish, latest bar closed bullish.
   - **Bearish Inversion:** Previous bar closed bullish, latest bar closed bearish.
3. **Auto-Reversal:** If an opposite signal fires while a position is held (e.g. holding a BUY, but Bearish Inversion occurs), the bot directly closes the position via the MT5Gateway and pauses briefly.
4. **Order Routing:** Passes the generated TradeSignal to the OrderRouter for margin/drawdown checks.
5. **Execution & Registration:** If approved, executes via MT5Gateway. The position size is calculated natively with dynamic step-precision routing (preventing MT5 10014 invalid volume errors). Registers a TradeThesis to the KnowledgeRegister.
