---
trigger: always_on
---

# Project Boundaries & Bot Separation

**CRITICAL MANDATE FOR ALL AGENTS:**
You are operating in a multi-bot environment. The bots in this repository are **strictly independent** from one another. Do NOT mix their architectures, rules, or constraints.

1. **The `Super` Bot (V1):** 
   - The primary bot located in the root directory (running via `unified_runner.py`). 
   - Uses `ghost_sniper`, `super_trend`, and the V1 `cab_super` modules.
   - Operates with strict lot size caps (e.g. `max_lot_demo_cap = 0.01`).

2. **The `cab/` Bot:** 
   - A completely independent, standalone bot.
   - Runs on a *different MT5 terminal* and a *different account* with a *different balance*.
   - Uses a 3-tier ADX dynamic risk system: 
     - ADX < 30: Min lot size (0.01) for gridding.
     - ADX 30-60: Dynamic lot sizing (1% risk).
     - ADX > 60: Dynamic lot sizing (1% risk).
   - **DO NOT** apply V1's `max_lot_demo_cap` or global constraints to this bot.

3. **The `cab_multi_pair/` Bot:**
   - Another independent, standalone bot.
   - Uses its own execution logic and config, separate from both `Super` and `cab`.

**ACTIONABLE RULE:**
Never blindly apply a patch intended for the `Super` bot to the `cab` or `cab_multi_pair` bots. If you encounter unexpected behavior (like massive lot sizes) in `cab` or `cab_multi_pair`, investigate it in the context of *that specific bot's mathematical strategy and terminal balance*, not the `Super` bot's constraints. If there is any confusion, **ask the user first** before changing core logic.
