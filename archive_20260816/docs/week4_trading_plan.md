# WEEK 4 TRADING PLAN — Context, Retention Rationale, and Data Collection Objectives

You are the implementation agent for a production unified algorithmic trading system
running Ghost Grid (magic 201/202/204), SuperTrend (magic 101234–408213), and CAB
Watcher (magic 999555) on an Exness MT5 demo account. This document is your operating
brief for Week 4 (Aug 11–15 2026).

Read it in full before touching anything. This is not a change request — it is a
standing plan. The only mechanical changes authorised for this week are the two already
implemented in the previous session (Option 2 SLTP fix and the two new audit CSV
columns). Everything else runs untouched.

═══════════════════════════════════════════════════════════════════════
SECTION 1 — WHAT WAS CHANGED BEFORE WEEK 4 STARTED AND WHY
═══════════════════════════════════════════════════════════════════════

Two changes were made. Both are now live. Do not re-implement them.

CHANGE 1: Option 2 SLTP anchor fix in ghost_super/ghost_sniper.py send_order()
The Phase 2 SLTP modify request now computes SL/TP geometry from result.price
(actual fill price) rather than the pre-order tick price. This eliminates the
10016 broker rejection that was placing naked trades into the system and causing
the 15-second kill-switch to terminate positions at arbitrary prices. Week 3 data
showed this kill-switch contamination was a primary driver of Ghost Grid's -$288
loss, making it impossible to evaluate whether 202's strategy has genuine edge
problems or was simply being murdered by architecture failures. Week 4 is the
first clean week where 202 P&L reflects actual SL hits only.

CHANGE 2: Two new columns in sniper_v51_live_audit.csv
h4_direction_at_arm: 'UP', 'DOWN', or 'UNKNOWN' based on H4 structural close
direction at the moment every probe is armed.
kr_regime_at_arm: the KR Layer 0 M15 regime label at the same moment.
These columns are pure logging. They change nothing about entry logic, gate
decisions, or exit behavior. They exist to test two specific hypotheses that
cannot be answered without this data (see Section 3).

═══════════════════════════════════════════════════════════════════════
SECTION 2 — WHAT IS RETAINED AND THE EXACT REASON FOR EACH DECISION
═══════════════════════════════════════════════════════════════════════

GHOST GRID 202 — retained at current parameters, no ADX gate, no SL change

Week 3 showed 316 fills, 39.7% win rate, -$250 loss, and near-zero separation
between win/loss conviction and ADX (wins: conv 37.0 / ADX 19.4, losses: conv
37.1 / ADX 20.0). Three interventions were proposed and all rejected:

Proposal A (ADX bimodal gate: only fire at ADX > 40 or ADX < 15) — rejected
because the entire Week 3 dataset contains zero trades at those extremes. Gating
to a range where no historical evidence exists is not a refinement, it is a
complete strategy replacement with no data behind it.

Proposal B (revert SL to 0.20xATR) — rejected because the SLTP kill-switch
contamination (Change 1 above) was inflating the loss count for Week 3. We
cannot evaluate SL width until we have a clean week where every loss is a
legitimate SL hit and not a kill-switch termination at an arbitrary price.

Proposal C (add conviction or ADX entry gate) — rejected because the conviction
and ADX separation between wins and losses is effectively zero across 315 mapped
trades. A gate on a signal with zero predictive separation does not improve
expectancy — it just reduces volume while preserving the same win rate.

The real diagnosis for 202's losses is structural: all 316 fills were SELL
direction while Gold made a sustained 130-point rally during Week 3. The M15
regime classified conditions as RANGING throughout, while the H4 timeframe was
clearly trending upward. 202 was selling into an uptrend because the probe arming
decision consults M15 regime only. That is a regime disconnect problem, not a
parameter problem. Confirming it requires the new h4_direction_at_arm data
from Week 4. No parameter change can substitute for that evidence.

GHOST GRID 201 — retained as shadow, no live execution, no gate added

