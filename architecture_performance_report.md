# Architecture and Performance Report: Unified Algo Trading Bot (Phase 2 Demo)

## 1. System Overview
The system is a fully automated, unified algorithmic trading architecture running exclusively on Exness MT5 demo (Account 474167713). It currently executes three primary, complementary trading models—a mean-reversion Ghost Grid, an M30 SuperTrend trend-follower, and a CAB H4 Inversion manager—inside a single Python process. By integrating multiple strategies under one roof, the bots share real-time regime intelligence and manage capital concurrently, executing via a single gateway.

## 2. Architecture Summary

### Thread Model
The unified runner operates via five daemon threads sharing a single MT5Gateway instance with a thread-safe lock to prevent race conditions:
- **Main Thread (60s):** Handles equity heartbeat, circuit breakers, magic isolation checks, and MT5 health.
- **GhostWatcher Thread (2s):** Monitors market pulse (ADX, ATR, conviction) and writes to SharedState.
- **GhostHunter Thread (1s):** Detects M1 probes and fires Ghost Grid legs (201/202/204).
- **CABWatcher Thread (15s):** Dedicated position fluid management thread for all active CAB positions.
- **CABEntry Thread (30s):** H4 inversion detection and execution (magic 999555).
- **SuperTrend Thread (30s):** Executes M30 trend following across 11 symbol pairs.

### Shared Infrastructure
- **MT5Gateway:** A single point of MT5 access utilizing a `threading.Lock` to strictly serialize API calls.
- **KnowledgeRegister:** The central nervous system for market intelligence. It strictly gathers and serializes raw market state data and trade outcomes, rather than arbitrarily blocking trades.
- **SharedState:** An in-memory, RLock-protected state store that replaces IPC overhead.
- **MQL5 Failover:** A highly robust EA (`UnifiedFailover.mq5`) providing 60s/120s failover protection across all symbols.

### Regime Complementarity Map

| Regime | ADX Signal | SuperTrend (M30) | Ghost Grid (M1) | CAB Watcher (H4) |
|---|---|---|---|---|
| **RANGING** | ADX low | SLEEPING | **ACTIVE (201/202)** | Watching |
| **STABLE** | ADX mid | Watching | 201 only | Watching |
| **TRENDING** | ADX 55+ | **ACTIVE** | 202 BLOCKED | REAPER alert |
| **EXHAUSTION** | ATR spike, weak body | Exits via DEAD state | 202 fading | **HARVESTER fires** |

## 3. Bot Details

### Ghost Grid (Mean-Reversion)
- **Active Regime:** RANGING / STABLE
- **Instruments:** XAUUSDm
- **Strategy Class:** Virtual accumulation grid reacting to M1 liquidity probes.
- **Entry Logic:** 
  - **Leg 201 (SCALP):** Always active, targets 1.0R. (Currently running in pure shadow/virtual mode).
  - **Leg 202 (REVERSAL):** Fires if ADX <= 40 and conviction <= 60. Fades the extreme of the probe.
  - **Leg 204 (GHOST CACHE):** A virtual nth-layer accumulator that fires deeper in the grid.
- **Management Logic:** Closes the entire grid at combined +1.0R or emergency stops at combined -3.0R. A protector lock moves SL to BE+30 points when combined +0.35R is hit. 
- **Key Parameters:** SL widened to 0.35xATR; 72-hour max stale grid lifespan; max 4 hard-capped legs.

### SuperTrend v2.3 (Trend-Following)
- **Active Regime:** TRENDING
- **Instruments:** 11 pairs (EURUSDm, GBPUSDm, XAUUSDm, XAGUSDm, BTCUSDm, ETHUSDm, USTECm, USOILm, USDJPYm, EURGBPm, AUDNZDm)
- **Strategy Class:** M30 dynamic trend follower utilizing K-Means optimal factor selection across 100 historical bars.
- **Entry Logic:** Waits for M15 regime confirmation and an incubation period (2 M30 bars) before committing capital on trend alignment.
- **Management Logic:** Operates on an intelligence-driven state machine (INCUBATING, CONFIRMED, DECAYING, DEAD). Uses an R-lock ratchet to move SL into profit (+1R locks BE, +2R locks 1R, etc.).
- **Key Parameters:** SL multiplier varies from 2.5x to 3.0x; target 5.0x to 6.0x ATR; Si-Confirmed threshold = 0.65.

