#!/usr/bin/env python3
import os
import pandas as pd
from datetime import datetime
from pathlib import Path

# ─── PATH MANAGEMENT (ROBUST MULTI-DIRECTORY RESOLUTION) ────────────────────
# __file__ is root/reports/audit_report.py
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

# Input Paths (pointing up to the root folder)
UNIFIED_LOG_PATH = ROOT_DIR / "unified_session_log.csv"
SNIPER_AUDIT_PATH = ROOT_DIR / "sniper_v51_live_audit.csv"

# Output Path (saved directly inside the reports folder)
OUTPUT_REPORT_PATH = SCRIPT_DIR / "unified_performance_report.txt"


def generate_dynamic_report():
    # 1. Get current tracking date dynamically
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")

    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("        UNIFIED FRAMEWORK RUNNER METRICS AUDIT REPORT")
    report_lines.append(f"  Generated On: {timestamp_str}")
    report_lines.append(f"  Target Active Session Checked: {today_str} (TODAY)")
    report_lines.append("=" * 70 + "\n")

    # ─── SECTION 1: PARSING THE SNIPER LIVE AUDIT LOG ────────────────────────
    if not SNIPER_AUDIT_PATH.exists():
        report_lines.append(f"⚠️ Warning: {SNIPER_AUDIT_PATH.name} not found at root.\n")
        sniper_today = pd.DataFrame()
        sniper_hist = pd.DataFrame()
    else:
        try:
            # Read and sanitize timestamps
            df_sniper = pd.read_csv(SNIPER_AUDIT_PATH)
            df_sniper['parsed_dt'] = pd.to_datetime(df_sniper['timestamp'], errors='coerce')
            df_sniper['date_str'] = df_sniper['parsed_dt'].dt.strftime('%Y-%m-%d')
            
            # Split into historical vs current day data
            sniper_today = df_sniper[df_sniper['date_str'] == today_str]
            sniper_hist = df_sniper
        except Exception as e:
            report_lines.append(f"❌ Error processing Sniper log: {e}\n")
            sniper_today = pd.DataFrame()
            sniper_hist = pd.DataFrame()

    # ─── SECTION 2: PARSING THE UNIFIED SESSION LOG ─────────────────────────
    if not UNIFIED_LOG_PATH.exists():
        report_lines.append(f"⚠️ Warning: {UNIFIED_LOG_PATH.name} not found at root.\n")
        unified_today = pd.DataFrame()
        unified_hist = pd.DataFrame()
    else:
        try:
            df_unified = pd.read_csv(UNIFIED_LOG_PATH)
            df_unified['parsed_dt'] = pd.to_datetime(df_unified['timestamp'], errors='coerce')
            df_unified['date_str'] = df_unified['parsed_dt'].dt.strftime('%Y-%m-%d')
            
            unified_today = df_unified[df_unified['date_str'] == today_str]
            unified_hist = df_unified
        except Exception as e:
            report_lines.append(f"❌ Error processing Unified log: {e}\n")
            unified_today = pd.DataFrame()
            unified_hist = pd.DataFrame()

    # ─── SECTION 3: CURRENT TRADING DAY PERFORMANCE ──────────────────────────
    report_lines.append(f"--- 1. CURRENT SESSION TRADING PERFORMANCE ({today_str}) ---")
    
    # Track which magics have printed activity today
    active_magics_today = set()

    # Analyze Sniper Fills for Today
    if not sniper_today.empty:
        fills_today = sniper_today[sniper_today['event_type'].str.contains('FILL', na=False, case=False)]
        if not fills_today.empty:
            report_lines.append("  ▶ Ghost Sniper Strategy Direct Fills:")
            for magic, group in fills_today.groupby('magic'):
                active_magics_today.add(int(magic))
                total_fills = len(group)
                sides = group['side'].value_counts().to_dict()
                side_str = ", ".join([f"{k}: {v}" for k, v in sides.items()])
                report_lines.append(f"      ↳ Magic {int(magic)} ({group['leg_type'].iloc[0]}): {total_fills} Fills [{side_str}]")

    # Analyze Unified Session log for Today
    if not unified_today.empty:
        # Filter for concrete trade executions / closures if logged
        actions_today = unified_today[~unified_today['action'].isin(['WATCHER_CYCLE', 'CYCLE_COMPLETE'])]
        if not actions_today.empty:
            report_lines.append("\n  ▶ Structural Runner Actions Checked:")
            for bot_name, group in actions_today.groupby('bot'):
                magics = group['magic'].dropna().unique()
                for m in magics:
                    active_magics_today.add(int(m))
                report_lines.append(f"      ↳ {bot_name.upper()} Engine triggered {len(group)} lifecycle event(s).")

    # Determine Silent Modules Today
    all_known_magics = {
        201: "Ghost_Sniper_Scalp",
        202: "Ghost_Sniper_Reversal",
        203: "Ghost_Sniper_TrendFollow",
        204: "Ghost_Sniper_GhostCache",
        101234: "SuperTrend_EURUSD",
        201567: "SuperTrend_GBPUSD",
        301890: "SuperTrend_XAUUSD",
        401213: "SuperTrend_XAGUSD",
        999555: "CAB_H4_Inversion"
    }

    silent_magics = [m for m in all_known_magics if m not in active_magics_today]
    
    if silent_magics:
        report_lines.append("\n  🚫 SILENT MODULES (Zero execution footprints detected today):")
        for sm in silent_magics:
            report_lines.append(f"      • {all_known_magics[sm]} (Magic: {sm})")
    else:
        report_lines.append("\n  🔥 ALL MODULES ACTIVE: No silent modules detected today!")

    report_lines.append("-" * 50 + "\n")

    # ─── SECTION 4: OVERALL HISTORICAL PERFORMANCE SUMMARY ──────────────────
    report_lines.append("--- 2. HISTORICAL OVERALL PERFORMANCE SUMMARY (ALL LOG DATA) ---")
    
    if not sniper_hist.empty:
        historical_fills = sniper_hist[sniper_hist['event_type'].str.contains('FILL', na=False, case=False)]
        if not historical_fills.empty:
            for magic, group in historical_fills.groupby('magic'):
                magic_int = int(magic)
                friendly_name = all_known_magics.get(magic_int, f"Unknown Strategy")
                total_historical = len(group)
                
                # Check performance breakdown if comments are available
                sl_hits = len(group[group['comment'].str.contains('SL', na=False, case=False)])
                tp_hits = len(group[group['comment'].str.contains('TP', na=False, case=False)])
                
                report_lines.append(f"  ▶ {friendly_name} (Magic: {magic_int}):")
                report_lines.append(f"      ↳ Total Positions Executed Historically : {total_historical}")
                if sl_hits or tp_hits:
                    report_lines.append(f"      ↳ Logged Stop Loss Hard-Hits          : {sl_hits}")
                    report_lines.append(f"      ↳ Logged Take Profit Targets Hit      : {tp_hits}")
        else:
            report_lines.append("  No historical position fills detected in logs.")
    else:
        report_lines.append("  No historical Sniper data accessible to compute summary trends.")

    # ─── WRITE OUTPUT TO REPORT FILE ─────────────────────────────────────────
    with open(OUTPUT_REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write("\n".join(report_lines))

    print(f"✅ Success: Updated report saved cleanly to:\n   👉 {OUTPUT_REPORT_PATH}")


if __name__ == "__main__":
    generate_dynamic_report()