Week 3 showed 30 shadow fills, 8 wins (26.7%), with a genuine ADX separation:
wins averaged ADX 32.9 / conviction 80.3 vs losses at ADX 24.7 / conviction 72.5.
An ADX > 30 gate was proposed. Rejected because 8 winners is not a sample from
which to derive a hard threshold. The confidence interval on that finding spans
most of the plausible range. Shadow continues running and logging until 80+
fills are accumulated, at which point the ADX separation can be re-evaluated
against a sample that can actually support a threshold decision.

SUPERTREND — retained at current sizing, no scale-up

SuperTrend is the only confirmed positive-expectancy component: +$119.26 across
73 trades at 41.1% win rate. Scale-up was proposed and rejected for three reasons:

Reason 1: The account is at approximately -28.7% overall drawdown from the $10,000
starting balance. Increasing position sizing on any component while the portfolio
is in drawdown and while 202's losses continue means increasing both upside and
downside exposure simultaneously. The net effect is higher risk at a moment when
risk reduction is the priority.

Reason 2: 73 trades is approaching but not yet at the sample size needed for
a sizing decision. The standard error on a 41.1% win rate at n=73 is approximately
±5.7%, meaning the true win rate could plausibly be anywhere from 35% to 47%.
Another 50+ trades narrows that interval to a point where the decision has
more confidence behind it.

Reason 3: SuperTrend's best performance (56% win rate) came in the RANGING
regime label (25 trades). But RANGING was the active label while Gold made a
130-point directional move during the same week. If the regime label is
systematically mislabeling H4 trends as RANGING (Hypothesis H4), SuperTrend's
56% in RANGING may be a labeling artifact rather than genuine regime edge. This
needs one more week of cross-referenced data before being trusted as a signal
worth scaling toward.

CAB WATCHER — retained at current parameters, no REAPER adjustment, no ATR change

CAB produced -$17.46 across 139 trades at 30.2% win rate. Two interventions were
proposed:

Proposal A (widen M15 ATR buffer) — rejected because zero REAPER fires were
recorded this week. The REAPER is not cutting trades early. Every one of the 97
losing trades hit its initial SL. Widening the ATR buffer increases the dollar
loss on every loser without changing the win rate, producing a worse expected
value per trade.

Proposal B (tighten REAPER_SI_MAX) — rejected for the same reason. You cannot
tighten a gate that never fired. There is no evidence the REAPER is the problem
and no mechanism by which tightening it would address SL hits that occur before
any management milestone is reached.

The correct working hypothesis (H5) is that the 2.5xATR SL distance is inside
the normal H4 noise band for some or all of the pairs CAB trades. This would
explain the regime-flat 30% win rate: if SL is inside noise, regime does not
matter because the position gets stopped out before the market has decided
direction. Confirming H5 requires comparing the pip distance from entry to
SL hit against the ATR at entry for each of the 97 losing trades. That data
comes from MT5 trade history at the end of Week 4 — it is a calculation, not
a code change.

CROSS-BOT SYNERGY PROPOSALS — all deferred, no implementation

Three synergy architectures were proposed during Week 3 analysis:
SuperTrend as Range Oracle for Ghost Grid, Ghost Grid as Momentum Oracle for CAB,
CAB as Macro Oracle for SuperTrend. All three are intellectually coherent and
may become valuable eventually. All three are deferred for the same set of reasons:

The sample sizes underlying all three proposals are insufficient for production
wiring. The KR regime accuracy question (H4) must be resolved before any
cross-bot signal based on regime classification can be trusted. The KR
architectural principle is that the Register informs but does not command —
live exit decisions belong to individual bots, not to cross-bot signals derived
from one week of data. Wiring one bot's runtime state to another bot's exit
logic before the underlying signals are validated creates failure modes that
cross bot boundaries and are difficult to diagnose.

These proposals are recorded as H6 and H7 in the hypothesis registry. They will
be re-evaluated when H2 and H4 are confirmed and sample sizes meet the minimums
stated in the registry.

═══════════════════════════════════════════════════════════════════════
SECTION 3 — WHAT TO WATCH DURING WEEK 4 AND WHY EACH METRIC MATTERS
═══════════════════════════════════════════════════════════════════════

PRIORITY 1 — H2 confirmation: Ghost Grid direction bias

