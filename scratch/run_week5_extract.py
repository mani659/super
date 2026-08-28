import os
import sys
import contextlib

def write_to_file(filepath, func):
    with open(filepath, 'w', encoding='utf-8') as f:
        with contextlib.redirect_stdout(f):
            func()
    print(f"Written to {filepath}")

def step2():
    import csv
    import pandas as pd
    from collections import Counter, defaultdict

    try:
        df = pd.read_csv("sniper_v51_live_audit.csv")
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df_w5 = df[df["timestamp"] >= "2026-08-18"].copy()

    # FILL events only (actual order executions — not ARMED/GATE_BLOCK)
    fills_w5 = df_w5[df_w5["event_type"].isin(
        ["ORDER_FILL_V51", "ORDER_FILL_V51_NO_SL"]
    )]
    fills_202_w5 = fills_w5[pd.to_numeric(fills_w5["magic"], errors="coerce") == 202]

    print(f"Week 5 total FILL events:        {len(fills_w5)}")
    print(f"Week 5 magic 202 FILL events:    {len(fills_202_w5)}")
    print(f"Week 5 magic 201 FILL events:    {len(fills_w5[fills_w5['magic'].astype(str)=='201'])}")
    print(f"Week 5 magic 204 FILL events:    {len(fills_w5[fills_w5['magic'].astype(str)=='204'])}")
    print()

    # 202 side distribution (UP_PROBE SELL bias check)
    print("=== 202 side distribution (Week 5) ===")
    print(fills_202_w5["side"].value_counts())
    print()

    # ARMED events — probe arming count and H4 direction breakdown
    armed_w5 = df_w5[df_w5["event_type"] == "ARMED"]
    print(f"=== Week 5 ARMED events: {len(armed_w5)} ===")
    print("Probe direction breakdown:")
    print(armed_w5["comment"].value_counts())
    print()
    print("H4 direction at arm breakdown:")
    print(armed_w5["h4_direction_at_arm"].value_counts())
    print()
    down_into_up = armed_w5[
        armed_w5["comment"].str.contains("DOWN", na=False) &
        (armed_w5["h4_direction_at_arm"] == "UP")
    ]
    print(f"DOWN_PROBE into H4_UP: {len(down_into_up)} of {len(armed_w5)} total ARMED")
    print()

    # F6 gate check
    blocked_st = df_w5[df_w5["event_type"].str.contains("BLOCKED_ST", na=False)
                       if "event_type" in df_w5.columns else pd.Series(dtype=bool)]
    print(f"=== F6 gate fires (GHOST_ARM_BLOCKED_ST_LONG): check unified_runner.log ===")

def step3():
    import pandas as pd
    import numpy as np
    try:
        df = pd.read_csv("sniper_v51_live_audit.csv")
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    fills = df[df["event_type"].isin(["ORDER_FILL_V51", "ORDER_FILL_V51_NO_SL"])]
    fills_202 = fills[pd.to_numeric(fills["magic"], errors="coerce") == 202].copy()
    fills_202["atr_at_fill"] = pd.to_numeric(fills_202["atr_at_fill"], errors="coerce")
    fills_202["adx_at_fill"]  = pd.to_numeric(fills_202["adx_at_fill"], errors="coerce")
    fills_202["conviction_at_fill"] = pd.to_numeric(
        fills_202["conviction_at_fill"], errors="coerce"
    )
    fills_202["h4_dir"] = fills_202["h4_direction_at_arm"].fillna("UNKNOWN")
    fills_202["week"] = np.where(
        fills_202["timestamp"] >= "2026-08-18", "W5",
        np.where(fills_202["timestamp"] >= "2026-08-11", "W4", "PRE")
    )

    for label, subset in [("Week 5", fills_202[fills_202["week"]=="W5"]),
                          ("Week 4+5 combined", fills_202[fills_202["week"].isin(["W4","W5"])])]:
        print(f"\n{'='*55}")
        print(f"  {label} — magic 202 fills: {len(subset)}")
        print(f"{'='*55}")

        print("\n--- Session breakdown ---")
        print(subset["session"].value_counts())

        print("\n--- Session × H4 direction fill counts ---")
        ct = pd.crosstab(subset["session"], subset["h4_dir"])
        print(ct)

        if len(subset.dropna(subset=["atr_at_fill"])) > 0:
            print("\n--- ATR quartiles ---")
            try:
                subset["atr_q"] = pd.qcut(
                    subset["atr_at_fill"].dropna(), 4,
                    labels=["Q1_low","Q2","Q3","Q4_high"], duplicates="drop"
                )
                print(subset["atr_q"].value_counts().sort_index())
            except Exception as e:
                print(f"  Cannot compute ATR quartiles: {e}")
            print(f"  ATR mean:   {subset['atr_at_fill'].mean():.4f}")
            print(f"  ATR median: {subset['atr_at_fill'].median():.4f}")
        else:
            print("\n--- ATR quartiles ---")
            print("  No ATR data.")

        if len(subset.dropna(subset=["adx_at_fill"])) > 0:
            print("\n--- ADX buckets (dead zone check) ---")
            bins = [0, 20, 25, 30, 35, 40, 999]
            labels = ["<20","20-25","25-30","30-35","35-40",">40"]
            subset["adx_bucket"] = pd.cut(
                subset["adx_at_fill"], bins=bins, labels=labels
            )
            print(subset["adx_bucket"].value_counts().sort_index())
        else:
            print("\n--- ADX buckets (dead zone check) ---")
            print("  No ADX data.")

        if len(subset.dropna(subset=["conviction_at_fill"])) > 0:
            print("\n--- Conviction buckets ---")
            cbins  = [0, 20, 30, 40, 50, 60, 999]
            clabels = ["<20","20-30","30-40","40-50","50-60",">60"]
            subset["conv_bucket"] = pd.cut(
                subset["conviction_at_fill"], bins=cbins, labels=clabels
            )
            print(subset["conv_bucket"].value_counts().sort_index())
        else:
            print("\n--- Conviction buckets ---")
            print("  No Conviction data.")

        print("\n--- FILL_NO_SL count ---")
        no_sl = subset[subset["event_type"] == "ORDER_FILL_V51_NO_SL"]
        print(f"  {len(no_sl)} naked fills (target: 0)")

