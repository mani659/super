---

# Week 5 Trading Plan
**Period:** Aug 18–22 2026
**Account:** 474167713 · Exness-MT5Trial15
**Phase:** Phase 2 Demo Testing — Statistical Gate Evaluation
**Last Updated:** Aug 16 2026

---

## 1. Objective

Week 5 has one primary objective and one secondary objective.

**Primary:** Collect a second week of session-labelled Ghost 202 data to 
confirm or refute the eight statistical findings (F1–F8) discovered in 
Week 4. Confirmation requires the same directional signal across combined 
Weeks 4+5 data (n=580+ matched trades). Refutation requires a meaningful 
reversal in at least two of the five key metrics (LONDON win rate, 
NY_CLOSE+H4_UP win rate, ATR Q2 win rate, conviction < 40 win rate, 
ADX 20-25 win rate).

**Secondary:** Implement the one agreed change that does not require 
additional session data — the F6 cross-bot gate (block Ghost UP_PROBE 
arming when SuperTrend holds a confirmed LONG on XAUUSDm in the KR).

The system otherwise runs unchanged. No session filters, no ATR gates, 
no conviction gates, no ADX dead zone gates. Those require the Week 5 
data to confirm before implementation.

---

## 2. What Is Running This Week

### Ghost Grid (XAUUSDm)
- Magic 202: live SELL reversals at probe retraction. No new gates added 
  this week (session filter deferred pending Week 5 data confirmation).
- Magic 201: shadow mode, virtual fills only. No change.
- Magic 204: first real data expected this week following the decouple 
  fix applied Aug 16. GhostCache now persists after 202 fire. Monitor 
  daily for GHOST_CACHE_FIRE events in logs/sniper_hunter.log.
- Probe arming gate: TRENDING_UP / TRENDING_DOWN / UNKNOWN still blocked 
  (unchanged from Week 4).
- F6 gate (new this week): block UP_PROBE arming when KR contains active 
  SuperTrend LONG thesis on XAUUSDm. Log as GHOST_ARM_BLOCKED_ST_LONG.

### SuperTrend (11 symbols)
- All 11 symbols running unchanged.
- Watch list: XAUUSDm (magic 301890) has produced negative R for two 
  consecutive weeks. If Week 5 produces a third negative week on 7+ 
  closed trades, disable via config switch entering Week 6. Do not 
  disable mid-week.
- No parameter changes. No scaling. Two positive-expectancy weeks is not 
  enough to scale before the primary loss driver (Ghost 202 session drag) 
  is addressed.

### CAB Watcher (all symbols)
- Running unchanged on all symbols.
- logs/cab_watcher.log is now active for the first time (path fix Aug 16).
  Confirm populated within the first hour of Week 5 session.
- H5 SL tightness analysis will be run at end of Week 5 from this log.
- No parameter changes to SL multiplier, PROTECTOR threshold, HARVESTER 
  threshold, or REAPER threshold. Those depend on H5 outcome.

---

## 3. The One Agreed Code Change This Week

### F6 — Cross-Bot Gate on Ghost 202 Arming

**What it does:** Before arming a new probe on XAUUSDm in 
ghost_hunter_thread, read the KR thesis registry for any active 
SuperTrend thesis on XAUUSDm with direction = +1 (LONG). If found, 
suppress UP_PROBE arming and log the block event. DOWN_PROBE arming 
is unaffected.

**Why now:** Evidence threshold met without needing additional data. 
n=34 opposing events confirmed 8pp win rate drop (40.3% → 32.4%) and 
3× worse per-trade P&L (-$0.30 → -$0.94). Mechanistically sound: ST 
LONG = confirmed M30 trend thesis active = Ghost mean-reversion SELL 
fights that thesis. This is the KR cross-bot intelligence use case 
working as designed.

**Scope:** Entry arming only. No effect on any open positions, any 
existing probes, or any other symbol. Single KR read added to the arming 
decision block in ghost_hunter_thread (unified_runner.py).

**Implementation target:** unified_runner.py ghost_hunter_thread, 
inside the `if armed is None:` block, before the UP_PROBE arming 
assignment. Also mirror the same check in ghost_sniper.py run_hunter() 
for standalone mode consistency.

**Verification:** grep "GHOST_ARM_BLOCKED_ST_LONG" logs/unified_runner.log 
or logs/sniper_hunter.log after first ST XAUUSDm entry fires. If the 
gate never triggers in a week where ST has open XAUUSDm positions, the 
wire is broken — check KR thesis read in the hunter thread.

**IDE agent implementation prompt:**