Every day, spot-check the sniper_v51_live_audit.csv file. Filter for
event_type = ARMED or FIRE and look at the h4_direction_at_arm column.
Count how many DOWN_PROBE armed events show h4_direction_at_arm = UP.
If this ratio is above 30% of all DOWN_PROBE events, the regime disconnect
is confirmed mid-week and should be flagged immediately.

Do not act on this mid-week. Flag it and continue collecting. The end-of-week
analysis will use the full week's data to make the determination.

At end of week run this exact query and save the output:

    python -c "
    import csv
    from collections import Counter
    rows = [r for r in csv.DictReader(open('sniper_v51_live_audit.csv'))
            if r.get('event_type') in ('ARMED',)]
    print('Total ARMED events:', len(rows))
    probe_h4 = Counter((r.get('comment',''), r.get('h4_direction_at_arm','')) for r in rows)
    for k,v in sorted(probe_h4.items()): print(k, v)
    print()
    fills = [r for r in csv.DictReader(open('sniper_v51_live_audit.csv'))
             if r.get('event_type') in ('ORDER_FILL_V51','ORDER_FILL_V51_NO_SL')]
    by_magic = Counter(r.get('magic','') for r in fills)
    print('Fills by magic:', by_magic)
    down_into_up = [r for r in rows if 'DOWN' in r.get('comment','')
                    and r.get('h4_direction_at_arm','') == 'UP']
    print('DOWN_PROBE into H4 UP:', len(down_into_up), 'of', len(rows), 'total')
    "

PRIORITY 2 — H4 confirmation: regime label accuracy

At end of week, from MT5 trade history, pull every SuperTrend entry and its
kr_regime_at_arm value from the audit log (match by timestamp within 60 seconds).
Also note the h4_direction_at_arm at the nearest Ghost Grid ARMED event within
30 minutes of each SuperTrend entry. If RANGING label appears alongside
h4_direction = UP or DOWN on more than 40% of SuperTrend entries, the KR M15
classifier is confirmed as unreliable for H4-timeframe decisions.

PRIORITY 3 — FILL_NO_SL count

Every day check logs/sniper_hunter.log for FILL_NO_SL events:

    grep -c "FILL_NO_SL" logs/sniper_hunter.log

The Week 3 baseline count was above zero. After the Option 2 SLTP fix, the
Week 4 target is zero or near-zero. If FILL_NO_SL events continue at the same
rate as Week 3, the fix did not deploy correctly and this must be investigated
immediately — do not wait until end of week.

PRIORITY 4 — Ghost Grid 202 SELL/BUY ratio

At end of week, count how many 202 fills were BUY vs SELL:

    python -c "
    import csv
    fills = [r for r in csv.DictReader(open('sniper_v51_live_audit.csv'))
             if r.get('magic') == '202' and r.get('event_type') in
             ('ORDER_FILL_V51','ORDER_FILL_V51_NO_SL')]
    from collections import Counter
    print('202 side distribution:', Counter(r.get('side','') for r in fills))
    "

Week 3 was 100% SELL. If Week 4 shows a more balanced BUY/SELL distribution,
that suggests the h4_direction gate on probe arming (once implemented) would
naturally correct the bias. If Week 4 is again heavily SELL-biased, the
structural short bias is confirmed regardless of H4 direction during the week.

PRIORITY 5 — CAB SL distance vs ATR (run at end of week from MT5 history)

From the MT5 ReportHistory export, for every CAB (magic 999555) losing trade,
compute: abs(entry_price - close_price) / ATR_at_entry. The ATR at entry is
available from the KR Layer 0 H4 snapshot — if not available directly, use
the cab_watcher.log which logs atr_raw on each management cycle. If the median
ratio is below 1.5, H5 is confirmed: SL is inside the H4 noise band.

PRIORITY 6 — System health checks (daily, takes 2 minutes)

    grep -c "FILL_NO_SL" logs/sniper_hunter.log
    grep -E "DEAD THREAD|CIRCUIT BREAKER|reconnect FAILED" logs/unified_runner.log | tail -10
    grep -c "LEG_TP SET" logs/sniper_brain.log
    python -c "
    import csv
    rows = list(csv.DictReader(open('logs/kpi_ledger.csv')))
    if rows:
        last = rows[-1]
        print('Last equity:', last.get('account_equity'))
        print('Entries allowed:', last.get('entries_allowed'))
        print('Open positions:', last.get('open_positions_total'))
    "

