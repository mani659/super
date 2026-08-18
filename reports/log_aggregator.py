import os
import re
import csv
import glob
from collections import defaultdict
from datetime import datetime, timedelta

# Configuration
LOG_DIRS = ['.', 'logs']  # Look in root and logs directory
OUTPUT_REPORT_NAME = 'daily_performance_report.txt'

# --- Regular Expressions for parsing ---
LOG_TIME_PATTERN = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')

def parse_datetime(dt_str):
    try:
        return datetime.strptime(dt_str.split(',')[0].split('.')[0], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

def process_log_file(filepath, report_data, yesterday_str):
    bot_name = os.path.basename(filepath)
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            match = LOG_TIME_PATTERN.search(line)
            if not match:
                continue
                
            dt = parse_datetime(match.group(1))
            if not dt:
                continue

            date_str = dt.strftime("%Y-%m-%d")
            is_yesterday = (date_str == yesterday_str)

            # Categorize events
            if "CRITICAL" in line or "ERROR" in line or "Exception" in line:
                report_data['errors'].append(f"[{bot_name}:{line_num}] {line.strip()}")
            elif "WARNING" in line:
                report_data['warnings'].append(f"[{bot_name}:{line_num}] {line.strip()}")
            elif "GRID: depth cap reached" in line:
                report_data['deadlocks'].append(f"[{bot_name}:{line_num}] {line.strip()}")
            elif "deferred" in line.lower() or "blocked" in line.lower():
                 report_data['deferred_actions'].append(f"[{bot_name}:{line_num}] {line.strip()}")
                 
            # Extract basic performance mentions 
            if "CYCLE" in line and is_yesterday:
                 report_data['daily_cycles'][bot_name] += 1

def process_csv_file(filepath, report_data, yesterday_str):
    bot_name = os.path.basename(filepath)
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            headers = next(reader, None)
            if not headers: return

            time_col_idx = -1
            for i, h in enumerate(headers):
                if 'time' in h.lower() or 'date' in h.lower():
                    time_col_idx = i
                    break
            
            if time_col_idx == -1: time_col_idx = 0 

            for row in reader:
                if len(row) <= time_col_idx: continue
                dt = parse_datetime(row[time_col_idx])
                if not dt: continue
                
                date_str = dt.strftime("%Y-%m-%d")
                is_yesterday = (date_str == yesterday_str)

                if is_yesterday:
                    if len(row) > 8 and "FILL" in str(row).upper():
                        report_data['daily_fills'][bot_name] += 1
                    if "SL_APPLIED" in str(row) or "STOP" in str(row).upper():
                        report_data['daily_stops'][bot_name] += 1
                        
    except Exception as e:
        print(f"Error processing CSV {filepath}: {e}")

def generate_report():
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    report_data = {
        'errors': [],
        'warnings': [],
        'deadlocks': [],
        'deferred_actions': [],
        'daily_cycles': defaultdict(int),
        'daily_fills': defaultdict(int),
        'daily_stops': defaultdict(int)
    }

    print(f"Aggregating logs for report. Target 'Yesterday': {yesterday_str}")

    log_files = []
    csv_files = []
    for d in LOG_DIRS:
        if os.path.exists(d):
            log_files.extend(glob.glob(os.path.join(d, '*.log')))
            log_files.extend(glob.glob(os.path.join(d, '*.txt'))) 
            csv_files.extend(glob.glob(os.path.join(d, '*.csv')))

    for f in log_files:
        process_log_file(f, report_data, yesterday_str)
    for f in csv_files:
        process_csv_file(f, report_data, yesterday_str)

    with open(OUTPUT_REPORT_NAME, 'w', encoding='utf-8') as out:
        out.write("="*60 + "\n")
        out.write(f" AUTOMATED MT5 FRAMEWORK PERFORMANCE REPORT \n")
        out.write(f" Generated: {today.strftime('%Y-%m-%d %H:%M:%S')} \n")
        out.write(f" Target Date (Previous Day): {yesterday_str} \n")
        out.write("="*60 + "\n\n")

        out.write("--- 1. PREVIOUS DAY ACTIVITY SUMMARY ---\n")
        out.write("Cycles/Heartbeats Recorded Yesterday:\n")
        for bot, count in report_data['daily_cycles'].items():
            out.write(f"  - {bot}: {count} cycles\n")
        if not report_data['daily_cycles']: out.write("  None found.\n")

        out.write("\nTrade Fills Recorded Yesterday:\n")
        for bot, count in report_data['daily_fills'].items():
            out.write(f"  - {bot}: {count} fills\n")
        if not report_data['daily_fills']: out.write("  None found.\n")
        
        out.write("\nStops/SL Events Recorded Yesterday:\n")
        for bot, count in report_data['daily_stops'].items():
            out.write(f"  - {bot}: {count} events\n")
        if not report_data['daily_stops']: out.write("  None found.\n")

        out.write("\n--- 2. CRITICAL SYSTEM EVENTS (ALL TIME) ---\n")
        
        out.write(f"\nA. Critical Errors/Exceptions ({len(report_data['errors'])} found)\n")
        for err in report_data['errors'][-20:]: 
            out.write(f"  {err}\n")
            
        out.write(f"\nB. Grid Deadlocks ({len(report_data['deadlocks'])} found)\n")
        for dl in report_data['deadlocks'][-20:]:
            out.write(f"  {dl}\n")

        out.write(f"\nC. Deferred/Blocked Actions ({len(report_data['deferred_actions'])} found)\n")
        for da in report_data['deferred_actions'][-20:]:
            out.write(f"  {da}\n")

    print(f"Report successfully generated at: {OUTPUT_REPORT_NAME}")

if __name__ == '__main__':
    generate_report()