```
Task: f6-cross-bot-gate
Files: unified_runner.py (ghost_hunter_thread), 
       ghost_super/ghost_sniper.py (run_hunter)

Context: When Ghost Grid attempts to arm a new UP_PROBE on XAUUSDm, 
check the KnowledgeRegister for any active SuperTrend thesis on 
XAUUSDm with direction = +1 (LONG). If found, suppress arming and log.

Evidence basis: n=34 opposing events, 8pp win rate drop, 3x worse 
per-trade P&L when ST holds LONG while Ghost 202 fires SELL.

In unified_runner.py ghost_hunter_thread:
Find the block inside `if armed is None:` that checks recent_high 
and arms UP_PROBE. Before the `if current_price > recent_high:` check, 
add:

    # F6 Cross-bot gate: block UP_PROBE when ST holds confirmed LONG
    st_long_active = False
    try:
        from core.knowledge_register import KnowledgeRegister
        kr = KnowledgeRegister()
        for thesis in kr._theses.values():
            if (thesis.symbol == SYMBOL and 
                thesis.bot_id in ("SuperTrend", "ST") and
                thesis.direction == 1):
                st_long_active = True
                break
    except Exception:
        pass  # fail open — never block on KR read failure
    
    if st_long_active and current_price > recent_high:
        logger.info(
            f"GHOST_ARM_BLOCKED_ST_LONG | "
            f"price={round(current_price,3)} | "
            f"ST LONG thesis active on XAUUSDm — suppressing UP_PROBE"
        )
        # Skip arming, continue loop
        time.sleep(1)
        continue

Important constraints:
- Fail open: if KR read throws any exception, st_long_active stays 
  False and arming proceeds normally. Never let a KR failure block 
  entries silently.
- DOWN_PROBE arming is NOT affected. Only UP_PROBE is gated.
- This is an arming gate only. It does not affect any open positions, 
  any existing probes, or the 202 fire logic once a probe is already 
  armed.
- If SYMBOL in this thread is configurable, gate applies to XAUUSDm 
  only — not to other symbols.
- Mirror the same gate in ghost_sniper.py run_hunter() at the same 
  logical point for standalone mode consistency.

After implementation, run:
  python test_ghost_gateway_port.py
All 18 tests must still pass. If any fail, do not deploy.

Add one new test to test_ghost_gateway_port.py:
    def test_19_f6_gate_logs_when_st_long_active(self):
        """
        When KR contains an active ST LONG thesis on XAUUSDm,
        GHOST_ARM_BLOCKED_ST_LONG should be logged.
        This is a logging/gate wiring test, not a KR unit test.
        """
        # Mock KR to return a ST LONG thesis
        # Verify the gate condition evaluates correctly
        # (Full integration test requires live KR — unit test 
        #  checks the condition logic only)
        from core.knowledge_register import KnowledgeRegister, TradeThesis
        import unittest.mock as mock
        kr = KnowledgeRegister()
        # Inject a mock thesis
        mock_thesis = mock.MagicMock()
        mock_thesis.symbol = "XAUUSDm"
        mock_thesis.bot_id = "SuperTrend"
        mock_thesis.direction = 1
        kr._theses[99999] = mock_thesis
        # Check gate detects it
        st_long_found = any(
            t.symbol == "XAUUSDm" and 
            t.bot_id in ("SuperTrend","ST") and 
            t.direction == 1
            for t in kr._theses.values()
        )
        self.assertTrue(st_long_found)
        # Clean up
        del kr._theses[99999]
        print("T19 PASS  F6 gate detects ST LONG thesis on XAUUSDm")

Report: exact lines modified in both files and test suite result 
(expected 19/19 pass).
```

---

## 4. Daily Monitoring Checklist

Run these checks each morning before stepping away. Takes 5 minutes.

### Check 1 — All threads alive
```
grep "Heartbeat OK" logs/unified_runner.log | tail -3
```
Expected: 5 threads alive in the most recent line.
Action if failed: check for FATAL or Exception lines above it.

### Check 2 — 204 firing (new this week)
```
grep "GHOST_CACHE_FIRE" logs/sniper_hunter.log | wc -l
```
Expected: nonzero by Day 3. If zero after Day 5, lower 
N_LAYERS_DEFAULT from 3 to 2 in ghost_super/ghost_cache.py — 
one change only, redeploy, monitor.

### Check 3 — F6 gate triggering
```
grep "GHOST_ARM_BLOCKED_ST_LONG" logs/unified_runner.log | tail -5
```
Expected: fires whenever ST has an open XAUUSDm position. 
If ST has open XAUUSDm trades visible in MT5 but this log 
line never appears, the gate wire is broken.

### Check 4 — CAB log active
```
wc -l logs/cab_watcher.log
```
Expected: growing line count each day. If zero or file missing 
on Day 1, the log path fix did not deploy — stop, re-check 
cab_watcher.py RotatingFileHandler path before proceeding.

### Check 5 — No naked trades
```
grep "FILL_NO_SL" logs/sniper_hunter.log | wc -l
```
Expected: zero. If nonzero, the Aug 8 SLTP fix has regressed.

