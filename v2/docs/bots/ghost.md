# Ghost Grid Bot (V2)
**Path:** 2/bots/ghost_bot.py

## Overview
The V2 Ghost Grid Bot has been ported from ghost_super/ghost_sniper.py (v5.2). 
All boilerplate file I/O, trailing stop calculations, and complex MT5 retry loops have been removed. It is now a pure state machine grid generator.

## Execution Pipeline
1. **Arming State:** 
   - Reads 1M data. If price breaks the 5-bar high/low, the bot enters the ARMED state.
   - It calculates a dynamic_step based on ATR (floored at 0.5 points).
2. **Triggering State:** 
   - Tracks the probe_extreme. If the price retraces by dynamic_step, the trigger fires.
3. **Layer 2 Gating (Intelligence):**
   - The bot reads the MarketStateSnapshot from the KnowledgeRegister.
   - **Scalp Leg (201):** Always fires if spread allows.
   - **Reversal Leg (202):** Blocked if ADX > 40 or Conviction > 60 (indicating strong trend).
4. **Order Routing:** Passes generated TradeSignals to the OrderRouter.
5. **Execution & Registration:** If approved, executes via MT5Gateway and logs the TradeThesis to the KnowledgeRegister.

## Missing V1 Elements (By Design)
- **Trend Leg (203):** Removed in V1 v5.2, correctly omitted here.
- **Ghost Cache:** The Ghost Cache system was omitted from the V2 execution cycle for now to focus purely on the baseline Scalp/Reversal mechanism.
- **CSV Logging:** Handled entirely by the unified KnowledgeRegister.
