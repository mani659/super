#!/usr/bin/env python3
"""
extract_bot_logs.py — v2 (updated July 2026)
=============================================
Run from the Super/ project root:

    python extract_bot_logs.py
    python extract_bot_logs.py --days 7
    python extract_bot_logs.py --days 14 --out my_extract

Changes from v1:
- Added sniper_brain.log parsing (GRID TP/STOP/PROTECTOR, LEG_TP_SET,
  GridState reset, BE_LOCK, GHOST_CACHE_FIRE — these were the most
  important events and were missing entirely from v1)
- Added cab_watcher.log as a separate target (unified_runner.py routes
  CAB logs there, not to cab_production_v16.3.log, when running unified)
- Added magic isolation detail extraction from the structured CSV
- SuperTrend section now captures R-multiple from the correct log format
- Produces a machine-readable summary.json alongside the human summary.md
  so the next session can load numbers directly without re-parsing

Usage: stdlib only, no pip installs needed.
Outputs a log_extract/ folder + log_extract.zip — upload the zip.
"""

import argparse
import csv
import glob
import json
import os
import re
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ──────────────────────────────────────────────────────────────────────────────

TS_FORMATS = [
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S,%f",
    "%Y-%m-%d %H:%M:%S",
]

def parse_ts(raw: str):
    raw = (raw or "").strip()
    for fmt in TS_FORMATS:
        try:
            return datetime.strptime(raw[:len(fmt)+4], fmt)
        except ValueError:
            continue
    return None

def find_rotations(basepath: str):
    paths = []
    if os.path.isfile(basepath):
        paths.append(basepath)
    for i in range(1, 10):
        p = f"{basepath}.{i}"
        if os.path.isfile(p):
            paths.append(p)
    return paths

def iter_lines(paths):
    for p in paths:
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                for line in f:
                    yield line
        except Exception as e:
            print(f"  ! could not read {p}: {e}")

def iter_csv(paths):
    for p in paths:
        try:
            with open(p, encoding="utf-8", errors="replace", newline="") as f:
                for row in csv.DictReader(f):
                    yield row
        except Exception as e:
            print(f"  ! could not read {p}: {e}")

def line_ts(line: str):
    m = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[.,]\d+)", line)
    return parse_ts(m.group(1)) if m else None