def step4():
    import re
    log_files = [
        "logs/sniper_hunter.log",
        "logs/sniper_hunter.log.1",
        "logs/sniper_hunter.log.2",
    ]

    gc_fires = []
    arm_events = []
    for f in log_files:
        try:
            with open(f, encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    if "GHOST_CACHE_FIRE" in line:
                        gc_fires.append(line.strip())
                    if "ARMED UP" in line or "ARMED DN" in line:
                        arm_events.append(line.strip())
        except FileNotFoundError:
            pass

    print(f"Total GHOST_CACHE_FIRE events across all log rotations: {len(gc_fires)}")
    print(f"Total ARMED events in hunter log: {len(arm_events)}")
    print()
    if gc_fires:
        print("First 5 GHOST_CACHE_FIRE lines:")
        for l in gc_fires[:5]: print(f"  {l}")
        print("Last 5:")
        for l in gc_fires[-5:]: print(f"  {l}")
    else:
        print("ACTION REQUIRED: Zero 204 fires.")
        print("If this is end of Day 5+, lower N_LAYERS_DEFAULT from 3 to 2")
        print("in ghost_super/ghost_cache.py — one change only.")

    f6_fires = []
    for f in ["logs/unified_runner.log", "logs/unified_runner.log.1",
              "logs/sniper_hunter.log", "logs/sniper_hunter.log.1"]:
        try:
            with open(f, encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    if "GHOST_ARM_BLOCKED_ST_LONG" in line:
                        f6_fires.append(line.strip())
        except FileNotFoundError:
            pass

    print(f"\nF6 gate (GHOST_ARM_BLOCKED_ST_LONG) fires: {len(f6_fires)}")
    if f6_fires:
        print("Sample:")
        for l in f6_fires[:3]: print(f"  {l}")
    else:
        print("Zero F6 fires. If ST had open XAUUSDm positions this week,")
        print("the gate wire may be broken — check KR thesis read in hunter thread.")

def step5():
    import re
    cab_log_files = [
        "logs/cab_watcher.log",
        "logs/cab_watcher.log.1",
    ]

    reaper_fires = []
    protector_fires = []
    harvester_fires = []
    osi_fires = []
    sl_hits = []

    for f in cab_log_files:
        try:
            with open(f, encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    if "REAPER FIRED" in line:
                        reaper_fires.append(line.strip())
                    if "PROTECTOR FIRED" in line:
                        protector_fires.append(line.strip())
                    if "HARVESTER" in line and "FIRED" in line:
                        harvester_fires.append(line.strip())
                    if "OSI" in line and ("FIRED" in line or "triggered" in line.lower()):
                        osi_fires.append(line.strip())
        except FileNotFoundError:
            pass

    print(f"CAB fluid matrix fires — Week 5 (from logs/cab_watcher.log):")
    print(f"  REAPER fires:    {len(reaper_fires)}")
    print(f"  PROTECTOR fires: {len(protector_fires)}")
    print(f"  HARVESTER fires: {len(harvester_fires)}")
    print(f"  OSI fires:       {len(osi_fires)}")
    print()
    if protector_fires:
        print("PROTECTOR samples:")
        for l in protector_fires[:3]: print(f"  {l}")
    if reaper_fires:
        print("REAPER samples:")
        for l in reaper_fires[:3]: print(f"  {l}")

def step6():
    import pandas as pd
    try:
        kpi = pd.read_csv("logs/kpi_ledger.csv")
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    kpi["timestamp_utc"] = pd.to_datetime(kpi["timestamp_utc"])
    kpi_w5 = kpi[kpi["timestamp_utc"] >= "2026-08-18"]

    print(f"KPI ledger rows (Week 5): {len(kpi_w5)}")
    if len(kpi_w5) > 0:
        print(f"\nWeek 5 equity range:")
        print(f"  Start (first row): {kpi_w5['account_equity'].iloc[0]:.2f}")
        print(f"  End   (last row):  {kpi_w5['account_equity'].iloc[-1]:.2f}")
        print(f"  Min:               {kpi_w5['account_equity'].min():.2f}")
        print(f"  Max:               {kpi_w5['account_equity'].max():.2f}")
        print(f"  Week 5 P&L:        {kpi_w5['account_equity'].iloc[-1] - kpi_w5['account_equity'].iloc[0]:.2f}")
        
        print(f"\nOpen positions (time-averaged):")
        print(f"  Avg open 202:        {kpi_w5['open_ghost_202'].mean():.2f}")
        print(f"  Avg open SuperTrend: {kpi_w5['open_supertrend'].mean():.2f}")
        print(f"  Avg open CAB:        {kpi_w5['open_cab'].mean():.2f}")
        print(f"  Avg open total:      {kpi_w5['open_positions_total'].mean():.2f}")

        print(f"\nRegime distribution (XAUUSDm, Week 5):")
        print(kpi_w5["regime_xauusd"].value_counts())

        # Check if circuit breaker fired
        cb_rows = kpi_w5[kpi_w5["entries_allowed"] == 0]
        print(f"\nCircuit breaker active rows: {len(cb_rows)}")
        if len(cb_rows) > 0:
            print(f"  First CB trip: {cb_rows['timestamp_utc'].iloc[0]}")
            print(f"  Equity at trip: {cb_rows['account_equity'].iloc[0]:.2f}")

def step7():
    import pandas as pd
    import numpy as np
    print("SuperTrend performance (from MT5 HTML):")
    try:
        tables = pd.read_html("ReportHistory-474167713.html")
        t = max(tables, key=len)
        w5_mask = t.astype(str).apply(lambda x: x.str.contains("2026.08.18|2026.08.19|2026.08.20|2026.08.21|2026.08.22|2026.08.23")).any(axis=1)
        st_mask = t.astype(str).apply(lambda x: x.str.contains("SuperTrend")).any(axis=1)
        st_w5 = t[w5_mask & st_mask]
        print(f"Total entries: {len(st_w5)}")
        if len(st_w5) > 0:
            profits = pd.to_numeric(st_w5.iloc[:, -1], errors="coerce").dropna()
            win_pct = (profits > 0).mean() * 100
            avg_prof = profits.mean()
            print(f"  Count:  {len(profits)}")
            print(f"  Mean P&L: ${avg_prof:.2f}")
            print(f"  Win%:   {win_pct:.1f}%")
            print(f"  Mean R: DATA MISSING (R not logged in HTML)")
        
        xau_mask = st_w5.astype(str).apply(lambda x: x.str.contains("XAU")).any(axis=1)
        xau_st = st_w5[xau_mask]
        print(f"\nSuperTrend XAUUSDm (magic 301890):")
        print(f"  Fills: {len(xau_st)}")
        if len(xau_st) > 0:
            xau_profits = pd.to_numeric(xau_st.iloc[:, -1], errors="coerce").dropna()
            print(f"  Mean P&L: ${xau_profits.mean():.2f}")
            print(f"  Win%:   {(xau_profits > 0).mean()*100:.1f}%")
            if xau_profits.mean() < 0 and len(xau_profits) >= 7:
                print("  *** Third consecutive negative week — disable magic 301890 in Week 6 ***")

    except Exception as e:
        print(f"Error parsing HTML: {e}")

def step8():
    import os
    from pathlib import Path
    import pandas as pd

    root = Path(".")
    htm_files = list(root.glob("*.htm")) + list(root.glob("*.html"))
    print(f"MT5 HTML export files found in root:")
    for f in htm_files:
        print(f"  {f.name}  ({f.stat().st_size:,} bytes)")

    if not htm_files:
        print("WARNING: No .htm/.html files found in root.")
        print("Week 4 MT5 trade history is needed to compute win/loss outcomes")
        print("for the session × H4 gate confirmation analysis.")
        print("Please export from MT5 Account History → All History → Save as HTML")
        print("and place in the Super/ root folder.")
    else:
        for htm_path in htm_files:
            try:
                tables = pd.read_html(str(htm_path))
                print(f"\n{htm_path.name}: {len(tables)} tables found")
                for i, t in enumerate(tables):
                    print(f"  Table {i}: {t.shape[0]} rows × {t.shape[1]} cols")
                    print(f"  Columns: {list(t.columns[:8])}")
                trade_table = max(tables, key=len)
                print(f"\nLargest table ({len(trade_table)} rows):")
                print(trade_table.head(3).to_string())
            except Exception as e:
                print(f"  Parse error: {e}")

if __name__ == "__main__":
    write_to_file("log_extract/week5/ghost_202_w5_overview.txt", step2)
    write_to_file("log_extract/week5/session_h4_crosstab_w5.txt", step3)
    write_to_file("log_extract/week5/ghost_204_check_w5.txt", step4)
    write_to_file("log_extract/week5/cab_fluid_matrix_w5.txt", step5)
    write_to_file("log_extract/week5/kpi_equity_w5.txt", step6)
    write_to_file("log_extract/week5/supertrend_w5.txt", step7)
    write_to_file("log_extract/week5/mt5_export_check_w5.txt", step8)