### CAB Watcher (Exhaustion/Inversion)
- **Active Regime:** EXHAUSTION
- **Instruments:** All symbols
- **Strategy Class:** H4 two-bar inversion entry and fluid position management.
- **Entry Logic:** Detects H4 bullish/bearish engulfing structures. Blocks entries during Asian hours (00:00-07:00 UTC) and strictly checks spread.
- **Management Logic:** Uses a fluid milestone matrix:
  - **PROTECTOR:** SL to BE + M15 ATR buffer at +1.2R.
  - **HARVESTER:** Close 50% and trail at +2.0R.
  - **REAPER:** Aggressively kills negative positions (-0.5R) if trend strength decays (SI<0.45, ER<0.25).
- **Key Parameters:** ATR-based lot sizing hard-capped at 0.01 demo maximum; strict limit of max 4 positions per symbol.

## 4. Week 4 Performance (Aug 11-15 2026)
- **Account Equity Trajectory:** $10,000 start → ~$6,723 at Week 4 close (-32.8% overall drawdown).
- **Ghost 202:** 347 fills on XAUUSDm (net ~$124 loss). This is the **primary drawdown driver**.
- **SuperTrend:** 110 entries across all symbols, generating a weighted average R of +0.088 over 58 closed trades. This marks the second consecutive week of positive expectancy.
- **CAB Watcher:** 31 entries. 2 PROTECTOR fires (first protector data in system history). 0 HARVESTER and 0 REAPER fires.
- **Ghost 201:** 479 virtual shadow fires.
- **Ghost 204:** 0 fires due to a now-resolved decoupling bug.

*Drawdown Honesty:* The primary cause of the drawdown is Ghost 202's aggressive counter-trend execution during specific high-momentum macro sessions, particularly when fading into strong H4 trends during the London and NY Close overlaps.

## 5. Statistical Findings (Week 4 Analysis)

*Note: All findings are derived from 293 matched Ghost 202 trades. Implementation of gates is deferred pending Week 5 validation.*

| ID | Finding Summary | Sample Size | Key Metric | Status |
|---|---|---|---|---|
| F1 | ATR is the strongest predictor of outcome. | n=293 | Q4 High-ATR win%=57.5% vs Q2 Low-ATR win%=27.4% | Pending Week 5 |
| F2 | NY_OVERLAP + H4_DOWN is the only highly profitable subset. | n=31 | win%=64.5%, +$1.55/trade | Pending Week 5 |
| F3 | Conviction > 50 strongly predicts wins (monotonic relationship). | n=293 | Conviction > 50 yields 50.0% win | Pending Week 5 |
| F4 | ADX 20-25 is a non-tradable "dead zone". | n=109 | win%=32.1%, -$0.69/trade | Pending Week 5 |
| F5 | LONDON session is structurally negative regardless of H4 trend. | n=59 | win%=28.6% (with H4 Down), -$1.04/trade | Pending Week 5 |
| F6 | Ghost 202 severely underperforms when fighting SuperTrend LONGs. | n=34 | win%=32.4%, 3x worse avg loss | Actionable Now |
| F7 | NY_CLOSE + H4_UP is the second-worst combination. | n=54 | win%=27.8%, -$0.68/trade | Pending Week 5 |
| F8 | Low ATR suppresses mean-reversion amplitude (spread consumes SL). | n=74 | win%=31.1%, avg hold 6 min | Pending Week 5 |

## 6. What Comes Next
- **Week 5 Objectives:** Collect a second consecutive week of session-labeled data to statistically confirm F1-F8. Implement the F6 cross-bot gate to immediately block Ghost UP_PROBE arming when SuperTrend holds a confirmed LONG thesis.
- **Gate System Status:** 
  - Gate 1 (Architecture Stability) = PASSED.
  - Gate 2 (204 vs 202) = In Progress.
  - Gate 3 (Individual Conviction) = In Progress (SuperTrend passing).
  - Gate 4/5 (Regime Matrix & Instrument Fit) = In Progress.
  - Gate 6 (Live Deployment) = The Finish Line.
- **Path to Live Deployment:** Achieve Gate 6 (avg R > 0.3 over 50 live trades on micro-lots). We require the session filters and regime alignment findings (F1-F8) to pass their Week 5 validation before they are hard-coded into the entry logic.

## 7. Open Collaboration Note
This architecture and statistical dataset are being shared as a discussion starter regarding quantifiable market edges. I am entirely open to either mechanically enhancing this current foundation or executing a clean-sheet build if the data dictates it. I bring deep production infrastructure knowledge and rigorous statistical methodology; I am eager to collaborate with your market intuitions.