def r_stats(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return {"n": 0}
    return {
        "n": len(vals),
        "avg": round(sum(vals)/len(vals), 4),
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
        "win_pct": round(100*sum(1 for v in vals if v > 0)/len(vals), 1),
    }

def num(x):
    if x is None:
        return 0.0
    x = str(x).replace(" ","").replace("\xa0","")
    try:
        return float(x)
    except:
        return 0.0

def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for row in rows:
            w.writerow(row)

# ──────────────────────────────────────────────────────────────────────────────
#  1. sniper_brain.log — GRID-LEVEL EVENTS (most important, was missing in v1)
# ──────────────────────────────────────────────────────────────────────────────

BRAIN_PATTERNS = {
    "GRID_TP":          re.compile(r"GRID TP \| R=([+-][\d.]+)"),
    "GRID_STOP":        re.compile(r"GRID STOP \| R=([+-][\d.]+)"),
    "GRID_PROTECTOR":   re.compile(r"GRID PROTECTOR \| ticket=(\d+) \| R=([+-][\d.]+)"),
    "GRID_STALE":       re.compile(r"GRID STALE_TIMEOUT"),
    "GRIDSTATE_RESET":  re.compile(r"GridState reset"),
    "LEG_ADDED":        re.compile(r"GRID: leg added ticket=(\d+)"),
    "DEPTH_CAP":        re.compile(r"GRID: depth cap reached"),
    "LEG_TP_SET":       re.compile(r"LEG_TP SET \| ticket=(\d+).*?tp_r=([\d.]+)R \(magic=(\d+)\)"),
    "BE_LOCK":          re.compile(r"BE_LOCK \| ticket=(\d+) magic=(\d+) \| R=([+-][\d.]+)"),
    "BE_LOCK_FAILED":   re.compile(r"BE_LOCK FAILED"),
    "GHOST_CACHE_FIRE": re.compile(r"GHOST_CACHE_FIRE magic=204 \| layer_depth=(\d+)"),
    "ARMED_UP":         re.compile(r"ARMED UP \|"),
    "ARMED_DN":         re.compile(r"ARMED DN \|"),
    "TREND_GONE_203":   re.compile(r"TREND_GONE_203 ticket=(\d+) R=([+-][\d.]+)"),
    "REAPER_203":       re.compile(r"REAPER_203 ticket=(\d+)"),
    "ATR_TRAIL_203":    re.compile(r"ATR_TRAIL_203 ticket=(\d+)"),
}

def process_brain_log(cutoff, outdir):
    paths = (find_rotations("logs/sniper_brain.log") +
             find_rotations("sniper_brain.log"))
    paths = list(dict.fromkeys(paths))  # deduplicate

    if not paths:
        return None, ["sniper_brain.log not found (checked logs/ and root)"]

    counts = Counter()
    grid_tp_r, grid_stop_r, protector_r, trend_gone_r = [], [], [], []
    layer_depths = []
    be_lock_magic = Counter()
    leg_tp_magic  = Counter()
    lines_total = lines_window = 0

    for line in iter_lines(paths):
        lines_total += 1
        ts = line_ts(line)
        if ts and ts < cutoff:
            continue
        lines_window += 1

        for name, pat in BRAIN_PATTERNS.items():
            m = pat.search(line)
            if not m:
                continue
            counts[name] += 1
            if name == "GRID_TP":
                grid_tp_r.append(float(m.group(1)))
            elif name == "GRID_STOP":
                grid_stop_r.append(float(m.group(1)))
            elif name == "GRID_PROTECTOR":
                protector_r.append(float(m.group(2)))
            elif name == "GHOST_CACHE_FIRE":
                layer_depths.append(int(m.group(1)))
            elif name == "BE_LOCK":
                be_lock_magic[m.group(2)] += 1
            elif name == "LEG_TP_SET":
                leg_tp_magic[m.group(3)] += 1
            elif name == "TREND_GONE_203":
                trend_gone_r.append(float(m.group(2)))
            break

    rows = [[k, v] for k, v in sorted(counts.items(), key=lambda x:-x[1])]
    write_csv(os.path.join(outdir, "brain_log_summary.csv"),
              ["event", "count"], rows)

    summary = {
        "lines_total": lines_total,
        "lines_window": lines_window,
        "event_counts": dict(counts),
        "grid_tp_r_stats": r_stats(grid_tp_r),
        "grid_stop_r_stats": r_stats(grid_stop_r),
        "protector_r_stats": r_stats(protector_r),
        "be_lock_by_magic": dict(be_lock_magic),
        "leg_tp_set_by_magic": dict(leg_tp_magic),
        "ghost_cache_layer_depths": layer_depths,
        "trend_gone_r_stats": r_stats(trend_gone_r),
        # derived signals for quick sanity checking
        "leg_tp_set_total": sum(leg_tp_magic.values()),
        "grid_exits_total": counts.get("GRID_TP", 0) + counts.get("GRID_STOP", 0),
        "grid_tp_rate": (
            round(counts.get("GRID_TP", 0) /
                  max(counts.get("GRID_TP", 0) + counts.get("GRID_STOP", 0), 1) * 100, 1)
            if counts.get("GRID_TP", 0) + counts.get("GRID_STOP", 0) > 0 else None
        ),
    }
    return summary, []


# ──────────────────────────────────────────────────────────────────────────────
#  2. unified_session_log.csv
# ──────────────────────────────────────────────────────────────────────────────

def process_unified_session(cutoff, outdir):
    paths = find_rotations("unified_session_log.csv")
    if not paths:
        return None, ["unified_session_log.csv not found"]

    by_bot_action = Counter()
    regime_counts = Counter()
    r_by_bot      = defaultdict(list)
    cb_trips      = []
    isolation_details = []
    rows_total = rows_window = 0

    for row in iter_csv(paths):
        rows_total += 1
        ts = parse_ts(row.get("timestamp",""))
        if ts and ts < cutoff:
            continue
        rows_window += 1

        bot    = row.get("bot","")
        action = row.get("action","")
        by_bot_action[(bot, action)] += 1

        if row.get("regime"):
            regime_counts[row["regime"]] += 1

        rm = row.get("r_multiple")
        if rm not in (None,""):
            try:
                r_by_bot[bot].append(float(rm))
            except ValueError:
                pass

        if action == "CIRCUIT_BREAKER_TRIPPED":
            cb_trips.append(row.get("timestamp",""))

        if action == "MAGIC_ISOLATION_BREACH_DETAIL":
            isolation_details.append({
                "ts": row.get("timestamp",""),
                "magic": row.get("magic",""),
                "symbol": row.get("symbol",""),
                "owners": row.get("regime",""),  # repurposed field
            })

    write_csv(os.path.join(outdir, "session_log_summary.csv"),
              ["bot","action","count"],
              [[b,a,c] for (b,a),c in sorted(by_bot_action.items(), key=lambda x:-x[1])])

    if isolation_details:
        write_csv(os.path.join(outdir, "isolation_breaches.csv"),
                  ["timestamp","magic","symbol","owners"],
                  [[d["ts"],d["magic"],d["symbol"],d["owners"]]
                   for d in isolation_details])

    summary = {
        "rows_total": rows_total,
        "rows_window": rows_window,
        "regime_counts": dict(regime_counts),
        "circuit_breaker_trips": cb_trips,
        "magic_isolation_breach_count": len(isolation_details),
        "isolation_details": isolation_details[:20],  # first 20 for summary
        "r_stats_by_bot": {b: r_stats(v) for b,v in r_by_bot.items()},
    }
    return summary, []


# ──────────────────────────────────────────────────────────────────────────────
#  3. sniper_v51_live_audit.csv — Ghost Hunter fills
# ──────────────────────────────────────────────────────────────────────────────

def process_ghost_audit(cutoff, outdir):
    paths = find_rotations("sniper_v51_live_audit.csv")
    if not paths:
        return None, ["sniper_v51_live_audit.csv not found"]

    events      = Counter()
    magic_fills = Counter()
    gate_blocks = Counter()
    sessions    = Counter()
    conv_by_magic = defaultdict(list)
    adx_by_magic  = defaultdict(list)
    rows_total = rows_window = 0

    for row in iter_csv(paths):
        rows_total += 1
        ts = parse_ts(row.get("timestamp",""))
        if ts and ts < cutoff:
            continue
        rows_window += 1

        evt = row.get("event_type","")
        events[evt] += 1
        if row.get("magic"):
            magic_fills[row["magic"]] += 1
        if row.get("session"):
            sessions[row["session"]] += 1
        if evt == "GATE_BLOCK" and row.get("magic"):
            gate_blocks[row["magic"]] += 1

        conv = row.get("conviction_at_fill")
        adx  = row.get("adx_at_fill")
        magic = row.get("magic","")
        if conv not in (None,""):
            try: conv_by_magic[magic].append(float(conv))
            except: pass
        if adx not in (None,""):
            try: adx_by_magic[magic].append(float(adx))
            except: pass

    write_csv(os.path.join(outdir, "ghost_audit_summary.csv"),
              ["event_type","count"],
              [[k,v] for k,v in sorted(events.items(), key=lambda x:-x[1])])

    summary = {
        "rows_total": rows_total,
        "rows_window": rows_window,
        "fills_by_magic": dict(magic_fills),
        "gate_blocks_by_magic": dict(gate_blocks),
        "sessions": dict(sessions),
        "conviction_at_fill_by_magic": {m: r_stats(v) for m,v in conv_by_magic.items()},
        "adx_at_fill_by_magic": {m: r_stats(v) for m,v in adx_by_magic.items()},
        "no_sl_fills": events.get("ORDER_FILL_V51_NO_SL", 0),
        "total_fills": events.get("ORDER_FILL_V51", 0),
        "no_sl_rate_pct": round(
            events.get("ORDER_FILL_V51_NO_SL",0) /
            max(events.get("ORDER_FILL_V51",0)+events.get("ORDER_FILL_V51_NO_SL",0),1)*100, 1
        ),
    }
    return summary, []


# ──────────────────────────────────────────────────────────────────────────────
#  4. sniper_conviction_log.csv — Ghost Watcher management actions
# ──────────────────────────────────────────────────────────────────────────────

def process_ghost_conviction(cutoff, outdir):
    paths = find_rotations("sniper_conviction_log.csv")
    if not paths:
        return None, ["sniper_conviction_log.csv not found"]

    actions   = Counter()
    exit_rsns = Counter()
    regimes   = Counter()
    r_by_magic = defaultdict(list)
    rows_total = rows_window = 0

    for row in iter_csv(paths):
        rows_total += 1
        ts = parse_ts(row.get("timestamp",""))
        if ts and ts < cutoff:
            continue
        rows_window += 1

        action = row.get("brain_action","")
        if action:
            actions[action] += 1
        if row.get("exit_reason"):
            exit_rsns[row["exit_reason"]] += 1
        if row.get("regime"):
            regimes[row["regime"]] += 1
        if action and action not in ("IDLE","WATCH","GRID_MANAGED"):
            rm = row.get("r_multiple")
            if rm not in (None,""):
                try:
                    r_by_magic[row.get("magic","")].append(float(rm))
                except: pass

    write_csv(os.path.join(outdir, "ghost_conviction_summary.csv"),
              ["brain_action","count"],
              [[k,v] for k,v in sorted(actions.items(), key=lambda x:-x[1])])

    summary = {
        "rows_total": rows_total,
        "rows_window": rows_window,
        "action_counts": dict(actions),
        "exit_reasons": dict(exit_rsns),
        "regime_counts": dict(regimes),
        "r_stats_at_management_action": {m: r_stats(v) for m,v in r_by_magic.items()},
    }
    return summary, []


# ──────────────────────────────────────────────────────────────────────────────
#  5. CAB logs — cab_production_v16.3.log + logs/cab_watcher.log
# ──────────────────────────────────────────────────────────────────────────────

CAB_PATTERNS = {
    "REAPER_FIRED":       re.compile(r"REAPER FIRED #(\d+) \| R=([+-][\d.]+) \| SI=([\d.]+)"),
    "REAPER_BLOCKED":     re.compile(r"REAPER BLOCKED #(\d+)"),
    "PROTECTOR_FIRED":    re.compile(r"PROTECTOR FIRED #(\d+) \| R=([+-][\d.]+)"),
    "HARVESTER_PARTIAL":  re.compile(r"HARVESTER PARTIAL #(\d+).*?R=([+-][\d.]+)"),
    "HARVESTER_FULL":     re.compile(r"HARVESTER FULL #(\d+) \| R=([+-][\d.]+)"),
    "CLOSE_DEFERRED":     re.compile(r"Close DEFERRED #(\d+)"),
    "CLOSE_FAILED":       re.compile(r"Close FAILED #(\d+)"),
    "SL_MODIFY_FAILED":   re.compile(r"SL modify FAILED #(\d+)"),
    "ORDER_FAILED":       re.compile(r"ORDER FAILED \|"),
    "RETRY_GAVE_UP":      re.compile(r"giving up on this bar"),
    "REGIME_COMPUTED":    re.compile(r"-- REGIME\[([^\]]+)\]: (\w+)"),
}

def process_cab_log(cutoff, outdir):
    paths = find_rotations("logs/cab_watcher.log")
    paths = list(dict.fromkeys(paths))
    if not paths:
        return None, ["logs/cab_watcher.log not found"]

    counts   = Counter()
    reaper_r = []
    harv_r   = []
    prot_r   = []
    regime_by_symbol = defaultdict(Counter)
    lines_total = lines_window = 0

    for line in iter_lines(paths):
        lines_total += 1
        ts = line_ts(line)
        if ts and ts < cutoff:
            continue
        lines_window += 1

        for name, pat in CAB_PATTERNS.items():
            m = pat.search(line)
            if not m:
                continue
            counts[name] += 1
            if name == "REAPER_FIRED":
                reaper_r.append(float(m.group(2)))
            elif name == "PROTECTOR_FIRED":
                prot_r.append(float(m.group(2)))
            elif name in ("HARVESTER_PARTIAL","HARVESTER_FULL"):
                harv_r.append(float(m.group(2)))
            elif name == "REGIME_COMPUTED":
                regime_by_symbol[m.group(1)][m.group(2)] += 1
            break

    write_csv(os.path.join(outdir, "cab_summary.csv"),
              ["event","count"],
              [[k,v] for k,v in sorted(counts.items(), key=lambda x:-x[1])])

    summary = {
        "lines_total": lines_total,
        "lines_window": lines_window,
        "event_counts": dict(counts),
        "regime_by_symbol": {s: dict(c) for s,c in regime_by_symbol.items()},
        "reaper_r_stats": r_stats(reaper_r),
        "protector_r_stats": r_stats(prot_r),
        "harvester_r_stats": r_stats(harv_r),
        "reaper_false_cut_rate_note": (
            "Cannot compute without closed-trade P&L — use MT5 trade history export"
        ),
    }
    return summary, []


# ──────────────────────────────────────────────────────────────────────────────
#  6. SuperTrend per-symbol logs
# ──────────────────────────────────────────────────────────────────────────────

ST_PATTERNS = {
    "ENTRY":           re.compile(r"(BUY|SELL) ENTRY \|"),
    "CLOSE_DEAD":      re.compile(r"DEAD\|"),
    "CLOSE_DECAYING":  re.compile(r"DECAYING_TIMEOUT"),
    "R1_BE_LOCK":      re.compile(r"R1_BE_LOCK"),
    "R2_LOCK_1R":      re.compile(r"R2_LOCK_1R"),
    "R3_LOCK_2R":      re.compile(r"R3_LOCK_2R"),
    "PARTIAL_CLOSE":   re.compile(r"PARTIAL CLOSE #\d+ \|"),
    "SESSION_BLOCK":   re.compile(r"Entry BLOCKED by session gate"),
    "EQUITY_FILTER":   re.compile(r"EQUITY FILTER ACTIVE"),
}
ST_CLOSE_R = re.compile(r"R=([+-]?[\d.]+) \| SI@close=")

def process_supertrend(cutoff, outdir):
    files = sorted(glob.glob("logs/supertrend_*.log"))
    if not files:
        return None, ["logs/supertrend_*.log not found"]

    per_sym = {}
    for path in files:
        sym = os.path.basename(path).replace("supertrend_","").replace(".log","")
        if sym == "runner":
            continue
        paths = find_rotations(path)
        counts  = Counter()
        r_vals  = []
        lines_total = lines_window = 0

        for line in iter_lines(paths):
            lines_total += 1
            ts = line_ts(line)
            if ts and ts < cutoff:
                continue
            lines_window += 1
            for name, pat in ST_PATTERNS.items():
                if pat.search(line):
                    counts[name] += 1
            m = ST_CLOSE_R.search(line)
            if m:
                r_vals.append(float(m.group(1)))

        per_sym[sym] = {
            "lines_window": lines_window,
            "event_counts": dict(counts),
            "r_stats": r_stats(r_vals),
        }

    rows = []
    for sym, d in per_sym.items():
        for evt, n in d["event_counts"].items():
            rows.append([sym, evt, n])
    write_csv(os.path.join(outdir,"supertrend_summary.csv"),
              ["symbol","event","count"], rows)

    return per_sym, []


# ──────────────────────────────────────────────────────────────────────────────
#  7. Runner health — unified_runner.log
# ──────────────────────────────────────────────────────────────────────────────

RUNNER_PATTERNS = {
    "HEARTBEAT_OK":          re.compile(r"Heartbeat OK"),
    "MAGIC_ISOLATION_BREACH":re.compile(r"MAGIC ISOLATION BREACH"),
    "CIRCUIT_BREAKER_TRIPPED":re.compile(r"CIRCUIT BREAKER TRIPPED"),
    "DEAD_THREADS":          re.compile(r"DEAD THREADS"),
    "MT5_RECONNECT_FAILED":  re.compile(r"reconnect FAILED|could not be restored"),
    "IPC_FAILURE_RECONNECT": re.compile(r"forcing reconnect"),
    "THREAD_STARTED":        re.compile(r"Thread started:"),
    "RUNNER_START":          re.compile(r"RUNNER_START"),
    "SWITCH_LOADED":         re.compile(r"load_switches"),
}

def process_runner_health(cutoff, outdir):
    paths = find_rotations("logs/unified_runner.log")
    if not paths:
        return None, ["logs/unified_runner.log not found"]

    counts = Counter()
    first_hb = last_hb = None
    start_times = []
    lines_total = lines_window = 0

    for line in iter_lines(paths):
        lines_total += 1
        ts = line_ts(line)
        if ts and ts < cutoff:
            continue
        lines_window += 1

        for name, pat in RUNNER_PATTERNS.items():
            if pat.search(line):
                counts[name] += 1
                if name == "HEARTBEAT_OK" and ts:
                    if first_hb is None: first_hb = ts
                    last_hb = ts
                if name == "RUNNER_START" and ts:
                    start_times.append(str(ts))
                break

    with open(os.path.join(outdir,"runner_health.md"),"w",encoding="utf-8") as f:
        f.write("# Runner health\n\n")
        for name, n in sorted(counts.items(), key=lambda x:-x[1]):
            f.write(f"- **{name}**: {n}\n")
        if first_hb and last_hb:
            span_h = (last_hb - first_hb).total_seconds() / 3600
            f.write(f"\nHeartbeat span: {first_hb} → {last_hb} ({span_h:.1f}h, {counts.get('HEARTBEAT_OK',0)} beats)\n")
        if start_times:
            f.write(f"\nProcess starts in window: {len(start_times)}\n")
            for s in start_times:
                f.write(f"  - {s}\n")

    return dict(counts), []


# ──────────────────────────────────────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Extract and summarise bot logs for review")
    ap.add_argument("--days", type=int, default=7, help="Trailing days to include (default 7)")
    ap.add_argument("--out",  default="log_extract", help="Output folder name")
    args = ap.parse_args()

    cutoff = datetime.now() - timedelta(days=args.days)
    outdir = args.out
    os.makedirs(outdir, exist_ok=True)

    print(f"Extracting last {args.days} days (cutoff: {cutoff:%Y-%m-%d %H:%M})")
    print(f"Output: {outdir}/\n")

    missing = []
    results = {}

    print("[1/7] sniper_brain.log (grid events — was missing in v1) ...")
    results["brain"], notes = process_brain_log(cutoff, outdir)
    missing += notes

    print("[2/7] unified_session_log.csv ...")
    results["session"], notes = process_unified_session(cutoff, outdir)
    missing += notes

    print("[3/7] sniper_v51_live_audit.csv (Ghost Hunter fills) ...")
    results["ghost_audit"], notes = process_ghost_audit(cutoff, outdir)
    missing += notes

    print("[4/7] sniper_conviction_log.csv (Ghost Watcher actions) ...")
    results["ghost_conviction"], notes = process_ghost_conviction(cutoff, outdir)
    missing += notes

    print("[5/7] CAB logs ...")
    results["cab"], notes = process_cab_log(cutoff, outdir)
    missing += notes

    print("[6/7] SuperTrend per-symbol logs ...")
    results["supertrend"], notes = process_supertrend(cutoff, outdir)
    missing += notes

    print("[7/7] Runner health (unified_runner.log) ...")
    results["runner"], notes = process_runner_health(cutoff, outdir)
    missing += notes

    # ── machine-readable JSON ──────────────────────────────────────────────
    with open(os.path.join(outdir,"summary.json"),"w",encoding="utf-8") as f:
        json.dump({"cutoff": str(cutoff), "days": args.days, **results},
                  f, indent=2, default=str)

    # ── human summary.md ──────────────────────────────────────────────────
    with open(os.path.join(outdir,"summary.md"),"w",encoding="utf-8") as f:
        f.write(f"# Bot log extract — trailing {args.days} days\n")
        f.write(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        f.write(f"Cutoff: {cutoff:%Y-%m-%d %H:%M:%S}\n\n")

        if missing:
            f.write("## Files not found\n")
            for m in missing:
                f.write(f"- {m}\n")
            f.write("\n")

        b = results.get("brain")
        f.write("## Ghost Grid — brain log (grid-level events)\n")
        if b:
            ec = b["event_counts"]
            f.write(f"- Lines in window: {b['lines_window']:,} / {b['lines_total']:,} total\n")
            f.write(f"- **LEG_TP_SET: {b['leg_tp_set_total']}** (should track ~1:1 with fills)\n")
            f.write(f"- **GRID TP fired: {ec.get('GRID_TP',0)}** | GRID STOP: {ec.get('GRID_STOP',0)}\n")
            f.write(f"- GridState reset: {ec.get('GRIDSTATE_RESET',0)} | Stale timeout: {ec.get('GRID_STALE',0)}\n")
            f.write(f"- GRID_PROTECTOR: {ec.get('GRID_PROTECTOR',0)} | Depth cap refused: {ec.get('DEPTH_CAP',0):,}\n")
            f.write(f"- BE_LOCK fires: {sum(b['be_lock_by_magic'].values())} by magic: {b['be_lock_by_magic']}\n")
            f.write(f"- GHOST_CACHE_FIRE (204): {ec.get('GHOST_CACHE_FIRE',0)} | layer depths: {b['ghost_cache_layer_depths'][:10]}\n")
            f.write(f"- ARMED UP: {ec.get('ARMED_UP',0)} | ARMED DN: {ec.get('ARMED_DN',0)}\n")
            f.write(f"- Grid TP R stats: {b['grid_tp_r_stats']}\n")
            f.write(f"- Grid Stop R stats: {b['grid_stop_r_stats']}\n")
        f.write("\n")

        ga = results.get("ghost_audit")
        f.write("## Ghost Hunter fills\n")
        if ga:
            f.write(f"- Fills by magic: {ga['fills_by_magic']}\n")
            f.write(f"- No-SL fill rate: {ga['no_sl_rate_pct']}% ({ga['no_sl_fills']} / {ga['total_fills']+ga['no_sl_fills']} fills)\n")
            f.write(f"- Gate blocks by magic: {ga['gate_blocks_by_magic']}\n")
            f.write(f"- Session distribution: {ga['sessions']}\n")
            f.write(f"- Conviction@fill by magic: {ga['conviction_at_fill_by_magic']}\n")
        f.write("\n")

        gc = results.get("ghost_conviction")
        f.write("## Ghost Watcher management actions\n")
        if gc:
            f.write(f"- Action counts: {gc['action_counts']}\n")
            f.write(f"- Exit reasons: {gc['exit_reasons']}\n")
        f.write("\n")

        cab = results.get("cab")
        f.write("## CAB Watcher\n")
        if cab:
            ec = cab["event_counts"]
            f.write(f"- Lines in window: {cab['lines_window']:,} / {cab['lines_total']:,}\n")
            f.write(f"- PROTECTOR fired: {ec.get('PROTECTOR_FIRED',0)} | R stats: {cab['protector_r_stats']}\n")
            f.write(f"- HARVESTER (partial+full): {ec.get('HARVESTER_PARTIAL',0)+ec.get('HARVESTER_FULL',0)} | R stats: {cab['harvester_r_stats']}\n")
            f.write(f"- REAPER fired: {ec.get('REAPER_FIRED',0)} | blocked: {ec.get('REAPER_BLOCKED',0)} | R stats: {cab['reaper_r_stats']}\n")
            f.write(f"- ORDER_FAILED: {ec.get('ORDER_FAILED',0)} | retry gave up: {ec.get('RETRY_GAVE_UP',0)}\n")
            f.write(f"- Close deferred: {ec.get('CLOSE_DEFERRED',0)} | Close failed: {ec.get('CLOSE_FAILED',0)}\n")
            f.write(f"- Regime by symbol: {cab['regime_by_symbol']}\n")
        f.write("\n")

        st = results.get("supertrend")
        f.write("## SuperTrend (per symbol)\n")
        if st:
            for sym, d in st.items():
                f.write(f"- **{sym}**: lines={d['lines_window']:,} | "
                        f"entries={d['event_counts'].get('ENTRY',0)} | "
                        f"R_stats={d['r_stats']} | "
                        f"events={d['event_counts']}\n")
        f.write("\n")

        sess = results.get("session")
        f.write("## Unified session log\n")
        if sess:
            f.write(f"- Rows in window: {sess['rows_window']:,} / {sess['rows_total']:,}\n")
            f.write(f"- Circuit breaker trips: {len(sess['circuit_breaker_trips'])} | times: {sess['circuit_breaker_trips']}\n")
            f.write(f"- Magic isolation breaches: {sess['magic_isolation_breach_count']}\n")
            if sess["isolation_details"]:
                f.write(f"- Isolation detail (first 5): {sess['isolation_details'][:5]}\n")
            f.write(f"- Regime distribution: {sess['regime_counts']}\n")
        f.write("\n")

        rn = results.get("runner")
        f.write("## Runner health\n")
        if rn:
            for k, v in rn.items():
                f.write(f"- {k}: {v}\n")
        f.write("\n")

    # ── zip ──────────────────────────────────────────────────────────────
    zip_path = f"{outdir}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(outdir):
            for fn in files:
                full = os.path.join(root, fn)
                zf.write(full, os.path.relpath(full, outdir))

    size_kb = os.path.getsize(zip_path) / 1024
    print(f"\nDone.")
    print(f"Upload: {zip_path}  ({size_kb:.1f} KB)")
    print(f"Preview: {outdir}/summary.md")
    print(f"\nQuick sanity check from summary.md:")
    print(f"  LEG_TP_SET total should be >> 8 (was 8 in entire 5-week Week-1 run)")
    print(f"  GRID TP/STOP total should be > 0 (was 0 across all prior logs)")
    print(f"  GHOST_CACHE_FIRE count should be > 0 (was 0 — 204 never wired before)")
    print(f"  CAB PROTECTOR/HARVESTER should appear for non-XAUUSDm symbols")


if __name__ == "__main__":
    main()