═══════════════════════════════════════════════════════════════════════
SECTION 4 — WHAT NOT TO DO THIS WEEK
═══════════════════════════════════════════════════════════════════════

Do not change any of the following regardless of what the daily logs show:
- SCALP_REV_SL_ATR_MULT (stays at 0.35)
- GATE_202_ADX_BLOCK (stays at 40)
- GATE_202_CONV_BLOCK (stays at 60)
- GHOST_ARM_BLOCKED_REGIMES (stays as configured)
- CAB PROTECTOR_R, HARVESTER_R, REAPER_R, REAPER_SI_MAX
- SuperTrend si_confirmed, risk_percent, max_positions
- Any cross-bot signal wiring or KR Layer 2/3 hard block activation
- N_LAYERS_DEFAULT for Ghost Cache 204

If a thread crashes, restart it. If MT5 disconnects, allow auto-reconnect.
If equity drops to circuit breaker threshold (10% daily drawdown), allow the
breaker to trip as designed. None of these events justify parameter changes
mid-week. Every parameter change during the data collection window corrupts
the dataset we are building to make those parameter decisions correctly.

═══════════════════════════════════════════════════════════════════════
SECTION 5 — END OF WEEK DELIVERABLES
═══════════════════════════════════════════════════════════════════════

At end of Week 4 (Aug 15 2026 close), collect and save the following before
the next analysis session:

1. MT5 ReportHistory HTML export — full trade history, all magic numbers
2. sniper_v51_live_audit.csv — full Week 4 file with h4_direction_at_arm
   and kr_regime_at_arm populated
3. logs/sniper_brain.log + rotations
4. logs/sniper_hunter.log + rotations
5. logs/unified_runner.log + rotations
6. logs/cab_watcher.log
7. logs/kpi_ledger.csv
8. Output of all five end-of-week queries from Section 3 saved to a
   file called week4_query_results.txt

Run the full test suite before the end-of-week handoff to confirm
no regressions accumulated during the week:

    python test_ghost_gateway_port.py
    python test_cab_gateway_port.py
    python test_cab_entry.py
    python test_supertrend_gateway_port.py

All four suites should pass at their established counts (17/17, 10/10,
16/16, 12/12). Report any failures immediately — do not wait for the
analysis session.

═══════════════════════════════════════════════════════════════════════
SECTION 6 — HYPOTHESIS STATUS GOING INTO WEEK 4
═══════════════════════════════════════════════════════════════════════

These are formally registered and will be evaluated against Week 4 data.
Do not attempt to answer them mid-week. Collect the data and let the
end-of-week analysis determine the verdict.

H1 [201 ADX Gate]: Requires 80+ shadow fills. Currently at 30. Accumulate.
H2 [202 Direction Bias]: Answerable from h4_direction_at_arm after Week 4.
    This is the highest priority hypothesis for the session.
H3 [202 Random Walk]: Requires 600+ total fills. Currently at ~315. Accumulate.
H4 [Regime Label Accuracy]: Answerable by cross-referencing new audit columns
    with SuperTrend entry timestamps after Week 4.
H5 [CAB SL Tightness]: Answerable from MT5 history SL distance calculation
    after Week 4.
H6 [Cross-Bot Range Oracle]: Blocked pending H4 confirmation. Do not evaluate.
H7 [Cross-Bot Momentum Oracle]: Blocked pending 30+ CAB PROTECTOR events.
    Currently at 6. Do not evaluate.
H8 [Equity trajectory]: Track weekly. Week 3 close $7,128.
    Week 4 target: stop the bleed from 202 kill-switch terminations
    (now fixed). Equity direction next week is the first clean signal
    about whether 202 has genuine structural problems beyond architecture.

The system runs. The data collects. The analysis happens at the end of the week.
Nothing changes in between.
