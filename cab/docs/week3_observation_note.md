# Week 3 Observation Note — CAB Standalone

**Period:** 30 Aug – 5 Sep 2026  
**Phase:** Pure Observation Window (ADR-003)  
**Status:** No strategy or parameter changes. Telemetry v2.1.1 active during the week; v2.1.2 (M5 LTF) deployed at end of week (5 Sep).

---

## 1. Stance

This note records only what the market delivered. No recommendations, no parameter suggestions, no code changes. Decision gate remains ~12 Sep 2026.

---

## 2. Metric Results (as defined in observation_window_plan.md)

### Metric 1 — Continuation Winners (> +1.5R or > +$800)

| Item | Result |
|------|--------|
| Large winners closed | **0** |
| Closed Continuation P&L (approx) | **≈ –$1,211** |
| Notable closed trades | EURGBP CONT_TREND_BUY –$276 · GBPUSD CONT_TREND_SELL –$455 · GBPUSD CONT_TRAP_SELL –$480 (REAPER) |

No trade met the large-winner threshold. Pattern continues from Week 2: the single large BTC outlier that defined Week 1 has not repeated.

### Metric 2 — Inversion + Grid Weekly Drag

| Vector | Approx Closed P&L | Notes |
|--------|-------------------|-------|
| Inversion | **≈ –$423** | Two USOIL INV_EXH_BUY losses (–$153, –$344). One EURUSD INV_EXH_SELL closed +$74 via H1. |
| Grid | **≈ +$20 to +$25** | Multiple small VWAP targets. No multi-layer blow-ups. Geometric spacing + 5-layer cap holding. |
| Combined | **≈ –$400** | Grid controlled; Inversion remains the primary drag source. |

### Metric 3 — Management Layer Effectiveness

| Exit Type | Observed Range | Assessment |
|-----------|----------------|------------|
| H1 Structural Invalidation | –0.18R to –0.53R | Still cutting well before –1.0R |
| REAPER | –0.57R on CONT_TRAP_SELL | Fired at threshold as designed |
| Grid VWAP | Small positives | Working |

Management layer remains the most reliable subsystem. Capital preservation intact.

---

## 3. Additional Observations (non-metric)

- v2.1.1 telemetry fields (ADX / Subtype / Session) appearing on harvest lines.
- Recurring log noise during the week: `[SKIP] No history orders found` — management robustness fix included in v2.1.2.
- Late-week open entries (4–5 Sep): BTC/ETH CONT_TRAP_BUY and BTC CONT_TREND_BUY — still open at time of note; not counted in closed results.
- v2.1.2 M5 LTF snapshot telemetry deployed 5 Sep; applies to new entries from Week 4 onward.

---

## 4. Running Score vs Decision Gate

| Question | Status after Week 3 |
|----------|---------------------|
| Large Continuation winners at usable frequency? | **No** (0 this window so far) |
| Inversion + Grid drag manageable? | Partially (Grid ok, Inversion still bleeds) |
| Management layer protecting capital? | **Yes** |

Window remains open. No action taken.

---

## 5. Data Sources Used

- `cab_watcher_production.log` (harvested trades 30 Aug – 5 Sep)
- MT5 Trade History Report (account 262924445, snapshot 5 Sep)
- Prior Week 1 / Week 2 baselines in `docs/`

*Exact dollar figures are approximate from log harvest lines. Final numbers should be reconciled against the official MT5 statement when convenient.*

*Post-note: v2.1.2 M5 LTF telemetry deployed 5 Sep; will apply to new entries from Week 4 onward. See `docs/feature_history.md` for details.*
