import os
import re
import csv
import glob
from collections import defaultdict
from datetime import datetime, timedelta

# --- Configuration & Architecture Mapping ---
LOG_DIRS = ['.', 'logs']
OUTPUT_REPORT_NAME = 'unified_performance_report.txt'

# Non-negotiable Magic Number Registry to detect silent modules
STRATEGY_REGISTRY = {
    "SuperTrend_EURUSD": 101234,
    "SuperTrend_GBPUSD": 201567,
    "SuperTrend_XAUUSD": 301890,
    "SuperTrend_XAGUSD": 401213,
    "Ghost_Sniper_Scalp": 201,
    "Ghost_Sniper_Reversal": 202,
    "Ghost_Sniper_TrendFollow": 203,
    "Ghost_Sniper_GhostCache": 204,
    "CAB_H4_Inversion": 999555
}

# Reverse mapping for lookups
MAGIC_TO_NAME = {v: k for k, v in STRATEGY_REGISTRY.items()}

# Time parsing regex
LOG_TIME_PATTERN = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')

def parse_datetime(dt_str):
    """Parses standard log timestamps and CSV fractional formats cleanly."""
    try:
        clean_str = dt_str.split(',')[0].split('.')[0].strip()
        return datetime.strptime(clean_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            return datetime.strptime(dt_str.split(' ')[0], "%Y.%m.%d")
        except Exception:
            return None

def init_metric_dict():
    return {"entries": 0, "sl_hits": 0, "tp_hits": 0}

def analyze_framework():
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    # Global multi-dimensional performance tracking structure
    performance = {
        "overall": defaultdict(init_metric_dict),
        "yesterday": defaultdict(init_metric_dict)
    }
    
    # System health diagnostics
    diagnostics = {
        'errors': [],
        'deadlocks': [],
        'spread_blocks': []
    }

    # Gather targets
    all_files = []
    for d in LOG_DIRS:
        if os.path.exists(d):
            all_files.extend(glob.glob(os.path.join(d, '*.log*')))
            all_files.extend(glob.glob(os.path.join(d, '*.csv')))
            all_files.extend(glob.glob(os.path.join(d, '*.txt')))

    for filepath in all_files:
        filename = os.path.basename(filepath)
        
        # --- Type A: Parsing Structured CSV Data ---
        if filepath.endswith('.csv'):
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    # Detect delimiter safely
                    sample = f.read(2048)
                    f.seek(0)
                    if not sample: continue
                    dialect = csv.Sniffer().sniff(sample) if ',' in sample or ';' in sample else None
                    reader = csv.reader(f, dialect=dialect if dialect else csv.excel)
                    headers = next(reader, None)
                    if not headers: continue

                    # Dynamically look for key performance metrics columns
                    h_lower = [h.lower() for h in headers]
                    time_idx = next((i for i, h in enumerate(h_lower) if 'time' in h or 'date' in h), 0)
                    magic_idx = next((i for i, h in enumerate(h_lower) if 'magic' in h), -1)
                    r_idx = next((i for i, h in enumerate(h_lower) if 'r_multiple' in h or 'profit' in h), -1)
                    comment_idx = next((i for i, h in enumerate(h_lower) if 'comment' in h or 'event' in h), -1)

                    for row in reader:
                        if len(row) <= max(time_idx, magic_idx): continue
                        dt = parse_datetime(row[time_idx])
                        if not dt: continue
                        
                        date_str = dt.strftime("%Y-%m-%d")
                        scope = "yesterday" if date_str == yesterday_str else "overall"
                        
                        try:
                            raw_magic = re.sub(r'\D', '', row[magic_idx])
                            magic = int(raw_magic) if raw_magic else None
                        except ValueError:
                            continue

                        if magic in MAGIC_TO_NAME:
                            # Isolate entries vs exits
                            row_str = " ".join(row).upper()
                            
                            # Standard Log Fill Event
                            if "FILL" in row_str or "ENTRY" in row_str or "ORDER_FILL" in row_str:
                                performance["overall"][magic]["entries"] += 1
                                if scope == "yesterday":
                                    performance["yesterday"][magic]["entries"] += 1
                                    
                            # Parse Stop Loss & Take Profit outcomes
                            if "SL_APPLIED" in row_str or "STOP_LOSS" in row_str:
                                performance["overall"][magic]["sl_hits"] += 1
                                if scope == "yesterday":
                                    performance["yesterday"][magic]["sl_hits"] += 1
                            elif "TP_APPLIED" in row_str or "TAKE_PROFIT" in row_str:
                                performance["overall"][magic]["tp_hits"] += 1
                                if scope == "yesterday":
                                    performance["yesterday"][magic]["tp_hits"] += 1
                                    
            except Exception:
                pass # Dynamic resilience for raw lock conflicts

        # --- Type B: Parsing Text Logging Files ---
        else:
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        # Capture system exceptions/errors
                        if "CRITICAL" in line or "ERROR" in line or "Exception" in line:
                            diagnostics['errors'].append(f"[{filename}:{line_num}] {line.strip()}")
                            continue
                        
                        # Capture dynamic roadblocks
                        if "GRID: depth cap reached" in line:
                            diagnostics['deadlocks'].append(f"[{filename}:{line_num}] {line.strip()}")
                        elif "deferred" in line.lower() or "blocked" in line.lower():
                            diagnostics['spread_blocks'].append(f"[{filename}:{line_num}] {line.strip()}")

                        # String parsing fallback for performance events in logs
                        match = LOG_TIME_PATTERN.search(line)
                        if match:
                            dt = parse_datetime(match.group(1))
                            if dt:
                                date_str = dt.strftime("%Y-%m-%d")
                                scope = "yesterday" if date_str == yesterday_str else "overall"
                                
                                # Trace magic signature within raw logs
                                for name, magic in STRATEGY_REGISTRY.items():
                                    if f"magic={magic}" in line or f"magic_number\": {magic}" in line or f" {magic} " in line:
                                        if "FILL" in line.upper() or "ENTRY" in line.upper():
                                            performance[scope][magic]["entries"] += 1
                                        if "SL" in line.upper() or "STOP LOSS" in line.upper():
                                            performance[scope][magic]["sl_hits"] += 1
                                        if "TP" in line.upper() or "TAKE PROFIT" in line.upper():
                                            performance[scope][magic]["tp_hits"] += 1
            except Exception:
                pass

    # --- Write Consolidated Analysis File ---
    with open(OUTPUT_REPORT_NAME, 'w', encoding='utf-8') as out:
        out.write("="*70 + "\n")
        out.write(f"        UNIFIED FRAMEWORK RUNNER METRICS AUDIT REPORT\n")
        out.write(f"  Generated On: {today.strftime('%Y-%m-%d %H:%M:%S')}\n")
        out.write(f"  Target Previous Session Checked: {yesterday_str}\n")
        out.write("="*70 + "\n\n")

        # Helper printing loop
        for timeline in ["yesterday", "overall"]:
            title = f"1. PREVIOUS SESSION TRADING PERFORMANCE ({yesterday_str})" if timeline == "yesterday" else "2. HISTORICAL OVERALL PERFORMANCE SUMMARY (ALL LOG DATA)"
            out.write(f"--- {title} ---\n")
            
            active_magics = set(performance[timeline].keys())
            silent_magics = set(STRATEGY_REGISTRY.values()) - active_magics
            
            # Print metrics for active strategies
            for magic, name in MAGIC_TO_NAME.items():
                if magic in active_magics:
                    m = performance[timeline][magic]
                    out.write(f"  ▶ {name} (Magic: {magic}):\n")
                    out.write(f"      ↳ Positions Executed : {m['entries']}\n")
                    out.write(f"      ↳ Stop Loss Hits    : {m['sl_hits']}\n")
                    out.write(f"      ↳ Take Profit Hits  : {m['tp_hits']}\n")
            
            # Call out completely silent systems explicitly
            out.write("\n  🚫 SILENT MODULES (Zero execution footprints detected):\n")
            if silent_magics:
                for sm in silent_magics:
                    out.write(f"      • {MAGIC_TO_NAME[sm]} (Magic: {sm})\n")
            else:
                out.write("      • None. Every script fired at least once.\n")
            out.write("\n" + "-"*50 + "\n\n")

        out.write("--- 3. CRITICAL OPERATIONAL ROADBLOCKS ---\n")
        out.write(f"  • Volatility Spread-Locks / Close Defers: {len(diagnostics['spread_blocks'])} events found\n")
        out.write(f"  • Grid Depth Exhaustion Restrictions     : {len(diagnostics['deadlocks'])} events found\n")
        out.write(f"  • Runtime Code Errors / Exceptions        : {len(diagnostics['errors'])} events found\n\n")
        
        if diagnostics['spread_blocks']:
            out.write("Recent Spread-Lock Warnings (Last 5):\n")
            for sb in diagnostics['spread_blocks'][-5:]: out.write(f"   {sb}\n")
        out.write("\n")
        
        if diagnostics['deadlocks']:
            out.write("Recent Grid Depth Protection Warnings (Last 5):\n")
            for dl in diagnostics['deadlocks'][-5:]: out.write(f"   {dl}\n")

    print(f"Framework report generated successfully: '{OUTPUT_REPORT_NAME}'")

if __name__ == '__main__':
    analyze_framework()