KNOWLEDGE REGISTER — LOCKED ARCHITECTURE v1
Supersedes: the "CROSS-BOT ARCHITECTURE — carried forward" section of the SuperTrend locked list, and generalizes CAB's locked Change 1 (Macro/Micro vector split) and Change 4 (entry/watcher state bus) from CAB-only to all three bots.
New file(s): a new shared module (e.g. knowledge_register.py), integrated via the existing SharedState pattern in unified_runner.py — no new IPC mechanism, no CSV/file-based state.

CORE PRINCIPLE:
The Register informs, it does not command. Each bot retains full sovereignty over its own entry/exit decisions. Only two categories of check are hard blocks (see LAYER 2 and LAYER 3 below) — everything else is an advisory input each bot's own logic decides how to weigh. This preserves the regime-complementarity architecture (three bots legitimately disagreeing is a feature, not a bug) while removing redundant/contradictory computation of the same underlying facts.

LAYER 0 — Shared Market State
Computed once per {symbol, timeframe, bar-close}, published for all bots:
  - Raw Wilder ADX value + percentile rank (retires 3 independent Wilder ADX implementations + ST's flaw-C ADX-from-rank approximation)
  - Raw ATR + ATR-ratio percentile rank
  - Body/range ratio + percentile rank
  - Regime label (RANGING/TRENDING_UP/TRENDING_DOWN/EXHAUSTION/UNKNOWN) — one canonical classifier replacing 3 independent ones
  - Session tag + session-quality flag (see Layer 0b)
  - Update timestamp + source bar-close time, so consumers can detect stale reads

LAYER 0b — Session & Execution Quality (NEW — not previously scoped per-bot)
One shared per-symbol signal combining: current session tag, live spread relative to that symbol's own recent-normal spread (generalizes the cost-aware spread logic already built independently in Ghost's _spread_allows_close and CAB's _spread_allows_close_cab into one shared pre-computed flag). Replaces three inconsistent per-bot session opinions (ST: hardcoded Asian FX block; Ghost: no session gate at all; CAB: two separate session concerns for entry and REAPER). Each bot still decides its own reaction to a low-quality flag — only the underlying fact is shared.

LAYER 1 — Thesis Registry
Generalizes CAB's already-locked Change 4 to ALL THREE bots, not CAB-only. Every entry (any bot, any magic) registers an immutable snapshot at fill time: entry ATR, entry regime, entry conviction (where available), direction, symbol, magic, setup type, Layer 0 state at that moment. Watchers read this snapshot instead of recalculating "what did entry conditions look like" later. Directly prevents the ATR-timeframe-mismatch class of bug already found in CAB (entry sizes off H4 ATR, watcher buffers off M15 ATR, no shared awareness).

LAYER 2 — Thesis Invalidation Bus
Codifies one ThesisInvalidation event: {symbol, direction, source_bot, reason, timestamp}. Generalizes three independently-built implementations of the same idea into one shared primitive:
  - SuperTrend: DEAD state trend-flip check
  - CAB: Opposite Signal Invalidation (OSI)
  - Ghost Grid: regime-arm-gate (GHOST_ARM_BLOCKED_REGIMES)
Any bot detecting a macro structure change against a direction publishes an invalidation event. Other bots subscribe and decide their own reaction (tighten trailing, freeze new probe arming, apply early-exit logic) — reaction stays bot-specific.
HARD RULE: an active invalidation flag for {symbol, direction} is a hard block on NEW entries in that direction across all bots. It is NEVER a hard block on managing an existing position — that stays each bot's own watcher's call (matches existing Ghost Grid precedent: new probes blocked, in-flight probes run to natural exit regardless of regime drift).

LAYER 3 — Portfolio Exposure Ledger
Generalizes CAB's Change 2 and SuperTrend's Change 8 (both currently locked as PER-BOT aggregate-R checks) into one cross-bot view, adding two things per-bot budgeting cannot see:
  1. Net directional exposure per symbol across ALL bots combined — e.g. ST long XAUUSD while Ghost Grid's 202 wants to open a short leg on the same symbol. Not a ban on opposing positions (mean-reversion vs trend-follow legitimately disagree at turning points) — but the account must be aware this is happening, not discover it via manual investigation (see: the still-unresolved Week 1 "31 unexplained magic isolation breaches").
  2. Correlation-aware combined risk cap — e.g. XAUUSDm + XAGUSDm treated as one correlated exposure bucket with its own combined ceiling, since independently-set risk_percent values on each symbol understate true combined single-factor exposure. This makes the Assessment Report's flagged "Gold concentration risk" concrete and enforceable rather than a narrative observation.
HARD RULE: a global per-symbol (or correlated-bucket) combined risk ceiling across all three bots is a hard block on new entries that would breach it. This is the one deliberately global, non-bot-specific override, because no individual bot can see the other two bots' exposure to make this call itself.

LAYER 4 — Decision Advisory API
Read interface each bot's existing entry-gate and watcher functions call into (implemented via the existing SharedState in-memory, RLock-protected pattern already proven in unified_runner.py — explicitly NOT a new CSV/file IPC mechanism):
  - get_market_state(symbol, timeframe) -> Layer 0 facts
  - get_entry_snapshot(ticket) -> Layer 1 immutable setup record
  - get_invalidation_flags(symbol) -> Layer 2 active flags, if any
  - get_portfolio_exposure(symbol_or_correlated_bucket) -> Layer 3 combined exposure figure
  - get_micro_degradation(ticket) -> generalizes CAB's locked Change 1 Micro Degradation Vector (R-velocity / price efficiency decay) from CAB-only to a shared, bot-agnostic signal available to ST and Ghost Grid's watchers as well, since trade decay is not a CAB-exclusive question

RECONCILIATION WITH PREVIOUSLY LOCKED PER-BOT CHANGES:
  - CAB's locked Change 1 (Macro/Micro vector split): Macro Vector's regime component should ultimately read from Layer 0 instead of CAB's own get_market_regime() once the Register is live. Micro Degradation Vector generalizes into Layer 4's get_micro_degradation(), shared rather than CAB-exclusive.
  - CAB's locked Change 2 (Grouped Portfolio R-Budgeting) and SuperTrend's locked Change 8 (per-symbol position group risk view): both remain as-is, PER-BOT, and should ship on their existing timeline — do NOT block them waiting for Layer 3. Layer 3 is additive (adds cross-bot net exposure + correlation awareness) on top of, not a replacement for, each bot's own existing per-bot aggregate-R check.
  - CAB's locked Change 4 (entry/watcher state bus): generalizes directly into Layer 1, scope expanded from CAB-only to all three bots.
  - CAB's locked Change 3 (event-driven execution anchors): stays CAB-specific implementation detail, not part of the Register — Layer 0's bar-close-triggered updates are a related but separate concept (Layer 0 publishes on bar close; each bot's own cycle timing, event-driven or polled, is unaffected by this).

ADDITIONAL SOURCES CONSIDERED AND EXPLICITLY DEFERRED (not locked in this pass):
  - Economic calendar / high-impact news blackout window shared across all bots — none of the three bots currently have this at all. Genuine gap, but new scope beyond what's been reviewed to date. Flag as a candidate for a future session, not part of this locked architecture.
  - Broker execution-quality feed (systemic slippage/spread-widening detection across all symbols simultaneously, e.g. rollover or news-driven) — partially covered by Layer 0b's per-symbol spread-quality flag; a full cross-symbol "something broker-side is wrong right now" meta-signal is a further extension, deferred.

IMPLEMENTATION SEQUENCING (recommended, not mandated):
  1. Layer 0 first — highest leverage, retires the most duplicated/approximated code (3x Wilder ADX, 3x regime classifier, ST's flaw-C approximation), lowest risk since it's read-only fact distribution with no behavior change to any bot's decision logic yet.
  2. Layer 1 next — needed before Layer 2/3 can be meaningfully useful (invalidation and exposure checks are more valuable once entry context is actually preserved and shared).
  3. Layer 2 and Layer 3 together — both are the first layers introducing hard-block behavior, should be tested together in demo before any live consideration, since both change entry behavior (new blocks that didn't exist before).
  4. Layer 4 API — really exists implicitly as soon as Layers 0-3 exist; formalizing it as a clean interface is a code-organization step, not a new capability, can be done incrementally alongside 1-3 rather than strictly after.