### Check 6 — Circuit breaker status
```
grep "CIRCUIT BREAKER" logs/unified_runner.log | tail -3
```
Expected: nothing, or RESET lines only. 
Action if TRIPPED: check open positions manually, no new entries 
until next session. Account equity has hit 10% daily drawdown.

---

## 5. End-of-Week Data Collection

Run on Friday Aug 22 before reviewing results:

```
python extract_bot_logs.py --days 7
```

Collect and upload for analysis:
1. Output zip from extract_bot_logs.py
2. logs/sniper_v51_live_audit.csv (must have h4_direction_at_arm column)
3. logs/sniper_hunter.log (check for GHOST_CACHE_FIRE and 
   GHOST_ARM_BLOCKED_ST_LONG)
4. logs/cab_watcher.log (first full week — critical for H5)
5. logs/kpi_ledger.csv
6. MT5 ReportHistory HTML export — full account, all magic numbers, 
   Aug 16–22 2026 (same export format as last week)

---

## 6. End-of-Week Decision Triggers

These are the specific criteria that determine what changes enter Week 6.
Each is a go/no-go gate, not a judgment call.

| Trigger | Condition | Action if Met | Action if Not Met |
|---------|-----------|---------------|-------------------|
| LONDON gate | LONDON win rate < 35% combined Weeks 4+5 (n≥118) | Implement LONDON session suppression on probe arming in Week 6 | Defer — pattern may not be structural |
| NY_CLOSE direction gate | NY_CLOSE + H4_UP win rate < 32% combined (n≥108) | Implement H4_UP block during NY_CLOSE arming in Week 6 | Defer one more week |
| ATR floor gate | ATR Q2 win rate < 30% combined (n≥146) | Implement M1 ATR > 1.8 arming gate in Week 6 | Defer |
| Conviction gate | Conviction 20-40 win rate < 35% combined (n≥272) | Implement conviction > 40 gate in Week 6 | Defer |
| ADX dead zone gate | ADX 20-25 win rate < 33% combined (n≥218) | Implement ADX 20-25 suppression in Week 6 | Defer |
| 204 n_layers adjust | Zero 204 fires after Day 5 | Lower N_LAYERS_DEFAULT to 2 mid-week | Keep at 3 |
| SuperTrend XAUUSDm | Third consecutive negative-R week (n≥7 closed) | Disable magic 301890 via config switch entering Week 6 | Keep running |
| H5 CAB SL tightness | Median SL hit distance < 1.5×ATR across CAB losses | SL widening enters Week 6 agenda | Defer |

---

## 7. What Is Explicitly Off the Table This Week

These items will not be touched regardless of what the data shows 
mid-week. If a pattern appears that seems to call for one of these, 
register it as a new finding and evaluate it at the end-of-week session.

- No session filters implemented mid-week (session data must reach 
  combined n thresholds first)
- No changes to SL multiplier (0.35×ATR) — H5 not yet confirmed
- No changes to CAB PROTECTOR, HARVESTER, or REAPER thresholds
- No SuperTrend scaling (positive expectancy confirmed but drawdown 
  still -32.8%, loss driver not yet mitigated)
- No Ghost Grid MAX_LEGS changes
- No KR Layer 2 or Layer 3 hard blocks activated (RAW_LOGGING_MODE 
  stays True — still in edge validation phase)
- No MarketPulseEngine instantiation (H4 confirmed broken — 
  redesign is a Week 6+ architectural item)
- No cross-bot exits or position management changes (bots inform 
  each other; they do not command each other's exits)

---

## 8. Account Risk Context

Starting equity for Week 5: approximately $6,723 (estimated from 
KPI ledger Week 4 close).
Starting equity from inception: $10,000.
Total drawdown from inception: approximately -32.8%.

The account is in meaningful drawdown. The correct response to this 
is not to stop the data collection — the data collection is precisely 
what is needed to implement the fixes that reduce this drawdown. The 
correct response is to not introduce any changes that increase variance 
while the dataset is being built.

Ghost Grid 202 is the primary drawdown driver. The session filter 
findings (F1–F8) directly address this. One more week of data confirms 
them. Week 6 implements them. That is the plan.

SuperTrend is the only confirmed positive-expectancy component. It is 
not being scaled because doing so while the primary loss driver 
(Ghost 202) is still unaddressed increases net risk when it needs 
to decrease.

No discretionary intervention in open positions. No manual closes. 
No lot size changes mid-week. The system runs the plan.

---

## 9. V2 Parallel Build Notes

V2 (modular refactor, separate account) is running in parallel. 
Any V1 fixes applied this week (F6 gate, any mid-week 204 adjustment) 
should be mapped to the equivalent V2 component at the end of the week 
session, not mid-week. V1 is the live data source. V2 receives the 
validated changes after V1 confirms them.

---

*This document governs Week 5 decisions. Any deviation from the 
plan requires explicit discussion and must be recorded before 
implementation. Evidence before action.*
